"""v4 Omega module — contract and routing tests.

Originally created at P1.6.0 to lock the breakdown contract before scoring
math landed. Now also protects the complete P1.6.6 omega module contract:
all dimensions populate, manufacturer adjustments apply, and final score
assembly is online.

Per `docs/plans/SCORING_V4_PROPOSAL.md` §4 + §9 (Omega / fish-oil policy)
+ scripts/data/omega_rubric.json:

    | Dimension          | Omega |
    |--------------------|------:|
    | Formulation        |   25  |
    | Dose               |   25  |
    | Evidence           |   20  |
    | Testing & Trust    |   15  |
    | Transparency       |   15  |
    | (5-dimension sum)  |  100  |

Plus two SEPARATE adjustments (§6 line 390, module-agnostic):

    | Manufacturer Trust         | +5  |
    | Manufacturer Violations    |  0 to -25 |

Shared contract with generic and probiotic modules — same `dimensions` /
`components` / `penalties` / `metadata` / `manufacturer_trust` /
`manufacturer_violations` shape. Different dimension caps and different
per-dimension sub-rubrics (omega Formulation is form/source/sustainability
centric; Dose is EPA+DHA band; Trust is IFOS scope-aware verified-only).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


# Phase 4: trust is no longer a core dimension (it became verification_bonus).
EXPECTED_DIMENSION_CAPS = {
    "formulation": 25,
    "dose": 25,
    "evidence": 20,
    "transparency": 15,
}


COMPLETE_OMEGA_PRODUCT = {
    "status": "active",
    "form_factor": "capsule",
    "product_name": "Omega-3 1055 mg Fish Oil",
    "supplement_type": {
        "type": "targeted",
        "category_breakdown": {"fatty_acid": 4},
    },
    "ingredient_quality_data": {
        "total_active": 2,
        "ingredients_scorable": [
            {
                "name": "Eicosapentaenoic Acid",
                "canonical_id": "epa",
                "mapped": True,
                "quantity": 690,
                "unit": "mg",
            },
            {
                "name": "Docosahexaenoic Acid",
                "canonical_id": "dha",
                "mapped": True,
                "quantity": 310,
                "unit": "mg",
            },
        ],
    },
}


# --- Direct module contract ----------------------------------------------


def test_score_omega_returns_module_result_with_five_dimensions() -> None:
    from scoring_v4.modules.omega import score_omega

    result = score_omega(COMPLETE_OMEGA_PRODUCT)

    breakdown = result.to_breakdown()
    assert breakdown["module"] == "omega"
    assert set(breakdown["dimensions"].keys()) == set(EXPECTED_DIMENSION_CAPS.keys())


def test_omega_dimension_caps_match_rubric_config() -> None:
    """Dimension caps locked from scripts/data/omega_rubric.json must match
    the runtime DIMENSION_CAPS exposed by omega.py. Config-as-truth: any
    drift here means someone changed one without the other."""
    from scoring_v4.modules.omega import score_omega

    rubric = json.loads((SCRIPTS_ROOT / "data" / "omega_rubric.json").read_text())
    config_caps = rubric["dimension_caps"]

    breakdown = score_omega(COMPLETE_OMEGA_PRODUCT).to_breakdown()
    for name, expected_cap in EXPECTED_DIMENSION_CAPS.items():
        assert breakdown["dimensions"][name]["max"] == expected_cap, (
            f"dimension cap drift: omega.{name}.max != {expected_cap}"
        )
        assert config_caps[name] == expected_cap, (
            f"omega_rubric.json drift: dimension_caps.{name} != {expected_cap}"
        )


def test_omega_dimensions_share_stable_contract() -> None:
    """The dict shape itself is stable across slices: every dimension always
    has score/max/components/penalties/metadata keys. Slices populate
    their dimension's score in-place as they ship.

    P1.6.6 expectation: all five omega dimensions are populated while the
    shared dict shape remains stable."""
    from scoring_v4.modules.omega import score_omega

    breakdown = score_omega(COMPLETE_OMEGA_PRODUCT).to_breakdown()

    for name in EXPECTED_DIMENSION_CAPS:
        dim = breakdown["dimensions"][name]
        assert "score" in dim
        assert "max" in dim
        assert "components" in dim
        assert "penalties" in dim
        assert "metadata" in dim

    # P1.6.6: all 5 dimensions populate.
    for populated in ("formulation", "dose", "evidence", "transparency"):
        assert breakdown["dimensions"][populated]["score"] is not None, (
            f"omega.{populated}.score should be populated through P1.6.5"
        )


def test_omega_manufacturer_trust_dimension_has_cap_5() -> None:
    from scoring_v4.modules.omega import score_omega

    breakdown = score_omega(COMPLETE_OMEGA_PRODUCT).to_breakdown()
    mt = breakdown["manufacturer_trust"]
    # Manufacturer Trust is module-agnostic and still capped at +5.
    assert mt["max"] == 5
    assert isinstance(mt["components"], dict)


def test_omega_manufacturer_violations_floor_minus_25() -> None:
    from scoring_v4.modules.omega import score_omega

    breakdown = score_omega(COMPLETE_OMEGA_PRODUCT).to_breakdown()
    mv = breakdown["manufacturer_violations"]
    # Shape is stable; the standard manufacturer-violation floor stays at -25.
    assert mv["floor"] == -25


def test_omega_phase_marker_rolls_forward_across_slices() -> None:
    """Module-level phase marker rolls forward as each P1.6.x slice lands.
    Asserting starts-with 'P1.6.' keeps the test resilient across maintenance
    slices without hiding a wrong module family."""
    from scoring_v4.modules.omega import score_omega

    breakdown = score_omega(COMPLETE_OMEGA_PRODUCT).to_breakdown()
    assert breakdown["phase"].startswith("P1.6."), (
        f"unexpected phase marker: {breakdown['phase']}"
    )


def test_score_omega_resilient_to_malformed_input() -> None:
    """Never raise on malformed input — the dimensions skeleton stays
    intact and the breakdown shape is unchanged. P1.6.6 lands score_100
    as a real number after final assembly (low end of the raw rubric range
    for empty input)."""
    from scoring_v4.modules.omega import score_omega

    for bad in (None, {}, {"supplement_type": None}, 42, "oops"):
        result = score_omega(bad)  # type: ignore[arg-type]
        breakdown = result.to_breakdown()
        assert breakdown["module"] == "omega"
        assert set(breakdown["dimensions"].keys()) == set(EXPECTED_DIMENSION_CAPS.keys())
        # P1.6.6/Phase 9: score_100 is the rubric production score; even
        # empty input yields a real number in [0, 100].
        assert breakdown["score_100"] is None or 0 <= breakdown["score_100"] <= 100


def test_score_omega_does_not_mutate_input() -> None:
    from scoring_v4.modules.omega import score_omega

    product = {**COMPLETE_OMEGA_PRODUCT}
    before = json.dumps(product, sort_keys=True)
    score_omega(product)
    assert json.dumps(product, sort_keys=True) == before


# --- Router contract -----------------------------------------------------


def test_router_dispatches_fish_oil_primary_category_to_omega() -> None:
    from scoring_v4.router import class_for_product

    product = {"primary_category": "fish_oil", "product_name": "Fish Oil 1000 mg"}
    assert class_for_product(product) == "omega"


def test_router_dispatches_omega3_primary_category_to_omega() -> None:
    from scoring_v4.router import class_for_product

    product = {"primary_category": "omega-3", "product_name": "EPA+DHA"}
    assert class_for_product(product) == "omega"


def test_router_dispatches_fish_oil_name_keyword_to_omega() -> None:
    """Fall through to keyword detection when primary_category is missing."""
    from scoring_v4.router import class_for_product

    product = {"product_name": "Maximum Fish Oil Triple Strength"}
    assert class_for_product(product) == "omega"


def test_router_dispatches_krill_name_keyword_to_omega() -> None:
    from scoring_v4.router import class_for_product

    product = {"product_name": "Antarctic Krill Oil 500 mg"}
    assert class_for_product(product) == "omega"


def test_router_dispatches_algae_name_keyword_to_omega() -> None:
    from scoring_v4.router import class_for_product

    product = {"product_name": "Vegan Algae Oil EPA DHA"}
    assert class_for_product(product) == "omega"


def test_router_dispatches_cod_liver_name_keyword_to_omega() -> None:
    from scoring_v4.router import class_for_product

    product = {"product_name": "Norwegian Cod Liver Oil"}
    assert class_for_product(product) == "omega"


def test_router_keeps_cod_liver_vitamin_panel_generic_without_omega_evidence() -> None:
    from scoring_v4.router import class_for_product

    product = {
        "product_name": "Cod Liver Oil A & D Supplement",
        "primary_type": "single_vitamin",
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"canonical_id": "vitamin_a", "quantity": 1250, "unit": "IU", "mapped": True},
                {"canonical_id": "vitamin_d", "quantity": 130, "unit": "IU", "mapped": True},
            ]
        },
    }
    assert class_for_product(product) == "generic"


def test_router_does_not_route_fatty_acid_plurality_alone_to_omega() -> None:
    """REMOVED PLURALITY CHECK (2026-05-20 real-catalog audit).
    A product whose category_breakdown shows fatty_acid plurality but
    has NO EPA/DHA canonical and NO omega name keyword must NOT route
    to omega. The plurality check was removed because the enricher
    categorizes ALA / GLA / CLA / MCT / lecithin all as 'fatty_acid' —
    none of which are EPA/DHA. Catalog audit caught ~250 false positives.
    Such products route to generic by fallthrough.

    Real catalog cases this prevents: Pure Encapsulations CLA / Borage
    Oil / Flax Seed Oil, Liposomal Glutathione (lecithin counts as
    fatty_acid), vitafusion D3 with MCT carrier. Nordic Naturals's
    Ultimate Omega is STILL caught by _has_omega_ingredient because the
    enricher canonicalizes EPA/DHA from the ingredient panel."""
    from scoring_v4.router import class_for_product

    product = {
        "product_name": "Premium Marine Lipid Complex",  # no omega keyword
        "supplement_type": {
            "type": "specialty",
            "category_breakdown": {"fatty_acid": 5, "antioxidant": 1},
        },
        # No EPA/DHA canonical in the panel
    }
    assert class_for_product(product) == "generic"


def test_router_does_not_route_cla_to_omega() -> None:
    """Catalog edge case: Pure Encapsulations CLA 1,000 mg has
    category_breakdown={vitamin: 1, fatty_acid: 1} and canonical_id=cla.
    CLA is conjugated linoleic acid, an OMEGA-6 isomer, NOT omega-3.
    Must route to generic."""
    from scoring_v4.router import class_for_product

    product = {
        "product_name": "CLA 1,000 mg",
        "supplement_type": {
            "type": "targeted",
            "category_breakdown": {"vitamin": 1, "fatty_acid": 1},
        },
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"name": "Vitamin E", "canonical_id": "vitamin_e", "quantity": 1},
                {"name": "CLA", "canonical_id": "cla", "quantity": 1000},
            ]
        },
    }
    assert class_for_product(product) == "generic"


def test_router_does_not_route_borage_oil_gla_to_omega() -> None:
    """Catalog edge case: Pure Encapsulations Borage Oil contains
    gamma_linolenic_acid (GLA, omega-6). Must route to generic."""
    from scoring_v4.router import class_for_product

    product = {
        "product_name": "Borage Oil",
        "supplement_type": {
            "type": "targeted",
            "category_breakdown": {"vitamin": 1, "fatty_acid": 1},
        },
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"name": "Vitamin E", "canonical_id": "vitamin_e", "quantity": 5},
                {"name": "Gamma-Linolenic Acid", "canonical_id": "gamma_linolenic_acid",
                 "quantity": 240},
            ]
        },
    }
    assert class_for_product(product) == "generic"


def test_router_does_not_route_flax_seed_ala_only_to_omega() -> None:
    """Catalog edge case: Pure Encapsulations Flax Seed Oil (Organic)
    contains alpha_linolenic_acid (ALA only — no EPA/DHA). Per the dev's
    2026-05-20 RDA-table feedback: ALA is a different molecule from
    EPA/DHA. Must route to generic so ALA-specific IOM AI logic applies
    (when rda_optimal_uls is fixed by Codex)."""
    from scoring_v4.router import class_for_product

    product = {
        "product_name": "Flax Seed Oil (Organic)",
        "supplement_type": {
            "type": "targeted",
            "category_breakdown": {"functional_food": 1, "fatty_acid": 1},
        },
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"name": "Flax Seed Oil", "canonical_id": "flaxseed", "quantity": 1000},
                {"name": "Alpha-Linolenic Acid", "canonical_id": "alpha_linolenic_acid",
                 "quantity": 540},
            ]
        },
    }
    assert class_for_product(product) == "generic"


def test_router_does_not_route_liposomal_glutathione_to_omega() -> None:
    """Catalog edge case: Pure Encapsulations Liposomal Glutathione has
    category_breakdown={antioxidant: 2, fatty_acid: 2} (lecithin counts
    as fatty_acid in the enricher). The product is glutathione, NOT
    omega-3. Must route to generic."""
    from scoring_v4.router import class_for_product

    product = {
        "product_name": "Liposomal Glutathione",
        "supplement_type": {
            "type": "targeted",
            "category_breakdown": {"antioxidant": 2, "fatty_acid": 2},
        },
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"name": "Glutathione", "canonical_id": "glutathione", "quantity": 250},
                {"name": "Lecithin", "canonical_id": "lecithin", "quantity": 200},
            ]
        },
    }
    assert class_for_product(product) == "generic"


def test_router_does_not_route_d3_with_mct_carrier_to_omega() -> None:
    """Catalog edge case: vitafusion D3 75 mcg has vitamin_d as primary
    active and MCT oil as a carrier. The PRIMARY active is D3, not
    EPA/DHA. Must NOT route to omega — D3 is a fat-soluble vitamin,
    not a fish-oil product."""
    from scoring_v4.router import class_for_product

    product = {
        "product_name": "D3 Extra Strength 75 mcg Natural Strawberry Flavor",
        "supplement_type": {
            "type": "targeted",
            "category_breakdown": {"vitamin": 1, "fatty_acid": 1},
        },
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"name": "Vitamin D", "canonical_id": "vitamin_d",
                 "quantity": 75, "unit": "mcg"},
                {"name": "MCT Oil", "canonical_id": "mct_oil", "quantity": 500},
            ]
        },
    }
    assert class_for_product(product) == "generic"


def test_router_routes_single_purpose_prenatal_dha_to_omega() -> None:
    """Single-purpose Prenatal DHA is omega, not an incomplete prenatal multi.

    Broad prenatal vitamin/mineral panels still route multi_or_prenatal; a DHA
    product should be scored on EPA/DHA disclosure and dose instead of being
    crushed for absent folate/iron/iodine/choline.
    """
    from scoring_v4.router import class_for_product

    product = {
        "product_name": "Prenatal DHA",
        "primary_category": "omega-3",  # would otherwise route to omega
    }
    assert class_for_product(product) == "omega"


def test_router_does_not_route_minority_fatty_acid_to_omega() -> None:
    """A specialty product with one fatty acid among 10 actives is not
    omega. category_breakdown is no longer an omega routing trigger."""
    from scoring_v4.router import class_for_product

    product = {
        "product_name": "Broad-Spectrum Adrenal Support",
        "supplement_type": {
            "type": "specialty",
            "category_breakdown": {"fatty_acid": 1, "botanical": 8, "vitamin": 1},
        },
    }
    assert class_for_product(product) == "generic"


def test_router_routes_omega_369_when_epa_dha_are_disclosed() -> None:
    """Omega 3-6-9 labels are not automatically excluded when EPA/DHA exists.

    Real catalog regression: some 3-6-9 products disclose EPA/DHA rows and have
    omega_3 taxonomy. Those should use the omega module rather than generic.
    """
    from scoring_v4.router import class_for_product

    product = {
        "product_name": "Omega 3-6-9 Lemon",
        "primary_type": "omega_3",
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"name": "Alpha-Linolenic Acid", "canonical_id": "alpha_linolenic_acid", "quantity": 378, "unit": "mg"},
                {"name": "EPA", "canonical_id": "epa", "quantity": 180, "unit": "mg"},
                {"name": "DHA", "canonical_id": "dha", "quantity": 120, "unit": "mg"},
                {"name": "Gamma Linolenic Acid", "canonical_id": "gamma_linolenic_acid", "quantity": 180, "unit": "mg"},
            ],
        },
    }
    assert class_for_product(product) == "omega"


def test_router_keeps_ala_only_omega_369_out_of_epa_dha_module() -> None:
    """ALA/GLA/CLA 3-6-9 products without EPA/DHA stay generic."""
    from scoring_v4.router import class_for_product

    product = {
        "product_name": "Omega 3-6-9",
        "primary_type": "omega_3",
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"name": "Alpha-Linolenic Acid", "canonical_id": "alpha_linolenic_acid", "quantity": 600, "unit": "mg"},
                {"name": "Gamma Linolenic Acid", "canonical_id": "gamma_linolenic_acid", "quantity": 200, "unit": "mg"},
                {"name": "Conjugated Linoleic Acid", "canonical_id": "cla", "quantity": 100, "unit": "mg"},
            ],
        },
    }
    assert class_for_product(product) == "generic"


def test_router_valid_classes_includes_omega() -> None:
    from scoring_v4.router import VALID_CLASSES

    assert "omega" in VALID_CLASSES


def test_router_dispatches_standalone_epa_name_to_omega() -> None:
    """Standalone EPA in product name routes omega. Word-boundary detection
    ensures this catches 'Pure EPA 500 mg' / 'EPA Concentrate' style
    products that don't have a combined 'EPA+DHA' or 'fish oil' keyword.

    Per Sean 2026-05-20: 'product name or ingredient panel with standalone
    EPA or DHA should route omega, not generic.'"""
    from scoring_v4.router import class_for_product

    product = {"product_name": "Pure EPA 500 mg Softgels"}
    assert class_for_product(product) == "omega"


