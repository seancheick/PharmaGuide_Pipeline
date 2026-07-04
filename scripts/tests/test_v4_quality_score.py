"""PharmaGuide six-pillar Quality Score — PR1 scaffold (Phase-1 linear mapping).

The public decision score = sum of six pillars (formulation/20, dose/20, evidence/20,
transparency/15, verification/15, safety_hygiene/10). PHASE 1 projects the existing v4
module breakdown into the pillars LINEARLY (no category-aware adapters yet) so the
side-by-side number + the bias is visible. raw_score_v4_100 is never changed. Hard safety
failures suppress the public score; the verdict shows instead.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _module_bd(form=24, form_max=30, dose=20, evidence=18, transparency=10, transp_max=10,
               verification=4, manuf_trust=3, hygiene=4, violation=0.0, class_i=0):
    bd = {
        "dimensions": {
            "formulation": {"score": form, "max": form_max},
            "dose": {"score": dose, "max": 25},
            "evidence": {"score": evidence, "max": 20},
            "transparency": {"score": transparency, "max": transp_max},
        },
        "verification_bonus": {"score": verification, "max": 8},
        "manufacturer_trust": {"score": manuf_trust, "max": 5},
        "safety_hygiene_base": {"score": hygiene, "max": 4},
    }
    if violation:
        # raw manufacturer-violation deduction is negative; class_i_count_3y splits
        # critical (safety) from quality-system (verification) per PR3.
        bd["manufacturer_violations"] = {
            "score": -abs(float(violation)),
            "metadata": {"class_i_count_3y": int(class_i),
                         "violation_count": max(1, int(class_i))},
        }
    return bd


def _shadow(raw=86.0, verdict="SAFE", module="sports", bd=None, suppressed_reason=None):
    breakdown = {"module": bd if bd is not None else _module_bd()}
    if suppressed_reason:
        breakdown["safety_gate"] = {"blocking_reason": suppressed_reason}
    return {
        "raw_score_v4_100": raw,
        "v4_verdict": verdict,
        "v4_module": module,
        "v4_breakdown": breakdown,
    }


# ---- pillar mapping --------------------------------------------------------

def test_pillar_sum_equals_quality_score() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    out = assemble_quality_score(_shadow())
    pillars = out["quality_pillars_v4"]
    total = round(sum(p["score"] for p in pillars.values()), 1)
    assert out["quality_score_v4_100"] == total


def test_pillars_use_six_pillar_weights() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    out = assemble_quality_score(_shadow())
    p = out["quality_pillars_v4"]
    assert p["formulation"]["max"] == 20
    assert p["dose"]["max"] == 20
    assert p["evidence"]["max"] == 20
    assert p["transparency"]["max"] == 15
    assert p["verification"]["max"] == 15
    assert p["safety_hygiene"]["max"] == 10


# ---- PR6 category-aware evidence pillar ------------------------------------

def test_evidence_strong_single_not_capped() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    # KSM-66/creatine-like: branded-RCT evidence 18 (the single-ingredient floor)
    # -> 18/19*20 ~= 18.9, NOT linear-capped at 18.
    out = assemble_quality_score(_shadow(module="generic", bd=_module_bd(evidence=18)))
    assert out["quality_pillars_v4"]["evidence"]["score"] >= 18.5


def test_evidence_weak_single_stays_low() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    # a weak-evidence single (unstudied botanical) must NOT be lifted
    out = assemble_quality_score(_shadow(module="generic", bd=_module_bd(evidence=6)))
    assert out["quality_pillars_v4"]["evidence"]["score"] < 8.0


def test_evidence_never_exceeds_20() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    out = assemble_quality_score(_shadow(module="generic", bd=_module_bd(evidence=20)))
    assert out["quality_pillars_v4"]["evidence"]["score"] <= 20.0


# ---- PR5 category-aware dose pillar ----------------------------------------

def test_dose_well_dosed_single_reaches_near_full() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    # KSM-66-like botanical: dose 21/25 raw -> 21/22*20 ~= 19.1
    out = assemble_quality_score(_shadow(module="generic",
                                         bd=_module_bd(dose=21, evidence=18)))
    assert out["quality_pillars_v4"]["dose"]["score"] >= 19.0


def test_dose_megadose_or_underdose_stays_low() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    # an overdosed/sub-clinical product already has LOW raw dose -> must NOT be lifted
    out = assemble_quality_score(_shadow(module="generic", bd=_module_bd(dose=8)))
    assert out["quality_pillars_v4"]["dose"]["score"] < 9.0


def test_dose_sports_full_dose_maxes() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    out = assemble_quality_score(_shadow(module="sports", bd=_module_bd(dose=25)))
    assert out["quality_pillars_v4"]["dose"]["score"] == 20.0


def test_dose_never_exceeds_20() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    out = assemble_quality_score(_shadow(module="generic", bd=_module_bd(dose=25)))
    assert out["quality_pillars_v4"]["dose"]["score"] <= 20.0


# ---- PR4 category-aware formulation pillar ---------------------------------

def test_formulation_single_ingredient_best_reaches_elite_band() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    # creatine-like: formulation 24/30 raw, sports single -> ~19-20/20 (purpose-fit,
    # normalized to the single-purpose achievable ceiling of 25, not breadth-30).
    out = assemble_quality_score(_shadow(module="sports", bd=_module_bd(form=24, form_max=30)))
    assert out["quality_pillars_v4"]["formulation"]["score"] >= 19.0


def test_formulation_cheap_form_stays_low() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    # magnesium-oxide-like cheap form (low raw formulation) must NOT be lifted
    out = assemble_quality_score(_shadow(module="generic", bd=_module_bd(form=2, form_max=30)))
    assert out["quality_pillars_v4"]["formulation"]["score"] < 4.0


def test_formulation_multi_uses_panel_reference() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    # multi/prenatal raw formulation is out of 25 (panel-aware already); ref 23
    out = assemble_quality_score(_shadow(module="multi_or_prenatal", bd=_module_bd(form=21, form_max=25)))
    f = out["quality_pillars_v4"]["formulation"]["score"]
    assert 17.0 <= f <= 19.0  # 21/23*20 ~= 18.3


def test_formulation_never_exceeds_20() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    out = assemble_quality_score(_shadow(module="sports", bd=_module_bd(form=30, form_max=30)))
    assert out["quality_pillars_v4"]["formulation"]["score"] <= 20.0


def test_archetype_classification() -> None:
    from scoring_v4.quality_score import _archetype
    assert _archetype("sports", {}) == "sports_single"
    assert _archetype("sports", {"metadata": {"sports_subtype": "pre_workout"}}) == "sports_pre_workout"
    assert _archetype("sports", {"metadata": {"sports_subtype": "protein"}}) == "sports_protein"
    assert _archetype("omega", {}) == "omega"
    assert _archetype("multi_or_prenatal", {}) == "prenatal_multi"
    botan = {"dimensions": {"formulation": {"metadata": {"botanical_profile_applied": True}}}}
    assert _archetype("generic", botan) == "generic_botanical_branded"
    assert _archetype("generic", {}) == "generic_single_molecule"



def test_safety_hygiene_pillar_clean_product_full_credit() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    out = assemble_quality_score(_shadow(bd=_module_bd(hygiene=4)))
    assert out["quality_pillars_v4"]["safety_hygiene"]["score"] == 10.0  # clean base 4/4 → 10


def test_safety_hygiene_banned_recalled_zeroes_pillar() -> None:
    # raw safety_hygiene_base = 0 when banned/recalled/watchlist present
    from scoring_v4.quality_score import assemble_quality_score
    out = assemble_quality_score(_shadow(verdict="CAUTION", bd=_module_bd(hygiene=0)))
    assert out["quality_pillars_v4"]["safety_hygiene"]["score"] == 0.0


# ---- PR3: manufacturer-violation split (was invisible in the public score) --

def test_quality_system_violation_lowers_verification_not_safety() -> None:
    # class_i == 0 → quality-system violation → verification pillar absorbs it
    from scoring_v4.quality_score import assemble_quality_score
    base = assemble_quality_score(_shadow(module="generic", bd=_module_bd()))
    viol = assemble_quality_score(_shadow(module="generic", bd=_module_bd(violation=2.5, class_i=0)))
    bp = base["quality_pillars_v4"]; vp = viol["quality_pillars_v4"]
    assert vp["verification"]["score"] == round(bp["verification"]["score"] - 2.5, 1)
    assert vp["safety_hygiene"]["score"] == bp["safety_hygiene"]["score"]  # safety untouched


def test_class_i_recall_lowers_safety_not_verification() -> None:
    # class_i > 0 → critical safety recall → safety pillar absorbs it
    from scoring_v4.quality_score import assemble_quality_score
    base = assemble_quality_score(_shadow(module="generic", bd=_module_bd()))
    viol = assemble_quality_score(_shadow(module="generic", bd=_module_bd(violation=4.0, class_i=1)))
    bp = base["quality_pillars_v4"]; vp = viol["quality_pillars_v4"]
    assert vp["safety_hygiene"]["score"] == round(bp["safety_hygiene"]["score"] - 4.0, 1)
    assert vp["verification"]["score"] == bp["verification"]["score"]  # verification untouched


def test_violation_penalty_floors_pillar_at_zero() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    viol = assemble_quality_score(_shadow(module="generic", bd=_module_bd(violation=99.0, class_i=1)))
    assert viol["quality_pillars_v4"]["safety_hygiene"]["score"] == 0.0


def test_b1_additive_and_sugar_penalties_reduce_public_safety_pillar() -> None:
    # The additive/sweetener signal still lowers formulation, but the public
    # Safety Hygiene pillar must not claim 10/10 when additive concerns exist.
    from scoring_v4.quality_score import assemble_quality_score
    bd = _module_bd(form=2, form_max=30, hygiene=4)
    bd["dimensions"]["formulation"]["penalties"] = {
        "B1_harmful_additives": -1.0,
        "B1_dietary_sugar": -2.0,
    }

    out = assemble_quality_score(_shadow(module="generic", bd=bd))
    pillar = out["quality_pillars_v4"]["safety_hygiene"]

    assert pillar["score"] == 7.0
    assert pillar["components"]["additive_or_sweetener_penalty"] == 3.0
    assert "additive or sweetener" in pillar["reason"]


def test_sleep_melatonin_gummy_penalty_reduces_public_safety_pillar() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    bd = _module_bd(form=2, form_max=30, hygiene=4)
    bd["dimensions"]["formulation"]["penalties"] = {
        "B1_sleep_melatonin_gummy": -2.0,
    }

    out = assemble_quality_score(_shadow(module="generic", bd=bd))
    pillar = out["quality_pillars_v4"]["safety_hygiene"]

    assert pillar["score"] == 8.0
    assert pillar["components"]["additive_or_sweetener_penalty"] == 2.0
    assert "additive or sweetener" in pillar["reason"]


def test_b7_over_ul_penalty_reduces_public_safety_pillar() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    bd = _module_bd(hygiene=4)
    bd["dimensions"]["dose"]["penalties"] = {"B7_dose_safety": -2.0}

    out = assemble_quality_score(_shadow(module="generic", bd=bd))
    pillar = out["quality_pillars_v4"]["safety_hygiene"]

    assert pillar["score"] == 8.0
    assert pillar["components"]["over_ul_penalty"] == 2.0
    assert "above established upper limits" in pillar["reason"]


def test_verification_pillar_reads_lowercase_v4_component_keys() -> None:
    from scoring_v4.quality_score import assemble_quality_score

    bd = _module_bd()
    bd["verification_bonus"] = {
        "score": 8.0,
        "max": 8.0,
        "components": {
            "b4a_verified_certifications": 10.0,
            "b4b_gmp": 4.0,
            "b4d_brand_testing_posture": 2.0,
        },
        "metadata": {
            "trust_metadata": {"verified_scope_counts": {"sku": 1}},
        },
    }

    out = assemble_quality_score(_shadow(module="omega", bd=bd))
    verification = out["quality_pillars_v4"]["verification"]

    assert verification["score"] > 9.0
    assert verification["components"]["cert"] > 0.0
    assert verification["components"]["gmp"] > 0.0
    assert verification["components"]["brand_testing"] > 0.0
    assert verification["components"]["fail_open_neutral"] is False


def test_active_simethicone_is_caution_not_blocked() -> None:
    from scoring_v4.gate_safety import evaluate_safety_gate

    result = evaluate_safety_gate({
        "activeIngredients": [{"name": "Simethicone"}],
        "inactiveIngredients": [],
    })

    assert result.verdict == "CAUTION"
    assert result.short_circuits_scoring is False
    assert result.blocking_reason is None
    assert "B0_WATCHLIST_SUBSTANCE" in result.safety_signals


def test_inactive_polydimethylsiloxane_is_warning_only() -> None:
    from scoring_v4.gate_safety import evaluate_safety_gate

    result = evaluate_safety_gate({
        "activeIngredients": [],
        "inactiveIngredients": [{"name": "Polydimethylsiloxane"}],
    })

    assert result.verdict is None
    assert result.short_circuits_scoring is False
    assert result.blocking_reason is None
    assert "B0_WATCHLIST_EXCIPIENT_WARNING_ONLY" in result.safety_signals


def test_violation_makes_quality_reflect_it_and_sum_holds() -> None:
    # the gap PR3 fixes: a violation product used to score IDENTICAL to a clean one
    from scoring_v4.quality_score import assemble_quality_score
    clean = assemble_quality_score(_shadow(module="generic", bd=_module_bd()))
    viol = assemble_quality_score(_shadow(module="generic", bd=_module_bd(violation=2.5, class_i=0)))
    assert viol["quality_score_v4_100"] < clean["quality_score_v4_100"]
    s = round(sum(p["score"] for p in viol["quality_pillars_v4"].values()), 1)
    assert s == viol["quality_score_v4_100"]


def test_violation_does_not_change_raw_score() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    viol = assemble_quality_score(_shadow(raw=70.2, module="generic", bd=_module_bd(violation=2.5)))
    assert viol["raw_score_v4_100"] == 70.2  # raw audit score never moves


# ---- raw preservation ------------------------------------------------------

def test_raw_score_never_changes() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    out = assemble_quality_score(_shadow(raw=86.0))
    assert out["raw_score_v4_100"] == 86.0
    assert out["raw_score_v4_100"] == 86.0  # explicit public-contract alias


# ---- suppression -----------------------------------------------------------

def test_blocked_suppresses_quality_score() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    out = assemble_quality_score(_shadow(verdict="BLOCKED", suppressed_reason="banned_substance"))
    assert out["quality_score_v4_100"] is None
    assert out["quality_score_status"] == "suppressed_safety"
    assert out["quality_score_suppressed_reason"] == "banned_substance"


def test_unsafe_suppresses_quality_score() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    out = assemble_quality_score(_shadow(verdict="UNSAFE"))
    assert out["quality_score_v4_100"] is None
    assert out["quality_score_status"] == "suppressed_safety"


def test_not_scored_status() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    out = assemble_quality_score(_shadow(verdict="NOT_SCORED", raw=None))
    assert out["quality_score_v4_100"] is None
    assert out["quality_score_status"] == "not_scored"


def test_caution_keeps_score() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    out = assemble_quality_score(_shadow(verdict="CAUTION"))
    assert out["quality_score_v4_100"] is not None
    assert out["quality_score_status"] == "scored"


def test_safe_is_scored() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    out = assemble_quality_score(_shadow(verdict="SAFE"))
    assert out["quality_score_status"] == "scored"


# ---- tiers -----------------------------------------------------------------

@pytest.mark.parametrize("score,tier", [
    (97.0, "Elite"), (92.0, "Excellent"), (85.0, "Strong"),
    (74.0, "Acceptable"), (60.0, "Weak"), (40.0, "Poor"),
])
def test_tier_bands(score, tier) -> None:
    from scoring_v4.quality_score import _tier
    assert _tier(score) == tier


def test_quality_tier_emitted() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    out = assemble_quality_score(_shadow())
    assert out["quality_tier"] in {"Elite", "Excellent", "Strong", "Acceptable", "Weak", "Poor"}


# ---- reason integrity ------------------------------------------------------

def test_every_pillar_has_a_reason() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    out = assemble_quality_score(_shadow())
    for name, p in out["quality_pillars_v4"].items():
        assert isinstance(p.get("reason"), str) and p["reason"], f"{name} missing reason"


def test_version_emitted() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    out = assemble_quality_score(_shadow())
    assert out["quality_score_version"].startswith("1.0.4")  # versioned public contract


def test_public_quality_cap_limits_score_without_changing_raw() -> None:
    from scoring_v4.quality_score import assemble_quality_score

    bd = _module_bd(form=24, dose=21, evidence=18, verification=8, manuf_trust=5, hygiene=4)
    bd["metadata"] = {
        "public_quality_cap": {
            "id": "generic_astaxanthin_single",
            "cap": 85.0,
            "reason": "Single-ingredient astaxanthin has promising but not elite clinical evidence.",
        }
    }

    out = assemble_quality_score(_shadow(raw=88.5, module="generic", bd=bd))

    assert out["raw_score_v4_100"] == 88.5
    assert out["quality_score_v4_100"] == 85.0
    assert out["quality_score_cap_v4"]["id"] == "generic_astaxanthin_single"
    assert out["quality_score_cap_v4"]["score_before_cap"] > 85.0
    assert round(sum(p["score"] for p in out["quality_pillars_v4"].values()), 1) == 85.0


def test_sports_preworkout_public_cap_limits_score_below_creatine_ceiling() -> None:
    from scoring_v4.quality_score import assemble_quality_score

    bd = _module_bd(form=30, dose=25, evidence=20, verification=8, manuf_trust=5, hygiene=4)
    bd["metadata"] = {
        "sports_subtype": "pre_workout",
        "public_quality_cap": {
            "id": "sports_pre_workout",
            "cap": 88.0,
            "reason": "Transparent pre-workout stacks should not score like focused creatine/protein products.",
        },
    }

    out = assemble_quality_score(_shadow(raw=94.0, module="sports", bd=bd))

    assert out["quality_score_v4_100"] == 88.0
    assert out["raw_score_v4_100"] == 94.0
    assert out["quality_score_cap_v4"]["id"] == "sports_pre_workout"
    assert round(sum(p["score"] for p in out["quality_pillars_v4"].values()), 1) == 88.0


# ---- PR2 verification pillar (saturate-subset + fail-open neutral) ----------

def _bd_verif(
    b4a=0.0,
    b4b=4.0,
    b4c=0.0,
    b4d=2.0,
    d1=2.0,
    d4=1.0,
    scope_counts=None,
):
    """module breakdown with verification + trust components for the verification pillar."""
    bd = _module_bd()
    bd["verification_bonus"]["components"] = {
        "B4a_verified_certifications": b4a, "B4b_gmp": b4b,
        "B4c_batch_traceability": b4c, "B4d_brand_testing_posture": b4d,
    }
    if scope_counts is None:
        scope_counts = {"sku": 1} if b4a > 0 else {}
    bd["verification_bonus"]["metadata"] = {
        "trust_metadata": {"verified_scope_counts": scope_counts}
    }
    bd["manufacturer_trust"]["components"] = {
        "D1_manufacturer_reputation": d1, "D2_disclosure_quality": 1.0,
        "D3_physician_formulated": 0.5, "D4_high_standard_region": d4,
        "D5_sustainability": 0.5,
    }
    return bd


def _bd_verif_with_brand_only_cert() -> dict:
    bd = _bd_verif(b4a=0.0, b4b=0.0, b4c=0.0, b4d=0.0)
    bd["verification_bonus"]["metadata"] = {
        "trust_metadata": {
            "verified_unscored_scope_counts": {"brand_only": 1},
            "verified_brand_only_programs": ["usp verified"],
        }
    }
    return bd


def _verif(bd):
    from scoring_v4.quality_score import assemble_quality_score
    out = assemble_quality_score(_shadow(bd=bd))
    return out["quality_pillars_v4"]["verification"]


def test_gold_cert_saturates_verification() -> None:
    # one gold third-party cert (B4a=12) saturates the pillar near max
    v = _verif(_bd_verif(b4a=12.0))
    assert v["score"] >= 14.0


def test_strong_cert_scores_high() -> None:
    v = _verif(_bd_verif(b4a=8.0))
    assert v["score"] >= 11.0


def test_label_asserted_cert_stays_small_in_public_pillar() -> None:
    v = _verif(_bd_verif(
        b4a=2.0,
        b4b=0.0,
        b4c=0.0,
        b4d=0.0,
        scope_counts={"label_asserted_product": 1},
    ))

    assert v["components"]["cert"] == 2.0
    assert "label claims third-party certification" in v["reason"].lower()
    assert v["score"] < _verif(_bd_verif(b4a=8.0, b4b=0.0, b4c=0.0, b4d=0.0))["score"]


def test_omega_b4a_scored_entries_scope_counts_as_registry_cert() -> None:
    bd = _bd_verif(b4a=10.0, b4b=0.0, b4c=0.0, b4d=2.0, scope_counts={})
    bd["verification_bonus"]["metadata"] = {
        "trust_metadata": {
            "b4a": {
                "B4a_scored_entries": [
                    {"program": "IFOS", "scope": "product_line", "pts": 10.0}
                ]
            }
        }
    }

    v = _verif(bd)

    assert v["components"]["cert"] == 12.0
    assert v["components"]["brand_testing"] == 2.0


def test_fail_open_neutral_when_no_cert_no_coa() -> None:
    # self-asserted cGMP only (B4a=0, B4c=0) = data-UNKNOWN -> neutral baseline, NOT zero
    v = _verif(_bd_verif(b4a=0.0, b4b=4.0, b4c=0.0))
    assert 6.0 <= v["score"] <= 10.0  # neutral 6 + soft, not cratered
    assert "neutral" in v["reason"].lower() or "unknown" in v["reason"].lower()


def test_brand_only_verified_cert_lifts_above_unknown_without_b4a_credit() -> None:
    unknown = _verif(_bd_verif(b4a=0.0, b4b=0.0, b4c=0.0, b4d=0.0))["score"]
    v = _verif(_bd_verif_with_brand_only_cert())

    assert v["score"] == unknown + 2.0
    assert v["components"]["cert"] == 0.0
    assert v["components"]["brand_only_cert"] == 2.0
    assert v["components"]["fail_open_neutral"] is False
    assert "brand/facility cert" in v["reason"].lower()
    assert "no third-party cert/coa" not in v["reason"].lower()


def test_brand_only_cert_does_not_stack_with_product_cert() -> None:
    product_cert = _verif(_bd_verif(b4a=8.0, b4b=0.0, b4c=0.0, b4d=0.0))
    bd = _bd_verif_with_brand_only_cert()
    bd["verification_bonus"]["components"]["B4a_verified_certifications"] = 8.0
    bd["verification_bonus"]["metadata"]["trust_metadata"]["verified_scope_counts"] = {"sku": 1}
    stacked = _verif(bd)

    assert stacked["score"] == product_cert["score"]
    assert stacked["components"]["brand_only_cert"] == 0.0


def test_brand_only_cert_does_not_unlock_gmp_and_testing_stack() -> None:
    unknown = _verif(_bd_verif(b4a=0.0, b4b=4.0, b4c=0.0, b4d=2.0))
    bd = _bd_verif_with_brand_only_cert()
    bd["verification_bonus"]["components"]["B4b_gmp"] = 4.0
    bd["verification_bonus"]["components"]["B4d_brand_testing_posture"] = 2.0
    lifted = _verif(bd)

    assert lifted["score"] == unknown["score"] + 2.0
    assert lifted["components"]["brand_only_cert"] == 2.0


def test_self_cgmp_does_not_carry_verification() -> None:
    # a product with ONLY self-cGMP must not score like a certified one
    cert = _verif(_bd_verif(b4a=12.0))["score"]
    self_cgmp = _verif(_bd_verif(b4a=0.0, b4b=4.0))["score"]
    assert self_cgmp < cert - 4.0


def test_coa_counts_as_real_signal_not_fail_open() -> None:
    # COA present (B4c) is a hard signal -> NOT the fail-open path
    v = _verif(_bd_verif(b4a=0.0, b4c=2.0))
    assert "neutral" not in v["reason"].lower()


def test_soft_signals_capped_at_3() -> None:
    # huge soft (reputation+region) cannot exceed the 3-point soft cap
    low = _verif(_bd_verif(b4a=12.0, d1=0.0, d4=0.0))["score"]
    high = _verif(_bd_verif(b4a=12.0, d1=2.0, d4=1.0))["score"]
    assert high - low <= 3.0 + 1e-9


def test_verification_never_exceeds_15() -> None:
    v = _verif(_bd_verif(b4a=12.0, b4c=2.0, d1=2.0, d4=1.0))
    assert v["score"] <= 15.0
