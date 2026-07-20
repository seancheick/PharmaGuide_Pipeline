"""Consumer-copy contract for the v4 six-pillar `reason` strings.

The v4 public quality score emits one human-readable ``reason`` per pillar
(formulation, dose, evidence, transparency, verification, safety_hygiene) plus a
``v4_score_explanation`` (top strengths / drags) built from those same reasons.
These strings are shown to END USERS in the Flutter "How it scores" UI, so they
must read as plain English a supplement shopper understands — NOT developer
jargon. This test is the guard: it asserts the reasons across a representative
set of scored products contain none of the internal-jargon tokens, are never
empty, and stay short.

It deliberately does NOT assert exact copy (that would be brittle); it asserts
the *contract* (no jargon, non-empty, length-bounded). Scores/thresholds are not
checked here — those are covered by ``test_v4_quality_score.py``.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


# Tokens that must NEVER reach a consumer (case-insensitive substring match).
# These are internal scoring vocabulary (module/archetype/phase names, raw
# fractions, arrows, "ceiling"/"breadth", etc.) that leak the math instead of
# explaining the result.
BANNED_JARGON = [
    "archetype",
    "breadth-30",
    "breadth",
    "phase-",
    "bio=",
    "bio_score",
    "→",            # → arrow
    "->",                # ascii arrow variant
    "module",
    "ceiling",
    "/25",               # pillar maxes are /20, /15, /10 — never /25
    "single molecule",
    "anchor",
    "mass-dominant",
    "raw_score",
    "affine",
    "rubric",
]

MAX_REASON_LEN = 140


# ── product builders (reuse the proven harness shape from test_v4_quality_score) ──

def _module_bd(form=24, form_max=30, dose=20, evidence=18, transparency=10,
               transp_max=10, verification=4, manuf_trust=3, hygiene=4,
               violation=0.0, class_i=0):
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
        bd["manufacturer_violations"] = {
            "score": -abs(float(violation)),
            "metadata": {"class_i_count_3y": int(class_i),
                         "violation_count": max(1, int(class_i))},
        }
    return bd


def _bd_verif(b4a=0.0, b4b=4.0, b4c=0.0, b4d=2.0, d1=2.0, d4=1.0):
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


def _bd_verif_brand_only():
    bd = _bd_verif(b4a=0.0, b4b=0.0, b4c=0.0, b4d=0.0)
    bd["verification_bonus"]["metadata"] = {
        "trust_metadata": {
            "verified_unscored_scope_counts": {"brand_only": 1},
            "verified_brand_only_programs": ["usp verified"],
        }
    }
    return bd


def _bd_botanical(form=20, dose=21, evidence=18):
    """generic_botanical_branded archetype (e.g. KSM-66)."""
    bd = _module_bd(form=form, form_max=30, dose=dose, evidence=evidence)
    bd["dimensions"]["formulation"]["metadata"] = {"botanical_profile_applied": True}
    return bd


def _shadow(raw=86.0, verdict="SAFE", module="sports", bd=None,
            suppressed_reason=None, clean_label_hits=None):
    breakdown = {"module": bd if bd is not None else _module_bd()}
    if suppressed_reason:
        breakdown["safety_gate"] = {"blocking_reason": suppressed_reason}
    if clean_label_hits is not None:
        breakdown.setdefault("safety_gate", {})["clean_label_hits"] = clean_label_hits
    return {
        "raw_score_v4_100": raw,
        "v4_verdict": verdict,
        "v4_module": module,
        "v4_breakdown": breakdown,
    }


def _titanium_dioxide_hit():
    """A clean-label additive hit (drives the safety pillar's penalty branch)."""
    return [{
        "name": "Titanium Dioxide",
        "standard_name": "titanium dioxide",
        "role": "inactive",
        "tier": "elevated",
        "penalty_base": 2.0,
        "status": "flagged",
        "consumer_note": "EU-restricted colorant.",
        "matched_rule_id": "e171",
    }]


def _scored_corpus():
    """A representative spread of scored products: every archetype/module, plus the
    edge branches that produce distinct pillar reasons (banned/recalled, Class I
    recall, quality-system violation, brand-only cert, fail-open verification,
    clean-label additive, cheap form / weak evidence)."""
    return {
        "sports_strong": _shadow(module="sports", bd=_module_bd()),
        "generic_single": _shadow(module="generic", bd=_module_bd()),
        "generic_botanical": _shadow(module="generic", bd=_bd_botanical()),
        "omega": _shadow(module="omega", bd=_module_bd()),
        "probiotic": _shadow(module="probiotic", bd=_module_bd()),
        "prenatal_multi": _shadow(module="multi_or_prenatal",
                                  bd=_module_bd(form=21, form_max=25)),
        "cheap_form": _shadow(module="generic", bd=_module_bd(form=2, form_max=30)),
        "weak_evidence": _shadow(module="generic", bd=_module_bd(evidence=6, dose=8)),
        # Mid-band across the four banded pillars (formulation/dose/evidence/
        # transparency) so the "middle" copy is exercised by the guard too.
        "mid_band": _shadow(module="generic",
                            bd=_module_bd(form=15, form_max=30, dose=15,
                                          evidence=12, transparency=6, transp_max=10)),
        "banned_recalled_caution": _shadow(verdict="CAUTION", module="generic",
                                            bd=_module_bd(hygiene=0)),
        "class_i_recall": _shadow(module="generic",
                                  bd=_module_bd(violation=4.0, class_i=1)),
        "quality_system_violation": _shadow(module="generic",
                                            bd=_module_bd(violation=2.5, class_i=0)),
        "verif_gold_cert": _shadow(bd=_bd_verif(b4a=12.0)),
        "verif_coa": _shadow(bd=_bd_verif(b4a=0.0, b4c=2.0)),
        "verif_fail_open": _shadow(bd=_bd_verif(b4a=0.0, b4b=4.0, b4c=0.0)),
        "verif_brand_only": _shadow(bd=_bd_verif_brand_only()),
        "verif_qs_violation": _shadow(module="generic",
                                      bd=_module_bd(violation=2.0, class_i=0)),
        "clean_label_additive": _shadow(module="generic", bd=_module_bd(),
                                        clean_label_hits=_titanium_dioxide_hit()),
    }


def _assemble(shadow):
    from scoring_v4.quality_score import assemble_quality_score
    return assemble_quality_score(shadow)


# ── helpers ────────────────────────────────────────────────────────────────

def _assert_consumer_ready(reason, where):
    assert isinstance(reason, str) and reason.strip(), f"{where}: empty reason"
    low = reason.lower()
    for tok in BANNED_JARGON:
        assert tok.lower() not in low, (
            f"{where}: jargon token {tok!r} leaked into consumer reason: {reason!r}"
        )
    assert len(reason) <= MAX_REASON_LEN, (
        f"{where}: reason too long ({len(reason)} > {MAX_REASON_LEN}): {reason!r}"
    )


# ── the contract: every pillar reason is consumer-ready ──────────────────────

@pytest.mark.parametrize("case", sorted(_scored_corpus().keys()))
def test_pillar_reasons_have_no_jargon(case) -> None:
    out = _assemble(_scored_corpus()[case])
    pillars = out["quality_pillars_v4"]
    assert pillars, f"{case}: expected scored pillars"
    for pillar_name, pillar in pillars.items():
        _assert_consumer_ready(pillar.get("reason"), f"{case}/{pillar_name}")


# ── the contract: every v4_score_explanation reason is consumer-ready ────────

@pytest.mark.parametrize("case", sorted(_scored_corpus().keys()))
def test_score_explanation_reasons_have_no_jargon(case) -> None:
    from build_final_db import _build_v4_score_explanation
    out = _assemble(_scored_corpus()[case])
    explanation = _build_v4_score_explanation(out["quality_pillars_v4"])
    assert explanation is not None, f"{case}: expected an explanation"
    for bucket in ("strengths", "drags"):
        for item in explanation.get(bucket, []):
            _assert_consumer_ready(
                item.get("reason"), f"{case}/explanation/{bucket}/{item.get('pillar')}"
            )


def test_all_six_pillars_covered_across_corpus() -> None:
    """Guard the guard: make sure the corpus actually exercises all six pillars
    (so a future pillar can't silently escape the jargon check)."""
    seen = set()
    for shadow in _scored_corpus().values():
        seen.update(_assemble(shadow)["quality_pillars_v4"].keys())
    assert seen == {
        "formulation", "dose", "evidence",
        "transparency", "verification", "safety_hygiene",
    }, f"corpus does not cover all six pillars, saw {sorted(seen)}"


def test_probiotic_aggregate_cfu_copy_does_not_claim_every_amount_is_disclosed() -> None:
    bd = _module_bd(transparency=13, transp_max=15)
    bd["dimensions"]["transparency"]["components"] = {
        "strain_identities_named": 8.0,
        "per_strain_cfu_on_label": 0.0,
        "aggregate_cfu_disclosure_proxy": 3.0,
    }
    out = _assemble(_shadow(module="probiotic", bd=bd))

    reason = out["quality_pillars_v4"]["transparency"]["reason"]
    assert reason == (
        "All strains are named and total CFU is disclosed, but amounts "
        "for each strain are not."
    )
    assert "every amount is disclosed" not in reason.lower()
