"""Generic Dose owner regressions.

Nutritional contributions consume qualified RDA/AI assessments; ordinary-adult
magnesium uses the approved 84 mg contribution target. Unsupported clinical
amounts retain source facts and completed-neutral Dose. The product-level
safety ceiling remains separate from adequacy and applies once.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


from scoring_v4.modules.generic_helpers import unbenchmarked_dose_credit

# V4.1 Step 4: every disclosed amount without a benchmark earns the one shared
# unbenchmarked neutral (11.4 public points), here on the generic reference 22.
NEUTRAL = unbenchmarked_dose_credit()

def _ingredient(
    *,
    name: str = "Magnesium",
    standard_name: str | None = None,
    canonical_id: str = "magnesium",
    bio_score: float = 14,
    quantity: float = 200,
    unit: str = "mg",
    **extra,
) -> dict:
    row = {
        "name": name,
        "standard_name": standard_name or name,
        "canonical_id": canonical_id,
        "mapped": True,
        "bio_score": bio_score,
        "quantity": quantity,
        "unit": unit,
    }
    row.update(extra)
    return row


def _product(
    *,
    ingredients: list | None = None,
    adequacy_results: list | None = None,
    safety_flags: list | None = None,
    supp_type: str = "single_nutrient",
    **extra,
) -> dict:
    rows = ingredients if ingredients is not None else [_ingredient()]
    product = {
        "status": "active",
        "form_factor": "capsule",
        "supplement_type": {"type": supp_type},
        "ingredient_quality_data": {
            "total_active": len(rows),
            "ingredients_scorable": rows,
            "ingredients": rows,
        },
    }
    if adequacy_results is not None or safety_flags is not None:
        product["rda_ul_data"] = {
            "adequacy_results": adequacy_results or [],
            "safety_flags": safety_flags or [],
        }
    product.update(extra)
    return product


def _adequacy(
    *,
    nutrient: str = "Magnesium",
    canonical_id: str | None = None,
    pct_rda: float | None = 50.0,
    pct_ul: float | None = 57.0,
    rda_ai: float | None = None,
) -> dict:
    # Explicit fixture identities and source reference values, never a
    # name-to-clinical-reference fallback for an unknown ingredient.
    references = {"Magnesium": ("magnesium", 400.0), "Zinc": ("zinc", 11.0),
                  "Potassium": ("potassium", 3400.0)}
    identity, reference = references.get(nutrient, (None, None))
    row = {"nutrient": nutrient, "pct_rda": pct_rda, "pct_ul": pct_ul}
    if canonical_id is not None or identity is not None:
        row["canonical_id"] = canonical_id or identity
    if rda_ai is not None or reference is not None:
        row["rda_ai"] = rda_ai if rda_ai is not None else reference
    return row


def _sleep_product(
    *,
    canonical_id: str = "melatonin",
    name: str = "Melatonin",
    quantity: float = 0.5,
    unit: str = "mg",
    adequacy_results: list | None = None,
) -> dict:
    return _product(
        ingredients=[
            _ingredient(
                name=name,
                standard_name=name,
                canonical_id=canonical_id,
                bio_score=10,
                quantity=quantity,
                unit=unit,
            )
        ],
        adequacy_results=adequacy_results if adequacy_results is not None else [],
        supplement_taxonomy={"primary_type": "sleep_support"},
    )


def _joint_product(
    *,
    ingredients: list | None = None,
) -> dict:
    return _product(
        ingredients=ingredients
        if ingredients is not None
        else [
            _ingredient(
                name="Glucosamine Sulfate",
                standard_name="Glucosamine",
                canonical_id="glucosamine",
                bio_score=11,
                quantity=1500,
                unit="mg",
            ),
            _ingredient(
                name="Chondroitin Sulfate",
                standard_name="Chondroitin",
                canonical_id="chondroitin",
                bio_score=9,
                quantity=1200,
                unit="mg",
            ),
        ],
        adequacy_results=[],
        supplement_taxonomy={"primary_type": "joint_support"},
    )


# --- Proxy metadata guardrails -------------------------------------------


def test_dose_payload_carries_proxy_metadata() -> None:
    """The method identifies approved contribution policy, not a deferred proxy."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(_product(adequacy_results=[_adequacy()]))

    meta = payload["metadata"]
    assert meta["phase"] == "P1.3.2a_dose_proxy"
    assert meta["method"] == "source_qualified_contribution_and_completed_neutral"
    assert "deferred_data_dependency" not in meta


def test_dose_phase_marker() -> None:
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(_product(adequacy_results=[_adequacy()]))
    assert payload["phase"] == "P1.3.2a_dose_proxy"


def test_dose_dimension_cap_25() -> None:
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(_product())
    assert payload["max"] == 25.0


def test_sleep_melatonin_low_dose_keeps_completed_neutral() -> None:
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(_sleep_product(quantity=0.5))

    assert payload["components"]["sleep_support_dose"] == NEUTRAL
    assert payload["metadata"]["method"] == "sleep_support_clinical_dose_v1"
    assert payload["metadata"]["sleep_support_dose"]["band"] == "no_benchmark_neutral"


def test_sleep_melatonin_high_dose_does_not_create_an_unsupported_curve() -> None:
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(_sleep_product(quantity=10))

    assert payload["components"]["sleep_support_dose"] == NEUTRAL
    assert payload["metadata"]["sleep_support_dose"]["band"] == "no_benchmark_neutral"


def test_sleep_5htp_reference_amount_keeps_completed_neutral() -> None:
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(
        _sleep_product(
            canonical_id="5_htp",
            name="5-HTP",
            quantity=100,
            adequacy_results=[_adequacy(nutrient="5-HTP", pct_rda=66.7, pct_ul=None)],
        )
    )

    assert payload["components"]["sleep_support_dose"] == NEUTRAL
    assert payload["metadata"]["sleep_support_dose"]["band"] == "no_benchmark_neutral"


def test_joint_glucosamine_chondroitin_keeps_completed_neutral_and_exposure() -> None:
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(_joint_product())

    assert payload["components"]["joint_support_dose"] == NEUTRAL
    assert payload["metadata"]["method"] == "joint_support_clinical_dose_v1"
    assert payload["metadata"]["joint_support_dose"]["adequate_actives"] == []
    assert {item["active"]: item["daily_mg"] for item in
            payload["metadata"]["joint_support_dose"]["actives"]} == {
        "glucosamine": 1500.0, "chondroitin": 1200.0}
    assert payload["metadata"]["joint_support_dose"]["band"] == "no_benchmark_neutral"


def test_joint_glucosamine_gram_units_do_not_fall_through_to_rda_proxy() -> None:
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(
        _joint_product(
            ingredients=[
                _ingredient(
                    name="Glucosamine Sulfate 2KCl",
                    standard_name="Glucosamine",
                    canonical_id="glucosamine",
                    bio_score=11,
                    quantity=2.0,
                    unit="g",
                )
            ]
        )
    )

    assert payload["components"]["joint_support_dose"] == NEUTRAL
    assert payload["metadata"]["joint_support_dose"]["actives"][0]["daily_mg"] == 2000.0


def test_joint_hydrolyzed_type_ii_is_not_undenatured_uc_ii() -> None:
    from scoring_v4.modules.joint_support import _joint_active_id

    row = _ingredient(
        name="Hydrolyzed Type II Collagen",
        standard_name="Collagen",
        canonical_id="collagen",
        matched_form="hydrolyzed collagen peptides",
        raw_source_text="Hydrolyzed Type II Collagen",
        quantity=600,
    )

    assert _joint_active_id(row) is None


def test_joint_undenatured_uc_ii_remains_recognized() -> None:
    from scoring_v4.modules.joint_support import _joint_active_id

    row = _ingredient(
        name="UC-II Undenatured Type II Collagen",
        standard_name="Collagen",
        canonical_id="collagen",
        matched_form="undenatured type ii collagen",
        raw_source_text="UC-II Undenatured Type II Collagen",
        quantity=40,
    )

    assert _joint_active_id(row) == "uc_ii"


@pytest.mark.parametrize("label", ["UC II", "uc_ii", "UCII"])
def test_joint_undenatured_uc_ii_aliases_remain_recognized(label: str) -> None:
    from scoring_v4.modules.joint_support import _joint_active_id

    row = _ingredient(
        name=label,
        standard_name=label,
        canonical_id=label,
        matched_form=label,
        raw_source_text=label,
        quantity=40,
    )

    assert _joint_active_id(row) == "uc_ii"


def test_joint_active_routing_is_stable_across_python_hash_seeds() -> None:
    row = {
        "name": "Hydrolyzed Collagen Type II",
        "standard_name": "Collagen",
        "canonical_id": "collagen",
        "matched_form": "hydrolyzed collagen peptides",
        "raw_source_text": "Hydrolyzed Collagen Type II",
    }
    statement = (
        "import sys; "
        f"sys.path.insert(0, {str(SCRIPTS_ROOT)!r}); "
        "from scoring_v4.modules.joint_support import _joint_active_id; "
        f"print(_joint_active_id({row!r}))"
    )

    outputs = []
    for seed in range(8):
        result = subprocess.run(
            [sys.executable, "-c", statement],
            check=True,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONHASHSEED": str(seed)},
        )
        outputs.append(result.stdout.strip())

    assert outputs == ["None"] * 8


# --- Supplemental-window proxy: in-window cases --------------------------


def test_window_proxy_in_window_returns_22() -> None:
    """200 mg magnesium meets the approved 84 mg adult contribution target."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(_product(adequacy_results=[_adequacy(pct_rda=50.0, pct_ul=57.0)]))
    assert payload["components"]["supplemental_window_proxy"] == 22.0


def test_magnesium_100mg_exceeds_84mg_contribution_target() -> None:
    """25% of the explicit 400 mg reference gives 100 mg; 84 mg earns full."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(_product(adequacy_results=[_adequacy(pct_rda=25.0, pct_ul=10.0)]))
    assert payload["components"]["supplemental_window_proxy"] == 22.0


def test_window_proxy_over_rda_under_ul_full_credit() -> None:
    """Above RDA but below UL — still in the supplemental window."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(_product(adequacy_results=[_adequacy(pct_rda=120.0, pct_ul=80.0)]))
    assert payload["components"]["supplemental_window_proxy"] == 22.0


# --- Supplemental-window proxy: sub-clinical case ------------------------


def test_window_proxy_subclinical_proportional() -> None:
    """10% of the explicit 400 mg RDA is 40 mg: 22 × 40/84 points."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(_product(adequacy_results=[_adequacy(pct_rda=10.0, pct_ul=2.0)]))
    assert payload["components"]["supplemental_window_proxy"] == round(22 * 40 / 84, 4)


