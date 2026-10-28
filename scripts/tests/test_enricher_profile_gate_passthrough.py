#!/usr/bin/env python3
"""Phase 2 / Step 7 — verify the enricher passes profile_gate through.

After v6.0 schema, every emitted condition_hits[], drug_class_hits[], and
pregnancy_lactation entry on a product's safety_hits[] MUST carry the
source rule's profile_gate. Flutter reads detail_blobs (downstream of the
enricher) and evaluates the gate to decide whether to render an alert —
so missing the gate at this layer means the alert ships ungated.
"""
from __future__ import annotations

import copy
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


def test_reproductive_hits_are_scoped_to_their_own_curated_condition(enricher):
    """A shared source block must not apply pregnancy severity to breastfeeding."""
    enriched = {
        "ingredient_quality_data": {
            "ingredients": [_ingredient("Yohimbe", "yohimbe")],
            "ingredients_skipped": [],
        }
    }
    enricher._collect_interaction_profile(enriched)
    hits = [
        condition
        for hit in enriched["ingredient_quality_data"]["ingredients"][0]["safety_hits"]
        for condition in hit.get("condition_hits", [])
        if condition["condition_id"] in {"pregnancy", "lactation"}
    ]
    assert hits
    from profile_gate_evaluator import evaluate_profile_gate, validate_profile_gate
    expected = {"pregnancy": "pregnant", "lactation": "breastfeeding"}
    for hit in hits:
        assert hit["profile_gate"]["requires"]["profile_flags_any"] == [expected[hit["condition_id"]]]
    assert any(hit["condition_id"] == "lactation" and hit["severity"] == "avoid" for hit in hits)
    assert any(hit["condition_id"] == "pregnancy" and hit["severity"] == "contraindicated" for hit in hits)

    for flags in ([], ["pregnant"], ["breastfeeding"], ["pregnant", "breastfeeding"]):
        for hit in hits:
            gate = hit["profile_gate"]
            assert validate_profile_gate(gate) == []
            result = evaluate_profile_gate(
                gate, {"profile_flags": flags}, {}, base_severity=hit["severity"]
            )
            assert result.fires == (expected[hit["condition_id"]] in flags)
            if result.fires:
                assert result.severity == hit["severity"]

    breastfeeding = next(hit for hit in hits if hit["condition_id"] == "lactation")
    assert "stimulant effects" in breastfeeding["alert_body"]
    assert "during pregnancy and breastfeeding" in breastfeeding["alert_body"]
    assert "pregnan" not in breastfeeding["alert_headline"].lower()
    assert breastfeeding["sources"] == ["https://www.nccih.nih.gov/health/yohimbe"]
    # Rendering target-specific copy must not rewrite the curated source record.
    source_block = next(
        hit["pregnancy_lactation"]
        for hit in enriched["ingredient_quality_data"]["ingredients"][0]["safety_hits"]
        if hit.get("pregnancy_lactation", {}).get("lactation_category") == "avoid"
    )
    assert source_block["profile_gate"]["requires"]["profile_flags_any"] == ["pregnant", "breastfeeding"]


def test_sage_pregnancy_warning_explains_why_and_cites_the_reason(enricher):
    enriched = {
        "ingredient_quality_data": {
            "ingredients": [_ingredient("Sage extract", "sage")],
            "ingredients_skipped": [],
        }
    }

    enricher._collect_interaction_profile(enriched)

    pregnancy_hits = [
        condition
        for hit in enriched["ingredient_quality_data"]["ingredients"][0]["safety_hits"]
        for condition in hit.get("condition_hits", [])
        if condition.get("condition_id") == "pregnancy"
    ]
    assert len(pregnancy_hits) == 1
    pregnancy = pregnancy_hits[0]
    reason = f"{pregnancy.get('mechanism', '')} {pregnancy.get('alert_body', '')}".lower()
    assert pregnancy["severity"] == "avoid"
    assert "thujone" in reason
    assert any("nccih.nih.gov/health/sage" in source for source in pregnancy["sources"])
    assert pregnancy["profile_gate"]["requires"]["profile_flags_any"] == ["pregnant"]


def test_st_johns_wort_breastfeeding_warning_has_target_specific_reason(enricher):
    enriched = {
        "ingredient_quality_data": {
            "ingredients": [_ingredient("St. John's Wort", "st_johns_wort")],
            "ingredients_skipped": [],
        }
    }

    enricher._collect_interaction_profile(enriched)

    lactation_hits = [
        condition
        for hit in enriched["ingredient_quality_data"]["ingredients"][0]["safety_hits"]
        for condition in hit.get("condition_hits", [])
        if condition.get("condition_id") == "lactation"
    ]
    assert len(lactation_hits) == 1
    lactation = lactation_hits[0]
    reason = f"{lactation.get('mechanism', '')} {lactation.get('alert_body', '')}".lower()
    assert lactation["severity"] == "caution"
    assert "colic" in reason
    assert "drowsiness" in reason
    assert "fetal" not in reason
    assert any("NBK501770" in source for source in lactation["sources"])
    assert lactation["profile_gate"]["requires"]["profile_flags_any"] == ["breastfeeding"]


