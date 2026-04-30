#!/usr/bin/env python3
"""
IQM coverage: Glucomannan (Batch 5 — verified pre-existing).

VERIFIED ALREADY IN IQM under `fiber` parent → form `konjac glucomannan`
(bio=9, score=12, natural=true). Per the user's "no double entry" rule,
do NOT create a duplicate top-level glucomannan entry. The 5 audit fires
must be tracked through alias coverage instead.

This test pins down the contract: glucomannan must be reachable via the
existing fiber/konjac glucomannan form aliases. Any future IQM cleanup
that removes this form would re-open the gap.

Identifiers verified during audit (for future reference if a top-level
entry ever becomes warranted):
- FDA GSRS: UNII 36W3E5TAMG ("KONJAC MANNAN"), CAS 37220-17-0, RxCUI 11454
- UMLS: CUI C0043572 (glucomannan, MTH)
- DSLD: 203 product references under "Botanical|Glucomannan"
"""

import json
import os

import pytest


@pytest.fixture(scope="module")
def iqm():
    return json.load(open(os.path.join(
        os.path.dirname(__file__), "..", "data", "ingredient_quality_map.json"
    )))


def test_glucomannan_form_exists_under_fiber_parent(iqm):
    """Pre-existing IQM coverage: fiber/konjac glucomannan."""
    fiber = iqm.get("fiber", {})
    forms = fiber.get("forms", {})
    assert "konjac glucomannan" in forms, (
        "Glucomannan must remain reachable as fiber/konjac glucomannan form"
    )


def test_glucomannan_aliases_cover_label_renderings(iqm):
    """The form's aliases must cover the renderings actually used on
    supplement labels so the enricher can match them."""
    fiber = iqm.get("fiber", {})
    form = fiber.get("forms", {}).get("konjac glucomannan", {})
    aliases = {a.lower().strip() for a in form.get("aliases", []) or []}
    needed = {
        "glucomannan",
        "konjac",
        "konjac root",
        "konjac mannan",
        "konjac flour",
        "amorphophallus konjac",
    }
    missing = needed - aliases
    assert not missing, f"fiber/konjac glucomannan missing aliases: {missing}"


def test_glucomannan_form_score_formula_consistent(iqm):
    """Schema rule: score = bio_score + (3 if natural else 0)."""
    fiber = iqm.get("fiber", {})
    form = fiber.get("forms", {}).get("konjac glucomannan", {})
    bio = form.get("bio_score")
    score = form.get("score")
    natural = bool(form.get("natural", False))
    if isinstance(bio, (int, float)) and isinstance(score, (int, float)):
        assert score == bio + (3 if natural else 0)


def test_no_duplicate_top_level_glucomannan(iqm):
    """Confirm the 'no double entry' invariant — there must NOT be a
    standalone top-level `glucomannan` IQM entry duplicating the form
    that already lives under `fiber`."""
    assert "glucomannan" not in iqm, (
        "Top-level 'glucomannan' would duplicate fiber/konjac glucomannan"
    )