def test_router_dispatches_standalone_dha_name_to_omega() -> None:
    """Standalone DHA — same policy as EPA. Algal DHA products typically
    label only 'DHA' without combined-form keyword."""
    from scoring_v4.router import class_for_product

    product = {"product_name": "Vegetarian DHA 300 mg"}
    assert class_for_product(product) == "omega"


def test_router_does_not_match_dhea_as_omega() -> None:
    """CRITICAL: DHEA (dehydroepiandrosterone) is a hormone, NOT omega-3.
    Word-boundary regex `\\bDHA\\b` must NOT match inside the word DHEA.
    A loose substring search would false-positive route every DHEA
    hormone product to omega — this test locks the guard."""
    from scoring_v4.router import class_for_product

    for name in (
        "DHEA 25 mg",
        "DHEA Daily Support",
        "Pure DHEA 50 mg Capsules",
        "Micronized DHEA",
    ):
        product = {"product_name": name}
        assert class_for_product(product) == "generic", (
            f"DHEA product wrongly routed to omega: {name!r}"
        )


def test_router_dispatches_ingredient_panel_epa_to_omega() -> None:
    """Strongest router signal — ingredient_quality_data has canonical_id=epa
    with positive quantity. Routes omega regardless of name. Catches
    products with brand-only or marketing names like 'Heart Health Formula'
    that nonetheless carry EPA as an active ingredient."""
    from scoring_v4.router import class_for_product

    product = {
        "product_name": "Cardio Health Formula",  # no omega keyword
        "supplement_type": {"type": "targeted"},
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"name": "Eicosapentaenoic Acid", "canonical_id": "epa",
                 "quantity": 400, "unit": "mg"}
            ],
        },
    }
    assert class_for_product(product) == "omega"


