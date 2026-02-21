#!/usr/bin/env python3
"""
Comprehensive Ingredient Match Audit
Checks ALL enriched products across ALL manufacturers for 7 issue types:
1. CATEGORY-MISMATCH
2. UNMAPPED
3. CROSS-VITAMIN
4. FORM-LOSS
5. PROBIOTIC-GENERIC
6. OMEGA-MISMATCH
7. DUPLICATE-SCORING
"""

import json
import os
import sys
import re
import subprocess
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent

# ============================================================
# Helper: restore enriched files from git history if missing
# ============================================================
MANUFACTURERS = {
    "Olly": "output_Olly_enriched/enriched",
    "Nordic-Naturals": "output_Nordic-Naturals_enriched/enriched",
    "Thorne": "output_Thorne_enriched/enriched",
    "Care_of": "output_Care_of_enriched/enriched",
    "Emerald_labs": "output_Emerald_labs_enriched/enriched",
    "hum": "output_hum_enriched/enriched",
    "Kirkland": "output_Kirkland_enriched/enriched",
}

RESTORE_COMMIT = "d5fd994"

def discover_enriched_files():
    """Find or restore all enriched batch files for every manufacturer."""
    all_files = {}
    for mfg, rel_dir in MANUFACTURERS.items():
        abs_dir = BASE / rel_dir
        if abs_dir.is_dir():
            jsons = sorted(abs_dir.glob("enriched_cleaned_batch_*.json"))
            if jsons:
                all_files[mfg] = [str(p) for p in jsons]
                continue
        # Try restoring from git history
        # First, figure out which files existed
        try:
            result = subprocess.run(
                ["git", "ls-tree", "-r", "--name-only", RESTORE_COMMIT, "--", f"scripts/{rel_dir}/"],
                capture_output=True, text=True, cwd=str(BASE.parent if (BASE / ".git").exists() else BASE),
                timeout=30,
            )
            # Find the git root
            git_root_result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, cwd=str(BASE),
                timeout=10,
            )
            git_root = git_root_result.stdout.strip()

            result = subprocess.run(
                ["git", "ls-tree", "-r", "--name-only", RESTORE_COMMIT, "--", f"scripts/{rel_dir}/"],
                capture_output=True, text=True, cwd=git_root,
                timeout=30,
            )
            files_in_git = [l.strip() for l in result.stdout.strip().split("\n") if l.strip() and "enriched_cleaned_batch" in l]
            if not files_in_git:
                print(f"  [WARN] No enriched files found in git for {mfg}")
                all_files[mfg] = []
                continue

            # Restore them
            abs_dir.mkdir(parents=True, exist_ok=True)
            restored = []
            for git_path in files_in_git:
                fname = os.path.basename(git_path)
                out_path = abs_dir / fname
                restore = subprocess.run(
                    ["git", "show", f"{RESTORE_COMMIT}:{git_path}"],
                    capture_output=True, cwd=git_root,
                    timeout=120,
                )
                if restore.returncode == 0:
                    out_path.write_bytes(restore.stdout)
                    restored.append(str(out_path))
                    print(f"  [RESTORED] {git_path} -> {out_path}")
                else:
                    print(f"  [FAIL] Could not restore {git_path}: {restore.stderr.decode()[:200]}")
            all_files[mfg] = restored
        except Exception as e:
            print(f"  [ERROR] Git restore failed for {mfg}: {e}")
            all_files[mfg] = []
    return all_files


