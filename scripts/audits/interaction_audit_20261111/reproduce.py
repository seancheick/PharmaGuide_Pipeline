"""Interaction audit Stage 1: reproduce the source-data findings in FINDINGS.md.

Usage: python3 scripts/audits/interaction_audit_20261111/reproduce.py

Prints OPEN or CLOSED for each finding and exits 1 while any finding is open.
CI forbids expected failures, so these checks live here. Each fix stage adds a
real test alongside its fix.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data"

# The app's only class crosswalk today
# (PharmaGuide ai lib/services/medications/medication_class_bridge.dart
# `_profileGateClassOverrides`); every other `class:x` id reaches rule id `x`.
APP_PROFILE_GATE_OVERRIDES = {"class:antiplatelet_agents": "antiplatelets"}
DIGOXIN, CLOBAZAM, VALPROIC_ACID, VENLAFAXINE, DULOXETINE = "3407", "21241", "11118", "39786", "72625"
HELD_INTERVALS = [
    # (timing rule held for an unsupported interval, curated pair publishing it)
    ("timing_iron_calcium_separate", "SSI_IRON_CALCIUM"),
    # Magnesium + levothyroxine is not a leak: Sean approved "at least 4 hours"
    # for the pair text on 2026-10-01 (D27); only the timing card stays held.
    ("timing_thyroid_med_soy_separate", "DSI_LEVOTHYROXINE_SOY"),
]


def _load(name: str):
    return json.loads((DATA / name).read_text())


CLASSES = _load("drug_classes.json")["classes"]
RULES = _load("ingredient_interaction_rules.json")["interaction_rules"]
TIMING = _load("timing_rules.json")["timing_rules"]


def _profile_id(class_id: str) -> str:
    return APP_PROFILE_GATE_OVERRIDES.get(class_id, class_id.removeprefix("class:"))


def _classes_for(rxcui: str) -> set[str]:
    return {_profile_id(cid) for cid, c in CLASSES.items() if rxcui in c.get("member_rxcuis", [])}


def gate_ids(sub_rule: dict) -> set[str]:
    """Ids the app matches: the authored drug_classes_any plus the rule class."""
    requires = (sub_rule.get("profile_gate") or {}).get("requires") or {}
    return {sub_rule["drug_class_id"], *(requires.get("drug_classes_any") or [])}


def unreachable() -> list[tuple[str, str]]:
    reachable = {_profile_id(cid) for cid in CLASSES}
    return sorted(
        (r["id"], d["drug_class_id"])
        for r in RULES
        for d in r.get("drug_class_rules") or []
        if not gate_ids(d) & reachable
    )


def _rule_ids(rule_id: str, drug_class_id: str | None = None) -> set[str]:
    rule = next(r for r in RULES if r["id"] == rule_id)
    subs = [d for d in rule["drug_class_rules"] if drug_class_id in (None, d["drug_class_id"])]
    return set().union(*(gate_ids(d) for d in subs))


def _curated_management(pair_id: str) -> str:
    for path in sorted((DATA / "curated_interactions").glob("*.json")):
        doc = json.loads(path.read_text())
        for item in (doc.get("interactions") if isinstance(doc, dict) else doc) or []:
            if item.get("id") == pair_id:
                return item.get("management") or ""
    raise KeyError(pair_id)


def _intervals(text: str) -> set[str]:
    return set(re.findall(r"(\d+)\s*hours?\s+(?:apart|away|before|after)", text))


def checks() -> list[tuple[str, bool, str]]:
    out = []
    gaps = unreachable()
    out.append(("1 rule classes reachable", not gaps, f"{len(gaps)} unreachable sub-rules"))
    out.append(
        ("2 digoxin -> cardiac_glycosides", "cardiac_glycosides" in _classes_for(DIGOXIN), str(_classes_for(DIGOXIN)))
    )
    cbd = _rule_ids("RULE_BANNED_CBD_INTERACTIONS")
    for name, rxcui in (("clobazam", CLOBAZAM), ("valproic acid", VALPROIC_ACID)):
        out.append((f"3 CBD rule reaches {name}", bool(_classes_for(rxcui) & cbd), str(_classes_for(rxcui))))
    sjw = _rule_ids("RULE_INGREDIENT_ST_JOHNS_WORT", "antidepressants_ssri_snri")
    for name, rxcui in (("venlafaxine", VENLAFAXINE), ("duloxetine", DULOXETINE)):
        out.append((f"4 SJW rule reaches {name}", bool(_classes_for(rxcui) & sjw), str(_classes_for(rxcui))))
    for timing_id, pair_id in HELD_INTERVALS:
        timing = next(t for t in TIMING if t["id"] == timing_id)
        held = _intervals(timing["advice"]) if timing["review_status"] != "verified" else set()
        leaked = held & _intervals(_curated_management(pair_id))
        out.append((f"5 held interval absent from {pair_id}", not leaked, f"publishes {sorted(leaked)} h"))
    return out


def main() -> int:
    results = checks()
    for name, closed, detail in results:
        print(f"{'CLOSED' if closed else 'OPEN  '} {name}: {detail}")
    return 0 if all(closed for _, closed, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())
