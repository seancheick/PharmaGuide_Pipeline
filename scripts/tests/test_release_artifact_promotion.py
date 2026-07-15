from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import promote_release_artifacts as promotion  # noqa: E402


def _dir(path: Path, marker: str) -> Path:
    path.mkdir()
    (path / "marker.txt").write_text(marker)
    return path


def test_promotes_both_candidates_and_removes_backups(tmp_path: Path) -> None:
    live_dist = _dir(tmp_path / "dist", "old-dist")
    live_final = _dir(tmp_path / "final", "old-final")
    candidate_dist = _dir(tmp_path / ".dist-candidate", "new-dist")
    candidate_final = _dir(tmp_path / ".final-candidate", "new-final")

    promotion.promote_release_artifacts(
        candidate_dist=candidate_dist,
        candidate_final=candidate_final,
        live_dist=live_dist,
        live_final=live_final,
    )

    assert (live_dist / "marker.txt").read_text() == "new-dist"
    assert (live_final / "marker.txt").read_text() == "new-final"
    assert not candidate_dist.exists()
    assert not candidate_final.exists()
    assert not (tmp_path / ".dist.release-backup").exists()
    assert not (tmp_path / ".final.release-backup").exists()


def test_second_promotion_failure_restores_both_live_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    live_dist = _dir(tmp_path / "dist", "old-dist")
    live_final = _dir(tmp_path / "final", "old-final")
    candidate_dist = _dir(tmp_path / ".dist-candidate", "new-dist")
    candidate_final = _dir(tmp_path / ".final-candidate", "new-final")
    real_replace = os.replace

    def fail_final_candidate(source, destination):
        if Path(source) == candidate_final:
            raise OSError("injected final promotion failure")
        return real_replace(source, destination)

    monkeypatch.setattr(promotion.os, "replace", fail_final_candidate)

    with pytest.raises(OSError, match="injected final promotion failure"):
        promotion.promote_release_artifacts(
            candidate_dist=candidate_dist,
            candidate_final=candidate_final,
            live_dist=live_dist,
            live_final=live_final,
        )

    assert (live_dist / "marker.txt").read_text() == "old-dist"
    assert (live_final / "marker.txt").read_text() == "old-final"
