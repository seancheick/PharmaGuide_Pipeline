"""Exercise the pinned checker against real Ruff output in a disposable Git repo."""
import json
import subprocess
from pathlib import Path

import pytest

import check_python_correctness as checker


@pytest.fixture
def repo(tmp_path):
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    (tmp_path / 'ruff.toml').write_text((checker.ROOT / 'ruff.toml').read_text())
    return tmp_path


def scan(repo, source):
    (repo / 'sample.py').write_text(source)
    subprocess.run(['git', '-C', str(repo), 'add', 'sample.py'], check=True)
    return checker.collect(repo)


def test_existing_violation_may_move_but_new_or_duplicate_cannot_hide(repo):
    old = scan(repo, 'def broken():\n    return missing\n')
    assert len(old) == 1
    moved = scan(repo, '# legitimate header\n\ndef broken():\n    return missing\n')
    assert not checker.new_findings(moved, old)
    changed = scan(repo, 'def broken():\n    return another_missing\n')
    assert checker.new_findings(changed, old)
    duplicate = scan(repo, 'def broken():\n    return missing\ndef another():\n    return missing\n')
    assert len(checker.new_findings(duplicate, old)) == 1
    assert not checker.new_findings(scan(repo, 'def fixed():\n    return 1\n'), old)


@pytest.mark.parametrize('source', [
    'print(unknown)  # noqa: F821\n',
    'def broken():\n    print(x)\n    x = 1\n',
    'assert (False, "message")\n',
    'if (False, False):\n    pass\n',
    'def broken(:\n',
])
def test_representative_correctness_errors_rejected(repo, source):
    assert checker.new_findings(scan(repo, source), [])


def test_baseline_is_explicit_and_wrong_version_fails(repo):
    baseline = repo / 'baseline.json'
    baseline.write_text(json.dumps({'ruff_version': 'wrong', 'findings': []}))
    with pytest.raises(ValueError, match='version'):
        checker.read_baseline(baseline, repo)


def test_command_exits_nonzero_and_reports_new_error(repo, monkeypatch, capsys):
    scan(repo, 'print(missing)\n')
    baseline = repo / 'baseline.json'
    baseline.write_text(json.dumps({'ruff_version': '0.14.0', 'findings': []}))
    monkeypatch.setattr(checker, 'ROOT', repo)
    monkeypatch.setattr(checker, 'BASELINE', baseline)
    assert checker.main() == 1
    assert 'sample.py: F821' in capsys.readouterr().out
    scan(repo, 'print("ok")\n')
    assert checker.main() == 0


def test_syntax_error_cannot_be_grandfathered(repo):
    findings = scan(repo, 'def broken(:\n')
    baseline = repo / 'baseline.json'
    baseline.write_text(json.dumps({'ruff_version': '0.14.0', 'findings': findings}))
    with pytest.raises(ValueError, match='syntax failures cannot be baselined'):
        checker.read_baseline(baseline, repo)
