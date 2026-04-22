"""
Sprint E1.3.1 — context-aware is_additive classifier regression tests.

Dual-use compounds (tocopherols, lecithin, some fatty acids) ship with
DSLD's ``isAdditive=True`` flag by default because they're commonly
used as preservatives / excipients. When the same compound appears in
the ACTIVE panel with a meaningful therapeutic dose, it IS the primary
active and MUST be scored (not skipped).

Dev rule (external review 2026-04-22): "Context decides classification
— not the ingredient name."

Canary target (sprint §E1.3.1 DoD):
  * Nature Made E 400 IU (DSLD 266975)            — Section A > 0
  * Pure Encapsulations Ultra-Synergist E (188715) — Section A > 0
  * Nature Made Triple Omega (DSLD 26689)          — Vitamin E scorable
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

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    import logging; logging.disable(logging.CRITICAL)
    return SupplementEnricherV3()


def _vitamin_e_180mg_active_with_additive_flag() -> dict:
    """Shape that matches what the cleaner emits for Nature Made E 400 IU
    — the exact canary the sprint targets. ``isAdditive=True`` because
    the DSLD ingredientGroup hints at a tocopheryl acetate preservative
    use, but this is the primary active at 180 mg per softgel."""
    return {
        "name": "Vitamin E",
        "standardName": "Vitamin E",
        "quantity": 180.0,
        "unit": "mg",
        "isAdditive": True,
        "additiveType": "preservative_natural",
        "ingredientGroup": "Vitamin E (alpha tocopheryl acetate)",
        "mapped": True,
        "raw_source_path": "activeIngredients",
        "hierarchyType": "source",
    }


def _vitamin_e_no_dose_inactive() -> dict:
    """Same compound, but in inactive panel without a disclosed dose —
    genuinely an additive. Must still be treated as additive."""
    return {
        "name": "Vitamin E",
        "standardName": "Vitamin E",
        "quantity": 0,
        "unit": "",
        "isAdditive": True,
        "additiveType": "preservative_natural",
        "ingredientGroup": "Vitamin E (alpha tocopheryl acetate)",
        "mapped": True,
        "raw_source_path": "inactiveIngredients",
    }


def _lecithin_active_500mg() -> dict:
    return {
        "name": "Sunflower Lecithin",
        "standardName": "Lecithin",
        "quantity": 500.0,
        "unit": "mg",
        "isAdditive": True,
        "additiveType": "emulsifier",
        "ingredientGroup": "Lecithin",
        "mapped": True,
        "raw_source_path": "activeIngredients",
    }


def _rice_flour_inactive() -> dict:
    return {
        "name": "Rice Flour",
        "standardName": "Rice Flour",
        "quantity": 0,
        "unit": "",
        "isAdditive": True,
        "ingredientGroup": "Rice Flour",
        "mapped": False,
        "raw_source_path": "inactiveIngredients",
    }


# ---------------------------------------------------------------------------
# Canary: Nature Made Vitamin E 400 IU must not be skipped
# ---------------------------------------------------------------------------

def test_vitamin_e_400iu_as_active_is_not_skipped(enricher) -> None:
    ing = _vitamin_e_180mg_active_with_additive_flag()
    reason = enricher._should_skip_from_scoring(ing, enricher.databases.get("ingredient_quality_map", {}), enricher.databases.get("botanical_ingredients", {}))
    assert reason != "is_additive", (
        f"Nature Made Vit E 400 IU skipped as additive; skip_reason={reason!r}. "
        f"Active + dose + IQM-known should override isAdditive flag."
    )


def test_vitamin_e_400iu_excipient_flags_not_excipient(enricher) -> None:
    ing = _vitamin_e_180mg_active_with_additive_flag()
    is_excipient, reason = enricher._compute_excipient_flags(ing)
    assert is_excipient is False, (
        f"Vit E 180 mg flagged excipient={is_excipient}, reason={reason!r} — "
        f"must pass through at therapeutic dose."
    )


# ---------------------------------------------------------------------------
# Inactive-section inactive: must still be additive
# ---------------------------------------------------------------------------

def test_vitamin_e_no_dose_in_inactive_panel_is_additive(enricher) -> None:
    ing = _vitamin_e_no_dose_inactive()
    reason = enricher._should_skip_from_scoring(ing, enricher.databases.get("ingredient_quality_map", {}), enricher.databases.get("botanical_ingredients", {}))
    # Without a therapeutic dose, isAdditive skip should still fire.
    assert reason is not None, (
        "Vit E without dose in inactive panel should still be skipped."
    )


# ---------------------------------------------------------------------------
# Dual-use matrix
# ---------------------------------------------------------------------------

def test_lecithin_500mg_active_is_not_skipped(enricher) -> None:
    ing = _lecithin_active_500mg()
    reason = enricher._should_skip_from_scoring(ing, enricher.databases.get("ingredient_quality_map", {}), enricher.databases.get("botanical_ingredients", {}))
    assert reason != "is_additive", (
        f"Lecithin 500 mg in active panel skipped; reason={reason!r}"
    )


def test_rice_flour_inactive_remains_additive(enricher) -> None:
    """Genuine excipient with no therapeutic identity must stay skipped."""
    ing = _rice_flour_inactive()
    reason = enricher._should_skip_from_scoring(ing, enricher.databases.get("ingredient_quality_map", {}), enricher.databases.get("botanical_ingredients", {}))
    # Either SKIP_REASON_ADDITIVE or some other-valid skip; just don't score it
    assert reason is not None, (
        "Rice flour in inactive panel must not score as active."
    )


# ---------------------------------------------------------------------------
# Dose-guard: trace Vitamin E (e.g. 2 mg in oil blend) must still skip
# ---------------------------------------------------------------------------

def test_vitamin_e_trace_dose_without_valid_unit_still_skipped(enricher) -> None:
    """Edge case: active-panel Vit E with qty=0 or no unit — no
    therapeutic-dose signal, so isAdditive override does NOT trigger.
    Respects the dev rule 'trace dose → additive'."""
    ing = _vitamin_e_180mg_active_with_additive_flag()
    ing["quantity"] = 0
    ing["unit"] = "NP"
    reason = enricher._should_skip_from_scoring(ing, enricher.databases.get("ingredient_quality_map", {}), enricher.databases.get("botanical_ingredients", {}))
    assert reason is not None, (
        "Vit E with qty=0/unit=NP should still be skipped even in active panel."
    )


# ---------------------------------------------------------------------------
# additiveType gate — same override applies
# ---------------------------------------------------------------------------

def test_additive_type_gate_respects_therapeutic_override(enricher) -> None:
    """If an ingredient has additiveType='preservative_natural' AND is
    IQM-known + dosed in the active panel, it's not a preservative —
    it's the active."""
    ing = _vitamin_e_180mg_active_with_additive_flag()
    ing["isAdditive"] = False  # clear flag A1
    # Only additiveType remains as a gate
    reason = enricher._should_skip_from_scoring(ing, enricher.databases.get("ingredient_quality_map", {}), enricher.databases.get("botanical_ingredients", {}))
    assert reason != "additive_type", (
        f"additiveType='preservative_natural' skipped Vit E 180 mg; reason={reason!r}"
    )
