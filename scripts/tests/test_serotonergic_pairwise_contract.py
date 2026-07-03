#!/usr/bin/env python3
"""Regression guards for serotonin-risk pairwise interactions.

These cover stack/Quick Check behavior that cannot be represented as a
profile-only drug-class warning: serotonergic supplement pairs must live in the
curated interaction database with canonical supplement identities.
"""

import json
from pathlib import Path

CURATED_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "curated_interactions"
    / "curated_interactions_v1.json"
)


def _rows():
    return json.loads(CURATED_PATH.read_text())["interactions"]


def test_5_htp_same_pair_is_curated_as_supplement_supplement_interaction():
    matches = [
        row for row in _rows()
        if {
            row.get("agent1_canonical_id"),
            row.get("agent2_canonical_id"),
        } == {"5_htp", "same"}
    ]
    assert len(matches) == 1
    row = matches[0]
    assert row["type"] == "Sup-Sup"
    assert row["severity"] == "Major"
    assert row["direction"] == "harmful"
    assert row["materiality"] == "presence"
    assert "serotonin" in row["mechanism"].lower()
    assert "5-htp" in row["management"].lower()
    assert "same" in row["management"].lower()
    assert row["source_urls"]


def test_curated_interactions_total_entries_matches_interactions_length():
    payload = json.loads(CURATED_PATH.read_text())
    assert payload["_metadata"]["total_entries"] == len(payload["interactions"])
