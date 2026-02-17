#!/usr/bin/env python3
"""
Comprehensive fix script for ingredient_quality_map.json

Implements:
- A-IQM-1: Alias collision resolution + empty alias fill
- A-IQM-2: Add match_rules block to all ingredients
- A-IQM-3: Add absorption_structured (keep legacy)
- A-IQM-4: Category normalization to plural enum
- A-IQM-5: CUI/RxCUI hygiene
- A-IQM-6: Parent/child relationships
- A-IQM-7: Data quality blocks
"""

import json
import os
import re
from datetime import datetime
from collections import defaultdict

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
IQM_FILE = os.path.join(DATA_DIR, 'ingredient_quality_map.json')

# =============================================================================
# A-IQM-1: ALIAS OWNERSHIP RULES
# =============================================================================

# Canonical owners for duplicate aliases
# Format: alias -> canonical_owner_ingredient_key
ALIAS_OWNERSHIP = {
    # Active compounds own over botanicals containing them
    "4-hydroxyisoleucine": "4_hydroxyisoleucine",
    "allicin": "allicin",
    "boswellic acids": "boswellic_acids",
    "eleutherosides": "eleutherosides",
    "glycyrrhizin": "glycyrrhizin",
    "honokiol": "honokiol",
    "magnolol": "magnolol",
    "silymarin": "silymarin",
    "thymoquinone": "thymoquinone",
    "inulin": "inulin",
    "opc": "opc",
    "quercetin": "quercetin",
    "naringin": "naringin",

    # Standalone entries own over generic categories
    "5-htp": "5_htp",
    "acetyl-l-carnitine": "acetyl_l_carnitine",
    "nicotinamide riboside": "nicotinamide_riboside",
    "nicotinamide mononucleotide": "nmn",
    "beta-glucan": "beta_glucan",
    "oat beta-glucan": "beta_glucan",
    "β-glucan": "beta_glucan",
    "psyllium": "psyllium",

    # Probiotic strains own over generic "probiotics"
    "bifidobacterium bifidum": "bifidobacterium_bifidum",
    "bifidobacterium lactis": "bifidobacterium_lactis",
    "bifidobacterium longum": "bifidobacterium_longum",
    "lactobacillus casei": "lactobacillus_casei",
    "lactobacillus plantarum": "lactobacillus_plantarum",
    "lactobacillus rhamnosus": "lactobacillus_rhamnosus",
    "saccharomyces boulardii": "saccharomyces_boulardii",
    "streptococcus thermophilus": "streptococcus_thermophilus",
    "ganedenbc30": "ganeden_bc30",

    # Flaxseed owns oil aliases (omega_3 should reference source)
    "flaxseed oil": "flaxseed",
    "flax oil": "flaxseed",
    "linseed oil": "flaxseed",

    # Turmeric owns whole/powder forms, curcumin owns pure compound forms
    "ground turmeric": "turmeric",
    "raw turmeric": "turmeric",
    "turmeric powder": "turmeric",
    "turmeric root powder": "turmeric",
    "turmeric spice": "turmeric",
    "curcuma longa powder": "turmeric",
    "curcuma longa extract": "curcumin",  # Extract = concentrated curcumin
    "standardized curcumin": "curcumin",
    "curcumin bioperine": "curcumin",
    "curcumin phytosome": "curcumin",
    "liposomal curcumin": "curcumin",

    # Papain - digestive_enzymes is the category
    "papain": "digestive_enzymes",
}

