#!/usr/bin/env python3
"""Full 15,412-record same-input corpus A/B comparator for Phase-3 integration."""

import argparse
import glob
import json
import time
from collections import Counter
from pathlib import Path

def snapshot(products_root: Path, out_path: Path):
    from scoring_v4.scored_artifact import build_scored_artifact

    t0 = time.time()
    count = 0
    crashes = 0
    files = sorted(glob.glob(str(products_root / "output_*_enriched/enriched/*.json")))
    print(f"Scoring {len(files)} enriched brand files from {products_root}...")

    with open(out_path, "w", encoding="utf-8") as sink:
        for f in files:
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
            except Exception as e:
                print(f"Error loading {f}: {e}")
                continue
            items = data if isinstance(data, list) else data.get("products", [data])
            for p in items:
                did = str(p.get("dsld_id") or p.get("id") or "")
                if not did:
                    continue
                try:
                    art = build_scored_artifact(p)
                    pillars = art.get("quality_pillars_v4") or {}
                    ev = pillars.get("evidence") or {}
                    ev_meta = ev.get("metadata") or {}
                    safety = pillars.get("safety_hygiene") or {}
                    rec = {
                        "dsld_id": did,
                        "brand": p.get("brand") or Path(f).parents[1].name.replace("output_", "").replace("_enriched", ""),
                        "name": p.get("name") or p.get("product_name") or "",
                        "module": art.get("v4_module"),
                        "total_score": art.get("quality_score_v4_100"),
                        "tier": art.get("quality_tier"),
                        "assessment_status": art.get("quality_assessment_status"),
                        "score_status": art.get("quality_score_status"),
                        "evidence_score": ev.get("score"),
                        "evidence_state": ev_meta.get("evidence_result_state") or ev.get("evidence_result_state"),
                        "safety_score": safety.get("score"),
                        "safety_verdict": art.get("safety_verdict") or (safety.get("verdict")),
                    }
                    sink.write(json.dumps(rec) + "\n")
                    count += 1
                except Exception as ex:
                    crashes += 1
                    print(f"Crash on {did}: {ex}")
            if count and count % 2000 < 50:
                print(f"  {count} products scored in {time.time() - t0:.1f}s...", flush=True)

    print(f"Finished: {count} products written to {out_path} ({crashes} crashes) in {time.time() - t0:.1f}s.")
    return count, crashes


