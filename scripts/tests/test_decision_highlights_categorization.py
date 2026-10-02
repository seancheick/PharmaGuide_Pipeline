"""
Sprint E1.1.1 — regression tests for decision_highlights re-classification.

Exercises the 3-bucket contract (``positive``, ``caution``, ``trust``)
and the build-time validator that blocks deny-list tokens
from leaking into ``positive``.

Covers the core symptoms from the 2026-04-21 Flutter device-testing
handoff: "Not lawful as a US dietary supplement" and similar danger-
valence strings rendered under a green thumbs-up. The categorization
guarantee is structural: danger-valence content MUST NOT appear in
``positive`` (rendered green).
"""

from __future__ import annotations

import re
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


def _base_scored(evidence: float = 0.0, score_100: float = 50.0, verdict: str = "SAFE") -> dict:
    return {
        "quality_pillars_v4": {"evidence": {"score": evidence, "max": 20}},
        "score_100_equivalent": score_100,
        "verdict": verdict,
        "product_safety_status": "no_known_catalog_concern",
        "quality_assessment_status": "complete",
    }


# ---------------------------------------------------------------------------
# Shape contract — three buckets. The danger bucket was removed 2026-10-02:
# bans matched ``banned_substance``, a code the safety gate never emits, so
# it shipped empty on all 15,133 products (73 BLOCKED), and no app reads it. Blocking reasons reach users
# through the verdict and warnings, never through these hero strings.
# ---------------------------------------------------------------------------

def test_shape_has_three_buckets() -> None:
    dh = build_decision_highlights(_base_enriched(), _base_scored())
    assert set(dh.keys()) == {"positive", "caution", "trust"}
    assert all(isinstance(dh[key], str) for key in dh)


def test_blocked_product_highlights_carry_caution_not_praise() -> None:
    scored = _base_scored(verdict="BLOCKED")
    scored["product_safety_status"] = "blocked"
    dh = build_decision_highlights(_base_enriched(), scored)
    assert dh["caution"] == "Catalog safety concerns require attention."
    assert not re.search(r"banned|recalled", dh["positive"], re.I)


# ---------------------------------------------------------------------------
# Caution bucket — non-blocking signals still flow into caution unchanged.
# ---------------------------------------------------------------------------

def test_caution_carries_additive_signal_when_not_blocked() -> None:
    enriched = _base_enriched()
    enriched["harmful_additives"] = [{"name": "Titanium Dioxide"}]
    dh = build_decision_highlights(enriched, _base_scored())
    assert "additive" in dh["caution"].lower()


def test_caution_does_not_carry_allergen_signal_when_not_personalized() -> None:
    enriched = _base_enriched()
    enriched["allergen_hits"] = [{"name": "Milk"}]
    dh = build_decision_highlights(enriched, _base_scored())
    assert "allergen" not in dh["caution"].lower()
    assert "no major caution" in dh["caution"].lower()


def test_no_caution_signal_message_on_clean_products() -> None:
    dh = build_decision_highlights(_base_enriched(), _base_scored())
    assert "no major caution" in dh["caution"].lower()


# ---------------------------------------------------------------------------
# Positive bucket — always benign, never carries danger tokens.
# ---------------------------------------------------------------------------

def test_positive_never_contains_deny_list_tokens() -> None:
    """Run through the branches that can assign positive and assert none
    carries a deny-list token. Covers: trusted-manufacturer, strong-
    evidence, score-75+, default fallback."""
    # Trusted + full disclosure branch
    e1 = _base_enriched()
    e1["is_trusted_manufacturer"] = True
    e1["has_full_disclosure"] = True
    dh1 = build_decision_highlights(e1, _base_scored())

    # Strong evidence branch
    dh2 = build_decision_highlights(_base_enriched(), _base_scored(evidence=15.0))

    # Score >= 75 branch (V4 /100)
    dh3 = build_decision_highlights(_base_enriched(), _base_scored(score_100=80.0))

    # Default branch
    dh4 = build_decision_highlights(_base_enriched(), _base_scored())

    deny = ("not lawful", "banned", "talk to your doctor", "arsenic",
            "trace metals", "undisclosed", "high glycemic", "contraindicated")
    for dh in (dh1, dh2, dh3, dh4):
        low = dh["positive"].lower()
        for token in deny:
            assert token not in low, f"positive leaks {token!r}: {dh['positive']!r}"


