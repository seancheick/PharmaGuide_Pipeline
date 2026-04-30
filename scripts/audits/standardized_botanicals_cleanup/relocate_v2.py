#!/usr/bin/env python3
"""
Phase §5b.1 completion — replace `is_misclassified_in_botanicals` flag
with explicit IQM parent cross-references on the 18 V1.1-flagged entries.

Why cross-reference instead of physical relocation:
- standardized_botanicals.json is the BONUS-AWARDING reference layer
  (match_ledger.py:463 — "bonus-only when label contains standardization
  evidence"). Physical relocation to IQM would change scoring behavior
  by making these entries contribute to core quality scores.
- 16 of 18 flagged entries DO have matching IQM parents (l_theanine,
  choline, glutathione, chromium, boron, iron, silicon, PEA, dha,
  phosphatidylserine, keratin, collagen, yeast_fermentate, beta_glucan,
  melatonin, d_mannose). Cross-referencing makes the relationship
  explicit without breaking the bonus layer.
- 2 entries have no IQM parent (bromelain, proprietary blend) — get
  explicit "no_iqm_parent" markers.

Net effect: standardized_botanicals.json is acknowledged as a "branded
standardized forms" reference (mixed botanical AND non-botanical),
with explicit cross-refs to IQM parents where they exist. The file's
purpose is clarified in _metadata.

Idempotent.
"""

import argparse, json, sys
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "standardized_botanicals.json"
IQM_PATH = Path(__file__).resolve().parents[2] / "data" / "ingredient_quality_map.json"


# Cross-ref mapping: standardized_botanical id → IQM parent id
IQM_PARENT_MAP = {
    "alphawave_l_theanine":             "l_theanine",
    "cognizin_citicoline":              "choline",
    "setria":                           "glutathione",
    "chromax":                          "chromium",
    "fruitex_b_calcium_fructoborate":   "boron",
    "sunactive_iron":                   "iron",
    "thermosil":                        "silicon",       # also matches 'silica'
    "levagen":                          "palmitoylethanolamide",
    "life_s_dha":                       "dha",
    "phosphatidylserine":               "phosphatidylserine",
    "keraglo":                          "keratin",
    "uniflex":                          "collagen",
    "epicor":                           "yeast_fermentate",
    "wellmune":                         "beta_glucan",
    "microactive_melatonin":            "melatonin",
    "d_mannose":                        "d_mannose",      # genuine duplicate
}

# Entries without an IQM parent — get explicit no-parent marker
NO_IQM_PARENT = {
    "bromelain":                                    "Pineapple enzyme — no IQM enzymes parent yet; consider adding for V1.1",
    "organic_gold_standard_potentiating_nutrients": "Proprietary blend — no clean parent target; defer per-entry analysis",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    # Verify IQM parents exist
    iqm = json.load(open(IQM_PATH))
    iqm_keys = set(iqm.keys())
    bad = [(eid, pid) for eid, pid in IQM_PARENT_MAP.items() if pid not in iqm_keys]
    if bad:
        print(f"FATAL: IQM parents not found for: {bad}", file=sys.stderr)
        return 2

    with open(DATA_PATH) as f:
        data = json.load(f)
    arr = data["standardized_botanicals"]
    by_id = {e["id"]: e for e in arr}

    cross_ref_count = 0
    no_parent_count = 0
    flag_removed = 0

    for eid, parent_id in IQM_PARENT_MAP.items():
        if eid not in by_id:
            print(f"WARNING: {eid} not in standardized_botanicals", file=sys.stderr)
            continue
        e = by_id[eid]
        attrs = e.get("attributes") or {}
        if attrs.get("iqm_parent_id") != parent_id:
            attrs["iqm_parent_id"] = parent_id
            cross_ref_count += 1
        # Remove the misclassified flag and the V1.1 hint
        if attrs.pop("is_misclassified_in_botanicals", None) is not None:
            flag_removed += 1
        attrs.pop("v1_1_relocation_target", None)
        e["attributes"] = attrs

    for eid, reason in NO_IQM_PARENT.items():
        if eid not in by_id:
            continue
        e = by_id[eid]
        attrs = e.get("attributes") or {}
        if attrs.get("no_iqm_parent_reason") != reason:
            attrs["no_iqm_parent_reason"] = reason
            no_parent_count += 1
        if attrs.pop("is_misclassified_in_botanicals", None) is not None:
            flag_removed += 1
        attrs.pop("v1_1_relocation_target", None)
        e["attributes"] = attrs

    if cross_ref_count == 0 and no_parent_count == 0 and flag_removed == 0:
        print("§5b.1 cross-refs already applied — no-op.")
        return 0

    print(f"§5b.1 completion:")
    print(f"  Added IQM parent cross-refs:  {cross_ref_count}")
    print(f"  Marked no-IQM-parent:         {no_parent_count}")
    print(f"  Removed 'misclassified' flag: {flag_removed}")

    if args.dry_run:
        print(f"\n[dry-run] would write {DATA_PATH}")
        return 0

    # Update file purpose in metadata to reflect broader scope
    md = data.get("_metadata", {})
    md["last_updated"] = "2026-04-30"
    purpose = md.get("purpose", "")
    new_purpose = (
        "Standardized branded forms reference (bonus-awarding layer per "
        "match_ledger.py — capped bonus when label shows standardization "
        "evidence). Holds plant-part botanicals AND non-botanical branded "
        "forms (amino acids, minerals, fatty acids, proteins, fibers, "
        "fermentates, hormones). Non-botanical entries cross-reference "
        "their matching IQM parent via attributes.iqm_parent_id."
    )
    if purpose != new_purpose:
        md["purpose"] = new_purpose
    data["_metadata"] = md

    with open(DATA_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"\nWrote {DATA_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
