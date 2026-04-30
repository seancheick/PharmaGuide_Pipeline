#!/usr/bin/env python3
"""
Phase 6 — V1.1 attributes layer scaffolding.

Per CLINICIAN_REVIEW.md Section 6: introduces the `attributes` object
on entries across all 3 reference files. The attributes object describes
what an ingredient IS or how it was made (vs `functional_roles[]` which
describes what it DOES).

V1 deterministic population (this commit):

  botanical_ingredients.json (all 459):
    attributes.source_origin     — derived from `category` field
                                    (root/herb/fruit/leaf → plant;
                                    mushroom/fungus → fungal;
                                    seaweed/algae → algal; honey → animal)

  harmful_additives.json:
    attributes.is_animal_derived — true on entries clearly animal-sourced
                                    (carmine/cochineal, glandular)

  other_ingredients.json:
    attributes.is_branded_complex — true on entries flagged is_active_only
                                     AND with brand-pattern name (BioCell,
                                     Tonalin, AstraGin, etc.)

V1.1 follow-up batches will populate the remaining attributes
(caramel_class, e171_eu_concern, is_synthetic_form, flavor_source,
colorant_source) per per-entry clinician spot-check.

Schema bumps:
  harmful_additives.json:    5.3.0 → 5.4.0
  other_ingredients.json:    5.3.0 → 5.4.0
  botanical_ingredients.json: 5.1.0 → 5.2.0

Idempotent.
"""

import argparse, json, sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[3]
DATA = SCRIPTS_DIR / "data"
HA_PATH = DATA / "harmful_additives.json"
OI_PATH = DATA / "other_ingredients.json"
BOT_PATH = DATA / "botanical_ingredients.json"


# ---------------------------------------------------------------------------
# Botanical source_origin derivation from category
# ---------------------------------------------------------------------------

BOT_CATEGORY_TO_SOURCE_ORIGIN = {
    "root": "plant", "herb": "plant", "fruit": "plant", "leaf": "plant",
    "seed": "plant", "bark": "plant", "vegetable": "plant",
    "flower": "plant", "grain": "plant", "botanical": "plant",
    "spice": "plant", "grass": "plant", "resin": "plant", "berry": "plant",
    "essential oil": "plant", "legume": "plant", "oil": "plant",
    "heartwood": "plant", "tuber": "plant", "stem": "plant",
    "bulb": "plant", "rhizome": "plant", "succulent": "plant",
    "whole_plant": "plant", "fiber": "plant", "protein": "plant",
    # Non-plant
    "mushroom": "fungal", "fungus": "fungal", "lichen": "fungal",
    "seaweed": "algal", "algae": "algal",
    # Animal-sourced
    "honey": "animal",
    # Skip ambiguous
    # "unspecified" → leave attributes empty
}


# ---------------------------------------------------------------------------
# Harmful additives — animal-derived entries (clear cases)
# ---------------------------------------------------------------------------

HA_ANIMAL_DERIVED_IDS = {
    "ADD_CARMINE_RED",       # cochineal insect extract
}

# Entries with caramel_class attribute (clinician 4F V1.1 spec)
HA_CARAMEL_CLASS_IDS = {
    "ADD_CARAMEL_COLOR": None,   # null = pending per-class data; B1 logic fires on iii/iv
}

# E171 concern flag (TiO2-related)
# TiO2 itself is in banned_recalled_ingredients.json, not harmful_additives.
# This attribute would surface on any future entries that mention TiO2.


# ---------------------------------------------------------------------------
# Other ingredients — branded-complex detection (name pattern)
# ---------------------------------------------------------------------------

# Brand markers that strongly suggest is_branded_complex=true
BRAND_MARKERS = {
    "biocell", "tonalin", "astragin", "alphasize", "bergapure", "lactospore",
    "verisol", "fortigel", "naturalslim", "longvida", "meriva", "sensoril",
    "ksm-66", "ksm66", "shoden", "goji", "wildbrine", "pomella", "trubrain",
    "carnosyn", "creapure", "biosora", "bioperine", "albion", "chelazome",
    "ferrochel", "magnesium glycinate", "calcium hmb", "perluxan", "univestin",
    "5-loxin", "aprésflex", "boswellin", "uc-ii", "type ii collagen",
    "purelean", "thermodiamine", "advantra-z", "p-synephrine",
    "calmaluna", "fibroprotect", "neumentix", "nuegg", "phytocannabinoid",
    "perilla", "corosolic", "glucohelp", "glucotrim", "fenfuro", "fenugreek 50",
    "satiereal", "saffron extract", "affron", "celluactiv", "rhodiolife",
    "spectrazyme", "zeolite",
}


