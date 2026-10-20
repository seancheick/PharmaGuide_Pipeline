"""Export matches each active row to its own dosage-normalization entry.

Solgar 218842 lists Beta-Carotene twice: 2,500 IU under Vitamin A
(ingredientRows[0].nestedRows[1]) and an undosed carotenoid-blend member
(ingredientRows[14].nestedRows[1]). Keyed by name alone, the undosed entry
replaced the converted 750 mcg RAE value and the blob exported None, which the
raw-to-final gate blocks as UNSAFE_UNIT_CONVERSION.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from build_final_db import _normalized_dose_entry  # noqa: E402


def _entry(source_field, amount, unit, normalized):
    return {
        "original_name": "Beta-Carotene",
        "original_amount": amount,
        "original_unit": unit,
        "normalized_amount": normalized,
        "normalized_unit": "mcg RAE" if normalized is not None else None,
        "source_field": source_field,
    }


NORMALIZED = [
    _entry("activeIngredients[2]", 2500.0, "IU", 750.0),
    _entry("activeIngredients[18]", 0.0, "NP", None),
]


def test_same_name_rows_keep_their_own_conversion():
    dosed = _normalized_dose_entry(NORMALIZED, 2, "Beta-Carotene", "Beta-Carotene")
    undosed = _normalized_dose_entry(NORMALIZED, 18, "Beta-Carotene", "Beta-Carotene")
    assert dosed["normalized_amount"] == 750.0
    assert dosed["normalized_unit"] == "mcg RAE"
    assert undosed["normalized_amount"] is None


def test_row_without_a_positional_entry_falls_back_to_name():
    legacy = [{"original_name": "Vitamin D3", "normalized_amount": 25.0, "normalized_unit": "mcg"}]
    assert _normalized_dose_entry(legacy, 0, "Vitamin D3", "Vitamin D3")["normalized_amount"] == 25.0
    assert _normalized_dose_entry(legacy, 0, "", "Vitamin D3")["normalized_amount"] == 25.0


def test_supplement_facts_positions_never_match_active_rows():
    other = [_entry("supplementFacts[2]", 0.0, "NP", None),
             _entry("activeIngredients[5]", 2500.0, "IU", 750.0)]
    # Position 2 in supplementFacts is a different list; it must not decide
    # active row 2. The name fallback is used instead.
    assert _normalized_dose_entry(other, 5, "Beta-Carotene", "Beta-Carotene")["normalized_amount"] == 750.0


def test_dict_shaped_normalization_is_still_read_by_name():
    by_name = {"Beta-Carotene": {"normalized_amount": 750.0}}
    assert _normalized_dose_entry(by_name, 3, "Beta-Carotene", "Beta-Carotene")["normalized_amount"] == 750.0


def test_missing_entry_is_empty():
    assert _normalized_dose_entry([], 0, "Zinc", "Zinc") == {}
    assert _normalized_dose_entry(None, 0, "Zinc", "Zinc") == {}


def test_a_siblings_positional_conversion_is_never_a_name_fallback():
    # A missing/omitted normalization must stay unknown rather than borrowing
    # the amount of a same-name row whose different source is explicitly known.
    assert _normalized_dose_entry(NORMALIZED[:1], 18, "Beta-Carotene", "Beta-Carotene") == {}


def test_ambiguous_legacy_same_name_conversions_stay_unknown():
    legacy = [dict(row, source_field="") for row in NORMALIZED]
    assert _normalized_dose_entry(legacy, 2, "Beta-Carotene", "Beta-Carotene") == {}
