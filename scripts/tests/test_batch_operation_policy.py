from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "batch_run_all_datasets.sh"


def test_targeted_runs_default_to_pipeline_only_and_require_release_opt_in() -> None:
    source = SCRIPT.read_text()

    assert '--pipeline-only)' in source
    assert '--release)' in source
    assert 'if [ -n "$TARGET_DATASETS" ] && [ "$RELEASE_EXPLICIT" != "1" ]' in source
    assert 'PIPELINE_ONLY=1' in source
    assert "Targeted runs use this safe default" in source
