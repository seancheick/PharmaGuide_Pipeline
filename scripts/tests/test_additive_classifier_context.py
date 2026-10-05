"""
Sprint E1.3.1 — context-aware is_additive classifier regression tests.

Dual-use compounds (tocopherols, lecithin, some fatty acids) ship with
DSLD's ``isAdditive=True`` flag by default because they're commonly
used as preservatives / excipients. When the same compound appears in
the ACTIVE panel with a recognized therapeutic identity, it remains active.
Dose independently determines whether its amount can be assessed.

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
    assert reason is None, f"Active lecithin skipped: {reason!r}"
    assert enricher._compute_excipient_flags(ing) == (False, None)


def test_rice_flour_inactive_remains_additive(enricher) -> None:
    """Genuine excipient with no therapeutic identity must stay skipped."""
    ing = _rice_flour_inactive()
    reason = enricher._should_skip_from_scoring(ing, enricher.databases.get("ingredient_quality_map", {}), enricher.databases.get("botanical_ingredients", {}))
    # Either SKIP_REASON_ADDITIVE or some other-valid skip; just don't score it
    assert reason is not None, (
        "Rice flour in inactive panel must not score as active."
    )


# ---------------------------------------------------------------------------
# An undisclosed amount does not reclassify an active-panel ingredient.
# ---------------------------------------------------------------------------

def test_vitamin_e_undisclosed_amount_remains_active_with_unknown_dose(enricher) -> None:
    ing = _vitamin_e_180mg_active_with_additive_flag()
    ing.update(quantity=0, unit="NP")
    assert enricher._compute_excipient_flags(ing) == (False, None)
    assert enricher._has_valid_therapeutic_dose(ing)[0] is False
    assert enricher._should_skip_from_scoring(
        ing, enricher.databases["ingredient_quality_map"],
        enricher.databases["botanical_ingredients"],
    ) is None


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

@pytest.mark.parametrize("source,quantity", [("active", 0), ("inactive", 180)])
def test_excipient_purpose_follows_source_membership_not_amount(enricher, source, quantity):
    row = _vitamin_e_180mg_active_with_additive_flag()
    row.update(source_section=source, quantity=quantity,
               unit="NP" if not quantity else "mg",
               cleaner_row_role="nested_display_only" if source == "active" else "inactive",
               isNestedIngredient=source == "active", parentBlend="Antioxidant Blend")
    assert enricher._compute_excipient_flags(row)[0] is (source == "inactive")
    # Undisclosed member amounts still cannot be counted as a known dose.
    if source == "active":
        assert enricher._should_skip_from_scoring(row, enricher.databases["ingredient_quality_map"],
                                                 enricher.databases["botanical_ingredients"]) is not None

@pytest.mark.parametrize("changes", [
    {"source_section": "inactive"},
    {"source_section": "active", "isNestedIngredient": True, "parentBlend": "Total Fat"},
    {"source_section": "active", "name": "Unknown carrier", "standardName": "Unknown carrier"},
    {"source_section": "active", "cleaner_row_role": "source_descriptor"},
    {"source_section": "active", "cleaner_row_role": "excipient", "score_eligible_by_cleaner": False},
    {"source_section": "active", "cleaner_row_role": "nutrition_fact"},
])
def test_additive_boundaries_preserve_inactive_rollup_and_unknown_carrier(enricher, changes):
    row = _vitamin_e_180mg_active_with_additive_flag()
    row.update(changes)
    assert enricher._compute_excipient_flags(row)[0] is True
    assert enricher._should_skip_from_scoring(row, enricher.databases["ingredient_quality_map"],
                                             enricher.databases["botanical_ingredients"]) is not None


def test_unpromoted_excipient_keeps_its_existing_recognition_owner(enricher):
    row = {"name": "Mannitol", "standardName": "Mannitol", "source_section": "active", "quantity": 1, "unit": "g"}
    assert enricher._compute_excipient_flags(row)[0] is True
    assert enricher._should_skip_from_scoring(row, enricher.databases["ingredient_quality_map"],
                                             enricher.databases["botanical_ingredients"]) == "recognized_non_scorable"


@pytest.mark.parametrize("section", ["absent", None, ""])
def test_active_collection_supplies_missing_legacy_section_without_mutating_label(enricher, section):
    row = _lecithin_active_500mg()
    row.pop("raw_source_path")
    if section != "absent":
        row["source_section"] = section
    product = {"id": "legacy-section", "activeIngredients": [row], "inactiveIngredients": []}
    result = enricher._collect_ingredient_quality_data(product)
    assert result["ingredients_scorable"], result["ingredients_skipped"]
    if section == "absent":
        assert "source_section" not in row
    else:
        assert row["source_section"] == section


@pytest.mark.parametrize("source,excipient", [("activeIngredients", False), ("inactiveIngredients", True)])
def test_legacy_explicit_section_names_keep_their_membership(enricher, source, excipient):
    row = _lecithin_active_500mg()
    row["source_section"] = source
    assert enricher._compute_excipient_flags(row)[0] is excipient
