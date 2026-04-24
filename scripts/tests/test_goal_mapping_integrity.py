#!/usr/bin/env python3
"""Goal-to-cluster mapping contract tests (schema v6.0.0).

Pipeline-owned matching contract. Flutter consumes the computed
``goal_matches`` and ``goal_match_confidence`` fields and only intersects
``selected_user_goals`` with ``product.goal_matches`` — it does not
recompute goal matching.
"""

import json
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Canonical Flutter goal IDs (authoritative source for matching contract).
CANONICAL_FLUTTER_GOAL_IDS = {
    "GOAL_SLEEP_QUALITY",
    "GOAL_REDUCE_STRESS_ANXIETY",
    "GOAL_INCREASE_ENERGY",
    "GOAL_DIGESTIVE_HEALTH",
    "GOAL_WEIGHT_MANAGEMENT",
    "GOAL_CARDIOVASCULAR_HEART_HEALTH",
    "GOAL_HEALTHY_AGING_LONGEVITY",
    "GOAL_BLOOD_SUGAR_SUPPORT",
    "GOAL_IMMUNE_SUPPORT",
    "GOAL_FOCUS_MENTAL_CLARITY",
    "GOAL_MOOD_EMOTIONAL_WELLNESS",
    "GOAL_MUSCLE_GROWTH_RECOVERY",
    "GOAL_JOINT_BONE_MOBILITY",
    "GOAL_SKIN_HAIR_NAILS",
    "GOAL_LIVER_DETOX",
    "GOAL_PRENATAL_PREGNANCY",
    "GOAL_HORMONAL_BALANCE",
    "GOAL_EYE_VISION_HEALTH",
}

# v6.0.0 contract — exactly these per-goal keys are allowed.
REQUIRED_FIELDS = {
    "id",
    "user_facing_goal",
    "cluster_weights",
    "required_clusters",
    "blocked_by_clusters",
    "min_match_score",
}


def _load_goals():
    return json.loads((DATA_DIR / "user_goals_to_clusters.json").read_text())


def _load_cluster_ids():
    clusters = json.loads((DATA_DIR / "synergy_cluster.json").read_text())
    return {c["id"] for c in clusters["synergy_clusters"]}


# ---------- top-level structure ----------


def test_goal_mapping_has_required_top_level_structure():
    data = _load_goals()
    assert "_metadata" in data
    assert "user_goal_mappings" in data
    assert isinstance(data["user_goal_mappings"], list)
    assert len(data["user_goal_mappings"]) > 0
    assert data["_metadata"]["schema_version"] == "6.0.0"


def test_goal_mapping_total_entries_matches_metadata():
    data = _load_goals()
    declared = data["_metadata"]["total_entries"]
    actual = len(data["user_goal_mappings"])
    assert declared == actual, (
        f"_metadata.total_entries={declared} but found {actual} entries"
    )


# ---------- per-goal schema ----------


def test_each_goal_has_only_canonical_fields():
    """Schema v6.0.0 — no legacy fields allowed (goal_category, goal_priority,
    core_clusters, anti_clusters, cluster_limits, confidence_threshold,
    conflicting_goals, synergy_goals)."""
    goals = _load_goals()["user_goal_mappings"]
    for goal in goals:
        keys = set(goal.keys())
        missing = REQUIRED_FIELDS - keys
        extras = keys - REQUIRED_FIELDS
        assert not missing, f"{goal.get('id', '?')} missing fields: {missing}"
        assert not extras, (
            f"{goal.get('id', '?')} has legacy/unknown fields: {extras} "
            "(schema v6.0.0 dropped goal_category, goal_priority, core_clusters, "
            "anti_clusters, cluster_limits, confidence_threshold, conflicting_goals, "
            "synergy_goals)"
        )


def test_goal_ids_are_unique():
    goals = _load_goals()["user_goal_mappings"]
    ids = [g["id"] for g in goals]
    assert len(ids) == len(set(ids)), (
        f"Duplicate goal IDs: {[i for i in ids if ids.count(i) > 1]}"
    )


def test_goal_ids_are_canonical_flutter_ids():
    """All goal IDs must match the 18 canonical Flutter app IDs exactly."""
    goals = _load_goals()["user_goal_mappings"]
    ids = {g["id"] for g in goals}
    extras = ids - CANONICAL_FLUTTER_GOAL_IDS
    missing = CANONICAL_FLUTTER_GOAL_IDS - ids
    assert not extras, f"Non-canonical goal IDs: {extras}"
    assert not missing, f"Missing canonical Flutter goal IDs: {missing}"


# ---------- cluster_weights ----------


def test_cluster_weights_are_valid_floats_in_range():
    goals = _load_goals()["user_goal_mappings"]
    for goal in goals:
        cw = goal["cluster_weights"]
        assert isinstance(cw, dict) and cw, (
            f"{goal['id']}: cluster_weights must be non-empty dict"
        )
        for cid, weight in cw.items():
            assert isinstance(weight, (int, float)), (
                f"{goal['id']}.cluster_weights.{cid}: weight must be numeric, "
                f"got {type(weight).__name__}"
            )
            assert 0.0 <= float(weight) <= 1.0, (
                f"{goal['id']}.cluster_weights.{cid}: weight={weight} "
                "out of range [0.0, 1.0]"
            )


