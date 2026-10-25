"""Exact NIH label editions: source amounts, regimen and honest limitations."""
import json
from pathlib import Path

import pytest

from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v3 import SupplementEnricherV3
from build_final_db import generate_dosing_summary
from scoring_v4.scored_artifact import build_scored_artifact
from serving_frequency import resolve_daily_serving_range


@pytest.fixture(scope="module")
def assessments():
    raw = json.loads((Path(__file__).parent / "fixtures/batch10_preparation_labels_raw.json").read_text())
    normalizer, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()
    results = {}
    for pid, source in raw.items():
        cleaned = normalizer.normalize_product(source)
        enriched, _ = enricher.enrich_product(cleaned)
        results[pid] = (source, cleaned, enriched)
    return results


@pytest.mark.parametrize("pid,daily", [("25501", 400), ("322515", 400), ("203385", 200)])
def test_declared_elemental_magnesium_is_not_added_to_its_source_mass(assessments, pid, daily):
    source, cleaned, enriched = assessments[pid]
    all_magnesium = [r for r in enriched["rda_ul_data"]["adequacy_results"]
                     if r.get("canonical_id") == "magnesium"]
    magnesium = [r for r in all_magnesium if r.get("scoring_eligible")]
    assert len(magnesium) == 1
    assert magnesium[0]["amount"] == daily
    assert magnesium[0]["over_ul"] is (daily > 350)
    assert magnesium[0]["reference"]["ul_basis"] == "supplemental_only"
    for source_material in (r for r in all_magnesium if not r.get("scoring_eligible")):
        assert source_material["skip_ul_reason"] == "compound_duplicate_row"
        assert source_material["pct_ul"] is None
        assert not source_material["over_ul"]
    assert resolve_daily_serving_range(enriched) == ((2, 2, False) if daily == 400 else (1, 1, False))
    if daily == 400:
        assert magnesium[0]["over_ul_amount"] == 50
        assert magnesium[0]["warnings"]
    # A resolved amount does not sign off the mixed/buffered preparation.
    assert build_scored_artifact(enriched)["quality_score_status"] == "not_scored"


def test_purelean_packet_retains_explicit_chromium_allocation_without_inferred_mass(assessments):
    source, cleaned, enriched = assessments["188790"]
    chromium = next(r for r in cleaned["activeIngredients"] if r.get("name") == "Chromium")
    assert chromium["quantity"] == 200
    assert chromium["unit"] == "mcg"
    zychrome = next(f for f in chromium["forms"] if "Zychrome" in f["name"])
    assert zychrome["percent"] == 50
    assert chromium["quantity"] * zychrome["percent"] / 100 == 100
    assert resolve_daily_serving_range(enriched) == (1, 1, False)
    assert not chromium.get("proprietaryBlend")
    assert not any("zychrome" in str(r.get("id") or "").lower()
                   for r in enriched["evidence_data"]["clinical_matches"])


def test_catalyte_keeps_scoop_amount_without_inventing_daily_maximum(assessments):
    source, cleaned, enriched = assessments["323080"]
    magnesium = next(r for r in cleaned["activeIngredients"] if r.get("name") == "Magnesium")
    assert magnesium["quantity"] == 40 and magnesium["unit"] == "mg"
    assert source["servingSizes"][0]["maxDailyServings"] is None
    assert enriched["serving_basis"]["max_servings_per_day"] is None
    assert resolve_daily_serving_range(enriched) == (1, 1, True)
    assert enriched["rda_ul_data"]["is_servings_estimated"] is True
    assert generate_dosing_summary(enriched)["dosing_summary"] == "See product label"
    assert cleaned["statements"] == source["statements"]
    assert build_scored_artifact(enriched)["quality_score_status"] == "not_scored"


@pytest.mark.parametrize("pid,expected", [("203385", 200), ("322515", 400)])
def test_interaction_thresholds_use_elemental_magnesium_not_source_material(assessments, pid, expected):
    enriched = assessments[pid][2]
    evaluations = [hit["dose_decision"]["dose_evaluation"]
                   for alert in enriched["interaction_profile"]["ingredient_alerts"]
                   if alert.get("standard_name") == "Magnesium"
                   for hit in alert.get("condition_hits", [])
                   if (hit.get("dose_decision") or {}).get("dose_evaluation")]
    assert evaluations
    assert {e["daily_amount"] for e in evaluations} == {expected}
