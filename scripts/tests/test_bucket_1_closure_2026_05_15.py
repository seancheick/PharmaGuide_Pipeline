"""
Bucket 1 (NOT_SCORED) tail closure — 2026-05-15.

Bucket 1 trajectory: 128 (May 13) → 42 (May 14) → 11 (May 15).
The 11 split into:
  - 5 NO_ACTIVES_DETECTED (DSLD authoring gaps — un-fixable)
  - 6 UNMAPPED_ACTIVE_INGREDIENT (fixable with targeted aliases / cleaner regex)

This file pins the four targeted fixes that close the 6 fixable products:

  1. IQM alias: collagen / hydrolyzed collagen peptides
     ← 'hydrolyzed collagen types 1 and 3' + 'collagen types 1 and 3'
     Closes Doctors_Best Collagen+Peptan family (203283, 203354, 209444).

  2. IQM alias: protein / protein (unspecified)
     ← 'egg white albumin'
     Closes GNC Egg Albumin Protein (82901).

  3. IQM alias: fish_oil / natural triglyceride
     ← 'fish oil triglycerides'
     Closes Doctors_Best Natural Vision Enhancers (269603).

  4. Cleaner regex: suffix-less 'less than N%' fragments
     ← _is_label_header now matches 'less than 0.1%' and '<0.1%'
     Closes GNC Aloe Vera Juice (214221) — raw DSLD parsed a label fragment
     into inactiveIngredients[] which then got promoted to active by the
     enricher and triggered UNMAPPED_ACTIVE_INGREDIENT.

All four are strict same-compound aliases (no new IQM entries, no invented
bio_scores), or pure regex-widening for a clear label artifact.
"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from enhanced_normalizer import EnhancedDSLDNormalizer


IQM_PATH = Path(__file__).resolve().parent.parent / "data" / "ingredient_quality_map.json"


# ---------------------------------------------------------------------------
# Data contract: IQM aliases present in the expected forms
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def iqm():
    return json.loads(IQM_PATH.read_text())


@pytest.mark.parametrize(
    "canonical_id,form_name,expected_alias",
    [
        # Fix 1: Collagen+Peptan family (3 products)
        ("collagen", "hydrolyzed collagen peptides", "hydrolyzed collagen types 1 and 3"),
        ("collagen", "hydrolyzed collagen peptides", "collagen types 1 and 3"),
        # Fix 2: Egg White Albumin (1 product)
        ("protein", "protein (unspecified)", "egg white albumin"),
        # Fix 3: Fish Oil Triglycerides (1 product)
        ("fish_oil", "natural triglyceride", "fish oil triglycerides"),
    ],
)
def test_iqm_alias_present_in_expected_form(iqm, canonical_id, form_name, expected_alias):
    """The four targeted aliases must be present in the IQM at the expected form.

    These were added to close the 6 fixable products in Bucket 1's UNMAPPED tail.
    If any is removed in a future edit, Bucket 1 re-grows and the affected
    products fall out of the scored catalog.
    """
    assert canonical_id in iqm, f"canonical_id {canonical_id!r} missing from IQM"
    forms = iqm[canonical_id].get("forms", {})
    assert form_name in forms, (
        f"form {form_name!r} missing from canonical_id={canonical_id!r}. "
        f"Available forms: {list(forms.keys())}"
    )
    aliases_lower = [a.lower() for a in forms[form_name].get("aliases", [])]
    assert expected_alias.lower() in aliases_lower, (
        f"alias {expected_alias!r} missing from "
        f"{canonical_id}.forms[{form_name!r}].aliases. "
        f"Bucket 1 closure regressed — re-add the alias."
    )


def test_collagen_hydrolyzed_form_bio_score_unchanged(iqm):
    """Sanity check — the alias add must NOT have changed bio_score.

    If a future edit silently bumps bio_score on the collagen hydrolyzed form,
    it changes the score of every Collagen+Peptan product. Pin the value.
    """
    form = iqm["collagen"]["forms"]["hydrolyzed collagen peptides"]
    assert form["bio_score"] == 11, (
        f"hydrolyzed collagen peptides bio_score changed from 11 to "
        f"{form['bio_score']} — confirm this was intentional and update test."
    )


def test_protein_unspecified_form_bio_score_unchanged(iqm):
    """Same sanity check for protein (unspecified). bio_score=5 is the
    conservative catchall for generic proteins (whey, milk, soy, egg).
    """
    form = iqm["protein"]["forms"]["protein (unspecified)"]
    assert form["bio_score"] == 5, (
        f"protein (unspecified) bio_score changed from 5 to "
        f"{form['bio_score']} — confirm this was intentional and update test."
    )


# NOTE: a metadata reconciliation test (declared total_form_aliases ==
# actual counted) was scoped out of this closure on 2026-05-15. Pre-existing
# drift of ~131 entries was discovered (declared=11983 vs counted=~12114
# BEFORE this closure's 4 additions). That drift is an IQM-authoring-pipeline
# hygiene issue, not part of Bucket 1's NOT_SCORED fix, and adding the
# assertion here would block this closure on a separate cleanup. Tracked
# as a follow-up: rerun the IQM statistics maintenance script and
# reconcile _metadata.


# ---------------------------------------------------------------------------
# Cleaner regex: _is_label_header catches suffix-less '%' fragments
# ---------------------------------------------------------------------------


class TestLabelHeaderSuffixlessFragments:
    """Fix 4 — _is_label_header now matches bare-percentage fragments that
    DSLD occasionally parses into inactiveIngredients[]."""

    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    @pytest.mark.parametrize(
        "fragment",
        [
            "less than 0.1%",   # the exact text from GNC Aloe Vera Juice (214221)
            "less than 1%",
            "less than 2%",
            "less than 5%",
            "<0.1%",
            "< 0.1%",
            "<1%",
            "< 2%",
            # Whitespace tolerance
            "  less than 0.1%  ",
        ],
    )
    def test_suffixless_percentage_fragments_detected_as_headers(self, normalizer, fragment):
        """These bare-percentage strings are label artifacts, not ingredients.
        They have no forms[] children, so _is_label_header marking them
        triggers _expand_header_forms_for_processing → empty expansion →
        the fragment is silently dropped before reaching the enricher.
        """
        assert normalizer._is_label_header(fragment.strip()) is True, (
            f"label fragment {fragment!r} not detected — it would slip through "
            f"to the enricher, get promoted from inactive to active, fail to "
            f"map to any canonical, and trigger UNMAPPED_ACTIVE_INGREDIENT → "
            f"NOT_SCORED. This is the exact failure mode of 214221 (GNC Aloe "
            f"Vera Juice). Re-tighten the regex."
        )

    @pytest.mark.parametrize(
        "real_ingredient",
        [
            "2% Milk Thistle Extract",     # already pinned in test_pipeline_regressions
            "5% Hydroxycitric Acid",
            "Standardized to 95% Curcuminoids",
            "0.3% Salicin",
            "20% Withanolides",
        ],
    )
    def test_real_ingredients_with_percentages_not_misclassified(
        self, normalizer, real_ingredient
    ):
        """Negative control: the suffix-less regex must NOT match real
        ingredient names that happen to contain a percentage. These are
        legitimate standardized-extract names that the cleaner must keep.
        """
        assert normalizer._is_label_header(real_ingredient) is False, (
            f"{real_ingredient!r} mistakenly treated as a label header — "
            f"the regex is too aggressive. It must only match BARE "
            f"'less than N%' / '<N%' strings, not ingredients that contain "
            f"a percentage."
        )

    def test_existing_with_of_suffix_patterns_still_match(self, normalizer):
        """Regression guard — the new patterns must NOT break the existing
        patterns that require 'of:' suffix.
        """
        # These are pinned by test_pipeline_regressions.py too, but cheap to
        # re-verify here so a future regex edit that breaks them fails this
        # test alongside the closure tests.
        assert normalizer._is_label_header("Less than 2% of:") is True
        assert normalizer._is_label_header("Contains less than 2% of:") is True
        assert normalizer._is_label_header("< 2% of:") is True


# ---------------------------------------------------------------------------
# Enricher promotion guard: _excluded_text_reason catches decimal percentages
#
# This is the LOAD-BEARING fix for product 214221. The cleaner's
# _is_label_header (tested above) is a defense-in-depth check; the actual
# code path that promotes "less than 0.1%" to active runs through the
# enricher's _excluded_text_reason at the start of _should_promote_to_scorable.
# The pre-fix regex required integer digits (\d+), so decimal percentages
# like "less than 0.1%" slipped past and got promoted.
# ---------------------------------------------------------------------------


class TestExcludedTextReasonDecimalPercentages:
    """Fix 4 (real load-bearing version) — _excluded_text_reason must reject
    decimal percentage label phrases before the promotion engine sees them."""

    @pytest.fixture
    def enricher(self):
        # Lazy import: enrich_supplements_v3 has heavy import-time data loads
        from enrich_supplements_v3 import SupplementEnricherV3
        return SupplementEnricherV3()

    @pytest.mark.parametrize(
        "fragment",
        [
            "less than 0.1%",   # exact text from 214221
            "less than 0.5%",
            "less than 1%",     # integer still works
            "less than 2.5%",
            "<0.1%",
            "< 0.1%",
            "<2.5%",
            "Contains less than 0.1%",
            "Contains < 0.5%",
            "May also contain < 0.1%",
        ],
    )
    def test_decimal_percentage_label_phrases_excluded_from_promotion(
        self, enricher, fragment
    ):
        """If _excluded_text_reason returns None, the promotion engine will
        evaluate this fragment as if it were a real ingredient. For decimal
        percentages, that produces UNMAPPED_ACTIVE_INGREDIENT → NOT_SCORED.
        The function must return a non-None skip reason.
        """
        reason = enricher._excluded_text_reason(fragment)
        assert reason is not None, (
            f"_excluded_text_reason({fragment!r}) returned None — the "
            f"promotion engine will treat this as a real ingredient and "
            f"trigger UNMAPPED_ACTIVE_INGREDIENT. This is the exact failure "
            f"mode that excluded 214221 (GNC Aloe Vera Juice). Re-check the "
            f"regex patterns at line ~3282 of enrich_supplements_v3.py — "
            f"\\d+ must accept decimals (\\d+(?:\\.\\d+)?)."
        )

    @pytest.mark.parametrize(
        "real_ingredient",
        [
            "Vitamin C",
            "Hydrolyzed Collagen",
            "2% Milk Thistle Extract",
            "Standardized to 95% Curcuminoids",
        ],
    )
    def test_real_ingredients_not_excluded(self, enricher, real_ingredient):
        """Negative control: real ingredient names with percentages must NOT
        be flagged as label phrases."""
        reason = enricher._excluded_text_reason(real_ingredient)
        assert reason is None, (
            f"_excluded_text_reason({real_ingredient!r}) returned {reason!r} — "
            f"a legitimate ingredient is being filtered out. The regex is "
            f"too aggressive; restrict it to bare 'less than N%' / '<N%' forms."
        )


# ---------------------------------------------------------------------------
# Document the 6 dsld_ids this closure is intended to recover
# ---------------------------------------------------------------------------


# These ids are the 6 fixable products from Bucket 1's UNMAPPED tail.
# A full end-to-end verification (run the pipeline on these brand dirs and
# assert all 6 land in the scored catalog, not excluded_by_gate) lives in
# scripts/tests/test_recalled_2026_05_smoke.py style — this file pins the
# unit-level changes, not the integration result.
BUCKET_1_CLOSURE_DSLD_IDS = (
    "203283",  # Doctors_Best Collagen Types 1 and 3 with Peptan 500 mg
    "203354",  # Doctors_Best Collagen Types 1 and 3 with Peptan 1000 mg
    "209444",  # Doctors_Best Collagen Types 1 and 3 with Peptan + Vit C
    "82901",   # GNC Egg Albumin Protein
    "214221",  # GNC Aloe Vera Juice Natural Wild Berry Flavor
    "269603",  # Doctors_Best Natural Vision Enhancers
)


def test_closure_dsld_id_manifest_unchanged():
    """If a future commit wants to drop one of these from the closure set,
    it should update this tuple deliberately (and probably also adjust the
    triage doc + commit message). Pin the count + IDs as a contract.
    """
    assert len(BUCKET_1_CLOSURE_DSLD_IDS) == 6
    assert set(BUCKET_1_CLOSURE_DSLD_IDS) == {
        "203283", "203354", "209444", "82901", "214221", "269603",
    }
