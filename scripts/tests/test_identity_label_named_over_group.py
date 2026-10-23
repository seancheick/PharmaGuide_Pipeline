"""Real DSLD labels: a printed ingredient keeps the identity its label names (ADR-0005).

The line integrity audit (2026-10-19, F1) found the enricher replacing an identity the printed
name proves with the identity of DSLD's coarse ingredientGroup: organic Wheat Grass exported as
"Couch Grass", Green Bell Pepper as chili pepper, Lactococcus cremoris as L. lactis, Ginger root
Olive leaf extract as olive fruit extract (losing its interaction rule).
A "Proprietary Blend" group still classifies a branded complex as a blend. Genuine repairs (a "Vitamin E" row first matched to its
sunflower-oil source, "Charcoal, Activated" first matched to MCT oil) must stay repaired.
"""
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def pipeline():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    logging.disable(logging.INFO)
    return EnhancedDSLDNormalizer(), SupplementEnricherV3()


@pytest.fixture(scope="module")
def products(pipeline):
    from build_final_db import build_detail_blob
    from scoring_v4.scored_artifact import build_scored_artifact

    normalizer, enricher = pipeline
    out = {}
    for path in sorted(FIXTURES.glob("identity_*_raw.json")):
        cleaned = normalizer.normalize_product(json.loads(path.read_text()))
        enriched, _ = enricher.enrich_product(cleaned)
        out[path.stem.split("_")[-2]] = (enriched, build_detail_blob(enriched, build_scored_artifact(enriched)))
    return out


def _row(enriched, path):
    [row] = [r for r in enriched["ingredient_quality_data"]["ingredients"] if r.get("raw_source_path") == path]
    return row


def _rules(enriched):
    profile = enriched.get("interaction_profile") or {}
    return {rule for summary in (profile.get("condition_summary") or {}).values() for rule in summary.get("rule_ids", [])}


@pytest.mark.parametrize("dsld_id,path,canonical,display", [
    ("178716", "ingredientRows[8].nestedRows[0]", "wheatgrass", "organic Wheat Grass"),
    ("174600", "ingredientRows[22].nestedRows[9]", "green_bell_pepper", "organic Green Bell Pepper"),
    ("174659", "ingredientRows[4].nestedRows[9]", "lactococcus_cremoris", "Lactococcus cremoris"),
    ("212273", "ingredientRows[0].nestedRows[1]", "olive_leaf", "Olive leaf extract"),
])
def test_label_named_identity_is_not_replaced_by_its_dsld_group(products, dsld_id, path, canonical, display):
    enriched, blob = products[dsld_id]
    row = _row(enriched, path)
    assert row["canonical_id"] == canonical
    assert row["identity_disposition"] == "clean"
    assert row["label_display_name"] == display
    exported = [r for r in blob["display_ingredients"] if r.get("raw_source_path") == path]
    assert exported and all(r.get("canonical_id") == canonical for r in exported)


def test_biovar_diacetylactis_is_lactococcus_lactis(products):
    # NCBI Taxonomy 44688: L. lactis subsp. lactis bv. diacetylactis (not L. cremoris, 1359).
    row = _row(products["174659"][0], "ingredientRows[4].nestedRows[11]")
    assert row["canonical_id"] == "lactococcus_lactis"
    assert row["canonical_id_before"] == "lactococcus_lactis"


@pytest.mark.parametrize("dsld_id,rule", [
    ("212273", "RULE_IQM_OLIVE_LEAF_DIABETES"),
    ("15698", "RULE_IQM_GINGER_BLEEDING"),
    ("1650", "RULE_IQM_PROBIOTICS_IMMUNOCOMPROMISED"),
])
def test_kept_identity_keeps_its_interaction_rule(products, dsld_id, rule):
    assert rule in _rules(products[dsld_id][0])


def test_proprietary_blend_group_keeps_a_branded_complex_a_blend(products):
    # LAB4 Probiotics: DSLD files the row as a proprietary blend; its strains carry the warning.
    row = _row(products["1650"][0], "ingredientRows[0]")
    assert row["canonical_id"] == "BLEND_GENERAL"


@pytest.mark.parametrize("dsld_id,path,before,canonical", [
    ("204501", "ingredientRows[11]", "sunflower_oil", "vitamin_e"),
    ("329902", "ingredientRows[0]", "mct_oil", "activated_charcoal"),
    # The printed words name IQM ginger, the scoring identity (2026-09-27 coherence fix).
    ("15698", "ingredientRows[0].nestedRows[3]", "ginger_extract", "ginger"),
])
def test_genuine_repairs_still_replace_a_wrong_first_match(products, dsld_id, path, before, canonical):
    row = _row(products[dsld_id][0], path)
    assert (row["canonical_id_before"], row["canonical_id"], row["identity_disposition"]) == (before, canonical, "repaired")


