"""Pillar explanations may only claim what the scorer established (V4.1 Step 2).

Each case is a contradiction measured in the stored catalog
(scripts/audits/score_accounting_20261014/AUDIT.md F3, F8, F10, F19). These
are display corrections: scores, states and safety outcomes stay unchanged.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scoring_v4 import quality_score as qs  # noqa: E402
from scoring_v4.pillar_explanations import attach_pillar_explanations  # noqa: E402


def _cfg():
    return qs._config()


def _evidence_pillar(state, raw, archetype="generic_botanical_branded"):
    dim = {"score": raw, "max": 20.0, "components": {"clinical_evidence_pipeline": raw},
           "metadata": {"evidence_result_state": state, "matched_entries": 0}}
    return qs._pillar_evidence(dim, 20, archetype, _cfg()), dim


def _explain(pillars, dims):
    return attach_pillar_explanations(pillars, {"dimensions": dims}, _cfg(), "generic")


# ---- F8: an Evidence zero must not read as "no research" -------------------

def test_applicability_zero_does_not_claim_an_empty_evidence_database():
    pillar, dim = _evidence_pillar("applicability_unestablished", 0.0)
    out = _explain({"evidence": pillar}, {"evidence": dim})
    facts = (out["evidence"].get("explanation") or {}).get("facts") or []
    assert not any(f["id"] == "matched_evidence_records" for f in facts)


def test_reviewed_zero_still_states_its_record_count():
    pillar, dim = _evidence_pillar("no_qualifying_human_evidence", 0.0)
    out = _explain({"evidence": pillar}, {"evidence": dim})
    facts = out["evidence"]["explanation"]["facts"]
    assert {"id": "matched_evidence_records", "label": "Qualifying evidence matches",
            "value_display": "0 in PharmaGuide's current evidence data"} in facts


def test_authority_copy_requires_awarded_points():
    zero, _ = _evidence_pillar("evaluated_authority", 0.0)
    assert "recognizes the physiological necessity" not in zero["reason"]
    assert zero["reason"] == (
        "These ingredients were reviewed against established nutritional authority, "
        "which earned no Evidence points for this product.")
    credited, _ = _evidence_pillar("evaluated_authority", 10.0, "generic_single_molecule")
    assert credited["reason"].startswith("Established nutritional authority recognizes")


# ---- F10: Dose and Formulation copy must match what was assessed -----------

UNBENCHMARKED = ("Dose disclosed, but adequacy cannot be determined confidently from available "
                 "evidence because an applicable dose benchmark is unavailable.")


def test_unbenchmarked_botanical_and_collagen_dose_do_not_claim_a_benchmark():
    for band_key in ("botanical_dose_band", "collagen_dose_band"):
        dim = {"score": 12.0, "max": 25.0, "components": {}, "metadata": {band_key: "disclosed_no_reference"}}
        pillar = qs._pillar_dose(dim, 20, "generic_botanical_branded", _cfg())
        assert pillar["reason"] == UNBENCHMARKED, band_key
        assert pillar["score"] == 11.4


def test_missing_botanical_amount_is_not_called_a_partial_dose():
    dim = {"score": 5.0, "max": 25.0, "components": {}, "metadata": {"botanical_dose_band": "primary_no_dose"}}
    pillar = qs._pillar_dose(dim, 20, "generic_botanical_branded", _cfg())
    assert pillar["reason"] == "No amount is disclosed for the main ingredient, so its dose cannot be assessed."


def test_botanical_formulation_names_what_earned_the_points():
    # V4.1 Step 4: identity is a neutral baseline and the printed amount earns
    # nothing here, so the copy says neither is earned quality.
    dim = {"score": 8.8, "max": 30.0, "components": {"A1_bio_score": 8.8},
           "metadata": {"formulation_profile": "botanical", "botanical_profile_applied": True,
                        "iqm_form_quality_assessed_count": 3,
                        "botanical_formulation": {"recognized_botanical_identity": 7.2,
                                                  "extract_not_whole_herb": 1.6}}}
    pillar = qs._pillar_formulation(dim, 20, "generic_botanical_branded", _cfg())
    assert pillar["score"] == 14.7
    assert pillar["reason"] == (
        "The recognized botanical identity receives neutral credit. "
        "Credited: extract preparation. Not credited: marker standardization.")
    assert "disclosed amount" not in pillar["reason"] and "verified" not in pillar["reason"]
    assert "absorbed" not in pillar["reason"] and "forms" not in pillar["reason"]


def test_non_form_quality_routes_do_not_claim_well_absorbed_forms():
    dim = {"score": 25.0, "max": 30.0,
           "components": {"sports_protein_source_quality": 15.0, "sports_protein_dose_transparency": 5.0,
                          "sports_protein_focus": 3.0, "sports_route_base": 2.0},
           "metadata": {}}
    pillar = qs._pillar_formulation(dim, 20, "sports_protein", _cfg())
    assert "absorbed" not in pillar["reason"]


def test_low_transparency_without_a_blend_does_not_blame_a_blend():
    dim = {"score": 4.0, "max": 10.0,
           "components": {"clear_disclosure_base": 6.0, "complete_active_identity_dose_disclosure": 0.0},
           "penalties": {"B2_false_allergen_free_claim": -2.0, "B5_proprietary_blend_opacity": 0.0,
                         "B6_marketing_claims": 0.0},
           "metadata": {"flags": [], "complete_active_disclosure": {"qualifies": False, "incomplete_rows": []}}}
    pillar = qs._pillar_from_dim("transparency", dim, 15, "transparency")
    assert pillar["score"] == 6.0
    assert "blend" not in pillar["reason"]
    assert pillar["reason"] == "A free-from claim on the label conflicts with its ingredients."


# ---- Verification and the sixth pillar ------------------------------------

def _module_bd(state_counts=None, b7=0.0, base_passed=True):
    return {
        "dimensions": {"dose": {"penalties": {"B7_dose_safety": -b7},
                                "metadata": {"B7_safety_evaluation": {"state_counts": state_counts or {}}}}},
        "safety_hygiene_base": {"score": 4.0 if base_passed else 0.0, "max": 4.0},
        "verification_bonus": {"components": {}, "metadata": {"trust_metadata": {}}},
    }


def test_unknown_verification_states_its_neutral_baseline():
    pillar = qs._pillar_verification(_module_bd(), 15, _cfg())
    assert pillar["score"] == 6.0
    assert pillar["reason"] == (
        "Unknown: no independent verification on file; neutral 6 of 15, 9 points need verified evidence.")


CLEAN_SCREEN = ("No catalog-level formula concerns found in the checks performed. "
                "Personal suitability was not assessed.")


def test_clean_screen_describes_its_scope():
    pillar = qs._pillar_safety_hygiene(_module_bd(), 10, _cfg())
    assert pillar["score"] == 10.0
    assert pillar["reason"] == CLEAN_SCREEN


def test_below_threshold_ul_concern_stays_visible_without_reading_as_a_deduction():
    bd = _module_bd(state_counts={"confirmed_over_threshold": 1})
    safety = qs._pillar_safety_hygiene(bd, 10, _cfg())
    assert safety["score"] == 10.0
    assert safety["reason"] == (
        "Not deducted here: one or more supplemental amounts exceed an established upper limit.")
    dose = qs._pillar_dose({"score": 11.0, "max": 25.0, "components": {},
                            "metadata": bd["dimensions"]["dose"]["metadata"]},
                           20, "generic_single_molecule", _cfg())
    assert "exceed established safety limits" in dose["reason"]


def test_unresolved_dose_check_is_also_explained_by_dose():
    bd = _module_bd(state_counts={"material_but_unresolved": 1})
    safety = qs._pillar_safety_hygiene(bd, 10, _cfg())
    assert safety["reason"].startswith("Not deducted here: one or more dose-safety checks could not be completed")
    dose = qs._pillar_dose({"score": 20.0, "max": 25.0, "components": {},
                            "metadata": bd["dimensions"]["dose"]["metadata"]},
                           20, "generic_single_molecule", _cfg())
    assert dose["reason"] == ("One or more dose-safety checks could not be completed because the amount, "
                              "form, or comparison basis was unresolved.")


def test_deducted_ul_concern_still_named_in_the_sixth_pillar():
    bd = _module_bd(state_counts={"confirmed_over_threshold": 1}, b7=2.0)
    safety = qs._pillar_safety_hygiene(bd, 10, _cfg())
    assert safety["score"] == 10.0
    assert "exceed an established upper limit" in safety["reason"]


def test_full_screen_beside_a_safety_caution_says_so():
    pillar = qs._pillar_safety_hygiene(_module_bd(), 10, _cfg(), catalog_caution=True)
    assert pillar["score"] == 10.0
    assert pillar["reason"] == ("These formula checks found no concern, but this product carries a separate "
                                "safety caution.")


# ---- F19 and the export strengths list -------------------------------------

def test_dose_safety_policy_fact_matches_the_classifier():
    bd = {"dimensions": {"dose": {"penalties": {"B7_dose_safety": -2.0}, "metadata": {
        "method": "rda_ul_proxy_until_dietary_intake_table",
        "dose_safety_policy": {"ul_pct_threshold": 150.0, "per_flag_penalty": 2.0, "cap": 3.0}}}}}
    pillars = {"dose": {"score": 10.0, "max": 20, "reason": "", "components": {"raw_dose": 11.0}},
               "safety_hygiene": {"score": 10.0, "max": 10, "components": {}}}
    out = attach_pillar_explanations(pillars, bd, _cfg(), "generic")
    fact = next(f for f in out["dose"]["explanation"]["facts"] if f["id"] == "dose_safety_penalty_policy")
    assert "can also trigger" not in fact["value_display"]
    assert fact["value_display"].endswith("Unresolved dose assessments are shown but do not trigger this penalty.")


def test_a_clean_screen_is_not_listed_as_a_strength():
    from build_final_db import _build_v4_score_explanation
    pillars = {
        "transparency": {"score": 15.0, "max": 15, "reason": "Fully transparent label."},
        "safety_hygiene": {"score": 10.0, "max": 10, "reason": CLEAN_SCREEN, "components": {}},
        "dose": {"score": 10.0, "max": 20, "reason": "partial"},
    }
    explanation = _build_v4_score_explanation(pillars)
    assert [s["pillar"] for s in explanation["strengths"]] == ["transparency"]


def test_dose_finding_is_not_worded_as_this_pillars_deduction_when_it_deducts_for_other_reasons():
    bd = _module_bd(state_counts={"confirmed_over_threshold": 1})
    safety = qs._pillar_safety_hygiene(bd, 10, _cfg(), clean_label_penalty=1.0)
    assert safety["score"] == 9.0
    assert safety["reason"] == ("Safety concern: it contains a restricted additive. Not deducted here: "
                                "one or more supplemental amounts exceed an established upper limit.")


def test_dose_safety_copy_names_its_single_numerical_owner():
    bd = {"dimensions": {"dose": {"penalties": {"B7_dose_safety": -2.0},
        "metadata": {"method": "rda_ul_proxy_until_dietary_intake_table"}}}}
    pillars = {"dose": {"score": 10.0, "max": 20, "reason": "", "components": {"raw_dose": 11.0}}}
    out = attach_pillar_explanations(pillars, bd, _cfg(), "generic")
    fact = next(f for f in out["dose"]["explanation"]["facts"] if f["id"] == "dose_safety_scoring")
    assert "Dose only" in fact["value_display"]
    assert "across two pillars" not in fact["value_display"]
