"""Regression tests for _compute_delivers_markers (Phase 4 of identity_bioactivity_split).

Tests cover both clinical models (default_contribution + standardization_required)
across the 9 source botanicals in botanical_marker_contributions.json. Asserts
estimated_dose_mg, estimation_method, confidence_scale, and evidence provenance.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


@pytest.fixture(scope="module")
def enricher():
    from enrich_supplements_v3 import SupplementEnricherV3
    return SupplementEnricherV3()


# -----------------------------------------------------------------------------
# default_contribution model — USDA-cited per-gram nutrient
# -----------------------------------------------------------------------------

def test_acerola_no_standardization_uses_default_contribution(enricher):
    """Bare acerola → vitamin_c at USDA default 16 mg/g × ingredient mass."""
    ing = {
        "canonical_id": "acerola_cherry",
        "raw_source_text": "Acerola Cherry Extract",
        "quantity": 50, "unit_normalized": "mg",
    }
    markers = enricher._compute_delivers_markers(ing)
    assert len(markers) == 1
    m = markers[0]
    assert m["marker_canonical_id"] == "vitamin_c"
    assert m["estimation_method"] == "default_contribution"
    assert m["confidence_scale"] == 0.7
    # 16 mg/g × 0.05 g = 0.8 mg
    assert m["estimated_dose_mg"] == pytest.approx(0.8, rel=0.01)
    assert m["evidence_id"].startswith("USDA_FDC:")
    assert "fdc.nal.usda.gov" in m["evidence_url"]


def test_acerola_with_standardization_overrides_default(enricher):
    """When label declares standardization, use it (preferable to default)."""
    ing = {
        "canonical_id": "acerola_cherry",
        "raw_source_text": "Acerola Cherry Extract std. 25% Vitamin C",
        "quantity": 50, "unit_normalized": "mg",
    }
    markers = enricher._compute_delivers_markers(ing)
    m = markers[0]
    assert m["estimation_method"] == "standardization_pct"
    assert m["confidence_scale"] == 1.0
    # 25% of 50 mg = 12.5 mg
    assert m["estimated_dose_mg"] == pytest.approx(12.5, rel=0.01)


def test_tomato_default_contribution_lycopene(enricher):
    """Tomato 1g → 0.218 mg lycopene (USDA puree value, μg→mg converted)."""
    ing = {
        "canonical_id": "tomato",
        "raw_source_text": "Tomato powder",
        "quantity": 1, "unit_normalized": "g",
    }
    markers = enricher._compute_delivers_markers(ing)
    assert len(markers) == 1
    m = markers[0]
    assert m["marker_canonical_id"] == "lycopene"
    assert m["estimation_method"] == "default_contribution"
    assert m["estimated_dose_mg"] == pytest.approx(0.218, rel=0.01)


# -----------------------------------------------------------------------------
# standardization_required model — PMID-cited, only credits if label declares
# -----------------------------------------------------------------------------

def test_turmeric_no_standardization_no_dose_credit(enricher):
    """Bare turmeric label MUST get marker entry with estimation_method='none' and
    confidence_scale=0.0 — no Section C dose credit allowed per Dr. Pham policy."""
    ing = {
        "canonical_id": "turmeric",
        "raw_source_text": "Turmeric (root) extract",
        "quantity": 400, "unit_normalized": "mg",
    }
    markers = enricher._compute_delivers_markers(ing)
    assert len(markers) == 1
    m = markers[0]
    assert m["marker_canonical_id"] == "curcumin"
    assert m["estimation_method"] == "none"
    assert m["confidence_scale"] == 0.0
    assert m["estimated_dose_mg"] is None
    # Evidence still cited (provenance)
    assert m["evidence_id"].startswith("PMID:")


def test_turmeric_with_95pct_curcuminoids_credits_marker(enricher):
    """Standardized 95% turmeric → 380 mg curcumin at full confidence."""
    ing = {
        "canonical_id": "turmeric",
        "raw_source_text": "Turmeric Extract standardized to 95% curcuminoids",
        "quantity": 400, "unit_normalized": "mg",
    }
    markers = enricher._compute_delivers_markers(ing)
    m = markers[0]
    assert m["estimation_method"] == "standardization_pct"
    assert m["confidence_scale"] == 1.0
    assert m["estimated_dose_mg"] == pytest.approx(380.0, rel=0.01)


def test_broccoli_sprout_no_standardization_no_credit(enricher):
    ing = {
        "canonical_id": "broccoli_sprout",
        "raw_source_text": "Broccoli Sprout Powder",
        "quantity": 200, "unit_normalized": "mg",
    }
    markers = enricher._compute_delivers_markers(ing)
    m = markers[0]
    assert m["marker_canonical_id"] == "sulforaphane"
    assert m["confidence_scale"] == 0.0
    assert m["estimated_dose_mg"] is None


def test_broccoli_sprout_with_glucoraphanin_standardization_credits(enricher):
    ing = {
        "canonical_id": "broccoli_sprout",
        "raw_source_text": "Broccoli Sprout Extract standardized to 13% glucoraphanin",
        "quantity": 200, "unit_normalized": "mg",
    }
    markers = enricher._compute_delivers_markers(ing)
    m = markers[0]
    assert m["estimation_method"] == "standardization_pct"
    assert m["estimated_dose_mg"] == pytest.approx(26.0, rel=0.01)
    assert m["confidence_scale"] == 1.0


def test_cayenne_no_standardization_no_credit(enricher):
    ing = {
        "canonical_id": "cayenne_pepper",
        "raw_source_text": "Cayenne Pepper Powder",
        "quantity": 100, "unit_normalized": "mg",
    }
    markers = enricher._compute_delivers_markers(ing)
    m = markers[0]
    assert m["marker_canonical_id"] == "capsaicin"
    assert m["confidence_scale"] == 0.0


def test_horse_chestnut_with_20pct_aescin_credits(enricher):
    """Industry-standard 20% aescin standardization."""
    ing = {
        "canonical_id": "horse_chestnut_seed",
        "raw_source_text": "Horse Chestnut Extract standardized to 20% aescin",
        "quantity": 300, "unit_normalized": "mg",
    }
    markers = enricher._compute_delivers_markers(ing)
    m = markers[0]
    assert m["marker_canonical_id"] == "aescin"
    assert m["estimation_method"] == "standardization_pct"
    # 20% × 300 mg = 60 mg
    assert m["estimated_dose_mg"] == pytest.approx(60.0, rel=0.01)


def test_japanese_knotweed_with_50pct_resveratrol_credits(enricher):
    ing = {
        "canonical_id": "japanese_knotweed",
        "raw_source_text": "Polygonum cuspidatum extract std. 50% trans-resveratrol",
        "quantity": 200, "unit_normalized": "mg",
    }
    markers = enricher._compute_delivers_markers(ing)
    m = markers[0]
    assert m["marker_canonical_id"] == "resveratrol"
    assert m["estimation_method"] == "standardization_pct"
    # 50% × 200 mg = 100 mg
    assert m["estimated_dose_mg"] == pytest.approx(100.0, rel=0.01)


# -----------------------------------------------------------------------------
# Negative cases — markers and unmapped get no contributions
# -----------------------------------------------------------------------------

def test_vitamin_c_marker_no_self_contribution(enricher):
    """A vitamin_c marker ingredient must NOT have a self-contribution entry."""
    ing = {
        "canonical_id": "vitamin_c",
        "raw_source_text": "Vitamin C (ascorbic acid)",
        "quantity": 500, "unit_normalized": "mg",
    }
    assert enricher._compute_delivers_markers(ing) == []


def test_unknown_canonical_returns_empty(enricher):
    ing = {
        "canonical_id": "unknown_botanical_xyz",
        "raw_source_text": "Some random extract",
        "quantity": 100, "unit_normalized": "mg",
    }
    assert enricher._compute_delivers_markers(ing) == []


def test_missing_canonical_id_returns_empty(enricher):
    ing = {"raw_source_text": "Unmapped Ingredient", "quantity": 100, "unit_normalized": "mg"}
    assert enricher._compute_delivers_markers(ing) == []


# -----------------------------------------------------------------------------
# Edge cases — missing mass, unknown units
# -----------------------------------------------------------------------------

def test_missing_quantity_default_contribution_provenance_only(enricher):
    """No quantity → default_contribution model still attaches marker but with
    estimation_method='default_contribution' and confidence_scale=0.4 (no dose)."""
    ing = {
        "canonical_id": "acerola_cherry",
        "raw_source_text": "Acerola Cherry Extract",
        "quantity": None, "unit_normalized": "mg",
    }
    markers = enricher._compute_delivers_markers(ing)
    m = markers[0]
    assert m["estimation_method"] == "default_contribution"
    assert m["confidence_scale"] == 0.4
    assert m["estimated_dose_mg"] is None
    assert "not computable" in m["basis"].lower()


def test_unsupported_unit_no_dose(enricher):
    """Units we can't convert (IU, %, etc.) yield no dose."""
    ing = {
        "canonical_id": "tomato",
        "raw_source_text": "Tomato extract",
        "quantity": 5, "unit_normalized": "IU",
    }
    markers = enricher._compute_delivers_markers(ing)
    m = markers[0]
    assert m["estimated_dose_mg"] is None
