"""LEDGER Q61 (Sean 2026-10-02): safety copy is never stronger than the evidence.

Evidence -> factual ``reason`` -> simplified ``safety_warning`` / one-liner.
Q57b corrected ``reason``; each phrase below survived in the user-facing copy
although its record's evidence does not support it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[1] / "data" / "banned_recalled_ingredients.json"

GONE = [
    ("BANNED_7_HYDROXYMITRAGYNINE", "13 times morphine"),
    ("RISK_KAVA", "over 100 cases"),
    ("RECALLED_OXYELITE_PRO", "97 cases"),
    ("BANNED_FASORACETAM", "failed clinical trials"),
    ("BANNED_FASORACETAM", "Failed investigational drug"),
    ("BANNED_ADD_PHTHALATES", "contamination rather than an added ingredient"),
    ("RISK_GREEN_TEA_EXTRACT_HIGH", "particularly above 800 mg"),
    ("SARM_ANDARINE", "vision disturbances"),
    ("SARM_OSTARINE", "failed cancer-cachexia trials"),
    ("SARM_OSTARINE", "hormonal suppression"),
    ("SARM_RAD140", "cardiovascular strain"),
    ("BANNED_S23", "liver strain"),
    ("BANNED_BMPEA", "Linked to cardiovascular risk"),
    ("BANNED_DMHA", "associated with elevated blood pressure and cardiovascular risk"),
    ("BANNED_EPHEDRA", "heart attacks"),
    ("BANNED_EPHEDRA", "otherwise healthy users"),
    ("BANNED_HIGENAMINE", "linked to cardiovascular stimulation risk"),
    ("ADD_HORDENINE", "drug-strength doses"),
    ("ADD_HORDENINE", "Stimulant at supplement doses"),
    ("HIGH_RISK_CHAPARRAL", "at least 18 reported cases"),
    ("HIGH_RISK_CHAPARRAL", "Not a lawful supplement ingredient"),
    ("HM_LEAD", "no safe blood level"),
    ("HM_LEAD", "kidney"),
    ("RISK_BITTER_ORANGE", "ephedrine-like cardiovascular effects"),
    ("RISK_GERMANIUM", "Inorganic germanium compounds"),
    ("RISK_GERMANIUM", "Not a lawful supplement ingredient"),
    ("STIM_METHYLHEXANAMINE_ANALOGS", "same cardiovascular risks as DMAA"),
    ("RECALLED_JACK3D", "was recalled after its DMAA content was linked to two deaths"),
    ("RECALLED_RHEUMACARE_CAPSULES", "thousands of times"),
    ("RECALLED_RHEUMACARE_CAPSULES", "Stop and test"),
    ("NOOTROPIC_BROMANTANE", "FDA has stated"),
    ("NOOTROPIC_BROMANTANE", "Not a lawful US supplement ingredient"),
    ("ADD_N_PHENETHYL_DIMETHYLAMINE", "not a lawful supplement ingredient"),
    ("RC_CARDARINE_ANALOGS", "Not lawful as supplements"),
]


@pytest.fixture(scope="module")
def entries() -> dict:
    return {e["id"]: e for e in json.loads(DATA.read_text())["ingredients"]}


@pytest.mark.parametrize("rule_id, phrase", GONE)
def test_overstated_copy_is_gone(entries, rule_id, phrase):
    entry = entries[rule_id]
    copy = f"{entry.get('safety_warning') or ''} {entry.get('safety_warning_one_liner') or ''}"
    assert phrase.lower() not in copy.lower()


@pytest.mark.parametrize(
    "rule_id, gone",
    [
        ("BANNED_S23", "not a dietary ingredient,  No NDI"),
        ("NOOTROPIC_BROMANTANE", "Products marketing it as a US supplement are adulterated"),
        ("RECALLED_RHEUMACARE_CAPSULES", "FDA issued an urgent recall"),
        ("RECALLED_JACK3D", "and was recalled"),
    ],
)
def test_reason_defect_is_gone(entries, rule_id, gone):
    assert gone not in entries[rule_id]["reason"]


def test_green_tea_keeps_the_q24_threshold_out_of_the_copy_but_in_the_evidence(entries):
    """Sean: rare injury occurs below 800 mg; 800 mg stays the dose signal (Q24)."""
    entry = entries["RISK_GREEN_TEA_EXTRACT_HIGH"]
    assert "lower doses" in entry["safety_warning"]
    assert "800 mg EGCG a day or more" in entry["reason"]
