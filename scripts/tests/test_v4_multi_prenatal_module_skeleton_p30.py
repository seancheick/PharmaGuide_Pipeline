"""v4 P3.0 — multi/prenatal module scaffold tests.

Locks the breakdown contract before P3 scoring math lands. The multi /
prenatal module is class-aware because broad micronutrient panels and
prenatal critical nutrients should not be judged with the generic
single-ingredient rubric.

Per `docs/plans/SCORING_V4_PROPOSAL.md` §4:

    | Dimension          | multi/prenatal |
    |--------------------|---------------:|
    | Formulation        |             25 |
    | Dose               |             30 |
    | Evidence           |             15 |
    | Testing & Trust    |             15 |
    | Transparency       |             15 |
    | (5-dimension sum)  |            100 |
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


EXPECTED_DIMENSION_CAPS = {
    "formulation": 25,
    "dose": 30,
    "evidence": 15,
    "trust": 15,
    "transparency": 15,
}


COMPLETE_MULTI_PRODUCT = {
    "status": "active",
    "form_factor": "tablet",
    "product_name": "Complete Multivitamin 2 per Day",
    "supplement_type": {"type": "multivitamin"},
    "primary_category": "multivitamin",
    "ingredient_quality_data": {
        "total_active": 8,
        "ingredients_scorable": [
            {
                "name": "Vitamin A",
                "canonical_id": "vitamin_a",
                "mapped": True,
                "quantity": 900,
                "unit": "mcg RAE",
            },
            {
                "name": "Vitamin C",
                "canonical_id": "vitamin_c",
                "mapped": True,
                "quantity": 90,
                "unit": "mg",
            },
            {
                "name": "Vitamin D",
                "canonical_id": "vitamin_d",
                "mapped": True,
                "quantity": 25,
                "unit": "mcg",
            },
            {
                "name": "Vitamin E",
                "canonical_id": "vitamin_e",
                "mapped": True,
                "quantity": 15,
                "unit": "mg",
            },
            {
                "name": "Folate",
                "canonical_id": "vitamin_b9_folate",
                "mapped": True,
                "quantity": 400,
                "unit": "mcg DFE",
            },
            {
                "name": "Vitamin B12",
                "canonical_id": "vitamin_b12_cobalamin",
                "mapped": True,
                "quantity": 50,
                "unit": "mcg",
            },
            {
                "name": "Zinc",
                "canonical_id": "zinc",
                "mapped": True,
                "quantity": 11,
                "unit": "mg",
            },
            {
                "name": "Iodine",
                "canonical_id": "iodine",
                "mapped": True,
                "quantity": 150,
                "unit": "mcg",
            },
        ],
    },
}


COMPLETE_PRENATAL_DHA_PRODUCT = {
    "status": "active",
    "form_factor": "softgel",
    "product_name": "Prenatal DHA 200 mg",
    "supplement_type": {"type": "targeted"},
    "ingredient_quality_data": {
        "total_active": 1,
        "ingredients_scorable": [
            {
                "name": "Docosahexaenoic Acid",
                "canonical_id": "dha",
                "mapped": True,
                "quantity": 200,
                "unit": "mg",
            },
        ],
    },
}


def test_score_multi_prenatal_returns_module_result_with_five_dimensions() -> None:
    from scoring_v4.modules.multi_prenatal import score_multi_prenatal

    breakdown = score_multi_prenatal(COMPLETE_MULTI_PRODUCT).to_breakdown()

    assert breakdown["module"] == "multi_or_prenatal"
    assert set(breakdown["dimensions"].keys()) == set(EXPECTED_DIMENSION_CAPS.keys())


def test_multi_prenatal_dimension_caps_match_spec() -> None:
    from scoring_v4.modules.multi_prenatal import score_multi_prenatal

    breakdown = score_multi_prenatal(COMPLETE_MULTI_PRODUCT).to_breakdown()
    for name, expected_cap in EXPECTED_DIMENSION_CAPS.items():
        assert breakdown["dimensions"][name]["max"] == expected_cap


def test_multi_prenatal_dimensions_share_stable_contract() -> None:
    from scoring_v4.modules.multi_prenatal import score_multi_prenatal

    breakdown = score_multi_prenatal(COMPLETE_MULTI_PRODUCT).to_breakdown()

    for name in EXPECTED_DIMENSION_CAPS:
        dim = breakdown["dimensions"][name]
        assert set(dim.keys()) == {"score", "max", "components", "penalties", "metadata"}

    # P3.2: formulation and dose are populated; the other three dimensions
    # remain scaffolded until their slices land.
    assert breakdown["dimensions"]["formulation"]["score"] is not None
    assert breakdown["dimensions"]["dose"]["score"] is not None
    for name in ("evidence", "trust", "transparency"):
        dim = breakdown["dimensions"][name]
        assert dim["score"] is None
        assert dim["components"] == {}
        assert dim["penalties"] == {}
        assert dim["metadata"] == {}


def test_multi_prenatal_manufacturer_adjustments_have_shared_contract() -> None:
    from scoring_v4.modules.multi_prenatal import score_multi_prenatal

    breakdown = score_multi_prenatal(COMPLETE_MULTI_PRODUCT).to_breakdown()

    assert breakdown["manufacturer_trust"]["score"] is None
    assert breakdown["manufacturer_trust"]["max"] == 5
    assert breakdown["manufacturer_trust"]["components"] == {}
    assert breakdown["manufacturer_violations"]["score"] is None
    assert breakdown["manufacturer_violations"]["floor"] == -25
    assert breakdown["manufacturer_violations"]["components"] == {}


def test_multi_prenatal_score_fields_stay_none_until_final_assembly() -> None:
    from scoring_v4.modules.multi_prenatal import score_multi_prenatal

    breakdown = score_multi_prenatal(COMPLETE_MULTI_PRODUCT).to_breakdown()

    assert breakdown["raw_score_100"] is None
    assert breakdown["score_100"] is None
    assert breakdown["phase"].startswith("P3.")
    assert breakdown["metadata"]["module_state"] == "dose_partial"


def test_score_multi_prenatal_resilient_to_malformed_input() -> None:
    from scoring_v4.modules.multi_prenatal import score_multi_prenatal

    for bad in (None, {}, {"supplement_type": None}, 42, "oops"):
        breakdown = score_multi_prenatal(bad).to_breakdown()  # type: ignore[arg-type]
        assert breakdown["module"] == "multi_or_prenatal"
        assert set(breakdown["dimensions"].keys()) == set(EXPECTED_DIMENSION_CAPS.keys())
        assert breakdown["score_100"] is None


def test_score_multi_prenatal_does_not_mutate_input() -> None:
    from scoring_v4.modules.multi_prenatal import score_multi_prenatal

    product = json.loads(json.dumps(COMPLETE_MULTI_PRODUCT))
    before = json.dumps(product, sort_keys=True)
    score_multi_prenatal(product)
    assert json.dumps(product, sort_keys=True) == before


def test_multi_prenatal_module_exported_from_modules_package() -> None:
    from scoring_v4 import modules

    assert "multi_prenatal" in modules.__all__


def test_shadow_scorer_wires_complete_multivitamin_to_p3_module() -> None:
    from score_supplements_v4_shadow import score_product_v4_shadow

    shadow = score_product_v4_shadow(COMPLETE_MULTI_PRODUCT)

    assert shadow["shadow_score_v4_module"] == "multi_or_prenatal"
    assert shadow["shadow_score_v4_100"] is None
    assert shadow["shadow_score_v4_verdict"] == "NOT_SCORED"
    assert shadow["shadow_score_v4_confidence"] == "skeleton"
    assert shadow["shadow_score_v4_breakdown"]["module"]["module"] == "multi_or_prenatal"
    assert shadow["shadow_score_v4_breakdown"]["module"]["phase"].startswith("P3.")


def test_shadow_scorer_wires_prenatal_dha_to_p3_not_omega() -> None:
    from score_supplements_v4_shadow import score_product_v4_shadow

    shadow = score_product_v4_shadow(COMPLETE_PRENATAL_DHA_PRODUCT)

    assert shadow["shadow_score_v4_module"] == "multi_or_prenatal"
    assert shadow["shadow_score_v4_breakdown"]["module"]["module"] == "multi_or_prenatal"


def test_shadow_scorer_completeness_failure_short_circuits_before_p3_module() -> None:
    from score_supplements_v4_shadow import score_product_v4_shadow

    incomplete = json.loads(json.dumps(COMPLETE_MULTI_PRODUCT))
    for ingredient in incomplete["ingredient_quality_data"]["ingredients_scorable"]:
        ingredient.pop("unit", None)

    shadow = score_product_v4_shadow(incomplete)

    assert shadow["shadow_score_v4_module"] == "multi_or_prenatal"
    assert shadow["shadow_score_v4_verdict"] == "NOT_SCORED"
    assert shadow["shadow_score_v4_confidence"] == "blocked_by_completeness_gate"
    assert "module" not in shadow["shadow_score_v4_breakdown"]


def test_shadow_scorer_safety_short_circuits_before_p3_module() -> None:
    from score_supplements_v4_shadow import score_product_v4_shadow

    unsafe = json.loads(json.dumps(COMPLETE_MULTI_PRODUCT))
    unsafe["contaminant_data"] = {
        "banned_substances": {
            "substances": [
                {
                    "name": "DMAA",
                    "status": "banned",
                    "match_type": "exact",
                }
            ]
        }
    }

    shadow = score_product_v4_shadow(unsafe)

    assert shadow["shadow_score_v4_verdict"] == "BLOCKED"
    assert shadow["shadow_score_v4_confidence"] == "blocked_by_safety_gate"
    assert "module" not in shadow["shadow_score_v4_breakdown"]