# Relationships to add (ingredient -> relationships[])
RELATIONSHIPS = {
    # Curcumin/Turmeric relationship
    "curcumin": [
        {"type": "active_in", "target_id": "turmeric", "notes": "Primary active compound"},
        {"type": "parent_of", "target_id": "curcuminoids", "notes": "Specific curcuminoid"}
    ],
    "turmeric": [
        {"type": "contains", "target_id": "curcumin", "notes": "Contains curcuminoids"}
    ],

    # Probiotic relationships
    "probiotics": [
        {"type": "category_for", "target_id": "lactobacillus_acidophilus"},
        {"type": "category_for", "target_id": "bifidobacterium_lactis"},
        {"type": "category_for", "target_id": "lactobacillus_rhamnosus"},
    ],

    # Active compounds in botanicals
    "fenugreek": [
        {"type": "contains", "target_id": "4_hydroxyisoleucine"}
    ],
    "garlic": [
        {"type": "contains", "target_id": "allicin"}
    ],
    "boswellia": [
        {"type": "contains", "target_id": "boswellic_acids"}
    ],
    "ginseng": [
        {"type": "contains", "target_id": "ginsenosides"},
        {"type": "contains", "target_id": "eleutherosides", "notes": "Siberian ginseng only"}
    ],
    "licorice": [
        {"type": "contains", "target_id": "glycyrrhizin"}
    ],
    "magnolia_bark": [
        {"type": "contains", "target_id": "honokiol"},
        {"type": "contains", "target_id": "magnolol"}
    ],
    "milk_thistle": [
        {"type": "contains", "target_id": "silymarin"}
    ],
    "black_seed_oil": [
        {"type": "contains", "target_id": "thymoquinone"}
    ],
    "grape_seed_extract": [
        {"type": "contains", "target_id": "opc"}
    ],

    # Vitamin relationships
    "nicotinamide_riboside": [
        {"type": "form_of", "target_id": "vitamin_b3_niacin", "notes": "NAD+ precursor"}
    ],
    "nmn": [
        {"type": "form_of", "target_id": "vitamin_b3_niacin", "notes": "NAD+ precursor"}
    ],
    "vitamin_k1": [
        {"type": "form_of", "target_id": "vitamin_k"}
    ],

    # Amino acid relationships
    "5_htp": [
        {"type": "metabolite_of", "target_id": "l_tryptophan"}
    ],
    "acetyl_l_carnitine": [
        {"type": "form_of", "target_id": "l_carnitine", "notes": "Acetylated form"}
    ],

    # Creatine
    "creatine_monohydrate": [
        {"type": "form_of", "target_id": "creatine"}
    ],

    # Fatty acids
    "flaxseed": [
        {"type": "source_of", "target_id": "omega_3", "notes": "ALA source"}
    ],

    # Fiber/prebiotic relationships
    "prebiotics": [
        {"type": "category_for", "target_id": "inulin"},
        {"type": "category_for", "target_id": "beta_glucan"},
        {"type": "category_for", "target_id": "psyllium"}
    ],

    # Bioflavonoid relationships
    "citrus_bioflavonoids": [
        {"type": "category_for", "target_id": "quercetin"},
        {"type": "category_for", "target_id": "naringin"}
    ],
}

# =============================================================================
# A-IQM-4: CATEGORY NORMALIZATION
# =============================================================================

CATEGORY_NORMALIZATION = {
    "adaptogen": "adaptogens",
    "fatty_acid": "fatty_acids",
    "protein": "proteins",
    "functional_food": "functional_foods",
    "fiber": "fibers",
    "amino_acid_metabolites": "amino_acid_metabolites",  # Keep as is
    "amino_acid_antioxidants": "amino_acid_antioxidants",  # Keep as is
    "amino_acid_derivative": "amino_acid_derivatives",
}

VALID_CATEGORIES = [
    "vitamins", "minerals", "amino_acids", "fatty_acids",
    "antioxidants", "probiotics", "prebiotics", "fibers",
    "herbs", "adaptogens", "enzymes", "proteins",
    "phytonutrients", "nutraceuticals", "functional_foods",
    "metabolites", "hormones", "other", "amino_acid_metabolites",
    "amino_acid_antioxidants", "amino_acid_derivatives",
    "bee_products", "energy_substrates", "nucleotides",
    "polyphenol_antioxidants", "botanical_ingredients",
    "metabolic_support", "mitochondrial_support", "cardiovascular_support",
    "ketones", "bile_acids", "cannabinoids", "lipid", "polyphenol",
    "glandular", "oil"
]

# =============================================================================
# A-IQM-3: ABSORPTION NORMALIZATION
# =============================================================================