def test_potassium_single_supplement_is_not_scored_against_total_dietary_ai() -> None:
    """A normal 99 mg potassium supplement must not look nearly empty merely
    because food supplies most of the 2,600–3,400 mg dietary AI."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(_product(
        ingredients=[_ingredient(
            name="Potassium",
            standard_name="Potassium",
            canonical_id="potassium",
            bio_score=8,
            quantity=99,
            unit="mg",
        )],
        adequacy_results=[_adequacy(
            nutrient="Potassium",
            canonical_id="potassium",
            pct_rda=2.912,
            pct_ul=None,
        )],
    ))

    assert payload["components"]["supplemental_window_proxy"] == NEUTRAL
    assert payload["metadata"]["window_proxy_reason"] == "dietary_intake_dominant_reference_excluded"
    assert payload["metadata"]["partial_credit_reason"] == "individual_quantified_dose_no_rda_reference"


def test_window_proxy_zero_dose_no_credit() -> None:
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(_product(adequacy_results=[_adequacy(pct_rda=0.0, pct_ul=0.0)]))
    assert payload["components"]["supplemental_window_proxy"] == 0.0


# --- Supplemental-window proxy: above an upper limit ----------------------


@pytest.mark.parametrize("pct_rda,pct_ul", [(300.0, 120.0), (400.0, 180.0)])
def test_window_proxy_over_ul_keeps_adequacy_credit(pct_rda, pct_ul) -> None:
    """Dose V4.1 §2.4: adequacy is scored alone; the one product-level ceiling
    (scoring_v4.dose_safety) caps the public pillar, never this band."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(_product(adequacy_results=[_adequacy(pct_rda=pct_rda, pct_ul=pct_ul)]))
    assert payload["components"]["supplemental_window_proxy"] == 22.0


# --- Supplemental-window proxy: no data case -----------------------------


def test_window_proxy_no_rda_data_with_label_dose_gets_partial_credit() -> None:
    """Botanicals / herbal products without RDA reference data can still
    have real label dosing. They get conservative partial credit, with
    metadata marking that this is not NIH/NHANES window math."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(_product(adequacy_results=[]))
    assert payload["score"] == NEUTRAL
    assert payload["components"]["supplemental_window_proxy"] == NEUTRAL
    assert payload["metadata"]["window_proxy_reason"] == "no_rda_reference_data"
    assert payload["metadata"]["window_proxy_status"] == "partial_credit_without_rda_proxy"
    assert payload["metadata"]["partial_credit_reason"] == "individual_quantified_dose_no_rda_reference"


@pytest.mark.parametrize("declared_on_label", [False, True])
def test_enzyme_activity_evidence_gets_no_reference_partial_dose_credit(declared_on_label) -> None:
    """Enzyme products are dosed by activity units, not mg. When the scoring
    contract recovers a GALU/HUT/etc. activity row, generic dose should treat it
    as real quantified dose evidence instead of "not evaluable".
    """
    from scoring_v4.modules.generic_dose import score_dose

    product = _product(
        ingredients=[],
        activeIngredients=[_ingredient(
            name="Alpha-Galactosidase", canonical_id="digestive_enzymes",
            quantity=0, unit="NP", raw_source_path="ingredientRows[0]",
            cleaner_row_role="active_scorable", score_eligible_by_cleaner=True,
            score_exclusion_reason=None,
            notes="300 GALU" if declared_on_label else "Declared enzyme",
        )],
        adequacy_results=[],
        ingredient_quality_data={
            "ingredients_scorable": [],
            "ingredients_skipped": [
                _ingredient(
                    name="Alpha-Galactosidase",
                    standard_name="Digestive Enzymes",
                    canonical_id="digestive_enzymes",
                    quantity=0,
                    unit="NP",
                    notes="Alpha Galactosidase (Form: Aspergillus niger) Note: 300 GALU",
                    raw_source_path="ingredientRows[0]",
                    cleaner_row_role="active_scorable",
                    score_eligible_by_cleaner=True,
                    score_exclusion_reason=None,
                )
            ],
        },
    )

    payload = score_dose(product)

    if not declared_on_label:
        # Canonical IQD research notes cannot invent a serving activity.
        assert payload["score"] is None
        assert payload["components"]["supplemental_window_proxy"] == 0.0
        return
    assert payload["score"] == NEUTRAL
    assert payload["components"]["supplemental_window_proxy"] == NEUTRAL
    assert payload["metadata"]["partial_credit_reason"] == "enzyme_activity_quantified_dose_no_rda_reference"


def test_ksm66_style_botanical_no_rda_is_not_punished_as_zero_dose() -> None:
    """A recognized preparation keeps its identity and source facts without
    turning an isolated regimen into a universal continuous Dose curve."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(
        _product(
            ingredients=[
                _ingredient(
                    name="KSM-66 Ashwagandha",
                    standard_name="Ashwagandha",
                    canonical_id="ashwagandha",
                    bio_score=11,
                    quantity=600,
                    unit="mg",
                    raw_taxonomy={"category": "botanical", "ingredientGroup": "Ashwagandha"},
                )
            ],
            adequacy_results=[
                _adequacy(nutrient="Ashwagandha", pct_rda=None, pct_ul=None),
            ],
        )
    )
    assert payload["score"] == NEUTRAL
    assert payload["components"]["botanical_clinical_dose"] == NEUTRAL
    assert payload["metadata"]["method"] == "botanical_clinical_dose_v1"
    assert payload["metadata"]["botanical_dose_band"] == "disclosed_no_reference"


def test_window_proxy_no_rda_and_no_quantified_dose_stays_not_evaluable() -> None:
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(
        _product(
            ingredients=[_ingredient(quantity=0, unit="")],
            adequacy_results=[],
        )
    )

    assert payload["score"] is None
    assert payload["metadata"]["window_proxy_status"] == "not_evaluable_by_rda_proxy"


def test_window_proxy_partial_rda_data_skips_unscorable_rows() -> None:
    """Mixed product: one nutrient with pct_rda data, one without → only
    the dosed one contributes; reason metadata records the skip."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(
        _product(
            adequacy_results=[
                _adequacy(nutrient="Magnesium", pct_rda=50.0, pct_ul=57.0),
                _adequacy(nutrient="Turmeric", pct_rda=None, pct_ul=None),
            ]
        )
    )
    assert payload["components"]["supplemental_window_proxy"] == 22.0


def test_window_proxy_averages_across_nutrients() -> None:
    """Declared magnesium and zinc each keep one source-qualified vote."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(
        _product(
            ingredients=[_ingredient(), _ingredient(name="Zinc", canonical_id="zinc", quantity=1.1)],
            adequacy_results=[
                _adequacy(nutrient="Magnesium", pct_rda=50.0, pct_ul=57.0),
                _adequacy(nutrient="Zinc", pct_rda=10.0, pct_ul=2.0),
            ], product_name="Magnesium and Zinc",
        )
    )
    assert payload["components"]["supplemental_window_proxy"] == 13.75


# --- Form quality is not a Dose input -----------------------------------
#
# IQM forms[].bio_score is the one form-quality owner (matrix concept
# `ingredient_form_quality`, quality_score 1.7.0). Dose scores the amount
# against a reference; a count of premium forms is neither.


def test_premium_form_count_earns_no_dose_credit() -> None:
    """Mg glycinate + Mg malate (both bio_score >= 12, one nutrient family)
    score exactly like Mg glycinate alone. Complexity creates obligations,
    not bonuses."""
    from scoring_v4.modules.generic_dose import score_dose

    adequacy = [_adequacy(nutrient="Magnesium", pct_rda=10.0, pct_ul=11.0)]
    glycinate = _ingredient(name="Mg Glycinate", standard_name="Magnesium",
                            canonical_id="mg_glycinate", bio_score=14)
    malate = _ingredient(name="Mg Malate", standard_name="Magnesium",
                         canonical_id="mg_malate", bio_score=13)

    single = score_dose(_product(ingredients=[glycinate], adequacy_results=adequacy))
    premium_pair = score_dose(_product(ingredients=[glycinate, malate], adequacy_results=adequacy))

    assert premium_pair["score"] == single["score"]
    assert premium_pair["components"] == single["components"]
    assert "multi_form_bonus" not in premium_pair["components"]


# --- Dose safety is recorded, not subtracted ------------------------------


def test_module_records_the_dose_safety_ceiling_without_a_subtraction() -> None:
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(_product(safety_flags=[
        {"nutrient": "A", "pct_ul": 180, "ul_gate_eligible": True},
        {"nutrient": "B", "pct_ul": 120, "ul_gate_eligible": True},
    ]))
    assert payload["penalties"] == {}
    assert payload["metadata"]["B7_safety_evaluation"]["dose_ceiling"]["cap_public"] == 0.0
    assert score_dose(_product())["metadata"]["B7_safety_evaluation"]["dose_ceiling"] is None


# --- Dimension score assembly --------------------------------------------


def test_dimension_score_thorne_canary_22_of_25() -> None:
    """The raw 22-point component retains the approved 84 mg magnesium target."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(
        _product(
            adequacy_results=[_adequacy(nutrient="Magnesium", pct_rda=50.0, pct_ul=57.0)],
            ingredients=[_ingredient()],
        )
    )
    assert payload["score"] == 22.0
    assert payload["max"] == 25.0


def test_dimension_score_floors_at_zero() -> None:
    """When a real dose-safety flag exists, the dimension is evaluable
    and still floors at zero."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(
        _product(
            adequacy_results=[_adequacy(pct_rda=0.0, pct_ul=180.0)],
            safety_flags=[{"nutrient": "A", "pct_ul": 200}],
        )
    )
    assert payload["score"] >= 0.0


def test_dimension_score_handles_malformed_input() -> None:
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(None)  # type: ignore[arg-type]
    assert payload["score"] is None
    assert payload["max"] == 25.0
    assert "supplemental_window_proxy" in payload["components"]
    assert payload["penalties"] == {}


# --- Shadow integration --------------------------------------------------


def test_shadow_wires_dose_dimension() -> None:
    from score_supplements_v4 import score_product_v4

    out = score_product_v4(
        _product(
            adequacy_results=[_adequacy(nutrient="Magnesium", pct_rda=50.0, pct_ul=57.0)],
        )
    )
    dose_dim = out["v4_breakdown"]["module"]["dimensions"]["dose"]
    assert dose_dim["score"] == 22.0
    assert dose_dim["max"] == 25.0
    assert "supplemental_window_proxy" in dose_dim["components"]
    # The proxy metadata must propagate through to the module breakdown so
    # audit / Flutter tooling sees it.
    assert dose_dim["metadata"]["phase"] == "P1.3.2a_dose_proxy"
    assert dose_dim["metadata"]["method"] == "source_qualified_contribution_and_completed_neutral"


