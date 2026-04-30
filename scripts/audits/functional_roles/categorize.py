#!/usr/bin/env python3
"""
Deterministic category → functional_roles mapper for other_ingredients.json.

Implements the clinician-locked mapping table from CLINICIAN_REVIEW.md
Section 2B + the mechanical concatenation decomposition rule for the
132 long-tail single-occurrence categories.

Returns one of four actions per entry:
  - "assign"          : roles list to apply
  - "retire"          : entry is label noise / descriptor — assign []
  - "move_to_actives" : Phase 4 cleanup will physically relocate — assign []
  - "manual_review"   : per-entry clinician verification needed — assign []

Reused by all other_ingredients backfill batches (4-7).
Vocab-gated against functional_roles_vocab.json v1.0.0.
"""

import json
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2]  # scripts/
VOCAB_PATH = SCRIPTS_DIR / "data" / "functional_roles_vocab.json"


def load_vocab_ids() -> set:
    with open(VOCAB_PATH, encoding="utf-8") as f:
        return {r["id"] for r in json.load(f)["functional_roles"]}


# ---------------------------------------------------------------------------
# Direct category → roles map (clinician Section 2B, top 30)
# ---------------------------------------------------------------------------

DIRECT_MAP = {
    "oil_carrier":             ["carrier_oil"],
    "flavor_natural":          ["flavor_natural"],
    "emulsifier":              ["emulsifier"],
    "sweetener_natural":       ["sweetener_natural"],
    "colorant_natural":        ["colorant_natural"],
    "fiber_prebiotic":         ["filler", "prebiotic_fiber"],
    "flavoring":               ["flavor_natural"],   # default to natural per clinician (per-entry verifiable later)
    "thickener_stabilizer":    ["thickener", "stabilizer"],
    "coating":                 ["coating"],
    "filler_binder":           ["filler", "binder"],
    "filler":                  ["filler"],
    "solvent":                 ["solvent"],
    "processing_aid":          ["processing_aid"],
    "fiber_plant":             ["filler", "prebiotic_fiber"],
    "capsule_material":        ["coating", "gelling_agent"],
    "acidity_regulator":       ["ph_regulator"],
    "fat_oil":                 ["carrier_oil"],
    "carrier_oil":             ["carrier_oil"],
    "humectant":               ["humectant"],
    "preservative":            ["preservative"],
    "antioxidant":             ["antioxidant"],
    "preservative_antioxidant": ["preservative", "antioxidant"],
    "preservative_antimicrobial": ["preservative"],
    "lubricant":               ["lubricant"],
    "binder":                  ["binder"],
    "disintegrant":            ["disintegrant"],
    "glidant":                 ["glidant"],
    "anti_caking":             ["anti_caking_agent"],
    "anticaking_agent":        ["anti_caking_agent"],
    "anticaking_flow_agent":   ["anti_caking_agent", "glidant"],
    "flow_agent_anticaking":   ["glidant", "anti_caking_agent"],
    "flow_agent":              ["glidant"],
    "flow_agent_filler":       ["glidant", "filler"],
    "filler_fiber":            ["filler"],
    "binder_filler":           ["binder", "filler"],
    "buffering_agent":         ["ph_regulator"],
    "thickener":               ["thickener"],
    "stabilizer":              ["stabilizer"],
    "gelling_agent":           ["gelling_agent"],
    "gelling_agent_natural":   ["gelling_agent"],
    "gelling_agent_stabilizer": ["gelling_agent", "stabilizer"],
    "color_natural":           ["colorant_natural"],
    "natural_colorant":        ["colorant_natural"],
    "color_descriptor":        ["colorant_natural"],
    "color_blend_descriptor":  ["colorant_natural"],
    "color_mineral":           ["colorant_natural"],
    "colorant_mineral":        ["colorant_natural"],
    "colorant_opacifier":      ["colorant_natural"],
    "colorant_generic":        ["colorant_natural"],
    "filler_opacifier_colorant": ["filler", "colorant_natural"],
    "filler_sweetener":        ["filler", "sweetener_natural"],
    "sweetener_sugar_alcohol": ["sweetener_sugar_alcohol"],
    "preservative_natural":    ["preservative"],
    "humectant_solvent":       ["humectant", "solvent"],
    "humectant_preservative":  ["humectant", "preservative"],
    "binder_coating_thickener": ["binder", "coating", "thickener"],
    "coating_film_former":     ["coating"],
    "coating_polymer":         ["coating"],
    "coating_resin":           ["coating", "glazing_agent"],
    "coating_specialized":     ["coating"],
    "coating_system_descriptor": ["coating"],
    "coating_colorant":        ["coating", "colorant_natural"],
    "fatty_acid_salt":         ["lubricant"],
    "fatty_acid_oil":          ["carrier_oil"],
    "fatty_acid_excipient":    ["lubricant"],
    "fatty_acid_descriptor":   ["lubricant"],
    "fatty_acid_component":    ["lubricant"],
    "fatty_acid_derivative":   ["lubricant"],
    "fat_fraction":            ["carrier_oil"],
    "excipient_lipid":         ["carrier_oil"],
    "excipient":               ["filler"],          # generic excipient → most common is bulk filler
    "essential_oil":           ["flavor_natural"],
    "flavor_additive":         ["flavor_natural"],
    "flavor_carrier":          ["flavor_natural", "carrier_oil"],
    "flavor_texture":          ["flavor_natural"],
    "flavoring_agent":         ["flavor_natural"],
    "flavoring_spice":         ["flavor_natural"],
    "fruit_vegetable_juice":   ["flavor_natural", "colorant_natural"],
    "carbohydrate":            ["filler"],
    "carbohydrate_derivative": ["filler"],
    "carbohydrate_matrix":     ["filler"],
    "grain_flour":             ["filler"],
    "grain_powder_descriptor": ["filler"],
    "dairy_excipient":         ["filler"],
    "fermented_food_complex":  ["flavor_natural"],
    "fermentation_medium":     ["processing_aid"],
    "fermentation_yeast":      ["processing_aid"],
    "culture_starter":         ["processing_aid"],
    "food_ingredient":         ["filler"],          # generic — most often bulk
    "mineral_salt":            ["ph_regulator"],
    "mineral salt":            ["ph_regulator"],    # space variant
    "antacid_excipient":       ["ph_regulator"],
    "chelating_agent":         ["preservative", "antioxidant"],  # per clinician — folded into preservative+antioxidant
    "emulsifier_stabilizer":   ["emulsifier", "stabilizer"],
    "protein_excipient":       ["filler", "stabilizer"],
    "delivery_form_descriptor": ["coating"],
    "delivery_system":         ["coating"],
    "capsule_shell":           ["coating", "gelling_agent"],
    "capsule_shell_descriptor": ["coating", "gelling_agent"],
    "base_matrix_descriptor":  ["filler"],
    "glazing_agent":           ["glazing_agent"],
    "specialty_compound":      ["filler"],
    "carrier_descriptor":      ["carrier_oil"],
    "color_natural":           ["colorant_natural"],
    "natural_flavor_compound": ["flavor_natural"],
    "fruit_concentrate":       ["flavor_natural"],   # default — high-% nutrient claims handled per-entry in spot-check
    "natural_flavor":          ["flavor_natural"],
    "flavor":                  ["flavor_natural"],
    "starch":                  ["filler", "binder"],
    # Round 2 additions — common manual_review categories
    "ph_adjuster":             ["ph_regulator"],
    "phytochemical_constituent": ["flavor_natural"],     # most are flavor/aroma compounds at typical use levels
    "grain_source_material":   ["filler"],
    # NOTE: "descriptor" handled in RETIRE_CATEGORIES (label noise — moved 2026-04-30 round 4)
    "colorant_flavoring_natural": ["flavor_natural", "colorant_natural"],
    "bulking_agent":           ["filler"],
    "carrier_base":            ["carrier_oil"],
    "buffer_acidity_regulator": ["ph_regulator"],
    "preservative_acidity_regulator": ["preservative", "ph_regulator"],
    "terpene_flavor":          ["flavor_natural"],
    "coating_agent":           ["coating"],
    "lipid_descriptor":        ["carrier_oil"],
    "plant_extract_natural":   ["flavor_natural"],
    "printing_ink_descriptor": ["colorant_natural"],
    "processing aid":          ["processing_aid"],       # space variant
    "mineral_salt_natural":    ["ph_regulator"],
    "botanical_oil":           ["carrier_oil"],
    "coating_protective":      ["coating"],
    "carrier_filler_natural":  ["carrier_oil", "filler"],
    "fruit_extract":           ["flavor_natural"],
    "solubilizer":             ["surfactant", "solvent"],
    "vehicle":                 ["solvent", "carrier_oil"],
    "buffering_salt":          ["ph_regulator"],
    "polymer_coating":         ["coating"],
    "flavor_enhancer":         ["flavor_enhancer"],
    "lipid_component":         ["carrier_oil"],
    "coating_glazing_natural": ["coating", "glazing_agent"],
    "protein_base":            ["filler", "stabilizer"],
    "protein":                 ["filler", "stabilizer"],     # generic protein excipient (e.g. whey isolate as bulk)
    "protein_source":          ["filler", "stabilizer"],
    "prebiotic_sweetener":     ["sweetener_natural", "prebiotic_fiber"],
    "sugar_alcohol":           ["sweetener_sugar_alcohol"],
    "tablet_lubricant":        ["lubricant"],
    "solubilizer_surfactant":  ["surfactant", "solvent"],
    "fatty_acid":              ["lubricant"],
    "emulsifier_descriptor":   ["emulsifier"],
    "oil_derivative":          ["carrier_oil"],
    "anti-caking agent":       ["anti_caking_agent"],        # hyphen + space variant
    "dairy_derivative":        ["filler", "stabilizer"],
    "plasticizer":             ["humectant"],                # plasticizers in capsule shells = humectants functionally
    # Round 3 — long-tail patterns
    "sweetener_syrup":         ["sweetener_natural"],
    "natural_sweetener_colorant": ["sweetener_natural", "colorant_natural"],
    "soluble_fiber_matrix":    ["filler", "prebiotic_fiber"],
    "thickener_gelling":       ["thickener", "gelling_agent"],
    "thickener_stabilizer_general": ["thickener", "stabilizer"],
    "starch_derivative":       ["filler", "binder"],
    "organic_acid_natural":    ["acidulant"],
    "processing_acid":         ["acidulant", "processing_aid"],
    "processing_aid_culture":  ["processing_aid"],
    "processing_aid_mineral":  ["processing_aid"],
    "protein_hydrolysate":     ["filler", "stabilizer"],
    "protein_derivative":      ["filler", "stabilizer"],
    "protein_plant":           ["filler", "stabilizer"],
    "protein_animal":          ["filler", "stabilizer"],
    "vegetable_concentrate":   ["flavor_natural", "colorant_natural"],
    "lubricant_flow_agent":    ["lubricant", "glidant"],
    "lubricant_plant_based":   ["lubricant"],
    "lipid_excipient":         ["carrier_oil"],
    "oil_descriptor":          ["carrier_oil"],
    "oil_blend_alternative":   ["carrier_oil"],
    "mineral_excipient":       ["ph_regulator"],
    "mineral_salt_excipient":  ["ph_regulator"],
    "mineral_salt_exipient":   ["ph_regulator"],   # typo variant
    "mineral_blend":           ["ph_regulator"],
    "mineral_complex":         ["ph_regulator"],
    "mineral_chelate_carrier": ["carrier_oil"],
    "pharmaceutical_excipient": ["filler"],
    "plasticizer_solvent":     ["humectant", "solvent"],
    "plasticizer_emulsifier":  ["humectant", "emulsifier"],
    "solvent_plasticizer_lubricant": ["solvent", "humectant", "lubricant"],
    "sweetener_humectant":     ["sweetener_sugar_alcohol", "humectant"],
    "phytosterol_glycoside":   ["filler"],   # used as bulk in phytosterol-containing supplements
    # NOTE: "metabolic_intermediate" handled in RETIRE_CATEGORIES (move-to-actives semantics actually, but rare and ambiguous — defer to clinician)
    # Hyphen alias for anti-caking already handled
}

