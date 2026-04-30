#!/usr/bin/env python3
"""
Clinical evidence matching must be hyphen-insensitive.

Bug discovered 2026-04-29: `_clinical_study_match` compared ingredient
names using `_normalize_text` which preserves hyphens. The evidence
database stores some entries with hyphens ("Alpha-Lipoic Acid") and
others without ("Alpha Lipoic Acid"). Supplement labels are inconsistent
about hyphen usage, causing silent C-section failures (matched_entries=0)
on real products that should have evidence matches.

Examples affected (sample):
- "Alpha Lipoic Acid" (label) vs "Alpha-Lipoic Acid" (DB)
- "5 Methyltetrahydrofolate" vs "5-Methyltetrahydrofolate"
- "Coenzyme Q10" vs "Coenzyme-Q10"
- "N Acetyl Cysteine" vs "N-Acetyl Cysteine"
- "L Carnitine" vs "L-Carnitine"

Fix: `_clinical_study_match` must use a hyphen-stripping normalized key
(make_normalized_key) as a secondary comparison pass, similar to how
`_check_additive_match` does for harmful-additive matching.
"""

import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
logging.disable(logging.CRITICAL)

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


@pytest.mark.parametrize("label_term,study_name", [
    ("Alpha Lipoic Acid",    "Alpha-Lipoic Acid"),
    ("Alpha-Lipoic Acid",    "Alpha Lipoic Acid"),
    ("Coenzyme Q10",         "Coenzyme-Q10"),
    ("Coenzyme-Q10",         "Coenzyme Q10"),
    ("5 Methyltetrahydrofolate", "5-Methyltetrahydrofolate"),
    ("N Acetyl Cysteine",    "N-Acetyl Cysteine"),
    ("N-Acetyl-Cysteine",    "N Acetyl Cysteine"),
    ("L Carnitine",          "L-Carnitine"),
    ("Beta Alanine",         "Beta-Alanine"),
    # Note: "Co Enzyme Q10" (split tokens) is beyond hyphen-only scope —
    # would require token-concatenation logic. Real DSLD labels use
    # "Coenzyme Q10" or "CoQ10" (the alias path handles abbreviations).
])
def test_clinical_match_hyphen_insensitive(enricher, label_term, study_name):
    """Hyphen presence/absence must NOT prevent evidence-DB matching."""
    study = {
        "id": "TEST_STUDY",
        "standard_name": study_name,
        "study_type": "rct_multiple",
        "evidence_level": "ingredient-human",
    }
    result = enricher._clinical_study_match([label_term], study)
    assert result is not None, (
        f"Hyphen mismatch silently breaks evidence: label={label_term!r} "
        f"vs study={study_name!r}"
    )


def test_clinical_match_negative_substantive_difference(enricher):
    """Hyphen-insensitive must NOT make truly different names match."""
    study = {
        "id": "TEST_STUDY",
        "standard_name": "Curcumin",
        "study_type": "rct_multiple",
        "evidence_level": "ingredient-human",
    }
    # Curcumin vs Magnesium are genuinely different — must NOT match
    result = enricher._clinical_study_match(["Magnesium"], study)
    assert result is None


def test_clinical_match_alias_path_still_works(enricher):
    """Aliases must continue to match correctly."""
    study = {
        "id": "TEST_STUDY",
        "standard_name": "Alpha-Lipoic Acid",
        "aliases": ["ALA", "thioctic acid"],
        "study_type": "rct_multiple",
        "evidence_level": "ingredient-human",
    }
    # Alias 'ALA' should match
    result = enricher._clinical_study_match(["ALA"], study)
    assert result is not None
    assert result.get("method") == "alias"


def test_clinical_match_real_ala_evidence_fires(enricher):
    """End-to-end check against the real backed_clinical_studies.json
    INGR_ALPHA_LIPOIC_ACID entry (the bug repro)."""
    import json
    ev = json.load(open(os.path.join(
        os.path.dirname(__file__), "..", "data", "backed_clinical_studies.json"
    )))
    ala_study = next(
        (s for s in ev["backed_clinical_studies"]
         if s.get("id") == "INGR_ALPHA_LIPOIC_ACID"),
        None,
    )
    assert ala_study, "Real ALA evidence entry must exist"
    # Pure Encapsulations product label says "Alpha Lipoic Acid" (no hyphen)
    result = enricher._clinical_study_match(["Alpha Lipoic Acid"], ala_study)
    assert result is not None, (
        "Real Pure Encapsulations Alpha Lipoic Acid 100mg product must match "
        "the INGR_ALPHA_LIPOIC_ACID evidence record"
    )
