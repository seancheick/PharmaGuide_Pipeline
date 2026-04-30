"""
Guard against duplicate drug_class_rules within a single rule entry.

The 2026-04-30 W/M/L/C batch renamed `mao_inhibitors` → `maois` (canonical
clinical_risk_taxonomy ID). The rename was applied post-hoc to data, after
the per-key upsert in backfill.py had already committed entries with the
old key. Result: two `maois` entries existed inside RULE_INGREDIENT_ST_JOHNS_WORT
and RULE_IQM_5HTP_SEROTONIN — same drug_class, different alert copy, both
firing for the same user, looking like a duplication bug to Flutter.

Spot-check on the multi-CYP-active stack caught the dupes; this test
locks the invariant so the same shape can't drift in again.
"""
from __future__ import annotations
import json
from pathlib import Path

DATA_PATH = Path(__file__).parent.parent / "data" / "ingredient_interaction_rules.json"


def test_no_duplicate_drug_class_id_within_rule():
    rules = json.loads(DATA_PATH.read_text())["interaction_rules"]
    dupes = []
    for r in rules:
        seen = {}
        for i, dcr in enumerate(r.get("drug_class_rules") or []):
            dcid = dcr.get("drug_class_id")
            if dcid in seen:
                dupes.append((r["id"], dcid, seen[dcid], i))
            else:
                seen[dcid] = i
    assert not dupes, (
        f"Found duplicate drug_class_id within drug_class_rules of "
        f"{len(dupes)} rule(s). Each (rule, drug_class_id) pair must "
        f"appear at most once. Drift typically comes from a rename without "
        f"re-running the upsert backfill.\n"
        + "\n".join(f"  {rid} / {dcid} at indices [{a}, {b}]"
                    for rid, dcid, a, b in dupes[:10])
    )


def test_no_duplicate_condition_id_within_rule():
    """Same invariant for condition_rules — symmetric guard."""
    rules = json.loads(DATA_PATH.read_text())["interaction_rules"]
    dupes = []
    for r in rules:
        seen = {}
        for i, cr in enumerate(r.get("condition_rules") or []):
            cid = cr.get("condition_id")
            if cid in seen:
                dupes.append((r["id"], cid, seen[cid], i))
            else:
                seen[cid] = i
    assert not dupes, (
        f"Found duplicate condition_id within condition_rules of "
        f"{len(dupes)} rule(s).\n"
        + "\n".join(f"  {rid} / {cid} at indices [{a}, {b}]"
                    for rid, cid, a, b in dupes[:10])
    )
