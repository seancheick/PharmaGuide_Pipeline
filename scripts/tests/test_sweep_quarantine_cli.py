"""The gated quarantine sweeper: dry-run approval artifact, guarded execute.

This is the ONLY path allowed to hard-delete expired quarantine. Contract:
dry-run default producing a durable approval JSON (dates, counts, bytes,
eTag coverage, deterministic path fingerprint); execute requires the approval
report plus matching --expected-count/--expected-bytes/--fingerprint, holds
the release lock, re-proves the candidate set fresh, refuses any drift,
batch-deletes at 500, checkpoints per shard, and counts as deleted only what
a final listing proves absent.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import date

import pytest

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))

from test_release_safety_protected_blobs import (  # noqa: E402
    FakeSupabaseClientForP35,
    _detail_index_bytes,
    _p35_bundled_and_dist,
    _registry_row,
)

QROOT = "shared/quarantine"
ELIGIBLE = "2026-07-17"
YOUNG = "2026-08-28"
TODAY = date(2026, 8, 29)
ACTIVE_VER = "2026.08.27.162958"


@pytest.fixture(autouse=True)
def _no_real_backoff_sleeps(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _s: None)


def _qh(shard: str, n: int) -> str:
    return shard + f"{n:062x}"


def _qpath(date_str: str, h: str) -> str:
    return f"{QROOT}/{date_str}/{h[:2]}/{h}.json"


def _world(tmp_path, *, eligible_hashes, young_hashes=(), active_hashes=None):
    """Registry + bundle + dist + quarantine objects on the shared P35 fake."""
    active_hashes = list(active_hashes or [_qh("aa", 900)])
    client = FakeSupabaseClientForP35()
    bucket = client.storage.from_("pharmaguide")
    bucket.put(
        f"v{ACTIVE_VER}/detail_index.json",
        _detail_index_bytes(active_hashes, ACTIVE_VER),
    )
    client.seed_registry([_registry_row(db_version=ACTIVE_VER, state="ACTIVE")])
    for h in active_hashes:
        bucket.put(f"shared/details/sha256/{h[:2]}/{h}.json", b"active-" + h[:8].encode())
    for h in eligible_hashes:
        bucket.put(_qpath(ELIGIBLE, h), b"old-" + h[:8].encode())
    for h in young_hashes:
        bucket.put(_qpath(YOUNG, h), b"young-" + h[:8].encode())
    flutter_repo, dist_dir = _p35_bundled_and_dist(
        tmp_path, bundled_hashes=active_hashes, dist_hashes=active_hashes,
    )
    return client, bucket, flutter_repo, dist_dir


def _dry(tmp_path, cli, client, **kw):
    out = tmp_path / "sweep_approval.json"
    code = cli.main(
        ["--approval-out", str(out)], client=client, today=TODAY, **kw,
    )
    return code, out


def _exec_args(tmp_path, approval, data, flutter_repo, dist_dir, **overrides):
    args = [
        "--execute",
        "--approval-report", str(approval),
        "--expected-count", str(overrides.pop("count", data["total_count"])),
        "--expected-bytes", str(overrides.pop("bytes", data["total_bytes"])),
        "--fingerprint", overrides.pop("fingerprint", data["path_fingerprint"]),
        "--flutter-repo", str(flutter_repo),
        "--dist-dir", str(dist_dir),
        "--lock-path", str(tmp_path / "release.lock"),
        "--checkpoint", str(tmp_path / "sweep.ckpt.json"),
    ]
    for key, value in overrides.items():
        args += [f"--{key}", str(value)]
    return args


# ---------------------------------------------------------------------------
# Dry run — the approval artifact
# ---------------------------------------------------------------------------


def test_dry_run_writes_the_approval_artifact_for_eligible_dates_only(tmp_path):
    import sweep_quarantine as cli

    eligible = [_qh("aa", 1), _qh("bb", 2)]
    client, _, _, _ = _world(
        tmp_path, eligible_hashes=eligible, young_hashes=[_qh("cc", 3)],
    )

    code, out = _dry(tmp_path, cli, client)

    assert code == 0
    data = json.loads(out.read_text())
    assert data["dates"] == [ELIGIBLE], "pre-TTL dates must never be included"
    assert data["total_count"] == 2
    assert data["total_bytes"] == sum(len(b"old-") + 8 for _ in eligible)
    assert data["per_date"][ELIGIBLE]["etag_coverage"] == 2
    assert len(data["path_fingerprint"]) == 64
    import hashlib

    expected = hashlib.sha256(
        "\n".join(sorted(_qpath(ELIGIBLE, h) for h in eligible)).encode("ascii")
    ).hexdigest()
    assert data["path_fingerprint"] == expected


def test_dry_run_refuses_to_write_an_approval_from_a_partial_scan(tmp_path):
    import sweep_quarantine as cli

    client, bucket, _, _ = _world(tmp_path, eligible_hashes=[_qh("aa", 1)])
    bucket.list_raises_for[f"{QROOT}/{ELIGIBLE}/aa"] = RuntimeError(
        "The connection to the database timed out"
    )

    code, out = _dry(tmp_path, cli, client)

    assert code != 0
    assert not out.exists(), "a partial scan must never become an approval"


def test_dry_run_with_nothing_eligible_writes_no_artifact(tmp_path):
    import sweep_quarantine as cli

    client, _, _, _ = _world(
        tmp_path, eligible_hashes=[], young_hashes=[_qh("cc", 3)],
    )

    code, out = _dry(tmp_path, cli, client)

    assert code == 0
    assert not out.exists()


# ---------------------------------------------------------------------------
# Execute — guarded hard delete
# ---------------------------------------------------------------------------


def _approved_world(tmp_path, cli, *, eligible=None, young=()):
    eligible = eligible if eligible is not None else [_qh("aa", 1), _qh("bb", 2)]
    client, bucket, flutter_repo, dist_dir = _world(
        tmp_path, eligible_hashes=eligible, young_hashes=young,
    )
    code, approval = _dry(tmp_path, cli, client)
    assert code == 0
    data = json.loads(approval.read_text())
    return client, bucket, flutter_repo, dist_dir, approval, data, eligible


def test_execute_requires_the_full_approval_quad(tmp_path, capsys):
    import sweep_quarantine as cli

    client, bucket, flutter_repo, dist_dir, approval, data, eligible = (
        _approved_world(tmp_path, cli)
    )
    before = dict(bucket.objects)

    code = cli.main(
        ["--execute", "--approval-report", str(approval)],
        client=client, today=TODAY,
    )

    assert code != 0
    assert bucket.objects == before
    out = capsys.readouterr().out
    assert "--expected-count" in out


@pytest.mark.parametrize("tamper", ["count", "bytes", "fingerprint"])
def test_execute_refuses_mismatched_approval_values(tmp_path, tamper):
    import sweep_quarantine as cli

    client, bucket, flutter_repo, dist_dir, approval, data, eligible = (
        _approved_world(tmp_path, cli)
    )
    before = dict(bucket.objects)
    override = {tamper: {"count": 999, "bytes": 1, "fingerprint": "0" * 64}[tamper]}

    code = cli.main(
        _exec_args(tmp_path, approval, data, flutter_repo, dist_dir, **override),
        client=client, today=TODAY,
    )

    assert code != 0
    assert bucket.objects == before


def test_execute_refuses_a_changed_candidate_set(tmp_path, capsys):
    import sweep_quarantine as cli

    client, bucket, flutter_repo, dist_dir, approval, data, eligible = (
        _approved_world(tmp_path, cli)
    )
    # A new object landed under the approved date after approval.
    bucket.put(_qpath(ELIGIBLE, _qh("dd", 9)), b"late arrival")
    before = dict(bucket.objects)

    code = cli.main(
        _exec_args(tmp_path, approval, data, flutter_repo, dist_dir),
        client=client, today=TODAY,
    )

    assert code != 0
    assert bucket.objects == before
    assert "changed" in capsys.readouterr().out.lower()


def test_execute_refuses_a_date_that_is_no_longer_eligible(tmp_path):
    import sweep_quarantine as cli

    client, bucket, flutter_repo, dist_dir, approval, data, eligible = (
        _approved_world(tmp_path, cli)
    )
    before = dict(bucket.objects)

    code = cli.main(
        _exec_args(tmp_path, approval, data, flutter_repo, dist_dir),
        client=client, today=date(2026, 8, 1),  # before the TTL boundary
    )

    assert code != 0
    assert bucket.objects == before


def test_execute_deletes_batches_of_500_proves_absence_and_holds_the_lock(tmp_path):
    import sweep_quarantine as cli

    eligible = [_qh("aa", i) for i in range(1200)]
    client, bucket, flutter_repo, dist_dir, approval, data, _ = (
        _approved_world(tmp_path, cli, eligible=eligible)
    )
    lock_path = tmp_path / "release.lock"
    batches = []
    lock_during_remove = []
    real_remove = bucket.remove

    def observing_remove(paths):
        batches.append(len(paths))
        lock_during_remove.append(lock_path.exists())
        return real_remove(paths)

    bucket.remove = observing_remove

    code = cli.main(
        _exec_args(tmp_path, approval, data, flutter_repo, dist_dir),
        client=client, today=TODAY,
    )

    assert code == 0
    assert all(size <= 500 for size in batches)
    assert max(batches) == 500
    assert all(lock_during_remove), "the release lock must be held during deletes"
    assert not lock_path.exists(), "lock released afterwards"
    for h in eligible:
        assert _qpath(ELIGIBLE, h) not in bucket.objects
    # The active blob and its index are untouched.
    assert any(p.startswith("shared/details/") for p in bucket.objects)


def test_execute_reports_residuals_and_exits_nonzero(tmp_path, capsys):
    import sweep_quarantine as cli

    eligible = [_qh("aa", 1), _qh("bb", 2)]
    client, bucket, flutter_repo, dist_dir, approval, data, _ = (
        _approved_world(tmp_path, cli, eligible=eligible)
    )
    survivor = _qpath(ELIGIBLE, eligible[0])
    real_remove = bucket.remove

    def lying_remove(paths):
        result = real_remove(paths)
        if survivor in paths:
            bucket.objects[survivor] = b"still here"
        return result

    bucket.remove = lying_remove

    code = cli.main(
        _exec_args(tmp_path, approval, data, flutter_repo, dist_dir),
        client=client, today=TODAY,
    )

    assert code != 0
    assert "residual" in capsys.readouterr().out.lower()


def test_execute_checkpoint_resume_does_not_redelete_proven_shards(tmp_path):
    import sweep_quarantine as cli

    eligible = [_qh("aa", 1), _qh("bb", 2)]
    client, bucket, flutter_repo, dist_dir, approval, data, _ = (
        _approved_world(tmp_path, cli, eligible=eligible)
    )
    real_remove = bucket.remove

    def failing_bb(paths):
        if any("/bb/" in p for p in paths):
            raise RuntimeError("The connection to the database timed out")
        return real_remove(paths)

    bucket.remove = failing_bb
    code = cli.main(
        _exec_args(tmp_path, approval, data, flutter_repo, dist_dir),
        client=client, today=TODAY,
    )
    assert code != 0
    assert (tmp_path / "sweep.ckpt.json").exists()

    bucket.remove = real_remove
    removes = []

    def recording_remove(paths):
        removes.append(tuple(paths))
        return real_remove(paths)

    bucket.remove = recording_remove
    code = cli.main(
        _exec_args(tmp_path, approval, data, flutter_repo, dist_dir),
        client=client, today=TODAY,
    )

    assert code == 0
    assert all(
        not any("/aa/" in p for p in batch) for batch in removes
    ), "a proven-complete shard must not be re-deleted on resume"
    for h in eligible:
        assert _qpath(ELIGIBLE, h) not in bucket.objects
    assert not (tmp_path / "sweep.ckpt.json").exists()


def test_execute_refuses_when_quarantine_holds_the_only_protected_copy(
    tmp_path, capsys,
):
    """If a protected hash's ONLY copy sits in quarantine, sweeping it would
    destroy the last copy of a live blob. Refuse the whole run."""
    import sweep_quarantine as cli

    protected_hash = _qh("aa", 900)  # referenced by the ACTIVE catalog
    client, bucket, flutter_repo, dist_dir = _world(
        tmp_path,
        eligible_hashes=[_qh("cc", 5)],
        active_hashes=[protected_hash],
    )
    # Catastrophic state: active copy is GONE; quarantine holds the only copy.
    del bucket.objects[f"shared/details/sha256/{protected_hash[:2]}/{protected_hash}.json"]
    bucket.put(_qpath(ELIGIBLE, protected_hash), b"only copy")

    code, approval = _dry(tmp_path, cli, client)
    assert code == 0
    data = json.loads(approval.read_text())
    before = dict(bucket.objects)

    code = cli.main(
        _exec_args(tmp_path, approval, data, flutter_repo, dist_dir),
        client=client, today=TODAY,
    )

    assert code != 0
    assert bucket.objects == before, "nothing may be deleted in that state"
    assert "protected" in capsys.readouterr().out.lower()
