"""scripts/ci_skip_guard.py: a CI skip outside the local-only files fails."""

from __future__ import annotations

import sys
from pathlib import Path

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
