#!/usr/bin/env python3
"""Classify baseline → candidate replay outcomes by cause (read-only).

    $PG_PYTHON reports/identity_line_20261019/measure_outcomes.py BASE.jsonl CAND.jsonl FROZEN_RAW OUT_JSON

Per product it compares scores, safety status, interaction rules, the app's ingredient-id union
(blob ingredients + active display rows + IQD ids, as product_canonical_ids.dart reads them),
allergen/banned/harmful hits and every IQD identity change; it also runs the raw-to-final line
checks on the candidate. Every changed product lands in at least one named cause.
"""
from __future__ import annotations

import collections
import gzip
import json
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from audit_raw_to_final import ProductRecord, _check_line_integrity  # noqa: E402


def rows(path):
    lines = (line for line in Path(path).read_text().splitlines() if line.strip())
    return {row["id"]: row for row in map(json.loads, lines)}


def record(path, pid):
    with gzip.open(Path(str(path) + ".records") / f"{pid}.json.gz", "rt", encoding="utf-8") as handle:
        return json.load(handle)


def norm_id(value):
    if value in (None, ""):
        return None
    text = str(value).strip().lower().replace("&", " and ").replace("'", "").replace("’", "")
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", text)).strip("_") or None


def fired_rules(enriched):
    profile = enriched.get("interaction_profile") or {}
    out = set()
    for key in ("condition_summary", "drug_class_summary"):
        for summary in (profile.get(key) or {}).values():
            out.update(summary.get("rule_ids") or [])
    return out


def app_ids(blob):
    out = set()
    for row in blob.get("ingredients") or []:
        out.add(norm_id(row.get("canonical_id")))
    for row in blob.get("display_ingredients") or []:
        section = str(row.get("source_section") or "").lower()
        if section in ("active", "activeingredients") and str(row.get("display_disposition") or "").lower() != "other_ingredient":
            out.add(norm_id(row.get("canonical_id")))
    for row in (blob.get("ingredient_quality_data") or {}).get("ingredients") or []:
        out.add(norm_id(row.get("canonical_id")))
    out.discard(None)
    return out


def carrier_ids(blob, enriched):
    """The three id carriers separately: blob ingredients, active ledger rows, enriched IQD."""
    ledger = {
        norm_id(row.get("canonical_id"))
        for row in blob.get("display_ingredients") or []
        if str(row.get("source_section") or "").lower() in ("active", "activeingredients")
        and str(row.get("display_disposition") or "").lower() != "other_ingredient"
    }
    iqd = enriched.get("ingredient_quality_data") or {}
    return {
        "blob_ingredients": {norm_id(r.get("canonical_id")) for r in blob.get("ingredients") or []} - {None},
        "display_ingredients_active": ledger - {None},
        "iqd": {norm_id(r.get("canonical_id")) for b in ("ingredients", "ingredients_skipped")
                for r in iqd.get(b) or [] if isinstance(r, dict)} - {None},
    }


def iqd_ids(enriched):
    out = {}
    iqd = enriched.get("ingredient_quality_data") or {}
    for bucket in ("ingredients", "ingredients_skipped"):
        for row in iqd.get(bucket) or []:
            if isinstance(row, dict) and row.get("raw_source_path"):
                out[(bucket, row["raw_source_path"])] = row
    return out


def contaminants(enriched):
    data = enriched.get("contaminant_data") or {}
    return json.dumps({k: data.get(k) for k in ("banned_substances", "harmful_additives", "allergens")}, sort_keys=True, default=str)