def test_shared_life_stage_warning_keeps_authored_reason_and_source(enricher):
    enriched = {
        "ingredient_quality_data": {
            "ingredients": [_ingredient("Zinc", "zinc")],
            "ingredients_skipped": [],
        }
    }

    enricher._collect_interaction_profile(enriched)

    hits = [
        condition
        for hit in enriched["ingredient_quality_data"]["ingredients"][0]["safety_hits"]
        for condition in hit.get("condition_hits", [])
        if condition.get("condition_id") in {"pregnancy", "lactation"}
    ]
    assert {hit["condition_id"] for hit in hits} == {"pregnancy", "lactation"}
    for hit in hits:
        assert "RDA-range doses" in hit["alert_body"]
        assert "Higher therapeutic doses" in hit["alert_body"]
        assert hit["sources"] == [
            "https://ods.od.nih.gov/factsheets/Zinc-HealthProfessional/"
        ]
        expected_flag = "pregnant" if hit["condition_id"] == "pregnancy" else "breastfeeding"
        assert hit["profile_gate"]["requires"]["profile_flags_any"] == [expected_flag]


def test_shared_lactation_warning_uses_reviewed_body_not_pregnancy_mechanism(enricher):
    enriched = {
        "ingredient_quality_data": {
            "ingredients": [_ingredient("Black cohosh", "black_cohosh")],
            "ingredients_skipped": [],
        }
    }

    enricher._collect_interaction_profile(enriched)

    lactation_hits = [
        condition
        for hit in enriched["ingredient_quality_data"]["ingredients"][0]["safety_hits"]
        for condition in hit.get("condition_hits", [])
        if condition.get("condition_id") == "lactation"
    ]
    assert len(lactation_hits) == 1
    lactation = lactation_hits[0]
    reason = f"{lactation.get('mechanism', '')} {lactation.get('alert_body', '')}".lower()
    assert "breastfeeding safety" in reason
    assert "nursing infant" in reason
    assert lactation["mechanism"] == lactation["alert_body"]
    assert not lactation["mechanism"].startswith("Pregnancy safety is uncertain")
    assert lactation["profile_gate"]["requires"]["profile_flags_any"] == [
        "breastfeeding"
    ]


def test_vitamin_b6_pregnancy_warning_does_not_reuse_lactation_reason(enricher):
    enriched = {
        "ingredient_quality_data": {
            "ingredients": [_ingredient("Vitamin B6", "vitamin_b6_pyridoxine")],
            "ingredients_skipped": [],
        }
    }

    enricher._collect_interaction_profile(enriched)

    pregnancy_hits = [
        condition
        for hit in enriched["ingredient_quality_data"]["ingredients"][0]["safety_hits"]
        for condition in hit.get("condition_hits", [])
        if condition.get("condition_id") == "pregnancy"
    ]
    assert len(pregnancy_hits) == 1
    pregnancy = pregnancy_hits[0]
    reason = f"{pregnancy.get('mechanism', '')} {pregnancy.get('alert_body', '')}".lower()
    assert pregnancy["severity"] == "monitor"
    assert "nerve damage" in reason
    assert "milk supply" not in reason
    assert "breastfeed" not in reason
    assert any(
        "ods.od.nih.gov/factsheets/Pregnancy-HealthProfessional" in source
        for source in pregnancy["sources"]
    )
    assert pregnancy["profile_gate"]["requires"]["profile_flags_any"] == [
        "pregnant"
    ]


def test_licorice_breastfeeding_warning_does_not_reuse_fetal_reason(enricher):
    enriched = {
        "ingredient_quality_data": {
            "ingredients": [_ingredient("Licorice root", "licorice_root")],
            "ingredients_skipped": [],
        }
    }

    enricher._collect_interaction_profile(enriched)

    hits = [
        condition
        for hit in enriched["ingredient_quality_data"]["ingredients"][0]["safety_hits"]
        for condition in hit.get("condition_hits", [])
        if condition.get("condition_id") == "lactation"
    ]
    assert len(hits) == 1
    lactation = hits[0]
    reason = f"{lactation.get('mechanism', '')} {lactation.get('alert_body', '')}".lower()
    assert "milk" in reason or "breastfeed" in reason
    assert "fetus" not in reason
    assert "placental" not in reason
    assert any("NBK501840" in source for source in lactation["sources"])
    assert lactation["profile_gate"]["requires"]["profile_flags_any"] == ["breastfeeding"]


