#!/usr/bin/env python3
"""Score a calibration packet with the scoring code of a given checkout.

Usage: score_packet.py <checkout_root> <out.json> [--packet pass1|pass2]
The packet records always come from the main checkout's gitignored
scripts/products/_rubric_packet folder. The snapshot records the input hash and
ids so diff_packet.py can refuse to compare snapshots of different inputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from select_packet import ID_FILES, products_path  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("checkout")
parser.add_argument("out")
parser.add_argument("--packet", choices=sorted(ID_FILES), default="pass1")
args = parser.parse_args()

root = Path(args.checkout).resolve()
raw = products_path(args.packet).read_bytes()
products = json.loads(raw)
ids = [str(p.get("dsld_id") or p.get("id")) for p in products]
frozen = [p["id"] for p in json.loads(ID_FILES[args.packet].read_text())["products"]]
if ids != frozen:
    raise SystemExit("REFUSED: extracted records do not match the frozen id list; re-run select_packet.py")

sys.path.insert(0, str(root / "scripts"))
os.chdir(root / "scripts")
from score_supplements_v4 import score_product_v4  # noqa: E402

snap = {"_meta": {
    "packet": args.packet,
    "input_sha256": hashlib.sha256(raw).hexdigest(),
    "ids": ids,
    "checkout_commit": subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
}}
for pid, product in zip(ids, products):
    result = score_product_v4(product)
    pillars = result.get("quality_pillars_v4") or {}
    snap[pid] = {
        "status": result.get("quality_score_status"),
        "score": result.get("quality_score_v4_100"),
        "tier": result.get("quality_tier"),
        "cap": (result.get("quality_score_cap_v4") or {}).get("id"),
        "pillars": {k: v.get("score") for k, v in pillars.items() if isinstance(v, dict)},
    }
Path(args.out).write_text(json.dumps(snap, indent=1, sort_keys=True))
print(len(ids), "products scored with", root, "commit", snap["_meta"]["checkout_commit"][:8])