def test_shadow_top_level_score_populated_at_p136() -> None:
    """P1.3.6 final assembly populates top-level raw_score_v4_100."""
    from score_supplements_v4 import score_product_v4

    out = score_product_v4(_product())
    assert out["raw_score_v4_100"] is not None
    assert out["v4_confidence"] in {"high", "moderate", "low"}
    assert out["v4_breakdown"]["confidence"]["band"] == out["v4_confidence"]


# --- Architecture lock ---------------------------------------------------


def test_generic_dose_does_not_import_v3_scorer() -> None:
    import scoring_v4.modules.generic_dose as gd

    source = Path(gd.__file__).read_text()
    assert "from score_supplements" not in source
    assert "import score_supplements" not in source


# --- Primary active without a reference cannot borrow full window credit ---


def _mixed_product(primary_qty: float):
    rows = [
        _ingredient(name="Vitamin B6", canonical_id="vitamin_b6_pyridoxine", quantity=1.7, unit="mg"),
        _ingredient(name="Vitamin B12", canonical_id="vitamin_b12_cobalamin", quantity=2.4, unit="mcg"),
        _ingredient(name="Cognigrape", canonical_id="cognigrape", quantity=primary_qty, unit="mg", bio_score=None),
    ]
    return _product(
        ingredients=rows,
        adequacy_results=[
            {"canonical_id": "vitamin_b6_pyridoxine", "nutrient": "Vitamin B6", "pct_rda": 130.0, "pct_ul": 1.7},
            {"canonical_id": "vitamin_b12_cobalamin", "nutrient": "Vitamin B12", "pct_rda": 100.0, "pct_ul": None},
        ],
        supp_type="multi",
    )


def test_unassessed_mass_primary_caps_window_credit_at_partial() -> None:
    # 304628-style label: two in-window vitamins, a 250 mg botanical with no
    # reference. The vitamins' window average must not present a complete
    # product-dose assessment while the mass-primary active is unassessed.
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(_mixed_product(250.0))
    assert payload["components"]["supplemental_window_proxy"] == NEUTRAL
    assert payload["metadata"]["window_proxy_status"] == "partial_credit_primary_active_unassessed"
    assert payload["metadata"]["primary_active_unassessed"] == "cognigrape"
    assert payload["metadata"]["partial_credit_value"] == NEUTRAL


def test_declared_purpose_rows_are_averaged_equally_with_unbenchmarked_fallback() -> None:
    from scoring_v4.modules.generic_dose import score_dose

    product = _product(
        ingredients=[
            _ingredient(name="Vitamin C", canonical_id="vitamin_c", quantity=90, unit="mg", raw_source_path="ingredientRows[0]"),
            _ingredient(name="Lactoferrin", canonical_id="lactoferrin", quantity=500, unit="mg", raw_source_path="ingredientRows[1]", bio_score=None),
        ],
        adequacy_results=[
            {"canonical_id": "vitamin_c", "nutrient": "Vitamin C", "pct_rda": 100.0, "pct_ul": 4.5},
            {"canonical_id": "lactoferrin", "nutrient": "Lactoferrin", "pct_rda": None, "pct_ul": None},
        ],
        product_name="Vitamin C and Lactoferrin",
    )

    payload = score_dose(product)

    assert payload["components"]["supplemental_window_proxy"] == pytest.approx(
        (22.0 + NEUTRAL) / 2.0
    )
    assert payload["metadata"]["purpose_ingredient_count"] == 2
    assert payload["metadata"]["unbenchmarked_purpose_ingredients"] == ["lactoferrin"]


def test_incidental_unbenchmarked_row_does_not_enter_purpose_average() -> None:
    from scoring_v4.modules.generic_dose import score_dose

    product = _product(
        ingredients=[
            _ingredient(name="Vitamin C", canonical_id="vitamin_c", quantity=90, unit="mg", raw_source_path="ingredientRows[0]"),
            _ingredient(name="Lactoferrin", canonical_id="lactoferrin", quantity=1, unit="mg", raw_source_path="ingredientRows[1]", bio_score=None),
        ],
        adequacy_results=[
            {"canonical_id": "vitamin_c", "nutrient": "Vitamin C", "pct_rda": 100.0, "pct_ul": 4.5},
            {"canonical_id": "lactoferrin", "nutrient": "Lactoferrin", "pct_rda": None, "pct_ul": None},
        ],
        product_name="Vitamin C",
    )

    payload = score_dose(product)

    assert payload["components"]["supplemental_window_proxy"] == 22.0
    assert payload["metadata"]["purpose_ingredient_count"] == 1
    assert payload["metadata"]["unbenchmarked_purpose_ingredients"] == []


@pytest.mark.parametrize("adapter,primary", [
    ("botanical", _ingredient(
        name="KSM-66 Ashwagandha", standard_name="Ashwagandha",
        canonical_id="ashwagandha", quantity=600, unit="mg",
        raw_source_path="ingredientRows[0]", matched_form="KSM-66 root extract",
    )),
    ("collagen", _ingredient(
        name="Hydrolyzed Collagen Peptides", standard_name="Collagen",
        canonical_id="collagen", quantity=3000, unit="mg",
        raw_source_path="ingredientRows[0]", matched_form="hydrolyzed collagen peptides",
    )),
])
def test_specialized_adapter_does_not_bypass_equal_multi_purpose_average(adapter, primary) -> None:
    from scoring_v4.modules.generic_dose import score_dose

    vitamin = _ingredient(
        name="Vitamin C", canonical_id="vitamin_c", quantity=1, unit="mg",
        raw_source_path="ingredientRows[1]",
    )
    product = _product(
        ingredients=[primary, vitamin],
        adequacy_results=[
            {"canonical_id": "vitamin_c", "nutrient": "Vitamin C", "pct_rda": 1.1, "pct_ul": 0.05},
        ],
        product_name=f"{primary['name']} and Vitamin C",
    )

    payload = score_dose(product)

    assert payload["metadata"]["dose_participation_basis"] == "declared_purpose_equal_weight"
    assert payload["metadata"]["purpose_ingredient_count"] == 2
    assert payload["metadata"]["method"] == "source_qualified_contribution_and_completed_neutral"


def test_multi_purpose_average_keeps_collagen_identity_without_inventing_a_dose_curve() -> None:
    from scoring_v4.modules.generic_dose import score_dose

    def assessed(quantity: float) -> dict:
        collagen = _ingredient(
            name="Hydrolyzed Collagen Peptides", standard_name="Collagen",
            canonical_id="collagen", quantity=quantity, unit="mg",
            raw_source_path="ingredientRows[0]",
            matched_form="hydrolyzed collagen peptides",
        )
        vitamin = _ingredient(
            name="Vitamin C", canonical_id="vitamin_c", quantity=90, unit="mg",
            raw_source_path="ingredientRows[1]",
        )
        return score_dose(_product(
            ingredients=[collagen, vitamin],
            adequacy_results=[{
                "canonical_id": "vitamin_c", "nutrient": "Vitamin C",
                "pct_rda": 100.0, "pct_ul": 4.5,
            }],
            product_name="Hydrolyzed Collagen Peptides and Vitamin C",
        ))

    below = assessed(100.0)
    within = assessed(5000.0)

    for payload in (below, within):
        assessment = payload["metadata"]["specialized_purpose_assessments"][0]
        assert assessment["score"] == NEUTRAL
        assert assessment["band"] == "disclosed_no_reference"
        assert payload["components"]["supplemental_window_proxy"] == round((NEUTRAL + 22) / 2, 4)
        assert payload["metadata"]["purpose_ingredient_count"] == 2


@pytest.mark.parametrize(
    "primary_type,active_name,canonical,low_amount,high_amount,expected_low,expected_high,owner",
    [
        ("sleep_support", "Melatonin", "melatonin", 0.5, 20.0, 17.27, 17.27, "sleep_support"),
        ("joint_support", "Glucosamine", "glucosamine", 750.0, 1500.0, 17.27, 17.27, "joint_support"),
        ("immune_support", "Beta Glucan", "beta_glucan", 50.0, 200.0, 17.27, 17.27, "immune_support"),
    ],
)
def test_multi_purpose_average_keeps_each_category_completed_neutral_vote(
    primary_type, active_name, canonical, low_amount, high_amount,
    expected_low, expected_high, owner,
) -> None:
    from scoring_v4.modules.generic_dose import score_dose

    def assessed(quantity: float) -> dict:
        active = _ingredient(
            name=active_name, canonical_id=canonical, quantity=quantity, unit="mg",
            raw_source_path="ingredientRows[0]", bio_score=None,
        )
        vitamin = _ingredient(
            name="Vitamin C", canonical_id="vitamin_c", quantity=90, unit="mg",
            raw_source_path="ingredientRows[1]",
        )
        return score_dose(_product(
            ingredients=[active, vitamin],
            adequacy_results=[{
                "canonical_id": "vitamin_c", "nutrient": "Vitamin C",
                "pct_rda": 100.0, "pct_ul": 4.5,
            }],
            product_name=f"{active_name} and Vitamin C",
            supplement_taxonomy={"primary_type": primary_type},
        ))

    low = assessed(low_amount)
    high = assessed(high_amount)

    assert low["components"]["supplemental_window_proxy"] == expected_low
    assert high["components"]["supplemental_window_proxy"] == expected_high
    assert low["metadata"]["specialized_purpose_assessments"][0]["assessment_owner"] == owner
    assert low["metadata"]["unbenchmarked_purpose_ingredients"] == []


def test_lactoferrin_source_regimen_does_not_create_a_general_dose_minimum() -> None:
    from scoring_v4.modules.generic_dose import score_dose

    row = _ingredient(
        name="Lactoferrin", canonical_id="lactoferrin", quantity=100, unit="mg",
        raw_source_path="ingredientRows[0]", bio_score=None,
    )
    product = _product(
        ingredients=[row], adequacy_results=[], product_name="Lactoferrin",
        evidence_data={"clinical_matches": [{
            "id": "INGR_LACTOFERRIN",
            "matched_source_row_refs": ["ingredientRows[0]"],
        }]},
    )

    payload = score_dose(product)

    assert payload["components"]["supplemental_window_proxy"] == NEUTRAL
    assert payload["metadata"]["positive_clinical_benchmark_assessments"] == []
    import json
    data = json.loads((SCRIPTS_ROOT / "data/backed_clinical_studies.json").read_text())
    record = next(item for item in data["backed_clinical_studies"] if item["id"] == "INGR_LACTOFERRIN")
    assert record["min_clinical_dose"] == 200
    assert {source["pmid"] for source in record["references_structured"]} == {"35276902", "19639462"}
    assert record["reference_semantics"]["curve"] == "completed_no_benchmark_neutral"


