#!/usr/bin/env python3
"""Regression checks for harmful additive umbrella parents vs atomic children."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enrich_supplements_v3 import SupplementEnricherV3


def test_disabled_harmful_umbrella_parent_does_not_score_when_child_matches():
    enricher = SupplementEnricherV3()

    harmful = enricher._check_harmful_additives([{"name": "TBHQ"}])
    ids = {item.get("additive_id") for item in harmful.get("additives", [])}

    assert "ADD_TBHQ" in ids
    assert "ADD_SYNTHETIC_ANTIOXIDANTS" not in ids


def test_atomic_nitrite_child_matches_without_parent_double_count():
    enricher = SupplementEnricherV3()

    harmful = enricher._check_harmful_additives([{"name": "Sodium Nitrite"}])
    ids = {item.get("additive_id") for item in harmful.get("additives", [])}

    assert "ADD_SODIUM_NITRITE" in ids
    assert "ADD_NITRITES" not in ids
