#!/usr/bin/env python3
"""Unit coverage for the UNII same-tier conflict scanner.

The runtime normalizer warns when a UNII is claimed by more than one entry at
the same lookup-priority tier. These tests lock the report-only scanner's core
classification rules without depending on the full data corpus.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR / "api_audit"))

import audit_unii_same_tier_conflicts as audit  # noqa: E402


def test_normalize_unii_contract():
    assert audit.normalize_unii(" pq6ck8pd0r ") == "PQ6CK8PD0R"
    assert audit.normalize_unii("0") is None
    assert audit.normalize_unii("1") is None
    assert audit.normalize_unii("PQ6CK8PD0") is None
    assert audit.normalize_unii("PQ6CK8PD0R!") is None


def test_same_tier_grouping_excludes_cross_tier_collision():
    records = [
        audit.UniiRecord(
            tier=4,
            tier_name="ingredient_quality_map",
            source="iqm_parent",
            file="ingredient_quality_map.json",
            entry_id="vitamin_c",
            standard_name="Vitamin C",
            unii="PQ6CK8PD0R",
        ),
        audit.UniiRecord(
            tier=6,
            tier_name="botanical_ingredients",
            source="botanical",
            file="botanical_ingredients.json",
            entry_id="some_botanical",
            standard_name="Some Botanical",
            unii="PQ6CK8PD0R",
        ),
    ]

    assert audit.find_same_tier_groups(records) == []


def test_iqm_same_parent_parent_form_collision_is_info():
    records = [
        audit.UniiRecord(
            tier=4,
            tier_name="ingredient_quality_map",
            source="iqm_parent",
            file="ingredient_quality_map.json",
            entry_id="vitamin_c",
            standard_name="Vitamin C",
            unii="PQ6CK8PD0R",
            parent_id="vitamin_c",
        ),
        audit.UniiRecord(
            tier=4,
            tier_name="ingredient_quality_map",
            source="iqm_form",
            file="ingredient_quality_map.json",
            entry_id="vitamin_c.forms[ascorbic acid]",
            standard_name="ascorbic acid",
            unii="PQ6CK8PD0R",
            parent_id="vitamin_c",
        ),
    ]

    [group] = audit.find_same_tier_groups(records)
    assert group.classification == "iqm_same_parent_parent_form"
    assert group.severity == "info"
    assert group.action == "suppress_runtime_warning_candidate"


def test_iqm_same_unii_different_parents_is_high_review():
    records = [
        audit.UniiRecord(
            tier=4,
            tier_name="ingredient_quality_map",
            source="iqm_parent",
            file="ingredient_quality_map.json",
            entry_id="vanadyl_sulfate",
            standard_name="Vanadyl Sulfate",
            unii="6DU9Y533FA",
            parent_id="vanadyl_sulfate",
        ),
        audit.UniiRecord(
            tier=4,
            tier_name="ingredient_quality_map",
            source="iqm_form",
            file="ingredient_quality_map.json",
            entry_id="vanadium.forms[vanadyl sulfate]",
            standard_name="vanadyl sulfate",
            unii="6DU9Y533FA",
            parent_id="vanadium",
        ),
    ]

    [group] = audit.find_same_tier_groups(records)
    assert group.classification == "iqm_cross_parent_same_unii"
    assert group.severity == "high_review"
    assert group.action == "review_data_model_or_exonerate"


def test_same_tier_exact_duplicate_name_is_review_not_high_review():
    records = [
        audit.UniiRecord(
            tier=6,
            tier_name="botanical_ingredients",
            source="botanical",
            file="botanical_ingredients.json",
            entry_id="botanical_a",
            standard_name="Acai Berry",
            unii="46AM2VJ0AW",
        ),
        audit.UniiRecord(
            tier=6,
            tier_name="botanical_ingredients",
            source="botanical",
            file="botanical_ingredients.json",
            entry_id="botanical_b",
            standard_name="Acai Berry",
            unii="46AM2VJ0AW",
        ),
    ]

    [group] = audit.find_same_tier_groups(records)
    assert group.classification == "same_tier_duplicate_name"
    assert group.severity == "review"


def test_collect_unii_records_includes_harmful_additive_tier():
    records = audit.collect_unii_records(REPO_ROOT)
    harmful_corn_syrup = [
        record for record in records
        if record.source == "harmful" and record.entry_id == "ADD_CORN_SYRUP_SOLIDS"
    ]

    assert harmful_corn_syrup
    assert harmful_corn_syrup[0].tier == 3
    assert harmful_corn_syrup[0].unii == "9G5L16BK6N"