def test_positive_benchmark_requires_label_purpose_applicability() -> None:
    from dose_assessment import positive_clinical_benchmark

    row = _ingredient(
        name="Lactoferrin", canonical_id="lactoferrin", quantity=200, unit="mg",
        raw_source_path="ingredientRows[0]", bio_score=None,
    )
    product = _product(
        ingredients=[row], adequacy_results=[], product_name="Night Formula",
        statements=[{"type": "Formula re: Contains", "notes": "Lactoferrin supports sleep."}],
        evidence_data={"clinical_matches": [{
            "id": "INGR_LACTOFERRIN",
            "matched_source_row_refs": ["ingredientRows[0]"],
        }]},
    )

    assert positive_clinical_benchmark(product, row) is None


@pytest.mark.parametrize("canonical,name,studied_mg", [
    ("l_leucine", "L-Leucine", 1742),
    ("tmg_betaine", "TMG Betaine", 2500),
    ("l_lysine", "L-Lysine", 1000),
    ("mct_oil", "MCT Oil", 12000),
    ("american_ginseng", "American Ginseng", 3000),
    ("phosphatidic_acid", "Phosphatidic Acid", 750),
    ("touchi_extract", "Touchi Extract", 900),
])
@pytest.mark.parametrize("amount_factor", [0.5, 1.0, 2.0])
def test_literature_regimen_amounts_do_not_create_dose_targets(
    canonical, name, studied_mg, amount_factor,
) -> None:
    """A verified intervention amount is not a reviewed effective minimum.

    The MCT primary source uses 12 g; source correction must not make 12 g
    full credit, or invent fractional efficacy below that discrete regimen.
    All seven records that supplied the old fallback are covered, including
    acute-only American ginseng and context-dependent TMG owner precedence.
    """
    from dose_assessment import positive_clinical_benchmark
    from scoring_v4.scored_artifact import build_scored_artifact

    row = _ingredient(
        name=name, canonical_id=canonical, quantity=studied_mg * amount_factor,
        unit="mg", raw_source_path="ingredientRows[0]", raw_source_text=name,
        dose_class="therapeutic_mass", cleaner_row_role="active_scorable",
        role_classification="active_scorable", scoreable_identity=True,
        mapped_identity=True, identity_disposition="clean",
        score_eligible_by_cleaner=True, source_section="active",
    )
    product = _product(
        ingredients=[row], activeIngredients=[row], adequacy_results=[],
        product_name=name, id=f"literature-regimen-{canonical}",
        evidence_data={"clinical_matches": []},
        servings_per_day_min=1, servings_per_day_max=1,
    )

    artifact = build_scored_artifact(product)

    assert positive_clinical_benchmark(product, row) is None
    assert artifact["quality_score_status"] == "scored"
    assert artifact["strict_scoring_contract"]["passed"] is True
    assert artifact["assessment_readiness"]["dose"]["readiness"] == "complete"
    dose = artifact["quality_pillars_v4"]["dose"]
    assert dose["score"] == 11.4
    receipt = dose["explanation"]["dose_receipt"]
    assert receipt["reconciles"] is True
    assert receipt["contributions"][0]["points"] == 11.4
    assert "clinical_reference" not in {
        item.get("reference_kind") for item in receipt["contributions"]
    }
    if canonical == "touchi_extract":
        assert receipt["aggregation"] == "single_profile_assessment"
        contribution_fact = next(fact for fact in dose["explanation"]["facts"]
                                 if fact["id"] == "dose_contributions")
        assert "completed neutral when none applies" in contribution_fact["detail"]
    assert "unfinished" not in dose["reason"].lower()


@pytest.mark.parametrize("canonical,values,basis", [
    ("l_leucine", [1742, 2747, 3000, 5000], "per_serving_threshold"),
    ("tmg_betaine", [4000, 2500], "daily_intake"),
    ("l_lysine", [1000, 3000], "daily_intake"),
    ("mct_oil", [12000], "daily_intake"),
    ("american_ginseng", [3000], "acute_challenge"),
    ("phosphatidic_acid", [750], "daily_intake"),
    ("touchi_extract", [900], "daily_intake"),
])
def test_retiring_literature_dose_targets_preserves_descriptive_source_exposure(
    canonical, values, basis,
) -> None:
    from evidence_resolver import _load_literature_evidence

    # Keep source-owned exposure facts and Evidence review provenance. Retiring
    # the numeric projection must neither erase the studies nor change their
    # acute/daily meaning, verification state, or native source amounts.
    record = _load_literature_evidence()[canonical]
    assert record["studied_dose_exposure"] == {
        "values": values, "unit": "mg", "basis": basis,
    }
    assert record["verification_result"] == "authoritative_pubmed_verified"
    assert record["verification_provenance"]["all_pmids_verified"] is True
    assert record["qualifying_human_studies"]
    semantics = record["reference_semantics"]
    assert semantics["reference_type"] == "no_benchmark"
    assert semantics["curve"] == "completed_no_benchmark_neutral"
    assert semantics["approval_status"].startswith("approved_existing_neutral_")


@pytest.mark.parametrize("canonical,operator", [
    ("touchi_extract", "ambiguous"),
    ("unrecognized_touchi_material", None),
])
def test_retired_literature_target_does_not_complete_capture_or_identity_gaps(canonical, operator):
    from scoring_v4.modules.botanical_profile import score_botanical_purpose_dose
    from scoring_v4.scored_artifact import build_scored_artifact

    row = _ingredient(
        name="Touchi Extract" if canonical == "touchi_extract" else "Unknown fermented material",
        canonical_id=canonical, quantity=900, unit="mg", raw_source_path="ingredientRows[0]",
        category="botanical", dose_class="therapeutic_mass", cleaner_row_role="active_scorable",
        role_classification="active_scorable", scoreable_identity=True, mapped_identity=True,
        identity_disposition="clean", score_eligible_by_cleaner=True, source_section="active",
    )
    if operator:
        row["quantity_operator"] = operator
    product = _product(
        ingredients=[row], activeIngredients=[row], adequacy_results=[],
        product_name=row["name"], servings_per_day_min=1, servings_per_day_max=1,
    )
    if operator:
        artifact = build_scored_artifact(product)
        assert artifact["quality_score_status"] == "not_scored"
        assert artifact["score_unavailable_reason"] == "blocked_by_completeness_gate"
        assert artifact["quality_pillars_v4"] is None
    else:
        assessment = score_botanical_purpose_dose(product, row)
        assert assessment["metadata"]["benchmark"] == "unresolved"
        assert assessment["score"] == 0.0


@pytest.mark.parametrize("record_id", ["INGR_D_MANNOSE", "INGR_L_CARNITINE"])
def test_null_or_mixed_trial_amount_is_not_a_dose_benchmark(record_id: str) -> None:
    from scoring_v4.modules.generic_dose import score_dose

    row = _ingredient(
        name="D-Mannose" if record_id == "INGR_D_MANNOSE" else "L-Carnitine",
        canonical_id="d_mannose" if record_id == "INGR_D_MANNOSE" else "l_carnitine",
        quantity=2000, unit="mg", raw_source_path="ingredientRows[0]", bio_score=None,
    )
    product = _product(
        ingredients=[row], adequacy_results=[], product_name=row["name"],
        evidence_data={"clinical_matches": [{"id": record_id, "matched_source_row_refs": ["ingredientRows[0]"]}]},
    )

    payload = score_dose(product)

    assert payload["components"]["supplemental_window_proxy"] == NEUTRAL
    assert payload["metadata"]["positive_clinical_benchmark_assessments"] == []


def test_carnipure_preserves_exact_preparation_source_without_a_general_dose_curve() -> None:
    from dose_assessment import positive_clinical_benchmark
    from scoring_v4.modules.generic_dose import score_dose
    import json

    row = _ingredient(
        name="Carnipure L-Carnitine Tartrate",
        standard_name="Carnipure L-Carnitine",
        canonical_id="l_carnitine",
        quantity=1000,
        unit="mg",
        raw_source_path="ingredientRows[0]",
    )
    assessment = positive_clinical_benchmark(
        _product(
            ingredients=[row],
            product_name="Carnipure L-Carnitine",
            evidence_data={"clinical_matches": [
                {"id": "BRAND_CARNIPURE", "matched_source_row_refs": ["ingredientRows[0]"]},
                {"id": "INGR_L_CARNITINE", "matched_source_row_refs": ["ingredientRows[0]"]},
            ]},
        ),
        row,
    )

    assert assessment is None
    assert score_dose(_product(ingredients=[row], product_name="Carnipure L-Carnitine"))["score"] == NEUTRAL
    data = json.loads((SCRIPTS_ROOT / "data/backed_clinical_studies.json").read_text())
    record = next(item for item in data["backed_clinical_studies"] if item["id"] == "BRAND_CARNIPURE")
    assert record["min_clinical_dose"] == 2000
    assert record["dose_unit"] == "mg"
    assert {source["pmid"] for source in record["references_structured"]} == {"11788381", "20045157"}
    assert record["reference_semantics"]["preparation"] == "Carnipure L-Carnitine"
    assert record["reference_semantics"]["curve"] == "completed_no_benchmark_neutral"


def test_acetyl_l_carnitine_does_not_borrow_the_carnipure_benchmark() -> None:
    from dose_assessment import positive_clinical_benchmark

    row = _ingredient(
        name="Acetyl-L-Carnitine",
        standard_name="Acetyl-L-Carnitine",
        canonical_id="acetyl_l_carnitine",
        quantity=1000,
        unit="mg",
        raw_source_path="ingredientRows[0]",
    )

    assert positive_clinical_benchmark(
        _product(ingredients=[row], product_name="Acetyl-L-Carnitine"), row,
    ) is None


@pytest.mark.parametrize("quantity", [200, 400])
def test_tesnor_retains_studied_arms_without_continuous_dose_credit(quantity: float) -> None:
    from dose_assessment import positive_clinical_benchmark
    from scoring_v4.modules.generic_dose import score_dose
    import json

    row = _ingredient(
        name="Tesnor",
        standard_name="Tesnor",
        canonical_id="tesnor",
        quantity=quantity,
        unit="mg",
        raw_source_path="ingredientRows[0]",
    )
    assessment = positive_clinical_benchmark(
        _product(ingredients=[row], product_name="Tesnor"), row,
    )

    assert assessment is None
    assert score_dose(_product(ingredients=[row], product_name="Tesnor"))["score"] == NEUTRAL
    data = json.loads((SCRIPTS_ROOT / "data/backed_clinical_studies.json").read_text())
    record = next(item for item in data["backed_clinical_studies"] if item["id"] == "BRAND_TESNOR")
    assert record["min_clinical_dose"] == 200 and record["dose_unit"] == "mg"
    assert {source["pmid"] for source in record["references_structured"]} == {"35129040", "35928723"}
    assert record["reference_semantics"]["preparation"] == "Tesnor"
    assert record["reference_semantics"]["curve"] == "completed_no_benchmark_neutral"
    assert "200or400mg" in record["reference_semantics"]["rationale"].replace(" ", "")


