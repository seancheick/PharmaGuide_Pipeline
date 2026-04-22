"""
Sprint E1.2.2.a — display_label regression tests.

Format contract: ``Brand Base Form``. Driven by:
  * forms[0].name when DSLD carries a descriptive form phrase
    ("Ashwagandha Root Extract")
  * name as the fallback when no forms
  * _BRANDED_TOKENS prefix when the source label carries a branded
    ingredient and the base phrase does not already include it

Covers invariants #1, #4, #5 from E1.0.1.
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

from scripts.build_final_db import _compute_display_label  # noqa: E402


# ---------------------------------------------------------------------------
# Branded tokens — source label carries a brand, base phrase doesn't
# ---------------------------------------------------------------------------

def test_ksm66_ashwagandha_preserves_brand_and_form() -> None:
    """Canary 306237 (Nutricost KSM-66): the descriptive DSLD form is
    "Ashwagandha Root Extract"; the branded token "KSM-66" lives on the
    ingredient name. Combined display must read "KSM-66 Ashwagandha
    Root Extract" — brand + base + plant-part + form."""
    ing = {
        "name": "KSM-66",
        "standard_name": "Ashwagandha",
        "forms": [{"name": "Ashwagandha Root Extract"}],
    }
    assert _compute_display_label(ing) == "KSM-66 Ashwagandha Root Extract"


def test_bioperine_preserves_brand() -> None:
    ing = {
        "name": "Bioperine",
        "standard_name": "Piperine (Black Pepper Extract)",
        "forms": [{"name": "Black Pepper Fruit Extract"}],
    }
    assert _compute_display_label(ing) == "BioPerine Black Pepper Fruit Extract"


def test_ferrochel_preserves_brand_for_iron() -> None:
    ing = {
        "name": "Ferrochel",
        "standard_name": "Iron",
        "forms": [{"name": "Iron Bisglycinate Chelate"}],
    }
    assert _compute_display_label(ing) == "Ferrochel Iron Bisglycinate Chelate"


# ---------------------------------------------------------------------------
# Already-branded base phrase — no double-prefix
# ---------------------------------------------------------------------------

def test_brand_already_in_form_is_not_duplicated() -> None:
    """If forms[0].name already carries the brand, don't prepend again."""
    ing = {
        "name": "KSM-66",
        "forms": [{"name": "KSM-66 Ashwagandha Root Extract"}],
    }
    # Must not emit "KSM-66 KSM-66 Ashwagandha Root Extract"
    assert _compute_display_label(ing) == "KSM-66 Ashwagandha Root Extract"


# ---------------------------------------------------------------------------
# No brand, with descriptive form — plant part must survive
# ---------------------------------------------------------------------------

def test_plant_part_preserved_when_no_brand() -> None:
    """Invariant #5 — plant-part words in forms[].name survive to display_label."""
    ing = {
        "name": "Turmeric",
        "standard_name": "Turmeric",
        "forms": [{"name": "Turmeric Root Extract"}],
    }
    label = _compute_display_label(ing)
    assert "root" in label.lower()
    assert "extract" in label.lower()


@pytest.mark.parametrize("part", ["Root", "Leaf", "Seed", "Bark", "Rhizome", "Aerial Parts"])
def test_all_plant_parts_preserved(part: str) -> None:
    ing = {
        "name": "Botanical",
        "standard_name": "Botanical",
        "forms": [{"name": f"Botanical {part} Extract"}],
    }
    label = _compute_display_label(ing)
    assert part.lower() in label.lower()


# ---------------------------------------------------------------------------
# No collapse to canonical (invariant #1)
# ---------------------------------------------------------------------------

def test_does_not_collapse_to_scoring_canonical() -> None:
    """Invariant #1 — when the source name differs from the canonical and
    a descriptive form is present, the display must surface the
    descriptive form, not the canonical."""
    ing = {
        "name": "KSM-66",
        "standard_name": "Ashwagandha",  # scoring canonical
        "forms": [{"name": "Ashwagandha Root Extract"}],
    }
    label = _compute_display_label(ing)
    assert label.lower() != "ashwagandha"


# ---------------------------------------------------------------------------
# Simple cases — no brand, no forms
# ---------------------------------------------------------------------------

def test_simple_vitamin_falls_back_to_name() -> None:
    """Simple Vitamin D3 with no branded token, no descriptive forms —
    display is just the name."""
    ing = {
        "name": "Vitamin D3",
        "forms": [],
    }
    assert _compute_display_label(ing) == "Vitamin D3"


def test_vitamin_with_chemical_form_composites_with_parens() -> None:
    """Vitamin A with forms[0].name="Acetate" must not collapse to
    "Acetate" (which drops the base). Must composite to e.g.
    "Vitamin A (Acetate)" so the user sees what vitamin it is."""
    ing = {
        "name": "Vitamin A",
        "forms": [{"name": "Acetate"}],
    }
    assert _compute_display_label(ing) == "Vitamin A (Acetate)"


