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
