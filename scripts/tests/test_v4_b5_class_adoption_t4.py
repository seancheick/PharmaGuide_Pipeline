"""SP-2 T4 — ADOPT-4 regression test for `generic_transparency._b5_class_for_product`.

Before T4: this function was a parallel classifier — it independently
re-inferred class from `supplement_type`, `primary_category`, and name
regex. Sean's central constraint (SP-0 design doc): "Do not create a
parallel classifier."

After T4: this function delegates to `router.class_for_product` (the
canonical taxonomy-first decision surface) and adds two B5-specific
overlays:
  1. Sports-keyword override → `sports_active` (B5 has this tier; the
     router does not — sports stacks score against the generic module
     but get their own opacity multiplier).
  2. Map router's `omega` scoring class → `generic` opacity tier.
     B5 doesn't separate omega; it rolls into generic with a 1.0x
     multiplier instead of multi's 1.3x.

The four B5 opacity tiers (with their B5_CLASS_MULTIPLIERS):
  probiotic         (0.4x) — same as router
  multi_or_prenatal (1.3x) — same as router
  sports_active     (1.5x) — B5-only; router has no sports class
  generic           (1.0x) — fallback / omega / collagen / single-actives
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scoring_v4.modules.generic_transparency import _b5_class_for_product


# --- Probiotic ---

def test_probiotic_taxonomy_returns_probiotic():
    product = {
        "primary_type": "probiotic",
        "product_name": "Daily Probiotic 50B CFU",
    }
    assert _b5_class_for_product(product) == "probiotic"


def test_probiotic_legacy_supp_type_is_not_routing_contract():
    """Legacy supp_type alone must not restore downstream classification."""
    product = {
        "supplement_type": {"type": "probiotic"},
        "product_name": "Daily Probiotic",
    }
    assert _b5_class_for_product(product) == "generic"


# --- Multi / prenatal ---

def test_multivitamin_taxonomy_returns_multi():
    product = {
        "primary_type": "multivitamin",
        "product_name": "Daily Women's Multi",
    }
    assert _b5_class_for_product(product) == "multi_or_prenatal"


def test_b_complex_taxonomy_returns_multi():
    """B-complex is a multi-vitamin variant in the router mapping."""
    product = {
        "primary_type": "b_complex",
        "product_name": "B-Complex 50",
    }
    assert _b5_class_for_product(product) == "multi_or_prenatal"


def test_prenatal_dha_name_without_multi_panel_does_not_force_multi():
    """Prenatal wording alone is not enough to force the multi rubric."""
    product = {
        "primary_type": "omega_3",  # taxonomy says omega
        "product_name": "Prenatal DHA Gummies",
    }
    assert _b5_class_for_product(product) == "generic"


# --- Sports (B5-only override) ---

def test_sports_pre_workout_returns_sports():
    product = {
        "primary_type": "pre_workout",
        "product_name": "Pre-Workout Powder Citrus Burst",
    }
    assert _b5_class_for_product(product) == "sports_active"


def test_sports_whey_protein_returns_sports():
    product = {
        "primary_type": "protein_powder",
        "product_name": "Whey Protein Isolate Vanilla",
    }
    assert _b5_class_for_product(product) == "sports_active"


def test_sports_creatine_returns_sports():
    product = {
        "primary_type": "amino_acid",
        "product_name": "Creatine Monohydrate Powder",
    }
    assert _b5_class_for_product(product) == "sports_active"


def test_sports_keyword_overrides_multivitamin():
    """Sports keyword wins over multivit name when product is a sports stack."""
    product = {
        "primary_type": "multivitamin",
        "product_name": "Sports Multivitamin Pre-Workout Stack",
    }
    assert _b5_class_for_product(product) == "sports_active"


# --- Omega → generic (B5 rollup) ---

def test_omega_3_returns_generic_opacity():
    """Router routes omega to its own scoring module; B5 maps that to
    generic opacity (1.0x) because B5 has no omega tier."""
    product = {
        "primary_type": "omega_3",
        "product_name": "Fish Oil 1000 mg",
    }
    assert _b5_class_for_product(product) == "generic"


# --- Generic catch-all + GENERIC_OVERRIDE behavior preservation ---

def test_collagen_returns_generic():
    """Pre-T4 the GENERIC_OVERRIDE_PRIMARY_CATEGORIES included `collagen`
    to send it to generic. With router/taxonomy, collagen products route
    to generic naturally."""
    product = {
        "primary_type": "collagen",
        "product_name": "Marine Collagen Peptides",
    }
    assert _b5_class_for_product(product) == "generic"


def test_joint_support_returns_generic():
    """Joint products with multi-style names like 'Daily Joint Complete'
    were previously routed to generic via GENERIC_OVERRIDE_KEYWORDS. With
    taxonomy, joint_support → router=generic → opacity=generic."""
    product = {
        "primary_type": "joint_support",
        "product_name": "Daily Joint Complete with Glucosamine",
    }
    assert _b5_class_for_product(product) == "generic"


def test_single_vitamin_returns_generic():
    product = {
        "primary_type": "single_vitamin",
        "product_name": "Vitamin D3 1000 IU",
    }
    assert _b5_class_for_product(product) == "generic"


def test_general_supplement_returns_generic():
    product = {
        "primary_type": "general_supplement",
        "product_name": "Mystery Supplement",
    }
    assert _b5_class_for_product(product) == "generic"


# --- Edge cases ---

def test_empty_product_returns_generic():
    assert _b5_class_for_product({}) == "generic"


def test_old_batch_legacy_multivit_does_not_recompute_multi():
    """Legacy supp_type alone must not route B5 opacity as multivitamin."""
    product = {
        "supplement_type": {"type": "multivitamin"},
        "product_name": "Daily Multi",
    }
    assert _b5_class_for_product(product) == "generic"


def test_old_batch_supp_type_specialty_returns_generic():
    """Pre-T4 the supp_type=specialty branch was confused; with router
    delegation, specialty alone routes to generic."""
    product = {
        "supplement_type": {"type": "specialty"},
        "product_name": "Hum Collagen Love",
    }
    assert _b5_class_for_product(product) == "generic"


# --- Probiotic > prenatal priority lock ---

def test_probiotic_prenatal_combo_returns_probiotic():
    """Probiotic priority is absolute — even with prenatal name keyword,
    probiotic taxonomy wins."""
    product = {
        "primary_type": "probiotic",
        "product_name": "Prenatal Probiotic Blend",
    }
    assert _b5_class_for_product(product) == "probiotic"
