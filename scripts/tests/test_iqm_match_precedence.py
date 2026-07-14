"""IQM identity resolution is deterministic and configured-priority first (H2)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


def _parent(name: str, *, priority: int, aliases=None, contains=None) -> dict:
    return {
        "standard_name": name,
        "aliases": aliases or [],
        "contains_aliases": contains or [],
        "forms": {},
        "match_rules": {"priority": priority, "match_mode": "alias_and_fuzzy"},
    }


def test_configured_priority_precedes_match_tier(enricher) -> None:
    quality_map = {
        "lower_priority_exact": _parent(
            "Lemon exact",
            priority=2,
            aliases=["Lemon Extract"],
        ),
        "higher_priority_bounded": _parent(
            "Citrus lemon",
            priority=0,
            contains=["lemon"],
        ),
    }

    result = enricher._match_quality_map(
        "Lemon Extract",
        "Lemon Extract",
        quality_map,
    )

    assert result is not None
    assert result["canonical_id"] == "higher_priority_bounded"


def test_dormant_fuzzy_ingredient_identity_fallback_is_retired(enricher) -> None:
    assert not hasattr(enricher, "_fuzzy_ingredient_match")
