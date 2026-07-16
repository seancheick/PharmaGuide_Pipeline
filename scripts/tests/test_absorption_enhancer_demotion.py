#!/usr/bin/env python3
"""Behavior tests for E1.23 absorption-enhancer sub-threshold demotion.

Pins the contract that:
  1. Piperine ≤ 10 mg is demoted from ingredients_scorable and flagged
     role_classification=recognized_non_scorable, score_included=false.
  2. Piperine > 10 mg is NOT demoted (stays scorable as a therapeutic active).
  3. Demotion preserves product["activeIngredients"] so cluster matching
     and interaction analysis still see the ingredient.
  4. The canonical taxonomy's ``is_single_scorable_active`` fact is computed
     from the post-demotion row population. The compatibility mirror remains
     a mechanical projection of the taxonomy; it does not classify again.
  5. Demotion never touches ingredients with independent nutritional value
     (Vitamin C, Vitamin D, MK7, amino acids) — those lack the
     ``non_scorable_when_sub_threshold`` field in absorption_enhancers.json.
"""

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3(config_path=str(SCRIPTS_DIR / "config" / "enrichment_config.json"))


def _build(name, actives):
    return {
        "dsld_id": 99999,
        "product_name": name,
        "productName": name,
        "fullName": name,
        "activeIngredients": actives,
        "inactiveIngredients": [],
    }


def test_bioperine_at_or_below_10mg_is_demoted(enricher):
    product = _build("Test Ashwagandha 600 mg", [
        {"name": "Ashwagandha", "quantity": 600.0, "unit": "mg"},
        {"name": "BioPerine", "quantity": 5.0, "unit": "mg"},
    ])
    enriched, _ = enricher.enrich_product(product)
    iqd = enriched["ingredient_quality_data"]
    demoted = iqd.get("demoted_absorption_enhancers") or []
    assert len(demoted) == 1
    assert demoted[0]["enhancer_id"] == "ENHANCER_BLACK_PEPPER"
    assert demoted[0]["quantity"] == 5.0
    # Scorable count is 1 (not 2) because BioPerine demoted
    scorable = iqd.get("ingredients_scorable") or []
    assert len(scorable) == 1
    assert "ashwagandha" in (scorable[0].get("name") or "").lower()


def test_bioperine_above_10mg_stays_scorable(enricher):
    """20mg piperine appears in thermogenic blends where it's therapeutic."""
    product = _build("Metabolism Boost", [
        {"name": "Green Tea Extract", "quantity": 500.0, "unit": "mg"},
        {"name": "BioPerine", "quantity": 20.0, "unit": "mg"},
    ])
    enriched, _ = enricher.enrich_product(product)
    iqd = enriched["ingredient_quality_data"]
    demoted = iqd.get("demoted_absorption_enhancers") or []
    assert demoted == [], (
        f"BioPerine 20mg should NOT be demoted (>10mg threshold), "
        f"but got {demoted}"
    )


def test_bioperine_exactly_10mg_is_demoted(enricher):
    """Threshold is inclusive: 10mg <= 10mg."""
    product = _build("Test Curcumin 500 mg", [
        {"name": "Curcumin", "quantity": 500.0, "unit": "mg"},
        {"name": "BioPerine", "quantity": 10.0, "unit": "mg"},
    ])
    enriched, _ = enricher.enrich_product(product)
    demoted = enriched["ingredient_quality_data"].get("demoted_absorption_enhancers") or []
    assert len(demoted) == 1
    assert demoted[0]["quantity"] == 10.0


def test_demotion_preserves_activeIngredients_for_cluster_matching(enricher):
    """Critical: synergy-cluster matching must still see the enhancer."""
    product = _build("Test Ashwagandha 600 mg", [
        {"name": "Ashwagandha", "quantity": 600.0, "unit": "mg"},
        {"name": "BioPerine", "quantity": 5.0, "unit": "mg"},
    ])
    enriched, _ = enricher.enrich_product(product)
    active_names = {
        (i.get("name") or "").lower()
        for i in enriched.get("activeIngredients") or []
    }
    assert "bioperine" in active_names, (
        "BioPerine must remain in activeIngredients so cluster matching "
        "and interaction rules still see it"
    )


def test_demotion_sets_canonical_single_scorable_fact(enricher):
    """One real active plus one demoted enhancer is canonically single-active."""
    product = _build("Test Ashwagandha 600 mg", [
        {"name": "Ashwagandha", "quantity": 600.0, "unit": "mg"},
        {"name": "BioPerine", "quantity": 5.0, "unit": "mg"},
    ])
    enriched, _ = enricher.enrich_product(product)
    taxonomy = enriched["supplement_taxonomy"]
    mirror = enriched["supplement_type"]
    assert taxonomy["is_single_scorable_active"] is True
    assert taxonomy["quantified_label_active_count"] == 1
    assert mirror["type"] == taxonomy["primary_type"]
    assert mirror["active_count"] == taxonomy["quantified_label_active_count"]


def test_demotion_ignored_for_therapeutic_enhancers(enricher):
    """Vitamin C, Vitamin D, MK7, amino acids have independent nutritional
    value and must NEVER be demoted. They don't carry the
    non_scorable_when_sub_threshold field in absorption_enhancers.json."""
    product = _build("Test Iron + Vitamin C", [
        {"name": "Iron", "quantity": 18.0, "unit": "mg"},
        {"name": "Vitamin C", "quantity": 50.0, "unit": "mg"},  # enhances iron absorption
    ])
    enriched, _ = enricher.enrich_product(product)
    demoted = enriched["ingredient_quality_data"].get("demoted_absorption_enhancers") or []
    assert demoted == [], (
        f"Vitamin C has nutritional value and must not be demoted, "
        f"but got {demoted}"
    )


def test_demotion_records_provenance(enricher):
    """Audit trail must carry enhancer_id + threshold + rationale."""
    product = _build("Test Ashwagandha 600 mg", [
        {"name": "Ashwagandha", "quantity": 600.0, "unit": "mg"},
        {"name": "BioPerine", "quantity": 5.0, "unit": "mg"},
    ])
    enriched, _ = enricher.enrich_product(product)
    demoted = enriched["ingredient_quality_data"]["demoted_absorption_enhancers"][0]
    assert demoted["enhancer_id"] == "ENHANCER_BLACK_PEPPER"
    assert demoted["threshold_mg"] == 10.0
    assert "piperine" in demoted["rationale"].lower() or "bioavailability" in demoted["rationale"].lower()
    # Also verify the row itself has the provenance fields
    iqd = enriched["ingredient_quality_data"]
    all_rows = iqd.get("ingredients") or []
    bioperine_row = next(
        (r for r in all_rows if "piperine" in (r.get("name") or "").lower() or "bioperine" in (r.get("name") or "").lower()),
        None,
    )
    assert bioperine_row is not None
    assert bioperine_row.get("role_classification") == "recognized_non_scorable"
    assert bioperine_row.get("score_included") is False
    assert bioperine_row.get("demotion_reason") == "absorption_enhancer_sub_threshold"
    assert "ENHANCER_BLACK_PEPPER" in (bioperine_row.get("demotion_ref") or "")


def test_no_demotion_when_no_enhancer_present(enricher):
    """Control: a product without any absorption enhancer should produce
    an empty demoted list."""
    product = _build("Test Vitamin D 1000 IU", [
        {"name": "Vitamin D", "quantity": 1000.0, "unit": "IU"},
    ])
    enriched, _ = enricher.enrich_product(product)
    demoted = enriched["ingredient_quality_data"].get("demoted_absorption_enhancers") or []
    assert demoted == []
