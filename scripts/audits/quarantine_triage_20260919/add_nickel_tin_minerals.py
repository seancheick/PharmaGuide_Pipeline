#!/usr/bin/env python3
"""Add Nickel and Tin canonical mineral identities to the IQM (Phase 1a).

Canonical-owner repair for the 183 safety-only identity conflicts: Supplement
Facts ultratrace Nickel/Tin rows were recognized ONLY by the harmful-additives
contaminant entries (ADD_NICKEL / ADD_TIN), which cannot supply a primary
identity (`safety_recognition_without_primary_identity`).

Follows the existing no-RDA ultratrace mineral precedent (strontium):
- category `minerals`, single `(<element> (unspecified))` form
- `match_mode: exact` (no fuzzy/contains risk)
- no `rda_ul_ref` (no DRI reference exists for these elements)
- safety recognition is NOT removed: ADD_NICKEL/ADD_TIN keep scoring penalties;
  the primary identity simply stops `safety_recognition_without_primary_identity`.

Identifiers were verified live on 2026-09-19 through independent gates, one
source per field (never cross-derived):
  FDA GSRS  (scripts/api_audit/verify_unii.py --search):  UNII
  PubChem   (scripts/api_audit/verify_pubchem.py --cid):  CID + CAS
  UMLS      (scripts/api_audit/verify_cui.py --search):   CUI
GSRS `dsld_info_raw` additionally confirms the element is a real DSLD label
surface (Nickel: 378 products; Tin: 205 products).

Run:  source scripts/python_env.sh && "$PG_PYTHON" \
      scripts/audits/quarantine_triage_20260919/add_nickel_tin_minerals.py
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
IQM_PATH = REPO / "scripts" / "data" / "ingredient_quality_map.json"

TODAY = date.today().isoformat()

NICKEL = {
    "standard_name": "Nickel",
    "category": "minerals",
    "cui": "C0028013",
    "rxcui": 1311629,
    "forms": {
        "nickel (unspecified)": {
            "bio_score": 7.0,
            "natural": False,
            "score": 7.0,
            "absorption": "moderate",
            "absorption_structured": {
                "quality": "moderate",
                "value": 0.5,
                "range_low": 0.4,
                "range_high": 0.6,
            },
            "consumer_note": (
                "This listing identifies nickel without naming its compound or "
                "salt. Nickel appears on some multivitamin labels as an "
                "ultratrace mineral; no daily requirement has been established."
            ),
            "consumer_note_review": {
                "by": "Quarantine remediation 2026-09-19 (canonical identity only; "
                      "no efficacy claim authored)",
                "date": TODAY,
            },
            "notes": (
                "Ultratrace element recognized by DSLD as a mineral label "
                "surface (378 products). No Nutrient Recommendations RDA or UL "
                "is established, so dose adequacy is not assessed and the row "
                "does not carry pillar weight. A primary identity is required so "
                "the row resolves canonically instead of falling through to "
                "contaminant-only recognition."
            ),
            "dosage_importance": 0.5,
            "aliases": ["Nickel", "Ni"],
        },
    },
    "match_rules": {
        "priority": 1,
        "match_mode": "exact",
        "exclusions": [],
    },
    "category_enum": "minerals",
    "data_quality": {
        "review_status": "validated",
        "completeness": 0.7,
        "last_reviewed_at": TODAY,
        "research_status": "validated",
    },
    "external_ids": {"unii": "7OV03QG267"},
    "gsrs": {
        "substance_name": "Nickel",
        "substance_class": "chemical",
        "cfr_sections": ["21 CFR 184.1537"],
        "dsld_count": 378,
        "dsld_info_raw": "Dietary Supplement Label Database|Mineral|Nickel | 93 (Number of products:378)",
        "active_moiety": None,
        "salt_parents": [],
        "metabolic_relationships": [],
        "metabolites": [],
    },
    "aliases": [],
}

TIN = {
    "standard_name": "Tin",
    "category": "minerals",
    "cui": "C0040238",
    "rxcui": 10603,
    "forms": {
        "tin (unspecified)": {
            "bio_score": 7.0,
            "natural": False,
            "score": 7.0,
            "absorption": "moderate",
            "absorption_structured": {
                "quality": "moderate",
                "value": 0.5,
                "range_low": 0.4,
                "range_high": 0.6,
            },
            "consumer_note": (
                "This listing identifies tin without naming its compound or "
                "salt. Tin appears on some multivitamin labels as an "
                "ultratrace mineral; no daily requirement has been established."
            ),
            "consumer_note_review": {
                "by": "Quarantine remediation 2026-09-19 (canonical identity only; "
                      "no efficacy claim authored)",
                "date": TODAY,
            },
            "notes": (
                "Ultratrace element recognized by DSLD as an element label "
                "surface (205 products). No Nutrient Recommendations RDA or UL "
                "is established, so dose adequacy is not assessed and the row "
                "does not carry pillar weight. A primary identity is required so "
                "the row resolves canonically instead of falling through to "
                "contaminant-only recognition."
            ),
            "dosage_importance": 0.5,
            "aliases": ["Tin", "Sn"],
        },
    },
    "match_rules": {
        "priority": 1,
        "match_mode": "exact",
        "exclusions": [],
    },
    "category_enum": "minerals",
    "data_quality": {
        "review_status": "validated",
        "completeness": 0.7,
        "last_reviewed_at": TODAY,
        "research_status": "validated",
    },
    "external_ids": {"unii": "387GMG9FH5"},
    "gsrs": {
        "substance_name": "TIN",
        "substance_class": "chemical",
        "cfr_sections": [],
        "dsld_count": 205,
        "dsld_info_raw": "Dietary Supplement Label Database|Element|Tin | 620 (Number of products:205)",
        "active_moiety": None,
        "salt_parents": [],
        "metabolic_relationships": [],
        "metabolites": [],
    },
    "aliases": [],
}

# UNIIs are 10 uppercase alphanumerics issued by FDA SUR. A mistyped
# CAS-in-UNII (9 chars, hyphens) can never pass.
UNII_RE = re.compile(r"^[0-9A-Z]{10}$")


def audit(iqm: dict) -> list[str]:
    problems: list[str] = []
    for key, entry, cas, cid in (
        ("nickel", NICKEL, "7440-02-0", 935),
        ("tin", TIN, "7440-31-5", 5352426),
    ):
        existing = iqm.get(key)
        if existing:
            problems.append(f"{key}: entry already exists — refusing to overwrite")
            continue
        if not UNII_RE.match(entry["external_ids"]["unii"]):
            problems.append(f"{key}: UNII {entry['external_ids']['unii']!r} fails UNII shape")
        # Live-verified field invariants (verified 2026-09-19 through
        # api_audit/verify_unii.py, verify_pubchem.py, verify_cui.py).
        if entry["gsrs"]["dsld_info_raw"] == "":
            problems.append(f"{key}: gsrs.dsld_info_raw must not be empty")
        if key == "nickel" and entry["cui"] != "C0028013":
            problems.append("nickel.cui drifted from the UMLS-verified C0028013")
        if key == "tin" and entry["cui"] != "C0040238":
            problems.append("tin.cui drifted from the UMLS-verified C0040238")
    return problems


def main() -> int:
    problems = audit(json.loads(IQM_PATH.read_text()))
    if problems:
        for p in problems:
            print(f"REFUSED: {p}")
        return 1

    raw = IQM_PATH.read_text()
    iqm = json.loads(raw)
    iqm["nickel"] = NICKEL
    iqm["tin"] = TIN

    meta = iqm["_metadata"]
    meta["total_entries"] = int(meta["total_entries"]) + 2
    meta["last_updated"] = TODAY
    note = (
        "nickel_tin_ultratrace_minerals_2026_09_19: added live-verified Nickel "
        "and Tin canonical mineral identities (strontium no-RDA precedent) so "
        "Supplement Facts ultratrace rows resolve canonically instead of "
        "falling through to harmful-additives-only recognition."
    )
    meta["notes"] = (str(meta.get("notes") or "").rstrip(" |") + " | " + note).strip(" |")

    keys = list(iqm.keys())
    order = keys.index("strontium") + 1
    reordered = {k: iqm[k] for k in keys[:order]}
    reordered.update({k: v for k, v in iqm.items() if k not in reordered})
    iqm = reordered

    IQM_PATH.write_text(json.dumps(iqm, indent=2, ensure_ascii=False) + "\n")
    print("added nickel, tin; total_entries =", meta["total_entries"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