@pytest.mark.parametrize(
    "name,canonical_id",
    [("Sytrinol", "sytrinol"), ("Zinc Picolinate", "zinc")],
)
def test_mixed_or_unbenchmarked_preparations_do_not_create_positive_benchmarks(
    name: str, canonical_id: str,
) -> None:
    from dose_assessment import positive_clinical_benchmark

    row = _ingredient(
        name=name,
        standard_name=name,
        canonical_id=canonical_id,
        quantity=300,
        unit="mg",
        raw_source_path="ingredientRows[0]",
    )

    assert positive_clinical_benchmark(
        _product(ingredients=[row], product_name=name), row,
    ) is None


def test_trace_unassessed_active_does_not_cap_window_credit() -> None:
    # A 1 mg unreferenced co-active is not the mass-primary; the assessed
    # vitamins own the dose story and full window credit stands.
    from scoring_v4.modules.generic_dose import score_dose, CAP_SUPPLEMENTAL_WINDOW

    payload = score_dose(_mixed_product(1.0))
    assert payload["components"]["supplemental_window_proxy"] == CAP_SUPPLEMENTAL_WINDOW
    assert "primary_active_unassessed" not in payload["metadata"]


def test_opaque_blend_total_is_not_a_dose_primary() -> None:
    # Raw D3 / Daily C-Protect pattern: an in-window vitamin plus a heavier
    # greens/fruit blend header. The opaque total is not the product's primary
    # active for the dose story; only an identified label active can cap.
    from scoring_v4.modules.generic_dose import _mass_primary_without_reference

    product = _mixed_product(1.0)
    blend = {
        "evidence_type": "blend_anchor_mass", "scoreable": True, "scoreable_identity": True,
        "score_eligible_by_cleaner": True, "dose_class": "therapeutic_mass", "dose_value": 755.0,
        "dose_unit": "mg", "source": "active", "raw_source_path": "ingredientRows[9]",
        "evidence_scope": "blend_level", "linked_rows": ["ingredientRows[9]"], "confidence": "low",
        "reason": "identity_bearing_blend_header_mass", "name": "Superfood greens blend",
        "canonical_id": "superfood_greens_herbal_blends", "clean_identity_id": "superfood_greens_herbal_blends",
        "scoring_parent_id": "superfood_greens_herbal_blends", "evidence_canonical_id": "superfood_greens_herbal_blends",
        "canonical_source_db": "proprietary_blends", "evidence_origin": "compatibility_derived",
    }
    product["product_scoring_evidence"] = [blend]
    assert _mass_primary_without_reference(product) is None

    unmapped = _mixed_product(250.0)
    unmapped["ingredient_quality_data"]["ingredients_scorable"][2]["canonical_source_db"] = "unmapped"
    assert _mass_primary_without_reference(unmapped) is None
    assert _mass_primary_without_reference(_mixed_product(250.0)) == "cognigrape"


# --- Round 3 (Codex audit): only usable assessments count; ties are deterministic ---


def test_empty_assessment_row_does_not_restore_full_credit() -> None:
    # An adequacy row for the primary with neither reference percentage is not
    # an assessment; the cap must hold exactly as if the row were absent.
    from scoring_v4.modules.generic_dose import score_dose

    product = _mixed_product(250.0)
    product["rda_ul_data"]["adequacy_results"].append(
        {"canonical_id": "cognigrape", "nutrient": "Cognigrape", "pct_rda": None, "pct_ul": None}
    )
    payload = score_dose(product)
    assert payload["components"]["supplemental_window_proxy"] == NEUTRAL
    assert payload["metadata"]["primary_active_unassessed"] == "cognigrape"


def test_ul_only_assessment_row_is_not_a_usable_assessment() -> None:
    # The window proxy skips a row with pct_ul but no pct_rda (no band); the
    # guard must use the same usability rule as the proxy it protects.
    from scoring_v4.modules.generic_dose import score_dose

    product = _mixed_product(250.0)
    product["rda_ul_data"]["adequacy_results"].append(
        {"canonical_id": "cognigrape", "nutrient": "Cognigrape", "pct_rda": None, "pct_ul": 4.0}
    )
    payload = score_dose(product)
    assert payload["components"]["supplemental_window_proxy"] == NEUTRAL


def test_unknown_reference_percentage_cannot_turn_an_unbenchmarked_primary_into_an_assessment() -> None:
    from scoring_v4.modules.generic_dose import score_dose, CAP_SUPPLEMENTAL_WINDOW

    product = _mixed_product(250.0)
    product["rda_ul_data"]["adequacy_results"].append(
        {"canonical_id": "cognigrape", "nutrient": "Cognigrape", "pct_rda": 80.0, "pct_ul": None}
    )
    payload = score_dose(product)
    assert payload["components"]["supplemental_window_proxy"] == NEUTRAL
    assert payload["metadata"]["primary_active_unassessed"] == "cognigrape"


def _tied_product(unassessed_first: bool):
    rows = [
        _ingredient(name="Vitamin C", canonical_id="vitamin_c", quantity=250.0, unit="mg"),
        _ingredient(name="Cognigrape", canonical_id="cognigrape", quantity=250.0, unit="mg", bio_score=None),
    ]
    if unassessed_first:
        rows.reverse()
    return _product(
        ingredients=rows,
        adequacy_results=[
            {"canonical_id": "vitamin_c", "nutrient": "Vitamin C", "pct_rda": 278.0, "pct_ul": 12.5},
        ],
        supp_type="multi",
    )


def test_tied_mass_primaries_cap_regardless_of_label_order() -> None:
    from scoring_v4.modules.generic_dose import score_dose

    for unassessed_first in (False, True):
        payload = score_dose(_tied_product(unassessed_first))
        assert payload["components"]["supplemental_window_proxy"] == NEUTRAL, unassessed_first
        assert payload["metadata"]["primary_active_unassessed"] == "cognigrape"


def test_mass_primary_label_actives_returns_every_tied_row_in_stable_order() -> None:
    from scoring_input_contract import mass_primary_label_actives
    from scoring_v4.modules.generic_helpers import get_active_ingredients

    for unassessed_first in (False, True):
        product = _tied_product(unassessed_first)
        primaries = mass_primary_label_actives(product, get_active_ingredients(product))
        assert [row["canonical_id"] for row in primaries] == ["cognigrape", "vitamin_c"]


# --- Assessments are source-linked: constituents and projections of the primary ---


def test_nested_constituent_does_not_assess_its_parent() -> None:
    # Flaxseed Oil 1000 mg declares ALA 500 mg under it; ALA carries the
    # reference, flaxseed oil does not. A constituent is a different substance:
    # shared ancestry is not assessment applicability, so the parent stays
    # capped (Codex round-3 audit).
    from scoring_v4.modules.generic_dose import score_dose

    rows = [
        _ingredient(name="Flaxseed Oil", canonical_id="flaxseed", quantity=1000.0, unit="mg", bio_score=None,
                    raw_source_path="ingredientRows[0]"),
        _ingredient(name="Alpha-Linolenic Acid", canonical_id="alpha_linolenic_acid", quantity=500.0, unit="mg",
                    raw_source_path="ingredientRows[0].nestedRows[0]"),
    ]
    product = _product(
        ingredients=rows,
        adequacy_results=[
            {"canonical_id": "flaxseed", "nutrient": "Flaxseed Oil", "pct_rda": None, "pct_ul": None},
            {"canonical_id": "alpha_linolenic_acid", "nutrient": "Alpha-Linolenic Acid", "pct_rda": 31.25, "pct_ul": None},
        ],
    )
    payload = score_dose(product)
    assert payload["components"]["supplemental_window_proxy"] == NEUTRAL
    assert payload["metadata"]["primary_active_unassessed"] == "flaxseed"


def test_title_projection_of_an_assessed_row_is_not_a_second_primary() -> None:
    # "Natural Vitamin K2 45 mcg": the label row is assessed; the enricher's
    # title-embedded projection of the same row ties it at 45 mcg. One
    # physical source, one assessment.
    from scoring_v4.modules.generic_dose import score_dose, _band_credit

    rows = [
        _ingredient(name="Vitamin K", canonical_id="vitamin_k", quantity=45.0, unit="mcg",
                    raw_source_path="ingredientRows[0]"),
        _ingredient(name="Vitamin K2", canonical_id="vitamin_k2", quantity=45.0, unit="mcg", bio_score=None,
                    raw_source_path="ingredientRows[0]", scoring_input_kind="label_active_projection",
                    linked_rows=["ingredientRows[0]"]),
    ]
    product = _product(
        ingredients=rows,
        adequacy_results=[{"canonical_id": "vitamin_k", "nutrient": "Vitamin K1", "pct_rda": 37.5, "pct_ul": None}],
    )
    payload = score_dose(product)
    # The assessed row's own credit (vitamin K at 37.5% of the AI under 1.4.0), not a partial-credit cap.
    assert payload["components"]["supplemental_window_proxy"] == pytest.approx(_band_credit(37.5, None, "vitamin_k"), abs=1e-4)
    assert "primary_active_unassessed" not in payload["metadata"]


def test_parent_with_unassessed_constituents_is_still_capped() -> None:
    # Fish oil 500 mg with EPA/DHA rows that carry no reference, beside an
    # assessed 90 mg vitamin C: the primary's source has no benchmark anywhere.
    from scoring_v4.modules.generic_dose import score_dose

    rows = [
        _ingredient(name="Omega-3 Fatty Acids", canonical_id="fish_oil", quantity=500.0, unit="mg", bio_score=None,
                    raw_source_path="ingredientRows[3]"),
        _ingredient(name="Eicosapentaenoic Acid", canonical_id="epa", quantity=325.0, unit="mg", bio_score=None,
                    raw_source_path="ingredientRows[3].nestedRows[0]"),
        _ingredient(name="Vitamin C", canonical_id="vitamin_c", quantity=90.0, unit="mg", raw_source_path="ingredientRows[4]"),
    ]
    product = _product(
        ingredients=rows,
        adequacy_results=[
            {"canonical_id": "fish_oil", "nutrient": "Omega-3", "pct_rda": None, "pct_ul": None},
            {"canonical_id": "epa", "nutrient": "EPA", "pct_rda": None, "pct_ul": None},
            {"canonical_id": "vitamin_c", "nutrient": "Vitamin C", "pct_rda": 100.0, "pct_ul": None},
        ],
        supp_type="multi",
    )
    payload = score_dose(product)
    assert payload["components"]["supplemental_window_proxy"] == NEUTRAL
    assert payload["metadata"]["primary_active_unassessed"] == "fish_oil"


