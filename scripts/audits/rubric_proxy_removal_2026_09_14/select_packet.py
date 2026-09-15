#!/usr/bin/env python3
"""Pick a small, stratified calibration packet instead of re-scoring the whole corpus.

Run from the repo root:  python3 scripts/audits/rubric_proxy_removal_2026_09_14/select_packet.py

Groups come from the existing scored breakdowns: each rubric change gets products it
should move, and every category gets controls that must not move. Selection is
deterministic (numeric id order, evenly spaced picks). Writes:
  packet_ids.json                      (committed: ids, groups, names)
  scripts/products/_rubric_packet/packet_products.json   (gitignored: enriched records)
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PRODUCTS = ROOT / "scripts/products"
HERE = Path(__file__).resolve().parent
OUT_IDS = HERE / "packet_ids.json"
OUT_PRODUCTS = PRODUCTS / "_rubric_packet/packet_products.json"


def _pick(rows, n):
    rows = sorted(rows, key=lambda r: int(r["id"]) if r["id"].isdigit() else 0)
    if len(rows) <= n:
        return rows
    step = len(rows) / n
    return [rows[int(i * step)] for i in range(n)]


def main() -> None:
    scored = []
    for f in sorted(glob.glob(str(PRODUCTS / "output_*_scored/scored/*.json"))):
        for r in json.load(open(f)):
            if r.get("_v4_quality_status") != "scored":
                continue
            dims = (r.get("_v4_module_breakdown") or {}).get("dimensions") or {}
            form = dims.get("formulation") or {}
            scored.append({
                "id": str(r["dsld_id"]), "name": r.get("product_name"), "module": r.get("_v4_module"),
                "comp": {**(form.get("components") or {}), **((dims.get("dose") or {}).get("components") or {})},
                "pen": form.get("penalties") or {}, "fmeta": form.get("metadata") or {},
                "cap": (r.get("_v4_quality_score_cap") or {}).get("id"),
            })

    def mod(m):
        return [r for r in scored if r["module"] == m]

    gen = mod("generic")
    marketing = lambda r: any(r["comp"].get(k) for k in ("A5a_organic", "A5d_non_gmo", "A5e_natural_source"))
    probio = mod("probiotic")
    ident = lambda r: (r["fmeta"].get("identified_strain_count") or 0, r["fmeta"].get("total_strain_count") or 0)
    groups = {
        "prenatal_gummy": _pick([r for r in mod("multi_or_prenatal") if r["pen"].get("gummy_formulation_limit")], 12),
        "prenatal_control": _pick([r for r in mod("multi_or_prenatal") if not r["pen"].get("gummy_formulation_limit")], 8),
        "fiber_gummy": _pick([r for r in mod("fiber_digestive") if r["pen"].get("fiber_gummy_delivery_penalty")], 10),
        "fiber_control": _pick([r for r in mod("fiber_digestive") if not r["pen"].get("fiber_gummy_delivery_penalty")
                                and r["comp"].get("fiber_practicality") == 2.0 and not marketing(r)], 6),
        "melatonin_gummy": _pick([r for r in gen if r["pen"].get("B1_sleep_melatonin_gummy")], 8),
        "immune_gummy": _pick([r for r in gen if r["pen"].get("B1_immune_gummy_or_syrup")], 8),
        "omega_ratio_in_range": _pick([r for r in mod("omega") if r["comp"].get("ratio_sanity")], 10),
        "omega_ratio_none": _pick([r for r in mod("omega") if not r["comp"].get("ratio_sanity")], 6),
        "probiotic_single_exact": _pick([r for r in probio if ident(r) == (1, 1)], 5),
        "probiotic_multi_all_exact": _pick([r for r in probio if ident(r)[0] == ident(r)[1] >= 2], 5),
        "probiotic_partial_exact": _pick([r for r in probio if 0 < ident(r)[0] < ident(r)[1]], 5),
        "probiotic_no_exact": _pick([r for r in probio if ident(r)[0] == 0 and ident(r)[1] > 0], 5),
        "probiotic_studied_formula": [r for r in probio if "native_potency_disclosed" in r["comp"]],
        "generic_organic": _pick([r for r in gen if r["comp"].get("A5a_organic")], 4),
        "generic_non_gmo": _pick([r for r in gen if r["comp"].get("A5d_non_gmo")], 3),
        "generic_natural": _pick([r for r in gen if r["comp"].get("A5e_natural_source")
                                  and not r["comp"].get("A5a_organic") and not r["comp"].get("A5d_non_gmo")], 3),
        "generic_capped": [r for r in gen if r["cap"] in ("generic_astaxanthin_single", "generic_coq10_single")],
        "generic_control": _pick([r for r in gen if not marketing(r) and not r["cap"]
                                  and not r["pen"].get("B1_sleep_melatonin_gummy")
                                  and not r["pen"].get("B1_immune_gummy_or_syrup")], 6),
        "sports_control": _pick([r for r in mod("sports") if not marketing(r)], 6),
        "b_complex_control": _pick([r for r in mod("b_complex") if not marketing(r)], 5),
    }
    seen, packet = set(), []
    for group, rows in groups.items():
        for r in rows:
            if r["id"] in seen:
                continue
            seen.add(r["id"])
            packet.append({"id": r["id"], "group": group, "module": r["module"], "name": r["name"]})

    wanted = {p["id"] for p in packet}
    records = {}
    for f in sorted(glob.glob(str(PRODUCTS / "output_*_enriched/enriched/*.json"))):
        for p in json.load(open(f)):
            pid = str(p.get("dsld_id") or p.get("id"))
            if pid in wanted:
                records[pid] = p
    missing = sorted(wanted - set(records))
    packet = [p for p in packet if p["id"] in records]
    OUT_IDS.write_text(json.dumps({"_metadata": {
        "purpose": "Stratified rubric calibration packet; controls must not move.",
        "selected_from": "scripts/products/output_*_scored (2026-09-13 scored breakdowns)",
        "missing_from_enriched": missing}, "products": packet}, indent=2) + "\n")
    OUT_PRODUCTS.parent.mkdir(parents=True, exist_ok=True)
    OUT_PRODUCTS.write_text(json.dumps([records[p["id"]] for p in packet]))
    counts = {}
    for p in packet:
        counts[p["group"]] = counts.get(p["group"], 0) + 1
    print(len(packet), "products;", "missing", len(missing), counts)


if __name__ == "__main__":
    main()