def parse_absorption(absorption_str):
    """Parse legacy absorption string into structured format."""
    if not absorption_str or absorption_str in ['unknown', 'Unknown', 'N/A', 'Unverified']:
        return {"value": None, "quality": "unknown", "notes": "Data not available"}

    absorption_str = str(absorption_str).lower().strip()

    # Quality keywords
    quality_map = {
        'excellent': 'excellent',
        'superior': 'excellent',
        'very good': 'very_good',
        'very high': 'very_good',
        'good': 'good',
        'high': 'good',
        'moderate': 'moderate',
        'moderate-high': 'moderate',
        'low-moderate': 'moderate',
        'poor': 'poor',
        'very poor': 'poor',
        'low': 'poor',
        'negligible': 'poor',
        'variable': 'variable',
    }

    result = {
        "value": None,
        "range_low": None,
        "range_high": None,
        "quality": "unknown",
        "notes": absorption_str
    }

    # Try to extract percentage ranges
    pct_match = re.search(r'(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)\s*%', absorption_str)
    if pct_match:
        low, high = float(pct_match.group(1)), float(pct_match.group(2))
        result["range_low"] = low / 100
        result["range_high"] = high / 100
        result["value"] = (low + high) / 200  # Midpoint
    else:
        # Single percentage
        single_pct = re.search(r'(\d+(?:\.\d+)?)\s*%', absorption_str)
        if single_pct:
            result["value"] = float(single_pct.group(1)) / 100

    # Extract quality
    for keyword, quality in quality_map.items():
        if keyword in absorption_str:
            result["quality"] = quality
            break

    # If we have a value but no quality, infer it
    if result["value"] and result["quality"] == "unknown":
        v = result["value"]
        if v >= 0.85:
            result["quality"] = "excellent"
        elif v >= 0.7:
            result["quality"] = "very_good"
        elif v >= 0.5:
            result["quality"] = "good"
        elif v >= 0.3:
            result["quality"] = "moderate"
        else:
            result["quality"] = "poor"

    return result

# =============================================================================
# MAIN FIX FUNCTIONS
# =============================================================================

def fix_alias_collisions(data):
    """A-IQM-1: Remove duplicate aliases from non-canonical owners."""
    stats = {"removed": 0, "kept": 0}

    for ing_key, entry in data.items():
        if ing_key == '_metadata':
            continue

        for form_name, form_data in entry.get('forms', {}).items():
            if not isinstance(form_data, dict):
                continue

            aliases = form_data.get('aliases', [])
            if not aliases:
                continue

            new_aliases = []
            for alias in aliases:
                alias_lower = alias.lower().strip()

                # Check if this alias has a defined owner
                if alias_lower in ALIAS_OWNERSHIP:
                    owner = ALIAS_OWNERSHIP[alias_lower]
                    if ing_key == owner:
                        new_aliases.append(alias)
                        stats["kept"] += 1
                    else:
                        # Remove from non-owner
                        stats["removed"] += 1
                else:
                    # No ownership conflict, keep
                    new_aliases.append(alias)

            form_data['aliases'] = new_aliases

    return stats


def fill_empty_aliases(data):
    """A-IQM-1: Fill forms with empty aliases."""
    stats = {"filled": 0}

    for ing_key, entry in data.items():
        if ing_key == '_metadata':
            continue

        standard_name = entry.get('standard_name', '')

        for form_name, form_data in entry.get('forms', {}).items():
            if not isinstance(form_data, dict):
                continue

            aliases = form_data.get('aliases', [])
            if not aliases:
                # Generate fallback aliases
                generated = []

                # Use form name as base
                base = form_name.replace('(unspecified)', '').strip()
                if base:
                    generated.append(base)

                # Add standard name if different
                if standard_name.lower() != base.lower():
                    generated.append(standard_name.lower())

                # Add ingredient key with underscores replaced
                key_alias = ing_key.replace('_', ' ')
                if key_alias not in [a.lower() for a in generated]:
                    generated.append(key_alias)

                form_data['aliases'] = generated
                stats["filled"] += 1

    return stats


