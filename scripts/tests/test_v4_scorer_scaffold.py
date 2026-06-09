"""v4 scorer scaffold tests — P1.0.

Locks the contract for the first slice of v4 scoring:

  1. `scoring_v4.router.class_for_product(product) -> str` returns one of
     {"generic", "probiotic", "multi_or_prenatal", "omega"}.  Decides
     which module processes the product. Uses the canonical taxonomy /
     scoring-input contract, with product-name signals limited to guarded
     prenatal context.
  2. `score_supplements_v4.score_product_v4(enriched)` returns
     the v4 result dict with the schema locked in §14 of
     SCORING_V4_PROPOSAL.md:
       - raw_score_v4_100
       - v4_module
       - v4_verdict
       - v4_confidence
       - v4_breakdown
       - v4_anchored

At P1.4, the entry point returns the class via the router, a score for
complete generic rows, and a typed confidence band. Gate failures keep
their blocked_by_* confidence strings.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


# --- Router contract ------------------------------------------------------


def test_router_probiotic_taxonomy_without_content_falls_back_generic() -> None:
    """Taxonomy alone is not enough to enter the probiotic module.

    Stale taxonomy can be polluted by upstream strain extraction, so route
    probiotic only when content evidence validates the class.
    """
    from scoring_v4.router import class_for_product
    product = {"supplement_taxonomy": {"primary_type": "probiotic"}}
    assert class_for_product(product) == "generic"


def _mv_panel_rows(canonicals: list[str]) -> list[dict]:
    """Minimal scorable rows for a multi-nutrient panel (router reads via
    get_scoring_ingredients)."""
    return [
        {
            "canonical_id": cid, "name": cid, "quantity": 100, "unit": "mg",
            "mapped": True, "source_section": "activeIngredients",
            "cleaner_row_role": "active_scorable", "score_eligible_by_cleaner": True,
            "dose_class": "therapeutic_mass", "role_classification": "active_scorable",
            "scoreable_identity": True,
        }
        for cid in canonicals
    ]


def test_router_multivitamin_taxonomy_without_content_falls_back_generic() -> None:
    """Taxonomy alone is not enough to enter the multi/prenatal module — mirrors
    the probiotic content-validation precedent. A `multivitamin` taxonomy tag with
    no disclosed multi-nutrient panel is a mis-tag and must route generic, not be
    crushed by prenatal-panel coverage floors for nutrients it never contained."""
    from scoring_v4.router import class_for_product
    product = {"supplement_taxonomy": {"primary_type": "multivitamin"}}
    assert class_for_product(product) == "generic"


def test_router_multivitamin_taxonomy_with_panel_routes_multi() -> None:
    """A real multivitamin (broad multi-nutrient panel) still routes multi."""
    from scoring_v4.router import class_for_product
    product = {
        "supplement_taxonomy": {"primary_type": "multivitamin"},
        "product_name": "Daily Foundation Formula",
        "ingredient_quality_data": {
            "ingredients_scorable": _mv_panel_rows(
                ["vitamin_a", "vitamin_c", "vitamin_d", "zinc", "iron"]
            )
        },
    }
    assert class_for_product(product) == "multi_or_prenatal"


def test_router_prenatal_dha_label_routes_to_omega_not_multi() -> None:
    """A DHA-only prenatal label should not be crushed by prenatal multi floors."""
    from scoring_v4.router import class_for_product
    product = {
        "supplement_taxonomy": {"primary_type": "general_supplement"},
        "product_name": "Prenatal Care DHA",
    }
    assert class_for_product(product) == "omega"


def test_router_multivitamin_taxonomy_wins_over_legacy_noise() -> None:
    """GoL Men's Multi style: a real multivitamin (broad panel) routes to multi
    even when legacy fields are noisy. Content validation (the panel) is what
    confirms the route — taxonomy + a genuine multi-nutrient panel together."""
    from scoring_v4.router import class_for_product
    product = {
        "supplement_type": {"type": "specialty"},
        "primary_category": "multivitamin",
        "supplement_taxonomy": {"primary_type": "multivitamin"},
        "product_name": "Men's Multi Organic Berry",
        "ingredient_quality_data": {
            "ingredients_scorable": _mv_panel_rows(
                ["vitamin_a", "vitamin_c", "vitamin_d", "vitamin_b12_cobalamin", "zinc", "selenium"]
            )
        },
    }
    assert class_for_product(product) == "multi_or_prenatal"


def test_router_probiotic_supp_type_beats_prenatal_keyword() -> None:
    """Validated probiotic content wins over a 'Prenatal' name keyword."""
    from scoring_v4.router import class_for_product
    product = {
        "supplement_taxonomy": {"primary_type": "probiotic"},
        "product_name": "Prenatal Probiotic",
        "probiotic_data": {
            "is_probiotic_product": True,
            "total_strain_count": 2,
            "has_cfu": True,
            "total_cfu": 1_500_000_000,
        },
    }
    assert class_for_product(product) == "probiotic"


def test_router_generic_default() -> None:
    """Anything else → generic. Single-nutrient, single-ingredient,
    botanical, specialty, etc. all flow through the generic module."""
    from scoring_v4.router import class_for_product
    product = {
        "supplement_taxonomy": {"primary_type": "single_vitamin"},
        "product_name": "Vitamin C 1000mg",
    }
    assert class_for_product(product) == "generic"


def test_router_unknown_supp_type_defaults_to_generic() -> None:
    """Missing or unrecognized supp_type → generic. Conservative default."""
    from scoring_v4.router import class_for_product
    assert class_for_product({}) == "generic"
    assert class_for_product({"supplement_taxonomy": {}}) == "generic"
    assert class_for_product({"supplement_taxonomy": {"primary_type": ""}}) == "generic"
    assert class_for_product({"supplement_taxonomy": {"primary_type": "weird_new_type"}}) == "generic"


def test_router_omega_routes_to_omega_after_p1_6_decision() -> None:
    """P1.6 decision landed: EPA/DHA-bearing omega products route to the
    dedicated omega module instead of generic."""
    from scoring_v4.router import class_for_product
    product = {
        "supplement_taxonomy": {"primary_type": "omega_3"},
        "product_name": "Fish Oil 1000mg",
    }
    assert class_for_product(product) == "omega"


def test_router_valid_classes_only() -> None:
    """Whatever input the router sees, it must return one of the three
    valid module class names. No surprise strings, no None."""
    from scoring_v4.router import class_for_product, VALID_CLASSES
    samples = [
        {},
        {"supplement_taxonomy": {"primary_type": "probiotic"}},
        {"supplement_taxonomy": {"primary_type": "multivitamin"}},
        {"supplement_taxonomy": {"primary_type": "general_supplement"}, "product_name": "Prenatal"},
        {"supplement_taxonomy": None},
        {"primary_type": "single_vitamin"},
    ]
    for s in samples:
        result = class_for_product(s)
        assert result in VALID_CLASSES, f"router returned {result!r} for {s!r}"


# --- V4 entry point contract ------------------------------------------


REQUIRED_V4_SCORER_KEYS = {
    "raw_score_v4_100",
    "v4_module",
    "v4_verdict",
    "v4_confidence",
    "v4_breakdown",
    "v4_anchored",
}


COMPLETE_GENERIC_PRODUCT = {
    "status": "active",
    "form_factor": "capsule",
    "supplement_taxonomy": {"primary_type": "single_mineral"},
    "ingredient_quality_data": {
        "total_active": 1,
        "ingredients_scorable": [
            {
                "name": "Magnesium",
                "canonical_id": "magnesium",
                "mapped": True,
                "dose": 200,
                "unit": "mg",
            }
        ],
    },
}


def test_v4_entry_point_returns_required_keys() -> None:
    """v3 score_supplements.py is untouched. v4 entry point lives in its
    own file and returns a deterministic dict of v4 result fields. Schema
    locked per §14 of SCORING_V4_PROPOSAL.md."""
    from score_supplements_v4 import score_product_v4
    out = score_product_v4({"supplement_type": {"type": "single_nutrient"}})
    missing = REQUIRED_V4_SCORER_KEYS - set(out.keys())
    assert not missing, f"v4 output missing keys: {missing}"


def test_v4_entry_point_module_matches_router() -> None:
    """The v4 output's module field must equal what the router decided.
    Drift between the two would break the rubric-rendering contract in
    Flutter (each module has its own dimension_descriptions)."""
    from score_supplements_v4 import score_product_v4
    from scoring_v4.router import class_for_product
    cases = [
        {"supplement_taxonomy": {"primary_type": "probiotic"}},
        {"supplement_taxonomy": {"primary_type": "multivitamin"}},
        {"supplement_taxonomy": {"primary_type": "single_vitamin"}},
        {"supplement_taxonomy": {"primary_type": "general_supplement"}, "product_name": "Prenatal DHA"},
    ]
    for p in cases:
        expected = class_for_product(p)
        actual = score_product_v4(p)["v4_module"]
        assert actual == expected, f"module drift on {p}: router={expected!r}, v4={actual!r}"


def test_v4_entry_point_p14_typed_confidence_band() -> None:
    """At P1.4, complete generic rows emit a top-level confidence band
    plus a typed confidence block in the breakdown."""
    from score_supplements_v4 import score_product_v4
    out = score_product_v4(COMPLETE_GENERIC_PRODUCT)
    assert out["v4_confidence"] in {"high", "moderate", "low"}
    assert out["v4_breakdown"]["confidence"]["band"] == out["v4_confidence"]


def test_v4_entry_point_p136_score_is_populated() -> None:
    """At P1.3.6, complete generic products emit a real v4 score."""
    from score_supplements_v4 import score_product_v4
    out = score_product_v4(COMPLETE_GENERIC_PRODUCT)
    assert out["raw_score_v4_100"] is not None
    assert out["v4_verdict"] in {"SAFE", "POOR"}
    assert out["v4_anchored"] is False


def test_v4_entry_point_breakdown_shape() -> None:
    """`v4_breakdown` must be a dict (even if empty at P1.0)
    so downstream code can iterate without None checks."""
    from score_supplements_v4 import score_product_v4
    out = score_product_v4({"supplement_type": {"type": "single_nutrient"}})
    assert isinstance(out["v4_breakdown"], dict)


def test_v4_entry_point_handles_minimal_input() -> None:
    """Robustness: the v4 scorer must not crash on empty product.
    At P1.2, empty input is incomplete and therefore NOT_SCORED."""
    from score_supplements_v4 import score_product_v4
    out = score_product_v4({})
    assert out["v4_module"] == "generic"
    assert out["v4_verdict"] == "NOT_SCORED"
    assert out["v4_confidence"] == "blocked_by_completeness_gate"


# --- Architecture lock ----------------------------------------------------


def test_v3_scorer_is_not_imported_by_v4() -> None:
    """Per §13 architecture lock: v3 and v4 share enriched input contract
    + stable helpers (cert_resolver, normalizer lookups) but NOT scoring
    policy. The v4 entry point must NOT import score_supplements
    (the v3 scorer module) — that would couple the two scoring layers
    and reintroduce drift risk."""
    import importlib
    # If the v4 module imports v3 scorer, this fails fast.
    mod = importlib.import_module("score_supplements_v4")
    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "from score_supplements " not in source, (
        "score_supplements_v4.py must not import the v3 scorer; "
        "shared logic should go through scoring_v4/* helpers"
    )
    assert "import score_supplements\n" not in source


def test_scoring_v4_package_importable() -> None:
    """Smoke test: the scoring_v4 package must import cleanly."""
    import scoring_v4
    from scoring_v4 import router  # noqa: F401
