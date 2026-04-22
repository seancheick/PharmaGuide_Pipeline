"""
Sprint E1.3.3 — fish oil EPA/DHA nested-NP propagation.

Many DSLD fish-oil products disclose total oil mass on the parent row
("Fish Oil 1200 mg") but leave nested EPA/DHA at ``quantity=0, unit=NP``.
The scorer's ``_compute_epa_dha_per_day`` then reports has_dose=False
and Section A stays at 0.

Same pattern as E1.2.1 (prop-blend parent-mass cascade) but for
fish-oil aggregation. Conservative fallback, config-gated:

    if EPA and DHA individual doses are NP AND parent is a fish-oil-
    class container AND parent mass is propagated via E1.2.1 →
    EPA+DHA_combined_mg = parent_mass_mg * omega3_from_parent_fraction

The ``omega3_from_parent_fraction`` default is ``0.5`` — middle of the
30% (standard grade) / 80% (concentrated) industry range. Config key:
``section_A_ingredient_quality.omega3_dose_bonus.fish_oil_parent_mass_fallback``.

Flags the product so the source is transparent:
    ``omega3_dose_source = "inferred_from_parent_mass"``

Canary (sprint §E1.3.3 DoD): DSLD 19055 Spring Valley Enteric Coated
Fish Oil 1290 mg → Section A > 0.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))


# ---------------------------------------------------------------------------
# Scorer-level fallback: _compute_epa_dha_per_day applies parent mass
# ---------------------------------------------------------------------------

def _fish_oil_product_with_np_epa_dha() -> dict:
    """Shape matching DSLD 19055 post-cleaner: parent Fish Oil mass
    propagated to children as parent_blend_mass_mg; EPA/DHA individual
    quantities are NP."""
    return {
        "ingredient_quality_data": {
            "ingredients": [
                {
                    "name": "Eicosapentaenoic Acid",
                    "canonical_id": "epa",
                    "quantity": 0,
                    "unit": "NP",
                    "parent_blend": "Fish Oil",
                    "parent_blend_mass_mg": 1200.0,
                    "is_proprietary_blend": False,
                    "is_blend_header": False,
                    "is_parent_total": False,
                },
                {
                    "name": "Docosahexaenoic Acid",
                    "canonical_id": "dha",
                    "quantity": 0,
                    "unit": "NP",
                    "parent_blend": "Fish Oil",
                    "parent_blend_mass_mg": 1200.0,
                    "is_proprietary_blend": False,
                    "is_blend_header": False,
                    "is_parent_total": False,
                },
            ],
        },
        "serving_basis": {"min_servings_per_day": 2, "max_servings_per_day": 2},
    }


@pytest.fixture(scope="module")
def scorer():
    import logging; logging.disable(logging.CRITICAL)
    from score_supplements import SupplementScorer
    return SupplementScorer()


def test_fish_oil_parent_mass_fallback_applies_when_epa_dha_are_np(scorer) -> None:
    product = _fish_oil_product_with_np_epa_dha()
    dose = scorer._compute_epa_dha_per_day(product)
    assert dose["has_explicit_dose"] is True, (
        f"Sprint E1.3.3: parent-mass fallback didn't fire. dose={dose}"
    )
    # 1200 mg parent × 0.5 fraction = 600 mg epa_dha per serving
    # × 2 servings/day = 1200 mg per day combined, split 50/50
    # epa_mg_per_unit = 300, dha_mg_per_unit = 300 per serving; per_day ≈ 1200
    assert dose["epa_dha_mg_per_unit"] == pytest.approx(600.0)
    assert dose["per_day_mid"] == pytest.approx(1200.0)


def test_fish_oil_fallback_tags_inferred_source(scorer) -> None:
    product = _fish_oil_product_with_np_epa_dha()
    dose = scorer._compute_epa_dha_per_day(product)
    assert dose.get("omega3_dose_source") == "inferred_from_parent_mass"


def test_fallback_does_not_fire_when_epa_dha_have_real_doses(scorer) -> None:
    """When EPA/DHA have individual doses, the fallback must not
    override — real values win."""
    product = {
        "ingredient_quality_data": {
            "ingredients": [
                {
                    "name": "EPA", "canonical_id": "epa",
                    "quantity": 360, "unit": "mg",
                    "parent_blend": "Fish Oil",
                    "parent_blend_mass_mg": 1200.0,
                },
                {
                    "name": "DHA", "canonical_id": "dha",
                    "quantity": 240, "unit": "mg",
                    "parent_blend": "Fish Oil",
                    "parent_blend_mass_mg": 1200.0,
                },
            ],
        },
        "serving_basis": {"min_servings_per_day": 1, "max_servings_per_day": 1},
    }
    dose = scorer._compute_epa_dha_per_day(product)
    assert dose["epa_dha_mg_per_unit"] == pytest.approx(600.0)
    # Real doses, not inferred
    assert dose.get("omega3_dose_source") != "inferred_from_parent_mass"


def test_fallback_ignores_non_fish_oil_parents(scorer) -> None:
    """Parent-mass inference is ONLY for fish-oil / krill-oil class
    containers. A prop blend with NP EPA/DHA nested under "Herbal
    Blend" must not trigger."""
    product = {
        "ingredient_quality_data": {
            "ingredients": [
                {
                    "name": "EPA", "canonical_id": "epa",
                    "quantity": 0, "unit": "NP",
                    "parent_blend": "Herbal Blend",
                    "parent_blend_mass_mg": 500.0,
                },
            ],
        },
        "serving_basis": {"min_servings_per_day": 1, "max_servings_per_day": 1},
    }
    dose = scorer._compute_epa_dha_per_day(product)
    assert dose["has_explicit_dose"] is False, (
        f"Herbal Blend parent should NOT trigger fish-oil fallback. dose={dose}"
    )


