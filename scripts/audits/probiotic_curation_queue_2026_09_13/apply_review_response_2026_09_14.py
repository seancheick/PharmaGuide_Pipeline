"""Apply the 2026-09-14 evidence review response to the probiotic registry.

Read-only by default.  ``--apply`` writes the source-bound field patches AND the
owner's final review statuses in one atomic write:

* approve_as_written / approve_with_correction -> ``review_status`` becomes
  ``clinician_approved`` with an attributable ``clinical_review`` block, and
  ``scoring_eligible`` becomes ``True`` unless the review itself set it False
  (rankings, class-level pools, uncontrolled designs stay non-scoring).
* reject -> ``review_status`` becomes ``rejected_source``.

Every patch must still match its recorded old value, every touched context must
pass the frozen contract AND the runtime validator, and the run is bound to the
registry snapshot it was reviewed against.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from clinical_evidence_schema import validate_frozen_context  # noqa: E402

REGISTRY = ROOT / "scripts/data/clinically_relevant_strains.json"
RESPONSE = ROOT / "docs/plans/PROBIOTIC_EVIDENCE_REVIEW_RESPONSE_2026-09-14.json"
APPROVE = {"approve_as_written", "approve_with_correction"}
REJECT = {"reject"}
REVIEW_SCOPE = "identity_dose_outcome_applicability"
MISSING = object()
_SEGMENT = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_]*)(?:\[(?P<index>\d+)\])?$")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _contexts(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for entry in registry.get("clinically_relevant_strains", []):
        for context in entry.get("study_contexts", []):
            cid = context.get("context_id")
            if cid in result:
                raise ValueError(f"duplicate context_id: {cid}")
            result[cid] = context
    return result


def _owner_of(registry: dict[str, Any]) -> dict[str, str]:
    return {
        context["context_id"]: entry["id"]
        for entry in registry.get("clinically_relevant_strains", [])
        for context in entry.get("study_contexts", [])
    }


def _read_path(root: Any, path: str) -> Any:
    current = root
    for raw in path.split("."):
        match = _SEGMENT.fullmatch(raw)
        if not match or not isinstance(current, dict) or match.group("key") not in current:
            return MISSING
        current = current[match.group("key")]
        if match.group("index") is not None:
            if not isinstance(current, list) or int(match.group("index")) >= len(current):
                return MISSING
            current = current[int(match.group("index"))]
    return current


def _write_path(root: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    current: Any = root
    for offset, raw in enumerate(parts):
        match = _SEGMENT.fullmatch(raw)
        if not match:
            raise ValueError(f"invalid field path: {path}")
        key, index = match.group("key"), match.group("index")
        last = offset == len(parts) - 1
        if index is None:
            if last:
                current[key] = deepcopy(value)
                return
            current = current.setdefault(key, {})
            continue
        sequence = current.setdefault(key, [])
        if not isinstance(sequence, list):
            raise ValueError(f"not a list: {path}")
        idx = int(index)
        if idx > len(sequence):
            raise ValueError(f"list gap for {path}")
        if idx == len(sequence):
            if not last:
                raise ValueError(f"missing list item for {path}")
            sequence.append(deepcopy(value))  # append a new outcome
            return
        if last:
            sequence[idx] = deepcopy(value)
            return
        current = sequence[idx]


def validate(registry: dict[str, Any], response: dict[str, Any], *, reviewer: str,
             reviewed_at: str) -> tuple[dict[str, Any], dict[str, int]]:
    """Return the prospective registry and a summary; raise on any mismatch."""
    from studied_formulas import valid_native_study_context

    metadata = response["_metadata"]
    bound_sha = metadata.get("dataset_sha256")
    applied_sha = metadata.get("applied_dataset_sha256")
    actual_sha = _sha256(REGISTRY)
    if applied_sha and actual_sha == applied_sha:
        raise SystemExit("review response already applied to this registry snapshot")
    if bound_sha and bound_sha != actual_sha:
        raise ValueError(f"dataset snapshot mismatch: bound {bound_sha}, current {actual_sha}")

    prospective = deepcopy(registry)
    contexts = _contexts(prospective)
    owners = _owner_of(prospective)
    known_ids = {e["id"] for e in prospective["clinically_relevant_strains"]}
    reviews = response["reviews"]
    if set(reviews) - set(contexts):
        raise ValueError(f"review records not in registry: {sorted(set(reviews) - set(contexts))}")
    summary = {"approved": 0, "rejected": 0, "patches": 0, "scoring_eligible_true": 0,
               "scoring_eligible_false": 0}
    for cid, review in reviews.items():
        context = contexts[cid]
        if context.get("review_status") != "source_verified_pending_clinical_review":
            raise ValueError(f"{cid}: expected pending status, found {context.get('review_status')!r}")
        decision = review["decision"]
        if decision not in APPROVE | REJECT:
            raise ValueError(f"{cid}: decision {decision!r} is not final")
        seen: set[str] = set()
        for patch in review["patches"]:
            path = patch["field_path"]
            if path in seen:
                raise ValueError(f"{cid}: duplicate patch path {path}")
            seen.add(path)
            if patch["source_pmid"] not in {str(p) for p in context.get("source_pmids", [])}:
                raise ValueError(f"{cid}: patch PMID {patch['source_pmid']} not attached to context")
            current = _read_path(context, path)
            current = None if current is MISSING else current
            if current != patch["old_value"]:
                raise ValueError(f"{cid}: old value mismatch at {path}: registry {current!r}, review {patch['old_value']!r}")
            _write_path(context, path, patch["new_value"])
            summary["patches"] += 1
        if decision in APPROVE:
            context["review_status"] = "clinician_approved"
            context["clinical_review"] = {
                "reviewer": reviewer,
                "reviewed_at": reviewed_at,
                "scope": REVIEW_SCOPE,
                "basis": "docs/plans/PROBIOTIC_EVIDENCE_REVIEW_RESPONSE_2026-09-14.json",
                "decision": decision,
            }
            if context.get("scoring_eligible") is False:
                summary["scoring_eligible_false"] += 1
            else:
                context["scoring_eligible"] = True
                summary["scoring_eligible_true"] += 1
            summary["approved"] += 1
        else:
            context["review_status"] = "rejected_source"
            context["scoring_eligible"] = False
            context["rejection_reason"] = review["reason"]
            summary["rejected"] += 1
        if context.get("context_schema_version") == "1.1.0":
            errors = validate_frozen_context(context, known_component_ids=known_ids)
            if errors:
                raise ValueError(f"{cid}: frozen contract errors {errors}")
        if not valid_native_study_context(context, owners[cid]):
            raise ValueError(f"{cid}: fails valid_native_study_context after apply")
    return prospective, summary


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--reviewer", required=True, help="attributable owner approving the review")
    args = parser.parse_args()
    reviewed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    response = json.loads(RESPONSE.read_text(encoding="utf-8"))
    before_sha = _sha256(REGISTRY)
    prospective, summary = validate(registry, response, reviewer=args.reviewer, reviewed_at=reviewed_at)
    print(json.dumps(summary))
    if not args.apply:
        print("dry run; no files changed")
        return 0
    prospective["_metadata"]["last_updated"] = reviewed_at[:10]
    prospective["_metadata"]["review_response_note_2026_09_14"] = (
        f"{summary['approved']} study contexts approved and {summary['rejected']} rejected on {reviewed_at[:10]} "
        f"from the 2026-09-14 evidence review response (reviewer of record: {args.reviewer}); "
        f"{summary['patches']} source-bound field patches applied; {summary['scoring_eligible_false']} approved contexts "
        "stay scoring_eligible=false by review decision."
    )
    _atomic_write(REGISTRY, prospective)
    response["_metadata"]["dataset_sha256"] = before_sha
    response["_metadata"]["applied_dataset_sha256"] = _sha256(REGISTRY)
    response["_metadata"]["applied_at"] = reviewed_at
    response["_metadata"]["reviewer_of_record"] = args.reviewer
    RESPONSE.write_text(json.dumps(response, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"applied; registry sha {before_sha[:12]} -> {_sha256(REGISTRY)[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