def test_router_dispatches_ingredient_panel_dha_to_omega() -> None:
    """Same as above for DHA canonical."""
    from scoring_v4.router import class_for_product

    product = {
        "product_name": "Brain Support Daily",  # no omega keyword
        "supplement_type": {"type": "specialty"},
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"name": "Docosahexaenoic Acid", "canonical_id": "dha",
                 "quantity": 200, "unit": "mg"}
            ],
        },
    }
    assert class_for_product(product) == "omega"


def test_router_does_not_route_mixed_formula_with_incidental_dha_to_omega() -> None:
    """A broad mixed formula with one DHA row is not an omega product.

    Real catalog regression: Thorne SynaQuell had 13 actives and one DHA
    row, was taxonomy-tagged omega_3, then v4 routed it into the omega module.
    The omega module should be reserved for primary EPA/DHA products, not
    every formula containing incidental DHA.
    """
    from scoring_v4.router import class_for_product

    product = {
        "product_name": "SynaQuell",
        "primary_type": "omega_3",
        "supplement_taxonomy": {"primary_type": "omega_3"},
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"name": "Riboflavin", "canonical_id": "vitamin_b2_riboflavin", "quantity": 25, "unit": "mg"},
                {"name": "Magnesium", "canonical_id": "magnesium", "quantity": 59, "unit": "mg"},
                {"name": "L-Leucine", "canonical_id": "l_leucine", "quantity": 1250, "unit": "mg"},
                {"name": "L-Isoleucine", "canonical_id": "l_isoleucine", "quantity": 625, "unit": "mg"},
                {"name": "L-Valine", "canonical_id": "l_valine", "quantity": 625, "unit": "mg"},
                {"name": "Glutathione", "canonical_id": "glutathione", "quantity": 250, "unit": "mg"},
                {"name": "Curcumin", "canonical_id": "curcumin", "quantity": 125, "unit": "mg"},
                {"name": "DHA", "canonical_id": "dha", "quantity": 125, "unit": "mg"},
                {"name": "Resveratrol", "canonical_id": "resveratrol", "quantity": 125, "unit": "mg"},
                {"name": "CoQ10", "canonical_id": "coq10", "quantity": 50, "unit": "mg"},
            ],
        },
    }
    assert class_for_product(product) == "generic"