# ============================================================
# Keyword→category mapping for CATEGORY-MISMATCH detection
# ============================================================
CATEGORY_KEYWORDS = {
    "vitamins": [
        ("vitamin a", "vitamin_a"), ("vitamin c", "vitamin_c"), ("vitamin d", "vitamin_d"),
        ("vitamin e", "vitamin_e"), ("vitamin k", "vitamin_k"), ("vitamin b1", "vitamin_b1"),
        ("thiamin", "vitamin_b1"), ("vitamin b2", "vitamin_b2"), ("riboflavin", "vitamin_b2"),
        ("vitamin b3", "vitamin_b3"), ("niacin", "vitamin_b3"), ("niacinamide", "vitamin_b3"),
        ("vitamin b5", "vitamin_b5"), ("pantothenic", "vitamin_b5"),
        ("vitamin b6", "vitamin_b6"), ("pyridoxine", "vitamin_b6"), ("pyridoxal", "vitamin_b6"),
        ("vitamin b7", "vitamin_b7"), ("biotin", "vitamin_b7"),
        ("vitamin b9", "vitamin_b9"), ("folate", "vitamin_b9"), ("folic acid", "vitamin_b9"),
        ("methylfolate", "vitamin_b9"),
        ("vitamin b12", "vitamin_b12"), ("cobalamin", "vitamin_b12"), ("methylcobalamin", "vitamin_b12"),
        ("cyanocobalamin", "vitamin_b12"),
        ("ascorbic acid", "vitamin_c"), ("tocopherol", "vitamin_e"),
        ("retinol", "vitamin_a"), ("beta-carotene", "vitamin_a"), ("beta carotene", "vitamin_a"),
        ("cholecalciferol", "vitamin_d"), ("ergocalciferol", "vitamin_d"),
        ("phytonadione", "vitamin_k"), ("menaquinone", "vitamin_k"),
    ],
    "minerals": [
        ("calcium", "calcium"), ("magnesium", "magnesium"), ("zinc", "zinc"),
        ("iron", "iron"), ("selenium", "selenium"), ("copper", "copper"),
        ("manganese", "manganese"), ("chromium", "chromium"), ("molybdenum", "molybdenum"),
        ("iodine", "iodine"), ("potassium", "potassium"), ("phosphorus", "phosphorus"),
        ("boron", "boron"), ("vanadium", "vanadium"), ("silica", "silica"),
        ("sodium", "sodium"),
    ],
    "omega_fatty_acids": [
        ("epa", "epa"), ("dha", "dha"), ("fish oil", "fish_oil"),
        ("omega-3", "omega_3"), ("omega 3", "omega_3"), ("omega-6", None),
        ("omega-7", None), ("omega-9", None), ("cod liver oil", None),
        ("krill oil", None), ("flaxseed oil", None), ("algal oil", None),
    ],
    "probiotics": [
        ("lactobacillus", None), ("bifidobacterium", None),
        ("streptococcus", None), ("saccharomyces", None),
        ("bacillus", None), ("lactococcus", None),
    ],
}

# Vitamin parent IDs for cross-vitamin check
VITAMIN_PARENTS = {
    "vitamin_a": ["vitamin_a", "retinol", "beta_carotene"],
    "vitamin_c": ["vitamin_c", "ascorbic_acid"],
    "vitamin_d": ["vitamin_d", "vitamin_d3", "cholecalciferol", "vitamin_d2", "ergocalciferol"],
    "vitamin_e": ["vitamin_e", "tocopherol", "d_alpha_tocopherol"],
    "vitamin_k": ["vitamin_k", "vitamin_k1", "vitamin_k2", "phytonadione", "menaquinone"],
    "vitamin_b1": ["vitamin_b1", "thiamine"],
    "vitamin_b2": ["vitamin_b2", "riboflavin"],
    "vitamin_b3": ["vitamin_b3", "niacin", "niacinamide"],
    "vitamin_b5": ["vitamin_b5", "pantothenic_acid"],
    "vitamin_b6": ["vitamin_b6", "pyridoxine", "pyridoxal"],
    "vitamin_b7": ["vitamin_b7", "biotin"],
    "vitamin_b9": ["vitamin_b9", "folate", "folic_acid"],
    "vitamin_b12": ["vitamin_b12", "vitamin_b12_cobalamin", "cobalamin", "methylcobalamin", "cyanocobalamin"],
}

