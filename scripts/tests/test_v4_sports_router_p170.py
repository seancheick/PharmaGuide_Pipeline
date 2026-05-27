"""Wave 6 sports v4 router tests.

The sports module must route explicit sports-nutrition products away from
generic RDA/UL dose math without turning every amino-acid or protein-like
product into a sports product.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scoring_v4.router import class_for_product


def _row(canonical_id: str, quantity: float = 1.0, unit: str = "g") -> dict:
    return {
        "canonical_id": canonical_id,
        "quantity": quantity,
        "unit": unit,
        "score_eligible": True,
        "score_eligible_by_cleaner": True,
        "score_exclusion_reason": None,
        "score_exclusion_reason_code": None,
    }


def _product(
    *,
    primary_type: str,
    name: str,
    rows: list[dict] | None = None,
) -> dict:
    return {
        "primary_type": primary_type,
        "supplement_taxonomy": {"primary_type": primary_type},
        "fullName": name,
        "product_name": name,
        "ingredient_quality_data": {"ingredients_scorable": rows or []},
    }


def test_pre_workout_taxonomy_routes_to_sports() -> None:
    product = _product(
        primary_type="pre_workout",
        name="RapidDrive Pre-Workout Amino Complex",
        rows=[_row("beta-alanine", 3200, "mg")],
    )

    assert class_for_product(product) == "sports"


def test_pre_workout_name_overrides_b_complex_taxonomy() -> None:
    product = _product(
        primary_type="b_complex",
        name="PRE Pre-Workout Complex Blue Raspberry",
        rows=[_row("l_citrulline", 6000, "mg"), _row("beta-alanine", 3000, "mg")],
    )

    assert class_for_product(product) == "sports"


def test_whey_protein_powder_routes_to_sports() -> None:
    product = _product(
        primary_type="protein_powder",
        name="Whey Protein Isolate Dutch Chocolate",
        rows=[_row("whey_protein", 25, "Gram(s)")],
    )

    assert class_for_product(product) == "sports"


def test_keratin_protein_powder_stays_generic() -> None:
    product = _product(
        primary_type="protein_powder",
        name="Keratin 500 mg",
        rows=[_row("keratin", 500, "mg")],
    )

    assert class_for_product(product) == "generic"


def test_creatine_amino_acid_routes_to_sports_by_canonical() -> None:
    product = _product(
        primary_type="amino_acid",
        name="Creatine Monohydrate 3 g",
        rows=[_row("creatine_monohydrate", 3, "Gram(s)")],
    )

    assert class_for_product(product) == "sports"


def test_bcaa_trio_routes_to_sports() -> None:
    product = _product(
        primary_type="amino_acid",
        name="Precision BCAA Gummy Worm",
        rows=[
            _row("l_leucine", 5, "Gram(s)"),
            _row("l_isoleucine", 2.5, "Gram(s)"),
            _row("l_valine", 2.5, "Gram(s)"),
        ],
    )

    assert class_for_product(product) == "sports"


def test_incidental_bcaa_trio_in_mixed_formula_stays_generic() -> None:
    product = _product(
        primary_type="omega_3",
        name="SynaQuell",
        rows=[
            _row("l_leucine", 1250, "mg"),
            _row("l_isoleucine", 625, "mg"),
            _row("l_valine", 625, "mg"),
            _row("dha", 125, "mg"),
            _row("curcumin", 125, "mg"),
        ],
    )

    assert class_for_product(product) == "generic"


def test_standalone_citrulline_routes_to_sports_by_name_and_canonical() -> None:
    product = _product(
        primary_type="amino_acid",
        name="L-Citrulline Powder",
        rows=[_row("l_citrulline", 1200, "mg")],
    )

    assert class_for_product(product) == "sports"


def test_nac_amino_acid_stays_generic() -> None:
    product = _product(
        primary_type="amino_acid",
        name="NAC 600 mg",
        rows=[_row("nac", 600, "mg")],
    )

    assert class_for_product(product) == "generic"


def test_theanine_sleep_support_stays_generic() -> None:
    product = _product(
        primary_type="amino_acid",
        name="Calm Sleep L-Theanine",
        rows=[_row("l_theanine", 200, "mg")],
    )

    assert class_for_product(product) == "generic"


def test_digestive_enzyme_amino_cofactor_stays_generic() -> None:
    product = _product(
        primary_type="amino_acid",
        name="Digestive Enzymes Ultra with Betaine HCl",
        rows=[_row("tmg_betaine", 650, "mg")],
    )

    assert class_for_product(product) == "generic"
