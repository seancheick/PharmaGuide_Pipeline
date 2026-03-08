#!/usr/bin/env python3
"""Goal-to-cluster mapping contract tests."""

import json
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def test_goal_mapping_uses_resolvable_cluster_ids_and_keeps_labels():
    goals = json.loads((DATA_DIR / "user_goals_to_clusters.json").read_text())["user_goal_mappings"]
    clusters = json.loads((DATA_DIR / "synergy_cluster.json").read_text())["synergy_clusters"]

    cluster_ids = {cluster["id"] for cluster in clusters}

    for goal in goals:
        primary_ids = goal.get("primary_cluster_ids")
        secondary_ids = goal.get("secondary_cluster_ids")
        primary_labels = goal.get("primary_clusters")
        secondary_labels = goal.get("secondary_clusters")

        assert isinstance(primary_ids, list) and primary_ids
        assert isinstance(secondary_ids, list)
        assert isinstance(primary_labels, list) and len(primary_labels) == len(primary_ids)
        assert isinstance(secondary_labels, list) and len(secondary_labels) == len(secondary_ids)
        assert set(primary_ids).issubset(cluster_ids)
        assert set(secondary_ids).issubset(cluster_ids)
