"""Plain MSM draws on ingredient-level MSM trials, at their studied doses.

BRAND_OPTIMSM carried the generic aliases "msm" and "methylsulfonylmethane"
and no studied dose, so every MSM row inherited branded status (the elevated
verified-primary Evidence floor) with no dose check. Its two trials used MSM
at 6 g/day (PMID 16309928, 3 g twice daily) and 2 g/day (PMID 37447322, ten
200 mg tablets of OptiMSM). Pure Encapsulations Glucosamine/MSM 182940 gives
500 mg MSM/day at minimum use and read Evidence 15.6/20 "evaluated_applicable"
after MSM became title-named (review, 2026-09-29).

Now OptiMSM keeps only its brand name, INGR_MSM holds the ingredient-level
record, and both carry the studied range (2-6 g/day), so 500 mg/day is below
every studied dose.
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


def test_500_mg_msm_is_below_the_studied_dose_and_not_branded():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact

    logging.disable(logging.INFO)
    raw = json.loads((FIXTURES / "title_short_name_182940_raw.json").read_text())
    enriched, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    matches = {m.get("id") for m in (enriched.get("evidence_data") or {}).get("clinical_matches") or []}
    assert "INGR_MSM" in matches and "BRAND_OPTIMSM" not in matches
    evidence = build_scored_artifact(enriched)["_v4_module_breakdown"]["dimensions"]["evidence"]
    assert "SUB_CLINICAL_DOSE_DETECTED" in json.dumps(evidence)
