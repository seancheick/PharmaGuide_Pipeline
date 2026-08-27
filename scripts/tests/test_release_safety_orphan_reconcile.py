"""Orphan reconciliation: a reviewable dry-run report, and nothing else.

Requirements pinned here:

  * every blob referenced by EVERY retained catalog version is protected —
    not merely the current one (the legacy dry-run path protected only the
    single current detail_index, so its "would delete" count was fiction);
  * the report carries exact counts an operator can approve against;
  * a dry run mutates nothing;
  * an inventory that could not read every shard proposes ZERO quarantine.
"""

from __future__ import annotations

import os
import re
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
    _registry_row,
)

PREFIX = "shared/details/sha256"
ACTIVE = "2026.08.26.141540"
RETAINED = "2026.08.25.090053"


@pytest.fixture(autouse=True)
def _no_real_backoff_sleeps(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _s: None)


def _h(tag: str) -> str:
    """A deterministic 64-hex blob hash seeded by a 2-char tag."""
    return (tag * 32)[:64]


def _seed(client, hashes, *, size=100):
    bucket = client.storage.from_("pharmaguide")
    for h in hashes:
        bucket.put(f"{PREFIX}/{h[:2]}/{h}.json", b"x" * size)


def _make_world(tmp_path, *, active_hashes, retained_hashes, extra_storage=()):
    """Storage holds active ∪ retained ∪ extra; registry has both versions."""
    client = FakeSupabaseClientForP35()
    bucket = client.storage.from_("pharmaguide")
    bucket.put(
        f"v{ACTIVE}/detail_index.json", _detail_index_bytes(list(active_hashes), ACTIVE),
    )
    bucket.put(
        f"v{RETAINED}/detail_index.json",
        _detail_index_bytes(list(retained_hashes), RETAINED),
    )
    client.seed_registry([
        _registry_row(db_version=ACTIVE, state="ACTIVE"),
        _registry_row(db_version=RETAINED, state="RETIRED"),
    ])
    _seed(client, set(active_hashes) | set(retained_hashes) | set(extra_storage))
    flutter_repo, dist_dir = _p35_bundled_and_dist(
        tmp_path, bundled_hashes=list(active_hashes), dist_hashes=list(active_hashes),
    )
    return client, flutter_repo, dist_dir


def _shards_for(*hash_groups):
    seen = set()
    for group in hash_groups:
        for h in group:
            seen.add(h[:2])
    return tuple(sorted(seen))


# ---------------------------------------------------------------------------
# Protected-set correctness
# ---------------------------------------------------------------------------


def test_blobs_referenced_only_by_the_older_retained_version_are_protected(tmp_path):
    """The 2026-08-25 catalog is still installed on users' phones. Its blobs
    are not orphans just because the 2026-08-26 index dropped them."""
    from release_safety.orphan_reconcile import build_orphan_report

    active = [_h("aa"), _h("bb")]
    retained_only = [_h("cc")]
    orphan = [_h("dd")]
    client, flutter_repo, dist_dir = _make_world(
        tmp_path, active_hashes=active, retained_hashes=retained_only,
        extra_storage=orphan,
    )

    report = build_orphan_report(
        client, flutter_repo_path=flutter_repo, dist_dir=dist_dir,
        retained_versions=(ACTIVE, RETAINED),
        shards=_shards_for(active, retained_only, orphan),
    )

    assert set(report.orphan_hashes) == set(orphan)
    assert _h("cc") not in report.orphan_hashes


def test_report_counts_protected_blobs_per_retained_version(tmp_path):
    from release_safety.orphan_reconcile import build_orphan_report

    active = [_h("aa"), _h("bb")]
    retained_only = [_h("cc")]
    client, flutter_repo, dist_dir = _make_world(
        tmp_path, active_hashes=active, retained_hashes=retained_only,
    )

    report = build_orphan_report(
        client, flutter_repo_path=flutter_repo, dist_dir=dist_dir,
        retained_versions=(ACTIVE, RETAINED),
        shards=_shards_for(active, retained_only),
    )

    assert report.protected_by_version[ACTIVE] == 2
    assert report.protected_by_version[RETAINED] == 1


