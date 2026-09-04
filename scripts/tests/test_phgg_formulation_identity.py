"""PHGG fiber formulation identity regressions.

Sunfiber / Sunfiber AG are branded partially hydrolyzed guar gum (PHGG)
preparations. The fiber scorer must recognize that material from row-owned
identity signals, not from display-name drift or product-title borrowing.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scoring_v4.modules.fiber_digestive_formulation import score_formulation  # noqa: E402
from scoring_v4.modules.fiber_digestive_helpers import (  # noqa: E402
    is_fiber_row,
    is_hydrolyzed_guar_fiber_row,
)


DATA_ROOT = Path(__file__).resolve().parent.parent / "data"


def _phgg_row(
    *,
    name: str,
    standard_name: str,
    standard_name_camel: str,
    canonical_id: str = "NHA_SUNFIBER_AG",
) -> dict:
    return {
        "name": name,
        "standard_name": standard_name,
        "standardName": standard_name_camel,
        "canonical_id": canonical_id,
        "quantity": 8.0,
        "unit": "Gram(s)",
        "unit_normalized": "gram(s)",
        "category": "complex carbohydrate",
        "matched_form": "",
        "raw_source_text": name,
        "notes": "partially hydrolyzed",
        "forms": [{"name": "Guar Gum, Hydrolyzed"}],
        "raw_taxonomy": {
            "category": "complex carbohydrate",
            "ingredientGroup": "Galactomanan",
            "forms": [{"name": "Guar Gum, Hydrolyzed"}],
        },
    }


def _product(*rows: dict, name: str = "FiberMend Daily Fiber") -> dict:
    return {
        "id": "phgg_test",
        "product_name": name,
        "fullName": name,
        "brandName": "Test Brand",
        "activeIngredients": list(rows),
        "ingredient_quality_data": {
            "ingredients": list(rows),
            "ingredients_scorable": list(rows),
        },
        "dietary_sensitivity_data": {
            "sugar": {
                "amount_g": 0.0,
                "level": "sugar_free",
                "contains_sugar": False,
                "has_added_sugar": False,
                "sugar_sources": [],
            },
            "sweeteners": {
                "artificial": [],
                "high_glycemic": [],
                "sugar_alcohols": [],
                "safer_alternatives": [],
            },
        },
        "nutrition_summary": {"dietary_fiber_g": 8.0},
        "nutrition_detail": {"dietary_fiber_g": 8.0},
        "contaminant_data": {
            "harmful_additives": {"found": False, "additives": []},
            "banned_substances": {"found": False, "substances": []},
        },
    }


@pytest.mark.parametrize(
    ("name", "standard_name", "standard_name_camel"),
    [
        ("Sunfiber AG", "Sunfiber AG", "Sunfiber AG"),
        ("Sunfiber", "Sunfiber", "Sunfiber"),
        ("Digestive Support Fiber", "Guar Gum", "Guar Gum"),
    ],
)
def test_phgg_material_keeps_fiber_identity_and_10_point_source_quality_across_display_names(
    name: str,
    standard_name: str,
    standard_name_camel: str,
) -> None:
    row = _phgg_row(
        name=name,
        standard_name=standard_name,
        standard_name_camel=standard_name_camel,
    )

    assert is_fiber_row(row) is True

    payload = score_formulation(_product(row))

    assert payload["components"]["fiber_source_quality"] == 10.0
    assert payload["metadata"]["fiber_source_class"] == "hydrolyzed_guar_fiber"
    assert payload["metadata"]["fiber_rows_evaluated"] == 1


@pytest.mark.parametrize(
    "canonical_id",
    [
        "NHA_SUNFIBER",
        "NHA_SUNFIBER_AG",
        "partially_hydrolyzed_guar_gum",
    ],
)
def test_phgg_canonical_family_is_recognized_even_when_display_name_is_neutral(
    canonical_id: str,
) -> None:
    row = _phgg_row(
        name="Digestive Support Blend",
        standard_name="Digestive Support Blend",
        standard_name_camel="Digestive Support Blend",
        canonical_id=canonical_id,
    )

    assert is_fiber_row(row) is True

    payload = score_formulation(_product(row, name="Daily Fiber Support"))

    assert payload["components"]["fiber_source_quality"] == 10.0
    assert payload["metadata"]["fiber_source_class"] == "hydrolyzed_guar_fiber"
    assert payload["metadata"]["fiber_rows_evaluated"] == 1


def test_explicit_hydrolyzed_guar_form_signal_recovers_phgg_without_sunfiber_canonical() -> None:
    row = _phgg_row(
        name="Hydrolyzed Guar Fiber",
        standard_name="Digestive Fiber",
        standard_name_camel="Digestive Fiber",
        canonical_id="fiber",
    )

    assert is_fiber_row(row) is True

    payload = score_formulation(_product(row))

    assert payload["components"]["fiber_source_quality"] == 10.0
    assert payload["metadata"]["fiber_source_class"] == "hydrolyzed_guar_fiber"


def test_comma_form_signal_alone_recovers_phgg_without_name_or_note_borrow() -> None:
    row = {
        "name": "Digestive Support Blend",
        "standard_name": "PHGG",
        "standardName": "PHGG",
        "canonical_id": "fiber",
        "quantity": 8.0,
        "unit": "Gram(s)",
        "unit_normalized": "gram(s)",
        "category": "fiber",
        "matched_form": "phgg",
        "raw_source_text": "Digestive Support Blend",
        "notes": "",
        "forms": [{"name": "Guar Gum, Hydrolyzed"}],
        "raw_taxonomy": {
            "category": "fiber",
            "ingredientGroup": "Fiber",
            "forms": [{"name": "Guar Gum, Hydrolyzed"}],
        },
    }

    assert is_fiber_row(row) is True

    payload = score_formulation(_product(row, name="Daily Fiber Support"))

    assert payload["components"]["fiber_source_quality"] == 10.0
    assert payload["metadata"]["fiber_source_class"] == "hydrolyzed_guar_fiber"
    assert is_hydrolyzed_guar_fiber_row(row) is True


def test_native_guar_remains_distinct_from_phgg_metadata() -> None:
    row = {
        "name": "Guar Gum",
        "standard_name": "Guar Gum",
        "standardName": "Guar Gum",
        "canonical_id": "guar_gum",
        "quantity": 8.0,
        "unit": "Gram(s)",
        "unit_normalized": "gram(s)",
        "category": "fiber",
        "matched_form": "",
        "raw_source_text": "Guar Gum",
        "notes": "",
        "forms": [{"name": "Guar Gum"}],
        "raw_taxonomy": {
            "category": "fiber",
            "ingredientGroup": "Guar",
            "forms": [{"name": "Guar Gum"}],
        },
    }

    assert is_fiber_row(row) is True

    payload = score_formulation(_product(row, name="Native Guar Fiber"))

    assert payload["components"]["fiber_source_quality"] == 10.0
    assert payload["metadata"]["fiber_source_class"] == "soluble_fiber"
    assert payload["metadata"]["fiber_source_class"] != "hydrolyzed_guar_fiber"


def test_other_ingredient_guar_canonical_keeps_existing_soluble_fiber_credit() -> None:
    row = {
        "name": "Guar Gum",
        "standard_name": "Guar Gum",
        "standardName": "Guar Gum",
        "canonical_id": "OI_GUAR_GUM",
        "quantity": 1500.0,
        "unit": "mg",
        "unit_normalized": "mg",
        "category": "unknown",
        "matched_form": "",
        "raw_source_text": "Guar Gum",
        "notes": "",
        "forms": [],
        "raw_taxonomy": {
            "category": "fiber",
            "ingredientGroup": "Guar",
            "forms": [],
        },
    }

    assert is_fiber_row(row) is True
    assert is_hydrolyzed_guar_fiber_row(row) is False

    payload = score_formulation(_product(row, name="Guar Gum"))

    assert payload["components"]["fiber_source_quality"] == 10.0
    assert payload["metadata"]["fiber_source_class"] == "soluble_fiber"


def test_other_ingredient_guar_canonical_with_owned_sunfiber_form_keeps_phgg_credit() -> None:
    row = {
        "name": "Guar Fiber",
        "standard_name": "Guar Gum",
        "standardName": "Guar Gum",
        "canonical_id": "OI_GUAR_GUM",
        "quantity": 3.2,
        "unit": "Gram(s)",
        "unit_normalized": "gram(s)",
        "category": "fibers",
        "matched_form": "",
        "raw_source_text": "Guar Fiber",
        "notes": "",
        "forms": [{"name": "Sunfiber"}],
        "raw_taxonomy": {
            "category": "fiber",
            "ingredientGroup": "Guar",
            "forms": [{"name": "Sunfiber"}],
        },
    }

    assert is_fiber_row(row) is True
    assert is_hydrolyzed_guar_fiber_row(row) is True

    payload = score_formulation(_product(row, name="Fortify Daily Prebiotic Fiber"))

    assert payload["components"]["fiber_source_quality"] == 10.0
    assert payload["metadata"]["fiber_source_class"] == "hydrolyzed_guar_fiber"


@pytest.mark.parametrize(
    "canonical_id",
    ["inulin", "iodine"],
)
def test_incompatible_canonical_with_phgg_carrier_form_does_not_become_phgg(
    canonical_id: str,
) -> None:
    row = {
        "name": canonical_id.title(),
        "standard_name": canonical_id.title(),
        "standardName": canonical_id.title(),
        "canonical_id": canonical_id,
        "quantity": 5.0,
        "unit": "Gram(s)",
        "unit_normalized": "gram(s)",
        "category": "fiber" if canonical_id == "inulin" else "mineral",
        "matched_form": "",
        "raw_source_text": canonical_id.title(),
        "notes": "",
        "forms": [{"name": "Guar Gum, Hydrolyzed"}],
        "raw_taxonomy": {
            "category": "fiber" if canonical_id == "inulin" else "mineral",
            "ingredientGroup": canonical_id.title(),
            "forms": [{"name": "Guar Gum, Hydrolyzed"}],
        },
    }

    assert is_hydrolyzed_guar_fiber_row(row) is False

    payload = score_formulation(_product(row, name="Neutral Product"))

    if canonical_id == "inulin":
        assert payload["components"]["fiber_source_quality"] == 9.0
        assert payload["metadata"]["fiber_source_class"] == "prebiotic_fiber"
    else:
        assert is_fiber_row(row) is False
        assert payload["metadata"].get("fiber_profile_applied") is not True


def test_stale_display_standard_name_and_matched_form_do_not_create_phgg_identity() -> None:
    row = {
        "name": "Digestive Support Blend",
        "standard_name": "Digestive Support Blend",
        "standardName": "PHGG",
        "canonical_id": "fiber",
        "quantity": 5.0,
        "unit": "Gram(s)",
        "unit_normalized": "gram(s)",
        "category": "fiber",
        "matched_form": "partially hydrolyzed guar gum",
        "raw_source_text": "Digestive Support Blend",
        "notes": "",
        "forms": [],
        "raw_taxonomy": {"category": "fiber", "ingredientGroup": "Fiber", "forms": []},
    }

    assert is_hydrolyzed_guar_fiber_row(row) is False

    payload = score_formulation(_product(row, name="Neutral Product"))

    assert payload["components"]["fiber_source_quality"] == 7.0
    assert payload["metadata"]["fiber_source_class"] == "generic_fiber"


def test_notphgg_token_does_not_match_phgg_word_boundary() -> None:
    row = {
        "name": "Digestive Support Blend",
        "standard_name": "Digestive Support Blend",
        "standardName": "Digestive Support Blend",
        "canonical_id": "fiber",
        "quantity": 5.0,
        "unit": "Gram(s)",
        "unit_normalized": "gram(s)",
        "category": "fiber",
        "matched_form": "",
        "raw_source_text": "Digestive Support Blend",
        "notes": "notphgg",
        "forms": [],
        "raw_taxonomy": {"category": "fiber", "ingredientGroup": "Fiber", "forms": []},
    }

    assert is_hydrolyzed_guar_fiber_row(row) is False

    payload = score_formulation(_product(row, name="Neutral Product"))

    assert payload["components"]["fiber_source_quality"] == 7.0
    assert payload["metadata"]["fiber_source_class"] == "generic_fiber"


def test_non_phgg_generic_signal_keeps_legacy_row_text_behavior_with_non_string_fields() -> None:
    row = {
        "name": "Digestive Support Blend",
        "standard_name": "Digestive Support Blend",
        "standardName": "Acacia Gum",
        "canonical_id": "fiber",
        "quantity": 5.0,
        "unit": "Gram(s)",
        "unit_normalized": "gram(s)",
        "category": 7,
        "matched_form": "acacia fiber",
        "raw_source_text": {"printed": "Acacia Fiber"},
        "notes": "",
        "forms": [],
        "raw_taxonomy": {"category": 7, "ingredientGroup": "Fiber", "forms": []},
    }

    payload = score_formulation(_product(row, name="Neutral Product"))

    assert payload["components"]["fiber_source_quality"] == 10.0
    assert payload["metadata"]["fiber_source_class"] == "soluble_fiber"


def test_compatible_fiber_row_keeps_acacia_credit_from_standard_name_and_matched_form() -> None:
    row = {
        "name": "Digestive Support Blend",
        "standard_name": "Digestive Support Blend",
        "standardName": "Acacia Fiber",
        "canonical_id": "fiber",
        "quantity": 5.0,
        "unit": "Gram(s)",
        "unit_normalized": "gram(s)",
        "category": "fiber",
        "matched_form": "acacia",
        "raw_source_text": "Digestive Support Blend",
        "notes": "",
        "forms": [],
        "raw_taxonomy": {"category": "fiber", "ingredientGroup": "Fiber", "forms": []},
    }

    payload = score_formulation(_product(row, name="Neutral Product"))

    assert payload["components"]["fiber_source_quality"] == 10.0
    assert payload["metadata"]["fiber_source_class"] == "soluble_fiber"


@pytest.mark.parametrize("signal", ["Guarana", "Guaranteed Fiber"])
def test_compatible_fiber_row_does_not_take_guar_credit_from_partial_word(signal: str) -> None:
    row = {
        "name": signal,
        "standard_name": signal,
        "standardName": signal,
        "canonical_id": "fiber",
        "quantity": 5.0,
        "unit": "Gram(s)",
        "unit_normalized": "gram(s)",
        "category": "fiber",
        "matched_form": "",
        "raw_source_text": signal,
        "notes": "",
        "forms": [],
        "raw_taxonomy": {"category": "fiber", "ingredientGroup": "Fiber", "forms": []},
    }

    payload = score_formulation(_product(row, name="Neutral Product"))

    assert payload["components"]["fiber_source_quality"] == 7.0
    assert payload["metadata"]["fiber_source_class"] == "generic_fiber"


def test_generic_prebiotic_row_does_not_borrow_phgg_identity_from_title_or_display_tokens() -> None:
    row = {
        "name": "Sunfiber Daily Prebiotic",
        "standard_name": "Sunfiber Daily Prebiotic",
        "standardName": "Sunfiber Daily Prebiotic",
        "canonical_id": "inulin",
        "quantity": 5.0,
        "unit": "Gram(s)",
        "unit_normalized": "gram(s)",
        "category": "fiber",
        "matched_form": "",
        "raw_source_text": "Sunfiber Daily Prebiotic",
        "notes": "",
        "forms": [],
        "raw_taxonomy": {
            "category": "fiber",
            "ingredientGroup": "Fiber",
            "forms": [],
        },
    }

    assert is_fiber_row(row) is True

    payload = score_formulation(_product(row, name="Sunfiber Gentle Gut Prebiotic"))

    assert payload["components"]["fiber_source_quality"] == 9.0
    assert payload["metadata"]["fiber_source_class"] == "prebiotic_fiber"
    assert payload["metadata"]["fiber_rows_evaluated"] == 1


def test_incompatible_canonical_with_stale_guar_and_sunfiber_text_does_not_take_guar_credit() -> None:
    row = {
        "name": "Guar Gum",
        "standard_name": "Guar Gum",
        "standardName": "Sunfiber",
        "canonical_id": "iodine",
        "quantity": 5.0,
        "unit": "Gram(s)",
        "unit_normalized": "gram(s)",
        "category": "mineral",
        "matched_form": "",
        "raw_source_text": "Sunfiber",
        "notes": "",
        "forms": [{"name": "Sunfiber"}],
        "raw_taxonomy": {
            "category": "mineral",
            "ingredientGroup": "Iodine",
            "forms": [{"name": "Sunfiber"}],
        },
    }

    assert is_hydrolyzed_guar_fiber_row(row) is False

    payload = score_formulation(_product(row, name="Neutral Product"))

    assert payload["components"]["fiber_source_quality"] != 10.0
    assert payload["metadata"]["fiber_source_class"] != "hydrolyzed_guar_fiber"


def test_sunfiber_ag_note_uses_agglomerated_identity_without_unverified_regulatory_claim() -> None:
    payload = json.loads((DATA_ROOT / "other_ingredients.json").read_text())
    entry = next(row for row in payload["other_ingredients"] if row["id"] == "NHA_SUNFIBER_AG")
    note = entry["notes"]

    assert "agglomerated phgg" in note.lower()
    assert "agricultural/food-grade" not in note.lower()
    assert "fda gras" not in note.lower()
    assert entry["last_updated"] == "2026-09-04"
