#!/usr/bin/env python3
"""Defense-in-depth: the proprietary-blend DETECTOR must never manufacture a
blend from a bare marketing suffix token ("Complex"/"Matrix"/"Formula") in an
ingredient name.

The detector matches only the curated multi-word `blend_terms` in
proprietary_blends.json (e.g. "energy blend", "focus complex"), which are
genuine blend categories. A dead `BLEND_INDICATOR_PATTERNS` constant used to
encode bare name-token matching (`\\b(blend|complex|matrix|formula)\\b ...`);
it was never wired in, but it is exactly the mechanism that mislabels branded
single-actives (EpiCor, Curcumin C3 Complex, Boron Complex) as opaque blends.
These tests lock name-token detection OFF so it can't be reintroduced, and
confirm the curated terms still fire.

Identity-based suppression of single-active false positives is the enricher's
job (`_collect_proprietary_data`, which has the IQM resolver); the detector
intentionally stays identity-blind and term-driven.
"""

import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
logging.disable(logging.CRITICAL)

from proprietary_blend_detector import ProprietaryBlendDetector  # noqa: E402


@pytest.fixture(scope="module")
def detector():
    return ProprietaryBlendDetector()


def _product(name, qty=250, unit="mg"):
    return {
        "id": "1",
        "activeIngredients": [{"name": name, "quantity": qty, "unit": unit}],
        "inactiveIngredients": [],
        "statements": [],
    }


# Branded single-actives + bare-token names must NOT be detected as blends.
@pytest.mark.parametrize(
    "name",
    [
        "EpiCor dried Yeast Fermentate Complex",
        "Curcumin C3 Complex",
        "Boron Complex",
        "Recovery Matrix",          # bare token, not a curated blend_term
        "Mega Complex",             # bare token, not a curated blend_term
        "Turmeric Formula",         # bare token, not a curated blend_term
    ],
)
def test_detector_ignores_bare_name_tokens(detector, name):
    result = detector.analyze_product(_product(name))
    assert result.blends_detected == [], (
        f"Detector must not manufacture a blend from a bare name token; {name!r} "
        f"matched {[b.blend_name for b in result.blends_detected]!r}"
    )


def test_dead_name_token_pattern_constant_is_removed():
    """The `BLEND_INDICATOR_PATTERNS` landmine (bare complex/matrix/formula/blend
    name-token regexes) must not exist — it is the exact future vector for
    re-misclassifying branded single-actives."""
    assert not hasattr(ProprietaryBlendDetector, "BLEND_INDICATOR_PATTERNS"), (
        "BLEND_INDICATOR_PATTERNS encodes bare name-token blend detection and must "
        "stay removed; identity-aware suppression belongs in the enricher."
    )


# Curated multi-word blend_terms are genuine blends and MUST still be detected.
@pytest.mark.parametrize("name", ["Energy Blend", "Thermogenic Blend", "Focus Complex"])
def test_detector_still_detects_curated_blend_terms(detector, name):
    result = detector.analyze_product(_product(name))
    assert result.blends_detected, (
        f"Curated blend_term {name!r} must still be detected as a proprietary blend."
    )
    assert all(b.disclosure_level == "none" for b in result.blends_detected)
