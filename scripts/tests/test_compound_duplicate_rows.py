"""Dual-declaration compound-row dedupe regression tests.

Found 2026-06-12 via live QA (dsld_id 315678, Double Wood "Magnesium
Glycinate 400 mg"): the label declares the same nutrient twice —

    Magnesium            60 mg   (bare elemental Supplement Facts row)
    Magnesium Glycinate 400 mg   (compound-weight restatement, ~14% elemental)

Both rows canonicalize to ``canonical_id: magnesium``. Before this fix the
duplicate poisoned three independent consumers:

1. D4.3 UL aggregation summed 60+400=460 mg → false "exceeds UL" flag
   (131% of the 350 mg supplemental magnesium UL).
2. ``infer_supplement_type`` counted 2 actives → 'targeted' instead of
   'single_nutrient'.
3. v4 formulation scoring saw 2 scorable actives → the premium-single
   floor and A6 focus bonus never fired (raw 11.5 → pillar 9.2/20 for a
   premium glycinate chelate).

Fix: ``supplement_type_utils.mark_compound_duplicate_rows`` marks the
compound-named row(s) with ``is_compound_duplicate=True`` whenever a bare
elemental row with a positive quantity shares the canonical group. The
marker is respected by ``infer_supplement_type``, scoring's
``is_scorable``, and ``_collect_rda_ul_data`` (skip reason
``compound_duplicate_row``).

Mirrors the Flutter app defense (lib/services/stack/stack_nutrient_aggregator.dart,
commit 99fa09b): bare elemental row wins; compound siblings excluded.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from supplement_type_utils import infer_supplement_type, mark_compound_duplicate_rows
from scoring_v4.modules.generic_helpers import is_scorable
from enrich_supplements_v3 import SupplementEnricherV3


def _mag_rows() -> list:
    return [
        {
            "name": "Magnesium",
            "standardName": "Magnesium",
            "canonical_id": "magnesium",
            "quantity": 60.0,
            "unit": "mg",
            "category": "minerals",
        },
        {
            "name": "Magnesium Glycinate",
            "standardName": "Magnesium Glycinate",
            "canonical_id": "magnesium",
            "quantity": 400.0,
            "unit": "mg",
            "category": "minerals",
        },
    ]


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


class TestMarkCompoundDuplicateRows:
    def test_marks_compound_row_when_bare_row_present(self) -> None:
        rows = _mag_rows()
        marked = mark_compound_duplicate_rows(rows)
        assert len(marked) == 1
        assert marked[0]["name"] == "Magnesium Glycinate"
        assert rows[1].get("is_compound_duplicate") is True
        assert "is_compound_duplicate" not in rows[0]

    def test_marks_source_compound_when_name_does_not_start_with_nutrient(self) -> None:
        rows = [
            {
                "name": "Vitamin C",
                "standardName": "Vitamin C",
                "canonical_id": "vitamin_c",
                "quantity": 900.0,
                "unit": "mg",
            },
            {
                "name": "Calcium",
                "standardName": "Calcium",
                "canonical_id": "calcium",
                "quantity": 90.0,
                "unit": "mg",
            },
            {
                "name": "Calcium Ascorbate",
                "standardName": "Vitamin C",
                "canonical_id": "vitamin_c",
                "quantity": 1000.0,
                "unit": "mg",
            },
        ]

        marked = mark_compound_duplicate_rows(rows)

        assert marked == [rows[2]]
        assert rows[2]["is_compound_duplicate"] is True
        assert "is_compound_duplicate" not in rows[0]
        assert "is_compound_duplicate" not in rows[1]

    def test_no_marking_without_bare_row(self) -> None:
        # Genuinely additive multi-form label: two compound rows, no bare row.
        rows = [
            {"name": "Magnesium Oxide", "canonical_id": "magnesium",
             "quantity": 250.0, "unit": "mg"},
            {"name": "Magnesium Citrate", "canonical_id": "magnesium",
             "quantity": 500.0, "unit": "mg"},
        ]
        assert mark_compound_duplicate_rows(rows) == []

    def test_no_marking_when_bare_row_has_no_dose(self) -> None:
        rows = _mag_rows()
        rows[0]["quantity"] = 0
        assert mark_compound_duplicate_rows(rows) == []

    def test_two_bare_rows_untouched(self) -> None:
        # D4.3's motivating teratogenicity case: both rows are bare
        # "Vitamin A" from different sources — additive, must still sum.
        rows = [
            {"name": "Vitamin A", "canonical_id": "vitamin_a",
             "quantity": 3000, "unit": "mcg"},
            {"name": "Vitamin A", "canonical_id": "vitamin_a",
             "quantity": 3000, "unit": "mcg"},
        ]
        assert mark_compound_duplicate_rows(rows) == []

    def test_probiotic_strain_rows_untouched(self) -> None:
        # A bare species row beside a strain-suffixed row can be genuinely
        # additive (distinct strains, own CFU). Outside the DRI set — no marking.
        rows = [
            {"name": "Lactobacillus Acidophilus",
             "canonical_id": "lactobacillus_acidophilus",
             "quantity": 5.0, "unit": "billion cfu"},
            {"name": "Lactobacillus Acidophilus LA-14",
             "canonical_id": "lactobacillus_acidophilus",
             "quantity": 10.0, "unit": "billion cfu"},
        ]
        assert mark_compound_duplicate_rows(rows) == []

    def test_botanical_extract_rows_untouched(self) -> None:
        # Root powder + extract are additive sources, not a restatement.
        rows = [
            {"name": "Turmeric", "canonical_id": "turmeric",
             "quantity": 500.0, "unit": "mg"},
            {"name": "Turmeric Extract", "canonical_id": "turmeric",
             "quantity": 100.0, "unit": "mg"},
        ]
        assert mark_compound_duplicate_rows(rows) == []

    def test_different_canonicals_untouched(self) -> None:
        rows = [
            {"name": "Magnesium", "canonical_id": "magnesium",
             "quantity": 60.0, "unit": "mg"},
            {"name": "Zinc Picolinate", "canonical_id": "zinc",
             "quantity": 30.0, "unit": "mg"},
        ]
        assert mark_compound_duplicate_rows(rows) == []

    def test_nested_and_parent_total_rows_skipped(self) -> None:
        rows = _mag_rows()
        rows[1]["is_nested_ingredient"] = True
        assert mark_compound_duplicate_rows(rows) == []

    def test_idempotent(self) -> None:
        rows = _mag_rows()
        mark_compound_duplicate_rows(rows)
        mark_compound_duplicate_rows(rows)
        assert sum(1 for r in rows if r.get("is_compound_duplicate")) == 1


class TestSupplementTypeClassification:
    def test_dual_declaration_classifies_as_single_nutrient(self) -> None:
        product = {
            "activeIngredients": _mag_rows(),
            "inactiveIngredients": [],
        }
        result = infer_supplement_type(product)
        assert result["active_count"] == 1
        assert result["type"] == "single_nutrient"

    def test_counterion_named_source_does_not_add_a_third_active(self) -> None:
        rows = [
            {"name": "Vitamin C", "standardName": "Vitamin C",
             "canonical_id": "vitamin_c", "quantity": 900.0, "unit": "mg"},
            {"name": "Calcium", "standardName": "Calcium",
             "canonical_id": "calcium", "quantity": 90.0, "unit": "mg"},
            {"name": "Calcium Ascorbate", "standardName": "Vitamin C",
             "canonical_id": "vitamin_c", "quantity": 1000.0, "unit": "mg"},
        ]

        result = infer_supplement_type(
            {"activeIngredients": rows, "inactiveIngredients": []}
        )

        assert result["active_count"] == 2


class TestIsScorable:
    def test_compound_duplicate_not_scorable(self) -> None:
        rows = _mag_rows()
        mark_compound_duplicate_rows(rows)
        assert is_scorable(rows[0]) is True
        assert is_scorable(rows[1]) is False


class TestRdaUlCollection:
    def test_no_false_aggregated_ul_flag(self, enricher) -> None:
        # 60 mg elemental is well under the 350 mg supplemental UL; the
        # 400 mg compound-weight restatement must not push the sum over.
        product = {
            "activeIngredients": _mag_rows(),
            "inactiveIngredients": [],
        }
        result = enricher._collect_rda_ul_data(
            product, min_servings_per_day=1, max_servings_per_day=1
        )
        flags = result.get("safety_flags", [])
        assert [f for f in flags if (f.get("nutrient") or "").lower().startswith("magnesium")] == []

        # The compound row is still emitted for display/evidence, but its
        # UL check is skipped with an explicit machine-readable reason.
        rda_rows = result.get("analyzed_ingredients", [])
        compound = [r for r in rda_rows if r.get("ingredient") == "Magnesium Glycinate"]
        assert compound and compound[0]["skip_ul_check"] is True
        assert compound[0]["skip_ul_reason"] == "compound_duplicate_row"

        bare = [r for r in rda_rows if r.get("ingredient") == "Magnesium"]
        assert bare and bare[0]["skip_ul_check"] is False

    def test_counterion_named_source_compound_is_not_a_second_stack_dose(
        self,
        enricher,
    ) -> None:
        rows = [
            {"name": "Vitamin C", "standardName": "Vitamin C",
             "canonical_id": "vitamin_c", "quantity": 900.0, "unit": "mg"},
            {"name": "Calcium", "standardName": "Calcium",
             "canonical_id": "calcium", "quantity": 90.0, "unit": "mg"},
            {"name": "Calcium Ascorbate", "standardName": "Vitamin C",
             "canonical_id": "vitamin_c", "quantity": 1000.0, "unit": "mg"},
        ]

        result = enricher._collect_rda_ul_data(
            {"activeIngredients": rows, "inactiveIngredients": []},
            min_servings_per_day=1,
            max_servings_per_day=1,
        )

        analyzed = result["analyzed_ingredients"]
        compound = next(
            row for row in analyzed if row["ingredient"] == "Calcium Ascorbate"
        )
        assert compound["skip_ul_check"] is True
        assert compound["skip_ul_reason"] == "compound_duplicate_row"

    def test_true_over_ul_on_bare_row_still_flags(self, enricher) -> None:
        # The dedupe must never mask a REAL breach: a bare elemental row
        # over the UL still flags.
        rows = _mag_rows()
        rows[0]["quantity"] = 600.0  # > 350 mg supplemental UL
        product = {"activeIngredients": rows, "inactiveIngredients": []}
        result = enricher._collect_rda_ul_data(
            product, min_servings_per_day=1, max_servings_per_day=1
        )
        flags = [
            f for f in result.get("safety_flags", [])
            if (f.get("nutrient") or "").lower().startswith("magnesium")
        ]
        assert len(flags) == 1
        assert flags[0]["amount"] == 600.0
