"""Verification receipts bind a real process result to its preserved log."""

from __future__ import annotations

import hashlib
import json
import sys
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from audits.run_verification_gate import run_gate  # noqa: E402


def _reusable_probe(tmp_path, *, command=None):
    script = tmp_path / 'probe.py'
    if not script.exists():
        script.write_text("from pathlib import Path\np=Path('calls')\np.write_text(p.read_text()+'x' if p.exists() else 'x')\n")
    return dict(name='source-check', command=command or [sys.executable, str(script)],
                log_path=tmp_path / 'gate.log', receipt_path=tmp_path / 'gate.json',
                cwd=tmp_path, input_globs=['probe.py', 'inputs/*.json'])


def test_read_only_success_reuses_content_not_mtime(tmp_path):
    args = _reusable_probe(tmp_path)
    assert run_gate(**args) == 0
    (tmp_path / 'probe.py').touch()
    assert run_gate(**args) == 0
    assert (tmp_path / 'calls').read_text() == 'x'


def test_changed_added_deleted_inputs_invalidate_reuse(tmp_path):
    args = _reusable_probe(tmp_path)
    inputs = tmp_path / 'inputs'
    inputs.mkdir()
    assert run_gate(**args) == 0
    path = inputs / 'one.json'
    for value in ['{}', '{"changed": true}']:
        path.write_text(value)
        assert run_gate(**args) == 0
    path.unlink()
    assert run_gate(**args) == 0
    assert (tmp_path / 'calls').read_text() == 'xxxx'


def test_environment_and_command_changes_invalidate_reuse(tmp_path, monkeypatch):
    args = _reusable_probe(tmp_path)
    assert run_gate(**args) == 0
    monkeypatch.setenv('PG_TEST_POLICY', 'changed')
    assert run_gate(**args) == 0
    args['command'] = [*args['command'], 'different-option']
    assert run_gate(**args) == 0
    assert (tmp_path / 'calls').read_text() == 'xxx'


def test_log_tampering_and_missing_log_invalidate_reuse(tmp_path):
    args = _reusable_probe(tmp_path)
    assert run_gate(**args) == 0
    args['log_path'].write_text('forged')
    assert run_gate(**args) == 0
    args['log_path'].unlink()
    assert run_gate(**args) == 0
    assert (tmp_path / 'calls').read_text() == 'xxx'


def test_failures_and_expired_receipts_never_reuse(tmp_path):
    args = _reusable_probe(tmp_path)
    args['command'] = [sys.executable, '-c', "raise SystemExit(7)"]
    assert run_gate(**args) == run_gate(**args) == 7
    args = _reusable_probe(tmp_path)
    assert run_gate(**args) == 0
    assert run_gate(**args, max_age_seconds=0) == 0
    assert (tmp_path / 'calls').read_text() == 'xx'


def test_input_drift_does_not_grant_reusable_success(tmp_path):
    args = _reusable_probe(tmp_path)
    (tmp_path / 'probe.py').write_text("from pathlib import Path\nPath('inputs').mkdir(exist_ok=True)\nPath('inputs/changed.json').write_text('changed')\n")
    assert run_gate(**args) != 0
    assert json.loads(args['receipt_path'].read_text())['exit_code'] != 0


def test_plain_gate_without_input_binding_always_executes(tmp_path):
    args = _reusable_probe(tmp_path)
    del args['input_globs']
    assert run_gate(**args) == run_gate(**args) == 0
    assert (tmp_path / 'calls').read_text() == 'xx'


def test_failed_later_gate_does_not_repeat_unchanged_completed_gate(tmp_path):
    args = _reusable_probe(tmp_path)
    assert run_gate(**args) == 0
    failed = dict(args, name='late-failure', command=[sys.executable, '-c', 'raise SystemExit(9)'],
                  receipt_path=tmp_path / 'late.json', log_path=tmp_path / 'late.log')
    assert run_gate(**failed) == 9
    assert run_gate(**args) == 0
    assert (tmp_path / 'calls').read_text() == 'x'


def test_damaged_and_incomplete_receipts_never_reuse(tmp_path):
    args = _reusable_probe(tmp_path)
    assert run_gate(**args) == 0
    for content in ['not json', '{"completed_at": null}', '[]']:
        args['receipt_path'].write_text(content)
        assert run_gate(**args) == 0
    assert (tmp_path / 'calls').read_text() == 'xxxx'


