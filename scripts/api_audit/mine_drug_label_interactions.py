#!/usr/bin/env python3
"""
mine_drug_label_interactions.py — Extract supplement-drug interaction mentions
from FDA drug labels (SPL/Structured Product Labeling).

Scans the `drug_interactions` and `warnings` sections of FDA-approved drug
labels for mentions of dietary supplement ingredients. Produces a candidates
review file for manual verification — NOT auto-imported per project rules.

Usage:
    # Process all downloaded partitions
    python3 scripts/api_audit/mine_drug_label_interactions.py

    # Process a single partition
    python3 scripts/api_audit/mine_drug_label_interactions.py --file drug-label-0001-of-0013.json

Output:
    scripts/reports/drug_label_interaction_candidates.json

Source: FDA OpenFDA bulk download → /drug/label
"""

import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
LABELS_DIR = DATA_DIR / "fda_drug_labels"
REPORTS_DIR = SCRIPT_DIR.parent / "reports"
IQM_PATH = DATA_DIR / "ingredient_quality_map.json"
RULES_PATH = DATA_DIR / "ingredient_interaction_rules.json"
OUTPUT_PATH = REPORTS_DIR / "drug_label_interaction_candidates.json"

# ---------------------------------------------------------------------------
# Supplement search terms — mapped to IQM canonical_ids
# ---------------------------------------------------------------------------

# Multi-word terms first (longest match)
SUPPLEMENT_TERMS = [
    ("st. john's wort", "st_johns_wort"),
    ("st john's wort", "st_johns_wort"),
    ("st. john", "st_johns_wort"),
    ("st john", "st_johns_wort"),
    ("green tea", "green_tea_extract"),
    ("fish oil", "fish_oil_omega3"),
    ("omega-3 fatty acid", "fish_oil_omega3"),
    ("omega-3", "fish_oil_omega3"),
    ("coenzyme q10", "coq10"),
    ("coenzyme q-10", "coq10"),
    ("coq10", "coq10"),
    ("ginkgo biloba", "ginkgo_biloba"),
    ("ginkgo", "ginkgo_biloba"),
    ("saw palmetto", "saw_palmetto"),
    ("milk thistle", "milk_thistle"),
    ("black cohosh", "black_cohosh"),
    ("evening primrose", "evening_primrose_oil"),
    ("dong quai", "dong_quai"),
    ("vitamin k", "vitamin_k"),
    ("vitamin e", "vitamin_e"),
    ("vitamin c", "vitamin_c"),
    ("vitamin d", "vitamin_d"),
    ("vitamin a", "vitamin_a"),
    ("vitamin b6", "vitamin_b6_pyridoxine"),
    ("vitamin b12", "vitamin_b12_cobalamin"),
    ("folic acid", "vitamin_b9_folate"),
    ("alpha lipoic acid", "alpha_lipoic_acid"),
    ("red yeast rice", "red_yeast_rice"),
    ("bitter orange", "bitter_orange"),
    ("white willow", "white_willow_bark"),
    ("horse chestnut", "horse_chestnut"),
    ("black seed oil", "black_seed_oil"),
    ("grape seed", "grape_seed_extract"),
    ("l-carnitine", "l_carnitine"),
    ("dietary supplement", "_generic_supplement"),
    ("herbal product", "_generic_herbal"),
    ("herbal supplement", "_generic_herbal"),
    ("botanical", "_generic_botanical"),
    ("natural product", "_generic_natural"),
    # Single-word terms
    ("garlic", "garlic"),
    ("ginger", "ginger"),
    ("ginseng", "ginseng"),
    ("turmeric", "turmeric"),
    ("curcumin", "turmeric"),
    ("echinacea", "echinacea"),
    ("valerian", "valerian"),
    ("kava", "kava"),
    ("kratom", "kratom"),
    ("cannabidiol", "cbd"),
    ("ashwagandha", "ashwagandha"),
    ("melatonin", "melatonin"),
    ("glucosamine", "glucosamine"),
    ("chondroitin", "chondroitin"),
    ("calcium", "calcium"),
    ("magnesium", "magnesium"),
    ("iron", "iron"),
    ("zinc", "zinc"),
    ("potassium", "potassium"),
    ("selenium", "selenium"),
    ("chromium", "chromium"),
    ("berberine", "berberine"),
    ("quercetin", "quercetin"),
    ("resveratrol", "resveratrol"),
    ("fenugreek", "fenugreek"),
    ("goldenseal", "goldenseal"),
    ("licorice", "licorice"),
    ("psyllium", "psyllium"),
    ("probiotics", "probiotics"),
    ("biotin", "vitamin_b7_biotin"),
    ("niacin", "vitamin_b3_niacin"),
]


