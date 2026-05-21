"""SP-2 T3 — ADOPT-3 regression test for `generic_trust._is_omega_like`.

Before T3: `_is_omega_like` returned True for ANY product with
`supplement_type.type == "specialty"`. That included everything in the
enricher's catch-all bucket (Collagen Love, Hair Sweet Hair, Counter
Cravings, etc.), causing marine certs to apply incorrectly.

After T3: reads `supplement_taxonomy.primary_type == "omega_3"` first.
Falls back to the ingredient-text physical-fact check (canonical names
mentioning omega / fish oil / krill / cod liver / marine / EPA / DHA),
which is the strong-signal omega detector.

The legacy `supp_type == "specialty"` check is REMOVED — it was a
heuristic that over-fired. Old-batch omega products are still caught by
the ingredient-text fallback because the enricher canonicalizes EPA/DHA
into ingredient names regardless of supp_type.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scoring_v4.modules.generic_trust import _is_omega_like


# --- Taxonomy-first cases ---

def test_taxonomy_omega_3_is_omega_like():
    """Taxonomy primary_type=omega_3 → omega-like, regardless of supp_type."""
    product = {
        "primary_type": "omega_3",
        "supplement_type": {"type": "specialty"},  # legacy noise — ignored
        "ingredient_quality_data": {"ingredients": [
            {"name": "Fish Oil", "canonical_id": "fish_oil", "quantity": 1000, "unit": "mg"},
        ]},
    }
    assert _is_omega_like(product) is True


def test_taxonomy_omega_3_nested_path_works():
    """Reads `supplement_taxonomy.primary_type` as fallback path."""
    product = {
        "supplement_taxonomy": {"primary_type": "omega_3"},
        "ingredient_quality_data": {"ingredients": [
            {"name": "EPA", "canonical_id": "epa", "quantity": 500, "unit": "mg"},
        ]},
    }
    assert _is_omega_like(product) is True


def test_taxonomy_herbal_botanical_is_not_omega_like():
    """Taxonomy classified as herbs → NOT omega-like, even if old supp_type
    was specialty."""
    product = {
        "primary_type": "herbal_botanical",
        "supplement_type": {"type": "specialty"},  # legacy — would have over-fired
        "ingredient_quality_data": {"ingredients": [
            {"name": "Ashwagandha", "canonical_id": "ashwagandha", "quantity": 600, "unit": "mg"},
        ]},
    }
    assert _is_omega_like(product) is False


def test_taxonomy_beauty_is_not_omega_like_despite_specialty():
    """Hum Hair Sweet Hair pattern — taxonomy=beauty, legacy=specialty.
    Pre-T3 this returned True via the supp_type=specialty branch."""
    product = {
        "primary_type": "beauty_hair_skin_nails",
        "supplement_type": {"type": "specialty"},
        "ingredient_quality_data": {"ingredients": [
            {"name": "Biotin", "canonical_id": "biotin", "quantity": 5000, "unit": "mcg"},
        ]},
    }
    assert _is_omega_like(product) is False


def test_taxonomy_collagen_is_not_omega_like_despite_specialty():
    """Hum Collagen Love pattern — taxonomy=general_supplement, legacy=specialty."""
    product = {
        "primary_type": "general_supplement",
        "supplement_type": {"type": "specialty"},
        "ingredient_quality_data": {"ingredients": [
            {"name": "Collagen Peptides", "canonical_id": "collagen", "quantity": 5000, "unit": "mg"},
        ]},
    }
    assert _is_omega_like(product) is False


# --- Old-batch fallback (no taxonomy) cases ---

def test_old_batch_fish_oil_text_is_omega_like():
    """Old batches without taxonomy still detected via ingredient text."""
    product = {
        # no primary_type, no supplement_taxonomy
        "supplement_type": {"type": "specialty"},
        "ingredient_quality_data": {"ingredients": [
            {"name": "Fish Oil Concentrate", "canonical_id": "fish_oil", "quantity": 1200, "unit": "mg"},
            {"name": "EPA", "canonical_id": "epa", "quantity": 650, "unit": "mg"},
            {"name": "DHA", "canonical_id": "dha", "quantity": 450, "unit": "mg"},
        ]},
    }
    assert _is_omega_like(product) is True


def test_old_batch_krill_text_is_omega_like():
    """Krill products detected via ingredient text fallback."""
    product = {
        "supplement_type": {"type": "specialty"},
        "ingredient_quality_data": {"ingredients": [
            {"name": "Krill Oil", "canonical_id": "krill_oil", "quantity": 500, "unit": "mg"},
        ]},
    }
    assert _is_omega_like(product) is True


def test_old_batch_specialty_without_omega_text_is_NOT_omega_like():
    """The critical regression: pre-T3 this returned True (supp_type=specialty).
    Post-T3, supp_type=specialty alone is NOT enough. Must have omega text
    in the canonical ingredient panel."""
    product = {
        "supplement_type": {"type": "specialty"},
        "ingredient_quality_data": {"ingredients": [
            {"name": "Quercetin", "canonical_id": "quercetin", "quantity": 500, "unit": "mg"},
        ]},
    }
    assert _is_omega_like(product) is False, (
        "supp_type='specialty' alone must NOT trigger omega-like. "
        "Pre-T3 this returned True and gave Quercetin products marine cert credit."
    )


# --- Edge cases ---

def test_empty_product_is_not_omega_like():
    assert _is_omega_like({}) is False


def test_none_product_is_not_omega_like():
    # Defensive — should not raise
    assert _is_omega_like(None) is False


def test_marine_keyword_in_ingredient_is_omega_like():
    """Marine source DHA is omega-like because DHA is explicit."""
    product = {
        "ingredient_quality_data": {"ingredients": [
            {"name": "Marine DHA from algae", "canonical_id": "dha", "quantity": 300, "unit": "mg"},
        ]},
    }
    assert _is_omega_like(product) is True


def test_marine_collagen_without_epa_dha_is_not_omega_like():
    """Marine source alone is not enough for omega Trust credit.

    IFOS/FoS/MSC scoring should not attach to marine collagen unless the
    product is actually EPA/DHA/fish-oil/krill/cod-liver omega.
    """
    product = {
        "primary_type": "collagen",
        "ingredient_quality_data": {"ingredients": [
            {"name": "Marine Collagen Peptides", "canonical_id": "collagen", "quantity": 5000, "unit": "mg"},
        ]},
    }
    assert _is_omega_like(product) is False
