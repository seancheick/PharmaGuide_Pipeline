#!/usr/bin/env python3
"""
Schema validation tests for proprietary_blends.json.

Concern 17 (CONCERNS.md): 'proprietary_blends DB has no schema enforcement.
Unlike IQM/OI/HA/BR, proprietary_blends entries are not schema-validated by any test.
Risk: Malformed entries silently fail to match at runtime.'

These tests enforce the contract so malformed entries are caught at commit time.
"""

import json
import pytest
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
BLENDS_FILE = DATA_DIR / "proprietary_blends.json"

REQUIRED_ENTRY_KEYS = {"id", "standard_name", "blend_terms", "risk_factors", "notes"}
REQUIRED_METADATA_KEYS = {"schema_version", "total_entries", "last_updated"}


@pytest.fixture(scope="module")
def blends_data():
    with open(BLENDS_FILE, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def blend_entries(blends_data):
    return blends_data.get("proprietary_blend_concerns", [])


class TestProprietaryBlendsMetadata:
    """_metadata block must be present and well-formed."""

    def test_metadata_present(self, blends_data):
        assert "_metadata" in blends_data, "proprietary_blends.json missing _metadata block"

    def test_metadata_has_required_keys(self, blends_data):
        meta = blends_data["_metadata"]
        missing = REQUIRED_METADATA_KEYS - set(meta.keys())
        assert not missing, f"_metadata missing keys: {missing}"

    def test_metadata_schema_version_is_string(self, blends_data):
        version = blends_data["_metadata"]["schema_version"]
        assert isinstance(version, str) and version, "schema_version must be a non-empty string"

    def test_metadata_total_entries_matches_actual_count(self, blends_data, blend_entries):
        declared = blends_data["_metadata"]["total_entries"]
        actual = len(blend_entries)
        assert declared == actual, (
            f"_metadata.total_entries={declared} but actual entry count={actual}"
        )

    def test_proprietary_blend_concerns_key_present(self, blends_data):
        assert "proprietary_blend_concerns" in blends_data, (
            "Top-level key 'proprietary_blend_concerns' missing"
        )

    def test_proprietary_blend_concerns_is_list(self, blends_data):
        assert isinstance(blends_data["proprietary_blend_concerns"], list)


class TestProprietaryBlendsEntrySchema:
    """Every entry must have all required fields with correct types."""

    def test_at_least_one_entry(self, blend_entries):
        assert len(blend_entries) > 0, "proprietary_blend_concerns must have at least one entry"

    @pytest.mark.parametrize("key", sorted(REQUIRED_ENTRY_KEYS))
    def test_all_entries_have_required_key(self, blend_entries, key):
        missing = [e.get("id", f"[index {i}]") for i, e in enumerate(blend_entries) if key not in e]
        assert not missing, f"Entries missing required key '{key}': {missing}"

    def test_all_ids_are_non_empty_strings(self, blend_entries):
        bad = [i for i, e in enumerate(blend_entries) if not isinstance(e.get("id"), str) or not e["id"]]
        assert not bad, f"Entries at indices {bad} have invalid 'id'"

    def test_all_ids_are_unique(self, blend_entries):
        ids = [e["id"] for e in blend_entries]
        duplicates = [id_ for id_ in set(ids) if ids.count(id_) > 1]
        assert not duplicates, f"Duplicate blend IDs found: {duplicates}"

    def test_all_standard_names_are_non_empty_strings(self, blend_entries):
        bad = [e["id"] for e in blend_entries if not isinstance(e.get("standard_name"), str) or not e["standard_name"].strip()]
        assert not bad, f"Entries with invalid standard_name: {bad}"

    def test_all_blend_terms_are_lists(self, blend_entries):
        bad = [e["id"] for e in blend_entries if not isinstance(e.get("blend_terms"), list)]
        assert not bad, f"Entries where blend_terms is not a list: {bad}"

    def test_all_blend_terms_are_non_empty_lists(self, blend_entries):
        bad = [e["id"] for e in blend_entries if not e.get("blend_terms")]
        assert not bad, f"Entries with empty blend_terms list: {bad}"

    def test_all_blend_terms_contain_only_strings(self, blend_entries):
        bad = []
        for e in blend_entries:
            non_str = [t for t in e.get("blend_terms", []) if not isinstance(t, str)]
            if non_str:
                bad.append(f"{e['id']}: {non_str[:3]}")
        assert not bad, f"Entries with non-string blend_terms: {bad}"

    def test_all_risk_factors_are_lists(self, blend_entries):
        bad = [e["id"] for e in blend_entries if not isinstance(e.get("risk_factors"), list)]
        assert not bad, f"Entries where risk_factors is not a list: {bad}"

    def test_all_risk_factors_contain_only_strings(self, blend_entries):
        bad = []
        for e in blend_entries:
            non_str = [r for r in e.get("risk_factors", []) if not isinstance(r, str)]
            if non_str:
                bad.append(f"{e['id']}: {non_str[:2]}")
        assert not bad, f"Entries with non-string risk_factors: {bad}"

    def test_all_notes_are_strings(self, blend_entries):
        bad = [e["id"] for e in blend_entries if not isinstance(e.get("notes"), str)]
        assert not bad, f"Entries where notes is not a string: {bad}"

    def test_no_duplicate_blend_terms_within_entry(self, blend_entries):
        bad = []
        for e in blend_entries:
            terms = e.get("blend_terms", [])
            seen = set()
            dupes = [t for t in terms if t in seen or seen.add(t)]
            if dupes:
                bad.append(f"{e['id']}: {dupes[:3]}")
        assert not bad, f"Entries with duplicate blend_terms: {bad}"

    def test_no_blend_term_duplicated_across_entries(self, blend_entries):
        """A blend_term in multiple entries creates ambiguous runtime matches."""
        term_to_ids: dict = {}
        for e in blend_entries:
            for term in e.get("blend_terms", []):
                term_to_ids.setdefault(term, []).append(e["id"])
        cross_dupes = {t: ids for t, ids in term_to_ids.items() if len(ids) > 1}
        assert not cross_dupes, (
            f"blend_terms appear in multiple entries (ambiguous matching): {cross_dupes}"
        )
