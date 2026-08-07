"""Read a filled REVIEW_<id>.md back into the frozen CSV contract.

The reviewer never computes a total and never touches slot/order/round -- this
does it. That removes the two failure classes the first returned sheet hit:
a uniform +10 arithmetic error (quality-checks dropped from a hand-sum) and an
invalid reviewer_slot that broke the join to the frozen template.

Everything is validated and nothing is silently accepted: out-of-range values,
non-half-point increments, unknown enum values, unknown or duplicated IDs, and
missing scores are all reported. A file with ANY error emits no CSV.

Usage: python3 parse_review_doc.py --doc REVIEW_KEVIN.md --slotmap .slotmap_KEVIN.json --out DIR
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

FIELDS = {
    "FORMULATION": ("formulation_0_20", 20), "DOSE": ("dose_0_20", 20),
    "EVIDENCE": ("evidence_0_20", 20), "TRANSPARENCY": ("transparency_0_15", 15),
    "VERIFICATION": ("verification_0_15", 15), "QUALITY": ("formula_quality_checks_0_10", 10),
}
SAFETY = {"blocked", "unsafe", "caution", "no_known_concern",
          "no_known_catalog_concern", "not_assessed"}
SAFETY_CANON = {"no_known_concern": "no_known_catalog_concern"}
CONF = {"high", "moderate", "low"}
YN = {"yes", "no"}
DEV = {"none", "saw_engine_score", "conflict_discovered", "source_access_failure", "other"}

OUT_COLS = ["benchmark_id", "reviewer_slot", "reviewer_id", "reviewer_order",
            "review_round", "correction_reason", "formulation_0_20", "dose_0_20",
            "evidence_0_20", "transparency_0_15", "verification_0_15",
            "formula_quality_checks_0_10", "overall_0_100", "product_safety_status",
            "safety_concern_driver", "assessment_confidence", "label_facts_sufficient",
            "source_citations_json", "rationale", "protocol_deviation"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", required=True, type=Path)
    ap.add_argument("--slotmap", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    sm = json.loads(a.slotmap.read_text())
    order, slot, rid = sm["order"], sm["slot"], sm["reviewer_id"]

    text = a.doc.read_text()
    blocks = re.findall(r"```\s*\nID:\s*(PG-[0-9A-Fa-f]+)\s*\n(.*?)```", text, re.S)
    errs, warns, rows, seen = [], [], [], set()

    for bid, body in blocks:
        def get(label):
            # the doc prints "FORMULATION (0-20):", so tolerate anything
            # between the label and its colon.
            m = re.search(rf"^{re.escape(label)}[^:\n]*:\s*(.*)$", body, re.M)
            return (m.group(1).strip() if m else "")

        if bid not in order:
            errs.append(f"{bid}: not in this reviewer's frozen product set")
            continue
        if bid in seen:
            errs.append(f"{bid}: appears more than once")
            continue
        seen.add(bid)

        vals, ok = {}, True
        for lab, (col, hi) in FIELDS.items():
            raw = re.sub(r"\(.*?\)", "", get(lab)).strip()
            if raw == "":
                errs.append(f"{bid}: {lab} is blank"); ok = False; continue
            try:
                v = float(raw)
            except ValueError:
                errs.append(f"{bid}: {lab} = {raw!r} is not a number"); ok = False; continue
            if not 0 <= v <= hi:
                errs.append(f"{bid}: {lab} = {v} outside 0–{hi}"); ok = False
            elif abs(v * 2 - round(v * 2)) > 1e-9:
                errs.append(f"{bid}: {lab} = {v} is not a whole or half point"); ok = False
            vals[col] = v
        if not ok:
            continue

        safety = get("SAFETY").lower().replace(" ", "_")
        if safety not in SAFETY:
            errs.append(f"{bid}: SAFETY = {get('SAFETY')!r} not one of {sorted(SAFETY)}")
            continue
        safety = SAFETY_CANON.get(safety, safety)
        conf, suff = get("CONFIDENCE").lower(), get("LABEL ENOUGH?").lower()
        if conf not in CONF:
            errs.append(f"{bid}: CONFIDENCE = {get('CONFIDENCE')!r}"); continue
        if suff not in YN:
            errs.append(f"{bid}: LABEL ENOUGH? = {get('LABEL ENOUGH?')!r}"); continue
        dev = (get("ODD").lower().replace(" ", "_") or "none")
        if dev not in DEV:
            dev = "other"
            warns.append(f"{bid}: ODD text not a known value — recorded as 'other', review manually")

        driver, srcs = get("DRIVER"), get("SOURCES")
        if safety in ("blocked", "unsafe", "caution") and not driver:
            errs.append(f"{bid}: SAFETY={safety} requires a DRIVER"); continue
        if not srcs:
            warns.append(f"{bid}: no SOURCES recorded")

        total = sum(vals.values())          # <- the arithmetic, done here
        rows.append({**vals, "benchmark_id": bid, "reviewer_slot": slot,
                     "reviewer_id": rid, "reviewer_order": order[bid], "review_round": 1,
                     "correction_reason": "", "overall_0_100": (int(total) if total == int(total) else total),
                     "product_safety_status": safety, "safety_concern_driver": driver,
                     "assessment_confidence": conf, "label_facts_sufficient": suff,
                     "source_citations_json": srcs, "rationale": get("WHY"),
                     "protocol_deviation": dev})

    missing = sorted(set(order) - seen)
    print(f"parsed {len(rows)} of {len(order)} products")
    if missing:
        print(f"\nNOT ANSWERED ({len(missing)}):")
        for m in missing[:15]:
            print(f"   {m}")
        if len(missing) > 15:
            print(f"   ... and {len(missing)-15} more")
    if warns:
        print(f"\nWARNINGS ({len(warns)}):")
        for w in warns[:20]:
            print(f"   {w}")
    if errs:
        print(f"\nERRORS ({len(errs)}) — no CSV written:")
        for e in errs[:30]:
            print(f"   {e}")
        return 1
    if missing:
        print("\nIncomplete — no CSV written. Ask the reviewer for the missing blocks.")
        return 1

    a.out.mkdir(parents=True, exist_ok=True)
    p = a.out / f"answers_{rid}.csv"
    with p.open("w", newline="\n") as fh:
        w = csv.DictWriter(fh, fieldnames=OUT_COLS)
        w.writeheader()
        rows.sort(key=lambda r: int(r["reviewer_order"]))
        w.writerows(rows)
    print(f"\nOK — arithmetic computed for all {len(rows)} rows. Wrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
