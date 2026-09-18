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
    # -> full evidence credit against the generic engine's reachable 18.
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
    # normalized to the single-purpose achievable ceiling of 24, not breadth-30).
    out = assemble_quality_score(_shadow(module="sports", bd=_module_bd(form=24, form_max=30)))
    assert out["quality_pillars_v4"]["formulation"]["score"] >= 19.0


def test_formulation_cheap_form_stays_low() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    # magnesium-oxide-like cheap form (low raw formulation) must NOT be lifted
    out = assemble_quality_score(_shadow(module="generic", bd=_module_bd(form=2, form_max=30)))
    assert out["quality_pillars_v4"]["formulation"]["score"] < 4.0


def test_formulation_multi_uses_panel_reference() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    # multi/prenatal raw formulation is IQM panel form quality 12 + disclosure 2; ref 14
    out = assemble_quality_score(_shadow(module="multi_or_prenatal", bd=_module_bd(form=12, form_max=14)))
    f = out["quality_pillars_v4"]["formulation"]["score"]
    assert f == 17.1  # 12/14*20


def test_formulation_never_exceeds_20() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    out = assemble_quality_score(_shadow(module="sports", bd=_module_bd(form=30, form_max=30)))
    assert out["quality_pillars_v4"]["formulation"]["score"] <= 20.0


def _fish_oil_formulation_breakdown(*, disclosed_form: str | None = None) -> dict:
    from scoring_v4.modules.omega_formulation import score_formulation

    product = {
        "product_name": "Fish Oil 1200 mg",
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {
                    "name": "Fish Oil",
                    "canonical_id": "fish_oil",
                    "quantity": 2400,
                    "unit": "mg",
                },
                {
                    "name": "EPA (Eicosapentaenoic Acid)",
                    "canonical_id": "epa",
                    "quantity": 360,
                    "unit": "mg",
                },
                {
                    "name": "DHA (Docosahexaenoic Acid)",
                    "canonical_id": "dha",
                    "quantity": 240,
                    "unit": "mg",
                },
            ],
        },
    }
    if disclosed_form:
        product["labelText"] = {"raw": f"Fish oil in {disclosed_form} form"}

    formulation = score_formulation(product)
    bd = _module_bd(form=formulation["score"], form_max=formulation["max"])
    bd["dimensions"]["formulation"] = formulation
    return bd


def test_fish_oil_parent_identity_does_not_imply_molecular_form() -> None:
    from scoring_v4.quality_score import assemble_quality_score

    out = assemble_quality_score(_shadow(
        module="omega",
        bd=_fish_oil_formulation_breakdown(),
    ))
    formulation = out["quality_pillars_v4"]["formulation"]

    assert formulation["score"] == 11.7  # 7/12*20; omega formulation reference 12 since 1.3.0
    assert formulation["components"]["raw_formulation"] == 7.0
    assert "molecular form is not disclosed" in formulation["reason"].lower()
    assert "basic" not in formulation["reason"].lower()
    assert "low-cost" not in formulation["reason"].lower()
    assert "omega_form" not in {
        fact["id"]
        for fact in formulation.get("explanation", {}).get("facts", [])
    }


def test_omega_formulation_reason_separates_form_disclosure_from_concentration() -> None:
    from scoring_v4.quality_score import assemble_quality_score

    undisclosed = assemble_quality_score(_shadow(
        module="omega",
        bd=_fish_oil_formulation_breakdown(),
    ))["quality_pillars_v4"]["formulation"]
    disclosed = assemble_quality_score(_shadow(
        module="omega",
        bd=_fish_oil_formulation_breakdown(disclosed_form="triglyceride"),
    ))["quality_pillars_v4"]["formulation"]

    assert "molecular form is not disclosed" in undisclosed["reason"].lower()
    assert "epa + dha make up 25%" in undisclosed["reason"].lower()
    assert "molecular form is disclosed as triglyceride" in disclosed["reason"].lower()
    assert "epa + dha make up 25%" in disclosed["reason"].lower()
    assert disclosed["explanation"]["facts"] == [
        {
            "id": "omega_form",
            "label": "Molecular form",
            "value": "tg",
            "value_display": "Triglyceride",
        },
    ]


