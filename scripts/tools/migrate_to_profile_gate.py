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


def _build_gate_for_condition(condition_id: str, *, rule_id: str = "?") -> dict[str, Any]:
    """condition_rules[] → profile_flag or condition gate."""
    cid = (condition_id or "").strip().lower()
    if not cid:
        raise ValueError(f"empty condition_id in rule {rule_id}; cannot generate gate")
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


def _build_gate_for_drug_class(drug_class_id: str, *, rule_id: str = "?") -> dict[str, Any]:
    """drug_class_rules[] → drug_class gate."""
    did = (drug_class_id or "").strip().lower()
    if not did:
        raise ValueError(f"empty drug_class_id in rule {rule_id}; cannot generate gate")
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


def _build_gate_for_dose_threshold(threshold: dict[str, Any], *, rule_id: str = "?") -> dict[str, Any]:
    """dose_thresholds[] → combination or dose gate."""
    scope = (threshold.get("scope") or "").strip().lower()
    target = (threshold.get("target_id") or "").strip().lower()

    if scope in {"condition", "drug_class", "profile_flag"} and not target:
        raise ValueError(
            f"dose_threshold in rule {rule_id} has scope={scope!r} but empty target_id; "
            f"refuse to generate a degraded pure-dose gate"
        )

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


def migrate_rules(data: dict[str, Any], *, force: bool = False) -> tuple[dict[str, Any], dict[str, int]]:
    """Apply the migration in-place and return (migrated_data, counts).

    force=True overwrites any existing profile_gate (use during migration
    development if mappings change). Default is idempotent — only writes
    when profile_gate is absent.
    """
    counts = {
        "condition_rules":             0,
        "drug_class_rules":            0,
        "dose_thresholds":             0,
        "pregnancy_lactation_blocks":  0,
        "rules_visited":               0,
        "condition_rules_already":     0,
        "drug_class_rules_already":    0,
        "dose_thresholds_already":     0,
        "preg_lac_already":            0,
    }

    rules = data.get("interaction_rules", [])
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        counts["rules_visited"] += 1
        rule_id = rule.get("id", "?")

        for cr in rule.get("condition_rules") or []:
            if not isinstance(cr, dict):
                continue
            if "profile_gate" in cr and not force:
                counts["condition_rules_already"] += 1
                continue
            cid = cr.get("condition_id", "")
            cr["profile_gate"] = _build_gate_for_condition(cid, rule_id=rule_id)
            counts["condition_rules"] += 1

        for dr in rule.get("drug_class_rules") or []:
            if not isinstance(dr, dict):
                continue
            if "profile_gate" in dr and not force:
                counts["drug_class_rules_already"] += 1
                continue
            did = dr.get("drug_class_id", "")
            dr["profile_gate"] = _build_gate_for_drug_class(did, rule_id=rule_id)
            counts["drug_class_rules"] += 1

        for dt in rule.get("dose_thresholds") or []:
            if not isinstance(dt, dict):
                continue
            if "profile_gate" in dt and not force:
                counts["dose_thresholds_already"] += 1
                continue
            dt["profile_gate"] = _build_gate_for_dose_threshold(dt, rule_id=rule_id)
            counts["dose_thresholds"] += 1

        pl = rule.get("pregnancy_lactation")
        if isinstance(pl, dict) and pl:
            if "profile_gate" in pl and not force:
                counts["preg_lac_already"] += 1
            else:
                preg_cat = (pl.get("pregnancy_category") or "").strip().lower()
                lact_cat = (pl.get("lactation_category") or "").strip().lower()
                if preg_cat in {"no_data", ""} and lact_cat in {"no_data", ""}:
                    pass
                else:
                    pl["profile_gate"] = _build_gate_for_preg_lac()
                    counts["pregnancy_lactation_blocks"] += 1

    return data, counts


# --- Post-migration assertions (run inside the script before write) ---


_ALLOWED_GATE_TYPES = {"condition", "drug_class", "profile_flag", "dose", "nutrient_form", "combination"}
_REQUIRES_KEYS = {"conditions_any", "drug_classes_any", "profile_flags_any"}
_EXCLUDES_KEYS = {"conditions_any", "drug_classes_any", "profile_flags_any", "product_forms_any", "nutrient_forms_any"}