# Reverse map: keyword -> expected vitamin group key
VITAMIN_KEYWORD_TO_GROUP = {}
for group_key, keywords_list in [
    ("vitamin_a", ["vitamin a", "retinol", "beta-carotene", "beta carotene", "retinyl"]),
    ("vitamin_c", ["vitamin c", "ascorbic acid"]),
    ("vitamin_d", ["vitamin d", "cholecalciferol", "ergocalciferol"]),
    ("vitamin_e", ["vitamin e", "tocopherol", "tocotrienol"]),
    ("vitamin_k", ["vitamin k", "phytonadione", "menaquinone", "phylloquinone"]),
    ("vitamin_b1", ["vitamin b1", "thiamin"]),
    ("vitamin_b2", ["vitamin b2", "riboflavin"]),
    ("vitamin_b3", ["vitamin b3", "niacin", "niacinamide", "nicotinamide"]),
    ("vitamin_b5", ["vitamin b5", "pantothenic"]),
    ("vitamin_b6", ["vitamin b6", "pyridoxine", "pyridoxal", "p-5-p"]),
    ("vitamin_b7", ["vitamin b7", "biotin"]),
    ("vitamin_b9", ["vitamin b9", "folate", "folic acid", "methylfolate", "5-mthf"]),
    ("vitamin_b12", ["vitamin b12", "cobalamin", "methylcobalamin", "cyanocobalamin", "hydroxocobalamin", "adenosylcobalamin"]),
]:
    for kw in keywords_list:
        VITAMIN_KEYWORD_TO_GROUP[kw.lower()] = group_key

# Allowed canonical IDs per vitamin group
VITAMIN_ALLOWED_IDS = {}
for group_key, allowed_ids in VITAMIN_PARENTS.items():
    VITAMIN_ALLOWED_IDS[group_key] = set(aid.lower() for aid in allowed_ids)

# Form keywords for FORM-LOSS check
FORM_KEYWORDS = [
    "bisglycinate", "glycinate", "citrate", "malate", "taurate", "threonate",
    "orotate", "picolinate", "gluconate", "aspartate", "oxide",
    "chelate", "chelated", "sulfate", "carbonate", "fumarate", "succinate",
    "methylcobalamin", "cyanocobalamin", "hydroxocobalamin", "adenosylcobalamin",
    "methylfolate", "5-mthf", "folinic acid", "quatrefolic",
    "pyridoxal-5-phosphate", "p-5-p", "pyridoxal 5'-phosphate",
    "d-alpha-tocopherol", "dl-alpha-tocopherol", "mixed tocopherols",
    "retinyl palmitate", "retinyl acetate", "beta-carotene",
    "cholecalciferol", "ergocalciferol",
    "ascorbyl palmitate", "sodium ascorbate", "calcium ascorbate", "ester-c",
    "phytonadione", "menaquinone-7", "menaquinone-4", "mk-7", "mk-4",
    "selenomethionine", "selenium yeast",
    "chromium picolinate", "chromium polynicotinate",
    "zinc monomethionine", "opti-zinc",
    "ferrous fumarate", "ferrous sulfate", "ferrous bisglycinate", "iron bisglycinate",
    "magnesium l-threonate", "magnesium taurate",
    "d3", "d-3",
]

# Probiotic species-specific canonical IDs
PROBIOTIC_SPECIES = {
    "lactobacillus acidophilus": "lactobacillus_acidophilus",
    "lactobacillus rhamnosus": "lactobacillus_rhamnosus",
    "lactobacillus plantarum": "lactobacillus_plantarum",
    "lactobacillus casei": "lactobacillus_casei",
    "lactobacillus reuteri": "lactobacillus_reuteri",
    "lactobacillus paracasei": "lactobacillus_paracasei",
    "lactobacillus gasseri": "lactobacillus_gasseri",
    "lactobacillus bulgaricus": "lactobacillus_bulgaricus",
    "lactobacillus salivarius": "lactobacillus_salivarius",
    "lactobacillus fermentum": "lactobacillus_fermentum",
    "lactobacillus helveticus": "lactobacillus_helveticus",
    "lactobacillus brevis": "lactobacillus_brevis",
    "bifidobacterium lactis": "bifidobacterium_lactis",
    "bifidobacterium longum": "bifidobacterium_longum",
    "bifidobacterium breve": "bifidobacterium_breve",
    "bifidobacterium infantis": "bifidobacterium_infantis",
    "bifidobacterium bifidum": "bifidobacterium_bifidum",
    "bifidobacterium animalis": "bifidobacterium_animalis",
    "streptococcus thermophilus": "streptococcus_thermophilus",
    "saccharomyces boulardii": "saccharomyces_boulardii",
    "bacillus coagulans": "bacillus_coagulans",
    "bacillus subtilis": "bacillus_subtilis",
}

