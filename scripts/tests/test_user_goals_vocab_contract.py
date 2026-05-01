#!/usr/bin/env python3
"""
Contract tests for `data/user_goals_vocab.json` (locked v1.0.0, 2026-04-30).

Single source of truth for user wellness goal labels migrated from
hardcoded `goalLabels` + `goalPriorities` maps in
`lib/core/constants/schema_ids.dart`.

Cross-data contract: the 18 IDs MUST match user_goals_to_clusters.json
(presentation here, cluster mapping there).
"""

import json
import os
import re

import pytest

VOCAB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "user_goals_vocab.json"
)


@pytest.fixture(scope="module")
def vocab():
    with open(VOCAB_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def goals(vocab):
    return vocab["user_goals"]


def test_metadata_block_present(vocab):
    md = vocab["_metadata"]
    assert md["schema_version"] == "1.0.0"
    assert md["total_entries"] == 18
    assert "LOCKED" in md["status"]


def test_exactly_18_goals_locked(goals):
    assert len(goals) == 18, f"locked at 18; got {len(goals)}"


REQUIRED_FIELDS = {"id", "name", "notes", "priority"}
OPTIONAL_FIELDS = {"related_condition_ids", "related_drug_class_ids"}
GOAL_ID_PATTERN = re.compile(r"^GOAL_[A-Z][A-Z0-9_]*$")
ALLOWED_PRIORITIES = {"high", "medium", "low"}


def test_required_fields_present(goals):
    for g in goals:
        keys = set(g.keys())
        missing = REQUIRED_FIELDS - keys
        extra = keys - (REQUIRED_FIELDS | OPTIONAL_FIELDS)
        assert not missing, f"goal {g.get('id')!r} missing: {missing}"
        assert not extra, f"goal {g['id']!r} extra fields: {extra}"


def test_every_id_unique_and_goal_prefix(goals):
    ids = [g["id"] for g in goals]
    assert len(set(ids)) == len(ids), "duplicate goal IDs"
    for gid in ids:
        assert GOAL_ID_PATTERN.match(gid), f"id {gid!r} doesn't match GOAL_<UPPER_SNAKE>"


def test_canonical_18_ids_match_schema_ids_dart(goals):
    expected = {
        "GOAL_SLEEP_QUALITY", "GOAL_REDUCE_STRESS_ANXIETY",
        "GOAL_INCREASE_ENERGY", "GOAL_DIGESTIVE_HEALTH",
        "GOAL_WEIGHT_MANAGEMENT", "GOAL_CARDIOVASCULAR_HEART_HEALTH",
        "GOAL_HEALTHY_AGING_LONGEVITY", "GOAL_BLOOD_SUGAR_SUPPORT",
        "GOAL_IMMUNE_SUPPORT", "GOAL_FOCUS_MENTAL_CLARITY",
        "GOAL_MOOD_EMOTIONAL_WELLNESS", "GOAL_MUSCLE_GROWTH_RECOVERY",
        "GOAL_JOINT_BONE_MOBILITY", "GOAL_SKIN_HAIR_NAILS",
        "GOAL_LIVER_DETOX", "GOAL_PRENATAL_PREGNANCY",
        "GOAL_HORMONAL_BALANCE", "GOAL_EYE_VISION_HEALTH",
    }
    actual = {g["id"] for g in goals}
    assert actual == expected, f"missing={expected-actual} extra={actual-expected}"


def test_priority_in_allowed_enum(goals):
    for g in goals:
        assert g["priority"] in ALLOWED_PRIORITIES, (
            f"{g['id']} priority={g['priority']!r}"
        )


def test_notes_within_char_limit(goals):
    over = [(g["id"], len(g["notes"])) for g in goals if len(g["notes"]) > 200]
    assert not over, f"notes exceed 200 chars: {over}"
    empty = [g["id"] for g in goals if not g["notes"].strip()]
    assert not empty, f"empty notes: {empty}"


def test_related_ids_well_formed(goals):
    for g in goals:
        for f in OPTIONAL_FIELDS:
            if f in g:
                assert isinstance(g[f], list), f"{g['id']}: {f} not list"
                for x in g[f]:
                    assert isinstance(x, str) and x.strip(), f"{g['id']}: bad {f} entry {x!r}"


# ---------------------------------------------------------------------------
# Cross-data: user_goals_to_clusters.json must use the same 18 IDs
# ---------------------------------------------------------------------------


def test_ids_match_user_goals_to_clusters(goals):
    path = os.path.join(
        os.path.dirname(__file__), "..", "data", "user_goals_to_clusters.json"
    )
    with open(path, encoding="utf-8") as f:
        clusters = json.load(f)

    cluster_ids = {m["id"] for m in clusters["user_goal_mappings"] if isinstance(m, dict) and "id" in m}
    vocab_ids = {g["id"] for g in goals}

    only_in_clusters = cluster_ids - vocab_ids
    only_in_vocab = vocab_ids - cluster_ids
    assert not only_in_clusters, (
        f"goal IDs in user_goals_to_clusters.json NOT in vocab: {only_in_clusters}"
    )
    assert not only_in_vocab, (
        f"goal IDs in vocab NOT in user_goals_to_clusters.json: {only_in_vocab}"
    )


# ---------------------------------------------------------------------------
# Cross-data: related_condition_ids / related_drug_class_ids must reference
# real entries in their respective vocabs
# ---------------------------------------------------------------------------


def test_related_condition_ids_in_condition_vocab(goals):
    cond_path = os.path.join(
        os.path.dirname(__file__), "..", "data", "condition_vocab.json"
    )
    with open(cond_path, encoding="utf-8") as f:
        cond_ids = {c["id"] for c in json.load(f)["conditions"]}

    for g in goals:
        for cid in g.get("related_condition_ids", []):
            assert cid in cond_ids, (
                f"goal {g['id']} references condition {cid!r} not in condition_vocab"
            )


def test_related_drug_class_ids_in_drug_class_vocab(goals):
    dc_path = os.path.join(
        os.path.dirname(__file__), "..", "data", "drug_class_vocab.json"
    )
    with open(dc_path, encoding="utf-8") as f:
        dc_ids = {d["id"] for d in json.load(f)["drug_classes"]}

    for g in goals:
        for did in g.get("related_drug_class_ids", []):
            assert did in dc_ids, (
                f"goal {g['id']} references drug_class {did!r} not in drug_class_vocab"
            )
