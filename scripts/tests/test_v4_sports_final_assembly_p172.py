"""Wave 6 sports v4 final assembly tests."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from score_supplements_v4_shadow import score_product_v4_shadow
from scoring_v4.modules.sports import score_sports


def _row(canonical_id: str, quantity: float, unit: str, *, name: str | None = None, bio_score: float = 14.0) -> dict:
    return {
        "name": name or canonical_id.replace("_", " ").title(),
        "standard_name": name or canonical_id.replace("_", " ").title(),
        "canonical_id": canonical_id,
        "quantity": quantity,
        "unit": unit,
        "bio_score": bio_score,
        "mapped": True,
        "mapped_identity": True,
        "scoreable_identity": True,
        "score_eligible_by_cleaner": True,
        "role_classification": "active_scorable",
        "cleaner_row_role": "active_scorable",
        "dose_class": "therapeutic_mass",
        "source_section": "activeIngredients",
        "raw_source_path": f"activeIngredients[{canonical_id}]",
    }


def _sports_product() -> dict:
    return {
        "id": 269425,
        "fullName": "Creatine Monohydrate 3 g",
        "product_name": "Creatine Monohydrate 3 g",
        "brandName": "Nutricost",
        "primary_type": "amino_acid",
        "supplement_taxonomy": {"primary_type": "amino_acid"},
        "form_factor_canonical": "powder",
        "ingredient_quality_data": {
            "ingredients_scorable": [
                _row("creatine_monohydrate", 3, "Gram(s)", name="Creatine Monohydrate"),
            ]
        },
    }


def test_score_sports_returns_shared_breakdown_shape_with_sports_dose() -> None:
    result = score_sports(_sports_product())
    breakdown = result.to_breakdown()

    assert breakdown["module"] == "sports"
    # Phase 4: trust is no longer a core dimension; it became verification_bonus.
    assert set(breakdown["dimensions"]) == {"formulation", "dose", "evidence", "transparency"}
    assert breakdown["verification_bonus"]["max"] == 8.0
    assert breakdown["dimensions"]["dose"]["metadata"]["phase"] == "P1.7_sports_dose_v1"
    assert breakdown["dimensions"]["dose"]["score"] == 16.0
    assert breakdown["raw_score_100"] is not None
    assert breakdown["score_100"] is not None


def test_shadow_dispatch_scores_sports_module() -> None:
    shadow = score_product_v4_shadow(_sports_product())

    assert shadow["shadow_score_v4_module"] == "sports"
    assert shadow["shadow_score_v4_100"] is not None
    assert shadow["shadow_score_v4_verdict"] in {"SAFE", "POOR", "CAUTION"}
    assert shadow["shadow_score_v4_breakdown"]["module"]["module"] == "sports"
    assert shadow["shadow_score_v4_breakdown"]["module"]["dimensions"]["dose"]["metadata"]["method"] == "sports_active_dose_bands_v1"


def test_shadow_completeness_gate_preserves_sports_module_name() -> None:
    shadow = score_product_v4_shadow(_sports_product())

    assert shadow["shadow_score_v4_breakdown"]["completeness_gate"]["module"] == "sports"
    assert shadow["shadow_score_v4_breakdown"]["completeness_gate"]["is_live_eligible"] is True
