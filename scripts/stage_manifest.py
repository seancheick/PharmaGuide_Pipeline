"""Single authority for pipeline stage output ownership."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Sequence

from run_artifacts import ensure_run_id


MANIFEST_NAME = ".stage_manifest.json"
SCHEMA_VERSION = "1.0.0"


class StageManifestError(ValueError):
    """A stage directory cannot prove ownership of its materialized files."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_stage_manifest(
    stage_dir: Path,
    stage: str,
    owned_files: Iterable[Path],
    *,
    processing_complete: bool = True,
    run_id: str | None = None,
) -> Path:
    """Atomically record the exact files produced by one stage run."""
    stage_dir = Path(stage_dir).resolve()
    stage_dir.mkdir(parents=True, exist_ok=True)
    resolved_files = sorted(
        {Path(path).resolve() for path in owned_files}, key=lambda path: path.name
    )

    for path in resolved_files:
        if path.parent != stage_dir:
            raise StageManifestError(f"Owned file is outside stage directory: {path}")
        if not path.is_file():
            raise StageManifestError(f"Owned file is missing: {path.name}")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "stage": stage,
        "generated_at": datetime.now(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        ),
        "processing_complete": bool(processing_complete),
        "owned_files": [path.name for path in resolved_files],
        "content_sha256": {path.name: _sha256(path) for path in resolved_files},
    }
    if run_id is not None:
        manifest["run_id"] = ensure_run_id(run_id)
    manifest_path = stage_dir / MANIFEST_NAME
    temp_path = stage_dir / f"{MANIFEST_NAME}.tmp"
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp_path, manifest_path)
    return manifest_path


def write_stage_manifest_from_directory(
    stage_dir: Path,
    stage: str,
    *,
    patterns: Sequence[str] = ("*.json",),
    run_id: str | None = None,
) -> Path:
    """Write ownership for the materialized top-level outputs of a stage."""
    stage_dir = Path(stage_dir).resolve()
    owned = sorted(
        {
            path
            for pattern in patterns
            for path in stage_dir.glob(pattern)
            if path.is_file() and not path.name.startswith(".")
        },
        key=lambda path: path.name,
    ) if stage_dir.is_dir() else []
    if not owned:
        raise StageManifestError(f"Stage produced no owned files: {stage_dir}")
    return write_stage_manifest(stage_dir, stage, owned, run_id=run_id)


def quarantine_stage_outputs(
    stage_dir: Path,
    *,
    patterns: Sequence[str] = ("*.json", "*.jsonl"),
) -> List[Path]:
    """Remove prior materialized outputs from a fresh stage run's scope."""
    stage_dir = Path(stage_dir).resolve()
    if not stage_dir.is_dir():
        return []
    candidates = {
        path
        for pattern in patterns
        for path in stage_dir.glob(pattern)
        if path.is_file() and not path.name.startswith(".")
    }
    manifest_path = stage_dir / MANIFEST_NAME
    if manifest_path.is_file():
        candidates.add(manifest_path)
    if not candidates:
        return []

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    quarantine_dir = stage_dir / "quarantine" / "stale_outputs" / timestamp
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    moved = []
    for source in sorted(candidates, key=lambda path: path.name):
        destination = quarantine_dir / source.name
        source.replace(destination)
        moved.append(destination)
    return moved


def select_stage_input_files(
    stage_dir: Path,
    expected_stage: str,
    *,
    require_manifest: bool = False,
    patterns: Sequence[str] = ("*.json",),
) -> List[Path]:
    """Return only verified files owned by a successful upstream stage.

    A present manifest is always authoritative. Compatibility callers may
    allow a missing manifest, but a malformed, incomplete, or contradictory
    manifest never falls back to a directory scan.
    """
    stage_dir = Path(stage_dir).resolve()
    if not stage_dir.is_dir():
        raise StageManifestError(f"Stage directory is missing: {stage_dir}")

    discovered = sorted(
        {
            path
            for pattern in patterns
            for path in stage_dir.glob(pattern)
            if path.is_file() and not path.name.startswith(".")
        },
        key=lambda path: path.name,
    )
    manifest_path = stage_dir / MANIFEST_NAME
    if not manifest_path.exists():
        if require_manifest:
            raise StageManifestError(f"Stage manifest is missing: {manifest_path}")
        return discovered

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StageManifestError(f"Stage manifest is unreadable: {exc}") from exc

    if not isinstance(manifest, dict):
        raise StageManifestError("Stage manifest must be a JSON object")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise StageManifestError("Stage manifest schema version is unsupported")
    if manifest.get("stage") != expected_stage:
        raise StageManifestError(
            f"Stage manifest names {manifest.get('stage')!r}; "
            f"expected {expected_stage!r}"
        )
    if manifest.get("processing_complete") is not True:
        raise StageManifestError("Stage manifest is not marked complete")

    names = manifest.get("owned_files")
    checksums = manifest.get("content_sha256")
    if not isinstance(names, list) or not names:
        raise StageManifestError("Stage manifest owns no files")
    if len(names) != len(set(names)):
        raise StageManifestError("Stage manifest contains duplicate owned files")
    if not isinstance(checksums, dict):
        raise StageManifestError("Stage manifest is missing content checksums")

    owned: List[Path] = []
    for name in names:
        if not isinstance(name, str) or Path(name).name != name:
            raise StageManifestError(f"Invalid owned filename: {name!r}")
        path = stage_dir / name
        if not path.is_file():
            raise StageManifestError(f"Owned file is missing: {name}")
        expected_hash = checksums.get(name)
        if not isinstance(expected_hash, str) or _sha256(path) != expected_hash:
            raise StageManifestError(f"Owned file checksum mismatch: {name}")
        if any(path.match(pattern) for pattern in patterns):
            owned.append(path)

    unowned = sorted(path.name for path in set(discovered) - set(owned))
    if unowned:
        raise StageManifestError(
            "Stage directory contains unowned files: " + ", ".join(unowned)
        )
    if not owned:
        raise StageManifestError("Stage manifest owns no consumable files")
    return sorted(owned, key=lambda path: path.name)
