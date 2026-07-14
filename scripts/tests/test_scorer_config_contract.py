"""Live scorer configuration keys have explicit behavioral contracts (H4)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from score_supplements import SupplementScorer


@pytest.fixture(scope="module")
def scorer() -> SupplementScorer:
    return SupplementScorer()


def _product(bio_score: float) -> dict:
    row = {
        "name": "Premium Nutrient",
        "canonical_id": "premium_nutrient",
        "mapped": True,
        "quantity": 10,
        "unit": "mg",
        "bio_score": bio_score,
        "dosage_importance": 1,
        "is_parent_total": False,
    }
    return {"ingredient_quality_data": {"ingredients_scorable": [row]}}


def test_multivitamin_floor_never_reduces_premium_a1(scorer) -> None:
    score = scorer._compute_bioavailability_score(_product(15), "multivitamin")

    assert score == pytest.approx(18)


def test_multivitamin_floor_raises_weak_a1_to_configured_floor(scorer) -> None:
    score = scorer._compute_bioavailability_score(_product(3), "multivitamin")

    assert score == pytest.approx(10.8)


def test_zero_point_configuration_is_not_replaced_by_default(scorer) -> None:
    a3 = scorer.config["section_A_ingredient_quality"]["A3_delivery_system"]
    a4 = scorer.config["section_A_ingredient_quality"]["A4_absorption_enhancer"]
    old_a3_max = a3["max"]
    old_a4_points = a4["points_if_paired"]
    a3["max"] = 0
    a4["points_if_paired"] = 0
    try:
        assert scorer._compute_delivery_score({"delivery_tier": 1}) == 0
        assert scorer._compute_absorption_bonus({"absorption_enhancer_paired": True}) == 0
    finally:
        a3["max"] = old_a3_max
        a4["points_if_paired"] = old_a4_points


def test_verdict_uses_same_rounding_boundary_as_display(scorer) -> None:
    verdict = scorer._derive_verdict(
        b0={"blocked": False, "unsafe": False},
        mapping_gate={"stop": False},
        flags=[],
        quality_score=31.96,
    )

    assert verdict == "SAFE"