def test_invalid_omega_form_state_is_not_silently_called_undisclosed() -> None:
    from scoring_v4.quality_score import assemble_quality_score

    bd = _fish_oil_formulation_breakdown()
    bd["dimensions"]["formulation"]["metadata"]["form_detected"] = "unexpected_code"

    formulation = assemble_quality_score(_shadow(
        module="omega",
        bd=bd,
    ))["quality_pillars_v4"]["formulation"]

    assert "molecular-form data needs review" in formulation["reason"].lower()
    assert "not disclosed" not in formulation["reason"].lower()


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


def test_b7_over_ul_penalty_reduces_public_safety_pillar() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    bd = _module_bd(hygiene=4)
    bd["dimensions"]["dose"]["penalties"] = {"B7_dose_safety": -2.0}
    bd["dimensions"]["dose"]["metadata"] = {
        "B7_safety_evaluation": {
            "state_counts": {"confirmed_over_threshold": 1},
        }
    }

    out = assemble_quality_score(_shadow(module="generic", bd=bd))
    pillar = out["quality_pillars_v4"]["safety_hygiene"]

    assert pillar["score"] == 8.0
    assert pillar["components"]["over_ul_penalty"] == 2.0
    assert "exceed an established upper limit" in pillar["reason"]


def test_confirmed_over_ul_below_b7_penalty_threshold_is_still_explained() -> None:
    """A 100–150% UL exposure is a caution even before the B7 score penalty.

    The shared dose-safety evaluator records the confirmed exceedance and the
    verdict gate prevents SAFE.  The public Safety explanation must not hide
    that finding merely because the graduated B7 deduction starts at 150%.
    """
    from scoring_v4.quality_score import assemble_quality_score

    bd = _module_bd(hygiene=4)
    bd["dimensions"]["dose"]["penalties"] = {"B7_dose_safety": 0.0}
    bd["dimensions"]["dose"]["metadata"] = {
        "B7_safety_evaluation": {
            "state_counts": {"confirmed_over_threshold": 1},
        }
    }

    out = assemble_quality_score(_shadow(module="generic", bd=bd))
    pillar = out["quality_pillars_v4"]["safety_hygiene"]

    assert pillar["score"] == 10.0
    assert "over_ul_penalty" not in pillar["components"]
    assert "exceed an established upper limit" in pillar["reason"]


def test_b7_unresolved_only_explains_incomplete_check_without_claiming_excess() -> None:
    from scoring_v4.quality_score import assemble_quality_score

    bd = _module_bd(hygiene=4)
    bd["dimensions"]["dose"]["penalties"] = {"B7_dose_safety": -2.0}
    bd["dimensions"]["dose"]["metadata"] = {
        "B7_safety_evaluation": {
            "state_counts": {"material_but_unresolved": 1},
        }
    }

    out = assemble_quality_score(_shadow(module="generic", bd=bd))
    pillar = out["quality_pillars_v4"]["safety_hygiene"]

    assert pillar["score"] == 8.0
    assert pillar["components"]["over_ul_penalty"] == 2.0
    assert pillar["components"]["dose_safety_state_counts"] == {
        "material_but_unresolved": 1,
    }
    assert (
        "dose-safety checks could not be completed because the amount, form, "
        "or comparison basis was unresolved"
    ) in pillar["reason"]
    assert "above established upper limits" not in pillar["reason"]


def test_b7_mixed_state_explains_confirmed_excess_and_unresolved_checks() -> None:
    from scoring_v4.quality_score import assemble_quality_score

    bd = _module_bd(hygiene=4)
    bd["dimensions"]["dose"]["penalties"] = {"B7_dose_safety": -3.0}
    bd["dimensions"]["dose"]["metadata"] = {
        "B7_safety_evaluation": {
            "state_counts": {
                "confirmed_over_threshold": 1,
                "material_but_unresolved": 1,
            },
        }
    }

    out = assemble_quality_score(_shadow(module="generic", bd=bd))
    pillar = out["quality_pillars_v4"]["safety_hygiene"]

    assert pillar["score"] == 7.0
    assert "exceed an established upper limit" in pillar["reason"]
    assert "additional dose-safety checks remain unresolved" in pillar["reason"]


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
            # GMP counts only when audited (1.3.0); label GMP wording alone scores 0.
            "trust_metadata": {"verified_scope_counts": {"sku": 1}, "gmp_basis": "verified_certification"},
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
    (97.0, "Exceptional"), (92.0, "Excellent"), (85.0, "Very good"),
    (74.0, "Good"), (60.0, "Needs improvement"), (40.0, "Poor"),
])
def test_tier_bands(score, tier) -> None:
    from scoring_v4.quality_score import _tier
    assert _tier(score) == tier


