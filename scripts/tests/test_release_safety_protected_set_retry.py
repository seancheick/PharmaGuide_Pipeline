"""The protected-set computation must survive a transient Supabase blip.

Release ``5f9417015df9`` (2026-08-26) rejected a 118,947-candidate orphan
sweep because ONE HTTP 544 ``DatabaseTimeout`` hit the existence check for
``v2026.08.26.141540`` — a directory containing three objects. See
``reports/release_audit/20260826T150301Z_5f9417015df9.jsonl``::

    "gate_name": "protected_set_computation",
    "reason": "Failed to list bucket='pharmaguide' path='v2026.08.26.141540'
               ... {'statusCode': 544, 'error': DatabaseTimeout}"

Fail-closed is correct and must stay. What was wrong is that a *blip* counted
as proof that the protected set could not be computed. These tests pin both
halves: transient failures are retried; persistent ones still fail closed and
quarantine nothing.
"""

from __future__ import annotations

import os
import sys
import time

import pytest

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))

from test_release_safety_protected_blobs import (  # noqa: E402
    FakeSupabaseClientForP35,
    _detail_index_bytes,
    _p35_bundled_and_dist,
    _P35Table,
    _registry_row,
)


def _storage_error(message="The connection to the database timed out",
                   code="DatabaseTimeout", status=544):
    from storage3.exceptions import StorageApiError

    return StorageApiError(message, code, status)


@pytest.fixture(autouse=True)
def _no_real_backoff_sleeps(monkeypatch):
    """Keep retry backoff instant so the suite stays fast."""
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)


def _flaky_list(bucket, target, failures):
    """Make ``bucket.list(path=...)`` raise ``failures`` times, then succeed."""
    real = bucket.list
    state = {"n": 0}

    def wrapper(path="", options=None):
        if path == target:
            state["n"] += 1
            if state["n"] <= failures:
                raise _storage_error()
        return real(path=path, options=options)

    bucket.list = wrapper
    return state


def _flaky_download(bucket, target, failures):
    real = bucket.download
    state = {"n": 0}

    def wrapper(path):
        if path == target:
            state["n"] += 1
            if state["n"] <= failures:
                raise _storage_error()
        return real(path)

    bucket.download = wrapper
    return state


def _seeded_client(active_version, retained_version, active_hashes, retained_hashes):
    client = FakeSupabaseClientForP35()
    bucket = client.storage.from_("pharmaguide")
    bucket.put(
        f"v{active_version}/detail_index.json",
        _detail_index_bytes(active_hashes, active_version),
    )
    bucket.put(
        f"v{retained_version}/detail_index.json",
        _detail_index_bytes(retained_hashes, retained_version),
    )
    client.seed_registry([
        _registry_row(db_version=active_version, state="ACTIVE"),
        _registry_row(db_version=retained_version, state="RETIRED"),
    ])
    return client, bucket


# ---------------------------------------------------------------------------
# Transient failures must NOT reject the sweep
# ---------------------------------------------------------------------------


def test_index_existence_check_survives_transient_544(tmp_path):
    """The exact 2026-08-26 failure must now succeed on retry."""
    from release_safety.protected_blobs import compute_protected_blob_set

    active, retained = "2026.08.26.141540", "2026.08.25.090053"
    a_hashes = ["aa" * 32, "bb" * 32]
    r_hashes = ["cc" * 32]
    client, bucket = _seeded_client(active, retained, a_hashes, r_hashes)
    state = _flaky_list(bucket, f"v{active}", failures=2)

    flutter_repo, dist_dir = _p35_bundled_and_dist(
        tmp_path, bundled_hashes=a_hashes, dist_hashes=a_hashes,
    )

    result = compute_protected_blob_set(
        flutter_repo, dist_dir,
        supabase_client=client,
        retained_versions=(active, retained),
    )

    # >= 3: the active version's index is fetched twice (once as the ACTIVE
    # registry row, once as a retained version). What matters is that the two
    # injected 544s were retried through rather than rejecting the sweep.
    assert state["n"] >= 3, "expected the 544s to be retried, not fatal"
    assert set(a_hashes) <= result.protected
    assert set(r_hashes) <= result.protected