def _nested_bitters_row(safety_flags: list) -> dict:
    """285635 (Liver Bitters Detox Spray): bitter orange nested under a
    non-therapeutic blend has no identity of its own; only its label row's
    banned/high-risk safety match names it."""
    path = "ingredientRows[0].nestedRows[7]"
    name = "organic Bitter Orange (fruit) extract"
    return {
        "activeIngredients": [{"name": name, "raw_source_path": path, "safety_flags": safety_flags}],
        "ingredient_quality_data": {
            # Production enrichment always carries the scorable list; its
            # row selection is the path under test.
            "ingredients_scorable": [],
            "ingredients": [],
            "ingredients_skipped": [{
                "name": name, "raw_source_text": name, "standard_name": name,
                "raw_source_path": path, "canonical_source_db": "unmapped",
                "skip_reason": "nested_under_non_therapeutic_parent",
            }],
        },
    }


def test_row_known_only_by_its_safety_match_meets_that_records_rules(enricher):
    enriched = _nested_bitters_row([{
        "source_db": "banned_recalled_ingredients", "entry_id": "BANNED_BITTER_ORANGE",
    }])

    profile = enricher._collect_interaction_profile(enriched)

    pregnancy = [
        hit
        for alert in profile["ingredient_alerts"]
        if alert["rule_id"] == "RULE_BANNED_BITTER_ORANGE_PREGNANCY"
        for hit in alert["condition_hits"]
        if hit["condition_id"] == "pregnancy"
    ]
    assert len(pregnancy) == 1
    assert pregnancy[0]["severity"] == "avoid"
    # No disclosed synephrine: amount unknown, still a hard pregnancy warning.
    assert pregnancy[0]["dose_decision"]["evaluation_status"] == "amount_unknown"
    assert pregnancy[0]["dose_decision"]["consumer_disposition"] == "block"
    assert "pregnancy" in profile["condition_summary"]


def test_row_with_no_identity_and_no_safety_match_meets_no_rules(enricher):
    profile = enricher._collect_interaction_profile(_nested_bitters_row([]))

    assert profile["ingredient_alerts"] == []


def _bitter_orange_hits(profile: dict, condition: str = "pregnancy") -> list:
    return [
        (alert["ingredient_name"], alert.get("subject_ref"), hit)
        for alert in profile["ingredient_alerts"]
        if "BITTER_ORANGE" in str(alert["rule_id"])
        for hit in alert["condition_hits"]
        if hit["condition_id"] == condition
    ]


def test_safety_matched_row_reloaded_into_both_lists_is_one_subject(enricher):
    """A reloaded artifact holds separate copies of one row in ingredients and
    ingredients_skipped; the safety-record rules still fire once."""
    enriched = _nested_bitters_row([{
        "source_db": "banned_recalled_ingredients", "entry_id": "BANNED_BITTER_ORANGE",
    }])
    iqd = enriched["ingredient_quality_data"]
    iqd["ingredients"] = [copy.deepcopy(iqd["ingredients_skipped"][0])]

    profile = enricher._collect_interaction_profile(enriched)

    assert len(_bitter_orange_hits(profile)) == 1


def test_identified_row_keeps_its_identity_and_meets_its_safety_rules(enricher):
    """182627: Bitter Orange Citrus Bioflavonoids is an IQM row; its safety match
    adds the bitter orange rules without replacing the row's own subject."""
    enriched = _nested_bitters_row([{
        "source_db": "banned_recalled_ingredients", "entry_id": "BANNED_BITTER_ORANGE",
    }])
    row = enriched["ingredient_quality_data"]["ingredients_skipped"][0]
    row.update(
        name="Bitter Orange Citrus Bioflavonoids",
        raw_source_text="Bitter Orange Citrus Bioflavonoids",
        canonical_id="citrus_bioflavonoids",
        canonical_source_db="ingredient_quality_map",
        skip_reason=None,
        quantity=200,
        unit="mg",
    )
    enriched["ingredient_quality_data"]["ingredients_scorable"] = [row]

    hits = _bitter_orange_hits(enricher._collect_interaction_profile(enriched))

    assert hits
    assert {subject["canonical_id"] for _name, subject, _hit in hits} == {"citrus_bioflavonoids"}


def test_derived_marker_row_does_not_inherit_its_source_rows_safety_match(enricher):
    enriched = _nested_bitters_row([{
        "source_db": "banned_recalled_ingredients", "entry_id": "BANNED_BITTER_ORANGE",
    }])
    enriched["ingredient_quality_data"]["ingredients_skipped"][0]["delivers_markers"] = [{
        "marker_canonical_id": "synephrine",
        "estimation_method": "standardization_pct",
        "estimated_dose_mg": 12.0,
    }]

    hits = _bitter_orange_hits(enricher._collect_interaction_profile(enriched))

    assert hits
    assert not any(name.startswith("Synephrine (from") for name, _subject, _hit in hits)