def test_quality_tier_emitted() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    out = assemble_quality_score(_shadow())
    assert out["quality_tier"] in {"Exceptional", "Excellent", "Very good", "Good", "Needs improvement", "Poor"}


# The catalog ships a whole number and the app prints it beside the tier, so
# the tier is decided from that whole number. 491 shipped products (Sept 2026)
# read "70 Weak" / "80 Acceptable" / "55 Poor" because the band was chosen from
# the one-decimal total while the number was rounded half up.
@pytest.mark.parametrize("total,shipped,tier", [
    (69.6, 70, "Good"), (69.4, 69, "Needs improvement"), (69.5, 70, "Good"),
    (79.5, 80, "Very good"), (79.4, 79, "Good"),
    (89.5, 90, "Excellent"), (94.5, 95, "Exceptional"), (54.5, 55, "Needs improvement"), (54.4, 54, "Poor"),
])
def test_tier_follows_the_shipped_whole_number(total, shipped, tier) -> None:
    from scoring_v4.quality_score import _tier, shipped_whole_score
    assert shipped_whole_score(total) == shipped
    assert _tier(shipped_whole_score(total)) == tier


def test_assembled_tier_matches_shipped_score() -> None:
    """End to end: whatever total the module produces, the emitted tier is the
    band of the whole number the catalog will ship for it."""
    from scoring_v4 import quality_score as qs
    out = qs.assemble_quality_score(_shadow())
    assert out["quality_tier"] == qs._tier(qs.shipped_whole_score(out["quality_score_v4_100"]))


# ---- reason integrity ------------------------------------------------------

def test_every_pillar_has_a_reason() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    out = assemble_quality_score(_shadow())
    for name, p in out["quality_pillars_v4"].items():
        assert isinstance(p.get("reason"), str) and p["reason"], f"{name} missing reason"


def test_version_emitted() -> None:
    """The emitted version must be the config's, not a second copy of it.

    This used to pin the string literally, so every config bump broke it while
    test_v4_config_registry (which reads config_version) stayed green — two
    hand-maintained copies of one fact. What matters here is that the assembled
    score actually carries the shipped config version, whatever it currently is.
    """
    from scoring_v4.config_registry import config_version
    from scoring_v4.quality_score import assemble_quality_score

    out = assemble_quality_score(_shadow())
    assert out["quality_score_version"] == config_version("quality_score")


def test_uncapped_product_can_reach_a_true_100() -> None:
    """There is no hidden global 99 cap; full marks require every pillar."""
    from scoring_v4.quality_score import assemble_quality_score

    bd = _module_bd(
        form=24,
        dose=25,
        evidence=18,
        transparency=10,
        verification=8,
        manuf_trust=5,
        hygiene=4,
    )
    bd["verification_bonus"] = {
        "components": {
            "B4a_verified_certifications": 12.0,
            "B4b_gmp": 4.0,
            "B4d_brand_testing_posture": 2.0,
        },
        "metadata": {
            "trust_metadata": {"verified_scope_counts": {"sku": 1}}
        },
    }
    bd["manufacturer_trust"] = {
        "components": {
            "D1_manufacturer_reputation": 2.0,
            "D4_high_standard_region": 1.0,
        }
    }
    out = assemble_quality_score(_shadow(raw=100.0, module="sports", bd=bd))

    assert out["quality_score_v4_100"] == 100.0
    assert out["quality_tier"] == "Exceptional"
    assert out["quality_score_cap_v4"] is None


def test_public_quality_cap_limits_score_without_changing_raw() -> None:
    from scoring_v4.quality_score import assemble_quality_score

    bd = _module_bd(form=24, dose=21, evidence=18, verification=8, manuf_trust=5, hygiene=4)
    bd["metadata"] = {
        "public_quality_cap": {
            "id": "example_module_cap",
            "cap": 85.0,
            "reason": "A module-emitted public cap is applied as an explicit adjustment.",
        }
    }

    out = assemble_quality_score(_shadow(raw=88.5, module="generic", bd=bd))

    assert out["raw_score_v4_100"] == 88.5
    assert out["quality_score_v4_100"] == 85.0
    assert out["quality_score_cap_v4"]["id"] == "example_module_cap"
    assert out["quality_score_cap_v4"]["score_before_cap"] > 85.0
    assert out["quality_score_cap_v4"]["adjustment"] < 0
    assert out["quality_score_cap_v4"]["presentation"] == "explicit_adjustment"
    assert round(sum(p["score"] for p in out["quality_pillars_v4"].values()), 1) == (
        out["quality_score_cap_v4"]["score_before_cap"]
    )


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
    assert out["quality_score_cap_v4"]["adjustment"] == (
        88.0 - out["quality_score_cap_v4"]["score_before_cap"]
    )
    assert round(sum(p["score"] for p in out["quality_pillars_v4"].values()), 1) == (
        out["quality_score_cap_v4"]["score_before_cap"]
    )


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


