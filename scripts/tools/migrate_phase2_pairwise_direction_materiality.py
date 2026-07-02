#!/usr/bin/env python3
"""Phase 2 (smart-flagging rework) — author `direction` + `materiality` on every
pairwise interaction in the curated_interactions/ files.

Files (all keyed "interactions"):
  curated_interactions_v1.json (110)  med_med_pairs_v1.json (29)
  batch_critical_2026_05.json  (10)                          = 149 pairs

direction  harmful | beneficial | neutral | unknown
    This is a RISK-interaction DB, so the default is `harmful`. `neutral` for
    the "compatible / standard co-therapy" rows the authors tagged
    interaction_effect_type == "Neutral" (CoQ10+statin, fish-oil+SSRI,
    vitD+AED, calcium/vitD+corticosteroid, K2+vitD, melatonin+beta-blocker).
    No `beneficial` rows: genuine synergies live in synergy_cluster.json, not
    here. ONE override: DSI_IMMUNOSUP_PROBIOTICS is tagged effect Neutral but
    its mechanism is bacteremia/sepsis risk in the immunocompromised — that is
    harmful, and must not be demoted to neutral.

materiality  presence | dose_dependent
    Authored FRESH per-pair, NOT mapped from `applies_to` (which is a scope
    descriptor: `applies_to:"dose_dependent"` includes warfarin+vitamin K
    (DSI_WAR_VITK, Major) — a canonical never-suppress interaction). Rule:
      - severity in {Major, Contraindicated}                  -> presence
        (never dose-suppress a serious interaction — warfarin+vitK, MAOI/
        serotonergic, chelation-treatment-failure, hyperkalemia, etc.)
      - else, a SUPPLEMENT-dose pair (Med-Sup/Sup-Sup/Sup-Med) whose effect is
        pharmacodynamically Additive                          -> dose_dependent
        (the floorable class: additive bleeding/sedation/BP/glucose — this is
        where DSI_FISHOIL_VITE lands; the floor VALUE is Phase-3 work)
      - else (Inhibitor/Enhancer PK & absorption, or a Med-Med/Med-Food pair
        with no supplement dose to floor)                     -> presence

Idempotent: rows already carrying `direction` are skipped. Serialization
(ensure_ascii) is auto-detected per file by a byte round-trip so the diff stays
minimal.

Usage:
    python3 scripts/tools/migrate_phase2_pairwise_direction_materiality.py          # dry-run
    python3 scripts/tools/migrate_phase2_pairwise_direction_materiality.py --apply
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "data" / "curated_interactions"
FILES = ["curated_interactions_v1.json", "med_med_pairs_v1.json", "batch_critical_2026_05.json"]
NEW_DATE = "2026-07-02"

SUPP_TYPES = {"Med-Sup", "Sup-Sup", "Sup-Med"}
# effect Neutral but the real direction is harmful (infection risk, not a benign combo)
DIRECTION_OVERRIDE = {"DSI_IMMUNOSUP_PROBIOTICS": "harmful"}


def classify(e: dict) -> tuple[str, str]:
    eid = e.get("id")
    effect = e.get("interaction_effect_type")
    sev = e.get("severity")
    typ = e.get("type")

    direction = DIRECTION_OVERRIDE.get(eid) or ("neutral" if effect == "Neutral" else "harmful")

    if sev in ("Major", "Contraindicated"):
        materiality = "presence"
    elif typ in SUPP_TYPES and effect == "Additive":
        materiality = "dose_dependent"
    else:
        materiality = "presence"
    return direction, materiality


def _serialize(doc: dict, ensure_ascii: bool) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=ensure_ascii) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    grand_dir, grand_mat = Counter(), Counter()
    checks = {}
    for fname in FILES:
        path = BASE / fname
        orig = path.read_text()
        doc = json.loads(orig)
        # detect the serialization that reproduces the file byte-for-byte
        ea = next((flag for flag in (False, True) if _serialize(doc, flag) == orig), None)
        if ea is None:
            raise SystemExit(f"{fname}: no clean round-trip; refusing to reformat")

        arr = doc["interactions"]
        tagged = 0
        for e in arr:
            if e.get("direction"):
                continue
            d, m = classify(e)
            e["direction"] = d
            e["materiality"] = m
            grand_dir[d] += 1
            grand_mat[m] += 1
            tagged += 1
            if e.get("id") in ("DSI_WAR_VITK", "DSI_FISHOIL_VITE",
                               "DSI_IMMUNOSUP_PROBIOTICS", "DSI_STATINS_COQ10"):
                checks[e["id"]] = (d, m, e.get("severity"), e.get("interaction_effect_type"),
                                   e.get("applies_to"))

        print(f"{fname}: tagged {tagged}/{len(arr)}")
        if args.apply and tagged:
            md = doc.setdefault("_metadata", {})
            md["last_updated"] = NEW_DATE
            md["schema_version"] = "1.1.0"
            md.setdefault("migration_notes", []).append(
                f"{NEW_DATE}: Phase 2 smart-flagging — authored direction + materiality "
                f"on all {tagged} pairwise interactions. materiality authored fresh "
                f"(NOT from applies_to): Major/Contraindicated + PK/absorption + "
                f"non-supplement pairs = presence (never suppress, incl. warfarin+vitK); "
                f"supplement-dose Additive pairs = dose_dependent (floorable, incl. "
                f"fish-oil+vitamin-E). Advisory-only; score- and (pre-Phase-4) "
                f"behavior-neutral. Applied via "
                f"scripts/tools/migrate_phase2_pairwise_direction_materiality.py."
            )
            path.write_text(_serialize(doc, ea))
            json.loads(path.read_text())  # prove validity

    print(f"\nTOTAL direction: {dict(grand_dir)}")
    print(f"TOTAL materiality: {dict(grand_mat)}")
    print("\nkey rows (id -> direction, materiality, severity, effect, applies_to):")
    for k, v in checks.items():
        print(f"  {k}: {v}")
    if not args.apply:
        print("\n(dry-run — pass --apply to write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