GENERIC_PROBIOTIC_IDS = {"probiotics", "probiotic", "probiotic_blend", "probiotics_blend", "probiotic_complex"}

# Omega parent IDs
EPA_IDS = {"epa", "eicosapentaenoic_acid", "omega_3_epa"}
DHA_IDS = {"dha", "docosahexaenoic_acid", "omega_3_dha"}
FISH_OIL_IDS = {"fish_oil", "omega_3", "omega_3_fatty_acids", "cod_liver_oil", "krill_oil"}
OMEGA_ALLOWED = EPA_IDS | DHA_IDS | FISH_OIL_IDS | {"algal_oil", "flaxseed_oil", "omega_3_ala"}


# ============================================================
# Audit checks
# ============================================================

def check_category_mismatch(ing, raw_lower, canonical_id_lower):
    """Check 1: Raw name suggests one nutrient category but canonical_id is different."""
    issues = []
    if not canonical_id_lower:
        return issues  # handled by unmapped check

    # Check mineral keywords
    for kw, expected_root in CATEGORY_KEYWORDS["minerals"]:
        if kw in raw_lower:
            # The canonical_id should contain the mineral keyword
            if expected_root and expected_root not in canonical_id_lower:
                # But also check: maybe the canonical_id is a compound form that's still correct
                # e.g., "calcium carbonate" -> "calcium" is fine
                # But "calcium" -> "zinc" is not
                issues.append({
                    "type": "CATEGORY-MISMATCH",
                    "detail": f"Raw name contains '{kw}' (mineral) but canonical_id is '{ing.get('canonical_id')}' (missing '{expected_root}')",
                })
            break  # Only flag the first matching keyword

    # Check vitamin keywords
    for kw_tuple in CATEGORY_KEYWORDS["vitamins"]:
        kw, expected_root = kw_tuple
        if kw in raw_lower:
            if expected_root and expected_root not in canonical_id_lower:
                issues.append({
                    "type": "CATEGORY-MISMATCH",
                    "detail": f"Raw name contains '{kw}' (vitamin) but canonical_id is '{ing.get('canonical_id')}' (missing '{expected_root}')",
                })
            break

    return issues


def check_unmapped(ing, raw_lower, canonical_id_lower):
    """Check 2: Any ingredient with no canonical_id."""
    issues = []
    cid = ing.get("canonical_id")
    if not cid or cid == "" or cid is None or str(cid).strip() == "":
        issues.append({
            "type": "UNMAPPED",
            "detail": f"No canonical_id assigned (mapped={ing.get('mapped')}, role={ing.get('role_classification')})",
        })
    return issues


def check_cross_vitamin(ing, raw_lower, canonical_id_lower):
    """Check 3: Vitamin A/C/D/E/K/B raw names matched to wrong vitamin parent."""
    issues = []
    if not canonical_id_lower:
        return issues

    for kw, group_key in VITAMIN_KEYWORD_TO_GROUP.items():
        if kw in raw_lower:
            allowed = VITAMIN_ALLOWED_IDS.get(group_key, set())
            # Check if canonical_id contains any of the allowed roots
            match_found = False
            for aid in allowed:
                if aid in canonical_id_lower:
                    match_found = True
                    break
            if not match_found:
                # Also allow the group key itself
                if group_key in canonical_id_lower:
                    match_found = True
                # Also allow generic "vitamin" if it has the right letter
                letter = group_key.replace("vitamin_", "")
                if f"vitamin_{letter}" in canonical_id_lower:
                    match_found = True

            if not match_found:
                # Avoid false positives: skip if it's an "other ingredient" or excipient
                if ing.get("source_section") == "other" or ing.get("is_excipient"):
                    continue
                issues.append({
                    "type": "CROSS-VITAMIN",
                    "detail": f"Raw name contains '{kw}' (expected group: {group_key}) but canonical_id is '{ing.get('canonical_id')}' (not in allowed: {sorted(allowed)})",
                })
            break  # Only match first keyword

    return issues


