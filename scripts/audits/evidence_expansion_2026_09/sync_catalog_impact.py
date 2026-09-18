#!/usr/bin/env python3
"""Inject catalog_impact and measured label_dose_profile into wave1_contexts.json (never hand-typed).

Counts drift within weeks and a hand-typed one is wrong the day it is written.
Run after authoring; it only writes the catalog_impact block of each candidate.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
FIELDS = ("slots", "products", "brands", "evidence_zero_products", "evidence_le8_products",
          "evidence_mean", "review_state")


def dose_profiles(slim: Path, canonical_ids: list[str]) -> dict:
    result = subprocess.run([sys.executable, str(OUT / "label_dose_profile.py"), "--slim", str(slim), *canonical_ids],
                            capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slim", type=Path, help="slim corpus; adds measured label_dose_profile")
    args = parser.parse_args()
    queue = {row["canonical_id"]: row for row in json.loads((OUT / "queue.json").read_text())["queue"]}
    path = OUT / "wave1_contexts.json"
    payload = json.loads(path.read_text())
    profiles = dose_profiles(args.slim, [c["canonical_id"] for c in payload["candidates"]]) if args.slim else {}
    for candidate in payload["candidates"]:
        if candidate["canonical_id"] in profiles:
            profile = profiles[candidate["canonical_id"]]
            candidate["label_dose_profile"] = profile
            # Generated from the measured distribution, never hand-typed: a prose dose
            # range written by hand drifts from the corpus within one edit.
            if profile.get("mg_median"):
                candidate["label_exposure_measured"] = (
                    f"Measured label exposure: median {profile['mg_median']:g} mg/day "
                    f"(p25 {profile['mg_p25']:g}, p75 {profile['mg_p75']:g}, "
                    f"min {profile['mg_min']:g}, max {profile['mg_max']:g}) across "
                    f"{profile['dosed_rows']} dosed rows. Source: inventory slim corpus, re-scored 2026-09-17.")
        row = queue[candidate["canonical_id"]]
        candidate["catalog_impact"] = {key: row[key] for key in FIELDS} | {
            "top_forms": [form for form, _ in row["top_forms"][:5]],
            "source": "inventory.json / queue.json, corpus re-scored 2026-09-17"}
    path.write_text(json.dumps(payload, indent=1) + "\n")
    print(json.dumps({c["canonical_id"]: c["catalog_impact"] for c in payload["candidates"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