# Categories that retire to []
RETIRE_CATEGORIES = {
    "marketing_descriptor",
    "descriptor_component",
    "source_descriptor",
    "phytochemical_marker",
    "label_descriptor",
    "blend_descriptor",
    "branded_descriptor",
    "branded_blend_descriptor",
    "labeling_indicator",
    "legacy_descriptor",
    "composition_descriptor",
    "carotenoid_descriptor",
    "botanical_descriptor",
    "hemp_descriptor",
    "mineral_descriptor",
    "phytochemical_descriptor",
    "phytochemical",
    "label_indicator",
    "certification_wrapper",
    "branded_phytochemical",
    "branded_novel_compound",
    "branded_phytosterol_wrapper",
    "phytochemical_isolate",
    "phytocannabinoid_descriptor",
    "phytonutrient_descriptor",
    "marine_mineral_descriptor",
    "fatty_acid_form_descriptor",
    "packaging_descriptor",
    "unclear_additive",
    "non_vitamin_factor",
    "mineral_source",
    "descriptor",                    # generic label noise
    "metabolic_intermediate",        # rare/ambiguous — clinician spot-check material
}

# Categories where entries are actives — clinician Phase 4 move
MOVE_TO_ACTIVES = {
    "botanical_extract",
    "botanical_compound",
    "botanical_food_component",
    "animal_glandular_tissue",
    "glandular_tissue",
    "glandular_extract",
    "animal_derived_protein",
    "animal_glandular",
    "animal_source_material",
    "amino_acid_derivative",
    "amino_acid_source",
    "branded_botanical_complex",
    "branded_complex",
    "branded_blend",
    "branded_enzyme_complex",
    "branded_protein_complex",
    "phytochemical_novel",
    "functional_ingredient",
    "functional_compound_source",
    "enzyme",                       # active enzymes go to ingredient pipeline
    "novel_compound",
    "phytocannabinoid",
    "branded_mineral_complex",
    "branded_ingredient",
    "branded_complex_extract",
    "proprietary_blend",
    "proprietary_complex",
    "fermentation_complex",
    "animal_derived",
    "glandular",
    "bioactive_peptide_complex",
    "base_blend",
    "terpene",
    "triterpenes",
    "phytosterol",
    "marine_animal_extract",
    "marine_tissue",
    "marine_mineral_algae",
    "nucleic_acid_support",
    "bioactive_constituent",
}

