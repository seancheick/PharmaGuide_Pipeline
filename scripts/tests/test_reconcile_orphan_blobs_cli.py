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


def _dry_run_artifact(tmp_path, cli, client, flutter_repo, dist_dir,
                      *, shards="aa,dd", run_date="2026-08-28"):
    """Produce a real approval artifact through the CLI's own dry run."""
    artifact = tmp_path / "approval.json"
    exit_code = cli.main(
        _argv(flutter_repo, dist_dir,
              "--json-report", str(artifact),
              "--run-date", run_date,
              shards=shards),
        client=client,
    )
    assert exit_code == 0, "artifact dry run must succeed"
    return artifact


def test_execute_requires_an_approval_artifact(tmp_path, capsys):
    import reconcile_orphan_blobs as cli

    client, bucket, flutter_repo, dist_dir = _world(tmp_path, orphans=[_h("dd")])
    before = dict(bucket.objects)

    exit_code = cli.main(
        _argv(flutter_repo, dist_dir, "--execute", "--expected-count", "1"),
        client=client,
    )

    assert exit_code == cli.EXIT_REFUSED
    assert bucket.objects == before
    assert "--approval-report" in capsys.readouterr().out


def test_execute_refuses_count_disagreeing_with_the_artifact(tmp_path, capsys):
    import reconcile_orphan_blobs as cli

    client, bucket, flutter_repo, dist_dir = _world(tmp_path, orphans=[_h("dd")])
    artifact = _dry_run_artifact(tmp_path, cli, client, flutter_repo, dist_dir)
    before = dict(bucket.objects)

    exit_code = cli.main(
        _argv(flutter_repo, dist_dir, "--execute", "--expected-count", "99",
              "--approval-report", str(artifact)),
        client=client,
    )

    assert exit_code == cli.EXIT_REFUSED
    assert bucket.objects == before
    out = capsys.readouterr().out
    assert "99" in out


def test_execute_refuses_a_tampered_artifact(tmp_path, capsys):
    """The digest pins the SET, not just its size: a swapped hash with the
    stale digest must be refused before anything is touched."""
    import reconcile_orphan_blobs as cli

    client, bucket, flutter_repo, dist_dir = _world(tmp_path, orphans=[_h("dd")])
    artifact = _dry_run_artifact(tmp_path, cli, client, flutter_repo, dist_dir)

    data = json.loads(artifact.read_text())
    (old_hash, fp), = list(data["candidate_fingerprints"].items())
    swapped = _h("ee")
    data["candidate_fingerprints"] = {swapped: fp}
    artifact.write_text(json.dumps(data))
    before = dict(bucket.objects)

    exit_code = cli.main(
        _argv(flutter_repo, dist_dir, "--execute", "--expected-count", "1",
              "--approval-report", str(artifact)),
        client=client,
    )

    assert exit_code == cli.EXIT_REFUSED
    assert bucket.objects == before
    assert "digest" in capsys.readouterr().out.lower()


def test_execute_refuses_non_hash_candidate_even_with_recomputed_digest(
    tmp_path, capsys,
):
    """An approval artifact is input, not a trusted path builder. Recomputing
    its digest must not make a malformed or path-shaped candidate actionable."""
    import reconcile_orphan_blobs as cli
    from release_safety.orphan_reconcile import hash_set_digest

    client, bucket, flutter_repo, dist_dir = _world(tmp_path, orphans=[_h("dd")])
    artifact = _dry_run_artifact(tmp_path, cli, client, flutter_repo, dist_dir)
    data = json.loads(artifact.read_text())
    (_old_hash, fp), = data["candidate_fingerprints"].items()
    malformed = "../not-a-content-hash"
    data["candidate_fingerprints"] = {malformed: fp}
    data["candidate_digest"] = hash_set_digest([malformed])
    artifact.write_text(json.dumps(data))
    before = dict(bucket.objects)

    exit_code = cli.main(
        _argv(flutter_repo, dist_dir, "--execute", "--expected-count", "1",
              "--approval-report", str(artifact)),
        client=client,
    )

    assert exit_code == cli.EXIT_REFUSED
    assert bucket.objects == before
    assert "64-char lowercase hex" in capsys.readouterr().out


