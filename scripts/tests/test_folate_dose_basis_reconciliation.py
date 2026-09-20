"""A folate total and its form breakdown may only be reconciled in one dose basis.

``is_folate_parent_total_duplicate_flag`` decides whether a declared total plus
its disclosed forms describe ONE exposure. It did that by comparing raw
``amount`` numbers, with no regard for the unit those numbers are expressed in.

Folate is the one nutrient where that is unsafe. Labels state it in mcg DFE
(dietary folate equivalents) *and* in the mass of the form supplying it, and the
two are not interchangeable — folic acid converts at 1.7 mcg DFE per mcg. A
parent stated in one basis and children in the other can reconcile numerically
by coincidence, collapsing a real exposure, or fail to reconcile when they
genuinely describe the same one.

Comparing across bases is not evidence of anything, so it must not suppress a
warning. Within a single basis, magnitudes must be normalized before comparison
so mg and mcg are not compared as bare numbers.

The plan's canaries also require the folic-acid and methylfolate cases to be
pinned separately rather than jointly in one combined fixture.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scoring_v4.dose_safety import is_folate_parent_total_duplicate_flag

THRESHOLD_IRRELEVANT = 425.0


def _flag(rows, *, nutrient="Folate", canonical="vitamin_b9_folate", aggregation="canonical_sum"):
    return {
        "nutrient": nutrient,
        "canonical_id": canonical,
        "pct_ul": THRESHOLD_IRRELEVANT,
        "ul_gate_eligible": True,
        "aggregation": aggregation,
        "contributing_rows": rows,
    }


# ── the two canaries the plan requires as separate cases ──────────────────


def test_folate_total_plus_folic_acid_child_is_one_exposure():
    assert is_folate_parent_total_duplicate_flag(_flag([
        {"ingredient": "Folate", "amount": 1700.0, "unit": "mcg DFE"},
        {"ingredient": "Folic Acid", "amount": 1700.0, "unit": "mcg DFE"},
    ])) is True


def test_folate_total_plus_methylfolate_child_is_one_exposure():
    assert is_folate_parent_total_duplicate_flag(_flag([
        {"ingredient": "Folate", "amount": 1000.0, "unit": "mcg DFE"},
        {"ingredient": "L-5-MTHF", "amount": 1000.0, "unit": "mcg DFE"},
    ])) is True


def test_folate_total_plus_multiple_disclosed_forms_is_one_exposure():
    assert is_folate_parent_total_duplicate_flag(_flag([
        {"ingredient": "Folate", "amount": 1700.0, "unit": "mcg DFE"},
        {"ingredient": "L-5-MTHF", "amount": 1000.0, "unit": "mcg DFE"},
        {"ingredient": "Folic Acid", "amount": 700.0, "unit": "mcg DFE"},
    ])) is True


# ── dose-basis integrity ──────────────────────────────────────────────────


def test_dfe_total_is_never_reconciled_against_a_plain_mass_form():
    """mcg DFE and mcg of folic acid are different quantities (1 mcg folic acid
    = 1.7 mcg DFE). A numeric match across the two bases is a coincidence, and a
    coincidence must not suppress an over-limit warning."""
    assert is_folate_parent_total_duplicate_flag(_flag([
        {"ingredient": "Folate", "amount": 1000.0, "unit": "mcg DFE"},
        {"ingredient": "Folic Acid", "amount": 1000.0, "unit": "mcg"},
    ])) is False


def test_mass_total_is_never_reconciled_against_a_dfe_form():
    assert is_folate_parent_total_duplicate_flag(_flag([
        {"ingredient": "Folate", "amount": 1000.0, "unit": "mcg"},
        {"ingredient": "L-5-MTHF", "amount": 1000.0, "unit": "mcg DFE"},
    ])) is False


def test_magnitudes_are_normalized_within_one_basis():
    """1 mg DFE is 1000 mcg DFE. Comparing the bare numbers 1 and 1000 would
    reject a genuine restatement."""
    assert is_folate_parent_total_duplicate_flag(_flag([
        {"ingredient": "Folate", "amount": 1.0, "unit": "mg DFE"},
        {"ingredient": "Folic Acid", "amount": 1000.0, "unit": "mcg DFE"},
    ])) is True


def test_bare_numbers_that_only_match_before_unit_conversion_are_not_collapsed():
    """1 mg vs 1000 mcg reconciles; 1000 mg vs 1000 mcg must not."""
    assert is_folate_parent_total_duplicate_flag(_flag([
        {"ingredient": "Folate", "amount": 1000.0, "unit": "mg"},
        {"ingredient": "Folic Acid", "amount": 1000.0, "unit": "mcg"},
    ])) is False


def test_units_absent_falls_back_to_bare_amount_comparison():
    """Older/partial artifacts carry no unit on contributing rows. Behaviour
    there is unchanged — the guard only engages on stated units."""
    assert is_folate_parent_total_duplicate_flag(_flag([
        {"ingredient": "Folate", "amount": 1700.0},
        {"ingredient": "Folic Acid", "amount": 1700.0},
    ])) is True


def test_unknown_unit_token_does_not_silently_reconcile_against_a_known_basis():
    assert is_folate_parent_total_duplicate_flag(_flag([
        {"ingredient": "Folate", "amount": 1700.0, "unit": "mcg DFE"},
        {"ingredient": "Folic Acid", "amount": 1700.0, "unit": "IU"},
    ])) is False


# ── guards that must keep working ─────────────────────────────────────────


def test_amounts_that_do_not_reconcile_are_still_distinct_exposures():
    assert is_folate_parent_total_duplicate_flag(_flag([
        {"ingredient": "Folate", "amount": 400.0, "unit": "mcg DFE"},
        {"ingredient": "Folic Acid", "amount": 1700.0, "unit": "mcg DFE"},
    ])) is False


def test_non_aggregate_flag_is_not_collapsed():
    assert is_folate_parent_total_duplicate_flag(_flag([
        {"ingredient": "Folate", "amount": 1700.0, "unit": "mcg DFE"},
        {"ingredient": "Folic Acid", "amount": 1700.0, "unit": "mcg DFE"},
    ], aggregation="single_row")) is False


def test_non_folate_nutrient_is_not_collapsed():
    assert is_folate_parent_total_duplicate_flag(_flag([
        {"ingredient": "Vitamin A", "amount": 1700.0, "unit": "mcg"},
        {"ingredient": "Retinyl Palmitate", "amount": 1700.0, "unit": "mcg"},
    ], nutrient="Vitamin A", canonical="vitamin_a")) is False


# ── 2026-09-20 source-resolution fixtures ────────────────────────────────
#
# Three Phase-3 products were carrying a folate flag that double-counted one
# printed exposure. Each shape below is the contributing-row set the enriched
# contract actually produced for that product.


def test_partial_form_breakdown_inside_a_declared_dfe_total_is_one_exposure():
    """246430 Pure Encapsulations PreNatal Nutrients.

    The label declares 1667 mcg DFE and separately discloses the 400 mcg of
    folic acid that is already inside that total (1000 mcg L-5-MTHF at 1:1 plus
    400 mcg folic acid x 1.7 = 1680). Charging the disclosed component again
    produced a false over-limit state; the child is a subset of the total.
    """
    assert is_folate_parent_total_duplicate_flag(_flag([
        {"ingredient": "Folate", "amount": 1667.0, "unit": "mcg DFE"},
        {"ingredient": "Folic Acid", "amount": 680.0, "unit": "mcg DFE"},
    ])) is True


def test_sibling_form_rows_for_one_printed_row_are_one_exposure():
    """243808 GNC Bulk 1340 Strawberries & Cream.

    The label prints ONE folate row with two preparation-basis columns and one
    folic-acid row with the matching pair, but this record emitted the single
    printed folic-acid row as two sibling rows (435 and 400 mcg). Summing them
    charged the same form twice; they carry the same name and basis, so they
    collapse to the maximum declared value before reconciling.
    """
    assert is_folate_parent_total_duplicate_flag(_flag([
        {"ingredient": "Folate", "amount": 1450.0, "unit": "mcg DFE"},
        {"ingredient": "Folic Acid", "amount": 1479.0, "unit": "mcg DFE"},
        {"ingredient": "Folic Acid", "amount": 1360.0, "unit": "mcg DFE"},
    ])) is True


def test_declared_total_named_folic_acid_still_reconciles_with_its_form():
    """201420 Solgar Male Multiple, after the reviewed row-identity correction.

    The declared-total row was mis-named 'Folic Acid' at a DFE amount; sibling
    record 201405 transcribes the same printed panel as 'Folate 1333 mcg DFE'.
    With the parent recognised and the 800 mcg form converted on the DFE basis
    the two describe one exposure.
    """
    assert is_folate_parent_total_duplicate_flag(_flag([
        {"ingredient": "Folate", "amount": 1333.0, "unit": "mcg DFE"},
        {"ingredient": "Folic Acid", "amount": 1360.0, "unit": "mcg DFE"},
    ])) is True


# ── the declared total is not always named as one (2026-09-20) ───────────
#
# The contract used to require a parent-name vocabulary, so a declared total
# DSLD transcribed under its own form's name was invisible: both it and its
# disclosed breakdown were charged as separate exposures. 201420 (Solgar Male
# Multiple) is the live case — the declared 1333 mcg DFE row and its nested
# 800 mcg breakdown both read `Folic Acid`, where sibling record 201405 of the
# same printed panel reads `Folate 1333 mcg DFE`. The fix keeps the data
# untouched and identifies the total from structure instead: the enricher
# anchors the declared nutrient row to a Daily Value, and failing that the
# declared-total (DFE) basis itself is the evidence.

DAILY_VALUE_ANCHORED = "daily_value_confirmed_nutrient_amount"
FORM_COMPONENT_ROW = "canonical_parent_substance_amount"


def test_mis_named_declared_total_is_recognised_by_its_daily_value_anchor():
    """The real 201420 contributing-row payload, as the pipeline emitted it."""
    assert is_folate_parent_total_duplicate_flag(_flag([
        {
            "ingredient": "Folic Acid",
            "amount": 1333.0,
            "unit": "mcg DFE",
            "pct_ul_individual": 79.96,
            "ul_exposure_basis": DAILY_VALUE_ANCHORED,
            "ul_gate_eligible": True,
        },
        {
            "ingredient": "Folic Acid",
            "amount": 1360.0,
            "unit": "mcg DFE",
            "pct_ul_individual": 81.58,
            "ul_exposure_basis": FORM_COMPONENT_ROW,
            "ul_gate_eligible": True,
        },
    ])) is True


def test_mis_named_declared_total_is_recognised_without_structural_fields():
    """Older artifacts carry no exposure basis. The declared-total basis is then
    the evidence, provided the repeated rows name one identity."""
    assert is_folate_parent_total_duplicate_flag(_flag([
        {"ingredient": "Folic Acid", "amount": 1333.0, "unit": "mcg DFE"},
        {"ingredient": "Folic Acid", "amount": 1360.0, "unit": "mcg DFE"},
    ])) is True


def test_two_daily_value_anchored_folate_rows_are_not_collapsed():
    """Two rows the enricher anchored to a Daily Value are two declarations.
    Neither can be singled out as the total, so neither is discounted."""
    assert is_folate_parent_total_duplicate_flag(_flag([
        {
            "ingredient": "Folic Acid",
            "amount": 1700.0,
            "unit": "mcg DFE",
            "ul_exposure_basis": DAILY_VALUE_ANCHORED,
        },
        {
            "ingredient": "L-5-MTHF",
            "amount": 400.0,
            "unit": "mcg DFE",
            "ul_exposure_basis": DAILY_VALUE_ANCHORED,
        },
    ])) is False


def test_differently_named_dfe_rows_without_a_named_total_are_not_collapsed():
    assert is_folate_parent_total_duplicate_flag(_flag([
        {"ingredient": "Folic Acid", "amount": 1700.0, "unit": "mcg DFE"},
        {"ingredient": "L-5-MTHF", "amount": 400.0, "unit": "mcg DFE"},
    ])) is False


def test_repeated_declaration_of_one_form_is_collapsed_to_its_maximum():
    """Two printed preparation columns are alternatives, not addends. Declared
    total 1450 with 900 and 800 declared for one form is one exposure at 900;
    summing them (1700) is what breaches the total."""
    assert is_folate_parent_total_duplicate_flag(_flag([
        {"ingredient": "Folic Acid", "amount": 1450.0, "unit": "mcg DFE"},
        {"ingredient": "Folic Acid", "amount": 900.0, "unit": "mcg DFE"},
        {"ingredient": "Folic Acid", "amount": 800.0, "unit": "mcg DFE"},
    ])) is True


def test_two_different_forms_beside_a_total_are_never_collapsed_as_one():
    """A differently named row is not a repeated declaration of the total, so
    it cannot be recognised from structure alone."""
    assert is_folate_parent_total_duplicate_flag(_flag([
        {"ingredient": "Folic Acid", "amount": 1450.0, "unit": "mcg DFE"},
        {"ingredient": "L-5-MTHF", "amount": 900.0, "unit": "mcg DFE"},
        {"ingredient": "Folic Acid", "amount": 800.0, "unit": "mcg DFE"},
    ])) is False


# ── guards on the new allowances ─────────────────────────────────────────


def test_a_large_form_beside_a_small_declared_total_is_not_collapsed():
    """The subset reading must not survive the form exceeding the total."""
    assert is_folate_parent_total_duplicate_flag(_flag([
        {"ingredient": "Folate", "amount": 400.0, "unit": "mcg DFE"},
        {"ingredient": "Folic Acid", "amount": 1700.0, "unit": "mcg DFE"},
    ])) is False


def test_distinct_forms_sharing_a_basis_are_never_collapsed():
    """Collapsing is scoped to repeated declarations of the SAME form. Two
    different disclosed forms are still two disclosures and must reconcile."""
    assert is_folate_parent_total_duplicate_flag(_flag([
        {"ingredient": "Folate", "amount": 400.0, "unit": "mcg DFE"},
        {"ingredient": "L-5-MTHF", "amount": 300.0, "unit": "mcg DFE"},
        {"ingredient": "Folic Acid", "amount": 300.0, "unit": "mcg DFE"},
    ])) is False


def test_a_mass_basis_panel_never_gets_the_declared_total_subset_reading():
    """A mass-basis panel itemises form masses, where a small child beside a
    large parent is not evidence that the child is inside the parent."""
    assert is_folate_parent_total_duplicate_flag(_flag([
        {"ingredient": "Folate", "amount": 400.0, "unit": "mcg"},
        {"ingredient": "Folic Acid", "amount": 100.0, "unit": "mcg"},
    ])) is False
