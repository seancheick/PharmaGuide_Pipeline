"""Batch 3b part 2: fit the new licorice and CBD copy to the authoring limits.

Run once from the repo root, after apply_batch3b_part2_review_fixes.py:
    $PG_PYTHON scripts/audits/clinical_review_20261111/apply_batch3b_part2_copy_limits.py

The batch's agent-written copy broke `validate_safety_copy` (alert_body 60-200 characters; informational_note
40-120), which PR CI found once #449 was retargeted to main. This copy is not word for word in the review file, so
the authoring limits apply. Each text is shortened only: severity, verbs ("avoid", "talk to"), the prescriber
condition, the DGL distinction, the named medicines and every source stay as they were. The `action` fields keep
the full wording.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
import data_batch  # noqa: E402

RULES = REPO / "scripts/data/ingredient_interaction_rules.json"

LICORICE_BP_BODY = (
    "Glycyrrhizin in licorice can raise blood pressure and lower potassium. If you take blood-pressure medicine, "
    "avoid it unless your prescriber has reviewed it. Licorice not labeled DGL may contain it."
)
LICORICE_DIGOXIN_BODY = (
    "Glycyrrhizin in licorice can lower potassium, making digoxin toxicity more likely. If you take digoxin, avoid "
    "it unless your prescriber advises it. Licorice not labeled DGL may contain it."
)
CBD_BODY = (
    "CBD can raise levels of some immunosuppressants, such as everolimus, tacrolimus or sirolimus. Ask that "
    "medicine's prescriber first; drug-level monitoring or a prescribed dose change may be needed."
)
CBD_NOTE = (
    "Prescription CBD raised everolimus levels in a label study — relevant to anyone on everolimus, tacrolimus or "
    "sirolimus."
)


def _sub(rule: dict, class_id: str) -> dict:
    [sub] = [s for s in rule["drug_class_rules"] if s["drug_class_id"] == class_id]
    return sub


def rules(blob: dict) -> None:
    for text in (LICORICE_BP_BODY, LICORICE_DIGOXIN_BODY, CBD_BODY):
        assert 60 <= len(text) <= 200, (len(text), text)
    assert 40 <= len(CBD_NOTE) <= 120, len(CBD_NOTE)
    by_id = {r["id"]: r for r in blob["interaction_rules"]}
    for rule_id in ("RULE_IQM_LICORICE_HYPERTENSION", "RULE_BOTANICAL_LICORICE_ROOT"):
        sub = _sub(by_id[rule_id], "antihypertensives")
        assert sub["alert_body"].startswith("Licorice that contains glycyrrhizin can raise blood pressure"), rule_id
        sub["alert_body"] = LICORICE_BP_BODY
    digoxin = _sub(by_id["RULE_IQM_LICORICE_HYPERTENSION"], "cardiac_glycosides")
    assert digoxin["alert_body"].startswith("Licorice that contains glycyrrhizin can lower potassium")
    digoxin["alert_body"] = LICORICE_DIGOXIN_BODY
    cbd = _sub(by_id["RULE_BANNED_CBD_INTERACTIONS"], "immunosuppressants")
    assert cbd["alert_body"].startswith("CBD can raise levels of certain immunosuppressant medicines")
    assert cbd["informational_note"].startswith("Prescription CBD raised everolimus levels in a label study;")
    cbd["alert_body"] = CBD_BODY
    cbd["informational_note"] = CBD_NOTE


if __name__ == "__main__":
    blob = data_batch.load(RULES)
    rules(blob)
    data_batch.save(RULES, blob)
