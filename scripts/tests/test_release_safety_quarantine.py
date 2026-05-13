"""Tests for scripts/release_safety/quarantine.py — move-to-quarantine
+ recover (ADR-0001 P2.1a).

Mock-based tests against a small in-memory Supabase storage client.
The mock supports:
  - storage.from_(bucket).copy(src, dst)
  - storage.from_(bucket).remove([paths])
  - storage.from_(bucket).list(path, options)
plus failure-injection hooks so we can exercise the COPY/DELETE
atomicity contract without a real network.

No real Supabase. No network. Per ADR-0001 P2 sign-off.
"""

from __future__ import annotations

import os
import sys
from typing import Optional, Set
import pytest

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))


# ---------------------------------------------------------------------------
# Mock Supabase storage
# ---------------------------------------------------------------------------


class MockBucket:
    """In-memory Supabase bucket. Maps full path -> bytes."""

    def __init__(self):
        # path -> bytes (we don't care about content, but tracking
        # presence + size lets us verify "object exists").
        self.objects: dict = {}

        # Failure injection: if a path is in fail_copy_to, the next
        # copy(_, that_path) raises. Same for fail_remove and fail_copy_from.
        self.fail_copy_to: Set[str] = set()
        self.fail_copy_from: Set[str] = set()
        self.fail_remove: Set[str] = set()

    def copy(self, src: str, dst: str):
        if src in self.fail_copy_from:
            raise RuntimeError(f"injected COPY failure (src={src})")
        if dst in self.fail_copy_to:
            raise RuntimeError(f"injected COPY failure (dst={dst})")
        if src not in self.objects:
            raise RuntimeError(f"source not found: {src}")
        self.objects[dst] = self.objects[src]
        return {"ok": True}

    def remove(self, paths):
        for p in paths:
            if p in self.fail_remove:
                raise RuntimeError(f"injected DELETE failure (path={p})")
            self.objects.pop(p, None)
        return [{"name": p} for p in paths]

    def list(self, path: str, options=None):
        # Return objects whose immediate parent matches `path`.
        # path = "shared/details/sha256/aa" → return entries named like
        # "{hash}.json" (just the leaf name, per Supabase API shape).
        prefix = path.rstrip("/") + "/" if path else ""
        results = []
        seen_dirs: Set[str] = set()
        for full in self.objects:
            if not full.startswith(prefix):
                continue
            rest = full[len(prefix):]
            if "/" not in rest:
                results.append({"name": rest})
            else:
                # Directory child — surface the immediate subdirectory name once.
                first = rest.split("/", 1)[0]
                if first not in seen_dirs:
                    seen_dirs.add(first)
                    results.append({"name": first})
        return results


class MockStorageNamespace:
    def __init__(self):
        self.buckets: dict = {}

    def from_(self, bucket: str) -> MockBucket:
        return self.buckets.setdefault(bucket, MockBucket())


class MockSupabaseClient:
    def __init__(self):
        self.storage = MockStorageNamespace()


# Shorthand helpers for tests
def _h(idx: int) -> str:
    return f"{idx:064x}"


def _active_path(blob_hash: str) -> str:
    return f"shared/details/sha256/{blob_hash[:2]}/{blob_hash}.json"


def _quarantine_path(date_str: str, blob_hash: str) -> str:
    return f"shared/quarantine/{date_str}/{blob_hash[:2]}/{blob_hash}.json"


# ---------------------------------------------------------------------------
# Test 1 — quarantine_target_path: pure path computation
# ---------------------------------------------------------------------------


def test_p2_1a_quarantine_target_path_default_today():
    from release_safety.quarantine import quarantine_target_path
    from datetime import datetime, timezone

    src = _active_path(_h(0))
    target = quarantine_target_path(src)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    assert target == f"shared/quarantine/{today}/00/{_h(0)}.json"


