"""Reviewed preparation names must survive registry-owned identity projection."""

from copy import deepcopy

import pytest

from clinical_applicability import filter_clinical_matches, reviewed_entries
from enrich_supplements_v3 import SupplementEnricherV3
from scoring_v4.modules.generic_evidence import resolved_clinical_matches


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


def _product(product_id, label, group, canonical, standard_name, quantity, source_ref):
    row = {
        "name": label, "raw_source_text": label, "standardName": standard_name,
        "canonical_id": canonical, "canonical_source_db": "ingredient_quality_map",
        "ingredientGroup": group, "raw_category": "botanical",
        "raw_source_path": source_ref, "quantity": quantity, "unit": "mg",
        "forms": [], "raw_taxonomy": {
            "category": "botanical", "ingredientGroup": group,
            "forms": [], "isNestedIngredient": False,
        },
        "cleaner_row_role": "active_scorable", "score_eligible_by_cleaner": True,
        "dose_class": "therapeutic_mass", "source_section": "active",
        "nestedIngredients": [], "isNestedIngredient": False,
    }
    return {"id": product_id, "fullName": label, "activeIngredients": [row],
            "inactiveIngredients": []}


@pytest.mark.parametrize("product_id,label,group,canonical,standard_name,quantity,source_ref,expected_id,study_id", [
    ("311175", "Boswellia serrata Resin Extract", "Boswellia", "boswellia",
     "Boswellia Serrata", 1000.0, "ingredientRows[0]", "boswellia_serrata_resin", "PRECLIN_BOSWELLIA"),
    ("259627", "Cranberry fruit concentrate", "Cranberry", "cranberry",
     "Cranberry Extract", 600.0, "ingredientRows[0]", "cranberry_fruit", "INGR_CRANBERRY"),
    ("333698", "Cranberry Fruit Concentrate", "Cranberry", "cranberry",
     "Cranberry Extract", 500.0, "ingredientRows[2]", "cranberry_fruit", "INGR_CRANBERRY"),
])
def test_source_declared_preparation_reaches_its_existing_evidence(
    enricher, product_id, label, group, canonical, standard_name, quantity,
    source_ref, expected_id, study_id,
):
    source = _product(product_id, label, group, canonical, standard_name, quantity, source_ref)
    product, issues = enricher.enrich_product(deepcopy(source))
    assert product.get("enrichment_status") != "validation_failed", issues
    active = product["activeIngredients"][0]
    assert active["canonical_id"] == expected_id
    matches, _ = resolved_clinical_matches(product)
    match = next((item for item in matches if item["id"] == study_id), None)
    assert match is not None
    assert match["matched_source_row_refs"] == [source_ref]
    assert match["matched_canonical_ids"] == [expected_id]
    for field in ("name", "raw_source_text", "raw_source_path", "forms", "quantity", "unit"):
        assert active[field] == source["activeIngredients"][0][field]


@pytest.mark.parametrize("study_id,label", [
    ("PRECLIN_BOSWELLIA", "Boswellia serrata resin powder"),
    ("PRECLIN_BOSWELLIA", "Boswellia essential oil"),
    ("INGR_CRANBERRY", "Cranberry seed oil"),
    ("INGR_CRANBERRY", "Cranberry leaf extract"),
])
def test_stale_generic_match_cannot_supply_a_different_preparation(study_id, label):
    source = _product("wrong-preparation", label, "Botanical", "unknown", label,
                      500.0, "ingredientRows[0]")
    match = {"id": study_id, "ingredient": label,
             "matched_source_row_refs": ["ingredientRows[0]"]}
    accepted, rejected = filter_clinical_matches(source, [match])
    assert accepted == []
    assert rejected[0]["reason_code"] == "clinical_form_excluded"


@pytest.mark.parametrize("study_id,unsupported", [
    ("PRECLIN_BOSWELLIA", {"Reduce Stress/Anxiety", "Healthy Aging/Longevity"}),
    ("INGR_CRANBERRY", {"Immune Support"}),
])
def test_reviewed_endpoints_do_not_inherit_unrelated_automatic_claims(study_id, unsupported):
    entry = reviewed_entries()[study_id]
    assert not unsupported.intersection(entry["health_goals_supported"])
    assert entry["primary_outcome"] not in unsupported
    assert "registry_completed_trials_count" not in entry
    assert "no automated downgrade signals" not in entry["effect_direction_rationale"]


@pytest.mark.parametrize("study_id,enrollment", [
    ("PRECLIN_BOSWELLIA", 545), ("INGR_CRANBERRY", 8857),
])
def test_enrollment_is_one_verified_review_not_automatic_registry_arithmetic(study_id, enrollment):
    entry = reviewed_entries()[study_id]
    assert entry["total_enrollment"] == enrollment
    assert "not summed" in entry["notes"]
    # Family-level evidence is not a studied milligram threshold, nor a new
    # approval of a generic preparation as equivalent to a named trial product.
    assert "min_clinical_dose" not in entry
    assert "minimum_daily_dose" not in entry["applicability"]
    assert "dose_unit" not in entry["applicability"]


def test_whole_plant_identifier_is_not_a_boswellia_extract_identifier():
    assert "unii" not in reviewed_entries()["PRECLIN_BOSWELLIA"].get("external_ids", {})


@pytest.mark.parametrize("label", ["AKBA", "Boswellic Acids"])
def test_isolated_constituent_does_not_identify_a_studied_whole_extract(enricher, label):
    assert enricher._clinical_study_match([label], reviewed_entries()["PRECLIN_BOSWELLIA"]) is None
