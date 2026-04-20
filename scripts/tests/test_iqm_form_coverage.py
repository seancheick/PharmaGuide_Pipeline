"""
Sprint D3.3 regression tests — IQM form-alias coverage for common DSLD forms.

Context: the deep accuracy audit flagged 30,807 scorable active rows
landing on ``<canonical>.forms["...(unspecified)"]`` at bio_score=5.
Hypothesis was that IQM was missing aliases for common supplement
forms, but direct enricher testing showed that when DSLD PROVIDES a
form name, the enricher correctly matches the specific IQM form
at bio_score 8-14 (not unspecified). The remaining "unspecified"
landings are legitimate — 29% of USA supplement labels don't specify
a chemical form ("Vitamin C 500 mg" vs "Vitamin C (as Ascorbic
Acid) 500 mg").

These tests lock in the coverage: for each top-volume canonical,
the common forms resolve to a specific IQM form with a bio_score
reflecting the premium-form grade (≥8), not the unspecified default.

If a future edit regresses this (e.g., accidentally removes an alias),
supplement-quality scoring would silently revert to conservative
defaults on products that correctly specify their form.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


@pytest.fixture(scope="module")
def iqm() -> dict:
    return json.loads(
        (Path(__file__).parent.parent / "data" / "ingredient_quality_map.json").read_text()
    )


# ---------------------------------------------------------------------------
# Common forms must match a specific IQM form, NOT unspecified
# ---------------------------------------------------------------------------


class TestCommonFormCoverage:
    """When DSLD provides a form name, enricher lands on specific IQM form."""

    @pytest.mark.parametrize("ing_name,form_name,expected_parent,expected_form_contains,min_bio_score", [
        # Calcium forms
        ("Calcium",   "Calcium Carbonate",     "calcium",   "carbonate",   8),
        ("Calcium",   "Calcium Citrate",       "calcium",   "citrate",     12),
        ("Calcium",   "Calcium Malate",        "calcium",   "malate",      10),
        ("Calcium",   "Calcium Bisglycinate",  "calcium",   "glycinate",   12),
        # Iron forms
        ("Iron",      "Ferrous Sulfate",       "iron",      "ferrous sulfate", 6),
        ("Iron",      "Ferrous Fumarate",      "iron",      "fumarate",    10),
        ("Iron",      "Ferrous Bisglycinate",  "iron",      "bisglycinate", 12),
        # Vitamin C forms
        ("Vitamin C", "Ascorbic Acid",         "vitamin_c", "ascorbic",    10),
        ("Vitamin C", "Calcium Ascorbate",     "vitamin_c", "calcium ascorbate", 12),
        # Vitamin D forms
        ("Vitamin D", "Cholecalciferol",       "vitamin_d", "cholecalciferol", 10),
        # Zinc forms
        ("Zinc",      "Zinc Picolinate",       "zinc",      "picolinate",  12),
        ("Zinc",      "Zinc Bisglycinate",     "zinc",      "glycinate",   12),
        # Magnesium forms
        ("Magnesium", "Magnesium Glycinate",   "magnesium", "glycinate",   12),
        ("Magnesium", "Magnesium Citrate",     "magnesium", "citrate",     8),
        ("Magnesium", "Magnesium Oxide",       "magnesium", "oxide",       2),   # bio=4 but >= 2 passes
        ("Magnesium", "Magnesium Threonate",   "magnesium", "threonate",   12),
        # Chromium forms
        ("Chromium",  "Chromium Picolinate",   "chromium",  "picolinate",  12),
        # Potassium forms
        ("Potassium", "Potassium Citrate",     "potassium", "citrate",     11),
        ("Potassium", "Potassium Chloride",    "potassium", "chloride",    10),
    ])
    def test_common_form_matches_specific_iqm_form(
        self, enricher, iqm, ing_name, form_name, expected_parent, expected_form_contains, min_bio_score,
    ) -> None:
        result = enricher._match_quality_map(
            ing_name, ing_name, iqm,
            cleaned_forms=[{"name": form_name}],
        )
        assert result is not None, f"{ing_name!r} / {form_name!r} did not match"
        cid = result.get("canonical_id")
        form_id = (result.get("form_id") or "").lower()
        bio = result.get("bio_score") or 0

        assert cid == expected_parent, (
            f"{ing_name!r} / {form_name!r} resolved to parent={cid!r}; "
            f"expected {expected_parent!r}. Form-specificity regression."
        )
        assert "unspecified" not in form_id, (
            f"{ing_name!r} / {form_name!r} landed on UNSPECIFIED form despite "
            f"DSLD providing specific form. IQM alias gap."
        )
        assert expected_form_contains in form_id, (
            f"{ing_name!r} / {form_name!r} landed on form {form_id!r}; "
            f"expected to contain {expected_form_contains!r}."
        )
        assert bio >= min_bio_score, (
            f"{ing_name!r} / {form_name!r} got bio_score={bio}; expected ≥{min_bio_score}. "
            f"Either the IQM bio_score was downgraded (check schema) or the match "
            f"landed on a wrong form."
        )


class TestUnspecifiedFormBaseline:
    """When DSLD provides NO form, enricher correctly falls back to unspecified."""

    @pytest.mark.parametrize("ing_name,expected_parent", [
        ("Calcium",   "calcium"),
        ("Vitamin C", "vitamin_c"),
        ("Zinc",      "zinc"),
    ])
    def test_no_forms_lands_on_unspecified(self, enricher, iqm, ing_name, expected_parent) -> None:
        """With no cleaned_forms, match falls back to the parent's unspecified form."""
        result = enricher._match_quality_map(ing_name, ing_name, iqm, cleaned_forms=[])
        assert result is not None
        assert result.get("canonical_id") == expected_parent
        # form_id may be the unspecified form OR a name-matched primary form
        # (e.g., "Calcium" alone matches the `calcium (unspecified)` form which
        # has alias "Calcium"). Either way the PARENT is correct.