def assert_post_migration_invariants(data: dict[str, Any]) -> list[str]:
    """Walk the migrated rules and surface every violation.

    Returns a list of error strings. Empty list = clean.
    """
    errors: list[str] = []
    for rule in data.get("interaction_rules", []):
        if not isinstance(rule, dict):
            continue
        rule_id = rule.get("id", "?")

        def check_subrule(sub: dict[str, Any], path: str) -> None:
            gate = sub.get("profile_gate")
            if not isinstance(gate, dict):
                errors.append(f"{rule_id}/{path}: missing profile_gate")
                return
            gt = gate.get("gate_type")
            if gt not in _ALLOWED_GATE_TYPES:
                errors.append(f"{rule_id}/{path}: gate_type={gt!r} not in {_ALLOWED_GATE_TYPES}")
            req = gate.get("requires") or {}
            for k in _REQUIRES_KEYS:
                if k not in req:
                    errors.append(f"{rule_id}/{path}: requires missing key {k!r}")
                else:
                    for v in req[k] or []:
                        if not v or not isinstance(v, str) or not v.strip():
                            errors.append(f"{rule_id}/{path}: empty/whitespace id in requires.{k}")
            exc = gate.get("excludes") or {}
            for k in _EXCLUDES_KEYS:
                if k not in exc:
                    errors.append(f"{rule_id}/{path}: excludes missing key {k!r}")
            if gt == "dose" and not gate.get("dose"):
                errors.append(f"{rule_id}/{path}: gate_type=dose requires non-null dose block")

        for i, cr in enumerate(rule.get("condition_rules") or []):
            if isinstance(cr, dict):
                check_subrule(cr, f"condition_rules[{i}]")
        for i, dr in enumerate(rule.get("drug_class_rules") or []):
            if isinstance(dr, dict):
                check_subrule(dr, f"drug_class_rules[{i}]")
        for i, dt in enumerate(rule.get("dose_thresholds") or []):
            if isinstance(dt, dict):
                check_subrule(dt, f"dose_thresholds[{i}]")
        pl = rule.get("pregnancy_lactation")
        if isinstance(pl, dict) and pl:
            preg = (pl.get("pregnancy_category") or "").strip().lower()
            lact = (pl.get("lactation_category") or "").strip().lower()
            has_data = preg not in {"no_data", ""} or lact not in {"no_data", ""}
            if has_data:
                check_subrule(pl, "pregnancy_lactation")
    return errors


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
    p.add_argument("--force", action="store_true",
                   help="Overwrite existing profile_gate fields (use during migration development "
                        "if mappings change). Default is idempotent — only writes when absent.")
    p.add_argument("--diff-lines", type=int, default=80,
                   help="When dry-run, max lines of diff to print (default: 80)")
    p.add_argument("--rules-path", type=Path, default=RULES_PATH,
                   help=f"Path to rule file (default: {RULES_PATH})")
    args = p.parse_args(argv)

    if not args.rules_path.exists():
        print(f"ERROR: rule file not found: {args.rules_path}", file=sys.stderr)
        return 2

    raw_text = args.rules_path.read_text(encoding="utf-8")
    before = json.loads(raw_text)
    after = copy.deepcopy(before)
    try:
        after, counts = migrate_rules(after, force=args.force)
    except ValueError as e:
        print(f"ERROR: migration failed: {e}", file=sys.stderr)
        return 3

    print("Migration counts:")
    for k, v in counts.items():
        print(f"  {k}: {v}")

    total = sum(v for k, v in counts.items() if k in (
        "condition_rules", "drug_class_rules", "dose_thresholds", "pregnancy_lactation_blocks"
    ))
    if total == 0:
        print("\nNo changes needed — file is already migrated (or empty).")
        return 0

    # Post-migration assertions before writing — surface every violation up front
    violations = assert_post_migration_invariants(after)
    if violations:
        print(f"\nERROR: post-migration invariant check found {len(violations)} violation(s):", file=sys.stderr)
        for v in violations[:20]:
            print(f"  - {v}", file=sys.stderr)
        if len(violations) > 20:
            print(f"  ... and {len(violations) - 20} more", file=sys.stderr)
        return 4

    if args.apply:
        new_text = json.dumps(after, indent=2, ensure_ascii=False) + "\n"
        args.rules_path.write_text(new_text, encoding="utf-8")
        print(f"\nApplied. {total} profile_gate fields written to {args.rules_path}")
        print("Post-migration invariants: PASS")
        return 0

    diff = render_diff(before, after, args.rules_path.name)
    lines = diff.splitlines()
    print(f"\nDry run — {total} profile_gate fields would be added.")
    print("Post-migration invariants: PASS")
    print(f"Unified diff (first {args.diff_lines} of {len(lines)} lines):\n")
    for line in lines[: args.diff_lines]:
        print(line)
    if len(lines) > args.diff_lines:
        print(f"\n... ({len(lines) - args.diff_lines} more lines) ...")
    print("\nRe-run with --apply to write changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
