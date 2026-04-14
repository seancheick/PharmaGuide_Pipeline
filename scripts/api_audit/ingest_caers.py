#!/usr/bin/env python3
"""
ingest_caers.py — FDA CAERS Adverse Event Signal Aggregator

Downloads (or reads cached) FDA CAERS bulk data, filters to dietary supplement
reports, extracts ingredient names from product brand names, matches to IQM
canonical IDs, and produces caers_adverse_event_signals.json.

Usage:
    python3 scripts/api_audit/ingest_caers.py [--refresh]

    --refresh   Re-download CAERS bulk data (default: use cached)

Output:
    scripts/data/caers_adverse_event_signals.json

Source: FDA Center for Food Safety and Applied Nutrition Adverse Event Reporting System
URL: https://api.fda.gov/download.json → /food/event
"""

import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "data")
CAERS_DIR = os.path.join(DATA_DIR, "fda_caers")
CAERS_FILE = os.path.join(CAERS_DIR, "food-event-0001-of-0001.json")
IQM_FILE = os.path.join(DATA_DIR, "ingredient_quality_map.json")
OUTPUT_FILE = os.path.join(DATA_DIR, "caers_adverse_event_signals.json")

# ---------------------------------------------------------------------------
# Industry codes for dietary supplements in CAERS
# ---------------------------------------------------------------------------
SUPPLEMENT_INDUSTRY_CODES = {"54"}  # Vit/Min/Prot/Unconv Diet(Human/Animal)

# Serious outcome categories (for serious_reports count)
SERIOUS_OUTCOMES = {
    "Hospitalization",
    "Death",
    "Life Threatening",
    "Visited Emergency Room",
    "Disability",
    "Required Intervention",
    "Congenital Anomaly",
    "Other Serious or Important Medical Event",
    "Other Serious Outcome",
}

# Signal strength thresholds (on serious_reports count)
SIGNAL_STRONG = 100
SIGNAL_MODERATE = 25
SIGNAL_WEAK = 10

# ---------------------------------------------------------------------------
# Build ingredient vocabulary from IQM canonical_ids + aliases
# ---------------------------------------------------------------------------