@pytest.mark.parametrize("name,form,expected", [
    ("Vitamin C", "Ascorbic Acid", "Vitamin C (Ascorbic Acid)"),
    ("Vitamin D", "Cholecalciferol", "Vitamin D (Cholecalciferol)"),
    ("Calcium", "Tricalcium Phosphate", "Calcium (Tricalcium Phosphate)"),
    # form already contains name — no parens needed
    ("Thiamine", "Thiamine Mononitrate", "Thiamine Mononitrate"),
    # form ⊂ name — form is redundant, use name
    ("Hemp extract", "extract", "Hemp extract"),
])
def test_vitamin_form_composition_matrix(name: str, form: str, expected: str) -> None:
    ing = {"name": name, "forms": [{"name": form}]}
    assert _compute_display_label(ing) == expected


def test_enzyme_without_forms_uses_name() -> None:
    """Plantizyme 35491 Amylase — empty forms, standard_name is a
    generic category. Display should use the raw name, not the category."""
    ing = {
        "name": "Amylase",
        "standard_name": "Digestive Enzymes",
        "forms": [],
    }
    assert _compute_display_label(ing) == "Amylase"


def test_empty_ingredient_returns_empty_string() -> None:
    assert _compute_display_label({}) == ""


# ---------------------------------------------------------------------------
# Case-insensitive brand matching
# ---------------------------------------------------------------------------

def test_brand_matched_case_insensitive() -> None:
    """Source label may carry "bioperine" lowercase; token list uses
    "BioPerine" — match must work either way, output preserves token case."""
    ing = {
        "name": "bioperine",
        "forms": [{"name": "Black Pepper Fruit Extract"}],
    }
    label = _compute_display_label(ing)
    assert "BioPerine" in label or "Bioperine" in label


# ---------------------------------------------------------------------------
# Hardening contracts (added 2026-04-22 per external-dev review after .a).
# These are permanent CI invariants — if a future regression drops the
# base name or the branded token, these fire immediately.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,form", [
    ("Vitamin A", "Acetate"),
    ("Vitamin C", "Ascorbic Acid"),
    ("Vitamin D", "Cholecalciferol"),
    ("Calcium", "Tricalcium Phosphate"),
    ("Magnesium", "Glycinate"),
    ("Iron", "Bisglycinate"),
    ("Zinc", "Picolinate"),
])
def test_display_label_never_drops_base_name(name: str, form: str) -> None:
    """Permanent invariant: when name is a base ingredient (vitamin/
    mineral) and form is a chemical descriptor, the base name must
    appear in display_label. Protects against substring false-positives
    like "Calcium" vs "Tricalcium Phosphate"."""
    ing = {"name": name, "forms": [{"name": form}]}
    label = _compute_display_label(ing)
    # Use word-boundary match — the base name must appear as a word
    import re as _re
    assert _re.search(r"\b" + _re.escape(name) + r"\b", label), (
        f"display_label {label!r} dropped base name {name!r}"
    )


@pytest.mark.parametrize("brand,form", [
    ("KSM-66", "Ashwagandha Root Extract"),
    ("BioPerine", "Black Pepper Fruit Extract"),
    ("Ferrochel", "Iron Bisglycinate Chelate"),
    ("Meriva", "Curcumin Phytosome"),
    ("Sensoril", "Ashwagandha Extract"),
])
def test_display_label_preserves_brand_token(brand: str, form: str) -> None:
    """Permanent invariant: whenever the source name carries a known
    branded token, it must survive to display_label (case-insensitive)."""
    ing = {"name": brand, "forms": [{"name": form}]}
    label = _compute_display_label(ing)
    assert brand.lower() in label.lower(), (
        f"display_label {label!r} dropped branded token {brand!r}"
    )


def test_magnesium_glycinate_composites_without_duplicating_form() -> None:
    """Edge case flagged in external-dev review: name="Magnesium",
    form="Glycinate" — must composite to "Magnesium (Glycinate)" and
    NOT accidentally emit "Magnesium Glycinate Glycinate" or drop
    either side."""
    ing = {"name": "Magnesium", "forms": [{"name": "Glycinate"}]}
    label = _compute_display_label(ing)
    assert label == "Magnesium (Glycinate)", label
    # And the inverse shape (form already carries base word):
    ing2 = {"name": "Magnesium", "forms": [{"name": "Magnesium Glycinate"}]}
    label2 = _compute_display_label(ing2)
    assert label2 == "Magnesium Glycinate", label2
    assert label2.lower().count("glycinate") == 1, (
        f"form-word duplicated: {label2!r}"
    )