def test_p2_1a_quarantine_target_path_explicit_run_date():
    from release_safety.quarantine import quarantine_target_path

    src = _active_path(_h(0))
    target = quarantine_target_path(src, run_date="2026-05-12")

    assert target == f"shared/quarantine/2026-05-12/00/{_h(0)}.json"


@pytest.mark.parametrize(
    "bad_src",
    [
        "not/a/storage/path",
        "shared/details/sha256/aa/short.json",       # not 64 hex
        "shared/details/sha256/AA/" + _h(0) + ".json",  # uppercase shard
        f"shared/details/sha256/00/{_h(0)}.txt",     # wrong extension
        "",
    ],
)
def test_p2_1a_quarantine_target_path_rejects_malformed_source(bad_src):
    from release_safety.quarantine import quarantine_target_path

    with pytest.raises(ValueError, match="active storage shape"):
        quarantine_target_path(bad_src)


def test_p2_1a_quarantine_target_path_rejects_malformed_run_date():
    from release_safety.quarantine import quarantine_target_path

    with pytest.raises(ValueError, match="ISO YYYY-MM-DD"):
        quarantine_target_path(_active_path(_h(0)), run_date="2026/05/12")


# ---------------------------------------------------------------------------
# Test 2 — quarantine_blob happy path: source moves to quarantine
# ---------------------------------------------------------------------------


def test_p2_1a_quarantine_blob_happy_path(monkeypatch):
    from release_safety.quarantine import quarantine_blob

    client = MockSupabaseClient()
    bucket = client.storage.from_("pharmaguide")
    src = _active_path(_h(42))
    bucket.objects[src] = b"blob bytes"

    ok, err = quarantine_blob(client, src, run_date="2026-05-12")

    assert ok is True
    assert err is None
    # Source is gone, quarantine target has the bytes.
    assert src not in bucket.objects
    target = _quarantine_path("2026-05-12", _h(42))
    assert target in bucket.objects
    assert bucket.objects[target] == b"blob bytes"


# ---------------------------------------------------------------------------
# Test 3 — quarantine_blob idempotent: source missing + target present
# ---------------------------------------------------------------------------


def test_p2_1a_quarantine_blob_idempotent_already_quarantined(monkeypatch):
    """Re-running cleanup on already-quarantined blobs is a no-op
    success, not an error. Required by HR-9."""
    from release_safety.quarantine import quarantine_blob

    client = MockSupabaseClient()
    bucket = client.storage.from_("pharmaguide")
    blob_hash = _h(42)
    target = _quarantine_path("2026-05-12", blob_hash)
    bucket.objects[target] = b"already moved"
    # Note: src is intentionally NOT in bucket.objects

    src = _active_path(blob_hash)
    ok, err = quarantine_blob(client, src, run_date="2026-05-12")

    assert ok is True
    assert err is None
    # Target still there, source still absent. No double-move, no error.
    assert target in bucket.objects
    assert src not in bucket.objects


# ---------------------------------------------------------------------------
# Test 4 — quarantine_blob: source AND target missing → fails (cleanup
#          asked us to quarantine something that doesn't exist)
# ---------------------------------------------------------------------------


def test_p2_1a_quarantine_blob_fails_when_neither_source_nor_target_exist():
    from release_safety.quarantine import quarantine_blob

    client = MockSupabaseClient()
    src = _active_path(_h(99))

    ok, err = quarantine_blob(client, src, run_date="2026-05-12")

    assert ok is False
    assert err is not None
    assert "not present" in err.lower() or "nothing to quarantine" in err.lower()


# ---------------------------------------------------------------------------
# Test 5 — quarantine_blob COPY failure: source preserved
# ---------------------------------------------------------------------------


