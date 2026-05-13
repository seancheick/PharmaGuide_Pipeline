"""Tests for scripts/release_safety/index_validator.py — detail_index.json
validator (ADR-0001 P1.2 / HR-11).

All tests are pure unit tests on tmp_path JSON files. No Supabase, no
network, no mocks needed. Runtime target: <100ms total.

Per the P1.2 sign-off (2026-05-12):
  - Duplicate blob hashes are ALLOWED (content-addressed store; two products
    with identical detail JSON legitimately share a hash). Surfaced via
    ``ValidatedIndex.duplicate_hash_groups`` for audit, not as an error.
  - Optional checksum/version cross-check is opt-in via the caller passing
    ``expected_db_checksum`` / ``expected_db_version``.
"""

from __future__ import annotations

import json
import os
import sys
import pytest

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

VALID_HASH_A = "a" * 64
VALID_HASH_B = "b" * 64
VALID_HASH_C = "c" * 64
VALID_HASH_REAL = "cefba629025d887466ed702759c203b470b86501bda8969bec39066e53198776"


def _make_entry(blob_hash: str, blob_version: int = 1) -> dict:
    """Build a realistic detail_index entry."""
    return {
        "blob_sha256": blob_hash,
        "storage_path": f"shared/details/sha256/{blob_hash[:2]}/{blob_hash}.json",
        "blob_version": blob_version,
    }


def _write_index(tmp_path, payload: dict) -> "Path":
    """Write a detail_index.json fixture and return its path."""
    p = tmp_path / "detail_index.json"
    p.write_text(json.dumps(payload))
    return p


# ---------------------------------------------------------------------------
# Test 1 — valid index returns correct ValidatedIndex
# ---------------------------------------------------------------------------


def test_p1_2_valid_index_returns_correct_validated_index(tmp_path):
    """A well-formed index parses into a ValidatedIndex with the expected
    counts, hash set, and no duplicates."""
    from release_safety.index_validator import validate_detail_index

    payload = {
        "1001": _make_entry(VALID_HASH_A),
        "1002": _make_entry(VALID_HASH_B),
        "1003": _make_entry(VALID_HASH_C),
    }
    index_path = _write_index(tmp_path, payload)

    result = validate_detail_index(index_path)

    assert result.index_path == index_path
    assert result.count == 3
    assert result.unique_hash_count == 3
    assert result.blob_hashes == frozenset({VALID_HASH_A, VALID_HASH_B, VALID_HASH_C})
    assert result.duplicate_hash_groups == {}
    assert result.db_version is None
    assert result.db_checksum is None


# ---------------------------------------------------------------------------
# Test 2 — missing file
# ---------------------------------------------------------------------------


def test_p1_2_missing_file_raises_malformed_json_error(tmp_path):
    """A non-existent index path raises MalformedJSONError naming the path."""
    from release_safety.index_validator import (
        validate_detail_index,
        MalformedJSONError,
    )

    bogus = tmp_path / "does_not_exist.json"

    with pytest.raises(MalformedJSONError) as excinfo:
        validate_detail_index(bogus)

    assert str(bogus) in str(excinfo.value)


# ---------------------------------------------------------------------------
# Test 3 — malformed JSON
# ---------------------------------------------------------------------------


def test_p1_2_malformed_json_raises_malformed_json_error(tmp_path):
    """A file that exists but doesn't parse as JSON raises MalformedJSONError."""
    from release_safety.index_validator import (
        validate_detail_index,
        MalformedJSONError,
    )

    p = tmp_path / "detail_index.json"
    p.write_text("THIS IS NOT JSON {{{")

    with pytest.raises(MalformedJSONError) as excinfo:
        validate_detail_index(p)

    assert "not valid JSON" in str(excinfo.value)
    assert str(p) in str(excinfo.value)


# ---------------------------------------------------------------------------
# Test 4 — top-level not a dict
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload,scenario",
    [
        ([{"blob_sha256": VALID_HASH_A}], "list_at_top"),
        ("just a string", "string_at_top"),
        (42, "number_at_top"),
        (None, "null_at_top"),
    ],
)
def test_p1_2_top_level_not_dict_raises_malformed_structure(tmp_path, payload, scenario):
    """If the parsed JSON's top-level is anything other than a dict, raise
    MalformedStructureError. The error message includes the actual type
    so the operator can fix the right thing."""
    from release_safety.index_validator import (
        validate_detail_index,
        MalformedStructureError,
    )

    p = tmp_path / "detail_index.json"
    p.write_text(json.dumps(payload))

    with pytest.raises(MalformedStructureError) as excinfo:
        validate_detail_index(p)

    assert "top-level must be a JSON object" in str(excinfo.value), scenario