# Categories needing per-entry clinician verification
MANUAL_REVIEW_CATEGORIES = {
    "colorant",                     # TiO2/pearlescent/per-source verification
    "color_blend_descriptor",       # ambiguous source
    "manual_review",                # post-Phase 4c canonical bucket (idempotent)
}

# Post-Phase 4c canonical transitional categories — make categorize.py
# idempotent by recognizing the canonical values it has already written.
POST_4C_RETIRE = {"label_descriptor"}
POST_4C_MOVE_TO_ACTIVES = {"active_pending_relocation"}


def _decompose_compound(category: str, vocab: set):
    """Mechanical decomposition of `_`-joined category strings into multiple
    vocab role IDs (e.g. `binder_coating_thickener` → [binder, coating,
    thickener]). Returns list if all parts resolve, else None."""
    parts = category.lower().split("_")
    out = []
    for p in parts:
        if p in vocab:
            out.append(p)
        else:
            # Try common aliases
            alias_map = {
                "anticaking": "anti_caking_agent",
                "antifoaming": "anti_foaming_agent",
                "ph": "ph_regulator",
                "color": "colorant_natural",
                "colorants": "colorant_natural",
                "flavor": "flavor_natural",
                "flavors": "flavor_natural",
                "flavoring": "flavor_natural",
                "carrier": "carrier_oil",
                "lubricants": "lubricant",
                "binders": "binder",
                "stabilizers": "stabilizer",
                "thickeners": "thickener",
            }
            if p in alias_map:
                out.append(alias_map[p])
            else:
                return None  # fail decomposition
    # dedupe preserving order
    seen = set()
    res = []
    for r in out:
        if r not in seen:
            seen.add(r)
            res.append(r)
    return res if res else None


