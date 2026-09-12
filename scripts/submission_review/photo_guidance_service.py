"""Authorized, bounded local photo guidance; no extraction jobs or writes.

The browser names evidence, not URLs. The existing reviewer API authorizes
both reads of its current manifest. Images live only in memory and a bounded
child process, so an OCR failure cannot wedge the reviewer HTTP process.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from threading import BoundedSemaphore
from urllib.parse import parse_qs, urlparse

from .extraction.bounded_http import request as bounded_request, TransportError
from .extraction.envelope import PHOTO_ROLES, _UUID, _SHA256
from .extraction.extractor import EvidencePhoto
from .extraction.photo_prep import MAX_SOURCE_BYTES

OCR_TIMEOUT_SECONDS = 45
GUIDANCE_TIMEOUT_SECONDS = 90
MAX_REPORT_BYTES = 32 * 1024
_ACTIVE = BoundedSemaphore(1)
_PROCESS_SLOT = BoundedSemaphore(1)
_REQUEST_KEYS = {"submission_id", "photo_id", "evidence_revision", "evidence_manifest_sha256"}


class GuidanceError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def validate_submission_photo_url(value: object, supabase_url: str) -> str:
    """The shared photo-access allowlist, also used by the lightbox proxy."""
    raw = str(value or "").strip()
    source = urlparse(raw)
    project = urlparse(supabase_url)
    prefix = "/storage/v1/object/sign/product-submission-photos/"
    query = parse_qs(source.query, keep_blank_values=True)
    if (source.scheme != "https" or source.netloc != project.netloc
            or source.username is not None or source.password is not None
            or not source.path.startswith(prefix) or source.path == prefix
            or source.fragment or set(query) != {"token"}
            or len(query["token"]) != 1 or not query["token"][0]):
        raise ValueError("invalid submission photo URL")
    return raw


def execute_photo_guidance(payload, authorization, project_url, anon_key) -> dict:
    """Hard deadline around DNS, both authorization reads, download and OCR.

    A socket timeout cannot bound OS DNS resolution. The outer process owns
    the whole operation; killing it releases the sole guidance slot without
    leaving a network thread or nested OCR child behind.
    """
    _validate_request(payload)
    if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
        raise GuidanceError(401, "Reviewer sign-in required.")
    if not _PROCESS_SLOT.acquire(blocking=False):
        raise GuidanceError(429, "Another photo is being checked. Please try again shortly.")
    try:
        wire = json.dumps({"selection": payload, "authorization": authorization,
                           "project_url": project_url, "anon_key": anon_key}).encode()
        if len(wire) > 16 * 1024:
            raise GuidanceError(400, "Invalid photo selection.")
        result = subprocess.run(
            [sys.executable, "-m", "submission_review.photo_guidance_service", "--authorized"],
            cwd=Path(__file__).resolve().parents[1], input=wire,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=GUIDANCE_TIMEOUT_SECONDS,
            env={"PATH": os.defpath, "PYTHONNOUSERSITE": "1", "OMP_NUM_THREADS": "1"},
            check=False,
        )
        if result.returncode != 0 or len(result.stdout) > MAX_REPORT_BYTES:
            raise ValueError()
        output = json.loads(result.stdout)
        if "error" in output:
            raise GuidanceError(output["status"], output["error"])
        report = output["report"]
        if not isinstance(report, dict):
            raise ValueError()
        return report
    except GuidanceError:
        raise
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        raise GuidanceError(503, "Photo guidance unavailable. You can still review the photos manually.") from None
    finally:
        _PROCESS_SLOT.release()


def _validate_request(value: object) -> dict:
    if not isinstance(value, dict) or set(value) != _REQUEST_KEYS:
        raise GuidanceError(400, "Select a submission photo to check.")
    if (not all(isinstance(value[key], str) and _UUID.fullmatch(value[key])
                for key in ("submission_id", "photo_id"))
            or type(value["evidence_revision"]) is not int or value["evidence_revision"] < 1
            or not isinstance(value["evidence_manifest_sha256"], str)
            or not _SHA256.fullmatch(value["evidence_manifest_sha256"])):
        raise GuidanceError(400, "Invalid evidence selection.")
    return value


def _bound_photo(row: object, selection: dict) -> dict:
    if (not isinstance(row, dict) or row.get("id") != selection["submission_id"]
            or type(row.get("evidence_revision")) is not int
            or row["evidence_revision"] != selection["evidence_revision"]
            or row.get("evidence_manifest_sha256") != selection["evidence_manifest_sha256"]):
        raise GuidanceError(409, "Photos changed. Reload this submission before checking.")
    photos = row.get("photos")
    if not isinstance(photos, list):
        raise GuidanceError(503, "Photo guidance unavailable.")
    matches = [p for p in photos if isinstance(p, dict) and p.get("photo_id") == selection["photo_id"]]
    if len(matches) != 1:
        raise GuidanceError(409, "This photo is no longer in the current evidence.")
    photo = matches[0]
    if (not isinstance(photo.get("content_sha256"), str)
            or not _SHA256.fullmatch(photo["content_sha256"])
            or not isinstance(photo.get("categories"), list)
            or not all(isinstance(role, str) and role in PHOTO_ROLES for role in photo["categories"])
            or len(photo["categories"]) > len(PHOTO_ROLES)):
        raise GuidanceError(503, "Photo guidance unavailable.")
    return photo


def review_photo_guidance(payload, authorization, project_url, anon_key,
                          validate_photo_url, *, transport=None, runner=None) -> dict:
    selection = _validate_request(payload)
    if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
        raise GuidanceError(401, "Reviewer sign-in required.")
    transport = transport or bounded_request
    runner = runner or run_photo_guidance

    def current_photo():
        response = transport("POST", project_url.rstrip("/") + "/functions/v1/review-product-submissions",
                             timeout=20, max_bytes=2 * 1024 * 1024,
                             headers={"authorization": authorization, "apikey": anon_key},
                             body={"action": "list", "submission_id": selection["submission_id"], "limit": 1})
        if response.status_code in (401, 403):
            raise GuidanceError(response.status_code, "Reviewer access could not be confirmed. Sign in again.")
        if response.status_code != 200:
            raise GuidanceError(503, "Photo guidance unavailable.")
        result = json.loads(response.content)
        rows = result.get("submissions") if isinstance(result, dict) else None
        if not isinstance(rows, list) or len(rows) != 1:
            raise GuidanceError(409, "Submission unavailable. Reload the queue.")
        return _bound_photo(rows[0], selection)

    if not _ACTIVE.acquire(blocking=False):
        raise GuidanceError(429, "Another photo is being checked. Please try again shortly.")
    try:
        photo = current_photo()  # Server authorizes before any image is read.
        url = validate_photo_url(photo.get("signed_url"), project_url)
        response = transport("GET", url, timeout=20, max_bytes=MAX_SOURCE_BYTES)
        if response.status_code != 200 or len(response.content) > MAX_SOURCE_BYTES:
            raise GuidanceError(503, "Photo could not be read. Please reload and retry.")
        digest = photo["content_sha256"]
        if hashlib.sha256(response.content).hexdigest() != digest:
            raise GuidanceError(409, "Photo does not match the current evidence.")
        evidence = EvidencePhoto(photo_id=photo["photo_id"], sha256=digest,
                                 categories=tuple(photo["categories"]))
        report = runner(evidence, response.content)
        fresh = current_photo()  # A replaced/revoked photo cannot get a late hint.
        if fresh["content_sha256"] != digest or fresh["categories"] != photo["categories"]:
            raise GuidanceError(409, "Photos changed. Reload this submission before checking.")
        return {**report, **selection, "photo_sha256": digest}
    except GuidanceError:
        raise
    except (TransportError, ValueError, TypeError, KeyError, OSError, subprocess.SubprocessError):
        raise GuidanceError(503, "Photo guidance unavailable. You can still review the photos manually.") from None
    finally:
        _ACTIVE.release()


def run_photo_guidance(photo: EvidencePhoto, raw: bytes) -> dict:
    """One fixed local program; no photos on disk, inherited secrets or logs."""
    metadata = json.dumps({"photo_id": photo.photo_id, "sha256": photo.sha256,
                           "categories": list(photo.categories)})
    result = subprocess.run(
        [sys.executable, "-m", "submission_review.photo_guidance_service", metadata],
        cwd=Path(__file__).resolve().parents[1], input=raw,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=OCR_TIMEOUT_SECONDS,
        env={"PATH": os.defpath, "PYTHONNOUSERSITE": "1", "OMP_NUM_THREADS": "1"},
        check=False,
    )
    # Child redirects all engine output and writes only a capped protocol message.
    if result.returncode != 0 or len(result.stdout) > MAX_REPORT_BYTES:
        raise GuidanceError(503, "Photo guidance unavailable. You can still review the photos manually.")
    report = json.loads(result.stdout)
    if not isinstance(report, dict) or report.get("status") not in {"suggestions", "unknown", "unreadable"}:
        raise GuidanceError(503, "Photo guidance unavailable.")
    return report


def _main() -> int:
    # Some native OCR runtimes print banners to fd 1, not Python's stdout.
    # Keep a private protocol fd and discard engine output before importing it.
    protocol = os.dup(1)
    with open(os.devnull, "wb") as sink:
        os.dup2(sink.fileno(), 1)
        os.dup2(sink.fileno(), 2)
    try:
        if sys.argv[1] == "--authorized":
            message = json.loads(sys.stdin.buffer.read(16 * 1024 + 1))
            try:
                report = {"report": review_photo_guidance(
                    message["selection"], message["authorization"], message["project_url"],
                    message["anon_key"], validate_submission_photo_url, runner=_read_photo,
                )}
            except GuidanceError as error:
                report = {"error": str(error), "status": error.status}
        else:
            metadata = json.loads(sys.argv[1])
            photo = EvidencePhoto(metadata["photo_id"], metadata["sha256"],
                                  categories=tuple(metadata["categories"]))
            report = _read_photo(photo, sys.stdin.buffer.read(MAX_SOURCE_BYTES + 1))
        wire = json.dumps(report, allow_nan=False).encode()
        if len(wire) > MAX_REPORT_BYTES:
            return 2
        with os.fdopen(protocol, "wb") as output:
            output.write(wire)
        return 0
    except Exception:
        return 2


def _read_photo(photo: EvidencePhoto, raw: bytes) -> dict:
    from .extraction.adapters.rapidocr_reader import RapidOcrReader
    from .extraction.extractor import EvidenceBundle
    from .extraction.photo_prep import prepare_bundle
    from .extraction.photo_guidance import guidance_for_page
    prepared = prepare_bundle(EvidenceBundle("guidance", 1, (photo,)),
                              reader=lambda _: raw).photos[0]
    page = RapidOcrReader().read(prepared.data, photo_id=photo.photo_id, input_id=prepared.input_id)
    report = guidance_for_page(page, declared=photo.categories)
    report["prepared_sha256"] = prepared.sent_sha256
    return report


if __name__ == "__main__":
    raise SystemExit(_main())
