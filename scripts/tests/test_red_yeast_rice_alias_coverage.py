"""Every real Red Yeast Rice label string must reach the high-risk rule.

The alias set is an exact-identity list, not a fuzzy matcher, so a qualifier the
curator did not anticipate silently drops the safety signal. Measured on the
enriched corpus, three variants declared by real products resolved to no rule at
all while the bare and `powder` forms resolved fine:

    Organic Red Yeast Rice          4 rows
    organic Red Yeast Rice powder   4 rows
    Monascus purpureus Extract      3 rows

Those products were still caught upstream by canonical identity, so nothing
shipped unflagged — but the resolver is the shared matcher, and a gap in it is a
gap for every consumer that does not have the upstream signal.

The false-positive block matters as much: `red yeast rice` must not be reachable
from rice, yeast, or koji terms that are not it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for candidate in (ROOT, ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from inactive_ingredient_resolver import InactiveIngredientResolver  # noqa: E402


RISK_RULE = "RISK_RED_YEAST_RICE"
BANNED_RULE = "BANNED_RED_YEAST_RICE"


@pytest.fixture(scope="module")
def resolver():
    return InactiveIngredientResolver()


# --------------------------------------------------------------------------- #
# Label strings observed on real products
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "label",
    [
        # already covered — regression guard
        "Red Yeast Rice",
        "Red Yeast Rice powder",
        "Red Yeast Rice Powder",
        "Red Yeast Rice extract",
        "Monascus purpureus",
        # observed in the corpus and previously unmatched
        "Organic Red Yeast Rice",
        "organic Red Yeast Rice",
        "organic Red Yeast Rice powder",
        "Monascus purpureus Extract",
    ],
)
def test_observed_red_yeast_rice_labels_reach_the_high_risk_rule(resolver, label) -> None:
    r = resolver.resolve(raw_name=label)
    assert r.matched_rule_id == RISK_RULE, (
        f"{label!r} resolved to {r.matched_rule_id!r}; every declared red yeast "
        "rice must reach the high-risk review rule"
    )
    assert r.is_safety_concern is True
    # Status is deliberately NOT asserted here. The banned -> high_risk move is
    # an unapproved US policy transition held at its previous status by
    # pending_us_policy_signoff; test_pending_policy_signoff_hold.py owns that.
    # This file owns one question only: does every real label string match?


@pytest.mark.parametrize(
    "label",
    [
        "Red Yeast Rice Extract (Monacolin K)",
        "Monacolin K",
        "Lovastatin",
        "Organic Red Yeast Rice standardized to Monacolin K",
    ],
)
def test_explicit_statin_evidence_still_blocks(resolver, label) -> None:
    r = resolver.resolve(raw_name=label)
    assert r.matched_rule_id == BANNED_RULE
    assert r.is_banned is True


# --------------------------------------------------------------------------- #
# False positives
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "label",
    [
        "Rice Bran",
        "Organic Brown Rice",
        "Organic Rice Protein",
        "Rice Flour",
        "Brown Rice Flour",
        "Rice Bran Extract",
        "Nutritional Yeast",
        "Saccharomyces cerevisiae",
        "Yeast Extract",
        "Torula Yeast",
        "Red Clover",
        "Red Beet Root",
        "Organic Red Raspberry",
        "Koji",
        "Organic Rice Concentrate",
        "Red Palm Oil",
    ],
)
def test_non_red_yeast_rice_terms_do_not_match(resolver, label) -> None:
    r = resolver.resolve(raw_name=label)
    assert r.matched_rule_id not in {RISK_RULE, BANNED_RULE}, (
        f"{label!r} wrongly matched {r.matched_rule_id!r}"
    )
