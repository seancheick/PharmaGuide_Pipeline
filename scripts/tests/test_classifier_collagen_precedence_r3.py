"""Phase 0d R3 — collagen identity outranks the `protein` CATEGORY.

THE DEFECT
    In the multi-active chain the protein branch sits at :1127 and the collagen
    branch at :1150, so protein wins. Worse, the protein branch fires on
    `category_counts.get("protein", 0) > 0` — collagen's category IS `protein`,
    and collagen is not in `_PROTEIN_IDS` — so it claims the product at
    confidence 0.9 with NO protein identity at all. The rendered reason says so
    out loud:

        19435 "Comfort" (collagen x2 + hyaluronic acid)
          -> protein_powder @0.9   reason: "protein powder signal: ids=[]"

    A branch with no identity evidence has no business claiming a type.

THE RULE
    Required identity: >=1 row whose canonical id is in `_COLLAGEN_IDS`.
    Dominance: collagen is >=50% of distinct actives, OR the only non-cofactor
    active (vitamin C / hyaluronic acid are collagen cofactors and must not
    defeat it), OR the title names collagen — identity CORROBORATED by intent,
    never intent alone.
    Exclusion: a broad vitamin/mineral panel outranks it. An incidental collagen
    row must not hijack a multivitamin — 68 real multivitamins carry one.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from supplement_taxonomy import classify_supplement  # noqa: E402


def _row(name, canonical_id, category, qty=100.0, unit="mg", **extra):
    row = {
        "name": name, "canonical_id": canonical_id, "standard_name": name,
        "category": category, "quantity": qty, "unit": unit, "mapped": True,
        "role_classification": "active_scorable",
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
    }
    row.update(extra)
    return row


def _product(name, rows):
    return {
        "dsld_id": 940001, "product_name": name, "fullName": name,
        "ingredient_quality_data": {"ingredients_scorable": rows},
        "probiotic_data": {"is_probiotic_product": False, "total_cfu": 0},
    }


# ---------------------------------------------------------------------------
# Positives — the real corpus canaries
# ---------------------------------------------------------------------------


def test_collagen_with_vitamin_c_cofactor_is_collagen():
    """269491 "Collagen Types 1 and 3 1000 mg" — was general_supplement @0.85
    with the reason literally naming collagen as dominant."""
    taxonomy = classify_supplement(_product("Collagen Types 1 and 3 1000 mg", [
        _row("Collagen", "collagen", "protein", 1000.0),
        _row("Vitamin C", "vitamin_c", "vitamin", 60.0),
    ]))
    assert taxonomy["primary_type"] == "collagen"


def test_collagen_with_hyaluronic_acid_cofactor_is_collagen():
    """19435 "Comfort" — was protein_powder @0.9 via the category hijack."""
    taxonomy = classify_supplement(_product("Comfort", [
        _row("Collagen Type II", "collagen", "protein", 40.0),
        _row("Hyaluronic Acid", "hyaluronic_acid", "fiber", 20.0),
    ]))
    assert taxonomy["primary_type"] == "collagen"


def test_collagen_with_beauty_vitamins_and_a_naming_title_is_collagen():
    """250086 "Collagen Natural Berry" — collagen is only 1 of 3 identities, so
    dominance alone does not carry it; the title naming collagen corroborates
    the identity that IS present."""
    taxonomy = classify_supplement(_product("Collagen Natural Berry Pomegranate", [
        _row("Collagen Peptides", "collagen", "protein", 10000.0),
        _row("Vitamin A", "vitamin_a", "vitamin", 900.0),
        _row("Vitamin E", "vitamin_e", "vitamin", 15.0),
    ]))
    assert taxonomy["primary_type"] == "collagen"


# ---------------------------------------------------------------------------
# Near-miss negatives — an incidental row must not hijack
# ---------------------------------------------------------------------------


def test_incidental_collagen_row_does_not_hijack_a_multivitamin():
    """The plan's explicit warning. 68 real multivitamins carry a collagen row."""
    rows = [
        _row("Vitamin A", "vitamin_a", "vitamin", 900.0),
        _row("Vitamin C", "vitamin_c", "vitamin", 90.0),
        _row("Vitamin D", "vitamin_d", "vitamin", 20.0),
        _row("Vitamin E", "vitamin_e", "vitamin", 15.0),
        _row("Zinc", "zinc", "mineral", 11.0),
        _row("Selenium", "selenium", "mineral", 55.0),
        _row("Magnesium", "magnesium", "mineral", 420.0),
        _row("Collagen", "collagen", "protein", 50.0),
    ]
    taxonomy = classify_supplement(_product("Daily Multivitamin Complete", rows))
    assert taxonomy["primary_type"] == "multivitamin", (
        f"an incidental collagen row hijacked a multivitamin -> "
        f"{taxonomy['primary_type']!r}"
    )


def test_whey_protein_is_still_protein_powder():
    """R3 must not cost the protein branch its real work."""
    taxonomy = classify_supplement(_product("Gold Standard Whey Protein Powder", [
        _row("Whey Protein Isolate", "whey_protein_isolate", "protein", 24000.0),
        _row("Whey Protein Concentrate", "whey_protein_concentrate", "protein", 6000.0),
    ]))
    assert taxonomy["primary_type"] == "protein_powder"


# ---------------------------------------------------------------------------
# The empty-id branch
# ---------------------------------------------------------------------------


def test_protein_branch_never_fires_without_a_protein_identity():
    """"protein powder signal: ids=[]" must be impossible. A branch that claims a
    type at 0.9 confidence while naming zero identities is asserting something it
    did not observe."""
    source = (SCRIPTS_DIR / "supplement_taxonomy.py").read_text()
    assert 'category_counts.get("protein", 0) > 0' not in source, (
        "the protein branch still fires on the bare `protein` CATEGORY, which "
        "collagen also carries"
    )


def test_no_type_is_claimed_from_an_empty_id_set():
    """A non-collagen, non-whey product whose only signal is category=protein
    must not be called protein_powder on no evidence."""
    taxonomy = classify_supplement(_product("Mystery Peptide Blend", [
        _row("Unknown Peptide A", "", "protein", 500.0),
        _row("Unknown Peptide B", "", "protein", 500.0),
    ]))
    reasons = " ".join(taxonomy["classification_reasons"])
    assert "ids=[]" not in reasons, (
        f"a branch claimed a type while naming no identities: {reasons!r}"
    )