# ---------------------------------------------------------------------------
# Report contents
# ---------------------------------------------------------------------------


def test_report_computes_exact_orphan_count_and_bytes(tmp_path):
    from release_safety.orphan_reconcile import build_orphan_report

    active = [_h("aa")]
    orphans = [_h("dd"), _h("ee")]
    client, flutter_repo, dist_dir = _make_world(
        tmp_path, active_hashes=active, retained_hashes=active,
        extra_storage=orphans,
    )

    report = build_orphan_report(
        client, flutter_repo_path=flutter_repo, dist_dir=dist_dir,
        retained_versions=(ACTIVE, RETAINED),
        shards=_shards_for(active, orphans),
    )

    assert report.orphan_count == 2
    assert report.orphan_bytes == 200  # two 100-byte blobs
    assert report.proposed_quarantine == 2
    assert report.total_objects_examined == 3


def test_text_report_carries_every_operator_approval_field(tmp_path):
    from release_safety.orphan_reconcile import build_orphan_report

    active = [_h("aa")]
    orphans = [_h("dd")]
    client, flutter_repo, dist_dir = _make_world(
        tmp_path, active_hashes=active, retained_hashes=active,
        extra_storage=orphans,
    )

    report = build_orphan_report(
        client, flutter_repo_path=flutter_repo, dist_dir=dist_dir,
        retained_versions=(ACTIVE, RETAINED),
        shards=_shards_for(active, orphans),
    )
    text = report.text_report()

    for needle in (
        "Total objects examined",
        "Protected blobs by retained version",
        ACTIVE,
        RETAINED,
        "Orphan blobs",
        "Estimated bytes",
        "Object categories",
        "Proposed quarantine",
        "Listing failures",
        "Retries",
        "Elapsed",
    ):
        assert needle in text, f"report is missing {needle!r}"


def test_report_exposes_category_breakdown_and_retry_counts(tmp_path):
    from release_safety.orphan_reconcile import build_orphan_report

    active = [_h("aa")]
    client, flutter_repo, dist_dir = _make_world(
        tmp_path, active_hashes=active, retained_hashes=active,
    )
    client.storage.from_("pharmaguide").put(f"{PREFIX}/aa/NOTES.txt", b"junk")

    report = build_orphan_report(
        client, flutter_repo_path=flutter_repo, dist_dir=dist_dir,
        retained_versions=(ACTIVE, RETAINED), shards=("aa",),
    )

    assert report.inventory.categories["unrecognized"] == 1
    assert report.inventory.retries == 0
    # A non-blob object is not a candidate for blob quarantine.
    assert report.orphan_count == 0


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------


def test_dry_run_report_mutates_nothing(tmp_path):
    from release_safety.orphan_reconcile import build_orphan_report

    active = [_h("aa")]
    orphans = [_h("dd")]
    client, flutter_repo, dist_dir = _make_world(
        tmp_path, active_hashes=active, retained_hashes=active,
        extra_storage=orphans,
    )
    bucket = client.storage.from_("pharmaguide")
    before = dict(bucket.objects)

    forbidden = []
    for op in ("remove", "move", "copy", "upload"):
        setattr(bucket, op, lambda *a, _op=op, **k: forbidden.append(_op))

    build_orphan_report(
        client, flutter_repo_path=flutter_repo, dist_dir=dist_dir,
        retained_versions=(ACTIVE, RETAINED),
        shards=_shards_for(active, orphans),
    )

    assert forbidden == [], f"dry run attempted mutations: {forbidden}"
    assert bucket.objects == before


