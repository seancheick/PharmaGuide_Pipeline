"""Printed values the label states as bounds or approximations keep that meaning.

Sean approved three source-model enhancements on 2026-10-29 after a photo audit
of new submissions: a printed "<1 g" must stay operator "<" + 1 + g (never 0,
0.5 or an exact 1 g), Polyunsaturated Fat is a Nutrition Facts field, and
"about 17" servings per container keeps 17 for arithmetic plus the printed
qualifier for disclosure. DSLD rows already carry the operator; Clean dropped it
(GNC 304446 printed "Protein <1 g" and shipped "1 g").
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parents[1]
sys.path.insert(0, str(SCRIPTS))

from enhanced_normalizer import EnhancedDSLDNormalizer, parse_servings_per_container  # noqa: E402

_PRODUCT = {
    "id": "fidelity-probe",
    "fullName": "Collagen Peptides",
    "brandName": "Probe",
    "productType": {"langualCodeDescription": "Non-Nutrient/Non-Botanical"},
    "physicalState": {"langualCodeDescription": "Powder"},
    "servingSizes": [{"minQuantity": 1, "maxQuantity": 1, "unit": "Scoop", "order": 1}],
    "servingsPerContainer": "60",
    "statements": [],
    "claims": [],
    "otheringredients": {"ingredients": []},
    "ingredientRows": [{
        "order": 1, "name": "Collagen Peptides", "ingredientGroup": "Collagen",
        "category": "protein", "forms": [], "nestedRows": [],
        "quantity": [{"servingSizeOrder": 1, "servingSizeQuantity": 1, "operator": "=",
                      "quantity": 10, "unit": "Gram(s)", "dailyValueTargetGroup": []}],
    }],
}


def _panel_row(name, amount, unit="Gram(s)", operator="=", order=0):
    return {
        "order": order, "name": name, "ingredientGroup": name, "category": "other",
        "forms": [], "nestedRows": [],
        "quantity": [{"servingSizeOrder": 1, "servingSizeQuantity": 1, "operator": operator,
                      "quantity": amount, "unit": unit, "dailyValueTargetGroup": []}],
    }


def _clean(**overrides):
    product = copy.deepcopy(_PRODUCT)
    product.update(overrides)
    return EnhancedDSLDNormalizer().normalize_product(product)


# ── 1. less-than quantities ─────────────────────────────────────────────────

def test_nutrition_fact_keeps_a_printed_less_than_bound() -> None:
    info = EnhancedDSLDNormalizer()._extract_nutritional_info([
        _panel_row("Protein", 1, operator="<"),
        _panel_row("Total Carbohydrates", 1, operator="<"),
        _panel_row("Total Fat", 1.5),
    ])
    assert info["protein"] == {"amount": 1.0, "unit": "Gram(s)", "operator": "<"}
    assert info["totalCarbohydrates"] == {"amount": 1.0, "unit": "Gram(s)", "operator": "<"}
    # Exact control: no operator key appears on an exact amount.
    assert info["totalFat"] == {"amount": 1.5, "unit": "Gram(s)"}


def test_label_display_text_shows_the_printed_bound() -> None:
    cleaned = _clean(ingredientRows=[
        _panel_row("Protein", 1, operator="<"),
        _panel_row("Total Fat", 1.5, order=1),
        *copy.deepcopy(_PRODUCT["ingredientRows"]),
    ])
    doses = {row["raw_source_text"]: row["exact_dose_text"] for row in cleaned["display_ingredients"]}
    assert doses["Protein"] == "<1 g"
    assert doses["Total Fat"] == "1.5 g"
    assert doses["Collagen Peptides"] == "10 g"


def test_reviewer_typed_bound_survives_clean_and_bad_operators_are_not_invented() -> None:
    cleaned = _clean(nutritionalInfo={
        "totalCarbohydrates": {"amount": 1, "unit": "g", "operator": "<"},
        "protein": {"amount": 1, "unit": "g", "operator": "about"},
        "calories": {"amount": 10, "unit": "kcal", "operator": "="},
    })
    info = cleaned["nutritionalInfo"]
    assert info["totalCarbohydrates"] == {"amount": 1.0, "unit": "g", "operator": "<"}
    assert "protein" not in info
    assert info["calories"] == {"amount": 10.0, "unit": "kcal"}


def test_nutrition_summary_keeps_scoring_numbers_and_discloses_the_bound() -> None:
    from enrich_supplements_v3 import SupplementEnricherV3

    summary = SupplementEnricherV3()._collect_nutrition_summary({"nutritionalInfo": {
        "protein": {"amount": 1.0, "unit": "g", "operator": "<"},
        "totalCarbohydrates": {"amount": 4.0, "unit": "g"},
        "sugars": {"amount": 1.0, "unit": "g", "operator": "<"},
    }})
    # The numeric summary contract is unchanged: scoring/routing read it.
    assert summary["protein_g"] == 1.0
    assert summary["total_carbohydrates_g"] == 4.0
    # A typed sugar bound is not an exact mass, the same as a DSLD one.
    assert summary["total_sugars_g"] is None
    assert summary["quantity_operators"] == {"protein_g": "<", "total_sugars_g": "<"}


def test_export_nutrition_detail_carries_the_operator_and_printed_servings_text() -> None:
    from build_final_db import build_detail_blob
    from test_export_gate import _base_enriched, _base_scored

    blob = build_detail_blob(_base_enriched(
        nutrition_summary={"protein_g": 1.0, "quantity_operators": {"protein_g": "<"}},
        servingsPerContainerText="about 17",
    ), _base_scored())
    assert blob["nutrition_detail"]["protein_g"] == 1.0
    assert blob["nutrition_detail"]["quantity_operators"] == {"protein_g": "<"}
    assert blob["serving_info"]["servings_per_container_text"] == "about 17"

    control = build_detail_blob(_base_enriched(), _base_scored())
    assert control["nutrition_detail"]["quantity_operators"] == {}
    assert control["serving_info"]["servings_per_container_text"] is None


# ── 2. polyunsaturated fat ─────────────────────────────────────────────────

def test_polyunsaturated_fat_is_a_nutrition_fact_not_an_active() -> None:
    cleaned = _clean(ingredientRows=[
        _panel_row("Total Fat", 1),
        _panel_row("Polyunsaturated Fat", 0.5, order=1),
        *copy.deepcopy(_PRODUCT["ingredientRows"]),
    ])
    assert cleaned["nutritionalInfo"]["polyunsaturatedFat"] == {"amount": 0.5, "unit": "Gram(s)"}
    assert "Polyunsaturated Fat" not in [row.get("name") for row in cleaned["activeIngredients"]]


def test_typed_polyunsaturated_fat_survives_clean() -> None:
    cleaned = _clean(nutritionalInfo={"polyunsaturatedFat": {"amount": 0.5, "unit": "g"}})
    assert cleaned["nutritionalInfo"]["polyunsaturatedFat"] == {"amount": 0.5, "unit": "g"}


# ── 3. approximate servings per container ──────────────────────────────────

@pytest.mark.parametrize("printed, number, text", [
    ("about 17", 17, "about 17"),
    ("About 50", 50, "About 50"),
    ("approximately 30", 30, "approximately 30"),
    ("60", 60, None),
    (90, 90, None),
    ("1,000", 1000, None),
])
def test_servings_per_container_parser(printed, number, text) -> None:
    assert parse_servings_per_container(printed) == (number, text)


@pytest.mark.parametrize("printed", ["about", "17ish", "about -3", "about 0", "", True, "nan"])
def test_servings_per_container_parser_rejects_unreadable_values(printed) -> None:
    assert parse_servings_per_container(printed) == (None, None)


def test_clean_keeps_the_number_and_the_printed_qualifier() -> None:
    approximate = _clean(servingsPerContainer="about 17")
    assert approximate["servingsPerContainer"] == 17
    assert approximate["servingsPerContainerText"] == "about 17"
    exact = _clean(servingsPerContainer="60")
    assert exact["servingsPerContainer"] == 60
    assert "servingsPerContainerText" not in exact


# ── import, draft and correction owners ────────────────────────────────────

def _approved_payload(**overrides):
    payload = {
        "brandName": "Probe", "fullName": "Collagen Peptides",
        "ingredientRows": [{"name": "Collagen Peptides", "ingredientGroup": "Collagen", "forms": [], "nestedRows": [],
                            "quantity": [{"quantity": 10, "unit": "g"}]}],
        "servingSizes": [{"minQuantity": 1, "maxQuantity": 1, "unit": "Scoop", "order": 1}],
        "otherIngredientsDisclosure": "declared_none", "otherIngredients": "",
    }
    payload.update(overrides)
    return payload


def test_importer_accepts_approximate_servings_and_typed_bounds() -> None:
    from product_submission_import import _validate_label_payload

    for printed in ("about 17", "About 50", 30, "30"):
        _validate_label_payload(_approved_payload(servingsPerContainer=printed))
    _validate_label_payload(_approved_payload(nutritionalInfo={
        "totalCarbohydrates": {"amount": 1, "unit": "g", "operator": "<"},
        "polyunsaturatedFat": {"amount": 0.5, "unit": "g"},
    }))


@pytest.mark.parametrize("overrides", [
    {"servingsPerContainer": "about"},
    {"servingsPerContainer": "17ish"},
    {"servingsPerContainer": "about 0"},
    {"nutritionalInfo": {"protein": {"amount": 1, "unit": "g", "operator": "roughly"}}},
])
def test_importer_rejects_unreadable_printed_values(overrides) -> None:
    from product_submission_import import SubmissionImportError, _validate_label_payload

    with pytest.raises(SubmissionImportError):
        _validate_label_payload(_approved_payload(**overrides))


def test_draft_amount_carries_a_printed_operator_into_the_approval_skeleton() -> None:
    from submission_review.extraction.to_manual_label import to_manual_label

    def field(value):
        return {"value": value, "status": "read", "confidence": None, "sources": []}

    row = {"display_name": field("Total Carbohydrate"), "percent_dv": None, "form_text": None,
           "parent_index": None, "is_blend_header": False, "status": "read",
           "amount": field({"value": 1, "unit_text": "g", "operator": "<"})}
    skeleton = to_manual_label({
        "identity": {"brand": field("Acme"), "product_name": field("Multi")},
        "serving": {"size": field("1 scoop"), "servings_per_container": field("about 17")},
        "ingredient_rows": [row], "other_ingredients": {"text": None, "disclosure_hint": "declared_none"},
        "statements": [],
    })
    assert skeleton.payload["ingredientRows"][0]["quantity"] == [{"quantity": 1.0, "unit": "g", "operator": "<"}]
    assert skeleton.payload["servingsPerContainer"] == "about 17"


def test_envelope_accepts_known_operators_only() -> None:
    from submission_review.extraction import envelope

    assert set(envelope._SHAPES["amount_value"]["properties"]) == {"value", "unit_text", "operator"}
    assert "operator" not in envelope._SHAPES["amount_value"]["required"]
    assert envelope.QUANTITY_OPERATORS == frozenset({"<", "<=", ">", ">=", "~"})


def test_reviewed_nutrition_repair_binds_the_original_object() -> None:
    normalizer = EnhancedDSLDNormalizer()
    product = copy.deepcopy(_PRODUCT)
    product["id"] = "repair-probe"
    product["nutritionalInfo"] = {"sodium": {"amount": 10, "unit": "mg"}}
    source = {key: product.get(key) for key in ("ingredientRows", "servingSizes", "statements")}
    import hashlib
    digest = hashlib.sha256(json.dumps(source, sort_keys=True, ensure_ascii=False,
                                      separators=(",", ":")).encode()).hexdigest()
    corrected = {"sodium": {"amount": 10, "unit": "mg"},
                 "totalCarbohydrates": {"amount": 1, "unit": "g", "operator": "<"}}
    normalizer._label_corrections_by_dsld_id = {"repair-probe": {
        "provenance_tag": "reviewed_submission_label_correction",
        "serving_basis_correction": {
            "raw_source_sha256": digest,
            "raw_product_fields": {"nutritionalInfo": {"sodium": {"amount": 10, "unit": "mg"}}},
            "corrected_product_fields": {"nutritionalInfo": corrected},
        },
    }}
    repaired = normalizer._apply_reviewed_serving_basis(product)
    assert repaired["nutritionalInfo"] == corrected
    assert repaired["servingSizes"] == product["servingSizes"]
    assert product["nutritionalInfo"] == {"sodium": {"amount": 10, "unit": "mg"}}

    product["nutritionalInfo"] = {"sodium": {"amount": 15, "unit": "mg"}}
    with pytest.raises(ValueError, match="metadata changed"):
        normalizer._apply_reviewed_serving_basis(product)


# The approved TJ Probiotic file (PG_SUB_54970EAA…) is untracked user data, so
# its reviewed carbohydrate row is measured by replay, not here.
@pytest.mark.parametrize("pid, key, expected", [
    ("PG_SUB_F580FBD60E574699B47D0982663F17DD", "polyunsaturatedFat",
     {"amount": 0.5, "unit": "g"}),
])
def test_approved_trader_joes_labels_gain_their_printed_rows(pid, key, expected) -> None:
    path = SCRIPTS.parent / "manual_labels" / "product_submissions" / f"{pid}.json"
    raw = json.loads(path.read_text())
    before = copy.deepcopy(raw)
    cleaned = EnhancedDSLDNormalizer().normalize_product(raw)
    assert cleaned["nutritionalInfo"][key] == expected
    # Approved bytes are immutable; the correction owner repairs a working copy.
    assert raw == before and key not in (raw.get("nutritionalInfo") or {})
