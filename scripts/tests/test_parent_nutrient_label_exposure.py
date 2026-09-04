"""A declared parent amount is distinct from its named source-material mass."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from enhanced_normalizer import EnhancedDSLDNormalizer  # noqa: E402
from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402
from scoring_v4.modules.multi_prenatal_dose import score_dose  # noqa: E402


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


def _declared_row(name: str, parent: str = "Magnesium") -> dict:
    return {
        "name": name,
        "raw_source_text": name,
        "raw_source_path": "ingredientRows[0]",
        "standardName": parent,
        "canonical_id": parent.lower().replace(" ", "_"),
        "canonical_source_db": "ingredient_quality_map",
        "ingredientGroup": parent,
        "raw_taxonomy": {"ingredientGroup": parent},
        "source_section": "active",
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
        "dose_class": "therapeutic_mass",
        "quantity": 30,
        "unit": "mg",
    }


def _basis(enricher: SupplementEnricherV3, row: dict) -> dict:
    return enricher._ul_exposure_basis(
        row,
        canonical_id=row["canonical_id"],
        standard_name=row["standardName"],
    )


@pytest.mark.parametrize(
    "parent,name",
    [
        ("Vitamin A", "Vitamin A (as retinyl palmitate)"),
        (
            "Vitamin D",
            "Vitamin D (as cholecalciferol) [from Lichen (whole plant)]",
        ),
        (
            "Vitamin E",
            "Vitamin E (as alpha-tocopherol from mixed tocopherols) "
            "[from Brassica napus (seed)]",
        ),
        ("Magnesium", "Magnesium (as dimagnesium malate)"),
        ("Zinc", "Zinc (as bisglycinate)"),
        ("Boron", "Boron (as calcium fructoborate)"),
        ("Magnesium", "  MAGNESIUM  (AS magnesium citrate)  "),
        ("Magnesium", "Magnesium [from magnesium citrate]"),
    ],
)
def test_explicit_parent_source_declaration_needs_no_daily_value_or_unii(
    enricher: SupplementEnricherV3, parent: str, name: str,
) -> None:
    basis = _basis(enricher, _declared_row(name, parent))

    assert basis["ul_gate_eligible"] is True
    assert basis["ul_exposure_basis"] == "supplement_facts_parent_nutrient_amount"
    assert basis["ul_gate_ineligible_reason"] is None


@pytest.mark.parametrize(
    "name,overrides",
    [
        ("Magnesium Citrate", {}),
        ("Magnesium citrate (as citrate)", {}),
        ("Magnesium (as citrate) compound mass", {}),
        ("Magnesium [as citrate)", {}),
        ("Magnesium (as citrate]", {}),
        (
            "Calcium D-glucarate",
            {
                "standardName": "Calcium",
                "canonical_id": "calcium",
                "ingredientGroup": "Calcium",
                "raw_taxonomy": {"ingredientGroup": "Calcium"},
            },
        ),
        ("Citrate source for Magnesium (as magnesium citrate)", {}),
        ("Magnesium (as citrate)", {"raw_source_text": "Magnesium citrate"}),
        ("Magnesium (as citrate)", {"source_section": "inactive"}),
        ("Magnesium (as citrate)", {"cleaner_row_role": "source_descriptor"}),
        ("Magnesium (as citrate)", {"score_eligible_by_cleaner": False}),
        ("Magnesium (as citrate)", {"dose_class": "source_material_mass"}),
        ("Magnesium (as citrate)", {"isNestedIngredient": True}),
        ("Magnesium (as citrate)", {"parentBlend": "Mineral complex"}),
        ("Magnesium (as citrate)", {"raw_taxonomy": {"ingredientGroup": "Minerals"}}),
        ("Magnesium (as citrate)", {"source_section": None}),
        ("Magnesium (as citrate)", {"canonical_id": "calcium"}),
    ],
)
def test_source_compound_and_unconfirmed_rows_remain_conservative(
    enricher: SupplementEnricherV3, name: str, overrides: dict,
) -> None:
    basis = _basis(enricher, {**_declared_row(name), **overrides})

    assert basis["ul_gate_eligible"] is False
    assert basis["ul_gate_ineligible_reason"] == "compound_mass_not_elemental"


def test_ritual_real_label_retains_nutrient_adequacy_after_reenrichment(
    enricher: SupplementEnricherV3,
) -> None:
    source = (
        ROOT / "manual_labels/product_submissions"
        / "PG_SUB_A89A9212EDDD4A89A54842EF791F2AE2.json"
    )
    raw = json.loads(source.read_text())
    cleaned = EnhancedDSLDNormalizer().normalize_product(raw)
    enriched, _issues = enricher.enrich_product(cleaned)
    data = enriched["rda_ul_data"]
    analyzed = {row["canonical_id"]: row for row in data["analyzed_ingredients"]}
    adequacy = {row["canonical_id"]: row for row in data["adequacy_results"]}

    for canonical_id in (
        "vitamin_a", "vitamin_d", "vitamin_e", "magnesium", "zinc", "boron",
    ):
        assert analyzed[canonical_id]["ul_gate_eligible"] is True, canonical_id
        assert analyzed[canonical_id]["ul_exposure_basis"] == (
            "supplement_facts_parent_nutrient_amount"
        )
        assert analyzed[canonical_id].get("skip_ul_reason") != (
            "worst_case_compound_mass_within_ul"
        )

    for canonical_id, expected_percent in (
        ("vitamin_a", 20), ("vitamin_d", 100 * 50 / 15),
        ("vitamin_e", 100 * 6.7 / 15), ("magnesium", 7.5),
        ("zinc", 100 * 2.4 / 11),
    ):
        assert adequacy[canonical_id]["pct_rda"] == pytest.approx(expected_percent)
        assert adequacy[canonical_id]["scoring_eligible"] is True
        assert not any(
            "compound mass" in note.lower()
            for note in adequacy[canonical_id]["notes"]
        )

    # Boron has a UL but no established RDA: the new label proof must not invent one.
    assert adequacy["boron"]["rda_ai"] is None

    dose = score_dose(enriched)
    assert dose["metadata"]["coverage_nutrient_count"] == 8
    assert dose["metadata"]["critical_nutrients_missing"] == ["iron"]