def _is_branded_complex(entry: dict) -> bool:
    """Heuristic: branded if (1) flagged is_active_only AND (2) name matches
    a known brand marker, OR (3) the entry id starts with a known brand prefix."""
    if not entry.get("is_active_only"):
        return False
    name = (entry.get("standard_name") or "").lower()
    aliases = " ".join((entry.get("aliases") or [])).lower()
    blob = f"{name} {aliases}"
    for marker in BRAND_MARKERS:
        if marker in blob:
            return True
    return False


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


def _apply_botanicals():
    with open(BOT_PATH) as f:
        data = json.load(f)
    arr = data["botanical_ingredients"]
    changes = 0
    for e in arr:
        cat = (e.get("category") or "").lower().strip()
        origin = BOT_CATEGORY_TO_SOURCE_ORIGIN.get(cat)
        if not origin:
            continue   # unspecified → leave attributes absent
        cur_attrs = e.get("attributes") or {}
        if cur_attrs.get("source_origin") != origin:
            cur_attrs["source_origin"] = origin
            e["attributes"] = cur_attrs
            changes += 1
    return data, arr, changes, BOT_PATH


def _apply_harmful_additives():
    with open(HA_PATH) as f:
        data = json.load(f)
    arr = data["harmful_additives"]
    changes = 0
    for e in arr:
        eid = e.get("id", "")
        cur_attrs = e.get("attributes") or {}
        if eid in HA_ANIMAL_DERIVED_IDS:
            if cur_attrs.get("is_animal_derived") is not True:
                cur_attrs["is_animal_derived"] = True
                e["attributes"] = cur_attrs
                changes += 1
        if eid in HA_CARAMEL_CLASS_IDS:
            target = HA_CARAMEL_CLASS_IDS[eid]
            # We want explicit null in JSON for "pending per-product"
            if "caramel_class" not in cur_attrs:
                cur_attrs["caramel_class"] = target
                e["attributes"] = cur_attrs
                changes += 1
    return data, arr, changes, HA_PATH


def _apply_other_ingredients():
    with open(OI_PATH) as f:
        data = json.load(f)
    arr = data["other_ingredients"]
    changes = 0
    for e in arr:
        cur_attrs = e.get("attributes") or {}
        is_branded = _is_branded_complex(e)
        # Only set attribute when true (lean schema — no false-default bloat)
        if is_branded:
            if cur_attrs.get("is_branded_complex") is not True:
                cur_attrs["is_branded_complex"] = True
                e["attributes"] = cur_attrs
                changes += 1
    return data, arr, changes, OI_PATH


def _bump_metadata(data, new_version, change_summary):
    md = data.get("_metadata", {})
    cur = md.get("schema_version", "")
    if cur != new_version:
        md["schema_version"] = new_version
    md["last_updated"] = "2026-04-30"
    if "field_contract_changes" not in md:
        md["field_contract_changes"] = {}
    md["field_contract_changes"][f"v{new_version}"] = change_summary
    data["_metadata"] = md


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    total_changes = 0
    files_to_write = []

    for fn, label, target_version, summary in [
        (_apply_botanicals,         "botanical_ingredients", "5.2.0",
         "2026-04-30 Phase 6 — V1.1 attributes scaffolding. Added attributes "
         "object with source_origin populated on all entries (plant/fungal/"
         "algal/animal derived from category)."),
        (_apply_harmful_additives,  "harmful_additives",     "5.4.0",
         "2026-04-30 Phase 6 — V1.1 attributes scaffolding. Added attributes "
         "object with is_animal_derived (Carmine cochineal) and caramel_class "
         "= null (Caramel Color, pending per-class data per CLINICIAN_REVIEW "
         "Section 4F)."),
        (_apply_other_ingredients,  "other_ingredients",     "5.4.0",
         "2026-04-30 Phase 6 — V1.1 attributes scaffolding. Added attributes "
         "object with is_branded_complex on heuristic-detected branded "
         "ingredient complexes (BioCell, Tonalin, AstraGin, etc.) — those "
         "flagged is_active_only AND with brand-marker name patterns."),
    ]:
        data, arr, changes, path = fn()
        print(f"{label:<24} changes: {changes:3d}")
        total_changes += changes
        if changes:
            _bump_metadata(data, target_version, summary)
            files_to_write.append((path, data))

    if total_changes == 0:
        print("Phase 6 already applied — no-op.")
        return 0

    if args.dry_run:
        print(f"\n[dry-run] would write {len(files_to_write)} files")
        return 0

    for path, data in files_to_write:
        with open(path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
