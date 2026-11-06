"""Full-producer parity for code invalidation with unchanged stage results."""
from copy import deepcopy
import json
from pathlib import Path

import pytest


@pytest.mark.parametrize('changed_stage', ['clean', 'enrich'])
def test_code_recheck_with_identical_real_results_matches_full_rebuild(
    tmp_path, monkeypatch, changed_stage,
):
    """A source invalidation needs a recheck, not automatic downstream work.

    Only the source stamp is changed in this infrastructure test. Both arms run
    the actual producers on repository raw-label fixtures; neither the semantic
    comparison nor the full-rebuild oracle is replaced by a synthetic scorer.
    """
    import pipeline_incremental as incremental
    from audits.quality_redesign.replay import without_volatile
    from pipeline_freshness import CODE_FINGERPRINT_KEY
    from run_pipeline import PipelineRunner
    from test_pipeline_incremental import _pin_comparison_dates

    _pin_comparison_dates(monkeypatch)
    captured_snapshot = incremental.current_snapshot
    invalidated = False

    def snapshot(repo):
        value = deepcopy(captured_snapshot(repo))
        if invalidated:
            value['stages'][changed_stage][CODE_FINGERPRINT_KEY] = incremental.digest(
                {'infrastructure_test_source_revision': changed_stage})
        return value

    monkeypatch.setattr(incremental, 'current_snapshot', snapshot)
    raw = tmp_path / 'raw'
    raw.mkdir()
    fixtures = Path(__file__).parent / 'fixtures'
    for name in ('incremental_creatine_336362_raw.json', 'evidence_truth_231852_raw.json'):
        row = json.loads((fixtures / name).read_text())
        (raw / (str(row['id']) + '.json')).write_text(json.dumps(row))
    runner = PipelineRunner()
    prefix = tmp_path / 'selective'
    incremental.run_incremental(runner, raw, prefix)
    old = {stage: incremental.stage_products(directory, stage)
           for stage, directory in zip(incremental.STAGES, incremental.stage_directories(prefix))}
    calls = []
    for stage in incremental.STAGES:
        original = getattr(runner, 'run_' + stage)

        def tracked(*args, _stage=stage, _original=original, **kwargs):
            calls.append(_stage)
            return _original(*args, **kwargs)

        monkeypatch.setattr(runner, 'run_' + stage, tracked)
    invalidated = True
    result = incremental.run_incremental(runner, raw, prefix)
    assert calls == [changed_stage]
    assert result['stages'] == {
        stage: sorted(old[stage]) if stage == changed_stage else []
        for stage in incremental.STAGES}
    # The control stages must retain their exact prior persisted products.
    for stage, directory in zip(incremental.STAGES, incremental.stage_directories(prefix)):
        if stage != changed_stage:
            assert incremental.stage_products(directory, stage) == old[stage]
    full = tmp_path / 'full'
    assert runner.run_pipeline(raw_dir=str(raw), output_prefix=str(full),
                               strict_release_gates=True)['success']
    kinds = {'clean': 'cleaned', 'enrich': 'enriched', 'score': 'scored'}
    for stage, selected_dir, full_dir in zip(
        incremental.STAGES, incremental.stage_directories(prefix), incremental.stage_directories(full),
    ):
        selected = incremental.stage_products(selected_dir, stage)
        expected = incremental.stage_products(full_dir, stage)
        assert {pid: without_volatile(row, kinds[stage]) for pid, row in selected.items()} == {
            pid: without_volatile(row, kinds[stage]) for pid, row in expected.items()}
