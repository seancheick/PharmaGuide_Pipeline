#!/usr/bin/env python3
"""Compare two packet snapshots group by group.

Usage: diff_packet.py <before.json> <after.json> [--packet pass1|pass2]
                      (--allow-group GROUP ... | --no-moves)
Exits 1 when a product outside the allowed groups moves (score, status, tier or
any pillar). Refuses snapshots scored from different inputs or id lists,
unknown group names, and groups prefixed control_ in --allow-group.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from select_packet import ID_FILES  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("before")
parser.add_argument("after")
parser.add_argument("--packet", choices=sorted(ID_FILES), default="pass1")
mode = parser.add_mutually_exclusive_group(required=True)
mode.add_argument("--allow-group", nargs="+")
mode.add_argument("--no-moves", action="store_true")
args = parser.parse_args()

before, after = (json.load(open(p)) for p in (args.before, args.after))
packet = json.loads(ID_FILES[args.packet].read_text())["products"]
known = {p["group"] for p in packet}
allowed = set(args.allow_group or [])
if allowed - known:
    raise SystemExit(f"REFUSED: unknown groups {sorted(allowed - known)}")
if any(g.startswith("control_") for g in allowed):
    raise SystemExit("REFUSED: control groups can never be allowed to move")
for label, snap in (("before", before), ("after", after)):
    meta = snap.get("_meta") or {}
    if meta.get("packet") != args.packet or meta.get("ids") != [p["id"] for p in packet]:
        raise SystemExit(f"REFUSED: {label} snapshot was not scored from the frozen {args.packet} id list")
if before["_meta"]["input_sha256"] != after["_meta"]["input_sha256"]:
    raise SystemExit("REFUSED: snapshots were scored from different packet inputs")

by_group = defaultdict(list)
unexpected = []
for p in packet:
    b, a = before[p["id"]], after[p["id"]]
    keys = set(b["pillars"]) | set(a["pillars"])
    moves = {k: round((a["pillars"].get(k) or 0) - (b["pillars"].get(k) or 0), 1)
             for k in sorted(keys) if a["pillars"].get(k) != b["pillars"].get(k)}
    changed = any(b[k] != a[k] for k in ("score", "status", "tier", "cap")) or bool(moves)
    delta = None if b["score"] is None or a["score"] is None else round(a["score"] - b["score"], 1)
    by_group[p["group"]].append((p, b, a, delta, moves, changed))
    if changed and p["group"] not in allowed:
        unexpected.append((p["id"], p["group"], f"{b['score']} -> {a['score']} {moves}"))

print(f"before {before['_meta']['checkout_commit'][:8]} -> after {after['_meta']['checkout_commit'][:8]}; input {before['_meta']['input_sha256'][:12]}")
for group, rows in by_group.items():
    deltas = [r[3] for r in rows if r[3] is not None]
    mean = round(sum(deltas) / len(deltas), 2) if deltas else None
    print(f"\n## {group}: {sum(r[5] for r in rows)}/{len(rows)} moved, mean delta {mean}")
    for p, b, a, delta, moves, changed in rows:
        if changed:
            tier = "" if b["tier"] == a["tier"] else f"  tier {b['tier']} -> {a['tier']}"
            status = "" if b["status"] == a["status"] else f"  status {b['status']} -> {a['status']}"
            print(f"   {p['id']:>7} {b['score']} -> {a['score']} ({delta if delta is None else f'{delta:+}'}) {moves}{tier}{status}  {(p['name'] or '')[:50]}")

print(f"\nUNEXPECTED MOVES: {len(unexpected)}")
for u in unexpected:
    print("  ", u)
sys.exit(1 if unexpected else 0)
