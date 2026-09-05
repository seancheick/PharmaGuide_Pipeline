"""Individually reviewed dispositions for lost botanical evidence joins.

The preferred-name correction moved several labels to narrower registry
identities that the evidence registry never named. Each family below was
reviewed against its primary source; joins are added only where the cited
review covers the source-declared preparation, and denials are explicit.
"""

from copy import deepcopy

import pytest

from clinical_applicability import filter_clinical_matches, reviewed_entries
from enrich_supplements_v3 import SupplementEnricherV3
from scoring_v4.modules.generic_evidence import resolved_clinical_matches
from test_botanical_evidence_reachability import _product


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


@pytest.mark.parametrize("product_id,label,group,canonical,standard_name,quantity,expected_id,study_id", [
    # PMID 24554461 (Cochrane 2014): 24 trials across Echinacea species and plant
    # parts, including seven trials of E. purpurea aerial-part preparations.
    ("260118", "Echinacea purpurea powder", "Echinacea", "echinacea",
     "Echinacea Purpurea", 500.0, "echinacea_purpurea_aerial", "INGR_ECHINACEA"),
    ("206905", "organic Echinacea purpurea", "Echinacea", "echinacea",
     "Echinacea Purpurea", 1200.0, "echinacea_purpurea_aerial", "INGR_ECHINACEA"),
    # PMID 37952511: 19 human studies of Astragalus (Radix Astragali, the root)
    # on immune markers; the root is the medicinal part named by "huang qi".
    ("74595", "Astragalus root powder", "Astragalus", "astragalus",
     "Astragalus", 500.0, "astragalus_root", "INGR_ASTRAGALUS"),
    ("222704", "Astragalus root powder", "Astragalus", "astragalus",
     "Astragalus", 550.0, "astragalus_root", "INGR_ASTRAGALUS"),
])
def test_source_declared_plant_part_reaches_its_reviewed_family_evidence(
    enricher, product_id, label, group, canonical, standard_name, quantity, expected_id, study_id,
):
    source = _product(product_id, label, group, canonical, standard_name, quantity, "ingredientRows[0]")
    product, issues = enricher.enrich_product(deepcopy(source))
    assert product.get("enrichment_status") != "validation_failed", issues
    active = product["activeIngredients"][0]
    assert active["canonical_id"] == expected_id
    matches, _ = resolved_clinical_matches(product)
    match = next((item for item in matches if item["id"] == study_id), None)
    assert match is not None
    assert match["matched_source_row_refs"] == ["ingredientRows[0]"]
    assert match["matched_canonical_ids"] == [expected_id]
    for field in ("name", "raw_source_text", "raw_source_path", "quantity", "unit"):
        assert active[field] == source["activeIngredients"][0][field]


@pytest.mark.parametrize("label,canonical,reason", [
    # PMID 24019277 pooled cinnamon trials in type 2 diabetes; the registry
    # family is Cassia/Cinnulin. Ceylon (Cinnamomum verum) is a different
    # species and must not borrow it.
    ("Ceylon Cinnamon Bark Extract", "ceylon_cinnamon", "clinical_identity_excluded"),
    ("Cinnamomum verum bark powder", "cinnamon_bark", "clinical_form_excluded"),
])
def test_ceylon_cinnamon_is_an_explicit_reviewed_denial(label, canonical, reason):
    source = _product("ceylon-scope", label, "Cinnamon", canonical, label, 1000.0, "ingredientRows[0]")
    match = {"id": "INGR_CINNAMON_EXTRACT", "ingredient": label,
             "matched_source_row_refs": ["ingredientRows[0]"]}
    accepted, rejected = filter_clinical_matches(source, [match])
    assert accepted == []
    assert rejected[0]["reason_code"] == reason