def test_execute_refuses_candidate_without_a_positive_recorded_size(
    tmp_path, capsys,
):
    import reconcile_orphan_blobs as cli

    client, bucket, flutter_repo, dist_dir = _world(tmp_path, orphans=[_h("dd")])
    artifact = _dry_run_artifact(tmp_path, cli, client, flutter_repo, dist_dir)
    data = json.loads(artifact.read_text())
    candidate = next(iter(data["candidate_fingerprints"]))
    data["candidate_fingerprints"][candidate]["size"] = 0
    artifact.write_text(json.dumps(data))
    before = dict(bucket.objects)

    exit_code = cli.main(
        _argv(flutter_repo, dist_dir, "--execute", "--expected-count", "1",
              "--approval-report", str(artifact)),
        client=client,
    )

    assert exit_code == cli.EXIT_REFUSED
    assert bucket.objects == before
    assert "positive size" in capsys.readouterr().out


def test_execute_refuses_a_blocked_report_as_artifact(tmp_path, capsys):
    """A blocked dry report pins nothing approvable and cannot authorize."""
    import reconcile_orphan_blobs as cli

    client, bucket, flutter_repo, dist_dir = _world(tmp_path, orphans=[_h("dd")])
    artifact = _dry_run_artifact(tmp_path, cli, client, flutter_repo, dist_dir)
    data = json.loads(artifact.read_text())
    data["blocked_reason"] = "simulated: inventory incomplete"
    data["candidate_digest"] = None
    data["candidate_fingerprints"] = {}
    artifact.write_text(json.dumps(data))
    before = dict(bucket.objects)

    exit_code = cli.main(
        _argv(flutter_repo, dist_dir, "--execute", "--expected-count", "0",
              "--approval-report", str(artifact)),
        client=client,
    )

    assert exit_code == cli.EXIT_REFUSED
    assert bucket.objects == before


def test_execute_moves_the_frozen_set_and_the_cli_resumes_for_real(tmp_path, capsys):
    """The reproduced operational gap: after a partial run, moved blobs vanish
    from any fresh scan, so a count-pinned re-run could never match again.
    Executing FROM the frozen artifact makes restart converge: same artifact,
    same count, same quarantine date — even across midnight."""
    import reconcile_orphan_blobs as cli

    orphans = [_h("dd"), _h("ee")]
    client, bucket, flutter_repo, dist_dir = _world(tmp_path, orphans=orphans)
    artifact = _dry_run_artifact(
        tmp_path, cli, client, flutter_repo, dist_dir,
        shards="aa,dd,ee", run_date="2026-08-28",
    )
    ckpt = tmp_path / "q.ckpt.json"

    # Run 1: shard ee's delete fails -> partial success, nonzero exit.
    real_remove = bucket.remove

    def failing_remove(paths):
        if any(_h("ee") in p for p in paths):
            raise RuntimeError("The connection to the database timed out")
        return real_remove(paths)

    bucket.remove = failing_remove
    exit_code = cli.main(
        _argv(flutter_repo, dist_dir, "--execute", "--expected-count", "2",
              "--approval-report", str(artifact),
              "--quarantine-checkpoint", str(ckpt),
              "--max-attempts", "2",
              "--lock-path", str(tmp_path / "lock"),
              shards="aa,dd,ee"),
        client=client,
    )
    assert exit_code != 0
    assert f"{PREFIX}/dd/{_h('dd')}.json" not in bucket.objects, "dd moved"
    assert f"{PREFIX}/ee/{_h('ee')}.json" in bucket.objects, "ee still active"

    # Run 2 (the real CLI restart, storage now CHANGED): same artifact, same
    # count, remove healthy again -> converges.
    bucket.remove = real_remove
    exit_code = cli.main(
        _argv(flutter_repo, dist_dir, "--execute", "--expected-count", "2",
              "--approval-report", str(artifact),
              "--quarantine-checkpoint", str(ckpt),
              "--lock-path", str(tmp_path / "lock"),
              shards="aa,dd,ee"),
        client=client,
    )
    assert exit_code == 0
    for h in orphans:
        assert f"{PREFIX}/{h[:2]}/{h}.json" not in bucket.objects
        assert (
            f"shared/quarantine/2026-08-28/{h[:2]}/{h}.json" in bucket.objects
        ), "every blob lands under the ARTIFACT's quarantine date"


