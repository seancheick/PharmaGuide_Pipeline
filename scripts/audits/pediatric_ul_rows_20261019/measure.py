#!/usr/bin/env python3
"""Classify every difference between main's accepted baseline and the child-UL candidate.

Both captures replay the same 15,414 frozen raw labels (manifest sha256 fd4f3ca7…) through Clean,
Enrich, Score and the detail blob with scripts/audits/quality_redesign/replay.py --full --blob. This
script reads the two projections and the kept stage records; it imports no production module.

    $PG_PYTHON scripts/audits/pediatric_ul_rows_20261019/measure.py \
        --old /Users/seancheick/pg_quality/corpus_20261019_post167/baseline_951a05415_unpinned.jsonl \
        --new /Users/seancheick/pg_quality/pediatric_ul_20261019/candidate_65efca6f8.jsonl \
        --held scripts/audits/dose_hold_census_20261019/census.json
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHILD_WORDS = ("child", "infant", "boys", "girls")
GAP_OLD = "pediatric_reference_gap"


def rows(path):
    with open(path) as fh:
        return {r["id"]: r for r in map(json.loads, fh)}


def record(path, pid):
    with gzip.open(Path(str(path) + ".records") / f"{pid}.json.gz", "rt", encoding="utf-8") as fh:
        return json.load(fh)


def is_child(cleaned):
    return any(any(w in str(g).lower() for w in CHILD_WORDS) for g in cleaned.get("targetGroups") or [])


def dose_score(row):
    dose = (row.get("pillars") or {}).get("dose") or {}
    return dose.get("score")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--held", required=True, help="dose_hold_census census.json (the 475)")
    args = ap.parse_args()
    old, new = rows(args.old), rows(args.new)
    assert set(old) == set(new)
    held_ids = set()
    # census.json lists at most 10 ids per bucket; the full 475 are recomputed from the old records
    # and checked against its count.
    expected_held = json.loads(Path(args.held).read_text())["buckets"]["pediatric_reference_gap"]["count"]
    out = {"products": len(new)}
    changed = sorted(i for i in new if old[i]["hashes"] != new[i]["hashes"])
    out["changed_products"] = len(changed)
    stage_changes = collections.Counter(stage for i in changed for stage in new[i]["hashes"]
                                        if new[i]["hashes"][stage] != old[i]["hashes"][stage])
    out["changed_by_stage"] = dict(stage_changes)

    non_child_changed, child_changed = [], []
    for pid in changed:
        cleaned = record(args.new, pid)["cleaned"]
        (child_changed if is_child(cleaned) else non_child_changed).append(pid)
    out["non_child_changed"] = non_child_changed[:50]
    out["non_child_changed_count"] = len(non_child_changed)

    transitions = collections.Counter(f"{old[i]['status']}->{new[i]['status']}" for i in new
                                      if old[i]["status"] != new[i]["status"])
    out["status_old"] = dict(collections.Counter(r["status"] for r in old.values()))
    out["status_new"] = dict(collections.Counter(r["status"] for r in new.values()))
    out["transitions"] = dict(transitions)

    # The 475 pediatric holds: every product whose old enriched record carried a gap row and was not_scored.
    still_held = collections.Counter()
    restored_totals, restored_dose = [], []
    restored_ceiling = collections.Counter()
    still_held_examples = collections.defaultdict(list)
    exceed_nutrients = collections.Counter()
    exceed_labels = collections.Counter()
    for pid in child_changed + [i for i in new if i not in changed]:
        if old[pid]["status"] != "not_scored":
            continue
        old_rec = record(args.old, pid)
        gaps = [a for a in (old_rec["enriched"].get("rda_ul_data") or {}).get("dose_assessments") or []
                if isinstance(a, dict) and a.get("reason_code") == GAP_OLD]
        if not gaps:
            continue
        held_ids.add(pid)
        new_rec = record(args.new, pid)
        if new[pid]["status"] == "scored":
            restored_totals.append(new[pid]["total"])
            restored_dose.append(dose_score(new[pid]))
            ceiling = ((new_rec["scored"].get("dose_safety_evaluation") or {}).get("dose_ceiling") or {})
            restored_ceiling["ceiling" if ceiling else "no ceiling"] += 1
        else:
            remaining = [a for a in (new_rec["enriched"].get("rda_ul_data") or {}).get("dose_assessments") or []
                         if isinstance(a, dict) and a.get("readiness") == "incomplete"]
            reasons = tuple(sorted({a.get("reason_code") or a.get("ul_assessment_status") for a in remaining}))
            groups = tuple(sorted(new_rec["cleaned"].get("targetGroups") or []))
            key = (new[pid]["status"], reasons or ("no incomplete dose row",))
            still_held[key] += 1
            if len(still_held_examples[str(key)]) < 3:
                still_held_examples[str(key)].append((pid, new[pid]["name"], groups,
                                                      [(a.get("ingredient"), a.get("reason_code")) for a in remaining][:3]))
    for pid in child_changed:
        new_rec = record(args.new, pid)
        for flag in (new_rec["enriched"].get("rda_ul_data") or {}).get("safety_flags") or []:
            population = flag.get("ul_population") or {}
            if "pediatric" in (population.get("members") or []) and flag.get("ul_gate_eligible"):
                exceed_nutrients[flag.get("nutrient")] += 1
                exceed_labels[population.get("label")] += 1
    out["held_475"] = {
        "found": len(held_ids),
        "expected_from_census": expected_held,
        "restored_to_scored": len(restored_totals),
        "restored_total_median": statistics.median(restored_totals) if restored_totals else None,
        "restored_total_range": [min(restored_totals), max(restored_totals)] if restored_totals else None,
        "restored_dose_median": statistics.median([d for d in restored_dose if d is not None]) if restored_dose else None,
        "restored_with_dose_ceiling": dict(restored_ceiling),
        "still_withheld": [[list(k[1]), k[0], n] for k, n in still_held.most_common()],
        "still_withheld_examples": still_held_examples,
    }
    out["child_exceedance_flags"] = {"by_nutrient": exceed_nutrients.most_common(20),
                                     "by_population_label": exceed_labels.most_common(10)}

    # Products that were scored before and still are: did any total move?
    moved = [(i, old[i]["total"], new[i]["total"]) for i in new
             if old[i]["status"] == new[i]["status"] == "scored" and old[i]["total"] != new[i]["total"]]
    out["scored_both_total_moves"] = {"count": len(moved),
                                     "examples": sorted(moved, key=lambda m: m[2] - m[1])[:10]}
    out["route_changes"] = sum(1 for i in new if old[i].get("route") != new[i].get("route"))
    (HERE / "measurement.json").write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(json.dumps(out, indent=1, default=str)[:6000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
