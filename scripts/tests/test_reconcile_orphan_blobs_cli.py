"""The orphan-reconciliation maintenance CLI, and its removal from the release.

Requirements pinned here:

  * catalog-version deletion and orphan reconciliation are separate steps;
  * a successful catalog publication never waits on the orphan inventory;
  * quarantine is the only action — there is no hard-delete path here;
  * ``--execute`` is impossible without an operator-supplied ``--expected-count``
    that matches a completed dry run exactly;
  * the release reports version cleanup and orphan cleanup as SEPARATE
    statuses, and never prints an unconditional "Storage cleanup OK".
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))

REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASE_SH = REPO_ROOT / "scripts" / "release_full.sh"

from test_release_safety_protected_blobs import (  # noqa: E402
    FakeSupabaseClientForP35,
    _detail_index_bytes,
    _p35_bundled_and_dist,
    _registry_row,
)

PREFIX = "shared/details/sha256"
ACTIVE = "2026.08.26.141540"
RETAINED = "2026.08.25.090053"


@pytest.fixture(autouse=True)
def _no_real_backoff_sleeps(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _s: None)


def _h(tag: str) -> str:
    return (tag * 32)[:64]


def _world(tmp_path, *, orphans=()):
    active = [_h("aa")]
    client = FakeSupabaseClientForP35()
    bucket = client.storage.from_("pharmaguide")
    for version in (ACTIVE, RETAINED):
        bucket.put(f"v{version}/detail_index.json",
                   _detail_index_bytes(active, version))
    client.seed_registry([
        _registry_row(db_version=ACTIVE, state="ACTIVE"),
        _registry_row(db_version=RETAINED, state="RETIRED"),
    ])
    for h in list(active) + list(orphans):
        bucket.put(f"{PREFIX}/{h[:2]}/{h}.json", b"x" * 100)
    flutter_repo, dist_dir = _p35_bundled_and_dist(
        tmp_path, bundled_hashes=active, dist_hashes=active,
    )
    return client, bucket, flutter_repo, dist_dir


def _argv(flutter_repo, dist_dir, *extra, shards="aa,dd"):
    return [
        "--flutter-repo", str(flutter_repo),
        "--dist-dir", str(dist_dir),
        "--retained-version", ACTIVE,
        "--retained-version", RETAINED,
        "--shards", shards,
        *extra,
    ]


# ---------------------------------------------------------------------------
# Dry run is the default and is inert
# ---------------------------------------------------------------------------


def test_dry_run_is_the_default_and_mutates_nothing(tmp_path, capsys):
    import reconcile_orphan_blobs as cli

    client, bucket, flutter_repo, dist_dir = _world(tmp_path, orphans=[_h("dd")])
    before = dict(bucket.objects)
    attempted = []
    for op in ("remove", "move", "copy", "upload"):
        setattr(bucket, op, lambda *a, _op=op, **k: attempted.append(_op))

    exit_code = cli.main(_argv(flutter_repo, dist_dir), client=client)
    out = capsys.readouterr().out

    assert exit_code == 0
    assert attempted == []
    assert bucket.objects == before
    assert "DRY RUN" in out
    assert re.search(r"Orphan blobs:\s+1\b", out), out


def test_dry_run_writes_a_machine_readable_report(tmp_path):
    import reconcile_orphan_blobs as cli

    client, _, flutter_repo, dist_dir = _world(tmp_path, orphans=[_h("dd")])
    report_path = tmp_path / "report.json"

    cli.main(
        _argv(flutter_repo, dist_dir, "--json-report", str(report_path)),
        client=client,
    )

    data = json.loads(report_path.read_text())
    assert data["orphan_count"] == 1
    assert data["proposed_quarantine"] == 1
    assert data["orphan_bytes"] == 100
    assert data["protected_by_version"][ACTIVE] == 1
    assert data["inventory"]["complete"] is True


# ---------------------------------------------------------------------------
# Execute is gated
# ---------------------------------------------------------------------------


def test_execute_requires_expected_count(tmp_path, capsys):
    import reconcile_orphan_blobs as cli

    client, bucket, flutter_repo, dist_dir = _world(tmp_path, orphans=[_h("dd")])
    attempted = []
    bucket.move = lambda *a, **k: attempted.append("move")

    exit_code = cli.main(_argv(flutter_repo, dist_dir, "--execute"), client=client)

    assert exit_code != 0
    assert attempted == []
    assert "--expected-count" in capsys.readouterr().out


def test_execute_refuses_when_expected_count_disagrees(tmp_path, capsys):
    import reconcile_orphan_blobs as cli

    client, bucket, flutter_repo, dist_dir = _world(tmp_path, orphans=[_h("dd")])
    attempted = []
    bucket.move = lambda *a, **k: attempted.append("move")

    exit_code = cli.main(
        _argv(flutter_repo, dist_dir, "--execute", "--expected-count", "99"),
        client=client,
    )

    assert exit_code != 0
    assert attempted == []
    out = capsys.readouterr().out
    assert "99" in out and "1" in out


def test_execute_refuses_when_the_report_is_blocked(tmp_path, capsys):
    """A shard we could not read means the count is not exact — so no action."""
    import reconcile_orphan_blobs as cli

    client, bucket, flutter_repo, dist_dir = _world(tmp_path, orphans=[_h("dd")])
    attempted = []
    bucket.move = lambda *a, **k: attempted.append("move")
    real_list = bucket.list

    def flaky(path="", options=None):
        if path == f"{PREFIX}/dd":
            raise RuntimeError("The connection to the database timed out")
        return real_list(path=path, options=options)

    bucket.list = flaky

    exit_code = cli.main(
        _argv(flutter_repo, dist_dir, "--execute", "--expected-count", "1",
              "--max-attempts", "2"),
        client=client,
    )

    assert exit_code != 0
    assert attempted == []
    assert "BLOCKED" in capsys.readouterr().out


def test_there_is_no_hard_delete_option(tmp_path):
    """Quarantine is the only allowed action in this tool."""
    import reconcile_orphan_blobs as cli

    parser_actions = {
        action.option_strings[0]
        for action in cli.build_parser()._actions
        if action.option_strings
    }
    assert "--orphan-blob-action" not in parser_actions
    assert "--delete" not in parser_actions

    source = Path(cli.__file__).read_text()
    assert "delete_orphan_blob_batch" not in source


# ---------------------------------------------------------------------------
# Resumability
# ---------------------------------------------------------------------------


def test_dry_run_checkpoint_lets_a_second_pass_skip_read_shards(tmp_path):
    import reconcile_orphan_blobs as cli

    client, bucket, flutter_repo, dist_dir = _world(tmp_path, orphans=[_h("dd")])
    ckpt = tmp_path / "inv.json"

    cli.main(
        _argv(flutter_repo, dist_dir, "--checkpoint", str(ckpt)), client=client,
    )
    assert ckpt.exists()

    bucket.listed = []
    real_list = bucket.list

    def recording(path="", options=None):
        bucket.listed.append(path)
        return real_list(path=path, options=options)

    bucket.list = recording
    cli.main(
        _argv(flutter_repo, dist_dir, "--checkpoint", str(ckpt)), client=client,
    )

    assert f"{PREFIX}/aa" not in bucket.listed
    assert f"{PREFIX}/dd" not in bucket.listed


def test_execute_rescans_storage_instead_of_reusing_dry_run_inventory(
    tmp_path, monkeypatch, capsys,
):
    """The approved count is checked against fresh storage at execution time."""
    import cleanup_old_versions
    import reconcile_orphan_blobs as cli

    client, bucket, flutter_repo, dist_dir = _world(
        tmp_path, orphans=[_h("dd")],
    )
    checkpoint = tmp_path / "inventory.json"
    args = _argv(
        flutter_repo,
        dist_dir,
        "--checkpoint", str(checkpoint),
        shards="aa,dd,ee",
    )
    assert cli.main(args, client=client) == 0

    new_hash = _h("ee")
    bucket.put(f"{PREFIX}/ee/{new_hash}.json", b"new")
    attempted = []
    monkeypatch.setattr(
        cleanup_old_versions,
        "quarantine_orphan_blob_batch",
        lambda *a, **k: attempted.append(True) or (1, 0, []),
    )

    exit_code = cli.main(
        args + ["--execute", "--expected-count", "1"],
        client=client,
    )

    assert exit_code == cli.EXIT_REFUSED
    assert attempted == []
    assert "does not match the 2 orphan(s) found now" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Release pipeline: separation + honest status
# ---------------------------------------------------------------------------


def _release_source() -> str:
    return RELEASE_SH.read_text()


def test_release_no_longer_runs_the_orphan_inventory_inline():
    """A successful catalog publication must not wait minutes on maintenance."""
    source = _release_source()
    inline_calls = re.findall(
        r"cleanup_old_versions\.py[^\n]*(?:\\\n[^\n]*)*", source,
    )
    assert inline_calls, "expected release_full.sh to still run version cleanup"
    for call in inline_calls:
        if call.strip().startswith("#"):
            continue
        assert "--cleanup-orphan-blobs" not in call, (
            "release_full.sh still blocks on the full orphan scan:\n" + call
        )


def test_release_reports_version_and_orphan_cleanup_as_separate_statuses():
    source = _release_source()
    assert "Version cleanup" in source
    assert "Orphan cleanup" in source


def test_release_never_prints_an_unconditional_storage_cleanup_ok():
    source = _release_source()
    assert 'ok "Storage cleanup step done"' not in source


def test_release_points_the_operator_at_the_maintenance_command():
    source = _release_source()
    assert "reconcile_orphan_blobs.py" in source


def test_release_full_sh_is_syntactically_valid():
    result = subprocess.run(
        ["bash", "-n", str(RELEASE_SH)], capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
