"""v4 Generic module — P1.3.0 scaffold tests.

Locks the breakdown contract for the generic module before any scoring
math lands. Subsequent slices (P1.3.1 Formulation, P1.3.2 Dose, P1.3.3
Evidence, P1.3.4 Trust, P1.3.5 Transparency, P1.3.6 Manufacturer + final
assembly) fill the `components` / `penalties` sub-dicts and the dimension
`score` fields in-place. The dimension keys, caps, and nesting shape are
the public contract — changing them is a breaking change to the audit /
score-delta / Flutter consumers.

Per `docs/plans/SCORING_V4_PROPOSAL.md` §4 (dimension weights):

    | Dimension          | Generic |
    |--------------------|---------|
    | Formulation        |   30    |
    | Dose               |   25    |
    | Evidence           |   20    |
    | Testing & Trust    |   15    |
    | Transparency       |   10    |
    | (5-dimension sum)  |  100    |

Plus two *separate* adjustments (§6 line 390):

    | Manufacturer Trust         | +5  |
    | Manufacturer Violations    |  0 to -25 |
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


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


EXPECTED_DIMENSION_CAPS = {
    "formulation": 30,
    "dose": 25,
    "evidence": 20,
    "transparency": 10,
}


# --- Direct module contract ----------------------------------------------


def test_score_generic_returns_module_result_with_five_dimensions() -> None:
    from scoring_v4.modules.generic import score_generic

    result = score_generic(COMPLETE_GENERIC_PRODUCT)

    breakdown = result.to_breakdown()
    assert breakdown["module"] == "generic"
    assert set(breakdown["dimensions"].keys()) == set(EXPECTED_DIMENSION_CAPS.keys())


def test_dimension_caps_match_proposal_section_4() -> None:
    from scoring_v4.modules.generic import score_generic

    breakdown = score_generic(COMPLETE_GENERIC_PRODUCT).to_breakdown()

    for name, expected_cap in EXPECTED_DIMENSION_CAPS.items():
        assert breakdown["dimensions"][name]["max"] == expected_cap, (
            f"dimension cap drift: {name}.max != {expected_cap}"
        )


def test_dimension_skeleton_has_components_and_penalties_subdicts() -> None:
    """Subsequent slices fill these in-place. The shape is the contract:
    every dimension always has score / max / components / penalties keys.

    Updated for P1.3.5: formulation, dose, evidence, trust, and
    transparency are populated."""
    from scoring_v4.modules.generic import score_generic

    breakdown = score_generic(COMPLETE_GENERIC_PRODUCT).to_breakdown()

    # All dimensions have the contract keys regardless of phase.
    for name in EXPECTED_DIMENSION_CAPS:
        dim = breakdown["dimensions"][name]
        assert "score" in dim
        assert "max" in dim
        assert "components" in dim
        assert "penalties" in dim

    # Formulation is complete at P1.3.1b.
    formulation = breakdown["dimensions"]["formulation"]
    assert formulation["score"] is not None
    assert formulation["components"]  # non-empty
    assert "A1_bio_score" in formulation["components"]

    # Dose is the RDA/UL proxy at P1.3.2a. The metadata is the contract
    # that signals the proxy state to downstream tooling.
    dose = breakdown["dimensions"]["dose"]
    assert dose["score"] is None
    assert "supplemental_window_proxy" in dose["components"]
    assert dose["metadata"]["method"] == "rda_ul_proxy_until_dietary_intake_table"
    assert dose["metadata"]["window_proxy_status"] == "not_evaluable_by_rda_proxy"

    # Evidence is online at P1.3.3. This fixture has no evidence matches, so
    # the score is a real 0, not skeleton/unknown.
    evidence = breakdown["dimensions"]["evidence"]
    assert evidence["score"] == 0.0
    assert "clinical_evidence_pipeline" in evidence["components"]
    assert evidence["metadata"]["phase"] == "P1.3.3_evidence_pipeline"

    # Phase 4: trust is now the additive verification_bonus (0-8). Its 0-15
    # source score + B4 components are preserved in the bonus payload.
    verification = breakdown["verification_bonus"]
    assert verification["metadata"]["source_trust_score_0_15"] == 0.0
    assert "B4a_verified_certifications" in verification["components"]
    assert verification["metadata"]["trust_metadata"]["phase"] == "P1.3.4_testing_trust"

    transparency = breakdown["dimensions"]["transparency"]
    assert transparency["score"] == 6.0
    assert "clear_disclosure_base" in transparency["components"]
    assert transparency["metadata"]["phase"] == "P1.3.5_transparency"


def test_manufacturer_trust_separate_dimension_with_cap_5() -> None:
    from scoring_v4.modules.generic import score_generic

    breakdown = score_generic(COMPLETE_GENERIC_PRODUCT).to_breakdown()

    mt = breakdown["manufacturer_trust"]
    assert mt["score"] == 0.0
    assert mt["max"] == 5
    assert mt["components"]["D2_disclosure_quality"] == 0.0
    assert mt["metadata"]["D1_source"] == "none"


def test_manufacturer_violations_separate_dimension_with_floor_minus_25() -> None:
    """Per §6 line 401: Manufacturer Violations is a SEPARATE dimension at
    the -25 scale, NOT inside the +15 testing/trust cap."""
    from scoring_v4.modules.generic import score_generic

    breakdown = score_generic(COMPLETE_GENERIC_PRODUCT).to_breakdown()

    mv = breakdown["manufacturer_violations"]
    assert mv["score"] == 0.0
    assert mv["floor"] == -25.0
    assert mv["components"]["manufacturer_violation_deduction"] == 0.0


def test_score_100_is_populated_with_raw_rubric_score() -> None:
    """Phase 9 keeps one score: score_100 is the raw rubric score."""
    from scoring_v4.modules.generic import score_generic

    breakdown = score_generic(COMPLETE_GENERIC_PRODUCT).to_breakdown()
    assert breakdown["score_100"] is not None
    assert breakdown["raw_score_100"] is not None
    assert 0.0 <= breakdown["score_100"] <= 100.0
    assert 0.0 <= breakdown["raw_score_100"] <= 100.0
    assert breakdown["metadata"]["phase"] == "P9_rubric_is_score"
    assert breakdown["metadata"]["score_policy"]["method"] == "rubric_raw_is_production_score"


def test_phase_marker_in_breakdown() -> None:
    """Phase marker tells audit/delta tooling whether to expect dimension
    scores. It now records the Phase 9 rubric-is-score slice."""
    from scoring_v4.modules.generic import score_generic

    breakdown = score_generic(COMPLETE_GENERIC_PRODUCT).to_breakdown()
    assert breakdown["phase"] == "P9_rubric_is_score"


def test_score_generic_resilient_to_missing_product() -> None:
    """Never raise. Direct generic-module calls still emit a bounded
    score even on malformed blobs; the real pipeline's completeness gate
    blocks those rows before module scoring."""
    from scoring_v4.modules.generic import score_generic

    for bad in (None, {}, {"supplement_type": None}, 42, "oops"):
        result = score_generic(bad)  # type: ignore[arg-type]
        breakdown = result.to_breakdown()
        assert breakdown["module"] == "generic"
        assert set(breakdown["dimensions"].keys()) == set(EXPECTED_DIMENSION_CAPS.keys())
        assert 0.0 <= breakdown["score_100"] <= 100.0


def test_score_generic_does_not_mutate_input() -> None:
    from scoring_v4.modules.generic import score_generic

    product = {**COMPLETE_GENERIC_PRODUCT}
    before = dict(product)
    score_generic(product)
    assert product == before


# --- Shadow integration ---------------------------------------------------


def test_shadow_wires_generic_module_breakdown_when_both_gates_pass() -> None:
    """After Layer 1 + Layer 2 pass, the shadow scorer must call the
    generic module and stash its breakdown under
    `shadow_score_v4_breakdown["module"]`. Score is online at P1.3.6."""
    from score_supplements_v4_shadow import score_product_v4_shadow

    out = score_product_v4_shadow(COMPLETE_GENERIC_PRODUCT)

    assert out["shadow_score_v4_module"] == "generic"
    assert out["shadow_score_v4_100"] is not None
    assert "module" in out["shadow_score_v4_breakdown"]
    module_block = out["shadow_score_v4_breakdown"]["module"]
    assert module_block["module"] == "generic"
    assert set(module_block["dimensions"].keys()) == set(EXPECTED_DIMENSION_CAPS.keys())
    assert module_block["score_100"] == out["shadow_score_v4_100"]


def test_shadow_does_not_wire_module_when_safety_short_circuits() -> None:
    """BLOCKED/UNSAFE finality precedes module scoring entirely."""
    from score_supplements_v4_shadow import score_product_v4_shadow

    product = {
        **COMPLETE_GENERIC_PRODUCT,
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
    assert "module" not in out["shadow_score_v4_breakdown"], (
        "Layer 1 short-circuit must NOT run module scoring"
    )


def test_shadow_does_not_wire_module_when_completeness_fails() -> None:
    """NOT_SCORED rows skip module scoring entirely — they are archive only."""
    from score_supplements_v4_shadow import score_product_v4_shadow

    incomplete = {
        "supplement_type": {"type": "single_nutrient"},
        "ingredient_quality_data": {
            "total_active": 1,
            "ingredients_scorable": [
                {"name": "Mystery", "canonical_id": "", "mapped": False}
            ],
        },
    }

    out = score_product_v4_shadow(incomplete)

    assert out["shadow_score_v4_verdict"] == "NOT_SCORED"
    assert "module" not in out["shadow_score_v4_breakdown"]


def test_shadow_does_not_wire_generic_module_for_probiotic_route() -> None:
    """Probiotic products route to a different (P2) module; the generic
    module breakdown must not leak onto them."""
    from score_supplements_v4_shadow import score_product_v4_shadow

    probiotic = {
        "status": "active",
        "form_factor": "capsule",
        "supplement_taxonomy": {"primary_type": "probiotic"},
        "supplement_type": {"type": "probiotic"},
        "ingredient_quality_data": {
            "total_active": 1,
            "ingredients_scorable": [
                {
                    "name": "Lactobacillus rhamnosus HN001",
                    "canonical_id": "lactobacillus_rhamnosus",
                    "mapped": True,
                }
            ],
        },
        "probiotic_data": {
            "is_probiotic_product": True,
            "total_billion_count": 20.0,
            "total_strain_count": 1,
            "probiotic_blends": [
                {"strains": ["Lactobacillus rhamnosus HN001"]}
            ],
        },
    }

    out = score_product_v4_shadow(probiotic)

    assert out["shadow_score_v4_module"] == "probiotic"
    # At P1.3.0 the generic-module breakdown is not emitted for non-generic
    # routes. P2 will land probiotic's own module block.
    module_block = out["shadow_score_v4_breakdown"].get("module")
    assert module_block is None or module_block.get("module") != "generic"


def test_shadow_module_score_and_typed_confidence_are_online_at_p14() -> None:
    """P1.4 adds typed confidence after P1.3.6 score assembly."""
    from score_supplements_v4_shadow import score_product_v4_shadow

    out = score_product_v4_shadow(COMPLETE_GENERIC_PRODUCT)
    assert out["shadow_score_v4_100"] is not None
    assert out["shadow_score_v4_confidence"] in {"high", "moderate", "low"}
    assert out["shadow_score_v4_breakdown"]["confidence"]["band"] == out["shadow_score_v4_confidence"]


# --- Architecture lock ----------------------------------------------------


def test_generic_module_does_not_import_v3_scorer() -> None:
    """v4 scoring policy is independent (§13 architecture lock)."""
    import scoring_v4.modules.generic as gm

    source = Path(gm.__file__).read_text()
    assert "from score_supplements" not in source
    assert "import score_supplements" not in source


def test_modules_subpackage_importable() -> None:
    """`scoring_v4.modules` is the package where per-class modules live.
    Probiotic (P2) and multi_or_prenatal (P3) will be siblings of generic."""
    import scoring_v4.modules  # noqa: F401
    import scoring_v4.modules.generic  # noqa: F401
