#!/usr/bin/env python3
"""UC-II clinical evidence matching regression.

DSLD 182041 ("Bio-Collagen with Patented UC-II 40 mg") already resolves
to the collagen / undenatured collagen IQM form. The matching gap is
Section C: the branded clinical record BRAND_UCII exists in
backed_clinical_studies.json but was not attached because the evidence
matcher only compared exact ingredient aliases and did not extract the
UC-II brand token from the collagen row context.
"""

from __future__ import annotations

import sys
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


def test_product_name_ucii_token_can_apply_to_collagen_row(enricher):
    """Some labels put UC-II in the product name while the active row says
    only collagen/cartilage. Product-context extraction should still attach
    BRAND_UCII, but only because the row is collagen-compatible."""
    enriched, _ = enricher.enrich_product(_ucii_product("Chicken Cartilage"))

    assert "BRAND_UCII" in _clinical_ids(enriched)
