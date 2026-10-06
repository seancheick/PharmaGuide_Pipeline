"""Preflight must fail closed for required or corrupt inputs (G2)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import preflight


def _write_required_data(data_dir: Path, *, corrupt: str | None = None) -> None:
    data_dir.mkdir(parents=True)
    for filename, _description in preflight.CRITICAL_DATA_FILES:
        (data_dir / filename).write_text(
            "{" if filename == corrupt else json.dumps({"_metadata": {}}),
            encoding="utf-8",
        )


def test_quick_mode_blocks_corrupt_critical_json(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    _write_required_data(data_dir, corrupt="allergens.json")
    monkeypatch.setattr(preflight, "DATA_DIR", data_dir)

    result = preflight.run_preflight(quick=True)

    assert result["summary"]["json_valid"] is False
    assert result["summary"]["all_ok"] is False
    assert result["summary"]["exit_code"] == 1


def test_full_mode_blocks_missing_required_config_script_and_schema(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    config_dir = tmp_path / "config"
    scripts_dir = tmp_path / "scripts"
    _write_required_data(data_dir)
    config_dir.mkdir()
    scripts_dir.mkdir()
    monkeypatch.setattr(preflight, "DATA_DIR", data_dir)
    monkeypatch.setattr(preflight, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(preflight, "SCRIPTS_DIR", scripts_dir)
    monkeypatch.setattr(preflight, "IMPORTANT_DATA_FILES", [])
    monkeypatch.setattr(preflight, "OPTIONAL_DATA_FILES", [])
    monkeypatch.setattr(preflight, "validate_database_schema", lambda: {"ok": False})
    monkeypatch.setattr(preflight, "validate_iqm_br_collision", lambda: {"ok": True})

    result = preflight.run_preflight()

    assert result["summary"]["configs_ok"] is False
    assert result["summary"]["scripts_ok"] is False
    assert result["summary"]["schema_v5_ok"] is False
    assert result["summary"]["all_ok"] is False
    assert result["summary"]["exit_code"] == 1


def test_preflight_does_not_require_deleted_temporary_configs() -> None:
    assert all("tmp" not in filename for filename, _ in preflight.CONFIG_FILES)


def test_clinical_reference_artifacts_are_fail_closed_inputs() -> None:
    critical = {filename for filename, _ in preflight.CRITICAL_DATA_FILES}

    assert "timing_rules.json" in critical
    assert "medication_depletions.json" in critical


def test_cleaning_config_uses_portable_stage_root() -> None:
    config = json.loads((preflight.CONFIG_DIR / "cleaning_config.json").read_text())

    assert not config["paths"]["input_directory"].startswith("/Users/")
    assert Path(config["paths"]["output_directory"]).name != "cleaned"


def test_preparation_aggregates_independent_failures_and_blocks_dependencies(tmp_path):
    raw = tmp_path / 'raw'
    raw.mkdir()
    (raw / 'bad.json').write_text('{')
    checks = [
        {'name': 'one', 'command': ['fake', 'one']},
        {'name': 'two', 'command': ['fake', 'two']},
        {'name': 'dependent', 'command': ['fake'], 'requires': ['raw_inputs']},
    ]
    calls = []
    def run(command, **kwargs):
        import subprocess
        calls.append(command)
        return subprocess.CompletedProcess(command, 1, 'failed', '')
    result = preflight.run_preparation(tmp_path, raw, checks=checks, runner=run)
    assert {c['name'] for c in result['checks'] if c['status'] == 'failed'} >= {'raw_inputs', 'one', 'two'}
    assert next(c for c in result['checks'] if c['name'] == 'dependent')['status'] == 'blocked'
    assert len(calls) == 2
    assert not result['ready']


def test_preparation_reuses_only_intact_success_and_invalidates_inventory(tmp_path):
    import subprocess
    raw = tmp_path / 'raw'
    raw.mkdir()
    (raw / '1.json').write_text(json.dumps({'id': 1, 'ingredientRows': []}))
    scripts = tmp_path / 'scripts'
    scripts.mkdir()
    owner = scripts / 'owner.py'
    owner.write_text('one')
    checks = [{'name': 'probe', 'command': ['fake', '--check']}]
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, 'probe completed', '')
    report = tmp_path / 'report.json'
    first = preflight.run_preparation(tmp_path, raw, checks=checks, runner=run, report_path=report)
    assert first['ready']
    second = preflight.run_preparation(tmp_path, raw, checks=checks, runner=run, report_path=report)
    assert second['ready'] and len(calls) == 1
    owner.write_text('two')
    preflight.run_preparation(tmp_path, raw, checks=checks, runner=run, report_path=report)
    assert len(calls) == 2
    saved = json.loads(report.read_text())
    next(c for c in saved['checks'] if c['name'] == 'probe')['stdout'] = 'tampered'
    report.write_text(json.dumps(saved))
    preflight.run_preparation(tmp_path, raw, checks=checks, runner=run, report_path=report)
    assert len(calls) == 3
    (raw / 'duplicate.json').write_text(json.dumps({'id': 1, 'ingredientRows': []}))
    assert not preflight.run_preparation(tmp_path, raw, checks=checks, runner=run)['ready']


def test_preparation_mutation_during_check_blocks_green(tmp_path):
    import subprocess
    raw = tmp_path / 'raw'
    raw.mkdir()
    (raw / '1.json').write_text(json.dumps({'id': 1, 'ingredientRows': []}))
    def run(command, **kwargs):
        (raw / '2.json').write_text(json.dumps({'id': 1, 'ingredientRows': []}))
        return subprocess.CompletedProcess(command, 0, 'completed', '')
    result = preflight.run_preparation(tmp_path, raw,
        checks=[{'name': 'probe', 'command': ['fake']}], runner=run)
    assert not result['ready']
    assert result['checks'][-1]['name'] == 'inputs_stable'
    assert result['checks'][-1]['status'] == 'failed'


def test_preparation_reuses_success_even_when_unrelated_check_failed(tmp_path):
    import subprocess
    raw = tmp_path / 'raw'
    raw.mkdir()
    (raw / '1.json').write_text(json.dumps({'id': 1, 'ingredientRows': []}))
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, int(command[-1] == 'bad'), 'completed', '')
    checks = [{'name': name, 'command': ['fake', name]} for name in ['good', 'bad']]
    report = tmp_path / 'report.json'
    assert not preflight.run_preparation(tmp_path, raw, checks=checks, runner=run, report_path=report)['ready']
    assert not preflight.run_preparation(tmp_path, raw, checks=checks, runner=run, report_path=report)['ready']
    assert calls == [['fake', 'good'], ['fake', 'bad'], ['fake', 'bad']]


def test_preparation_receipt_invalidates_command_environment_and_raw_changes(tmp_path, monkeypatch):
    import subprocess
    raw = tmp_path / 'raw'
    raw.mkdir()
    label = raw / '1.json'
    label.write_text(json.dumps({'id': 1, 'ingredientRows': []}))
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, 'completed', '')
    report = tmp_path / 'report.json'
    checks = [{'name': 'probe', 'command': ['fake', 'one']}]
    def prepare():
        return preflight.run_preparation(tmp_path, raw, checks=checks, runner=run, report_path=report)
    assert prepare()['ready']
    checks[0]['command'] = ['fake', 'two']
    assert prepare()['ready'] and len(calls) == 2
    monkeypatch.setenv('PG_RUNTIME_SEMANTIC_OPTION', 'new')
    assert prepare()['ready'] and len(calls) == 3
    label.write_text(json.dumps({'id': 1, 'ingredientRows': [{'name': 'changed'}]}))
    assert prepare()['ready'] and len(calls) == 4
    label.unlink()
    assert not prepare()['ready']


def test_preparation_evidence_rejects_bare_canary_summary_and_missing_reference_payload():
    for evidence, stdout in [('canaries', 'Checked: 2  Failed: 0  Total: 2'), ('references', '{}')]:
        check = {'status': 'passed', 'exit_code': 0, 'command': ['fake'], 'completed': True,
                 'duration_seconds': 1, 'stdout': stdout, 'stderr': ''}
        check['integrity'] = preflight._digest(check)
        assert not preflight._valid_preparation_check(check, {'command': ['fake'], 'evidence': evidence})


def test_preparation_unknown_collection_skip_and_filtered_selection_are_not_success():
    evidence = {'completed': True, 'exit_code': 0,
        'nodes': [{'nodeid': 'test_one.py::test_one', 'phase': 'source', 'reason': 'source'}],
        'collection_skips': [{'nodeid': 'test_two.py', 'reason': 'missing dependency'}]}
    assert not preflight._valid_test_evidence(evidence, inventory=True)
    evidence['collection_skips'] = []
    evidence['selection'] = {'args': ['scripts/tests'], 'keyword': 'only_one'}
    assert not preflight._valid_test_evidence(evidence, inventory=True)


def test_preparation_hashes_environment_files_workflow_and_flutter_consumers(tmp_path, monkeypatch):
    raw = tmp_path / 'raw'
    raw.mkdir()
    (raw / '1.json').write_text(json.dumps({'id': 1, 'ingredientRows': []}))
    flutter = tmp_path / 'app'
    (flutter / 'lib').mkdir(parents=True)
    consumer = flutter / 'lib/consumer.dart'
    consumer.write_text('one')
    monkeypatch.setenv('FLUTTER_REPO', str(flutter))
    (tmp_path / '.env').write_text('KEY=secret')
    (tmp_path / '.github/workflows').mkdir(parents=True)
    workflow = tmp_path / '.github/workflows/tests.yml'
    workflow.write_text('one')
    first = preflight._preparation_inputs(tmp_path, raw)
    assert first['files']['.env'] != 'KEY=secret'
    consumer.write_text('two')
    assert preflight._preparation_inputs(tmp_path, raw) != first
    workflow.unlink()
    assert '.github/workflows/tests.yml' not in preflight._preparation_inputs(tmp_path, raw)['files']


def test_preparation_incomplete_checkpoint_and_evidence_survive_interruption(tmp_path):
    raw = tmp_path / 'raw'
    raw.mkdir()
    (raw / '1.json').write_text(json.dumps({'id': 1, 'ingredientRows': []}))
    report = tmp_path / 'receipt.json'
    def run(command, **kwargs):
        evidence = Path(kwargs['env']['PG_PREPARATION_REPORT'])
        evidence.write_text(json.dumps({'completed': False, 'failed_node': 'test_one'}))
        raise KeyboardInterrupt()
    import pytest
    with pytest.raises(KeyboardInterrupt):
        preflight.run_preparation(tmp_path, raw, checks=[{'name': 'probe', 'command': ['fake']}],
                                  runner=run, report_path=report)
    checkpoint = json.loads(report.read_text())
    assert checkpoint['completed'] is False and checkpoint['ready'] is False
    assert json.loads(Path(checkpoint['evidence_path']).read_text())['failed_node'] == 'test_one'


def test_preparation_stage_plan_uses_all_existing_json_and_jsonl_patterns(tmp_path, monkeypatch):
    import pipeline_freshness
    monkeypatch.setattr(pipeline_freshness, 'stage_freshness_issues', lambda root: [])
    raw = tmp_path / 'raw'
    raw.mkdir()
    (raw / '1.json').write_text(json.dumps({'id': 1, 'ingredientRows': []}))
    def earliest():
        return preflight.run_preparation(tmp_path, raw, checks=[])['regeneration']['earliest_stage']
    assert earliest() == 'clean'
    cleaned = tmp_path / 'scripts/products/output_Test/cleaned'
    cleaned.mkdir(parents=True)
    (cleaned / 'cleaned_batch_1.jsonl').write_text('{}\n')
    assert earliest() == 'enrich'
    enriched = tmp_path / 'scripts/products/output_Test_enriched/enriched'
    enriched.mkdir(parents=True)
    (enriched / 'batch.json').write_text('[]')
    assert earliest() == 'score'
    scored = tmp_path / 'scripts/products/output_Test_scored/scored'
    scored.mkdir(parents=True)
    (scored / 'batch.json').write_text('[]')
    assert earliest() is None


def test_preparation_receipt_invalidates_test_reference_and_runtime(tmp_path, monkeypatch):
    import subprocess
    raw = tmp_path / 'raw'
    raw.mkdir()
    (raw / '1.json').write_text(json.dumps({'id': 1, 'ingredientRows': []}))
    (tmp_path / 'scripts/tests').mkdir(parents=True)
    (tmp_path / 'scripts/data').mkdir()
    test = tmp_path / 'scripts/tests/test_owner.py'
    reference = tmp_path / 'scripts/data/map.json'
    test.write_text('one')
    reference.write_text('{}')
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, 'completed', '')
    def prepare():
        return preflight.run_preparation(tmp_path, raw,
            checks=[{'name': 'probe', 'command': ['fake']}], runner=run, report_path=tmp_path / 'receipt.json')
    assert prepare()['ready']
    test.write_text('two')
    assert prepare()['ready'] and len(calls) == 2
    reference.write_text('{"changed": true}')
    assert prepare()['ready'] and len(calls) == 3
    runtime = preflight._preparation_runtime
    monkeypatch.setattr(preflight, '_preparation_runtime', lambda: dict(runtime(), version='different'))
    assert prepare()['ready'] and len(calls) == 4


def test_preparation_non_object_raw_is_aggregated_as_failure(tmp_path):
    raw = tmp_path / 'raw'
    raw.mkdir()
    (raw / 'array.json').write_text('["id", "ingredientRows"]')
    result = preflight.run_preparation(tmp_path, raw, checks=[])
    assert not result['ready']
    assert any('JSON object' in issue for issue in result['inputs']['errors'])


def test_preparation_fingerprints_source_extensions_and_external_migrations(tmp_path, monkeypatch):
    raw = tmp_path / 'raw'
    raw.mkdir()
    (raw / '1.json').write_text(json.dumps({'id': 1, 'ingredientRows': []}))
    static = tmp_path / 'scripts/submission_review/static'
    static.mkdir(parents=True)
    javascript = static / 'app.js'
    javascript.write_text('one')
    flutter = tmp_path / 'app'
    migrations = flutter / 'supabase/migrations'
    migrations.mkdir(parents=True)
    sql = migrations / '20261006.sql'
    sql.write_text('one')
    monkeypatch.setenv('FLUTTER_REPO', str(flutter))
    first = preflight._preparation_inputs(tmp_path, raw)
    javascript.write_text('two')
    second = preflight._preparation_inputs(tmp_path, raw)
    assert first != second
    sql.write_text('two')
    third = preflight._preparation_inputs(tmp_path, raw)
    assert second != third
    sql.unlink()
    assert 'flutter/supabase/migrations/20261006.sql' not in preflight._preparation_inputs(tmp_path, raw)['files']


def test_preparation_hashes_source_audit_docs_and_app_vocab_but_not_operational_ledger(tmp_path, monkeypatch):
    raw = tmp_path / 'raw'
    raw.mkdir()
    (raw / '1.json').write_text(json.dumps({'id': 1, 'ingredientRows': []}))
    audits = tmp_path / 'scripts/audits'
    audits.mkdir(parents=True)
    document = audits / 'SOURCE_RECONCILIATION.md'
    document.write_text('one')
    ledger = audits / 'LEDGER.md'
    ledger.write_text('one')
    flutter = tmp_path / 'app'
    (flutter / 'assets/data').mkdir(parents=True)
    vocab = flutter / 'assets/data/vocab.json'
    vocab.write_text('{}')
    monkeypatch.setenv('FLUTTER_REPO', str(flutter))
    first = preflight._preparation_inputs(tmp_path, raw)
    ledger.write_text('two')
    assert preflight._preparation_inputs(tmp_path, raw) == first
    document.write_text('two')
    assert preflight._preparation_inputs(tmp_path, raw) != first
    second = preflight._preparation_inputs(tmp_path, raw)
    vocab.write_text('{"changed":true}')
    assert preflight._preparation_inputs(tmp_path, raw) != second


def test_preparation_malformed_receipts_never_crash_or_grant_reuse(tmp_path):
    import subprocess
    raw = tmp_path / 'raw'
    raw.mkdir()
    (raw / '1.json').write_text(json.dumps({'id': 1, 'ingredientRows': []}))
    receipt = tmp_path / 'receipt.json'
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, 'completed', '')
    for value in [[], None, {'checks': None}, {'checks': [None, []]}, {'checks': {}}, {'checks': [{'name': []}]}]:
        receipt.write_text(json.dumps(value))
        result = preflight.run_preparation(tmp_path, raw,
            checks=[{'name': 'probe', 'command': ['fake']}], runner=run, report_path=receipt)
        assert result['ready']
    assert len(calls) == 6


def test_preparation_invalid_nested_evidence_is_rejected():
    valid = {'completed': True, 'exit_code': 0, 'selection': {'args': ['scripts/tests']},
             'nodes': [{'nodeid': 'one', 'phase': 'source', 'reason': 'source owner'}],
             'outcomes': {'one': [{'when': phase, 'outcome': 'passed'} for phase in ['setup', 'call', 'teardown']]}}
    for field, value in [('nodes', [None]), ('nodes', [{'nodeid': [], 'phase': 'source'}]),
                         ('outcomes', []), ('outcomes', {'one': [None]}),
                         ('outcomes', {'one': [{'when': None, 'outcome': 'passed'}]})]:
        assert not preflight._valid_test_evidence(dict(valid, **{field: value}))


def test_preparation_runtime_binds_same_path_node_binary_content(tmp_path, monkeypatch):
    import shutil
    node = tmp_path / 'node'
    node.write_bytes(b'first executable')
    real_which = shutil.which
    monkeypatch.setattr(shutil, 'which', lambda name: str(node) if name == 'node' else real_which(name))
    first = preflight._preparation_runtime()
    node.write_bytes(b'replaced executable at same path')
    second = preflight._preparation_runtime()
    assert first['executables']['node']['path'] == second['executables']['node']['path']
    assert first['executables']['node']['sha256'] != second['executables']['node']['sha256']
