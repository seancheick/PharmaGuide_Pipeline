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
