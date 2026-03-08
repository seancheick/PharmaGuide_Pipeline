#!/usr/bin/env python3
"""Regression tests for manufacturer violation matching precision."""

import os
import sys

import pytest

# Add parent directory to path for imports (normalized to avoid ".." in __file__)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


def _set_violations_db(enricher: SupplementEnricherV3, rows):
    enricher.databases["manufacturer_violations"] = {
        "manufacturer_violations": rows
    }


def test_violation_match_rejects_fuzzy_false_positive(enricher):
    """Do not penalize when names are only fuzzy-similar (Thorne/Health Fixer case)."""
    _set_violations_db(
        enricher,
        [
            {
                "id": "V035",
                "manufacturer": "Health Fixer",
                "violation_type": "Class I Recall",
                "severity_level": "critical",
                "total_deduction_applied": -18.0,
                "is_resolved": False,
                "date": "2025-04-29",
            }
        ],
    )

    result = enricher._check_violations(
        brand="Thorne PreCon Health",
        manufacturer="Thorne Research, Inc.",
    )

    assert result["found"] is False
    assert result["total_deduction_applied"] == pytest.approx(0.0)
    assert result["violations"] == []


def test_violation_match_accepts_exact_after_company_normalization(enricher):
    """Exact company match should survive LLC/Inc suffix normalization."""
    _set_violations_db(
        enricher,
        [
            {
                "id": "V100",
                "manufacturer": "Healthy Directions",
                "violation_type": "Warning Letter",
                "severity_level": "high",
                "total_deduction_applied": -8.0,
                "is_resolved": True,
                "date": "2024-01-10",
            }
        ],
    )

    result = enricher._check_violations(
        brand="",
        manufacturer="Healthy Directions, LLC",
    )

    assert result["found"] is True
    assert result["total_deduction_applied"] == pytest.approx(-8.0)
    assert len(result["violations"]) == 1
    assert result["violations"][0]["match_method"] == "exact_company_normalized"
    assert result["violations"][0]["match_source"] == "manufacturer"
    assert result["violations"][0]["match_confidence"] == pytest.approx(1.0)


def test_violation_match_accepts_approved_alias_only(enricher):
    """Approved aliases can be used for deterministic penalty matching."""
    _set_violations_db(
        enricher,
        [
            {
                "id": "V101",
                "manufacturer": "Health Fixer",
                "aliases": ["PreCon Health"],
                "violation_type": "Class I Recall",
                "severity_level": "critical",
                "total_deduction_applied": -18.0,
                "is_resolved": False,
                "date": "2025-04-29",
            }
        ],
    )

    result = enricher._check_violations(
        brand="PreCon Health",
        manufacturer="Thorne Research, Inc.",
    )

    assert result["found"] is True
    assert result["total_deduction_applied"] == pytest.approx(-18.0)
    assert len(result["violations"]) == 1
    assert result["violations"][0]["match_source"] == "brandName"
    assert result["violations"][0]["matched_alias"] == "PreCon Health"


def test_violation_match_rejects_shared_token_only(enricher):
    """Shared token overlap is insufficient without exact normalized equality."""
    _set_violations_db(
        enricher,
        [
            {
                "id": "V102",
                "manufacturer": "World Green Nutrition, Inc.",
                "violation_type": "Class I Recall",
                "severity_level": "critical",
                "total_deduction_applied": -10.0,
                "is_resolved": True,
                "date": "2024-01-12",
            }
        ],
    )

    result = enricher._check_violations(
        brand="Nutrition Now",
        manufacturer="Nutrition Now",
    )

    assert result["found"] is False
    assert result["total_deduction_applied"] == pytest.approx(0.0)
    assert result["violations"] == []
