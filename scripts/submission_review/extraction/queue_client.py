"""The authenticated queue client: how a worker actually reaches the database.

A worker signs in as its own account. It never uses the service role, never
borrows a reviewer's session. Queue operations use worker RPCs; photo downloads
use the worker-scoped Storage policy, so the database
stays the only place that decides what this machine may see or do.

Everything crossing the network here is bounded. Requests have deadlines,
responses have size ceilings, and fetched evidence lands in a private temporary
directory that is removed even when a job fails.
"""

from __future__ import annotations

import contextlib
import base64
import json
import os
import shutil
import tempfile
import time
import re
from urllib.parse import quote, urlsplit
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .extractor import (
    EvidenceBundle,
    EvidencePhoto,
    ExtractionConfig,
    ExtractionError,
)
from .bounded_http import request, TransportError
from .photo_prep import MAX_SOURCE_BYTES
from .worker import LeaseLostError, LeasedJob

#: One RPC should answer quickly; a hung call must not hold a lease open.
DEFAULT_TIMEOUT_SECONDS = 20.0
#: A leased manifest is a handful of small rows.
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
#: Matches the app's upload ceiling; anything larger did not come from us.
MAX_PHOTO_BYTES = MAX_SOURCE_BYTES
PHOTO_BUCKET = "product-submission-photos"


class QueueConfigurationError(RuntimeError):
    """The worker is not configured to reach the queue at all."""


@dataclass(frozen=True)
class WorkerCredentials:
    """Where the worker's own identity comes from.

    Deliberately not the service key. A worker that held the service role could
    read every user's photos and write anything; the whole point of a machine
    account is that the database can refuse it.
    """

    url: str
    anon_key: str
    email: str
    password: str

    def __post_init__(self):
        try:
            url = urlsplit(self.url)
            if (url.scheme not in {"http", "https"} or not url.hostname or url.username
                    or url.password or url.query or url.fragment or url.path not in {"", "/"}
                    or (url.scheme == "http" and url.hostname not in {"127.0.0.1", "::1", "localhost"})):
                raise ValueError()
            if not self.anon_key.startswith("sb_publishable_"):
                parts = self.anon_key.split(".")
                if len(parts) != 3:
                    raise ValueError()
                claims = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))
                if claims.get("role") != "anon":
                    raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise QueueConfigurationError("worker requires an HTTPS project URL and a public, non-admin API key") from None

    @classmethod
    def from_environment(cls, env: dict[str, str] | None = None) -> "WorkerCredentials":
        source = env if env is not None else os.environ
        url = (source.get("SUPABASE_URL") or "").rstrip("/")
        anon_key = (
            source.get("SUPABASE_PUBLISHABLE_KEY")
            or source.get("SUPABASE_ANON_KEY")
            or ""
        ).strip()
        email = (source.get("EXTRACTION_WORKER_EMAIL") or "").strip()
        password = source.get("EXTRACTION_WORKER_PASSWORD") or ""
        missing = [
            name
            for name, value in (
                ("SUPABASE_URL", url),
                ("SUPABASE_PUBLISHABLE_KEY or SUPABASE_ANON_KEY", anon_key),
                ("EXTRACTION_WORKER_EMAIL", email),
                ("EXTRACTION_WORKER_PASSWORD", password),
            )
            if not value
        ]
        if missing:
            raise QueueConfigurationError(
                "the extraction worker needs its own account: missing "
                + ", ".join(missing)
            )
        for forbidden in ("SUPABASE_SECRET_KEY", "SUPABASE_SERVICE_ROLE_KEY"):
            if (source.get(forbidden) or "").strip():
                # Present in the environment is not the same as used, but a
                # runner that can reach the service key is one edit away from
                # using it. Fail loudly rather than rely on discipline.
                raise QueueConfigurationError(
                    f"{forbidden} must not be in the worker's environment"
                )
        return cls(url=url, anon_key=anon_key, email=email, password=password)


