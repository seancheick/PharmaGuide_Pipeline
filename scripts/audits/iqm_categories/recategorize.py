#!/usr/bin/env python3
"""
IQM category_enum cleanup — recategorize misfiled 'other' entries.

Audit findings (2026-04-30): of the 616 IQM parents, 77 are in
category_enum='other'. Inspection revealed clear misclassifications —
chondroitin/glucosamine should be `fibers` (glycosaminoglycans);
collagen/keratin should be `proteins`; chlorella/spirulina/colostrum
are `functional_foods`; etc.

Conservative scope: only obvious reclassifications backed by the
canonical 12-value enum (amino_acids, antioxidants, enzymes,
fatty_acids, fibers, functional_foods, herbs, minerals, other,
probiotics, proteins, vitamins). Ambiguous entries (hormones,
nucleotides, organic acids, sulfur compounds) STAY in 'other' — the
'other' bucket is legitimate for entries that don't cleanly fit the
12 buckets.

Idempotent.
"""

import argparse, json, sys
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "ingredient_quality_map.json"

# IQM parent_id → new category_enum (only confident reclassifications).
RECATEGORIZE = {
    # other → functional_foods (whole-food / fermented / algal)
    "apple_cider_vinegar":       "functional_foods",
    "coconut_water":             "functional_foods",
    "chlorella":                 "functional_foods",
    "spirulina":                 "functional_foods",
    "brewers_yeast":             "functional_foods",
    "colostrum":                 "functional_foods",
    "irish_sea_moss":            "functional_foods",
    "yeast_fermentate":          "functional_foods",
    "rice_bran":                 "functional_foods",
    "cgf":                       "functional_foods",
    "touchi_extract":            "functional_foods",

    # other → proteins (clear protein / protein-derivative)
    "collagen":                  "proteins",
    "casein_hydrolysate":        "proteins",
    "keratin":                   "proteins",

    # other → fibers (glycosaminoglycan / polysaccharide / prebiotic)
    "prebiotics":                "fibers",
    "oligosaccharides":          "fibers",
    "chondroitin":               "fibers",
    "hyaluronic_acid":           "fibers",
    "glucosamine":               "fibers",
    "inositol_hexaphosphate":    "fibers",

    # other → fatty_acids (clear lipid / phospholipid / bile acid)
    "palmitic_acid":             "fatty_acids",
    "lecithin":                  "fatty_acids",
    "phosphatidylethanolamine":  "fatty_acids",
    "alpha_gpc":                 "fatty_acids",
    "d_beta_hydroxybutyrate_bhb": "fatty_acids",
    "tudca":                     "fatty_acids",

    # other → minerals
    "bentonite":                 "minerals",

    # other → amino_acids (clear amino-derivative)
    "creatine_monohydrate":      "amino_acids",
    "choline":                   "amino_acids",
    "paba":                      "amino_acids",
    "spermidine":                "amino_acids",

    # other → vitamins (vitamin B3 / NAD+ family)
    "nicotinamide_riboside":     "vitamins",
    "nmn":                       "vitamins",

    # other → antioxidants (established antioxidant phytochemicals)
    "urolithin_a":               "antioxidants",
    "diindolylmethane":          "antioxidants",

    # other → herbs (plant-derived alkaloids)
    "caffeine":                  "herbs",
    "theophylline":              "herbs",
    "xanthines":                 "herbs",
    "methylliberine":            "herbs",
    "berberine_supplement":      "herbs",
    "synephrine":                "herbs",

    # Round 2 (2026-04-30) — second-pass audit on remaining 'other' bucket

    # other → proteins
    "apoaequorin":               "proteins",        # jellyfish photoprotein

    # other → vitamins (B-vitamin family / NAD precursors)
    "inositol":                  "vitamins",        # formerly vit B8
    "nad_precursors":            "vitamins",        # NAD+ = B3 family

    # other → functional_foods
    "sea_cucumber":              "functional_foods", # marine functional food

    # other → minerals
    "humic_acid":                "minerals",         # humic substance / soil mineral
    "shuddha_laksha":            "minerals",         # Ayurvedic mineral preparation

    # other → amino_acids (amine / amino-derivative compounds)
    "dmae":                      "amino_acids",      # dimethylaminoethanol
    "phenylethylamine":          "amino_acids",      # PEA — amino acid metabolite
    "same":                      "amino_acids",      # S-adenosyl-methionine
    "centrophenoxine":           "amino_acids",      # DMAE ester (meclofenoxate)

    # other → antioxidants
    "ipriflavone":               "antioxidants",     # isoflavone
    "raspberry_ketones":         "antioxidants",     # phenolic ketone

    # other → fibers
    "d_mannose":                 "fibers",           # FDA dietary fiber (UTI use)
}

VALID_CATEGORIES = {
    "amino_acids", "antioxidants", "enzymes", "fatty_acids",
    "fibers", "functional_foods", "herbs", "minerals",
    "other", "probiotics", "proteins", "vitamins",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    # Validate target categories
    bad_targets = [(k, v) for k, v in RECATEGORIZE.items() if v not in VALID_CATEGORIES]
    if bad_targets:
        print(f"FATAL: target categories not in canonical 12: {bad_targets}", file=sys.stderr)
        return 2

    with open(DATA_PATH) as f:
        data = json.load(f)

    changes = []
    not_found = []
    for parent_id, new_cat in RECATEGORIZE.items():
        if parent_id not in data:
            not_found.append(parent_id)
            continue
        entry = data[parent_id]
        if not isinstance(entry, dict):
            print(f"FATAL: {parent_id} is not a dict", file=sys.stderr)
            return 2
        cur = entry.get("category_enum")
        if cur != new_cat:
            changes.append((parent_id, cur, new_cat))
            entry["category_enum"] = new_cat

    if not_found:
        print(f"WARNING: {len(not_found)} parent_ids not found in IQM:")
        for n in not_found:
            print(f"  {n}")

    if not changes:
        print("IQM recategorization already applied — no-op.")
        return 0

    print(f"IQM recategorization applying {len(changes)} change(s):")
    for pid, old, new in changes:
        print(f"  {pid:35} {old} → {new}")

    if args.dry_run:
        print(f"\n[dry-run] would write {DATA_PATH}")
        return 0

    # Bump _metadata.last_updated
    if isinstance(data.get("_metadata"), dict):
        data["_metadata"]["last_updated"] = "2026-04-30"

    with open(DATA_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"\nWrote {DATA_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
