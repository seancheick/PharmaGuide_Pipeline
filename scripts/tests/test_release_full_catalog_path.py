import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "release_full.sh"
INTERACTION_SCRIPT = Path(__file__).resolve().parents[1] / "rebuild_interaction_db.sh"
INTERACTION_VERSION_CONFIG = (
    Path(__file__).resolve().parents[1] / "config" / "interaction_db_release.json"
)


def test_release_full_uses_only_gated_snapshot_for_catalog_mutation() -> None:
    source = SCRIPT.read_text()

    assert source.count("bash scripts/rebuild_dashboard_snapshot.sh") == 2
    assert '"$PG_PYTHON" scripts/build_all_final_dbs.py' not in source
    assert '"$PG_PYTHON" scripts/release_catalog_artifact.py' not in source


def test_interaction_import_fallback_uses_gated_catalog_path() -> None:
    source = INTERACTION_SCRIPT.read_text()

    assert "bash scripts/rebuild_dashboard_snapshot.sh" in source
    assert '"$PG_PYTHON" scripts/release_catalog_artifact.py' not in source


def test_interaction_rebuild_default_comes_from_tracked_release_config() -> None:
    config = json.loads(INTERACTION_VERSION_CONFIG.read_text())
    source = INTERACTION_SCRIPT.read_text()
    release_source = SCRIPT.read_text()

    assert config["interaction_db_version"] == "1.0.10"
    assert config["build_time_utc"] == "2026-07-29T16:30:00Z"
    assert 'INTERACTION_VERSION_CONFIG="$SCRIPT_DIR/config/interaction_db_release.json"' in source
    assert "interaction_db_version" in source
    assert "build_time_utc" in source
    assert '--build-time "$INTERACTION_BUILD_TIME"' in source
    assert (
        '"$REPO_ROOT/scripts/config/interaction_db_release.json"'
        in release_source
    )
    assert 'INTERACTION_VERSION="1.0.2"' not in source


def test_interaction_rebuild_regenerates_the_derived_suppai_feed() -> None:
    source = INTERACTION_SCRIPT.read_text()
    release_source = SCRIPT.read_text()

    assert 'SUPPAI_DIR="${PHARMAGUIDE_SUPPAI_DIR:-' in source
    assert '--suppai-dir "$SUPPAI_DIR"' in source
    assert '--build-time "$INTERACTION_BUILD_TIME"' in source
    assert 'if [[ ! -f "$OUTPUT_DIR/research_pairs.json" ]]' not in source
    assert '"$REPO_ROOT/scripts/data/ingredient_quality_map.json"' in release_source
    assert '"$SUPPAI_DIR/cui_metadata.json"' in release_source
    assert '"$SUPPAI_DIR/interaction_id_dict.json"' in release_source
    assert '"$SUPPAI_DIR/meta.json"' in release_source
    assert '"$SUPPAI_DIR/paper_metadata.json"' in release_source
    assert '"$SUPPAI_DIR/sentence_dict.json"' in release_source