def test_incomplete_inventory_proposes_zero_quarantine(tmp_path):
    """Fail closed: if we could not read every shard, we cannot prove what is
    an orphan, so nothing may be proposed."""
    from release_safety.orphan_reconcile import build_orphan_report

    active = [_h("aa")]
    orphans = [_h("dd")]
    client, flutter_repo, dist_dir = _make_world(
        tmp_path, active_hashes=active, retained_hashes=active,
        extra_storage=orphans,
    )

    bucket = client.storage.from_("pharmaguide")
    real_list = bucket.list

    def flaky(path="", options=None):
        if path == f"{PREFIX}/dd":
            raise RuntimeError("The connection to the database timed out")
        return real_list(path=path, options=options)

    bucket.list = flaky

    report = build_orphan_report(
        client, flutter_repo_path=flutter_repo, dist_dir=dist_dir,
        retained_versions=(ACTIVE, RETAINED),
        shards=_shards_for(active, orphans),
        max_attempts=2,
    )

    assert report.inventory.complete is False
    assert report.proposed_quarantine == 0
    assert report.blocked_reason is not None
    text = report.text_report()
    assert re.search(r"Proposed quarantine:\s+0\b", text), text
    assert "BLOCKED" in text


def test_protected_set_failure_proposes_zero_quarantine(tmp_path):
    """A protected set we cannot prove means nothing is provably an orphan."""
    from release_safety.orphan_reconcile import build_orphan_report

    active = [_h("aa")]
    orphans = [_h("dd")]
    client, flutter_repo, dist_dir = _make_world(
        tmp_path, active_hashes=active, retained_hashes=active,
        extra_storage=orphans,
    )

    bucket = client.storage.from_("pharmaguide")
    real_download = bucket.download

    def broken(path):
        if path.endswith("detail_index.json"):
            raise RuntimeError("The connection to the database timed out")
        return real_download(path)

    bucket.download = broken

    report = build_orphan_report(
        client, flutter_repo_path=flutter_repo, dist_dir=dist_dir,
        retained_versions=(ACTIVE, RETAINED),
        shards=_shards_for(active, orphans),
        max_attempts=2,
    )

    assert report.proposed_quarantine == 0
    assert report.blocked_reason is not None
    assert report.orphan_count == 0


def test_orphan_hashes_are_sorted_for_reproducible_review(tmp_path):
    from release_safety.orphan_reconcile import build_orphan_report

    active = [_h("aa")]
    orphans = [_h("ff"), _h("dd"), _h("ee")]
    client, flutter_repo, dist_dir = _make_world(
        tmp_path, active_hashes=active, retained_hashes=active,
        extra_storage=orphans,
    )

    report = build_orphan_report(
        client, flutter_repo_path=flutter_repo, dist_dir=dist_dir,
        retained_versions=(ACTIVE, RETAINED),
        shards=_shards_for(active, orphans),
    )

    assert list(report.orphan_hashes) == sorted(report.orphan_hashes)


# ---------------------------------------------------------------------------
# Phase 0 — frozen safety contract: digests + candidate fingerprints
# ---------------------------------------------------------------------------


def test_report_freezes_candidate_and_protected_digests(tmp_path):
    """The digests pin exactly which set an operator approved. Construction
    matches the quarantine checkpoint identity: sha256 of newline-joined
    sorted hashes."""
    import hashlib

    from release_safety.orphan_reconcile import build_orphan_report

    active = [_h("aa")]
    orphans = [_h("dd"), _h("ee")]
    client, flutter_repo, dist_dir = _make_world(
        tmp_path, active_hashes=active, retained_hashes=active,
        extra_storage=orphans,
    )

    report = build_orphan_report(
        client, flutter_repo_path=flutter_repo, dist_dir=dist_dir,
        retained_versions=(ACTIVE, RETAINED),
        shards=_shards_for(active, orphans),
    )

    expected_candidates = hashlib.sha256(
        "\n".join(sorted(orphans)).encode("ascii")
    ).hexdigest()
    assert report.candidate_digest == expected_candidates
    assert report.protected_digest == hashlib.sha256(
        "\n".join(sorted(set(active))).encode("ascii")
    ).hexdigest()
    data = report.to_dict()
    assert data["candidate_digest"] == expected_candidates
    assert data["protected_digest"] == report.protected_digest


