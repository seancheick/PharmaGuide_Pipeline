#!/usr/bin/env python3
"""Authoring helper for ingredient_interaction_rules.json.

Implements the workflow in scripts/INTERACTION_RULE_AUTHORING_SOP.md:
- one rule per ingredient (subject_ref); appends to existing rule on match
- refuses duplicate condition_id / drug_class_id on the same subject
- enforces taxonomy enums (severity, evidence_level, condition, drug_class)
- enforces v5.2 authored copy lengths (alert_headline 20-60, alert_body 60-200,
  informational_note 40-120; informational_note required for avoid/contraindicated)
- bumps `_metadata.total_entries`, `total_rules`, `last_updated`
- defaults review_owner to `pharmaguide_clinical_team` (SOP standard)

Does NOT author dose_thresholds — add those by hand per SOP §"Dose Threshold Policy".

Examples:
    # Add a condition rule
    python3 scripts/tools/add_rule.py \\
        --db ingredient_quality_map --canonical-id IQM_GINGER \\
        --condition pregnancy --severity caution --evidence limited \\
        --mechanism "..." --action "..." \\
        --alert-headline "..." --alert-body "..." --informational-note "..." \\
        --source https://... --reviewer "Lead Clinician"

    # Add a drug-class rule
    python3 scripts/tools/add_rule.py \\
        --db ingredient_quality_map --canonical-id IQM_GINGER \\
        --drug-class anticoagulants --severity caution --evidence moderate \\
        --mechanism "..." --action "..." \\
        --alert-headline "..." --alert-body "..." \\
        --source https://... --reviewer "Lead Clinician"

    # Preview without writing
    python3 scripts/tools/add_rule.py ... --dry-run
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RULES_PATH = REPO / "scripts" / "data" / "ingredient_interaction_rules.json"
TAXONOMY_PATH = REPO / "scripts" / "data" / "clinical_risk_taxonomy.json"

VALID_DBS = {
    "ingredient_quality_map",
    "banned_recalled_ingredients",
    "harmful_additives",
    "botanical_ingredients",
    "other_ingredients",
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _today() -> str:
    return _dt.date.today().isoformat()


def _len_ok(value: str, lo: int, hi: int, name: str) -> None:
    n = len(value)
    if n < lo or n > hi:
        raise SystemExit(f"ERROR: {name} length {n} outside [{lo}, {hi}]: {value!r}")


def _build_subrule(args, kind: str) -> dict:
    sub: dict = {}
    if kind == "condition":
        sub["condition_id"] = args.condition
    else:
        sub["drug_class_id"] = args.drug_class
    sub["severity"] = args.severity
    sub["evidence_level"] = args.evidence
    sub["mechanism"] = args.mechanism
    sub["action"] = args.action
    sub["sources"] = list(args.source or [])
    if args.alert_headline:
        _len_ok(args.alert_headline, 20, 60, "alert_headline")
        sub["alert_headline"] = args.alert_headline
    if args.alert_body:
        _len_ok(args.alert_body, 60, 200, "alert_body")
        sub["alert_body"] = args.alert_body
    if args.informational_note:
        _len_ok(args.informational_note, 40, 120, "informational_note")
        sub["informational_note"] = args.informational_note
    if args.severity in {"avoid", "contraindicated"} and not args.informational_note:
        raise SystemExit(
            "ERROR: informational_note is required when severity is avoid or contraindicated"
        )
    return sub


def _new_rule_id(db: str, canonical_id: str, suffix: str) -> str:
    db_short = {
        "ingredient_quality_map": "INGREDIENT",
        "banned_recalled_ingredients": "BANNED",
        "harmful_additives": "ADDITIVE",
        "botanical_ingredients": "BOTANICAL",
        "other_ingredients": "OTHER",
    }.get(db, db.upper())
    canon = canonical_id.replace("IQM_", "").replace("BANNED_", "").replace("ADDITIVE_", "")
    return f"RULE_{db_short}_{canon}_{suffix}".upper()


def _find_rule(rules: list[dict], db: str, canonical_id: str) -> dict | None:
    for r in rules:
        s = r.get("subject_ref") or {}
        if s.get("db") == db and s.get("canonical_id") == canonical_id:
            return r
    return None


def _validate_taxonomy(tax: dict, args, kind: str) -> None:
    valid_conditions = {c["id"] for c in tax.get("conditions", []) if isinstance(c, dict)}
    valid_drug_classes = {c["id"] for c in tax.get("drug_classes", []) if isinstance(c, dict)}
    valid_sev = {s["id"] for s in tax.get("severity_levels", []) if isinstance(s, dict)}
    valid_ev = {e["id"] for e in tax.get("evidence_levels", []) if isinstance(e, dict)}

    if kind == "condition" and args.condition not in valid_conditions:
        raise SystemExit(
            f"ERROR: unknown condition '{args.condition}'. Valid: {sorted(valid_conditions)}"
        )
    if kind == "drug" and args.drug_class not in valid_drug_classes:
        raise SystemExit(
            f"ERROR: unknown drug_class '{args.drug_class}'. Valid: {sorted(valid_drug_classes)}"
        )
    if valid_sev and args.severity not in valid_sev:
        raise SystemExit(f"ERROR: unknown severity '{args.severity}'. Valid: {sorted(valid_sev)}")
    if valid_ev and args.evidence not in valid_ev:
        raise SystemExit(f"ERROR: unknown evidence '{args.evidence}'. Valid: {sorted(valid_ev)}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", required=True, choices=sorted(VALID_DBS))
    p.add_argument("--canonical-id", required=True, dest="canonical_id")

    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--condition", help="condition_id (e.g., pregnancy, hypertension)")
    g.add_argument("--drug-class", dest="drug_class", help="drug_class_id (e.g., anticoagulants)")

    p.add_argument("--severity", required=True, help="caution | avoid | contraindicated | ...")
    p.add_argument("--evidence", required=True, dest="evidence", help="limited | moderate | probable | strong | ...")
    p.add_argument("--mechanism", required=True)
    p.add_argument("--action", required=True)
    p.add_argument("--source", action="append", help="repeatable; URL")
    p.add_argument("--alert-headline", dest="alert_headline", default="")
    p.add_argument("--alert-body", dest="alert_body", default="")
    p.add_argument("--informational-note", dest="informational_note", default="")
    p.add_argument("--reviewer", default="pharmaguide_clinical_team",
                   help="review_owner value (SOP default: pharmaguide_clinical_team)")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    kind = "condition" if args.condition else "drug"
    tax = _load(TAXONOMY_PATH)
    _validate_taxonomy(tax, args, kind)

    data = _load(RULES_PATH)
    rules: list[dict] = data.get("interaction_rules", [])
    sub = _build_subrule(args, kind)

    existing = _find_rule(rules, args.db, args.canonical_id)
    action_msg: str

    if existing is None:
        suffix = (args.condition or args.drug_class).upper()
        new_rule = {
            "id": _new_rule_id(args.db, args.canonical_id, suffix),
            "subject_ref": {"db": args.db, "canonical_id": args.canonical_id},
            "condition_rules": [sub] if kind == "condition" else [],
            "drug_class_rules": [sub] if kind == "drug" else [],
            "dose_thresholds": [],
            "pregnancy_lactation": {},
            "last_reviewed": _today(),
            "review_owner": args.reviewer,
        }
        rules.append(new_rule)
        action_msg = f"created new rule {new_rule['id']}"
    else:
        bucket_key = "condition_rules" if kind == "condition" else "drug_class_rules"
        bucket = existing.setdefault(bucket_key, [])
        target_id = args.condition if kind == "condition" else args.drug_class
        id_field = "condition_id" if kind == "condition" else "drug_class_id"
        for entry in bucket:
            if (entry.get(id_field) or "").strip().lower() == target_id:
                raise SystemExit(
                    f"ERROR: subject {args.canonical_id} already has a {kind} rule for "
                    f"'{target_id}' (rule id: {existing.get('id')}). Edit that entry directly "
                    f"or remove it first."
                )
        bucket.append(sub)
        existing["last_reviewed"] = _today()
        existing["review_owner"] = args.reviewer
        action_msg = f"appended {kind} '{target_id}' to {existing['id']}"

    meta = data.setdefault("_metadata", {})
    meta["total_entries"] = len(rules)
    meta["total_rules"] = len(rules)
    meta["last_updated"] = _today()

    if args.dry_run:
        print(f"DRY RUN — would: {action_msg}")
        print("Sub-rule preview:")
        print(json.dumps(sub, indent=2))
        return 0

    RULES_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"OK: {action_msg}")
    print(f"File: {RULES_PATH} ({len(rules)} rules)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