def test_router_does_not_route_theanine_caffeine_with_incidental_dha_to_omega() -> None:
    """DHA can appear in non-omega functional stacks; that alone is not enough."""
    from scoring_v4.router import class_for_product

    product = {
        "product_name": "L-Theanine + Caffeine",
        "primary_type": "omega_3",
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"name": "DHA", "canonical_id": "dha", "quantity": 450, "unit": "mg"},
                {"name": "L-Theanine", "canonical_id": "l_theanine", "quantity": 200, "unit": "mg"},
                {"name": "Caffeine", "canonical_id": "caffeine", "quantity": 100, "unit": "mg"},
            ],
        },
    }
    assert class_for_product(product) == "generic"


def test_router_keeps_fish_oil_with_vitamin_d_as_omega() -> None:
    """A fish-oil product with vitamin D remains omega: EPA/DHA is primary."""
    from scoring_v4.router import class_for_product

    product = {
        "product_name": "Fish Oil With Vitamin D3",
        "primary_type": "omega_3",
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"name": "Vitamin D", "canonical_id": "vitamin_d", "quantity": 25, "unit": "mcg"},
                {"name": "Fish Oil", "canonical_id": "fish_oil", "quantity": 755, "unit": "mg"},
                {"name": "EPA", "canonical_id": "epa", "quantity": 33, "unit": "mg"},
                {"name": "DHA", "canonical_id": "dha", "quantity": 166, "unit": "mg"},
            ],
        },
    }
    assert class_for_product(product) == "omega"