def test_nested_projection_under_an_assessed_parent_is_not_a_second_primary() -> None:
    # Real 25514 shape: the enricher cuts a "Vitamin K2" child under the
    # assessed "Vitamin K" label row at the same 45 mcg. The parent's
    # assessment is the assessment of the child's source.
    from scoring_v4.modules.generic_dose import score_dose, _band_credit

    rows = [
        _ingredient(name="Vitamin K", canonical_id="vitamin_k", quantity=45.0, unit="mcg",
                    raw_source_path="ingredientRows[0]"),
        _ingredient(name="Vitamin K2", canonical_id="vitamin_k2", quantity=45.0, unit="mcg", bio_score=None,
                    raw_source_path="ingredientRows[0].nestedRows[0]", scoring_input_kind="label_active_projection",
                    linked_rows=["ingredientRows[0].nestedRows[0]"], reason="single_active_title_embedded_mass"),
    ]
    product = _product(
        ingredients=rows,
        adequacy_results=[{"canonical_id": "vitamin_k", "nutrient": "Vitamin K1", "pct_rda": 37.5, "pct_ul": None}],
    )
    payload = score_dose(product)
    # The assessed row's own credit (vitamin K at 37.5% of the AI under 1.4.0), not a partial-credit cap.
    assert payload["components"]["supplemental_window_proxy"] == pytest.approx(_band_credit(37.5, None, "vitamin_k"), abs=1e-4)
    assert "primary_active_unassessed" not in payload["metadata"]


def test_nested_child_without_the_title_projection_marker_is_not_the_parent() -> None:
    # Same shape as above but a real nested child: an ordinary projection or
    # constituent nested under an assessed row does not inherit its assessment.
    from scoring_v4.modules.generic_dose import score_dose, _band_credit

    rows = [
        _ingredient(name="Vitamin K", canonical_id="vitamin_k", quantity=45.0, unit="mcg",
                    raw_source_path="ingredientRows[0]"),
        _ingredient(name="Oleic Acid", canonical_id="oleic_acid", quantity=45.0, unit="mcg", bio_score=None,
                    raw_source_path="ingredientRows[0].nestedRows[0]", scoring_input_kind="label_active_projection",
                    linked_rows=["ingredientRows[0].nestedRows[0]"], reason="identity_bearing_active_anchor_mass"),
    ]
    product = _product(
        ingredients=rows,
        adequacy_results=[{"canonical_id": "vitamin_k", "nutrient": "Vitamin K1", "pct_rda": 37.5, "pct_ul": None}],
    )
    payload = score_dose(product)
    # The unassessed primary caps the window at the no-reference credit; it never raises it.
    expected = min(NEUTRAL, _band_credit(37.5, None, "vitamin_k"))
    assert payload["components"]["supplemental_window_proxy"] == pytest.approx(expected, abs=1e-4)
    assert payload["metadata"]["primary_active_unassessed"] == "oleic_acid"


def test_sibling_constituent_row_does_not_assess_the_primary() -> None:
    # Some labels print ALA as a sibling of flaxseed oil, not under it. Shared
    # identity never creates lineage, so the parent stays unassessed.
    from scoring_v4.modules.generic_dose import score_dose

    rows = [
        _ingredient(name="Flaxseed Oil", canonical_id="flaxseed", quantity=1000.0, unit="mg", bio_score=None,
                    raw_source_path="ingredientRows[0]"),
        _ingredient(name="Alpha-Linolenic Acid", canonical_id="alpha_linolenic_acid", quantity=500.0, unit="mg",
                    raw_source_path="ingredientRows[1]"),
    ]
    product = _product(
        ingredients=rows,
        adequacy_results=[
            {"canonical_id": "flaxseed", "nutrient": "Flaxseed Oil", "pct_rda": None, "pct_ul": None},
            {"canonical_id": "alpha_linolenic_acid", "nutrient": "Alpha-Linolenic Acid", "pct_rda": 62.5, "pct_ul": None},
        ],
    )
    payload = score_dose(product)
    assert payload["components"]["supplemental_window_proxy"] == NEUTRAL
    assert payload["metadata"]["primary_active_unassessed"] == "flaxseed"


def test_assessed_constituent_nested_under_the_primary_does_not_assess_it() -> None:
    # Codex round-3 audit: vitamin C nested under Cognigrape in the label tree
    # must not transfer its assessment upward. Shared ancestry is not
    # assessment applicability; only the primary's own assessment counts.
    from scoring_v4.modules.generic_dose import score_dose

    rows = [
        _ingredient(name="Cognigrape", canonical_id="cognigrape", quantity=250.0, unit="mg", bio_score=None,
                    raw_source_path="ingredientRows[0]"),
        _ingredient(name="Vitamin C", canonical_id="vitamin_c", quantity=90.0, unit="mg",
                    raw_source_path="ingredientRows[0].nestedRows[0]"),
    ]
    product = _product(
        ingredients=rows,
        adequacy_results=[{"canonical_id": "vitamin_c", "nutrient": "Vitamin C", "pct_rda": 100.0, "pct_ul": 4.5}],
        supp_type="multi",
    )
    payload = score_dose(product)
    assert payload["components"]["supplemental_window_proxy"] == NEUTRAL
    assert payload["metadata"]["primary_active_unassessed"] == "cognigrape"


# --- 1.4.0 reference-aware adequacy --------------------------------------


def _row(canonical_id: str, pct_rda: float, pct_ul=None) -> dict:
    return {"nutrient": canonical_id, "canonical_id": canonical_id, "pct_rda": pct_rda, "pct_ul": pct_ul}


@pytest.mark.parametrize(
    ("pct_rda", "expected"),
    [(10.0, 5.5), (20.0, 11.0), (25.0, 11.6875), (60.0, 16.5), (100.0, 22.0), (250.0, 22.0)],
)
def test_dri_nutrient_credit_grows_from_fda_high_source_to_full_requirement(pct_rda, expected) -> None:
    """DRI vitamins: 20% of the RDA (FDA 'high source') earns half, 100% earns full."""
    from scoring_v4.modules.generic_dose import _band_credit

    assert _band_credit(pct_rda, 10.0, "vitamin_d") == pytest.approx(expected)


@pytest.mark.parametrize("canonical", ["calcium", "magnesium", "l_glutamine", "nac", "unmapped_compound", None])
def test_unqualified_reference_does_not_get_a_quarter_rda_fallback(canonical) -> None:
    from scoring_v4.modules.generic_dose import _band_credit

    assert _band_credit(25.0, 10.0, canonical) is None
    assert _band_credit(10.0, 5.0, canonical) is None


def test_over_ul_amounts_keep_qualified_adequacy_credit_without_a_second_reduction() -> None:
    from scoring_v4.modules.generic_dose import _band_credit

    for canonical, row in (("vitamin_d", None), ("magnesium", {"rda_ai": 400}),
                           ("calcium", {"rda_ai": 1000})):
        assert _band_credit(300.0, 120.0, canonical, row) == 22.0
        assert _band_credit(400.0, 180.0, canonical, row) == 22.0
    # An unsupported clinical percentage supplies no adequacy reference even
    # when it carries an upper-limit percentage.
    assert _band_credit(300.0, 120.0, "quercetin") is None


def test_higher_dose_up_to_the_qualified_reference_never_scores_lower() -> None:
    from scoring_v4.modules.generic_dose import _band_credit

    for canonical, row in (("zinc", None), ("phosphorus", None),
                           ("magnesium", {"rda_ai": 400}), ("calcium", {"rda_ai": 1000})):
        credits = [_band_credit(float(pct), 10.0, canonical, row) for pct in range(0, 101, 5)]
        assert credits == sorted(credits)


def test_dri_map_points_at_official_dri_reference_entries() -> None:
    """Every mapped reference id exists and none is a no-DRI clinical anchor."""
    import json
    from pathlib import Path
    from scoring_v4.modules import generic_dose

    data = json.loads((Path(generic_dose.__file__).resolve().parents[2] / "data" / "rda_optimal_uls.json").read_text())
    by_id = {entry["id"]: entry for entry in data["nutrient_recommendations"]}
    for ref in set(generic_dose._DRI_REFERENCE_BY_CANONICAL.values()):
        assert ref in by_id, ref
        assert "no official dri" not in str(by_id[ref].get("notes") or "").lower(), ref


@pytest.mark.parametrize("pct_rda", [25.0, 50.0, 100.0, 140.0])
def test_verified_source_amount_does_not_create_a_general_quercetin_dose_curve(pct_rda) -> None:
    from scoring_v4.modules.generic_dose import _band_credit, score_dose

    assert _band_credit(pct_rda, None, "quercetin") is None
    payload = score_dose(_product(
        ingredients=[_ingredient(name="Quercetin", canonical_id="quercetin", quantity=500 * pct_rda / 100)],
        adequacy_results=[_adequacy(nutrient="Quercetin", canonical_id="quercetin", pct_rda=pct_rda, pct_ul=None)]))
    assert payload["score"] == NEUTRAL


def test_retired_clinical_anchor_map_preserves_reviewed_source_facts() -> None:
    import json
    from scoring_v4.modules import generic_dose
    from scoring_v4.quality_score_config import block

    root = Path(generic_dose.__file__).resolve().parents[3]
    ledger = json.loads((root / "scripts/audits/clinical_anchor_verification_2026_09_15/anchor_verification.json").read_text())
    data = json.loads((root / "scripts/data/rda_optimal_uls.json").read_text())
    by_id = {entry["id"]: entry for entry in data["nutrient_recommendations"]}
    # Source verification and historical intervention amounts remain evidence;
    # they no longer authorize continuous or quarter-reference Dose credit.
    for item in ledger["anchors"]:
        entry = by_id[item["id"]]
        assert entry["notes"].count("Anchor dose ") == 1, item["id"]
        if item["graduation_eligible"]:
            assert {e["pmid"] for e in item["evidence"]} & set(entry["references"]), item["id"]
            expected = item.get("anchor_proposed", item["anchor_current"])
            assert {row["rda_ai"] for row in entry["data"]} == {expected}, item["id"]
        assert entry["reference_semantics"]["curve"] == "completed_no_benchmark_neutral"
    assert not hasattr(generic_dose, "_CLINICAL_ANCHOR_REFERENCE_BY_CANONICAL")
    assert "_clinical_anchor_reference_by_canonical" not in block("dose_magnitudes", "generic")["generic"]


