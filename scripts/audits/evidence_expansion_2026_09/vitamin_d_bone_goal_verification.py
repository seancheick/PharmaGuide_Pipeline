#!/usr/bin/env python3
"""Does removing the D3 bone claim cost any product its shipped bone goal? (read-only)

The vitamin-D clinical cleanup was applied, reverted, and is now re-applied. It
was reverted on a measurement error: the belief that removing "Joint & Bone
Health" from INGR_VITAMIN_D3 would strip the bone goal from a large number of
products. That premise says two owners are one owner, and they are not:

    backed_clinical_studies.json  ->  INTERVENTION evidence (what a trial showed)
                                      surfaces on the clinical evidence card
    synergy_cluster.json          ->  NUTRIENT-FUNCTION relationship (physiology)
                                      surfaces as product-facing goal_matches

scripts/tests/test_vitamin_d_bone_goal_ownership.py pins that split structurally.
This script is the empirical half: it scores every vitamin-D-containing product
BOTH ways with the production scorer and the production goal builder, and reports
what actually moved.

Faithful in the same way scope_repair_projection is - and it reuses that module
rather than restating it - because the scorer reads the match copy baked into the
enriched product while applicability is read live from the registry. Repainting
only one of the two would understate or overstate the change.

Expected, and asserted in the summary:
  * shipped goal_matches changes = 0
  * bone claims disappear from the D3 evidence card where they existed
  * no Evidence, total-score or tier movement anywhere

    python3 scripts/audits/evidence_expansion_2026_09/vitamin_d_bone_goal_verification.py \
        --slim <slim.jsonl> --baseline <baseline backed_clinical_studies.json>
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scope_repair_projection import evidence_of, load_registry, repaint_match  # noqa: E402

RECORD = "INGR_VITAMIN_D3"
BONE = "bone"


def bone_claims(blob: dict) -> dict:
    """The bone text the D3 evidence card would show for this product."""
    for match in ((blob.get("evidence_data") or {}).get("clinical_matches") or []):
        if (match.get("id") or match.get("study_id")) != RECORD:
            continue
        return {
            "health_goals_supported": [g for g in match.get("health_goals_supported") or []
                                       if BONE in str(g).lower()],
            "key_endpoints": [k for k in match.get("key_endpoints") or []
                              if BONE in str(k).lower()],
        }
    return {"health_goals_supported": [], "key_endpoints": []}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slim", required=True, type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--out", default="vitamin_d_bone_goal_verification.json")
    args = parser.parse_args()

    baseline_registry = load_registry(args.baseline)
    live_registry = load_registry(ROOT / "scripts/data/backed_clinical_studies.json")
    if baseline_registry.get(RECORD) == live_registry.get(RECORD):
        print(f"{RECORD} is identical in both registries; nothing to verify", file=sys.stderr)
        return 1

    import build_final_db
    import clinical_applicability
    from score_supplements_v4 import score_product_v4

    targets: dict[str, dict] = {}
    for line in args.slim.open():
        product = json.loads(line)
        vitamin_d_row = any(
            str(row.get("canonical_id") or "").replace("_", " ").lower().startswith("vitamin d")
            for row in product.get("rows") or [])
        carries_record = any(m["id"] == RECORD for m in product["accepted_matches"])
        if vitamin_d_row or carries_record:
            targets[product["dsld_id"]] = {
                "brand_dir": product["brand_dir"], "brand": product["brand_name"],
                "name": product["product_name"], "module": product["module"],
                "carries_d3_record": carries_record}
    print(f"vitamin-D-containing products: {len(targets)}", file=sys.stderr)

    by_brand = collections.defaultdict(set)
    for dsld_id, meta in targets.items():
        by_brand[meta["brand_dir"]].add(dsld_id)

    goal_changes, output_changes, card_cleared, card_never_had_bone = [], [], [], []
    scored = 0
    for brand_dir, ids in sorted(by_brand.items()):
        for path in sorted(glob.glob(str(ROOT / f"scripts/products/output_{brand_dir}_enriched/enriched/*.json"))):
            for enriched in json.load(open(path)):
                dsld_id = str(enriched.get("dsld_id"))
                if dsld_id not in ids:
                    continue
                meta = targets[dsld_id]

                before_blob = json.loads(json.dumps(enriched))
                clinical_applicability.reviewed_entries = lambda r=baseline_registry: r
                before = score_product_v4(json.loads(json.dumps(before_blob)))
                before_goals = build_final_db.compute_goal_matches(json.loads(json.dumps(before_blob)))

                after_blob = json.loads(json.dumps(enriched))
                matches = ((after_blob.get("evidence_data") or {}).get("clinical_matches") or [])
                for index, match in enumerate(matches):
                    if (match.get("id") or match.get("study_id")) == RECORD:
                        matches[index] = repaint_match(match, live_registry[RECORD])
                clinical_applicability.reviewed_entries = lambda r=live_registry: r
                after = score_product_v4(json.loads(json.dumps(after_blob)))
                after_goals = build_final_db.compute_goal_matches(json.loads(json.dumps(after_blob)))

                scored += 1
                row = {"dsld_id": dsld_id, "brand": meta["brand"], "product_name": meta["name"],
                       "module": meta["module"]}

                if before_goals != after_goals:
                    goal_changes.append({**row, "before": before_goals, "after": after_goals})

                signature = lambda r: (evidence_of(r), r.get("quality_score_v4_100"), r.get("quality_tier"))
                if signature(before) != signature(after):
                    output_changes.append({**row, "before": signature(before), "after": signature(after)})

                if meta["carries_d3_record"]:
                    bone_before, bone_after = bone_claims(before_blob), bone_claims(after_blob)
                    had = bool(bone_before["health_goals_supported"] or bone_before["key_endpoints"])
                    has = bool(bone_after["health_goals_supported"] or bone_after["key_endpoints"])
                    if had and not has:
                        card_cleared.append(dsld_id)
                    elif not had:
                        card_never_had_bone.append(dsld_id)
                    elif has:
                        output_changes.append({**row, "bone_claim_survived": bone_after})
        print(f"{brand_dir}: scored {scored}", file=sys.stderr, flush=True)

    d3_products = sum(1 for m in targets.values() if m["carries_d3_record"])
    payload = {"_metadata": {
        "question": "Does removing the bone claim from the D3 clinical record take any product's "
                    "shipped bone goal away? The revert assumed it did, on a count that was "
                    "asserted and never measured.",
        "ownership": "goal_matches is owned by the bone_health synergy cluster; the clinical "
                     "registry owns intervention evidence. Two owners, two claims.",
        "vitamin_d_products_scored": scored,
        "products_carrying_the_d3_record": d3_products,
        "shipped_goal_matches_changes": len(goal_changes),
        "evidence_total_or_tier_changes": len(output_changes),
        "d3_cards_with_the_bone_claim_removed": len(card_cleared),
        "d3_cards_that_never_carried_a_bone_claim": len(card_never_had_bone),
        "verdict": ("CLEAN - no shipped goal or score moved; the bone claim was removed from the "
                    "evidence card only"
                    if not goal_changes and not output_changes
                    else "DIRTY - see goal_matches_changes / output_changes"),
    },
        "goal_matches_changes": goal_changes,
        "output_changes": output_changes,
        "sample_cards_cleared": card_cleared[:25]}
    (OUT / args.out).write_text(json.dumps(payload, indent=1))
    print(json.dumps(payload["_metadata"], indent=1))
    return 0 if not goal_changes and not output_changes else 2


if __name__ == "__main__":
    raise SystemExit(main())