@pytest.mark.parametrize("product_id,label,canonical,standard_name,forms", [
    ("330605", "Ceylon Cinnamon Bark Extract", "ceylon_cinnamon", "Ceylon Cinnamon", []),
    ("271345", "Ceylon Cinnamon, Powder", "ceylon_cinnamon", "Ceylon Cinnamon",
     [{"name": "Cinnamomum verum", "category": "botanical"}]),
])
def test_ceylon_denial_is_recorded_on_the_real_label_path(enricher, product_id, label, canonical, standard_name, forms):
    source = _product(product_id, label, "Cinnamon", canonical, standard_name, 1000.0, "ingredientRows[0]")
    source["activeIngredients"][0]["forms"] = deepcopy(forms)
    source["activeIngredients"][0]["raw_taxonomy"]["forms"] = deepcopy(forms)
    product, issues = enricher.enrich_product(deepcopy(source))
    assert product.get("enrichment_status") != "validation_failed", issues
    matches, _ = resolved_clinical_matches(product)
    assert "INGR_CINNAMON_EXTRACT" not in {item["id"] for item in matches}
    rejected = product["evidence_data"].get("rejected_clinical_matches") or []
    reasons = {item.get("id"): item.get("reason_code") for item in rejected}
    assert reasons.get("INGR_CINNAMON_EXTRACT") == "clinical_identity_excluded"


def test_cassia_cinnamon_preparation_keeps_its_evidence():
    source = _product("cassia-scope", "Cinnamon bark extract", "Cinnamon", "cinnamon_bark",
                      "Cinnamon Bark", 500.0, "ingredientRows[0]")
    match = {"id": "INGR_CINNAMON_EXTRACT", "ingredient": "Cinnamon bark extract",
             "matched_source_row_refs": ["ingredientRows[0]"]}
    accepted, rejected = filter_clinical_matches(source, [match])
    assert rejected == []
    assert [item["id"] for item in accepted] == ["INGR_CINNAMON_EXTRACT"]


@pytest.mark.parametrize("study_id,labels", [
    # PMID 32010325 concerns garlic supplements / Kyolic aged garlic extract;
    # fermented black garlic is a different preparation with no reviewed join.
    ("INGR_GARLIC", ["Black Garlic Bulb Extract", "Black Garlic", "S-Allyl Cysteine"]),
    # PRECLIN_RESVERATROL pools isolated resveratrol trials; a 60 mg whole
    # red-grape extract is not an isolated-resveratrol intervention.
    ("PRECLIN_RESVERATROL", ["BioVin Advanced", "Grape", "Red Grape Extract"]),
    # INGR_DIGESTIVE_ENZYMES cites a multi-enzyme dyspepsia trial; a DPP-IV
    # gluten/dairy protease product is not that intervention.
    ("INGR_DIGESTIVE_ENZYMES", ["BioCore DPP-IV", "Digestive Enzymes"]),
])
def test_unreviewed_preparations_do_not_reach_family_evidence(enricher, study_id, labels):
    assert enricher._clinical_study_match(labels, reviewed_entries()[study_id]) is None


@pytest.mark.parametrize("study_id", ["INGR_ECHINACEA", "INGR_ASTRAGALUS", "INGR_CINNAMON_EXTRACT"])
def test_reviewed_join_adds_no_dose_threshold_or_strength_change(study_id):
    entry = reviewed_entries()[study_id]
    assert "min_clinical_dose" not in entry
    assert "minimum_daily_dose" not in (entry.get("applicability") or {})
    assert "dose_unit" not in (entry.get("applicability") or {})


# --- Independent review of the 5.3.11 botanical patch on real labels --------


def _scoped_source(label, group, canonical, standard_name, quantity, forms):
    source = _product("patch-review", label, group, canonical, standard_name, quantity, "ingredientRows[0]")
    row = source["activeIngredients"][0]
    row["forms"] = [{"name": name, "category": "botanical"} for name in forms]
    row["raw_taxonomy"]["forms"] = deepcopy(row["forms"])
    return source


