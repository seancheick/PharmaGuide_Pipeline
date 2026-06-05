"""v4 Probiotic Dose — P2.2 tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _strain(
    name: str,
    *,
    cfu_per_day: int | None = 10_000_000_000,
    adequacy_tier: str | None = "good",
    support: str | None = "high",
    is_inactivated: bool = False,
    is_postbiotic: bool = False,
) -> dict:
    return {
        "strain": name,
        "name": name,
        "clinical_id": name.upper().replace(" ", "_"),
        "cfu_per_day": cfu_per_day,
        "adequacy_tier": adequacy_tier,
        "clinical_support_level": support,
        "is_inactivated": is_inactivated,
        "is_postbiotic": is_postbiotic,
    }


def _product(
    *,
    total_strain_count: int = 3,
    blends: list[dict] | None = None,
    clinical_strains: list[dict] | None = None,
) -> dict:
    if clinical_strains is None:
        clinical_strains = [
            _strain("Lactobacillus rhamnosus GG", adequacy_tier="excellent", support="high"),
            _strain("Bifidobacterium lactis BB-12", adequacy_tier="good", support="moderate"),
            _strain("Lactobacillus reuteri DSM 17938", adequacy_tier="adequate", support="weak"),
        ]
    if blends is None:
        blends = [
            {
                "name": strain["name"],
                "strains": [strain["name"]],
                "cfu_data": {"has_cfu": strain.get("cfu_per_day") is not None, "cfu_count": strain.get("cfu_per_day")},
            }
            for strain in clinical_strains
        ]
    return {
        "status": "active",
        "form_factor": "capsule",
        "supplement_type": {"type": "probiotic"},
        "ingredient_quality_data": {
            "total_active": max(1, total_strain_count),
            "ingredients_scorable": [
                {"name": "Probiotic Blend", "canonical_id": "probiotic_blend", "mapped": True, "has_dose": True}
            ],
        },
        "probiotic_data": {
            "is_probiotic": True,
            "is_probiotic_product": True,
            "total_strain_count": total_strain_count,
            "total_billion_count": 50.0,
            "has_cfu": True,
            "probiotic_blends": blends,
            "clinical_strains": clinical_strains,
        },
    }


def test_probiotic_dose_scores_full_25_when_all_strains_have_cfu_and_adequacy_caps() -> None:
    from scoring_v4.modules.probiotic_dose import score_dose

    payload = score_dose(_product())

    assert payload["score"] == 25.0
    assert payload["max"] == 25.0
    assert payload["components"] == {
        "per_strain_cfu_disclosure": 10.0,
        "cfu_adequacy": 15.0,
    }
    assert payload["metadata"]["phase"] == "P2.2_probiotic_dose"
    assert payload["metadata"]["cfu_adequacy_v3_points"] == 5.0
    assert payload["metadata"]["cfu_adequacy_scaled_points"] == 15.0
    assert payload["metadata"]["cfu_adequacy_basis"] == "per_strain_cfu_disclosed"


def test_aggregate_blend_cfu_gets_capped_adequacy_proxy_not_disclosure_credit() -> None:
    from scoring_v4.modules.probiotic_dose import score_dose

    aggregate_blend = {
        "name": "Probiotic Blend",
        "strains": ["Lactobacillus acidophilus", "Bifidobacterium lactis", "Lactobacillus rhamnosus"],
        "cfu_data": {"has_cfu": True, "billion_count": 50.0, "cfu_count": 50_000_000_000},
    }
    clinical_strains = [
        _strain("Lactobacillus acidophilus", cfu_per_day=None, adequacy_tier=None, support="high"),
        _strain("Bifidobacterium lactis", cfu_per_day=None, adequacy_tier=None, support="high"),
        _strain("Lactobacillus rhamnosus", cfu_per_day=None, adequacy_tier=None, support="high"),
    ]

    payload = score_dose(
        _product(total_strain_count=3, blends=[aggregate_blend], clinical_strains=clinical_strains)
    )

    assert payload["score"] == 8.0
    assert payload["components"]["per_strain_cfu_disclosure"] == 0.0
    assert payload["components"]["cfu_adequacy"] == 8.0
    assert payload["metadata"]["per_strain_cfu_disclosed_count"] == 0
    assert payload["metadata"]["window_proxy_reason"] == "aggregate_cfu_not_per_strain"
    assert payload["metadata"]["cfu_adequacy_basis"] == "aggregate_cfu_modeled_proxy"
    assert payload["metadata"]["aggregate_cfu_proxy"]["applied"] is True
    assert payload["metadata"]["aggregate_cfu_proxy"]["proxy_tier"] == "excellent"


def test_low_aggregate_cfu_still_gets_no_proxy_dose_credit() -> None:
    from scoring_v4.modules.probiotic_dose import score_dose

    aggregate_blend = {
        "name": "Probiotic Blend",
        "strains": ["Lactobacillus acidophilus", "Bifidobacterium lactis", "Lactobacillus rhamnosus"],
        "cfu_data": {"has_cfu": True, "billion_count": 0.9, "cfu_count": 900_000_000},
    }
    clinical_strains = [
        _strain("Lactobacillus acidophilus", cfu_per_day=None, adequacy_tier=None, support="high"),
        _strain("Bifidobacterium lactis", cfu_per_day=None, adequacy_tier=None, support="high"),
        _strain("Lactobacillus rhamnosus", cfu_per_day=None, adequacy_tier=None, support="high"),
    ]

    product = _product(total_strain_count=3, blends=[aggregate_blend], clinical_strains=clinical_strains)
    product["probiotic_data"]["total_billion_count"] = 0.9

    payload = score_dose(product)

    assert payload["score"] == 0.0
    assert payload["components"]["cfu_adequacy"] == 0.0
    assert payload["metadata"]["cfu_adequacy_basis"] == "no_cfu_adequacy_credit"
    assert payload["metadata"]["aggregate_cfu_proxy"]["applied"] is False
    assert payload["metadata"]["aggregate_cfu_proxy"]["reason"] == "aggregate_cfu_below_proxy_floor"


def test_probiotic_dose_accepts_final_blob_probiotic_detail_alias() -> None:
    from scoring_v4.modules.probiotic_dose import score_dose

    product = _product()
    product["probiotic_detail"] = product.pop("probiotic_data")

    payload = score_dose(product)

    assert payload["score"] == 25.0
    assert payload["metadata"]["total_strain_count"] == 3


def test_per_strain_cfu_disclosure_is_proportional_to_named_strain_count() -> None:
    from scoring_v4.modules.probiotic_dose import score_dose

    blends = [
        {
            "name": "Lactobacillus rhamnosus GG",
            "strains": ["Lactobacillus rhamnosus GG"],
            "cfu_data": {"has_cfu": True, "cfu_count": 10_000_000_000},
        },
        {
            "name": "Bifidobacterium lactis BB-12",
            "strains": ["Bifidobacterium lactis BB-12"],
            "cfu_data": {"has_cfu": False, "cfu_count": None},
        },
    ]
    clinical_strains = [
        _strain("Lactobacillus rhamnosus GG", cfu_per_day=None, adequacy_tier=None),
        _strain("Bifidobacterium lactis BB-12", cfu_per_day=None, adequacy_tier=None),
    ]

    payload = score_dose(_product(total_strain_count=2, blends=blends, clinical_strains=clinical_strains))

    assert payload["components"]["per_strain_cfu_disclosure"] == 5.0
    assert payload["metadata"]["per_strain_cfu_disclosed_count"] == 1
    assert payload["metadata"]["total_strain_count"] == 2


def test_incomplete_per_strain_cfu_still_uses_aggregate_cfu_adequacy_proxy() -> None:
    """Aggregate CFU is dose evidence even when a label discloses CFU for
    only part of a multi-strain blend.

    Real case: a probiotic with total 10B CFU and 8 named strains disclosed
    one per-strain CFU-like row. The old logic treated "one per-strain CFU
    present" as a reason to discard the aggregate CFU proxy entirely, causing
    Dose to collapse to disclosure-only points.
    """
    from scoring_v4.modules.probiotic_dose import score_dose

    blends = [
        {
            "name": "B. bifidum",
            "strains": ["B. bifidum"],
            "cfu_data": {"has_cfu": True},
        },
        {
            "name": "Probiotic Complex Blend",
            "strains": [
                "B. bifidum",
                "B. lactis",
                "L. rhamnosus",
                "L. plantarum",
                "L. acidophilus",
                "L. salivarius",
                "B. longum",
                "L. reuteri",
            ],
            "cfu_data": {"has_cfu": True, "billion_count": 10.0, "cfu_count": 10_000_000_000},
        },
    ]
    clinical_strains = [
        _strain("B. bifidum", cfu_per_day=None, adequacy_tier=None, support="high"),
        _strain("B. lactis", cfu_per_day=None, adequacy_tier=None, support="high"),
        _strain("L. rhamnosus", cfu_per_day=None, adequacy_tier=None, support="moderate"),
        _strain("L. plantarum", cfu_per_day=None, adequacy_tier=None, support="moderate"),
        _strain("L. acidophilus", cfu_per_day=None, adequacy_tier=None, support="high"),
        _strain("L. salivarius", cfu_per_day=None, adequacy_tier=None, support="weak"),
        _strain("B. longum", cfu_per_day=None, adequacy_tier=None, support="high"),
        _strain("L. reuteri", cfu_per_day=None, adequacy_tier=None, support="weak"),
    ]

    product = _product(total_strain_count=8, blends=blends, clinical_strains=clinical_strains)
    product["probiotic_data"]["total_billion_count"] = 10.0
    product["probiotic_data"]["total_cfu"] = 10_000_000_000

    payload = score_dose(product)

    assert payload["components"]["per_strain_cfu_disclosure"] == 1.25
    assert payload["components"]["cfu_adequacy"] == 8.0
    assert payload["metadata"]["per_strain_cfu_disclosed_count"] == 1
    assert payload["metadata"]["aggregate_cfu_proxy"]["applied"] is True
    assert payload["metadata"]["aggregate_cfu_proxy"]["reason"] == "aggregate_cfu_even_split_proxy"
    assert payload["metadata"]["cfu_adequacy_basis"] == "aggregate_cfu_modeled_proxy"


def test_single_strain_has_cfu_boolean_counts_for_disclosure_without_numeric_adequacy() -> None:
    from scoring_v4.modules.probiotic_dose import score_dose

    blends = [
        {
            "name": "Lactobacillus rhamnosus GG",
            "strains": ["Lactobacillus rhamnosus GG"],
            "cfu_data": {"has_cfu": True},
        }
    ]
    clinical_strains = [_strain("Lactobacillus rhamnosus GG", cfu_per_day=None, adequacy_tier="good")]

    payload = score_dose(_product(total_strain_count=1, blends=blends, clinical_strains=clinical_strains))

    assert payload["components"]["per_strain_cfu_disclosure"] == 10.0
    assert payload["components"]["cfu_adequacy"] == 0.0


@pytest.mark.parametrize(
    ("tier", "support", "expected_v3", "expected_v4"),
    [
        ("low", "high", 0.0, 0.0),
        ("adequate", "high", 1.0, 3.0),
        ("good", "high", 2.0, 6.0),
        ("excellent", "high", 3.0, 9.0),
        ("good", "moderate", 1.5, 4.5),
        ("excellent", "weak", 1.5, 4.5),
        ("good", "unknown", 1.0, 3.0),
    ],
)
def test_cfu_adequacy_preserves_v3_tier_support_math_then_scales_2x(
    tier: str,
    support: str,
    expected_v3: float,
    expected_v4: float,
) -> None:
    from scoring_v4.modules.probiotic_dose import score_dose

    payload = score_dose(
        _product(total_strain_count=1, clinical_strains=[_strain("LGG", adequacy_tier=tier, support=support)])
    )

    assert payload["metadata"]["cfu_adequacy_v3_points"] == pytest.approx(expected_v3)
    assert payload["components"]["cfu_adequacy"] == pytest.approx(expected_v4)


def test_cfu_adequacy_caps_v3_five_points_to_v4_fifteen_points() -> None:
    from scoring_v4.modules.probiotic_dose import score_dose

    strains = [
        _strain(f"Clinical Strain {idx}", adequacy_tier="excellent", support="high")
        for idx in range(1, 5)
    ]

    payload = score_dose(_product(total_strain_count=4, clinical_strains=strains))

    assert payload["metadata"]["cfu_adequacy_v3_points"] == 5.0
    assert payload["components"]["cfu_adequacy"] == 15.0


def test_cfu_adequacy_hard_gates_missing_tier_missing_cfu_and_postbiotic() -> None:
    from scoring_v4.modules.probiotic_dose import score_dose

    strains = [
        _strain("No tier", adequacy_tier=None, support="high"),
        _strain("No cfu", cfu_per_day=None, adequacy_tier="excellent", support="high"),
        _strain("Postbiotic", adequacy_tier="excellent", support="high", is_postbiotic=True),
        _strain("Inactivated", adequacy_tier="excellent", support="high", is_inactivated=True),
    ]

    product = _product(total_strain_count=4, clinical_strains=strains)
    product["probiotic_data"]["has_cfu"] = False
    product["probiotic_data"]["total_billion_count"] = 0.0
    product["probiotic_data"]["total_cfu"] = 0
    product["probiotic_data"]["probiotic_blends"] = []

    payload = score_dose(product)

    assert payload["components"]["cfu_adequacy"] == 0.0
    skipped = [row.get("skipped_reason") for row in payload["metadata"]["cfu_adequacy_contributions"]]
    assert "postbiotic_inactivated_no_cfu_credit" in skipped


def test_score_probiotic_wires_dose_dimension_at_p22() -> None:
    from scoring_v4.modules.probiotic import score_probiotic

    breakdown = score_probiotic(_product()).to_breakdown()
    dose = breakdown["dimensions"]["dose"]

    assert dose["score"] == 25.0
    assert dose["max"] == 25.0
    assert dose["metadata"]["phase"] == "P2.2_probiotic_dose"
    # Module-level phase rolls forward as each P2.x slice lands; per-dimension
    # phase markers stay locked to the slice that owns them.
    assert breakdown["phase"].startswith("P2.")
    assert breakdown["dimensions"]["evidence"]["score"] is not None
    # score_100 lands at P2.6 final assembly — the dose dimension contract
    # is independent of when final assembly runs.


def test_probiotic_dose_resilient_to_malformed_input() -> None:
    from scoring_v4.modules.probiotic_dose import score_dose

    for bad in (None, {}, {"probiotic_data": None}, 42, "oops"):
        payload = score_dose(bad)  # type: ignore[arg-type]
        assert payload["score"] == 0.0
        assert payload["max"] == 25.0
        assert payload["components"]["per_strain_cfu_disclosure"] == 0.0
        assert payload["components"]["cfu_adequacy"] == 0.0
