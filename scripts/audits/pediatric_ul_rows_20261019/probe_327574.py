#!/usr/bin/env python3
"""Real-label probe: MegaFood Women's Advanced Multivitamin (DSLD 327574) at this source.

Reads the canonical cleaned record from main's accepted replay and prints the adult score
assessment of zinc, the product-level Dose ceiling and the child note.

    $PG_PYTHON scripts/audits/pediatric_ul_rows_20261019/probe_327574.py
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402
from scoring_v4.dose_safety import evaluate_dose_safety  # noqa: E402

RECORDS = Path("/Users/seancheick/pg_quality/corpus_20261019_post167/baseline_951a05415_unpinned.jsonl.records")


def main() -> int:
    for pid in sys.argv[1:] or ["327574", "332879"]:
        with gzip.open(RECORDS / f"{pid}.json.gz", "rt") as handle:
            cleaned = json.load(handle)["cleaned"]
        rda = SupplementEnricherV3()._collect_rda_ul_data(cleaned, min_servings_per_day=1, max_servings_per_day=1)
        zinc = next(row for row in rda["adequacy_results"] if row.get("canonical_id") == "zinc")
        print(json.dumps({
            "id": pid, "name": cleaned.get("fullName"), "targetGroups": cleaned.get("targetGroups"),
            "adult_zinc": {key: zinc.get(key) for key in ("ul", "pct_ul", "over_ul")},
            "adult_population": (zinc.get("ul_population") or {}).get("label"),
            "dose_ceiling": evaluate_dose_safety({"rda_ul_data": rda}).dose_ceiling(),
            "child_notes": [{key: note.get(key) for key in ("nutrient", "status", "ul", "pct_ul", "warning", "reason")}
                            for note in rda["child_ul_screen"]],
        }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
