"""display_tone: penalty-aware dot color for the 'Other ingredients' surface.

The shipped dot must reflect the harmful-additive penalty B1 ACTUALLY applied
(post-exemption), not the additive's file severity. The two diverge: a vegetarian
capsule shell resolves to microcrystalline cellulose for DISPLAY (amber under the
old severity_status path) but B1 never penalizes it (the label doesn't match the
MCC aliases), so it costs 0 points and must read green. Maltodextrin matches
directly, costs 0.5, and must read light orange.

Codex caveat baked in: green = "0 penalty AND no safety/regulatory concern". Any
banned_recalled row (banned / recalled / high_risk / watchlist) floors at red even
when B1 adds 0 points, because B0 — not B1 — owns its score penalty.
"""
import inspect
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from build_final_db import (
    _inactive_display_tone,
    _inactive_penalty_tones,
    _inactive_penalty_tones_by_label,
)
from audit_contract_sync import INACTIVE_CONTRACT, _audit_ingredient_contract


@pytest.mark.parametrize(
    "matched_source,matched_rule_id,penalty_tones,expected",
    [
        # Capsule shell: display resolves to MCC, but B1 never penalized it → green.
        ("harmful_additives", "ADD_MICROCRYSTALLINE_CELLULOSE", {}, "green"),
        # Maltodextrin: B1 applied a low (0.5) penalty → light orange.
        ("harmful_additives", "ADD_MALTODEXTRIN", {"ADD_MALTODEXTRIN": "light_orange"}, "light_orange"),
        # Moderate additive actually penalized (1.0) → dark orange.
        ("harmful_additives", "ADD_CARRAGEENAN", {"ADD_CARRAGEENAN": "dark_orange"}, "dark_orange"),
        # High / critical additive (2.0 / 3.0) → red.
        ("harmful_additives", "ADD_TITANIUM_DIOXIDE", {"ADD_TITANIUM_DIOXIDE": "red"}, "red"),
        ("harmful_additives", "ADD_BVO", {"ADD_BVO": "red"}, "red"),
        # Regulatory floor: banned_recalled rows are red even with 0 B1 points.
        ("banned_recalled", "WATCH_BOVINE_BRAIN_PHOSPHATIDYLSERINE", {}, "red"),
        ("banned_recalled", "BANNED_BLUE1", {}, "red"),
        # A harmful row whose B1 penalty was exempted (not in the map) → green.
        ("harmful_additives", "ADD_SILICON_DIOXIDE", {}, "green"),
        # Benign / unmatched → green.
        ("other_ingredients", "OI_CELLULOSE", {}, "green"),
        ("active_nutrient_form", None, {}, "green"),
        (None, None, {}, "green"),
    ],
)
def test_inactive_display_tone(matched_source, matched_rule_id, penalty_tones, expected):
    assert _inactive_display_tone(matched_source, matched_rule_id, penalty_tones) == expected


def test_penalty_tones_are_derived_from_inactive_penalty_ledger() -> None:
    scored = {
        "_v4_inactive_penalty_details": [
            {
                "matched_rule_id": "LOW",
                "penalty_tier": "low",
                "penalty_applied": 0.5,
            },
            {
                "matched_rule_id": "MODERATE",
                "penalty_tier": "moderate",
                "penalty_applied": 2.0,
            },
            {
                "matched_rule_id": "HIGH",
                "penalty_tier": "high",
                "penalty_applied": 3.0,
            },
            {
                "matched_rule_id": "EXEMPT",
                "penalty_tier": "critical",
                "penalty_applied": 0.0,
            },
        ]
    }

    assert _inactive_penalty_tones(scored) == {
        "LOW": "light_orange",
        "MODERATE": "dark_orange",
        "HIGH": "red",
        "EXEMPT": "green",
    }


