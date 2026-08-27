"""Shard-window quarantine engine: request-count discipline + fail-closed proofs.

Replaces the per-blob interrogation (2 existence listings + copy + visibility
poll + delete ≈ 5 requests/blob, 3+ of them expensive shard listings) with a
per-shard machine: classify from listings, copy, one verification listing,
batched deletes, one absence-proof listing. Listing count is a function of
SHARD count, never of blob count.

The fake bucket derives eTags from content (as the live API's content-MD5
does), so a faithful copy verifies naturally and a corrupted target fails
naturally.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time

import pytest

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))

ACTIVE_PREFIX = "shared/details/sha256"
RUN_DATE = "2026-08-28"
QPREFIX = f"shared/quarantine/{RUN_DATE}"


@pytest.fixture(autouse=True)
def _no_real_backoff_sleeps(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _s: None)


def _h(shard: str, n: int) -> str:
    return shard + f"{n:062x}"


def _active(h: str) -> str:
    return f"{ACTIVE_PREFIX}/{h[:2]}/{h}.json"


def _target(h: str) -> str:
    return f"{QPREFIX}/{h[:2]}/{h}.json"


class _Bucket:
    """In-memory bucket: sorted paginated listings with {size, eTag} metadata,
    copy, batched remove — plus fault injection and an op log."""

    def __init__(self, objects=None):
        self.objects: dict[str, bytes] = dict(objects or {})
        self.ops: list[tuple] = []
        self.fail_copy_to: set[str] = set()
        self.fail_remove_containing: set[str] = set()
        self.silently_keep_on_remove: set[str] = set()
        self.drop_from_listings: set[str] = set()

    def _etag(self, data: bytes) -> str:
        return f'"{hashlib.md5(data).hexdigest()}"'

    def list(self, path="", options=None):
        self.ops.append(("list", path))
        opts = options or {}
        limit = int(opts.get("limit", 1000))
        offset = int(opts.get("offset", 0))
        base = path.rstrip("/") + "/" if path else ""
        names = sorted(
            full[len(base):]
            for full in self.objects
            if full.startswith(base)
            and "/" not in full[len(base):]
            and full not in self.drop_from_listings
        )
        return [
            {"name": n, "metadata": {
                "size": len(self.objects[base + n]),
                "eTag": self._etag(self.objects[base + n]),
            }}
            for n in names[offset:offset + limit]
        ]

    def copy(self, src, dst):
        self.ops.append(("copy", src, dst))
        if dst in self.fail_copy_to:
            raise RuntimeError(f"injected COPY failure (dst={dst})")
        if src not in self.objects:
            raise RuntimeError(f"source not found: {src}")
        self.objects[dst] = self.objects[src]
        return {"ok": True}

    def remove(self, paths):
        self.ops.append(("remove", tuple(paths)))
        for p in paths:
            if any(tag in p for tag in self.fail_remove_containing):
                raise RuntimeError(f"injected DELETE failure (path={p})")
        for p in paths:
            if p not in self.silently_keep_on_remove:
                self.objects.pop(p, None)
        return [{"name": p} for p in paths]

    # --- assertions -----------------------------------------------------
    def listing_count(self):
        return sum(1 for op in self.ops if op[0] == "list")

    def remove_batches(self):
        return [op[1] for op in self.ops if op[0] == "remove"]


class _Client:
    def __init__(self, bucket):
        self.bucket = bucket
        self.storage = self

    def from_(self, name):
        assert name == "pharmaguide"
        return self.bucket


def _seed(hashes):
    bucket = _Bucket({_active(h): f"content-{h[:12]}".encode() for h in hashes})
    return _Client(bucket), bucket


def _fingerprints(bucket, hashes):
    from release_safety.blob_inventory import ObjectFingerprint

    out = {}
    for h in hashes:
        data = bucket.objects[_active(h)]
        out[h] = ObjectFingerprint(size=len(data), etag=bucket._etag(data))
    return out


def _run(client, bucket, hashes, *, fingerprints=None, **kw):
    import cleanup_old_versions as cov

    if fingerprints is None:
        fingerprints = _fingerprints(bucket, hashes)
    return cov.quarantine_orphan_blob_batch(
        client, set(hashes),
        run_date=RUN_DATE,
        source_fingerprints=fingerprints,
        **kw,
    )


# ---------------------------------------------------------------------------
# Happy path + request-count discipline
# ---------------------------------------------------------------------------


def test_moves_all_candidates_and_listing_count_tracks_shards_not_blobs():
    hashes = [_h("aa", i) for i in range(50)] + [_h("bb", i) for i in range(50)]
    client, bucket = _seed(hashes)

    moved, failed, failed_paths = _run(client, bucket, hashes)

    assert (moved, failed, failed_paths) == (100, 0, [])
    for h in hashes:
        assert _active(h) not in bucket.objects
        assert _target(h) in bucket.objects
    # ≤4 listings per shard (classify active+target, verify target, prove
    # active) — NEVER proportional to the 100 blobs.
    assert bucket.listing_count() <= 8


def test_non_candidate_and_protected_blobs_are_untouched():
    candidates = [_h("aa", 1)]
    bystander = _h("aa", 2)
    client, bucket = _seed(candidates + [bystander])

    moved, failed, _ = _run(client, bucket, candidates)

    assert (moved, failed) == (1, 0)
    assert _active(bystander) in bucket.objects
    assert _target(bystander) not in bucket.objects


def test_batch_deletes_in_groups_of_500_and_paginates_past_1000():
    hashes = [_h("aa", i) for i in range(1200)]
    client, bucket = _seed(hashes)

    moved, failed, _ = _run(client, bucket, hashes)

    assert (moved, failed) == (1200, 0)
    batches = bucket.remove_batches()
    assert [len(b) for b in batches] == [500, 500, 200]
    # Pagination actually happened: some listing was re-requested at a
    # deeper offset (the fake honors limit/offset; 1200 > one 1000 page).
    assert bucket.listing_count() >= 6


def test_idempotent_resume_after_interrupted_move():
    """Source already gone + verified target = already complete, no re-copy."""
    hashes = [_h("aa", 1), _h("aa", 2)]
    client, bucket = _seed(hashes)
    fingerprints = _fingerprints(bucket, hashes)
    # Simulate a prior run that moved aa/1 fully.
    bucket.objects[_target(hashes[0])] = bucket.objects.pop(_active(hashes[0]))
    bucket.ops.clear()

    moved, failed, _ = _run(client, bucket, hashes, fingerprints=fingerprints)

    assert (moved, failed) == (2, 0)
    copies = [op for op in bucket.ops if op[0] == "copy"]
    assert len(copies) == 1, "the completed blob must not be re-copied"


# ---------------------------------------------------------------------------
# Fail-closed states
# ---------------------------------------------------------------------------


def test_copy_failure_preserves_source_and_fails_only_that_blob():
    hashes = [_h("aa", 1), _h("aa", 2)]
    client, bucket = _seed(hashes)
    bucket.fail_copy_to.add(_target(hashes[0]))

    moved, failed, failed_paths = _run(client, bucket, hashes)

    assert (moved, failed) == (1, 1)
    assert _active(hashes[0]) in bucket.objects, "failed copy must preserve source"
    assert _target(hashes[1]) in bucket.objects
    assert any(hashes[0] in p for p in failed_paths)


def test_target_fingerprint_mismatch_blocks_the_whole_shard():
    """A corrupted pre-existing target means our identity model is wrong for
    this shard — delete nothing here, continue elsewhere."""
    aa = [_h("aa", 1), _h("aa", 2)]
    bb = [_h("bb", 1)]
    client, bucket = _seed(aa + bb)
    bucket.objects[_target(aa[0])] = b"CORRUPTED-DIFFERENT-CONTENT"

    moved, failed, failed_paths = _run(client, bucket, aa + bb)

    assert moved == 1, "only the healthy shard proceeds"
    assert failed == 2, "every candidate in the blocked shard is failed"
    for h in aa:
        assert _active(h) in bucket.objects, "blocked shard must delete nothing"
    assert _active(bb[0]) not in bucket.objects


def test_delete_failure_leaves_recoverable_duplicate():
    hashes = [_h("aa", 1)]
    client, bucket = _seed(hashes)
    bucket.fail_remove_containing.add(hashes[0])

    moved, failed, failed_paths = _run(client, bucket, hashes)

    assert (moved, failed) == (0, 1)
    assert _active(hashes[0]) in bucket.objects
    assert _target(hashes[0]) in bucket.objects, (
        "delete failure must leave the recoverable duplicate"
    )


def test_missing_source_fingerprint_blocks_the_shard():
    from release_safety.blob_inventory import ObjectFingerprint

    aa = [_h("aa", 1)]
    bb = [_h("bb", 1)]
    client, bucket = _seed(aa + bb)
    fingerprints = _fingerprints(bucket, aa + bb)
    fingerprints[bb[0]] = ObjectFingerprint(size=3, etag=None)  # unproven

    moved, failed, _ = _run(client, bucket, aa + bb, fingerprints=fingerprints)

    assert moved == 1
    assert failed == 1
    assert _active(bb[0]) in bucket.objects


def test_source_drift_since_approval_blocks_the_shard():
    """Active object no longer matches the frozen approved fingerprint —
    storage changed since the dry run; act on nothing in that shard."""
    hashes = [_h("aa", 1)]
    client, bucket = _seed(hashes)
    fingerprints = _fingerprints(bucket, hashes)
    bucket.objects[_active(hashes[0])] = b"rewritten since approval"

    moved, failed, _ = _run(client, bucket, hashes, fingerprints=fingerprints)

    assert (moved, failed) == (0, 1)
    assert _active(hashes[0]) in bucket.objects
    assert _target(hashes[0]) not in bucket.objects


def test_candidate_missing_everywhere_fails_that_shard():
    hashes = [_h("aa", 1)]
    client, bucket = _seed(hashes)
    fingerprints = _fingerprints(bucket, hashes)
    del bucket.objects[_active(hashes[0])]

    moved, failed, _ = _run(client, bucket, hashes, fingerprints=fingerprints)

    assert (moved, failed) == (0, 1)


def test_residual_candidate_after_delete_is_reported_failed():
    """remove() returning success while the object survives must not count
    as moved — the absence proof is the authority."""
    hashes = [_h("aa", 1)]
    client, bucket = _seed(hashes)
    bucket.silently_keep_on_remove.add(_active(hashes[0]))

    moved, failed, failed_paths = _run(client, bucket, hashes)

    assert moved == 0
    assert failed == 1
    assert any("residual" in p or hashes[0] in p for p in failed_paths)


def test_vanished_bystander_is_reported_as_postcondition_violation():
    """If a non-candidate disappears during the shard window, say so loudly."""
    candidate = _h("aa", 1)
    bystander = _h("aa", 2)
    client, bucket = _seed([candidate, bystander])
    real_remove = bucket.remove

    def remove_and_eat_bystander(paths):
        result = real_remove(paths)
        bucket.objects.pop(_active(bystander), None)
        return result

    bucket.remove = remove_and_eat_bystander

    moved, failed, failed_paths = _run(client, bucket, [candidate])

    assert failed >= 1
    assert any(bystander in p for p in failed_paths)


# ---------------------------------------------------------------------------
# Checkpoint: shard-level, digest-keyed, no quadratic membership scan
# ---------------------------------------------------------------------------


def test_checkpoint_resume_skips_completed_shards(tmp_path):
    hashes = [_h("aa", 1), _h("bb", 1)]
    client, bucket = _seed(hashes)
    fingerprints = _fingerprints(bucket, hashes)
    bucket.fail_remove_containing.add(hashes[1])
    ckpt = tmp_path / "q.json"

    moved, failed, _ = _run(
        client, bucket, hashes, fingerprints=fingerprints, checkpoint_path=ckpt,
    )
    assert (moved, failed) == (1, 1)
    assert ckpt.exists()
    saved = json.loads(ckpt.read_text())
    assert "aa" in saved["shards"]
    assert "bb" not in saved["shards"], "a failed shard must not be checkpointed"

    bucket.fail_remove_containing.clear()
    bucket.ops.clear()
    moved, failed, _ = _run(
        client, bucket, hashes, fingerprints=fingerprints, checkpoint_path=ckpt,
    )

    assert (moved, failed) == (2, 0)
    touched = {op[1] for op in bucket.ops if op[0] == "list"}
    assert not any(path.endswith("/aa") for path in touched), (
        "completed shard must not be re-listed on resume"
    )
    assert not ckpt.exists(), "a fully successful run clears its checkpoint"


def test_checkpoint_for_a_different_candidate_set_is_refused(tmp_path):
    # One clean shard + one failing shard leaves a persisting checkpoint.
    hashes = [_h("aa", 1), _h("bb", 1)]
    client, bucket = _seed(hashes)
    fingerprints = _fingerprints(bucket, hashes)
    ckpt = tmp_path / "q.json"
    bucket.fail_remove_containing.add(hashes[1])
    _run(client, bucket, hashes, fingerprints=fingerprints, checkpoint_path=ckpt)
    assert ckpt.exists()

    other = [_h("aa", 7)]
    bucket.objects[_active(other[0])] = b"other"
    with pytest.raises(ValueError, match="different candidate"):
        _run(
            client, bucket, other,
            fingerprints=_fingerprints(bucket, other),
            checkpoint_path=ckpt,
        )


def test_engine_never_lists_per_blob_parents():
    """The defining property: no per-candidate existence interrogation."""
    hashes = [_h("aa", i) for i in range(40)]
    client, bucket = _seed(hashes)

    _run(client, bucket, hashes)

    assert bucket.listing_count() <= 4
