"""v4 Probiotic Evidence — P2.3 tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _match(
    *,
    id: str = "STRAIN_LGG_EVIDENCE",
    ingredient: str = "Lactobacillus rhamnosus GG",
    standard_name: str = "Lactobacillus rhamnosus GG",
    study_type: str = "clinical_strain",
    evidence_level: str = "strain-clinical",
    effect_direction: str = "positive_strong",
    total_enrollment: int | None = None,
    published_studies_count: int | None = None,
    **extra,
) -> dict:
    row = {
        "id": id,
        "ingredient": ingredient,
        "standard_name": standard_name,
        "study_name": standard_name,
        "study_type": study_type,
        "evidence_level": evidence_level,
        "effect_direction": effect_direction,
    }
    if total_enrollment is not None:
        row["total_enrollment"] = total_enrollment
    if published_studies_count is not None:
        row["published_studies_count"] = published_studies_count
    row.update(extra)
    return row


def _clinical_strain(
    strain: str = "Lactobacillus rhamnosus GG",
    indication: str = "prevention of antibiotic-associated diarrhea",
) -> dict:
    return {
        "strain": strain,
        "clinical_id": strain.upper().replace(" ", "_"),
        "clinical_support_level": "high",
        "indication_primary": indication,
    }


def _product(
    *,
    product_name: str = "Daily Digestive Probiotic",
    brand_name: str = "Example Probiotics",
    matches: list[dict] | None = None,
    clinical_strains: list[dict] | None = None,
) -> dict:
    return {
        "status": "active",
        "form_factor": "capsule",
        "product_name": product_name,
        "brand_name": brand_name,
        "supplement_type": {"type": "probiotic"},
        "ingredient_quality_data": {
            "total_active": 1,
            "ingredients_scorable": [
                {
                    "name": "Lactobacillus rhamnosus GG",
                    "standard_name": "Lactobacillus rhamnosus GG",
                    "canonical_id": "lactobacillus_rhamnosus_gg",
                    "mapped": True,
                    "has_dose": True,
                }
            ],
        },
        "evidence_data": {
            "clinical_matches": [_match()] if matches is None else matches,
        },
        "probiotic_data": {
            "is_probiotic": True,
            "is_probiotic_product": True,
            "total_strain_count": 1,
            "clinical_strain_count": 1,
            "clinical_strains": [_clinical_strain()] if clinical_strains is None else clinical_strains,
        },
    }


def test_probiotic_evidence_scores_pipeline_plus_exact_indication_relevance() -> None:
    from scoring_v4.modules.probiotic_evidence import score_evidence

    payload = score_evidence(_product())

    assert payload["max"] == 20.0
    assert payload["score"] == 10.6
    assert payload["components"] == {
        "strain_clinical_evidence": 2.6,
        "indication_relevance": 8.0,
    }
    assert payload["metadata"]["phase"] == "P2.3_probiotic_evidence"
    assert payload["metadata"]["indication_relevance_level"] == "direct"


def test_strain_clinical_evidence_caps_at_12_points() -> None:
    from scoring_v4.modules.probiotic_evidence import score_evidence

    matches = [
        _match(
            id=f"STRAIN_{idx}",
            standard_name=f"Clinical Strain {idx}",
            published_studies_count=50,
            base_points=7,
            multiplier=1,
        )
        for idx in range(1, 8)
    ]

    payload = score_evidence(_product(matches=matches))

    assert payload["components"]["strain_clinical_evidence"] == 12.0
    assert payload["metadata"]["generic_evidence_score"] > 12.0


def test_prenatal_positioning_gets_partial_relevance_for_infant_evidence() -> None:
    from scoring_v4.modules.probiotic_evidence import score_evidence

    product = _product(
        product_name="Once Daily Prenatal",
        clinical_strains=[
            _clinical_strain(
                strain="Lactobacillus rhamnosus HN001",
                indication="atopic eczema prevention in infants",
            )
        ],
    )

    payload = score_evidence(product)

    assert payload["components"]["indication_relevance"] == 4.0
    assert payload["metadata"]["indication_relevance_level"] == "partial"


def test_generic_daily_probiotic_gets_broad_relevance_for_gut_or_immune_strains() -> None:
    from scoring_v4.modules.probiotic_evidence import score_evidence

    product = _product(
        product_name="Daily Probiotic 50 Billion",
        clinical_strains=[_clinical_strain(indication="immune support and gut health")],
    )

    payload = score_evidence(product)

    assert payload["components"]["indication_relevance"] == 4.0
    assert payload["metadata"]["indication_relevance_level"] == "broad"


def test_unrelated_positioning_gets_no_indication_relevance() -> None:
    from scoring_v4.modules.probiotic_evidence import score_evidence

    product = _product(
        product_name="Women's Vaginal Probiotic",
        clinical_strains=[_clinical_strain(indication="gingivitis and plaque reduction")],
    )

    payload = score_evidence(product)

    assert payload["components"]["indication_relevance"] == 0.0
    assert payload["metadata"]["indication_relevance_level"] == "none"


def test_effect_direction_negative_zeros_indication_relevance() -> None:
    from scoring_v4.modules.probiotic_evidence import score_evidence

    product = _product(matches=[_match(effect_direction="negative")])

    payload = score_evidence(product)

    assert payload["components"]["strain_clinical_evidence"] == 0.0
    assert payload["components"]["indication_relevance"] == 0.0
    assert payload["metadata"]["indication_effect_multiplier"] == 0.0
    assert payload["score"] == 0.0


def test_effect_direction_mixed_downweights_indication_relevance() -> None:
    from scoring_v4.modules.probiotic_evidence import score_evidence

    product = _product(matches=[_match(effect_direction="mixed")])

    payload = score_evidence(product)

    assert payload["components"]["indication_relevance"] == 4.8
    assert payload["metadata"]["indication_effect_multiplier"] == 0.6


def test_score_probiotic_wires_evidence_dimension_at_p23() -> None:
    from scoring_v4.modules.probiotic import score_probiotic

    breakdown = score_probiotic(_product()).to_breakdown()

    evidence = breakdown["dimensions"]["evidence"]
    assert evidence["score"] == 10.6
    assert evidence["metadata"]["phase"] == "P2.3_probiotic_evidence"
    assert breakdown["phase"] == "P2.3_probiotic_evidence"
    assert breakdown["dimensions"]["trust"]["score"] is None


def test_probiotic_evidence_accepts_final_blob_probiotic_detail_alias() -> None:
    from scoring_v4.modules.probiotic_evidence import score_evidence

    product = _product()
    product["probiotic_detail"] = product.pop("probiotic_data")

    payload = score_evidence(product)

    assert payload["score"] == 10.6
    assert payload["metadata"]["clinical_strain_count"] == 1


def test_probiotic_evidence_resilient_to_malformed_input() -> None:
    from scoring_v4.modules.probiotic_evidence import score_evidence

    for bad in (None, {}, {"evidence_data": None, "probiotic_data": None}, 42, "oops"):
        payload = score_evidence(bad)  # type: ignore[arg-type]
        assert payload["score"] == 0.0
        assert payload["max"] == 20.0
        assert payload["components"]["strain_clinical_evidence"] == 0.0
        assert payload["components"]["indication_relevance"] == 0.0
