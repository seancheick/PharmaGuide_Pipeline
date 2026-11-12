"""Batch 3b part 2: CBD immunosuppressant text follows the EPIDIOLEX label it cites.

Run once from the repo root:
    $PG_PYTHON scripts/audits/clinical_review_20261111/apply_batch3b_part2_cbd_everolimus.py

An independent review asked whether CBD covers everolimus. It does: everolimus (RxCUI 141704) is a member of
class:immunosuppressants, which reaches the immunosuppressants sub-rule of RULE_BANNED_CBD_INTERACTIONS (caution).
The sub-rule's text, however, named only tacrolimus and sirolimus, and its note said "CBD affects immune function",
which the cited label does not say. EPIDIOLEX (setid 8bf27097, revised 7/2025, read 2026-11-11), section 7.2:
oral everolimus exposure rose about 2.5-fold; when starting EPIDIOLEX, monitor everolimus levels and adjust the
dose; exposure to other oral P-gp substrates (sirolimus, tacrolimus, digoxin) may increase; consider drug-level
monitoring and dose reduction. Severity, headline, body, gate and evidence level are unchanged.

Left for Dr. Pham with the F7 CBD split (DISPOSITIONS question 5): the class also holds injected biologics the
label does not concern (adalimumab, etanercept), and digoxin, which the label names, has no CBD rule.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
import data_batch  # noqa: E402

RULES = REPO / "scripts/data/ingredient_interaction_rules.json"


def rules(blob: dict) -> None:
    rule = next(r for r in blob["interaction_rules"] if r["id"] == "RULE_BANNED_CBD_INTERACTIONS")
    [sub] = [s for s in rule["drug_class_rules"] if s["drug_class_id"] == "immunosuppressants"]
    assert sub["informational_note"] == "CBD affects immune function — relevant to people on immunosuppressants."
    assert sub["mechanism"].startswith("The EPIDIOLEX label advises monitoring")
    sub["mechanism"] = (
        "The EPIDIOLEX label reports that prescription cannabidiol raised oral everolimus exposure about 2.5-fold, "
        "and that exposure to other oral P-glycoprotein substrates, such as sirolimus and tacrolimus, may rise; it "
        "advises drug-level monitoring and dose adjustment. This should not be generalized to clinically proven "
        "inhibition of all CYP3A4 substrates."
    )
    sub["action"] = (
        "Monitor everolimus, tacrolimus or sirolimus levels closely; a dose reduction may be needed. Tell the team "
        "that prescribes it about CBD use."
    )
    sub["informational_note"] = (
        "Prescription CBD raised everolimus levels in a label study; relevant to people taking everolimus, "
        "tacrolimus or sirolimus."
    )


if __name__ == "__main__":
    blob = data_batch.load(RULES)
    rules(blob)
    data_batch.save(RULES, blob)
