"""
T1: Banned-watchlist class recognition.

Policy watchlist entries in banned_recalled_ingredients.json use
entity_type="class" (e.g., SPIKE_ANABOLIC_STEROIDS, SPIKE_TIANEPTINE_ANALOGUES).
Each class entry lists specific molecule aliases like
"3,3-Azo-17a-Methyl-5a-Androstan-17b-Ol".

Prior to this fix, both the non-scorable index and _check_banned_substances
filtered out entity_type="class" entirely, so products with these exact
molecule names (e.g., Legion pre-workouts) slipped through both the
enrichment recognition layer and the safety gate.

Fix: allow class entities for EXACT alias matching only (dict lookup for
non-scorable index; strict alias/exact match in _check_banned_substances).
Fuzzy token-bounded matching remains disabled for class entities to avoid
over-blocking generic chemistry terms.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402


LEGION_STEROID_LABELS = [
    "3,3-Azo-17a-Methyl-5a-Androstan-17b-Ol",
    "2, 17a-Dimethyl-17b-Hydroxy-5a-Androst-2-Ene",
    "17a-Ethyl-Estr-5(6)-Ene-3B-Diol",
]

EXPECTED_BANNED_ID = "SPIKE_ANABOLIC_STEROIDS"


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


@pytest.mark.parametrize("label", LEGION_STEROID_LABELS)
def test_legion_steroid_hits_banned_substances_check(enricher, label):
    """Safety-critical: each Legion steroid molecule must be flagged as banned."""
    result = enricher._check_banned_substances(
        [{"name": label, "standardName": label}]
    )
    assert result["found"] is True, (
        f"Expected {label!r} to be flagged as banned; got {result}"
    )
    banned_ids = {s.get("banned_id") for s in result["substances"]}
    assert EXPECTED_BANNED_ID in banned_ids, (
        f"Expected {EXPECTED_BANNED_ID} in banned_ids for {label!r}, got {banned_ids}"
    )
    # All class matches must be exact or alias, never token_bounded
    for sub in result["substances"]:
        if sub.get("banned_id") == EXPECTED_BANNED_ID:
            assert sub["match_type"] in ("exact", "alias"), (
                f"Class match must be exact/alias only, got {sub['match_type']} "
                f"for {label!r}"
            )


@pytest.mark.parametrize("label", LEGION_STEROID_LABELS)
def test_legion_steroid_appears_in_nonscorable_index(enricher, label):
    """Enrichment-recognition: aliases must be reachable via _is_recognized_non_scorable."""
    recognition = enricher._is_recognized_non_scorable(label, label)
    assert recognition is not None, (
        f"Expected {label!r} to be recognized as non-scorable; got None"
    )
    assert recognition.get("recognition_source") == "banned_recalled_ingredients"
    assert recognition.get("recognition_reason") == "banned"


OTHER_BANNED_CLASS_ALIASES = [
    # (label, expected banned_id) — one representative alias per class,
    # all verified to exist in the aliases list of each class entry
    ("cardarine derivatives", "RC_CARDARINE_ANALOGS"),
    ("tianeptine analogues", "SPIKE_TIANEPTINE_ANALOGUES"),
    ("octodrine derivatives", "STIM_METHYLHEXANAMINE_ANALOGS"),
]


@pytest.mark.parametrize("label,expected_id", OTHER_BANNED_CLASS_ALIASES)
def test_other_banned_class_aliases_are_flagged(enricher, label, expected_id):
    """
    All four banned-status class entries must match via exact/alias.
    BANNED_ADD_SYNTHETIC_FOOD_ACIDS (watchlist) stays disabled and is not tested.
    """
    result = enricher._check_banned_substances(
        [{"name": label, "standardName": label}]
    )
    banned_ids = {s.get("banned_id") for s in result.get("substances", [])}
    assert expected_id in banned_ids, (
        f"Expected {expected_id} in banned_ids for {label!r}, got {banned_ids}"
    )


def test_class_entity_does_not_over_match_generic_chemistry(enricher):
    """
    Regression guardrail: class entities must not over-match via token-bounded
    fuzzy matching. A generic chemistry term that merely shares tokens with
    steroid aliases (e.g., "Methyl Alcohol") must NOT be flagged under
    SPIKE_ANABOLIC_STEROIDS.
    """
    result = enricher._check_banned_substances(
        [{"name": "Methyl Alcohol", "standardName": "Methyl Alcohol"}]
    )
    banned_ids = {s.get("banned_id") for s in result.get("substances", [])}
    assert EXPECTED_BANNED_ID not in banned_ids, (
        f"Generic 'Methyl Alcohol' must not match SPIKE_ANABOLIC_STEROIDS "
        f"via token-bounded fuzzy match; got {banned_ids}"
    )
