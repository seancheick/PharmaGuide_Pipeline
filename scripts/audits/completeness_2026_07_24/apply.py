#!/usr/bin/env python3
"""Apply the 2026-07-24 drug-class completeness gaps (Codex point 6).

Idempotent: appends each live-verified (rxcui, name) to its class's parallel
arrays only if absent, then recomputes _metadata.total_members. Six drugs / seven
insertions; every rxcui was live-verified Active + correct entity on 2026-07-24.
"""
import json
from pathlib import Path

PATH = Path(__file__).resolve().parents[2] / "data" / "drug_classes.json"

# (class_id, rxcui, member_name)
ADDITIONS = [
    ("class:proton_pump_inhibitors", "816346", "dexlansoprazole"),
    ("class:acid_suppressants", "816346", "dexlansoprazole"),
    ("class:fluoroquinolones", "1927663", "delafloxacin"),
    ("class:fluoroquinolones", "138099", "gemifloxacin"),
    ("class:antiplatelet_agents", "3521", "dipyridamole"),
    ("class:insulins", "1605101", "insulin isophane"),
    ("class:hiv_protease_inhibitors", "195088", "lopinavir"),
]


def main() -> int:
    doc = json.loads(PATH.read_text())
    classes = doc["classes"]
    added = 0
    touched = set()
    for cid, rx, name in ADDITIONS:
        c = classes[cid]
        touched.add(cid)
        if rx in c["member_rxcuis"]:
            print(f"  skip (present): {cid} {rx} {name}")
            continue
        c["member_rxcuis"].append(rx)
        c["member_names"].append(name)
        added += 1
        print(f"  +{cid}: {name} ({rx})")
    # Members must stay sorted by (name, rxcui) for byte-identical builds.
    for cid in touched:
        c = classes[cid]
        pairs = sorted(zip(c["member_names"], c["member_rxcuis"]))
        c["member_names"] = [n for n, _ in pairs]
        c["member_rxcuis"] = [r for _, r in pairs]
    total = sum(len(c["member_rxcuis"]) for c in classes.values())
    doc["_metadata"]["total_members"] = total
    doc["_metadata"]["last_updated"] = "2026-07-24"
    PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
    print(f"\nadded {added} insertion(s); total_members now {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
