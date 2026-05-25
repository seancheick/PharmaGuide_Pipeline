"""SP-2.7 v3 _b5_class_for_product taxonomy-first migration.

Before this commit: v3 _b5_class_for_product read only `supplement_type` /
`primary_category` / product-name keywords (the parallel-classifier pattern
identical to what v4 ADOPT-4 just killed).

After this commit: the v3 method reads `supplement_taxonomy.primary_type`
as the canonical signal first. Legacy fields remain as fallback for old
enriched batches that lack the taxonomy.

Locks the following behaviors:
  - Taxonomy primary_type=probiotic → probiotic
  - Taxonomy primary_type in {multivitamin, b_complex} → multi_or_prenatal
  - Taxonomy primary_type=omega_3 → generic (B5 has no omega tier)
  - Taxonomy primary_type=collagen / joint_support / etc → generic
  - Prenatal name keyword overrides taxonomy=omega_3 (prenatal DHA case)
  - Sports keyword still beats multi mapping
  - Probiotic wins only for explicit probiotic taxonomy/legacy type, or for
    underclassified general_supplement rows with shipped probiotic flags
  - Old-batch fallback (no taxonomy) preserves the v3 legacy paths
    including GENERIC_OVERRIDE for collagen/enzyme/joint/omega keywords
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from score_supplements import SupplementScorer


@pytest.fixture(scope="module")
def scorer() -> SupplementScorer:
    return SupplementScorer()


def _product(
    *,
    primary_type=None,
    supp_type=None,
    primary_category=None,
    product_name="Example Product",
    brand_name="Example Brand",
) -> dict:
    p = {
        "product_name": product_name,
        "fullName": f"{brand_name} {product_name}",
        "brand_name": brand_name,
    }
    if primary_type is not None:
        p["primary_type"] = primary_type
        p["supplement_taxonomy"] = {"primary_type": primary_type}
    if supp_type is not None:
        p["supplement_type"] = {"type": supp_type, "active_count": 5}
    if primary_category is not None:
        p["primary_category"] = primary_category
    return p


# --- Taxonomy primary_type is the canonical signal ---

def test_taxonomy_probiotic_returns_probiotic(scorer):
    assert scorer._b5_class_for_product(_product(primary_type="probiotic")) == "probiotic"


def test_taxonomy_multivitamin_returns_multi(scorer):
    assert scorer._b5_class_for_product(_product(primary_type="multivitamin")) == "multi_or_prenatal"


def test_taxonomy_b_complex_returns_multi(scorer):
    """B-complex is a multi variant per taxonomy → multi opacity tier."""
    assert scorer._b5_class_for_product(_product(primary_type="b_complex")) == "multi_or_prenatal"


def test_taxonomy_omega_3_returns_generic(scorer):
    """Omega rolls up to generic opacity — B5 has no omega tier."""
    product = _product(primary_type="omega_3", product_name="Fish Oil 1000mg")
    assert scorer._b5_class_for_product(product) == "generic"


def test_taxonomy_collagen_returns_generic(scorer):
    """Collagen products → generic opacity (no separate collagen tier)."""
    product = _product(primary_type="collagen", product_name="Marine Collagen Peptides")
    assert scorer._b5_class_for_product(product) == "generic"


def test_taxonomy_joint_support_returns_generic(scorer):
    product = _product(primary_type="joint_support", product_name="Joint Complete")
    assert scorer._b5_class_for_product(product) == "generic"


def test_taxonomy_single_vitamin_returns_generic(scorer):
    product = _product(primary_type="single_vitamin", product_name="Vitamin D3 1000 IU")
    assert scorer._b5_class_for_product(product) == "generic"


# --- Overlays still fire correctly ---

def test_sports_keyword_beats_taxonomy_multivit(scorer):
    """Sports stack with multivitamin taxonomy → sports_active (1.5x)."""
    product = _product(primary_type="multivitamin", product_name="Pre-Workout Multi Stack")
    assert scorer._b5_class_for_product(product) == "sports_active"


def test_probiotic_taxonomy_beats_prenatal_name(scorer):
    """Probiotic priority is absolute — prenatal name does not override."""
    product = _product(primary_type="probiotic", product_name="Prenatal Probiotic Blend")
    assert scorer._b5_class_for_product(product) == "probiotic"


def test_prenatal_dha_keeps_omega_3_b5_class(scorer):
    """Prenatal DHA: structurally a single-active omega-3 product, not a
    multi-vitamin panel. Even though the name carries "Prenatal", the
    product has no vitamin/mineral panel — B5 should route to `generic`
    (the omega opacity tier), not `multi_or_prenatal`.

    Policy change 2026-05-23: the prior expectation that any "Prenatal"
    keyword override the omega taxonomy into multi_or_prenatal was retired.
    It mis-rated single-active prenatal omegas and probiotic-marketed-as-
    prenatal products. Real prenatal multivitamins carry
    primary_type="multivitamin" and still route correctly via Priority 4.
    Locked alongside test_v4_canary_coverage canary 74124 (Nordic Prenatal
    DHA → generic).
    """
    product = _product(primary_type="omega_3", product_name="Prenatal DHA Gummies")
    assert scorer._b5_class_for_product(product) == "generic"


# --- Old-batch fallback (no taxonomy field at all) ---

def test_old_batch_legacy_multivit_still_routes_multi(scorer):
    """No primary_type field — falls through to legacy supp_type."""
    product = _product(supp_type="multivitamin")
    assert scorer._b5_class_for_product(product) == "multi_or_prenatal"


def test_old_batch_legacy_probiotic_still_wins(scorer):
    product = _product(supp_type="probiotic")
    assert scorer._b5_class_for_product(product) == "probiotic"


def test_product_level_probiotic_evidence_overrides_underclassified_taxonomy(scorer):
    """GNC 1650 shape: strict scoring may leave only the prebiotic carrier
    row scorable, so taxonomy exports general_supplement even though
    product-level CFU/strain evidence proves this is a probiotic product."""
    product = _product(
        primary_type="general_supplement",
        supp_type="general_supplement",
        product_name="Ultra Probiotic Rescue & Refresh Kit 150 Billion CFUs",
        brand_name="GNC Probiotics",
    )
    product["probiotic_data"] = {
        "is_probiotic_product": True,
        "total_cfu": 150_000_000_000,
        "total_billion_count": 150.0,
        "total_strain_count": 5,
    }
    assert scorer._b5_class_for_product(product) == "probiotic"


def test_shipped_catalog_probiotic_flags_override_underclassified_taxonomy(scorer):
    """The shipped products_core row has only catalog booleans available;
    the canary gate must still route proven probiotic products correctly."""
    product = _product(
        primary_type=None,
        supp_type="general_supplement",
        primary_category="general_supplement",
        product_name="Ultra Probiotic Rescue & Refresh Kit 150 Billion CFUs",
        brand_name="GNC Probiotics",
    )
    product["is_probiotic"] = 1
    product["contains_probiotics"] = 1
    assert scorer._b5_class_for_product(product) == "probiotic"


def test_probiotic_content_does_not_override_explicit_multivitamin_signal(scorer):
    """Garden greens/multi products can contain probiotic strains, but a real
    multivitamin panel still uses the multi opacity tier."""
    product = _product(
        supp_type="multivitamin",
        primary_category="multivitamin",
        product_name="Raw Organic Perfect Food Green Superfood Chocolate",
        brand_name="Garden of Life",
    )
    product["is_probiotic"] = 1
    product["contains_probiotics"] = 1
    assert scorer._b5_class_for_product(product) == "multi_or_prenatal"


def test_probiotic_content_does_not_override_explicit_greens_taxonomy(scorer):
    """Greens powders can include probiotic rows, but B5 should not apply the
    lighter probiotic opacity multiplier unless the product itself is a
    probiotic. This locks DSLD 204739 after the greens taxonomy refresh."""
    product = _product(
        primary_type="greens_powder",
        supp_type="greens_powder",
        primary_category="greens_powder",
        product_name="Raw Organic Perfect Food Green Superfood Chocolate",
        brand_name="Garden of Life",
    )
    product["is_probiotic"] = 1
    product["contains_probiotics"] = 1
    assert scorer._b5_class_for_product(product) == "generic"


def test_old_batch_primary_category_multivit_fallback(scorer):
    """GoL MyKind pattern — no taxonomy, supp_type=specialty, primary_category=multivitamin."""
    product = _product(supp_type="specialty", primary_category="multivitamin",
                       product_name="MyKind Men's Multi")
    assert scorer._b5_class_for_product(product) == "multi_or_prenatal"


def test_old_batch_unknown_supp_type_returns_generic(scorer):
    product = _product(supp_type=None, product_name="Mystery Supplement")
    assert scorer._b5_class_for_product(product) == "generic"


# --- GENERIC_OVERRIDE safety net (kept for old batches) ---

def test_old_batch_enzyme_with_multivit_supp_routes_generic(scorer):
    """v3 GENERIC_OVERRIDE protects against enzyme products mis-tagged
    multivitamin by the enricher. Preserved when taxonomy absent."""
    product = _product(
        supp_type="multivitamin",
        primary_category="enzymes",
        product_name="Digestive Enzymes Complex",
    )
    assert scorer._b5_class_for_product(product) == "generic"


def test_old_batch_joint_with_multivit_supp_routes_generic(scorer):
    product = _product(
        supp_type="multivitamin",
        primary_category=None,
        product_name="Daily Joint Complete with Glucosamine",
    )
    assert scorer._b5_class_for_product(product) == "generic"
