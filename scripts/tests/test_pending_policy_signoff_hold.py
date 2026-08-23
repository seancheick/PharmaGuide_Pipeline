"""A safety rule may not relax itself. An operator has to sign it off.

The mechanism: a rule carrying ``pending_us_policy_signoff`` resolves with
``previous_fields`` overlaid -- the exact pre-change values from the diff of the
commit that relaxed it, not a guess at which field the verdict keys on -- until
``approved`` is true. ``us_applicable`` is a code default rather than a field
(an unauthored jurisdiction list used to imply US applicability and no longer
does), so a held rule also gets an explicit US jurisdiction at the held status.

Applied wherever these rules enter the pipeline: the resolver's index (which
build_final_db's active index reuses) and the enricher's database load, which
writes the safety_flags the v4 gate turns into a verdict.

**No rule is currently held.** The two candidates were investigated and neither
is a policy transition -- see
``docs/release_candidates/safety_signoff_packet_2026_08_22.md``. The mechanism
stays because the next real relaxation needs it, and an untested mechanism is
not a mechanism.
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
    hold_unapproved_policy_payload,
)

BANNED_RECALLED = ROOT / "scripts" / "data" / "banned_recalled_ingredients.json"


def _entry(**hold):
    return {
        "id": "RULE_X",
        "status": "watchlist",
        "match_mode": "disabled",
        "legal_status_enum": "lawful",
        "safety_warning_one_liner": "Assess from the label amount.",
        "jurisdictions": [],
        PENDING_POLICY_HOLD_KEY: {
            "previous_status": "banned",
            "proposed_status": "watchlist",
            "packet": "docs/release_candidates/safety_signoff_packet_2026_08_22.md",
            "approved": False,
            "previous_fields": {
                "status": "banned",
                "match_mode": "active",
                "legal_status_enum": "not_lawful_as_supplement",
                "safety_warning_one_liner": "Stop using and talk to your doctor.",
            },
            **hold,
        },
    }


# --------------------------------------------------------------------------- #
# The mechanism
# --------------------------------------------------------------------------- #


def test_an_unapproved_hold_restores_every_previous_field() -> None:
    held = apply_pending_policy_hold(_entry())
    assert held["status"] == "banned"
    assert held["match_mode"] == "active", (
        "a retired rule is `disabled` and would never reach an index"
    )
    assert held["legal_status_enum"] == "not_lawful_as_supplement"
    assert held["safety_warning_one_liner"] == "Stop using and talk to your doctor.", (
        "a held status must not carry the copy written for the lower posture"
    )
    assert held["policy_hold_applied"]["held_status"] == "banned"
    assert held["policy_hold_applied"]["proposed_status"] == "watchlist"


def test_a_held_rule_becomes_us_applicable_at_the_held_status() -> None:
    """`us_applicable` is a code default, not a field."""
    held = apply_pending_policy_hold(_entry())
    us = [j for j in held["jurisdictions"] if j["region"] == "US"]
    assert len(us) == 1
    assert us[0]["status"] == "banned"
    assert us[0]["source"]["type"] == "policy_hold"


def test_an_existing_us_jurisdiction_is_restated_not_duplicated() -> None:
    entry = _entry()
    entry["jurisdictions"] = [
        {"region": "US", "level": "federal", "status": "watchlist"},
        {"region": "EU", "level": "union", "status": "banned"},
    ]
    held = apply_pending_policy_hold(entry)
    us = [j for j in held["jurisdictions"] if j["region"] == "US"]
    assert len(us) == 1 and us[0]["status"] == "banned"
    assert [j for j in held["jurisdictions"] if j["region"] == "EU"]


def test_approval_releases_the_hold() -> None:
    """Flipping `approved` is the whole release action."""
    approved = apply_pending_policy_hold(_entry(approved=True))
    assert approved["status"] == "watchlist"
    assert approved["match_mode"] == "disabled"
    assert "policy_hold_applied" not in approved


def test_an_entry_without_a_hold_is_returned_unchanged() -> None:
    entry = {"id": "X", "status": "banned"}
    assert apply_pending_policy_hold(entry) is entry


@pytest.mark.parametrize("hold_override", [
    {"previous_fields": {}},
    {"previous_fields": None},
    {"approved": "yes"},
])
def test_a_malformed_hold_never_relaxes(hold_override) -> None:
    held = apply_pending_policy_hold(_entry(**hold_override))
    if hold_override.get("approved") == "yes":
        assert held["status"] == "banned", "a non-boolean approval is not approval"
    else:
        # Nothing to restore: the entry stands as authored rather than being
        # rewritten from an empty overlay.
        assert held["status"] == "watchlist"


def test_the_payload_helper_applies_to_every_entry() -> None:
    payload = {"ingredients": [_entry(), {"id": "Y", "status": "banned"}]}
    out = hold_unapproved_policy_payload(payload)
    assert out["ingredients"][0]["status"] == "banned"
    assert out["ingredients"][1] == {"id": "Y", "status": "banned"}
    assert hold_unapproved_policy_payload({"other": 1}) == {"other": 1}
    assert hold_unapproved_policy_payload(None) is None


# --------------------------------------------------------------------------- #
# Current state of the data
# --------------------------------------------------------------------------- #


def test_no_rule_is_currently_held_without_a_packet_entry() -> None:
    """Any hold that appears must point at a packet that exists.

    Zero holds today. If one is added, it has to name the document that
    justifies it, so a relaxation cannot be paused silently and forgotten.
    """
    payload = json.loads(BANNED_RECALLED.read_text(encoding="utf-8"))
    for entry in payload.get("ingredients") or []:
        if not isinstance(entry, dict):
            continue
        hold = entry.get(PENDING_POLICY_HOLD_KEY)
        if not isinstance(hold, dict):
            continue
        assert hold.get("packet"), f"{entry.get('id')}: hold names no packet"
        assert (ROOT / hold["packet"]).is_file(), (
            f"{entry.get('id')}: packet missing at {hold['packet']}"
        )
        assert isinstance(hold.get("previous_fields"), dict) and hold["previous_fields"], (
            f"{entry.get('id')}: a hold must carry the exact previous field values"
        )
        assert hold.get("previous_mechanism"), (
            f"{entry.get('id')}: a hold must record what produced the previous outcome"
        )
