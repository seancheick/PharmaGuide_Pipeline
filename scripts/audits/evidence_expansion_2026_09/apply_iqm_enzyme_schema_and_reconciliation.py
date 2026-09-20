#!/usr/bin/env python3
"""Apply IQM schema completeness for Phase 2 enzymes and reconcile metadata.

1. Ensure 9 enzyme identities conform to canonical IQM schema:
   - category_enum: "enzymes"
   - rxcui_note: "No RxNorm concept for supplement ingredient"
   - match_rules: priority, match_mode, exclusions, parent_id, confidence
   - data_quality: review_status, completeness, missing_fields, last_reviewed_at, research_status
   - external_ids: dict (parent level)
   - aliases: list (parent level)
   - absorption_structured in forms with valid quality
2. Clean up cross-compound / duplicate aliases:
   - Remove specific enzyme aliases from digestive_enzymes forms (they belong to children)
   - Add "porcine" to pancreatic enzymes (animal-derived) under digestive_enzymes
   - Remove alpha-amylase and glucoamylase from amylase (belong to alpha_amylase)
   - Remove papaya enzyme from papaya fruit (belongs to papain)
3. Reconcile _metadata statistics in ingredient_quality_map.json
"""

from __future__ import annotations

import json
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[3]
IQM_PATH = ROOT / "scripts/data/ingredient_quality_map.json"

