"""Regression tests for the shared transient-error classifier + retry helper.

Context (2026-08-26 release ``5f9417015df9``): a single HTTP 544
``DatabaseTimeout`` on a *three-object* listing of ``v2026.08.26.141540``
aborted the whole protected-set computation, which fail-closed the orphan
cleanup. The listing was not slow and not large — it was transiently
unavailable, and the call site had no retry at all.

These tests pin the classification rule (by *cause*, not exception type —
supabase-py funnels 544, 404 and permission errors through the same
``StorageApiError``) and the retry contract.
"""

from __future__ import annotations

import os
import sys

import pytest

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))


def _storage_error(message: str, code: str, status):
    from storage3.exceptions import StorageApiError

    return StorageApiError(message, code, status)


# ---------------------------------------------------------------------------
# Classification — by cause, not by exception type
# ---------------------------------------------------------------------------


def test_supabase_544_database_timeout_is_transient():
    """The exact error that aborted release 5f9417015df9."""
    from release_safety.transient import is_transient_error

    exc = _storage_error(
        "The connection to the database timed out", "DatabaseTimeout", 544
    )
    assert is_transient_error(exc) is True


def test_storage_404_not_found_is_permanent():
    """A missing object must never be retried — it is a real, stable answer."""
    from release_safety.transient import is_transient_error

    exc = _storage_error("Object not found", "NoSuchKey", 404)
    assert is_transient_error(exc) is False


def test_storage_403_permission_denied_is_permanent():
    from release_safety.transient import is_transient_error

    exc = _storage_error("new row violates row-level security", "Unauthorized", 403)
    assert is_transient_error(exc) is False


def test_storage_500_and_503_are_transient():
    from release_safety.transient import is_transient_error

    assert is_transient_error(_storage_error("boom", "InternalError", 500)) is True
    assert is_transient_error(_storage_error("busy", "ServiceUnavailable", 503)) is True


def test_string_status_codes_are_classified_by_value():
    """storage3 types ``status`` as ``Union[int, str]`` — both must classify."""
    from release_safety.transient import is_transient_error

    assert is_transient_error(_storage_error("t", "DatabaseTimeout", "544")) is True
    assert is_transient_error(_storage_error("nf", "NoSuchKey", "404")) is False


def test_httpx_timeouts_and_connection_errors_are_transient():
    import httpx

    from release_safety.transient import is_transient_error

    assert is_transient_error(httpx.ReadTimeout("read timed out")) is True
    assert is_transient_error(httpx.ConnectError("connection refused")) is True
    assert is_transient_error(TimeoutError("wall-clock budget exceeded")) is True


def test_postgrest_statement_timeout_is_transient_but_schema_error_is_not():
    from postgrest.exceptions import APIError

    from release_safety.transient import is_transient_error

    timeout = APIError({"message": "canceling statement due to statement timeout",
                        "code": "57014"})
    schema = APIError({"message": "Invalid schema: storage", "code": "PGRST106"})

    assert is_transient_error(timeout) is True
    assert is_transient_error(schema) is False


def test_unknown_errors_are_permanent_by_default():
    """Fail closed: an error we cannot classify must not be retried blindly."""
    from release_safety.transient import is_transient_error

    assert is_transient_error(ValueError("malformed detail_index")) is False


# ---------------------------------------------------------------------------
# Retry contract
# ---------------------------------------------------------------------------


def test_retry_transient_succeeds_after_transient_failures():
    from release_safety.transient import retry_transient

    attempts = []

    def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise _storage_error("timed out", "DatabaseTimeout", 544)
        return "ok"

    slept = []
    result = retry_transient(flaky, max_attempts=5, sleep=slept.append)

    assert result == "ok"
    assert len(attempts) == 3
    assert len(slept) == 2, "must back off between attempts, not spin"
    assert slept[1] > slept[0], "backoff must grow"


def test_retry_transient_reraises_original_error_after_exhausting_attempts():
    from release_safety.transient import retry_transient

    attempts = []

    def always_timeout():
        attempts.append(1)
        raise _storage_error("timed out", "DatabaseTimeout", 544)

    with pytest.raises(Exception) as excinfo:
        retry_transient(always_timeout, max_attempts=4, sleep=lambda _s: None)

    assert "DatabaseTimeout" in str(excinfo.value)
    assert len(attempts) == 4, "must attempt exactly max_attempts times"


def test_retry_transient_does_not_retry_permanent_errors():
    """A 404 answered once is answered forever — retrying wastes the budget."""
    from release_safety.transient import retry_transient

    attempts = []

    def not_found():
        attempts.append(1)
        raise _storage_error("Object not found", "NoSuchKey", 404)

    with pytest.raises(Exception):
        retry_transient(not_found, max_attempts=5, sleep=lambda _s: None)

    assert len(attempts) == 1


def test_retry_transient_reports_each_retry_to_the_observer():
    """Retry counts feed the dry-run report's failures/retries line."""
    from release_safety.transient import retry_transient

    seen = []
    attempts = []

    def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise _storage_error("timed out", "DatabaseTimeout", 544)
        return "ok"

    retry_transient(
        flaky,
        max_attempts=5,
        sleep=lambda _s: None,
        on_retry=lambda attempt, exc: seen.append(attempt),
    )

    assert seen == [1, 2]


def test_retry_transient_caps_the_backoff_delay():
    from release_safety.transient import retry_transient

    slept = []

    def always_timeout():
        raise _storage_error("timed out", "DatabaseTimeout", 544)

    with pytest.raises(Exception):
        retry_transient(
            always_timeout,
            max_attempts=8,
            base_delay=1.0,
            max_delay=4.0,
            sleep=slept.append,
        )

    assert slept, "expected backoff sleeps"
    assert max(slept) <= 4.0
