#!/usr/bin/env python3
"""S6 additive-penalty calibration + config-hoist guards (2026-07-04).

Locks four things:
  1. the v4 additive points live in scoring_v4/config/quality_score.json at the
     S6 values — LOW held at 0.5 (benign fillers stay quiet), moderate/high/
     critical raised to 2/3/4 for real severity separation;
  2. generic_formulation.py reads those config values at runtime and CANNOT
     silently diverge from the file (the config-hoist parity guard);
  3. the real B1 penalty function yields the new magnitudes;
  4. a moderate additive drops the real safety_hygiene pillar below 10 (the
     "no misleading 10/10 hygiene with a bad additive" invariant).

Hermetic: reads the shipped config + calls the real scoring functions, no network.
"""
import json
import sys
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scoring_v4 import quality_score as qs                       # noqa: E402
from scoring_v4.modules import generic_formulation as gf         # noqa: E402

_CONFIG_PATH = SCRIPTS_ROOT / "scoring_v4" / "config" / "quality_score.json"
CONFIG = json.loads(_CONFIG_PATH.read_text())
S6_POINTS = {"critical": 4.0, "high": 3.0, "moderate": 2.0, "low": 0.5, "none": 0.0}


def test_config_has_s6_additive_points():
    fp = CONFIG["formulation_penalties"]
    assert fp["b1_harmful_additive_points"] == S6_POINTS
    assert fp["b1_harmful_additive_cap"] == 15.0


def test_low_held_moderate_high_critical_raised():
    pts = CONFIG["formulation_penalties"]["b1_harmful_additive_points"]
    assert pts["low"] == 0.5, "low must stay quiet — do not punish benign fillers"
    assert (pts["moderate"], pts["high"], pts["critical"]) == (2.0, 3.0, 4.0)


def test_runtime_matches_config_no_drift():
    """The module must READ the config, not hold a hardcoded copy that can drift."""
    cfg_pts = {k: float(v) for k, v in
               CONFIG["formulation_penalties"]["b1_harmful_additive_points"].items()}
    assert gf.B1_HARMFUL_ADDITIVE_POINTS == cfg_pts
    assert gf.B1_HARMFUL_ADDITIVE_POINTS == S6_POINTS
    assert gf.B1_HARMFUL_ADDITIVE_CAP == CONFIG["formulation_penalties"]["b1_harmful_additive_cap"]


def _prod(sev):
    return {"contaminant_data": {"harmful_additives": {"additives": [
        {"additive_id": f"ADD_TEST_{sev}", "severity_level": sev, "source_section": "inactive"}
    ]}}}


def test_penalty_function_uses_new_magnitudes():
    assert gf._penalty_b1_harmful_additives(_prod("low")) == 0.5
    assert gf._penalty_b1_harmful_additives(_prod("moderate")) == 2.0
    assert gf._penalty_b1_harmful_additives(_prod("high")) == 3.0
    assert gf._penalty_b1_harmful_additives(_prod("critical")) == 4.0


def test_moderate_additive_drops_safety_hygiene_below_10():
    """End-to-end on the real pillar: a lone moderate additive (−2.0 formulation
    penalty) must pull safety_hygiene below a perfect 10/10."""
    cfg = qs._config()
    module_bd = {
        "safety_hygiene_base": {"score": 10.0, "max": 10.0},
        "dimensions": {"formulation": {"penalties": {"B1_harmful_additives": -2.0}}},
    }
    pillar = qs._pillar_safety_hygiene(module_bd, 10.0, cfg)
    assert pillar["score"] < 10.0
    assert pillar["score"] == 8.0  # 10 − min(2.0, cap 4.0)


def test_base_safety_driver_is_not_hidden_by_a_small_additive_deduction():
    """Safety 0 comes from the watchlist match, so the reason must name it even
    when a 0.5 additive deduction is also present."""
    cfg = qs._config()
    module_bd = {
        "safety_hygiene_base": {"score": 0.0, "max": 4.0, "metadata": {
            "drivers": [{"status": "watchlist", "name": "Carob color"}]}},
        "dimensions": {"formulation": {"penalties": {"B1_harmful_additives": -0.5}}},
    }
    pillar = qs._pillar_safety_hygiene(module_bd, 10.0, cfg)
    assert pillar["score"] == 0.0
    assert pillar["reason"] == (
        "Safety concern: it contains a watchlisted ingredient (Carob color) "
        "and it contains additive or sweetener/form-factor concerns."
    )