def _normalize(text):
    """Lowercase, strip non-alphanumeric, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def build_ingredient_vocabulary(iqm_path):
    """
    Build a lookup dict: normalized_name -> canonical_id

    Uses the IQM canonical_id (converted from snake_case to space-separated)
    plus all non-CUI aliases.
    """
    with open(iqm_path) as f:
        iqm = json.load(f)

    vocab = {}  # normalized_name -> canonical_id
    for canon_id, entry in iqm.items():
        if canon_id == "_metadata":
            continue

        # Convert canonical_id: "green_tea_extract" -> "green tea extract"
        readable = canon_id.replace("_", " ")
        vocab[_normalize(readable)] = canon_id

        # Add aliases (skip CUI codes like C0012345)
        for alias in entry.get("aliases", []):
            if re.match(r"^C\d{5,}$", alias):
                continue
            normed = _normalize(alias)
            if len(normed) >= 3:  # skip very short aliases
                vocab[normed] = canon_id

    return vocab


# ---------------------------------------------------------------------------
# Common supplement ingredient terms extracted from product names
# ---------------------------------------------------------------------------

# Multi-word ingredients that must be matched as phrases (before single-word)
MULTI_WORD_INGREDIENTS = [
    ("green tea extract", "green_tea_extract"),
    ("green tea", "green_tea_extract"),
    ("fish oil", "fish_oil_omega3"),
    ("st johns wort", "st_johns_wort"),
    ("st john s wort", "st_johns_wort"),
    ("saint johns wort", "st_johns_wort"),
    ("garcinia cambogia", "garcinia_cambogia"),
    ("garcinia cambosia", "garcinia_cambogia"),
    ("black cohosh", "black_cohosh"),
    ("ginkgo biloba", "ginkgo_biloba"),
    ("saw palmetto", "saw_palmetto"),
    ("vitamin b12", "vitamin_b12_cobalamin"),
    ("vitamin b 12", "vitamin_b12_cobalamin"),
    ("vitamin b6", "vitamin_b6_pyridoxine"),
    ("vitamin b 6", "vitamin_b6_pyridoxine"),
    ("vitamin b1", "vitamin_b1_thiamine"),
    ("vitamin b 1", "vitamin_b1_thiamine"),
    ("vitamin b2", "vitamin_b2_riboflavin"),
    ("vitamin b 2", "vitamin_b2_riboflavin"),
    ("vitamin b3", "vitamin_b3_niacin"),
    ("vitamin b 3", "vitamin_b3_niacin"),
    ("vitamin b5", "vitamin_b5_pantothenic"),
    ("vitamin b 5", "vitamin_b5_pantothenic"),
    ("vitamin b7", "vitamin_b7_biotin"),
    ("vitamin b 7", "vitamin_b7_biotin"),
    ("vitamin b9", "vitamin_b9_folate"),
    ("vitamin b 9", "vitamin_b9_folate"),
    ("folic acid", "vitamin_b9_folate"),
    ("vitamin d3", "vitamin_d"),
    ("vitamin d 3", "vitamin_d"),
    ("vitamin d", "vitamin_d"),
    ("vitamin c", "vitamin_c"),
    ("vitamin e", "vitamin_e"),
    ("vitamin a", "vitamin_a"),
    ("vitamin k", "vitamin_k"),
    ("coenzyme q10", "coq10"),
    ("coq10", "coq10"),
    ("alpha lipoic acid", "alpha_lipoic_acid"),
    ("milk thistle", "milk_thistle"),
    ("red yeast rice", "red_yeast_rice"),
    ("kava kava", "kava"),
    ("bitter orange", "bitter_orange"),
    ("white willow bark", "white_willow_bark"),
    ("white willow", "white_willow_bark"),
    ("dong quai", "dong_quai"),
    ("evening primrose", "evening_primrose_oil"),
    ("horse chestnut", "horse_chestnut"),
    ("stinging nettle", "stinging_nettle"),
    ("lions mane", "lions_mane"),
    ("lion s mane", "lions_mane"),
    ("black seed oil", "black_seed_oil"),
    ("grape seed", "grape_seed_extract"),
    ("l carnitine", "l_carnitine"),
    ("l glutamine", "l_glutamine"),
    ("l arginine", "l_arginine"),
    ("l theanine", "l_theanine"),
    ("l tryptophan", "l_tryptophan"),
    ("l tyrosine", "l_tyrosine"),
    ("l lysine", "l_lysine"),
    ("l citrulline", "l_citrulline"),
    ("whey protein", "whey_protein"),
    ("collagen peptide", "collagen"),
    ("glucosamine chondroitin", "glucosamine"),
    ("omega 3", "fish_oil_omega3"),
]

# Single-word ingredient matches (only if word boundary match)
SINGLE_WORD_INGREDIENTS = {
    "melatonin": "melatonin",
    "biotin": "vitamin_b7_biotin",
    "niacin": "vitamin_b3_niacin",
    "thiamine": "vitamin_b1_thiamine",
    "riboflavin": "vitamin_b2_riboflavin",
    "calcium": "calcium",
    "magnesium": "magnesium",
    "iron": "iron",
    "zinc": "zinc",
    "selenium": "selenium",
    "chromium": "chromium",
    "potassium": "potassium",
    "copper": "copper",
    "manganese": "manganese",
    "iodine": "iodine",
    "turmeric": "turmeric",
    "curcumin": "turmeric",
    "ashwagandha": "ashwagandha",
    "echinacea": "echinacea",
    "ginseng": "ginseng",
    "valerian": "valerian",
    "kratom": "kratom",
    "kava": "kava",
    "ginkgo": "ginkgo_biloba",
    "elderberry": "elderberry",
    "astragalus": "astragalus",
    "rhodiola": "rhodiola",
    "bacopa": "bacopa",
    "berberine": "berberine",
    "quercetin": "quercetin",
    "resveratrol": "resveratrol",
    "spirulina": "spirulina",
    "chlorella": "chlorella",
    "creatine": "creatine_monohydrate",
    "glucosamine": "glucosamine",
    "chondroitin": "chondroitin",
    "collagen": "collagen",
    "probiotics": "probiotics",
    "probiotic": "probiotics",
    "caffeine": "caffeine",
    "dmaa": "dmaa",
    "yohimbe": "yohimbe",
    "yohimbine": "yohimbe",
    "ephedra": "ephedra",
    "comfrey": "comfrey",
    "chaparral": "chaparral",
    "pennyroyal": "pennyroyal",
    "aristolochic": "aristolochic_acid",
    "5 htp": "5_htp",
    "dhea": "dhea",
    "sam e": "sam_e",
    "msm": "msm",
    "boron": "boron",
    "coq10": "coq10",
    "maca": "maca",
    "tribulus": "tribulus",
    "fenugreek": "fenugreek",
    "cinnamon": "cinnamon",
    "garlic": "garlic",
    "ginger": "ginger",
    "peppermint": "peppermint",
    "lavender": "lavender",
    "chamomile": "chamomile",
    "dandelion": "dandelion",
    "oregano": "oregano",
    "senna": "senna",
    "cascara": "cascara",
    "psyllium": "psyllium",
    "flaxseed": "flaxseed",
    "boswellia": "boswellia",
    "butterbur": "butterbur",
    "cordyceps": "cordyceps",
    "reishi": "reishi",
}

# Canonical dedup map — merge aliases into single canonical IDs
CANONICAL_DEDUP = {
    "fish_oil": "fish_oil_omega3",
    "omega_3": "fish_oil_omega3",
    "omega3": "fish_oil_omega3",
}

# Multi-ingredient product keywords — when these appear in the name,
# the report is about the PRODUCT, not any single ingredient.
# We skip these to avoid inflating base-rate ingredients like calcium/vitamin D.
MULTI_INGREDIENT_KEYWORDS = [
    "multivitamin", "multi vitamin", "multiminerals", "multimineral",
    "centrum", "one a day", "one-a-day", "alive!", "mega food",
    "megafood", "garden of life", "prenatal", "postnatal",
    "men s 50", "women s 50", "men s multi", "women s multi",
    "complete multi", "daily multi", "multi for",
]

# Max ingredients from a single product name — if we extract too many,
# it's likely a multi-ingredient product and signals are diluted.
MAX_INGREDIENTS_PER_PRODUCT = 3


def extract_ingredients_from_name(product_name, iqm_vocab):
    """
    Extract ingredient canonical_ids from a product brand name.
    Returns a set of canonical_ids found.

    Filters out multi-ingredient products (multivitamins, "centrum", etc.)
    to avoid inflating base-rate ingredients. Deduplicates aliases.
    """
    normed = _normalize(product_name)

    # Skip multi-ingredient products entirely
    for kw in MULTI_INGREDIENT_KEYWORDS:
        if kw in normed:
            return set()

    found = set()

    # Phase 1: multi-word phrase matches (longest first)
    for phrase, canon_id in MULTI_WORD_INGREDIENTS:
        if phrase in normed:
            found.add(canon_id)

    # Phase 2: single-word boundary matches
    for word, canon_id in SINGLE_WORD_INGREDIENTS.items():
        if re.search(r"\b" + re.escape(word) + r"\b", normed):
            found.add(canon_id)

    # Phase 3: IQM vocab match (catches anything the hardcoded lists miss)
    for vocab_term, canon_id in iqm_vocab.items():
        if len(vocab_term) >= 5 and vocab_term in normed:
            found.add(canon_id)

    # Dedup canonical aliases
    found = {CANONICAL_DEDUP.get(cid, cid) for cid in found}

    # If too many ingredients extracted, it's likely a combo product — skip
    if len(found) > MAX_INGREDIENTS_PER_PRODUCT:
        return set()

    return found


# ---------------------------------------------------------------------------
# Main aggregation
# ---------------------------------------------------------------------------

def aggregate_caers_signals(caers_path, iqm_vocab):
    """
    Parse CAERS data, filter to supplement reports, extract ingredients,
    and aggregate adverse event signals per ingredient.
    """
    print(f"Loading CAERS data from {caers_path}...")
    with open(caers_path) as f:
        data = json.load(f)

    results = data.get("results", [])
    print(f"Total CAERS reports: {len(results)}")

    # Per-ingredient aggregation
    signals = defaultdict(lambda: {
        "total_reports": 0,
        "serious_reports": 0,
        "outcomes": Counter(),
        "reactions": Counter(),
        "report_years": Counter(),
    })

    supp_reports = 0
    matched_reports = 0
    unmatched_names = Counter()

    for report in results:
        products = report.get("products", [])
        outcomes = report.get("outcomes", [])
        reactions = report.get("reactions", [])

        # Filter: at least one supplement product in SUSPECT role
        supp_products = [
            p for p in products
            if p.get("industry_code") in SUPPLEMENT_INDUSTRY_CODES
            and p.get("role") == "SUSPECT"
        ]
        if not supp_products:
            continue

        supp_reports += 1
        is_serious = any(o in SERIOUS_OUTCOMES for o in outcomes)

        # Extract year from date_created
        date_str = report.get("date_created", "")
        year = date_str[:4] if len(date_str) >= 4 else "unknown"

        # Extract ingredients from all suspect supplement products
        report_ingredients = set()
        for prod in supp_products:
            name = prod.get("name_brand", "")
            ingredients = extract_ingredients_from_name(name, iqm_vocab)
            report_ingredients.update(ingredients)
            if not ingredients:
                unmatched_names[name] += 1

        if report_ingredients:
            matched_reports += 1

        # Attribute report to each matched ingredient
        for canon_id in report_ingredients:
            sig = signals[canon_id]
            sig["total_reports"] += 1
            if is_serious:
                sig["serious_reports"] += 1
            for o in outcomes:
                sig["outcomes"][o] += 1
            for r in reactions:
                sig["reactions"][r] += 1
            sig["report_years"][year] += 1

    print(f"Supplement reports: {supp_reports}")
    print(f"Matched to ingredients: {matched_reports} ({matched_reports/max(supp_reports,1)*100:.1f}%)")
    print(f"Unique ingredients found: {len(signals)}")
    print(f"Unmatched product names: {len(unmatched_names)}")

    return dict(signals), supp_reports, unmatched_names


def classify_signal_strength(serious_reports):
    """Classify signal strength based on serious report count."""
    if serious_reports >= SIGNAL_STRONG:
        return "strong"
    elif serious_reports >= SIGNAL_MODERATE:
        return "moderate"
    elif serious_reports >= SIGNAL_WEAK:
        return "weak"
    else:
        return "minimal"


def build_output(signals, total_supp_reports):
    """Build the final JSON output structure."""
    output_signals = {}
    for canon_id, sig in sorted(signals.items(), key=lambda x: -x[1]["serious_reports"]):
        # Only include ingredients with >= SIGNAL_WEAK serious reports
        if sig["serious_reports"] < SIGNAL_WEAK:
            continue

        output_signals[canon_id] = {
            "canonical_id": canon_id,
            "total_reports": sig["total_reports"],
            "serious_reports": sig["serious_reports"],
            "outcomes": {
                "hospitalization": sig["outcomes"].get("Hospitalization", 0),
                "er_visit": sig["outcomes"].get("Visited Emergency Room", 0),
                "life_threatening": sig["outcomes"].get("Life Threatening", 0),
                "death": sig["outcomes"].get("Death", 0),
                "disability": sig["outcomes"].get("Disability", 0),
                "required_intervention": sig["outcomes"].get("Required Intervention", 0),
            },
            "top_reactions": [
                r for r, _ in sig["reactions"].most_common(10)
            ],
            "signal_strength": classify_signal_strength(sig["serious_reports"]),
            "year_range": f"{min(sig['report_years'].keys())}-{max(sig['report_years'].keys())}",
        }

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "_metadata": {
            "schema_version": "1.0.0",
            "source": "FDA CAERS bulk download (food/event)",
            "source_url": "https://api.fda.gov/download.json",
            "last_updated": now,
            "total_supplement_reports_analyzed": total_supp_reports,
            "total_ingredients_with_signals": len(output_signals),
            "signal_thresholds": {
                "strong": f">={SIGNAL_STRONG} serious reports",
                "moderate": f"{SIGNAL_MODERATE}-{SIGNAL_STRONG-1} serious reports",
                "weak": f"{SIGNAL_WEAK}-{SIGNAL_MODERATE-1} serious reports",
                "minimal": f"<{SIGNAL_WEAK} serious reports (excluded)",
            },
        },
        "signals": output_signals,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if not os.path.exists(CAERS_FILE):
        print(f"ERROR: CAERS data not found at {CAERS_FILE}")
        print("Download from: https://download.open.fda.gov/food/event/food-event-0001-of-0001.json.zip")
        print("Unzip into scripts/data/fda_caers/")
        sys.exit(1)

    if not os.path.exists(IQM_FILE):
        print(f"ERROR: IQM file not found at {IQM_FILE}")
        sys.exit(1)

    # Build vocabulary
    print("Building ingredient vocabulary from IQM...")
    iqm_vocab = build_ingredient_vocabulary(IQM_FILE)
    print(f"Vocabulary size: {len(iqm_vocab)} terms")

    # Aggregate
    signals, total_supp, unmatched = aggregate_caers_signals(CAERS_FILE, iqm_vocab)

    # Build output
    output = build_output(signals, total_supp)

    # Write
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nWrote {OUTPUT_FILE}")
    print(f"Ingredients with signals: {len(output['signals'])}")

    # Show top 15 by serious reports
    print("\n=== Top 15 ingredients by serious adverse event reports ===")
    for canon_id, sig in list(output["signals"].items())[:15]:
        print(f"  {canon_id}: {sig['serious_reports']} serious / {sig['total_reports']} total [{sig['signal_strength']}]")

    # Show top unmatched names for future vocabulary expansion
    print(f"\n=== Top 20 unmatched product names (for vocabulary expansion) ===")
    for name, count in unmatched.most_common(20):
        print(f"  {count:>4}  {name}")


if __name__ == "__main__":
    main()