def test_execute_reports_prior_reverification_separately_from_mutation_failure(
    tmp_path, capsys,
):
    import reconcile_orphan_blobs as cli

    orphans = [_h("dd"), _h("ee")]
    client, bucket, flutter_repo, dist_dir = _world(tmp_path, orphans=orphans)
    artifact = _dry_run_artifact(
        tmp_path, cli, client, flutter_repo, dist_dir,
        shards="aa,dd,ee", run_date="2026-08-28",
    )
    ckpt = tmp_path / "q.ckpt.json"
    lock_path = tmp_path / "lock"
    real_remove = bucket.remove

    def fail_ee_delete(paths):
        if any(_h("ee") in path for path in paths):
            raise RuntimeError("DatabaseTimeout: connection timed out")
        return real_remove(paths)

    bucket.remove = fail_ee_delete
    first_exit = cli.main(
        _argv(flutter_repo, dist_dir, "--execute", "--expected-count", "2",
              "--approval-report", str(artifact),
              "--quarantine-checkpoint", str(ckpt),
              "--max-attempts", "2", "--lock-path", str(lock_path),
              shards="aa,dd,ee"),
        client=client,
    )
    assert first_exit != 0

    bucket.remove = real_remove
    real_list = bucket.list

    def fail_dd_reverification(path="", options=None):
        if path == f"{PREFIX}/dd":
            raise RuntimeError("DatabaseTimeout: connection timed out")
        return real_list(path=path, options=options)

    bucket.list = fail_dd_reverification
    capsys.readouterr()
    second_exit = cli.main(
        _argv(flutter_repo, dist_dir, "--execute", "--expected-count", "2",
              "--approval-report", str(artifact),
              "--quarantine-checkpoint", str(ckpt),
              "--max-attempts", "2", "--lock-path", str(lock_path),
              shards="aa,dd,ee"),
        client=client,
    )

    output = capsys.readouterr().out.lower()
    assert second_exit != 0
    assert "0 mutation failures" in output
    assert "1 verification unavailable" in output
    assert "fresh dry run" in output


def test_execute_blocks_candidates_that_became_protected(tmp_path, capsys):
    """A frozen candidate re-referenced by a NEWER retained catalog since
    approval must be skipped loudly — identical content means identical
    fingerprints, so drift detection alone cannot catch this."""
    import reconcile_orphan_blobs as cli
    from test_release_safety_protected_blobs import (
        _detail_index_bytes,
        _registry_row,
    )

    orphans = [_h("dd"), _h("ee")]
    client, bucket, flutter_repo, dist_dir = _world(tmp_path, orphans=orphans)
    artifact = _dry_run_artifact(
        tmp_path, cli, client, flutter_repo, dist_dir, shards="aa,dd,ee",
    )

    # A new ACTIVE catalog now references dd.
    newver = "2026.08.29.000000"
    bucket.put(
        f"v{newver}/detail_index.json",
        _detail_index_bytes([_h("dd")], newver),
    )
    client.seed_registry([_registry_row(db_version=newver, state="ACTIVE")])

    exit_code = cli.main(
        _argv(flutter_repo, dist_dir, "--execute", "--expected-count", "2",
              "--approval-report", str(artifact),
              "--lock-path", str(tmp_path / "lock"),
              shards="aa,dd,ee"),
        client=client,
    )

    out = capsys.readouterr().out
    assert exit_code != 0
    assert f"{PREFIX}/dd/{_h('dd')}.json" in bucket.objects, (
        "the re-protected candidate must NOT be moved"
    )
    assert f"{PREFIX}/ee/{_h('ee')}.json" not in bucket.objects, (
        "still-orphaned candidates proceed"
    )
    assert "protected" in out.lower()


