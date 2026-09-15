#!/usr/bin/env python3
"""Score the calibration packet with the scoring code of a given checkout.

Usage: score_packet.py <checkout_root> <out.json>
The packet always comes from the main checkout (scripts/products/_rubric_packet).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

MAIN = Path(__file__).resolve().parents[3]
PACKET = MAIN / "scripts/products/_rubric_packet/packet_products.json"

root, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2])
sys.path.insert(0, str(root / "scripts"))
os.chdir(root / "scripts")
from score_supplements_v4 import score_product_v4  # noqa: E402

snap = {}
for product in json.load(open(PACKET)):
    result = score_product_v4(product)
    pillars = result.get("quality_pillars_v4") or {}
    snap[str(product.get("dsld_id") or product.get("id"))] = {
        "status": result.get("quality_score_status"),
        "score": result.get("quality_score_v4_100"),
        "tier": result.get("quality_tier"),
        "cap": (result.get("quality_score_cap_v4") or {}).get("id"),
        "pillars": {k: v.get("score") for k, v in pillars.items() if isinstance(v, dict)},
    }
out.write_text(json.dumps(snap, indent=1, sort_keys=True))
print(len(snap), "products scored with", root)