def test_fail_open_neutral_when_only_label_gmp_wording() -> None:
    # label-text cGMP only (B4b from enricher text match, no audit) = unknown -> neutral 6, NOT zero
    v = _verif(_bd_verif(b4a=0.0, b4b=4.0, b4c=0.0, b4d=0.0, d1=0.0, d4=1.0))
    assert v["score"] == 6.0
    assert v["components"]["gmp"] == 0.0
    assert v["components"]["tier"] == "unknown"
    assert "unknown" in v["reason"].lower()


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


def test_region_does_not_count_and_reputation_is_capped() -> None:
    # manufacturing region is not verification; reputation is brand-level context capped at 2
    region_only = _verif(_bd_verif(b4a=0.0, b4b=0.0, b4c=0.0, b4d=0.0, d1=0.0, d4=1.0))
    reputation = _verif(_bd_verif(b4a=0.0, b4b=0.0, b4c=0.0, b4d=0.0, d1=5.0, d4=1.0))
    assert region_only["score"] == 6.0
    assert reputation["components"]["reputation"] == 2.0
    assert reputation["score"] == 8.0
    assert reputation["components"]["tier"] == "claim_or_brand"


def test_audited_gmp_counts_but_label_gmp_wording_does_not() -> None:
    label = _verif(_bd_verif(b4a=0.0, b4b=4.0, b4c=0.0, b4d=0.0, d1=0.0, d4=0.0))
    bd = _bd_verif(b4a=0.0, b4b=4.0, b4c=0.0, b4d=0.0, d1=0.0, d4=0.0)
    bd["verification_bonus"]["metadata"]["trust_metadata"]["gmp_basis"] = "manufacturer_facility"
    audited = _verif(bd)
    assert label["components"]["gmp"] == 0.0 and label["score"] == 6.0
    assert audited["components"]["gmp"] == 2.0 and audited["score"] == 8.0
    assert audited["components"]["tier"] == "manufacturing"


def test_more_independent_evidence_never_scores_lower() -> None:
    """Evidence tiers are ordered: unknown < claim/brand < manufacturing < product level.

    Before 1.3.0 a batch-COA product could score 2.5 and a label cert claim 7
    while an unknown product with reputation and region points scored 9."""
    unknown = _verif(_bd_verif(b4a=0.0, b4b=0.0, b4c=0.0, b4d=0.0, d1=0.0, d4=1.0))
    claim_best = _verif(_bd_verif(b4a=2.0, b4b=4.0, b4c=0.0, b4d=2.0, d1=2.0, d4=1.0,
                                  scope_counts={"label_asserted_product": 1}))
    manufacturing = _bd_verif_with_brand_only_cert()
    manufacturing["verification_bonus"]["components"].update({"B4b_gmp": 4.0, "B4d_brand_testing_posture": 2.0})
    manufacturing["verification_bonus"]["metadata"]["trust_metadata"]["gmp_basis"] = "manufacturer_facility"
    manufacturing["manufacturer_trust"]["components"]["D1_manufacturer_reputation"] = 2.0
    manufacturing_best = _verif(manufacturing)
    product_cert = _verif(_bd_verif(b4a=8.0, b4b=0.0, b4c=0.0, b4d=0.0, d1=0.0, d4=0.0))

    assert unknown["score"] < claim_best["score"] <= 8.0
    assert claim_best["score"] < manufacturing_best["score"] <= 10.0
    assert manufacturing_best["score"] < product_cert["score"]
    assert product_cert["score"] >= 11.0
    assert [v["components"]["tier"] for v in (unknown, claim_best, manufacturing_best, product_cert)] == [
        "unknown", "claim_or_brand", "manufacturing", "product"]