def test_execute_holds_the_release_lock_through_mutations(tmp_path):
    import reconcile_orphan_blobs as cli

    client, bucket, flutter_repo, dist_dir = _world(tmp_path, orphans=[_h("dd")])
    artifact = _dry_run_artifact(tmp_path, cli, client, flutter_repo, dist_dir)
    lock_path = tmp_path / "release.lock"

    lock_seen_during_copy = []
    real_copy = bucket.copy

    def observing_copy(src, dst):
        lock_seen_during_copy.append(lock_path.exists())
        return real_copy(src, dst)

    bucket.copy = observing_copy

    exit_code = cli.main(
        _argv(flutter_repo, dist_dir, "--execute", "--expected-count", "1",
              "--approval-report", str(artifact),
              "--lock-path", str(lock_path)),
        client=client,
    )

    assert exit_code == 0
    assert lock_seen_during_copy == [True], (
        "the release lock must be held while storage is being mutated"
    )
    assert not lock_path.exists(), "the lock is released afterwards"


def test_execute_refuses_when_another_process_holds_the_lock(tmp_path, capsys):
    import reconcile_orphan_blobs as cli

    client, bucket, flutter_repo, dist_dir = _world(tmp_path, orphans=[_h("dd")])
    artifact = _dry_run_artifact(tmp_path, cli, client, flutter_repo, dist_dir)
    lock_path = tmp_path / "release.lock"
    lock_path.write_text(json.dumps({
        "pid": os.getpid(),  # a live pid that is not us... it IS us; use ppid
        "hostname": "test",
        "acquired_at": "2026-08-28T00:00:00+00:00",
        "current_step": "concurrent release",
    }))
    before = dict(bucket.objects)

    # A live foreign holder: use PID 1 (always alive, never us).
    lock_path.write_text(json.dumps({
        "pid": 1,
        "hostname": "test",
        "acquired_at": "2026-08-28T00:00:00+00:00",
        "current_step": "concurrent release",
    }))

    exit_code = cli.main(
        _argv(flutter_repo, dist_dir, "--execute", "--expected-count", "1",
              "--approval-report", str(artifact),
              "--lock-path", str(lock_path)),
        client=client,
    )

    assert exit_code != 0
    assert bucket.objects == before, "no mutation while another release runs"


def test_canary_acts_on_a_deterministic_subset_of_the_frozen_set_only(tmp_path):
    import reconcile_orphan_blobs as cli

    orphans = sorted([_h("dd"), _h("ee"), _h("ff")])
    client, bucket, flutter_repo, dist_dir = _world(tmp_path, orphans=orphans)
    artifact = _dry_run_artifact(
        tmp_path, cli, client, flutter_repo, dist_dir, shards="aa,dd,ee,ff",
    )

    exit_code = cli.main(
        _argv(flutter_repo, dist_dir, "--execute", "--canary", "2",
              "--expected-count", "2",
              "--approval-report", str(artifact),
              "--lock-path", str(tmp_path / "lock"),
              shards="aa,dd,ee,ff"),
        client=client,
    )

    assert exit_code == 0
    moved = [h for h in orphans if f"{PREFIX}/{h[:2]}/{h}.json" not in bucket.objects]
    assert moved == orphans[:2], "the canary subset must be deterministic"
    assert f"{PREFIX}/{orphans[2][:2]}/{orphans[2]}.json" in bucket.objects


def test_canary_selection_is_deterministic_and_spans_all_available_shards():
    import reconcile_orphan_blobs as cli

    selector = getattr(cli, "_select_canary_candidates", None)
    assert selector is not None, "the canary needs an explicit selection policy"
    candidates = [
        f"{shard:02x}{ordinal:062x}"
        for shard in range(256)
        for ordinal in range(2)
    ]

    selected = selector(candidates, 256)

    assert selected == selector(list(reversed(candidates)), 256)
    assert {candidate[:2] for candidate in selected} == {
        f"{shard:02x}" for shard in range(256)
    }


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
    cleanup_source = (
        Path(cli.__file__).with_name("cleanup_old_versions.py").read_text()
    )
    assert "delete_orphan_blob_batch" not in source + cleanup_source
    assert "def _remove_storage_batch" not in cleanup_source


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
    assert "--approval-report" in source


def test_release_full_sh_is_syntactically_valid():
    result = subprocess.run(
        ["bash", "-n", str(RELEASE_SH)], capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
