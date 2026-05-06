#!/usr/bin/env python3
"""Contract tests for `clinical_risk_taxonomy.json::profile_flags[]`.

profile_flags[] was introduced in taxonomy schema 5.2.0 to support the
v6.0 profile_gate schema (see scripts/INTERACTION_RULE_SCHEMA_V6_ADR.md).

Locked decisions for v6.0:
  - 7 starting flags: pregnant, trying_to_conceive, breastfeeding,
    post_op_recovery, surgery_scheduled, hypoglycemia_history,
    bleeding_history
  - No trimester sub-flags (per project decision 2026-05-05)
  - kidney/liver stay as conditions, not flags (Flutter captures them
    as conditions today)
  - Each entry: id (snake_case), label, category, description
"""

import json
import os
import re

import pytest

TAX_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "clinical_risk_taxonomy.json"
)


@pytest.fixture(scope="module")
def taxonomy():
    with open(TAX_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def flags(taxonomy):
    return taxonomy["profile_flags"]


EXPECTED_FLAG_IDS = {
    "pregnant",
    "trying_to_conceive",
    "breastfeeding",
    "post_op_recovery",
    "surgery_scheduled",
    "hypoglycemia_history",
    "bleeding_history",
}


def test_profile_flags_block_present(taxonomy):
    assert "profile_flags" in taxonomy, "profile_flags[] block must exist (taxonomy v5.2.0+)"
    assert isinstance(taxonomy["profile_flags"], list)


def test_initial_flag_set_locked(flags):
    ids = {f["id"] for f in flags}
    missing = EXPECTED_FLAG_IDS - ids
    extra = ids - EXPECTED_FLAG_IDS
    assert not missing, f"missing locked flags: {missing}"
    assert not extra, (
        f"unexpected flags {extra}; profile_flags vocabulary changes "
        f"require an ADR amendment"
    )


def test_each_flag_has_required_fields(flags):
    for flag in flags:
        assert "id" in flag, f"flag missing id: {flag}"
        assert "label" in flag, f"flag missing label: {flag['id']}"
        assert "category" in flag, f"flag missing category: {flag['id']}"
        assert "description" in flag, f"flag missing description: {flag['id']}"


def test_ids_are_snake_case(flags):
    pat = re.compile(r"^[a-z][a-z0-9_]*$")
    for flag in flags:
        assert pat.match(flag["id"]), f"non-snake_case id: {flag['id']!r}"


def test_no_trimester_subflags(flags):
    """Per ADR §"What profile_gate is NOT" — no trimester logic in v6.0."""
    ids = {f["id"] for f in flags}
    forbidden = {"first_trimester", "second_trimester", "third_trimester"}
    overlap = ids & forbidden
    assert not overlap, (
        f"trimester flags forbidden in v6.0: {overlap}; "
        f"requires ADR amendment to introduce"
    )


def test_categories_are_recognized(flags):
    valid_categories = {"reproductive", "perioperative", "metabolic", "hematologic"}
    for flag in flags:
        assert flag["category"] in valid_categories, (
            f"flag {flag['id']} has unknown category {flag['category']!r}; "
            f"expected one of {valid_categories}"
        )


def test_no_duplicate_ids(flags):
    ids = [f["id"] for f in flags]
    assert len(ids) == len(set(ids)), f"duplicate flag ids: {ids}"


def test_kidney_liver_not_in_flags(flags):
    """kidney_disease and liver_disease are conditions, not flags
    (per ADR — Flutter captures them as conditions today)."""
    ids = {f["id"] for f in flags}
    assert "kidney_disease_known" not in ids
    assert "liver_disease_known" not in ids


def test_descriptions_nonempty(flags):
    for flag in flags:
        assert flag["description"].strip(), f"flag {flag['id']} has empty description"
        assert len(flag["description"]) >= 30, (
            f"flag {flag['id']} description too short: {flag['description']!r}"
        )