def compare(base_path: Path, int_path: Path, out_path: Path):
    print(f"Comparing {base_path} against {int_path}...")
    base = {}
    with open(base_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                base[r["dsld_id"]] = r

    integrated = {}
    with open(int_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                integrated[r["dsld_id"]] = r

    only_in_base = sorted(set(base) - set(integrated))
    only_in_int = sorted(set(integrated) - set(base))

    ev_score_movers = []
    total_score_movers = []
    tier_movers = []
    ev_state_movers = []
    status_movers = []
    safety_score_movers = []
    safety_verdict_movers = []
    quarantine_exits = []
    quarantine_entries = []

    state_trans = Counter()
    status_trans = Counter()
    tier_trans = Counter()

    for did, new in integrated.items():
        old = base.get(did)
        if not old:
            continue

        # Score checks
        old_ev_s = float(old.get("evidence_score") or 0.0)
        new_ev_s = float(new.get("evidence_score") or 0.0)
        if abs(new_ev_s - old_ev_s) > 1e-4:
            ev_score_movers.append({"dsld_id": did, "name": new["name"], "old": old_ev_s, "new": new_ev_s})

        old_tot = float(old.get("total_score") or 0.0)
        new_tot = float(new.get("total_score") or 0.0)
        if abs(new_tot - old_tot) > 1e-4:
            total_score_movers.append({"dsld_id": did, "name": new["name"], "old": old_tot, "new": new_tot})

        if old.get("tier") != new.get("tier"):
            tier_movers.append({"dsld_id": did, "name": new["name"], "old": old.get("tier"), "new": new.get("tier")})
            tier_trans[f"{old.get('tier')} -> {new.get('tier')}"] += 1

        # Evidence state checks
        if old.get("evidence_state") != new.get("evidence_state"):
            ev_state_movers.append({
                "dsld_id": did,
                "name": new["name"],
                "module": new["module"],
                "old": old.get("evidence_state"),
                "new": new.get("evidence_state"),
            })
            state_trans[f"{old.get('evidence_state')} -> {new.get('evidence_state')}"] += 1

        # Assessment status checks
        if old.get("assessment_status") != new.get("assessment_status"):
            status_movers.append({
                "dsld_id": did,
                "name": new["name"],
                "old": old.get("assessment_status"),
                "new": new.get("assessment_status"),
            })
            status_trans[f"{old.get('assessment_status')} -> {new.get('assessment_status')}"] += 1

        # Safety checks
        old_saf_s = float(old.get("safety_score") or 0.0)
        new_saf_s = float(new.get("safety_score") or 0.0)
        if abs(new_saf_s - old_saf_s) > 1e-4:
            safety_score_movers.append({"dsld_id": did, "name": new["name"], "old": old_saf_s, "new": new_saf_s})

        if old.get("safety_verdict") != new.get("safety_verdict"):
            safety_verdict_movers.append({"dsld_id": did, "name": new["name"], "old": old.get("safety_verdict"), "new": new.get("safety_verdict")})

        # Quarantine checks (score_status: scored vs not_scored)
        if old.get("score_status") == "not_scored" and new.get("score_status") == "scored":
            quarantine_exits.append(did)
        elif old.get("score_status") == "scored" and new.get("score_status") == "not_scored":
            quarantine_entries.append(did)

    report = {
        "products_base": len(base),
        "products_integrated": len(integrated),
        "only_in_base": only_in_base,
        "only_in_integrated": only_in_int,
        "evidence_score_movers_count": len(ev_score_movers),
        "evidence_score_movers": ev_score_movers,
        "total_score_movers_count": len(total_score_movers),
        "total_score_movers": total_score_movers,
        "tier_movers_count": len(tier_movers),
        "tier_movers": tier_movers,
        "tier_transitions": dict(tier_trans),
        "evidence_state_movers_count": len(ev_state_movers),
        "evidence_state_transitions": dict(state_trans),
        "evidence_state_movers_sample": ev_state_movers[:30],
        "assessment_status_movers_count": len(status_movers),
        "assessment_status_transitions": dict(status_trans),
        "assessment_status_movers_sample": status_movers[:30],
        "safety_score_movers_count": len(safety_score_movers),
        "safety_verdict_movers_count": len(safety_verdict_movers),
        "quarantine_exits_count": len(quarantine_exits),
        "quarantine_entries_count": len(quarantine_entries),
    }

    with open(out_path, "w", encoding="utf-8") as fp:
        json.dump(report, fp, indent=2)

    print("\n" + "="*80)
    print("FULL 15,412-PRODUCT SAME-INPUT CORPUS REPLAY SUMMARY")
    print("="*80)
    print(f"Products Base: {len(base)} | Integrated: {len(integrated)}")
    print(f"Added: {len(only_in_int)} | Dropped: {len(only_in_base)}")
    print(f"Evidence Score Movers: {len(ev_score_movers)}")
    print(f"Total Quality Score Movers: {len(total_score_movers)}")
    print(f"Quality Tier Movers: {len(tier_movers)}")
    print(f"Safety Score Movers: {len(safety_score_movers)}")
    print(f"Safety Verdict Movers: {len(safety_verdict_movers)}")
    print(f"Quarantine Entries: {len(quarantine_entries)} | Exits: {len(quarantine_exits)}")
    print(f"\nEvidence State Movers: {len(ev_state_movers)}")
    for k, v in state_trans.items():
        print(f"  {k}: {v}")
    print(f"\nAssessment Status Movers: {len(status_movers)}")
    for k, v in status_trans.items():
        print(f"  {k}: {v}")

    # Check product 321383
    p321383 = integrated.get("321383")
    if p321383:
        print(f"\nProduct 321383 Final State: {p321383.get('evidence_state')} | Status: {p321383.get('assessment_status')}")

    print(f"\nDetailed report written to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", action="store_true")
    parser.add_argument("--compare", action="store_true")
    parser.add_argument("--products-root", type=Path, default=Path("scripts/products"))
    parser.add_argument("--out", type=Path, default=Path("/tmp/snapshot.jsonl"))
    parser.add_argument("--base", type=Path)
    parser.add_argument("--integrated", type=Path)
    args = parser.parse_args()

    if args.snapshot:
        snapshot(args.products_root, args.out)
    elif args.compare:
        compare(args.base, args.integrated, args.out)