def test_report_carries_a_source_fingerprint_for_every_candidate(tmp_path):
    from release_safety.orphan_reconcile import build_orphan_report

    active = [_h("aa")]
    orphans = [_h("dd")]
    client, flutter_repo, dist_dir = _make_world(
        tmp_path, active_hashes=active, retained_hashes=active,
        extra_storage=orphans,
    )

    report = build_orphan_report(
        client, flutter_repo_path=flutter_repo, dist_dir=dist_dir,
        retained_versions=(ACTIVE, RETAINED),
        shards=_shards_for(active, orphans),
    )

    fps = report.candidate_fingerprints
    assert set(fps) == set(orphans)
    assert fps[_h("dd")].size == 100
    assert fps[_h("dd")].etag, "eTag must be captured for every candidate"
    data = report.to_dict()
    assert data["candidate_fingerprints"][_h("dd")]["size"] == 100
    assert data["candidate_fingerprints"][_h("dd")]["etag"] == fps[_h("dd")].etag


def test_blocked_report_freezes_no_candidate_digest(tmp_path):
    """A blocked report proposes nothing, so it must pin nothing approvable."""
    from release_safety.orphan_reconcile import build_orphan_report

    active = [_h("aa")]
    orphans = [_h("dd")]
    client, flutter_repo, dist_dir = _make_world(
        tmp_path, active_hashes=active, retained_hashes=active,
        extra_storage=orphans,
    )
    bucket = client.storage.from_("pharmaguide")
    real_list = bucket.list

    def flaky(path="", options=None):
        if path == f"{PREFIX}/dd":
            raise RuntimeError("The connection to the database timed out")
        return real_list(path=path, options=options)

    bucket.list = flaky

    report = build_orphan_report(
        client, flutter_repo_path=flutter_repo, dist_dir=dist_dir,
        retained_versions=(ACTIVE, RETAINED),
        shards=_shards_for(active, orphans),
        max_attempts=2,
    )

    assert report.blocked_reason is not None
    assert report.candidate_digest is None
    assert report.candidate_fingerprints == {}


# ---------------------------------------------------------------------------
# Hardening pass: the report IS the approval artifact
# ---------------------------------------------------------------------------


def test_report_carries_a_quarantine_run_date(tmp_path):
    """The artifact pins the quarantine date, so a run resumed after midnight
    still lands every blob under the SAME date directory."""
    from release_safety.orphan_reconcile import build_orphan_report

    active = [_h("aa")]
    client, flutter_repo, dist_dir = _make_world(
        tmp_path, active_hashes=active, retained_hashes=active,
        extra_storage=[_h("dd")],
    )

    report = build_orphan_report(
        client, flutter_repo_path=flutter_repo, dist_dir=dist_dir,
        retained_versions=(ACTIVE, RETAINED),
        shards=_shards_for(active, [_h("dd")]),
        run_date="2026-08-28",
    )

    assert report.quarantine_run_date == "2026-08-28"
    assert report.to_dict()["quarantine_run_date"] == "2026-08-28"


def test_candidate_without_etag_blocks_the_dry_report(tmp_path):
    """An unproven fingerprint must block at REPORT time — not surface later
    as an apparently actionable count that execute then refuses."""
    from release_safety.orphan_reconcile import build_orphan_report

    active = [_h("aa")]
    orphans = [_h("dd")]
    client, flutter_repo, dist_dir = _make_world(
        tmp_path, active_hashes=active, retained_hashes=active,
        extra_storage=orphans,
    )
    bucket = client.storage.from_("pharmaguide")
    real_list = bucket.list

    def stripping(path="", options=None):
        items = real_list(path=path, options=options)
        for item in items:
            metadata = item.get("metadata")
            if isinstance(metadata, dict):
                metadata.pop("eTag", None)
        return items

    bucket.list = stripping

    report = build_orphan_report(
        client, flutter_repo_path=flutter_repo, dist_dir=dist_dir,
        retained_versions=(ACTIVE, RETAINED),
        shards=_shards_for(active, orphans),
    )

    assert report.blocked_reason is not None
    assert "fingerprint" in report.blocked_reason.lower()
    assert report.proposed_quarantine == 0
    assert report.candidate_digest is None
