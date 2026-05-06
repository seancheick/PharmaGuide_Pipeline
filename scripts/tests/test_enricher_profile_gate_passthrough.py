#!/usr/bin/env python3
"""Phase 2 / Step 7 — verify the enricher passes profile_gate through.

After v6.0 schema, every emitted condition_hits[], drug_class_hits[], and
pregnancy_lactation entry on a product's safety_hits[] MUST carry the
source rule's profile_gate. Flutter reads detail_blobs (downstream of the
enricher) and evaluates the gate to decide whether to render an alert —
so missing the gate at this layer means the alert ships ungated.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


def _ingredient(name: str, canonical_id: str, recognition_source: str = "ingredient_quality_map"):
    """Match the test fixture pattern from test_interaction_tracker.py:
    IQM ingredients use canonical_id; non-IQM sources use matched_entry_id only."""
    base = {
        "name": name,
        "raw_source_text": name,
        "standard_name": name,
        "recognition_source": recognition_source,
        "matched_entry_id": canonical_id,
    }
    if recognition_source == "ingredient_quality_map":
        base["canonical_id"] = canonical_id
    return base


def test_condition_hits_carry_profile_gate(enricher):
    """A product with ginkgo (pregnancy/anticoagulants/bleeding/etc.) must have
    profile_gate on every condition_hit emitted."""
    enriched = {
        "ingredient_quality_data": {
            "ingredients": [_ingredient("Ginkgo biloba", "ginkgo")],
            "ingredients_skipped": [],
        }
    }
    enricher._collect_interaction_profile(enriched)

    safety_hits = enriched["ingredient_quality_data"]["ingredients"][0].get("safety_hits", [])
    assert safety_hits, "ginkgo should produce safety_hits"

    missing = []
    for hit in safety_hits:
        for i, cond in enumerate(hit.get("condition_hits") or []):
            if cond.get("profile_gate") is None:
                missing.append(f"{hit.get('rule_id')}/condition_hits[{i}]({cond.get('condition_id')})")
    assert not missing, f"condition_hits missing profile_gate: {missing}"


def test_drug_class_hits_carry_profile_gate(enricher):
    """drug_class_hits[] must also carry profile_gate."""
    enriched = {
        "ingredient_quality_data": {
            "ingredients": [_ingredient("Ginkgo biloba", "ginkgo")],
            "ingredients_skipped": [],
        }
    }
    enricher._collect_interaction_profile(enriched)

    safety_hits = enriched["ingredient_quality_data"]["ingredients"][0].get("safety_hits", [])
    missing = []
    for hit in safety_hits:
        for i, dr in enumerate(hit.get("drug_class_hits") or []):
            if dr.get("profile_gate") is None:
                missing.append(f"{hit.get('rule_id')}/drug_class_hits[{i}]({dr.get('drug_class_id')})")
    assert not missing, f"drug_class_hits missing profile_gate: {missing}"


def test_pregnancy_block_emit_carries_profile_gate(enricher):
    """When a rule has a pregnancy_lactation block with non-no_data
    categories, the emitted condition_hit (pregnancy/lactation) must carry
    the block's profile_gate."""
    enriched = {
        "ingredient_quality_data": {
            "ingredients": [_ingredient("CBD", "BANNED_CBD_US",
                                          recognition_source="banned_recalled_ingredients")],
            "ingredients_skipped": [],
        }
    }
    enricher._collect_interaction_profile(enriched)

    safety_hits = enriched["ingredient_quality_data"]["ingredients"][0].get("safety_hits", [])
    found_preg_or_lact_with_gate = False
    for hit in safety_hits:
        for cond in hit.get("condition_hits") or []:
            if cond.get("condition_id") in ("pregnancy", "lactation") and cond.get("profile_gate"):
                gate = cond["profile_gate"]
                # The gate may come from condition_rules entry OR pregnancy_lactation block
                # Either way must be a structurally-valid profile_flag gate
                assert gate.get("gate_type") == "profile_flag", gate
                assert gate.get("requires", {}).get("profile_flags_any"), gate
                found_preg_or_lact_with_gate = True
    assert found_preg_or_lact_with_gate, (
        "CBD product must emit at least one pregnancy or lactation condition_hit "
        "with a non-null profile_gate"
    )


def test_profile_gate_shape_matches_source_rule(enricher):
    """The emitted profile_gate is the exact dict from the source rule —
    same gate_type, same requires.profile_flags_any. Uses CBD which has an
    explicit condition_rules entry for pregnancy."""
    import json
    rules = json.loads((Path(__file__).resolve().parents[1] / "data" / "ingredient_interaction_rules.json").read_text())
    target = None
    for r in rules["interaction_rules"]:
        if r["subject_ref"].get("canonical_id") == "BANNED_CBD_US":
            for cr in r.get("condition_rules", []):
                if cr.get("condition_id") == "pregnancy":
                    target = cr
                    break
            if target:
                break
    assert target is not None, "CBD pregnancy condition_rule must exist as fixture"
    expected_gate = target["profile_gate"]

    enriched = {
        "ingredient_quality_data": {
            "ingredients": [_ingredient("CBD", "BANNED_CBD_US",
                                          recognition_source="banned_recalled_ingredients")],
            "ingredients_skipped": [],
        }
    }
    enricher._collect_interaction_profile(enriched)

    safety_hits = enriched["ingredient_quality_data"]["ingredients"][0].get("safety_hits", [])
    matching = [
        cond for hit in safety_hits
        for cond in (hit.get("condition_hits") or [])
        if cond.get("condition_id") == "pregnancy"
    ]
    assert matching, "CBD must emit a pregnancy condition_hit"
    emitted_gate = next((c["profile_gate"] for c in matching if c.get("profile_gate")), None)
    assert emitted_gate is not None
    assert emitted_gate.get("gate_type") == expected_gate["gate_type"]
    assert emitted_gate.get("requires", {}).get("profile_flags_any") == expected_gate["requires"]["profile_flags_any"]
