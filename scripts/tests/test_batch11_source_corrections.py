"""Verified source transcriptions and distinct serving-column ownership."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v3 import SupplementEnricherV3
from serving_frequency import resolve_daily_serving_range

FIXTURES = Path(__file__).parent / "fixtures"
DATA = Path(__file__).parents[1] / "data"
REPAIRED = ["270233", "62816", "231826", "315691", "252842", "254473", "254474", "254475", "269689", "287389"]


@pytest.fixture(scope="module")
def sources():
    return json.loads((FIXTURES / "batch11_label_source_raw.json").read_text())


@pytest.fixture(scope="module")
def products(sources):
    normalizer, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()
    result = {}
    for pid, raw in sources.items():
        clean = normalizer.normalize_product(deepcopy(raw))
        enriched, _ = enricher.enrich_product(clean)
        result[pid] = (clean, enriched)
    return result


def test_energy_plus_reduced_nadh_amount_and_source(products):
    clean, enriched = products["270233"]
    row = next(r for r in clean["activeIngredients"] if r["raw_source_path"] == "ingredientRows[2]")
    assert row["quantity"] == 20 and row["unit"] == "mg"
    assert row["canonical_id"] == "nadh"
    assert "disodium phosphate" not in json.dumps(row["forms"]).lower()
    assert "disodium salt" in json.dumps(row["forms"]).lower()


def test_iodine_transcription_preserves_actual_daily_range(products):
    clean, enriched = products["62816"]
    row = next(r for r in clean["activeIngredients"] if r.get("canonical_id") == "iodine")
    assert row["quantity"] == 25 and row["unit"] == "mcg"
    result = next(r for r in enriched["rda_ul_data"]["adequacy_results"] if r.get("canonical_id") == "iodine")
    assert (result["per_day_min"], result["per_day_max"]) == (25, 50)


def test_insea_amount_belongs_to_preparation_not_unquantified_heading(products):
    clean, _ = products["231826"]
    rows = {r["name"]: r for r in clean["activeIngredients"]}
    assert rows["InSea2"]["quantity"] == 125 and rows["InSea2"]["unit"] == "mg"
    heading = rows.get("Calorie Control Complex")
    if heading:
        assert heading["unit"] == "NP"
    # No individual polyphenol or species allocation follows from 125 mg.
    for row in clean["activeIngredients"]:
        if row.get("raw_source_path", "").startswith("ingredientRows[3].nestedRows[0]."):
            assert row.get("unit") in {"NP", None, ""}


def test_emergency_ki_uses_two_tablet_facts_basis_without_losing_restrictions(products, sources):
    clean, _ = products["315691"]
    row = next(r for r in clean["activeIngredients"] if r["name"] == "Potassium Iodide")
    assert row["quantity"] == 130 and row["unit"] == "mg"
    variants = row.get("quantityVariants") or row.get("raw_taxonomy", {}).get("quantityVariants")
    assert variants and variants[0]["serving_size_quantity"] == 2
    assert clean["statements"] == sources["315691"]["statements"]


@pytest.mark.parametrize("pid", ["252842", "254473", "254474", "254475"])
def test_citrate_volume_note_does_not_change_grams_or_elemental_sodium(products, pid):
    clean, enriched = products[pid]
    assert clean["servingSizes"][0]["notes"] == "about 1/3 tbsp"
    row = next(r for r in clean["activeIngredients"] if r.get("canonical_id") == "sodium")
    assert row["quantity"] == 600 and row["unit"] == "mg"
    assert clean["servingSizes"][0]["minQuantity"] == 3
    assert resolve_daily_serving_range(enriched) == (1, 1, False)


def test_magnesium_starting_scoop_is_half_the_two_scoop_facts_panel(products):
    clean, enriched = products["269689"]
    assert resolve_daily_serving_range(enriched) == (0.5, 1, False)
    row = next(r for r in enriched["rda_ul_data"]["adequacy_results"]
               if r.get("canonical_id") == "magnesium" and r.get("scoring_eligible"))
    assert (row["per_day_min"], row["per_day_max"]) == (200, 400)
    assert row["over_ul"] is True
    from scoring_v4.scored_artifact import build_scored_artifact
    scored = build_scored_artifact(enriched)
    ceiling = scored["dose_safety_evaluation"]["dose_ceiling"]
    assert ceiling["minimum_exceeds"] is False
    assert ceiling["cap_public"] is None and ceiling["deduction_public"] == 2.0
    assert scored["product_safety_status"] == "caution"


def test_manganese_daily_column_is_not_multiplied_as_a_two_tablet_amount(products):
    row = next(r for r in products["66513"][1]["rda_ul_data"]["adequacy_results"]
               if r.get("canonical_id") == "manganese")
    assert (row["per_day_min"], row["per_day_max"]) == (2, 2)


def test_cleaner_preserves_a_fractional_daily_serving_count():
    [row] = EnhancedDSLDNormalizer()._process_serving_sizes([{
        "minQuantity": 2, "maxQuantity": 2, "unit": "Scoop(s)",
        "minDailyServings": 0.5, "maxDailyServings": 1}])
    assert row["minDailyServings"] == 0.5
    assert row["maxDailyServings"] == 1


@pytest.mark.parametrize("pid", REPAIRED)
def test_reviewed_repairs_reject_a_changed_source_record(sources, pid):
    raw = deepcopy(sources[pid])
    raw["statements"].append({"type": "Suggested/Recommended/Usage/Directions", "notes": "changed edition"})
    with pytest.raises(ValueError, match="Reviewed serving source changed"):
        EnhancedDSLDNormalizer().normalize_product(raw)


def test_theracurmin_randomized_and_analyzed_counts_are_distinct_without_approval():
    from clinical_applicability import assess_clinical_source_review
    records = json.loads((DATA / "backed_clinical_studies.json").read_text())["backed_clinical_studies"]
    record = next(r for r in records if r["id"] == "BRAND_THERACURMIN")
    for field in ["notes", "notable_studies", "effect_direction_rationale"]:
        assert "randomized 40" not in record[field]
        assert "46" in record[field] and "40" in record[field]
    assert record["total_enrollment"] is None
    assert assess_clinical_source_review(record)["is_complete"] is False


def test_sunactive_rejected_citation_is_retained_as_rejected_provenance():
    data = json.loads((DATA / "standardized_botanicals.json").read_text())
    entries = next(v for v in data.values() if isinstance(v, list))
    record = next(r for r in entries if r.get("id") == "sunactive_iron")
    assert record["bonus_eligible"] is False
    assert record["data_quality"] == "requires_verification"
    assert any("19674817" in s and s.startswith("Rejected attribution:") for s in record["sources"])


def test_virtiva_retains_exact_leaf_phospholipid_composition_without_allocating_complex(products):
    clean, enriched = products["287389"]
    row = next(r for r in clean["activeIngredients"] if "Virtiva" in r["name"])
    assert row["quantity"] == 120 and row["unit"] == "mg"
    text = json.dumps(row).lower()
    assert "sunflower" in text and "leaf" in text
    assert "5%" in text and "12%" in text
    assert "6%" not in text
    # The source composition does not make 120 mg of pure ginkgo or PS.
    assert not row.get("isProprietaryBlend")


@pytest.mark.parametrize("parent,form,grade", [
    ("nicotinamide_riboside", "niagen (nicotinamide riboside chloride)", 13),
    ("nicotinamide_riboside", "nicotinamide riboside (unspecified)", 11),
    ("devils_claw", "devil's claw extract", 7),
    ("devils_claw", "devil's claw (unspecified)", 6),
    ("devils_claw", "devil's claw standardized (harpagoside)", 9),
])
def test_unestablished_human_absorption_fraction_is_not_a_numeric_estimate(parent, form, grade):
    record = json.loads((DATA / "ingredient_quality_map.json").read_text())[parent]["forms"][form]
    assert record["absorption"] == "unknown"
    assert record["absorption_structured"] == {
        "value": None, "range_low": None, "range_high": None, "quality": "unknown"}
    assert record["bio_score"] == grade


def test_niagen_attribution_supports_metabolome_response_without_inventing_absorption():
    record = json.loads((DATA / "ingredient_quality_map.json").read_text())["nicotinamide_riboside"]
    text = record["forms"]["niagen (nicotinamide riboside chloride)"]["notes"]
    assert "27721479" in text
    assert "27720903" not in text and "142%" not in text
    assert "85-90%" not in text and "Science Advances 2024" not in text


def test_devil_claw_ema_status_does_not_claim_well_established_efficacy():
    record = json.loads((DATA / "ingredient_quality_map.json").read_text())["devils_claw"]
    text = record["forms"]["devil's claw extract"]["notes"]
    assert "traditional use" in text.lower()
    assert "European Medicines Agency well-established use" not in text


@pytest.mark.parametrize("value", ["NaN", float("nan")])
def test_fractional_daily_count_does_not_introduce_nonfinite_json(value):
    [row] = EnhancedDSLDNormalizer()._process_serving_sizes([{
        "minQuantity": 1, "maxQuantity": 1, "unit": "Capsule(s)",
        "minDailyServings": value, "maxDailyServings": 1}])
    assert row["minDailyServings"] == 0


def test_returned_iqm_sources_keep_the_studied_endpoint_and_preparation():
    rows = json.loads((DATA / 'ingredient_quality_map.json').read_text())
    for parent in ['sea_buckthorn', 'fenugreek']:
        assert 'rutin systemic 1-5%' not in json.dumps(rows[parent])
    assert 'intact systemic bioavailability' in rows['sea_buckthorn']['forms']['sea buckthorn seed oil']['notes']
    assert 'single 500 mg trans-resveratrol tablet' in rows['red_wine_extract']['forms']['standardized red wine extract']['notes']
    assert 'not 500 mg isolated diosgenin' in rows['diosgenin']['forms']['diosgenin (unspecified)']['notes']
    assert 'six young men' in rows['perilla_oil']['forms']['perilla seed oil']['notes']
    sage_note = rows['sage']['forms']['cognivia sage extract']['notes']
    assert 'PMID20377818' in sage_note
    assert 'not oral Cognivia in healthy adults' in sage_note
    assert '10.1038/sj.ijo.0801322' not in sage_note
    assert 'preclinical in-vitro rat-platelet experiment' in rows['cayenne_pepper']['forms']['cayenne pepper (unspecified)']['notes']
    assert '~50% inactive L-βHB enantiomer' not in rows['inositol']['forms']['d-chiro-inositol']['notes']


@pytest.mark.parametrize('form', ['cascara sagrada bark extract', 'cascara sagrada bark powder'])
def test_cascara_cell_experiments_do_not_supply_human_absolute_absorption(form):
    rows = json.loads((DATA / 'ingredient_quality_map.json').read_text())
    record = rows['cascara_sagrada']['forms'][form]
    assert record['absorption'] == 'unknown'
    assert record['absorption_structured'] == {
        'value': None, 'range_low': None, 'range_high': None, 'quality': 'unknown'}
    assert 'human absolute absorption' in record['notes']


def test_ala_tracer_does_not_supply_whole_perilla_oil_absolute_absorption():
    record = json.loads((DATA / 'ingredient_quality_map.json').read_text())['perilla_oil']['forms']['perilla seed oil']
    assert record['absorption'] == 'unknown'
    assert record['absorption_structured'] == {
        'value': None, 'range_low': None, 'range_high': None, 'quality': 'unknown'}
    assert record['bio_score'] == 10
