import os
from pathlib import Path
import subprocess
import sys

import pytest

import ci_change_scope as scope


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, 'init', '-q')
    git(tmp_path, 'config', 'user.email', 'test@example.invalid')
    git(tmp_path, 'config', 'user.name', 'Test')
    (tmp_path / 'README.md').write_text('Initial\n')
    git(tmp_path, 'add', '.')
    git(tmp_path, 'commit', '-qm', 'initial')
    return tmp_path


def commit(repo, path, text='Changed\n'):
    destination = repo / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text)
    git(repo, 'add', '.')
    git(repo, 'commit', '-qm', 'change')
    return git(repo, 'rev-parse', 'HEAD')


@pytest.mark.parametrize('path', ['README.md', 'AGENTS.md', 'CLAUDE.md', 'docs/a.md',
    'knowledge/a.md', '.claude/skills/check/SKILL.md', '.claude/state/CURRENT_HANDOFF.md',
    'scripts/audits/example/report.md'])
def test_documentation_allowlist(repo, path):
    base = git(repo, 'rev-parse', 'HEAD')
    head = commit(repo, path)
    assert scope.classify(repo, base, head) == 'docs'
    (repo / 'uncommitted.py').write_text('broken')
    assert scope.classify(repo, base, head) == 'docs'


@pytest.mark.parametrize('path', ['.github/workflows/check.yml', 'scripts/data/x.json',
    'scripts/tests/test_x.py', 'ruff.toml', 'docs/script.py', 'scripts/data/policy.md',
    '.claude/state/other.md', 'arbitrary.md'])
def test_other_changes_need_full(repo, path):
    base = git(repo, 'rev-parse', 'HEAD')
    head = commit(repo, path)
    assert scope.classify(repo, base, head) == 'full'


def test_mixed_and_renamed_code_still_need_full(repo):
    base = git(repo, 'rev-parse', 'HEAD')
    commit(repo, 'docs/change.md')
    head = commit(repo, 'source.py')
    assert scope.classify(repo, base, head) == 'full'
    (repo / 'source.py').rename(repo / 'docs/source.md')
    git(repo, 'add', '-A')
    git(repo, 'commit', '-qm', 'rename')
    assert scope.classify(repo, head, git(repo, 'rev-parse', 'HEAD')) == 'full'


@pytest.mark.parametrize('mode', ['executable', 'symlink'])
def test_nonregular_documentation_needs_full(repo, mode):
    base = git(repo, 'rev-parse', 'HEAD')
    path = repo / 'README.md'
    if mode == 'executable':
        path.chmod(0o755)
    else:
        path.unlink()
        path.symlink_to('elsewhere')
    git(repo, 'add', '.')
    git(repo, 'commit', '-qm', mode)
    assert scope.classify(repo, base, git(repo, 'rev-parse', 'HEAD')) == 'full'


def test_invalid_empty_and_unbound_refs_need_full(repo):
    head = git(repo, 'rev-parse', 'HEAD')
    for base in ['', '0' * 40, 'f' * 40, 'HEAD', head]:
        assert scope.classify(repo, base, head) == 'full'


def test_cli_rejects_documentation_whitespace(repo):
    base = git(repo, 'rev-parse', 'HEAD')
    head = commit(repo, 'README.md', 'Trailing  \n')
    result = subprocess.run([sys.executable, str(Path(scope.__file__)), '--repo', str(repo),
        '--base', base, '--head', head], capture_output=True, text=True)
    assert result.returncode != 0
    assert result.stdout.strip() == 'docs'
    assert 'whitespace' in result.stderr.lower()


def test_required_merge_job_rejects_failure_cancellation_and_missing_scope():
    import os
    import yaml
    workflow = yaml.safe_load((Path(__file__).resolve().parents[2] / '.github/workflows/pipeline-tests.yml').read_text())
    job = workflow['jobs']['merge-ready']
    assert job['if'] == 'always()'
    assert set(job['needs']) == {'scope', 'fast'}
    script = job['steps'][0]['run']
    for scope, kind, fast, expected in [
        ('success', 'docs', 'skipped', 0),
        ('success', 'full', 'success', 0),
        ('success', 'full', 'failure', 1),
        ('success', 'full', 'skipped', 1),
        ('success', 'full', 'cancelled', 1),
        ('failure', 'docs', 'skipped', 1),
        ('success', '', 'success', 1),
    ]:
        result = subprocess.run(['bash', '-e', '-c', script], env={**os.environ,
            'SCOPE_RESULT': scope, 'KIND': kind, 'FAST_RESULT': fast})
        assert (result.returncode != 0) == bool(expected)


def test_candidate_checks_have_one_required_pr_event():
    import yaml
    workflow = yaml.load((Path(__file__).resolve().parents[2] / '.github/workflows/pipeline-tests.yml').read_text(), Loader=yaml.BaseLoader)
    assert workflow['on']['push']['branches'] == ['main']
    assert workflow['on']['pull_request']['branches'] == ['main']
    assert 'workflow_dispatch' in workflow['on']
