"""Plain MSM draws on ingredient-level MSM trials, at their studied doses.

BRAND_OPTIMSM carried the generic aliases "msm" and "methylsulfonylmethane"
and no studied dose, so every MSM row inherited branded status (the elevated
verified-primary Evidence floor) with no dose check. Its two trials used MSM
at 6 g/day (PMID 16309928, 3 g twice daily) and 2 g/day (PMID 37447322, ten
200 mg tablets of OptiMSM). Pure Encapsulations Glucosamine/MSM 182940 gives
500 mg MSM/day at minimum use and read Evidence 15.6/20 "evaluated_applicable"
after MSM became title-named (review, 2026-09-29).

The returned A015/A093 decisions accept one exact OptiMSM mild-knee-pain
trial, not every generic MSM preparation. The 2 g and historical 6 g amounts
remain discrete source facts, not a continuous efficacy range or minimum.
General Dose uses the separately accepted neutral policy.
"""
import json
import logging
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
DATA = Path(__file__).resolve().parents[1] / "data"


def _entries():
    rows = json.loads((DATA / "backed_clinical_studies.json").read_text())["backed_clinical_studies"]
    return {e["id"]: e for e in rows}


def test_optimsm_is_the_brand_only_and_msm_is_ingredient_level():
    entries = _entries()
    assert entries["BRAND_OPTIMSM"]["aliases"] == ["optimsm"]
    msm = entries["INGR_MSM"]
    assert msm["evidence_level"] == "ingredient-human"
    assert {"msm", "methylsulfonylmethane"} <= set(msm["aliases"])
    for entry in (msm, entries["BRAND_OPTIMSM"]):
        assert (entry["min_clinical_dose"], entry["max_studied_clinical_dose"], entry["dose_unit"]) == (2000, 6000, "mg")
        assert {r["pmid"] for r in entry["references_structured"]} == {"16309928", "37447322"}


def test_generic_msm_cannot_inherit_the_exact_optimsm_trial():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact

    logging.disable(logging.INFO)
    raw = json.loads((FIXTURES / "title_short_name_182940_raw.json").read_text())
    enriched, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    matches = {m.get("id") for m in (enriched.get("evidence_data") or {}).get("clinical_matches") or []}
    assert "INGR_MSM" not in matches and "BRAND_OPTIMSM" not in matches
    artifact = build_scored_artifact(enriched)
    evidence = artifact["_v4_module_breakdown"]["dimensions"]["evidence"]
    dose = artifact["_v4_module_breakdown"]["dimensions"]["dose"]
    assert "SUB_CLINICAL_DOSE_DETECTED" not in json.dumps(evidence)
    msm = next(
        item for item in dose["metadata"]["specialized_purpose_assessments"]
        if item.get("active") == "msm"
    )
    assert msm["assessment_owner"] == "joint_support"
    # The trial amounts remain source facts; they do not establish a general
    # continuous Dose curve for every MSM preparation and purpose.
    assert msm["band"] == "no_benchmark_neutral"
    assert msm["score"] == 12.54
    assert msm["daily_mg"] == 500.0
    assert msm["daily_mg"] < _entries()["INGR_MSM"]["min_clinical_dose"]
