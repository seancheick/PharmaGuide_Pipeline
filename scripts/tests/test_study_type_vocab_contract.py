#!/usr/bin/env python3
"""Contract tests for `data/study_type_vocab.json`."""

import json
import os

import pytest

VOCAB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "study_type_vocab.json")
CLINICAL_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "backed_clinical_studies.json"
)
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "scoring_config.json")


@pytest.fixture(scope="module")
def vocab():
    with open(VOCAB_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def study_types(vocab):
    return vocab["study_types"]


def test_metadata(vocab):
    md = vocab["_metadata"]
    assert md["schema_version"] == "1.0.0"
    assert md["total_entries"] == 7
    assert "LOCKED" in md["status"]
    assert md["char_limit_notes"] == 200


def test_exactly_7_study_types(study_types):
    assert len(study_types) == 7


REQUIRED_FIELDS = {"id", "name", "notes", "base_points", "tier"}


def test_required_fields_present(study_types):
    for entry in study_types:
        keys = set(entry.keys())
        assert REQUIRED_FIELDS == keys, (
            f"study_type {entry.get('id')!r} fields drift: "
            f"missing={REQUIRED_FIELDS - keys}, extra={keys - REQUIRED_FIELDS}"
        )


def test_canonical_7_ids(study_types):
    expected = {
        "systematic_review_meta",
        "rct_multiple",
        "rct_single",
        "clinical_strain",
        "observational",
        "animal_study",
        "in_vitro",
    }
    actual = {entry["id"] for entry in study_types}
    assert actual == expected, f"missing={expected - actual} extra={actual - expected}"


def test_base_points_match_scoring_config(study_types):
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)
    expected = cfg["section_C_evidence_research"]["study_type_base_points"]
    actual = {entry["id"]: entry["base_points"] for entry in study_types}
    assert actual == expected


def test_notes_within_char_limit(study_types):
    over = [(entry["id"], len(entry["notes"])) for entry in study_types if len(entry["notes"]) > 200]
    assert not over, f"notes >200 chars: {over}"


def test_every_clinical_study_type_in_vocab(study_types):
    with open(CLINICAL_PATH, encoding="utf-8") as f:
        data = json.load(f)
    found = set()
    for entry in data.get("backed_clinical_studies", data if isinstance(data, list) else []):
        if isinstance(entry, dict) and isinstance(entry.get("study_type"), str):
            found.add(entry["study_type"])
    if not found:
        for value in data.values():
            if isinstance(value, dict) and isinstance(value.get("study_type"), str):
                found.add(value["study_type"])
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and isinstance(item.get("study_type"), str):
                        found.add(item["study_type"])
    vocab_ids = {entry["id"] for entry in study_types}
    unknown = found - vocab_ids
    assert not unknown, f"clinical study_type values NOT in vocab: {unknown}"
    assert len(found) == 7