def test_label_join_colours_a_charge_the_rule_id_join_cannot_see() -> None:
    """A charged row must colour even when the two matchers disagree on the id.

    The enricher's harmful matcher and the display resolver are two matchers over
    one label string. Measured on the real corpus 2026-08-07: 95 charged rows
    across 89 products land on different ids, so the rule-id join silently misses
    and the dot falls through to green. The largest classes are the FD&C colour
    lakes (charged ADD_YELLOW6/BLUE1/BLUE2/RED40, resolved to the benign
    NHA_ARTIFICIAL_COLORS) and dl-alpha-tocopherol (charged ADD_SYNTHETIC_VITAMINS,
    resolved to OI_TOCOPHEROL_PRESERVATIVE). Artificial colours reading green is
    exactly the surface a user checks, so this must not regress.
    """
    scored = {
        "_v4_inactive_penalty_details": [
            {
                "matched_rule_id": "ADD_YELLOW6",
                "penalty_tier": "moderate",
                "penalty_applied": 2.0,
                "matched_labels": ["fd&c yellow 6 lake"],
            }
        ]
    }
    label_tones = _inactive_penalty_tones_by_label(scored)
    assert label_tones == {"fd&c yellow 6 lake": "dark_orange"}

    # The id join cannot hit: the resolver assigned a different, benign id.
    assert (
        _inactive_display_tone(
            "other_ingredients",
            "NHA_ARTIFICIAL_COLORS",
            _inactive_penalty_tones(scored),
            label_tones=label_tones,
            row_labels=("FD&C Yellow 6 Lake", "FD&C Yellow 6 Lake"),
        )
        == "dark_orange"
    )

    # An uncharged row on the same product must stay green — the label join must
    # not leak a tone onto rows the scorer never charged.
    assert (
        _inactive_display_tone(
            "other_ingredients",
            "PII_HPMC",
            _inactive_penalty_tones(scored),
            label_tones=label_tones,
            row_labels=("Hypromellose", "Hypromellose"),
        )
        == "green"
    )


def test_ledger_rows_carry_the_labels_the_scorer_charged() -> None:
    """The scorer must emit matched_labels or the label join has nothing to use."""
    import sys as _sys
    from pathlib import Path as _Path

    _sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
    from scoring_v4.modules.generic_formulation import (
        _b1_harmful_additive_penalty_detail,
    )

    detail = _b1_harmful_additive_penalty_detail(
        {
            "harmful_additives": [
                {
                    "additive_id": "ADD_YELLOW6",
                    "severity": "moderate",
                    "source_section": "inactive",
                    "raw_source_text": "FD&C Yellow 6 Lake",
                }
            ]
        }
    )
    rows = detail["inactive_penalty_details"]
    assert len(rows) == 1, rows
    assert rows[0]["matched_labels"] == ["fd&c yellow 6 lake"], rows[0]


@pytest.mark.parametrize(
    "harmful_severity,expected",
    [
        ("moderate", "dark_orange"),
        ("high", "red"),
    ],
)
def test_resolver_only_safety_concern_cannot_render_green(
    harmful_severity, expected
):
    """A resolver safety hit must remain visible even when B1 missed it."""
    if "harmful_severity" not in inspect.signature(_inactive_display_tone).parameters:
        actual = "missing_safety_fallback"
    else:
        actual = _inactive_display_tone(
            "harmful_additives",
            "ADD_RESOLVER_ONLY",
            {},
            harmful_severity=harmful_severity,
        )
    assert actual == expected


def test_contract_requires_display_tone_on_every_fresh_inactive_row() -> None:
    spec = INACTIVE_CONTRACT["display_tone"]
    assert spec["required"] is True
    assert spec["strict_complete"] is True
    assert spec["values"] == ["green", "light_orange", "dark_orange", "red"]

    complete = _audit_ingredient_contract(
        [{"inactive_ingredients": [{"display_tone": "green"}]}],
        "inactive_ingredients",
        {"display_tone": spec},
    )
    incomplete = _audit_ingredient_contract(
        [
            {
                "inactive_ingredients": [
                    {"display_tone": "green"},
                    {"display_tone": None},
                ]
            }
        ],
        "inactive_ingredients",
        {"display_tone": spec},
    )

    assert complete["fields"]["display_tone"]["status"] == "GREEN"
    assert incomplete["fields"]["display_tone"]["status"] == "RED"


def test_contract_rejects_unknown_display_tone_values() -> None:
    spec = INACTIVE_CONTRACT["display_tone"]
    audited = _audit_ingredient_contract(
        [{"inactive_ingredients": [{"display_tone": "blue"}]}],
        "inactive_ingredients",
        {"display_tone": spec},
    )

    field = audited["fields"]["display_tone"]
    assert field["status"] == "RED"
    assert field["unexpected_enum_values"] == ["blue"]
