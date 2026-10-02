"""LEDGER Q64 (Sean 2026-10-02): the copy may not state a fact its evidence lacks.

Q57b corrected ``reason`` while stale claims stayed in the copy ("13 times
morphine", "97 cases"). ``validate_safety_copy.copy_claims_without_evidence``
flags a number, regulatory term or named outcome in the warning or one-liner
that the record's evidence text (reason, status, jurisdictions, read sources)
never states. The production banned/recalled file must be clean.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from validate_safety_copy import copy_claims_without_evidence  # noqa: E402


def _entry(reason: str, warning: str, one_liner: str = "Stop using and talk to your doctor.") -> dict:
    return {"id": "X", "status": "banned", "legal_status_enum": "under_review", "reason": reason,
            "safety_warning": warning, "safety_warning_one_liner": one_liner, "references_structured": [], "jurisdictions": []}


@pytest.mark.parametrize(
    "reason, warning, flagged",
    [
        ("A partial opioid agonist, more potent than morphine in animals.", "Estimated 13 times morphine potency. Stop.", "number '13 times'"),
        ("Linked to liver injury in 36 cases.", "Linked to over 100 cases of liver injury. Stop.", "number '100 cases'"),
        ("No US determination exists.", "FDA banned it. Stop.", "'banned'"),
        ("Case reports of liver injury.", "Linked to liver injury and acromegaly. Stop.", "'acromegaly'"),
        ("Two placebo-controlled trials showed no clear advantage.", "A product that was recalled. Stop.", "'recalled'"),
    ],
)
def test_a_copy_fact_missing_from_the_evidence_is_flagged(reason, warning, flagged):
    assert flagged in copy_claims_without_evidence(_entry(reason, warning))


@pytest.mark.parametrize(
    "reason, warning, flagged",
    [
        ("A 2013 report described opioid activity.", "Estimated 13 times morphine potency. Stop.", "number '13 times'"),
        ("A product contained 1800 mcg per serving.", "Particularly above 800 mg. Stop.", "number '800 mg'"),
    ],
)
def test_a_number_inside_another_number_is_not_support(reason, warning, flagged):
    assert flagged in copy_claims_without_evidence(_entry(reason, warning))


@pytest.mark.parametrize(
    "reason, warning",
    [
        ("Multiple fatalities have been reported.", "Linked to deaths. Stop."),
        ("Caused malignant tumors in rats.", "Linked to cancer concerns. Avoid."),
        ("California prohibits it in food from 2027.", "Banned in California food from 2027. Avoid."),
        ("FDA has not approved it.", "An unapproved drug. Stop."),
    ],
)
def test_a_synonym_or_negative_form_is_accepted(reason, warning):
    assert copy_claims_without_evidence(_entry(reason, warning)) == []


def test_production_banned_recalled_copy_matches_its_evidence():
    data = json.loads((ROOT / "scripts" / "data" / "banned_recalled_ingredients.json").read_text())
    flagged = {e["id"]: copy_claims_without_evidence(e) for e in data["ingredients"] if e.get("match_mode") != "disabled"}
    assert {k: v for k, v in flagged.items() if v} == {}