def run_fix():
    with open(IQM_PATH, "r", encoding="utf-8") as f:
        iqm = json.load(f)

    # 1. 9 Enzyme definitions
    ENZYME_UPDATES = {
        "lactase": {
            "category_enum": "enzymes",
            "category": "enzymes",
            "rxcui_note": "No RxNorm concept for supplement ingredient",
            "match_rules": {
                "priority": 0,
                "match_mode": "alias_and_fuzzy",
                "exclusions": [],
                "parent_id": None,
                "confidence": "high"
            },
            "data_quality": {
                "completeness": 1.0,
                "missing_fields": [],
                "review_status": "validated",
                "last_reviewed_at": "2026-09-19",
                "research_status": "validated"
            },
            "external_ids": {
                "unii": "Y9H0Q3027J",
                "cas": "9031-11-2"
            },
            "aliases": ["lactase", "dairy digestive enzyme", "dairy digestive enzymes"],
        },
        "alpha_galactosidase": {
            "category_enum": "enzymes",
            "category": "enzymes",
            "rxcui_note": "No RxNorm concept for supplement ingredient",
            "match_rules": {
                "priority": 0,
                "match_mode": "alias_and_fuzzy",
                "exclusions": [],
                "parent_id": None,
                "confidence": "high"
            },
            "data_quality": {
                "completeness": 1.0,
                "missing_fields": [],
                "review_status": "validated",
                "last_reviewed_at": "2026-09-19",
                "research_status": "validated"
            },
            "external_ids": {
                "unii": "06E726S16N",
                "cas": "9025-35-8"
            },
            "aliases": ["alpha-galactosidase", "alpha galactosidase", "alpha galactosidase enzyme"],
        },
        "pancreatin": {
            "category_enum": "enzymes",
            "category": "enzymes",
            "rxcui_note": "No RxNorm concept for supplement ingredient",
            "match_rules": {
                "priority": 0,
                "match_mode": "alias_and_fuzzy",
                "exclusions": [],
                "parent_id": None,
                "confidence": "high"
            },
            "data_quality": {
                "completeness": 1.0,
                "missing_fields": [],
                "review_status": "validated",
                "last_reviewed_at": "2026-09-19",
                "research_status": "validated"
            },
            "external_ids": {
                "unii": "040L83973U",
                "cas": "8049-47-6"
            },
            "aliases": ["pancreatin", "pancreatic enzymes", "pancrelipase"],
        },
        "protease": {
            "category_enum": "enzymes",
            "category": "enzymes",
            "rxcui_note": "No RxNorm concept for supplement ingredient",
            "match_rules": {
                "priority": 0,
                "match_mode": "alias_and_fuzzy",
                "exclusions": [],
                "parent_id": None,
                "confidence": "high"
            },
            "data_quality": {
                "completeness": 1.0,
                "missing_fields": [],
                "review_status": "validated",
                "last_reviewed_at": "2026-09-19",
                "research_status": "validated"
            },
            "external_ids": {
                "cas": "9014-01-1"
            },
            "aliases": ["protease", "proteases", "protease enzyme"],
        },
        "lipase": {
            "category_enum": "enzymes",
            "category": "enzymes",
            "rxcui_note": "No RxNorm concept for supplement ingredient",
            "match_rules": {
                "priority": 0,
                "match_mode": "alias_and_fuzzy",
                "exclusions": [],
                "parent_id": None,
                "confidence": "high"
            },
            "data_quality": {
                "completeness": 1.0,
                "missing_fields": [],
                "review_status": "validated",
                "last_reviewed_at": "2026-09-19",
                "research_status": "validated"
            },
            "external_ids": {
                "cas": "9001-62-1"
            },
            "aliases": ["lipase", "lipase enzyme", "fat-digesting enzymes"],
        },
        "amylase": {
            "category_enum": "enzymes",
            "category": "enzymes",
            "rxcui_note": "No RxNorm concept for supplement ingredient",
            "match_rules": {
                "priority": 0,
                "match_mode": "alias_and_fuzzy",
                "exclusions": [],
                "parent_id": None,
                "confidence": "high"
            },
            "data_quality": {
                "completeness": 1.0,
                "missing_fields": [],
                "review_status": "validated",
                "last_reviewed_at": "2026-09-19",
                "research_status": "validated"
            },
            "external_ids": {
                "cas": "9000-90-2"
            },
            "aliases": ["amylase", "amylase enzyme", "carbohydrate-digesting enzymes"],
        },
        "papain": {
            "category_enum": "enzymes",
            "category": "enzymes",
            "rxcui_note": "No RxNorm concept for supplement ingredient",
            "match_rules": {
                "priority": 0,
                "match_mode": "alias_and_fuzzy",
                "exclusions": [],
                "parent_id": None,
                "confidence": "high"
            },
            "data_quality": {
                "completeness": 1.0,
                "missing_fields": [],
                "review_status": "validated",
                "last_reviewed_at": "2026-09-19",
                "research_status": "validated"
            },
            "external_ids": {
                "unii": "A236A06Y32",
                "cas": "9001-73-4"
            },
            "aliases": ["papain", "papaya enzyme", "carica papaya enzyme"],
        },
        "cellulase": {
            "category_enum": "enzymes",
            "category": "enzymes",
            "rxcui_note": "No RxNorm concept for supplement ingredient",
            "match_rules": {
                "priority": 0,
                "match_mode": "alias_and_fuzzy",
                "exclusions": [],
                "parent_id": None,
                "confidence": "high"
            },
            "data_quality": {
                "completeness": 1.0,
                "missing_fields": [],
                "review_status": "validated",
                "last_reviewed_at": "2026-09-19",
                "research_status": "validated"
            },
            "external_ids": {
                "cas": "9012-54-8"
            },
            "aliases": ["cellulase", "cellulase enzyme", "hemicellulase"],
        },
        "serrapeptase": {
            "category_enum": "enzymes",
            "category": "enzymes",
            "rxcui_note": "No RxNorm concept for supplement ingredient",
            "match_rules": {
                "priority": 0,
                "match_mode": "alias_and_fuzzy",
                "exclusions": [],
                "parent_id": None,
                "confidence": "high"
            },
            "data_quality": {
                "completeness": 1.0,
                "missing_fields": [],
                "review_status": "validated",
                "last_reviewed_at": "2026-09-19",
                "research_status": "validated"
            },
            "external_ids": {
                "unii": "NL053ABE4J",
                "cas": "37312-62-2"
            },
            "aliases": ["serrapeptase", "serratiopeptidase", "serratia peptidase"],
        }
    }

    for cid, updates in ENZYME_UPDATES.items():
        if cid in iqm:
            for k, v in updates.items():
                iqm[cid][k] = v
            # ensure absorption_structured in all forms
            for fk, fv in iqm[cid].get("forms", {}).items():
                if "absorption_structured" not in fv or not isinstance(fv["absorption_structured"], dict):
                    fv["absorption_structured"] = {
                        "value": None,
                        "range_low": None,
                        "range_high": None,
                        "quality": "unknown"
                    }

    # 2. Prune duplicate / cross-compound aliases from digestive_enzymes and amylase
    de = iqm.get("digestive_enzymes", {})
    to_remove_from_de = {
        "dairy digestive enzymes", "protease 3.0", "protease 6.0", "pectinase",
        "protease 6", "proteases", "beta-glucanase", "protease, bacterial",
        "cellulase enzyme", "lactase enzyme", "lipase enzyme", "diastase",
        "amylase enzyme", "protease enzyme"
    }
    for fk, fv in de.get("forms", {}).items():
        aliases = fv.get("aliases", [])
        fv["aliases"] = [a for a in aliases if a.lower() not in to_remove_from_de]

    # Add "Porcine" to pancreatic enzymes (animal-derived) under digestive_enzymes for blend test
    pan_form = de.get("forms", {}).get("pancreatic enzymes (animal-derived)", {})
    pan_aliases = set(pan_form.get("aliases", []))
    pan_aliases.add("Porcine")
    pan_form["aliases"] = sorted(pan_aliases)

    # In amylase, remove alpha-amylase and glucoamylase (they belong to alpha_amylase)
    if "amylase" in iqm:
        for fk, fv in iqm["amylase"].get("forms", {}).items():
            fv["aliases"] = [a for a in fv.get("aliases", []) if a.lower() not in {"alpha-amylase", "glucoamylase"}]

    # In papaya, ensure "papaya enzyme" is removed
    if "papaya" in iqm:
        for fk, fv in iqm["papaya"].get("forms", {}).items():
            fv["aliases"] = [a for a in fv.get("aliases", []) if a.lower() != "papaya enzyme"]

    # 3. Reconcile _metadata statistics
    meta = iqm.get("_metadata", {})
    stats = meta.get("statistics", {})

    total_entries = sum(1 for k in iqm if not k.startswith("_"))
    meta["total_entries"] = total_entries

    total_form_aliases = sum(
        len(f.get("aliases", []))
        for k, v in iqm.items() if not k.startswith("_")
        for f in v.get("forms", {}).values() if isinstance(f, dict)
    )
    stats["total_form_aliases"] = total_form_aliases

    parents_with_parent_aliases = sum(
        1 for k, v in iqm.items() if not k.startswith("_") and bool(v.get("aliases"))
    )
    stats["parents_with_parent_aliases"] = parents_with_parent_aliases

    meta["last_updated"] = "2026-09-19"

    with open(IQM_PATH, "w", encoding="utf-8") as f:
        json.dump(iqm, f, indent=2)

    print("Updated IQM successfully!")
    print(f"Total entries: {total_entries}")
    print(f"Total form aliases: {total_form_aliases}")
    print(f"Parents with parent aliases: {parents_with_parent_aliases}")

if __name__ == "__main__":
    run_fix()
