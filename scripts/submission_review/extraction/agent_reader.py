"""An agent as a reader: it reads the photographs and files a label_draft_v1.

The agent (Claude or any other) is one more producer behind the same extractor
the queue worker uses, so its reading gets the same envelope validation,
deterministic checks and independent grounding (RapidOCR over the same
prepared bytes). What it writes is a draft and a reviewer draft; the five
field confirmations and the approval stay the reviewer's clicks in the console.

    fetch  S01 [S02 ...]   photos + an OCR lead reading for each submission
    sheet  S01             every cited region as one image, to check the boxes
    record S01 --model M   file the agent's reading.json as a draft
    save   S01             save label.json as the review, after checks
    verify S01             read back what the server holds; READY or NOT ready

Work lives in ``$PG_SUBMISSION_WORKDIR`` (default /tmp/pg_submissions/<alias>).
Output names aliases only; submission ids, user ids and URLs are never printed.

Account: until a machine reviewer exists, requests run as the reviewer named
by ``PG_REVIEWER_EMAIL`` through an admin-minted session (Sean, 2026-09-27:
"use my account for now"). Photos may go to hosted models (same decision).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import env_loader  # noqa: E402,F401
from product_submission_import import (  # noqa: E402
    SubmissionImportError, _validate_label_payload,
)
from submission_review.extraction import bounded_http  # noqa: E402
from submission_review.extraction.checks import convention_findings  # noqa: E402
from submission_review.extraction.envelope import (  # noqa: E402
    LABEL_CONTENT_KEYS, SCHEMA_VERSION, LabelDraftError, validate_label_draft_v1,
)
from submission_review.extraction.extractor import (  # noqa: E402
    EvidenceBundle, EvidencePhoto, ExtractionConfig, ExtractionResult,
    LabelDraftExtractor, PreparedBundle, Usage,
)
from submission_review.extraction.photo_prep import prepare_bundle  # noqa: E402
from submission_review.extraction.to_manual_label import (  # noqa: E402
    STATEMENT_TYPE, to_manual_label,
)

PROVIDER = "agent"
#: Bump when the product-submissions-prep skill's reading rules change.
PROMPT_VERSION = "product-submissions-prep/1"
RETENTION = "hosted-ok-sean-2026-09-27"
WORK = Path(os.environ.get("PG_SUBMISSION_WORKDIR", "/tmp/pg_submissions"))
EDGE_PATH = "/functions/v1/review-product-submissions"
MAX_JSON = 16 * 1024 * 1024
MAX_PHOTO = 15 * 1024 * 1024


class AgentError(RuntimeError):
    pass


# ------------------------------------------------------------ pure pieces

def build_draft(content: Mapping[str, Any], bundle: PreparedBundle, model: str) -> dict[str, Any]:
    """The agent's label content plus the provenance only the runtime knows.

    A source may name just its photo_id; the prepared input for that photo is
    filled in, since the agent reads photos, not prepared inputs.
    """
    extra = set(content) - LABEL_CONTENT_KEYS
    if extra:
        raise AgentError(f"reading.json has non-label keys: {sorted(extra)}")
    inputs = {photo.photo_id: photo.input_id for photo in bundle.photos}

    def bind(value: Any) -> Any:
        if isinstance(value, dict):
            bound = {key: bind(item) for key, item in value.items()}
            if "photo_id" in bound and "input_id" not in bound and "declared" not in bound:
                if bound["photo_id"] not in inputs:
                    raise AgentError("a source names a photo this submission does not have")
                bound["input_id"] = inputs[bound["photo_id"]]
            return bound
        if isinstance(value, list):
            return [bind(item) for item in value]
        return value

    return {
        **bind(dict(content)),
        "schema_version": SCHEMA_VERSION,
        "draft_origin": "model",
        "provider": PROVIDER,
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "evidence_revision": bundle.evidence_revision,
        "evidence_snapshot": bundle.snapshot,
        "sent_inputs": [photo.as_sent_input() for photo in bundle.photos],
    }


def reading_changes(skeleton: Any, label: Any, path: str = "$") -> list[str]:
    """Where label.json departs from what the recorded reading says.

    label.json may only add what a draft cannot carry (ingredientGroup,
    physicalState, statement types, daily servings, ...). Changing a value the
    reading supplied means the reading was wrong: fix reading.json and record
    again, so the draft the reviewer sees and the label agree.
    """
    if isinstance(skeleton, Mapping):
        if not isinstance(label, Mapping):
            return [path]
        changes = []
        for key, value in skeleton.items():
            if key not in label:
                changes.append(f"{path}.{key}")
            elif key == "type" and value == STATEMENT_TYPE:
                continue  # the neutral default is there to be replaced
            else:
                changes.extend(reading_changes(value, label[key], f"{path}.{key}"))
        return changes
    if isinstance(skeleton, list):
        if not isinstance(label, list) or len(label) != len(skeleton):
            return [path]
        changes = []
        for index, value in enumerate(skeleton):
            changes.extend(reading_changes(value, label[index], f"{path}[{index}]"))
        return changes
    return [] if skeleton == label else [path]


class _FiledReading:
    """Adapter that returns the agent's already-written draft."""

    def __init__(self, draft: dict[str, Any]) -> None:
        self._draft = draft

    def extract(self, bundle: PreparedBundle, config: ExtractionConfig) -> ExtractionResult:
        return ExtractionResult(draft=self._draft, usage=Usage())