def check_form_loss(ing, raw_lower, canonical_id_lower):
    """Check 4: Raw name contains specific form info but matched to (unspecified) form."""
    issues = []
    if not canonical_id_lower:
        return issues

    form_id = str(ing.get("form_id") or "").lower().strip()
    matched_form = str(ing.get("matched_form") or "").lower().strip()

    # Check if raw name or extracted forms contain a specific form
    all_text = raw_lower
    # Also check extracted_forms
    for ef in (ing.get("extracted_forms") or []):
        raw_form = str(ef.get("raw_form_text") or "").lower()
        all_text += " " + raw_form

    has_specific_form = False
    found_form = None
    for fkw in FORM_KEYWORDS:
        if fkw.lower() in all_text:
            has_specific_form = True
            found_form = fkw
            break

    if has_specific_form:
        # Check if the matched form is unspecified or generic
        unspecified_markers = ["unspecified", "generic", "unknown", "not specified", "general"]
        is_unspecified = False
        for marker in unspecified_markers:
            if marker in form_id or marker in matched_form:
                is_unspecified = True
                break
        # Also check if form_id is empty
        if not form_id or form_id in ("", "none", "null"):
            is_unspecified = True
        # Check if form_unmapped is True
        if ing.get("form_unmapped"):
            is_unspecified = True

        if is_unspecified:
            issues.append({
                "type": "FORM-LOSS",
                "detail": f"Raw name contains specific form '{found_form}' but form_id='{ing.get('form_id')}', matched_form='{ing.get('matched_form')}', form_unmapped={ing.get('form_unmapped')}",
            })

    return issues


def check_probiotic_generic(ing, raw_lower, canonical_id_lower):
    """Check 5: Specific strain name matched to generic 'probiotics' parent."""
    issues = []
    if not canonical_id_lower:
        return issues

    for species_name, expected_id in PROBIOTIC_SPECIES.items():
        if species_name.lower() in raw_lower:
            if canonical_id_lower in GENERIC_PROBIOTIC_IDS:
                issues.append({
                    "type": "PROBIOTIC-GENERIC",
                    "detail": f"Raw name contains species '{species_name}' but canonical_id is generic '{ing.get('canonical_id')}' (expected: '{expected_id}' or similar)",
                })
            break

    return issues


def check_omega_mismatch(ing, raw_lower, canonical_id_lower):
    """Check 6: EPA/DHA/fish oil ingredients matched to wrong parent."""
    issues = []
    if not canonical_id_lower:
        return issues

    # EPA check
    if ("epa" in raw_lower or "eicosapentaenoic" in raw_lower) and "dha" not in raw_lower:
        if canonical_id_lower not in {x.lower() for x in EPA_IDS} and "epa" not in canonical_id_lower and "omega" not in canonical_id_lower and "fish" not in canonical_id_lower:
            issues.append({
                "type": "OMEGA-MISMATCH",
                "detail": f"Raw name suggests EPA but canonical_id is '{ing.get('canonical_id')}'",
            })

    # DHA check
    if ("dha" in raw_lower or "docosahexaenoic" in raw_lower) and "epa" not in raw_lower:
        if canonical_id_lower not in {x.lower() for x in DHA_IDS} and "dha" not in canonical_id_lower and "omega" not in canonical_id_lower and "fish" not in canonical_id_lower:
            issues.append({
                "type": "OMEGA-MISMATCH",
                "detail": f"Raw name suggests DHA but canonical_id is '{ing.get('canonical_id')}'",
            })

    # Fish oil check
    if "fish oil" in raw_lower:
        if "fish" not in canonical_id_lower and "omega" not in canonical_id_lower and "epa" not in canonical_id_lower and "dha" not in canonical_id_lower:
            issues.append({
                "type": "OMEGA-MISMATCH",
                "detail": f"Raw name suggests fish oil but canonical_id is '{ing.get('canonical_id')}'",
            })

    return issues


