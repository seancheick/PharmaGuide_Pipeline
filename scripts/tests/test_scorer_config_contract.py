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
