"""Classify every missed-warning row from missed_warnings.py by why its rule did not fire.

Read-only. For each active display row whose cleaner identity has a profile rule that did not
fire, look up the enricher's row (same raw_source_path) and decide:
  identity_nulled   - the enricher left the row without any interaction subject
  identity_swapped  - the enricher subject (plus family/twin) cannot reach the rule's subject
  *_covered_by_fired_rule - every condition/drug target of the missed rule is already warned at the
                      same or higher severity by a rule that did fire on the product
  subject_reached_* - the rule's subject is reachable and the rule declined:
                      header_not_scanned (a blend header row is never scanned), not_present
                      (measured zero), form_scope, dose_threshold, other
argv: RECORDS_DIR MISSED_JSON|- RULES_JSON OUT_JSON  (- = every product in RECORDS_DIR)
"""
import collections, gzip, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from identity.interaction import interaction_subject_refs, label_row_establishes_presence  # noqa: E402

RECORDS, MISSED, RULES, OUT = Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
rules = json.load(open(RULES))["interaction_rules"]
rule_subjects = collections.defaultdict(set)  # canonical_id -> {(db, id)}
rule_meta = {}
W = {"contraindicated": 5, "avoid": 4, "caution": 3, "monitor": 2, "informational": 1}
rule_targets = collections.defaultdict(dict)  # canonical_id -> {(kind, target): weight}
for r in rules:
    cid0 = (r.get("subject_ref") or {}).get("canonical_id")
    for c in r.get("condition_rules") or []:
        t = rule_targets[cid0]; k = ("condition", c.get("condition_id"))
        t[k] = max(t.get(k, 0), W.get(c.get("severity"), 0))
    for c in r.get("drug_class_rules") or []:
        t = rule_targets[cid0]; k = ("drug", c.get("drug_class_id"))
        t[k] = max(t.get(k, 0), W.get(c.get("severity"), 0))
for r in rules:
    ref = r.get("subject_ref") or {}
    rule_subjects[ref.get("canonical_id")].add((ref.get("db"), ref.get("canonical_id")))
    rule_meta[ref.get("canonical_id")] = {
        "has_dose_thresholds": bool(r.get("dose_thresholds")),
        "form_scope": bool(r.get("form_scope")),
    }


def norm(v):
    raw = str(v or "").strip().lower().replace("&", " and ").replace("'", "").replace("’", "")
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", raw)).strip("_") or None


def subject(e):
    cid = str(e.get("canonical_id") or "").strip()
    if cid:
        return (e.get("canonical_source_db") or "ingredient_quality_map", cid)
    src, rid = e.get("recognition_source"), e.get("matched_entry_id") or e.get("recognized_entry_id")
    return (src, rid) if src and rid else None


if MISSED == "-":  # every product in RECORDS_DIR, every subject with a rule
    pids = sorted(p.name[:-8] for p in RECORDS.glob("*.json.gz"))
    missed = {"missed": rule_subjects}
else:
    missed = json.load(open(MISSED))
    pids = sorted({p for v in missed["products"].values() for p in v})
rows, counts = [], collections.Counter()
for pid in pids:
    s = json.load(gzip.open(RECORDS / f"{pid}.json.gz", "rt"))
    blob, enr = s.get("blob") or {}, s.get("enriched") or {}
    fired = {w.get("source_rule_id") for w in (blob.get("warnings") or []) + (blob.get("warnings_profile_gated") or []) if isinstance(w, dict)}
    product_fired = {}
    for a in (enr.get("interaction_profile") or {}).get("ingredient_alerts") or []:
        for kind, key, field in (("condition", "condition_hits", "condition_id"), ("drug", "drug_class_hits", "drug_class_id")):
            for h in a.get(key) or []:
                k = (kind, h.get(field))
                product_fired[k] = max(product_fired.get(k, 0), W.get(h.get("severity"), 0))
    iqd = enr.get("ingredient_quality_data") or {}
    by_path = {}
    for key in ("ingredients", "ingredients_skipped"):
        for r in iqd.get(key) or []:
            if isinstance(r, dict):
                by_path.setdefault(r.get("raw_source_path"), r)
    for d in blob.get("display_ingredients") or []:
        if not isinstance(d, dict) or str(d.get("source_section") or "").lower() not in ("active", "activeingredients"):
            continue
        if str(d.get("display_disposition") or "").lower() == "other_ingredient":
            continue
        cid = norm(d.get("canonical_id"))
        if cid not in missed["missed"] or cid not in rule_subjects:
            continue
        rule_ids = {r["id"] for r in rules if (r.get("subject_ref") or {}).get("canonical_id") == cid}
        if rule_ids & fired:
            continue
        e = by_path.get(d.get("raw_source_path")) or {}
        subj = subject(e) if e else None
        reach = set(interaction_subject_refs(*subj)) if subj else set()
        if not e:
            cls = "no_enricher_row"
        elif not subj:
            cls = "identity_nulled"
        elif reach & rule_subjects[cid]:
            if e.get("skip_reason") == "blend_header_total_weight_only":
                cls = "subject_reached_header_not_scanned"
            elif not label_row_establishes_presence(e):
                cls = "subject_reached_not_present"
            elif rule_meta[cid]["form_scope"]:
                cls = "subject_reached_form_scope"
            elif rule_meta[cid]["has_dose_thresholds"]:
                cls = "subject_reached_dose_threshold"
            else:
                cls = "subject_reached_other"
        else:
            cls = "identity_swapped"
        if not cls.startswith("subject_reached") and all(product_fired.get(k, 0) >= w for k, w in rule_targets[cid].items()):
            cls += "_covered_by_fired_rule"
        rec = {
            "id": pid, "product": blob.get("product_name"), "path": d.get("raw_source_path"),
            "label": e.get("raw_source_text") or e.get("name"), "display_id": cid,
            "enricher_id": e.get("canonical_id"), "enricher_db": e.get("canonical_source_db"),
            "canonical_id_before": e.get("canonical_id_before"),
            "disposition": e.get("identity_disposition"), "reason": e.get("identity_decision_reason"),
            "role": e.get("role_classification"), "cleaner_row_role": e.get("cleaner_row_role"),
            "qty": e.get("quantity"), "unit": e.get("unit"), "class": cls,
            "rule_has_dose": rule_meta[cid]["has_dose_thresholds"], "rule_form_scope": rule_meta[cid]["form_scope"],
            "rules": sorted(rule_ids),
        }
        rows.append(rec)
        counts[(cls, cid, rec["reason"])] += 1
summary = collections.Counter(r["class"] for r in rows)
print("rows by class:", dict(summary))
print("products by class:", {c: len({r["id"] for r in rows if r["class"] == c}) for c in summary})
for k, n in sorted(counts.items(), key=lambda kv: (kv[0][0], -kv[1])):
    print(f"  {n:4d} {k}")
json.dump(rows, open(OUT, "w"), indent=1, default=str)
