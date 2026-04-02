#!/usr/bin/env python3
"""Goal-to-cluster mapping contract tests (schema v5.2.0)."""

import json
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent.parent / "data"

VALID_GOAL_PRIORITIES = {"high", "medium", "low"}
VALID_GOAL_CATEGORIES = {
    "mental", "metabolic", "cardiovascular", "fitness",
    "hormonal", "immune", "longevity", "aesthetic", "sensory", "reproductive",
}


def _load_goals():
    return json.loads((DATA_DIR / "user_goals_to_clusters.json").read_text())


def _load_cluster_ids():
    clusters = json.loads((DATA_DIR / "synergy_cluster.json").read_text())
    return {c["id"] for c in clusters["synergy_clusters"]}


def test_goal_mapping_has_required_top_level_structure():
    data = _load_goals()
    assert "_metadata" in data
    assert "user_goal_mappings" in data
    assert isinstance(data["user_goal_mappings"], list)
    assert len(data["user_goal_mappings"]) > 0
    assert data["_metadata"]["schema_version"] == "5.2.0"


def test_goal_mapping_total_entries_matches_metadata():
    data = _load_goals()
    declared = data["_metadata"]["total_entries"]
    actual = len(data["user_goal_mappings"])
    assert declared == actual, f"_metadata.total_entries={declared} but found {actual} entries"


def test_each_goal_has_required_fields():
    goals = _load_goals()["user_goal_mappings"]
    required = [
        "id", "user_facing_goal", "goal_category", "goal_priority",
        "cluster_weights", "core_clusters", "anti_clusters",
        "cluster_limits", "confidence_threshold",
        "conflicting_goals", "synergy_goals",
    ]
    for goal in goals:
        for field in required:
            assert field in goal, f"{goal.get('id', '?')} missing field: {field}"


def test_goal_ids_are_unique():
    goals = _load_goals()["user_goal_mappings"]
    ids = [g["id"] for g in goals]
    assert len(ids) == len(set(ids)), f"Duplicate goal IDs: {[i for i in ids if ids.count(i) > 1]}"


def test_goal_priority_values_are_valid():
    goals = _load_goals()["user_goal_mappings"]
    for goal in goals:
        assert goal["goal_priority"] in VALID_GOAL_PRIORITIES, (
            f"{goal['id']}: invalid goal_priority={goal['goal_priority']!r}"
        )


def test_goal_category_values_are_valid():
    goals = _load_goals()["user_goal_mappings"]
    for goal in goals:
        assert goal["goal_category"] in VALID_GOAL_CATEGORIES, (
            f"{goal['id']}: invalid goal_category={goal['goal_category']!r}"
        )


def test_cluster_weights_are_valid_floats_in_range():
    goals = _load_goals()["user_goal_mappings"]
    for goal in goals:
        cw = goal["cluster_weights"]
        assert isinstance(cw, dict) and cw, f"{goal['id']}: cluster_weights must be non-empty dict"
        for cid, weight in cw.items():
            assert isinstance(weight, (int, float)), (
                f"{goal['id']}.cluster_weights.{cid}: weight must be numeric, got {type(weight).__name__}"
            )
            assert 0.0 <= float(weight) <= 1.0, (
                f"{goal['id']}.cluster_weights.{cid}: weight={weight} out of range [0.0, 1.0]"
            )


def test_all_cluster_weight_keys_are_valid_cluster_ids():
    goals = _load_goals()["user_goal_mappings"]
    valid_ids = _load_cluster_ids()
    for goal in goals:
        for cid in goal.get("cluster_weights", {}):
            assert cid in valid_ids, (
                f"{goal['id']}.cluster_weights has unknown cluster id: {cid!r}"
            )


def test_core_clusters_are_non_empty_and_in_cluster_weights():
    goals = _load_goals()["user_goal_mappings"]
    valid_ids = _load_cluster_ids()
    for goal in goals:
        core = goal["core_clusters"]
        assert isinstance(core, list) and core, f"{goal['id']}: core_clusters must be non-empty list"
        cw_keys = set(goal.get("cluster_weights", {}))
        for cid in core:
            assert cid in valid_ids, f"{goal['id']}: core_clusters has unknown cluster id: {cid!r}"
            assert cid in cw_keys, (
                f"{goal['id']}: core_cluster {cid!r} must appear in cluster_weights"
            )


def test_anti_clusters_are_valid_cluster_ids():
    goals = _load_goals()["user_goal_mappings"]
    valid_ids = _load_cluster_ids()
    for goal in goals:
        for cid in goal.get("anti_clusters", []):
            assert cid in valid_ids, (
                f"{goal['id']}.anti_clusters has unknown cluster id: {cid!r}"
            )


def test_cluster_limits_keys_are_valid_cluster_ids_with_positive_int_values():
    goals = _load_goals()["user_goal_mappings"]
    valid_ids = _load_cluster_ids()
    for goal in goals:
        for cid, limit in goal.get("cluster_limits", {}).items():
            assert cid in valid_ids, (
                f"{goal['id']}.cluster_limits has unknown cluster id: {cid!r}"
            )
            assert isinstance(limit, int) and limit >= 1, (
                f"{goal['id']}.cluster_limits.{cid}: limit must be positive int, got {limit!r}"
            )


def test_confidence_threshold_is_float_in_range():
    goals = _load_goals()["user_goal_mappings"]
    for goal in goals:
        ct = goal["confidence_threshold"]
        assert isinstance(ct, (int, float)), (
            f"{goal['id']}: confidence_threshold must be numeric, got {type(ct).__name__}"
        )
        assert 0.0 < float(ct) <= 1.0, (
            f"{goal['id']}: confidence_threshold={ct} out of range (0.0, 1.0]"
        )


def test_conflicting_and_synergy_goals_reference_valid_goal_ids():
    data = _load_goals()
    goals = data["user_goal_mappings"]
    all_ids = {g["id"] for g in goals}
    for goal in goals:
        for gid in goal.get("conflicting_goals", []):
            assert gid in all_ids, f"{goal['id']}.conflicting_goals references unknown goal: {gid!r}"
        for gid in goal.get("synergy_goals", []):
            assert gid in all_ids, f"{goal['id']}.synergy_goals references unknown goal: {gid!r}"


def test_conflicting_goals_are_bidirectional():
    goals = _load_goals()["user_goal_mappings"]
    conflict_map = {g["id"]: set(g.get("conflicting_goals", [])) for g in goals}
    for gid, conflicts in conflict_map.items():
        for other in conflicts:
            assert gid in conflict_map.get(other, set()), (
                f"{gid} lists {other} as conflicting, but {other} does not list {gid} back"
            )


def test_no_duplicate_cluster_ids_within_goal():
    """A cluster ID should not appear in both core_clusters and anti_clusters."""
    goals = _load_goals()["user_goal_mappings"]
    for goal in goals:
        core = set(goal.get("core_clusters", []))
        anti = set(goal.get("anti_clusters", []))
        overlap = core & anti
        assert not overlap, (
            f"{goal['id']}: cluster(s) {overlap} appear in both core_clusters and anti_clusters"
        )
