"""
Fish oil EPA/DHA nested-NP propagation policy.

Many DSLD fish-oil products disclose total oil mass on the parent row
("Fish Oil 1200 mg") but leave nested EPA/DHA at ``quantity=0, unit=NP``.
The shipped scorer must not estimate EPA+DHA from that parent mass. Dose
bonuses require explicit EPA, DHA, or combined EPA/DHA label amounts.

The legacy parent-mass fallback still exists behind an explicit config flag
for backcompat experiments, but default scoring keeps it disabled.
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


def test_fish_oil_parent_mass_fallback_is_disabled_by_default(scorer) -> None:
    product = _fish_oil_product_with_np_epa_dha()
    dose = scorer._compute_epa_dha_per_day(product)
    assert dose["has_explicit_dose"] is False, (
        f"Parent fish-oil mass must not infer EPA+DHA by default. dose={dose}"
    )
    assert dose["epa_dha_mg_per_unit"] == pytest.approx(0.0)
    assert dose["per_day_mid"] is None
    assert "omega3_dose_source" not in dose


def test_fish_oil_fallback_does_not_tag_inferred_source_by_default(scorer) -> None:
    product = _fish_oil_product_with_np_epa_dha()
    dose = scorer._compute_epa_dha_per_day(product)
    assert dose.get("omega3_dose_source") != "inferred_from_parent_mass"


def _explicit_epa_dha_row(name: str, canonical_id: str, quantity: float) -> dict:
    """Build a strict-contract-compliant scorable row for an EPA/DHA active.

    Mirrors the shape produced by the cleaner + enricher when an EPA or DHA
    ingredient carries an explicit per-serving dose. See
    scripts/scoring_input_contract.py:_evaluate_row for the required field
    set.
    """
    return {
        "name": name,
        "canonical_id": canonical_id,
        "quantity": quantity,
        "unit": "mg",
        "source_section": "active",
        "raw_source_path": f"ingredientRows[{canonical_id}]",
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
        "dose_class": "therapeutic_mass",
        "role_classification": "active_scorable",
        "scoreable_identity": True,
        "mapped": True,
    }


def test_fallback_does_not_fire_when_epa_dha_have_real_doses(scorer) -> None:
    """When EPA/DHA have individual doses, the explicit values are summed
    and there is no parent-mass inference (which is retired).
    """
    product = {
        "ingredient_quality_data": {
            "ingredients_scorable": [
                _explicit_epa_dha_row("EPA", "epa", 360),
                _explicit_epa_dha_row("DHA", "dha", 240),
            ],
        },
        "serving_basis": {"min_servings_per_day": 1, "max_servings_per_day": 1},
    }
    dose = scorer._compute_epa_dha_per_day(product)
    assert dose["epa_dha_mg_per_unit"] == pytest.approx(600.0)
    # Real doses, never inferred from parent mass (retired path).
    assert dose.get("omega3_dose_source") != "inferred_from_parent_mass"
    assert "omega3_dose_source" not in dose


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


def test_krill_oil_parent_also_does_not_infer_by_default(scorer) -> None:
    """Krill oil parent mass also cannot stand in for explicit EPA/DHA."""
    product = _fish_oil_product_with_np_epa_dha()
    for ing in product["ingredient_quality_data"]["ingredients"]:
        ing["parent_blend"] = "Krill Oil"
    dose = scorer._compute_epa_dha_per_day(product)
    assert dose["has_explicit_dose"] is False


def test_no_fallback_when_parent_mass_absent(scorer) -> None:
    product = _fish_oil_product_with_np_epa_dha()
    for ing in product["ingredient_quality_data"]["ingredients"]:
        ing.pop("parent_blend_mass_mg", None)
    dose = scorer._compute_epa_dha_per_day(product)
    assert dose["has_explicit_dose"] is False


# ---------------------------------------------------------------------------
# Config-gated
# ---------------------------------------------------------------------------

def test_legacy_fallback_cannot_be_re_enabled_via_stale_config(scorer) -> None:
    """Retired-policy regression test.

    The parent-mass fallback (`fish_oil_parent_mass_fallback`) is retired:
    parent fish-oil / krill-oil mass must never be used to infer EPA+DHA.
    Even if a stale config file at deploy time still carries `enabled: True`,
    the scorer must NOT produce a dose and must NOT tag the result as
    `omega3_dose_source: inferred_from_parent_mass`.

    Rationale: a label that reads "Fish Oil 1000 mg" is not equivalent to
    "EPA + DHA 1000 mg". Inferring EPA+DHA from total oil mass overstates
    the disclosed clinical evidence. See
    `scripts/config/scoring_config.json` → `omega3_dose_bonus.fish_oil_parent_mass_fallback._description`.
    """
    product = _fish_oil_product_with_np_epa_dha()
    original_cfg = scorer.config.get("section_A_ingredient_quality", {}).get(
        "omega3_dose_bonus", {}
    ).get("fish_oil_parent_mass_fallback")
    o3 = scorer.config.setdefault("section_A_ingredient_quality", {}).setdefault(
        "omega3_dose_bonus", {}
    )
    o3["fish_oil_parent_mass_fallback"] = {
        "enabled": True,
        "epa_dha_fraction_of_parent": 0.5,
        "eligible_parent_blends": ["fish oil", "krill oil"],
    }
    try:
        dose = scorer._compute_epa_dha_per_day(product)
        # Stale config must be a no-op: zero inferred dose, no inference tag.
        assert dose["has_explicit_dose"] is False, (
            f"Stale fish_oil_parent_mass_fallback config must NOT cause "
            f"parent-mass inference. dose={dose}"
        )
        assert dose["epa_dha_mg_per_unit"] == pytest.approx(0.0)
        assert dose["per_day_mid"] is None
        assert dose.get("omega3_dose_source") != "inferred_from_parent_mass"
        assert "omega3_dose_source" not in dose
    finally:
        if original_cfg is None:
            del o3["fish_oil_parent_mass_fallback"]
        else:
            o3["fish_oil_parent_mass_fallback"] = original_cfg


# ---------------------------------------------------------------------------
# Historical canary: DSLD 19055 end-to-end rebuild
# ---------------------------------------------------------------------------

def test_19055_canary_artifact_is_not_a_current_policy_gate() -> None:
    import json
    blob_path = ROOT / "reports" / "canary_rebuild" / "19055.json"
    if not blob_path.exists():
        pytest.skip("19055 canary not rebuilt yet")
    blob = json.loads(blob_path.read_text())
    omega = (blob.get("audit") or {}).get("omega3") or {}
    assert omega.get("omega3_dose_source") != "inferred_from_parent_mass"
