#!/usr/bin/env python3
"""Contract tests for `clinical_risk_taxonomy.json::product_forms[]`.

product_forms[] was introduced in taxonomy schema 5.2.0 to support the
v6.0 profile_gate schema (see scripts/INTERACTION_RULE_SCHEMA_V6_ADR.md).
Used by `excludes.product_forms_any` to suppress alerts for product
forms that don't apply (e.g., topical aloe excluded from oral-aloe
pregnancy alert).

Locked decisions for v6.0 (initial set, intentionally small):
  - 9 starting forms across 2 categories: delivery_route + potency_class
  - delivery_route: topical_only, oral, capsule, tablet, powder, liquid_oral
  - potency_class: culinary_turmeric, high_potency_extract, unknown
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
def forms(taxonomy):
    return taxonomy["product_forms"]


EXPECTED_FORM_IDS = {
    "topical_only",
    "oral",
    "capsule",
    "tablet",
    "powder",
    "liquid_oral",
    "culinary_turmeric",
    "high_potency_extract",
    "unknown",
}


def test_product_forms_block_present(taxonomy):
    assert "product_forms" in taxonomy, "product_forms[] block must exist (taxonomy v5.2.0+)"
    assert isinstance(taxonomy["product_forms"], list)


def test_initial_form_set_locked(forms):
    ids = {f["id"] for f in forms}
    missing = EXPECTED_FORM_IDS - ids
    extra = ids - EXPECTED_FORM_IDS
    assert not missing, f"missing locked forms: {missing}"
    assert not extra, (
        f"unexpected forms {extra}; product_forms vocabulary changes "
        f"require an ADR amendment"
    )


def test_each_form_has_required_fields(forms):
    for form in forms:
        assert "id" in form, f"form missing id: {form}"
        assert "label" in form, f"form missing label: {form['id']}"
        assert "category" in form, f"form missing category: {form['id']}"
        assert "description" in form, f"form missing description: {form['id']}"


def test_ids_are_snake_case(forms):
    pat = re.compile(r"^[a-z][a-z0-9_]*$")
    for form in forms:
        assert pat.match(form["id"]), f"non-snake_case id: {form['id']!r}"


def test_categories_are_recognized(forms):
    valid_categories = {"delivery_route", "potency_class"}
    for form in forms:
        assert form["category"] in valid_categories, (
            f"form {form['id']} has unknown category {form['category']!r}; "
            f"expected one of {valid_categories}"
        )


def test_no_duplicate_ids(forms):
    ids = [f["id"] for f in forms]
    assert len(ids) == len(set(ids)), f"duplicate form ids: {ids}"


def test_delivery_route_set_present(forms):
    """The starter delivery_route group must include the canonical 6."""
    delivery_ids = {f["id"] for f in forms if f["category"] == "delivery_route"}
    expected = {"topical_only", "oral", "capsule", "tablet", "powder", "liquid_oral"}
    assert expected <= delivery_ids, f"delivery_route missing: {expected - delivery_ids}"


def test_potency_class_set_present(forms):
    """The starter potency_class group must include the canonical 3."""
    potency_ids = {f["id"] for f in forms if f["category"] == "potency_class"}
    expected = {"culinary_turmeric", "high_potency_extract", "unknown"}
    assert expected <= potency_ids, f"potency_class missing: {expected - potency_ids}"


def test_unknown_is_default(forms):
    """`unknown` must exist for products with no explicit form_scope."""
    ids = {f["id"] for f in forms}
    assert "unknown" in ids


def test_descriptions_nonempty(forms):
    for form in forms:
        assert form["description"].strip(), f"form {form['id']} has empty description"
        assert len(form["description"]) >= 20, (
            f"form {form['id']} description too short: {form['description']!r}"
        )
