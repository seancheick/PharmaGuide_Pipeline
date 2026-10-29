#!/usr/bin/env python3
"""UC-II discovery and qualified material attribution.

The May 26 matcher fix discovers a branded candidate from compatible product
context. Discovery does not prove that a generic cartilage row is the exact
UC-II preparation. Current clinical applicability requires a source-bound
material relationship; it has no title-to-generic-row preparation proof.
Actual DSLD182041 names UC-II on its retained ingredient row and stays positive.
"""

from __future__ import annotations

import sys
import json
from copy import deepcopy
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3(
        config_path=str(SCRIPTS_DIR / "config" / "enrichment_config.json")
    )


def _ucii_product(active_name: str = "UC-II standardized Cartilage") -> dict:
    return {
        "id": "182041",
        "dsld_id": "182041",
        "fullName": "Bio-Collagen with Patented UC-II 40 mg",
        "product_name": "Bio-Collagen with Patented UC-II 40 mg",
        "brandName": "Life Extension",
        "brand_name": "Life Extension",
        "activeIngredients": [
            {
                "name": active_name,
                "standardName": "Collagen",
                "canonical_id": "collagen",
                "canonical_source_db": "ingredient_quality_map",
                "cleaner_row_role": "active_scorable",
                "score_eligible_by_cleaner": True,
                "raw_source_text": active_name,
                "raw_source_path": "ingredientRows[0]",
                "quantity": 40.0,
                "unit": "mg",
                "forms": [{"name": "standardized", "source": "name_extraction"}],
            }
        ],
        "inactiveIngredients": [],
    }


def _clinical_ids(enriched: dict) -> set[str]:
    return {
        str(m.get("id") or m.get("study_id"))
        for m in enriched.get("evidence_data", {}).get("clinical_matches", [])
        if m.get("id") or m.get("study_id")
    }


def test_182041_ucii_matches_undenatured_collagen_form(enricher):
    """Guard the part that already works: UC-II must stay on the
    undenatured collagen form, not generic collagen."""
    enriched, _ = enricher.enrich_product(_ucii_product())
    rows = enriched["ingredient_quality_data"]["ingredients_scorable"]

    assert len(rows) == 1
    row = rows[0]
    assert row.get("canonical_id") == "collagen"
    assert row.get("matched_form") == "undenatured collagen"
    assert row.get("bio_score") == 9.0


def test_182041_ucii_attaches_brand_clinical_evidence(enricher):
    """The Life Extension UC-II product must attach the existing
    BRAND_UCII clinical record so Section C is not silently zero."""
    enriched, _ = enricher.enrich_product(_ucii_product())

    assert "BRAND_UCII" in _clinical_ids(enriched)


def test_title_ucii_discovers_candidate_but_does_not_prove_generic_cartilage_material(enricher):
    """Keep contextual discovery, without treating its global token as a
    verified title-to-row material relationship. No ruling bans titles; this
    owner's existing source contract supplies no such preparation proof."""
    product = _ucii_product("Chicken Cartilage")
    row = product["activeIngredients"][0]
    token = enricher._product_context_branded_token_for_ingredient(
        product["product_name"], row, row["name"], row["standardName"])
    assert token == "UC-II"
    enriched, _ = enricher.enrich_product(product)
    assert "BRAND_UCII" not in _clinical_ids(enriched)
    rejected = next(m for m in enriched["evidence_data"]["rejected_clinical_matches"]
                    if m.get("id") == "BRAND_UCII")
    assert rejected["reason_code"] == "clinical_form_mismatch"


def test_real_182041_retained_source_qualifies_exact_ucii_material(enricher):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    raw = json.loads((Path(__file__).parent / "fixtures/ucii_182041_raw.json").read_text())
    assert raw["ingredientRows"][0]["name"] == "UC-II standardized Cartilage"
    enriched, errors = enricher.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    assert not errors
    assert "BRAND_UCII" in _clinical_ids(enriched)
    match = next(m for m in enriched["evidence_data"]["clinical_matches"] if m.get("id") == "BRAND_UCII")
    assert match["matched_source_row_refs"] == ["ingredientRows[0]"]
    assert match["ingredient"] == raw["ingredientRows"][0]["name"]
    assert match["applicability_assessment"]["status"] == "applicable"


@pytest.mark.parametrize("shape", ["generic", "wrong_material", "multiple_generic"])
def test_title_ucii_cannot_lend_material_identity_to_unproven_rows(enricher, shape):
    product = _ucii_product("Undenatured Collagen II")
    if shape == "wrong_material":
        product["activeIngredients"][0].update(name="Calcium carbonate", standardName="Calcium",
            raw_source_text="Calcium carbonate", canonical_id="calcium", forms=[])
    if shape == "multiple_generic":
        companion = deepcopy(product["activeIngredients"][0])
        companion.update(name="Chicken Cartilage", raw_source_text="Chicken Cartilage",
                         raw_source_path="ingredientRows[1]", quantity=200)
        product["activeIngredients"].append(companion)
    enriched, _ = enricher.enrich_product(product)
    assert "BRAND_UCII" not in _clinical_ids(enriched)


def test_exact_ucii_source_remains_qualified_beside_generic_cartilage(enricher):
    product = _ucii_product()
    companion = deepcopy(product["activeIngredients"][0])
    companion.update(name="Chicken Cartilage", raw_source_text="Chicken Cartilage",
                     raw_source_path="ingredientRows[1]", quantity=200)
    product["activeIngredients"].append(companion)
    enriched, _ = enricher.enrich_product(product)
    assert "BRAND_UCII" in _clinical_ids(enriched)
    match = next(m for m in enriched["evidence_data"]["clinical_matches"] if m.get("id") == "BRAND_UCII")
    assert match["matched_source_row_refs"] == ["ingredientRows[0]"]
    assert match["ingredient"] == "UC-II standardized Cartilage"
