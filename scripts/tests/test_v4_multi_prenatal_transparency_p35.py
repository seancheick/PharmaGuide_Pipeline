"""v4 P3.5 — multi/prenatal Transparency dimension tests.

Multi/prenatal Transparency is panel-aware:

    Positive components:
        panel ingredient identities disclosed   4 pts
        panel individual doses disclosed        7 pts
        B3 claim_compliance bonus               up to +4

    Penalties reused from generic_transparency:
        B2 false allergen-free claim            up to -2
        B5 proprietary blend opacity            class-aware multi/prenatal 1.3x
        B6 marketing / disease claims           -5

Final: clamp(0, 15, positives - penalty magnitudes).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _ingredient(
    canonical_id: str | None,
    *,
    name: str | None = None,
    quantity: float | None = 100.0,
    unit: str | None = "mg",
) -> dict:
    row = {
        "name": name or (canonical_id or "").replace("_", " ").title(),
        "standard_name": name or (canonical_id or "").replace("_", " ").title(),
        "canonical_id": canonical_id,
        "mapped": bool(canonical_id),
    }
    if quantity is not None:
        row["quantity"] = quantity
    if unit is not None:
        row["unit"] = unit
    return row


def _panel_ingredients() -> list[dict]:
    return [
        _ingredient("vitamin_a", name="Vitamin A", quantity=900, unit="mcg RAE"),
        _ingredient("vitamin_c", name="Vitamin C", quantity=90, unit="mg"),
        _ingredient("vitamin_d", name="Vitamin D", quantity=25, unit="mcg"),
        _ingredient("vitamin_e", name="Vitamin E", quantity=15, unit="mg"),
        _ingredient("vitamin_b9_folate", name="Folate", quantity=400, unit="mcg DFE"),
        _ingredient("vitamin_b12_cobalamin", name="Vitamin B12", quantity=50, unit="mcg"),
        _ingredient("zinc", name="Zinc", quantity=11, unit="mg"),
        _ingredient("iodine", name="Iodine", quantity=150, unit="mcg"),
    ]


def _product(
    *,
    ingredients: list[dict] | None = None,
    compliance: dict | None = None,
    allergens: list[dict] | None = None,
    has_disease_claims: bool = False,
    proprietary_blends: list[dict] | None = None,
    top_level_ingredients: bool = False,
    **extra,
) -> dict:
    rows = list(ingredients if ingredients is not None else _panel_ingredients())
    product = {
        "status": "active",
        "form_factor": "tablet",
        "product_name": "Complete Prenatal Multivitamin",
        "supplement_taxonomy": {"primary_type": "multivitamin"},
        "supplement_type": {"type": "multivitamin"},
        "primary_category": "multivitamin",
        "ingredient_quality_data": {
            "total_active": len(rows),
            "ingredients_scorable": rows,
        },
        "compliance_data": compliance or {},
        "contaminant_data": {"allergens": {"allergens": allergens or []}},
        "has_disease_claims": has_disease_claims,
        "proprietary_blends": proprietary_blends or [],
        "proprietary_data": {"total_active_mg": 1000, "total_active_ingredients": len(rows)},
    }
    if top_level_ingredients:
        product["ingredients"] = rows
        product.pop("ingredient_quality_data")
    product.update(extra)
    return product


def test_transparency_full_panel_disclosure_scores_identity_and_dose_components() -> None:
    from scoring_v4.modules.multi_prenatal_transparency import score_transparency

    payload = score_transparency(_product())

    assert payload["score"] == 11.0
    assert payload["max"] == 15.0
    assert payload["components"]["panel_identity_disclosure"] == 4.0
    assert payload["components"]["panel_individual_dose_disclosure"] == 7.0
    assert payload["components"]["B3_claim_compliance"] == 0.0
    assert payload["metadata"]["panel_dose_coverage"] == 1.0


def test_transparency_partial_dose_disclosure_is_proportional() -> None:
    from scoring_v4.modules.multi_prenatal_transparency import score_transparency

    rows = _panel_ingredients()
    for row in rows[:4]:
        row.pop("unit", None)
    payload = score_transparency(_product(ingredients=rows))

    assert payload["components"]["panel_identity_disclosure"] == 4.0
    # No-unit rows stay scoreable identity rows but no longer count as
    # individual dose disclosure.
    assert payload["components"]["panel_individual_dose_disclosure"] == 3.5
    assert payload["metadata"]["panel_dose_count"] == 4
    assert payload["metadata"]["panel_dose_coverage"] == 0.5


def test_transparency_partial_identity_disclosure_is_proportional() -> None:
    from scoring_v4.modules.multi_prenatal_transparency import score_transparency

    rows = _panel_ingredients()
    for row in rows[:2]:
        row["canonical_id"] = ""
        row["standard_name"] = ""
        row["name"] = ""
        row["mapped"] = False
    payload = score_transparency(_product(ingredients=rows))

    # Strict scoring excludes unmapped identity rows upstream; module sees
    # only validated panel rows.
    assert payload["components"]["panel_identity_disclosure"] == 4.0
    assert payload["metadata"]["panel_named_count"] == 6


def test_transparency_b3_claim_compliance_reuses_generic_and_clamps_at_15() -> None:
    from scoring_v4.modules.multi_prenatal_transparency import score_transparency

    product = _product(
        compliance={
            "gluten_free": True,
            "allergen_free_claims": ["dairy-free"],
            "vegan": True,
            "conflicts": [],
            "has_may_contain_warning": False,
        }
    )
    payload = score_transparency(product)

    assert payload["components"]["B3_claim_compliance"] == 4.0
    assert payload["score"] == 15.0
    assert payload["metadata"]["cap_applied"] is False


def test_transparency_b2_allergen_presence_alone_has_no_penalty() -> None:
    from scoring_v4.modules.multi_prenatal_transparency import score_transparency

    payload = score_transparency(_product(
        allergens=[{"allergen_id": "soy", "severity_level": "high"}]
    ))

    assert payload["penalties"]["B2_false_allergen_free_claim"] == 0.0
    assert payload["score"] == 11.0


def test_transparency_b2_false_allergen_claim_reuses_generic() -> None:
    from scoring_v4.modules.multi_prenatal_transparency import score_transparency

    payload = score_transparency(_product(
        allergens=[{"allergen_id": "soy", "severity_level": "high"}],
        compliance={
            "allergen_free_claims": ["soy-free"],
            "gluten_free": False,
            "vegan": False,
            "conflicts": [],
            "has_may_contain_warning": False,
        },
    ))

    assert payload["penalties"]["B2_false_allergen_free_claim"] == -2.0
    assert payload["score"] == 9.0


def test_transparency_b6_disease_claim_penalty_reuses_generic() -> None:
    from scoring_v4.modules.multi_prenatal_transparency import score_transparency

    payload = score_transparency(_product(has_disease_claims=True))

    assert payload["penalties"]["B6_marketing_claims"] == -5.0
    assert payload["metadata"]["flags"] == ["DISEASE_CLAIM_DETECTED"]
    assert payload["score"] == 6.0


def test_transparency_b5_opacity_uses_multi_prenatal_class_multiplier() -> None:
    from scoring_v4.modules.multi_prenatal_transparency import score_transparency

    payload = score_transparency(_product(
        proprietary_blends=[{
            "name": "Prenatal Nutrient Blend",
            "disclosure_level": "partial",
            "blend_total_mg": 500,
            "source_path": "activeIngredients[0]",
            "child_ingredients": [
                {"name": "Vitamin A", "amount": 200, "unit": "mcg"},
                {"name": "Folate"},
                {"name": "Iodine"},
                {"name": "Choline"},
            ],
            "hidden_count": 3,
        }],
    ))

    evidence = payload["metadata"]["B5_blend_evidence"]
    assert payload["penalties"]["B5_proprietary_blend_opacity"] < 0
    assert evidence[0]["blend_class"] == "multi_or_prenatal"
    assert evidence[0]["class_multiplier_applied"] == 1.3


def test_transparency_disclosed_panel_with_opaque_food_matrix_gets_moderate_hit() -> None:
    from scoring_v4.modules.multi_prenatal_transparency import score_transparency

    food_matrix_rows = [
        _ingredient("apple", name="Organic Apple", quantity=None, unit=None),
        _ingredient("beet_root", name="Organic Beet", quantity=None, unit=None),
        _ingredient("broccoli", name="Organic Broccoli", quantity=None, unit=None),
        _ingredient("carrot", name="Organic Carrot", quantity=None, unit=None),
        _ingredient("spinach", name="Organic Spinach", quantity=None, unit=None),
        _ingredient("ginger", name="Organic Ginger", quantity=None, unit=None),
        _ingredient("peppermint", name="Organic Peppermint", quantity=None, unit=None),
        _ingredient("lemon_peel", name="Organic Lemon Peel", quantity=None, unit=None),
        _ingredient("cranberry", name="Organic Cranberry", quantity=None, unit=None),
        _ingredient("raspberry", name="Organic Raspberry", quantity=None, unit=None),
    ]
    for row in food_matrix_rows:
        row["dose_status"] = "not_disclosed_blend"

    payload = score_transparency(_product(
        ingredients=_panel_ingredients() + food_matrix_rows,
        proprietary_blends=[{
            "name": "Organic Food Blend",
            "disclosure_level": "partial",
            "blend_total_mg": 1400,
            "source_path": "activeIngredients[18]",
            "child_ingredients": [{"name": row["name"]} for row in food_matrix_rows],
            "hidden_count": len(food_matrix_rows),
        }],
        proprietary_data={"total_active_mg": 1753, "total_active_ingredients": 18},
    ))

    assert payload["metadata"]["panel_active_count"] == 8
    assert payload["metadata"]["panel_excluded_adjunct_count"] == 10
    assert payload["metadata"]["panel_dose_coverage"] == 1.0
    assert payload["components"]["panel_individual_dose_disclosure"] == 7.0
    assert payload["penalties"]["B5_proprietary_blend_opacity"] == -2.0
    assert payload["metadata"]["B5_adjunct_blend_cap_applied"] is True
    assert payload["score"] == 9.0


def test_transparency_hidden_prenatal_nutrients_still_keeps_full_b5_penalty() -> None:
    from scoring_v4.modules.multi_prenatal_transparency import score_transparency

    payload = score_transparency(_product(
        ingredients=_panel_ingredients(),
        proprietary_blends=[{
            "name": "Prenatal Nutrient Blend",
            "disclosure_level": "partial",
            "blend_total_mg": 500,
            "source_path": "activeIngredients[8]",
            "child_ingredients": [
                {"name": "Folate"},
                {"name": "Iron"},
                {"name": "Iodine"},
                {"name": "Choline"},
            ],
            "hidden_count": 4,
        }],
        proprietary_data={"total_active_mg": 1000, "total_active_ingredients": 12},
    ))

    assert payload["metadata"]["panel_dose_coverage"] == 1.0
    assert payload["metadata"]["B5_adjunct_blend_cap_applied"] is False
    assert payload["penalties"]["B5_proprietary_blend_opacity"] < -3.0
    assert payload["score"] < 8.0


def test_transparency_value_driving_opaque_blends_do_not_use_adjunct_cap() -> None:
    from scoring_v4.modules.multi_prenatal_transparency import score_transparency

    payload = score_transparency(_product(
        ingredients=_panel_ingredients(),
        proprietary_blends=[{
            "name": "Antioxidant, Immune & Metabolism Blend",
            "disclosure_level": "partial",
            "blend_total_mg": 500,
            "source_path": "activeIngredients[8]",
            "child_ingredients": [
                {"name": "Green Tea Extract"},
                {"name": "Alpha Lipoic Acid"},
                {"name": "CoQ10"},
                {"name": "L-Carnitine"},
            ],
            "hidden_count": 4,
        }],
        proprietary_data={"total_active_mg": 1000, "total_active_ingredients": 12},
    ))

    assert payload["metadata"]["panel_dose_coverage"] == 1.0
    assert payload["metadata"]["B5_adjunct_blend_cap_applied"] is False
    assert payload["metadata"]["B5_adjunct_blend_cap_reason"] == "value_relevant_blend_payload"
    assert payload["penalties"]["B5_proprietary_blend_opacity"] < -3.0
    assert payload["score"] < 8.0


def test_transparency_floors_at_zero_under_heavy_penalties() -> None:
    from scoring_v4.modules.multi_prenatal_transparency import score_transparency

    payload = score_transparency(_product(
        ingredients=[],
        has_disease_claims=True,
        allergens=[{"allergen_id": "milk", "severity_level": "high"}],
        proprietary_blends=[{
            "name": "Hidden Prenatal Matrix",
            "disclosure_level": "none",
            "source_path": "activeIngredients[0]",
            "hidden_count": 10,
        }],
        proprietary_data={"total_active_ingredients": 10},
    ))

    assert payload["score"] == 0.0
    assert payload["metadata"]["floor_applied"] is True


def test_transparency_accepts_final_detail_blob_top_level_ingredients_alias() -> None:
    from scoring_v4.modules.multi_prenatal_transparency import score_transparency

    payload = score_transparency(_product(top_level_ingredients=True))

    # Top-level display ingredients are export/rendering data, not scoring
    # input. Strict v4 requires ingredient_quality_data.ingredients_scorable.
    assert payload["score"] == 0.0
    assert payload["metadata"]["panel_active_count"] == 0


def test_transparency_resilient_to_malformed_input() -> None:
    from scoring_v4.modules.multi_prenatal_transparency import score_transparency

    for bad in (None, {}, {"ingredient_quality_data": None}, 42, "oops"):
        payload = score_transparency(bad)  # type: ignore[arg-type]
        assert payload["score"] >= 0.0
        assert payload["max"] == 15.0
        assert "panel_identity_disclosure" in payload["components"]


def test_score_multi_prenatal_wires_transparency_dimension() -> None:
    from scoring_v4.modules.multi_prenatal import score_multi_prenatal

    breakdown = score_multi_prenatal(_product()).to_breakdown()
    trans = breakdown["dimensions"]["transparency"]

    assert trans["score"] == 11.0
    assert trans["metadata"]["phase"] == "P3.5_multi_prenatal_transparency"
    assert breakdown["score_100"] is not None
    assert breakdown["phase"].startswith("P3.")
    assert breakdown["metadata"]["module_state"] in {"dimensions_complete", "complete"}


def test_multi_prenatal_transparency_does_not_import_v3_scorer() -> None:
    source_path = SCRIPTS_ROOT / "scoring_v4" / "modules" / "multi_prenatal_transparency.py"
    tree = ast.parse(source_path.read_text())

    forbidden = {"score_supplements", "score_supplements_v3"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(alias.name in forbidden for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.module not in forbidden