def test_p2_1a_quarantine_blob_copy_failure_preserves_source():
    """If COPY fails, source MUST remain in active storage. The blob is
    then recoverable by the next cleanup attempt — no data loss."""
    from release_safety.quarantine import quarantine_blob

    client = MockSupabaseClient()
    bucket = client.storage.from_("pharmaguide")
    src = _active_path(_h(0))
    bucket.objects[src] = b"important data"

    target = _quarantine_path("2026-05-12", _h(0))
    bucket.fail_copy_to.add(target)

    ok, err = quarantine_blob(client, src, run_date="2026-05-12")

    assert ok is False
    assert err is not None
    assert "COPY" in err
    assert "source preserved" in err
    # Source MUST still exist; target MUST NOT exist.
    assert src in bucket.objects
    assert target not in bucket.objects


# ---------------------------------------------------------------------------
# Test 6 — quarantine_blob DELETE-source failure after COPY
# ---------------------------------------------------------------------------


def test_p2_1a_quarantine_blob_delete_failure_after_copy_reports_clearly():
    """COPY succeeds, DELETE source fails. Both copies exist; next
    cleanup pass will retry the DELETE. Error message must explain
    the duplicate state to the operator."""
    from release_safety.quarantine import quarantine_blob

    client = MockSupabaseClient()
    bucket = client.storage.from_("pharmaguide")
    src = _active_path(_h(0))
    bucket.objects[src] = b"data"
    bucket.fail_remove.add(src)

    ok, err = quarantine_blob(client, src, run_date="2026-05-12")

    assert ok is False
    assert err is not None
    assert "DELETE" in err
    assert "duplicated" in err.lower()
    # Both copies still present (COPY succeeded, DELETE failed).
    target = _quarantine_path("2026-05-12", _h(0))
    assert src in bucket.objects
    assert target in bucket.objects


# ---------------------------------------------------------------------------
# Test 7 — recover_blob happy path: quarantine → active
# ---------------------------------------------------------------------------


def test_p2_1a_recover_blob_happy_path():
    from release_safety.quarantine import recover_blob

    client = MockSupabaseClient()
    bucket = client.storage.from_("pharmaguide")
    blob_hash = _h(0)
    quar_path = _quarantine_path("2026-04-15", blob_hash)
    bucket.objects[quar_path] = b"recoverable data"

    ok, err = recover_blob(client, blob_hash, search_dates=["2026-04-15"])

    assert ok is True
    assert err is None
    # Active path now has the bytes; quarantine copy is gone.
    active = _active_path(blob_hash)
    assert active in bucket.objects
    assert bucket.objects[active] == b"recoverable data"
    assert quar_path not in bucket.objects


# ---------------------------------------------------------------------------
# Test 8 — recover_blob idempotent: already at active path
# ---------------------------------------------------------------------------


def test_p2_1a_recover_blob_idempotent_already_at_active_path():
    from release_safety.quarantine import recover_blob

    client = MockSupabaseClient()
    bucket = client.storage.from_("pharmaguide")
    blob_hash = _h(0)
    active = _active_path(blob_hash)
    bucket.objects[active] = b"already restored"

    ok, err = recover_blob(client, blob_hash, search_dates=["2026-04-15"])

    assert ok is True
    assert err is None
    # Still at active path; no duplicate writes.
    assert bucket.objects[active] == b"already restored"


# ---------------------------------------------------------------------------
# Test 9 — recover_blob: blob not found anywhere → false with TTL hint
# ---------------------------------------------------------------------------


def test_p2_1a_recover_blob_not_found_returns_false_with_ttl_hint():
    """If the blob is past the 30-day TTL (sweeper hard-deleted it), it
    is no longer recoverable. Error message must mention the TTL."""
    from release_safety.quarantine import recover_blob

    client = MockSupabaseClient()
    blob_hash = _h(99)

    ok, err = recover_blob(
        client, blob_hash,
        search_dates=["2026-04-01", "2026-04-02"],
    )

    assert ok is False
    assert err is not None
    assert "30-day TTL" in err or "no longer possible" in err


