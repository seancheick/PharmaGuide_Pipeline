"""
Sprint E1.2.2.c — standardization_note regression tests.

Extract standardization strings ("5% withanolides", "95% curcuminoids")
from ingredient notes / matched_form. Tight regex only — dev rule:
"If I'm not 100% sure the % belongs to this compound, return null."

Allowed compounds (conservative starter list; expand case-by-case):
  withanolides | curcuminoids | ginsenosides | rosavins | bacosides |
  saponins | piperine | EGCG | silymarin

Intentionally narrow to avoid false positives from:
  * absorption percentages ("90% absorbed")
  * bioavailability ("~4% bioavailability")
  * survival rates ("~30-50% survival")
  * generic "standardized extract" marketing language

Extracted string shape: ``"5% withanolides"`` — just percent + compound,
normalized to lowercase compound. Returns ``None`` when nothing matches.

Covers invariant #6 (standardization_note_preserved) from E1.0.1.
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

from scripts.build_final_db import _compute_standardization_note  # noqa: E402


# ---------------------------------------------------------------------------
# Positive cases — real standardization phrases must extract correctly
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("Standardized to 5% withanolides", "5% withanolides"),
    ("95% curcuminoids", "95% curcuminoids"),
    ("Contains 10% ginsenosides", "10% ginsenosides"),
    ("Standardized to 3% rosavins and 1% salidrosides", "3% rosavins"),
    ("55% bacosides", "55% bacosides"),
    ("Standardized to 20% saponins", "20% saponins"),
    ("95%+ piperine", "95% piperine"),
    ("≥50% EGCG", "50% EGCG"),
    ("80% silymarin", "80% silymarin"),
])
def test_positive_cases_extract(text: str, expected: str) -> None:
    ing = {"notes": text}
    assert _compute_standardization_note(ing) == expected


def test_ksm_66_canary_string_extracts() -> None:
    """Canary 306237: KSM-66 notes carry "~5% withanolides"."""
    ing = {"notes": "Patented full-spectrum root-only extract with ~5% withanolides (Ixoreal Biomed)."}
    assert _compute_standardization_note(ing) == "5% withanolides"


def test_bioperine_canary_piperine_extracts() -> None:
    """Canary 306237: Bioperine notes carry "95%+ piperine"."""
    ing = {"notes": "BioPerine (Sabinsa, 95%+ piperine) is the patented standardized form."}
    assert _compute_standardization_note(ing) == "95% piperine"


def test_green_tea_egcg_extracts_from_matched_form() -> None:
    """Canary 1036 Green Tea leaf extract: matched_form="green tea extract (50% EGCG)"."""
    ing = {"matched_form": "green tea extract (50% EGCG)"}
    assert _compute_standardization_note(ing) == "50% EGCG"


# ---------------------------------------------------------------------------
# Negative cases (CRITICAL) — dev's explicit list + absorption percents
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "High withanolide content",           # no %
    "Standardized extract",                # no %, no compound
    "Curcuminoid complex",                 # no %
    "Contains 500 mg curcuminoids",        # mg, not %
    "90% absorbed",                        # bioavailability, not a compound
    "~4% bioavailability",                 # likewise
    "~30-50% survival",                    # survival rate
    "Provides ~92% pantothenic acid by weight",  # weight share, not standardization
    "40% elemental calcium",               # elemental content, not standardization
    "highly standardized",                  # marketing, no %
    "",                                     # empty string
])
def test_negative_cases_return_none(text: str) -> None:
    ing = {"notes": text}
    assert _compute_standardization_note(ing) is None, (
        f"false-positive match on: {text!r}"
    )


def test_empty_ingredient_returns_none() -> None:
    assert _compute_standardization_note({}) is None


def test_non_string_notes_returns_none() -> None:
    assert _compute_standardization_note({"notes": None}) is None
    assert _compute_standardization_note({"notes": 42}) is None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_trailing_qualifier_does_not_break_match() -> None:
    """Sprint dev edge case: "Standardized to 5% withanolides (min)"."""
    ing = {"notes": "Standardized to 5% withanolides (min)."}
    assert _compute_standardization_note(ing) == "5% withanolides"


def test_case_insensitive_compound_match() -> None:
    ing = {"notes": "Contains 5% WITHANOLIDES"}
    # Output normalizes compound to canonical casing from the allowlist
    result = _compute_standardization_note(ing)
    assert result is not None
    assert "withanolides" in result.lower()


def test_fractional_percent_rejected() -> None:
    """Keep the starter regex tight — integer percents only in v1."""
    ing = {"notes": "5.5% withanolides"}
    # Dev rule: conservative. If we later want fractional support, add
    # explicitly; until then, reject to avoid encoding false precision.
    result = _compute_standardization_note(ing)
    # Either None or exactly "5% withanolides" — whichever the impl chooses.
    # The test locks the behavior — current impl: None (tight integer-only).
    assert result is None


def test_range_percent_rejected() -> None:
    """Ranges "5-10% withanolides" can't be faithfully reduced to a
    single number — return None (dev: don't parse ranges)."""
    ing = {"notes": "Standardized to 5-10% withanolides"}
    assert _compute_standardization_note(ing) is None


def test_notes_as_list_of_strings_handled() -> None:
    """Enricher may emit notes as list[str]; scan each entry."""
    ing = {"notes": ["General blurb.", "Standardized to 5% withanolides."]}
    assert _compute_standardization_note(ing) == "5% withanolides"


def test_multiple_compound_claims_returns_first_match() -> None:
    """Conservative: return the FIRST match in the text (document order)
    — don't try to merge or list all claims."""
    ing = {"notes": "Contains 5% withanolides and 95% piperine."}
    result = _compute_standardization_note(ing)
    assert result == "5% withanolides"


# ---------------------------------------------------------------------------
# Dev's critical guardrail — standardization_note does NOT modify dose
# ---------------------------------------------------------------------------

def test_standardization_extraction_does_not_mutate_ingredient() -> None:
    """The helper reads only; must not write back fields on the input dict."""
    ing = {
        "name": "Ashwagandha",
        "quantity": 600,
        "unit": "mg",
        "notes": "Standardized to 5% withanolides",
    }
    before = dict(ing)
    _compute_standardization_note(ing)
    assert ing == before, "ingredient dict was mutated by helper"


# ---------------------------------------------------------------------------
# Source priority — prefer matched_form, then notes, then raw_source_text
# ---------------------------------------------------------------------------

def test_matched_form_checked_first() -> None:
    """DSLD-authored matched_form is most structured; prefer it when
    present."""
    ing = {
        "matched_form": "green tea extract (50% EGCG)",
        "notes": "Some other text with 5% withanolides",
    }
    # matched_form wins
    assert _compute_standardization_note(ing) == "50% EGCG"


def test_notes_fallback_when_matched_form_lacks_match() -> None:
    ing = {
        "matched_form": "ashwagandha (unspecified)",
        "notes": "Standardized to 5% withanolides",
    }
    assert _compute_standardization_note(ing) == "5% withanolides"
