"""v4 P3.1 — multi/prenatal Formulation dimension tests.

Formulation for multis/prenatals is intentionally different from generic:
it rewards panel-wide form quality without letting dozens of ingredients
stack unbounded premium credit, and it flags gummy/formulation limitations
before Dose/Prenatal-critical adequacy lands in P3.2.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _ingredient(
    canonical_id: str,
    *,
    name: str | None = None,
    bio_score: float = 12.0,
    quantity: float = 10.0,
    unit: str = "mg",
    matched_form: str | None = None,
    dosage_importance: float | None = None,
) -> dict:
    row = {
        "name": name or canonical_id.replace("_", " ").title(),
        "canonical_id": canonical_id,
        "mapped": True,
        "quantity": quantity,
        "unit": unit,
        "bio_score": bio_score,
    }
    if matched_form is not None:
        row["matched_form"] = matched_form
    if dosage_importance is not None:
        row["dosage_importance"] = dosage_importance
    return row


def _product(*, form_factor: str = "tablet", name: str = "Complete Multivitamin", ingredients=None) -> dict:
    return {
        "status": "active",
        "form_factor": form_factor,
        "product_name": name,
        "supplement_type": {"type": "multivitamin"},
        "primary_category": "multivitamin",
        "ingredient_quality_data": {
            "total_active": len(ingredients or []),
            "ingredients_scorable": list(ingredients or []),
        },
    }


def _premium_prenatal_ingredients() -> list[dict]:
    return [
        _ingredient("vitamin_b9_folate", name="Folate", bio_score=14, quantity=1000, unit="mcg DFE", matched_form="L-5-MTHF methylfolate"),
        _ingredient("vitamin_b12_cobalamin", name="Vitamin B12", bio_score=14, quantity=50, unit="mcg", matched_form="Methylcobalamin"),
        _ingredient("vitamin_d", name="Vitamin D3", bio_score=12, quantity=25, unit="mcg", matched_form="Cholecalciferol D3"),
        _ingredient("vitamin_k", name="Vitamin K2", bio_score=13, quantity=90, unit="mcg", matched_form="MK-7 menaquinone-7"),
        _ingredient("iron", name="Iron", bio_score=13, quantity=27, unit="mg", matched_form="Iron bisglycinate chelate"),
        _ingredient("zinc", name="Zinc", bio_score=13, quantity=11, unit="mg", matched_form="Zinc bisglycinate chelate"),
        _ingredient("iodine", name="Iodine", bio_score=11, quantity=150, unit="mcg", matched_form="Potassium iodide"),
        _ingredient("choline", name="Choline", bio_score=11, quantity=110, unit="mg", matched_form="Choline bitartrate"),
    ]


def test_formulation_payload_shape_and_phase() -> None:
    from scoring_v4.modules.multi_prenatal_formulation import score_formulation

    payload = score_formulation(_product(ingredients=_premium_prenatal_ingredients()))

    assert payload["metadata"]["phase"] == "P3.1_multi_prenatal_formulation"
    assert set(payload.keys()) == {"score", "components", "penalties", "metadata"}
    assert payload["score"] is not None
    assert payload["score"] <= 25.0


def test_panel_form_quality_uses_neutral_value_as_a_true_floor() -> None:
    from scoring_v4.modules.multi_prenatal_formulation import score_formulation

    product = _product(ingredients=[
        _ingredient("vitamin_a", bio_score=15),
        _ingredient("vitamin_c", bio_score=9),
    ])

    payload = score_formulation(product)

    # avg=12 already exceeds the neutral floor, so it must not be reduced.
    assert payload["components"]["panel_form_quality"] == 9.6


def test_panel_form_quality_floor_never_reduces_premium_panel() -> None:
    from scoring_v4.modules.multi_prenatal_formulation import score_formulation

    product = _product(ingredients=[
        _ingredient("vitamin_a", bio_score=15),
        _ingredient("vitamin_c", bio_score=15),
    ])

    payload = score_formulation(product)

    assert payload["components"]["panel_form_quality"] == 12.0


def test_premium_form_diversity_skip_first_and_caps_at_4() -> None:
    from scoring_v4.modules.multi_prenatal_formulation import score_formulation

    ingredients = [
        _ingredient(f"nutrient_{i}", bio_score=13, matched_form=f"premium form {i}")
        for i in range(12)
    ]

    payload = score_formulation(_product(ingredients=ingredients))

    assert payload["components"]["premium_form_diversity"] == 4.0
    assert payload["metadata"]["premium_form_count"] == 12


def test_key_form_support_prefers_methylfolate_over_folic_acid() -> None:
    from scoring_v4.modules.multi_prenatal_formulation import score_formulation

    methyl = score_formulation(_product(ingredients=[
        _ingredient("vitamin_b9_folate", name="Folate", matched_form="L-5-MTHF methylfolate"),
    ]))
    folic = score_formulation(_product(ingredients=[
        _ingredient("vitamin_b9_folate", name="Folate", matched_form="Folic acid"),
    ]))

    assert methyl["components"]["key_form_support"] == 1.25
    assert folic["components"]["key_form_support"] == 0.75


def test_key_form_support_credits_core_multi_forms_without_prenatal_requirement() -> None:
    from scoring_v4.modules.multi_prenatal_formulation import score_formulation

    product = _product(name="Men's Multivitamin", ingredients=[
        _ingredient("vitamin_b12_cobalamin", matched_form="Methylcobalamin"),
        _ingredient("vitamin_d", matched_form="Cholecalciferol D3"),
        _ingredient("vitamin_k", matched_form="MK-7"),
        _ingredient("zinc", matched_form="Zinc bisglycinate"),
    ])

    payload = score_formulation(product)

    assert payload["components"]["key_form_support"] == 4.0
    assert "missing_prenatal_dha" not in payload["penalties"]


def test_presence_floor_preserves_positive_multi_form_signal_after_penalty_clamp(monkeypatch) -> None:
    """If a formulation penalty exceeds positive form signal, keep a small
    presence floor instead of displaying 0 for a mapped active."""
    import scoring_v4.modules.multi_prenatal_formulation as formulation

    monkeypatch.setattr(formulation, "GUMMY_FORMULATION_PENALTY", 10.0)

    product = _product(
        form_factor="gummy",
        ingredients=[
            _ingredient("vitamin_c", bio_score=1, matched_form="ascorbic acid"),
        ],
    )

    payload = formulation.score_formulation(product)

    assert payload["score"] == formulation.FORMULATION_PRESENCE_FLOOR
    assert payload["metadata"]["presence_floor"]["applied"] is True
    assert payload["metadata"]["presence_floor"]["pre_floor_score"] < 0


def test_presence_floor_does_not_apply_to_multi_with_no_positive_form_signal(monkeypatch) -> None:
    import scoring_v4.modules.multi_prenatal_formulation as formulation

    monkeypatch.setattr(formulation, "GUMMY_FORMULATION_PENALTY", 10.0)

    product = _product(form_factor="gummy", ingredients=[])

    payload = formulation.score_formulation(product)

    assert payload["score"] == 0.0
    assert payload["metadata"]["presence_floor"]["applied"] is False


def test_dose_panel_structure_rewards_individual_dose_disclosure() -> None:
    from scoring_v4.modules.multi_prenatal_formulation import score_formulation

    full = score_formulation(_product(ingredients=_premium_prenatal_ingredients()))
    partial_rows = _premium_prenatal_ingredients()
    for row in partial_rows[:3]:
        row.pop("unit", None)
    partial = score_formulation(_product(ingredients=partial_rows))

    assert full["components"]["panel_disclosure_structure"] == 2.0
    assert partial["components"]["panel_disclosure_structure"] == 1.0
    assert partial["metadata"]["dose_coverage"] == 0.625


def test_gummy_formulation_loses_dosage_form_credit_and_gets_modest_penalty() -> None:
    from scoring_v4.modules.multi_prenatal_formulation import score_formulation

    tablet = score_formulation(_product(form_factor="tablet", ingredients=_premium_prenatal_ingredients()))
    gummy = score_formulation(_product(form_factor="gummy", name="Adult Multi Gummies", ingredients=_premium_prenatal_ingredients()))

    assert tablet["components"]["dosage_form_suitability"] == 2.0
    assert gummy["components"]["dosage_form_suitability"] == 0.0
    assert gummy["penalties"]["gummy_formulation_limit"] == -3.0
    assert gummy["score"] == tablet["score"] - 5.0


def test_empty_or_malformed_product_scores_zero_not_none() -> None:
    from scoring_v4.modules.multi_prenatal_formulation import score_formulation

    for bad in (None, {}, {"ingredient_quality_data": None}, "oops", 7):
        payload = score_formulation(bad)  # type: ignore[arg-type]
        assert payload["score"] == 0.0
        assert payload["components"]["panel_form_quality"] == 0.0


def test_score_multi_prenatal_wires_formulation_dimension() -> None:
    from scoring_v4.modules.multi_prenatal import score_multi_prenatal

    breakdown = score_multi_prenatal(_product(ingredients=_premium_prenatal_ingredients())).to_breakdown()
    formulation = breakdown["dimensions"]["formulation"]

    assert formulation["score"] is not None
    assert formulation["metadata"]["phase"] == "P3.1_multi_prenatal_formulation"
    assert breakdown["score_100"] is not None
    assert breakdown["phase"].startswith("P3.")


def test_formulation_dimension_does_not_mutate_input() -> None:
    from scoring_v4.modules.multi_prenatal_formulation import score_formulation

    product = _product(ingredients=_premium_prenatal_ingredients())
    before = json.dumps(product, sort_keys=True)
    score_formulation(product)
    assert json.dumps(product, sort_keys=True) == before


def test_formulation_accepts_final_detail_blob_top_level_ingredients_alias() -> None:
    from scoring_v4.modules.multi_prenatal_formulation import score_formulation

    product = _product(ingredients=_premium_prenatal_ingredients())
    product["ingredients"] = product.pop("ingredient_quality_data")["ingredients_scorable"]

    payload = score_formulation(product)

    assert payload["score"] == 0.0
    assert payload["metadata"]["premium_form_count"] == 0


def test_multi_prenatal_formulation_does_not_import_v3_scorer() -> None:
    source = (SCRIPTS_ROOT / "scoring_v4" / "modules" / "multi_prenatal_formulation.py").read_text()

    assert "import score_supplements" not in source
    assert "from score_supplements" not in source
