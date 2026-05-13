"""Structured audit log for release-safety operations (ADR-0001 P1.5a).

Append-only JSON-lines log with per-event fsync. Each event is one
self-contained JSON object on a single line:

    {"event_type": "gate_passed", "release_id": "abc...", "timestamp": "...", ...}

Design constraints (per P1.5a sign-off):
  - Append-only. Existing log content is never rewritten.
  - fsync after every event so a crash between events does not lose
    completed events.
  - Deterministic event body ordering (``sort_keys=True``) so two
    events with the same payload produce byte-identical lines except
    for the timestamp. P1.5b depends on this for idempotency tests.
  - Stable ``release_id`` per AuditLog instance — every event from one
    invocation carries the same release_id, so concurrent or
    historically-interleaved logs are demultiplexable.

What this module does NOT do
============================
  - It does NOT enforce schema on the caller-supplied fields. The audit
    log is structured-but-flexible; the schema lives in the calling code
    (P1.5b gates orchestrator) and tests there.
  - It does NOT handle multi-writer concurrency. The pipeline release
    lock (P1.1) ensures only one process writes a given log at a time.
  - It does NOT rotate logs. Each release run gets its own file via
    ``make_audit_log()``; rotation is the operator's call.

Public API
==========
    AuditLog(path, *, release_id)              — append events to a file
    make_audit_log(audit_dir=None, *, release_id=None, timestamp=None)
                                               — construct with auto-named file
    read_audit_log(path) -> list[dict]         — parse for forensics/tests
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

# Lives at <dsld_clean_root>/reports/release_audit/. Created lazily.
DEFAULT_AUDIT_DIR = Path(__file__).resolve().parents[2] / "reports" / "release_audit"

# release_id length in hex chars. UUID4 has 32 hex chars; we truncate to 12
# (48 bits of entropy, ~1-in-280-trillion collision chance) for shorter,
# operator-friendly filenames and log lines.
RELEASE_ID_HEX_LEN = 12


# ---------------------------------------------------------------------------
# AuditLog
# ---------------------------------------------------------------------------


class AuditLog:
    """Append-only JSON-lines audit log.

    Each call to ``event()`` opens the file in append mode, writes one
    JSON object on its own line, flushes, fsyncs, then closes. The
    open-per-event pattern trades trivial I/O overhead for guaranteed
    durability without file-handle bookkeeping.

    Every event automatically includes:
      - ``event_type``: caller-supplied string
      - ``release_id``: this AuditLog's release_id
      - ``timestamp``: ISO 8601 UTC at write time

    Caller-supplied keyword arguments are merged into the event payload.
    Keys are serialized with ``sort_keys=True`` so identical payloads
    produce byte-identical lines (modulo the timestamp).
    """

    def __init__(self, path: Path, *, release_id: str):
        self._path = Path(path)
        if not isinstance(release_id, str) or not release_id:
            raise ValueError(
                f"release_id must be a non-empty string, got {release_id!r}"
            )
        self._release_id = release_id

        # Ensure parent directory exists. Lazy creation matches the rest of
        # the release_safety package.
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    @property
    def release_id(self) -> str:
        return self._release_id

    def event(self, event_type: str, **fields: Any) -> None:
        """Append a structured event.

        Args:
            event_type: short identifier for the event (e.g. ``"gate_passed"``).
                Caller-controlled; no enum enforcement at this layer.
            **fields: arbitrary structured payload. Values must be JSON-
                serializable (str, int, float, bool, None, list, dict).

        Raises:
            ValueError: ``event_type`` is empty or not a string.
            TypeError: a field value is not JSON-serializable.
            OSError: the underlying write/flush/fsync fails.
        """
        if not isinstance(event_type, str) or not event_type:
            raise ValueError(
                f"event_type must be a non-empty string, got {event_type!r}"
            )

        # Reserved keys come from this method, not the caller. Catch
        # accidental shadowing early so the audit log isn't ambiguous.
        # NB: ``event_type`` is the positional parameter, so Python itself
        # raises TypeError if a caller passes it via **fields — no need to
        # check here. We only guard the other two reserved keys.
        reserved = {"release_id", "timestamp"}
        clobber = reserved & set(fields)
        if clobber:
            raise ValueError(
                f"Event field names {sorted(clobber)} are reserved by AuditLog"
            )

        payload: Dict[str, Any] = dict(fields)
        payload["event_type"] = event_type
        payload["release_id"] = self._release_id
        payload["timestamp"] = datetime.now(timezone.utc).isoformat()

        line = json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n"

        with open(self._path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_audit_log(
    audit_dir: Optional[Path] = None,
    *,
    release_id: Optional[str] = None,
    timestamp: Optional[datetime] = None,
) -> AuditLog:
    """Construct an AuditLog with an auto-generated filename.

    Filename format: ``{YYYYMMDDTHHMMSSZ}_{release_id}.jsonl``
    (e.g. ``20260512T203456Z_a1b2c3d4e5f6.jsonl``).

    Args:
        audit_dir: directory to create the log in. Defaults to
            ``DEFAULT_AUDIT_DIR`` (``<dsld_clean>/reports/release_audit/``).
        release_id: explicit release_id. Generated from uuid4 (truncated)
            when None.
        timestamp: timestamp used to stamp the filename. Defaults to UTC
            now. Useful for deterministic testing.

    Returns:
        An ``AuditLog`` ready to receive events.
    """
    if audit_dir is None:
        audit_dir = DEFAULT_AUDIT_DIR
    audit_dir = Path(audit_dir)
    audit_dir.mkdir(parents=True, exist_ok=True)

    if release_id is None:
        release_id = uuid.uuid4().hex[:RELEASE_ID_HEX_LEN]

    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    elif timestamp.tzinfo is None:
        # Treat naive datetimes as UTC rather than guessing local time.
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    ts_str = timestamp.strftime("%Y%m%dT%H%M%SZ")
    filename = f"{ts_str}_{release_id}.jsonl"
    return AuditLog(audit_dir / filename, release_id=release_id)


# ---------------------------------------------------------------------------
# Reader (for forensics + tests)
# ---------------------------------------------------------------------------


def read_audit_log(path: Path) -> List[dict]:
    """Parse a JSONL audit log into a list of event dicts.

    Skips blank lines AND malformed lines silently. Append-only logs can
    only have malformed content from a crashed write (typically the very
    last line); this is normal recovery behavior, not data loss reporting.
    A caller that wants to know about partial-write damage should compare
    line counts to event counts before calling.

    Args:
        path: path to the JSONL log file.

    Returns:
        List of parsed event dicts in file order.

    Raises:
        FileNotFoundError: ``path`` does not exist. Catch in callers that
            tolerate missing logs.
    """
    events: List[dict] = []
    with open(path, encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events
