from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "release_full.sh"
INTERACTION_SCRIPT = Path(__file__).resolve().parents[1] / "rebuild_interaction_db.sh"


def test_release_full_uses_only_gated_snapshot_for_catalog_mutation() -> None:
    source = SCRIPT.read_text()

    assert source.count("bash scripts/rebuild_dashboard_snapshot.sh") == 2
    assert '"$PG_PYTHON" scripts/build_all_final_dbs.py' not in source
    assert '"$PG_PYTHON" scripts/release_catalog_artifact.py' not in source


def test_interaction_import_fallback_uses_gated_catalog_path() -> None:
    source = INTERACTION_SCRIPT.read_text()

    assert "bash scripts/rebuild_dashboard_snapshot.sh" in source
    assert '"$PG_PYTHON" scripts/release_catalog_artifact.py' not in source
