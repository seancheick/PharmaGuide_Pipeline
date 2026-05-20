"""v4 Probiotic module — P2.0 scaffold tests.

Locks the breakdown contract for the probiotic module before any
probiotic-specific scoring math lands. Subsequent slices (P2.1
Formulation, P2.2 Dose, P2.3 Evidence, P2.4 Trust, P2.5 Transparency,
P2.6 Manufacturer + final assembly) fill the `components` / `penalties`
sub-dicts and the dimension `score` fields in-place.

Per `docs/plans/SCORING_V4_PROPOSAL.md` §4 + §6 (probiotic rubric):

    | Dimension          | Probiotic |
    |--------------------|----------:|
    | Formulation        |    25     |
    | Dose               |    25     |
    | Evidence           |    20     |
    | Testing & Trust    |    15     |
    | Transparency       |    15     |
    | (5-dimension sum)  |   100     |

Plus two SEPARATE adjustments (§6 line 390):

    | Manufacturer Trust         | +5  |
    | Manufacturer Violations    |  0 to -25 |

Shared contract with generic module — same `dimensions` / `components` /
`penalties` / `metadata` / `manufacturer_trust` / `manufacturer_violations`
shape. Different dimension caps and different per-dimension sub-rubrics
(probiotic Formulation is CFU/strain-centric, not bio_score-centric).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


EXPECTED_DIMENSION_CAPS = {
    "formulation": 25,
    "dose": 25,
    "evidence": 20,
    "trust": 15,
    "transparency": 15,
}


COMPLETE_PROBIOTIC_PRODUCT = {
    "status": "active",
    "form_factor": "capsule",
    "supplement_type": {"type": "probiotic"},
    "ingredient_quality_data": {
        "total_active": 1,
        "ingredients_scorable": [
            {
                "name": "Lactobacillus rhamnosus HN001",
                "canonical_id": "lactobacillus_rhamnosus",
                "standard_name": "Lactobacillus rhamnosus",
                "mapped": True,
                "has_dose": True,
            }
        ],
    },
    "probiotic_data": {
        "is_probiotic_product": True,
        "total_billion_count": 20.0,
        "total_strain_count": 1,
        "clinical_strain_count": 1,
        "has_cfu": True,
        "has_survivability_coating": False,
        "prebiotic_present": False,
        "probiotic_blends": [
            {"name": "Lactobacillus rhamnosus HN001",
             "strains": ["Lactobacillus rhamnosus HN001"],
             "cfu_data": {"has_cfu": False, "billion_count": 0}}
        ],
        "clinical_strains": [
            {"name": "Lactobacillus rhamnosus HN001",
             "adequacy_tier": None, "clinical_support_level": "high",
             "cfu_per_day": None}
        ],
    },
}


# --- Direct module contract ----------------------------------------------


def test_score_probiotic_returns_module_result_with_five_dimensions() -> None:
    from scoring_v4.modules.probiotic import score_probiotic

    result = score_probiotic(COMPLETE_PROBIOTIC_PRODUCT)

    breakdown = result.to_breakdown()
    assert breakdown["module"] == "probiotic"
    assert set(breakdown["dimensions"].keys()) == set(EXPECTED_DIMENSION_CAPS.keys())


def test_probiotic_dimension_caps_match_proposal_section_4() -> None:
    from scoring_v4.modules.probiotic import score_probiotic

    breakdown = score_probiotic(COMPLETE_PROBIOTIC_PRODUCT).to_breakdown()

    for name, expected_cap in EXPECTED_DIMENSION_CAPS.items():
        assert breakdown["dimensions"][name]["max"] == expected_cap, (
            f"dimension cap drift: {name}.max != {expected_cap}"
        )


def test_probiotic_dimensions_share_skeleton_contract() -> None:
    """At P2.0, all dimensions are skeleton (score=None, empty components/penalties).
    Subsequent P2.1+ slices populate them. The shape itself is the contract."""
    from scoring_v4.modules.probiotic import score_probiotic

    breakdown = score_probiotic(COMPLETE_PROBIOTIC_PRODUCT).to_breakdown()

    for name in EXPECTED_DIMENSION_CAPS:
        dim = breakdown["dimensions"][name]
        assert "score" in dim
        assert "max" in dim
        assert "components" in dim
        assert "penalties" in dim
        assert "metadata" in dim
        assert dim["score"] is None, f"{name}.score must be None at P2.0"
        assert dim["components"] == {}, f"{name}.components must start empty"
        assert dim["penalties"] == {}, f"{name}.penalties must start empty"


def test_probiotic_manufacturer_trust_dimension_has_cap_5() -> None:
    from scoring_v4.modules.probiotic import score_probiotic

    breakdown = score_probiotic(COMPLETE_PROBIOTIC_PRODUCT).to_breakdown()
    mt = breakdown["manufacturer_trust"]
    assert mt["score"] is None
    assert mt["max"] == 5
    assert mt["components"] == {}


def test_probiotic_manufacturer_violations_floor_minus_25() -> None:
    from scoring_v4.modules.probiotic import score_probiotic

    breakdown = score_probiotic(COMPLETE_PROBIOTIC_PRODUCT).to_breakdown()
    mv = breakdown["manufacturer_violations"]
    assert mv["score"] is None
    assert mv["floor"] == -25


def test_probiotic_score_100_is_none_at_p20() -> None:
    """No score math runs at P2.0 — both raw_score_100 and score_100 None
    until P2.6 final assembly."""
    from scoring_v4.modules.probiotic import score_probiotic

    breakdown = score_probiotic(COMPLETE_PROBIOTIC_PRODUCT).to_breakdown()
    assert breakdown["score_100"] is None
    assert breakdown.get("raw_score_100") is None


def test_probiotic_phase_marker_p20_scaffold() -> None:
    from scoring_v4.modules.probiotic import score_probiotic

    breakdown = score_probiotic(COMPLETE_PROBIOTIC_PRODUCT).to_breakdown()
    assert breakdown["phase"] == "P2.0_probiotic_scaffold"


def test_score_probiotic_resilient_to_malformed_input() -> None:
    """Never raise. Must safely emit a skeleton even on malformed/empty input."""
    from scoring_v4.modules.probiotic import score_probiotic

    for bad in (None, {}, {"supplement_type": None}, 42, "oops"):
        result = score_probiotic(bad)  # type: ignore[arg-type]
        breakdown = result.to_breakdown()
        assert breakdown["module"] == "probiotic"
        assert set(breakdown["dimensions"].keys()) == set(EXPECTED_DIMENSION_CAPS.keys())
        assert breakdown["score_100"] is None


def test_score_probiotic_does_not_mutate_input() -> None:
    from scoring_v4.modules.probiotic import score_probiotic

    product = {**COMPLETE_PROBIOTIC_PRODUCT}
    before = dict(product)
    score_probiotic(product)
    assert product == before


# --- Shadow integration ---------------------------------------------------


def test_shadow_wires_probiotic_module_when_route_is_probiotic() -> None:
    """After Layer 1 + Layer 2 pass for a probiotic-routed product, the
    shadow scorer must call score_probiotic and stash its breakdown under
    `shadow_score_v4_breakdown["module"]`."""
    from score_supplements_v4_shadow import score_product_v4_shadow

    out = score_product_v4_shadow(COMPLETE_PROBIOTIC_PRODUCT)

    assert out["shadow_score_v4_module"] == "probiotic"
    assert "module" in out["shadow_score_v4_breakdown"]
    module_block = out["shadow_score_v4_breakdown"]["module"]
    assert module_block["module"] == "probiotic"
    assert set(module_block["dimensions"].keys()) == set(EXPECTED_DIMENSION_CAPS.keys())
    # P2.0: scaffold only — score_100 None, confidence either skeleton or
    # whatever the existing pipeline routed in.
    assert module_block["score_100"] is None


def test_shadow_does_not_wire_probiotic_module_when_safety_short_circuits() -> None:
    """BLOCKED/UNSAFE finality precedes module scoring entirely."""
    from score_supplements_v4_shadow import score_product_v4_shadow

    product = {
        **COMPLETE_PROBIOTIC_PRODUCT,
        "contaminant_data": {
            "banned_substances": {
                "substances": [
                    {"name": "Vinpocetine", "status": "banned", "match_type": "exact"}
                ]
            }
        },
    }
    out = score_product_v4_shadow(product)

    assert out["shadow_score_v4_verdict"] == "BLOCKED"
    assert "module" not in out["shadow_score_v4_breakdown"]


def test_shadow_does_not_wire_probiotic_module_when_completeness_fails() -> None:
    from score_supplements_v4_shadow import score_product_v4_shadow

    incomplete = {
        "supplement_type": {"type": "probiotic"},
        "ingredient_quality_data": {
            "total_active": 0,
            "ingredients_scorable": [],
        },
    }
    out = score_product_v4_shadow(incomplete)

    assert out["shadow_score_v4_verdict"] == "NOT_SCORED"
    assert "module" not in out["shadow_score_v4_breakdown"]


def test_shadow_does_not_route_generic_product_to_probiotic_module() -> None:
    """A single-nutrient product still routes to generic. P2.0 must not
    leak probiotic-module breakdown onto generic-routed rows."""
    from score_supplements_v4_shadow import score_product_v4_shadow

    generic = {
        "status": "active", "form_factor": "capsule",
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


def test_probiotic_module_does_not_import_v3_scorer() -> None:
    """v4 scoring policy is independent (§13 architecture lock)."""
    import scoring_v4.modules.probiotic as pm

    source = Path(pm.__file__).read_text()
    assert "from score_supplements" not in source
    assert "import score_supplements" not in source


def test_probiotic_module_importable_via_modules_package() -> None:
    import scoring_v4.modules as modules
    import scoring_v4.modules.probiotic  # noqa: F401

    assert "probiotic" in modules.__all__
