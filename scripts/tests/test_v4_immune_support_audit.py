"""Immune-support audit regressions.

These pin the category behavior surfaced by the July 2026 immune audit:
clean daily immune formulas should be able to score in the high-80s, while
gummy/syrup/high-zinc "emergency" formulas should not look benchmark-clean.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

import pytest  # noqa: E402

from score_supplements_v4 import score_product_v4  # noqa: E402
from scoring_v4.modules import immune_support  # noqa: E402


DATA_DIR = SCRIPTS_DIR / "data"


@pytest.mark.parametrize("active", ["vitamin_c", "vitamin_d3", "zinc", "copper", "selenium"])
@pytest.mark.parametrize("pct,credit", [(10, .25), (20, .5), (50, .6875), (100, 1), (600, 1)])
def test_immune_nutrient_purpose_uses_source_rda_curve(active, pct, credit):
    product = _immune_product()
    row = next(r for r in product["ingredient_quality_data"]["ingredients_scorable"] if r["canonical_id"] == active)
    product["rda_ul_data"]["adequacy_results"] = [{
        "nutrient": row["name"], "canonical_id": active, "pct_rda": pct,
        "rda_ai": 777, "scoring_eligible": True,
    }]
    result = immune_support.score_immune_purpose_dose(product, row)
    assert result["score"] == pytest.approx(credit * 22)
    assert result["reference"]["rda_ai"] == 777
    assert "target_range" not in result
    # One declared purpose must not be replaced by a whole-formula score.
    product["ingredient_quality_data"]["ingredients_scorable"] = [row]
    product["ingredient_quality_data"]["ingredients"] = [row]
    from scoring_v4.scored_artifact import build_scored_artifact
    artifact = build_scored_artifact(product)
    assert artifact["quality_score_status"] == "scored"
    assert artifact["quality_pillars_v4"]["dose"]["score"] == round(credit * 20, 1)


@pytest.mark.parametrize("active", ["beta_glucan", "quercetin", "elderberry"])
@pytest.mark.parametrize("quantity", [1, 250, 1000, 5000])
def test_immune_non_nutrient_purpose_has_no_general_dose_curve(active, quantity):
    from scoring_v4.modules.generic_helpers import unbenchmarked_dose_credit

    product = _immune_product()
    row = next(r for r in product["ingredient_quality_data"]["ingredients_scorable"] if r["canonical_id"] == active)
    row["quantity"] = quantity
    result = immune_support.score_immune_purpose_dose(product, row)
    assert result["score"] == unbenchmarked_dose_credit()
    assert result["band"] == "disclosed_no_reference"


def test_immune_nutrient_does_not_invent_an_rda_from_disclosed_mass():
    product = _immune_product()
    row = product["ingredient_quality_data"]["ingredients_scorable"][0]
    product["rda_ul_data"]["adequacy_results"] = []
    assert immune_support.score_immune_purpose_dose(product, row) is None
    product["rda_ul_data"]["adequacy_results"] = [{
        "canonical_id": "vitamin_c", "nutrient": "Vitamin C", "pct_rda": 100,
        "scoring_eligible": False}]
    assert immune_support.score_immune_purpose_dose(product, row) is None


def _row(
    name: str,
    canonical_id: str,
    quantity: float,
    unit: str,
    *,
    bio_score: float = 12.0,
    category: str = "vitamin",
) -> Dict[str, Any]:
    return {
        "name": name,
        "standard_name": name,
        "canonical_id": canonical_id,
        "quantity": quantity,
        "unit": unit,
        "bio_score": bio_score,
        "mapped": True,
        "scoreable_identity": True,
        "cleaner_row_role": "active_scorable",
        "category": category,
    }


def _cert(program: str = "NSF Sport", scope: str = "sku") -> Dict[str, Any]:
    return {
        "program": program,
        "scope": scope,
        "record_id": f"FIXTURE_{program.upper().replace(' ', '_')}",
        "source_url": "https://registry.example/certified-products",
        "snapshot_date": "2026-09-16",
        "recency_status": "fresh",
        "brand_matched": True,
    }


def _immune_product(*, high_zinc: bool = False, gummy: bool = False) -> Dict[str, Any]:
    zinc_mg = 50.0 if high_zinc else 15.0
    sugar = {
        "level": "high" if gummy else "sugar_free",
        "contains_sugar": gummy,
        "has_added_sugar": gummy,
        "amount_g": 8 if gummy else 0,
        "sugar_sources": ["glucose syrup"] if gummy else [],
    }
    return {
        "product_name": (
            "Ultra Immune Emergency Gummies"
            if gummy
            else "ClearShield Immune Daily"
        ),
        "brand_name": "PharmaGuide Benchmark",
        "primary_type": "immune_support",
        "supplement_taxonomy": {"primary_type": "immune_support"},
        "product_status": "active",
        "form_factor": "gummy" if gummy else "capsule",
        "form_factor_canonical": "gummy" if gummy else "capsule",
        "verified_cert_programs": [_cert()],
        "ingredient_quality_data": {
            "ingredients_scorable": [
                _row("Vitamin C as calcium ascorbate", "vitamin_c", 500, "mg", bio_score=13),
                _row("Vitamin D3", "vitamin_d3", 25, "mcg", bio_score=13),
                _row("Zinc bisglycinate", "zinc", zinc_mg, "mg", bio_score=13, category="mineral"),
                _row("Copper bisglycinate", "copper", 1, "mg", bio_score=13, category="mineral"),
                _row("Selenium selenomethionine", "selenium", 55, "mcg", bio_score=13, category="mineral"),
                _row("Yeast beta-glucan 1,3/1,6", "beta_glucan", 250, "mg", bio_score=11, category="other"),
                _row("Quercetin phytosome", "quercetin", 500, "mg", bio_score=12, category="botanical"),
                _row("Elderberry extract", "elderberry", 300, "mg", bio_score=10, category="botanical"),
            ]
        },
        "evidence_data": {
            "clinical_matches": [
                {
                    "ingredient": "Vitamin C",
                    "standard_name": "Vitamin C",
                    "study_type": "systematic_review_meta",
                    "evidence_level": "ingredient-human",
                    "effect_direction": "positive_weak",
                    "total_enrollment": 1000,
                    "min_clinical_dose": 200,
                    "dose_unit": "mg",
                },
                {
                    "ingredient": "Vitamin D3",
                    "standard_name": "Vitamin D3",
                    "study_type": "systematic_review_meta",
                    "evidence_level": "ingredient-human",
                    "effect_direction": "positive_weak",
                    "total_enrollment": 1000,
                    "min_clinical_dose": 15,
                    "dose_unit": "mcg",
                },
                {
                    "ingredient": "Zinc",
                    "standard_name": "Zinc",
                    "study_type": "systematic_review_meta",
                    "evidence_level": "ingredient-human",
                    "effect_direction": "positive_weak",
                    "total_enrollment": 500,
                    "min_clinical_dose": 10,
                    "dose_unit": "mg",
                },
            ]
        },
        "rda_ul_data": {
            "safety_flags": (
                [{"nutrient": "Zinc", "canonical_id": "zinc", "pct_ul": 125.0,
                  "ul": 40.0, "unit": "mg", "ul_gate_eligible": True, "flag": "OVER_UL_Zinc"}]
                if high_zinc
                else []
            ),
            "adequacy_results": [
                {"nutrient": "Vitamin C", "pct_rda": 555, "pct_ul": 25},
                {"nutrient": "Vitamin D3", "pct_rda": 125, "pct_ul": 25},
                {"nutrient": "Zinc", "pct_rda": 455 if high_zinc else 136, "pct_ul": 125 if high_zinc else 37.5},
                {"nutrient": "Copper", "pct_rda": 111, "pct_ul": 10},
                {"nutrient": "Selenium", "pct_rda": 100, "pct_ul": 12.2},
            ],
        },
        "dietary_sensitivity_data": {
            "sugar": sugar,
            "sweeteners": {"high_glycemic": ["glucose syrup"] if gummy else []},
        },
    }


def _emergency_gummy_product() -> Dict[str, Any]:
    product = _immune_product(high_zinc=True, gummy=True)
    product["verified_cert_programs"] = []
    product["ingredient_quality_data"]["ingredients_scorable"] = [
        _row("Vitamin C", "vitamin_c", 1000, "mg", bio_score=8),
        _row("Vitamin D3", "vitamin_d3", 100, "mcg", bio_score=10),
        _row("Zinc oxide", "zinc", 50, "mg", bio_score=4, category="mineral"),
        _row("Elderberry syrup concentrate", "elderberry", 100, "mg", bio_score=6, category="botanical"),
    ]
    return product


def _botanical_stack_with_duplicate_rows() -> Dict[str, Any]:
    rows = [
        _row("Vitamin C", "vitamin_c", 250, "mg", bio_score=10),
    ]
    for name, canonical_id in (
        ("Echinacea", "echinacea"),
        ("Goldenseal", "goldenseal"),
        ("Astragalus", "astragalus"),
        ("Andrographis", "andrographis"),
        ("Oregano oil", "oregano_oil"),
    ):
        rows.append(_row(name, canonical_id, 100, "mg", bio_score=6, category="botanical"))
        rows.append(_row(f"{name} extract duplicate", canonical_id, 100, "mg", bio_score=6, category="botanical"))

    product = _immune_product()
    product["product_name"] = "Immune Botanical Defense Complex"
    product["verified_cert_programs"] = []
    product["ingredient_quality_data"]["ingredients_scorable"] = rows
    product["evidence_data"]["clinical_matches"] = []
    product["rda_ul_data"]["safety_flags"] = []
    product["rda_ul_data"]["adequacy_results"] = [
        {"nutrient": "Vitamin C", "pct_rda": 277, "pct_ul": 12.5},
    ]
    product["dietary_sensitivity_data"] = {
        "sugar": {"level": "sugar_free", "contains_sugar": False, "has_added_sugar": False, "amount_g": 0},
        "sweeteners": {},
    }
    return product


def test_daily_immune_formula_uses_nutritional_and_completed_neutral_purposes() -> None:
    out = score_product_v4(_immune_product())

    assert out["v4_module"] == "generic"
    # Five nutrient purposes meet their RDA; three non-nutrients use .57 neutral.
    assert out["quality_pillars_v4"]["dose"]["score"] == 16.8
    assert out["quality_pillars_v4"]["formulation"]["score"] >= 16.0
    immune_meta = out["v4_breakdown"]["module"]["dimensions"]["formulation"][
        "metadata"
    ]["immune_support"]
    assert immune_meta["profile_applied"] is False
    assert immune_meta["design_audit_applied"] is True


def test_gummy_high_zinc_immune_formula_not_benchmark_clean() -> None:
    out = score_product_v4(_immune_product(high_zinc=True, gummy=True))
    pillars = out["quality_pillars_v4"]
    dose = out["v4_breakdown"]["module"]["dimensions"]["dose"]

    # Guard the owning pillars, not a tuned total-score cutoff. The gummy form
    # itself is neutral; excess zinc and added sugar remain visible where they
    # belong.
    assert pillars["safety_hygiene"]["score"] < 10.0
    assert pillars["dose"]["score"] < 20.0
    zinc = next(
        item for item in dose["metadata"]["specialized_purpose_assessments"]
        if item.get("active") == "zinc"
    )
    # Nutritional adequacy plateaus; confirmed excess is the final ceiling's.
    assert zinc["score"] == 22.0
    assert pillars["dose"]["score"] == 10.0


def test_high_zinc_changes_dose_not_formulation_quality() -> None:
    normal = score_product_v4(_immune_product())
    high_zinc = score_product_v4(_immune_product(high_zinc=True))
    normal_pillars = normal["quality_pillars_v4"]
    high_pillars = high_zinc["quality_pillars_v4"]

    assert (
        high_pillars["formulation"]["score"]
        == normal_pillars["formulation"]["score"]
    )
    assert high_pillars["dose"]["score"] < normal_pillars["dose"]["score"]


def test_high_zinc_gummy_does_not_receive_clean_daily_immune_evidence_floor() -> None:
    out = score_product_v4(_emergency_gummy_product())
    evidence = out["v4_breakdown"]["module"]["dimensions"]["evidence"]

    # The approved equal-purpose Dose policy can move the aggregate score.
    # This regression owns only the immune Evidence floor and therefore pins
    # the raw Evidence result instead of an unrelated total-score threshold.
    assert evidence["score"] < 14.0
    assert evidence["metadata"]["immune_support_evidence_floor_applied"] is False


def test_high_variability_botanical_count_dedupes_duplicate_rows() -> None:
    out = score_product_v4(_botanical_stack_with_duplicate_rows())
    formulation = out["v4_breakdown"]["module"]["dimensions"]["formulation"]
    immune_meta = formulation["metadata"]["immune_support"]

    assert immune_meta["high_variability_botanical_count"] == 5
    assert "immune_high_variability_botanical_stack" in formulation["penalties"]
    assert formulation["penalties"]["immune_high_variability_botanical_stack"] == -3.0
    assert formulation["score"] == pytest.approx(
        sum(formulation["components"].values()) - 3.0
    )


def _with_dose(canonical_id: str, amount: float, unit: str | None = None) -> Dict[str, Any]:
    product = _immune_product()
    for row in product["ingredient_quality_data"]["ingredients_scorable"]:
        if row["canonical_id"] == canonical_id:
            row["quantity"] = amount
            if unit:
                row["unit"] = unit
    return product


@pytest.mark.parametrize("canonical_id,component,points", [
    ("vitamin_c", "vitamin_c_daily_range", 3),
    ("vitamin_d3", "vitamin_d_daily_range", 3),
    ("zinc", "zinc_daily_range", 3),
    ("copper", "copper_balance", 1.5),
    ("selenium", "selenium_daily_range", 1.5),
])
def test_immune_formula_nutrients_follow_source_rda_with_existing_budgets(canonical_id, component, points):
    product = _immune_product()
    for pct, fraction in [(10, .25), (20, .5), (50, .6875), (100, 1), (1000, 1)]:
        product["rda_ul_data"]["adequacy_results"] = [{
            "canonical_id": canonical_id, "pct_rda": pct, "scoring_eligible": True}]
        dose = immune_support.score_immune_support_dose(product)
        assert dose["components"][component] == round(points * fraction, 4)


@pytest.mark.parametrize("canonical_id,component,points", [
    ("beta_glucan", "beta_glucan_disclosed", 3),
    ("quercetin", "quercetin_disclosed", 2.5),
    ("elderberry", "elderberry_disclosed", 2.5),
])
def test_immune_formula_botanicals_keep_completed_neutral_within_component_budget(canonical_id, component, points):
    from scoring_v4.modules.generic_helpers import unbenchmarked_dose_credit
    from scoring_v4.modules.generic_dose import CAP_SUPPLEMENTAL_WINDOW

    for amount in (1, 250, 1000, 10000):
        dose = immune_support.score_immune_support_dose(_with_dose(canonical_id, amount))
        assert dose["components"][component] == round(points * unbenchmarked_dose_credit() / CAP_SUPPLEMENTAL_WINDOW, 4)


@pytest.mark.parametrize(
    ("canonical_id", "amount", "unit", "flag"),
    [
        ("zinc", 40.0, "mg", None),
        ("zinc", 40.5, "mg", "high_zinc"),
        ("vitamin_d3", 100.0, "mcg", None),
        ("vitamin_d3", 100.5, "mcg", "high_vitamin_d"),
        ("vitamin_d3", 4000, "IU", None),
        ("vitamin_d3", 4001, "IU", "high_vitamin_d"),
    ],
)
def test_immune_high_dose_thresholds_are_strictly_greater(canonical_id, amount, unit, flag) -> None:
    product = _with_dose(canonical_id, amount, unit)
    dose = immune_support.score_immune_support_dose(product)

    assert dose["metadata"]["high_zinc"] is (flag == "high_zinc")
    assert dose["metadata"]["high_vitamin_d"] is (flag == "high_vitamin_d")
    # Dose V4.1 section 2.4: the UL flags are metadata; the product-level
    # ceiling, not a withheld component, reduces Dose once.
    assert dose["components"]["daily_use_discipline"] == 2.0
    formulation = immune_support.immune_support_formulation_adjustment(product)
    assert formulation["metadata"]["high_zinc"] is (flag == "high_zinc")


def test_immune_full_nutrient_formula_preserves_neutral_non_nutrient_shares() -> None:
    dose = immune_support.score_immune_support_dose(_immune_product())

    # 12 nutrient points + 8 non-nutrient points at .57 + existing 2-point compatibility component.
    assert sum(dose["components"].values()) == 18.56
    assert dose["score"] == 18.56 and isinstance(dose["score"], float)


def test_immune_dose_reads_every_magnitude_from_config(monkeypatch) -> None:
    # A literal left beside a matching constant passes the drift guard; this does not.
    product = _immune_product()
    with monkeypatch.context() as m:
        m.setitem(immune_support.IMMUNE_DOSE_BANDS, "vitamin_c_mg", {"points": 4.0})
        m.setitem(immune_support.IMMUNE_DOSE_BANDS, "copper_mg", {"points": 2.0})
        m.setattr(immune_support, "IMMUNE_DAILY_USE_DISCIPLINE_POINTS", 1.0)
        m.setattr(immune_support, "IMMUNE_DOSE_CAP", 5.0)
        dose = immune_support.score_immune_support_dose(product)
        assert dose["components"]["vitamin_c_daily_range"] == 4.0
        assert dose["components"]["copper_balance"] == 2.0
        assert dose["components"]["daily_use_discipline"] == 1.0
        assert dose["score"] == 5.0
    with monkeypatch.context() as m:
        m.setattr(immune_support, "HIGH_ZINC_THRESHOLD_MG", 10.0)
        m.setattr(immune_support, "HIGH_VITAMIN_D_THRESHOLD_MCG", 20.0)
        meta = immune_support.score_immune_support_dose(product)["metadata"]
        assert meta["high_zinc"] is True and meta["high_vitamin_d"] is True
        assert immune_support.immune_support_formulation_adjustment(product)["metadata"]["high_zinc"] is True


def test_immune_goal_mapping_excludes_broad_lifestyle_clusters() -> None:
    mappings = json.loads((DATA_DIR / "user_goals_to_clusters.json").read_text())[
        "user_goal_mappings"
    ]
    immune = next(item for item in mappings if item["id"] == "GOAL_IMMUNE_SUPPORT")

    assert set(immune["required_clusters"]) == {
        "immune_defense",
        "immune_probiotic_blend",
    }
    assert not {
        "bone_health",
        "antioxidant_defense",
        "detox_pathway",
        "liver_support",
    } & set(immune["cluster_weights"])


def test_immune_defense_copy_does_not_claim_tier_1_synergy() -> None:
    clusters = json.loads((DATA_DIR / "synergy_cluster.json").read_text())[
        "synergy_clusters"
    ]
    immune = next(item for item in clusters if item["id"] == "immune_defense")

    assert immune["evidence_tier"] == 3
    assert "Tier 1" not in immune["note"]
    assert "no clinical trial has tested this exact combination" in immune["evidence_note"]
