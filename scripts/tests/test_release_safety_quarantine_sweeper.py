"""Tests for scripts/release_safety/quarantine_sweeper.py — TTL-based
hard-delete of expired quarantine (ADR-0001 P2.1b).

Mock-based tests against the same in-memory Supabase client pattern
used in P2.1a. The sweeper deliberately uses ``now`` injection for
deterministic eligibility tests; no real time-based flakiness.
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timezone
from typing import Set
import pytest

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))


# ---------------------------------------------------------------------------
# Mock Supabase storage (same shape as P2.1a tests)
# ---------------------------------------------------------------------------


class MockBucket:
    def __init__(self):
        self.objects: dict = {}
        self.fail_remove: Set[str] = set()

    def remove(self, paths):
        for p in paths:
            if p in self.fail_remove:
                raise RuntimeError(f"injected DELETE failure (path={p})")
            self.objects.pop(p, None)
        return [{"name": p} for p in paths]

    def list(self, path: str, options=None):
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


def _h(idx: int) -> str:
    return f"{idx:064x}"


def _quarantine_path(date_str: str, blob_hash: str) -> str:
    return f"shared/quarantine/{date_str}/{blob_hash[:2]}/{blob_hash}.json"


def _put(bucket: MockBucket, date_str: str, blob_hash: str, content: bytes = b"x"):
    bucket.objects[_quarantine_path(date_str, blob_hash)] = content


# ---------------------------------------------------------------------------
# Test 1 — eligibility: today is not eligible
# ---------------------------------------------------------------------------


def test_p2_1b_today_is_not_eligible():
    from release_safety.quarantine_sweeper import is_eligible_for_hard_delete

    assert is_eligible_for_hard_delete(
        "2026-05-12", ttl_days=30, now=date(2026, 5, 12),
    ) is False


# ---------------------------------------------------------------------------
# Test 2 — exactly 30 days old is NOT eligible (boundary)
# ---------------------------------------------------------------------------


def test_p2_1b_exactly_thirty_days_old_is_not_eligible():
    """Boundary: exactly ttl_days old is still inside the recovery window.
    A blob quarantined 30 days ago at midnight survives until midnight on
    day 31."""
    from release_safety.quarantine_sweeper import is_eligible_for_hard_delete

    now_anchor = date(2026, 5, 12)
    thirty_days_ago = "2026-04-12"

    assert is_eligible_for_hard_delete(
        thirty_days_ago, ttl_days=30, now=now_anchor,
    ) is False


# ---------------------------------------------------------------------------
# Test 3 — 31+ days old IS eligible
# ---------------------------------------------------------------------------


def test_p2_1b_thirty_one_days_old_is_eligible():
    from release_safety.quarantine_sweeper import is_eligible_for_hard_delete

    now_anchor = date(2026, 5, 12)
    thirty_one_days_ago = "2026-04-11"

    assert is_eligible_for_hard_delete(
        thirty_one_days_ago, ttl_days=30, now=now_anchor,
    ) is True


def test_p2_1b_far_past_dates_are_eligible():
    from release_safety.quarantine_sweeper import is_eligible_for_hard_delete

    now_anchor = date(2026, 5, 12)

    assert is_eligible_for_hard_delete(
        "2025-01-01", ttl_days=30, now=now_anchor,
    ) is True


# ---------------------------------------------------------------------------
# Test 4 — future-dated quarantine entries are not eligible (defensive)
# ---------------------------------------------------------------------------


def test_p2_1b_future_dates_are_not_eligible():
    """Should never happen in practice (would require system clock skew
    or hand-edit), but the math should not flip eligible."""
    from release_safety.quarantine_sweeper import is_eligible_for_hard_delete

    now_anchor = date(2026, 5, 12)
    future = "2026-12-31"

    assert is_eligible_for_hard_delete(
        future, ttl_days=30, now=now_anchor,
    ) is False


# ---------------------------------------------------------------------------
# Test 5 — eligibility input validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_input",
    ["2026/05/12", "12-05-2026", "not a date", "", "2026-5-12"],
)
def test_p2_1b_eligibility_rejects_malformed_date_strings(bad_input):
    from release_safety.quarantine_sweeper import is_eligible_for_hard_delete

    with pytest.raises(ValueError, match="ISO YYYY-MM-DD"):
        is_eligible_for_hard_delete(bad_input, ttl_days=30, now=date(2026, 5, 12))


def test_p2_1b_eligibility_rejects_negative_ttl():
    from release_safety.quarantine_sweeper import is_eligible_for_hard_delete

    with pytest.raises(ValueError, match="non-negative"):
        is_eligible_for_hard_delete(
            "2026-05-12", ttl_days=-1, now=date(2026, 5, 12),
        )


# ---------------------------------------------------------------------------
# Test 6 — sweep dry-run by default deletes nothing
# ---------------------------------------------------------------------------


def test_p2_1b_sweep_dry_run_by_default_deletes_nothing():
    from release_safety.quarantine_sweeper import sweep_quarantine

    client = MockSupabaseClient()
    bucket = client.storage.from_("pharmaguide")

    # Old date (eligible) with 3 blobs; fresh date (not eligible) with 2.
    for i in range(3):
        _put(bucket, "2026-04-01", _h(i))           # 41 days old vs 2026-05-12
    for i in range(2):
        _put(bucket, "2026-05-10", _h(100 + i))     # 2 days old

    snapshot = dict(bucket.objects)
    result = sweep_quarantine(client, now=date(2026, 5, 12))   # dry_run defaults True

    assert result.dry_run is True
    assert result.eligible_dates == ["2026-04-01"]
    assert result.candidates_per_date == {"2026-04-01": 3}
    assert result.deleted_per_date == {"2026-04-01": 0}
    assert result.failed_per_date == {"2026-04-01": 0}
    # Storage state UNCHANGED.
    assert bucket.objects == snapshot


# ---------------------------------------------------------------------------
# Test 7 — sweep --execute deletes only eligible dates
# ---------------------------------------------------------------------------


def test_p2_1b_sweep_execute_deletes_only_eligible_dates():
    from release_safety.quarantine_sweeper import sweep_quarantine

    client = MockSupabaseClient()
    bucket = client.storage.from_("pharmaguide")

    # 3 blobs in eligible date, 2 blobs in fresh date.
    for i in range(3):
        _put(bucket, "2026-04-01", _h(i))
    fresh_paths = []
    for i in range(2):
        path = _quarantine_path("2026-05-10", _h(100 + i))
        bucket.objects[path] = b"fresh"
        fresh_paths.append(path)

    result = sweep_quarantine(
        client, dry_run=False, now=date(2026, 5, 12),
    )

    assert result.dry_run is False
    assert result.eligible_dates == ["2026-04-01"]
    assert result.candidates_per_date == {"2026-04-01": 3}
    assert result.deleted_per_date == {"2026-04-01": 3}
    assert result.failed_per_date == {"2026-04-01": 0}
    assert result.total_eligible == 3
    assert result.total_deleted == 3
    assert result.total_failed == 0

    # All 3 eligible blobs gone from storage.
    for i in range(3):
        assert _quarantine_path("2026-04-01", _h(i)) not in bucket.objects
    # All 2 fresh blobs survive.
    for path in fresh_paths:
        assert path in bucket.objects


# ---------------------------------------------------------------------------
# Test 8 — empty quarantine is a no-op
# ---------------------------------------------------------------------------


def test_p2_1b_sweep_empty_quarantine_returns_zero_result():
    from release_safety.quarantine_sweeper import sweep_quarantine

    client = MockSupabaseClient()
    result = sweep_quarantine(client, dry_run=False, now=date(2026, 5, 12))

    assert result.eligible_dates == []
    assert result.candidates_per_date == {}
    assert result.deleted_per_date == {}
    assert result.failed_per_date == {}
    assert result.total_eligible == 0
    assert result.total_deleted == 0
    assert result.total_failed == 0


# ---------------------------------------------------------------------------
# Test 9 — idempotent reruns
# ---------------------------------------------------------------------------


def test_p2_1b_sweep_idempotent_reruns():
    """First sweep deletes eligible blobs; second sweep is a no-op
    (those blobs are gone). Required by HR-9."""
    from release_safety.quarantine_sweeper import sweep_quarantine

    client = MockSupabaseClient()
    bucket = client.storage.from_("pharmaguide")
    for i in range(3):
        _put(bucket, "2026-04-01", _h(i))

    r1 = sweep_quarantine(client, dry_run=False, now=date(2026, 5, 12))
    assert r1.total_deleted == 3
    assert bucket.objects == {}

    r2 = sweep_quarantine(client, dry_run=False, now=date(2026, 5, 12))
    # Re-sweep finds nothing — empty quarantine, no errors.
    assert r2.total_eligible == 0
    assert r2.total_deleted == 0
    assert r2.total_failed == 0


# ---------------------------------------------------------------------------
# Test 10 — non-ISO date directories are ignored defensively
# ---------------------------------------------------------------------------


def test_p2_1b_sweep_ignores_non_iso_directories():
    """Operator-edited or garbage directories under shared/quarantine/
    must not crash the sweep or get treated as a date."""
    from release_safety.quarantine_sweeper import sweep_quarantine

    client = MockSupabaseClient()
    bucket = client.storage.from_("pharmaguide")
    # An eligible real date
    _put(bucket, "2026-04-01", _h(0))
    # A non-ISO directory (would never come from the production code)
    bucket.objects[f"shared/quarantine/garbage_dir_name/00/{_h(99)}.json"] = b"keep"

    result = sweep_quarantine(client, dry_run=False, now=date(2026, 5, 12))

    assert result.eligible_dates == ["2026-04-01"]
    assert result.deleted_per_date == {"2026-04-01": 1}
    # Garbage dir contents UNTOUCHED.
    assert f"shared/quarantine/garbage_dir_name/00/{_h(99)}.json" in bucket.objects


# ---------------------------------------------------------------------------
# Test 11 — partial failure: one delete fails, others still proceed
# ---------------------------------------------------------------------------


def test_p2_1b_sweep_partial_failure_continues_and_reports(monkeypatch):
    """Per P2.1b sign-off: when one blob delete fails, the sweep continues
    across the remaining eligible blobs AND the result reports the failed
    count instead of aborting or silently swallowing the error."""
    from release_safety.quarantine_sweeper import sweep_quarantine

    client = MockSupabaseClient()
    bucket = client.storage.from_("pharmaguide")
    # Five eligible blobs
    for i in range(5):
        _put(bucket, "2026-04-01", _h(i))

    # Inject a failure on the 3rd blob (index 2 by sorted hash order)
    failing_path = _quarantine_path("2026-04-01", _h(2))
    bucket.fail_remove.add(failing_path)

    result = sweep_quarantine(client, dry_run=False, now=date(2026, 5, 12))

    assert result.dry_run is False
    assert result.eligible_dates == ["2026-04-01"]
    assert result.candidates_per_date == {"2026-04-01": 5}

    # 4 deleted, 1 failed — the sweep MUST continue past the failure.
    assert result.deleted_per_date == {"2026-04-01": 4}
    assert result.failed_per_date == {"2026-04-01": 1}
    assert result.total_eligible == 5
    assert result.total_deleted == 4
    assert result.total_failed == 1

    # The failing blob is still in storage; the other 4 are gone.
    assert failing_path in bucket.objects
    for i in range(5):
        if i == 2:
            continue
        assert _quarantine_path("2026-04-01", _h(i)) not in bucket.objects


# ---------------------------------------------------------------------------
# Test 12 — multi-date sweep: only past-TTL ones are swept
# ---------------------------------------------------------------------------


def test_p2_1b_sweep_multiple_dates_only_eligible_swept():
    """Sweep walks every date directory but only processes the eligible
    subset. Date ordering in the result is ascending."""
    from release_safety.quarantine_sweeper import sweep_quarantine

    client = MockSupabaseClient()
    bucket = client.storage.from_("pharmaguide")

    now_anchor = date(2026, 5, 12)

    # Eligible (older than 30 days)
    _put(bucket, "2026-03-01", _h(0))            # 72 days old
    _put(bucket, "2026-04-01", _h(1))            # 41 days old
    _put(bucket, "2026-04-01", _h(2))
    # Boundary — exactly 30 days, NOT eligible
    _put(bucket, "2026-04-12", _h(3))
    # Fresh — not eligible
    _put(bucket, "2026-05-10", _h(4))
    _put(bucket, "2026-05-12", _h(5))

    result = sweep_quarantine(client, dry_run=False, now=now_anchor)

    assert result.eligible_dates == ["2026-03-01", "2026-04-01"]
    assert result.candidates_per_date == {"2026-03-01": 1, "2026-04-01": 2}
    assert result.deleted_per_date == {"2026-03-01": 1, "2026-04-01": 2}
    assert result.failed_per_date == {"2026-03-01": 0, "2026-04-01": 0}

    # Boundary + fresh dates UNTOUCHED
    assert _quarantine_path("2026-04-12", _h(3)) in bucket.objects
    assert _quarantine_path("2026-05-10", _h(4)) in bucket.objects
    assert _quarantine_path("2026-05-12", _h(5)) in bucket.objects


# ---------------------------------------------------------------------------
# Test 13 — SweepResult aggregate properties
# ---------------------------------------------------------------------------


def test_p2_1b_sweep_result_aggregate_properties():
    """total_eligible / total_deleted / total_failed sum across dates."""
    from release_safety.quarantine_sweeper import sweep_quarantine

    client = MockSupabaseClient()
    bucket = client.storage.from_("pharmaguide")
    # 2 dates, each with 2 blobs, all eligible
    _put(bucket, "2026-04-01", _h(0))
    _put(bucket, "2026-04-01", _h(1))
    _put(bucket, "2026-04-02", _h(2))
    _put(bucket, "2026-04-02", _h(3))

    result = sweep_quarantine(client, dry_run=False, now=date(2026, 5, 12))

    assert result.total_eligible == 4
    assert result.total_deleted == 4
    assert result.total_failed == 0
    assert sum(result.candidates_per_date.values()) == result.total_eligible


# ---------------------------------------------------------------------------
# Test 14 — sweep accepts datetime as well as date for ``now``
# ---------------------------------------------------------------------------


def test_p2_1b_sweep_accepts_datetime_for_now():
    from release_safety.quarantine_sweeper import sweep_quarantine

    client = MockSupabaseClient()
    bucket = client.storage.from_("pharmaguide")
    _put(bucket, "2026-04-01", _h(0))

    now_dt = datetime(2026, 5, 12, 14, 30, tzinfo=timezone.utc)
    result = sweep_quarantine(client, dry_run=False, now=now_dt)

    assert result.eligible_dates == ["2026-04-01"]
    assert result.total_deleted == 1