def test_verification_never_exceeds_15() -> None:
    v = _verif(_bd_verif(b4a=12.0, b4c=2.0, d1=2.0, d4=1.0))
    assert v["score"] <= 15.0


def test_label_claim_does_not_erase_verified_facility_evidence() -> None:
    from copy import deepcopy
    bd = _bd_verif_with_brand_only_cert()
    before = _verif(bd)
    after = deepcopy(bd)
    after["verification_bonus"]["components"]["B4a_verified_certifications"] = 2.0
    after["verification_bonus"]["metadata"]["trust_metadata"]["verified_scope_counts"] = {"label_asserted_product": 1}
    actual = _verif(after)
    assert actual["score"] >= before["score"]
    assert actual["components"]["tier"] == "manufacturing"


def test_omega_facility_metadata_reaches_the_shared_pillar() -> None:
    bd = _bd_verif(b4b=4, b4d=0, d1=0)
    bd["verification_bonus"]["metadata"]["trust_metadata"]["b4b"] = {"gmp_basis": "manufacturer_facility", "gmp_evidence": "audited facility"}
    assert _verif(bd)["components"]["gmp"] == 2.0


def test_lookup_or_qr_code_is_not_independent_product_testing() -> None:
    bd = _bd_verif(b4a=0, b4b=0, b4c=1, b4d=0, d1=0)
    actual = _verif(bd)
    assert actual["components"]["tier"] == "claim_or_brand"
    assert actual["score"] <= 8
    assert "independently verified" not in actual["reason"].lower().replace("not independently verified", "")


# ---- dose copy when the primary active has no benchmark ---------------------

def test_dose_reason_names_the_missing_primary_benchmark() -> None:
    from scoring_v4.quality_score import _pillar_dose, _config

    cfg = _config()
    dim = {
        "score": 16.0,
        "metadata": {
            "window_proxy_status": "partial_credit_primary_active_unassessed",
            "primary_active_unassessed": "cognigrape",
            "partial_credit_value": 16.0,
        },
    }
    out = _pillar_dose(dim, 20.0, "multi", cfg)
    assert "benchmark" in out["reason"].lower()
    assert "studied range" not in out["reason"].lower()


def test_disclosed_amount_without_reference_does_not_claim_studied_dose():
    from scoring_v4.quality_score import _pillar_dose, _config

    dim = {
        "score": 16.0,
        "metadata": {"window_proxy_status": "partial_credit_without_rda_proxy"},
    }
    out = _pillar_dose(dim, 20.0, "generic", _config())
    assert "benchmark is unavailable" in out["reason"]
    assert "studied range" not in out["reason"]
    # Explanation changes must not change the dose points.
    control = _pillar_dose({"score": 16.0}, 20.0, "generic", _config())
    assert out["score"] == control["score"]


def test_opaque_blend_reason_precedes_missing_reference_reason():
    from scoring_v4.quality_score import _pillar_dose, _config

    dim = {"score": 16.0, "metadata": {
        "window_proxy_status": "partial_credit_without_rda_proxy",
        "botanical_dose_band": "blend_total_only",
    }}
    out = _pillar_dose(dim, 20.0, "generic", _config())
    assert "individual ingredient amounts" in out["reason"]


def test_verification_pillar_names_the_audited_gmp_basis() -> None:
    """The app's GMP badge renders the pillar's decision, so the pillar records
    which audited source earned the GMP points (2026-09-16: 6,866 products had
    pillar GMP credit and no badge; 399 had a label-wording "GMP Certified"
    badge the pillar gave no credit)."""
    label = _verif(_bd_verif(b4a=0.0, b4b=4.0, b4c=0.0, b4d=0.0, d1=0.0, d4=0.0))
    facility = _bd_verif(b4a=0.0, b4b=4.0, b4c=0.0, b4d=0.0, d1=0.0, d4=0.0)
    facility["verification_bonus"]["metadata"]["trust_metadata"]["gmp_basis"] = "manufacturer_facility"
    certified = _bd_verif(b4a=0.0, b4b=4.0, b4c=0.0, b4d=0.0, d1=0.0, d4=0.0)
    certified["verification_bonus"]["metadata"]["trust_metadata"]["gmp_basis"] = "verified_certification"
    omega = _bd_verif(b4b=4, b4d=0, d1=0)
    omega["verification_bonus"]["metadata"]["trust_metadata"]["b4b"] = {
        "gmp_basis": "verified_certification", "gmp_evidence": "IFOS"}
    unknown = _bd_verif(b4a=0.0, b4b=4.0, b4c=0.0, b4d=0.0, d1=0.0, d4=0.0)
    unknown["verification_bonus"]["metadata"]["trust_metadata"]["gmp_basis"] = "label_claim"

    assert label["components"]["gmp_basis"] is None
    assert _verif(facility)["components"]["gmp_basis"] == "manufacturer_facility"
    assert _verif(certified)["components"]["gmp_basis"] == "verified_certification"
    assert _verif(omega)["components"]["gmp_basis"] == "verified_certification"
    assert _verif(unknown)["components"]["gmp"] == 0.0


