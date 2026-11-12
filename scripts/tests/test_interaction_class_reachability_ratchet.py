"""Ratchet: no new interaction sub-rule may gate on a class no medication reaches.

The interaction audit (2026-11-11) found 79 drug-class sub-rules whose
`profile_gate.requires.drug_classes_any` names no medication class in
drug_classes.json, so an entered medicine never triggers them (a class picked
in the profile still does). Stage 2 added the missing medication classes,
leaving 8; this test lets the count fall but never rise. Lower the ceiling as
fixes land.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
sys.path.insert(0, str(DATA.parent))

from rule_change_gate import APP_PROFILE_GATE_OVERRIDES  # noqa: E402  (the app's class crosswalk)
CEILING = 8
KNOWN_UNREACHABLE_CLASSES = {
    # Enzyme-substrate groups and antiarrhythmics: membership needs a
    # per-drug source review (Stage 3), not an ATC lookup.
    "cyp3a4_substrates",
    "cyp2d6_substrates",
    "antiarrhythmics",
}


def _unreachable() -> list[tuple[str, str]]:
    classes = json.loads((DATA / "drug_classes.json").read_text())["classes"]
    rules = json.loads((DATA / "ingredient_interaction_rules.json").read_text())["interaction_rules"]
    reachable = {APP_PROFILE_GATE_OVERRIDES.get(c, c.removeprefix("class:")) for c in classes}
    out = []
    for rule in rules:
        for sub in rule.get("drug_class_rules") or []:
            requires = (sub.get("profile_gate") or {}).get("requires") or {}
            if not {sub["drug_class_id"], *(requires.get("drug_classes_any") or [])} & reachable:
                out.append((rule["id"], sub["drug_class_id"]))
    return out


def test_unreachable_drug_class_sub_rules_never_grow():
    found = _unreachable()
    new_classes = {cls for _, cls in found} - KNOWN_UNREACHABLE_CLASSES
    assert not new_classes, f"sub-rules gate on classes no medication reaches: {sorted(new_classes)}"
    assert len(found) <= CEILING, f"{len(found)} unreachable sub-rules (ceiling {CEILING})"


def test_ratchet_detects_an_unreachable_gate(monkeypatch):
    """Control: a rule gated only on an unknown class is reported."""
    rules = {"interaction_rules": [{"id": "R", "drug_class_rules": [{"drug_class_id": "not_a_class"}]}]}
    real_read = Path.read_text
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda self, *a, **k: json.dumps(rules) if self.name == "ingredient_interaction_rules.json" else real_read(self, *a, **k),
    )
    assert _unreachable() == [("R", "not_a_class")]