def check_duplicate_scoring(product_ingredients):
    """Check 7: Same ingredient appearing in both scorable and additive domains."""
    issues = []
    by_canonical = defaultdict(list)
    for ing in product_ingredients:
        cid = ing.get("canonical_id")
        if cid:
            role = ing.get("role_classification", "")
            by_canonical[cid].append((ing.get("name") or ing.get("raw_source_text", "?"), role))

    for cid, entries in by_canonical.items():
        roles = set(role for _, role in entries)
        has_scorable = any("scorable" in r.lower() for r in roles if r)
        has_additive = any("additive" in r.lower() or "excipient" in r.lower() for r in roles if r)
        if has_scorable and has_additive:
            names = [n for n, _ in entries]
            roles_str = [f"{n} ({r})" for n, r in entries]
            issues.append({
                "type": "DUPLICATE-SCORING",
                "detail": f"canonical_id '{cid}' appears in both scorable and additive domains: {roles_str}",
                "product_level": True,
            })

    return issues


# ============================================================
# Main audit loop
# ============================================================

def audit_product(product):
    """Run all checks on a single product's ingredients."""
    iqd = product.get("ingredient_quality_data", {})
    ingredients = iqd.get("ingredients", [])

    product_name = product.get("fullName", product.get("id", "UNKNOWN"))
    product_id = product.get("id", "?")

    all_issues = []

    for ing in ingredients:
        raw = str(ing.get("raw_source_text") or ing.get("name") or "").strip()
        raw_lower = raw.lower()
        canonical_id = str(ing.get("canonical_id") or "").strip()
        canonical_id_lower = canonical_id.lower()

        # Run all 6 ingredient-level checks
        for check_fn in [check_category_mismatch, check_unmapped, check_cross_vitamin,
                         check_form_loss, check_probiotic_generic, check_omega_mismatch]:
            found = check_fn(ing, raw_lower, canonical_id_lower)
            for issue in found:
                issue["product_id"] = product_id
                issue["product_name"] = product_name
                issue["ingredient_raw"] = raw
                issue["canonical_id"] = canonical_id
                issue["form_id"] = ing.get("form_id", "")
                issue["role"] = ing.get("role_classification", "")
                issue["source_section"] = ing.get("source_section", "")
                all_issues.append(issue)

    # Check 7: Duplicate scoring (product-level)
    dup_issues = check_duplicate_scoring(ingredients)
    for issue in dup_issues:
        issue["product_id"] = product_id
        issue["product_name"] = product_name
        issue["ingredient_raw"] = "(product-level check)"
        issue["canonical_id"] = ""
        issue["form_id"] = ""
        issue["role"] = ""
        issue["source_section"] = ""
        all_issues.append(issue)

    return all_issues, len(ingredients)