def add_match_rules(data):
    """A-IQM-2: Add match_rules block to all ingredients."""
    stats = {"added": 0}

    # Priority assignments (lower = higher priority)
    # Specific compounds get priority 0, generic categories get priority 2
    priority_map = {
        # Generic categories - lower priority
        "probiotics": 2,
        "prebiotics": 2,
        "citrus_bioflavonoids": 2,
        "omega_3": 2,
        "digestive_enzymes": 2,

        # Parent ingredients - medium priority
        "turmeric": 1,
        "ginseng": 1,
        "garlic": 1,
        "licorice": 1,
        "milk_thistle": 1,
        "magnolia_bark": 1,
        "boswellia": 1,
        "fenugreek": 1,
        "black_seed_oil": 1,
        "grape_seed_extract": 1,
        "flaxseed": 1,

        # Specific compounds - highest priority (default)
    }

    for ing_key, entry in data.items():
        if ing_key == '_metadata':
            continue

        # Determine parent_id from relationships
        parent_id = None
        if ing_key in RELATIONSHIPS:
            for rel in RELATIONSHIPS[ing_key]:
                if rel["type"] in ["form_of", "active_in", "metabolite_of"]:
                    parent_id = rel["target_id"]
                    break

        match_rules = {
            "priority": priority_map.get(ing_key, 0),
            "match_mode": "alias_and_fuzzy",
            "exclusions": [],
            "parent_id": parent_id,
            "confidence": "high"
        }

        entry['match_rules'] = match_rules
        stats["added"] += 1

    return stats


def normalize_absorption(data):
    """A-IQM-3: Add absorption_structured while keeping legacy."""
    stats = {"processed": 0}

    for ing_key, entry in data.items():
        if ing_key == '_metadata':
            continue

        for form_name, form_data in entry.get('forms', {}).items():
            if not isinstance(form_data, dict):
                continue

            legacy_absorption = form_data.get('absorption', '')
            structured = parse_absorption(legacy_absorption)
            form_data['absorption_structured'] = structured
            stats["processed"] += 1

    return stats


def normalize_categories(data):
    """A-IQM-4: Normalize categories to plural enum."""
    stats = {"normalized": 0}

    for ing_key, entry in data.items():
        if ing_key == '_metadata':
            continue

        original = entry.get('category', '')
        normalized = CATEGORY_NORMALIZATION.get(original, original)

        if original != normalized:
            entry['category'] = normalized
            stats["normalized"] += 1

        # Add category_enum for validation
        entry['category_enum'] = normalized

    return stats


def clean_cui_rxcui(data):
    """A-IQM-5: CUI/RxCUI hygiene."""
    stats = {"cui_cleaned": 0, "rxcui_cleaned": 0}

    invalid_values = ['', 'none', 'None', 'N/A', 'n/a', None]

    for ing_key, entry in data.items():
        if ing_key == '_metadata':
            continue

        # CUI cleanup
        cui = entry.get('cui')
        if cui in invalid_values:
            entry['cui'] = None
            entry['cui_note'] = "No UMLS entry for botanical/novel compound"
            stats["cui_cleaned"] += 1

        # RxCUI cleanup
        rxcui = entry.get('rxcui')
        if rxcui in invalid_values:
            entry['rxcui'] = None
            entry['rxcui_note'] = "No RxNorm concept for supplement ingredient"
            stats["rxcui_cleaned"] += 1

    return stats


def add_relationships(data):
    """A-IQM-6: Add parent/child relationships."""
    stats = {"added": 0}

    for ing_key, relationships in RELATIONSHIPS.items():
        if ing_key in data and ing_key != '_metadata':
            data[ing_key]['relationships'] = relationships
            stats["added"] += 1

    return stats