def test_positive_strong_quality_uses_v4_score_100() -> None:
    """The 'strong overall quality' positive is gated on the V4 /100 score
    (score_100_equivalent >= 75), not the retired V3 score_80."""
    dh = build_decision_highlights(_base_enriched(), _base_scored(score_100=80.0))
    assert dh["positive"] == "Strong overall quality profile."
    dh_low = build_decision_highlights(_base_enriched(), _base_scored(score_100=70.0))
    assert "closer look" in dh_low["positive"].lower()


def test_positive_evidence_uses_v4_evidence_pillar() -> None:
    """The 'meaningful clinical evidence' positive is gated on the V4 evidence
    pillar (>= 12 of /20), not the retired V3 section_scores.C."""
    dh = build_decision_highlights(_base_enriched(), _base_scored(evidence=13.0))
    assert dh["positive"] == "Backed by meaningful clinical evidence."
    dh_low = build_decision_highlights(_base_enriched(), _base_scored(evidence=8.0))
    assert "closer look" in dh_low["positive"].lower()


# ---------------------------------------------------------------------------
# Validator — raises on violation; silent on clean input.
# ---------------------------------------------------------------------------

def test_validator_passes_on_clean_highlights() -> None:
    dh = {
        "positive": "Strong overall quality profile.",
        "caution": "No major caution signal surfaced.",
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
        "trust": "",
    }
    _validate_decision_highlights(dh, "OK-LIST")  # no exception

    dh_bad = {
        "positive": ["Safe baseline.", "Not lawful as a US dietary supplement."],
        "caution": "",
        "trust": "",
    }
    with pytest.raises(ValueError):
        _validate_decision_highlights(dh_bad, "BAD-LIST")


def test_highlights_ignore_legacy_quality_and_readiness_verdicts() -> None:
    results = []
    for verdict in ("SAFE", "POOR", "CAUTION"):
        scored = _base_scored(verdict=verdict)
        scored.update(product_safety_status="no_known_catalog_concern",
                      quality_assessment_status="complete", quality_tier="Poor")
        results.append(build_decision_highlights(_base_enriched(), scored))
    assert results[0] == results[1] == results[2]


def test_highlights_use_typed_safety_and_assessment_independently() -> None:
    scored = _base_scored(verdict="SAFE")
    scored.update(product_safety_status="caution", quality_assessment_status="complete")
    assert "safety" in build_decision_highlights(_base_enriched(), scored)["caution"].lower()
    scored.update(product_safety_status="no_known_catalog_concern", quality_assessment_status="partial")
    copy = build_decision_highlights(_base_enriched(), scored)["caution"]
    assert "assessment" in copy.lower() and "incomplete" in copy.lower()
    assert "safety" not in copy.lower()


def test_highlights_missing_safety_never_claims_no_caution() -> None:
    scored = _base_scored()
    for status in (None, "not_assessed", "unknown_status"):
        scored["product_safety_status"] = status
        assert build_decision_highlights(_base_enriched(), scored)["caution"] == "Safety assessment is incomplete."


def test_highlights_keep_additive_reason_on_a_blocked_product() -> None:
    enriched = _base_enriched()
    enriched["harmful_additives"] = [{"name": "Titanium dioxide"}]
    scored = _base_scored(verdict="SAFE")
    scored["product_safety_status"] = "blocked"
    result = build_decision_highlights(enriched, scored)
    assert result["caution"] == "Includes additives with known safety concerns."
