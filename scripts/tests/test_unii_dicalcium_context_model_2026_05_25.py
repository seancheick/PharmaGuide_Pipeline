#!/usr/bin/env python3
"""Regression coverage for active-vs-inactive Dicalcium Phosphate UNII use.

P0 UNII audit 2026-05-25: exact UNII L11K75P92J is dicalcium phosphate.
That identity legitimately appears as an active calcium/phosphorus source and
as an inactive filler. Runtime must keep those contexts distinct instead of
letting the inactive filler inherit an IQM-tier payload through normalized
name lookup.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR / "api_audit"))

from enhanced_normalizer import EnhancedDSLDNormalizer  # noqa: E402
from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402
import audit_unii_same_tier_conflicts as unii_audit  # noqa: E402


IQM_PATH = REPO_ROOT / "scripts/data/ingredient_quality_map.json"
OTHER_PATH = REPO_ROOT / "scripts/data/other_ingredients.json"


def _iqm() -> dict:
    return json.loads(IQM_PATH.read_text())


def _other_ingredients() -> list[dict]:
    return json.loads(OTHER_PATH.read_text())["other_ingredients"]


def _normalizer() -> EnhancedDSLDNormalizer:
    logging.getLogger("enhanced_normalizer").setLevel(logging.ERROR)
    return EnhancedDSLDNormalizer()


def _filler_entry() -> dict:
    for entry in _other_ingredients():
        if entry.get("id") == "PII_DICALCIUM_PHOSPHATE":
            return entry
    raise AssertionError("PII_DICALCIUM_PHOSPHATE missing")


def test_dicalcium_unii_active_ownership_is_calcium_form_not_standalone_parent():
    iqm = _iqm()

    assert iqm["calcium"]["external_ids"]["unii"] == "SY7Q814VUP"
    assert iqm["calcium"]["forms"]["dicalcium phosphate"]["external_ids"]["unii"] == "L11K75P92J"

    standalone = iqm["dicalcium_phosphate"]
    assert (standalone.get("external_ids") or {}).get("unii") is None
    assert "L11K75P92J" in standalone["unii_note"]


def test_inactive_dicalcium_filler_keeps_exact_unii_for_nonscorable_context():
    filler = _filler_entry()

    assert filler["external_ids"]["unii"] == "L11K75P92J"
    assert filler["category"] == "filler"

    enricher = SupplementEnricherV3()
    recognition = enricher._nonscorable_unii_index["L11K75P92J"]
    assert recognition["matched_entry_id"] == "PII_DICALCIUM_PHOSPHATE"
    assert recognition["recognition_source"] == "other_ingredients"


def test_global_unii_lookup_prefers_active_calcium_for_active_rows():
    normalizer = _normalizer()
    payload = normalizer._unii_to_payload_lookup["L11K75P92J"]

    assert payload["type"] == "ingredient"
    assert payload["standard_name"] == "Calcium"
    assert payload["priority"] == 4


def test_other_ingredient_unii_records_keep_other_tier_in_same_tier_scanner():
    records = unii_audit.collect_unii_records(REPO_ROOT)
    filler_records = [
        record for record in records
        if record.unii == "L11K75P92J" and record.entry_id == "PII_DICALCIUM_PHOSPHATE"
    ]

    assert len(filler_records) == 1
    assert filler_records[0].tier == 9
    assert filler_records[0].tier_name == "other_ingredients"


def test_dicalcium_phosphate_unii_no_longer_has_same_tier_conflict():
    groups = unii_audit.find_same_tier_groups(unii_audit.collect_unii_records(REPO_ROOT))

    assert not [group for group in groups if group.unii == "L11K75P92J"]