@pytest.mark.parametrize("label,forms", [
    ("Boswellia serrata gum extract", []),                               # 74761, 273861, 47945/75017
    ("Boswellia serrata AKBA standardized extract (wood) resin", ["extract", "standardized"]),  # 12196
    ("Apres-Flex", []),                                                  # 19436 (label spelling of ApresFlex)
    ("Casperome", ["Indian Frankincense Phytosome"]),                    # 337853, 337859
])
def test_boswellia_extract_preparations_on_real_labels_reach_family_evidence(label, forms):
    source = _scoped_source(label, "Boswellia", "boswellia", "Boswellia Serrata", 100.0, forms)
    match = {"id": "PRECLIN_BOSWELLIA", "ingredient": label, "matched_source_row_refs": ["ingredientRows[0]"]}
    accepted, rejected = filter_clinical_matches(source, [match])
    assert rejected == []
    assert [item["id"] for item in accepted] == ["PRECLIN_BOSWELLIA"]


def test_bare_boswellia_serrata_row_stays_denied_until_source_proves_extract():
    # 243146: product title says extract, the source row says only
    # "Boswellia serrata" with a boswellic-acid form. Recorded as ambiguous.
    source = _scoped_source("Boswellia serrata", "Boswellia", "boswellia", "Boswellia Serrata", 450.0, ["Boswellic Acid"])
    match = {"id": "PRECLIN_BOSWELLIA", "ingredient": "Boswellia serrata", "matched_source_row_refs": ["ingredientRows[0]"]}
    accepted, rejected = filter_clinical_matches(source, [match])
    assert accepted == []
    assert rejected[0]["reason_code"] == "clinical_form_mismatch"


def test_misspelled_generic_cinnamon_label_keeps_family_evidence():
    # 62194 Spring Valley prints "Cinnammon"; the cleaner mapped it correctly.
    source = _scoped_source("Cinnammon", "Cinnamon", "cinnamon", "Cinnamon", 1000.0, [])
    match = {"id": "INGR_CINNAMON_EXTRACT", "ingredient": "Cinnammon", "matched_source_row_refs": ["ingredientRows[0]"]}
    accepted, rejected = filter_clinical_matches(source, [match])
    assert rejected == []
    assert [item["id"] for item in accepted] == ["INGR_CINNAMON_EXTRACT"]


@pytest.mark.parametrize("product_id,label,quantity", [
    ("184792", "PACRAN Cranberry (Vaccinium macrocarpon) powder", 300.0),
    ("74399", "Pacran Cranberry concentrate powder", 250.0),
])
def test_scorer_recovery_carries_its_row_reference_through_a_source_required_scope(enricher, product_id, label, quantity):
    # Old code credited these fruit powders through scoring-contract recovery.
    # The 5.3.11 source-required cranberry scope must evaluate the exact row
    # the recovery came from, not reject every recovered entry as unresolved.
    source = _product(product_id, label, "Cranberry", "cranberry", "Cranberry Concentrate", quantity, "ingredientRows[0]")
    product, issues = enricher.enrich_product(deepcopy(source))
    assert product.get("enrichment_status") != "validation_failed", issues
    assert [m["id"] for m in product["evidence_data"]["clinical_matches"]] == []
    matches, recovered = resolved_clinical_matches(product)
    match = next((item for item in matches if item["id"] == "INGR_CRANBERRY"), None)
    assert match is not None
    assert match.get("evidence_origin") == "scoring_contract_recovery"
    assert match["matched_source_row_refs"] == ["ingredientRows[0]"]
    assert [item["id"] for item in recovered] == ["INGR_CRANBERRY"]


def test_scorer_recovery_still_respects_the_source_required_exclusion(enricher):
    source = _product("seed-oil", "Cranberry seed oil", "Cranberry", "cranberry", "Cranberry Concentrate", 500.0, "ingredientRows[0]")
    product, _ = enricher.enrich_product(deepcopy(source))
    matches, recovered = resolved_clinical_matches(product)
    assert "INGR_CRANBERRY" not in {item["id"] for item in matches}
    assert recovered == []


def test_boswellia_primary_outcome_uses_the_locked_vocabulary():
    entry = reviewed_entries()["PRECLIN_BOSWELLIA"]
    assert entry["primary_outcome"] == "Joint & Bone Health"
