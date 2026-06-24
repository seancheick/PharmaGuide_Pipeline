"""V3 A6 'single-nutrient premium form' bonus must require EXACTLY one dosed
standalone active — not merely 'at least one'.

Regression for the beta finding on Paradise Earth 'Vitamin D3 + K2' (dsld 336897):
the V3 A6 bonus (which drives the user-facing 'Single-nutrient premium form' pro
in score_bonuses) fired for a 2-active product because the gate was
`if not candidates`. A D3+K2 product (2 dosed actives) is not single-nutrient.
Mirrors the v4 guard in scoring_v4/modules/generic_formulation.py
(test_v4_generic_formulation_p131.py).
"""
import os
import sys
from pathlib import Path

import pytest

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from score_supplements import SupplementScorer


@pytest.fixture(scope="module")
def scorer():
    return SupplementScorer(str(SCRIPTS_ROOT / "config" / "scoring_config.json"))


def _dosed(name, cid):
    return {
        "name": name,
        "standard_name": name,
        "canonical_id": cid,
        "mapped": True,
        "quantity": 125.0,
        "unit": "mcg",
        "has_dose": True,
        "bio_score": 12.0,
        "is_proprietary_blend": False,
        "score_eligible_by_cleaner": True,
        "scoring_input_kind": "active_form",
    }


def test_a6_fires_for_exactly_one_dosed_active(scorer, monkeypatch):
    # Isolate the candidate-count guard: feed the scorable rows directly.
    monkeypatch.setattr(
        scorer, "_get_active_ingredients", lambda p: [_dosed("Vitamin D3", "vitamin_d")]
    )
    bonus = scorer._compute_single_efficiency_bonus({}, "single_vitamin")
    assert bonus > 0, "A6 should award a true single-nutrient product"


def test_a6_blocked_for_two_dosed_actives(scorer, monkeypatch):
    # The D3+K2 case from 336897 — two dosed standalone actives is not single.
    monkeypatch.setattr(
        scorer,
        "_get_active_ingredients",
        lambda p: [_dosed("Vitamin D3", "vitamin_d"), _dosed("Vitamin K2", "vitamin_k")],
    )
    bonus = scorer._compute_single_efficiency_bonus({}, "single_vitamin")
    assert bonus == 0.0, "A6 must NOT fire when >1 dosed active is present"
