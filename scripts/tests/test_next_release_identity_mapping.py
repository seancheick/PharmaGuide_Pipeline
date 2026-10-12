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


@pytest.mark.parametrize('name,canonical,amount,unit,form', [
    ('Palmitoleic Acid', 'palmitoleic_acid', 210, 'mg', 'Provinal'),
    ('Caprylic Acid', 'mct_oil', 14, 'g', 'Medium Chain Triglycerides'),
])
def test_measured_fatty_acid_keeps_cleaner_identity(normalizer, enricher, name, canonical, amount, unit, form):
    from scoring_input_contract import get_scoring_ingredients
    raw = {'id': 'fatty-identity', 'fullName': name, 'brandName': 'Test',
           'ingredientRows': [{'name': name, 'ingredientGroup': name,
               'category': 'fatty acid', 'order': 1, 'nestedRows': [],
               'forms': [{'name': form}], 'quantity': [{'quantity': amount, 'unit': unit}]}],
           'otheringredients': {'ingredients': []}}
    cleaned = normalizer.normalize_product(raw)
    active = cleaned['activeIngredients'][0]
    assert active['score_eligible_by_cleaner'] is True
    assert active['canonical_id'] == canonical
    enriched, issues = enricher.enrich_product(cleaned)
    scoring = get_scoring_ingredients(enriched)
    assert scoring.mapped_count == 1, issues
    assert scoring.unmapped_count == 0
    assert scoring.rows[0]['canonical_id'] == canonical
    assert scoring.rows[0]['quantity'] == amount
    assert scoring.mapped_coverage == 1.0


@pytest.mark.parametrize('name', ['Total Fat', 'Other Omega-3 Fatty Acids', 'Palmitoleic Acid'])
def test_fatty_nutrition_rollup_stays_excluded(enricher, name):
    row = {'name': name, 'raw_source_text': name, 'quantity': 210, 'unit': 'mg',
           'raw_category': 'fat', 'source_section': 'active',
           'cleaner_row_role': 'nutrition_rollup', 'score_eligible_by_cleaner': False,
           'canonical_id': 'palmitoleic_acid', 'canonical_source_db': 'ingredient_quality_map'}
    assert enricher._should_skip_from_scoring(row, {}, {}) in {'excluded_nutrition_fact', 'blend_header_total_weight_only'}


@pytest.mark.parametrize('name,canonical', [
    ('Cannabidiol', 'NHA_CANNABIDIOL'),
    ('Sulbutiamine', 'NHA_SULBUTIAMINE'),
    ('3,3-Azo-17a-Methyl-5a-Androstan-17b-Ol', 'NHA_METHYLDIAZIRINOL'),
    ('2, 17a-Dimethyl-17b-Hydroxy-5a-Androst-2-Ene', 'NHA_DIMETHANDROSTENOL'),
])
def test_verified_blocked_identity_never_restores_quality(normalizer, enricher, name, canonical):
    from scoring_v4.scored_artifact import build_scored_artifact
    from scoring_input_contract import get_scoring_ingredients
    raw = {'id': 'blocked-identity', 'fullName': name, 'brandName': 'Test',
           'ingredientRows': [{'name': name, 'ingredientGroup': name,
               'category': 'non-nutrient/non-botanical', 'order': 1,
               'nestedRows': [], 'forms': [], 'quantity': [{'quantity': 25, 'unit': 'mg'}]}],
           'otheringredients': {'ingredients': []}}
    enriched, issues = enricher.enrich_product(normalizer.normalize_product(raw))
    ingredient = enriched['ingredient_quality_data']['ingredients'][0]
    assert ingredient['canonical_id'] == canonical, issues
    assert ingredient['bio_score'] is None
    scoring = get_scoring_ingredients(enriched)
    assert scoring.unmapped_count == 0
    scored = build_scored_artifact(enriched)
    assert scored['quality_score_status'] == 'suppressed_safety'
    assert scored['quality_score_v4_100'] is None
    assert scored['product_safety_status'] == 'blocked'


