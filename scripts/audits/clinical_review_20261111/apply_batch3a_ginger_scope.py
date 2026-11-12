"""Batch 3a follow-up: ginger's blood-thinner finding carries warfarin evidence, so it gets the warfarin scope.

Run once from the repo root, after apply_batch3a_vka_scope.py:
    $PG_PYTHON scripts/audits/clinical_review_20261111/apply_batch3a_ginger_scope.py

Dr. Pham's A9 row is ginger + warfarin (caution for supplemental or concentrated ginger, limited and conflicting
evidence). The rule's two sources are a cohort of warfarin users (PMID 17723077) and a single-dose crossover in
healthy men taking no anticoagulant (PMID 15801937); neither covers another blood thinner. The rule nevertheless
warned every blood-thinner user, DOAC users included, unlike the other warfarin rows (A2, A4, A7, A8). An outside
review (CodeRabbit, PR #447) flagged it; reproduced 2026-11-11. Ginkgo and garlic keep every blood thinner: each
cites an NCCIH page that names blood thinners in general.

- RULE_IQM_GINGER_BLEEDING: the `anticoagulants` sub-rule becomes the warfarin-only pair of sub-rules the other
  rows use (an identified vitamin K antagonist; otherwise an unidentified blood thinner, DOACs excluded), with
  copy that names warfarin. Severity, evidence, mechanism, sources and the review record are unchanged.
- RULE_OTHER_GINGER_EXTRACT_BLEEDING: the same subject under its other-ingredient identity. It cited the NCCIH
  ginger page, which does not mention bleeding, warfarin or platelets (read 2026-11-11), and claimed "mild
  antiplatelet or anticoagulant activity". It now carries the reviewed ginger finding and scope. This is an agent
  alignment, recorded as such; it adds no review record.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
import data_batch  # noqa: E402

RULES = REPO / "scripts/data/ingredient_interaction_rules.json"

WARFARIN_COPY = {
    "action": (
        "If you take warfarin, talk to your prescriber before using ginger supplements or concentrates, and report "
        "unusual bruising or bleeding."
    ),
    "alert_headline": "May add to warfarin's bleeding risk",
    "alert_body": (
        "Ginger supplements may add to bleeding risk with warfarin; the evidence is limited and conflicting. Talk to "
        "your prescriber before adding ginger and report unusual bruising or bleeding."
    ),
    "informational_note": "Ginger supplements may affect bleeding risk — relevant to anyone on warfarin.",
}
FINDING_KEYS = ("severity", "evidence_level", "mechanism", "sources", "direction", "materiality")


def _warfarin_pair(subs: list, i: int) -> None:
    """Replace the all-blood-thinner sub-rule at i with the identified-VKA and unidentified-fallback pair."""
    fallback = subs[i]
    assert fallback["drug_class_id"] == "anticoagulants"
    assert fallback["profile_gate"]["requires"]["drug_classes_any"] == ["anticoagulants"]
    assert fallback["profile_gate"]["excludes"]["drug_classes_any"] == []
    fallback.update(WARFARIN_COPY)
    vka = copy.deepcopy(fallback)
    vka["drug_class_id"] = "vitamin_k_antagonists"
    vka["profile_gate"]["requires"]["drug_classes_any"] = ["vitamin_k_antagonists"]
    fallback["profile_gate"]["excludes"]["drug_classes_any"] = ["doacs", "vitamin_k_antagonists"]
    subs.insert(i, vka)


def rules(blob: dict) -> None:
    by_id = {r["id"]: r for r in blob["interaction_rules"]}
    reviewed_subs = by_id["RULE_IQM_GINGER_BLEEDING"]["drug_class_rules"]
    assert not [s for s in reviewed_subs if s["drug_class_id"] == "vitamin_k_antagonists"]
    [i] = [n for n, s in enumerate(reviewed_subs) if s["drug_class_id"] == "anticoagulants"]
    reviewed = reviewed_subs[i]
    assert reviewed["clinical_review"]["reviewer"] == "Dr. Pham"
    _warfarin_pair(reviewed_subs, i)

    extract = by_id["RULE_OTHER_GINGER_EXTRACT_BLEEDING"]
    [j] = [n for n, s in enumerate(extract["drug_class_rules"]) if s["drug_class_id"] == "anticoagulants"]
    sub = extract["drug_class_rules"][j]
    assert sub["sources"] == ["https://www.nccih.nih.gov/health/ginger"]
    for key in FINDING_KEYS:
        sub[key] = copy.deepcopy(reviewed[key])
    _warfarin_pair(extract["drug_class_rules"], j)
    extract["last_reviewed"] = "2026-11-11"
    extract["review_owner"] = (
        "Source-content review (agent), 2026-11-11: aligned with RULE_IQM_GINGER_BLEEDING (Dr. Pham A9, ginger + "
        "warfarin); the NCCIH ginger page it cited does not mention bleeding"
    )


if __name__ == "__main__":
    blob = data_batch.load(RULES)
    rules(blob)
    data_batch.save(RULES, blob)
