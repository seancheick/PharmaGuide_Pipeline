"""D1 contract test for the catalog manifest the Flutter app polls.

The Flutter app discovers new catalog releases by reading a row from the
Supabase `export_manifest` table (see
`PharmaGuide-ai/lib/data/supabase/sync_service.dart::fetchCurrentDbVersion`).
That table is populated by `sync_to_supabase.py` directly from the JSON
file `release_catalog_artifact.py` stages at `dist/export_manifest.json`.

This test pins the JSON-side contract that the Flutter app — and the
sync uploader that writes the table — depend on. If a future build
mutates the schema (renaming `db_version`, dropping `checksum`,
introducing a non-sortable version format, etc.) this suite fails
loudly *before* the change reaches the device.

Track D1 calls these out as the four required Flutter-facing keys:

    latest_version  ← `db_version`
    bundle_url      ← derivable from `db_version` (no separate field;
                      stored at `v{db_version}/pharmaguide_core.db` in
                      the `pharmaguide` Supabase Storage bucket)
    sha256          ← `checksum` (and the raw-hex sibling `checksum_sha256`)
    released_at     ← `generated_at`

Plus the monotonicity gate: a newer staged release must have a
strictly-greater `db_version` than the previous one. The pipeline
build version format is `YYYY.MM.DD.HHMMSS`, which is lexicographically
sortable — so plain string comparison is sufficient and we don't need
to parse the version string at all.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import release_catalog_artifact as rca  # noqa: E402

# Reuse the synthetic-release fixture builder from the existing
# release-test suite. Keeping the two suites in lock-step prevents
# fixture drift: if the upstream release-script test changes how it
# builds a "valid" pipeline output, the contract test follows.
from test_release_catalog_artifact import (  # noqa: E402
    _make_fake_db,
    _write_manifest_json,
)


# ---------------------------------------------------------------------------
# Constants the Flutter side and the uploader rely on
# ---------------------------------------------------------------------------


REQUIRED_KEYS = (
    "db_version",
    "schema_version",
    "pipeline_version",
    "scoring_version",
    "product_count",
    "min_app_version",
    "generated_at",
    "checksum",
    "checksum_sha256",
)

DB_VERSION_PATTERN = re.compile(
    r"^\d{4}\.\d{2}\.\d{2}\.\d{6}$"
)  # e.g. 2026.04.27.063145

SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")

# Mirrors `SupabaseContract.coreDbPath(version)` in
# lib/data/supabase/supabase_contract.dart. If that contract ever
# changes the test must change with it.
def expected_bundle_path(db_version: str) -> str:
    return f"v{db_version}/pharmaguide_core.db"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _staged_manifest(tmp_path: Path, *, db_version: str) -> Dict[str, Any]:
    """Build a synthetic release dir and run it through
    `validate_release_candidate` + `build_release_manifest` so we get
    the *exact* dict that the staged dist/export_manifest.json holds.
    """
    input_dir = tmp_path / f"in_{db_version}"
    input_dir.mkdir()
    db_path = input_dir / "pharmaguide_core.db"
    _make_fake_db(db_path, row_count=600, db_version=db_version)
    _write_manifest_json(
        input_dir / "export_manifest.json",
        db_path,
        row_count=600,
        db_version=db_version,
    )

    validation = rca.validate_release_candidate(
        input_dir=input_dir, min_products=500
    )
    return rca.build_release_manifest(
        source_manifest=validation["manifest"],
        checksum_sha256=validation["checksum_sha256"],
    )


# ---------------------------------------------------------------------------
# Required-keys contract
# ---------------------------------------------------------------------------


def test_staged_manifest_has_every_required_key(tmp_path: Path) -> None:
    """The four Flutter-facing fields plus the metadata the uploader
    needs must all be present in the staged manifest.
    """
    manifest = _staged_manifest(tmp_path, db_version="2026.04.27.063145")
    missing = [k for k in REQUIRED_KEYS if k not in manifest]
    assert missing == [], (
        f"Staged manifest is missing required keys: {missing}. "
        "Either release_catalog_artifact.build_release_manifest stopped "
        "writing them or the contract drifted."
    )


def test_db_version_alias_is_latest_version(tmp_path: Path) -> None:
    """`db_version` IS the `latest_version` field the Flutter app reads.
    No separate alias key is required, but the field must exist and be
    non-empty.
    """
    manifest = _staged_manifest(tmp_path, db_version="2026.04.27.063145")
    assert manifest["db_version"] == "2026.04.27.063145"
    assert isinstance(manifest["db_version"], str)
    assert manifest["db_version"].strip() != ""


def test_generated_at_alias_is_released_at(tmp_path: Path) -> None:
    """`generated_at` is the `released_at` the manifest contract calls
    for. It must be parseable as an ISO-8601 datetime in UTC.
    """
    manifest = _staged_manifest(tmp_path, db_version="2026.04.27.063145")
    raw = manifest["generated_at"]
    assert isinstance(raw, str)
    parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None, (
        f"generated_at must carry timezone info; got {raw!r}"
    )
    assert parsed.utcoffset() == dt.timedelta(0), (
        f"generated_at must be UTC; got offset {parsed.utcoffset()!r}"
    )


# ---------------------------------------------------------------------------
# Format gates
# ---------------------------------------------------------------------------


def test_db_version_is_lex_sortable_timestamp(tmp_path: Path) -> None:
    """`YYYY.MM.DD.HHMMSS` — chosen specifically so plain string sort
    gives chronological order. If the format ever drifts (e.g. drops
    leading zeros), monotonicity comparisons in the uploader and the
    Flutter "is newer?" check both break silently.
    """
    manifest = _staged_manifest(tmp_path, db_version="2026.04.27.063145")
    assert DB_VERSION_PATTERN.match(manifest["db_version"]), (
        f"db_version {manifest['db_version']!r} doesn't match the "
        f"expected YYYY.MM.DD.HHMMSS shape — string sort no longer "
        "gives chronological ordering."
    )


def test_checksum_sha256_is_64_char_hex(tmp_path: Path) -> None:
    manifest = _staged_manifest(tmp_path, db_version="2026.04.27.063145")
    raw = manifest["checksum_sha256"]
    assert isinstance(raw, str)
    assert SHA256_HEX_PATTERN.match(raw), (
        f"checksum_sha256 {raw!r} is not 64 lowercase hex chars."
    )


def test_checksum_prefixed_form_matches_raw(tmp_path: Path) -> None:
    """Producers and consumers may use either form. Whichever path the
    Flutter app picks, the two must agree.
    """
    manifest = _staged_manifest(tmp_path, db_version="2026.04.27.063145")
    prefixed = manifest["checksum"]
    raw = manifest["checksum_sha256"]
    assert prefixed == f"sha256:{raw}", (
        f"checksum {prefixed!r} and checksum_sha256 {raw!r} disagree."
    )


def test_bundle_url_derivable_from_db_version(tmp_path: Path) -> None:
    """The Flutter app builds the bundle path via
    `SupabaseContract.coreDbPath(db_version)` rather than reading a
    separate URL field. Lock that derivation here so any future
    refactor that introduces a `bundle_url` field has to update the
    derivation rule on both sides.
    """
    manifest = _staged_manifest(tmp_path, db_version="2026.04.27.063145")
    expected = expected_bundle_path(manifest["db_version"])
    assert expected == "v2026.04.27.063145/pharmaguide_core.db"


# ---------------------------------------------------------------------------
# Monotonicity gate
# ---------------------------------------------------------------------------


def test_newer_release_has_strictly_greater_db_version(tmp_path: Path) -> None:
    """Two consecutive staged releases must compare as old < new.

    The uploader (sync_to_supabase.py:needs_update) treats `db_version`
    as the freshness key. If the format ever produced a tie or a
    backwards version, the new bundle would be silently rejected and
    the Flutter app would never see the update.
    """
    older = _staged_manifest(tmp_path, db_version="2026.04.27.063145")
    newer = _staged_manifest(tmp_path, db_version="2026.04.28.013000")
    assert older["db_version"] < newer["db_version"]


def test_db_version_sorts_chronologically_at_format_boundaries(
    tmp_path: Path,
) -> None:
    """Stress the lex-sort claim across the trickiest format jumps
    (year rollover, month/day single-digit padding boundaries, hour
    crossing midnight).
    """
    versions = [
        "2025.12.31.235959",
        "2026.01.01.000000",
        "2026.01.01.000001",
        "2026.04.27.063145",
        "2026.04.28.013000",
    ]
    for older, newer in zip(versions, versions[1:]):
        assert older < newer, (
            f"String sort places {older!r} after {newer!r}; the "
            "monotonicity gate would treat the older release as newer."
        )


def test_release_staged_at_is_set(tmp_path: Path) -> None:
    """Sanity check: `release_staged_at` is set fresh on every stage
    and must parse as a UTC ISO-8601 timestamp. This is a separate
    field from `generated_at` (build time) — it pins the moment the
    artifact was frozen for upload.
    """
    manifest = _staged_manifest(tmp_path, db_version="2026.04.27.063145")
    raw = manifest["release_staged_at"]
    assert isinstance(raw, str)
    parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    assert parsed.utcoffset() == dt.timedelta(0)


# ---------------------------------------------------------------------------
# Schema-stability guard
# ---------------------------------------------------------------------------


def test_no_unexpected_required_keys_dropped(tmp_path: Path) -> None:
    """If a future change drops one of the required fields the test
    above (`test_staged_manifest_has_every_required_key`) catches it.
    But it's easy to add a key and forget to also add it to the
    REQUIRED_KEYS tuple — leaving the contract under-tested. This
    second guard makes that mistake explicit by asserting the staged
    manifest's key set is a *superset* of REQUIRED_KEYS, and prints
    any new keys so a maintainer can decide whether to add them to
    the contract.
    """
    manifest = _staged_manifest(tmp_path, db_version="2026.04.27.063145")
    keys = set(manifest.keys())
    extra = sorted(keys - set(REQUIRED_KEYS) - {"release_staged_at"})
    # `extra` is informational, not a failure. It surfaces in the test
    # output via stdout when running `pytest -v`.
    if extra:
        print(
            "[manifest-contract] new fields detected (consider promoting "
            "to the contract): " + ", ".join(extra)
        )
    assert set(REQUIRED_KEYS).issubset(keys)


def test_dist_export_manifest_round_trips_through_json(tmp_path: Path) -> None:
    """The Flutter side reads the manifest as JSON. If a non-JSON-safe
    value ever leaks in (e.g. a Path or a datetime object), the upload
    would fail at write time. Lock this by asserting the staged
    manifest survives a JSON round-trip with no field loss.
    """
    manifest = _staged_manifest(tmp_path, db_version="2026.04.27.063145")
    encoded = json.dumps(manifest, sort_keys=True)
    decoded = json.loads(encoded)
    assert decoded == manifest
