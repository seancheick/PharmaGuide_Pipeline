"""Q50 regression lock: magnesium interaction-rule citations (Sean, 2026-10-01).

Evidence: `scripts/audits/levo_grapefruit_severity_20261001/research.md`, Q50.

- Magnesium x lithium is retired. Its only citation (the ODS magnesium fact
  sheet) never mentions lithium, the lithium label lists no magnesium or
  antacid interaction, and the one human study (Goode 1984, PMID 6428800)
  found an Al/Mg antacid did not change lithium bioavailability.
- Magnesium x kidney disease cited a kidney.org page about potassium; it now
  cites hypermagnesemia evidence and the magnesium laxative Drug Facts label.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

RULES = Path(__file__).resolve().parents[1] / "data" / "ingredient_interaction_rules.json"


@pytest.fixture(scope="module")
def magnesium_rule() -> dict:
    data = json.loads(RULES.read_text())
    return next(r for r in data["interaction_rules"] if r["id"] == "RULE_IQM_MAGNESIUM_HYPERTENSION")


def test_magnesium_lithium_rule_is_retired(magnesium_rule):
    drug_classes = {s["drug_class_id"] for s in magnesium_rule["drug_class_rules"]}
    assert "lithium" not in drug_classes


def test_magnesium_kidney_rule_cites_magnesium_evidence(magnesium_rule):
    sub = next(s for s in magnesium_rule["condition_rules"] if s["condition_id"] == "kidney_disease")
    sources = " ".join(sub["sources"])
    assert "kidney.org/atoz/content/potassium" not in sources
    for required in ("31379418", "37512002", "8cc7d52a-8fc3-4f52-9e50-b15613ddd02c"):
        assert required in sources, required
    # Mechanism states only what its sources support.
    assert "cardiac arrest" not in sub["mechanism"]