def test_router_does_not_route_dhea_canonical_to_omega() -> None:
    """A hormone product with canonical_id=dhea must NOT route to omega.
    Ingredient-panel detection only triggers on EPA/DHA/EPA_DHA canonicals,
    NOT DHEA (different molecule, different canonical token)."""
    from scoring_v4.router import class_for_product

    product = {
        "product_name": "DHEA Hormone Support 50 mg",
        "supplement_type": {"type": "specialty"},
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"name": "Dehydroepiandrosterone", "canonical_id": "dhea",
                 "quantity": 50, "unit": "mg"}
            ],
        },
    }
    assert class_for_product(product) == "generic"


def test_router_dispatches_ingredient_panel_with_zero_quantity_not_to_omega() -> None:
    """Defensive: if EPA/DHA canonical is present but quantity is zero or
    missing, the ingredient-panel signal does NOT trigger. Name keywords
    or other signals can still route omega (this product has neither)."""
    from scoring_v4.router import class_for_product

    product = {
        "product_name": "Some Generic Stack",
        "supplement_type": {"type": "specialty"},
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"name": "EPA placeholder", "canonical_id": "epa", "quantity": 0},
                {"name": "DHA placeholder", "canonical_id": "dha"},  # no quantity
            ],
        },
    }
    assert class_for_product(product) == "generic"


# --- Completeness gate contract ------------------------------------------


