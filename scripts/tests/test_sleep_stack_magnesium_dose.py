#!/usr/bin/env python3
"""Clinical lock: sleep_stack magnesium effective dose = 200 mg.

The sleep-effective magnesium dose is ~200-500 mg (Abbasi 2012, PMID 23853635,
used 500 mg; meta-analysis Mah & Pitre 2021, PMID 33865376). The cluster's own
cited insomnia RCT (Rondanelli, PMID 21226679) dosed ~225 mg. The
original 100 mg floor under-counted: it let a sub-effective magnesium-only
product read as fully "Supported" for sleep. 200 mg also harmonizes sleep_stack
with its sibling clusters (stress_resilience and magnesium_nervous_system are
already 200 mg) and with the enricher comment that already named ~200 mg as the
sleep-relevant dose.

This is a clinical lock — a future edit must not silently revert it. With the
underdosed-sole-primary emit in place, a magnesium-only product at 100-199 mg
now surfaces as "partially supported" for sleep, not falsely "Supported."
"""

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402

SYNERGY_PATH = SCRIPTS_DIR / "data" / "synergy_cluster.json"


def test_sleep_stack_magnesium_threshold_is_200():
    data = json.loads(SYNERGY_PATH.read_text())
    sleep = next(
        c for c in data["synergy_clusters"] if c.get("id") == "sleep_stack"
    )
    assert sleep["min_effective_doses"]["magnesium"] == 200


def test_sleep_stack_note_matches_threshold():
    """The human-readable note must not contradict the data (no 'magnesium >= 100')."""
    data = json.loads(SYNERGY_PATH.read_text())
    sleep = next(
        c for c in data["synergy_clusters"] if c.get("id") == "sleep_stack"
    )
    note = sleep.get("note", "")
    assert "magnesium >= 100" not in note
    assert "magnesium >= 200" in note


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


def _magnesium_only(qty_mg):
    return {
        "name": "Test Single Active Product",
        "activeIngredients": [
            {
                "name": "Magnesium Glycinate",
                "standardName": "Magnesium",
                "quantity": qty_mg,
                "unit": "mg",
            }
        ],
    }


def test_magnesium_150_is_underdosed_for_sleep(enricher):
    """150 mg magnesium (>=50% of 200, below it) → sleep_stack present-but-underdosed."""
    clusters = enricher._collect_synergy_data(_magnesium_only(150))
    sleep = next((c for c in clusters if c.get("cluster_id") == "sleep_stack"), None)
    assert sleep is not None
    assert sleep.get("underdosed_single") is True


def test_magnesium_250_is_adequate_for_sleep(enricher):
    """250 mg magnesium (>= 200) → adequate solo sleep match (supported)."""
    clusters = enricher._collect_synergy_data(_magnesium_only(250))
    sleep = next((c for c in clusters if c.get("cluster_id") == "sleep_stack"), None)
    assert sleep is not None
    assert sleep.get("single_ingredient_match") is True
    assert sleep.get("underdosed_single") in (False, None)
