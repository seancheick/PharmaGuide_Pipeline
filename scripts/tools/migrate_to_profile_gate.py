#!/usr/bin/env python3
"""Migrate ingredient_interaction_rules.json from v5.3.x to v6.0 by populating
profile_gate on every sub-rule.

Implements the migration table from scripts/INTERACTION_RULE_SCHEMA_V6_ADR.md.
Default mode is dry-run: prints a unified diff and exits without writing.
Pass --apply to write the migrated file in place.

Mappings (deterministic, no clinical judgment):

  condition_rules[].condition_id="pregnancy"        → profile_flag gate, flags=[pregnant, trying_to_conceive]
  condition_rules[].condition_id="lactation"        → profile_flag gate, flags=[breastfeeding]
  condition_rules[].condition_id="ttc"              → profile_flag gate, flags=[trying_to_conceive]
  condition_rules[].condition_id="surgery_scheduled"→ profile_flag gate, flags=[surgery_scheduled]
  condition_rules[].condition_id=*                  → condition gate, conditions_any=[<id>]
  drug_class_rules[].drug_class_id=*                → drug_class gate, drug_classes_any=[<id>]
  dose_thresholds[] (scope=condition)               → combination gate (conditions_any) + dose
  dose_thresholds[] (scope=drug_class)              → combination gate (drug_classes_any) + dose
  dose_thresholds[] (scope=profile_flag)            → combination gate (profile_flags_any) + dose
  dose_thresholds[] (no scope / pure dose)          → dose gate
  pregnancy_lactation block                         → profile_flag gate, flags=[pregnant, trying_to_conceive, breastfeeding]

The script is idempotent: re-running on already-migrated rules is a no-op
because it only sets profile_gate when absent.

Schema bump (5.3.x → 6.0.0) is NOT done by this script; that lands in Step 4.
"""
from __future__ import annotations

import argparse
import copy
import difflib
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
RULES_PATH = REPO / "scripts" / "data" / "ingredient_interaction_rules.json"

# Profile-flag mappings for condition_id values that map to lifecycle/perioperative flags
PROFILE_FLAG_CONDITION_MAP: dict[str, list[str]] = {
    "pregnancy":         ["pregnant", "trying_to_conceive"],
    "lactation":         ["breastfeeding"],
    "ttc":               ["trying_to_conceive"],
    "surgery_scheduled": ["surgery_scheduled"],
}


def _empty_excludes() -> dict[str, list]:
    return {
        "conditions_any": [],
        "drug_classes_any": [],
        "profile_flags_any": [],
        "product_forms_any": [],
        "nutrient_forms_any": [],
    }


def _build_gate_for_condition(condition_id: str) -> dict[str, Any]:
    """condition_rules[] → profile_flag or condition gate."""
    cid = (condition_id or "").strip().lower()
    if cid in PROFILE_FLAG_CONDITION_MAP:
        return {
            "gate_type": "profile_flag",
            "requires": {
                "conditions_any":    [],
                "drug_classes_any":  [],
                "profile_flags_any": list(PROFILE_FLAG_CONDITION_MAP[cid]),
            },
            "excludes": _empty_excludes(),
            "dose":     None,
        }
    return {
        "gate_type": "condition",
        "requires": {
            "conditions_any":    [cid],
            "drug_classes_any":  [],
            "profile_flags_any": [],
        },
        "excludes": _empty_excludes(),
        "dose":     None,
    }


def _build_gate_for_drug_class(drug_class_id: str) -> dict[str, Any]:
    """drug_class_rules[] → drug_class gate."""
    did = (drug_class_id or "").strip().lower()
    return {
        "gate_type": "drug_class",
        "requires": {
            "conditions_any":    [],
            "drug_classes_any":  [did],
            "profile_flags_any": [],
        },
        "excludes": _empty_excludes(),
        "dose":     None,
    }


def _build_gate_for_dose_threshold(threshold: dict[str, Any]) -> dict[str, Any]:
    """dose_thresholds[] → combination or dose gate."""
    scope = (threshold.get("scope") or "").strip().lower()
    target = (threshold.get("target_id") or "").strip().lower()

    dose_block = {
        "basis":              threshold.get("basis"),
        "comparator":         threshold.get("comparator"),
        "value":              threshold.get("value"),
        "unit":               threshold.get("unit"),
        "severity_if_met":    threshold.get("severity_if_met"),
        "severity_if_not_met": threshold.get("severity_if_not_met"),
    }

    if scope == "condition" and target:
        if target in PROFILE_FLAG_CONDITION_MAP:
            return {
                "gate_type": "combination",
                "requires": {
                    "conditions_any":    [],
                    "drug_classes_any":  [],
                    "profile_flags_any": list(PROFILE_FLAG_CONDITION_MAP[target]),
                },
                "excludes": _empty_excludes(),
                "dose":     dose_block,
            }
        return {
            "gate_type": "combination",
            "requires": {
                "conditions_any":    [target],
                "drug_classes_any":  [],
                "profile_flags_any": [],
            },
            "excludes": _empty_excludes(),
            "dose":     dose_block,
        }
    if scope == "drug_class" and target:
        return {
            "gate_type": "combination",
            "requires": {
                "conditions_any":    [],
                "drug_classes_any":  [target],
                "profile_flags_any": [],
            },
            "excludes": _empty_excludes(),
            "dose":     dose_block,
        }
    if scope == "profile_flag" and target:
        return {
            "gate_type": "combination",
            "requires": {
                "conditions_any":    [],
                "drug_classes_any":  [],
                "profile_flags_any": [target],
            },
            "excludes": _empty_excludes(),
            "dose":     dose_block,
        }
    return {
        "gate_type": "dose",
        "requires": {
            "conditions_any":    [],
            "drug_classes_any":  [],
            "profile_flags_any": [],
        },
        "excludes": _empty_excludes(),
        "dose":     dose_block,
    }