# ---------------------------------------------------------------------------
# Test 5 — entry missing usable hash field
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "entry,scenario",
    [
        ({},                                                 "empty_entry"),
        ({"blob_version": 1, "label": "X"},                  "no_hash_or_path"),
        ({"blob_sha256": ""},                                "empty_blob_sha256"),
        ({"blob_sha256": None},                              "null_blob_sha256"),
        ({"storage_path": "shared/details/sha256/aa/bogus"}, "unparseable_storage_path"),
    ],
)
def test_p1_2_entry_missing_hash_raises_missing_field(tmp_path, entry, scenario):
    """An entry that yields no usable hash from blob_sha256 OR storage_path
    raises MissingFieldError naming the dsld_id."""
    from release_safety.index_validator import (
        validate_detail_index,
        MissingFieldError,
    )

    payload = {"1001": _make_entry(VALID_HASH_A), "9999": entry}
    p = _write_index(tmp_path, payload)

    with pytest.raises(MissingFieldError) as excinfo:
        validate_detail_index(p)

    assert "9999" in str(excinfo.value), scenario


# ---------------------------------------------------------------------------
# Test 6 — malformed hash length
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_hash,scenario",
    [
        ("a" * 63,  "too_short"),
        ("a" * 65,  "too_long"),
        ("a" * 32,  "md5_length"),
        ("",        "empty_string"),  # caught by missing-field path; ensure
                                      # we treat empty as missing not malformed
    ],
)
def test_p1_2_malformed_hash_length_rejected(tmp_path, bad_hash, scenario):
    """Hashes that are not exactly 64 hex chars are rejected.

    Empty strings are caught by the missing-field path (an empty hash means
    no hash). Other lengths trigger MalformedHashError.
    """
    from release_safety.index_validator import (
        validate_detail_index,
        MalformedHashError,
        MissingFieldError,
        IndexValidationError,
    )

    entry = {"blob_sha256": bad_hash}
    payload = {"1001": entry}
    p = _write_index(tmp_path, payload)

    with pytest.raises(IndexValidationError):
        validate_detail_index(p)


# ---------------------------------------------------------------------------
# Test 7 — uppercase hash rejected
# ---------------------------------------------------------------------------


def test_p1_2_uppercase_hash_rejected(tmp_path):
    """Blob hashes must be lowercase hex per the pipeline contract.
    Uppercase letters trigger MalformedHashError so we don't accidentally
    create case-sensitive storage-path mismatches."""
    from release_safety.index_validator import (
        validate_detail_index,
        MalformedHashError,
    )

    upper_hash = ("A" * 64)  # all uppercase
    payload = {"1001": {"blob_sha256": upper_hash}}
    p = _write_index(tmp_path, payload)

    with pytest.raises(MalformedHashError) as excinfo:
        validate_detail_index(p)

    assert "lowercase" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Test 8 — non-hex characters rejected
# ---------------------------------------------------------------------------


def test_p1_2_non_hex_hash_rejected(tmp_path):
    """A hash containing non-hex characters (e.g. 'g', 'z') triggers
    MalformedHashError."""
    from release_safety.index_validator import (
        validate_detail_index,
        MalformedHashError,
    )

    # 64 chars but with 'z' — invalid hex
    bad_hash = ("z" * 64)
    payload = {"1001": {"blob_sha256": bad_hash}}
    p = _write_index(tmp_path, payload)

    with pytest.raises(MalformedHashError):
        validate_detail_index(p)


# ---------------------------------------------------------------------------
# Test 9 — duplicate hash ALLOWED (content-addressed; surfaced as audit)
# ---------------------------------------------------------------------------


