"""Held label identities resolve without borrowing constituent or form ratings."""

import pytest
from copy import deepcopy
import json
from pathlib import Path

from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def normalizer():
    return EnhancedDSLDNormalizer()


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


@pytest.mark.parametrize("literal,canonical,registry", [
    ("organic Hemp Oil extract", "NHA_HEMP_EXTRACT", "other_ingredients"),
    ("Hemp Oil (aerial plant parts) extract", "NHA_HEMP_EXTRACT", "other_ingredients"),
    ("Hemp Oil extract", "NHA_HEMP_EXTRACT", "other_ingredients"),
    ("Broad Spectrum Phytocannabinoids", "NHA_PHYTOCANNABINOIDS", "other_ingredients"),
    ("Alginic Acid", "NHA_ALGINIC_ACID", "other_ingredients"),
    ("Maltodextrin", "NHA_MALTODEXTRIN", "other_ingredients"),
    ("Oxyphyte Apple powder extract", "apple_powder_extract", "botanical_ingredients"),
    ("Calendula", "calendula", "botanical_ingredients"),
    ("Mixed-Carotenoids", "total_carotenoids", "ingredient_quality_map"),
    ("EpiCor dried Yeast Fermentate Complex", "epicor", "standardized_botanicals"),
])
def test_exact_label_preparation_owner(enricher, literal, canonical, registry):
    assert enricher._current_canonical_identity_registry().resolve_verified_preferred(literal) == (
        canonical, registry,
    )


def test_epicor_whole_fermentate_is_not_blend_total(normalizer):
    raw = {
        "name": "EpiCor dried Yeast Fermentate Complex", "category": "other",
        "ingredientGroup": "Saccharomyces cerevisiae", "nestedRows": [],
        "quantity": [{"quantity": 250, "unit": "mg"}],
        "forms": [{"name": "Saccharomyces cerevisiae", "prefix": "from"}],
    }
    assert not normalizer._is_dsld_active_blend_total_row(raw)
    assert normalizer._is_dsld_active_blend_total_row({
        **raw, "name": "Proprietary Fermentate Blend", "category": "blend",
        "ingredientGroup": "Proprietary Blend",
    })
    assert normalizer._is_dsld_active_blend_total_row({
        **raw, "nestedRows": [{"name": "Undisclosed component"}],
    })


def test_prenatal_transcription_correction_is_product_scoped(normalizer):
    raw = [{"name": "Dextrose", "category": "sugar", "ingredientGroup": "Glucose",
            "uniiCode": "IY9XDZ35W2", "quantity": [{"quantity": 200, "unit": "mg"}],
            "forms": [{"name": "Glucose", "uniiCode": "5SL0G7R0OK"}]}]
    corrected = normalizer._apply_label_corrections(deepcopy(raw), "178711")[0]
    assert corrected["name"] == "DHA"
    assert corrected["ingredientGroup"] == "DHA"
    assert corrected["uniiCode"] is None
    assert corrected["forms"][0]["name"] == "Schizochytrium sp. oil"
    assert corrected["quantity"] == raw[0]["quantity"]
    assert corrected["_pre_correction_name"] == "Dextrose"
    assert normalizer._apply_label_corrections(deepcopy(raw), "different-label") == raw


def test_tagetes_marigold_does_not_borrow_calendula_identifiers():
    data = json.loads((Path(__file__).parents[1] / "data/standardized_botanicals.json").read_text())
    entry = next(row for row in data["standardized_botanicals"] if row["id"] == "marigold")
    assert entry.get("external_ids", {}).get("unii") != "18E7415PXQ"
    assert entry.get("rxcui") != "1309775"


def test_maltodextrin_primary_identity_retains_separate_safety_owner(enricher):
    registry = enricher._current_canonical_identity_registry()
    assert registry.resolve_verified_preferred("Maltodextrin") == (
        "NHA_MALTODEXTRIN", "other_ingredients",
    )
    # The safety entry and its exact recognition remain; primary identity does
    # not delete or downgrade it, nor turn an undosed blend leaf into350mg.
    entry = next(row for row in enricher.databases["harmful_additives"]["harmful_additives"]
                 if row["id"] == "ADD_MALTODEXTRIN")
    assert "maltodextrin" in entry["aliases"]
    assert entry["severity_level"] == "low"


@pytest.mark.parametrize("literal", ["CBD", "Cannabidiol", "Sodium Alginate", "Hemp Seed Oil"])
def test_near_names_do_not_become_extract_or_acid(enricher, literal):
    resolved = enricher._current_canonical_identity_registry().resolve_preferred(literal)
    assert resolved not in {
        ("NHA_HEMP_EXTRACT", "other_ingredients"),
        ("NHA_PHYTOCANNABINOIDS", "other_ingredients"),
        ("NHA_ALGINIC_ACID", "other_ingredients"),
    }


@pytest.mark.parametrize("literal", [
    "Hemp Oil extract", "Broad Spectrum Phytocannabinoids", "Alginic Acid",
])
def test_preparation_recognition_does_not_invent_iqm_rating(enricher, literal):
    product, issues = enricher.enrich_product({
        "id": "mapping-contract", "fullName": "Preparation",
        "activeIngredients": [{
            "name": literal, "raw_source_text": literal,
            "raw_source_path": "ingredientRows[0]", "quantity": 50, "unit": "mg",
            "source_section": "active", "cleaner_row_role": "active_scorable",
            "score_eligible_by_cleaner": True, "forms": [],
        }], "inactiveIngredients": [],
    })
    assert product, issues
    row = product["ingredient_quality_data"]["ingredients"][0]
    assert row["canonical_id"] is not None
    assert row["canonical_source_db"] == "other_ingredients"
    assert row["bio_score"] is None
    assert row["final_form_bio_score"] is None
    assert row["source_label_name"] == literal



def test_primary_maltodextrin_has_source_supported_display_role():
    data = json.loads((Path(__file__).parents[1] / "data/other_ingredients.json").read_text())
    entry = next(r for r in data["other_ingredients"] if r["id"] == "NHA_MALTODEXTRIN")
    assert entry["category"] == "filler"
    assert entry["functional_roles"] == ["filler"]
    assert "cargill.com/food-bev/na/maltodextrin" in entry["notes"]
    assert "individual product" in entry["notes"]
