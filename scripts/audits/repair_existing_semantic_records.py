#!/usr/bin/env python3
"""Apply semantic applicability corrections to flagged records in literature_evidence_records.json."""
from __future__ import annotations

import json
from pathlib import Path

RECORDS_PATH = Path("scripts/data/literature_evidence_records.json")

CORRECTIONS = {
    "l_proline": {
        "effect_direction": "no_qualifying_human_evidence",
        "qualifying_human_studies": [],
        "applicability_decision": "Reproducible literature search identified no qualifying clinical efficacy trials for standalone oral L-proline supplementation (Colostrinin proline-rich polypeptide is not L-proline).",
        "applicability_status": "no_qualifying_trials_found",
    },
    "strontium": {
        "effect_direction": "applicability_unestablished",
        "applicability_decision": "Strontium ranelate prescription trials do not transfer to over-the-counter strontium dietary supplement salts (citrate/carbonate); clinical fracture reduction for supplement forms is unproven.",
        "applicability_status": "prescription_ranelate_cannot_transfer_to_supplement_salts",
    },
    "black_tea_leaf": {
        "effect_direction": "applicability_unestablished",
        "applicability_decision": "Theaflavin-enriched green tea extract trials do not transfer to crude black tea leaf powder without extraction and standardization equivalence.",
        "applicability_status": "green_tea_extract_cannot_transfer_to_black_tea",
    },
    "mucuna_pruriens": {
        "effect_direction": "applicability_unestablished",
        "applicability_decision": "Acute 15-30 g whole seed powder Parkinson's trials (1,000 mg L-DOPA) do not transfer to low-dose dietary supplement extracts without demonstration of clinical equivalence.",
        "applicability_status": "high_dose_powder_cannot_transfer_to_low_dose_extract",
    },
    "dmae": {
        "effect_direction": "applicability_unestablished",
        "applicability_decision": "Combination drug trials containing DMAE with vitamins and minerals do not establish standalone DMAE efficacy.",
        "applicability_status": "combination_drug_cannot_establish_standalone_efficacy",
    },
    "beta_glucan": {
        "effect_direction": "applicability_unestablished",
        "applicability_decision": "Baker's yeast beta-1,3/1,6-glucan evidence requires specific yeast insoluble glucan material disclosure; does not transfer to generic or oat/cereal beta-glucan.",
        "applicability_status": "yeast_beta_glucan_requires_material_specificity",
    },
    "goji_berry": {
        "effect_direction": "applicability_unestablished",
        "applicability_decision": "Liquid standardized Lycium barbarum juice (120 mL/day) trials do not transfer to generic dry fruit powder without bioequivalence.",
        "applicability_status": "liquid_juice_cannot_transfer_to_dry_powder",
    },
    "hops": {
        "effect_direction": "applicability_unestablished",
        "applicability_decision": "Valerian-hops fixed combination trials cannot establish standalone hops sedative efficacy.",
        "applicability_status": "fixed_combination_cannot_establish_standalone_efficacy",
    },
    "l_cysteine": {
        "effect_direction": "applicability_unestablished",
        "applicability_decision": "Multi-precursor combination trials do not isolate standalone L-cysteine clinical efficacy.",
        "applicability_status": "combination_precursor_cannot_establish_standalone_efficacy",
    },
    "alpha_amylase": {
        "effect_direction": "applicability_unestablished",
        "applicability_decision": "Multi-enzyme complex trials do not isolate standalone alpha-amylase clinical efficacy.",
        "applicability_status": "multi_enzyme_complex_cannot_establish_standalone_efficacy",
    },
}


def main():
    data = json.loads(RECORDS_PATH.read_text(encoding="utf-8"))
    records = data["literature_evidence_records"]

    corrected_count = 0
    for r in records:
        cid = r["canonical_id"]
        if cid in CORRECTIONS:
            patch = CORRECTIONS[cid]
            r["effect_direction"] = patch["effect_direction"]
            r["applicability_decision"] = patch["applicability_decision"]
            r["applicability_status"] = patch["applicability_status"]
            if "qualifying_human_studies" in patch:
                r["qualifying_human_studies"] = patch["qualifying_human_studies"]
            corrected_count += 1
            print(f"Patched {cid} -> {patch['effect_direction']}")

    data["_metadata"]["last_updated"] = "2026-09-20"
    RECORDS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Successfully patched {corrected_count} records.")


if __name__ == "__main__":
    main()