def test_index_download_survives_transient_544(tmp_path):
    from release_safety.protected_blobs import compute_protected_blob_set

    active, retained = "2026.08.26.141540", "2026.08.25.090053"
    a_hashes = ["aa" * 32]
    r_hashes = ["cc" * 32]
    client, bucket = _seeded_client(active, retained, a_hashes, r_hashes)
    state = _flaky_download(bucket, f"v{retained}/detail_index.json", failures=2)

    flutter_repo, dist_dir = _p35_bundled_and_dist(
        tmp_path, bundled_hashes=a_hashes, dist_hashes=a_hashes,
    )

    result = compute_protected_blob_set(
        flutter_repo, dist_dir,
        supabase_client=client,
        retained_versions=(active, retained),
    )

    assert state["n"] >= 3
    assert set(r_hashes) <= result.protected


def test_registry_row_query_survives_transient_timeout(tmp_path, monkeypatch):
    """``list_releases_by_state`` had no retry either — it is on the same path."""
    from release_safety.protected_blobs import compute_protected_blob_set

    active, retained = "2026.08.26.141540", "2026.08.25.090053"
    a_hashes = ["aa" * 32]
    client, bucket = _seeded_client(active, retained, a_hashes, ["cc" * 32])

    # Patch at the class: the fake's ``select()`` returns a NEW _P35Table, so
    # patching one instance would never be reached.
    real_execute = _P35Table.execute
    calls = {"n": 0}

    def execute(self):
        if self._name == "catalog_releases":
            calls["n"] += 1
            if calls["n"] <= 2:
                raise _storage_error(
                    "canceling statement due to statement timeout",
                    code="57014", status=None,
                )
        return real_execute(self)

    monkeypatch.setattr(_P35Table, "execute", execute)

    flutter_repo, dist_dir = _p35_bundled_and_dist(
        tmp_path, bundled_hashes=a_hashes, dist_hashes=a_hashes,
    )

    result = compute_protected_blob_set(
        flutter_repo, dist_dir,
        supabase_client=client,
        retained_versions=(active,),
    )

    assert calls["n"] > 2, "expected the registry query to be retried"
    assert set(a_hashes) <= result.protected


# ---------------------------------------------------------------------------
# Persistent failures must STILL fail closed
# ---------------------------------------------------------------------------


def test_persistent_544_still_fails_closed(tmp_path):
    """Retry removes the blip failure mode — it must not remove fail-closed."""
    from release_safety.protected_blobs import (
        RegistryFetchError,
        compute_protected_blob_set,
    )

    active, retained = "2026.08.26.141540", "2026.08.25.090053"
    a_hashes = ["aa" * 32]
    client, bucket = _seeded_client(active, retained, a_hashes, ["cc" * 32])
    _flaky_list(bucket, f"v{active}", failures=10_000)

    flutter_repo, dist_dir = _p35_bundled_and_dist(
        tmp_path, bundled_hashes=a_hashes, dist_hashes=a_hashes,
    )

    with pytest.raises(RegistryFetchError):
        compute_protected_blob_set(
            flutter_repo, dist_dir,
            supabase_client=client,
            retained_versions=(active, retained),
        )


def test_permanent_missing_index_is_not_retried(tmp_path):
    """A genuinely absent index is a stable answer — retrying it wastes budget
    and must not soften the hard failure."""
    from release_safety.protected_blobs import (
        RegistryDetailIndexMissingError,
        compute_protected_blob_set,
    )

    active = "2026.08.26.141540"
    a_hashes = ["aa" * 32]
    client = FakeSupabaseClientForP35()
    bucket = client.storage.from_("pharmaguide")
    # Registry row promises an index that was never uploaded.
    client.seed_registry([_registry_row(db_version=active, state="ACTIVE")])

    listed = []
    real = bucket.list

    def counting(path="", options=None):
        listed.append(path)
        return real(path=path, options=options)

    bucket.list = counting

    flutter_repo, dist_dir = _p35_bundled_and_dist(
        tmp_path, bundled_hashes=a_hashes, dist_hashes=a_hashes,
    )

    with pytest.raises(RegistryDetailIndexMissingError):
        compute_protected_blob_set(
            flutter_repo, dist_dir, supabase_client=client,
        )

    assert listed.count(f"v{active}") == 1, (
        "a missing object must be answered once, not retried"
    )
