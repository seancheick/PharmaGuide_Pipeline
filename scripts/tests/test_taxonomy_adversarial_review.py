"""Adversarial review regressions for the supplement taxonomy consolidation.

These cases were found by reviewing the full 14,193-product branch delta, not
by extending the implementation's happy-path fixtures.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from supplement_taxonomy import classify_supplement  # noqa: E402


def _row(name: str, canonical_id: str, category: str, quantity: float = 100.0):
    return {
        "name": name,
        "standard_name": name,
        "canonical_id": canonical_id,
        "category": category,
        "quantity": quantity,
        "unit": "mg",
        "mapped": True,
        "role_classification": "active_scorable",
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
        "raw_source_path": f"activeIngredients[{name}]",
    }


def _product(name: str, rows: list[dict]):
    return {
        "dsld_id": 970001,
        "product_name": name,
        "fullName": name,
        "ingredient_quality_data": {"ingredients_scorable": rows},
        "probiotic_data": {"is_probiotic_product": False, "total_cfu": 0},
    }


def test_complete_taxonomy_is_invariant_to_ingredient_row_order():
    """Row order is label presentation, not clinical evidence precedence.

    Before this regression was added, reversing zinc + vitamin C preserved the
    primary type but changed ``secondary_type`` from zinc to vitamin_c and
    reordered the policy-grade row-evidence payload. A full-corpus reversal
    check found 1,442 products with this decision drift.
    """
    rows = [
        _row("Zinc", "zinc", "mineral", 15.0),
        _row("Vitamin C", "vitamin_c", "vitamin", 100.0),
    ]

    forward = classify_supplement(_product("Daily Duo", rows))
    reverse = classify_supplement(_product("Daily Duo", list(reversed(rows))))

    assert forward == reverse


def test_fallback_reason_and_category_maps_are_invariant_to_row_order():
    """Even diagnostic prose is contract output and must be reproducible.

    A corpus-wide reversal found 607 products whose decisions were stable but
    whose fallback reason embedded an insertion-ordered category mapping.
    """
    rows = [
        _row("CoQ10", "coq10", "antioxidant", 100.0),
        _row("PQQ", "pqq", "other", 20.0),
        _row("Inositol", "inositol", "other", 50.0),
    ]

    forward = classify_supplement(_product("Daily Cellular Formula", rows))
    reverse = classify_supplement(
        _product("Daily Cellular Formula", list(reversed(rows)))
    )

    assert forward == reverse


def test_duplicate_forms_do_not_inflate_category_dominance():
    """R1 dedup must apply to category ratios as well as ``active_count``.

    Two ginkgo label rows are one identity. Counting them twice while counting
    the denominator by distinct identity makes a one-of-three botanical look
    like a >60% herbal blend.
    """
    taxonomy = classify_supplement(_product("Balanced Antioxidant Trio", [
        _row("Ginkgo Leaf", "ginkgo", "herb", 120.0),
        _row("Ginkgo Extract", "ginkgo", "herb", 60.0),
        _row("CoQ10", "coq10", "antioxidant", 100.0),
        _row("PQQ", "pqq", "antioxidant", 20.0),
    ]))

    assert taxonomy["distinct_active_identity_count"] == 3
    assert taxonomy["category_breakdown"]["herb"] == 1
    assert taxonomy["primary_type"] != "herbal_botanical"


def test_two_distinct_botanicals_do_not_fall_into_the_two_active_black_hole():
    taxonomy = classify_supplement(_product("Ginseng and Guarana", [
        _row("Ginseng", "ginseng", "herb", 200.0),
        _row("Guarana", "guarana", "herb", 100.0),
    ]))

    assert taxonomy["primary_type"] == "herbal_botanical"


def test_two_distinct_amino_acids_remain_an_amino_formula():
    taxonomy = classify_supplement(_product("Nitric Oxide Booster", [
        _row("L-Arginine", "l_arginine", "amino_acid", 1000.0),
        _row("L-Citrulline", "l_citrulline", "amino_acid", 1000.0),
    ]))

    assert taxonomy["primary_type"] == "amino_acid"


def test_named_probiotic_with_only_fiber_support_remains_probiotic():
    product = _product("Kids Probiotic Gummies", [
        _row("Bacillus coagulans", "bacillus_coagulans", "probiotic", 5.0),
        _row("Dietary Fiber", "fiber", "fiber", 1000.0),
    ])
    product["probiotic_data"] = {
        "is_probiotic_product": True,
        "total_cfu": 1_000_000_000,
        "total_strain_count": 1,
    }

    assert classify_supplement(product)["primary_type"] == "probiotic"


def test_collagen_tie_cannot_override_a_contradictory_product_identity():
    """Real corpus shape: Nature's Way 212953 ``Turmeric Complex``.

    The panel is Theracurmin 100 mg + UC-II collagen 40 mg. A count tie is not
    collagen dominance, and the product title positively identifies turmeric.
    """
    taxonomy = classify_supplement(_product("Turmeric Complex", [
        _row("Theracurmin", "curcumin", "herb", 100.0),
        _row("UC-II standardized Cartilage", "collagen", "protein", 40.0),
    ]))

    assert taxonomy["primary_type"] != "collagen"


def test_gelatin_title_corroborates_a_collagen_identity():
    taxonomy = classify_supplement(_product("Gelatin", [
        _row("Gelatin", "collagen", "protein", 1000.0),
        _row("Calcium", "calcium", "mineral", 20.0),
    ]))

    assert taxonomy["primary_type"] == "collagen"


def test_confident_classification_has_a_decisive_machine_reason_code():
    taxonomy = classify_supplement(_product("Magnesium Glycinate", [
        _row("Magnesium Glycinate", "magnesium", "mineral", 200.0),
    ]))

    assert taxonomy["classification_confidence"] > 0
    assert taxonomy["classification_reason_codes"], (
        "a confident type with no machine reason cannot satisfy the plan's "
        "per-product expected-change ledger"
    )
    assert "single_mineral_identity" in taxonomy["classification_reason_codes"]
