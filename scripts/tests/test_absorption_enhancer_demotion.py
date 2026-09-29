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

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402


DATA_PATH = SCRIPTS_DIR / "data" / "absorption_enhancers.json"


def test_piperine_threshold_is_explicitly_governed_as_product_policy():
    payload = json.loads(DATA_PATH.read_text())
    entry = next(
        row
        for row in payload["absorption_enhancers"]
        if row["id"] == "ENHANCER_BLACK_PEPPER"
    )
    policy = entry["non_scorable_when_sub_threshold"]

    assert payload["_metadata"]["schema_version"] == "5.1.1"
    assert payload["_metadata"]["last_updated"] == "2026-09-29"
    assert policy["threshold_basis"] == "classification_convention"
    rationale = policy["rationale"].lower()
    assert "not a clinically established boundary" in rationale
    assert "pmid 10715596" in rationale
    assert "pmid 9619120" in rationale
    assert "20 mg/kg" in rationale and "animal arm" in rationale


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3(config_path=str(SCRIPTS_DIR / "config" / "enrichment_config.json"))


def _build(name, actives):
    return {
        "dsld_id": 99999,
        "product_name": name,
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


def _enrich_fixture(name):
    import logging
    from enhanced_normalizer import EnhancedDSLDNormalizer

    logging.disable(logging.INFO)
    raw = json.loads((Path(__file__).parent / "fixtures" / name).read_text())
    enriched, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    return enriched


def _scored_canonicals(enriched):
    from scoring_input_contract import get_scoring_ingredients

    return {r.get("canonical_id") for r in get_scoring_ingredients(enriched, strict=True).rows}


def test_a_demoted_absorption_aid_is_not_projected_back_into_scoring():
    """229934 Turmerich Joint: the enricher demotes BioPerine 5 mg, and the
    compatibility anchor projection (identity_bearing_active_anchor_mass) put
    it back as a scored active: all 114 demoted products in the 2026-09-29
    corpus scored piperine anyway."""
    enriched = _enrich_fixture("enhancer_demoted_229934_raw.json")
    assert enriched["ingredient_quality_data"]["demoted_absorption_enhancers"]
    assert "piperine" not in _scored_canonicals(enriched)
    # Still on the label, so it still pairs with the turmeric it enhances (A4).
    assert enriched["absorption_enhancer_paired"] is True


def test_piperine_read_under_its_iqm_name_is_demoted_and_pairs_with_curcumin():
    """182824 prints "Bioperine Black Pepper (Piper nigrum) extract" 5.3 mg. Enhancer
    matching is by name and the row's IQM name "Piperine (Black Pepper Extract)" was
    no alias: 44 rows of <= 10 mg piperine were never demoted, and the label earned
    no curcumin pairing (A4) while piperine owned its Evidence."""
    from evidence_resolver import evidence_owner_canonicals

    enriched = _enrich_fixture("brand_generic_182824_raw.json")
    demoted = enriched["ingredient_quality_data"]["demoted_absorption_enhancers"]
    assert [d["enhancer_id"] for d in demoted] == ["ENHANCER_BLACK_PEPPER"]
    assert "piperine" not in _scored_canonicals(enriched)
    assert "piperine" not in evidence_owner_canonicals(enriched)
    assert enriched["absorption_enhancer_paired"] is True