# ---------------------------------------------------------------------------
# Test 10 — recover_blob: invalid hash format raises ValueError
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_hash",
    ["short", "A" * 64, "g" * 64, "", "0" * 63, "0" * 65],
)
def test_p2_1a_recover_blob_rejects_malformed_hash(bad_hash):
    from release_safety.quarantine import recover_blob

    client = MockSupabaseClient()
    with pytest.raises(ValueError, match="64-char lowercase hex"):
        recover_blob(client, bad_hash)


# ---------------------------------------------------------------------------
# Test 11 — parse_quarantine_path round-trip
# ---------------------------------------------------------------------------


def test_p2_1a_parse_quarantine_path_round_trip():
    from release_safety.quarantine import (
        quarantine_target_path,
        parse_quarantine_path,
    )

    src = _active_path(_h(123))
    target = quarantine_target_path(src, run_date="2026-05-12")
    parsed = parse_quarantine_path(target)

    assert parsed is not None
    assert parsed.date_str == "2026-05-12"
    assert parsed.shard == _h(123)[:2]
    assert parsed.hash == _h(123)
    assert parsed.leaf == f"{_h(123)}.json"


def test_p2_1a_parse_quarantine_path_returns_none_for_malformed():
    from release_safety.quarantine import parse_quarantine_path

    assert parse_quarantine_path("not/a/quarantine/path") is None
    assert parse_quarantine_path("shared/details/sha256/aa/" + _h(0) + ".json") is None
    assert parse_quarantine_path("shared/quarantine/badformat/aa/" + _h(0) + ".json") is None


# ---------------------------------------------------------------------------
# Test 12 — list_quarantine_dates returns sorted ISO date directories
# ---------------------------------------------------------------------------


def test_p2_1a_list_quarantine_dates_sorted_and_filtered():
    """Only valid YYYY-MM-DD directories are returned. Sorted ascending
    so the sweeper iterates oldest-first."""
    from release_safety.quarantine import list_quarantine_dates

    client = MockSupabaseClient()
    bucket = client.storage.from_("pharmaguide")
    # Spread some quarantined blobs across multiple dates + add a bogus dir
    bucket.objects[f"shared/quarantine/2026-04-15/00/{_h(0)}.json"] = b"x"
    bucket.objects[f"shared/quarantine/2026-05-01/00/{_h(1)}.json"] = b"y"
    bucket.objects[f"shared/quarantine/2026-04-01/00/{_h(2)}.json"] = b"z"
    bucket.objects[f"shared/quarantine/badly_named/00/{_h(3)}.json"] = b"q"  # filtered

    dates = list_quarantine_dates(client)
    assert dates == ["2026-04-01", "2026-04-15", "2026-05-01"]


# ---------------------------------------------------------------------------
# Test 13 — recover_blob restores then opportunistically cleans up other
#           quarantine copies of the same hash
# ---------------------------------------------------------------------------


def test_p2_1a_recover_blob_cleans_up_other_quarantine_copies():
    """If the same hash got quarantined on two different dates (e.g.,
    cleanup ran twice on different days before P2.2 wire-in landed),
    recover_blob should restore from one AND clean up the other so the
    storage state is fully restored."""
    from release_safety.quarantine import recover_blob

    client = MockSupabaseClient()
    bucket = client.storage.from_("pharmaguide")
    blob_hash = _h(0)

    quar_a = _quarantine_path("2026-04-15", blob_hash)
    quar_b = _quarantine_path("2026-05-01", blob_hash)
    bucket.objects[quar_a] = b"data"
    bucket.objects[quar_b] = b"data"

    ok, err = recover_blob(
        client, blob_hash,
        search_dates=["2026-04-15", "2026-05-01"],
    )

    assert ok is True
    assert err is None
    # Active is restored
    active = _active_path(blob_hash)
    assert active in bucket.objects
    # BOTH quarantine copies are gone
    assert quar_a not in bucket.objects
    assert quar_b not in bucket.objects
