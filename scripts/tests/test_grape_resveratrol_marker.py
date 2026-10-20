"""A grape extract standardized to trans-resveratrol carries a resveratrol marker.

BioVin Advanced (269265, 302705) is a 60 mg red-wine grape extract whose label note declares
"5% Trans-Resveratrol" (3 mg). Its identity is grape, not resveratrol (ADR-0005; a grape extract
row is not a resveratrol row), so RULE_IQM_RESVERATROL_BLEEDING never reached it: grape had no
resveratrol entry in botanical_marker_contributions.json, and the marker scan never read the
row's printed note. The marker owner now carries an analysis-only resveratrol row from the
declared standardization; the identity stays grape and the rule's own materiality decides.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def enricher():
    from enrich_supplements_v3 import SupplementEnricherV3

    return SupplementEnricherV3()


@pytest.fixture(scope="module")
def enrich(enricher):
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalizer, cache = EnhancedDSLDNormalizer(), {}

    def run(dsld_id: int) -> dict:
        if dsld_id not in cache:
            raw = json.loads((FIXTURES / f"grape_resveratrol_{dsld_id}_raw.json").read_text())
            cache[dsld_id], _ = enricher.enrich_product(normalizer.normalize_product(raw))
        return cache[dsld_id]

    return run


@pytest.mark.parametrize("dsld_id", [269265, 302705])
def test_declared_trans_resveratrol_reaches_the_resveratrol_rule(enrich, dsld_id):
    enriched = enrich(dsld_id)
    [row] = [r for r in enriched["ingredient_quality_data"]["ingredients"] if r.get("raw_source_text") == "BioVin Advanced"]
    assert row["canonical_id"] == "grape"
    [marker] = [m for m in row["delivers_markers"] if m["marker_canonical_id"] == "resveratrol"]
    assert (marker["estimation_method"], marker["estimated_dose_mg"]) == ("standardization_pct", 3.0)
    alerts = [a for a in enriched["interaction_profile"]["ingredient_alerts"] if a["rule_id"] == "RULE_IQM_RESVERATROL_BLEEDING"]
    assert alerts and alerts[0]["subject_ref"]["canonical_id"] == "resveratrol"


def test_grape_without_a_declared_standardization_carries_no_resveratrol_mass(enricher):
    markers = enricher._compute_delivers_markers(
        {"canonical_id": "grape", "raw_source_text": "Grape Skin Extract", "quantity": 200, "unit_normalized": "mg"}
    )
    [marker] = [m for m in markers if m["marker_canonical_id"] == "resveratrol"]
    assert marker["estimated_dose_mg"] is None and marker["estimation_method"] == "none"


def test_another_constituents_percentage_is_not_resveratrol(enricher):
    """"40% Total Polyphenols" alone never becomes a resveratrol mass."""
    markers = enricher._compute_delivers_markers(
        {"canonical_id": "grape", "raw_source_text": "Grape Extract", "quantity": 100, "unit_normalized": "mg"},
        row_notes="40% Total Polyphenols",
    )
    [marker] = [m for m in markers if m["marker_canonical_id"] == "resveratrol"]
    assert marker["estimated_dose_mg"] is None


def _resveratrol_rule():
    rules = json.loads((SCRIPTS / "data" / "ingredient_interaction_rules.json").read_text())["interaction_rules"]
    [rule] = [r for r in rules if r["id"] == "RULE_IQM_RESVERATROL_BLEEDING"]
    return rule


def test_resveratrol_bleeding_advisory_states_uncertainty_without_advice_to_change_medication():
    """Sean, 2026-10-19: keep a clearly qualified advisory for anticoagulants,
    antiplatelets and bleeding disorders; clinical significance at low declared
    amounts is uncertain. No proven-risk wording, no mg cutoff, no medication
    adjustment."""
    rule = _resveratrol_rule()
    subs = [s for s in rule["condition_rules"] if s["condition_id"] == "bleeding_disorders"]
    subs += [s for s in rule["drug_class_rules"] if s["drug_class_id"] in ("anticoagulants", "antiplatelets")]
    assert len(subs) == 3
    for sub in subs:
        copy = " ".join(str(sub.get(k) or "") for k in ("alert_headline", "alert_body", "action", "informational_note"))
        lowered = copy.lower()
        assert "uncertain" in lowered or "not established" in lowered
        for banned in ("inr", "dose may need", "limit dose", "reduce", "adjust", "increases bleeding", "proven"):
            assert banned not in lowered, (sub.get("condition_id") or sub.get("drug_class_id"), banned)
        assert not __import__("re").search(r"\d+\s*mg", copy)
        assert sub["materiality"] == "presence"
    assert rule["dose_thresholds"] == []


def _knotweed_row(enriched):
    rows = [r for r in enriched["ingredient_quality_data"]["ingredients"]
            if "knotweed" in str(r.get("raw_source_text")).lower()]
    assert rows
    return rows[0]


def _alerts(enriched, rule_id="RULE_IQM_RESVERATROL_BLEEDING"):
    return [a for a in enriched["interaction_profile"]["ingredient_alerts"] if a["rule_id"] == rule_id]


@pytest.mark.parametrize("dsld_id,dose_mg", [
    # "Japanese Knotweed root extract" inside a blend, "standardized to 50% Resveratrol", no own amount.
    (249518, None),
    # 150 mg "Japanese Knotweed extract", standardized to (75 mg) 50% Resveratrol.
    (251683, 75.0),
])
def test_knotweed_keeps_its_plant_identity_and_declared_resveratrol_meets_its_rule(enrich, dsld_id, dose_mg):
    """Sean, 2026-10-19 (ADR-0005 amendment): knotweed keeps its verified plant
    identity; a source-qualified constituent route reaches resveratrol warnings."""
    enriched = enrich(dsld_id)
    row = _knotweed_row(enriched)
    assert row["canonical_id"] == "japanese_knotweed"
    [marker] = [m for m in row["delivers_markers"] if m["marker_canonical_id"] == "resveratrol"]
    assert marker["declared_standardization_pct"] == 50.0
    assert marker["estimated_dose_mg"] == dose_mg
    assert _alerts(enriched)


def test_undeclared_knotweed_keeps_its_identity_without_a_resveratrol_mass(enrich):
    """302512 "Japanese Knotweed root extract" declares no resveratrol: the plant
    identity stays and no resveratrol amount is invented."""
    enriched = enrich(302512)
    row = _knotweed_row(enriched)
    assert row["canonical_id"] == "japanese_knotweed"
    assert all(m.get("estimated_dose_mg") is None and not m.get("declared_standardization_pct")
               for m in row["delivers_markers"])


@pytest.mark.parametrize("dsld_id,label", [
    # Alive! Men's Ultra Potency: undeclared "Japanese Knotweed root extract".
    (302512, "Japanese Knotweed root extract"),
    # DHEA Complete: knotweed listed inside its knotweed + grape header blend.
    (58854, "Japanese Knotweed"),
])
def test_knotweed_meets_the_qualified_resveratrol_advisory_without_a_declaration(enrich, dsld_id, label):
    """Knotweed root is a principal resveratrol source (Sean, ADR-0005 amendment):
    the plant keeps its identity and answers to the resveratrol advisory."""
    assert label in {alert["ingredient_name"] for alert in _alerts(enrich(dsld_id))}


def test_knotweed_answers_to_resveratrol_for_interactions_only():
    from identity.interaction import interaction_subject_refs

    refs = interaction_subject_refs("botanical_ingredients", "japanese_knotweed")
    assert refs == [("botanical_ingredients", "japanese_knotweed"), ("ingredient_quality_map", "resveratrol")]
    assert interaction_subject_refs("botanical_ingredients", "grape") == [("botanical_ingredients", "grape")]


def test_blend_header_declared_resveratrol_is_a_declaration_without_a_dose(enrich):
    """181895: the 3 mg "Japanese Knotweed (root) and whole Red Grape extracts" header
    declares "std. to 35% Trans-Resveratrol": resveratrol meets its rule, but the blend
    total never becomes its dose (D1c)."""
    enriched = enrich(181895)
    alerts = _alerts(enriched)
    assert alerts
    for alert in alerts:
        for hit in alert["condition_hits"] + alert["drug_class_hits"]:
            evaluation = hit.get("dose_threshold_evaluation") or {}
            assert evaluation.get("evaluated") is not True
