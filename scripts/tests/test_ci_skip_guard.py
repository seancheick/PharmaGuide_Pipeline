"""scripts/ci_skip_guard.py: a CI skip outside the local-only files fails."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ci_skip_guard import undeclared_skips  # noqa: E402
from test_profiles import LOCAL_ONLY_TEST_FILES  # noqa: E402

_JUNIT = """<?xml version="1.0"?>
<testsuites><testsuite>
  <testcase classname="scripts.tests.{local}" name="test_corpus"><skipped message="local enriched corpus not available"/></testcase>
  <testcase classname="scripts.tests.test_ran.TestThing" name="test_ok"/>
  {extra}
</testsuite></testsuites>
"""


def _write(tmp_path, extra=""):
    local = sorted(LOCAL_ONLY_TEST_FILES)[0].removesuffix(".py")
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


def test_ci_shards_cover_the_fast_profile_exactly_once():
    import subprocess

    profiles = Path(__file__).resolve().parents[1] / "test_profiles.py"

    def files(*extra):
        out = subprocess.run(
            [sys.executable, str(profiles), "fast", *extra],
            check=True, capture_output=True, text=True,
        ).stdout.split()
        return out

    shards = [files("--shard", f"{i}/4") for i in range(1, 5)]
    assert sorted(sum(shards, [])) == sorted(files())