def test_reputation_that_restates_certification_or_gmp_is_not_counted_twice() -> None:
    """D1 mid-tier reputation is derived only from verified certifications or
    audited GMP, which the pillar already scores as cert / gmp points."""
    restated = _bd_verif(b4a=0.0, b4b=4.0, b4c=0.0, b4d=0.0, d1=1.0, d4=0.0)
    restated["verification_bonus"]["metadata"]["trust_metadata"]["gmp_basis"] = "verified_certification"
    restated["manufacturer_trust"]["metadata"] = {"D1_source": "mid_tier_verified_evidence"}
    curated = _bd_verif(b4a=0.0, b4b=0.0, b4c=0.0, b4d=0.0, d1=2.0, d4=0.0)
    curated["manufacturer_trust"]["metadata"] = {"D1_source": "top_manufacturer_exact"}

    assert _verif(restated)["components"]["reputation"] == 0.0
    assert _verif(curated)["components"]["reputation"] == 2.0


def test_gmp_signal_wording_matches_its_basis() -> None:
    facility = _bd_verif(b4a=0.0, b4b=4.0, b4c=0.0, b4d=0.0, d1=0.0, d4=0.0)
    facility["verification_bonus"]["metadata"]["trust_metadata"]["gmp_basis"] = "manufacturer_facility"
    certified = _bd_verif(b4a=0.0, b4b=4.0, b4c=0.0, b4d=0.0, d1=0.0, d4=0.0)
    certified["verification_bonus"]["metadata"]["trust_metadata"]["gmp_basis"] = "verified_certification"

    assert "manufacturer is listed in an audited GMP facility registry" in _verif(facility)["reason"]
    assert "made in an audited GMP facility" not in _verif(facility)["reason"]
    assert "made in an audited GMP facility" in _verif(certified)["reason"]


# ---- POOR is owned by the shipped tier (2026-09-16) ---------------------------
# The verdict used the hidden module raw score (< 40) while users see the
# six-pillar score and tier: products scoring 55-60 ("Needs improvement") were
# POOR and products scoring 40-54 ("Poor") were SAFE.

def _lowest_tier() -> str:
    from scoring_v4.quality_score import _config
    return _config()["tiers"][-1]["name"]


def _poor_band_bd():
    return _module_bd(form=2, form_max=30, dose=2, evidence=1, transparency=1, verification=0,
                      manuf_trust=0, hygiene=0)


@pytest.mark.parametrize("provisional", ["SAFE", "POOR"])
def test_poor_verdict_follows_the_lowest_shipped_tier(provisional) -> None:
    from scoring_v4.quality_score import assemble_quality_score

    low = assemble_quality_score(_shadow(raw=60.0, verdict=provisional, bd=_poor_band_bd()))
    high = assemble_quality_score(_shadow(raw=30.0, verdict=provisional))

    assert low["quality_tier"] == _lowest_tier()
    assert low["v4_verdict"] == "POOR"
    assert high["quality_tier"] != _lowest_tier()
    assert high["v4_verdict"] == "SAFE"


def test_caution_keeps_precedence_over_the_tier() -> None:
    from scoring_v4.quality_score import assemble_quality_score

    out = assemble_quality_score(_shadow(raw=20.0, verdict="CAUTION", bd=_poor_band_bd()))

    assert out["quality_tier"] == _lowest_tier()
    assert out["v4_verdict"] == "CAUTION"


def test_module_score_no_longer_decides_poor() -> None:
    from score_supplements_v4 import _verdict_from_score

    assert _verdict_from_score(48.2, raw_score_100=31.0) == "SAFE"
    assert _verdict_from_score(12.0) == "SAFE"
    assert _verdict_from_score(12.0, "CAUTION") == "CAUTION"
    assert _verdict_from_score(None, None) == "NOT_SCORED"
