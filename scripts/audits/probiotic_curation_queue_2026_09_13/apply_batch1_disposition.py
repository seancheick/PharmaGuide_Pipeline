"""Validate and optionally apply the source-bound batch-1 evidence patch.

The disposition is deliberately separate from clinical sign-off.  By default
this command performs a read-only check against the exact registry snapshot.
``--apply`` writes only the explicitly listed field patches, never review
statuses, and refuses to run if the snapshot or any expected old value changed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

import sys

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from clinical_evidence_schema import validate_frozen_context


REGISTRY = ROOT / "scripts/data/clinically_relevant_strains.json"
DISPOSITION = Path(__file__).with_name("batch1_disposition_2026-09-14.json")
DECISION_COUNTS = {
    "approve_as_written": 14,
    "approve_with_correction": 8,
    "needs_source_clarification": 1,
    "archive_from_consumer_scoring": 2,
}
MISSING = object()
_SEGMENT = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_]*)(?:\[(?P<index>\d+)\])?$")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _contexts(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for entry in registry.get("clinically_relevant_strains", []):
        for context in entry.get("study_contexts", []):
            context_id = context.get("context_id") if isinstance(context, dict) else None
            if isinstance(context_id, str) and context_id:
                if context_id in result:
                    raise ValueError(f"duplicate context_id: {context_id}")
                result[context_id] = context
    return result


def _read_path(root: dict[str, Any], path: str) -> Any:
    current: Any = root
    for raw in path.split("."):
        match = _SEGMENT.fullmatch(raw)
        if not match or not isinstance(current, dict) or match.group("key") not in current:
            return MISSING
        current = current[match.group("key")]
        if match.group("index") is not None:
            if not isinstance(current, list):
                return MISSING
            index = int(match.group("index"))
            if index >= len(current):
                return MISSING
            current = current[index]
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
        if not isinstance(current, dict) or key not in current:
            if last:
                if not isinstance(current, dict):
                    raise ValueError(f"cannot set {path}")
                current[key] = deepcopy(value)
                return
            raise ValueError(f"missing parent for {path}")
        if index is None:
            if last:
                current[key] = deepcopy(value)
                return
            current = current[key]
            continue
        sequence = current[key]
        if not isinstance(sequence, list) or int(index) >= len(sequence):
            raise ValueError(f"missing list item for {path}")
        if last:
            sequence[int(index)] = deepcopy(value)
            return
        current = sequence[int(index)]


def _already_applied(registry: dict[str, Any], disposition: dict[str, Any]) -> bool:
    """True when every declared patch value is already present in the registry.

    The snapshot hash binds a patch to the exact registry it was written for;
    once applied, the patched values themselves are the proof. Later, unrelated
    registry changes (a status decision, the next curation wave) must not turn
    an applied disposition back into a snapshot mismatch.
    """
    patches = disposition.get("patches")
    if not isinstance(patches, list) or not patches:
        return False
    contexts = _contexts(registry)
    for patch in patches:
        if not isinstance(patch, dict):
            return False
        context = contexts.get(patch.get("record_id"))
        if context is None or not isinstance(patch.get("field_path"), str):
            return False
        current = _read_path(context, patch["field_path"])
        if current is MISSING or current != patch.get("new_value"):
            return False
    return True


def validate(registry: dict[str, Any], disposition: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    metadata = disposition.get("_metadata")
    if not isinstance(metadata, dict):
        raise ValueError("disposition metadata is required")
    expected_sha = metadata.get("dataset_sha256")
    actual_sha = _sha256(REGISTRY)
    applied_sha = metadata.get("applied_dataset_sha256")
    already_applied = actual_sha == applied_sha or _already_applied(registry, disposition)
    if expected_sha != actual_sha and not already_applied:
        raise ValueError(
            f"dataset snapshot mismatch: expected {expected_sha}, current {actual_sha}"
        )
    snapshot_id = metadata.get("review_snapshot_id")
    if not isinstance(snapshot_id, str) or not snapshot_id.strip():
        raise ValueError("review_snapshot_id is required")
    decisions = disposition.get("decisions")
    if not isinstance(decisions, dict) or len(decisions) != sum(DECISION_COUNTS.values()):
        raise ValueError("batch-1 decisions must cover exactly 25 contexts")
    counts: dict[str, int] = {}
    for record_id, decision in decisions.items():
        if not isinstance(record_id, str) or not isinstance(decision, str):
            raise ValueError("decision keys and values must be strings")
        counts[decision] = counts.get(decision, 0) + 1
    if counts != DECISION_COUNTS:
        raise ValueError(f"decision counts mismatch: {counts}")
    unpatched = disposition.get("unpatched_corrections")
    if not isinstance(unpatched, dict):
        raise ValueError("unpatched_corrections must explicitly list deferred corrections")
    expected_unpatched = {
        record_id
        for record_id, decision in decisions.items()
        if decision == "approve_with_correction"
    }

    contexts = _contexts(registry)
    missing_decisions = sorted(set(decisions) - set(contexts))
    if missing_decisions:
        raise ValueError(f"decision records not found: {missing_decisions}")

    patches = disposition.get("patches")
    if not isinstance(patches, list) or not patches:
        raise ValueError("at least one explicit patch is required")
    seen_paths: set[tuple[str, str]] = set()
    patched_records: set[str] = set()
    prospective = deepcopy(registry)
    prospective_contexts = _contexts(prospective)
    for patch in patches:
        if not isinstance(patch, dict):
            raise ValueError("patch entries must be objects")
        record_id = patch.get("record_id")
        field_path = patch.get("field_path")
        if not isinstance(record_id, str) or record_id not in prospective_contexts:
            raise ValueError(f"patch record not found: {record_id!r}")
        if not isinstance(field_path, str) or not field_path:
            raise ValueError("patch field_path is required")
        key = (record_id, field_path)
        if key in seen_paths:
            raise ValueError(f"duplicate patch path: {record_id}.{field_path}")
        seen_paths.add(key)
        patched_records.add(record_id)
        if not all(isinstance(patch.get(key), str) and patch[key].strip() for key in (
            "source_pmid", "source_url", "source_location", "reviewer_reason"
        )):
            raise ValueError(f"source provenance is incomplete for {record_id}.{field_path}")
        context = prospective_contexts[record_id]
        if patch["source_pmid"] not in {str(pmid) for pmid in context.get("source_pmids", [])}:
            raise ValueError(f"source PMID is not attached to {record_id}")
        current = _read_path(context, field_path)
        old_value = patch.get("old_value")
        if current is MISSING:
            current = None
        if already_applied:
            if current != patch.get("new_value"):
                raise ValueError(
                    f"applied value mismatch for {record_id}.{field_path}: "
                    f"expected {patch.get('new_value')!r}, current {current!r}"
                )
        else:
            if current != old_value:
                raise ValueError(
                    f"old value mismatch for {record_id}.{field_path}: "
                    f"expected {old_value!r}, current {current!r}"
                )
            _write_path(context, field_path, patch.get("new_value"))

    if expected_unpatched - patched_records != set(unpatched):
        raise ValueError(
            "unpatched_corrections must equal correction decisions without patches: "
            f"expected={sorted(expected_unpatched - patched_records)}, "
            f"declared={sorted(unpatched)}"
        )
    if set(unpatched) & patched_records:
        raise ValueError(f"unpatched correction also has a patch: {sorted(set(unpatched) & patched_records)}")

    frozen_contexts = _contexts(prospective)
    known_ids = set(
        entry.get("id")
        for entry in prospective.get("clinically_relevant_strains", [])
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    )
    for record_id in {patch["record_id"] for patch in patches}:
        context = frozen_contexts[record_id]
        errors = validate_frozen_context(context, known_component_ids=known_ids)
        if errors:
            raise ValueError(f"frozen context invalid for {record_id}: {errors}")
        if context.get("review_status") != "source_verified_pending_clinical_review":
            raise ValueError(f"patch must not change review status for {record_id}")
    return contexts, prospective


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write the validated patch")
    args = parser.parse_args()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    disposition = json.loads(DISPOSITION.read_text(encoding="utf-8"))
    _, prospective = validate(registry, disposition)
    if args.apply and not _already_applied(registry, disposition):
        _atomic_write(REGISTRY, prospective)
        print(f"applied {len(disposition['patches'])} batch-1 field patches; review statuses unchanged")
    elif args.apply:
        print("batch-1 field patches already applied; review statuses unchanged")
    else:
        print(f"validated {len(disposition['patches'])} batch-1 field patches (dry run; no files changed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
