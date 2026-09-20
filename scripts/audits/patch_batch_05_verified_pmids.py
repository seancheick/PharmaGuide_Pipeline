#!/usr/bin/env python3
"""Patch verified canonical PMIDs for Batch 5 records."""
from __future__ import annotations

import json
from pathlib import Path

RECORDS_PATH = Path("scripts/data/literature_evidence_records.json")

PATCHES = {
    "citrus_bergamot": {
        "pmid": "30501605",
        "title": "Hypoglycemic and Hypolipemic Effects of a New Lecithin Formulation of Bergamot Polyphenolic Fraction: A Double Blind, Randomized, Placebo- Controlled Study.",
        "effect_direction": "positive_moderate",
    },
    "african_mango": {
        "pmid": "19254366",
        "title": "IGOB131, a novel seed extract of the West African plant Irvingia gabonensis, significantly reduces body weight and improves metabolic parameters in overweight humans in a randomized double-blind placebo controlled investigation.",
        "effect_direction": "positive_moderate",
    },
    "olive_fruit_extract": {
        "pmid": "23516412",
        "title": "Olive (Olea europaea L.) leaf polyphenols improve insulin sensitivity in middle-aged overweight men: a randomized, placebo-controlled, crossover trial.",
        "effect_direction": "positive_moderate",
    },
    "policosanol": {
        "pmid": "16705107",
        "title": "Effect of policosanol on lipid levels among patients with hypercholesterolemia or combined hyperlipidemia: a randomized controlled trial.",
        "effect_direction": "null",
    },
    "deer_antler_velvet": {
        "pmid": "14669926",
        "title": "The effects of deer antler velvet extract or powder supplementation on aerobic power, erythropoiesis, and muscular strength and endurance characteristics.",
        "effect_direction": "null",
    },
    "evening_primrose": {
        "qualifying_human_studies": [],
        "effect_direction": "applicability_unestablished",
        "applicability_status": "crude_material_lacks_standardization",
        "applicability_decision": "Crude evening primrose powder lacks standardized gamma-linolenic acid (GLA) oil extraction; clinical Cochrane trials for eczema showed null efficacy.",
    },
}


def main():
    data = json.loads(RECORDS_PATH.read_text(encoding="utf-8"))
    records = data["literature_evidence_records"]

    for r in records:
        cid = r["canonical_id"]
        if cid in PATCHES:
            patch = PATCHES[cid]
            if "pmid" in patch:
                studies = r.get("qualifying_human_studies", [])
                if studies:
                    studies[0]["pmid"] = patch["pmid"]
                    studies[0]["title"] = patch["title"]
                    studies[0]["effect_direction"] = patch["effect_direction"]
                r["effect_direction"] = patch["effect_direction"]
            elif "qualifying_human_studies" in patch:
                r["qualifying_human_studies"] = patch["qualifying_human_studies"]
                r["effect_direction"] = patch["effect_direction"]
                r["applicability_status"] = patch["applicability_status"]
                r["applicability_decision"] = patch["applicability_decision"]
            print(f"Patched {cid}")

    RECORDS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Done patching.")


if __name__ == "__main__":
    main()
