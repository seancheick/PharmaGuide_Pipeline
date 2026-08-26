"""Shared transient-failure classifier + retry helper for release-safety I/O.

Why this exists
---------------
Release ``5f9417015df9`` (2026-08-26) fail-closed the orphan cleanup because a
single HTTP 544 ``DatabaseTimeout`` hit the *existence check* for
``v2026.08.26.141540/detail_index.json`` — a directory holding three objects.
The call was neither large nor slow; Supabase was momentarily unavailable and
the call site had no retry. One blip rejected the entire sweep.

Classification is by **cause, not exception type**. supabase-py funnels a
544 timeout, a 404 miss, and a 403 permission error through the same
``StorageApiError`` class, so `except StorageApiError` cannot tell a retryable
blip from a stable answer. We read the status/code carried *inside* the error.

Fail-closed default: an error we cannot positively classify as transient is
treated as permanent and re-raised immediately. Retrying an unknown error can
turn a hard failure into a slow hard failure, and — worse — can mask a real
"this object is gone" answer that the protected-set computation depends on.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Optional, TypeVar

T = TypeVar("T")

#: HTTP statuses that mean "ask again shortly".
#: 544 is Supabase storage-api's ``DatabaseTimeout``.
TRANSIENT_HTTP_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504, 522, 524, 544})

#: Postgres SQLSTATEs surfaced by PostgREST that are retryable.
#: 57014 = query_canceled (statement timeout), 40001 = serialization_failure,
#: 40P01 = deadlock_detected, 53300 = too_many_connections,
#: 08006/08003 = connection failure.
TRANSIENT_PG_CODES = frozenset(
    {"57014", "40001", "40P01", "53300", "53400", "08006", "08003", "08000"}
)

#: Substrings that identify a transient condition when no status code is
#: available. Matched case-insensitively against the error's own text only.
_TRANSIENT_TEXT = (
    "databasetimeout",
    "timed out",
    "timeout",
    "temporarily unavailable",
    "service unavailable",
    "connection reset",
    "connection refused",
    "connection error",
    "server disconnected",
    "too many requests",
)

_STATUS_DIGITS = re.compile(r"^\s*(\d{3})\s*$")


def _status_of(exc: BaseException) -> Optional[int]:
    """Best-effort HTTP status extraction from a Supabase/httpx error."""
    for attr in ("status", "status_code"):
        raw = getattr(exc, attr, None)
        if isinstance(raw, bool):
            continue
        if isinstance(raw, int):
            return raw
        if isinstance(raw, str):
            match = _STATUS_DIGITS.match(raw)
            if match:
                return int(match.group(1))
    response = getattr(exc, "response", None)
    if response is not None:
        raw = getattr(response, "status_code", None)
        if isinstance(raw, int) and not isinstance(raw, bool):
            return raw
    return None


def is_transient_error(exc: BaseException) -> bool:
    """Return True when ``exc`` is worth retrying.

    Ordering matters: an explicit status/code always wins over text matching,
    so a 404 whose message happens to contain the word "timeout" is still
    treated as permanent.
    """
    # 1. Wall-clock / transport failures are transient by construction.
    if isinstance(exc, TimeoutError):
        return True
    try:  # httpx is a hard dependency of supabase-py, but stay importable.
        import httpx

        if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
            return True
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in TRANSIENT_HTTP_STATUSES
    except ImportError:  # pragma: no cover - httpx always present in practice
        pass

    # 2. Explicit HTTP status (storage3 StorageApiError, httpx responses).
    status = _status_of(exc)
    if status is not None:
        return status in TRANSIENT_HTTP_STATUSES

    # 3. PostgREST SQLSTATE / error code.
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code:
        if code in TRANSIENT_PG_CODES:
            return True
        # A non-numeric PostgREST code (PGRST106, ...) is a stable client
        # error. Numeric SQLSTATEs not in the allowlist are stable too.
        return False

    # 4. Last resort: the error's own text.
    text = str(exc).lower()
    return any(token in text for token in _TRANSIENT_TEXT)


def retry_transient(
    fn: Callable[[], T],
    *,
    max_attempts: int = 5,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
    sleep: Optional[Callable[[float], Any]] = None,
    on_retry: Optional[Callable[[int, BaseException], Any]] = None,
) -> T:
    """Call ``fn`` with exponential backoff on transient failures.

    Args:
        fn: zero-argument callable to invoke.
        max_attempts: total attempts, including the first.
        base_delay / max_delay: exponential backoff bounds in seconds.
        sleep: injected for tests; defaults to ``time.sleep``.
        on_retry: called as ``(attempt_number, exception)`` before each retry.
            Used to feed retry counts into the dry-run report.

    Returns:
        Whatever ``fn`` returns.

    Raises:
        The original exception — permanent errors immediately, transient ones
        after ``max_attempts`` have been used. The caller still fails closed;
        retrying only removes the *blip* failure mode.
    """
    if max_attempts < 1:
        raise ValueError(f"max_attempts must be >= 1, got {max_attempts}")
    if sleep is None:
        import time as _time

        sleep = _time.sleep

    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — classified below.
            if attempt >= max_attempts or not is_transient_error(exc):
                raise
            if on_retry is not None:
                on_retry(attempt, exc)
            sleep(min(base_delay * (2 ** (attempt - 1)), max_delay))
    raise AssertionError("unreachable")  # pragma: no cover