def test_snapshot_and_release_share_only_read_only_gate_results(tmp_path):
    import shutil
    scripts = tmp_path / 'scripts'
    (scripts / 'audits').mkdir(parents=True)
    shutil.copy(SCRIPTS / 'audits/run_verification_gate.py', scripts / 'audits')
    probe = scripts / 'probe.py'
    probe.write_text("from pathlib import Path\np=Path('calls')\np.write_text(p.read_text()+'x' if p.exists() else 'x')\n")
    corpus = scripts / 'products/output_Test_enriched/enriched'
    corpus.mkdir(parents=True)
    batch = corpus / 'batch.json'
    batch.write_text('[]')
    for filename in ['rebuild_dashboard_snapshot.sh', 'release_full.sh']:
        text = (SCRIPTS / filename).read_text()
        function = text.split('run_strict_gate() {', 1)[1].split('\n}', 1)[0]
        harness = f'''set -e
REPO_ROOT={str(tmp_path)!r}
PG_PYTHON={sys.executable!r}
info() {{ echo "$*"; }}
ok() {{ echo "$*"; }}
run_strict_gate() {{{function}
}}
run_strict_gate "clinical drift contract" "$PG_PYTHON" scripts/probe.py
'''
        result = subprocess.run(['bash', '-c', harness], cwd=tmp_path, capture_output=True,
                                text=True, env={**os.environ}, timeout=20)
        assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / 'calls').read_text() == 'x'
    batch.write_text('[{"changed":true}]')
    assert subprocess.run(['bash', '-c', harness], cwd=tmp_path, capture_output=True).returncode == 0
    assert (tmp_path / 'calls').read_text() == 'xx'
    # Same wrapper and input set, but publication/stateful labels never reuse.
    publication = harness.replace('run_strict_gate "clinical drift contract"',
                                  'run_strict_gate "interaction DB release asset + app hydration pin"')
    for _ in range(2):
        assert subprocess.run(['bash', '-c', publication], cwd=tmp_path, capture_output=True).returncode == 0
    assert (tmp_path / 'calls').read_text() == 'xxxx'


def test_actual_shared_gate_commands_match_between_snapshot_and_release():
    import re
    from audits.run_verification_gate import REUSABLE_RELEASE_GATES
    scripts = []
    for filename in ['rebuild_dashboard_snapshot.sh', 'release_full.sh']:
        text = (SCRIPTS / filename).read_text().replace('$PRODUCTS_DIR', '$REPO_ROOT/scripts/products')
        scripts.append(dict(re.findall(r'run_strict_gate "([^"]+)" \\\n\s+([^\n]+)', text)))
    for name in REUSABLE_RELEASE_GATES:
        assert scripts[0][name] == scripts[1][name], name


def test_curated_interaction_changes_invalidate_shared_release_receipts(tmp_path):
    from audits.run_verification_gate import RELEASE_SOURCE_INPUTS
    args = _reusable_probe(tmp_path)
    args['input_globs'] = RELEASE_SOURCE_INPUTS
    scripts = tmp_path / 'scripts'
    scripts.mkdir()
    (tmp_path / 'probe.py').replace(scripts / 'probe.py')
    args['command'] = [sys.executable, str(scripts / 'probe.py')]
    curated = scripts / 'data/curated_interactions'
    curated.mkdir(parents=True)
    rules = curated / 'rules.json'
    rules.write_text('{}')
    assert run_gate(**args) == 0
    rules.write_text('{"reviewed":true}')
    assert run_gate(**args) == 0
    assert (tmp_path / 'calls').read_text() == 'xx'


def test_success_receipt_binds_exit_code_command_and_log(tmp_path: Path) -> None:
    log = tmp_path / "gate.log"
    receipt = tmp_path / "gate.receipt.json"

    exit_code = run_gate(
        name="pipeline_fast_suite",
        command=[sys.executable, "-c", "print('all green')"],
        log_path=log,
        receipt_path=receipt,
        cwd=tmp_path,
    )

    assert exit_code == 0
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["gate_name"] == "pipeline_fast_suite"
    assert payload["exit_code"] == 0
    assert payload["command"] == [sys.executable, "-c", "print('all green')"]
    assert payload["log_sha256"] == hashlib.sha256(log.read_bytes()).hexdigest()
    assert "all green" in log.read_text(encoding="utf-8")


def test_failed_command_still_writes_nonzero_receipt(tmp_path: Path) -> None:
    log = tmp_path / "gate.log"
    receipt = tmp_path / "gate.receipt.json"

    exit_code = run_gate(
        name="pipeline_release_suite",
        command=[sys.executable, "-c", "print('failed'); raise SystemExit(7)"],
        log_path=log,
        receipt_path=receipt,
        cwd=tmp_path,
    )

    assert exit_code == 7
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["exit_code"] == 7
    assert payload["completed_at"]


def test_tool_call_bookkeeping_does_not_invalidate_real_configuration(tmp_path, monkeypatch):
    args = _reusable_probe(tmp_path)
    monkeypatch.setenv('CODEX_TOOL_CALL_ID', 'first-command')
    assert run_gate(**args) == 0
    monkeypatch.setenv('CODEX_TOOL_CALL_ID', 'reviewed-retry')
    assert run_gate(**args) == 0
    assert (tmp_path / 'calls').read_text() == 'x'
    monkeypatch.setenv('PG_TEST_POLICY', 'new-policy')
    assert run_gate(**args) == 0
    assert (tmp_path / 'calls').read_text() == 'xx'
