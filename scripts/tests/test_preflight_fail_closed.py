"""Preflight must fail closed for required or corrupt inputs (G2)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import preflight


def test_schema_respects_condition_synonyms_and_rejects_deprecated_ingredient_fields(tmp_path, monkeypatch):
    for filename, primary in [('clinical_risk_taxonomy.json', 'conditions'), ('ingredient_quality_map.json', 'ingredients')]:
        metadata = json.loads((preflight.DATA_DIR / filename).read_text())['_metadata']
        (tmp_path / filename).write_text(json.dumps({'_metadata': metadata, primary: [{'id': 'one', 'synonyms': ['alias']}]}))
    monkeypatch.setattr(preflight, 'REFERENCE_DATABASES', ['clinical_risk_taxonomy.json', 'ingredient_quality_map.json'])
    result = preflight.validate_database_schema(tmp_path)
    assert 'clinical_risk_taxonomy.json' in result['passed']
    assert [entry['file'] for entry in result['failed']] == ['ingredient_quality_map.json']
    taxonomy = json.loads((tmp_path / 'clinical_risk_taxonomy.json').read_text())
    taxonomy['synonyms'] = ['deprecated root']
    (tmp_path / 'clinical_risk_taxonomy.json').write_text(json.dumps(taxonomy))
    assert any("Deprecated root field 'synonyms'" in issue for entry in preflight.validate_database_schema(tmp_path)['failed'] for issue in entry['issues'])


def test_preparation_receipt_binds_existing_unii_source_cache_content_and_absence(tmp_path, monkeypatch):
    import subprocess
    monkeypatch.setenv('FLUTTER_REPO', str(tmp_path / 'absent_app'))
    raw = tmp_path / 'raw'
    raw.mkdir()
    (raw / '1.json').write_text(json.dumps({'id': 1, 'ingredientRows': []}))
    cache = tmp_path / 'scripts/data/fda_unii_cache.json'
    cache.parent.mkdir(parents=True)
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, 'ok', '')
    receipt = tmp_path / 'receipt.json'
    def prepare():
        return preflight.run_preparation(tmp_path, raw, checks=[{'name': 'probe', 'command': ['fake']}], runner=run, report_path=receipt)
    absent = prepare()
    assert absent['inputs']['files']['repo/scripts/data/fda_unii_cache.json'] == 'MISSING'
    cache.write_text('{"caffeine":"3G6A5W338E"}')
    assert prepare()['ready']
    assert prepare()['ready']
    assert len(calls) == 2
    cache.write_text('{"caffeine":"WRONG"}')
    assert prepare()['ready']
    assert len(calls) == 3
    cache.unlink()
    assert prepare()['ready']
    assert len(calls) == 4


def test_preparation_runtime_ignores_descriptor_numbers_but_binds_worker_budget(monkeypatch):
    monkeypatch.setenv('PG_TEST_LOCK_FDS', '3')
    before = preflight._preparation_runtime()
    monkeypatch.setenv('PG_TEST_LOCK_FDS', '9,10')
    assert preflight._preparation_runtime() == before
    monkeypatch.setenv('PG_TEST_WORKERS', 'different-budget')
    assert preflight._preparation_runtime() != before



def test_preparation_runtime_ignores_only_named_shell_launch_bookkeeping(monkeypatch):
    monkeypatch.setenv('SHELL_PID', '100')
    before = preflight._preparation_runtime()
    monkeypatch.setenv('SHELL_PID', '200')
    assert preflight._preparation_runtime() == before
    monkeypatch.delenv('SHELL_PID')
    assert preflight._preparation_runtime() == before
    for key in ['PG_TEST_WORKERS', 'PG_RUN_OCR_FIDELITY_TESTS', 'FLUTTER_REPO',
                'SUPABASE_SERVICE_ROLE_KEY', 'OTHER_PID']:
        with monkeypatch.context() as context:
            context.setenv(key, 'meaningful-runtime-change')
            changed = preflight._preparation_runtime()
            assert changed != before, key
            assert changed['environment'][key] == preflight._digest('meaningful-runtime-change')


def test_preparation_runtime_matches_across_real_shell_launches():
    import os
    import subprocess
    code = "import sys; sys.path.insert(0, 'scripts'); import preflight; print(preflight._digest(preflight._preparation_runtime()))"
    command = ['bash', '-c', 'source scripts/python_env.sh; "$PG_PYTHON" -c "$1"', '_', code]
    def launch(pid, **settings):
        environment = dict(os.environ, SHELL_PID=pid, **settings)
        return subprocess.run(command, cwd=Path(__file__).resolve().parents[2],
                              env=environment, capture_output=True, text=True,
                              encoding='utf-8', check=True, timeout=30).stdout.strip()
    before = launch('100')
    assert launch('200') == before
    assert launch('300', PG_TEST_WORKERS='changed-budget') != before

def test_preparation_cli_reacquires_lock_when_only_held_environment_is_present(tmp_path, monkeypatch):
    import subprocess
    import pytest
    monkeypatch.setenv('PG_TEST_LOCK_HELD', '1')
    monkeypatch.setenv('PG_TEST_LOCK_FDS', '999999')
    monkeypatch.setenv('PG_TEST_LOCK_DIR', str(tmp_path))
    monkeypatch.setattr(sys, 'argv', ['preflight.py', '--prepare', '--raw-root', str(tmp_path)])
    monkeypatch.setattr(preflight, 'run_preparation', lambda *args, **kwargs: pytest.fail('Stale held flag bypassed acquisition'))
    calls = []
    monkeypatch.setattr(subprocess, 'call', lambda command, **kwargs: calls.append(command) or 0)
    with pytest.raises(SystemExit) as exit_result:
        preflight.main()
    assert exit_result.value.code == 0
    assert calls and Path(calls[0][1]).name == 'test_lock.py'
    assert calls[0][2:4] == ['exclusive', '--']


def test_preparation_utf8_inputs_manifest_and_receipt_under_ascii_locale(tmp_path):
    import os
    import subprocess
    script = r'''
import sys,json
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import preflight,subprocess
root=Path(sys.argv[2]); raw=root/'raw'; raw.mkdir()
(raw/'1.json').write_bytes(json.dumps({'id':1,'ingredientRows':[],'name':'Caf\u00e9'},ensure_ascii=False).encode('utf-8'))
manifest=root/'scripts/tests/fixtures/contract_snapshots/_manifest.json'
manifest.parent.mkdir(parents=True)
manifest.write_bytes(json.dumps({'products':[{'dsld_id':1,'name':'Caf\u00e9'}]},ensure_ascii=False).encode('utf-8'))
calls=[]
def run(command,**kwargs):
    calls.append(command)
    return subprocess.CompletedProcess(command,0,'Caf\u00e9','')
report=root/'receipt.json'
checks=[{'name':'probe','command':['fake']}]
first=preflight.run_preparation(root,raw,checks=checks,runner=run,report_path=report)
assert first['ready'],ascii(first['inputs']['errors'])
assert preflight._preparation_canary_identifiers(root)==['1']
report.write_bytes(json.dumps(first,ensure_ascii=False).encode('utf-8'))
second=preflight.run_preparation(root,raw,checks=checks,runner=run,report_path=report)
assert second['ready'] and calls==[['fake']]
protocol=preflight.run_preparation(root,raw,checks=[{'name':'protocol','command':[sys.executable,'-c',"import sys;sys.stdout.buffer.write(b'Caf\\xc3\\xa9')"]}])
assert protocol['ready'],ascii(protocol['checks'])
assert protocol['checks'][1]['stdout']=='Caf\u00e9'
print('UTF8 preparation passed')
'''
    # The script itself stays ASCII, but authored fixtures contain UTF-8 bytes.
    environment = dict(os.environ, PYTHONUTF8='0', PYTHONCOERCECLOCALE='0', LC_ALL='C',
                       FLUTTER_REPO=str(tmp_path / 'no_app'))
    process = subprocess.run([sys.executable, '-c', script, str(Path(preflight.__file__).parent), str(tmp_path)],
                             env=environment, capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert process.returncode == 0, process.stdout + process.stderr


def test_preparation_date_rollover_is_not_input_mutation(tmp_path, monkeypatch):
    import subprocess
    monkeypatch.setattr(preflight, '_preparation_inputs', lambda *args, **kwargs: {'files': {}, 'errors': [], 'raw_count': 1})
    runtime = iter([{'environment': {'same': 'hash'}, 'freshness_date': '2026-10-06'},
                    {'environment': {'same': 'hash'}, 'freshness_date': '2026-10-07'}])
    monkeypatch.setattr(preflight, '_preparation_runtime', lambda: next(runtime))
    result = preflight.run_preparation(tmp_path, tmp_path, checks=[{'name': 'source', 'command': ['fake']}],
        runner=lambda command, **kwargs: subprocess.CompletedProcess(command, 0, 'ok', ''))
    assert result['ready']
    assert result['runtime']['freshness_date'] == '2026-10-06', 'Do not restamp completed source receipts'


def test_preparation_rollover_still_blocks_real_environment_or_source_mutation(tmp_path, monkeypatch):
    import subprocess
    for changed in ['environment', 'files']:
        inputs = iter([{'files': {'source': 'before'}, 'errors': [], 'raw_count': 1},
                       {'files': {'source': 'after' if changed == 'files' else 'before'}, 'errors': [], 'raw_count': 1}])
        runtime = iter([{'environment': {'value': 'before'}, 'freshness_date': '2026-10-06'},
                        {'environment': {'value': 'after' if changed == 'environment' else 'before'}, 'freshness_date': '2026-10-07'}])
        monkeypatch.setattr(preflight, '_preparation_inputs', lambda *args, **kwargs: next(inputs))
        monkeypatch.setattr(preflight, '_preparation_runtime', lambda: next(runtime))
        result = preflight.run_preparation(tmp_path, tmp_path, checks=[{'name': 'source', 'command': ['fake']}],
            runner=lambda command, **kwargs: subprocess.CompletedProcess(command, 0, 'ok', ''))
        assert not result['ready'] and result['checks'][-1]['status'] == 'failed'


def test_preparation_next_day_invalidates_receipt_reuse(tmp_path, monkeypatch):
    import subprocess
    monkeypatch.setattr(preflight, '_preparation_inputs', lambda *args, **kwargs: {'files': {}, 'errors': [], 'raw_count': 1})
    runtime = {'environment': {'same': 'hash'}, 'freshness_date': '2026-10-06'}
    monkeypatch.setattr(preflight, '_preparation_runtime', lambda: dict(runtime))
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, 'ok', '')
    def prepare():
        return preflight.run_preparation(tmp_path, tmp_path, checks=[{'name': 'source', 'command': ['fake']}],
                                       runner=run, report_path=tmp_path / 'receipt.json')
    assert prepare()['ready'] and prepare()['ready']
    assert len(calls) == 1
    runtime['freshness_date'] = '2026-10-07'
    assert prepare()['ready'] and len(calls) == 2


def test_preparation_default_checks_revalidate_calendar_owner_at_final_acceptance(tmp_path, monkeypatch):
    import subprocess
    monkeypatch.setattr(preflight, '_preparation_inputs', lambda *args, **kwargs: {'files': {}, 'errors': [], 'raw_count': 1})
    monkeypatch.setattr(preflight, '_preparation_runtime', lambda: {'freshness_date': '2026-10-06', 'environment': {}})
    monkeypatch.setattr(preflight, '_preparation_canary_identifiers', lambda *args: ['1'])
    for initial, final in [(0, 1), (1, 0), (0, 0)]:
        calendar_calls = []
        def run(command, **kwargs):
            if command[-1] == 'preparation-gates':
                output = '\n'.join(json.dumps(gate) for gate in [
                    {'phase': 'artifact', 'command': ['deferred']},
                    {'phase': 'live', 'command': ['live-owner']}])
            elif command == ['live-owner']:
                assert kwargs.get('timeout') == 900
                output = 'live complete'
            elif 'fda_manufacturer_violations_sync.py' in ' '.join(command):
                calendar_calls.append(command)
                return subprocess.CompletedProcess(command, initial if len(calendar_calls) == 1 else final, 'calendar result', '')
            elif command[-1] == '--json':
                output = json.dumps({'summary': {'all_ok': True, 'exit_code': 0},
                    **{key: {'failed': []} for key in ['critical', 'configs', 'scripts', 'json_valid']}})
            elif 'freeze_contract_snapshots.py' in ' '.join(command):
                output = '[1] UNCHANGED\nChecked: 1  Failed: 0  Total: 1\n'
            else:
                evidence = {'completed': True, 'exit_code': 0, 'collection_errors': [], 'collection_skips': [],
                    'selection': {'args': ['scripts/tests']},
                    'nodes': [{'nodeid': 'owner::test_source', 'phase': 'source', 'reason': 'source owner'}],
                    'outcomes': {'owner::test_source': [{'when': stage, 'outcome': 'passed'} for stage in ['setup', 'call', 'teardown']]}}
                Path(kwargs['env']['PG_PREPARATION_REPORT']).write_text(json.dumps(evidence), encoding='utf-8')
                output = 'pytest complete'
            return subprocess.CompletedProcess(command, 0, output, '')
        report = tmp_path / 'calendar_receipt.json'
        report.unlink(missing_ok=True)
        result = preflight.run_preparation(tmp_path, tmp_path, runner=run, report_path=report)
        checks = {check['name']: check for check in result['checks']}
        assert len(calendar_calls) == 2
        assert checks['fda_freshness']['status'] == ('failed' if initial else 'passed')
        assert checks['fda_freshness_final']['status'] == ('failed' if final else 'passed')
        assert result['ready'] is (initial == final == 0)
        if initial == final == 0:
            repeated = preflight.run_preparation(tmp_path, tmp_path, runner=run, report_path=report)
            assert repeated['ready'] and len(calendar_calls) == 3
            repeated_checks = {check['name']: check for check in repeated['checks']}
            assert repeated_checks['fda_freshness']['reused'] is True
            assert not repeated_checks['fda_freshness_final'].get('reused', False)


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
    assert first['files']['repo/.env'] != 'KEY=secret'
    consumer.write_text('two')
    assert preflight._preparation_inputs(tmp_path, raw) != first
    workflow.unlink()
    assert 'repo/.github/workflows/tests.yml' not in preflight._preparation_inputs(tmp_path, raw)['files']


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


def test_preparation_git_inventory_covers_report_code_root_fixtures_manual_labels_and_docs(tmp_path, monkeypatch):
    import subprocess
    raw = tmp_path / 'raw'
    raw.mkdir()
    (raw / '1.json').write_text(json.dumps({'id': 1, 'ingredientRows': []}))
    monkeypatch.setenv('FLUTTER_REPO', str(tmp_path / 'absent_app'))
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    paths = ['scripts/reports/source.py', 'reports/storage_cleanup/fixture.json',
             'manual_labels/product_submissions/approved.json', 'docs/UNII_BACKFILL_DEFERRED.md']
    for name in paths:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('one')
    subprocess.run(['git', '-C', str(tmp_path), 'add', *paths], check=True)
    first = preflight._preparation_inputs(tmp_path, raw)
    for name in paths:
        path = tmp_path / name
        path.write_text('two')
        second = preflight._preparation_inputs(tmp_path, raw)
        assert first != second, name
        path.write_text('one')
    missing = tmp_path / paths[0]
    missing.unlink()
    result = preflight._preparation_inputs(tmp_path, raw)
    assert result['files']['repo/' + paths[0]] == 'MISSING'
    assert not result['errors']
    new_source = tmp_path / 'scripts/new_owner.unknown_extension'
    new_source.write_text('new source type')
    assert 'repo/scripts/new_owner.unknown_extension' in preflight._preparation_inputs(tmp_path, raw)['files']


def test_preparation_custom_untracked_git_report_is_operational_not_source_mutation(tmp_path, monkeypatch):
    import subprocess
    raw = tmp_path / 'raw'
    raw.mkdir()
    (raw / '1.json').write_text(json.dumps({'id': 1, 'ingredientRows': []}))
    monkeypatch.setenv('FLUTTER_REPO', str(tmp_path / 'missing_app'))
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, 'completed', '')
    for _ in range(2):
        assert preflight.run_preparation(tmp_path, raw,
            checks=[{'name': 'probe', 'command': ['fake']}], runner=run,
            report_path=tmp_path / 'readiness.json')['ready']
    assert len(calls) == 1



def test_preparation_live_deadline_kills_direct_child_preserves_successors_and_never_reuses_failure(tmp_path):
    import os
    import subprocess
    import pytest
    repo = tmp_path / 'repo'
    (repo / 'scripts').mkdir(parents=True)
    source = repo / 'scripts/source.py'
    source.write_text("print('source passed')", encoding='utf-8')
    raw = tmp_path / 'raw'
    raw.mkdir()
    (raw / '1.json').write_text(json.dumps({'id': 1, 'ingredientRows': []}), encoding='utf-8')
    pidfile = tmp_path / 'live.pid'
    code = "import os,sys,time; from pathlib import Path; Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(0.6)"
    checks = [
        {'name': 'source', 'command': [sys.executable, str(source)]},
        {'name': 'live', 'phase': 'live', 'timeout_seconds': 0.2,
         'command': [sys.executable, '-c', code, str(pidfile)]},
        {'name': 'successor', 'command': [sys.executable, '-c', "print('successor passed')"]},
    ]
    receipt = tmp_path / 'receipt.json'
    def prepare():
        return preflight.run_preparation(repo, raw, checks=checks, report_path=receipt)
    first = prepare()
    states = {check['name']: check for check in first['checks']}
    assert states['live']['status'] == 'failed'
    assert 'timed out' in states['live']['stderr']
    assert not states['live']['completed']
    assert first['completed'] and not first['ready'] and not first['publication_ready']
    assert states['successor']['status'] == states['inputs_stable']['status'] == 'passed'
    with pytest.raises(ProcessLookupError):
        os.kill(int(pidfile.read_text()), 0)
    second = prepare()
    repeated = {check['name']: check for check in second['checks']}
    assert repeated['source']['reused'] and repeated['successor']['reused']
    assert repeated['live']['status'] == 'failed' and not repeated['live'].get('reused', False)
    assert second['completed'] and not second['ready'] and repeated['inputs_stable']['status'] == 'passed'

    source.write_text("print('changed source passed')", encoding='utf-8')
    changed = prepare()
    changed_states = {check['name']: check for check in changed['checks']}
    assert changed['fingerprint'] != second['fingerprint']
    assert not changed_states['source'].get('reused', False)
    assert changed_states['source']['stdout'].strip() == 'changed source passed'
    assert not changed['ready'] and changed_states['inputs_stable']['status'] == 'passed'


def test_preparation_live_deadline_default_is_phase_owned_and_success_always_rechecks(tmp_path, monkeypatch):
    import subprocess
    monkeypatch.setattr(preflight, '_preparation_inputs', lambda *args, **kwargs: {'files': {}, 'errors': [], 'raw_count': 1})
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs.get('timeout')))
        return subprocess.CompletedProcess(command, 0, 'passed', '')
    checks = [
        {'name': 'live', 'phase': 'live', 'command': ['live-owner']},
        {'name': 'source', 'phase': 'source', 'timeout_seconds': 0.01, 'command': ['source-owner']},
    ]
    receipt = tmp_path / 'receipt.json'
    assert preflight.run_preparation(tmp_path, tmp_path, checks=checks, runner=run, report_path=receipt)['ready']
    assert calls == [(['live-owner'], 900), (['source-owner'], None)]
    calls.clear()
    repeated = preflight.run_preparation(tmp_path, tmp_path, checks=checks, runner=run, report_path=receipt)
    assert repeated['ready'] and calls == [(['live-owner'], 900)]
    assert next(check for check in repeated['checks'] if check['name'] == 'source')['reused']


def test_preparation_reuses_sealed_success_after_interrupt(tmp_path):
    import subprocess
    import pytest
    raw = tmp_path / 'raw'
    raw.mkdir()
    (raw / '1.json').write_text(json.dumps({'id': 1, 'ingredientRows': []}))
    receipt = tmp_path / 'receipt.json'
    calls = []
    def run(command, **kwargs):
        calls.append(command[-1])
        if command[-1] == 'interrupt':
            raise KeyboardInterrupt()
        return subprocess.CompletedProcess(command, 0, 'OK', '')
    checks = [{'name': name, 'command': ['fake', name]} for name in ('good', 'interrupt')]
    for _ in range(2):
        with pytest.raises(KeyboardInterrupt):
            preflight.run_preparation(tmp_path, raw, checks=checks, runner=run, report_path=receipt)
    assert calls == ['good', 'interrupt', 'interrupt']
    saved = json.loads(receipt.read_text())
    assert not saved['ready'] and not saved['completed']
    assert saved['checks'][-1]['status'] == 'failed'


def test_preparation_announces_check_before_runner_and_failure(tmp_path, capsys):
    import subprocess
    raw = tmp_path / 'raw'
    raw.mkdir()
    (raw / '1.json').write_text(json.dumps({'id': 1, 'ingredientRows': []}))
    def run(command, **kwargs):
        assert 'START: broken' in capsys.readouterr().err
        return subprocess.CompletedProcess(command, 1, '', 'broken test')
    result = preflight.run_preparation(tmp_path, raw,
        checks=[{'name': 'broken', 'command': ['fake']}], runner=run)
    assert not result['ready']
    assert 'FAILED: broken' in capsys.readouterr().err


def test_parallel_preparation_requires_identical_inventory_and_disjoint_complete_outcomes():
    import copy
    nodes = [{'nodeid': f'scripts/tests/test_sample.py::test_{i}', 'phase': 'source', 'reason': 'source'} for i in range(2)]
    stages = [{'when': stage, 'outcome': 'passed'} for stage in ('setup', 'call', 'teardown')]
    workers = [dict(completed=True, nodes=copy.deepcopy(nodes), selection={'args': ['scripts/tests']},
                    outcomes={nodes[i]['nodeid']: stages}) for i in range(2)]
    def valid(payloads):
        evidence = preflight._combine_preparation_workers(payloads)
        evidence.update(completed=True, exit_code=0)
        return preflight._valid_test_evidence(evidence)
    assert valid(workers)
    assert not valid(workers[:1])  # missing execution
    assert not valid(workers + workers[:1])  # duplicate execution
    changed = copy.deepcopy(workers)
    changed[1]['nodes'][0]['reason'] = 'different policy'
    assert not valid(changed)
    changed = copy.deepcopy(workers)
    changed[1]['completed'] = False
    assert not valid(changed)
    changed = copy.deepcopy(workers)
    changed[1]['outcomes'][nodes[1]['nodeid']][1]['outcome'] = 'failed'
    assert not valid(changed)
    assert not valid([])


def test_preparation_real_process_reports_elapsed_and_current_test(tmp_path, capsys):
    import sys
    evidence = tmp_path / 'progress.json'
    evidence.write_text(json.dumps({'current_test': 'sample::test_one', 'finished_tests': 1, 'selected_tests': 2,
                                   'failures': ['sample::test_broken']}))
    result = preflight._preparation_process([sys.executable, '-c', 'import time; time.sleep(.1)'],
        cwd=tmp_path, env=dict(__import__('os').environ, PG_PREPARATION_REPORT=str(evidence)))
    output = capsys.readouterr().err
    assert result.returncode == 0
    assert 'elapsed' in output and '1/2 tests' in output and 'sample::test_one' in output
    assert 'FAILED: sample::test_broken' in output


def test_default_preparation_collects_executes_once_and_reuses_full_coverage(tmp_path, monkeypatch):
    import subprocess
    monkeypatch.setattr(preflight, '_preparation_inputs', lambda *args, **kwargs: {'files': {}, 'errors': [], 'raw_count': 1})
    monkeypatch.setattr(preflight, '_preparation_runtime', lambda: {'version': 'same'})
    monkeypatch.setattr(preflight, '_preparation_canary_identifiers', lambda root: ['1'])
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        stdout = 'OK'
        if command[-1] == 'preparation-gates':
            stdout = json.dumps({'phase': 'source', 'command': ['fake-gate']})
        elif '--json' in command:
            stdout = json.dumps(dict(summary={'all_ok': True, 'exit_code': 0},
                                     **{key: {'failed': []} for key in ('critical', 'configs', 'scripts', 'json_valid')}))
        elif '--check' in command and 'scripts/tests/freeze_contract_snapshots.py' in command:
            stdout = '[1] UNCHANGED\nChecked: 1  Failed: 0  Total: 1'
        if 'preparation' in command:
            node = {'nodeid': 'scripts/tests/test_one.py::test_one', 'phase': 'source', 'reason': 'source'}
            evidence = dict(completed=True, exit_code=0, selection={'args': ['scripts/tests']}, nodes=[node],
                            outcomes={node['nodeid']: [{'when': stage, 'outcome': 'passed'} for stage in ('setup', 'call', 'teardown')]})
            Path(kwargs['env']['PG_PREPARATION_REPORT']).write_text(json.dumps(evidence))
        return subprocess.CompletedProcess(command, 0, stdout, '')
    receipt = tmp_path / 'receipt.json'
    first = preflight.run_preparation(tmp_path, tmp_path, runner=run, report_path=receipt)
    assert first['ready']
    assert not any('--collect-only' in command for command in calls)
    assert sum('preparation' in command for command in calls) == 1
    second = preflight.run_preparation(tmp_path, tmp_path, runner=run, report_path=receipt)
    assert second['ready']
    assert sum('preparation' in command for command in calls) == 1
    assert next(check for check in second['checks'] if check['name'] == 'source_tests')['reused']


def test_preparation_detected_input_drift_cannot_be_erased_by_later_restore(tmp_path):
    import subprocess
    raw = tmp_path / 'raw'
    raw.mkdir()
    label = raw / '1.json'
    original = json.dumps({'id': 1, 'ingredientRows': []})
    label.write_text(original)
    def run(command, **kwargs):
        label.write_text(json.dumps({'id': 1, 'ingredientRows': [{'name': 'changed'}]}) if command[-1] == 'mutate' else original)
        return subprocess.CompletedProcess(command, 0, 'OK', '')
    result = preflight.run_preparation(tmp_path, raw, runner=run, report_path=tmp_path / 'report.json',
        checks=[{'name': name, 'command': ['fake', name]} for name in ('mutate', 'restore')])
    assert not result['ready'] and result['checkpoint_stable'] is False
    assert result['checks'][-1]['status'] == 'failed'


def test_preparation_live_test_name_overrides_throttled_evidence(tmp_path, capsys):
    import os
    evidence = tmp_path / 'progress.json'
    evidence.write_text(json.dumps({'current_test': 'stale::test_previous', 'finished_tests': 1, 'selected_tests': 2}))
    code = 'import sys,time; print(\'PG_PREPARATION_PROGRESS:\'+\'{"current_test":"live::test_slow","finished_tests":1,"selected_tests":2}\',file=sys.stderr,flush=True); time.sleep(1.2)'
    result = preflight._preparation_process([sys.executable, '-c', code], cwd=tmp_path,
        env=dict(os.environ, PG_PREPARATION_REPORT=str(evidence)))
    assert result.returncode == 0
    assert 'live::test_slow' in capsys.readouterr().err
    assert 'PG_PREPARATION_PROGRESS:' not in result.stderr


def test_parallel_progress_keeps_long_test_visible_after_other_worker_finishes(tmp_path, monkeypatch, capsys):
    import conftest
    from types import SimpleNamespace
    with monkeypatch.context() as hook_patch:
        hook_patch.setenv('PG_PREPARATION_REPORT', str(tmp_path / 'progress.json'))
        hook_patch.setattr(conftest, '_PREPARATION_CONFIG', None)
        hook_patch.setattr(conftest, '_PREPARATION_ACTIVE', set())
        hook_patch.setattr(conftest, '_PREPARATION', {'nodes': [], 'outcomes': {}, 'selected_tests': 2})
        conftest.pytest_runtest_logstart('long::test_slow', None)
        conftest.pytest_runtest_logstart('short::test_fast', None)
        conftest.pytest_runtest_logreport(SimpleNamespace(nodeid='short::test_fast', when='teardown', outcome='passed', skipped=False, failed=False))
        frames = [json.loads(line.removeprefix('PG_PREPARATION_PROGRESS:')) for line in capsys.readouterr().err.splitlines() if line.startswith('PG_PREPARATION_PROGRESS:')]
        assert frames[-1]['current_test'] == 'long::test_slow'
        assert frames[-1]['finished_tests'] == 1


def test_preparation_checkpoint_midnight_keeps_epoch_without_false_input_drift(tmp_path, monkeypatch):
    import subprocess
    monkeypatch.setattr(preflight, '_preparation_inputs', lambda *args, **kwargs: {'files': {}, 'errors': [], 'raw_count': 1})
    runtime = iter([{'environment': {'same': 'hash'}, 'freshness_date': '2026-10-06'},
                    {'environment': {'same': 'hash'}, 'freshness_date': '2026-10-07'},
                    {'environment': {'same': 'hash'}, 'freshness_date': '2026-10-07'}])
    monkeypatch.setattr(preflight, '_preparation_runtime', lambda: next(runtime))
    result = preflight.run_preparation(tmp_path, tmp_path, checks=[{'name': 'source', 'command': ['fake']}],
        runner=lambda command, **kwargs: subprocess.CompletedProcess(command, 0, 'OK', ''), report_path=tmp_path / 'receipt.json')
    assert result['ready'] and result['checkpoint_stable']
    assert result['runtime']['freshness_date'] == '2026-10-06'
