"""List medication-supplement pairs whose curated severity and profile-rule severity differ.

Usage: $PG_PYTHON scripts/audits/interaction_audit_20261111/conflicts.py [--json PATH]

A curated pair (drug class or drug x supplement) and an interaction-rule sub-rule
(supplement subject x drug class) describe the same situation when the
supplement canonical id matches and the drug class matches, or the drug's
RxCUI is a member of the sub-rule's class. The curated severity is mapped with
the production map (`verify_interactions.SEVERITY_MAP`). A difference is a
lead for review, not a verdict: scope (preparation, route, dose) may differ.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
from api_audit.verify_interactions import SEVERITY_MAP  # noqa: E402

DATA = REPO / "scripts/data"
RANK = {"informational": 0, "monitor": 1, "caution": 2, "avoid": 3, "contraindicated": 4}


def _curated():
    for path in sorted((DATA / "curated_interactions").glob("*.json")):
        yield from json.loads(path.read_text())["interactions"]


def _sides(item):
    """(drug ids, supplement canonical id) for a medication-supplement pair, else None."""
    kind = item.get("type")
    if kind == "Med-Sup":
        return item["agent1_id"], item.get("agent2_canonical_id")
    if kind == "Sup-Med":
        return item["agent2_id"], item.get("agent1_canonical_id")
    return None


def conflicts():
    classes = json.loads((DATA / "drug_classes.json").read_text())["classes"]
    members = {cid.removeprefix("class:"): set(c["member_rxcuis"]) for cid, c in classes.items()}
    rules = json.loads((DATA / "ingredient_interaction_rules.json").read_text())["interaction_rules"]
    subs = {}
    for rule in rules:
        subject = (rule.get("subject_ref") or {}).get("canonical_id")
        for i, sub in enumerate(rule.get("drug_class_rules") or []):
            subs.setdefault(subject, []).append((rule["id"], i, sub))
    out = []
    for item in _curated():
        sides = _sides(item)
        if not sides or not sides[1]:
            continue
        drug, supplement = sides
        curated = SEVERITY_MAP.get(str(item["severity"]).lower())
        for rule_id, i, sub in subs.get(supplement, []):
            cls = sub["drug_class_id"]
            same = drug == f"class:{cls}" or drug in members.get(cls, set())
            if same and sub.get("severity") != curated:
                out.append({
                    "pair": item["id"], "pair_severity": curated, "drug": drug, "supplement": supplement,
                    "rule": f"{rule_id}/drug_class_rules[{i}]", "rule_class": cls,
                    "rule_severity": sub.get("severity"),
                    "gap": RANK.get(curated, -1) - RANK.get(sub.get("severity"), -1),
                })
    return sorted(out, key=lambda c: (-abs(c["gap"]), c["pair"]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    found = conflicts()
    for c in found:
        print(f"{c['pair']:36} {c['pair_severity']:15} vs {c['rule_severity']:15} {c['rule']} ({c['supplement']})")
    print(f"{len(found)} conflicts")
    if args.json:
        args.json.write_text(json.dumps(found, indent=2) + "\n")


if __name__ == "__main__":
    main()
