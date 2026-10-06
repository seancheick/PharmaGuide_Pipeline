"""scripts/ci_skip_guard.py: a CI skip outside the local-only files fails."""

from __future__ import annotations

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ci_skip_guard import undeclared_skips  # noqa: E402
from test_profiles import LOCAL_ONLY_TEST_FILES  # noqa: E402

_JUNIT = """<?xml version="1.0"?>
<testsuites><testsuite>
  <testcase classname="scripts.tests.{local}" name="test_corpus"><skipped message="35491 canary not rebuilt yet"/></testcase>
  <testcase classname="scripts.tests.test_ran.TestThing" name="test_ok"/>
  {extra}
</testsuite></testsuites>
"""


def _write(tmp_path, extra=""):
    local = "test_active_count_reconciliation"
    path = tmp_path / "junit.xml"
    path.write_text(_JUNIT.format(local=local, extra=extra))
    return path


def test_declared_local_only_skips_pass(tmp_path):
    assert undeclared_skips(_write(tmp_path)) == []


def test_a_skip_in_an_undeclared_file_fails(tmp_path):
    extra = (
        '<testcase classname="scripts.tests.test_new_corpus_check.TestX" name="test_y">'
        '<skipped message="no build directory available"/></testcase>'
    )

    assert undeclared_skips(_write(tmp_path, extra)) == [
        "test_new_corpus_check.py::test_y — no build directory available",
    ]


def test_every_local_only_file_exists():
    tests_dir = Path(__file__).resolve().parent
    assert all((tests_dir / name).exists() for name in LOCAL_ONLY_TEST_FILES)


def test_unrelated_skip_in_a_declared_file_is_rejected(tmp_path):
    p = _write(tmp_path)
    p.write_text(p.read_text().replace('35491 canary not rebuilt yet', 'optional dependency unexpectedly missing'))
    assert undeclared_skips(p)


def test_local_profile_rejects_missing_corpus_skip(tmp_path):
    assert undeclared_skips(_write(tmp_path), profile='local')


def test_empty_junit_is_not_evidence_of_a_completed_suite(tmp_path):
    p = tmp_path / 'empty.xml'
    p.write_text('<testsuites/>')
    assert undeclared_skips(p)


def test_shards_cover_every_fast_file_exactly_once():
    from test_profiles import iter_profile_paths
    expected = set(iter_profile_paths('fast'))
    shards = [list(iter_profile_paths('fast', shard_index=i, shard_count=4)) for i in range(4)]
    assert all(shards)
    flattened = [p for shard in shards for p in shard]
    assert len(flattened) == len(set(flattened))
    assert set(flattened) == expected


def test_invalid_shard_does_not_fall_back_to_the_whole_suite():
    import pytest
    from test_profiles import iter_profile_paths
    for index, count in [(4, 4), (-1, 4), (0, 0), (0, None)]:
        with pytest.raises(ValueError):
            list(iter_profile_paths('fast', shard_index=index, shard_count=count))


@pytest.mark.parametrize('shard,index', [('1/4', 0), ('4/4', 3)])
def test_existing_shard_cli_uses_the_canonical_partition(monkeypatch, capsys, shard, index):
    from test_profiles import main, iter_profile_paths
    monkeypatch.setattr(sys, 'argv', ['test_profiles.py', 'fast', '--shard', shard])
    assert main() == 0
    repo = Path(__file__).resolve().parents[2]
    assert capsys.readouterr().out.splitlines() == [str(p.relative_to(repo)) for p in iter_profile_paths('fast', shard_index=index, shard_count=4)]


def test_conflicting_shard_interfaces_fail_closed(monkeypatch):
    from test_profiles import main
    monkeypatch.setattr(sys, 'argv', ['test_profiles.py', 'fast', '--shard', '1/4', '--shard-index', '0', '--shard-count', '4'])
    with pytest.raises(SystemExit):
        main()


def test_preparation_inventory_runs_source_cases_in_mixed_files():
    from test_profiles import preparation_phase
    assert preparation_phase('test_v4_safety_parity_release.py', 'test_exact_high_risk_still_yields_caution')[0] == 'source'
    assert preparation_phase('test_v4_safety_parity_release.py', 'test_v3_blocked_release_products_remain_v4_blocked')[0] == 'artifact'
    assert preparation_phase('test_submission_print_fidelity.py', 'test_scoring_refuses_a_line_whose_dose_is_missing')[0] == 'source'
    assert preparation_phase('test_submission_print_fidelity.py', 'test_preparation_costs_nothing_at_the_working_operating_point')[0] == 'external'
    assert preparation_phase('test_manifest_contract.py', 'test_staged_manifest_has_every_required_key')[0] == 'source'


def test_preparation_evidence_refuses_missing_coverage_skips_and_incomplete_outcomes():
    from preflight import _valid_test_evidence
    evidence = {'completed': True, 'exit_code': 0, 'collection_errors': [],
        'selection': {'args': ['scripts/tests']},
        'nodes': [{'nodeid': 'a::test_one', 'phase': 'source', 'reason': 'source owner'}],
        'outcomes': {'a::test_one': [
            {'when': stage, 'outcome': 'passed'} for stage in ['setup', 'call', 'teardown']]}}
    assert _valid_test_evidence(evidence)
    evidence['outcomes']['a::test_one'][1]['outcome'] = 'skipped'
    assert not _valid_test_evidence(evidence)
    evidence['outcomes'] = {}
    assert not _valid_test_evidence(evidence)
    evidence['completed'] = False
    assert not _valid_test_evidence(evidence, inventory=True)


def test_preparation_does_not_infer_artifact_dependency_from_synthetic_path_tokens():
    from test_profiles import preparation_phase
    for filename, name in [
        ('test_release_artifact_paths.py', 'test_default_paths_resolve_to_live_build'),
        ('test_run_pipeline_output_prefix.py', 'test_resolve_path'),
        ('test_graceful_degradation.py', 'test_graceful_degradation'),
        ('test_cert_audit_canary.py', 'test_audit_report_recency_gated_b4a_does_not_credit_stale'),
    ]:
        assert preparation_phase(filename, name)[0] == 'source'


def test_preparation_inventory_order_is_not_coverage_but_missing_or_changed_nodes_are():
    from preflight import _same_preparation_inventory
    one = {'nodeid': 'one', 'phase': 'source', 'reason': 'owner'}
    two = {'nodeid': 'two', 'phase': 'artifact', 'reason': 'generated'}
    assert _same_preparation_inventory({'nodes': [one, two]}, {'nodes': [two, one]})
    assert not _same_preparation_inventory({'nodes': [one, two]}, {'nodes': [one]})
    assert not _same_preparation_inventory({'nodes': [one, two]}, {'nodes': [one, dict(two, phase='source')]})