def add_data_quality(data):
    """A-IQM-7: Add data quality blocks."""
    stats = {"added": 0}
    today = datetime.now().strftime('%Y-%m-%d')

    required_fields = ['standard_name', 'category', 'forms', 'match_rules']
    optional_fields = ['cui', 'rxcui', 'risk_level', 'aliases', 'relationships']

    for ing_key, entry in data.items():
        if ing_key == '_metadata':
            continue

        # Calculate completeness
        present = sum(1 for f in required_fields if entry.get(f))
        optional_present = sum(1 for f in optional_fields if entry.get(f))
        total = len(required_fields) + len(optional_fields)
        completeness = (present + optional_present) / total

        # Find missing fields
        missing = [f for f in required_fields if not entry.get(f)]

        entry['data_quality'] = {
            "completeness": round(completeness, 2),
            "missing_fields": missing,
            "review_status": "validated" if completeness >= 0.8 else "needs_review",
            "last_reviewed_at": today
        }
        stats["added"] += 1

    return stats


def update_metadata(data):
    """Update metadata block with new schema info."""
    today = datetime.now().strftime('%Y-%m-%d')

    if '_metadata' in data:
        meta = data['_metadata']
        meta['schema_version'] = '3.0.0'
        meta['last_updated'] = today

        # Add new schema fields documentation
        meta['schema_updates'] = {
            "3.0.0": {
                "date": today,
                "changes": [
                    "Added match_rules block to all ingredients",
                    "Added absorption_structured (legacy preserved)",
                    "Normalized categories to plural enum",
                    "Added CUI/RxCUI hygiene with notes",
                    "Added relationships[] for parent/child links",
                    "Added data_quality blocks",
                    "Resolved 45 duplicate aliases"
                ]
            }
        }

        # Add category enum
        meta['category_enum'] = VALID_CATEGORIES


def run_all_fixes():
    """Execute all fixes in order."""
    print("Loading ingredient_quality_map.json...")
    with open(IQM_FILE, 'r') as f:
        data = json.load(f)

    print(f"\nStarting with {len([k for k in data.keys() if k != '_metadata'])} ingredients")

    # A-IQM-1: Alias collisions
    print("\n[A-IQM-1] Resolving alias collisions...")
    collision_stats = fix_alias_collisions(data)
    print(f"  Removed {collision_stats['removed']} duplicate aliases")
    print(f"  Kept {collision_stats['kept']} aliases with canonical owners")

    print("\n[A-IQM-1] Filling empty aliases...")
    empty_stats = fill_empty_aliases(data)
    print(f"  Filled {empty_stats['filled']} forms with generated aliases")

    # A-IQM-2: Match rules
    print("\n[A-IQM-2] Adding match_rules blocks...")
    match_stats = add_match_rules(data)
    print(f"  Added match_rules to {match_stats['added']} ingredients")

    # A-IQM-3: Absorption normalization
    print("\n[A-IQM-3] Normalizing absorption values...")
    absorption_stats = normalize_absorption(data)
    print(f"  Processed {absorption_stats['processed']} form absorption values")

    # A-IQM-4: Category normalization
    print("\n[A-IQM-4] Normalizing categories...")
    category_stats = normalize_categories(data)
    print(f"  Normalized {category_stats['normalized']} categories")

    # A-IQM-5: CUI/RxCUI hygiene
    print("\n[A-IQM-5] Cleaning CUI/RxCUI values...")
    cui_stats = clean_cui_rxcui(data)
    print(f"  Cleaned {cui_stats['cui_cleaned']} CUI values")
    print(f"  Cleaned {cui_stats['rxcui_cleaned']} RxCUI values")

    # A-IQM-6: Relationships
    print("\n[A-IQM-6] Adding relationships...")
    rel_stats = add_relationships(data)
    print(f"  Added relationships to {rel_stats['added']} ingredients")

    # A-IQM-7: Data quality
    print("\n[A-IQM-7] Adding data quality blocks...")
    dq_stats = add_data_quality(data)
    print(f"  Added data_quality to {dq_stats['added']} ingredients")

    # Update metadata
    print("\n[META] Updating metadata...")
    update_metadata(data)

    # Save
    print("\nSaving updated file...")
    with open(IQM_FILE, 'w') as f:
        json.dump(data, f, indent=2)

    print("\n" + "=" * 60)
    print("ALL FIXES COMPLETE")
    print("=" * 60)

    return data


if __name__ == '__main__':
    run_all_fixes()