def main():
    print("=" * 100)
    print("COMPREHENSIVE INGREDIENT MATCH AUDIT")
    print("=" * 100)
    print()

    # Discover / restore files
    print("PHASE 1: Discovering enriched files...")
    print("-" * 60)
    mfg_files = discover_enriched_files()
    print()

    # Combined totals
    grand_total_ingredients = 0
    grand_total_products = 0
    grand_issues_by_type = defaultdict(list)
    all_issues = []

    # Per-manufacturer audit
    for mfg in sorted(MANUFACTURERS.keys()):
        files = mfg_files.get(mfg, [])
        print("=" * 100)
        print(f"MANUFACTURER: {mfg}")
        print(f"  Enriched files: {len(files)}")

        if not files:
            print("  [SKIP] No enriched files available")
            print()
            continue

        mfg_issues = []
        mfg_ingredients = 0
        mfg_products = 0

        for fpath in files:
            fname = os.path.basename(fpath)
            try:
                with open(fpath, "r") as f:
                    products = json.load(f)
            except Exception as e:
                print(f"  [ERROR] Could not load {fname}: {e}")
                continue

            if not isinstance(products, list):
                print(f"  [WARN] {fname} is not a list, skipping")
                continue

            for product in products:
                issues, ing_count = audit_product(product)
                mfg_ingredients += ing_count
                mfg_products += 1
                mfg_issues.extend(issues)

        grand_total_ingredients += mfg_ingredients
        grand_total_products += mfg_products

        # Summary for this manufacturer
        print(f"  Products checked: {mfg_products}")
        print(f"  Ingredients checked: {mfg_ingredients}")
        print(f"  Issues found: {len(mfg_issues)}")

        if mfg_issues:
            # Group by type
            by_type = defaultdict(list)
            for iss in mfg_issues:
                by_type[iss["type"]].append(iss)

            for itype in sorted(by_type.keys()):
                items = by_type[itype]
                print(f"\n  --- {itype}: {len(items)} issue(s) ---")
                for item in items:
                    print(f"    Product: [{item['product_id']}] {item['product_name']}")
                    print(f"      Ingredient: {item['ingredient_raw']}")
                    print(f"      canonical_id: {item['canonical_id']}")
                    if item.get('form_id'):
                        print(f"      form_id: {item['form_id']}")
                    if item.get('role'):
                        print(f"      role: {item['role']}")
                    print(f"      -> {item['detail']}")
                    print()

                grand_issues_by_type[itype].extend(items)

        all_issues.extend(mfg_issues)
        print()

    # ============================================================
    # COMBINED SUMMARY
    # ============================================================
    print()
    print("=" * 100)
    print("COMBINED SUMMARY ACROSS ALL MANUFACTURERS")
    print("=" * 100)
    print(f"Total manufacturers checked: {len([m for m in MANUFACTURERS if mfg_files.get(m)])}")
    print(f"Total products checked: {grand_total_products}")
    print(f"Total ingredients checked: {grand_total_ingredients}")
    print(f"Total issues found: {len(all_issues)}")
    print()

    if all_issues:
        print("ISSUES BY TYPE:")
        print("-" * 60)
        for itype in ["CATEGORY-MISMATCH", "UNMAPPED", "CROSS-VITAMIN", "FORM-LOSS",
                       "PROBIOTIC-GENERIC", "OMEGA-MISMATCH", "DUPLICATE-SCORING"]:
            items = grand_issues_by_type.get(itype, [])
            print(f"\n  {itype}: {len(items)} total issue(s)")
            if items:
                # Group by manufacturer
                by_mfg = defaultdict(list)
                for item in items:
                    # Derive manufacturer from product info or file context
                    by_mfg["(all)"].append(item)

                for item in items:
                    pid = item['product_id']
                    pname = item['product_name']
                    raw = item['ingredient_raw']
                    cid = item['canonical_id']
                    print(f"    [{pid}] {pname} | {raw} -> {cid}")
                    print(f"      {item['detail']}")

        print()
        print("=" * 100)
        print("ISSUE COUNTS SUMMARY TABLE")
        print("=" * 100)
        print(f"{'Issue Type':<25} {'Count':>8}")
        print("-" * 35)
        for itype in ["CATEGORY-MISMATCH", "UNMAPPED", "CROSS-VITAMIN", "FORM-LOSS",
                       "PROBIOTIC-GENERIC", "OMEGA-MISMATCH", "DUPLICATE-SCORING"]:
            count = len(grand_issues_by_type.get(itype, []))
            print(f"{itype:<25} {count:>8}")
        print("-" * 35)
        print(f"{'TOTAL':<25} {len(all_issues):>8}")
    else:
        print("*** NO ISSUES FOUND - ALL INGREDIENTS PASS ALL 7 CHECKS ***")

    print()
    print("=" * 100)
    print("AUDIT COMPLETE")
    print("=" * 100)


if __name__ == "__main__":
    main()
