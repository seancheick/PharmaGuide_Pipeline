"""v4 P3.3 — multi/prenatal Evidence dimension tests."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _ingredient(canonical_id: str, *, name: str | None = None, quantity: float = 100.0, unit: str = "mg") -> dict:
    return {
        "name": name or canonical_id.replace("_", " ").title(),
        "standard_name": name or canonical_id.replace("_", " ").title(),
        "canonical_id": canonical_id,
        "mapped": True,
        "quantity": quantity,
        "unit": unit,
    }


def _match(
    ingredient: str,
    *,
    study_type: str = "rct_multiple",
    evidence_level: str = "ingredient-human",
    effect_direction: str = "positive_strong",
    enrollment: float = 250,
    published_studies: int | None = None,
    study_id: str | None = None,
) -> dict:
    row = {
        "ingredient": ingredient,
        "standard_name": ingredient,
        "study_name": ingredient,
        "study_type": study_type,
        "evidence_level": evidence_level,
        "effect_direction": effect_direction,
        "total_enrollment": enrollment,
    }
    if published_studies is not None:
        row["published_studies_count"] = published_studies
    if study_id is not None:
        row["study_id"] = study_id
    return row


def _product(*, matches=None, ingredients=None) -> dict:
    return {
        "status": "active",
        "form_factor": "tablet",
        "product_name": "Complete Multivitamin",
        "supplement_type": {"type": "multivitamin"},
        "primary_category": "multivitamin",
        "ingredient_quality_data": {
            "total_active": len(ingredients or []),
            "ingredients_scorable": list(ingredients or []),
        },
        "evidence_data": {
            "clinical_matches": list(matches or []),
        },
    }


def test_evidence_payload_shape_and_phase() -> None:
    from scoring_v4.modules.multi_prenatal_evidence import score_evidence

    payload = score_evidence(_product(matches=[_match("Vitamin D")]))

    assert set(payload.keys()) == {"score", "max", "components", "penalties", "metadata", "phase"}
    assert payload["max"] == 15.0
    assert payload["phase"] == "P3.3_multi_prenatal_evidence"
    assert payload["metadata"]["phase"] == "P3.3_multi_prenatal_evidence"


def test_multivitamin_evidence_rescales_generic_pipeline_to_15_point_cap() -> None:
    from scoring_v4.modules.generic_evidence import score_evidence as score_generic_evidence
    from scoring_v4.modules.multi_prenatal_evidence import score_evidence

    product = _product(
        ingredients=[_ingredient("vitamin_d", name="Vitamin D")],
        matches=[_match("Vitamin D")],
    )
    generic = score_generic_evidence(product)
    multi = score_evidence(product)

    assert generic["score"] == 4.5
    assert multi["components"]["class_adjusted_clinical_evidence"] == 3.375
    assert multi["score"] == 3.375
    assert multi["metadata"]["generic_evidence_score"] == 4.5


def test_high_evidence_panel_rescales_without_exceeding_15_point_cap() -> None:
    from scoring_v4.modules.multi_prenatal_evidence import score_evidence

    product = _product(
        ingredients=[
            _ingredient("vitamin_d", name="Vitamin D"),
            _ingredient("folate", name="Folate"),
            _ingredient("iron", name="Iron"),
            _ingredient("vitamin_b12", name="Vitamin B12"),
        ],
        matches=[
            _match("Vitamin D", study_type="systematic_review_meta", evidence_level="product-human", enrollment=1500, study_id="vitd"),
            _match("Folate", study_type="systematic_review_meta", evidence_level="product-human", enrollment=1500, study_id="folate"),
            _match("Iron", study_type="systematic_review_meta", evidence_level="product-human", enrollment=1500, study_id="iron"),
            _match("Vitamin B12", study_type="systematic_review_meta", evidence_level="product-human", enrollment=1500, study_id="b12", published_studies=50),
        ],
    )

    payload = score_evidence(product)

    assert payload["metadata"]["generic_evidence_score"] == 18.0
    assert payload["score"] == 13.5
    assert payload["score"] <= 15.0


def test_top_n_dampening_is_preserved_from_generic_pipeline() -> None:
    from scoring_v4.modules.multi_prenatal_evidence import score_evidence

    matches = [_match(f"Nutrient {i}", study_id=str(i)) for i in range(6)]
    payload = score_evidence(_product(matches=matches))

    assert payload["metadata"]["generic_evidence_metadata"]["top_n_applied"] == 4
    assert payload["metadata"]["dampening_policy"] == "generic_top_n_then_0_75_rescale"


def test_negative_effect_direction_contributes_zero() -> None:
    from scoring_v4.modules.multi_prenatal_evidence import score_evidence

    payload = score_evidence(_product(matches=[
        _match("Vitamin D", effect_direction="negative"),
    ]))

    assert payload["score"] == 0.0
    assert payload["components"]["class_adjusted_clinical_evidence"] == 0.0


def test_depth_bonus_is_rescaled_with_pipeline_not_added_separately() -> None:
    from scoring_v4.modules.generic_evidence import score_evidence as score_generic_evidence
    from scoring_v4.modules.multi_prenatal_evidence import score_evidence

    product = _product(matches=[
        _match("Vitamin D", published_studies=50),
    ])

    generic = score_generic_evidence(product)
    multi = score_evidence(product)

    assert generic["components"]["depth_bonus"] == 0.5
    assert multi["metadata"]["generic_evidence_components"]["depth_bonus"] == 0.5
    assert multi["score"] == round(generic["score"] * 0.75, 4)


def test_empty_or_malformed_product_scores_zero() -> None:
    from scoring_v4.modules.multi_prenatal_evidence import score_evidence

    for bad in (None, {}, {"evidence_data": None}, "oops", 12):
        payload = score_evidence(bad)  # type: ignore[arg-type]
        assert payload["score"] == 0.0
        assert payload["components"]["class_adjusted_clinical_evidence"] == 0.0


def test_score_multi_prenatal_wires_evidence_dimension() -> None:
    from scoring_v4.modules.multi_prenatal import score_multi_prenatal

    breakdown = score_multi_prenatal(_product(matches=[_match("Vitamin D")])).to_breakdown()

    evidence = breakdown["dimensions"]["evidence"]
    assert evidence["score"] is not None
    assert evidence["metadata"]["phase"] == "P3.3_multi_prenatal_evidence"
    assert breakdown["score_100"] is not None
    assert breakdown["phase"].startswith("P3.")


def test_multi_prenatal_evidence_does_not_import_v3_scorer() -> None:
    source = (SCRIPTS_ROOT / "scoring_v4" / "modules" / "multi_prenatal_evidence.py").read_text()

    assert "import score_supplements" not in source
    assert "from score_supplements" not in source
