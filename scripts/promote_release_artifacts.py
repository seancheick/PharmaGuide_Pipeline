#!/usr/bin/env python3
"""Atomically promote gated catalog candidates with rollback.

The snapshot builder writes and validates sibling candidate directories first.
This module is the only step allowed to replace the live ``dist`` and
``final_db_output`` directories.
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path
from typing import Optional


def _remove_directory(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def _require_atomic_sibling(candidate: Path, live: Path) -> None:
    if candidate.parent.resolve() != live.parent.resolve():
        raise ValueError(
            f"candidate {candidate} must be a sibling of {live} so promotion "
            "uses an atomic same-filesystem rename"
        )


def promote_release_artifacts(
    *,
    candidate_dist: Path,
    candidate_final: Path,
    live_dist: Path,
    live_final: Path,
) -> None:
    """Rename both gated candidates into place, restoring both on failure."""
    candidate_dist = candidate_dist.resolve()
    candidate_final = candidate_final.resolve()
    live_dist = live_dist.resolve()
    live_final = live_final.resolve()

    for candidate in (candidate_dist, candidate_final):
        if not candidate.is_dir():
            raise FileNotFoundError(f"release candidate directory missing: {candidate}")
    _require_atomic_sibling(candidate_dist, live_dist)
    _require_atomic_sibling(candidate_final, live_final)

    backup_dist = live_dist.with_name(f".{live_dist.name}.release-backup")
    backup_final = live_final.with_name(f".{live_final.name}.release-backup")
    _remove_directory(backup_dist)
    _remove_directory(backup_final)

    dist_promoted = False
    final_promoted = False
    try:
        if live_dist.exists():
            os.replace(live_dist, backup_dist)
        os.replace(candidate_dist, live_dist)
        dist_promoted = True

        if live_final.exists():
            os.replace(live_final, backup_final)
        os.replace(candidate_final, live_final)
        final_promoted = True
    except Exception:
        # Reverse the partial transaction. Moving a promoted directory back to
        # its candidate name preserves it for diagnosis while the last known
        # good live directories are restored.
        if final_promoted and live_final.exists():
            os.replace(live_final, candidate_final)
        if backup_final.exists():
            os.replace(backup_final, live_final)
        if dist_promoted and live_dist.exists():
            os.replace(live_dist, candidate_dist)
        if backup_dist.exists():
            os.replace(backup_dist, live_dist)
        raise

    _remove_directory(backup_dist)
    _remove_directory(backup_final)


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Promote fully gated catalog candidates into live paths."
    )
    parser.add_argument("--dist-candidate", required=True)
    parser.add_argument("--final-candidate", required=True)
    parser.add_argument("--dist-dir", default="scripts/dist")
    parser.add_argument("--final-dir", default="scripts/final_db_output")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    promote_release_artifacts(
        candidate_dist=Path(args.dist_candidate),
        candidate_final=Path(args.final_candidate),
        live_dist=Path(args.dist_dir),
        live_final=Path(args.final_dir),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
