#!/usr/bin/env python3
"""Curcumin C3 Complex + Bioperine pairing upgrade in IQM form selection.

Bug discovered 2026-05-25 (Wave 6.Z, Sports_Research DSLD 317006
"Turmeric Curcumin C3 Complex"). The enricher's IQM form matcher selects
the FIRST form-name match by string equality. For C3 Complex + Bioperine
products it picks form `curcumin c3 complex` (bio_score=6) rather than the
more clinically accurate `curcumin c3 complex with bioperine` (bio_score=7),
even though the product clearly contains both ingredients.

The IQM at scripts/data/ingredient_quality_map.json has these two adjacent
forms under parent `curcumin`:
  - `curcumin c3 complex with bioperine` -> bio_score=7
  - `curcumin c3 complex`                -> bio_score=6

CONTRACT
========
When a product's matched IQM identity is parent=`curcumin` with form
`curcumin c3 complex`, AND the product also contains a piperine/Bioperine
row (active or recognized non-scorable absorption enhancer — i.e. any
ingredients[] row with canonical_id=`piperine`), the enricher must upgrade
that row's matched_form/form_id to `curcumin c3 complex with bioperine`
and its bio_score/score to 7.

This is a downstream pairing upgrade; the primary blend_header_total skip
bug for 317006 was fixed in test_curcumin_c3_complex_branded_active_2026_05_25.py.

Negative regression: a C3 Complex product WITHOUT piperine must remain
on bio_score=6. The plain `curcumin c3 complex` form and the
`curcumin (unspecified)` fallback are untouched.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3(
        config_path=str(SCRIPTS_DIR / "config" / "enrichment_config.json")
    )


def _build(name: str, actives: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "dsld_id": 317006,
        "product_name": name,
        "productName": name,
        "fullName": name,
        "brandName": "Sports Research",
        "activeIngredients": actives,
        "inactiveIngredients": [],
    }


def _find_curcumin_row(iqd: Dict[str, Any]) -> Dict[str, Any]:
    """Locate the curcumin row across the union of ingredients lists."""
    seen_ids = set()
    for key in ("ingredients", "ingredients_scorable",
                "ingredients_recognized_non_scorable"):
        for row in iqd.get(key) or []:
            if not isinstance(row, dict):
                continue
            if id(row) in seen_ids:
                continue
            seen_ids.add(id(row))
            if str(row.get("canonical_id") or "").lower() == "curcumin":
                return row
    return {}


# ---------------------------------------------------------------------------
# Primary regression: 317006 shape — C3 Complex + Bioperine
# ---------------------------------------------------------------------------

def test_317006_curcumin_c3_complex_upgrades_to_with_bioperine(enricher):
    """The 317006 shape (Curcumin C3 Complex 500mg + Bioperine 5mg) must
    yield matched_form='curcumin c3 complex with bioperine' bio_score=7."""
    product = _build("Turmeric Curcumin C3 Complex", [
        {"name": "Curcumin C3 Complex", "quantity": 500.0, "unit": "mg"},
        {"name": "Bioperine", "quantity": 5.0, "unit": "mg"},
    ])
    enriched, _ = enricher.enrich_product(product)
    iqd = enriched["ingredient_quality_data"]
    curcumin = _find_curcumin_row(iqd)
    assert curcumin, "Curcumin row not found in enriched output"

    assert curcumin.get("matched_form") == "curcumin c3 complex with bioperine", (
        f"Expected matched_form='curcumin c3 complex with bioperine' "
        f"after Bioperine pairing upgrade. Got "
        f"matched_form={curcumin.get('matched_form')!r}."
    )
    assert curcumin.get("form_id") == "curcumin c3 complex with bioperine", (
        f"form_id must mirror the upgraded matched_form. Got "
        f"form_id={curcumin.get('form_id')!r}."
    )
    assert curcumin.get("bio_score") == 7, (
        f"Expected bio_score=7 (with-bioperine variant). Got "
        f"bio_score={curcumin.get('bio_score')!r}."
    )


def test_317006_upgrade_works_with_piperine_label_name(enricher):
    """Some labels disclose 'Piperine' instead of 'Bioperine'. Both
    resolve to canonical_id='piperine' and must trigger the pairing
    upgrade equally."""
    product = _build("Turmeric Curcumin C3 Complex", [
        {"name": "Curcumin C3 Complex", "quantity": 500.0, "unit": "mg"},
        {"name": "Piperine", "quantity": 5.0, "unit": "mg"},
    ])
    enriched, _ = enricher.enrich_product(product)
    iqd = enriched["ingredient_quality_data"]
    curcumin = _find_curcumin_row(iqd)
    assert curcumin.get("matched_form") == "curcumin c3 complex with bioperine"
    assert curcumin.get("bio_score") == 7


# ---------------------------------------------------------------------------
# Negative regressions: don't upgrade when there's no pairing signal
# ---------------------------------------------------------------------------

def test_curcumin_c3_without_piperine_stays_bio_score_6(enricher):
    """C3 Complex alone — without any piperine/Bioperine row — must NOT
    be upgraded. It stays on the plain `curcumin c3 complex` form
    (bio_score=6)."""
    product = _build("Solo C3", [
        {"name": "Curcumin C3 Complex", "quantity": 500.0, "unit": "mg"},
    ])
    enriched, _ = enricher.enrich_product(product)
    iqd = enriched["ingredient_quality_data"]
    curcumin = _find_curcumin_row(iqd)
    assert curcumin.get("matched_form") == "curcumin c3 complex", (
        f"C3 Complex without piperine must stay 'curcumin c3 complex'. "
        f"Got matched_form={curcumin.get('matched_form')!r}."
    )
    assert curcumin.get("bio_score") == 6


def test_curcumin_unspecified_with_piperine_not_upgraded(enricher):
    """The pairing upgrade is form-specific: it must NOT promote a
    `curcumin (unspecified)` match into the C3-with-bioperine slot.
    Curcumin alone (no C3 Complex token) + Bioperine must remain on
    whatever the matcher chose (typically 'curcumin (unspecified)'
    bio_score=5)."""
    product = _build("Generic Curcumin + Pepper", [
        {"name": "Curcumin", "quantity": 500.0, "unit": "mg"},
        {"name": "Bioperine", "quantity": 5.0, "unit": "mg"},
    ])
    enriched, _ = enricher.enrich_product(product)
    iqd = enriched["ingredient_quality_data"]
    curcumin = _find_curcumin_row(iqd)
    mf = curcumin.get("matched_form") or ""
    assert mf != "curcumin c3 complex with bioperine", (
        f"Plain 'Curcumin' label must NOT be upgraded into the C3-with-"
        f"bioperine slot. Got matched_form={mf!r}."
    )
