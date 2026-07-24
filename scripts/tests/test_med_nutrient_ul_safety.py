"""Standing safety gate: no PUBLICATION-READY medication-depletion entry may
recommend a chronic nutrient dose above the conservative adult Tolerable Upper
Intake Level (UL), unless it carries an explicit ``dose_exemption`` naming a
supervised context (clinician-directed / deficiency treatment or prevention /
pregnancy / oncology / nephrology) where supra-UL dosing is deliberate.

Origin: the content audit caught OCP->B6 recommending 25-50 mg B6 — above the
EFSA 12 mg UL — where chronic high-dose B6 causes peripheral neuropathy. This
gate makes that class of defect impossible to ship silently.

Design choices:
  * Only ``verified`` (publication-ready) entries are gated. Suppressed entries
    (unverified / needs_revision / rejected) are allowed to still contain
    defects — that is why they are suppressed.
  * ULs are the STRICTER of the US IOM and EFSA adult values: a safety gate
    should be conservative. Nutrients with no established UL (B12, potassium,
    vitamin K, CoQ10) are omitted.
  * A supra-UL dose is permitted only with an explicit ``dose_exemption`` — the
    human reviewer's assertion that the dose is a deliberate supervised choice
    (e.g. isoniazid + pyridoxine, methotrexate folate rescue).
"""

import json
import os
import re

# (limit, unit) — stricter of IOM / EFSA adult UL. Unit is the nutrient's native
# label as it appears in recommendation copy.
_UL = {
    "vitamin_b6": (12, "mg"),  # EFSA 2023 (stricter than IOM 100 mg); neuropathy
    "folate": (1000, "mcg"),  # IOM UL, synthetic folic acid
    "magnesium": (350, "mg"),  # IOM supplemental UL
    "calcium": (2000, "mg"),  # IOM UL (adults 51+)
    "iron": (45, "mg"),  # IOM UL
    "vitamin_d": (100, "mcg"),  # IOM UL (= 4000 IU)
    "zinc": (40, "mg"),  # IOM UL
    "niacin": (35, "mg"),  # IOM UL, nicotinic acid
}

_EXEMPTIONS = {
    "clinician_directed",
    "deficiency_treatment",
    "deficiency_prevention",
    "pregnancy",
    "oncology",
    "nephrology",
}

# User-visible fields that can carry a numeric dose recommendation.
_DOSE_FIELDS = (
    "recommendation",
    "alert_body",
    "monitoring_note",
    "monitoring_tip_short",
    "acknowledgement_note",
)

_NUM = r"(\d[\d,]*(?:\.\d+)?)"


def _max_dose(text, unit):
    """Largest dose in ``text`` expressed in ``unit`` ('mg' or 'mcg'). For a mcg
    target, IU amounts are converted (1 mcg = 40 IU) so vitamin D dosed in IU is
    still caught. Returns None when no matching dose is present."""
    if not text:
        return None
    best = None
    for m in re.finditer(_NUM + r"\s*" + unit + r"\b", text, re.I):
        v = float(m.group(1).replace(",", ""))
        best = v if best is None else max(best, v)
    if unit == "mcg":  # vitamin D is commonly written in IU
        for m in re.finditer(_NUM + r"\s*iu\b", text, re.I):
            v = float(m.group(1).replace(",", "")) / 40.0
            best = v if best is None else max(best, v)
    return best


def _load_depletions():
    path = os.path.join(
        os.path.dirname(__file__), os.pardir, "data", "medication_depletions.json"
    )
    with open(path, encoding="utf-8") as f:
        return json.load(f)["depletions"]


def test_dose_parser_selfcheck():
    assert _max_dose("25–50 mg of B6", "mg") == 50
    assert _max_dose("1,000 mcg/day", "mcg") == 1000
    assert _max_dose("1,000–2,000 IU vitamin D3", "mcg") == 50  # 2000 IU
    assert _max_dose("take it 4 hours apart", "mg") is None


def test_no_publication_ready_entry_recommends_above_ul():
    violations = []
    for e in _load_depletions():
        if e.get("citation_review_status") != "verified":
            continue
        if e.get("dose_exemption") in _EXEMPTIONS:
            continue
        cid = (e.get("depleted_nutrient") or {}).get("canonical_id")
        if cid not in _UL:
            continue
        limit, unit = _UL[cid]
        for field in _DOSE_FIELDS:
            dose = _max_dose(e.get(field) or "", unit)
            if dose is not None and dose > limit:
                violations.append(
                    f"{e['id']}: {field} recommends {dose:g} {unit} "
                    f"> UL {limit} {unit} ({cid}) — cut the dose or add a "
                    f"justified dose_exemption"
                )
    assert not violations, "\n  " + "\n  ".join(violations)
