#!/usr/bin/env python3
"""Contract and data-quality tests for medication_depletions.json."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEPLETIONS_FILE = DATA_DIR / "medication_depletions.json"
DRUG_CLASSES_FILE = DATA_DIR / "drug_classes.json"

VALID_SEVERITIES = {"significant", "moderate", "mild"}
VALID_EVIDENCE_LEVELS = {"established", "probable", "possible"}
VALID_ONSET_TIMELINES = {"weeks", "months", "years"}
VALID_DRUG_REF_TYPES = {"class", "drug"}
VALID_SOURCE_TYPES = {"pubmed", "reference", "nih_ods", "fda", "nccih"}


@pytest.fixture(scope="module")
def depletion_data():
    with open(DEPLETIONS_FILE) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def depletions(depletion_data):
    return depletion_data["depletions"]


@pytest.fixture(scope="module")
def drug_classes():
    with open(DRUG_CLASSES_FILE) as f:
        return json.load(f)


# ── Metadata contract ──────────────────────────────────────────────

class TestDepletionMetadata:
    def test_has_metadata(self, depletion_data):
        assert "_metadata" in depletion_data

    def test_metadata_required_fields(self, depletion_data):
        meta = depletion_data["_metadata"]
        for field in ("description", "purpose", "schema_version", "last_updated", "total_entries"):
            assert field in meta, f"Missing metadata field: {field}"

    def test_schema_version_is_5x(self, depletion_data):
        ver = depletion_data["_metadata"]["schema_version"]
        assert ver.startswith("5."), f"Expected 5.x schema, got {ver}"

    def test_total_entries_matches(self, depletion_data, depletions):
        declared = depletion_data["_metadata"]["total_entries"]
        actual = len(depletions)
        assert declared == actual, f"Metadata says {declared} entries but found {actual}"

    def test_purpose_is_depletion(self, depletion_data):
        assert depletion_data["_metadata"]["purpose"] == "depletion_checker"

    def test_has_clinical_disclaimer(self, depletion_data):
        assert "clinical_disclaimer" in depletion_data["_metadata"]


# ── Schema contract per entry ──────────────────────────────────────

class TestDepletionSchema:
    def test_all_ids_unique(self, depletions):
        ids = [d["id"] for d in depletions]
        assert len(ids) == len(set(ids)), f"Duplicate IDs: {[x for x in ids if ids.count(x) > 1]}"

    def test_ids_prefixed(self, depletions):
        for d in depletions:
            assert d["id"].startswith("DEP_"), f"ID must start with 'DEP_': {d['id']}"

    def test_required_fields_present(self, depletions):
        required = {"id", "drug_ref", "depleted_nutrient", "severity", "mechanism",
                     "clinical_impact", "recommendation", "onset_timeline",
                     "evidence_level", "sources"}
        for d in depletions:
            missing = required - set(d.keys())
            assert not missing, f"Entry {d['id']} missing fields: {missing}"

    def test_drug_ref_structure(self, depletions):
        for d in depletions:
            ref = d["drug_ref"]
            assert "type" in ref, f"Entry {d['id']} drug_ref missing 'type'"
            assert "id" in ref, f"Entry {d['id']} drug_ref missing 'id'"
            assert "display_name" in ref, f"Entry {d['id']} drug_ref missing 'display_name'"
            assert ref["type"] in VALID_DRUG_REF_TYPES, f"Entry {d['id']} invalid drug_ref type: {ref['type']}"

    def test_depleted_nutrient_structure(self, depletions):
        for d in depletions:
            nut = d["depleted_nutrient"]
            assert "standard_name" in nut, f"Entry {d['id']} depleted_nutrient missing 'standard_name'"
            assert "canonical_id" in nut, f"Entry {d['id']} depleted_nutrient missing 'canonical_id'"

    def test_severity_valid(self, depletions):
        for d in depletions:
            assert d["severity"] in VALID_SEVERITIES, f"Entry {d['id']} has invalid severity: {d['severity']}"

    def test_evidence_level_valid(self, depletions):
        for d in depletions:
            assert d["evidence_level"] in VALID_EVIDENCE_LEVELS, f"Entry {d['id']} invalid evidence_level"

    def test_onset_timeline_valid(self, depletions):
        for d in depletions:
            assert d["onset_timeline"] in VALID_ONSET_TIMELINES, f"Entry {d['id']} invalid onset_timeline"


# ── Cross-reference validation ─────────────────────────────────────

class TestDepletionCrossReferences:
    def test_class_refs_exist_in_drug_classes(self, depletions, drug_classes):
        """Every class-type drug_ref must reference a real class in drug_classes.json."""
        known_classes = set(drug_classes.get("classes", {}).keys())
        missing = []
        for d in depletions:
            if d["drug_ref"]["type"] == "class":
                class_id = d["drug_ref"]["id"]
                if class_id not in known_classes:
                    missing.append(f"{d['id']} → {class_id}")
        assert not missing, f"Drug class refs not found in drug_classes.json: {missing}"


# ── Source quality ─────────────────────────────────────────────────

class TestDepletionSources:
    def test_every_entry_has_at_least_one_source(self, depletions):
        for d in depletions:
            assert len(d["sources"]) >= 1, f"Entry {d['id']} has no sources"

    def test_source_type_valid(self, depletions):
        for d in depletions:
            for s in d["sources"]:
                assert s["source_type"] in VALID_SOURCE_TYPES, \
                    f"Entry {d['id']} has invalid source_type: {s['source_type']}"

    def test_sources_have_url(self, depletions):
        for d in depletions:
            for s in d["sources"]:
                assert "url" in s and s["url"].startswith("http"), \
                    f"Entry {d['id']} source missing valid URL"

    def test_pubmed_urls_are_specific(self, depletions):
        for d in depletions:
            for s in d["sources"]:
                if s["source_type"] == "pubmed":
                    url = s["url"]
                    assert "?term=" not in url, f"Entry {d['id']} has query-placeholder PubMed URL"

    def test_significant_severity_has_pubmed(self, depletions):
        """At least 60% of significant depletions should have a PubMed-backed source."""
        significant = [d for d in depletions if d["severity"] == "significant"]
        with_pubmed = [d for d in significant if any(s["source_type"] == "pubmed" for s in d["sources"])]
        ratio = len(with_pubmed) / len(significant) if significant else 1.0
        assert ratio >= 0.60, (
            f"Only {len(with_pubmed)}/{len(significant)} ({ratio:.0%}) significant entries have PubMed sources; need >=60%"
        )


# ── Data quality ───────────────────────────────────────────────────

class TestDepletionDataQuality:
    def test_minimum_entry_count(self, depletions):
        assert len(depletions) >= 50, f"Expected >=50 depletions, got {len(depletions)}"

    def test_metformin_b12_exists(self, depletions):
        """The most clinically important depletion must be present."""
        found = any(
            "metformin" in d["drug_ref"]["display_name"].lower() and
            "b12" in d["depleted_nutrient"]["standard_name"].lower()
            for d in depletions
        )
        assert found, "Metformin → B12 depletion must be present"

    def test_statins_coq10_exists(self, depletions):
        found = any(
            d["drug_ref"]["id"] == "class:statins" and
            d["depleted_nutrient"]["canonical_id"] in ("coenzyme_q10", "coq10")
            for d in depletions
        )
        assert found, "Statins → CoQ10 depletion must be present"

    def test_ppi_magnesium_exists(self, depletions):
        found = any(
            d["drug_ref"]["id"] == "class:antacids" and
            "magnesium" in d["depleted_nutrient"]["canonical_id"].lower()
            for d in depletions
        )
        assert found, "PPIs/Antacids → Magnesium depletion must be present"

    def test_recommendation_is_consumer_friendly(self, depletions):
        for d in depletions:
            assert len(d["recommendation"]) >= 20, f"Entry {d['id']} recommendation too short"

    def test_mechanism_is_not_empty(self, depletions):
        for d in depletions:
            assert len(d["mechanism"]) >= 20, f"Entry {d['id']} mechanism too short"
