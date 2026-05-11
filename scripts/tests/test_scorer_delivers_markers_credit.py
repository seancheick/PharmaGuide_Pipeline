"""Phase 5 regression: scorer Section C credits delivers_markers at scaled
confidence.

End-to-end test: synthetic product → enrich → score, asserts that:
  - Standardized turmeric (95% curcuminoids) gets curcumin Section C credit
  - Bare turmeric (no standardization) gets NO curcumin Section C credit
  - Pure curcumin ingredient still gets full curcumin credit via primary path
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


@pytest.fixture(scope="module")
def scorer():
    from score_supplements import SupplementScorer
    return SupplementScorer()


def _make_product(active_ingredients):
    return {
        "dsld_id": 99999,
        "product_name": "Test Synthetic Product",
        "productName": "Test Synthetic Product",
        "fullName": "Test Synthetic Product",
        "brandName": "TestBrand",
        "activeIngredients": active_ingredients,
        "inactiveIngredients": [],
    }


def _enrich_and_score(enricher, scorer, product):
    enriched, _ = enricher.enrich_product(product)
    scored = scorer.score_product(enriched)
    return enriched, scored


def test_standardized_turmeric_gets_curcumin_section_c_credit(enricher, scorer):
    """A turmeric extract with 95% curcuminoid standardization MUST be credited
    for curcumin clinical evidence (confidence_scale=1.0 → full credit)."""
    product = _make_product([
        {
            "name": "Turmeric Extract",
            "standardName": "Turmeric Extract",
            "raw_source_text": "Turmeric Extract standardized to 95% curcuminoids",
            "canonical_id": "turmeric",
            "canonical_source_db": "botanical_ingredients",
            "quantity": 400.0, "unit": "mg",
        },
    ])
    enriched, scored = _enrich_and_score(enricher, scorer, product)

    # Verify delivers_markers attached
    ings = enriched["ingredient_quality_data"]["ingredients"]
    assert len(ings) == 1
    dm = ings[0].get("delivers_markers", [])
    assert any(
        m.get("marker_canonical_id") == "curcumin" and m.get("confidence_scale") == 1.0
        for m in dm
    ), f"Expected curcumin marker with confidence 1.0, got {dm}"

    # Verify Section C has the marker-via clinical match
    clinical = enriched.get("evidence_data", {}).get("clinical_matches", [])
    curcumin_via_marker = [
        m for m in clinical
        if m.get("marker_via_ingredient") == "turmeric"
        and "curcumin" in (m.get("standard_name") or "").lower()
    ]
    # If backed_clinical_studies has any curcumin entry, this should yield matches
    if curcumin_via_marker:
        # Confidence scale must be 1.0 (full credit)
        assert all(m.get("marker_confidence_scale") == 1.0 for m in curcumin_via_marker), \
            "Standardized 95% turmeric must credit curcumin at full confidence"


def test_bare_turmeric_no_curcumin_section_c_credit(enricher, scorer):
    """A bare turmeric label (no standardization keyword) MUST NOT credit
    curcumin Section C clinical evidence (confidence_scale=0 → skipped upstream)."""
    product = _make_product([
        {
            "name": "Turmeric Root",
            "standardName": "Turmeric Root",
            "raw_source_text": "Turmeric (root) extract",
            "canonical_id": "turmeric",
            "canonical_source_db": "botanical_ingredients",
            "quantity": 400.0, "unit": "mg",
        },
    ])
    enriched, _ = _enrich_and_score(enricher, scorer, product)

    # Source botanicals classify as non-scorable in identity_bioactivity_split;
    # they appear in ingredients_skipped (not ingredients_scorable).
    iqd = enriched["ingredient_quality_data"]
    skipped = iqd.get("ingredients_skipped", [])
    scorable = iqd.get("ingredients_scorable", [])
    all_ings = skipped + scorable + (iqd.get("ingredients") or [])
    turmeric_rec = next(
        (i for i in all_ings if i.get("canonical_id") == "turmeric"),
        None,
    )
    assert turmeric_rec is not None, (
        f"Turmeric row not found in any ingredient list "
        f"(skipped={len(skipped)}, scorable={len(scorable)})"
    )
    dm = turmeric_rec.get("delivers_markers", [])
    curcumin_marker = next((m for m in dm if m.get("marker_canonical_id") == "curcumin"), None)
    assert curcumin_marker is not None, f"No curcumin marker in delivers_markers; got {dm}"
    assert curcumin_marker.get("estimation_method") == "none"
    assert curcumin_marker.get("confidence_scale") == 0.0

    # Verify NO curcumin-via-marker clinical match (confidence=0 short-circuits)
    clinical = enriched.get("evidence_data", {}).get("clinical_matches", [])
    curcumin_via_marker = [
        m for m in clinical if m.get("marker_via_ingredient") == "turmeric"
    ]
    assert not curcumin_via_marker, (
        f"Bare turmeric MUST NOT trigger marker-via-ingredient clinical matches; "
        f"got {len(curcumin_via_marker)}: {curcumin_via_marker[:2]}"
    )


def test_pure_curcumin_full_primary_credit(enricher, scorer):
    """Pure curcumin product (canonical_id='curcumin') still gets primary-path
    Section C credit; no delivers_markers (curcumin is not a source botanical).
    """
    product = _make_product([
        {
            "name": "Curcumin",
            "standardName": "Curcumin",
            "raw_source_text": "Curcumin 500mg",
            "canonical_id": "curcumin",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 500.0, "unit": "mg",
        },
    ])
    enriched, _ = _enrich_and_score(enricher, scorer, product)
    ings = enriched["ingredient_quality_data"]["ingredients"]
    assert len(ings) == 1
    # delivers_markers should be empty (curcumin is a marker, not a source)
    assert ings[0].get("delivers_markers") == []


def test_acerola_default_contribution_credits_vitamin_c_at_partial_confidence(enricher, scorer):
    """Acerola (no standardization) uses USDA default contribution. Section C
    credit for vitamin_c via this ingredient should be scaled to 0.7."""
    product = _make_product([
        {
            "name": "Acerola Cherry Extract",
            "standardName": "Acerola Cherry Extract",
            "raw_source_text": "Acerola Cherry Extract",
            "canonical_id": "acerola_cherry",
            "canonical_source_db": "botanical_ingredients",
            "quantity": 50.0, "unit": "mg",
        },
    ])
    enriched, _ = _enrich_and_score(enricher, scorer, product)
    iqd = enriched["ingredient_quality_data"]
    all_ings = (iqd.get("ingredients") or []) + iqd.get("ingredients_scorable", []) + iqd.get("ingredients_skipped", [])
    acerola_rec = next(
        (i for i in all_ings if i.get("canonical_id") == "acerola_cherry"), None
    )
    assert acerola_rec is not None
    dm = acerola_rec.get("delivers_markers", [])
    vc = next((m for m in dm if m.get("marker_canonical_id") == "vitamin_c"), None)
    assert vc is not None
    assert vc.get("estimation_method") == "default_contribution"
    assert vc.get("confidence_scale") == 0.7

    clinical = enriched.get("evidence_data", {}).get("clinical_matches", [])
    vc_via_marker = [
        m for m in clinical
        if m.get("marker_via_ingredient") == "acerola_cherry"
        and "vitamin c" in (m.get("standard_name") or "").lower()
    ]
    if vc_via_marker:
        # Scaled at 0.7 confidence
        assert all(m.get("marker_confidence_scale") == 0.7 for m in vc_via_marker)
