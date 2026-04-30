#!/usr/bin/env python3
"""
2E CYP2D6 follow-up — clinician-locked 2026-04-30 email reply.

Two rules approved at the proposed severities, with copy refinements on
the action verbs:

  Bupleurum × CYP2D6 substrates → caution
    Subject: botanical_ingredients.bupleurum_root
    Action verb: "consider discussing this supplement with your prescriber"
    (encouragement-toned, matches caution tier per clinician note).

  St. John's Wort × CYP2D6 substrates → monitor
    Subject: ingredient_quality_map.st_johns_wort (existing)
    Dose threshold: ≥900 mg/day standardized extract.
    Action verb: "your prescriber may want to monitor for changes in drug
    effect" (monitor-tier action, not avoidance).
    Mechanism note: effect is mixed in direction (some induction, some weak
    inhibition reported across studies) — flag for future reviewers.
    Severity gap from C4 (CYP3A4 contraindicated) is intentional; do not
    let future harmonization collapse them.

Pregnancy/lactation:
  - Bupleurum: pregnancy_category=caution (emmenagogue activity in TCM
    literature), lactation_category=no_data.
  - SJW: pre-seed already in place from existing C4 rule (preg=avoid,
    lact=caution); no change.

Idempotent.
"""

from __future__ import annotations
import argparse, json, sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
RULES_PATH = DATA_DIR / "ingredient_interaction_rules.json"


BUPLEURUM_CYP2D6_RULE = {
    "drug_class_id": "cyp2d6_substrates",
    "severity": "caution",
    "evidence_level": "theoretical",
    "mechanism": "Saikosaponins inhibit CYP2D6 in vitro and in animal models. Clinical evidence in humans is limited but consistent in mechanism. Bupleurum often appears in multi-herb TCM formulas (Xiao Yao San, Bupleurum & Dragon Bone) where users may not recognize it on the ingredient label.",
    "action": "If you take a CYP2D6-substrate prescription drug, consider discussing this supplement with your prescriber. Especially relevant for many SSRIs/SNRIs, tricyclics, codeine, tramadol, and tamoxifen.",
    "sources": [
        "https://pubmed.ncbi.nlm.nih.gov/24509137/",
        "https://pubmed.ncbi.nlm.nih.gov/19548302/"
    ],
    "alert_headline": "May affect prescription drug levels",
    "alert_body": "If you take a CYP2D6-substrate prescription drug, consider discussing bupleurum with your prescriber. Bupleurum may slow how some antidepressants and pain medications are processed.",
    "informational_note": "Bupleurum inhibits CYP2D6 in preclinical evidence — relevant to anyone on antidepressants, opioids, or tamoxifen.",
}


SJW_CYP2D6_RULE = {
    "drug_class_id": "cyp2d6_substrates",
    "severity": "monitor",
    "evidence_level": "probable",
    "mechanism": "At ≥900 mg/day standardized extract, SJW has measurable CYP2D6 effect — the direction is mixed across studies (some induction, some weak inhibition reported). This is distinct from SJW's dramatic and consistent CYP3A4 induction (see contraindicated rule with CYP3A4-substrate drugs). Effect at typical lower doses is not clinically significant.",
    "action": "If you take a CYP2D6-substrate prescription drug at high-dose St. John's Wort (≥900 mg/day), your prescriber may want to monitor for changes in drug effect. The CYP3A4 interaction at any dose is the dominant clinical concern — see the existing contraindication.",
    "sources": [
        "https://pubmed.ncbi.nlm.nih.gov/10976546/",
        "https://pubmed.ncbi.nlm.nih.gov/15054636/"
    ],
    "alert_headline": "High-dose may shift drug levels",
    "alert_body": "If you take a CYP2D6-substrate prescription drug, your prescriber may want to monitor for changes in drug effect at high-dose St. John's Wort (≥900 mg/day).",
    "informational_note": "SJW at ≥900 mg/day has mixed-direction CYP2D6 effect — distinct from its dominant CYP3A4 induction.",
}


