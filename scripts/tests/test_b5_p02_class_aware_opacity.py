"""P0.2 regression tests — class-aware B5 proprietary-blend opacity.

Codex's P0.1d work landed the cert-overcredit fix. P0.2 closes the opacity
side: a hidden CFU on a probiotic and a hidden stimulant dose are NOT the
same risk and should NOT earn the same penalty.

Class router (derived from canonical taxonomy, native scoring classification,
and B5-local product-name overlays):

  - probiotic        → multiplier 0.4  (strain-named + aggregate CFU is
                                        industry norm, modest penalty)
  - multi_or_prenatal → multiplier 1.3 (each vitamin has a known RDA;
                                        blends obscure expected dosing)
  - sports_active    → multiplier 1.5  (opaque blends hide stimulant /
                                        amino-acid doses — worst case)
  - generic          → multiplier 1.0  (v3 behavior preserved)

Cap stays at the dimension cap (10). The multiplier scales the ramp,
not the ceiling — heavy opacity in a sports product still capped, but
mild opacity in a probiotic stays well below it.

These tests exercise ``_compute_proprietary_blend_penalty`` directly
with minimal blend dicts. The class-router signal lives on the product, not
the blend. The legacy ``supplement_type`` mirror and ``primary_category``
field are deliberately not decision inputs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from score_supplements import SupplementScorer  # noqa: E402


@pytest.fixture(scope="module")
def scorer() -> SupplementScorer:
    return SupplementScorer()


def _opaque_blend(
    name: str = "Proprietary Blend",
    total_mg: float = 500.0,
    hidden_count: int = 4,
    disclosure_level: str = "none",
) -> Dict[str, Any]:
    """One fully-opaque blend with a declared total but no disclosed children."""
    return {
        "name": name,
        "disclosure_level": disclosure_level,
        "blend_total_mg": total_mg,
        "hidden_count": hidden_count,
        "nested_count": hidden_count,
        "children_with_amount": [],
        "children_without_amount": [],
        "sources": ["detector", "cleaning"],
        "source_field": "activeIngredients",
        "source_path": "activeIngredients[0]",
    }


def _partial_blend(
    name: str = "Energy Blend",
    total_mg: float = 1000.0,
    disclosed_children_mg: float = 200.0,
    hidden_count: int = 3,
) -> Dict[str, Any]:
    """Blend that names children + total but hides per-child amounts.
    Uses the production-side keys: `child_ingredients` and
    `evidence.ingredients_without_amounts` (matches what the enricher emits)."""
    return {
        "name": name,
        "disclosure_level": "partial",
        "blend_total_mg": total_mg,
        "hidden_count": hidden_count,
        "nested_count": hidden_count,
        "child_ingredients": [
            {"name": "Disclosed Child", "amount": disclosed_children_mg, "unit": "mg"}
        ],
        "evidence": {
            "ingredients_without_amounts": [
                {"name": f"Hidden Child {i}"} for i in range(hidden_count)
            ],
        },
        "sources": ["detector", "cleaning"],
        "source_field": "activeIngredients",
        "source_path": "activeIngredients[0]",
    }


def _full_blend(name: str = "Transparent Blend") -> Dict[str, Any]:
    """A blend where every child is disclosed with amounts → no penalty."""
    return {
        "name": name,
        "disclosure_level": "full",
        "blend_total_mg": 500.0,
        "hidden_count": 0,
        "nested_count": 0,
        "children_with_amount": [
            {"name": "C1", "amount": 200, "unit": "mg"},
            {"name": "C2", "amount": 300, "unit": "mg"},
        ],
        "children_without_amount": [],
        "sources": ["cleaning"],
        "source_field": "activeIngredients",
        "source_path": "activeIngredients[0]",
    }


def _product(
    blends: List[Dict[str, Any]],
    primary_type: Optional[str] = None,
    product_name: str = "Example Product",
    brand_name: str = "Example Brand",
    total_active_mg: float = 2000.0,
    total_active_ingredients: int = 5,
    scoring_route: Optional[str] = None,
    legacy_supp_type: Optional[str] = None,
    legacy_primary_category: Optional[str] = None,
) -> Dict[str, Any]:
    """Minimal product using current contracts, plus opt-in legacy decoys."""
    base = {
        "product_name": product_name,
        "fullName": f"{brand_name} {product_name}",
        "brand_name": brand_name,
        "proprietary_blends": blends,
        "proprietary_data": {
            "blends": blends,
            "total_active_mg": total_active_mg,
            "total_active_ingredients": total_active_ingredients,
        },
        "ingredient_quality_data": {
            "total_active": total_active_ingredients,
            "ingredients_scorable": [],
        },
    }
    if primary_type is not None:
        base["primary_type"] = primary_type
        base["supplement_taxonomy"] = {"primary_type": primary_type}
    if scoring_route is not None:
        base["product_scoring_classification"] = {"route_module": scoring_route}
    if legacy_supp_type is not None:
        base["supplement_type"] = {
            "type": legacy_supp_type,
            "active_count": total_active_ingredients,
        }
    if legacy_primary_category is not None:
        base["primary_category"] = legacy_primary_category
    return base


# --- Baseline: generic preserves v3 behavior --------------------------------


def _v3_penalty_for_opaque() -> float:
    """Reference penalty for one opaque blend on a 5-ingredient / 2000mg product.
    Using mg-share: hidden_mass_mg = 500, total_active_mg = 2000, impact = 0.25.
    none-level base = 2.0, prop_coef = 5.0 → 2.0 + 5.0 * 0.25 = 3.25."""
    return 3.25


def _v3_penalty_for_partial() -> float:
    """Partial blend: total 1000, disclosed 200, hidden 800, impact = 800/2000 = 0.4.
    partial-level base = 1.0, prop_coef = 3.0 → 1.0 + 3.0 * 0.4 = 2.2."""
    return 2.2


def test_b5_generic_unchanged_for_unclassified_product(scorer: SupplementScorer) -> None:
    """A product with no class signal scores the same as v3 (multiplier 1.0).
    This is the regression-prevention anchor."""
    product = _product(blends=[_opaque_blend()])
    flags: List[str] = []
    penalty = scorer._compute_proprietary_blend_penalty(product, flags)
    assert penalty == pytest.approx(_v3_penalty_for_opaque() * 1.0, rel=1e-6)


def test_b5_specialty_unclassified_uses_generic_multiplier(scorer: SupplementScorer) -> None:
    """An unrecognized taxonomy type routes to generic (1.0x)."""
    product = _product(blends=[_opaque_blend()], primary_type="specialty")
    flags: List[str] = []
    penalty = scorer._compute_proprietary_blend_penalty(product, flags)
    assert penalty == pytest.approx(_v3_penalty_for_opaque() * 1.0, rel=1e-6)


# --- Probiotic: 0.4x ---------------------------------------------------------


def test_b5_probiotic_opaque_blend_reduced_to_04x(scorer: SupplementScorer) -> None:
    """A probiotic with an opaque proprietary blend (e.g., strains named in
    a `Probiotic Blend` container without per-strain CFU) gets 40% of the
    v3 penalty.  Strain-level CFU opacity is a category norm — partial
    transparency is genuinely better than hidden, but not the worst case."""
    product = _product(blends=[_opaque_blend()], primary_type="probiotic")
    flags: List[str] = []
    penalty = scorer._compute_proprietary_blend_penalty(product, flags)
    assert penalty == pytest.approx(_v3_penalty_for_opaque() * 0.4, rel=1e-6)


def test_b5_probiotic_partial_blend_reduced_to_04x(scorer: SupplementScorer) -> None:
    """Probiotic with partial-disclosure blend → 40% of v3."""
    product = _product(blends=[_partial_blend()], primary_type="probiotic")
    flags: List[str] = []
    penalty = scorer._compute_proprietary_blend_penalty(product, flags)
    assert penalty == pytest.approx(_v3_penalty_for_partial() * 0.4, rel=1e-6)


def test_b5_probiotic_full_disclosure_zero(scorer: SupplementScorer) -> None:
    """Class multiplier doesn't matter when the base penalty is zero —
    a probiotic with all per-strain CFU disclosed still scores 0."""
    product = _product(blends=[_full_blend()], primary_type="probiotic")
    flags: List[str] = []
    penalty = scorer._compute_proprietary_blend_penalty(product, flags)
    assert penalty == 0.0


# --- Multivitamin / prenatal: 1.3x ------------------------------------------


def test_b5_multivitamin_opaque_amplified_to_13x(scorer: SupplementScorer) -> None:
    """Multivitamins have well-known RDAs per nutrient. An opaque blend
    hides expected per-vitamin dosing → 1.3x v3."""
    product = _product(blends=[_opaque_blend()], primary_type="multivitamin")
    flags: List[str] = []
    penalty = scorer._compute_proprietary_blend_penalty(product, flags)
    assert penalty == pytest.approx(_v3_penalty_for_opaque() * 1.3, rel=1e-6)


def test_b5_prenatal_multivit_with_panel_uses_multi_class(scorer: SupplementScorer) -> None:
    """A genuine prenatal multivitamin with canonical taxonomy
    routes to multi_or_prenatal (1.3x) — the safety/dose-expectation
    profile of a vitamin/mineral panel justifies the tier.

    Updated 2026-05-23: the legacy "prenatal name keyword alone routes
    multi" override (former Priority 5 of _b5_class_for_product) was
    retired because it mis-classified single-active prenatal omegas and
    probiotic-marketed-as-prenatal products. To trigger multi_or_prenatal,
    the product now needs canonical multivitamin taxonomy or a native verified
    broad-panel scoring classification. See the inverse test below.
    """
    product = _product(
        blends=[_opaque_blend()],
        primary_type="multivitamin",
        product_name="Prenatal Multivitamin DHA",
    )
    flags: List[str] = []
    penalty = scorer._compute_proprietary_blend_penalty(product, flags)
    assert penalty == pytest.approx(_v3_penalty_for_opaque() * 1.3, rel=1e-6)


def test_b5_prenatal_dha_omega_routes_generic_not_multi(scorer: SupplementScorer) -> None:
    """Prenatal-marketed DHA/fish-oil products are not prenatal multis for
    blend-opacity purposes. They should use the generic omega path until the
    omega module owns this explicitly."""
    product = _product(
        blends=[_opaque_blend()],
        primary_type="omega_3",
        product_name="Prenatal DHA Unflavored Formula",
    )
    flags: List[str] = []
    penalty = scorer._compute_proprietary_blend_penalty(product, flags)
    assert penalty == pytest.approx(_v3_penalty_for_opaque() * 1.0, rel=1e-6)


def test_b5_prenatal_multivit_does_not_double_amp(scorer: SupplementScorer) -> None:
    """If taxonomy=multivitamin and name='Prenatal', stay at 1.3x —
    multi_or_prenatal is one class, not two stacked signals."""
    product = _product(
        blends=[_opaque_blend()],
        primary_type="multivitamin",
        product_name="Prenatal Multivitamin",
    )
    flags: List[str] = []
    penalty = scorer._compute_proprietary_blend_penalty(product, flags)
    assert penalty == pytest.approx(_v3_penalty_for_opaque() * 1.3, rel=1e-6)


def test_b5_enzyme_primary_category_misclassified_as_multi_routes_generic(
    scorer: SupplementScorer,
) -> None:
    """Some shipped enzyme products have primary_category=multivitamin even
    though the label/product name is enzyme-specific. Do not amplify as a multi."""
    product = _product(
        blends=[_opaque_blend()],
        primary_type="digestive_enzyme",
        product_name="Digestive Enzymes Ultra",
        legacy_primary_category="multivitamin",
    )
    flags: List[str] = []
    penalty = scorer._compute_proprietary_blend_penalty(product, flags)
    assert penalty == pytest.approx(_v3_penalty_for_opaque() * 1.0, rel=1e-6)


def test_b5_joint_support_misclassified_as_multivitamin_routes_generic(
    scorer: SupplementScorer,
) -> None:
    """Glucosamine/chondroitin/MSM products can be misclassified as multivitamin
    in v3 artifacts; opacity semantics are generic joint-support, not multi."""
    product = _product(
        blends=[_opaque_blend()],
        primary_type="joint_support",
        product_name="Triple Strength Glucosamine Chondroitin MSM",
        legacy_supp_type="multivitamin",
        legacy_primary_category="collagen",
    )
    flags: List[str] = []
    penalty = scorer._compute_proprietary_blend_penalty(product, flags)
    assert penalty == pytest.approx(_v3_penalty_for_opaque() * 1.0, rel=1e-6)


# --- Sports active: 1.5x -----------------------------------------------------


def test_b5_pre_workout_opaque_heaviest_15x(scorer: SupplementScorer) -> None:
    """Pre-workout with opaque blend → 1.5x v3.  Opaque blends in stimulant
    products are the WORST opacity case — they actively hide stim dose."""
    product = _product(
        blends=[_opaque_blend(name="Energy Matrix")],
        primary_type="general_supplement",
        product_name="Hyper Pre-Workout Energy Matrix",
    )
    flags: List[str] = []
    penalty = scorer._compute_proprietary_blend_penalty(product, flags)
    assert penalty == pytest.approx(_v3_penalty_for_opaque() * 1.5, rel=1e-6)


def test_b5_bcaa_keyword_routes_to_sports(scorer: SupplementScorer) -> None:
    """Product named '… BCAA Blend' → sports_active class."""
    product = _product(
        blends=[_opaque_blend()],
        primary_type="general_supplement",
        product_name="MaxLife BCAA Recovery Blend",
    )
    flags: List[str] = []
    penalty = scorer._compute_proprietary_blend_penalty(product, flags)
    assert penalty == pytest.approx(_v3_penalty_for_opaque() * 1.5, rel=1e-6)


def test_b5_creatine_keyword_routes_to_sports(scorer: SupplementScorer) -> None:
    product = _product(
        blends=[_opaque_blend()],
        primary_type="general_supplement",
        product_name="PowerLab Creatine Stack",
    )
    flags: List[str] = []
    penalty = scorer._compute_proprietary_blend_penalty(product, flags)
    assert penalty == pytest.approx(_v3_penalty_for_opaque() * 1.5, rel=1e-6)


# --- Cap still wins ---------------------------------------------------------


def test_b5_cap_holds_even_for_sports_with_many_blends(scorer: SupplementScorer) -> None:
    """Sports product + 4 opaque blends would raw-sum to 4 × 3.25 × 1.5 = 19.5
    but the dimension cap is 10. Multiplier scales the ramp, not the ceiling."""
    blends = [_opaque_blend(name=f"Blend {i}") for i in range(4)]
    product = _product(
        blends=blends,
        primary_type="general_supplement",
        product_name="MegaPre Pre-Workout",
    )
    flags: List[str] = []
    penalty = scorer._compute_proprietary_blend_penalty(product, flags)
    assert penalty == pytest.approx(10.0, rel=1e-6)


# --- Evidence emission ------------------------------------------------------


def test_b5_evidence_includes_class_routing(scorer: SupplementScorer) -> None:
    """Each blend's evidence should record the routed class + multiplier,
    so the score-delta report can explain why penalties shifted post-P0.2."""
    product = _product(blends=[_opaque_blend()], primary_type="probiotic")
    flags: List[str] = []
    scorer._compute_proprietary_blend_penalty(product, flags)
    assert scorer._last_b5_blend_evidence, "evidence list must be populated"
    ev = scorer._last_b5_blend_evidence[0]
    assert ev.get("blend_class") == "probiotic"
    assert ev.get("class_multiplier_applied") == pytest.approx(0.4, rel=1e-6)


# --- Config drift prevention -----------------------------------------------


def test_b5_config_documents_class_multipliers() -> None:
    """Config must list class_multipliers — same drift-prevention contract
    we applied to B4a in P0.1d."""
    cfg = json.loads((SCRIPTS_ROOT / "config" / "scoring_config.json").read_text())
    b5 = cfg["section_B_safety_purity"]["B5_proprietary_blends"]
    cls = b5.get("class_multipliers") or {}
    assert cls.get("probiotic") == 0.4
    assert cls.get("multi_or_prenatal") == 1.3
    assert cls.get("sports_active") == 1.5
    assert cls.get("generic") == 1.0


# --- No-blend short-circuit (regression) ------------------------------------


def test_b5_no_blends_returns_zero(scorer: SupplementScorer) -> None:
    """Product with no blends returns 0 regardless of class — multiplier
    must never resurrect a zero penalty."""
    for primary_type in ("probiotic", "multivitamin", "specialty", None):
        product = _product(blends=[], primary_type=primary_type)
        flags: List[str] = []
        penalty = scorer._compute_proprietary_blend_penalty(product, flags)
        assert penalty == 0.0, f"non-zero for primary_type={primary_type}"


# --- Direct class router unit tests ----------------------------------------


def test_class_router_probiotic(scorer: SupplementScorer) -> None:
    assert scorer._b5_class_for_product(_product([], primary_type="probiotic")) == "probiotic"


def test_class_router_multivitamin(scorer: SupplementScorer) -> None:
    assert scorer._b5_class_for_product(_product([], primary_type="multivitamin")) == "multi_or_prenatal"


def test_class_router_prenatal_name_alone_does_not_override(scorer: SupplementScorer) -> None:
    """Locked 2026-05-23: a "Prenatal Care DHA"-style canonical omega product
    routes to `generic`, NOT `multi_or_prenatal`. The legacy
    prenatal-name-keyword override (former Priority 5 of
    _b5_class_for_product) was retired because it mis-rated single-active
    prenatal omegas and probiotic-marketed-as-prenatal products. Genuine
    prenatal multivitamins still route correctly via taxonomy or the native
    scoring classification."""
    assert scorer._b5_class_for_product(
        _product([], primary_type="omega_3", product_name="Prenatal Care DHA")
    ) == "generic"


def test_class_router_sports_pre_workout(scorer: SupplementScorer) -> None:
    assert scorer._b5_class_for_product(
        _product([], primary_type="general_supplement", product_name="Hyper Pre-Workout")
    ) == "sports_active"


def test_class_router_sports_bcaa(scorer: SupplementScorer) -> None:
    assert scorer._b5_class_for_product(
        _product([], primary_type="general_supplement", product_name="BCAA Recovery 2:1:1")
    ) == "sports_active"


def test_class_router_generic_default(scorer: SupplementScorer) -> None:
    assert scorer._b5_class_for_product(
        _product([], primary_type="single_vitamin", product_name="Vitamin C 1000mg")
    ) == "generic"


def test_class_router_unknown_supp_type_default(scorer: SupplementScorer) -> None:
    assert scorer._b5_class_for_product(_product([])) == "generic"


def test_class_router_probiotic_beats_pre_workout_name(scorer: SupplementScorer) -> None:
    """If supp_type classifier says probiotic, that wins over any product-name
    keyword (the type classifier already inspected the ingredient panel)."""
    assert scorer._b5_class_for_product(
        _product([], primary_type="probiotic", product_name="Pre-Workout Probiotic")
    ) == "probiotic"


# --- P0.2 follow-up: classifier-disagreement repairs ----------------------
# The canary set exposed three classifier disagreement patterns on real
# shipped products. These tests lock in the router's intended behavior so
# the supp_type quirks don't silently mis-class B5 opacity.


def test_class_router_sports_keyword_beats_multivitamin_supp_type(
    scorer: SupplementScorer,
) -> None:
    """Nutricost PRE Pre-Workout (DSLD 306381) has supp_type=multivitamin
    because the formula bundles vitamins into the matrix. The product is
    functionally a pre-workout stack — opacity here hides per-component
    stim / amino doses. Sports class (1.5x) wins over multi (1.3x)."""
    assert scorer._b5_class_for_product(
        _product([], primary_type="multivitamin", product_name="Hyper Pre-Workout Energy Matrix")
    ) == "sports_active"


def test_class_router_bcaa_name_beats_multivitamin_supp_type(
    scorer: SupplementScorer,
) -> None:
    """GNC Beyond Raw Precision BCAA Gummy (DSLD 211334) — supp_type=multivit
    because gummy + vitamin co-pack. Sports keyword wins."""
    assert scorer._b5_class_for_product(
        _product([], primary_type="multivitamin", product_name="Precision BCAA Gummy")
    ) == "sports_active"


def test_class_router_whey_name_beats_multivitamin_supp_type(
    scorer: SupplementScorer,
) -> None:
    """SR Whey Protein Isolate (DSLD 268690) — supp_type=multivit because
    whey + added vitamins/minerals. Sports class wins because protein blend
    opacity is a sports-stack concern, not a multi-panel concern."""
    assert scorer._b5_class_for_product(
        _product([], primary_type="multivitamin", product_name="Whey Protein Isolate Chocolate")
    ) == "sports_active"


def test_class_router_ignores_legacy_primary_category_multivitamin(
    scorer: SupplementScorer,
) -> None:
    """A legacy primary_category cannot independently route B5."""
    assert scorer._b5_class_for_product(
        _product([], legacy_supp_type="specialty", product_name="Men's Multi Organic Berry",
                 legacy_primary_category="multivitamin")
    ) == "generic"


def test_class_router_native_broad_panel_routes_multivitamin(
    scorer: SupplementScorer,
) -> None:
    """The native scoring contract can route a verified broad panel."""
    assert scorer._b5_class_for_product(
        _product([], scoring_route="multi_or_prenatal", product_name="Daily Foundation Multi",
                 legacy_supp_type="targeted", legacy_primary_category="multivitamin")
    ) == "multi_or_prenatal"


def test_class_router_primary_category_fallback_doesnt_overreach(
    scorer: SupplementScorer,
) -> None:
    """Other legacy categories stay generic unless a B5-local name rule fires."""
    assert scorer._b5_class_for_product(
        _product([], legacy_supp_type="specialty", product_name="Fish Oil EPA",
                 legacy_primary_category="omega-3")
    ) == "generic"
    assert scorer._b5_class_for_product(
        _product([], legacy_supp_type="targeted", product_name="Collagen Peptides",
                 legacy_primary_category="collagen")
    ) == "generic"


def test_class_router_canonical_probiotic_wins_over_legacy_category(
    scorer: SupplementScorer,
) -> None:
    """Canonical probiotic taxonomy wins over a stale legacy category."""
    assert scorer._b5_class_for_product(
        _product([], primary_type="probiotic", product_name="Probiotic 50B",
                 legacy_primary_category="multivitamin")
    ) == "probiotic"
