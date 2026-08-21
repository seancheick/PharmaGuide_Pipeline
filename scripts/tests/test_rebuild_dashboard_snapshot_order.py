from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "rebuild_dashboard_snapshot.sh"


def test_snapshot_gates_candidates_before_live_promotion() -> None:
    source = SCRIPT.read_text()

    promotion = source.index("promote_release_artifacts.py")
    freshness_gate = source.index('run_strict_gate "catalog artifact freshness"')
    candidate_stage = source.index("--output-dir \"$DIST_CANDIDATE\"")

    assert candidate_stage < freshness_gate < promotion
    assert "--output-dir scripts/dist" not in source
    assert "rm -rf scripts/final_db_output" not in source
    assert source.rindex("run_strict_gate", 0, promotion) < promotion


def test_source_gates_run_before_catalog_build() -> None:
    source = SCRIPT.read_text()
    build = source.index('"$PG_PYTHON" scripts/build_final_db.py')

    for label in (
        'run_strict_gate "source-of-truth matrix"',
        'run_strict_gate "cleaner/IQD row contract"',
        'run_strict_gate "enrichment/IQD source-of-truth contract"',
        'run_strict_gate "clinical drift contract"',
        'run_strict_gate "active identity integrity"',
        'run_strict_gate "RDA/UL emitted-reference stamp parity"',
        'run_strict_gate "scoring assessment readiness"',
    ):
        assert source.index(label) < build


def test_candidate_only_mode_preserves_gated_artifacts_without_live_promotion() -> None:
    source = SCRIPT.read_text()

    assert "--candidate-only" in source
    assert "--candidate-root" in source
    assert '[[ "$CANDIDATE_ROOT" = /* ]]' in source
    assert '[[ ! -e "$CANDIDATE_ROOT" ]]' in source

    candidate_branch = source.index(
        'if [[ "$CANDIDATE_ONLY" == "true" ]]; then',
        source.index('run_strict_gate "catalog artifact freshness"'),
    )
    promotion = source.index('"$PG_PYTHON" scripts/promote_release_artifacts.py')

    assert candidate_branch < promotion
    assert 'mv "$CANDIDATE_STAGE" "$CANDIDATE_ROOT"' in source
    assert 'DIST_OUTPUT="$CANDIDATE_ROOT/dist"' in source
    assert 'FINAL_OUTPUT="$CANDIDATE_ROOT/final_db_output"' in source


def test_snapshot_build_uses_strict_export_error_gate() -> None:
    source = SCRIPT.read_text()
    build_start = source.index('"$PG_PYTHON" scripts/build_final_db.py')
    build_end = source.index('run_strict_gate "detail-blob field completeness"')

    assert "--strict" in source[build_start:build_end]
