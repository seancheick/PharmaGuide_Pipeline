"""v4 probiotic completeness gate regressions."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scoring_v4.gate_completeness import evaluate_completeness_gate  # noqa: E402


def _scorable_row(
    name: str,
    canonical_id: str,
    quantity: float,
    unit: str,
    index: int,
) -> dict:
    return {
        "name": name,
        "raw_source_text": name,
        "raw_source_path": f"ingredientRows[{index}]",
        "canonical_id": canonical_id,
        "mapped": True,
        "mapped_identity": True,
        "scoreable_identity": True,
        "identity_disposition": "clean",
        "source_section": "active",
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
        "role_classification": "active_scorable",
        "dose_class": "therapeutic_mass",
        "quantity": quantity,
        "unit": unit,
        "has_dose": True,
        "score_exclusion_reason": None,
    }


def test_product_level_named_strains_satisfy_probiotic_active_identity() -> None:
    """Ritual/Seed-style labels disclose strains + aggregate CFU at product
    level while top-level scorable rows can be prebiotic/postbiotic support
    ingredients. That is scoreable with transparency/confidence debt; it must
    not be erased as NOT_SCORED for missing active_identity.
    """
    product = {
        "status": "active",
        "form_factor": "capsule",
        "product_name": "Ritual Synbiotic+",
        "primary_type": "probiotic",
        "supplement_taxonomy": {"primary_type": "probiotic"},
        "probiotic_data": {
            "is_probiotic_product": True,
            "total_strain_count": 2,
            "total_billion_count": 11.0,
            "probiotic_blends": [
                {
                    "name": "Probiotic Blend",
                    "strains": [
                        "Lactobacillus rhamnosus LGG",
                        "Bifidobacterium lactis BB-12",
                    ],
                    "cfu_data": {"billion_count": 11.0},
                }
            ],
        },
        "ingredient_quality_data": {
            "ingredients_scorable": [
                _scorable_row("PreforPro", "bacteriophages", 15, "mg", 0),
                _scorable_row("Tributyrin", "butyric_acid", 300, "mg", 1),
            ],
            "ingredients": [
                _scorable_row("PreforPro", "bacteriophages", 15, "mg", 0),
                _scorable_row("Tributyrin", "butyric_acid", 300, "mg", 1),
            ],
        },
    }

    result = evaluate_completeness_gate(product, "probiotic")

    assert result.is_live_eligible is True
    assert "active_identity" not in result.missing_fields


def test_product_level_cfu_without_named_strain_does_not_satisfy_identity() -> None:
    """Aggregate CFU alone is not enough identity evidence for probiotic
    scoring. The gate may score named-strain aggregate blends, not anonymous
    probiotic totals.
    """
    product = {
        "status": "active",
        "form_factor": "capsule",
        "product_name": "Anonymous Probiotic",
        "primary_type": "probiotic",
        "probiotic_data": {
            "is_probiotic_product": True,
            "total_strain_count": 0,
            "total_billion_count": 10.0,
            "probiotic_blends": [
                {"name": "Probiotic Blend", "strains": [], "cfu_data": {"billion_count": 10.0}}
            ],
        },
        "ingredient_quality_data": {
            "ingredients_scorable": [
                _scorable_row("Glucose", "glucose", 1, "g", 0)
            ],
            "ingredients": [_scorable_row("Glucose", "glucose", 1, "g", 0)],
        },
    }

    result = evaluate_completeness_gate(product, "probiotic")

    assert result.is_live_eligible is False
    assert "active_identity" in result.missing_fields
