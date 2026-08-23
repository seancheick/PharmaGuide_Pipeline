"""A safety rule may not relax itself. An operator has to sign it off.

Two US policy re-reads on this branch lower a consumer-facing verdict:

  RISK_RED_YEAST_RICE      banned -> high_risk   27 live products
  ADD_SODIUM_TETRABORATE   banned -> watchlist   17 live products (rule retired)

Both are well-sourced. Neither is approved. The pipeline must not enact a
clinical-policy decision by shipping it, so each rule carries a
``pending_us_policy_signoff`` block and resolves at ``previous_status`` until
``approved`` is true. Flipping that one field is the entire release action.

The hold is applied at the single point where banned_recalled entries enter the
resolver, before the ``match_mode`` filter -- a retired rule is ``disabled`` and
would otherwise never reach an index at all.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for candidate in (ROOT, ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from identity.safety import (  # noqa: E402
    PENDING_POLICY_HOLD_KEY,
    apply_pending_policy_hold,
)
from inactive_ingredient_resolver import InactiveIngredientResolver  # noqa: E402

BANNED_RECALLED = ROOT / "scripts" / "data" / "banned_recalled_ingredients.json"

HELD_RULES = {
    "RISK_RED_YEAST_RICE": {
        "previous_status": "banned",
        "proposed_status": "high_risk",
        "labels": ["Red Yeast Rice", "Organic Red Yeast Rice",
                   "Red Yeast Rice powder", "Monascus purpureus"],
    },
    "ADD_SODIUM_TETRABORATE": {
        "previous_status": "banned",
        "proposed_status": "watchlist",
        "labels": ["Sodium Tetraborate", "Sodium Tetraborate Decahydrate",
                   "borax"],
    },
}


@pytest.fixture(scope="module")
def resolver():
    return InactiveIngredientResolver()


def _entries():
    payload = json.loads(BANNED_RECALLED.read_text(encoding="utf-8"))
    return {
        str(e.get("id")): e
        for e in payload.get("ingredients") or []
        if isinstance(e, dict)
    }


# --------------------------------------------------------------------------- #
# The declared holds
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("rule_id", sorted(HELD_RULES))
def test_hold_is_declared_and_unapproved(rule_id) -> None:
    entry = _entries()[rule_id]
    hold = entry[PENDING_POLICY_HOLD_KEY]
    want = HELD_RULES[rule_id]
    assert hold["previous_status"] == want["previous_status"]
    assert hold["proposed_status"] == want["proposed_status"]
    assert str(entry.get("status") or "").lower() == want["proposed_status"], (
        "the entry keeps its proposed status on disk; the hold is applied at "
        "load time so the sign-off is one field flip"
    )
    assert hold["approved"] is False
    assert hold["approved_by"] is None
    assert hold["packet"], "a hold must point at the sign-off packet"
    assert hold["previous_mechanism"], (
        "a hold must record what actually produced the previous outcome, so a "
        "reviewer is not left to infer it from the verdict"
    )
    assert hold["previous_safety_warning_one_liner"], (
        "a held status must carry the consumer copy that matched it"
    )
    assert (ROOT / hold["packet"]).is_file(), (
        f"sign-off packet missing: {hold['packet']}"
    )


@pytest.mark.parametrize(
    "label",
    [lbl for rule in HELD_RULES.values() for lbl in rule["labels"]],
)
def test_held_rules_resolve_at_the_conservative_status(resolver, label) -> None:
    r = resolver.resolve(raw_name=label)
    assert r.matched_rule_id in HELD_RULES, (
        f"{label!r} resolved to {r.matched_rule_id!r}"
    )
    assert r.regulatory_status == "banned", (
        f"{label!r} resolved at {r.regulatory_status!r}; an unapproved policy "
        "relaxation must not reach a consumer-facing verdict"
    )
    assert r.is_banned is True
    assert r.is_safety_concern is True
    entry = _entries()[r.matched_rule_id]
    assert r.safety_warning_one_liner == (
        entry[PENDING_POLICY_HOLD_KEY]["previous_safety_warning_one_liner"]
    ), (
        f"{label!r} shows relaxed copy on a held status; a BLOCKED product must "
        "not carry the wording written for the lower posture"
    )


# --------------------------------------------------------------------------- #
# The mechanism
# --------------------------------------------------------------------------- #


def test_approval_releases_the_hold() -> None:
    """Flipping `approved` is the whole release action."""
    entry = dict(_entries()["RISK_RED_YEAST_RICE"])
    assert apply_pending_policy_hold(entry)["status"] == "banned"

    approved = dict(entry)
    approved[PENDING_POLICY_HOLD_KEY] = {
        **entry[PENDING_POLICY_HOLD_KEY],
        "approved": True,
        "approved_by": "operator",
    }
    assert apply_pending_policy_hold(approved)["status"] == "high_risk"


def test_a_retired_rule_is_put_back_in_the_matcher() -> None:
    """`match_mode: disabled` would keep a held rule inert."""
    entry = dict(_entries()["ADD_SODIUM_TETRABORATE"])
    assert entry["match_mode"] == "disabled"
    held = apply_pending_policy_hold(entry)
    assert held["match_mode"] == "exact"
    assert held["policy_hold_applied"]["held_match_mode"] == "exact"


def test_an_entry_without_a_hold_is_returned_unchanged() -> None:
    entry = {"id": "X", "status": "banned"}
    assert apply_pending_policy_hold(entry) is entry


@pytest.mark.parametrize("hold", [
    {},                                    # no previous_status
    {"previous_status": ""},               # blank
    {"previous_status": "banned", "approved": "yes"},   # not a real bool
])
def test_a_malformed_hold_fails_closed(hold) -> None:
    entry = {"id": "X", "status": "watchlist", PENDING_POLICY_HOLD_KEY: hold}
    result = apply_pending_policy_hold(entry)
    assert result["status"] in {"banned", "watchlist"}
    if hold.get("previous_status"):
        assert result["status"] == "banned", "a non-boolean approval is not approval"


def test_explicit_statin_evidence_is_unaffected_by_the_hold(resolver) -> None:
    """The banned RYR rule was already banned; the hold changes nothing there."""
    r = resolver.resolve(raw_name="Red Yeast Rice Extract (Monacolin K)")
    assert r.matched_rule_id == "BANNED_RED_YEAST_RICE"
    assert r.is_banned is True


def test_unrelated_rules_are_untouched(resolver) -> None:
    for label, expect_banned in (("Cannabidiol", True), ("Yohimbe", False),
                                 ("Vitamin C", False)):
        r = resolver.resolve(raw_name=label)
        assert bool(r.is_banned) is expect_banned, (label, r.matched_rule_id)