@pytest.mark.parametrize("literal,owner,not_owner", [
    ("Lactococcus lactis subsp. lactis biovar diacetylactis", "lactococcus_lactis", "lactococcus_cremoris"),
    ("Olive juice extract", "olive_fruit_extract", "olive_leaf"),
    ("ElevATP", "PII_ELEVATP_BRANDED_BLEND", "shilajit"),
    ("Ancient Peat & Apple Extract", "PII_ELEVATP_BRANDED_BLEND", "shilajit"),
    ("Sweet Wormwood", "sweet_wormwood_herb", "artemisinin"),
    ("Artemisia annua extract", "sweet_wormwood_herb", "artemisinin"),
])
def test_curated_alias_names_the_printed_substance(pipeline, literal, owner, not_owner):
    registry = pipeline[1]._current_canonical_identity_registry()
    assert registry.literal_identity_matches(literal, owner)
    assert not registry.literal_identity_matches(literal, not_owner)


def test_export_carries_the_enricher_identity(products):
    # 1646 "Probiotic Complex Blend" is a weight-only blend header. The enricher keeps
    # its "probiotics" identity for interactions only (F2b); the exported analysis row
    # carries exactly the enricher's decision (one row, one identity).
    enriched, blob = products["1646"]
    path = "ingredientRows[0]"
    enricher_id = _row(enriched, path)["canonical_id"]
    assert enricher_id == "probiotics"
    [exported] = [r for r in blob["ingredients"] if r.get("raw_source_path") == path]
    assert exported.get("canonical_id") == enricher_id
    ledger = [r for r in blob["display_ingredients"] if r.get("raw_source_path") == path]
    assert ledger and all((r.get("analysis") or {}).get("canonical_id") in (None, enricher_id) for r in ledger)


@pytest.mark.parametrize("literal,not_owner", [
    # BioVin / BioVin Advanced are red-wine grape extracts (5% trans-resveratrol standard for
    # Advanced); a grape extract row is not a resveratrol row (replay 2026-10-19: 269265, 328514).
    ("BioVin", "resveratrol"),
    ("BioVin Advanced", "resveratrol"),
    # "Cabbage palm" names Sabal palmetto and acai (Euterpe oleracea); the corpus row sits in a
    # berry blend that DSLD groups as Acai (64382).
    ("Cabbage Palm", "saw_palmetto"),
])
def test_ambiguous_or_brand_aliases_do_not_name_another_substance(pipeline, literal, not_owner):
    registry = pipeline[1]._current_canonical_identity_registry()
    assert not registry.literal_identity_matches(literal, not_owner)


def test_biovin_advanced_is_a_grape_extract(pipeline):
    registry = pipeline[1]._current_canonical_identity_registry()
    assert registry.literal_identity_matches("BioVin Advanced", "grape")


def test_exact_cherry_species_survives_generic_group_and_powder_suffix(products):
    row = _row(products['294296'][0], 'ingredientRows[0]')
    assert row['canonical_id'] == 'dark_sweet_cherry'
    assert row['label_display_name'] == 'Wild Cherry Fruit Extract, Powder'
    assert row['quantity'] == 500 and row['unit'] == 'mg'


def test_biotinate_is_recognized_without_a_form_grade_or_completed_assessment(products):
    from scoring_v4.scored_artifact import build_scored_artifact
    enriched, _ = products['299744']
    row = _row(enriched, 'ingredientRows[0]')
    assert row['canonical_id'] == 'vitamin_b7_biotin'
    assert row['form_id'] == 'magnesium biotinate'
    assert row['form_match_status'] == 'mapped' and row['bio_score'] is None
    assert row['quantity'] == 10000 and row['unit'] == 'mcg'
    artifact = build_scored_artifact(enriched)
    assert artifact['quality_score_status'] == 'not_scored'
    assert 'form_quality_unassessed' in artifact['strict_scoring_contract']['findings']
    assert not any(r.get('canonical_id') == 'keratin' for r in enriched['ingredient_quality_data']['ingredients'])


def test_named_hair_complex_does_not_invent_component_amounts_or_clear_holds(products):
    from scoring_v4.scored_artifact import build_scored_artifact
    enriched, _ = products['336100']
    row = _row(enriched, 'ingredientRows[0]')
    assert row['quantity'] == 10000 and row['unit'] == 'mcg'
    assert row['bio_score'] is None
    assert build_scored_artifact(enriched)['quality_score_status'] == 'not_scored'
    assert not any(r.get('canonical_id') == 'keratin' for r in enriched['ingredient_quality_data']['ingredients'])
