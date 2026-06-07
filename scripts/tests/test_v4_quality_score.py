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
               verification=4, manuf_trust=3, hygiene=4):
    return {
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


def _shadow(raw=86.0, verdict="SAFE", module="sports", bd=None, suppressed_reason=None):
    breakdown = {"module": bd if bd is not None else _module_bd()}
    if suppressed_reason:
        breakdown["safety_gate"] = {"blocking_reason": suppressed_reason}
    return {
        "shadow_score_v4_100": raw,
        "shadow_score_v4_verdict": verdict,
        "shadow_score_v4_module": module,
        "shadow_score_v4_breakdown": breakdown,
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
    assert _archetype("omega", {}) == "omega"
    assert _archetype("multi_or_prenatal", {}) == "prenatal_multi"
    botan = {"dimensions": {"formulation": {"metadata": {"botanical_profile_applied": True}}}}
    assert _archetype("generic", botan) == "generic_botanical_branded"
    assert _archetype("generic", {}) == "generic_single_molecule"


def test_evidence_pillar_is_identity_when_caps_match() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    out = assemble_quality_score(_shadow(bd=_module_bd(evidence=18)))
    assert out["quality_pillars_v4"]["evidence"]["score"] == 18.0  # (18/20)*20


def test_safety_hygiene_pillar_scales_to_10() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    out = assemble_quality_score(_shadow(bd=_module_bd(hygiene=4)))
    assert out["quality_pillars_v4"]["safety_hygiene"]["score"] == 10.0  # (4/4)*10


# ---- raw preservation ------------------------------------------------------

def test_raw_score_never_changes() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    out = assemble_quality_score(_shadow(raw=86.0))
    assert out["shadow_score_v4_100"] == 86.0
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
    assert "phase1" in out["quality_score_version"] or "1.0.0" in out["quality_score_version"]


# ---- PR2 verification pillar (saturate-subset + fail-open neutral) ----------

def _bd_verif(b4a=0.0, b4b=4.0, b4c=0.0, b4d=2.0, d1=2.0, d4=1.0):
    """module breakdown with verification + trust components for the verification pillar."""
    bd = _module_bd()
    bd["verification_bonus"]["components"] = {
        "B4a_verified_certifications": b4a, "B4b_gmp": b4b,
        "B4c_batch_traceability": b4c, "B4d_brand_testing_posture": b4d,
    }
    bd["manufacturer_trust"]["components"] = {
        "D1_manufacturer_reputation": d1, "D2_disclosure_quality": 1.0,
        "D3_physician_formulated": 0.5, "D4_high_standard_region": d4,
        "D5_sustainability": 0.5,
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


def test_fail_open_neutral_when_no_cert_no_coa() -> None:
    # self-asserted cGMP only (B4a=0, B4c=0) = data-UNKNOWN -> neutral baseline, NOT zero
    v = _verif(_bd_verif(b4a=0.0, b4b=4.0, b4c=0.0))
    assert 6.0 <= v["score"] <= 10.0  # neutral 6 + soft, not cratered
    assert "neutral" in v["reason"].lower() or "unknown" in v["reason"].lower()


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
