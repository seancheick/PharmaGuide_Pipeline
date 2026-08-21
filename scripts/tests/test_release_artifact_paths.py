"""Path selection for live and preserved release artifacts."""

from pathlib import Path


def test_default_paths_resolve_to_live_build(monkeypatch) -> None:
    monkeypatch.delenv("PG_RELEASE_CANDIDATE_ROOT", raising=False)
    from scripts.release_artifact_paths import catalog_dist_dir, final_build_dir

    repo_root = Path(__file__).resolve().parents[2]
    assert catalog_dist_dir() == repo_root / "scripts" / "dist"
    assert final_build_dir() == repo_root / "scripts" / "final_db_output"


def test_candidate_paths_resolve_to_preserved_pair(tmp_path, monkeypatch) -> None:
    candidate = tmp_path / "candidate"
    monkeypatch.setenv("PG_RELEASE_CANDIDATE_ROOT", str(candidate))
    from scripts.release_artifact_paths import catalog_dist_dir, final_build_dir

    assert catalog_dist_dir() == candidate / "dist"
    assert final_build_dir() == candidate / "final_db_output"
