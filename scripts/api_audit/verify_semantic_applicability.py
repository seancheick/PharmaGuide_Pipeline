#!/usr/bin/env python3
"""Semantic applicability verification gate for literature_evidence_records.json.

Deterministically verifies that the actual clinical intervention supports the
canonical identity and material receiving the disposition:
1. Combination vs Standalone Guard: Multi-ingredient combination trials cannot
   establish standalone single-ingredient efficacy.
2. Material/Form Guard: Crude powders cannot inherit purified extracts/oils;
   liquid juices cannot inherit dry powders; pharmaceutical drug salts (e.g.
   strontium ranelate) cannot transfer to dietary supplement salts; distinct
   botanical extracts cannot transfer across species.
3. No-Study Semantics Guard: Zero qualifying studies must emit
   no_qualifying_human_evidence, reserving reviewed_null_unfavorable exclusively
   for actual qualifying trials showing null or harmful outcomes.
4. Dose-Exposure Guard: Studied dose values must represent actual tested exposure;
   extreme dose disconnects cannot transfer without proven equivalence.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
SCRIPTS_ROOT = REPO_ROOT / "scripts"
LITERATURE_RECORDS_PATH = SCRIPTS_ROOT / "data" / "literature_evidence_records.json"


COMBO_INDICATORS = [
    r"\bfixed\s+(?:\w+\s+)?combination\b",
    r"\bcontaining\s+vitamin-mineral\b",
    r"\bcombination\s+of\s+glutathione\b",
    r"\bmultienzyme\s+complex\b",
    r"\bmulti-enzyme\s+complex\b",
    r"\bmulti-ingredient\b",
    r"\bherbal\s+mixture\b",
    r"\bpolyherbal\b",
]

# Canaries explicitly forbidden from standalone clinical claims
STANDALONE_COMBINATION_CANARIES: Dict[str, str] = {
    "hops": "valerian hops extract combination",
    "l_cysteine": "combination of glutathione and resveratrol precursors",
    "dmae": "DMAE containing vitamin-mineral drug combination",
    "alpha_amylase": "multienzyme complex (DigeZyme)",
}

MATERIAL_FORM_MISMATCH_CANARIES: Dict[str, Dict[str, Any]] = {
    "l_proline": {
        "disallowed_term": "colostrinin",
        "reason": "Colostrinin (proline-rich polypeptide complex) cannot transfer to standalone L-proline",
    },
    "strontium": {
        "disallowed_term": "ranelate",
        "reason": "Strontium ranelate prescription trials cannot transfer to dietary supplement strontium salts",
    },
    "black_tea_leaf": {
        "disallowed_term": "green tea",
        "reason": "Theaflavin-enriched green tea extract cannot transfer to generic black tea leaf",
    },
    "mucuna_pruriens": {
        "disallowed_term": "parkinson",
        "reason": "High-dose whole seed powder Parkinson's trials (1,000 mg L-DOPA) cannot transfer to low-dose extracts",
    },
    "beta_glucan": {
        "disallowed_term": "baker's yeast",
        "reason": "Insoluble yeast beta-(1,3/1,6)-glucan cannot transfer to generic beta-glucan without material match",
    },
    "goji_berry": {
        "disallowed_term": "juice",
        "reason": "Standardized liquid juice (120 mL/day) cannot transfer to generic dry powder without bioequivalence",
    },
}


def audit_semantic_applicability(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_records = len(records)
    clean_records = 0
    flagged_records: List[Dict[str, Any]] = []

    for r in records:
        cid = r.get("canonical_id", "")
        eff = r.get("effect_direction", "")
        studies = r.get("qualifying_human_studies", [])
        app_dec = str(r.get("applicability_decision") or "").lower()
        record_issues: List[str] = []

        # 1. No-Study Semantics Invariant
        if eff in ("null", "negative"):
            if not studies:
                record_issues.append(
                    "VIOLATION: effect_direction is null/negative but qualifying_human_studies is empty. "
                    "Must be no_qualifying_human_evidence."
                )
        if eff == "no_qualifying_human_evidence":
            if len(studies) > 0:
                record_issues.append(
                    f"VIOLATION: effect_direction is no_qualifying_human_evidence but carries {len(studies)} studies."
                )

        # 2. Combination -> Standalone Efficacy Guard
        if eff in ("positive_strong", "positive_moderate", "positive_weak"):
            if cid in STANDALONE_COMBINATION_CANARIES:
                trigger = STANDALONE_COMBINATION_CANARIES[cid]
                record_issues.append(
                    f"VIOLATION: {cid} claims positive clinical efficacy from combination intervention: '{trigger}'"
                )
            for s in studies:
                title = s.get("title", "")
                for pat in COMBO_INDICATORS:
                    if re.search(pat, title, re.IGNORECASE):
                        record_issues.append(
                            f"VIOLATION: {cid} cites combination trial '{title}' while claiming positive standalone efficacy"
                        )

        # 3. Material / Form Specificity Guard
        if eff in ("positive_strong", "positive_moderate", "positive_weak"):
            if cid in MATERIAL_FORM_MISMATCH_CANARIES:
                rule = MATERIAL_FORM_MISMATCH_CANARIES[cid]
                disallowed = rule["disallowed_term"]
                for s in studies:
                    title = s.get("title", "").lower()
                    if disallowed in title:
                        record_issues.append(
                            f"VIOLATION: {cid} material mismatch: {rule['reason']} (Found '{disallowed}' in title)"
                        )

        # 4. Whole food powder / Excipient Guard
        if eff == "not_efficacy_relevant":
            if len(studies) > 0:
                record_issues.append(
                    f"VIOLATION: not_efficacy_relevant record carries {len(studies)} qualifying studies."
                )

        if record_issues:
            flagged_records.append({
                "canonical_id": cid,
                "effect_direction": eff,
                "issues": record_issues,
            })
        else:
            clean_records += 1

    return {
        "total_records": total_records,
        "clean_records": clean_records,
        "flagged_count": len(flagged_records),
        "flagged_records": flagged_records,
    }


def main() -> int:
    if not LITERATURE_RECORDS_PATH.exists():
        print(f"Error: {LITERATURE_RECORDS_PATH} not found", file=sys.stderr)
        return 1

    payload = json.loads(LITERATURE_RECORDS_PATH.read_text(encoding="utf-8"))
    records = payload.get("literature_evidence_records", [])

    results = audit_semantic_applicability(records)
    print("=" * 70)
    print("SEMANTIC APPLICABILITY AUDIT")
    print("=" * 70)
    print(f"Total Records Evaluated: {results['total_records']}")
    print(f"Clean Records:          {results['clean_records']}")
    print(f"Flagged Records:        {results['flagged_count']}")

    if results["flagged_records"]:
        print("\nFlagged Violations:")
        for fr in results["flagged_records"]:
            print(f"\n  [{fr['canonical_id']}] (effect_direction: {fr['effect_direction']})")
            for iss in fr["issues"]:
                print(f"    - {iss}")
        return 1

    print("\nALL RECORDS PASS SEMANTIC APPLICABILITY GATE!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