def test_base_safety_failure_without_driver_detail_keeps_the_generic_cause():
    cfg = qs._config()
    module_bd = {
        "safety_hygiene_base": {"score": 0.0, "max": 4.0},
        "dimensions": {"formulation": {"penalties": {"B1_harmful_additives": -0.5}}},
    }
    pillar = qs._pillar_safety_hygiene(module_bd, 10.0, cfg)
    assert pillar["reason"].startswith(
        "Safety concern: it contains a banned, recalled, or watchlisted ingredient and "
    )


def _bd_with_additives(details, penalty):
    return {
        "safety_hygiene_base": {"score": 10.0, "max": 10.0},
        "dimensions": {"formulation": {
            "penalties": {"B1_harmful_additives": -penalty},
            "metadata": {"inactive_penalty_details": details},
        }},
    }


def test_gras_excipients_do_not_reduce_the_safety_pillar():
    """Silicon dioxide, magnesium stearate and MCC are recorded in PharmaGuide's
    own additive data as GRAS with no safety finding — "quality signal only".
    They stay formulation-quality signals and stop charging clinical Safety."""
    cfg = qs._config()
    details = [
        {"matched_rule_id": "ADD_SILICON_DIOXIDE", "penalty_tier": "low", "penalty_applied": 0.5},
        {"matched_rule_id": "ADD_MAGNESIUM_STEARATE", "penalty_tier": "low", "penalty_applied": 0.5},
    ]
    pillar = qs._pillar_safety_hygiene(_bd_with_additives(details, 1.0), 10.0, cfg)

    assert pillar["score"] == 10.0
    assert "additive_or_sweetener_penalty" not in pillar["components"]
    assert pillar["reason"] == "No banned, recalled, or watchlisted ingredients."


def test_a_moderate_additive_still_reduces_the_safety_pillar():
    cfg = qs._config()
    details = [
        {"matched_rule_id": "ADD_SUCRALOSE", "penalty_tier": "moderate", "penalty_applied": 2.0},
        {"matched_rule_id": "ADD_SILICON_DIOXIDE", "penalty_tier": "low", "penalty_applied": 0.5},
    ]
    pillar = qs._pillar_safety_hygiene(_bd_with_additives(details, 2.5), 10.0, cfg)

    assert pillar["score"] == 8.0  # only the moderate sweetener is charged
    assert "additive" in pillar["reason"]


def _mirror_breakdown(sugar_penalty, additive_penalty, low_tier_points):
    """A formulation breakdown whose additive ledger and applied penalty disagree.

    generic_formulation clamps B1_harmful_additives at b1_harmful_additive_cap
    while inactive_penalty_details keeps every per-item magnitude, so the ledger
    can legitimately sum to more than the penalty that was actually charged.
    """
    return {"dimensions": {"formulation": {
        "penalties": {
            "B1_dietary_sugar": sugar_penalty,
            "B1_harmful_additives": additive_penalty,
        },
        "metadata": {"inactive_penalty_details": [
            {"matched_rule_id": f"ADD_GRAS_{index}", "penalty_tier": "low",
             "penalty_applied": points}
            for index, points in enumerate(low_tier_points)
        ]},
    }}}


def test_capped_additive_ledger_cannot_eat_the_sugar_deduction():
    """Removing GRAS excipients from Safety must never remove a sweetener.

    The low-severity exclusion subtracts the excipient ledger from the mirrored
    penalty total. That total carries the CLAMPED additive penalty, so an
    uncapped ledger must be clamped to what the additive penalty actually
    charged — otherwise the excess is taken out of B1_dietary_sugar, and a
    sugary product silently stops losing Safety points.
    """
    # 10 GRAS fillers (5.0 of ledger) against a 1.0 charged additive penalty.
    breakdown = _mirror_breakdown(-4.0, -1.0, [0.5] * 10)

    assert qs._formulation_additive_safety_penalty(breakdown, qs._config()) == 4.0


def test_low_severity_magnitude_never_exceeds_the_penalty_it_explains():
    breakdown = _mirror_breakdown(-3.0, -2.0, [0.5] * 6)

    assert qs._low_severity_additive_magnitude(breakdown) == 2.0
