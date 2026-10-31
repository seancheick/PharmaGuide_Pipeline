"""An opaque dominant botanical blend explains its own limitation.

When the Formulation subject is a printed blend total whose preparation cannot
be verified (Citri-Sculpt Blend 900 mg, 176190; Sinetrol-XPur Mediterranean
Citrus Blend 450 mg, 232084), the score stays conservative, and the reason names
that blend instead of saying no botanical identity was confirmed. Green tea and
guarana on 176190 are separately identified and are assessed separately.
"""
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def _artifact(fixture):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact

    logging.disable(logging.INFO)
    raw = json.loads((FIXTURES / fixture).read_text())
    enriched, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    return build_scored_artifact(enriched)


@pytest.mark.parametrize("fixture,label,separate", [
    ("raw_blend_grapefruit_176190.json", "Citri-Sculpt Blend, 900 mg", True),
    ("raw_title_green_67032.json", "Citri-Sculpt Blend, 900 mg", True),
    ("raw_blend_grapefruit_232084.json", "Sinetrol-XPur Mediterranean Citrus Blend, 450 mg", False),
])
def test_opaque_primary_blend_names_its_preparation_limitation(fixture, label, separate):
    formulation = _artifact(fixture)["quality_pillars_v4"]["formulation"]
    expected = (f"The main botanical blend ({label}) is disclosed, but its exact preparation "
                "cannot be verified for Formulation scoring.")
    if separate:
        expected += " Other identified ingredients are assessed separately."
    assert formulation["reason"] == expected
    # Copy only: the unverified blend still earns no formulation credit.
    assert formulation["score"] == 0.0
    assert any(e["id"] == "weak_or_unidentified_botanical" for e in formulation["receipt"]["entries"])


def test_unidentified_botanical_without_a_blend_total_keeps_the_identity_reason():
    from scoring_v4.quality_score import _profile_formulation_reason
    metadata = {"botanical_profile_applied": True,
                "botanical_formulation": {"weak_or_unidentified_botanical": -4.0}}
    assert _profile_formulation_reason(metadata) == (
        "Botanical identity could not be confirmed, so no formulation credit was given.")
