"""Tests for context-aware harmful additive routing.

Verifies that the scorer suppresses precautionary (low/moderate) harmful
additive penalties for ingredients sourced from the Supplement Facts
(active) panel, while still applying them for Other Ingredients (inactive).

High/critical severity penalties fire regardless of source section.

See: enrich_supplements_v3.py _collect_contaminant_data (source tagging)
     score_supplements.py _compute_harmful_additives_penalty (suppression)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure scripts/ is on the path so we can import score_supplements
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from score_supplements import SupplementScorer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_product(additives: list[dict]) -> dict:
    """Minimal product dict with harmful additives for penalty testing."""
    return {
        "dsld_id": "test_routing",
        "product_name": "Test Routing Product",
        "enrichment_version": "3.4.0",
        "contaminant_data": {
            "harmful_additives": {
                "found": bool(additives),
                "additives": additives,
            },
            "banned_substances": {"found": False, "substances": []},
            "allergens": {"found": False, "allergens": []},
        },
    }


def _make_additive(
    name: str,
    additive_id: str,
    severity: str,
    source_section: str,
) -> dict:
    """Minimal harmful additive match record."""
    return {
        "ingredient": name,
        "additive_name": name,
        "additive_id": additive_id,
        "severity_level": severity,
        "source_section": source_section,
        "category": "test",
    }


@pytest.fixture(scope="module")
def scorer() -> SupplementScorer:
    """Scorer with default config — no data files needed for penalty calc."""
    return SupplementScorer.__new__(SupplementScorer)


@pytest.fixture(autouse=True)
def _patch_config(scorer):
    """Ensure scorer has a minimal config for B1 penalty."""
    scorer.config = {
        "section_B_safety_purity": {
            "B1_harmful_additives": {
                "cap": 8.0,
            },
        },
    }


# ---------------------------------------------------------------------------
# Scenario 1: Inactive-source → penalty fires normally
# ---------------------------------------------------------------------------


def test_inactive_low_severity_fires(scorer):
    """Low severity additive in Other Ingredients → penalty applied."""
    product = _make_product([
        _make_additive("Silicon Dioxide", "ADD_SILICON_DIOXIDE", "low", "inactive"),
    ])
    penalty = scorer._compute_harmful_additives_penalty(product)
    assert penalty > 0, "Low severity inactive additive should incur a penalty"


def test_inactive_moderate_severity_fires(scorer):
    """Moderate severity additive in Other Ingredients → penalty applied."""
    product = _make_product([
        _make_additive("Xylitol", "ADD_XYLITOL", "moderate", "inactive"),
    ])
    penalty = scorer._compute_harmful_additives_penalty(product)
    assert penalty > 0, "Moderate severity inactive additive should incur a penalty"


# ---------------------------------------------------------------------------
# Scenario 2: Active-source + low/moderate severity → penalty suppressed
# ---------------------------------------------------------------------------


def test_active_low_severity_suppressed(scorer):
    """Low severity additive from Supplement Facts → penalty suppressed."""
    product = _make_product([
        _make_additive("Silicon Dioxide", "ADD_SILICON_DIOXIDE", "low", "active"),
    ])
    penalty = scorer._compute_harmful_additives_penalty(product)
    assert penalty == 0, "Low severity active-source additive should be suppressed"


def test_active_moderate_severity_suppressed(scorer):
    """Moderate severity additive from Supplement Facts → penalty suppressed."""
    product = _make_product([
        _make_additive("Senna", "ADD_SENNA", "moderate", "active"),
    ])
    penalty = scorer._compute_harmful_additives_penalty(product)
    assert penalty == 0, "Moderate severity active-source additive should be suppressed"


# ---------------------------------------------------------------------------
# Scenario 3: Active-source + high/critical severity → penalty still fires
# ---------------------------------------------------------------------------


def test_active_high_severity_fires(scorer):
    """High severity additive from Supplement Facts → penalty still applied."""
    product = _make_product([
        _make_additive("Senna", "ADD_SENNA", "high", "active"),
    ])
    penalty = scorer._compute_harmful_additives_penalty(product)
    assert penalty > 0, "High severity active-source additive should still fire"


def test_active_critical_severity_fires(scorer):
    """Critical severity additive from Supplement Facts → penalty fires."""
    product = _make_product([
        _make_additive("Dangerous Compound", "ADD_DANGER", "critical", "active"),
    ])
    penalty = scorer._compute_harmful_additives_penalty(product)
    assert penalty > 0, "Critical severity active-source additive should fire"


# ---------------------------------------------------------------------------
# Scenario 4: Mixed sources — only inactive penalties count
# ---------------------------------------------------------------------------


def test_mixed_sources_only_inactive_counts(scorer):
    """Same additive from both active (moderate) and inactive (moderate).
    Only the inactive entry should contribute to the penalty."""
    product = _make_product([
        _make_additive("Xylitol", "ADD_XYLITOL", "moderate", "active"),
        _make_additive("BHT", "ADD_BHT", "moderate", "inactive"),
    ])
    penalty = scorer._compute_harmful_additives_penalty(product)
    # Only BHT (inactive, moderate) should fire — xylitol (active, moderate) suppressed
    assert penalty > 0, "Inactive-source additive should fire"
    # Penalty should equal exactly 1 moderate item (1.0 default for moderate)
    assert penalty == 1.0, f"Expected 1.0 for single moderate inactive, got {penalty}"


def test_no_additives_zero_penalty(scorer):
    """No harmful additives at all → zero penalty."""
    product = _make_product([])
    penalty = scorer._compute_harmful_additives_penalty(product)
    assert penalty == 0


# ---------------------------------------------------------------------------
# Scenario 5: Unknown source_section → treated as penalty (safe default)
# ---------------------------------------------------------------------------


def test_unknown_source_not_suppressed(scorer):
    """Missing source_section defaults to 'unknown' → penalty fires (safe default)."""
    product = _make_product([{
        "ingredient": "Mystery Additive",
        "additive_name": "Mystery",
        "additive_id": "ADD_MYSTERY",
        "severity_level": "low",
        # no source_section key
        "category": "test",
    }])
    penalty = scorer._compute_harmful_additives_penalty(product)
    assert penalty > 0, "Unknown source should default to penalty (safe default)"


# ---------------------------------------------------------------------------
# Scenario 6: Verify penalty values match risk_map
# ---------------------------------------------------------------------------


def test_penalty_values_match_risk_map(scorer):
    """Verify exact penalty amounts for each severity level."""
    for severity, expected in [("low", 0.5), ("moderate", 1.0), ("high", 2.0), ("critical", 3.0)]:
        product = _make_product([
            _make_additive(f"Test-{severity}", f"ADD_{severity.upper()}", severity, "inactive"),
        ])
        penalty = scorer._compute_harmful_additives_penalty(product)
        assert penalty == expected, f"Severity '{severity}' should give {expected}, got {penalty}"
