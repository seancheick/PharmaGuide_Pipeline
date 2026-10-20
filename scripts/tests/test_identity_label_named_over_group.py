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


def test_export_carries_the_enricher_identity_even_when_unresolved(products):
    # F2: 1646 "Probiotic Complex Blend" (a weight-only blend header) is left without an
    # identity by the enricher; the exported analysis row must not fill in the cleaner's
    # "probiotics" (one row, two identities).
    enriched, blob = products["1646"]
    path = "ingredientRows[0]"
    assert _row(enriched, path)["canonical_id"] is None
    [exported] = [r for r in blob["ingredients"] if r.get("raw_source_path") == path]
    assert not exported.get("canonical_id")
    assert exported.get("is_mapped") is not True
    # The display ledger row keeps the printed identity for the app's ingredient-id
    # union; its analysis namespace carries the enricher's decision.
    ledger = [r for r in blob["display_ingredients"] if r.get("raw_source_path") == path]
    assert ledger and all(not (r.get("analysis") or {}).get("canonical_id") for r in ledger)
    assert any(r.get("canonical_id") == "probiotics" for r in ledger)


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