@pytest.mark.parametrize("count", [1, 2, 3, 4])
@pytest.mark.parametrize("with_benchmark", [False, True])
def test_approved_fallback_calibration_keeps_all_purpose_rows(count, with_benchmark):
    from scoring_v4.modules.generic_dose import score_dose
    unknowns = [("Lactoferrin", "lactoferrin"), ("D-Mannose", "d_mannose"),
                ("D-Aspartic Acid", "d_aspartic_acid"), ("CogniGrape", "cognigrape")]
    chosen = ([("Vitamin C", "vitamin_c")] if with_benchmark else [])
    chosen += unknowns[:count - len(chosen)]
    rows = [_ingredient(name=name, canonical_id=canonical, quantity=500, unit="mg",
                        bio_score=None, raw_source_path=f"ingredientRows[{index}]")
            for index, (name, canonical) in enumerate(chosen)]
    adequacy = [{"canonical_id": canonical, "nutrient": name,
                 "pct_rda": 100.0 if canonical == "vitamin_c" else None,
                 "pct_ul": 4.5 if canonical == "vitamin_c" else None}
                for name, canonical in chosen]
    p = _product(ingredients=rows, adequacy_results=adequacy,
                 product_name=" and ".join(name for name, _ in chosen))
    payload = score_dose(p)
    expected = ((22.0 if with_benchmark else NEUTRAL) + NEUTRAL * (count - 1)) / count
    assert NEUTRAL == 12.54
    assert payload["components"]["supplemental_window_proxy"] == pytest.approx(expected, abs=1e-4)
    assert payload["metadata"]["purpose_ingredient_count"] == count
    assert len(payload["metadata"]["unbenchmarked_purpose_ingredients"]) == count - int(with_benchmark)


@pytest.mark.parametrize("scope", ["lent", "structural", "header", "total_only"])
@pytest.mark.parametrize("owner,canonical,quantity", [
    ("joint_support", "chondroitin", 1200),
    ("sleep_support", "melatonin", 3),
    ("immune_support", "elderberry", 500),
])
def test_specialized_dose_requires_individual_exposure(owner, canonical, quantity, scope):
    from importlib import import_module
    from scoring_v4.modules.generic_helpers import has_usable_individual_dose

    row = _ingredient(name=canonical, canonical_id=canonical, quantity=quantity)
    product = _product(ingredients=[row], primary_type=owner)
    assess = getattr(import_module("scoring_v4.modules." + owner),
                     {"joint_support": "score_joint_purpose_dose",
                      "sleep_support": "score_sleep_purpose_dose",
                      "immune_support": "score_immune_purpose_dose"}[owner])
    assert assess(product, row) is not None
    projected = dict(row, evidence_type="blend_anchor_mass", evidence_scope="blend_level",
                     scoring_input_kind="product_level_evidence",
                     reason="identity_bearing_blend_header_mass_from_nested_child" if scope == "lent"
                     else "identity_bearing_blend_header_mass")
    if scope in {"header", "total_only"}:
        projected = dict(row, **{"is_blend_header" if scope == "header" else "blend_total_weight_only": True})
    assert not has_usable_individual_dose(projected)
    assert assess(product, projected) is None
    # An actual label-row projection keeps its own disclosed exposure.
    disclosed = dict(row, evidence_type="blend_anchor_mass", evidence_scope="row_level",
                     scoring_input_kind="label_active_projection")
    assert has_usable_individual_dose(disclosed)
    assert assess(product, disclosed) == assess(product, row)


@pytest.mark.parametrize("pid", ["12196", "176071", "204571"])
def test_raw_blend_total_never_becomes_an_individual_dose(pid):
    import json
    from copy import deepcopy
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact

    raw = json.loads((Path(__file__).parent / "fixtures" / f"dose_blend_{pid}_raw.json").read_text())
    clean = EnhancedDSLDNormalizer().normalize_product(deepcopy(raw))
    enriched, errors = SupplementEnricherV3().enrich_product(clean)
    assert not errors
    result = build_scored_artifact(enriched)
    dose = result["_v4_module_breakdown"]["dimensions"]["dose"]
    if pid == "12196":
        assert "chondroitin" not in [item["active"] for item in
                dose["metadata"].get("specialized_purpose_assessments", [])]
        assert any(item["active"] == "glucosamine" and item["daily_mg"] == 1500
                   for item in dose["metadata"]["specialized_purpose_assessments"])
    elif pid == "204571":
        assert dose["components"]["supplemental_window_proxy"] == NEUTRAL
        assert dose["metadata"]["partial_credit_value"] == NEUTRAL
        assert dose["metadata"]["unbenchmarked_purpose_ingredients"]
    else:
        # The raw notes disclose individual enzyme activity (DU/HUT/FCCPU);
        # reject container mass while preserving that distinct usable exposure.
        assert dose["metadata"]["partial_credit_reason"] == "enzyme_activity_quantified_dose_no_rda_reference"
        assert dose["score"] == NEUTRAL


def test_structural_blend_fallback_preserves_existing_product_credit():
    from scoring_v4.modules.generic_dose import (
        _score_no_reference_quantified_dose,
    )
    total = _ingredient(name="Digestive enzyme blend", canonical_id="enzyme_blend", quantity=500,
                        evidence_type="blend_anchor_mass", evidence_scope="blend_level",
                        scoring_input_kind="product_level_evidence", dose_class="therapeutic_mass",
                        dose_value=500, dose_unit="mg", scoreable=True)
    product = _product(ingredients=[total], product_scoring_evidence=[total])
    score, reason = _score_no_reference_quantified_dose(product)
    assert score == NEUTRAL
    assert reason == "blend_anchor_quantified_dose_no_rda_reference"


@pytest.mark.parametrize("lent,disclosed,expected", [(False, True, True), (True, True, False), (False, False, False)])
def test_declared_structural_purpose_keeps_product_total_fallback(lent, disclosed, expected):
    from scoring_v4.modules.generic_dose import (
        _score_declared_purpose_window,
    )
    total = _ingredient(name="Digestive enzyme blend", canonical_id="enzyme_blend", quantity=500,
                        evidence_type="blend_anchor_mass", evidence_scope="blend_level",
                        scoring_input_kind="product_level_evidence", dose_class="therapeutic_mass",
                        dose_value=500, dose_unit="mg", scoreable=True)
    product = _product(ingredients=[total], product_scoring_evidence=[total],
                       fullName="Digestive enzyme blend")
    if lent:
        total["reason"] = "identity_bearing_blend_header_mass_from_nested_child"
    if not disclosed:
        total["quantity"] = total["dose_value"] = None
    score, unknown, count, clinical, specialized, fallbacks, hidden, _entries = _score_declared_purpose_window(product)
    assert count == 1
    # Dose V4.1 section 2.3: a disclosed total without a benchmark and an
    # amount the label hides (lent to a nested child) both take the neutral,
    # recorded apart; a missing amount with no label nondisclosure keeps 0.
    assert score == (NEUTRAL if expected or lent else 0)
    assert unknown == (["enzyme_blend"] if expected else [])
    assert hidden == (["enzyme_blend"] if lent else [])
    assert not clinical and not specialized
    assert fallbacks == ([NEUTRAL] if expected or lent else [])


def test_mixed_preparation_and_individual_fallbacks_keep_each_purpose_vote():
    from scoring_v4.modules.generic_dose import score_dose
    total = _ingredient(name="Digestive enzyme blend", canonical_id="enzyme_blend", quantity=500,
                        evidence_type="blend_anchor_mass", evidence_scope="blend_level",
                        scoring_input_kind="product_level_evidence", dose_class="therapeutic_mass",
                        dose_value=500, dose_unit="mg", scoreable=True)
    active = _ingredient(name="Astragalus", canonical_id="astragalus", quantity=100)
    product = _product(ingredients=[total, active], product_scoring_evidence=[total],
                       fullName="Digestive enzyme blend with Astragalus")
    dose = score_dose(product)
    assert dose["metadata"]["purpose_ingredient_count"] == 2
    # A disclosed preparation total and an individual amount, both without a
    # benchmark, each keep one vote at the same shared neutral.
    assert dose["components"]["supplemental_window_proxy"] == NEUTRAL
    assert dose["metadata"]["unbenchmarked_purpose_ingredients"] == ["astragalus", "enzyme_blend"]
    assert dose["metadata"]["partial_credit_value"] == NEUTRAL


@pytest.mark.parametrize("canonical", ["phosphorus", "alpha_linolenic_acid"])
def test_approved_nutritional_replacements_remove_quarter_reference_shortcut(canonical):
    from scoring_v4.modules.generic_dose import _band_credit
    assert _band_credit(25.0, None, canonical) == pytest.approx(11.6875)
    assert _band_credit(100.0, None, canonical) == 22.0


@pytest.mark.parametrize("canonical", ["sodium", "chloride", "quercetin", "unmapped_compound"])
def test_reviewed_generic_reference_cannot_borrow_an_unsupported_numeric_anchor(canonical):
    from scoring_v4.modules.generic_dose import _band_credit
    assert _band_credit(25.0, None, canonical) is None
    assert _band_credit(1000.0, None, canonical) is None


@pytest.mark.parametrize("canonical", ["magnesium", "calcium"])
def test_ineligible_contribution_context_has_no_quarter_rda_fallback(canonical):
    from scoring_v4.modules.generic_dose import _band_credit
    assert _band_credit(25.0, None, canonical) is None
    assert _band_credit(25.0, None, canonical, {"rda_ai":400.0,"ul_population":{"members":["pediatric"]}}) == 22 * (.5 + .5 * 5 / 80)


@pytest.mark.parametrize(("pct","expected"), [(0,0),(10,.25),(20,.5),(50,.6875),(100,1),(150,1)])
def test_shared_nutritional_curve_is_one_source_owned_policy(pct,expected):
    from scoring_v4.modules.generic_dose import nutritional_unit_credit
    assert nutritional_unit_credit(pct) == pytest.approx(expected)


def test_completed_reference_review_has_no_interim_diet_table_dependency():
    from scoring_v4.modules.generic_dose import score_dose
    dose=score_dose(_product(adequacy_results=[]))
    assert 'deferred_data_dependency' not in dose['metadata']
    assert dose['metadata']['method']=='source_qualified_contribution_and_completed_neutral'


def _declared_companion_amount_product(companion):
    return _product(
        ingredients=[_ingredient(name='Vitamin C', canonical_id='vitamin_c', quantity=90), companion],
        product_name='Vitamin C + L-Tyrosine', primary_type='general_supplement',
        adequacy_results=[{'nutrient': 'Vitamin C', 'canonical_id': 'vitamin_c',
                           'amount': 90, 'unit': 'mg', 'rda_ai': 90, 'pct_rda': 100}])


