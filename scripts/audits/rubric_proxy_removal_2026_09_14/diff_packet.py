#!/usr/bin/env python3
"""Compare two packet snapshots group by group.

Usage: diff_packet.py <before.json> <after.json> [--allow-group GROUP ...]
Exits 1 when a product outside the allowed groups moves, so an unintended
side effect cannot pass silently. Controls are never allowed.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
before, after = (json.load(open(p)) for p in sys.argv[1:3])
allowed = set(sys.argv[sys.argv.index("--allow-group") + 1:]) if "--allow-group" in sys.argv else set()
packet = json.load(open(HERE / "packet_ids.json"))["products"]

by_group = defaultdict(list)
unexpected = []
for p in packet:
    b, a = before.get(p["id"]), after.get(p["id"])
    if b is None or a is None:
        unexpected.append((p["id"], p["group"], "missing in a snapshot"))
        continue
    delta = None if b["score"] is None or a["score"] is None else round(a["score"] - b["score"], 1)
    pillar_moves = {k: round((a["pillars"].get(k) or 0) - (v or 0), 1)
                    for k, v in b["pillars"].items() if (a["pillars"].get(k) or 0) != (v or 0)}
    changed = b["score"] != a["score"] or b["status"] != a["status"] or bool(pillar_moves)
    by_group[p["group"]].append((p, b, a, delta, pillar_moves, changed))
    if changed and p["group"] not in allowed:
        unexpected.append((p["id"], p["group"], f"{b['score']} -> {a['score']} {pillar_moves}"))

for group, rows in by_group.items():
    moved = [r for r in rows if r[5]]
    deltas = [r[3] for r in rows if r[3] is not None]
    mean = round(sum(deltas) / len(deltas), 2) if deltas else None
    print(f"\n## {group}: {len(moved)}/{len(rows)} moved, mean delta {mean}")
    for p, b, a, delta, moves, changed in rows:
        if changed:
            tier = "" if b["tier"] == a["tier"] else f"  tier {b['tier']} -> {a['tier']}"
            print(f"   {p['id']:>7} {b['score']} -> {a['score']} ({delta:+}) {moves}{tier}  {p['name'][:50]}")

print(f"\nUNEXPECTED MOVES: {len(unexpected)}")
for u in unexpected:
    print("  ", u)
sys.exit(1 if unexpected else 0)
