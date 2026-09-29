"""A publishing release runs only from a clean checkout at the fetched origin/main.

On 2026-09-29 a release built catalog 2026.09.29.100221 in a checkout still at
827f6b90 while four fixes had landed on origin/main. Every gate passed, because
the freshness gate compares outputs with the checkout they run in, and HEAD was
pushed (only behind). The GitHub upload timing out was all that stopped it.
"""
import re
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "release_full.sh"


def _function_source() -> str:
    source = SCRIPT.read_text(encoding="utf-8")
    match = re.search(r"^require_release_base\(\) \{\n.*?^\}\n", source, re.S | re.M)
    assert match, "release_full.sh defines require_release_base"
    return match.group(0)


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def _repos(tmp_path: Path) -> tuple[Path, Path]:
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)], check=True, capture_output=True)
    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True, capture_output=True)
    _git(work, "config", "user.email", "t@example.com")
    _git(work, "config", "user.name", "t")
    (work / "a.txt").write_text("1")
    _git(work, "add", "a.txt")
    _git(work, "commit", "-qm", "one")
    _git(work, "push", "-q", "origin", "HEAD:main")
    return origin, work


def _check(work: Path) -> subprocess.CompletedProcess:
    script = "err() { echo \"$*\" >&2; }\n" + _function_source() + f'require_release_base "{work}"\n'
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True)


def test_a_clean_checkout_at_origin_main_passes(tmp_path):
    _, work = _repos(tmp_path)
    assert _check(work).returncode == 0


def test_a_checkout_behind_origin_main_is_refused(tmp_path):
    origin, work = _repos(tmp_path)
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(origin), str(other)], check=True, capture_output=True)
    _git(other, "config", "user.email", "t@example.com")
    _git(other, "config", "user.name", "t")
    (other / "a.txt").write_text("2")
    _git(other, "commit", "-qam", "two")
    _git(other, "push", "-q", "origin", "HEAD:main")
    result = _check(work)
    assert result.returncode != 0
    assert "origin/main" in result.stderr


def test_uncommitted_tracked_changes_are_refused(tmp_path):
    _, work = _repos(tmp_path)
    (work / "a.txt").write_text("dirty")
    result = _check(work)
    assert result.returncode != 0
    assert "uncommitted" in result.stderr


def test_the_base_check_runs_before_any_release_step():
    source = SCRIPT.read_text(encoding="utf-8")
    call = source.index('require_release_base "$REPO_ROOT"')
    assert call < source.index("run_strict_gate ")
    assert call < source.index("# Step 5: Sync to Supabase")
    guard = source[source.rindex("\nif ", 0, call):call]
    assert "SKIP_FLUTTER == 0" in guard and "SKIP_SUPABASE == 0" in guard
