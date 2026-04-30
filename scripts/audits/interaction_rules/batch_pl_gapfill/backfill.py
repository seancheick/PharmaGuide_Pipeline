#!/usr/bin/env python3
"""
Pregnancy/Lactation hybrid gap-fill (clinician-locked plan, 2026-04-30).

Section 3 of INTERACTION_RULES_REVIEW.md — fills empty pregnancy_lactation
slots with a clinician-locked hybrid policy:

  Option A (bulk-default `monitor`):
    Low-risk, well-studied nutrients at RDA-range doses:
    - Standard B-complex vitamins
    - Vitamin C, D (<2000 IU), E (at RDA)
    - Standard minerals at RDA range
    - Established-safety probiotic strains
    - Single-ingredient amino acids at typical doses
    Auto-note: "No severe pregnancy-specific evidence; talk to your clinician."

  Option B (banned/recalled subjects):
    Default `contraindicated` in pregnancy regardless of mechanism.

  Option C (default for everything else):
    pregnancy_category = lactation_category = "no_data"
    notes = "Limited data — discuss with your healthcare provider before use
             during pregnancy or breastfeeding."

Schema additions (clinician-locked):
  evidence_level: "no_data" | "limited" | "moderate" | "strong"
    distinguishes "we have data, default is monitor" from "we have no data,
    monitor is a safety posture".

Idempotent: only fills empty/no_data slots. Pre-existing pregnancy data
(from W/M/L/C batch + earlier curation) is preserved.
"""

from __future__ import annotations
import argparse, json, sys
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[3] / "data" / "ingredient_interaction_rules.json"


# Option A — RDA-range low-risk nutrients (bulk-default monitor)
# Identified by canonical_id; excludes high-dose-only forms and aminos
# flagged by clinician (5-HTP, tryptophan, tyrosine).
OPTION_A_LOW_RISK = {
    # B-complex vitamins
    "thiamine", "vitamin_b1", "riboflavin", "vitamin_b2",
    "niacin", "niacinamide", "vitamin_b3",
    "pantothenic_acid", "vitamin_b5",
    "vitamin_b6", "pyridoxine", "p5p", "pyridoxal_5_phosphate",
    "biotin", "vitamin_b7",
    "folate", "folic_acid", "methylfolate",
    "vitamin_b12", "cobalamin", "methylcobalamin", "cyanocobalamin",
    "choline",
    # Vitamins (RDA-range)
    "vitamin_c", "ascorbic_acid",
    "vitamin_d", "vitamin_d3", "cholecalciferol",  # at <2000 IU; flag dose
    "vitamin_e",  # already populated for some forms
    # Minerals (RDA-range)
    "calcium", "magnesium", "zinc", "potassium", "phosphorus",
    "manganese", "molybdenum", "chromium", "selenium", "copper",
    # Amino acids at typical doses (excluding clinician-flagged serotonergics)
    "leucine", "isoleucine", "valine", "lysine", "histidine",
    "arginine", "glutamine", "glycine", "taurine", "carnitine",
    "n_acetyl_cysteine", "nac",
    # Probiotics (genus-level safety established)
    "lactobacillus", "bifidobacterium", "saccharomyces_boulardii",
}

# Option B — high-priority targeted: banned/recalled subjects → contraindicated
# Applied via subject_ref.db == "banned_recalled_ingredients" check.

# Option C — default for everything else
OPTION_C_NOTE = (
    "Limited data — discuss with your healthcare provider before use during "
    "pregnancy or breastfeeding."
)
OPTION_C_HEADLINE = "Limited safety data"
OPTION_C_BODY = (
    "There isn't enough specific safety data to give a confident recommendation "
    "for pregnancy or breastfeeding. Talk to your obstetrician or pediatrician "
    "before using this supplement."
)
OPTION_C_INFO_NOTE = (
    "Pregnancy/lactation safety data is limited — clinician guidance recommended."
)

OPTION_A_NOTE = (
    "No severe pregnancy-specific evidence at RDA-range doses; talk to your "
    "clinician before use, especially at higher doses."
)
OPTION_A_HEADLINE = "Standard nutrient — clinician guidance suggested"
OPTION_A_BODY = (
    "At RDA-range doses, this nutrient has no specific pregnancy or lactation "
    "concerns. Higher therapeutic doses may have a different safety profile — "
    "talk to your clinician."
)
OPTION_A_INFO_NOTE = (
    "RDA-range standard nutrient — generally compatible with pregnancy and "
    "lactation; high-dose forms have separate evidence bases."
)

OPTION_B_NOTE = (
    "Banned/recalled or high-risk substance — avoid in pregnancy regardless of "
    "underlying mechanism."
)
OPTION_B_HEADLINE = "Do not use in pregnancy"
OPTION_B_BODY = (
    "This substance is banned, recalled, or high-risk and should not be used "
    "during pregnancy or breastfeeding under any circumstances."
)
OPTION_B_INFO_NOTE = (
    "Banned/recalled or high-risk substance — pregnancy default is contraindicated."
)


