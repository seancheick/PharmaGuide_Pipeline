"""v4 Probiotic Formulation — P2.1 tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _product(
    *,
    total_billion: float = 50.0,
    strain_count: int = 8,
    clinical_strain_count: int = 5,
    prebiotic_present: bool = True,
    survivability: bool = True,
    delivery_tier: int | None = None,
    blends: list[dict] | None = None,
) -> dict:
    if blends is None:
        blends = [
            {
                "name": f"Strain {i}",
                "strain_count": 1,
                "strains": [f"Strain {i}"],
                "cfu_data": {"has_cfu": False, "billion_count": 0, "cfu_count": 0},
            }
            for i in range(1, strain_count + 1)
        ]
    return {
        "status": "active",
        "form_factor": "capsule",
        "supplement_type": {"type": "probiotic"},
        "ingredient_quality_data": {
            "total_active": max(1, strain_count),
            "ingredients_scorable": [
                {"name": "Lactobacillus rhamnosus", "canonical_id": "lacto", "mapped": True, "has_dose": True}
            ],
        },
        "delivery_tier": delivery_tier,
        "probiotic_data": {
            "is_probiotic": True,
            "is_probiotic_product": True,
            "probiotic_blends": blends,
            "has_cfu": total_billion > 0,
            "total_cfu": total_billion * 1_000_000_000,
            "total_billion_count": total_billion,
            "total_strain_count": strain_count,
            "clinical_strain_count": clinical_strain_count,
            "clinical_strains": [
                {"strain": f"Clinical {i}", "clinical_id": f"STRAIN_{i}"}
                for i in range(1, clinical_strain_count + 1)
            ],
            "prebiotic_present": prebiotic_present,
            "prebiotic_name": "Inulin" if prebiotic_present else "",
            "has_survivability_coating": survivability,
        },
    }


def test_probiotic_formulation_scores_full_25_point_contract() -> None:
    from scoring_v4.modules.probiotic_formulation import score_formulation

    payload = score_formulation(_product())

    assert payload["score"] == 25.0
    assert payload["max"] == 25.0
    assert payload["components"] == {
        "total_cfu_disclosed": 4.0,
        "cfu_amount": 5.0,
        "named_species_diversity": 4.0,
        "clinical_strain_codes": 8.0,
        "delivery_survivability": 3.0,
        "prebiotic_complement": 1.0,
    }
    assert payload["metadata"]["phase"] == "P2.1_probiotic_formulation"


@pytest.mark.parametrize(
    ("total_billion", "expected"),
    [
        (0.0, 0.0),
        (0.5, 1.5),
        (1.1, 3.0),
        (10.0, 4.0),
        (50.0, 5.0),
    ],
)
def test_cfu_amount_tiers(total_billion: float, expected: float) -> None:
    from scoring_v4.modules.probiotic_formulation import score_formulation

    payload = score_formulation(_product(total_billion=total_billion))

    assert payload["components"]["cfu_amount"] == expected
    assert payload["components"]["total_cfu_disclosed"] == (4.0 if total_billion > 0 else 0.0)


@pytest.mark.parametrize(
    ("strain_count", "expected"),
    [
        (0, 0.0),
        (1, 3.0),
        (2, 3.0),
        (3, 4.0),
        (8, 4.0),
        (9, 3.0),
        (15, 3.0),
        (16, 2.0),
    ],
)
def test_named_species_diversity_tiers(strain_count: int, expected: float) -> None:
    from scoring_v4.modules.probiotic_formulation import score_formulation

    payload = score_formulation(_product(strain_count=strain_count))

    assert payload["components"]["named_species_diversity"] == expected


@pytest.mark.parametrize(
    ("clinical_strain_count", "expected"),
    [
        (0, 0.0),
        (1, 3.0),
        (2, 5.0),
        (3, 7.0),
        (5, 8.0),
    ],
)
def test_clinical_strain_code_tiers_use_v4_eight_point_cap(
    clinical_strain_count: int,
    expected: float,
) -> None:
    from scoring_v4.modules.probiotic_formulation import score_formulation

    payload = score_formulation(_product(clinical_strain_count=clinical_strain_count))

    assert payload["components"]["clinical_strain_codes"] == expected


@pytest.mark.parametrize(
    ("survivability", "delivery_tier", "expected"),
    [
        (True, None, 3.0),
        (False, 1, 3.0),
        (False, 2, 2.5),
        (False, 3, 1.5),
        (False, None, 0.0),
    ],
)
def test_delivery_survivability_uses_enriched_survivability_then_delivery_tier(
    survivability: bool,
    delivery_tier: int | None,
    expected: float,
) -> None:
    from scoring_v4.modules.probiotic_formulation import score_formulation

    payload = score_formulation(_product(survivability=survivability, delivery_tier=delivery_tier))

    assert payload["components"]["delivery_survivability"] == expected


def test_prebiotic_complement_uses_p05_enriched_flag() -> None:
    from scoring_v4.modules.probiotic_formulation import score_formulation

    with_prebiotic = score_formulation(_product(prebiotic_present=True))
    without_prebiotic = score_formulation(_product(prebiotic_present=False))

    assert with_prebiotic["components"]["prebiotic_complement"] == 1.0
    assert without_prebiotic["components"]["prebiotic_complement"] == 0.0


def test_probiotic_formulation_accepts_final_blob_probiotic_detail_alias() -> None:
    from scoring_v4.modules.probiotic_formulation import score_formulation

    product = _product()
    product["probiotic_detail"] = product.pop("probiotic_data")

    payload = score_formulation(product)

    assert payload["score"] == 25.0
    assert payload["metadata"]["total_billion_count"] == 50.0


def test_strain_count_falls_back_to_unique_blend_strains() -> None:
    from scoring_v4.modules.probiotic_formulation import score_formulation

    blends = [
        {"strains": ["Lactobacillus acidophilus", "Bifidobacterium lactis"]},
        {"strains": ["Lactobacillus acidophilus", "Lactobacillus rhamnosus"]},
    ]
    payload = score_formulation(_product(strain_count=0, blends=blends))

    assert payload["metadata"]["total_strain_count"] == 3
    assert payload["components"]["named_species_diversity"] == 4.0


def test_score_probiotic_wires_formulation_and_preserves_p21_payload_at_p23() -> None:
    from scoring_v4.modules.probiotic import score_probiotic

    breakdown = score_probiotic(_product()).to_breakdown()
    formulation = breakdown["dimensions"]["formulation"]

    assert formulation["score"] == 25.0
    assert formulation["max"] == 25.0
    assert formulation["metadata"]["phase"] == "P2.1_probiotic_formulation"
    assert breakdown["dimensions"]["dose"]["score"] is not None
    # Module-level phase rolls forward as each P2.x slice lands.
    assert breakdown["phase"].startswith("P2.")
    # score_100 lands at P2.6 final assembly — the formulation dimension
    # contract is independent of when final assembly runs.


def test_probiotic_formulation_resilient_to_malformed_input() -> None:
    from scoring_v4.modules.probiotic_formulation import score_formulation

    for bad in (None, {}, {"probiotic_data": None}, 42, "oops"):
        payload = score_formulation(bad)  # type: ignore[arg-type]
        assert payload["score"] == 0.0
        assert payload["max"] == 25.0
