#!/usr/bin/env python3
"""
standardized_botanicals.json — category cleanup (V1.1 sub-task 5b.1).

Per V1_1_ROADMAP.md §5b.1: 41 of 239 entries (17%) carry non-botanical
plant-part categories. Three actions per entry:

  A. RENAME (19 entries) — entry IS a botanical extract; rename
     category to the source plant part (fruit/seed_fruit/root/bark/
     leaf/tuber/berry).

  B. KEEP AS 'standardized' (4 entries) — branded extracts with
     insufficient public data on source/standardization. Defer per-
     entry to clinician.

  C. FLAG FOR RELOCATION (18 entries) — entries that aren't really
     botanicals (mineral chelates, amino acids, fatty acids, proteins,
     enzymes, fibers, hormones). Mark with
     attributes.is_misclassified_in_botanicals: true for V1.1 physical
     relocation to the appropriate ref file (IQM amino_acids/minerals/
     fatty_acids/proteins/fibers/enzymes/other).

Idempotent.
"""

import argparse, json, sys
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "standardized_botanicals.json"


# ---------------------------------------------------------------------------
# Category A: rename to plant-part (19 entries)
# ---------------------------------------------------------------------------

RENAME = {
    # Black pepper — peppercorns are dried fruit; convention is seed_fruit
    "black_pepper_extract":     "seed_fruit",
    # Grape seed extracts (Vitis vinifera)
    "cognigrape":               "seed_fruit",
    "enovita":                  "seed_fruit",
    "grape_seed_extract":       "seed_fruit",
    "proanthoplex":             "seed_fruit",
    # Cranberry (Vaccinium macrocarpon)
    "cran_max":                 "fruit",
    "cranrx":                   "fruit",
    "pacran":                   "fruit",
    # Citrus / berry / coffee fruit
    "morosil":                  "fruit",          # Moro blood orange
    "neurofactor":              "fruit",          # whole coffee fruit
    "optiberry":                "berry",          # multi-berry blend
    "slimbione":                "fruit",          # bitter melon (Momordica charantia)
    # Rhizomes / roots
    "curcumin":                 "root",           # turmeric (Curcuma longa) rhizome
    "enxtra":                   "root",           # Alpinia galanga rhizome
    "gingerols":                "root",           # ginger (Zingiber officinale) rhizome
    "shogaols":                 "root",           # ginger rhizome
    # Leaves
    "ginkgolides":              "leaf",           # Ginkgo biloba leaf
    # Bark
    "pine_bark_extract":        "bark",           # Pinus pinaster bark
    # Tuber
    "slendesta":                "tuber",          # potato (Solanum tuberosum) protein extract
}

# ---------------------------------------------------------------------------
# Category C: flag for V1.1 relocation (18 entries)
# Each entry gets attributes.is_misclassified_in_botanicals: true
# AND attributes.target_ref_file = "<filename>" hint for V1.1 work.
# ---------------------------------------------------------------------------

RELOCATE = {
    # Amino acids → ingredient_quality_map.json (amino_acids bucket)
    "alphawave_l_theanine":     "ingredient_quality_map.json (amino_acids)",
    "cognizin_citicoline":      "ingredient_quality_map.json (amino_acids)",
    "setria":                   "ingredient_quality_map.json (amino_acids)",
    # Minerals → IQM minerals
    "chromax":                  "ingredient_quality_map.json (minerals)",
    "fruitex_b_calcium_fructoborate": "ingredient_quality_map.json (minerals)",
    "sunactive_iron":           "ingredient_quality_map.json (minerals)",
    "thermosil":                "ingredient_quality_map.json (minerals)",
    # Fatty acids → IQM fatty_acids
    "levagen":                  "ingredient_quality_map.json (fatty_acids)",
    "life_s_dha":               "ingredient_quality_map.json (fatty_acids)",
    "phosphatidylserine":       "ingredient_quality_map.json (fatty_acids)",
    # Proteins → IQM proteins
    "keraglo":                  "ingredient_quality_map.json (proteins)",
    "uniflex":                  "ingredient_quality_map.json (proteins)",
    # Enzymes → IQM enzymes
    "bromelain":                "ingredient_quality_map.json (enzymes)",
    # Functional foods → IQM functional_foods
    "epicor":                   "ingredient_quality_map.json (functional_foods)",
    # Fibers → IQM fibers
    "wellmune":                 "ingredient_quality_map.json (fibers)",
    # Hormones → IQM other (hormones legitimately stay in 'other')
    "microactive_melatonin":    "ingredient_quality_map.json (other — hormones)",
    # D-mannose → DUPLICATE of IQM fibers; remove from this file in V1.1
    "d_mannose":                "DUPLICATE — already in ingredient_quality_map.json (fibers)",
    # Proprietary blend → keep as 'blend' (no clean target file)
    "organic_gold_standard_potentiating_nutrients":
        "BLEND — proprietary, defer per-entry analysis",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(DATA_PATH) as f:
        data = json.load(f)
    arr = data["standardized_botanicals"]
    by_id = {e["id"]: e for e in arr}

    rename_changes = []
    flag_changes = []

    # Category A — rename
    for eid, new_cat in RENAME.items():
        if eid not in by_id:
            print(f"WARNING: rename target {eid} not found", file=sys.stderr)
            continue
        e = by_id[eid]
        cur = e.get("category")
        if cur != new_cat:
            rename_changes.append((eid, cur, new_cat))
            e["category"] = new_cat

    # Category C — flag for relocation
    for eid, hint in RELOCATE.items():
        if eid not in by_id:
            print(f"WARNING: relocate target {eid} not found", file=sys.stderr)
            continue
        e = by_id[eid]
        attrs = e.get("attributes") or {}
        if (attrs.get("is_misclassified_in_botanicals") is not True
                or attrs.get("v1_1_relocation_target") != hint):
            attrs["is_misclassified_in_botanicals"] = True
            attrs["v1_1_relocation_target"] = hint
            e["attributes"] = attrs
            flag_changes.append((eid, hint))

    total = len(rename_changes) + len(flag_changes)
    if total == 0:
        print("standardized_botanicals cleanup already applied — no-op.")
        return 0

    print(f"Renaming {len(rename_changes)} entries to plant-part categories:")
    for eid, old, new in rename_changes:
        print(f"  {eid:42} {old} → {new}")
    print(f"\nFlagging {len(flag_changes)} entries for V1.1 relocation:")
    for eid, hint in flag_changes:
        print(f"  {eid:42} → {hint}")

    if args.dry_run:
        print(f"\n[dry-run] would write {DATA_PATH}")
        return 0

    md = data.get("_metadata", {})
    md["last_updated"] = "2026-04-30"
    data["_metadata"] = md

    with open(DATA_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"\nWrote {DATA_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
