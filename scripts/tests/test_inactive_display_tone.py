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

from build_final_db import _inactive_display_tone


@pytest.mark.parametrize(
    "matched_source,matched_rule_id,b1_applied_tier,expected",
    [
        # Capsule shell: display resolves to MCC, but B1 never penalized it → green.
        ("harmful_additives", "ADD_MICROCRYSTALLINE_CELLULOSE", {}, "green"),
        # Maltodextrin: B1 applied a low (0.5) penalty → light orange.
        ("harmful_additives", "ADD_MALTODEXTRIN", {"ADD_MALTODEXTRIN": "low"}, "light_orange"),
        # Moderate additive actually penalized (1.0) → dark orange.
        ("harmful_additives", "ADD_CARRAGEENAN", {"ADD_CARRAGEENAN": "moderate"}, "dark_orange"),
        # High / critical additive (2.0 / 3.0) → red.
        ("harmful_additives", "ADD_TITANIUM_DIOXIDE", {"ADD_TITANIUM_DIOXIDE": "high"}, "red"),
        ("harmful_additives", "ADD_BVO", {"ADD_BVO": "critical"}, "red"),
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
def test_inactive_display_tone(matched_source, matched_rule_id, b1_applied_tier, expected):
    assert _inactive_display_tone(matched_source, matched_rule_id, b1_applied_tier) == expected


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