def _build_gate_for_preg_lac() -> dict[str, Any]:
    """pregnancy_lactation block → profile_flag gate (union of reproductive flags).

    Flutter chooses severity from the block's pregnancy_category vs lactation_category
    based on which user flag matched. Step 5 of the v6.0 plan may split the block
    into separate condition_rules entries for cleaner severity selection.
    """
    return {
        "gate_type": "profile_flag",
        "requires": {
            "conditions_any":    [],
            "drug_classes_any":  [],
            "profile_flags_any": ["pregnant", "trying_to_conceive", "breastfeeding"],
        },
        "excludes": _empty_excludes(),
        "dose":     None,
    }


def migrate_rules(data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
    """Apply the migration in-place and return (migrated_data, counts)."""
    counts = {
        "condition_rules":   0,
        "drug_class_rules":  0,
        "dose_thresholds":   0,
        "pregnancy_lactation_blocks": 0,
        "rules_visited":     0,
        "rules_already_migrated": 0,
    }

    rules = data.get("interaction_rules", [])
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        counts["rules_visited"] += 1

        for cr in rule.get("condition_rules") or []:
            if isinstance(cr, dict) and "profile_gate" not in cr:
                cid = cr.get("condition_id", "")
                cr["profile_gate"] = _build_gate_for_condition(cid)
                counts["condition_rules"] += 1

        for dr in rule.get("drug_class_rules") or []:
            if isinstance(dr, dict) and "profile_gate" not in dr:
                did = dr.get("drug_class_id", "")
                dr["profile_gate"] = _build_gate_for_drug_class(did)
                counts["drug_class_rules"] += 1

        for dt in rule.get("dose_thresholds") or []:
            if isinstance(dt, dict) and "profile_gate" not in dt:
                dt["profile_gate"] = _build_gate_for_dose_threshold(dt)
                counts["dose_thresholds"] += 1

        pl = rule.get("pregnancy_lactation")
        if isinstance(pl, dict) and pl and "profile_gate" not in pl:
            preg_cat = (pl.get("pregnancy_category") or "").strip().lower()
            lact_cat = (pl.get("lactation_category") or "").strip().lower()
            if preg_cat in {"no_data", ""} and lact_cat in {"no_data", ""}:
                pass
            else:
                pl["profile_gate"] = _build_gate_for_preg_lac()
                counts["pregnancy_lactation_blocks"] += 1

    return data, counts


def render_diff(before: dict, after: dict, path_label: str) -> str:
    """Produce a unified diff string between two JSON dicts (sorted, indented)."""
    before_text = json.dumps(before, indent=2, ensure_ascii=False, sort_keys=False).splitlines(keepends=True)
    after_text  = json.dumps(after,  indent=2, ensure_ascii=False, sort_keys=False).splitlines(keepends=True)
    diff = difflib.unified_diff(
        before_text, after_text,
        fromfile=f"a/{path_label}",
        tofile=f"b/{path_label}",
        n=3,
    )
    return "".join(diff)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--apply", action="store_true",
                   help="Write the migrated file in place (default: dry-run with diff preview)")
    p.add_argument("--diff-lines", type=int, default=80,
                   help="When dry-run, max lines of diff to print (default: 80)")
    p.add_argument("--rules-path", type=Path, default=RULES_PATH,
                   help=f"Path to rule file (default: {RULES_PATH})")
    args = p.parse_args(argv)

    if not args.rules_path.exists():
        print(f"ERROR: rule file not found: {args.rules_path}", file=sys.stderr)
        return 2

    raw_text = args.rules_path.read_text()
    before = json.loads(raw_text)
    after = copy.deepcopy(before)
    after, counts = migrate_rules(after)

    print("Migration counts:")
    for k, v in counts.items():
        print(f"  {k}: {v}")

    total = sum(v for k, v in counts.items() if k not in ("rules_visited", "rules_already_migrated"))
    if total == 0:
        print("\nNo changes needed — file is already migrated (or empty).")
        return 0

    if args.apply:
        new_text = json.dumps(after, indent=2, ensure_ascii=False) + "\n"
        args.rules_path.write_text(new_text)
        print(f"\nApplied. {total} profile_gate fields written to {args.rules_path}")
        return 0

    diff = render_diff(before, after, args.rules_path.name)
    lines = diff.splitlines()
    print(f"\nDry run — {total} profile_gate fields would be added.")
    print(f"Unified diff (first {args.diff_lines} of {len(lines)} lines):\n")
    for line in lines[: args.diff_lines]:
        print(line)
    if len(lines) > args.diff_lines:
        print(f"\n... ({len(lines) - args.diff_lines} more lines) ...")
    print("\nRe-run with --apply to write changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
