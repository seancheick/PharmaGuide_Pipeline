"""
Sprint E1.1.1 — regression tests for decision_highlights re-classification.

Exercises the 4-bucket contract (``positive``, ``caution``, ``danger``,
``trust``) and the build-time validator that blocks deny-list tokens
from leaking into ``positive``.

Covers the core symptoms from the 2026-04-21 Flutter device-testing
handoff: "Not lawful as a US dietary supplement" and similar danger-
valence strings rendered under a green thumbs-up. The categorization
guarantee is structural: danger-valence content MUST route into the
``danger`` bucket (rendered red by Flutter) and MUST NOT appear in
``positive`` (rendered green).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_final_db import (  # noqa: E402
    build_decision_highlights,
    _validate_decision_highlights,
)


def _base_enriched() -> dict:
    return {
        "dsld_id": "TEST-0001",
        "is_trusted_manufacturer": False,
        "has_full_disclosure": False,
        "named_cert_programs": [],
        "harmful_additives": [],
        "allergen_hits": [],
    }


def _base_scored(section_c: float = 0.0, score_80: float = 40.0, verdict: str = "SAFE") -> dict:
    return {
        "section_scores": {"C_evidence_research": {"score": section_c}},
        "score_80": score_80,
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# Shape contract — all 4 buckets always present.
# ---------------------------------------------------------------------------

def test_shape_always_has_four_buckets() -> None:
    dh = build_decision_highlights(_base_enriched(), _base_scored(), None)
    assert set(dh.keys()) == {"positive", "caution", "danger", "trust"}
    assert isinstance(dh["positive"], str)
    assert isinstance(dh["caution"], str)
    assert isinstance(dh["danger"], list)
    assert isinstance(dh["trust"], str)


def test_danger_is_empty_list_when_no_blocking_reason() -> None:
    dh = build_decision_highlights(_base_enriched(), _base_scored(), None)
    assert dh["danger"] == []


# ---------------------------------------------------------------------------
# Blocking-reason routing — banned / recalled / high_risk → danger bucket.
# ---------------------------------------------------------------------------

def test_banned_substance_routes_to_danger() -> None:
    dh = build_decision_highlights(
        _base_enriched(),
        _base_scored(verdict="BLOCKED"),
        "banned_substance",
    )
    assert any("banned" in s.lower() for s in dh["danger"]), dh
    # Must not also appear in positive
    assert "banned" not in dh["positive"].lower()


def test_recalled_ingredient_routes_to_danger() -> None:
    dh = build_decision_highlights(
        _base_enriched(),
        _base_scored(verdict="BLOCKED"),
        "recalled_ingredient",
    )
    assert any("recalled" in s.lower() for s in dh["danger"]), dh
    assert "recalled" not in dh["positive"].lower()


def test_high_risk_ingredient_routes_to_danger() -> None:
    dh = build_decision_highlights(
        _base_enriched(),
        _base_scored(verdict="UNSAFE"),
        "high_risk_ingredient",
    )
    assert any("high risk" in s.lower() for s in dh["danger"]), dh


# ---------------------------------------------------------------------------
# Caution bucket — non-blocking signals still flow into caution unchanged.
# ---------------------------------------------------------------------------

def test_caution_carries_additive_signal_when_not_blocked() -> None:
    enriched = _base_enriched()
    enriched["harmful_additives"] = [{"name": "Titanium Dioxide"}]
    dh = build_decision_highlights(enriched, _base_scored(), None)
    assert "additive" in dh["caution"].lower()
    assert dh["danger"] == []


def test_caution_carries_allergen_signal_when_not_blocked() -> None:
    enriched = _base_enriched()
    enriched["allergen_hits"] = [{"name": "Milk"}]
    dh = build_decision_highlights(enriched, _base_scored(), None)
    assert "allergen" in dh["caution"].lower()


def test_no_caution_signal_message_on_clean_products() -> None:
    dh = build_decision_highlights(_base_enriched(), _base_scored(), None)
    assert "no major caution" in dh["caution"].lower()


# ---------------------------------------------------------------------------
# Positive bucket — always benign, never carries danger tokens.
# ---------------------------------------------------------------------------

def test_positive_never_contains_deny_list_tokens() -> None:
    """Run through the branches that can assign positive and assert none
    carries a deny-list token. Covers: trusted-manufacturer, strong-
    evidence, score-60+, default fallback."""
    # Trusted + full disclosure branch
    e1 = _base_enriched()
    e1["is_trusted_manufacturer"] = True
    e1["has_full_disclosure"] = True
    dh1 = build_decision_highlights(e1, _base_scored(), None)

    # Strong evidence branch
    dh2 = build_decision_highlights(_base_enriched(), _base_scored(section_c=15.0), None)

    # Score >= 60 branch
    dh3 = build_decision_highlights(_base_enriched(), _base_scored(score_80=65.0), None)

    # Default branch
    dh4 = build_decision_highlights(_base_enriched(), _base_scored(), None)

    deny = ("not lawful", "banned", "talk to your doctor", "arsenic",
            "trace metals", "undisclosed", "high glycemic", "contraindicated")
    for dh in (dh1, dh2, dh3, dh4):
        low = dh["positive"].lower()
        for token in deny:
            assert token not in low, f"positive leaks {token!r}: {dh['positive']!r}"


# ---------------------------------------------------------------------------
# Validator — raises on violation; silent on clean input.
# ---------------------------------------------------------------------------

def test_validator_passes_on_clean_highlights() -> None:
    dh = {
        "positive": "Strong overall quality profile.",
        "caution": "No major caution signal surfaced.",
        "danger": [],
        "trust": "Trust signals limited.",
    }
    _validate_decision_highlights(dh, "CLEAN-0001")  # no exception expected


@pytest.mark.parametrize("bad_string", [
    "Not lawful as a US dietary supplement. Talk to your doctor.",
    "Concentrated added sugar. Some can carry trace arsenic.",
    "Undisclosed colorant. Transparency concerns.",
    "Diabetes. Contains high glycemic sweetener.",
    "Banned stimulant detected in formulation.",
])
def test_validator_raises_on_deny_list_in_positive(bad_string: str) -> None:
    dh = {
        "positive": bad_string,
        "caution": "",
        "danger": [],
        "trust": "",
    }
    with pytest.raises(ValueError, match="decision_highlights.positive"):
        _validate_decision_highlights(dh, "BAD-0001")


def test_validator_handles_list_shape_positive() -> None:
    """positive may be a list[str] post-future-migration; validator scans
    every element."""
    dh = {
        "positive": ["Safe baseline.", "Strong evidence."],
        "caution": "",
        "danger": [],
        "trust": "",
    }
    _validate_decision_highlights(dh, "OK-LIST")  # no exception

    dh_bad = {
        "positive": ["Safe baseline.", "Not lawful as a US dietary supplement."],
        "caution": "",
        "danger": [],
        "trust": "",
    }
    with pytest.raises(ValueError):
        _validate_decision_highlights(dh_bad, "BAD-LIST")