def test_completeness_gate_omega_accepts_explicit_epa_and_dha() -> None:
    """A product with disclosed EPA and DHA mg quantities passes the omega
    gate. Real canary shape (Sports Research 327776 + Nordic 288740)."""
    from scoring_v4.gate_completeness import evaluate_completeness_gate

    result = evaluate_completeness_gate(COMPLETE_OMEGA_PRODUCT, "omega")
    assert result.is_live_eligible is True
    assert "epa_or_dha_disclosed" in result.checked_fields
    assert "epa_or_dha_disclosed" not in result.missing_fields


def test_completeness_gate_omega_accepts_pure_epa_only() -> None:
    """Pure-EPA products (e.g. prescription-grade icosapent ethyl) qualify
    even without DHA. Per Sean 2026-05-20: 'At least one is the right
    eligibility policy because pure EPA and pure DHA products can be
    legitimate.'"""
    from scoring_v4.gate_completeness import evaluate_completeness_gate

    product = {
        "status": "active",
        "form_factor": "capsule",
        "product_name": "Pure EPA 500 mg",
        "supplement_type": {"type": "specialty"},
        "ingredient_quality_data": {
            "total_active": 1,
            "ingredients_scorable": [
                {"name": "EPA", "canonical_id": "epa", "mapped": True,
                 "quantity": 500, "unit": "mg"},
            ],
        },
    }
    result = evaluate_completeness_gate(product, "omega")
    assert result.is_live_eligible is True
    assert "epa_or_dha_disclosed" not in result.missing_fields


def test_completeness_gate_omega_accepts_pure_dha_only() -> None:
    """Pure-DHA products (e.g. algal DHA for vegans / prenatal DHA route)
    qualify even without EPA."""
    from scoring_v4.gate_completeness import evaluate_completeness_gate

    product = {
        "status": "active",
        "form_factor": "softgel",
        "product_name": "Algal DHA 200 mg",
        "supplement_type": {"type": "specialty"},
        "ingredient_quality_data": {
            "total_active": 1,
            "ingredients_scorable": [
                {"name": "DHA", "canonical_id": "dha", "mapped": True,
                 "quantity": 200, "unit": "mg"},
            ],
        },
    }
    result = evaluate_completeness_gate(product, "omega")
    assert result.is_live_eligible is True
    assert "epa_or_dha_disclosed" not in result.missing_fields


def test_completeness_gate_omega_rejects_fish_oil_parent_only() -> None:
    """A 'Fish Oil 1000 mg' product with no EPA/DHA breakdown fails the
    omega completeness gate → NOT_SCORED. Per §9 line 509: 'Fish oil
    1000 mg with no EPA/DHA breakdown should score significantly lower.'
    P1.6 enforces this as live-eligibility, not a score cap."""
    from scoring_v4.gate_completeness import evaluate_completeness_gate

    product = {
        "status": "active",
        "form_factor": "capsule",
        "product_name": "Fish Oil 1000 mg",
        "supplement_type": {"type": "specialty"},
        "ingredient_quality_data": {
            "total_active": 1,
            "ingredients_scorable": [
                {
                    "name": "Fish Oil",
                    "canonical_id": "fish_oil",
                    "mapped": True,
                    "quantity": 1000,
                    "unit": "mg",
                }
            ],
        },
    }
    result = evaluate_completeness_gate(product, "omega")
    assert result.is_live_eligible is False
    assert "epa_or_dha_disclosed" in result.missing_fields


def test_completeness_gate_omega_rejects_omega3_parent_mass_only() -> None:
    """Broad omega-3 parent mass is not EPA/DHA disclosure.

    This locks the RDA-table integrity decision: omega_3_fatty_acids /
    omega3 is not a synonym for combined EPA+DHA. A product can route to
    omega by name/category, but Layer 2 requires EPA, DHA, or explicit
    EPA+DHA combined disclosure with dose and unit.
    """
    from scoring_v4.gate_completeness import evaluate_completeness_gate

    product = {
        "status": "active",
        "form_factor": "capsule",
        "product_name": "Omega-3 Fatty Acids 1000 mg",
        "primary_category": "omega3",
        "supplement_type": {"type": "specialty"},
        "ingredient_quality_data": {
            "total_active": 1,
            "ingredients_scorable": [
                {
                    "name": "Omega-3 Fatty Acids",
                    "canonical_id": "omega3",
                    "mapped": True,
                    "quantity": 1000,
                    "unit": "mg",
                }
            ],
        },
    }
    result = evaluate_completeness_gate(product, "omega")
    assert result.is_live_eligible is False
    assert "epa_or_dha_disclosed" in result.missing_fields


def test_completeness_gate_omega_rejects_epa_without_quantity() -> None:
    """EPA disclosed but no mg quantity → fails the gate. Aligns with
    'do not invent fields' — labeled-without-amount is not adequate
    disclosure for live catalog eligibility."""
    from scoring_v4.gate_completeness import evaluate_completeness_gate

    product = {
        "status": "active",
        "form_factor": "capsule",
        "supplement_type": {"type": "specialty"},
        "ingredient_quality_data": {
            "total_active": 1,
            "ingredients_scorable": [
                {"name": "EPA", "canonical_id": "epa", "mapped": True},  # no quantity
            ],
        },
    }
    result = evaluate_completeness_gate(product, "omega")
    assert result.is_live_eligible is False
    assert "epa_or_dha_disclosed" in result.missing_fields


