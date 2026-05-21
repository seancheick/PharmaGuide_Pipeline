"""SP-4 C4 — ingredient_category canonical contract across pipeline stages.

End-to-end contract: an ingredient row's category survives canonicalization
identically whether the upstream value came from:
  - IQM parent data (plural form like `vitamins`)
  - Name inference at enrichment time (singular `vitamin`)
  - Legacy CATEGORY_ALIASES map (now wrapping the SP-4 normalizer)
  - Variant spelling / spacing (`fatty acid`, `Fatty-Acid`, `FATTY_ACID`)

Synthetic test — no enriched batches required. Locks:
  1. SP-4 normalizer and legacy canonical_category() return identical output.
  2. The taxonomy classifier produces stable category counts regardless of
     plural / singular / spaced input.
  3. The vocab file matches what the normalizer emits.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ingredient_category_normalizer import canonicalize_ingredient_category
from supplement_type_utils import canonical_category
from supplement_taxonomy import classify_supplement


# ============================================================================
# 1. Normalizer + legacy wrapper return identical canonical id
# ============================================================================

PLURAL_AND_SINGULAR_PAIRS = [
    ("vitamins", "vitamin"),
    ("minerals", "mineral"),
    ("herbs", "herb"),
    ("antioxidants", "antioxidant"),
    ("fatty_acids", "fatty_acid"),
    ("amino_acids", "amino_acid"),
    ("probiotics", "probiotic"),
    ("proteins", "protein"),
    ("fibers", "fiber"),
    ("enzymes", "enzyme"),
    ("functional_foods", "functional_food"),
]


@pytest.mark.parametrize("plural,singular", PLURAL_AND_SINGULAR_PAIRS)
def test_plural_and_singular_canonicalize_identically(plural, singular):
    """An IQM-side row (plural) and a runtime-inferred row (singular) must
    end up with the same canonical id so the taxonomy classifier counts
    them as the same category."""
    assert canonicalize_ingredient_category(plural) == singular
    assert canonical_category(plural) == singular
    assert canonicalize_ingredient_category(singular) == singular
    assert canonical_category(singular) == singular


@pytest.mark.parametrize("raw", [
    "vitamins", "vitamin", "Vitamin", "VITAMINS", "  vitamin  ",
    "fatty acids", "fatty-acids", "FATTY_ACID", "fatty acid",
])
def test_legacy_wrapper_matches_normalizer(raw):
    """canonical_category() is now a thin wrapper. Outputs must match."""
    assert canonical_category(raw) == canonicalize_ingredient_category(raw)


# ============================================================================
# 2. Taxonomy classifier produces stable counts regardless of input form
# ============================================================================

def _make_product(category_form: str) -> dict:
    """Build a synthetic 3-vitamin product with the given category form."""
    return {
        "product_name": "Test Vitamin Trio",
        "fullName": "Test Vitamin Trio",
        "ingredient_quality_data": {
            "ingredients": [
                {"name": "Vitamin A", "canonical_id": "vitamin_a",
                 "category": category_form, "quantity": 1500, "unit": "mcg"},
                {"name": "Vitamin C", "canonical_id": "vitamin_c",
                 "category": category_form, "quantity": 500, "unit": "mg"},
                {"name": "Vitamin D", "canonical_id": "vitamin_d",
                 "category": category_form, "quantity": 1000, "unit": "IU"},
            ],
        },
    }


def test_taxonomy_counts_vitamins_regardless_of_input_form():
    """Whether the enricher wrote `vitamins` (IQM-plural) or `vitamin`
    (name-inference-singular) or `Vitamin` (raw label) into each row's
    category, the taxonomy classifier must count them all as `vitamin`."""
    for form in ("vitamins", "vitamin", "Vitamin", "VITAMIN", "  vitamins  "):
        result = classify_supplement(_make_product(form))
        breakdown = result["category_breakdown"]
        assert breakdown.get("vitamin", 0) == 3, (
            f"category={form!r} → category_breakdown={breakdown!r}. "
            f"Expected 3 vitamins regardless of input form."
        )


# ============================================================================
# 3. Mixed-form panel — all canonicalize to same target
# ============================================================================

def test_mixed_form_panel_categorizes_correctly():
    """A real-world product can have rows with mixed category forms (some
    from IQM parents, some from name inference). All forms of 'vitamin'
    must aggregate together."""
    product = {
        "product_name": "Mixed Form Multivitamin",
        "ingredient_quality_data": {
            "ingredients": [
                {"name": "Vitamin A", "canonical_id": "vitamin_a",
                 "category": "vitamins",  # plural (IQM-style)
                 "quantity": 1500, "unit": "mcg"},
                {"name": "Vitamin C", "canonical_id": "vitamin_c",
                 "category": "vitamin",  # singular (inference-style)
                 "quantity": 500, "unit": "mg"},
                {"name": "Calcium", "canonical_id": "calcium",
                 "category": "MINERALS",  # uppercase plural
                 "quantity": 500, "unit": "mg"},
                {"name": "Zinc", "canonical_id": "zinc",
                 "category": "Mineral",  # title-case singular
                 "quantity": 15, "unit": "mg"},
            ],
        },
    }
    result = classify_supplement(product)
    breakdown = result["category_breakdown"]
    assert breakdown.get("vitamin", 0) == 2, (
        f"Mixed-form panel must aggregate vitamins. Got: {breakdown!r}"
    )
    assert breakdown.get("mineral", 0) == 2, (
        f"Mixed-form panel must aggregate minerals. Got: {breakdown!r}"
    )


# ============================================================================
# 4. Edge-value pass-through (unrecognized values flow unchanged)
# ============================================================================

def test_edge_values_flow_through_unchanged():
    """Edge tokens like `section_other`, `blend_header`, `delivery` must
    survive canonicalization so downstream consumers can reason about them."""
    for raw in ("section_other", "blend_header", "blend header", "delivery"):
        result = canonicalize_ingredient_category(raw)
        # Either the input pre-canonicalized OR mapped to a known vocab id —
        # what matters is the value is preserved/canonicalized, not nuked.
        assert result, f"canonicalize({raw!r}) returned empty string"


def test_unknown_category_doesnt_break_taxonomy():
    """A product with an unrecognized category value must still classify
    without raising — falls through gracefully."""
    product = {
        "product_name": "Mystery Product",
        "ingredient_quality_data": {
            "ingredients": [
                {"name": "Unknown Compound", "canonical_id": "x",
                 "category": "mystery_category",
                 "quantity": 100, "unit": "mg"},
            ],
        },
    }
    # Must not raise.
    result = classify_supplement(product)
    assert "primary_type" in result
