"""A truthful zero classification confidence must survive score assembly.

THE BUG
    `score_supplements.score_product` assembled the scored payload with:

        "percentile_category_confidence": (
            product.get("supplement_taxonomy", {}).get("classification_confidence")
            or product.get("percentile_category_confidence")
        ),

    `or` tests TRUTHINESS, so a legitimate confidence of **0.0** is falsy and
    falls through to the legacy field. Zero is a real, meaningful value here:
    the classifier emits `classification_confidence = 0.0` when it has no
    quantified evidence ("no quantified active ingredients") — a truthful "I
    don't know", not a missing value.

    The fallback is not benign. The legacy `percentile_category_confidence` is
    written by the enricher's own percentile inference, which has its OWN
    confidence — so a taxonomy that honestly said 0.0 gets REPLACED by, say,
    0.85. The scored artifact then reports a confident classification for a
    product the classifier could not classify. That is worse than a null: it is
    a plausible lie.

    The same `X or Y` shape hits `percentile_category_signals`, where an empty
    reason list ([] is falsy) falls back to the legacy signals.

THE RULE
    Fall back only when the taxonomy value is genuinely ABSENT (None). Never
    conflate "zero/empty" with "missing".

    (`_resolve_percentile_category` already gets this right via `as_float(...,
    None)`; only the payload assembly regressed.)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from score_supplements import SupplementScorer  # noqa: E402


@pytest.fixture(scope="module")
def scorer():
    return SupplementScorer()


_DEFAULT = object()


def _product(*, taxonomy_confidence, legacy_confidence,
             taxonomy_reasons=_DEFAULT, legacy_signals=None):
    """A product whose taxonomy and legacy percentile fields disagree.

    `taxonomy_reasons=None` means the key is ABSENT from the taxonomy (the
    genuine-fallback case), as distinct from `[]` which means "present and
    empty" — the whole point of the bug.
    """
    if taxonomy_reasons is _DEFAULT:
        taxonomy_reasons = ["no quantified active ingredients"]

    taxonomy = {
        "percentile_category": "general_supplement",
        "classification_confidence": taxonomy_confidence,
    }
    if taxonomy_reasons is not None:
        taxonomy["classification_reasons"] = taxonomy_reasons

    return {
        "dsld_id": 880001,
        "product_name": "Test Product",
        "status": "active",
        "supplement_taxonomy": taxonomy,
        "percentile_category": "general_supplement",
        "percentile_category_confidence": legacy_confidence,
        "percentile_category_signals": (
            legacy_signals if legacy_signals is not None else ["legacy:signal"]
        ),
        "ingredient_quality_data": {"ingredients_scorable": [], "ingredients": []},
    }


def test_zero_taxonomy_confidence_is_not_replaced_by_the_legacy_value(scorer):
    """The core defect: a truthful 0.0 was overwritten by the legacy inferer's
    own confidence, so the artifact claimed 0.85 for an unclassifiable product."""
    scored = scorer.score_product(
        _product(taxonomy_confidence=0.0, legacy_confidence=0.85)
    )

    assert scored["percentile_category_confidence"] == 0.0, (
        "a truthful zero-confidence classification was replaced by the legacy "
        "field's confidence — the artifact now reports a confidence the "
        "classifier never had"
    )


def test_zero_taxonomy_confidence_is_preserved_as_zero_not_none(scorer):
    """Zero must survive as zero — not be coalesced away to a null."""
    scored = scorer.score_product(
        _product(taxonomy_confidence=0.0, legacy_confidence=None)
    )

    confidence = scored["percentile_category_confidence"]
    assert confidence is not None, "a truthful 0.0 was coalesced to None"
    assert confidence == 0.0


def test_real_taxonomy_confidence_still_wins(scorer):
    """The near-miss: the fix must not stop a normal value from taking
    precedence."""
    scored = scorer.score_product(
        _product(taxonomy_confidence=0.9, legacy_confidence=0.3)
    )
    assert scored["percentile_category_confidence"] == 0.9


def test_absent_taxonomy_confidence_still_falls_back(scorer):
    """The fallback must survive for genuinely missing values — that is the
    behavior the `or` was there to provide."""
    scored = scorer.score_product(
        _product(taxonomy_confidence=None, legacy_confidence=0.7)
    )
    assert scored["percentile_category_confidence"] == 0.7


def test_empty_taxonomy_reasons_are_not_replaced_by_legacy_signals(scorer):
    """Same falsy-fallback shape on the signals field: [] is falsy, so an empty
    reason list silently adopted the legacy inferer's signals."""
    scored = scorer.score_product(
        _product(
            taxonomy_confidence=0.5,
            legacy_confidence=0.5,
            taxonomy_reasons=[],
            legacy_signals=["legacy:greens", "legacy:powder"],
        )
    )

    assert scored["percentile_category_signals"] == [], (
        "an empty taxonomy reason list was replaced by legacy signals — the "
        "artifact attributes reasoning to the taxonomy that it never produced"
    )


def test_absent_taxonomy_reasons_still_fall_back(scorer):
    scored = scorer.score_product(
        _product(
            taxonomy_confidence=0.5,
            legacy_confidence=0.5,
            taxonomy_reasons=None,
            legacy_signals=["legacy:signal"],
        )
    )
    assert scored["percentile_category_signals"] == ["legacy:signal"]


def test_no_truthiness_fallback_remains_in_the_payload_assembly():
    """Source guard: `X or Y` on a field whose zero/empty value is meaningful
    re-introduces this defect silently."""
    source = (SCRIPTS_DIR / "score_supplements.py").read_text()
    start = source.index('"percentile_category_confidence":')
    end = source.index('"output_schema_version"', start)
    block = source[start:end]

    assert "or product.get" not in block, (
        "the payload still uses a truthiness fallback for confidence/signals; "
        "0.0 and [] are meaningful values, not missing ones"
    )
