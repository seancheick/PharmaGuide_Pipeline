#!/usr/bin/env python3
"""Contract and data-quality tests for timing_rules.json."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TIMING_FILE = DATA_DIR / "timing_rules.json"

VALID_RULE_TYPES = {"separate", "take_together", "take_with_food", "take_on_empty_stomach", "time_of_day"}
VALID_EVIDENCE_LEVELS = {"established", "probable", "possible"}
VALID_SOURCE_TYPES = {"pubmed", "reference", "nih_ods", "fda", "nccih"}


@pytest.fixture(scope="module")
def timing_data():
    with open(TIMING_FILE) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def rules(timing_data):
    return timing_data["timing_rules"]


# ── Metadata contract ──────────────────────────────────────────────

class TestTimingMetadata:
    def test_has_metadata(self, timing_data):
        assert "_metadata" in timing_data

    def test_metadata_required_fields(self, timing_data):
        meta = timing_data["_metadata"]
        for field in ("description", "purpose", "schema_version", "last_updated", "total_entries"):
            assert field in meta, f"Missing metadata field: {field}"

    def test_schema_version_is_5x(self, timing_data):
        ver = timing_data["_metadata"]["schema_version"]
        assert ver.startswith("5."), f"Expected 5.x schema, got {ver}"

    def test_total_entries_matches(self, timing_data, rules):
        declared = timing_data["_metadata"]["total_entries"]
        actual = len(rules)
        assert declared == actual, f"Metadata says {declared} entries but found {actual}"

    def test_purpose_is_timing(self, timing_data):
        assert timing_data["_metadata"]["purpose"] == "timing_optimization"


# ── Schema contract per rule ───────────────────────────────────────

class TestTimingRuleSchema:
    def test_all_ids_unique(self, rules):
        ids = [r["id"] for r in rules]
        assert len(ids) == len(set(ids)), f"Duplicate IDs: {[x for x in ids if ids.count(x) > 1]}"

    def test_ids_prefixed(self, rules):
        for r in rules:
            assert r["id"].startswith("timing_"), f"ID must start with 'timing_': {r['id']}"

    def test_required_fields_present(self, rules):
        required = {"id", "ingredient1", "ingredient2", "rule_type", "advice", "mechanism",
                     "separation_hours", "score_impact", "evidence_level", "sources"}
        for r in rules:
            missing = required - set(r.keys())
            assert not missing, f"Rule {r['id']} missing fields: {missing}"

    def test_rule_type_valid(self, rules):
        for r in rules:
            assert r["rule_type"] in VALID_RULE_TYPES, f"Rule {r['id']} has invalid rule_type: {r['rule_type']}"

    def test_evidence_level_valid(self, rules):
        for r in rules:
            assert r["evidence_level"] in VALID_EVIDENCE_LEVELS, f"Rule {r['id']} has invalid evidence_level"

    def test_score_impact_is_int(self, rules):
        for r in rules:
            assert isinstance(r["score_impact"], int), f"Rule {r['id']} score_impact must be int"

    def test_separation_hours_nullable(self, rules):
        for r in rules:
            val = r["separation_hours"]
            assert val is None or isinstance(val, (int, float)), f"Rule {r['id']} separation_hours must be int/float/null"

    def test_separate_rules_have_hours(self, rules):
        for r in rules:
            if r["rule_type"] == "separate":
                assert r["separation_hours"] is not None and r["separation_hours"] > 0, \
                    f"Separate rule {r['id']} must specify positive separation_hours"

    def test_ingredients_lowercase(self, rules):
        for r in rules:
            assert r["ingredient1"] == r["ingredient1"].lower(), f"Rule {r['id']} ingredient1 must be lowercase"
            assert r["ingredient2"] == r["ingredient2"].lower(), f"Rule {r['id']} ingredient2 must be lowercase"


# ── Source quality ─────────────────────────────────────────────────

class TestTimingSources:
    def test_every_rule_has_at_least_one_source(self, rules):
        for r in rules:
            assert len(r["sources"]) >= 1, f"Rule {r['id']} has no sources"

    def test_source_type_valid(self, rules):
        for r in rules:
            for s in r["sources"]:
                assert s["source_type"] in VALID_SOURCE_TYPES, \
                    f"Rule {r['id']} has invalid source_type: {s['source_type']}"

    def test_sources_have_url(self, rules):
        for r in rules:
            for s in r["sources"]:
                assert "url" in s and s["url"].startswith("http"), \
                    f"Rule {r['id']} source missing valid URL"

    def test_pubmed_urls_are_specific(self, rules):
        """PubMed URLs must point to a specific article, not a search query."""
        for r in rules:
            for s in r["sources"]:
                if s["source_type"] == "pubmed":
                    url = s["url"]
                    assert "?term=" not in url and "/?term=" not in url, \
                        f"Rule {r['id']} has query-placeholder PubMed URL: {url}"


# ── Data quality ───────────────────────────────────────────────────

class TestTimingDataQuality:
    def test_minimum_rule_count(self, rules):
        assert len(rules) >= 30, f"Expected >=30 rules, got {len(rules)}"

    def test_established_conflicts_have_penalty(self, rules):
        for r in rules:
            if r["rule_type"] == "separate" and r["evidence_level"] == "established":
                assert r["score_impact"] < 0, \
                    f"Established separation rule {r['id']} should have negative score_impact"

    def test_take_together_rules_have_bonus_or_neutral(self, rules):
        for r in rules:
            if r["rule_type"] == "take_together":
                assert r["score_impact"] >= 0, \
                    f"Take-together rule {r['id']} should have non-negative score_impact"

    def test_iron_calcium_separation_exists(self, rules):
        """The most clinically important timing rule must be present."""
        pairs = {(r["ingredient1"], r["ingredient2"]) for r in rules}
        assert ("iron", "calcium") in pairs or ("calcium", "iron") in pairs

    def test_advice_is_consumer_friendly(self, rules):
        for r in rules:
            assert len(r["advice"]) >= 20, f"Rule {r['id']} advice too short"
            assert len(r["advice"]) <= 300, f"Rule {r['id']} advice too long for UI"
