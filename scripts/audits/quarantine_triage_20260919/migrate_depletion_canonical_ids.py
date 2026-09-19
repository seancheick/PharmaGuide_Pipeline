#!/usr/bin/env python3
"""Migrate legacy depleted_nutrient.canonical_id values to IQM canonical keys (Phase 6).

23 of 80 medication-depletion entries carried legacy nutrient ids that do not
resolve in the IQM canonical vocabulary (`vitamin_b12`, `folate`, `coenzyme_q10`,
`vitamin_b6`, `thiamin`, `biotin` instead of `vitamin_b12_cobalamin`,
`vitamin_b9_folate`, `coq10`, `vitamin_b6_pyridoxine`, `vitamin_b1_thiamine`,
`vitamin_b7_biotin`). Each mapping is verified 1:1 against the live IQM before
being applied; the script refuses to run if any target key is missing or any
legacy value has no exactly-one mapping.

Idempotent: a second run finds nothing to change.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
MED = DATA / "medication_depletions.json"
IQM = DATA / "ingredient_quality_map.json"

# legacy -> canonical IQM key (each verified to exist before applying)
MIGRATION = {
    "folate": "vitamin_b9_folate",
    "vitamin_b12": "vitamin_b12_cobalamin",
    "coenzyme_q10": "coq10",
    "vitamin_b6": "vitamin_b6_pyridoxine",
    "thiamin": "vitamin_b1_thiamine",
    "biotin": "vitamin_b7_biotin",
}


def iqm_keys() -> set[str]:
    iqm = json.loads(IQM.read_text())
    return set(iqm["ingredients"].keys()) if "ingredients" in iqm else set(iqm.keys()) - {"_metadata"}


def main() -> int:
    keys = iqm_keys()
    missing_targets = [t for t in MIGRATION.values() if t not in keys]
    if missing_targets:
        print(f"REFUSING: target IQM keys do not exist: {missing_targets}", file=sys.stderr)
        return 1

    raw = MED.read_text()
    data = json.loads(raw)
    deps = data["depletions"]

    legacy_counts: dict[str, int] = {}
    for e in deps:
        cid = (e.get("depleted_nutrient") or {}).get("canonical_id")
        if cid in MIGRATION:
            legacy_counts[cid] = legacy_counts.get(cid, 0) + 1
            e["depleted_nutrient"]["canonical_id"] = MIGRATION[cid]

    total = sum(legacy_counts.values())
    if total == 0:
        print("nothing to migrate (already done)")
        return 0

    # sanity: every legacy id in the file is covered by MIGRATION
    unresolved = [
        (e["id"], (e.get("depleted_nutrient") or {}).get("canonical_id"))
        for e in deps
        if (e.get("depleted_nutrient") or {}).get("canonical_id") not in MIGRATION
        and (e.get("depleted_nutrient") or {}).get("canonical_id") not in keys
    ]
    if unresolved:
        print(f"REFUSING: canonical_ids resolve in neither MIGRATION nor IQM: {unresolved}", file=sys.stderr)
        return 1

    MED.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    # metadata note (append to existing notes if present)
    md = data["_metadata"]
    stamp = "2026-09-19: migrated 23 depleted_nutrient.canonical_id values to IQM canonical keys (vitamin_b12->vitamin_b12_cobalamin, folate->vitamin_b9_folate, coenzyme_q10->coq10, vitamin_b6->vitamin_b6_pyridoxine, thiamin->vitamin_b1_thiamine, biotin->vitamin_b7_biotin); enforced by verify_medication_depletion_identifiers.py."
    md["notes"] = (md.get("notes", "") + " " + stamp).strip()

    MED.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    print(f"migrated {total} entries:")
    for legacy, canon in sorted(MIGRATION.items()):
        n = legacy_counts.get(legacy, 0)
        if n:
            print(f"  {legacy} -> {canon}: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