class SupabaseExtractionQueue:
    """`ExtractionQueue` over the worker's own authenticated session."""

    def __init__(
        self,
        credentials: WorkerCredentials,
        *,
        transport=None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        workspace: Path | None = None,
        attempt_journal: Path | None = None,
    ) -> None:
        self._credentials = credentials
        self._timeout = timeout
        self._transport = transport or _RequestsTransport()
        self._access_token: str | None = None
        self._workspace = workspace
        self._leases: dict[str, Path] = {}
        self._token_expires = 0.0
        self._photo_sources: dict[str, tuple[str, str, EvidencePhoto]] = {}
        self._attempt_journal = attempt_journal
        if attempt_journal is not None:
            attempt_journal.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            descriptor = os.open(attempt_journal, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            os.fchmod(descriptor, 0o600)
            os.close(descriptor)

    # -- session ---------------------------------------------------------

    def sign_in(self) -> None:
        """Exchange the worker's own credentials for a short-lived session."""
        payload = self._transport.post_json(
            f"{self._credentials.url}/auth/v1/token?grant_type=password",
            headers={
                "apikey": self._credentials.anon_key,
                "Content-Type": "application/json",
            },
            body={
                "email": self._credentials.email,
                "password": self._credentials.password,
            },
            timeout=self._timeout,
        )
        token = (payload or {}).get("access_token")
        if not isinstance(token, str) or not token:
            raise QueueConfigurationError("the worker account could not sign in")
        self._access_token = token
        self._token_expires = time.monotonic() + max(1, float(payload.get("expires_in", 3600)) - 60)

    def _headers(self) -> dict[str, str]:
        if not self._access_token or time.monotonic() >= self._token_expires:
            self.sign_in()
        return {
            "apikey": self._credentials.anon_key,
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    def _rpc(self, name: str, body: dict[str, Any] | None = None) -> Any:
        return self._transport.post_json(
            f"{self._credentials.url}/rest/v1/rpc/{name}",
            headers=self._headers(),
            body=body or {},
            timeout=self._timeout,
        )

    # -- ExtractionQueue -------------------------------------------------

    def claim(self, limit: int) -> list[LeasedJob]:
        rows = self._rpc(
            "claim_product_submission_extraction_jobs", {"p_limit": int(limit)}
        )
        if not isinstance(rows, list):
            raise ExtractionError("unsupported_evidence", "invalid claim response")
        jobs: list[LeasedJob] = []
        for row in rows:
            job = self._build_job(row)
            if job is not None:
                jobs.append(job)
        return jobs

    def heartbeat(self, job_id: str, fencing_token: int) -> None:
        try:
            self._rpc(
                "heartbeat_product_submission_extraction_job",
                {"p_job_id": job_id, "p_fencing_token": int(fencing_token)},
            )
        except _RpcRejected as rejected:
            # Only the recognized lease rejection is loss; disabled extraction
            # and other SQL precondition failures are not interchangeable.
            if rejected.is_lease_lost:
                raise LeaseLostError(str(rejected)) from rejected
            raise

    def reserve(self, job_id: str, fencing_token: int) -> bool:
        granted = self._rpc(
            "reserve_product_submission_extraction_budget",
            {"p_job_id": job_id, "p_fencing_token": int(fencing_token)},
        )
        if type(granted) is not bool:
            raise _RpcRejected("invalid budget acknowledgement", code=None)
        return granted

    def complete(
        self,
        job_id: str,
        fencing_token: int,
        outcome: str,
        *,
        draft: dict[str, Any] | None = None,
        usage: dict[str, Any] | None = None,
        error_code: str | None = None,
        cost_microcents: int | None = None,
    ) -> None:
        body: dict[str, Any] = {
            "p_job_id": job_id,
            "p_fencing_token": int(fencing_token),
            "p_outcome": outcome,
            "p_error_code": error_code,
            "p_cost_microcents": cost_microcents,
        }
        if draft is not None:
            body.update(
                {
                    "p_schema_version": draft.get("schema_version"),
                    "p_provider": draft.get("provider"),
                    "p_model": draft.get("model"),
                    "p_prompt_version": draft.get("prompt_version"),
                    "p_input_image_hashes": draft.get("evidence_snapshot"),
                    "p_draft_payload": draft,
                    "p_field_provenance": {},
                    "p_usage": usage,
                }
            )
        self._journal(job_id, fencing_token, outcome, cost_microcents, "completion_requested")
        try:
            self._rpc("complete_product_submission_extraction_job", body)
        except Exception as error:
            # An acknowledgement may be lost after COMMIT. Read this worker's
            # exact attempt receipt; never retry the write or run inference again.
            confirmed = False
            try:
                receipt = self.attempt_outcome(job_id, fencing_token)
                confirmed = (
                    receipt["job_state"] == outcome
                    and receipt["draft_recorded"] == (outcome == "review_ready")
                    and (cost_microcents is None or (
                        not receipt["reservation_open"]
                        and receipt["settled_microcents"] == cost_microcents)))
            except Exception:
                pass
            if not confirmed:
                if isinstance(error, _RpcRejected) and error.is_lease_lost:
                    raise LeaseLostError("extraction lease lost") from None
                raise
        finally:
            self.release_evidence(job_id)
        self._journal(job_id, fencing_token, outcome, cost_microcents, "completion_confirmed")

    def _journal(self, job_id, fencing_token, outcome, cost_microcents, event):
        # Local operator breadcrumb only, not an authority for retry or billing.
        # No photos, label text, auth data or user/submission identifiers.
        if self._attempt_journal is None:
            return
        record = {"job_id": job_id, "fencing_token": fencing_token, "outcome": outcome,
                  "cost_microcents": cost_microcents, "event": event}
        descriptor = os.open(self._attempt_journal, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, separators=(",", ":")) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def attempt_outcome(self, job_id: str, fencing_token: int) -> dict[str, Any]:
        """What actually happened to one attempt, when the answer was lost.

        A completion can time out with the transaction already committed.
        Retrying blind double-charges or files a second draft; giving up blind
        strands a reservation and loses a draft that exists. So the worker
        asks, keyed on the exact attempt: a later attempt's result says nothing
        about this one.
        """
        rows = self._rpc(
            "product_submission_extraction_attempt_outcome",
            {"p_job_id": job_id, "p_fencing_token": int(fencing_token)},
        )
        if isinstance(rows, list) and rows:
            rows = rows[0]
        if not isinstance(rows, dict):
            raise _RpcRejected("the queue returned no attempt outcome", code=None)
        if any(type(rows.get(key)) is not bool for key in
               ("attempt_is_current", "draft_recorded", "reservation_open")):
            raise _RpcRejected("invalid attempt acknowledgement", code=None)
        return {
            "attempt_is_current": bool(rows.get("attempt_is_current")),
            "job_state": rows.get("job_state"),
            "result_extraction_version": rows.get("result_extraction_version"),
            "draft_recorded": bool(rows.get("draft_recorded")),
            "reservation_open": bool(rows.get("reservation_open")),
            "reserved_microcents": int(rows.get("reserved_microcents") or 0),
            "settled_microcents": int(rows.get("settled_microcents") or 0),
        }

    def remaining_microcents(self) -> int:
        # The worker-facing view, which checks the allowlist and is granted to
        # authenticated. The bare allowance function it wraps is internal and
        # revoked from every role, so calling that directly fails in a real
        # deployment however well it reads.
        rows = self._rpc("product_submission_extraction_budget_state")
        if isinstance(rows, list) and rows:
            rows = rows[0]
        if not isinstance(rows, dict):
            return 0
        try:
            return max(0, int(rows.get("remaining_microcents") or 0))
        except (TypeError, ValueError):
            return 0

    # -- evidence --------------------------------------------------------

    def _build_job(self, row: Any) -> LeasedJob | None:
        if not isinstance(row, dict):
            raise ExtractionError("unsupported_evidence", "invalid claim row")
        manifest = row.get("evidence_manifest")
        object_paths = row.get("evidence_object_paths")
        configuration = row.get("configuration")
        if not isinstance(manifest, dict) or not manifest:
            raise ExtractionError("unsupported_evidence", "invalid evidence manifest")
        if not isinstance(object_paths, dict) or not isinstance(configuration, dict):
            raise ExtractionError("unsupported_evidence", "invalid claim configuration")
        uuid = r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}"
        if (not all(isinstance(key, str) and re.fullmatch(uuid, key)
                    and isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
                    for key, value in manifest.items())
                or not all(isinstance(row.get(key), str) and re.fullmatch(uuid, row[key])
                           for key in ("job_id", "submission_id"))
                or not all(type(row.get(key)) is int and row[key] > 0
                           for key in ("fencing_token", "evidence_revision"))):
            raise ExtractionError("unsupported_evidence", "invalid lease identity")
        config = _configuration_from(configuration)
        # The lease describes exactly one set of photos. If the hashes and the
        # paths disagree, the worker has been told to read something other than
        # what it must attribute the draft to, so it reads nothing.
        if set(object_paths) != set(manifest):
            raise ExtractionError(
                "unsupported_evidence", "the lease described inconsistent evidence"
            )
        job_id = str(row.get("job_id") or "")
        directory = self._lease_directory(job_id)
        photos: list[EvidencePhoto] = []
        try:
            for photo_id, digest in sorted(manifest.items()):
                path = directory / f"{photo_id}.bin"
                photo = EvidencePhoto(photo_id=photo_id, sha256=digest, path=str(path))
                self._photo_sources[str(path)] = (job_id, object_paths[photo_id], photo)
                photos.append(photo)
        except Exception:
            self.release_evidence(job_id)
            raise
        return LeasedJob(
            job_id=job_id,
            fencing_token=int(row.get("fencing_token") or 0),
            bundle=EvidenceBundle(
                submission_id=str(row.get("submission_id") or ""),
                evidence_revision=int(row.get("evidence_revision") or 0),
                photos=tuple(photos),
            ),
            configuration=config,
            # Heartbeat well before the SQL minimum lease of 30 seconds.
            heartbeat_seconds=5.0,
        )

    def _lease_directory(self, job_id: str) -> Path:
        existing = self._leases.get(job_id)
        if existing is not None:
            return existing
        root = self._workspace
        directory = Path(
            tempfile.mkdtemp(prefix="pg-extraction-", dir=str(root) if root else None)
        )
        # Owner-only: leased evidence is another person's private photographs.
        directory.chmod(0o700)
        self._leases[job_id] = directory
        return directory

    def read_evidence(self, photo: EvidencePhoto) -> bytes:
        """Fetch only registered evidence, inside the worker heartbeat scope."""
        source = self._photo_sources.get(photo.path)
        if source is None or source[2] != photo:
            raise ExtractionError("unsupported_evidence", "photo was not leased")
        job_id, object_path, _ = source
        directory = self._leases[job_id]
        return self._fetch_photo(object_path, photo.photo_id, directory).read_bytes()

    def _fetch_photo(self, object_path: str, photo_id: str, directory: Path) -> Path:
        # The path comes from the lease, not from string-building here: the
        # database owns where a submission's bytes live.
        if (not object_path or any(part in {"", ".", ".."} for part in object_path.split("/"))
                or "\\" in object_path or any(ord(c) < 32 for c in object_path)):
            raise ExtractionError("unsupported_evidence", "unusable evidence path")
        data = self._transport.get_bytes(
            f"{self._credentials.url}/storage/v1/object/{PHOTO_BUCKET}/{quote(object_path, safe='/')}",
            headers=self._headers(),
            timeout=self._timeout,
            max_bytes=MAX_PHOTO_BYTES,
        )
        # The leaf is a validated UUID from the manifest, so it cannot traverse,
        # and the directory is private to this lease.
        destination = directory / f"{photo_id}.bin"
        destination.write_bytes(data)
        destination.chmod(0o600)
        return destination

    def release_evidence(self, job_id: str) -> None:
        """Remove a lease's fetched photos. Safe to call more than once."""
        directory = self._leases.pop(job_id, None)
        if directory is None:
            return
        self._photo_sources = {path: source for path, source in self._photo_sources.items() if source[0] != job_id}
        with contextlib.suppress(OSError):
            shutil.rmtree(directory, ignore_errors=True)

    def close(self) -> None:
        for job_id in list(self._leases):
            self.release_evidence(job_id)


def _configuration_from(payload: dict[str, Any]) -> ExtractionConfig:
    """Build the run configuration from what the queue pinned at enqueue.

    The worker never supplies these. A job that was enqueued under one model
    must not be answered by another, and the database is where that is decided.
    """
    try:
        for key in ("provider", "model", "model_digest", "prompt_version", "prep_config_version"):
            if not isinstance(payload[key], str) or not payload[key].strip():
                raise ValueError()
        if not re.fullmatch(r"[0-9a-f]{64}", payload["model_digest"]):
            raise ValueError()
        if type(payload.get("max_cost_microcents", 0)) is not int or payload.get("max_cost_microcents", 0) < 0:
            raise ValueError()
        return ExtractionConfig(
            provider=str(payload["provider"]),
            model=str(payload["model"]),
            model_digest=str(payload["model_digest"]),
            prompt_version=str(payload["prompt_version"]),
            prep_config_version=str(payload["prep_config_version"]),
            retention_policy_version=payload.get("retention_policy_version"),
            max_cost_microcents=int(payload.get("max_cost_microcents") or 0),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ExtractionError(
            "unsupported_evidence", "the queue returned an unusable configuration"
        ) from error


class _RpcRejected(RuntimeError):
    def __init__(self, message: str, *, code: str | None) -> None:
        super().__init__(message)
        self.code = code

    @property
    def is_lease_lost(self) -> bool:
        return self.code == "lease_lost"


class _RequestsTransport:
    """The only place this module touches the network."""

    def post_json(
        self,
        url: str,
        *,
        headers: dict[str, str],
        body: dict[str, Any],
        timeout: float,
    ) -> Any:
        try:
            return _decode(request("POST", url, headers=headers, body=body,
                                   timeout=timeout, max_bytes=MAX_RESPONSE_BYTES))
        except TransportError:
            raise _RpcRejected("queue request failed", code=None) from None

    def get_bytes(self, url: str, *, headers: dict[str, str],
                  timeout: float, max_bytes: int) -> bytes:
        try:
            response = request("GET", url, headers=headers, timeout=timeout, max_bytes=max_bytes)
        except TransportError:
            raise _RpcRejected("evidence request failed", code=None) from None
        if not 200 <= response.status_code < 300:
            raise _RpcRejected("evidence request rejected", code=None)
        return response.content


def _decode(response: Any) -> Any:
    body = response.content or b""
    if len(body) > MAX_RESPONSE_BYTES:
        raise _RpcRejected("queue response exceeds the size limit", code=None)
    if not 200 <= response.status_code < 300:
        code = None
        message = f"queue rejected the request with {response.status_code}"
        with contextlib.suppress(Exception):
            payload = json.loads(body.decode("utf-8"))
            if isinstance(payload, dict):
                code = payload.get("code")
                if code == "55000" and payload.get("message") == "extraction lease is not held":
                    code = "lease_lost"
                # Never surface the database's own message: it can quote row
                # values, and a runner's output is read in a shared terminal.
        raise _RpcRejected(message, code=code)
    if not body:
        return None
    try:
        return json.loads(body.decode("utf-8"))
    except ValueError as error:
        raise _RpcRejected("queue returned an unreadable response", code=None) from error


__all__ = [
    "MAX_PHOTO_BYTES",
    "QueueConfigurationError",
    "SupabaseExtractionQueue",
    "WorkerCredentials",
]
