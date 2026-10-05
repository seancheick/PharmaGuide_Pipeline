"""Every blend carries its 21 CFR 101.36 disclosure tier; hidden-stimulant caution needs materiality.

942 shipped blends left Enrich with disclosure_level null (flattened children under a parent
the cleaner did not flag). Consumers read null differently: Transparency treated 39 fully
quantified blends as hidden, while the safety gate skipped the rest. The tier now comes from
one rule (proprietary_blend_detector.disclosure_tier) for detector, cleaner and enricher.

Sean, 2026-10-04: disclosure and stimulant materiality are separate facts. An explicit stimulant
identity hidden in a partial/none blend triggers the caution; a caffeine-source botanical
triggers it only when the printed blend total cannot rule out a dose above the existing
STIMULANT_CAFFEINE_HIGH_DOSE line.
"""

import copy
import json
from pathlib import Path

import pytest

from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v3 import SupplementEnricherV3
from proprietary_blend_detector import disclosure_tier
from scoring_v4.gate_safety import _has_undisclosed_stimulant_blend
from scoring_v4.scored_artifact import build_scored_artifact

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.mark.parametrize("total,with_amounts,without_amounts,expected", [
    (True, 2, 0, "full"),
    (False, 2, 0, "full"),
    (True, 0, 3, "partial"),
    (True, 1, 2, "partial"),
    (False, 0, 3, "none"),
    (False, 1, 1, "none"),
    (True, 0, 0, "none"),
])
def test_disclosure_tier_follows_101_36(total, with_amounts, without_amounts, expected):
    assert disclosure_tier(total, with_amounts, without_amounts) == expected


@pytest.fixture(scope="module")
def pipeline():
    return EnhancedDSLDNormalizer(), SupplementEnricherV3()


def _run(pipeline, dsld_id):
    normalizer, enricher = pipeline
    raw = json.loads((FIXTURES / f"blend_disclosure_{dsld_id}_raw.json").read_text())
    enriched, _ = enricher.enrich_product(normalizer.normalize_product(copy.deepcopy(raw)))
    return enriched, build_scored_artifact(enriched)


def _blend(enriched, name):
    return next(b for b in enriched["proprietary_blends"] if b["name"] == name)


@pytest.mark.parametrize("dsld_id", ["289060", "1179", "219842", "247106"])
def test_no_blend_leaves_enrich_without_a_tier(pipeline, dsld_id):
    enriched, _ = _run(pipeline, dsld_id)
    assert {b["disclosure_level"] for b in enriched["proprietary_blends"]} <= {"full", "partial", "none"}


def test_fully_quantified_caffeine_blend_is_full_and_not_hidden(pipeline):
    enriched, scored = _run(pipeline, "219842")
    assert _blend(enriched, "Caffeine Blend")["disclosure_level"] == "full"
    assert "STIMULANT_UNDISCLOSED_BLEND" not in scored["flags"]


def test_explicit_caffeine_hidden_in_partial_blend_is_a_caution(pipeline):
    enriched, scored = _run(pipeline, "1179")
    assert _blend(enriched, "Thermo Energy Intensifier")["disclosure_level"] == "partial"
    assert "STIMULANT_UNDISCLOSED_BLEND" in scored["flags"]
    assert scored["product_safety_status"] == "caution"


def test_tiny_multi_botanical_tea_blend_is_partial_without_stimulant_caution(pipeline):
    enriched, scored = _run(pipeline, "289060")
    assert _blend(enriched, "Stress & Energy Adaptogens (Extracts)")["disclosure_level"] == "partial"
    assert "STIMULANT_UNDISCLOSED_BLEND" not in scored["flags"]


def test_partial_blend_without_stimulant_has_no_stimulant_signal(pipeline):
    enriched, scored = _run(pipeline, "247106")
    assert _blend(enriched, "Organic Vegetables")["disclosure_level"] == "partial"
    assert not [f for f in scored["flags"] if f.startswith("STIMULANT_")]


def _product(name, total_mg, kids, level="partial"):
    return {"proprietary_blends": [{
        "name": name, "disclosure_level": level, "blend_total_mg": total_mg,
        "total_weight": total_mg, "unit": "mg" if total_mg else "",
        "child_ingredients": [{"name": k, "amount": None, "unit": ""} for k in kids],
    }]}


@pytest.mark.parametrize("name,total,kids,expected", [
    ("Energy Blend", 63.0, ["Green Tea extract", "Ginseng"], False),
    ("Energy Blend", 600.0, ["Green Tea extract", "Ginseng"], True),
    ("Energy Blend", None, ["Guarana seed extract"], True),
    ("Antioxidant Blend", 50.0, ["Synephrine HCl", "Grape seed"], True),
    ("Antioxidant Blend", 50.0, ["Caffeine Anhydrous"], True),
    ("Pre-Workout Matrix", 50.0, ["Beta-Alanine"], True),
    ("Antioxidant Blend", 900.0, ["Green Tea extract"], False),
])
def test_hidden_stimulant_needs_identity_or_material_botanical_bound(name, total, kids, expected):
    assert _has_undisclosed_stimulant_blend(_product(name, total, kids)) is expected


def test_fully_disclosed_blend_never_hides_a_stimulant():
    assert _has_undisclosed_stimulant_blend(
        _product("Energy Blend", 600.0, ["Caffeine"], level="full")) is False
