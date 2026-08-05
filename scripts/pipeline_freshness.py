"""Content fingerprints for pipeline inputs that must trigger regeneration."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable


REFERENCE_FINGERPRINT_KEY = "reference_data_sha256_v1"


def _reference_data_files(repo_root: Path) -> list[Path]:
    data_dir = Path(repo_root).resolve() / "scripts" / "data"
    return sorted(
        {
            *data_dir.glob("*.json"),
            *(data_dir / "curated_overrides").glob("*.json"),
        },
        key=lambda path: path.relative_to(repo_root).as_posix(),
    )


def _content_set_fingerprint(paths: Iterable[Path], *, root: Path) -> str:
    """Hash relative paths and bytes so touches do not look like data changes."""
    root = Path(root).resolve()
    digest = hashlib.sha256()
    for path in sorted(
        {Path(path).resolve() for path in paths},
        key=lambda item: item.relative_to(root).as_posix(),
    ):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        file_digest = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                file_digest.update(chunk)
        # Fixed-width digest marks the file boundary unambiguously.
        digest.update(file_digest.digest())
    return digest.hexdigest()


def enrichment_reference_fingerprint(repo_root: Path) -> str:
    """Return the deterministic reference-data input stamp for enrichment."""
    repo_root = Path(repo_root).resolve()
    return _content_set_fingerprint(
        _reference_data_files(repo_root),
        root=repo_root,
    )


def enrichment_reference_freshness_issues(repo_root: Path) -> list[str]:
    """Return enrich manifests that do not match current reference contents."""
    repo_root = Path(repo_root).resolve()
    reference_files = _reference_data_files(repo_root)
    if not reference_files:
        return []

    enriched_dirs = sorted(
        {
            output.parent
            for output in (
                repo_root / "scripts" / "products"
            ).glob("output_*_enriched/enriched/*.json")
            if output.is_file() and not output.name.startswith(".")
        },
        key=str,
    )
    if not enriched_dirs:
        return []

    current = enrichment_reference_fingerprint(repo_root)
    issues: list[str] = []
    for stage_dir in enriched_dirs:
        manifest_path = stage_dir / ".stage_manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            issues.append(f"{manifest_path}: unreadable ({exc})")
            continue

        if not isinstance(manifest, dict):
            issues.append(f"{manifest_path}: malformed manifest root")
            continue
        input_fingerprints = manifest.get("input_fingerprints")
        if input_fingerprints is not None and not isinstance(
            input_fingerprints, dict
        ):
            issues.append(f"{manifest_path}: malformed input_fingerprints")
            continue

        declared = (input_fingerprints or {}).get(REFERENCE_FINGERPRINT_KEY)
        if declared != current:
            reason = "missing" if declared is None else "content mismatch"
            issues.append(
                f"{manifest_path}: reference_data fingerprint {reason}"
            )
    return issues