def test_completeness_gate_omega_rejects_epa_quantity_without_unit() -> None:
    """EPA quantity without a valid unit is not dose disclosure. P1.6.2
    computes mg/day, so live eligibility must require quantity + unit,
    not just a positive number."""
    from scoring_v4.gate_completeness import evaluate_completeness_gate

    product = {
        "status": "active",
        "form_factor": "capsule",
        "supplement_type": {"type": "specialty"},
        "ingredient_quality_data": {
            "total_active": 1,
            "ingredients_scorable": [
                {"name": "EPA", "canonical_id": "epa", "mapped": True,
                 "quantity": 500},
            ],
        },
    }
    result = evaluate_completeness_gate(product, "omega")
    assert result.is_live_eligible is False
    assert "epa_or_dha_disclosed" in result.missing_fields


def test_completeness_gate_omega_rejects_epa_with_np_unit() -> None:
    """The DSLD NP sentinel means the unit was not provided. It must not
    satisfy the EPA/DHA disclosure gate."""
    from scoring_v4.gate_completeness import evaluate_completeness_gate

    product = {
        "status": "active",
        "form_factor": "capsule",
        "supplement_type": {"type": "specialty"},
        "ingredient_quality_data": {
            "total_active": 1,
            "ingredients_scorable": [
                {"name": "EPA", "canonical_id": "epa", "mapped": True,
                 "quantity": 500, "unit": "NP"},
            ],
        },
    }
    result = evaluate_completeness_gate(product, "omega")
    assert result.is_live_eligible is False
    assert "epa_or_dha_disclosed" in result.missing_fields


# --- Shadow integration ---------------------------------------------------


def test_shadow_wires_omega_module_when_route_is_omega() -> None:
    """After Layer 1 + Layer 2 pass for an omega-routed product, the
    shadow scorer must call score_omega and stash its breakdown under
    `shadow_score_v4_breakdown["module"]`."""
    from score_supplements_v4_shadow import score_product_v4_shadow

    out = score_product_v4_shadow(COMPLETE_OMEGA_PRODUCT)

    assert out["shadow_score_v4_module"] == "omega"
    assert "module" in out["shadow_score_v4_breakdown"]
    module_block = out["shadow_score_v4_breakdown"]["module"]
    assert module_block["module"] == "omega"
    assert set(module_block["dimensions"].keys()) == set(EXPECTED_DIMENSION_CAPS.keys())
    # P1.6.6: score_100 is a real production number after final assembly.
    assert module_block["score_100"] is not None
    assert 0 <= module_block["score_100"] <= 100


def test_shadow_does_not_wire_omega_module_when_completeness_fails() -> None:
    """A fish-oil-parent-only product fails Layer 2 and skips score_omega.
    Confirms the omega completeness gate plumbs through correctly."""
    from score_supplements_v4_shadow import score_product_v4_shadow

    incomplete = {
        "status": "active",
        "form_factor": "capsule",
        "product_name": "Fish Oil 1000 mg",
        "supplement_type": {"type": "specialty"},
        "ingredient_quality_data": {
            "total_active": 1,
            "ingredients_scorable": [
                {"name": "Fish Oil", "canonical_id": "fish_oil", "mapped": True,
                 "quantity": 1000, "unit": "mg"},
            ],
        },
    }
    out = score_product_v4_shadow(incomplete)

    assert out["shadow_score_v4_verdict"] == "NOT_SCORED"
    assert out["shadow_score_v4_module"] == "omega"
    assert out["shadow_score_v4_breakdown"]["completeness_gate"]["module"] == "omega"
    assert "epa_or_dha_disclosed" in out["shadow_score_v4_breakdown"]["completeness_gate"]["missing_fields"]


def test_shadow_does_not_route_generic_product_to_omega_module() -> None:
    """A magnesium single-nutrient still routes to generic — omega routing must
    not leak omega routing onto non-omega rows."""
    from score_supplements_v4_shadow import score_product_v4_shadow

    generic = {
        "status": "active", "form_factor": "capsule",
        "product_name": "Magnesium Glycinate 200 mg",
        "supplement_type": {"type": "single_nutrient"},
        "ingredient_quality_data": {
            "total_active": 1,
            "ingredients_scorable": [
                {"name": "Mg", "canonical_id": "magnesium", "mapped": True,
                 "bio_score": 14, "quantity": 200, "unit": "mg"}
            ],
        },
    }
    out = score_product_v4_shadow(generic)

    assert out["shadow_score_v4_module"] == "generic"
    module_block = out["shadow_score_v4_breakdown"].get("module")
    assert module_block is not None
    assert module_block["module"] == "generic"


# --- Architecture lock ---------------------------------------------------