def _extract_context(text, term, window=200):
    """Extract text window around a term mention."""
    idx = text.lower().find(term.lower())
    if idx < 0:
        return ""
    start = max(0, idx - window // 2)
    end = min(len(text), idx + len(term) + window // 2)
    snippet = text[start:end].strip()
    # Clean up whitespace
    snippet = re.sub(r"\s+", " ", snippet)
    return snippet


def process_partition(filepath):
    """Process a single drug label partition file. Returns list of candidate hits."""
    with open(filepath) as f:
        data = json.load(f)

    results = data.get("results", [])
    candidates = []

    for record in results:
        # Get drug info
        openfda = record.get("openfda", {})
        brand_names = openfda.get("brand_name", [])
        generic_names = openfda.get("generic_name", [])
        drug_name = (brand_names[0] if brand_names else
                     generic_names[0] if generic_names else "unknown")
        generic_name = generic_names[0] if generic_names else ""

        # Get rxcuis for cross-referencing
        rxcuis = openfda.get("rxcui", [])
        pharm_classes = openfda.get("pharm_class_epc", [])

        # Combine interaction + warning text
        di_text = " ".join(record.get("drug_interactions", []))
        warn_text = " ".join(record.get("warnings", []))
        combined = di_text + " " + warn_text

        if len(combined.strip()) < 20:
            continue

        combined_lower = combined.lower()

        # Search for supplement mentions
        found_terms = set()
        for term, canon_id in SUPPLEMENT_TERMS:
            if canon_id.startswith("_generic"):
                continue  # skip generic terms for candidate extraction
            if term in combined_lower and canon_id not in found_terms:
                found_terms.add(canon_id)
                context = _extract_context(combined, term)
                source_section = "drug_interactions" if term in di_text.lower() else "warnings"
                candidates.append({
                    "supplement_canonical_id": canon_id,
                    "supplement_term_matched": term,
                    "drug_name": drug_name,
                    "drug_generic": generic_name[:100],
                    "drug_rxcuis": rxcuis[:3],
                    "drug_pharm_classes": pharm_classes[:3],
                    "source_section": source_section,
                    "context": context[:500],
                    "label_set_id": record.get("set_id", ""),
                })

    return candidates


def aggregate_candidates(all_candidates):
    """Aggregate candidates by supplement, dedup by drug generic name."""
    by_supplement = defaultdict(list)
    for c in all_candidates:
        by_supplement[c["supplement_canonical_id"]].append(c)

    aggregated = {}
    for canon_id, hits in sorted(by_supplement.items(), key=lambda x: -len(x[1])):
        # Dedup by generic drug name
        seen_drugs = set()
        unique_hits = []
        for h in hits:
            drug_key = h["drug_generic"].lower().strip() or h["drug_name"].lower().strip()
            if drug_key not in seen_drugs:
                seen_drugs.add(drug_key)
                unique_hits.append(h)

        aggregated[canon_id] = {
            "canonical_id": canon_id,
            "total_label_mentions": len(hits),
            "unique_drugs_mentioning": len(unique_hits),
            "drug_examples": [
                {
                    "drug": h["drug_name"],
                    "generic": h["drug_generic"],
                    "rxcuis": h["drug_rxcuis"],
                    "pharm_classes": h["drug_pharm_classes"],
                    "section": h["source_section"],
                    "context": h["context"],
                }
                for h in unique_hits[:20]  # cap examples at 20
            ],
        }

    return aggregated


def load_existing_rules():
    """Load existing interaction rules to identify gaps."""
    if not RULES_PATH.exists():
        return set()
    with open(RULES_PATH) as f:
        data = json.load(f)
    # Rules use subject_ref.canonical_id — normalize to IQM-style canonical_id
    covered = set()
    for r in data.get("interaction_rules", data.get("rules", [])):
        # Try subject_ref.canonical_id first
        subj = r.get("subject_ref", {})
        cid = subj.get("canonical_id", "")
        if cid:
            # Normalize: "RULE_GINKGO_BILOBA_..." → "ginkgo_biloba"
            # The canonical_id in rules may be uppercase or have prefixes
            covered.add(cid.lower())
        # Also try the rule id pattern: RULE_{INGREDIENT}_...
        rule_id = r.get("id", "")
        if rule_id.startswith("RULE_"):
            parts = rule_id.replace("RULE_", "").split("_")
            # Try progressive joins to find the ingredient portion
            for i in range(1, min(4, len(parts) + 1)):
                candidate = "_".join(parts[:i]).lower()
                covered.add(candidate)
    return covered


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Mine FDA drug labels for supplement interactions")
    parser.add_argument("--file", help="Process a single partition file")
    args = parser.parse_args()

    REPORTS_DIR.mkdir(exist_ok=True)

    if args.file:
        files = [Path(args.file)]
    else:
        files = sorted(LABELS_DIR.glob("drug-label-*.json"))
        if not files:
            # Try unzipped files
            zips = sorted(LABELS_DIR.glob("drug-label-*.json.zip"))
            if zips:
                print(f"Found {len(zips)} zip files — unzipping first...")
                import zipfile
                for zp in zips:
                    with zipfile.ZipFile(zp) as zf:
                        zf.extractall(LABELS_DIR)
                files = sorted(LABELS_DIR.glob("drug-label-*.json"))

    if not files:
        print("ERROR: No drug label files found.")
        print(f"Download from: https://download.open.fda.gov/drug/label/")
        print(f"Place in: {LABELS_DIR}/")
        sys.exit(1)

    print(f"Processing {len(files)} partition(s)...")
    all_candidates = []
    for i, filepath in enumerate(files, 1):
        print(f"  [{i}/{len(files)}] {filepath.name}...", end=" ", flush=True)
        hits = process_partition(filepath)
        print(f"{len(hits)} hits")
        all_candidates.extend(hits)

    print(f"\nTotal raw hits: {len(all_candidates)}")

    # Aggregate
    aggregated = aggregate_candidates(all_candidates)
    print(f"Unique supplements mentioned: {len(aggregated)}")

    # Cross-reference with existing rules
    existing_rules = load_existing_rules()
    new_candidates = {k: v for k, v in aggregated.items() if k not in existing_rules}
    already_covered = {k: v for k, v in aggregated.items() if k in existing_rules}

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    output = {
        "_metadata": {
            "generated_at": now,
            "source": "FDA drug labels (SPL) bulk download",
            "partitions_processed": len(files),
            "total_raw_hits": len(all_candidates),
            "unique_supplements": len(aggregated),
            "new_candidates": len(new_candidates),
            "already_in_rules": len(already_covered),
            "note": "REVIEW FILE — NOT auto-imported. Each candidate must be manually verified before adding to curated_interactions.json.",
        },
        "new_candidates": new_candidates,
        "already_covered": {k: {"unique_drugs": v["unique_drugs_mentioning"]} for k, v in already_covered.items()},
    }

    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nWrote: {OUTPUT_PATH}")

    # Summary
    print(f"\n=== Summary ===")
    print(f"Supplements mentioned in FDA drug labels: {len(aggregated)}")
    print(f"Already in our interaction rules: {len(already_covered)}")
    print(f"NEW candidates (not in rules): {len(new_candidates)}")
    print(f"\n=== Top 15 new candidates by drug label mentions ===")
    for canon_id, data in sorted(new_candidates.items(), key=lambda x: -x[1]["unique_drugs_mentioning"])[:15]:
        print(f"  {canon_id}: {data['unique_drugs_mentioning']} unique drugs mention it")


if __name__ == "__main__":
    main()
