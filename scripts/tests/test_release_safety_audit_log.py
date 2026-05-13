"""Tests for scripts/release_safety/audit_log.py — append-only JSONL
audit log (ADR-0001 P1.5a).

All tests are pure unit tests against tmp_path. No Supabase, no network.
fsync behavior is verified by monkeypatching ``os.fsync`` in the
audit_log module — durability semantics matter for the safety primitive
and shouldn't quietly regress.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
import pytest

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))


# ---------------------------------------------------------------------------
# Test 1 — happy path: write events, read back, fields preserved
# ---------------------------------------------------------------------------


def test_p1_5a_happy_path_write_and_read(tmp_path):
    """Write three events, read them back, verify each event has the
    required fields plus the caller-supplied payload."""
    from release_safety.audit_log import AuditLog, read_audit_log

    log_path = tmp_path / "audit.jsonl"
    log = AuditLog(log_path, release_id="rel_test_001")

    log.event("gate_started", gate_name="bundle_alignment")
    log.event("gate_passed", gate_name="bundle_alignment", duration_ms=42)
    log.event("gate_failed", gate_name="blast_radius",
              would_delete=523, threshold_pct=5.0)

    events = read_audit_log(log_path)

    assert len(events) == 3

    # Required fields on every event
    for ev in events:
        assert ev["release_id"] == "rel_test_001"
        assert "timestamp" in ev
        # Timestamps must be ISO 8601 UTC and parseable
        datetime.fromisoformat(ev["timestamp"])

    # Payload preserved
    assert events[0]["event_type"] == "gate_started"
    assert events[0]["gate_name"] == "bundle_alignment"
    assert events[1]["event_type"] == "gate_passed"
    assert events[1]["duration_ms"] == 42
    assert events[2]["event_type"] == "gate_failed"
    assert events[2]["would_delete"] == 523
    assert events[2]["threshold_pct"] == 5.0


# ---------------------------------------------------------------------------
# Test 2 — release_id consistency within an instance
# ---------------------------------------------------------------------------


def test_p1_5a_release_id_consistent_within_instance(tmp_path):
    """All events from one AuditLog instance MUST carry the same
    release_id, regardless of how many events are written."""
    from release_safety.audit_log import AuditLog, read_audit_log

    log = AuditLog(tmp_path / "audit.jsonl", release_id="stable_id")
    for i in range(10):
        log.event("tick", index=i)

    events = read_audit_log(tmp_path / "audit.jsonl")
    assert len(events) == 10
    assert {e["release_id"] for e in events} == {"stable_id"}


# ---------------------------------------------------------------------------
# Test 3 — release_ids unique across make_audit_log() calls
# ---------------------------------------------------------------------------


def test_p1_5a_make_audit_log_generates_unique_release_ids(tmp_path):
    """Two consecutive ``make_audit_log()`` calls must produce different
    release_ids. Used to demultiplex concurrent or interleaved log files."""
    from release_safety.audit_log import make_audit_log

    log_a = make_audit_log(tmp_path / "audit_dir_a")
    log_b = make_audit_log(tmp_path / "audit_dir_b")

    assert log_a.release_id != log_b.release_id
    # And both look like hex of the expected length
    assert len(log_a.release_id) == 12
    assert all(c in "0123456789abcdef" for c in log_a.release_id)


# ---------------------------------------------------------------------------
# Test 4 — fsync called per event (durability invariant)
# ---------------------------------------------------------------------------


def test_p1_5a_fsync_called_per_event(tmp_path, monkeypatch):
    """Every event write MUST call os.fsync — without it, a process
    crash between events can lose acknowledged events. This is the
    durability invariant for the safety primitive."""
    from release_safety import audit_log

    fsync_calls = []
    real_fsync = audit_log.os.fsync

    def counted_fsync(fd):
        fsync_calls.append(fd)
        return real_fsync(fd)

    monkeypatch.setattr(audit_log.os, "fsync", counted_fsync)

    log = audit_log.AuditLog(tmp_path / "audit.jsonl", release_id="fsync_test")
    log.event("first")
    log.event("second")
    log.event("third", payload="data")

    # One fsync per event, no skips, no double-counts.
    assert len(fsync_calls) == 3


# ---------------------------------------------------------------------------
# Test 5 — deterministic field ordering (sort_keys=True invariant)
# ---------------------------------------------------------------------------


def test_p1_5a_event_payload_is_deterministically_ordered(tmp_path):
    """The same caller-supplied payload, supplied in different keyword
    orders, must produce byte-identical JSON for the payload portion
    (timestamp differs naturally between events; we strip it for
    comparison). P1.5b idempotency tests rely on this."""
    from release_safety.audit_log import AuditLog

    log = AuditLog(tmp_path / "audit.jsonl", release_id="determ")

    # Two events with identical event_type and identical payload but
    # the kwargs supplied in different orders.
    log.event("test_event", zebra=1, apple=2, mango=3)
    log.event("test_event", mango=3, apple=2, zebra=1)

    raw_lines = (tmp_path / "audit.jsonl").read_text().splitlines()
    assert len(raw_lines) == 2

    def strip_timestamp(line: str) -> str:
        d = json.loads(line)
        d.pop("timestamp", None)
        return json.dumps(d, sort_keys=True)

    # Both events must produce the same byte content sans timestamp.
    assert strip_timestamp(raw_lines[0]) == strip_timestamp(raw_lines[1])

    # And the keys must appear in alphabetical order in the raw line
    # (sort_keys=True). Spot-check on the first line.
    parsed_first = json.loads(raw_lines[0])
    rendered_first = json.dumps(parsed_first, sort_keys=True)
    # The substring "apple" must come before "mango" in the raw line.
    assert raw_lines[0].index('"apple"') < raw_lines[0].index('"mango"')
    assert raw_lines[0].index('"mango"') < raw_lines[0].index('"zebra"')


# ---------------------------------------------------------------------------
# Test 6 — append across instances
# ---------------------------------------------------------------------------


def test_p1_5a_append_across_instances_does_not_overwrite(tmp_path):
    """Two AuditLog instances pointing at the same path append; the
    second does not truncate or rewrite the first's events. Useful for
    re-attaching to an in-progress audit log after a restart."""
    from release_safety.audit_log import AuditLog, read_audit_log

    log_path = tmp_path / "audit.jsonl"

    inst1 = AuditLog(log_path, release_id="rel_first")
    inst1.event("first_session_a")
    inst1.event("first_session_b")

    inst2 = AuditLog(log_path, release_id="rel_second")
    inst2.event("second_session_only")

    events = read_audit_log(log_path)
    assert len(events) == 3
    assert [e["event_type"] for e in events] == [
        "first_session_a", "first_session_b", "second_session_only",
    ]
    # Each event carries the release_id of the writing instance.
    assert events[0]["release_id"] == "rel_first"
    assert events[1]["release_id"] == "rel_first"
    assert events[2]["release_id"] == "rel_second"


# ---------------------------------------------------------------------------
# Test 7 — partial-write recovery (truncated / garbage trailing line)
# ---------------------------------------------------------------------------


def test_p1_5a_read_recovers_from_truncated_or_garbage_trailing_line(tmp_path):
    """``read_audit_log`` skips malformed lines (typically the truncated
    final line from a crashed write) and returns the parseable events.
    A crash between flush+fsync cycles must not poison subsequent reads."""
    from release_safety.audit_log import AuditLog, read_audit_log

    log_path = tmp_path / "audit.jsonl"

    log = AuditLog(log_path, release_id="recovery_test")
    log.event("event_a")
    log.event("event_b")
    log.event("event_c")

    # Append a malformed trailing line (simulates a crash mid-write
    # AFTER a successful fsync of earlier events).
    with open(log_path, "a") as f:
        f.write('{"event_type": "truncated_eve')   # NB: no newline, invalid JSON

    events = read_audit_log(log_path)

    # The three good events must still be readable; the malformed
    # trailing line is silently skipped.
    assert len(events) == 3
    assert [e["event_type"] for e in events] == ["event_a", "event_b", "event_c"]


# ---------------------------------------------------------------------------
# Test 8 — make_audit_log auto-generated filename format
# ---------------------------------------------------------------------------


def test_p1_5a_make_audit_log_filename_format(tmp_path):
    """``make_audit_log()`` produces a file named
    ``{YYYYMMDDTHHMMSSZ}_{release_id}.jsonl`` so logs sort lexically by
    time and are demultiplexable by release_id."""
    from release_safety.audit_log import make_audit_log

    fixed_ts = datetime(2026, 5, 12, 20, 34, 56, tzinfo=timezone.utc)
    log = make_audit_log(
        audit_dir=tmp_path,
        release_id="rel_abc12def345",
        timestamp=fixed_ts,
    )

    assert log.path.parent == tmp_path
    assert log.path.name == "20260512T203456Z_rel_abc12def345.jsonl"

    # Writing produces the file at the expected path.
    log.event("created")
    assert log.path.exists()


# ---------------------------------------------------------------------------
# Test 9 — event with nested dict/list serializes
# ---------------------------------------------------------------------------


def test_p1_5a_event_with_nested_structures(tmp_path):
    """Nested dicts and lists in the payload are serialized as JSON
    (not stringified). Critical for P1.5b which logs structured fields
    like protected_set summaries."""
    from release_safety.audit_log import AuditLog, read_audit_log

    log = AuditLog(tmp_path / "audit.jsonl", release_id="nested_test")
    log.event(
        "protected_set_computed",
        bundled=dict(version="v1", count=8331),
        sample_hashes=["a" * 64, "b" * 64],
        metrics={"union": 8400, "intersection": 8000},
    )

    events = read_audit_log(tmp_path / "audit.jsonl")
    assert len(events) == 1
    ev = events[0]
    assert ev["bundled"] == {"version": "v1", "count": 8331}
    assert ev["sample_hashes"] == ["a" * 64, "b" * 64]
    assert ev["metrics"] == {"union": 8400, "intersection": 8000}


# ---------------------------------------------------------------------------
# Test 10 — event with no extra fields works
# ---------------------------------------------------------------------------


def test_p1_5a_event_with_no_extra_fields(tmp_path):
    """An event with only ``event_type`` (no kwargs) writes the three
    required fields and nothing else. Common for marker events like
    ``"started"`` or ``"complete"``."""
    from release_safety.audit_log import AuditLog, read_audit_log

    log = AuditLog(tmp_path / "audit.jsonl", release_id="bare_test")
    log.event("started")

    events = read_audit_log(tmp_path / "audit.jsonl")
    assert len(events) == 1
    ev = events[0]
    assert set(ev.keys()) == {"event_type", "release_id", "timestamp"}
    assert ev["event_type"] == "started"


# ---------------------------------------------------------------------------
# Test 11 — reserved field collision raises (defensive)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("reserved_field", ["release_id", "timestamp"])
def test_p1_5a_reserved_field_collision_raises(tmp_path, reserved_field):
    """Caller cannot shadow the audit log's own structural fields. Early
    failure prevents ambiguity in audit log forensics (e.g., two
    ``release_id`` keys with different values).

    NB: ``event_type`` is not parametrized because it is a positional
    parameter — Python itself raises TypeError on collision before the
    function body runs. The module's reserved-key guard covers
    ``release_id`` and ``timestamp`` only.
    """
    from release_safety.audit_log import AuditLog

    log = AuditLog(tmp_path / "audit.jsonl", release_id="reserved_test")

    with pytest.raises(ValueError, match="reserved"):
        log.event("collide", **{reserved_field: "should_not_be_overridable"})

    # No event was written.
    assert not (tmp_path / "audit.jsonl").exists() or \
           (tmp_path / "audit.jsonl").read_text() == ""


def test_p1_5a_event_type_collision_blocked_by_python_at_call_site(tmp_path):
    """Documenting Python's own guarantee: passing ``event_type`` as a
    keyword argument when it is already the positional parameter raises
    TypeError at the call site. The audit log relies on this behavior
    rather than re-checking it; this test pins the assumption."""
    from release_safety.audit_log import AuditLog

    log = AuditLog(tmp_path / "audit.jsonl", release_id="positional_test")

    with pytest.raises(TypeError, match="event_type"):
        log.event("collide", event_type="should_not_be_overridable")


# ---------------------------------------------------------------------------
# Test 12 — event_type validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_type,scenario",
    [
        ("",     "empty_string"),
        (None,   "none"),
        (123,    "int"),
        ([],     "list"),
        ({},     "dict"),
    ],
)
def test_p1_5a_event_type_validation_rejects_non_string(tmp_path, bad_type, scenario):
    """``event_type`` must be a non-empty string. Anything else raises
    ValueError before any I/O happens."""
    from release_safety.audit_log import AuditLog

    log = AuditLog(tmp_path / "audit.jsonl", release_id="type_test")

    with pytest.raises(ValueError):
        log.event(bad_type)

    # No event written.
    assert not (tmp_path / "audit.jsonl").exists() or \
           (tmp_path / "audit.jsonl").read_text() == ""