# ------------------------------------------------------------ the service

def _env(name: str, *alternates: str) -> str:
    for key in (name, *alternates):
        value = (os.environ.get(key) or "").strip()
        if value:
            return value
    raise AgentError(f"missing {name} in the environment (.env)")


def _private_dir(path: Path) -> Path:
    """Work files hold private photos, submission ids and a session: owner only."""
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)
    return path


class Reviewer:
    """The review function, called with the configured reviewer's session."""

    def __init__(self) -> None:
        self.url = _env("SUPABASE_URL").rstrip("/")
        self.anon = _env("SUPABASE_ANON_KEY", "SUPABASE_PUBLISHABLE_KEY")
        self.email = _env("PG_REVIEWER_EMAIL")
        # One cached session per account, so changing PG_REVIEWER_EMAIL never
        # keeps acting as the previous reviewer.
        account = hashlib.sha256(self.email.lower().encode()).hexdigest()[:16]
        self.token_path = WORK / f".session-{account}"

    def _post(self, path: str, body: dict, headers: dict) -> tuple[int, Any]:
        response = bounded_http.request(
            "POST", self.url + path, timeout=90, max_bytes=MAX_JSON,
            headers=headers, body=body)
        try:
            return response.status_code, json.loads(response.content or b"{}")
        except ValueError:
            return response.status_code, {}

    def _mint(self) -> str:
        service = _env("SUPABASE_SERVICE_ROLE_KEY")
        email = self.email
        status, link = self._post(
            "/auth/v1/admin/generate_link", {"type": "magiclink", "email": email},
            {"apikey": service, "authorization": f"Bearer {service}"})
        if status != 200 or not link.get("email_otp"):
            raise AgentError(f"could not mint a reviewer session ({status})")
        status, verified = self._post(
            "/auth/v1/verify",
            {"email": email, "token": link["email_otp"], "type": "magiclink"},
            {"apikey": self.anon})
        if status != 200 or not verified.get("access_token"):
            raise AgentError(f"could not verify the reviewer session ({status})")
        _private_dir(WORK)
        # Created owner-only and never through a planted symlink.
        fd = os.open(self.token_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(verified["access_token"])
        self.token_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        return verified["access_token"]

    def token(self, *, fresh: bool = False) -> str:
        if not fresh and self.token_path.exists():
            cached = self.token_path.read_text().strip()
            if cached:
                return cached
        return self._mint()

    def call(self, action: str, **payload: Any) -> dict:
        for fresh in (False, True):
            status, body = self._post(
                EDGE_PATH, {"action": action, **payload},
                {"apikey": self.anon, "authorization": f"Bearer {self.token(fresh=fresh)}"})
            if status != 401:
                break
        if status != 200:
            detail = body.get("error") if isinstance(body, dict) else None
            raise AgentError(f"{action} refused ({status}): {str(detail)[:200]}")
        return body

    def open_submissions(self) -> list[dict]:
        rows, after = [], None
        while True:
            body = self.call("list", limit=100, status="open", **({"after": after} if after else {}))
            rows.extend(body.get("submissions") or [])
            after = body.get("next_after")
            if not after:
                return rows

    def submission(self, submission_id: str) -> dict:
        rows = self.call("list", submission_id=submission_id).get("submissions") or []
        if len(rows) != 1:
            raise AgentError("that submission is no longer open")
        return rows[0]


def _aliases(rows: list[dict] | None = None) -> dict[str, str]:
    """alias -> submission id, stable across runs on this machine."""
    path = WORK / "aliases.json"
    mapping = json.loads(path.read_text()) if path.exists() else {}
    if rows is not None:
        known = set(mapping.values())
        for row in rows:
            if row["id"] not in known:
                number = len(mapping) + 1
                while f"S{number:02d}" in mapping:
                    number += 1
                mapping[f"S{number:02d}"] = row["id"]
        _private_dir(WORK)
        path.write_text(json.dumps(mapping, indent=1))
    return mapping


def _resolve(alias: str) -> str:
    mapping = _aliases()
    if alias.upper() not in mapping:
        raise AgentError(f"unknown alias {alias}; run `list` first")
    return mapping[alias.upper()]


def _bundle(submission: dict, directory: Path) -> EvidenceBundle:
    manifest = json.loads((directory / "photos.json").read_text())
    files = {entry["photo_id"]: entry["file"] for entry in manifest}
    if any(photo["photo_id"] not in files for photo in submission.get("photos") or ()):
        raise AgentError("the photos changed after `fetch`; run `fetch` again")
    return EvidenceBundle(
        submission_id=submission["id"],
        evidence_revision=submission["evidence_revision"],
        photos=tuple(
            EvidencePhoto(photo_id=photo["photo_id"], sha256=photo["content_sha256"],
                          path=files[photo["photo_id"]],
                          categories=tuple(photo.get("categories") or ()))
            for photo in submission.get("photos") or ()
        ),
    )


# ------------------------------------------------------------ commands

def cmd_list(api: Reviewer) -> None:
    rows = api.open_submissions()
    mapping = {value: key for key, value in _aliases(rows).items()}
    print(f"open submissions: {len(rows)}")
    for row in rows:
        print(f"  {mapping[row['id']]}  {row.get('kind') or '-':<16} "
              f"{row.get('review_status') or '-':<13} photos={len(row.get('photos') or [])} "
              f"submitted={(row.get('submitted_at') or row.get('created_at') or '')[:10]}")


def cmd_fetch(api: Reviewer, alias: str) -> None:
    from submission_review.extraction.adapters.ocr_adapter import (
        PROVIDER as OCR, RULES_VERSION, OcrLabelAdapter,
    )
    from submission_review.extraction.adapters.rapidocr_reader import RapidOcrReader

    alias = alias.upper()
    submission = api.submission(_resolve(alias))
    directory = WORK / alias
    _private_dir(directory)
    _private_dir(directory / "photos")
    manifest = []
    for index, photo in enumerate(submission.get("photos") or [], start=1):
        response = bounded_http.request("GET", photo["signed_url"], timeout=90, max_bytes=MAX_PHOTO)
        if response.status_code != 200:
            raise AgentError(f"{alias} photo {index:02d} download failed ({response.status_code})")
        if hashlib.sha256(response.content).hexdigest() != photo["content_sha256"]:
            raise AgentError(f"{alias} photo {index:02d} does not match its evidence hash")
        category = "-".join(photo.get("categories") or ["uncategorised"])
        target = directory / "photos" / f"{index:02d}_{category}.jpg"
        target.write_bytes(response.content)
        manifest.append({"photo": f"{index:02d}", "photo_id": photo["photo_id"],
                         "categories": photo.get("categories") or [], "file": str(target)})
    (directory / "photos.json").write_text(json.dumps(manifest, indent=1))

    # The OCR reading is a lead to correct against the photographs, never the answer.
    prepared = prepare_bundle(_bundle(submission, directory))
    config = ExtractionConfig(provider=OCR, model="rapidocr", model_digest="0" * 64,
                              prompt_version=RULES_VERSION, retention_policy_version="local-only-v1")
    lead = OcrLabelAdapter(RapidOcrReader()).extract(prepared, config).draft
    reading = {key: lead[key] for key in LABEL_CONTENT_KEYS if key in lead}
    (directory / "reading.json").write_text(json.dumps(reading, indent=1, ensure_ascii=False))
    print(f"{alias}: {len(manifest)} photo(s) and an OCR lead reading in {directory}")
    for entry in manifest:
        print(f"    {entry['photo']}  {', '.join(entry['categories']) or 'uncategorised'}")


def cmd_sheet(alias: str) -> None:
    """One image of every cited region, labelled by field.

    Each region becomes the crop beside the reviewer's tick, so a box that
    frames the wrong text wastes their time or, worse, looks like support for
    a value it does not show. Look at the sheet before recording.
    """
    from PIL import Image, ImageDraw

    alias = alias.upper()
    directory = WORK / alias
    reading = json.loads((directory / "reading.json").read_text())
    files = {entry["photo_id"]: entry["file"]
             for entry in json.loads((directory / "photos.json").read_text())}
    tiles: list[tuple[str, Any]] = []

    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for source in value.get("sources") or []:
                region = source.get("region")
                if region and source.get("photo_id") in files:
                    with Image.open(files[source["photo_id"]]) as image:
                        width, height = image.size
                        tile = image.convert("RGB").crop((
                            int(region["x"] * width), int(region["y"] * height),
                            int((region["x"] + region["w"]) * width),
                            int((region["y"] + region["h"]) * height)))
                    tile.thumbnail((900, 220))
                    tiles.append((path, tile))
            for key, item in value.items():
                if key != "sources":
                    walk(item, f"{path}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{path}[{index}]")

    for key in ("identity", "serving", "ingredient_rows", "other_ingredients", "statements"):
        walk(reading.get(key), key)
    if not tiles:
        print(f"{alias}: no regions in reading.json")
        return
    sheet = Image.new("RGB", (920, sum(tile.height + 28 for _, tile in tiles)), "white")
    draw = ImageDraw.Draw(sheet)
    top = 0
    for path, tile in tiles:
        draw.text((6, top + 6), path, fill="black")
        sheet.paste(tile, (6, top + 24))
        top += tile.height + 28
    target = directory / "regions_sheet.png"
    sheet.save(target)
    print(f"{alias}: {len(tiles)} region(s) -> {target}")


def cmd_record(api: Reviewer, alias: str, model: str) -> int:
    from submission_review.extraction.adapters.rapidocr_reader import RapidOcrReader

    alias = alias.upper()
    directory = WORK / alias
    submission = api.submission(_resolve(alias))
    prepared = prepare_bundle(_bundle(submission, directory))
    content = json.loads((directory / "reading.json").read_text())
    draft = build_draft(content, prepared, model)

    # The extractor would refuse a malformed reading as "invalid provider
    # draft"; ask the envelope owner first so the reader sees where and why.
    try:
        validate_label_draft_v1(draft)
    except LabelDraftError as error:
        print(f"{alias}: not recorded; reading.json is not a valid draft: {error}")
        return 1
    problems = convention_findings(draft)
    if problems:
        print(f"{alias}: not recorded; fix reading.json first:")
        for finding in problems:
            print(f"    {finding['code']}: {finding['detail']}")
        return 1

    config = ExtractionConfig(
        provider=PROVIDER, model=model,
        model_digest=hashlib.sha256(model.encode()).hexdigest(),
        prompt_version=PROMPT_VERSION, retention_policy_version=RETENTION)
    result = LabelDraftExtractor(_FiledReading(draft), grounding_reader=RapidOcrReader()).extract(
        prepared, config, submission_gtin=submission.get("normalized_upc"))
    usage = result.usage.as_payload()
    api.call("record_extraction", submission_id=submission["id"], extraction={
        "schema_version": SCHEMA_VERSION, "provider": PROVIDER, "model": model,
        "prompt_version": PROMPT_VERSION, "input_image_hashes": prepared.snapshot,
        "draft_payload": result.draft, "field_provenance": {}, "confidence": None,
        "usage": usage, "evidence_revision": prepared.evidence_revision,
    })
    (directory / "draft.json").write_text(json.dumps(result.draft, indent=1, ensure_ascii=False))
    skeleton = to_manual_label(result.draft)
    (directory / "label.json").write_text(json.dumps(skeleton.payload, indent=1, ensure_ascii=False))
    (directory / "unresolved.json").write_text(json.dumps(skeleton.unresolved, indent=1, ensure_ascii=False))

    print(f"{alias}: draft recorded; label.json and unresolved.json written")
    for finding in result.draft.get("discrepancies") or []:
        print(f"    finding {finding['severity']}: {finding['code']} — {finding.get('detail') or ''}")
    grounding = usage.get("grounding") or {}
    print(f"    grounding: {grounding.get('grounded')}/{grounding.get('checked')} fields found "
          f"by independent OCR ({grounding.get('status')})")
    for entry in grounding.get("fields") or []:
        if not entry.get("grounded"):
            # Not an error: OCR misses fine print. Each one is a field to re-read.
            print(f"      re-read {entry['path']}: {entry.get('reason')}")
    print(f"    fill {len(skeleton.unresolved)} unresolved item(s) in label.json, then `save {alias}`")
    return 0


def save_refusal(draft: dict, label: dict, submission: dict, review: dict) -> str | None:
    """Why `save` must not write this label as the review, or None."""
    if draft.get("evidence_revision") != submission.get("evidence_revision"):
        return "the photos changed after `record`; run `fetch` and `record` again"
    if any(entry.get("live") for entry in review.get("verifications") or []):
        return "the reviewer has already ticked fields; the review is theirs now"
    saved = (review.get("draft") or {}).get("payload")
    if saved and saved not in (label, to_manual_label(draft).payload):
        return "the reviewer has edited the saved review; the review is theirs now"
    return None


def cmd_save(api: Reviewer, alias: str) -> int:
    alias = alias.upper()
    directory = WORK / alias
    draft = json.loads((directory / "draft.json").read_text())
    label = json.loads((directory / "label.json").read_text())
    changes = reading_changes(to_manual_label(draft).payload, label)
    if changes:
        print(f"{alias}: not saved; label.json changes values the recorded reading supplied:")
        for path in changes[:20]:
            print(f"    {path}")
        print("    fix reading.json and run `record` again")
        return 1
    try:
        _validate_label_payload(label)
    except SubmissionImportError as error:
        print(f"{alias}: not saved; the catalog importer refuses it: {error}")
        return 1
    diagnostics = api.call("validate_label", payload=label).get("diagnostics") or []
    if diagnostics:
        print(f"{alias}: not saved; {len(diagnostics)} server diagnostic(s):")
        for item in diagnostics[:20]:
            print("    " + json.dumps(item)[:200])
        return 1
    submission = api.submission(_resolve(alias))
    review = api.call("load_review", submission_id=submission["id"]).get("review") or {}
    refusal = save_refusal(draft, label, submission, review)
    if refusal:
        print(f"{alias}: not saved; {refusal}")
        return 1
    api.call("save_review", submission_id=submission["id"], payload=label,
             expected_evidence_revision=submission["evidence_revision"],
             evidence_manifest_sha256=submission["evidence_manifest_sha256"])
    print(f"{alias}: saved. In the console: open it, compare each field with its crop, "
          f"tick the five fields, approve.")
    return 0


def cmd_verify(api: Reviewer, alias: str, model: str | None) -> int:
    """Read back what the server holds and say whether it is ready for the reviewer."""
    alias = alias.upper()
    submission_id = _resolve(alias)
    review = api.call("load_review", submission_id=submission_id).get("review") or {}
    saved = review.get("draft") or {}
    submission = api.submission(submission_id)
    latest = (submission.get("extractions") or [{}])[0]
    local_path = WORK / alias / "label.json"
    checks = {
        "saved review matches label.json": bool(saved.get("payload")) and local_path.exists()
            and saved["payload"] == json.loads(local_path.read_text()),
        "saved review is current (not superseded)": saved.get("superseded") is False,
        "server diagnostics: 0": bool(saved.get("payload")) and not (
            api.call("validate_label", payload=saved["payload"]).get("diagnostics") or []),
        "no field ticked for the reviewer": not any(
            entry.get("live") for entry in review.get("verifications") or []),
        "latest draft is the agent's, at this revision": latest.get("provider") == PROVIDER
            and latest.get("evidence_revision") == submission.get("evidence_revision")
            and (model is None or latest.get("model") == model),
    }
    for label, passed in checks.items():
        print(f"  {'ok  ' if passed else 'FAIL'} {label}")
    findings = (latest.get("draft_payload") or {}).get("discrepancies") or []
    for finding in findings:
        print(f"  note finding {finding['severity']}: {finding['code']}")
    print(f"  status {submission.get('review_status')}; barcode check "
          f"{'recorded' if review.get('identity_check') else 'not yet run'}; "
          f"catalog picture {'chosen' if review.get('product_image') else 'not yet chosen'} "
          f"(the console does both when the reviewer opens it)")
    ready = all(checks.values())
    print(f"{alias}: {'READY for the reviewer' if ready else 'NOT ready'}")
    return 0 if ready else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    fetch = sub.add_parser("fetch")
    fetch.add_argument("aliases", nargs="+")
    sheet = sub.add_parser("sheet")
    sheet.add_argument("alias")
    record = sub.add_parser("record")
    record.add_argument("alias")
    record.add_argument("--model", required=True, help="the reading model, e.g. claude-opus-5-5")
    save = sub.add_parser("save")
    save.add_argument("alias")
    verify = sub.add_parser("verify")
    verify.add_argument("alias")
    verify.add_argument("--model", help="also require the latest draft to be this model's")
    args = parser.parse_args(argv)
    if args.command == "sheet":
        cmd_sheet(args.alias)  # local only: no account needed
        return 0
    try:
        api = Reviewer()
        if args.command == "list":
            cmd_list(api)
            return 0
        if args.command == "fetch":
            for alias in args.aliases:
                cmd_fetch(api, alias)
            return 0
        if args.command == "record":
            return cmd_record(api, args.alias, args.model)
        if args.command == "verify":
            return cmd_verify(api, args.alias, args.model)
        return cmd_save(api, args.alias)
    except (AgentError, bounded_http.TransportError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