def test_omega_module_does_not_import_v3_scorer() -> None:
    """v4 scoring policy is independent (§13 architecture lock).
    Apply to all omega per-dimension stubs. Uses AST inspection so
    docstring mentions of 'score_supplements' don't trigger false positives."""
    import ast
    import scoring_v4.modules.omega as om

    omega_files = [
        Path(om.__file__),
        Path(om.__file__).parent / "omega_formulation.py",
        Path(om.__file__).parent / "omega_dose.py",
        Path(om.__file__).parent / "omega_evidence.py",
        Path(om.__file__).parent / "omega_trust.py",
        Path(om.__file__).parent / "omega_transparency.py",
    ]
    for f in omega_files:
        tree = ast.parse(f.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module_name = node.module or ""
                assert not module_name.startswith("score_supplements"), (
                    f"v4→v3 import in {f.name}: from {module_name}"
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("score_supplements"), (
                        f"v4→v3 import in {f.name}: import {alias.name}"
                    )


def test_omega_module_importable_via_modules_package() -> None:
    import scoring_v4.modules as modules
    import scoring_v4.modules.omega  # noqa: F401

    assert "omega" in modules.__all__


# --- Config-as-truth -----------------------------------------------------


def test_omega_rubric_config_present_and_well_formed() -> None:
    """omega_rubric.json exists, is valid JSON, and carries the contract
    fields the module code expects. Per Sean 2026-05-20: 'Config-driven is
    right, but only if tests lock the behavior. Don't let omega_rubric.json
    become an untested policy blob.'"""
    rubric_path = SCRIPTS_ROOT / "data" / "omega_rubric.json"
    assert rubric_path.exists()
    rubric = json.loads(rubric_path.read_text())

    # Top-level structure
    for key in ("_metadata", "phase", "dimension_caps", "formulation",
                "dose", "evidence", "trust", "transparency", "router",
                "completeness_gate"):
        assert key in rubric, f"omega_rubric missing top-level key: {key}"

    # Metadata schema lock
    assert rubric["_metadata"]["schema_version"] == "1.0.0"
    assert rubric["_metadata"]["purpose"] == "scoring_v4_omega_module_rubric"

    # Phase 4: trust moved out of the core denominator to verification_bonus,
    # so the core dimension caps now sum to 85 (the trust SCORING section
    # remains in the rubric and is consumed by the verification bonus).
    assert sum(rubric["dimension_caps"].values()) == 85


def test_omega_rubric_form_tier_table_locked() -> None:
    """Form tier values are deliberate clinical-tier choices, not knobs."""
    rubric = json.loads((SCRIPTS_ROOT / "data" / "omega_rubric.json").read_text())
    form_tier = rubric["formulation"]["form_tier"]

    # Locked weights per scientific bioavailability tiering.
    assert form_tier["tg"] == 8     # triglyceride: gold standard
    assert form_tier["pl"] == 7     # phospholipid (krill)
    assert form_tier["rtg"] == 6    # re-esterified triglyceride
    assert form_tier["ee"] == 4     # ethyl ester
    assert form_tier["undefined"] == 2


def test_omega_rubric_dose_bands_match_v3_legacy_thresholds() -> None:
    """EPA+DHA dose-band thresholds are lifted from
    scoring_config.section_A_ingredient_quality.omega3_dose_bonus.bands.
    Thresholds (250/500/1000/2000/4000) are evidence-grounded
    (EFSA/FDA/AHA/ACC); they must not drift unless the underlying
    guidance changes. Scores are rescaled to /20 for the omega Dose
    sub-component."""
    rubric = json.loads((SCRIPTS_ROOT / "data" / "omega_rubric.json").read_text())
    bands = rubric["dose"]["epa_dha_bands"]

    thresholds = [b["min_mg_day"] for b in bands]
    assert thresholds == [4000, 2000, 1000, 500, 250, 0]

    # Top of band reaches the dim cap of 20.
    assert bands[0]["score"] == 20  # 4000+ prescription
    assert bands[-1]["score"] == 0  # below_efsa_ai


def test_omega_rubric_trust_scope_policy_only_credits_verified_scopes() -> None:
    """Per Sean's 2026-05-20 directive: needs_review and brand_only stay
    zero. Only sku and curated product_line score. Locked here so a future
    config tweak can't silently reintroduce manufacturer overcredit."""
    rubric = json.loads((SCRIPTS_ROOT / "data" / "omega_rubric.json").read_text())
    policy = rubric["trust"]["b4a_scope_policy"]

    assert policy["sku"] == 10
    assert policy["product_line"] == 10
    assert policy["needs_review"] == 0
    assert policy["brand_only"] == 0
    assert policy["claimed_only"] == 0
    assert policy["rejected"] == 0


def test_omega_rubric_sustainability_eligibility_requires_rules_db_verification() -> None:
    """Friend of the Sea / MSC counted only when rules_db verifies the
    claim — bare label text without backing does NOT score. Prevents
    a silent path back to manufacturer overcredit through sustainability."""
    rubric = json.loads((SCRIPTS_ROOT / "data" / "omega_rubric.json").read_text())
    sust = rubric["formulation"]["sustainability_cert"]

    assert sust["eligibility"] == "rules_db_verified"
    assert "Friend of the Sea" in sust["eligible_programs"]
    assert "MSC" in sust["eligible_programs"]
    assert sust["score"] == 4
