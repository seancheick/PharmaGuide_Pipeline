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