def main():
    base_path, cand_path, raw_root, out = map(Path, sys.argv[1:5])
    base, cand = rows(base_path), rows(cand_path)
    raw_index = {p.stem: p for p in raw_root.rglob("*.json")}
    causes = collections.Counter()
    identity_pairs = collections.Counter()
    pair_examples = collections.defaultdict(list)
    score_moves, safety_moves, rules_lost, rules_gained, app_lost, app_gained = [], [], [], [], [], []
    contaminant_moves, gate_findings = [], collections.Counter()
    per_id = collections.defaultdict(lambda: collections.Counter())
    unexplained = []
    for pid in sorted(base):
        b, c = base[pid], cand[pid]
        if b.get("hashes") == c.get("hashes"):
            continue
        br, cr = record(base_path, pid), record(cand_path, pid)
        product_causes = set()
        b_iqd, c_iqd = iqd_ids(br["enriched"]), iqd_ids(cr["enriched"])
        for key in sorted(set(b_iqd) | set(c_iqd), key=str):
            bo, co = b_iqd.get(key) or {}, c_iqd.get(key) or {}
            if bo.get("canonical_id") != co.get("canonical_id"):
                pair = (bo.get("canonical_id"), co.get("canonical_id"), co.get("identity_disposition"))
                identity_pairs[pair] += 1
                if len(pair_examples[pair]) < 3:
                    pair_examples[pair].append((pid, key[1], co.get("raw_source_text")))
                product_causes.add("identity_changed")
            elif bo.get("label_display_name") != co.get("label_display_name"):
                product_causes.add("display_name_changed")
        if (b.get("total"), b.get("status")) != (c.get("total"), c.get("status")):
            score_moves.append((pid, b.get("total"), c.get("total"), b.get("status"), c.get("status"),
                                {k: (b.get("pillars") or {}).get(k, {}).get("score") if isinstance((b.get("pillars") or {}).get(k), dict) else None for k in ("formulation", "dose", "evidence")}))
            product_causes.add("score_moved")
        bs = (br.get("scored") or {}).get("product_safety_status") or (br.get("blob") or {}).get("product_safety_status")
        cs = (cr.get("scored") or {}).get("product_safety_status") or (cr.get("blob") or {}).get("product_safety_status")
        if bs != cs:
            safety_moves.append((pid, bs, cs))
            product_causes.add("safety_status_moved")
        bf, cf = fired_rules(br["enriched"]), fired_rules(cr["enriched"])
        if bf - cf:
            rules_lost.append((pid, sorted(bf - cf)))
            product_causes.add("interaction_rule_lost")
        if cf - bf:
            rules_gained.append((pid, sorted(cf - bf)))
            product_causes.add("interaction_rule_gained")
        ba, ca = app_ids(br.get("blob") or {}), app_ids(cr.get("blob") or {})
        if ba - ca:
            app_lost.append((pid, sorted(ba - ca)))
            product_causes.add("app_id_lost")
        if ca - ba:
            app_gained.append((pid, sorted(ca - ba)))
            product_causes.add("app_id_gained")
        bc, cc = carrier_ids(br.get("blob") or {}, br["enriched"]), carrier_ids(cr.get("blob") or {}, cr["enriched"])
        for carrier in bc:
            for gone in bc[carrier] - cc[carrier]:
                per_id[gone][f"{carrier}_lost"] += 1
            for new_id in cc[carrier] - bc[carrier]:
                per_id[new_id][f"{carrier}_gained"] += 1
        if contaminants(br["enriched"]) != contaminants(cr["enriched"]):
            contaminant_moves.append(pid)
            product_causes.add("contaminant_moved")
        if not product_causes:
            unexplained.append(pid)
        causes.update(product_causes)
    # The line gate on every candidate product.
    for pid in sorted(cand):
        cr = record(cand_path, pid)
        if not cr.get("blob") or pid not in raw_index:
            continue
        rec = ProductRecord(pid, None, None, None)
        _check_line_integrity(rec, json.loads(raw_index[pid].read_text()), cr["cleaned"], cr["enriched"], cr["blob"])
        gate_findings.update(f.code for f in rec.findings)
    report = {
        "products": len(base), "changed_products": sum(1 for p in base if base[p].get("hashes") != cand[p].get("hashes")),
        "causes": dict(causes), "unexplained_products": unexplained,
        "candidate_line_gate_findings": dict(gate_findings),
        "identity_pairs": [[list(k), n, pair_examples[k]] for k, n in identity_pairs.most_common()],
        "score_moves": score_moves, "safety_moves": safety_moves,
        "interaction_rules_lost": rules_lost, "interaction_rules_gained": rules_gained,
        "app_ids_lost": app_lost, "app_ids_gained": app_gained, "contaminant_moves": contaminant_moves,
        "per_id_carrier_counts": {k: dict(v) for k, v in sorted(per_id.items())},
    }
    out.write_text(json.dumps(report, indent=1, default=str) + "\n")
    print(json.dumps({k: report[k] for k in ("products", "changed_products", "causes", "candidate_line_gate_findings")}, indent=1))
    print("unexplained:", unexplained[:20], "score moves:", len(score_moves), "safety moves:", len(safety_moves))


if __name__ == "__main__":
    main()
