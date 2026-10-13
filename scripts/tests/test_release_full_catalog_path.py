import json
import re
from pathlib import Path

import pytest


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


def test_release_image_probe_shares_extractor_eligibility() -> None:
    source = SCRIPT.read_text().split("step3_needs_run()", 1)[1].split("if (( SKIP_PRODUCT_IMAGES", 1)[0]
    assert "from extract_product_images import needs_image_extraction" in source
    assert "SELECT COUNT(*)" not in source
    assert ')" || return 0' in source  # probe errors must not silently skip work


def test_release_full_enters_the_global_lock_before_any_release_gate() -> None:
    source = SCRIPT.read_text()

    wrapper = 'scripts/run_with_release_lock.py'
    assert wrapper in source
    assert source.index(wrapper) < source.index(
        'run_strict_gate "source-of-truth matrix"'
    )


def test_interaction_import_fallback_uses_gated_catalog_path() -> None:
    source = INTERACTION_SCRIPT.read_text()

    assert "bash scripts/rebuild_dashboard_snapshot.sh" in source
    assert '"$PG_PYTHON" scripts/release_catalog_artifact.py' not in source


def test_interaction_rebuild_default_comes_from_tracked_release_config() -> None:
    config = json.loads(INTERACTION_VERSION_CONFIG.read_text())
    source = INTERACTION_SCRIPT.read_text()
    release_source = SCRIPT.read_text()

    # The contract is that the rebuild reads the tracked config, not that the
    # version never moves: a curated rule change must be able to bump it.
    assert re.fullmatch(r"\d+\.\d+\.\d+", config["interaction_db_version"])
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", config["build_time_utc"])
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


def test_release_moves_the_app_hydration_pin_with_the_bundle() -> None:
    source = SCRIPT.read_text()
    publish = '--publish-flutter-pin "$FLUTTER_REPO"'
    verify = 'bash "$FLUTTER_REPO/tool/fetch_interaction_db.sh"'
    pin = "tool/interaction_db.release.json"

    # Published after every preflight gate, before anything reaches Supabase.
    assert source.index('run_strict_gate "Flutter import preflight"') < source.index(publish)
    assert source.index(publish) < source.index("# Step 5: Sync to Supabase")
    # The app's own hydration verifier checks pin, manifest and DB before the commit.
    assert source.index('run_strict_gate "Flutter bundle parity"') < source.index(verify)
    add_line = next(l for l in source.splitlines() if 'git -C "$FLUTTER_REPO" add' in l)
    status_line = next(l for l in source.splitlines() if "status --porcelain -- assets/db" in l)
    assert source.index(verify) < source.index(add_line)
    assert pin in add_line
    assert pin in status_line


def test_release_preflight_only_local_run_never_reaches_artifact_gates():
    import os
    import subprocess
    result = subprocess.run(
        ["bash", str(SCRIPT), "--preflight-only", "--skip-supabase", "--skip-flutter"],
        capture_output=True, text=True, env={**os.environ}, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Release prerequisites passed" in result.stdout
    assert "Step 1/8" not in result.stdout


def test_release_checks_flutter_main_with_existing_release_base_owner():
    source = SCRIPT.read_text()
    publishing = source.split('if (( SKIP_FLUTTER == 0 ||', 1)[1].split('START_TS=', 1)[0]
    assert 'require_release_base "$FLUTTER_REPO" || exit 1' in publishing
    assert publishing.index('require_release_base "$FLUTTER_REPO"') < publishing.index('PREFLIGHT_ONLY == 1')


@pytest.mark.parametrize("prepared,stale,expected", [
    (True, False, "preserved"), (True, True, "refused"),
    (False, False, "fetched"),
])
def test_release_prepared_inputs_preserve_verified_submission_set(tmp_path, prepared, stale, expected):
    import os
    import shlex
    import subprocess

    source = SCRIPT.read_text()
    start = source.index("submission_labels_exist() {")
    stage_zero = source[start:source.index("# Step 1:", start)]
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "label.json").write_text("{}")
    manifests = [tmp_path / name for name in ["clean.json", "enrich.json", "score.json"]]
    for manifest in manifests:
        manifest.write_text("{}")
    os.utime(raw / "label.json", (1, 1))
    fake_python = tmp_path / "python"
    fake_python.write_text(
        "#!/bin/bash\n"
        'if [[ "$*" == *check-stage-manifests* ]]; then exit ' + str(int(stale)) + '; fi\n'
        'echo "$*" >> "$RELEASE_PROBE_CALLS"\n'
    )
    fake_python.chmod(0o755)
    calls = tmp_path / "calls"
    variables = {
        "PG_PYTHON": str(fake_python), "REPO_ROOT": str(tmp_path),
        "SUBMISSION_OUTPUT_DIR": str(raw), "SUBMISSION_PIPELINE_PREFIX": str(tmp_path / "out"),
        "SUBMISSION_CLEAN_MANIFEST": str(manifests[0]),
        "SUBMISSION_ENRICH_MANIFEST": str(manifests[1]),
        "SUBMISSION_SCORE_MANIFEST": str(manifests[2]),
    }
    harness = "set -e\nFORCE=0\nSKIP_SUPABASE=0\nSUPABASE_DRY_RUN=0\nPREPARED_INPUTS=" + str(int(prepared)) + "\n"
    harness += "\n".join(f"{k}={shlex.quote(v)}" for k, v in variables.items()) + "\n"
    harness += 'info(){ :; }; ok(){ :; }; skip(){ echo "$*"; }; err(){ echo "$*"; };\n'
    result = subprocess.run(["bash", "-c", harness + stage_zero], text=True, capture_output=True,
                            env={**os.environ, "RELEASE_PROBE_CALLS": str(calls)}, timeout=15)
    recorded = calls.read_text() if calls.exists() else ""
    if expected == "refused":
        assert result.returncode != 0
        assert "prepared" in (result.stdout + result.stderr).lower()
        assert "--fetch" not in recorded
        assert "run_pipeline.py" not in recorded
    elif expected == "preserved":
        assert result.returncode == 0, result.stdout + result.stderr
        assert "--fetch" not in recorded
        assert "run_pipeline.py" not in recorded
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert "--fetch" in recorded


def test_release_cli_accepts_prepared_inputs_in_read_only_preflight():
    import os
    import subprocess
    result = subprocess.run(
        ["bash", str(SCRIPT), "--preflight-only", "--skip-supabase", "--skip-flutter", "--prepared-inputs"],
        capture_output=True, text=True, env={**os.environ}, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Release prerequisites passed" in result.stdout
    assert "Step 1/8" not in result.stdout