@pytest.mark.parametrize('unit', ['NP', '', 'scoop'])
@pytest.mark.parametrize('quantity', [0,100])
def test_declared_quantity_with_unusable_unit_is_incomplete(unit, quantity):
    from scoring_v4.scored_artifact import build_scored_artifact
    companion = _ingredient(name='L-Tyrosine', canonical_id='l_tyrosine', quantity=quantity, unit=unit)
    artifact = build_scored_artifact(_declared_companion_amount_product(companion))
    assert artifact['quality_assessment_status'] == 'partial' or artifact['quality_score_status'] == 'not_scored'
    dose = artifact['_v4_module_breakdown']['dimensions']['dose']
    assert dose['score'] is None
    assert dose['metadata']['reason_code'] == 'unresolved_source_quantity'


@pytest.mark.parametrize('unit', ['mg', 'mcg', 'g'])
def test_declared_zero_is_absence_rather_than_lost_source_quantity(unit):
    from scoring_v4.scored_artifact import build_scored_artifact
    from scoring_v4.modules.generic_dose import _unread_declared_purpose_rows
    companion = _ingredient(name='L-Tyrosine', canonical_id='l_tyrosine', quantity=0, unit=unit)
    product = _declared_companion_amount_product(companion)
    assert _unread_declared_purpose_rows(product) == []
    artifact = build_scored_artifact(product)
    dose = artifact['_v4_module_breakdown']['dimensions']['dose']
    assert dose['metadata'].get('reason_code') != 'unresolved_source_quantity'


def test_shared_unread_guard_retains_legitimate_cfu_has_dose_owner():
    from scoring_v4.modules.generic_dose import _unread_declared_purpose_rows
    row = _ingredient(name='Lactobacillus rhamnosus', canonical_id='lactobacillus_rhamnosus',
                      quantity=None, unit='CFU', has_dose=True)
    product = _declared_companion_amount_product(row)
    product['product_name'] = 'Vitamin C + Lactobacillus rhamnosus'
    assert _unread_declared_purpose_rows(product) == []


def test_shared_unread_guard_retains_typed_product_evidence_owner():
    from scoring_v4.modules.generic_dose import _unread_declared_purpose_rows
    row = _ingredient(name='Digestive enzyme blend', canonical_id='enzyme_blend', quantity=None, unit='',
                      scoring_input_kind='product_level_evidence', evidence_type='blend_anchor_mass',
                      evidence_scope='blend_level', dose_class='therapeutic_mass',
                      dose_value=500, dose_unit='mg', scoreable=True)
    product = _declared_companion_amount_product(row)
    product['product_scoring_evidence'] = [row]
    product['product_name'] = 'Vitamin C + Digestive enzyme blend'
    assert _unread_declared_purpose_rows(product) == []


def _named_eaa_group_product(*, unavailable=0, hidden=False):
    from scoring_v4.modules.sports_helpers import EAA_CANONICALS

    rows = [_ingredient(name=key.replace('_', ' '), canonical_id=key,
                        quantity=(0 if hidden else None) if index < unavailable else 1000,
                        unit='NP' if hidden and index < unavailable else 'mg',
                        cleaner_row_role='nested_display_only' if hidden and index < unavailable else 'active_scorable',
                        raw_source_path=f'ingredientRows[{index}]')
            for index, key in enumerate(sorted(EAA_CANONICALS))]
    rows.extend([_ingredient(name='L-Theanine', canonical_id='l_theanine', quantity=100),
                 _ingredient(name='Creatine', canonical_id='creatine_monohydrate', quantity=3000)])
    return _product(ingredients=rows, supp_type='general_supplement',
                    product_name='L-Theanine + Creatine + EAA', fullName='L-Theanine + Creatine + EAA',
                    primary_type='general_supplement', supplement_taxonomy={'primary_type':'general_supplement'})


@pytest.mark.parametrize('unavailable', [1, 4, 9])
def test_named_eaa_group_keeps_lost_member_amounts_in_generic_and_public_dose(unavailable):
    from scoring_v4.modules.generic_dose import _score_declared_purpose_window, score_dose
    from scoring_v4.scored_artifact import build_scored_artifact

    product = _named_eaa_group_product(unavailable=unavailable)
    window = _score_declared_purpose_window(product)
    assert window[2] == 3
    assert [r['ingredient'] for r in window[7]].count('eaa') == 1
    assert next(r for r in window[7] if r['ingredient'] == 'eaa')['assessment'] == 'unresolved_source_quantity'
    assert score_dose(product)['score'] is None
    artifact = build_scored_artifact(product)
    dose = artifact['_v4_module_breakdown']['dimensions']['dose']
    assert dose['score'] is None
    assert dose['metadata']['reason_code'] == 'unresolved_source_quantity'
    assert artifact['quality_assessment_status'] == 'partial' or artifact['quality_score_status'] == 'not_scored'


@pytest.mark.parametrize('unavailable', [0, 1, 4, 9])
def test_named_eaa_group_has_one_vote_with_disclosed_or_positively_hidden_members(unavailable):
    from scoring_v4.modules.generic_dose import _score_declared_purpose_window, score_dose

    product = _named_eaa_group_product(unavailable=unavailable, hidden=True)
    window = _score_declared_purpose_window(product)
    assert window[2] == 3
    assert {r['ingredient'] for r in window[7]} == {'eaa', 'l_theanine', 'creatine_monohydrate'}
    eaa = next(r for r in window[7] if r['ingredient'] == 'eaa')
    assert eaa['credit_raw'] == pytest.approx(NEUTRAL)
    assert eaa['assessment'] == ('hidden_amount_neutral' if unavailable else 'no_benchmark_neutral')
    assert 'amount_per_serving' not in eaa
    assert score_dose(product)['score'] is not None


def test_one_unresolved_hidden_eaa_member_keeps_the_source_hold():
    from scoring_v4.modules.generic_dose import score_dose
    product = _named_eaa_group_product(unavailable=4, hidden=True)
    product['ingredient_quality_data']['ingredients'][0]['quantity_operator'] = 'ambiguous'
    assert score_dose(product)['score'] is None


@pytest.mark.parametrize('unavailable', [0, 4])
def test_positive_but_unresolved_eaa_member_cannot_complete_the_group(unavailable):
    from scoring_v4.modules.generic_dose import score_dose
    product = _named_eaa_group_product(unavailable=unavailable, hidden=True)
    product['ingredient_quality_data']['ingredients'][8]['quantity_operator'] = 'unknown'
    assert score_dose(product)['score'] is None


def test_source_qualified_whole_eaa_owner_keeps_exactly_one_generic_vote():
    from test_v4_sports_dose_p171 import _nested_complete_eaa_source
    from scoring_v4.modules.generic_dose import _score_declared_purpose_window

    product = _nested_complete_eaa_source()
    product['product_name'] = product['fullName'] = 'EAA'
    window = _score_declared_purpose_window(product)
    assert window[2] == 1
    assert len(window[7]) == 1
    assert window[7][0]['ingredient'] == 'essential_amino_acids'
    assert window[0] == pytest.approx(NEUTRAL)


def test_exact_strict_amino_source_precedes_a_stale_unresolved_mirror_twin():
    from copy import deepcopy
    from scoring_v4.modules.generic_dose import _score_declared_purpose_window, score_dose

    product = _named_eaa_group_product()
    product['ingredient_quality_data']['ingredients'] = deepcopy(product['ingredient_quality_data']['ingredients'])
    product['ingredient_quality_data']['ingredients'][0]['quantity_operator'] = 'unknown'
    window = _score_declared_purpose_window(product)
    assert window[2] == 3
    assert next(r for r in window[7] if r['ingredient'] == 'eaa')['assessment'] == 'no_benchmark_neutral'
    assert score_dose(product)['score'] is not None


def test_unnamed_eaa_members_do_not_create_an_extra_purpose_or_hold():
    from scoring_v4.modules.generic_dose import _score_declared_purpose_window, score_dose
    product = _named_eaa_group_product(unavailable=9)
    product['product_name'] = product['fullName'] = 'L-Theanine + Creatine'
    window = _score_declared_purpose_window(product)
    assert window[2] == 2
    assert {r['ingredient'] for r in window[7]} == {'l_theanine', 'creatine_monohydrate'}
    assert score_dose(product)['score'] is not None


def _named_bcaa_with_whole_preparation(*, hidden=False, qualified=True, unresolved=False):
    from scoring_v4.modules.sports_helpers import BCAA_CANONICALS
    product = _named_eaa_group_product(unavailable=9 if hidden else 0, hidden=hidden)
    rows = [r for r in product['ingredient_quality_data']['ingredients']
            if r['canonical_id'] in BCAA_CANONICALS]
    owner = _ingredient(name='BCAA', canonical_id='branched_chain_amino_acids', quantity=7000,
                        raw_source_path='ingredientRows[20]')
    if qualified:
        owner.update(scoring_input_kind='product_level_evidence', evidence_type='blend_anchor_mass',
                     evidence_scope='blend_level', dose_class='therapeutic_mass', scoreable=True, dose_value=7000)
    if unresolved:
        owner['quantity_operator'] = 'unknown'
    rows.append(owner)
    product['ingredient_quality_data']['ingredients'] = rows
    product['ingredient_quality_data']['ingredients_scorable'] = rows
    product['product_name'] = product['fullName'] = 'BCAA'
    return product


@pytest.mark.parametrize('hidden', [False, True])
def test_qualified_bcaa_preparation_has_one_vote_despite_split_member_rows(hidden):
    from scoring_v4.modules.generic_dose import _score_declared_purpose_window
    product = _named_bcaa_with_whole_preparation(hidden=hidden)
    window = _score_declared_purpose_window(product)
    assert window[2] == len(window[7]) == 1
    assert window[7][0]['ingredient'] == 'branched_chain_amino_acids'
    assert window[0] == pytest.approx(NEUTRAL)


@pytest.mark.parametrize('qualified,unresolved', [(False, False), (True, True)])
def test_unqualified_or_unresolved_bcaa_header_cannot_suppress_missing_member_hold(qualified, unresolved):
    from scoring_v4.modules.generic_dose import _score_declared_purpose_window, score_dose
    product = _named_bcaa_with_whole_preparation(qualified=qualified, unresolved=unresolved)
    product['ingredient_quality_data']['ingredients'][0]['quantity'] = None
    window = _score_declared_purpose_window(product)
    assert any(r['ingredient'] == 'bcaa' and r['assessment'] == 'unresolved_source_quantity' for r in window[7])
    assert score_dose(product)['score'] is None