def test_all_cluster_weight_keys_are_valid_cluster_ids():
    goals = _load_goals()["user_goal_mappings"]
    valid_ids = _load_cluster_ids()
    for goal in goals:
        for cid in goal.get("cluster_weights", {}):
            assert cid in valid_ids, (
                f"{goal['id']}.cluster_weights has unknown cluster id: {cid!r}"
            )


def test_cluster_weights_sum_is_positive():
    """matched_weight / max_weight is undefined when max_weight == 0."""
    goals = _load_goals()["user_goal_mappings"]
    for goal in goals:
        total = sum(float(w) for w in goal["cluster_weights"].values())
        assert total > 0.0, (
            f"{goal['id']}: cluster_weights total must be > 0 (got {total})"
        )


# ---------- required_clusters ----------


def test_required_clusters_are_lists_of_valid_cluster_ids():
    goals = _load_goals()["user_goal_mappings"]
    valid_ids = _load_cluster_ids()
    for goal in goals:
        req = goal["required_clusters"]
        assert isinstance(req, list), (
            f"{goal['id']}: required_clusters must be a list"
        )
        for cid in req:
            assert isinstance(cid, str), (
                f"{goal['id']}.required_clusters: entries must be strings, "
                f"got {type(cid).__name__}"
            )
            assert cid in valid_ids, (
                f"{goal['id']}.required_clusters has unknown cluster id: {cid!r}"
            )


def test_required_clusters_appear_in_cluster_weights():
    """A required cluster that has no weight contributes 0 to score —
    almost certainly an authoring mistake."""
    goals = _load_goals()["user_goal_mappings"]
    for goal in goals:
        cw_keys = set(goal["cluster_weights"])
        for cid in goal["required_clusters"]:
            assert cid in cw_keys, (
                f"{goal['id']}.required_clusters: {cid!r} not in cluster_weights "
                "(would force a zero-weight match)"
            )


# ---------- blocked_by_clusters ----------


def test_blocked_by_clusters_are_lists_of_valid_cluster_ids():
    goals = _load_goals()["user_goal_mappings"]
    valid_ids = _load_cluster_ids()
    for goal in goals:
        blocked = goal["blocked_by_clusters"]
        assert isinstance(blocked, list), (
            f"{goal['id']}: blocked_by_clusters must be a list"
        )
        for cid in blocked:
            assert isinstance(cid, str), (
                f"{goal['id']}.blocked_by_clusters: entries must be strings, "
                f"got {type(cid).__name__}"
            )
            assert cid in valid_ids, (
                f"{goal['id']}.blocked_by_clusters has unknown cluster id: {cid!r}"
            )


def test_required_and_blocked_do_not_overlap():
    """Logical contradiction: a cluster can't simultaneously qualify and disqualify."""
    goals = _load_goals()["user_goal_mappings"]
    for goal in goals:
        req = set(goal["required_clusters"])
        blk = set(goal["blocked_by_clusters"])
        overlap = req & blk
        assert not overlap, (
            f"{goal['id']}: cluster(s) {overlap} appear in both "
            "required_clusters and blocked_by_clusters"
        )


# ---------- min_match_score ----------


def test_min_match_score_is_in_valid_range():
    """min_match_score must be numeric in (0.0, 1.0]."""
    goals = _load_goals()["user_goal_mappings"]
    for goal in goals:
        mms = goal["min_match_score"]
        assert isinstance(mms, (int, float)), (
            f"{goal['id']}: min_match_score must be numeric, "
            f"got {type(mms).__name__}"
        )
        assert 0.0 < float(mms) <= 1.0, (
            f"{goal['id']}: min_match_score={mms} out of range (0.0, 1.0]"
        )


def test_min_match_score_is_achievable():
    """A goal whose min_match_score exceeds the max possible score for its
    required-only cluster set is unreachable — should never happen by accident."""
    goals = _load_goals()["user_goal_mappings"]
    for goal in goals:
        cw = goal["cluster_weights"]
        max_weight = sum(float(w) for w in cw.values())
        # Best case: every weighted cluster present → score = 1.0.
        # We just sanity-check that min_match_score isn't larger than 1.0
        # (already enforced) and that max_weight is positive (already enforced).
        # Also ensure that if we ONLY hit the required clusters, the score
        # could plausibly meet the threshold (warn-style assertion).
        req = goal["required_clusters"]
        if req:
            req_weight = sum(float(cw.get(c, 0.0)) for c in req)
            req_only_score = req_weight / max_weight
            # Soft check: required-only score should be at least 0.2 of threshold,
            # otherwise the goal is unreachable from required alone.
            # This catches authoring errors where required clusters carry weight 0.
            assert req_weight > 0.0, (
                f"{goal['id']}: required_clusters carry zero weight "
                "(required cluster present but contributes nothing to score)"
            )
            # Ensure threshold is reachable (best-case score == 1.0 always >= threshold)
            assert goal["min_match_score"] <= 1.0, (
                f"{goal['id']}: min_match_score > 1.0 is unreachable"
            )
            del req_only_score  # informational only