BUPLEURUM_PREG_LACT = {
    "pregnancy_category": "caution",
    "lactation_category": "no_data",
    "evidence_level": "limited",
    "mechanism": "Emmenagogue activity in TCM literature; limited modern safety data in pregnancy. Lactation safety data absent.",
    "notes": "Use caution in pregnancy due to traditional emmenagogue activity. Lactation safety not established — clinician guidance recommended.",
    "alert_headline": "Talk to your clinician",
    "alert_body": "Bupleurum has traditional emmenagogue activity and limited safety data in pregnancy. Talk to your obstetrician before use during pregnancy or breastfeeding.",
    "informational_note": "Bupleurum has limited pregnancy safety data — clinician guidance recommended.",
}


def find_rule(rules, db, canonical_id):
    for r in rules:
        sref = r.get("subject_ref", {})
        if sref.get("db") == db and sref.get("canonical_id") == canonical_id:
            return r
    return None


def upsert_drug_class_rule(rule_obj, payload):
    dcrs = rule_obj.setdefault("drug_class_rules", [])
    target_id = payload["drug_class_id"]
    for i, dcr in enumerate(dcrs):
        if dcr.get("drug_class_id") == target_id:
            if dcr == payload:
                return False, "noop"
            dcrs[i] = payload
            return True, "updated"
    dcrs.append(payload)
    return True, "added"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    data = json.load(open(RULES_PATH))
    rules = data["interaction_rules"]
    summary = {"bupleurum_rule": "noop", "sjw_cyp2d6_rule": "noop", "bupleurum_preg_lact": "noop"}

    # Bupleurum — botanical_ingredients subject_ref. Create rule entry if missing.
    bup_rule = find_rule(rules, "botanical_ingredients", "bupleurum_root")
    if bup_rule is None:
        bup_rule = {
            "id": "RULE_BOTAN_BUPLEURUM_CYP2D6",
            "subject_ref": {"db": "botanical_ingredients", "canonical_id": "bupleurum_root"},
            "condition_rules": [],
            "drug_class_rules": [],
            "dose_thresholds": [],
            "pregnancy_lactation": dict(BUPLEURUM_PREG_LACT),
            "last_reviewed": "2026-04-30",
            "review_owner": "pharmaguide_clinical_team",
        }
        rules.append(bup_rule)
        summary["bupleurum_preg_lact"] = "added (with rule)"
    else:
        # Mirror pregnancy/lactation seed if not yet populated
        pl = bup_rule.get("pregnancy_lactation") or {}
        if pl.get("pregnancy_category") in (None, "", "no_data"):
            bup_rule["pregnancy_lactation"] = dict(BUPLEURUM_PREG_LACT)
            summary["bupleurum_preg_lact"] = "seeded"

    changed, action = upsert_drug_class_rule(bup_rule, BUPLEURUM_CYP2D6_RULE)
    if changed:
        summary["bupleurum_rule"] = action

    # SJW — append cyp2d6_substrates rule to the existing IQM rule entry.
    sjw_rule = find_rule(rules, "ingredient_quality_map", "st_johns_wort")
    if sjw_rule is None:
        print("FATAL: st_johns_wort rule not found", file=sys.stderr)
        return 2
    changed, action = upsert_drug_class_rule(sjw_rule, SJW_CYP2D6_RULE)
    if changed:
        summary["sjw_cyp2d6_rule"] = action

    # Bump metadata
    md = data["_metadata"]
    md["last_updated"] = "2026-04-30"
    md["total_rules"] = len(rules)
    md["total_entries"] = len(rules)

    print("2E CYP2D6 follow-up:")
    for k, v in summary.items():
        print(f"  {k:30s} {v}")
    print(f"  total rules now:               {len(rules)}")

    if args.dry_run:
        print("\n[dry-run] would write")
        return 0

    json.dump(data, open(RULES_PATH, "w"), indent=2, ensure_ascii=False)
    open(RULES_PATH, "a").write("\n")
    print(f"\nWrote {RULES_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
