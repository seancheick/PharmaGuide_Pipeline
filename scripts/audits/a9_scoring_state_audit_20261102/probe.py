#!/usr/bin/env python3
"""Print the driver fields behind each unfinished state, one real label at a time.

Usage: probe.py <enriched_root> <dsld_id> [<dsld_id> ...]
Reads stored enriched output and scores it with the production scorer. Writes nothing.
"""
import glob
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _driver(scored):
    pillars = scored.get("quality_pillars_v4") or {}
    evidence = pillars.get("evidence") or {}
    release = (scored.get("assessment_readiness") or {}).get("release_assessment") or {}
    gate = scored.get("_v4_safety_gate") or {}
    return {
        "route": scored.get("_v4_module"),
        "quality_score_status": scored.get("quality_score_status"),
        "quality_assessment_status": scored.get("quality_assessment_status"),
        "product_safety_status": scored.get("product_safety_status"),
        "quality_score_v4_100": scored.get("quality_score_v4_100"),
        "quality_tier": scored.get("quality_tier"),
        "score_unavailable_reason": scored.get("score_unavailable_reason"),
        "verdict": scored.get("verdict"),
        "pillar_scores": {name: p.get("score") for name, p in pillars.items()},
        "evidence_display_state": evidence.get("display_state"),
        "release_blockers": release.get("blockers"),
        "mapped_coverage": scored.get("mapped_coverage"),
        "ingredient_assessment_errors": gate.get("ingredient_assessment_errors"),
    }


def main():
    from scoring_v4.scored_artifact import build_scored_artifact

    logging.disable(logging.WARNING)
    root, wanted = sys.argv[1], set(sys.argv[2:])
    for path in sorted(glob.glob(f"{root}/output_*_enriched/enriched/enriched_*.json")):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        for product in data if isinstance(data, list) else data.get("products", []):
            dsld_id = str(product.get("dsld_id"))
            if dsld_id in wanted:
                wanted.discard(dsld_id)
                print(json.dumps({"dsld_id": dsld_id, "name": product.get("product_name"),
                                  **_driver(build_scored_artifact(product))}), flush=True)
        if not wanted:
            return
    if wanted:
        print("not found:", sorted(wanted))


if __name__ == "__main__":
    main()
