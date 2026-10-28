"""Resolve release artifacts without conflating candidates with live output."""

from __future__ import annotations

import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def release_candidate_root() -> Path | None:
    value = os.environ.get("PG_RELEASE_CANDIDATE_ROOT", "").strip()
    return Path(value) if value else None


def catalog_dist_dir() -> Path:
    candidate = release_candidate_root()
    return candidate / "dist" if candidate else REPO_ROOT / "scripts" / "dist"


def final_build_dir() -> Path:
    candidate = release_candidate_root()
    return (
        candidate / "final_db_output"
        if candidate
        else REPO_ROOT / "scripts" / "final_db_output"
    )


def canary_baseline_dir(repo_root: Path | None = None) -> Path:
    """The reviewed canary baseline shared by assertions and release readiness."""
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    return root / "reports" / "baseline_pre_e1_2_2" / "quality_source_reviewed_20261028"
