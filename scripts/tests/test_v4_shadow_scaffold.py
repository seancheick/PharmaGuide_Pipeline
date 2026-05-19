"""v4 shadow scorer scaffold tests — P1.0.

Locks the contract for the first slice of v4 shadow scoring:

  1. `scoring_v4.router.class_for_product(product) -> str` returns one of
     {"generic", "probiotic", "multi_or_prenatal"}.  Decides which module
     processes the product. Uses supp_type + primary_category +
     product-name signals, in priority order.
  2. `score_supplements_v4_shadow.score_product_v4_shadow(enriched)` returns
     the shadow column dict with the schema locked in §14 of
     SCORING_V4_PROPOSAL.md:
       - shadow_score_v4_100
       - shadow_score_v4_module
       - shadow_score_v4_verdict
       - shadow_score_v4_confidence
       - shadow_score_v4_breakdown
       - shadow_score_v4_anchored

At P1.0, the entry point returns the class via the router and a
"skeleton" confidence; scoring math comes online in P1.1+ as the
gates and generic module land.
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


def test_router_probiotic_supp_type() -> None:
    """supp_type=probiotic — strongest signal, beats everything."""
    from scoring_v4.router import class_for_product
    product = {"supplement_type": {"type": "probiotic"}}
    assert class_for_product(product) == "probiotic"


def test_router_multivitamin_supp_type() -> None:
    from scoring_v4.router import class_for_product
    product = {"supplement_type": {"type": "multivitamin"}}
    assert class_for_product(product) == "multi_or_prenatal"


def test_router_prenatal_keyword_routes_to_multi() -> None:
    """A specialty/targeted product named 'Prenatal …' still routes to
    multi_or_prenatal — the safety/dose-expectation profile matches.

    Mirrors the B5 router's prenatal detection but is a separate decision
    surface (B5 multiplier vs v4 module routing)."""
    from scoring_v4.router import class_for_product
    product = {
        "supplement_type": {"type": "specialty"},
        "product_name": "Prenatal Care DHA",
    }
    assert class_for_product(product) == "multi_or_prenatal"


def test_router_specialty_with_multivit_primary_category_falls_back() -> None:
    """GoL Men's Multi style: supp_type=specialty + primary_category=
    multivitamin → multi_or_prenatal."""
    from scoring_v4.router import class_for_product
    product = {
        "supplement_type": {"type": "specialty"},
        "primary_category": "multivitamin",
        "product_name": "Men's Multi Organic Berry",
    }
    assert class_for_product(product) == "multi_or_prenatal"


def test_router_probiotic_supp_type_beats_prenatal_keyword() -> None:
    """If the enricher already classified a product as probiotic, that
    wins over a 'Prenatal' name keyword (the type classifier already
    inspected the ingredient panel — trust it)."""
    from scoring_v4.router import class_for_product
    product = {
        "supplement_type": {"type": "probiotic"},
        "product_name": "Prenatal Probiotic",
    }
    assert class_for_product(product) == "probiotic"


def test_router_generic_default() -> None:
    """Anything else → generic. Single-nutrient, single-ingredient,
    botanical, specialty, etc. all flow through the generic module."""
    from scoring_v4.router import class_for_product
    product = {
        "supplement_type": {"type": "single_nutrient"},
        "product_name": "Vitamin C 1000mg",
    }
    assert class_for_product(product) == "generic"


def test_router_unknown_supp_type_defaults_to_generic() -> None:
    """Missing or unrecognized supp_type → generic. Conservative default."""
    from scoring_v4.router import class_for_product
    assert class_for_product({}) == "generic"
    assert class_for_product({"supplement_type": {}}) == "generic"
    assert class_for_product({"supplement_type": {"type": ""}}) == "generic"
    assert class_for_product({"supplement_type": {"type": "weird_new_type"}}) == "generic"


def test_router_omega_stays_generic_until_p1_5_decision() -> None:
    """P1.5 decision gate: does generic-module handle omega-3 acceptably,
    or does omega need its own module before P2? Until that decision,
    omega routes to generic and we accept whatever rank-order falls out."""
    from scoring_v4.router import class_for_product
    product = {
        "supplement_type": {"type": "targeted"},
        "primary_category": "omega-3",
        "product_name": "Fish Oil 1000mg",
    }
    assert class_for_product(product) == "generic"


def test_router_valid_classes_only() -> None:
    """Whatever input the router sees, it must return one of the three
    valid module class names. No surprise strings, no None."""
    from scoring_v4.router import class_for_product, VALID_CLASSES
    samples = [
        {},
        {"supplement_type": {"type": "probiotic"}},
        {"supplement_type": {"type": "multivitamin"}},
        {"supplement_type": {"type": "specialty"}, "product_name": "Prenatal"},
        {"supplement_type": None},
        {"supplement_type": "single_nutrient"},  # legacy string form
    ]
    for s in samples:
        result = class_for_product(s)
        assert result in VALID_CLASSES, f"router returned {result!r} for {s!r}"


# --- Shadow entry point contract ------------------------------------------


REQUIRED_SHADOW_KEYS = {
    "shadow_score_v4_100",
    "shadow_score_v4_module",
    "shadow_score_v4_verdict",
    "shadow_score_v4_confidence",
    "shadow_score_v4_breakdown",
    "shadow_score_v4_anchored",
}


COMPLETE_GENERIC_PRODUCT = {
    "status": "active",
    "form_factor": "capsule",
    "supplement_type": {"type": "single_nutrient"},
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


def test_shadow_entry_point_returns_required_keys() -> None:
    """v3 score_supplements.py is untouched. v4 entry point lives in its
    own file and returns a deterministic dict of shadow columns. Schema
    locked per §14 of SCORING_V4_PROPOSAL.md."""
    from score_supplements_v4_shadow import score_product_v4_shadow
    out = score_product_v4_shadow({"supplement_type": {"type": "single_nutrient"}})
    missing = REQUIRED_SHADOW_KEYS - set(out.keys())
    assert not missing, f"shadow output missing keys: {missing}"


def test_shadow_entry_point_module_matches_router() -> None:
    """The shadow output's module field must equal what the router decided.
    Drift between the two would break the rubric-rendering contract in
    Flutter (each module has its own dimension_descriptions)."""
    from score_supplements_v4_shadow import score_product_v4_shadow
    from scoring_v4.router import class_for_product
    cases = [
        {"supplement_type": {"type": "probiotic"}},
        {"supplement_type": {"type": "multivitamin"}},
        {"supplement_type": {"type": "single_nutrient"}},
        {"supplement_type": {"type": "specialty"}, "product_name": "Prenatal DHA"},
    ]
    for p in cases:
        expected = class_for_product(p)
        actual = score_product_v4_shadow(p)["shadow_score_v4_module"]
        assert actual == expected, f"module drift on {p}: router={expected!r}, shadow={actual!r}"


def test_shadow_entry_point_p10_skeleton_confidence() -> None:
    """At P1.2, scoring math still isn't online yet. For a complete,
    scoreable product, the entry point must
    declare its skeleton state in `shadow_score_v4_confidence` so any
    downstream code (audit/report/Flutter) can tell the shadow column
    isn't fully populated yet. Later phases overwrite to typed sub-
    categories: 'high' / 'moderate' / 'low' / 'insufficient_data'."""
    from score_supplements_v4_shadow import score_product_v4_shadow
    out = score_product_v4_shadow(COMPLETE_GENERIC_PRODUCT)
    assert out["shadow_score_v4_confidence"] == "skeleton"


def test_shadow_entry_point_p10_score_is_none() -> None:
    """At P1.2, no scoring math runs for complete products.
    shadow_score_v4_100 must be None (not 0 — that would be confusable
    with a real low score)."""
    from score_supplements_v4_shadow import score_product_v4_shadow
    out = score_product_v4_shadow(COMPLETE_GENERIC_PRODUCT)
    assert out["shadow_score_v4_100"] is None
    assert out["shadow_score_v4_verdict"] is None
    assert out["shadow_score_v4_anchored"] is False


def test_shadow_entry_point_breakdown_shape() -> None:
    """`shadow_score_v4_breakdown` must be a dict (even if empty at P1.0)
    so downstream code can iterate without None checks."""
    from score_supplements_v4_shadow import score_product_v4_shadow
    out = score_product_v4_shadow({"supplement_type": {"type": "single_nutrient"}})
    assert isinstance(out["shadow_score_v4_breakdown"], dict)


def test_shadow_entry_point_handles_minimal_input() -> None:
    """Robustness: the shadow scorer must not crash on empty product.
    At P1.2, empty input is incomplete and therefore NOT_SCORED."""
    from score_supplements_v4_shadow import score_product_v4_shadow
    out = score_product_v4_shadow({})
    assert out["shadow_score_v4_module"] == "generic"
    assert out["shadow_score_v4_verdict"] == "NOT_SCORED"
    assert out["shadow_score_v4_confidence"] == "blocked_by_completeness_gate"


# --- Architecture lock ----------------------------------------------------


def test_v3_scorer_is_not_imported_by_v4_shadow() -> None:
    """Per §13 architecture lock: v3 and v4 share enriched input contract
    + stable helpers (cert_resolver, normalizer lookups) but NOT scoring
    policy. The v4 shadow entry point must NOT import score_supplements
    (the v3 scorer module) — that would couple the two scoring layers
    and reintroduce drift risk."""
    import importlib
    # If the shadow module imports v3 scorer, this fails fast.
    mod = importlib.import_module("score_supplements_v4_shadow")
    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "from score_supplements " not in source, (
        "score_supplements_v4_shadow.py must not import the v3 scorer; "
        "shared logic should go through scoring_v4/* helpers"
    )
    assert "import score_supplements\n" not in source


def test_scoring_v4_package_importable() -> None:
    """Smoke test: the scoring_v4 package must import cleanly."""
    import scoring_v4
    from scoring_v4 import router  # noqa: F401