def test_krill_oil_parent_also_triggers_fallback(scorer) -> None:
    """Krill oil is functionally equivalent for this fallback path."""
    product = _fish_oil_product_with_np_epa_dha()
    for ing in product["ingredient_quality_data"]["ingredients"]:
        ing["parent_blend"] = "Krill Oil"
    dose = scorer._compute_epa_dha_per_day(product)
    assert dose["has_explicit_dose"] is True


def test_no_fallback_when_parent_mass_absent(scorer) -> None:
    product = _fish_oil_product_with_np_epa_dha()
    for ing in product["ingredient_quality_data"]["ingredients"]:
        ing.pop("parent_blend_mass_mg", None)
    dose = scorer._compute_epa_dha_per_day(product)
    assert dose["has_explicit_dose"] is False


# ---------------------------------------------------------------------------
# Config-gated
# ---------------------------------------------------------------------------

def test_fallback_can_be_disabled_via_config(scorer) -> None:
    product = _fish_oil_product_with_np_epa_dha()
    original_cfg = scorer.config.get("section_A_ingredient_quality", {}).get(
        "omega3_dose_bonus", {}
    ).get("fish_oil_parent_mass_fallback")
    # Monkey-patch via scorer.config
    o3 = scorer.config.setdefault("section_A_ingredient_quality", {}).setdefault(
        "omega3_dose_bonus", {}
    )
    o3["fish_oil_parent_mass_fallback"] = {"enabled": False, "epa_dha_fraction_of_parent": 0.5}
    try:
        dose = scorer._compute_epa_dha_per_day(product)
        assert dose["has_explicit_dose"] is False, (
            "Fallback must respect enabled=False"
        )
    finally:
        if original_cfg is None:
            del o3["fish_oil_parent_mass_fallback"]
        else:
            o3["fish_oil_parent_mass_fallback"] = original_cfg


# ---------------------------------------------------------------------------
# Canary: DSLD 19055 end-to-end rebuild
# ---------------------------------------------------------------------------

def test_19055_canary_section_a_positive_after_fix() -> None:
    import json
    blob_path = ROOT / "reports" / "canary_rebuild" / "19055.json"
    if not blob_path.exists():
        pytest.skip("19055 canary not rebuilt yet")
    blob = json.loads(blob_path.read_text())
    sa = blob.get("section_breakdown", {}).get("ingredient_quality", {}).get("score", 0)
    assert sa > 0, (
        f"Sprint §E1.3.3 DoD: 19055 Spring Valley Fish Oil Section A must be > 0; got {sa}"
    )
