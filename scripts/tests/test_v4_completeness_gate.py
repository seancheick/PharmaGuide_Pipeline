"""v4 Layer 2 — Completeness Gate tests (P1.2).

The gate decides live-catalog eligibility before score math runs. It is
class-aware and intentionally narrower than quality scoring: missing hard
minimums produces NOT_SCORED; missing nice-to-have fields belongs to the
confidence/scoring slices later.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _ingredient(
    *,
    name: str = "Magnesium",
    canonical_id: str = "magnesium",
    dose: float | None = 200,
    unit: str | None = "mg",
) -> dict:
    row = {
        "name": name,
        "standard_name": name,
        "canonical_id": canonical_id,
        "mapped": bool(canonical_id),
    }
    if dose is not None:
        row["dose"] = dose
    if unit is not None:
        row["unit"] = unit
    return row


def _product(*, module: str = "generic", ingredients: list[dict] | None = None, **extra) -> dict:
    supp_type = {
        "generic": "single_nutrient",
        "probiotic": "probiotic",
        "multi_or_prenatal": "multivitamin",
    }[module]
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
    product.update(extra)
    return product


# --- Direct gate contract -------------------------------------------------


def test_generic_complete_single_nutrient_is_live_eligible() -> None:
    from scoring_v4.gate_completeness import evaluate_completeness_gate

    result = evaluate_completeness_gate(_product(), module="generic")

    assert result.is_live_eligible is True
    assert result.verdict is None
    assert result.missing_fields == []
    assert result.module == "generic"


def test_generic_missing_active_identity_is_not_scored() -> None:
    from scoring_v4.gate_completeness import evaluate_completeness_gate

    product = _product(ingredients=[_ingredient(canonical_id="", dose=200, unit="mg")])
    result = evaluate_completeness_gate(product, module="generic")

    assert result.is_live_eligible is False
    assert result.verdict == "NOT_SCORED"
    assert "active_identity" in result.missing_fields


def test_generic_low_mapped_coverage_is_not_scored() -> None:
    from scoring_v4.gate_completeness import evaluate_completeness_gate

    product = _product(
        ingredients=[
            _ingredient(name="Magnesium", canonical_id="magnesium"),
            _ingredient(name="Unmapped herb", canonical_id=""),
        ],
    )
    result = evaluate_completeness_gate(product, module="generic")

    assert result.is_live_eligible is False
    assert result.mapped_coverage == 0.5
    assert "mapped_coverage" in result.missing_fields


def test_explicit_discontinued_status_is_not_live_eligible() -> None:
    from scoring_v4.gate_completeness import evaluate_completeness_gate

    result = evaluate_completeness_gate(
        _product(status="discontinued"),
        module="generic",
    )

    assert result.is_live_eligible is False
    assert result.verdict == "NOT_SCORED"
    assert "product_status_active" in result.missing_fields


def test_missing_form_factor_is_not_scored() -> None:
    from scoring_v4.gate_completeness import evaluate_completeness_gate

    result = evaluate_completeness_gate(
        _product(form_factor=None, product_form=None),
        module="generic",
    )

    assert result.is_live_eligible is False
    assert "form_factor" in result.missing_fields


def test_generic_missing_dose_is_not_scored() -> None:
    from scoring_v4.gate_completeness import evaluate_completeness_gate

    result = evaluate_completeness_gate(
        _product(ingredients=[_ingredient(dose=None, unit="mg")]),
        module="generic",
    )

    assert result.is_live_eligible is False
    assert "dose_with_unit" in result.missing_fields


def test_generic_enzyme_activity_is_valid_dose_evidence() -> None:
    """Digestive enzymes are dosed by activity units (ALU/PPI/BLGU/...), not
    mass. The enricher marks these rows dose_class='enzyme_activity' with an
    activity_unit, but the mass quantity stays 0/NP. v4 must treat the enzyme
    activity as valid dose evidence — NOT block the product as missing
    dose_with_unit. (Real case: DSLD 293966 Pure Encapsulations Tolerase G.)
    """
    from scoring_v4.gate_completeness import evaluate_completeness_gate

    enzyme_row = {
        "name": "Tolerase G",
        "standard_name": "Tolerase G",
        "canonical_id": "digestive_enzymes",
        "mapped": True,
        "dose": 0.0,
        "unit": "NP",
        "dose_class": "enzyme_activity",
        "activity_unit": "ALU",
    }
    result = evaluate_completeness_gate(_product(ingredients=[enzyme_row]), module="generic")

    assert result.is_live_eligible is True
    assert "dose_with_unit" not in result.missing_fields
    assert result.verdict is None


def test_probiotic_total_cfu_plus_named_strains_passes_without_per_strain_cfu() -> None:
    """Garden of Life Prenatal-style shape: total CFU is present, named
    strains are present, but per-strain CFU is missing. This must ship."""
    from scoring_v4.gate_completeness import evaluate_completeness_gate

    product = _product(
        module="probiotic",
        ingredients=[
            _ingredient(
                name="Lactobacillus rhamnosus HN001",
                canonical_id="lactobacillus_rhamnosus",
                dose=None,
                unit="NP",
            )
        ],
        probiotic_data={
            "is_probiotic_product": True,
            "has_cfu": True,
            "total_billion_count": 20.0,
            "total_strain_count": 1,
            "probiotic_blends": [
                {
                    "strains": ["Lactobacillus rhamnosus HN001"],
                    "cfu_data": {"has_cfu": False, "billion_count": 0},
                }
            ],
        },
        product_scoring_evidence=[
            {
                "name": "Total CFU",
                "canonical_id": "probiotic_cfu_total",
                "evidence_type": "probiotic_cfu",
                "scoreable": True,
                "scoreable_identity": True,
                "score_eligible_by_cleaner": True,
                "dose_class": "probiotic_cfu",
                "dose_value": 20_000_000_000,
                "dose_unit": "CFU",
                "source": "statements",
                "raw_source_path": "statements[0]",
                "evidence_scope": "product_level",
                "linked_rows": ["statements[0]"],
                "confidence": "high",
                "reason": "product_level_cfu_with_probiotic_identity",
            }
        ],
    )

    result = evaluate_completeness_gate(product, module="probiotic")

    assert result.is_live_eligible is True
    assert result.verdict is None


def test_probiotic_missing_total_cfu_is_not_scored() -> None:
    from scoring_v4.gate_completeness import evaluate_completeness_gate

    product = _product(
        module="probiotic",
        ingredients=[_ingredient(name="Lactobacillus acidophilus", dose=None, unit="NP")],
        probiotic_data={
            "is_probiotic_product": True,
            "total_billion_count": 0,
            "total_strain_count": 1,
        },
    )

    result = evaluate_completeness_gate(product, module="probiotic")

    assert result.is_live_eligible is False
    assert "total_cfu" in result.missing_fields


def test_probiotic_missing_named_strain_is_not_scored() -> None:
    from scoring_v4.gate_completeness import evaluate_completeness_gate

    product = _product(
        module="probiotic",
        ingredients=[_ingredient(name="Probiotic blend", canonical_id="probiotic_blend", dose=None, unit="NP")],
        probiotic_data={
            "is_probiotic_product": True,
            "total_billion_count": 20.0,
            "total_strain_count": 0,
            "probiotic_blends": [{"strains": []}],
        },
    )

    result = evaluate_completeness_gate(product, module="probiotic")

    assert result.is_live_eligible is False
    assert "named_strain" in result.missing_fields


def test_multi_or_prenatal_with_sixty_percent_dose_panel_passes() -> None:
    from scoring_v4.gate_completeness import evaluate_completeness_gate

    ingredients = [
        _ingredient(name=f"Nutrient {i}", canonical_id=f"nutrient_{i}", dose=(i if i <= 6 else None))
        for i in range(1, 11)
    ]
    product = _product(module="multi_or_prenatal", ingredients=ingredients)

    result = evaluate_completeness_gate(product, module="multi_or_prenatal")

    assert result.is_live_eligible is True
    assert result.dose_coverage == 1.0


def test_multi_or_prenatal_below_sixty_percent_dose_panel_is_not_scored() -> None:
    from scoring_v4.gate_completeness import evaluate_completeness_gate

    ingredients = [
        _ingredient(name=f"Nutrient {i}", canonical_id=f"nutrient_{i}", dose=(i if i <= 5 else None))
        for i in range(1, 11)
    ]
    product = _product(module="multi_or_prenatal", ingredients=ingredients)

    result = evaluate_completeness_gate(product, module="multi_or_prenatal")

    assert result.is_live_eligible is True
    assert result.dose_coverage == 1.0
    assert "micronutrient_panel_dose_coverage" not in result.missing_fields


def test_sports_with_positive_creatine_dose_is_live_eligible() -> None:
    from scoring_v4.gate_completeness import evaluate_completeness_gate

    product = _product(
        ingredients=[
            _ingredient(name="Creatine Monohydrate", canonical_id="creatine_monohydrate", dose=3, unit="Gram(s)")
        ],
        primary_type="amino_acid",
        supplement_taxonomy={"primary_type": "amino_acid"},
    )

    result = evaluate_completeness_gate(product, module="sports")

    assert result.module == "sports"
    assert result.is_live_eligible is True
    assert "sports_active_dose" not in result.missing_fields


def test_sports_without_sports_active_dose_is_not_scored() -> None:
    from scoring_v4.gate_completeness import evaluate_completeness_gate

    product = _product(
        ingredients=[_ingredient(name="Calcium", canonical_id="calcium", dose=200, unit="mg")],
        primary_type="pre_workout",
        supplement_taxonomy={"primary_type": "pre_workout"},
    )

    result = evaluate_completeness_gate(product, module="sports")

    assert result.module == "sports"
    assert result.is_live_eligible is False
    assert "sports_active_dose" in result.missing_fields


def test_malformed_product_never_raises_and_is_not_scored() -> None:
    from scoring_v4.gate_completeness import evaluate_completeness_gate

    result = evaluate_completeness_gate(None, module="generic")  # type: ignore[arg-type]

    assert result.is_live_eligible is False
    assert result.verdict == "NOT_SCORED"
    assert result.missing_fields


# --- Shadow integration ---------------------------------------------------


def test_shadow_entry_point_marks_incomplete_clean_product_not_scored() -> None:
    from score_supplements_v4_shadow import score_product_v4_shadow

    out = score_product_v4_shadow(
        _product(ingredients=[_ingredient(canonical_id="", dose=None, unit=None)])
    )

    assert out["shadow_score_v4_100"] is None
    assert out["shadow_score_v4_verdict"] == "NOT_SCORED"
    assert out["shadow_score_v4_confidence"] == "blocked_by_completeness_gate"
    assert out["shadow_score_v4_anchored"] is False
    gate = out["shadow_score_v4_breakdown"]["completeness_gate"]
    assert gate["is_live_eligible"] is False
    assert "active_identity" in gate["missing_fields"]


def test_shadow_entry_point_preserves_safety_short_circuit_before_completeness() -> None:
    from score_supplements_v4_shadow import score_product_v4_shadow

    product = _product(ingredients=[_ingredient(canonical_id="", dose=None, unit=None)])
    product["contaminant_data"] = {
        "banned_substances": {
            "substances": [
                {"name": "Vinpocetine", "status": "banned", "match_type": "exact"}
            ]
        }
    }

    out = score_product_v4_shadow(product)

    assert out["shadow_score_v4_verdict"] == "BLOCKED"
    assert out["shadow_score_v4_confidence"] == "blocked_by_safety_gate"
    assert "safety_gate" in out["shadow_score_v4_breakdown"]
    assert "completeness_gate" not in out["shadow_score_v4_breakdown"]


def test_completeness_fail_overrides_caution_but_keeps_safety_breakdown() -> None:
    from score_supplements_v4_shadow import score_product_v4_shadow

    product = _product(
        ingredients=[_ingredient(canonical_id="", dose=None, unit=None)],
        has_disease_claims=True,
    )

    out = score_product_v4_shadow(product)

    assert out["shadow_score_v4_verdict"] == "NOT_SCORED"
    assert out["shadow_score_v4_breakdown"]["safety_gate"]["verdict"] == "CAUTION"
    assert out["shadow_score_v4_breakdown"]["completeness_gate"]["is_live_eligible"] is False
