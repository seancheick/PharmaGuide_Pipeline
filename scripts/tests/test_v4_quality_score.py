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


def test_formulation_pillar_linear_remap() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    # formulation 24/30 -> (24/30)*20 = 16.0
    out = assemble_quality_score(_shadow(bd=_module_bd(form=24, form_max=30)))
    assert out["quality_pillars_v4"]["formulation"]["score"] == 16.0


def test_evidence_pillar_is_identity_when_caps_match() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    out = assemble_quality_score(_shadow(bd=_module_bd(evidence=18)))
    assert out["quality_pillars_v4"]["evidence"]["score"] == 18.0  # (18/20)*20


def test_verification_pillar_merges_bonus_and_trust() -> None:
    from scoring_v4.quality_score import assemble_quality_score
    # (verification 8 + trust 5) / (8+5=13) * 15 == 15
    out = assemble_quality_score(_shadow(bd=_module_bd(verification=8, manuf_trust=5)))
    assert out["quality_pillars_v4"]["verification"]["score"] == 15.0


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