def test_p1_2_duplicate_hash_is_allowed_and_surfaced_in_audit(tmp_path):
    """Per P1.2 sign-off: duplicate blob hashes are valid in a content-
    addressed store. Two products with identical detail JSON share a hash
    legitimately. The validator MUST NOT raise; it MUST report the duplicate
    via duplicate_hash_groups for audit logging."""
    from release_safety.index_validator import validate_detail_index

    # 1001 and 1003 deliberately share VALID_HASH_A
    payload = {
        "1001": _make_entry(VALID_HASH_A),
        "1002": _make_entry(VALID_HASH_B),
        "1003": _make_entry(VALID_HASH_A),
    }
    p = _write_index(tmp_path, payload)

    # Must NOT raise.
    result = validate_detail_index(p)

    # Counts: 3 entries total, 2 unique hashes.
    assert result.count == 3
    assert result.unique_hash_count == 2
    assert result.blob_hashes == frozenset({VALID_HASH_A, VALID_HASH_B})

    # Duplicate group surfaces both dsld_ids that share the hash.
    assert VALID_HASH_A in result.duplicate_hash_groups
    assert sorted(result.duplicate_hash_groups[VALID_HASH_A]) == ["1001", "1003"]
    # Non-duplicated hashes do NOT appear in the audit map.
    assert VALID_HASH_B not in result.duplicate_hash_groups


# ---------------------------------------------------------------------------
# Test 10 — checksum mismatch
# ---------------------------------------------------------------------------


def test_p1_2_checksum_mismatch_raises(tmp_path):
    """When the caller passes expected_db_checksum, the index's
    _meta.db_checksum_sha256 must match. Mismatch raises ChecksumMismatchError
    naming both values."""
    from release_safety.index_validator import (
        validate_detail_index,
        ChecksumMismatchError,
    )

    payload = {
        "_meta": {
            "db_version": "2026.05.12.203133",
            "db_checksum_sha256": "actualchecksumXYZ",
        },
        "1001": _make_entry(VALID_HASH_A),
    }
    p = _write_index(tmp_path, payload)

    with pytest.raises(ChecksumMismatchError) as excinfo:
        validate_detail_index(
            p,
            expected_db_checksum="differentchecksumABC",
        )

    msg = str(excinfo.value)
    assert "differentchecksumABC" in msg
    assert "actualchecksumXYZ" in msg


# ---------------------------------------------------------------------------
# Test 11 — checksum match
# ---------------------------------------------------------------------------


def test_p1_2_checksum_match_succeeds_and_returns_metadata(tmp_path):
    """When expected_db_checksum matches the index's _meta value, validation
    succeeds and ValidatedIndex carries the version + checksum metadata."""
    from release_safety.index_validator import validate_detail_index

    expected_checksum = "matching_checksum_abc123"
    expected_version = "2026.05.12.203133"

    payload = {
        "_meta": {
            "db_version": expected_version,
            "db_checksum_sha256": expected_checksum,
        },
        "1001": _make_entry(VALID_HASH_A),
        "1002": _make_entry(VALID_HASH_B),
    }
    p = _write_index(tmp_path, payload)

    result = validate_detail_index(
        p,
        expected_db_checksum=expected_checksum,
        expected_db_version=expected_version,
    )

    assert result.count == 2
    assert result.db_version == expected_version
    assert result.db_checksum == expected_checksum


# ---------------------------------------------------------------------------
# Test 12 — realistic multi-entry fixture mirroring pipeline output
# ---------------------------------------------------------------------------


def test_p1_2_realistic_fixture_validates_end_to_end(tmp_path):
    """A realistic 5-entry index (mirroring real pipeline output shape) with
    one legitimately-deduplicated hash and one entry whose hash is parseable
    only from storage_path (no blob_sha256 field) should validate cleanly."""
    from release_safety.index_validator import validate_detail_index

    # Hash for entry 5 will be parsed from storage_path, not blob_sha256.
    storage_only_entry = {
        "storage_path": f"shared/details/sha256/{VALID_HASH_REAL[:2]}/{VALID_HASH_REAL}.json",
        "blob_version": 1,
    }

    payload = {
        "222862": _make_entry(VALID_HASH_A),                # GOL Women CBD
        "222770": _make_entry(VALID_HASH_B),                # GOL CBD+ Relax
        "222788": _make_entry(VALID_HASH_A),                # dedup with 222862
        "222844": _make_entry(VALID_HASH_C),
        "222850": storage_only_entry,                       # hash from storage_path only
    }
    p = _write_index(tmp_path, payload)

    result = validate_detail_index(p)

    assert result.count == 5
    assert result.unique_hash_count == 4
    assert result.blob_hashes == frozenset({
        VALID_HASH_A, VALID_HASH_B, VALID_HASH_C, VALID_HASH_REAL,
    })
    # Dedup surfaces in audit
    assert sorted(result.duplicate_hash_groups[VALID_HASH_A]) == ["222788", "222862"]
    # Other hashes are unique — NOT in audit map
    for solo in (VALID_HASH_B, VALID_HASH_C, VALID_HASH_REAL):
        assert solo not in result.duplicate_hash_groups
