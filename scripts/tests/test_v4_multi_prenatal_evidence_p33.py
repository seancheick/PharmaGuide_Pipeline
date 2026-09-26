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
    assert payload["max"] == 20.0
    assert payload["phase"] == "P3.3_multi_prenatal_evidence"
    assert payload["metadata"]["phase"] == "P3.3_multi_prenatal_evidence"


def test_complete_multivitamin_panel_earns_full_authority_evidence() -> None:
    from scoring_v4.modules.multi_prenatal_evidence import score_evidence

    product = _product(
        ingredients=[
            _ingredient("vitamin_a", name="Vitamin A"),
            _ingredient("vitamin_c", name="Vitamin C"),
            _ingredient("vitamin_d", name="Vitamin D"),
            _ingredient("vitamin_b9_folate", name="Folate"),
            _ingredient("vitamin_b12_cobalamin", name="Vitamin B12"),
            _ingredient("zinc", name="Zinc"),
        ],
    )
    multi = score_evidence(product)

    assert multi["score"] == 20.0
    assert multi["components"]["essential_panel_authority"] == 20.0
    assert multi["metadata"]["authority_covered_count"] == 6


def test_incidental_clinical_breadth_cannot_raise_panel_evidence() -> None:
    from scoring_v4.modules.multi_prenatal_evidence import score_evidence

    product = _product(
        ingredients=[_ingredient("vitamin_d", name="Vitamin D")],
        matches=[
            _match("Vitamin D", study_type="systematic_review_meta", evidence_level="product-human", enrollment=1500, study_id="vitd"),
            _match("Folate", study_type="systematic_review_meta", evidence_level="product-human", enrollment=1500, study_id="folate"),
            _match("Iron", study_type="systematic_review_meta", evidence_level="product-human", enrollment=1500, study_id="iron"),
            _match("Vitamin B12", study_type="systematic_review_meta", evidence_level="product-human", enrollment=1500, study_id="b12", published_studies=50),
        ],
    )

    payload = score_evidence(product)

    assert payload["score"] == round(20.0 / 6.0, 4)
    assert payload["metadata"]["authority_covered_count"] == 1
    assert payload["metadata"]["authority_resolution_reasons"]["vitamin_a"] == (
        "essential_panel_nutrient_not_disclosed"
    )


def test_clinical_matches_without_panel_nutrients_do_not_create_evidence() -> None:
    from scoring_v4.modules.multi_prenatal_evidence import score_evidence

    matches = [_match(f"Nutrient {i}", study_id=str(i)) for i in range(6)]
    payload = score_evidence(_product(matches=matches))

    assert payload["score"] == 0.0
    assert payload["metadata"]["authority_covered_count"] == 0


def test_authority_evidence_is_independent_of_unrelated_negative_match() -> None:
    from scoring_v4.modules.multi_prenatal_evidence import score_evidence

    payload = score_evidence(_product(
        ingredients=[_ingredient("vitamin_d", name="Vitamin D")],
        matches=[_match("Unrelated adjunct", effect_direction="negative")],
    ))

    assert payload["score"] == round(20.0 / 6.0, 4)


def test_prenatal_uses_prenatal_authority_panel() -> None:
    from scoring_v4.modules.multi_prenatal_evidence import score_evidence

    product = _product(ingredients=[
        _ingredient("vitamin_b9_folate", name="Folate"),
        _ingredient("iron", name="Iron"),
        _ingredient("iodine", name="Iodine"),
        _ingredient("vitamin_d", name="Vitamin D"),
        _ingredient("vitamin_b12_cobalamin", name="Vitamin B12"),
    ])
    product["product_name"] = "Complete Prenatal"

    payload = score_evidence(product)

    assert payload["score"] == 20.0
    assert payload["metadata"]["panel_mode"] == "prenatal"


def test_empty_or_malformed_product_scores_zero() -> None:
    from scoring_v4.modules.multi_prenatal_evidence import score_evidence

    for bad in (None, {}, {"evidence_data": None}, "oops", 12):
        payload = score_evidence(bad)  # type: ignore[arg-type]
        assert payload["score"] == 0.0
        assert payload["components"]["essential_panel_authority"] == 0.0


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
