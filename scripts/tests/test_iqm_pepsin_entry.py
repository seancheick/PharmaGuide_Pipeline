#!/usr/bin/env python3
"""
IQM coverage: Pepsin (Batch 5 IQM gap fill #1).

Pepsin (UNII: GID333S43J, CUI: C0030909, RxCUI: 8016) is a gastric protease
listed in 255 DSLD products and used in 16+ multi-enzyme supplements that
were previously skipped as `recognized_non_scorable` (because pepsin lived
in `other_ingredients.json` but had no IQM scoring entry). Adding the IQM
entry gives those products a real Section A1 score.

Identifiers verified via:
- FDA GSRS: UNII GID333S43J, CAS 9001-75-6, CFR 21 CFR 184.1595 (GRAS),
  21 CFR 310.540 (in OTC drug products)
- UMLS: CUI C0030909 ("pepsin A", source: MTH)
- DSLD: 255 product references

No duplicate entry exists — `other_ingredients.json:PII_PEPSIN` is for
recognition only and carries no scoring data.
"""

import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logging.disable(logging.CRITICAL)


@pytest.fixture(scope="module")
def iqm():
    import json
    return json.load(open(os.path.join(
        os.path.dirname(__file__), "..", "data", "ingredient_quality_map.json"
    )))


def test_pepsin_iqm_entry_exists(iqm):
    """Pepsin must be a top-level IQM entry (not just under digestive_enzymes blend)."""
    assert "pepsin" in iqm, "IQM must have a top-level 'pepsin' entry"


def test_pepsin_iqm_identifiers_match_other_ingredients(iqm):
    """CUI + UNII must match the canonical record in other_ingredients.json
    so we never have two entries claiming different identities for the same
    substance."""
    pepsin = iqm["pepsin"]
    assert pepsin.get("cui") == "C0030909", (
        f"Pepsin CUI must be C0030909 (UMLS-verified); got {pepsin.get('cui')}"
    )
    ext = pepsin.get("external_ids", {})
    assert ext.get("unii") == "GID333S43J", (
        f"Pepsin UNII must be GID333S43J (FDA GSRS-verified); got {ext.get('unii')}"
    )


def test_pepsin_iqm_has_scorable_form(iqm):
    """Pepsin must have at least one form with score + bio_score so the
    enricher routes products containing it through the scoring path
    (not skipped as recognized_non_scorable)."""
    pepsin = iqm["pepsin"]
    forms = pepsin.get("forms", {})
    assert forms, "Pepsin must have at least one form definition"

    found_scorable = False
    for form_key, form in forms.items():
        if (
            isinstance(form, dict)
            and isinstance(form.get("score"), (int, float))
            and isinstance(form.get("bio_score"), (int, float))
        ):
            found_scorable = True
            # Range sanity vs other digestive enzymes:
            #   alpha_amylase: score 15, bio 12 (excellent absorption)
            #   lysozyme:      score 13, bio 10 (limited oral)
            # Pepsin sits between (acid-pH only, denatured post-gastric)
            assert 8 <= form["score"] <= 16, (
                f"Pepsin score should sit ~10-14 (acid-pH-only enzyme); got {form['score']}"
            )
            assert 6 <= form["bio_score"] <= 14, (
                f"Pepsin bio_score should sit ~8-12; got {form['bio_score']}"
            )
            assert form.get("dosage_importance") is not None
            break
    assert found_scorable, "At least one pepsin form must carry score + bio_score"


def test_pepsin_iqm_aliases_cover_common_label_renderings(iqm):
    """Aliases must include forms used on supplement labels."""
    pepsin = iqm["pepsin"]
    forms = pepsin.get("forms", {})
    all_aliases = set()
    for form in forms.values():
        if isinstance(form, dict):
            for a in form.get("aliases", []) or []:
                all_aliases.add(a.lower().strip())
    # Common label renderings
    expected = {"pepsin", "pepsin enzyme", "pepsin powder"}
    missing = expected - all_aliases
    assert not missing, f"Pepsin entry missing common aliases: {missing}"


def test_pepsin_category_is_enzymes(iqm):
    pepsin = iqm["pepsin"]
    assert pepsin.get("category") == "enzymes"
    assert pepsin.get("category_enum") == "enzymes"


def test_pepsin_match_rules_present(iqm):
    """Match rules block consistent with other enzyme entries."""
    pepsin = iqm["pepsin"]
    mr = pepsin.get("match_rules", {})
    assert mr.get("match_mode") in ("alias_and_fuzzy", "alias_only", "exact")
    assert mr.get("confidence") in ("high", "medium")
