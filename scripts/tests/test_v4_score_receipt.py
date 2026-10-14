"""Score receipts: every public pillar point is reconstructable (V4.1 Step 2).

Contract: scripts/audits/score_accounting_20261014/AUDIT.md §8. A receipt is a
projection of the scorer's own result. It never changes a score, max, tier or
state; it only itemizes them. Fixtures mirror real module-breakdown shapes
(Meru, Garcinia, Airborne, a Culturelle-style probiotic) because CI has no
product corpus.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scoring_v4.quality_score import assemble_quality_score  # noqa: E402

KINDS = {"earned", "neutral", "disclosure", "deduction", "floor", "cap", "rounding"}


def _dim(score, mx, components, penalties=None, metadata=None):
    return {"score": score, "max": mx, "components": components,
            "penalties": penalties or {}, "metadata": metadata or {}}


def _verification(b4a=0.0, b4b=0.0, b4c=0.0, b4d=0.0, gmp_basis=None, scopes=None):
    trust = {"verified_scope_counts": scopes or {}, "verified_unscored_scope_counts": {}}
    if gmp_basis:
        trust["gmp_basis"] = gmp_basis
    return {"score": 0.0, "max": 8.0,
            "components": {"B4a_verified_certifications": b4a, "B4b_gmp": b4b,
                           "B4c_batch_traceability": b4c, "B4d_brand_testing_posture": b4d},
            "metadata": {"trust_metadata": trust}}


def _base(passed=True, drivers=None):
    if passed:
        return {"score": 4.0, "max": 4.0,
                "components": {"no_banned_high_risk_or_watchlist_match": 2.0, "no_recalled_match": 2.0}}
    return {"score": 0.0, "max": 4.0, "components": {},
            "metadata": {"drivers": drivers or [{"status": "high_risk", "name": "Garcinia cambogia extract"}]}}


def _transparency(base=6.0, bonus=4.0, penalties=None, metadata=None):
    return _dim(max(0.0, base + bonus + sum((penalties or {}).values())), 10.0,
                {"clear_disclosure_base": base, "complete_active_identity_dose_disclosure": bonus,
                 "B3_claim_compliance": 0.0, "hypoallergenic_bonus": 0.0},
                penalties or {"B2_false_allergen_free_claim": 0.0, "B5_proprietary_blend_opacity": 0.0,
                              "B6_marketing_claims": 0.0}, metadata)


def _botanical_formulation(profile, penalties=None, floor_applied=False, score=None):
    a1 = min(15.0, max(0.0, sum(profile.values())))
    pen = penalties or {"B1_dietary_sugar": 0.0, "B0_moderate_watchlist": 0.0, "B1_harmful_additives": 0.0}
    running = a1 + sum(pen.values())
    return _dim(score if score is not None else max(0.0, running), 30.0,
                {"A1_bio_score": a1, "A3_delivery_system": 0.0, "A4_absorption_enhancer": 0.0,
                 "A5b_standardized_botanical": 0.0},
                pen,
                {"formulation_profile": "botanical", "botanical_profile_applied": True,
                 "botanical_formulation": profile, "iqm_form_quality_assessed_count": 3,
                 "presence_floor": {"target": 2.0, "pre_floor_score": running, "applied": floor_applied}})


def _meru_breakdown():
    return {
        "dimensions": {
            "formulation": _botanical_formulation({"recognized_botanical_identity": 6.0,
                                                   "quantified_dose_present": 2.0,
                                                   "extract_not_whole_herb": 2.0}),
            "dose": _dim(12.0, 25.0, {"botanical_clinical_dose": 12.0}, {"B7_dose_safety": 0.0},
                         {"botanical_dose_band": "disclosed_no_reference"}),
            "evidence": _dim(0.0, 20.0, {"clinical_evidence_pipeline": 0.0, "depth_bonus": 0.0}, {},
                             {"evidence_result_state": "applicability_unestablished", "matched_entries": 0}),
            "transparency": _transparency(),
        },
        "verification_bonus": _verification(),
        "manufacturer_trust": {"score": 1.0, "max": 5.0, "components": {"D1_manufacturer_reputation": 0.0}},
        "safety_hygiene_base": _base(),
    }


def _assemble(bd, module="generic", verdict="SAFE", raw=37.0, clean_label_hits=None):
    return assemble_quality_score({
        "raw_score_v4_100": raw, "v4_verdict": verdict, "v4_module": module,
        "v4_breakdown": {"module": bd, "safety_gate": {"clean_label_hits": clean_label_hits or []}},
    })


def _assert_reconciles(out):
    pillars = out["quality_pillars_v4"]
    for name, pillar in pillars.items():
        receipt = pillar.get("receipt")
        assert receipt is not None, f"{name} has no receipt"
        entries = receipt["entries"]
        assert {e["kind"] for e in entries} <= KINDS, name
        assert round(sum(e["points"] for e in entries), 4) == round(pillar["score"], 4), name
        rounding = [e for e in entries if e["kind"] == "rounding"]
        assert {e["id"] for e in rounding} <= {"rounding", "module_rounding"}, name
        assert len(rounding) == len({e["id"] for e in rounding}), name
        assert all(abs(e["points"]) <= 0.0505 for e in rounding if e["id"] == "rounding"), name
        assert all(abs(e["points"]) <= 0.011 for e in rounding if e["id"] == "module_rounding"), name
        assert receipt["unawarded"] >= -1e-9, name
        assert receipt["realized_deductions"] <= 1e-9, name
        assert receipt["nominal_deductions"] <= 1e-9, name
        assert round(pillar["score"] + receipt["unawarded"] - receipt["realized_deductions"], 4) == pillar["max"], name
    assert round(sum(p["score"] for p in pillars.values()), 1) == out["quality_score_v4_100"]


def _entry(out, pillar, entry_id):
    return next(e for e in out["quality_pillars_v4"][pillar]["receipt"]["entries"] if e["id"] == entry_id)


def _ids(out, pillar):
    return [e["id"] for e in out["quality_pillars_v4"][pillar]["receipt"]["entries"]]


# ---- Meru: baselines, disclosure credit and an applicability zero ----------

def test_meru_receipt_reconciles_to_55_7_without_changing_any_pillar():
    out = _assemble(_meru_breakdown())
    pillars = out["quality_pillars_v4"]
    assert {k: p["score"] for k, p in pillars.items()} == {
        "formulation": 13.3, "dose": 11.4, "evidence": 0.0, "transparency": 15.0,
        "verification": 6.0, "safety_hygiene": 10.0}
    assert out["quality_score_v4_100"] == 55.7
    _assert_reconciles(out)


def test_botanical_profile_detail_replaces_its_aggregate():
    out = _assemble(_meru_breakdown())
    ids = _ids(out, "formulation")
    assert "A1_bio_score" not in ids
    assert _entry(out, "formulation", "recognized_botanical_identity")["kind"] == "neutral"
    assert _entry(out, "formulation", "quantified_dose_present")["kind"] == "disclosure"
    assert _entry(out, "formulation", "extract_not_whole_herb")["kind"] == "earned"
    assert _entry(out, "formulation", "recognized_botanical_identity")["points"] == pytest.approx(8.0)


def test_unbenchmarked_dose_and_unconditional_bases_are_labelled_neutral():
    out = _assemble(_meru_breakdown())
    assert _entry(out, "dose", "botanical_clinical_dose")["kind"] == "neutral"
    assert _entry(out, "transparency", "clear_disclosure_base")["kind"] == "neutral"
    assert _entry(out, "transparency", "clear_disclosure_base")["points"] == pytest.approx(9.0)
    assert _entry(out, "verification", "neutral_baseline") == {
        "id": "neutral_baseline", "kind": "neutral", "source": "verification_subscale.neutral_baseline",
        "raw": 6.0, "points": 6.0}
    assert _entry(out, "safety_hygiene", "catalog_screen")["kind"] == "neutral"
    assert out["quality_pillars_v4"]["verification"]["receipt"]["unawarded"] == pytest.approx(9.0)


# ---- Garcinia: a penalty absorbed by the presence floor --------------------

def test_presence_floor_absorption_is_visible_as_realized_vs_nominal():
    bd = _meru_breakdown()
    bd["dimensions"]["formulation"] = _botanical_formulation(
        {"recognized_botanical_identity": 6.0, "quantified_dose_present": 2.0, "extract_not_whole_herb": 2.0},
        penalties={"B1_dietary_sugar": 0.0, "B0_moderate_watchlist": -10.0, "B1_harmful_additives": 0.0},
        floor_applied=True, score=2.0)
    bd["safety_hygiene_base"] = _base(passed=False)
    out = _assemble(bd, verdict="CAUTION")
    form = out["quality_pillars_v4"]["formulation"]
    assert form["score"] == 2.7
    assert _entry(out, "formulation", "presence_floor")["kind"] == "floor"
    assert form["receipt"]["nominal_deductions"] == pytest.approx(-13.3333, abs=1e-3)
    assert form["receipt"]["realized_deductions"] == pytest.approx(-10.6, abs=1e-6)
    assert out["quality_pillars_v4"]["safety_hygiene"]["score"] == 0.0
    _assert_reconciles(out)


# ---- Airborne-style multi: B1 and B7 mirrored into the sixth pillar --------

def test_mirrored_deductions_are_separate_entries_in_both_pillars():
    bd = _meru_breakdown()
    bd["dimensions"]["formulation"] = _dim(
        3.08, 14.0, {"panel_form_quality": 8.08, "panel_disclosure_structure": 1.0},
        {"B1_dietary_sugar": -2.0, "B0_moderate_watchlist": 0.0, "B1_harmful_additives": -4.0},
        {"presence_floor": {"target": 2.0, "pre_floor_score": 3.08, "applied": False},
         "inactive_penalty_details": []})
    bd["dimensions"]["dose"] = _dim(
        9.9015, 25.0, {"rda_ai_coverage": 9.0681, "panel_breadth": 1.1667, "critical_nutrient_coverage": 1.6667},
        {"B7_dose_safety": -2.0},
        {"B7_safety_evaluation": {"state_counts": {"confirmed_over_threshold": 2}, "flags": [
            {"state": "confirmed_over_threshold", "penalized": True, "pct_ul": 160.0}]}})
    bd["dimensions"]["evidence"] = _dim(10.0, 20.0, {"essential_panel_authority": 10.0}, {},
                                        {"evidence_result_state": "evaluated_authority"})
    out = _assemble(bd, module="multi_or_prenatal", verdict="CAUTION")
    assert out["quality_pillars_v4"]["formulation"]["score"] == 4.4
    assert out["quality_pillars_v4"]["dose"]["score"] == 8.6
    assert out["quality_pillars_v4"]["safety_hygiene"]["score"] == 4.0
    assert _entry(out, "formulation", "B1_harmful_additives")["kind"] == "deduction"
    assert _entry(out, "safety_hygiene", "additive_or_sweetener_penalty")["points"] == -4.0
    assert _entry(out, "safety_hygiene", "over_ul_penalty")["points"] == -2.0
    assert _entry(out, "dose", "B7_dose_safety")["points"] == pytest.approx(-2.0 * 20 / 23, abs=1e-4)
    _assert_reconciles(out)


# ---- Evidence floors and caps are bounds, never addends --------------------

def test_evidence_floor_and_cap_are_typed_bounds():
    bd = _meru_breakdown()
    bd["dimensions"]["evidence"] = _dim(
        17.0, 20.0, {"clinical_evidence_pipeline": 9.7956, "depth_bonus": 0.0,
                     "primary_evidence_floor": 18.0, "immune_support_evidence_cap": 17.0}, {},
        {"evidence_result_state": "evaluated_applicable"})
    bd["dimensions"]["formulation"]["metadata"]["immune_support"] = {"profile_applied": True}
    out = _assemble(bd)
    assert out["quality_pillars_v4"]["evidence"]["score"] == 20.0
    assert _entry(out, "evidence", "primary_evidence_floor")["kind"] == "floor"
    assert _entry(out, "evidence", "immune_support_evidence_cap")["kind"] == "cap"
    _assert_reconciles(out)


# ---- Verification tiers ------------------------------------------------------

@pytest.mark.parametrize("vb, scopes, expected, bound", [
    (_verification(b4d=2.0), {}, 8.0, None),
    (_verification(b4a=1.0), {"sku": 1}, 11.0, None),  # 6 + minimum cert 5 already meets the product floor
    (_verification(b4a=12.0, b4b=4.0, b4c=2.0, b4d=2.0, gmp_basis="verified_certification"), {"sku": 1}, 15.0, "verification_cap"),
])
def test_verification_receipt_itemizes_baseline_signals_and_tier_bounds(vb, scopes, expected, bound):
    bd = _meru_breakdown()
    vb["metadata"]["trust_metadata"]["verified_scope_counts"] = scopes
    bd["verification_bonus"] = vb
    out = _assemble(bd)
    pillar = out["quality_pillars_v4"]["verification"]
    assert pillar["score"] == expected
    assert _entry(out, "verification", "neutral_baseline")["points"] == 6.0
    if bound:
        assert bound in _ids(out, "verification")
    _assert_reconciles(out)


def test_quality_system_violation_is_a_verification_deduction():
    bd = _meru_breakdown()
    bd["manufacturer_violations"] = {"score": -4.0, "metadata": {"class_i_count_3y": 0}}
    out = _assemble(bd)
    assert out["quality_pillars_v4"]["verification"]["score"] == 2.0
    assert _entry(out, "verification", "quality_system_violation_penalty")["points"] == -4.0
    _assert_reconciles(out)


# ---- Unrated form neutral, blend withholding, fail-closed keys -------------

def test_unrated_form_neutral_is_a_neutral_floor_entry():
    bd = _meru_breakdown()
    bd["dimensions"]["formulation"] = _dim(
        0.0, 30.0, {"A1_bio_score": 0.0, "A3_delivery_system": 0.0, "A4_absorption_enhancer": 0.0,
                    "A5b_standardized_botanical": 0.0},
        {"B1_dietary_sugar": 0.0, "B0_moderate_watchlist": 0.0, "B1_harmful_additives": 0.0},
        {"formulation_profile": "generic_iqm", "iqm_form_quality_assessed_count": 0,
         "presence_floor": {"target": 2.0, "pre_floor_score": 0.0, "applied": False}})
    out = _assemble(bd)
    assert out["quality_pillars_v4"]["formulation"]["score"] == 12.0
    entry = _entry(out, "formulation", "unrated_form_neutral")
    assert entry["kind"] == "neutral" and entry["points"] == 12.0
    _assert_reconciles(out)


def test_blend_blocked_disclosure_bonus_is_shown_as_withheld():
    bd = _meru_breakdown()
    bd["dimensions"]["transparency"] = _transparency(
        bonus=0.0,
        penalties={"B2_false_allergen_free_claim": 0.0, "B5_proprietary_blend_opacity": -3.0,
                   "B6_marketing_claims": 0.0},
        metadata={"complete_active_disclosure": {"qualifies": False, "blockers": ["proprietary_blend_opacity"]}})
    out = _assemble(bd)
    withheld = _entry(out, "transparency", "complete_active_identity_dose_disclosure")
    assert withheld["points"] == 0.0 and withheld["withheld_by"] == ["proprietary_blend_opacity"]
    _assert_reconciles(out)


def test_unregistered_component_fails_closed():
    bd = _meru_breakdown()
    bd["dimensions"]["dose"]["components"]["invented_bonus"] = 3.0
    with pytest.raises(RuntimeError, match="unregistered v4 score component"):
        _assemble(bd)


def test_receipt_that_cannot_replay_the_module_result_fails_closed():
    bd = _meru_breakdown()
    bd["dimensions"]["dose"]["score"] = 15.0  # module result no longer equals its itemized parts
    with pytest.raises(RuntimeError, match="receipt does not reconcile"):
        _assemble(bd)


def test_unitemized_legacy_breakdown_gets_no_receipt():
    out = _assemble({
        "dimensions": {"formulation": {"score": 24, "max": 30}, "dose": {"score": 20, "max": 25},
                       "evidence": {"score": 18, "max": 20}, "transparency": {"score": 10, "max": 10}},
        "verification_bonus": {"score": 4, "max": 8}, "safety_hygiene_base": {"score": 4, "max": 4}},
        module="sports")
    assert all("receipt" not in p for p in out["quality_pillars_v4"].values())


def test_receipts_never_change_pillar_numbers():
    bd = _meru_breakdown()
    with_receipts = _assemble(copy.deepcopy(bd))
    for pillar in with_receipts["quality_pillars_v4"].values():
        pillar.pop("receipt")
    from scoring_v4 import quality_score
    original = quality_score._attach_score_receipts
    try:
        quality_score._attach_score_receipts = lambda pillars, *a, **k: pillars
        without = _assemble(copy.deepcopy(bd))
    finally:
        quality_score._attach_score_receipts = original
    assert with_receipts["quality_pillars_v4"] == without["quality_pillars_v4"]
    assert with_receipts["quality_score_v4_100"] == without["quality_score_v4_100"]
