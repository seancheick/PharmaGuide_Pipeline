"""D2.10 — a "from X" child row is provenance of its parent, not an unmapped active.

GNC 31147 lists ``EGCG 50 mg`` with a nested ``from Green Tea Leaf Extract
56 mg``. The child names where the parent came from; its quantity is the
parent extract's weight. It must be recognised as a source descriptor (so it
does not count as an unmapped active in coverage) and must never become a
scorable active of its own — whatever its quantity.

This replaces six tests that only grepped the enricher's source text for the
branch's identifiers: they stayed green whether or not the route still fired.
"""

from __future__ import annotations

import pytest

from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v3 import SupplementEnricherV3
from tests.test_clinical_signoff_engineering_fixes_20260919 import _make_dsld_product, _row


@pytest.fixture(scope="module")
def enriched_31147_shape() -> dict:
    rows = [
        _row("EGCG", 50, "mg", category="non-nutrient/non-botanical", ingredientGroup="EGCG",
             nestedRows=[_row("from Green Tea Leaf Extract", 56, "mg", category="botanical",
                              ingredientGroup="Green Tea")]),
    ]
    product = _make_dsld_product(990210, "D2.10 canary", rows)
    product["physicalState"] = {"langualCode": "E0159", "langualCodeDescription": "Softgel"}  # DSLD shape
    cleaned = EnhancedDSLDNormalizer().normalize_product(product)
    enriched, _ = SupplementEnricherV3().enrich_product(cleaned)
    return enriched


def _source_rows(enriched: dict) -> list[dict]:
    iqd = enriched.get("ingredient_quality_data") or {}
    return [
        row
        for key in ("ingredients", "ingredients_skipped", "ingredients_scorable")
        for row in iqd.get(key) or []
        if str(row.get("raw_source_text") or row.get("name") or "").lower().startswith("from ")
    ]


def test_from_prefix_child_is_a_recognised_source_descriptor(enriched_31147_shape) -> None:
    rows = _source_rows(enriched_31147_shape)
    assert rows, "the 'from Green Tea Leaf Extract' child disappeared from the enriched rows"
    assert {row.get("recognition_reason") for row in rows} == {"source_descriptor_child_row"}


def test_source_descriptor_child_is_never_scorable_even_with_a_quantity(enriched_31147_shape) -> None:
    iqd = enriched_31147_shape.get("ingredient_quality_data") or {}
    scorable = [
        row for row in iqd.get("ingredients_scorable") or []
        if str(row.get("raw_source_text") or row.get("name") or "").lower().startswith("from ")
    ]
    assert scorable == []