@pytest.mark.parametrize('name', ['Cannabidiolic acid', 'Sulbutiamine Hydrochloride',
    'Hemp Seed Oil', '17a-Ethyl-Estr-5(6)-Ene-3B-Diol'])
def test_near_name_does_not_borrow_new_chemical_identity(enricher, name):
    canonical = enricher._current_canonical_identity_registry().resolve_verified_preferred(name)
    assert not canonical or canonical[0] not in {
        'NHA_CANNABIDIOL', 'NHA_SULBUTIAMINE', 'NHA_METHYLDIAZIRINOL', 'NHA_DIMETHANDROSTENOL'}


@pytest.mark.parametrize('name', ['Palmitoleic Acid', 'Total Fat'])
def test_real_nutrition_panel_does_not_become_fatty_active(normalizer, enricher, name):
    from scoring_input_contract import get_scoring_ingredients
    raw = {'id': 'oil-panel', 'fullName': 'Oil nutrition disclosure', 'brandName': 'Test',
           'ingredientRows': [{'name': name, 'ingredientGroup': name, 'category': 'fat',
               'order': 1, 'nestedRows': [], 'forms': [],
               'quantity': [{'quantity': 1, 'unit': 'Gram(s)'}]}],
           'otheringredients': {'ingredients': []}}
    cleaned = normalizer.normalize_product(raw)
    assert not any(x.get('score_eligible_by_cleaner') is True for x in cleaned['activeIngredients'])
    enriched, issues = enricher.enrich_product(cleaned)
    scoring = get_scoring_ingredients(enriched)
    assert scoring.mapped_count == scoring.unmapped_count == 0, issues
    assert scoring.mapped_coverage == 0.0


def test_fatty_acid_oil_profile_keeps_its_existing_exclusion(normalizer, enricher):
    from scoring_input_contract import get_scoring_ingredients
    raw = {'id': 'oil-composition', 'fullName': 'Flaxseed Oil 1250 mg', 'brandName': 'Test',
           'ingredientRows': [{'name': 'Flaxseed Oil', 'ingredientGroup': 'Flaxseed Oil',
               'category': 'fat', 'order': 1, 'forms': [],
               'quantity': [{'quantity': 1250, 'unit': 'mg'}],
               'nestedRows': [{'name': 'Oleic Acid', 'ingredientGroup': 'Oleic Acid',
                   'category': 'fatty acid', 'order': 2, 'forms': [], 'nestedRows': [],
                   'quantity': [{'quantity': 200, 'unit': 'mg'}]}]}],
           'otheringredients': {'ingredients': []}}
    enriched, issues = enricher.enrich_product(normalizer.normalize_product(raw))
    scoring = get_scoring_ingredients(enriched)
    assert not any(x.get('canonical_id') == 'oleic_acid' for x in scoring.rows), issues
    leaf = next(x for x in enriched['ingredient_quality_data']['ingredients'] if x['name'] == 'Oleic Acid')
    assert leaf['skip_reason'] == 'excluded_nutrition_fact'


def test_sole_omega_total_is_not_a_discrete_fatty_acid(enricher):
    # Cleaner-owned generic total reaches the same exclusion seam as a
    # discrete fatty acid, but still has no constituent-specific quantity.
    row = {'name': 'Total Omega-3 Fatty Acids',
           'raw_source_text': 'Total Omega-3 Fatty Acids',
           'raw_category': 'fatty acid', 'quantity': 600, 'unit': 'mg',
           'cleaner_row_role': 'active_scorable', 'score_eligible_by_cleaner': True,
           'canonical_id': 'fish_oil', 'canonical_source_db': 'ingredient_quality_map',
           '_sole_active_row': True, 'forms': []}
    assert enricher._should_skip_from_scoring(row, {}, {}) == 'excluded_nutrition_fact'