def is_empty(value) -> bool:
    return value in (None, "", "no_data")


def set_if_diff(pl: dict, key: str, new_value):
    """Set pl[key]=new_value only if it actually differs. Returns True on change."""
    if pl.get(key) != new_value:
        pl[key] = new_value
        return True
    return False


def classify(rule_obj) -> str:
    """Return 'A' (low-risk default monitor), 'B' (banned default contraindicated), or 'C' (no_data)."""
    sref = rule_obj.get("subject_ref", {})
    db = sref.get("db")
    cid = (sref.get("canonical_id") or "").lower()

    if db == "banned_recalled_ingredients":
        return "B"
    if cid in OPTION_A_LOW_RISK:
        return "A"
    return "C"


def fill_pregnancy_lactation(pl: dict, classification: str) -> bool:
    """Populate empty fields based on classification. Returns True if changed."""
    changed = False
    if classification == "A":
        if is_empty(pl.get("pregnancy_category")):
            pl["pregnancy_category"] = "monitor"
            changed = True
        if is_empty(pl.get("lactation_category")):
            pl["lactation_category"] = "monitor"
            changed = True
        if is_empty(pl.get("evidence_level")):
            pl["evidence_level"] = "limited"
            changed = True
        if is_empty(pl.get("notes")):
            pl["notes"] = OPTION_A_NOTE
            changed = True
        if is_empty(pl.get("alert_headline")):
            pl["alert_headline"] = OPTION_A_HEADLINE
            changed = True
        if is_empty(pl.get("alert_body")):
            pl["alert_body"] = OPTION_A_BODY
            changed = True
        if is_empty(pl.get("informational_note")):
            pl["informational_note"] = OPTION_A_INFO_NOTE
            changed = True

    elif classification == "B":
        if is_empty(pl.get("pregnancy_category")):
            pl["pregnancy_category"] = "contraindicated"
            changed = True
        if is_empty(pl.get("lactation_category")):
            pl["lactation_category"] = "avoid"
            changed = True
        if is_empty(pl.get("evidence_level")):
            pl["evidence_level"] = "moderate"
            changed = True
        if is_empty(pl.get("notes")):
            pl["notes"] = OPTION_B_NOTE
            changed = True
        if is_empty(pl.get("alert_headline")):
            pl["alert_headline"] = OPTION_B_HEADLINE
            changed = True
        if is_empty(pl.get("alert_body")):
            pl["alert_body"] = OPTION_B_BODY
            changed = True
        if is_empty(pl.get("informational_note")):
            pl["informational_note"] = OPTION_B_INFO_NOTE
            changed = True

    else:  # C
        if pl.get("pregnancy_category") in (None, ""):
            pl["pregnancy_category"] = "no_data"
            changed = True
        if pl.get("lactation_category") in (None, ""):
            pl["lactation_category"] = "no_data"
            changed = True
        if pl.get("evidence_level") in (None, ""):
            pl["evidence_level"] = "no_data"
            changed = True
        if is_empty(pl.get("notes")):
            pl["notes"] = OPTION_C_NOTE
            changed = True
        if is_empty(pl.get("alert_headline")):
            pl["alert_headline"] = OPTION_C_HEADLINE
            changed = True
        if is_empty(pl.get("alert_body")):
            pl["alert_body"] = OPTION_C_BODY
            changed = True
        if is_empty(pl.get("informational_note")):
            pl["informational_note"] = OPTION_C_INFO_NOTE
            changed = True

    if "sources" not in pl:
        pl["sources"] = []
        changed = True
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(DATA_PATH) as f:
        data = json.load(f)
    rules = data["interaction_rules"]

    by_class = {"A": 0, "B": 0, "C": 0}
    changed_count = 0

    for r in rules:
        pl = r.get("pregnancy_lactation") or {}
        r["pregnancy_lactation"] = pl
        cls = classify(r)
        if fill_pregnancy_lactation(pl, cls):
            changed_count += 1
            by_class[cls] += 1

    md = data.setdefault("_metadata", {})
    md["last_updated"] = "2026-04-30"
    if "schema_version" in md and md["schema_version"] < "5.3.0":
        md["schema_version"] = "5.3.0"
    md.setdefault("pregnancy_lactation_evidence_levels",
                  ["no_data", "limited", "moderate", "strong"])

    print(f"Rules updated:           {changed_count} / {len(rules)}")
    print(f"  Option A (low-risk):   {by_class['A']}")
    print(f"  Option B (banned):     {by_class['B']}")
    print(f"  Option C (no_data):    {by_class['C']}")

    if args.dry_run:
        print("\n[dry-run] would write changes")
        return 0

    with open(DATA_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"\nWrote {DATA_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
