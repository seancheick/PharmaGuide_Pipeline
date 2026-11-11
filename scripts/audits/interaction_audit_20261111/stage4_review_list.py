"""Stage 4 review list for the PharmD: the highest-volume rules and theoretical-only rules.

Usage: $PG_PYTHON scripts/audits/interaction_audit_20261111/stage4_review_list.py > stage4_review_list.md

Volumes come from baseline.json (4,000 sampled blobs); they rank rules for review and are not a
false-positive rate. For each top subject per profile it prints the sub-rule that fires, its
severity and evidence level, whether a dose gate exists, and whether the warning text names an
amount the gate does not enforce (text and gate disagree). No data changes.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
DATA = REPO / "scripts/data"
RANK = {"informational": 0, "monitor": 1, "caution": 2, "avoid": 3, "contraindicated": 4}
CONDITION = {"pregnancy": "pregnancy", "lactation": "lactation", "diabetes": "diabetes",
             "kidney_disease": "kidney_disease", "heart_disease": "heart_disease"}
AMOUNT = re.compile(r"\d[\d,.]*\s*(?:IU|mg|mcg|µg|g)\b", re.I)


def _subs(rule, profile):
    if profile in CONDITION:
        for i, sub in enumerate(rule.get("condition_rules") or []):
            if sub.get("condition_id") == CONDITION[profile]:
                yield f"condition_rules[{i}]", sub
    for i, sub in enumerate(rule.get("drug_class_rules") or []):
        if sub.get("drug_class_id") == profile:
            yield f"drug_class_rules[{i}]", sub


def _dose_gated(rule, sub, profile):
    if (sub.get("profile_gate") or {}).get("dose") or sub.get("min_effective_dose"):
        return True
    return any(t.get("target_id") in (profile, sub.get("condition_id"), sub.get("drug_class_id"))
               for t in rule.get("dose_thresholds") or [])


def _text_amount(sub):
    text = " ".join(str(sub.get(k) or "") for k in ("mechanism", "action", "alert_body", "alert_headline"))
    return sorted(set(m.group(0) for m in AMOUNT.finditer(text)))


def main() -> None:
    baseline = json.loads((HERE / "baseline.json").read_text())
    rules = json.loads((DATA / "ingredient_interaction_rules.json").read_text())["interaction_rules"]
    by_subject = {}
    for rule in rules:
        by_subject.setdefault((rule.get("subject_ref") or {}).get("canonical_id"), []).append(rule)

    print("## G1. Highest-volume rules per profile (baseline sample, 4,000 products)\n")
    print("| Profile (share warned) | Subject (products) | Sub-rule | Severity | Evidence | Dose gate | Amount named in text, not gated | Sources |")
    print("|---|---|---|---|---|---|---|---|")
    for profile, data in baseline["profiles"].items():
        share = f"{data['share_of_products_warned']:.1%}"
        for subject, count in data["top_subjects"][:5]:
            hits = [(r, path, sub) for r in by_subject.get(subject, []) for path, sub in _subs(r, profile)]
            if not hits:
                print(f"| {profile} ({share}) | {subject} ({count}) | via pregnancy_lactation block or curated pair | | | | | |")
                continue
            for rule, path, sub in hits:
                gated = _dose_gated(rule, sub, profile)
                amounts = "" if gated else ", ".join(_text_amount(sub))
                print(f"| {profile} ({share}) | {subject} ({count}) | `{rule['id']}` {path} | {sub.get('severity')} | "
                      f"{sub.get('evidence_level')} | {'yes' if gated else 'no'} | {amounts} | {len(sub.get('sources') or [])} |")

    print("\n## G2. Theoretical or limited-evidence sub-rules at caution or above\n")
    print("| Rule | Sub-rule | Target | Severity | Evidence | Sources |")
    print("|---|---|---|---|---|---|")
    n = 0
    for rule in rules:
        for key in ("condition_rules", "drug_class_rules"):
            for i, sub in enumerate(rule.get(key) or []):
                if sub.get("evidence_level") in ("theoretical", "limited") and RANK.get(sub.get("severity"), 0) >= 2:
                    n += 1
                    target = sub.get("condition_id") or sub.get("drug_class_id")
                    print(f"| `{rule['id']}` | {key}[{i}] | {target} | {sub['severity']} | {sub['evidence_level']} | {len(sub.get('sources') or [])} |")
    print(f"\n{n} sub-rules.\n")

    timing = json.loads((DATA / "timing_rules.json").read_text())
    rows = [t for t in timing.get("rules", timing.get("timing_rules", [])) if t.get("review_status") != "verified"]
    print("## G3. Timing rules not published (review_status other than verified)\n")
    print("| Rule | Status | Reason held |")
    print("|---|---|---|")
    for t in rows:
        reason = "; ".join(t.get("review_blockers") or []) or t.get("review_note") or ""
        print(f"| `{t.get('id')}` | {t.get('review_status')} | {str(reason)[:160]} |")
    print(f"\n{len(rows)} rules.")


if __name__ == "__main__":
    main()
