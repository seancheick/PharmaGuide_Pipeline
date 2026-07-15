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
    ):
        assert source.index(label) < build
