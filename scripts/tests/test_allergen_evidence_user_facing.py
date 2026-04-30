#!/usr/bin/env python3
"""
Allergen `evidence` field must be user-facing copy, not a developer source path.

Bug discovered 2026-04-30 (Flutter dev report): the AlertSummaryCard accordion
was rendering "Presence: contains. labelText.parsed.allergens: fish" in the user
UI because the pipeline stored the developer source-path string
`"labelText.parsed.allergens: <name>"` in the `evidence` field for
allergens detected via `labelText.parsed.allergens`.

Other allergen source paths (`label_warning`, `label_statement`) correctly pass
the user-readable label phrase (e.g. "Contains: Milk, Soy") into `evidence`.
Only the parsed-allergens path was leaking the dotted source path.

Fix: format as `f"Contains: {allergen_text.title()}"` to match the other
source paths and the FDA-style "Contains:" label declaration users recognize.

Contract: `evidence` strings on every allergen hit must NEVER contain a dotted
developer path like `labelText.parsed.X` or `labelText.X`.
"""

import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
logging.disable(logging.CRITICAL)

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


def _make_product(parsed_allergens):
    """Minimal product with labelText.parsed.allergens populated."""
    return {
        "id": "TEST_ALLERGEN_EVIDENCE",
        "labelText": {"parsed": {"allergens": parsed_allergens}},
        "ingredients": [],
        "statements": [],
        "compliance_data": {},
        "targetGroups": [],
    }


def test_parsed_allergen_evidence_is_user_facing(enricher):
    """`evidence` must be user-readable, not a dotted developer path."""
    product = _make_product(["fish"])
    hits = enricher._extract_allergen_presence_from_text(product)
    assert hits, "Expected at least one allergen hit for 'fish'"
    fish_hit = next((h for h in hits if h.get("allergen_id", "").lower().endswith("fish")
                     or "fish" in h.get("matched_text", "").lower()), hits[0])
    evidence = fish_hit.get("evidence", "")
    assert "labelText." not in evidence, (
        f"evidence leaked source path: {evidence!r}. "
        "Must be user-facing copy (e.g. 'Contains: Fish'), not a dotted dev path."
    )
    assert evidence.lower().startswith("contains"), (
        f"evidence should start with 'Contains:' to match label-declaration "
        f"convention (FDA style). Got: {evidence!r}"
    )


def test_parsed_allergen_evidence_titlecases_name(enricher):
    """Allergen text should be title-cased for display (Flutter renders verbatim)."""
    product = _make_product(["soy"])
    hits = enricher._extract_allergen_presence_from_text(product)
    soy_hits = [h for h in hits if "soy" in h.get("matched_text", "").lower()]
    assert soy_hits, "Expected soy allergen hit"
    evidence = soy_hits[0]["evidence"]
    assert "Soy" in evidence, f"Expected title-cased 'Soy' in evidence; got {evidence!r}"


def test_no_allergen_evidence_contains_developer_path(enricher):
    """Sweep: across all allergen source paths, evidence never carries dev paths."""
    product = {
        "id": "TEST_SWEEP",
        "labelText": {"parsed": {"allergens": ["milk", "wheat"]}},
        "ingredients": [],
        "statements": [{"text": "Contains: Milk, Wheat, Soy"}],
        "compliance_data": {},
        "targetGroups": [],
    }
    hits = enricher._extract_allergen_presence_from_text(product)
    assert hits, "Expected allergen hits"
    for h in hits:
        evidence = h.get("evidence", "") or ""
        assert "labelText." not in evidence, (
            f"Allergen {h.get('allergen_name')!r} (source={h.get('source')!r}) "
            f"leaked dev path in evidence: {evidence!r}"
        )
        assert "parsed." not in evidence, (
            f"Allergen {h.get('allergen_name')!r} leaked dotted dev field "
            f"name in evidence: {evidence!r}"
        )