def categorize(entry: dict, vocab: set):
    """Return (action, roles_or_none, rationale).

    Idempotent — handles both the original raw category strings and the
    post-Phase-4c canonical values (vocab IDs + transitional buckets).
    """
    category = (entry.get("category") or "").lower().strip()
    if not category:
        return ("manual_review", [], "no category")

    # Post-Phase 4c canonical transitional buckets (idempotent path)
    if category in POST_4C_RETIRE:
        return ("retire", [], f"post-4c canonical: {category}")
    if category in POST_4C_MOVE_TO_ACTIVES:
        return ("move_to_actives", [], f"post-4c canonical: {category}")

    # Post-Phase 4c canonical: a vocab ID directly = assign with that role
    # (preserves the existing functional_roles[] which may have multiple roles)
    if category in vocab:
        existing_roles = entry.get("functional_roles") or []
        if existing_roles:
            return ("assign", list(existing_roles), f"post-4c vocab: {category}")
        return ("assign", [category], f"post-4c vocab: {category}")

    if category in DIRECT_MAP:
        roles = DIRECT_MAP[category]
        # Validate vocab membership
        for r in roles:
            if r not in vocab:
                return ("manual_review", [], f"BUG: direct map produced unknown role {r!r}")
        return ("assign", roles, f"direct map: {category}")

    if category in RETIRE_CATEGORIES:
        return ("retire", [], f"retired class: {category}")

    if category in MOVE_TO_ACTIVES:
        return ("move_to_actives", [], f"Phase 4 actives: {category}")

    if category in MANUAL_REVIEW_CATEGORIES:
        return ("manual_review", [], f"per-entry verification: {category}")

    # Try mechanical decomposition for long-tail
    decomp = _decompose_compound(category, vocab)
    if decomp:
        return ("assign", decomp, f"mechanical decomposition: {category} → {decomp}")

    return ("manual_review", [], f"unmapped category: {category}")


if __name__ == "__main__":
    # CLI: print per-category disposition over current other_ingredients.json
    import sys
    vocab = load_vocab_ids()
    DATA_PATH = SCRIPTS_DIR / "data" / "other_ingredients.json"
    with open(DATA_PATH) as f:
        arr = json.load(f)["other_ingredients"]
    from collections import Counter
    actions = Counter()
    samples = {}
    for e in arr:
        action, roles, why = categorize(e, vocab)
        actions[action] += 1
        if action not in samples:
            samples[action] = []
        if len(samples[action]) < 5:
            samples[action].append((e.get("id"), e.get("category"), roles, why))
    print(f"Total entries: {len(arr)}")
    for action, count in actions.most_common():
        print(f"\n{action}: {count}")
        for s in samples.get(action, []):
            print(f"  {s}")
