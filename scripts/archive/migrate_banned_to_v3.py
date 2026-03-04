#!/usr/bin/env python3
"""
Migration script: banned_recalled_ingredients.json v2.2 -> v3.0

This script:
1. Adds new schema v3.0 fields (legal_status_enum, clinical_risk_enum, match_rules, etc.)
2. Fixes status contradictions (high_risk items marked as "banned")
3. Deduplicates entries (e.g., Sibutramine)
4. Converts to single ingredients[] list with class_tags
5. Adds operations metadata (data_quality, last_reviewed_at, etc.)

Run with: python migrate_banned_to_v3.py [--dry-run]
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional
from copy import deepcopy

# File paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(SCRIPT_DIR, "data", "banned_recalled_ingredients.json")
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "data", "banned_recalled_ingredients_v3.json")
BACKUP_FILE = os.path.join(SCRIPT_DIR, "data", "banned_recalled_ingredients_v2_backup.json")

# Status mapping: category -> default legal_status_enum
CATEGORY_TO_LEGAL_STATUS = {
    "permanently_banned": "banned_federal",
    "nootropic_banned": "not_lawful_as_supplement",
    "sarms_prohibited": "not_lawful_as_supplement",
    "high_risk_ingredients": "high_risk",
    "illegal_spiking_agents": "adulterant",
    "heavy_metal_limits": "contaminant_risk",
    "wada_prohibited_2024": "wada_prohibited",
    "state_regional_bans": "banned_state",
    "new_emerging_threats": "under_review",
    "pharmaceutical_adulterants": "adulterant",
    "designer_stimulants": "not_lawful_as_supplement",
    "synthetic_cannabinoids": "controlled_substance",
    "schedule_I_psychoactives": "controlled_substance",
    "novel_peptides": "not_lawful_as_supplement",
    "research_chemicals": "not_lawful_as_supplement",
    "recalled_supplement_brands": "contaminant_risk",
}

# Per-ingredient overrides for legal_status_enum
INGREDIENT_OVERRIDES = {
    "RISK_KAVA": "restricted",  # Banned in UK/Germany, not US
    "RISK_KRATOM_NATURAL": "not_lawful_as_supplement",
    "HIGH_RISK_GERMANDER": "restricted",  # Banned in France/Germany, not US
    "BANNED_CBD_US": "not_lawful_as_supplement",  # Drug exclusion rule
    "RISK_GREEN_TEA_EXTRACT_HIGH": "lawful",  # Only risky at high doses
}

# severity_level to clinical_risk_enum mapping
SEVERITY_TO_CLINICAL_RISK = {
    "critical": "critical",
    "high": "high",
    "moderate": "moderate",
    "low": "low",
}

# IDs to deduplicate: canonical_id -> list of superseded_ids
DEDUPE_MAP = {
    "BANNED_SIBUTRAMINE": ["SPIKE_SIBUTRAMINE"],
}

# Ingredient type mapping based on category and standard_name patterns
def infer_ingredient_type(item: Dict, category: str) -> str:
    """Infer ingredient_type based on category and item data."""
    name = item.get("standard_name", "").lower()
    category_lower = category.lower()

    if "botanical" in name or any(x in category_lower for x in ["botanical", "herb"]):
        return "botanical"
    if any(x in category_lower for x in ["pharmaceutical", "drug", "spiking"]):
        return "pharmaceutical"
    if "peptide" in category_lower or "peptide" in name:
        return "peptide"
    if "hormone" in name or "igf" in name:
        return "hormone"
    if any(x in category_lower for x in ["heavy_metal", "contaminant"]):
        return "contaminant"
    if any(x in category_lower for x in ["nootropic", "racetam"]):
        return "synthetic"
    if any(x in category_lower for x in ["sarm", "steroid"]):
        return "synthetic"
    if any(x in name for x in ["stimulant", "dmaa", "dmha"]):
        return "synthetic"
    return "synthetic"  # Default


def build_match_rules(item: Dict) -> Dict:
    """Build match_rules block from existing aliases."""
    aliases = item.get("aliases", [])
    standard_name = item.get("standard_name", "")

    # Collect all tokens for matching
    label_tokens = [standard_name.lower()] if standard_name else []
    label_tokens.extend([alias.lower() for alias in aliases])

    # Remove duplicates while preserving order
    seen = set()
    unique_tokens = []
    for token in label_tokens:
        if token not in seen:
            seen.add(token)
            unique_tokens.append(token)

    return {
        "match_mode": "alias_and_fuzzy",
        "label_tokens": unique_tokens,
        "exclusions": [],
        "case_sensitive": False
    }


def build_references_structured(item: Dict) -> List[Dict]:
    """Convert scientific_references strings to structured format."""
    refs = item.get("scientific_references", [])
    structured = []

    for ref in refs:
        if not ref:
            continue
        ref_obj = {"evidence_grade": "R"}  # Default to regulatory

        # Parse DOI references
        if "DOI:" in ref or "doi:" in ref:
            parts = ref.split(" - ", 1)
            doi_part = parts[0].replace("DOI:", "").replace("doi:", "").strip()
            title = parts[1] if len(parts) > 1 else ""
            ref_obj = {
                "type": "doi",
                "id": doi_part,
                "title": title,
                "evidence_grade": "A" if any(x in title.lower() for x in ["trial", "rct", "meta"]) else "B",
                "url": f"https://doi.org/{doi_part}"
            }
        # Parse FDA references
        elif "FDA" in ref:
            ref_obj = {
                "type": "fda_advisory",
                "title": ref,
                "evidence_grade": "R"
            }
            # Try to extract date
            import re
            date_match = re.search(r'(\d{4}-\d{2}-\d{2}|\d{4})', ref)
            if date_match:
                ref_obj["date"] = date_match.group(1)
        # Parse WADA references
        elif "WADA" in ref:
            ref_obj = {
                "type": "wada_list",
                "title": ref,
                "evidence_grade": "R"
            }
        # Parse other references
        else:
            ref_obj = {
                "type": "other",
                "title": ref,
                "evidence_grade": "R"
            }

        structured.append(ref_obj)

    return structured


def build_regulatory_actions(item: Dict) -> List[Dict]:
    """Build regulatory_actions from existing banned_date/banned_by fields."""
    actions = []

    banned_date = item.get("banned_date", "")
    banned_by = item.get("banned_by", "")
    reason = item.get("reason", "")

    if banned_date and banned_date not in ["", "2024-ongoing", "2025-ongoing", "varies"]:
        action = {
            "action_type": "ban" if banned_by else "warning",
            "agency": banned_by or "FDA",
            "date": banned_date,
            "summary": reason[:200] if reason else ""
        }
        actions.append(action)

    return actions


def build_jurisdictions(item: Dict, legal_status: str) -> List[Dict]:
    """Build jurisdictions array for state/regional bans."""
    jurisdictions = []

    regulatory_status = item.get("regulatory_status", {})

    # Parse US federal status
    if "US" in regulatory_status or "US_Federal" in regulatory_status:
        us_status = regulatory_status.get("US") or regulatory_status.get("US_Federal", "")
        if us_status:
            jurisdictions.append({
                "region": "US",
                "level": "federal",
                "status": "banned" if "banned" in us_status.lower() else "restricted",
                "effective_date": item.get("ban_effective_date", item.get("banned_date", "")),
                "source": {"type": "fda_action", "citation": us_status[:100]}
            })

    # Parse state-specific bans
    for key, value in regulatory_status.items():
        if key not in ["US", "US_Federal", "Canada", "EU", "Australia", "Global", "WADA", "DEA", "Military", "WHO/IARC"]:
            # This is likely a state
            jurisdictions.append({
                "region": "US",
                "level": "state",
                "name": key.replace("_", " "),
                "status": "schedule_I" if "schedule i" in value.lower() else ("schedule_II" if "schedule ii" in value.lower() else "banned"),
                "effective_date": "",
                "source": {"type": "state_statute", "citation": value[:100]}
            })

    # Check for state bans in notes
    banned_countries = item.get("banned_countries", [])
    for country in banned_countries:
        jurisdictions.append({
            "region": country,
            "level": "national",
            "status": "banned",
            "source": {"type": "national_ban"}
        })

    return jurisdictions


def build_data_quality(item: Dict) -> Dict:
    """Build data_quality block."""
    missing = []

    if not item.get("CUI"):
        missing.append("CUI")
    if not item.get("mechanism_of_harm") or "requires further" in item.get("mechanism_of_harm", "").lower():
        missing.append("mechanism_of_harm")
    if not item.get("scientific_references"):
        missing.append("references")

    completeness = 1.0 - (len(missing) * 0.1)

    return {
        "completeness": round(max(0.5, completeness), 2),
        "missing_fields": missing,
        "review_status": "validated" if not missing else "needs_review"
    }


def migrate_entry(item: Dict, category: str) -> Dict:
    """Migrate a single entry to v3.0 schema."""
    migrated = deepcopy(item)

    entry_id = item.get("id", "")

    # Add canonical_name (same as standard_name)
    migrated["canonical_name"] = item.get("standard_name", "")

    # Add synonyms (from aliases)
    migrated["synonyms"] = item.get("aliases", [])

    # Add ingredient_type
    migrated["ingredient_type"] = infer_ingredient_type(item, category)

    # Add class_tags (from category)
    existing_category = item.get("category", "")
    migrated["class_tags"] = [category]
    if existing_category and existing_category != category:
        migrated["class_tags"].append(existing_category)

    # Add use_case_categories based on category
    use_cases = []
    if any(x in category.lower() for x in ["weight", "fat"]):
        use_cases.append("weight_loss")
    if any(x in category.lower() for x in ["sarm", "steroid", "muscle"]):
        use_cases.append("bodybuilding")
    if any(x in category.lower() for x in ["sexual", "erectile"]):
        use_cases.append("sexual_enhancement")
    if any(x in category.lower() for x in ["nootropic", "cognitive"]):
        use_cases.append("cognitive_enhancement")
    migrated["use_case_categories"] = use_cases if use_cases else ["general"]

    # Add match_rules
    migrated["match_rules"] = build_match_rules(item)

    # Add legal_status_enum (with overrides)
    if entry_id in INGREDIENT_OVERRIDES:
        legal_status = INGREDIENT_OVERRIDES[entry_id]
    else:
        legal_status = CATEGORY_TO_LEGAL_STATUS.get(category, "restricted")
    migrated["legal_status_enum"] = legal_status

    # Add clinical_risk_enum (from severity_level)
    severity = item.get("severity_level", "moderate")
    migrated["clinical_risk_enum"] = SEVERITY_TO_CLINICAL_RISK.get(severity, "moderate")

    # Add jurisdictions
    migrated["jurisdictions"] = build_jurisdictions(item, legal_status)

    # Add regulatory_actions
    migrated["regulatory_actions"] = build_regulatory_actions(item)

    # Add references_structured
    migrated["references_structured"] = build_references_structured(item)

    # Add operations metadata
    migrated["data_quality"] = build_data_quality(item)
    migrated["last_reviewed_at"] = datetime.now().strftime("%Y-%m-%d")
    migrated["reviewed_by"] = "migration_script"
    migrated["source_confidence"] = "medium"
    migrated["update_flags"] = {"needs_source_verification": False}

    # Preserve original category as source_category
    migrated["source_category"] = category

    return migrated


def merge_duplicates(ingredients: List[Dict], dedupe_map: Dict) -> List[Dict]:
    """Merge duplicate entries, keeping canonical and adding supersedes_ids."""
    # Build lookup by ID
    by_id = {item["id"]: item for item in ingredients}

    # Process deduplication
    ids_to_remove = set()
    for canonical_id, superseded_ids in dedupe_map.items():
        if canonical_id not in by_id:
            continue

        canonical = by_id[canonical_id]
        canonical["supersedes_ids"] = superseded_ids

        # Merge data from superseded entries
        for sup_id in superseded_ids:
            if sup_id in by_id:
                superseded = by_id[sup_id]

                # Merge synonyms
                canonical["synonyms"] = list(set(canonical.get("synonyms", []) + superseded.get("synonyms", [])))

                # Merge use_case_categories
                canonical["use_case_categories"] = list(set(canonical.get("use_case_categories", []) + superseded.get("use_case_categories", [])))

                # Merge class_tags
                canonical["class_tags"] = list(set(canonical.get("class_tags", []) + superseded.get("class_tags", [])))

                # Update match_rules
                canonical["match_rules"]["label_tokens"] = list(set(
                    canonical["match_rules"]["label_tokens"] +
                    superseded.get("match_rules", {}).get("label_tokens", [])
                ))

                ids_to_remove.add(sup_id)

    # Remove superseded entries
    return [item for item in ingredients if item["id"] not in ids_to_remove]


def migrate_file(dry_run: bool = False) -> Dict:
    """Migrate the entire file to v3.0 schema."""
    # Load current file
    print(f"Loading: {INPUT_FILE}")
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Count entries
    total_entries = 0
    for key, value in data.items():
        if key != "_metadata" and isinstance(value, list):
            total_entries += len(value)
    print(f"Found {total_entries} entries across {len([k for k in data.keys() if k != '_metadata'])} categories")

    # Build v3.0 structure
    v3_data = {
        "schema_version": "3.0",
        "last_updated": datetime.now().strftime("%Y-%m-%d"),
        "data_source_metadata": {
            "sources": ["FDA", "WADA", "DEA", "internal_curation"],
            "update_frequency": "monthly"
        },
        "migration": {
            "deprecated_fields": ["status", "banned_date", "banned_by", "scientific_references", "aliases"],
            "authoritative_fields": ["legal_status_enum", "clinical_risk_enum", "jurisdictions", "references_structured", "synonyms"],
            "deprecation_timeline": "deprecated fields will be removed in v4.0",
            "migrated_from": "2.2",
            "migration_date": datetime.now().strftime("%Y-%m-%d")
        },
        "ingredients": []
    }

    # Migrate each category
    for category, items in data.items():
        if category == "_metadata":
            continue
        if not isinstance(items, list):
            continue

        print(f"Migrating {len(items)} entries from '{category}'...")

        for item in items:
            migrated = migrate_entry(item, category)
            v3_data["ingredients"].append(migrated)

    # Deduplicate
    print(f"Deduplicating entries...")
    original_count = len(v3_data["ingredients"])
    v3_data["ingredients"] = merge_duplicates(v3_data["ingredients"], DEDUPE_MAP)
    removed_count = original_count - len(v3_data["ingredients"])
    print(f"Removed {removed_count} duplicate entries")

    # Sort by ID for consistency
    v3_data["ingredients"].sort(key=lambda x: x.get("id", ""))

    # Add metadata
    v3_data["_metadata"] = {
        "description": "Banned and recalled ingredients database for regulatory compliance and safety (v3.0)",
        "purpose": "safety_disqualification_and_regulatory_compliance",
        "schema_version": "3.0",
        "last_updated": datetime.now().strftime("%Y-%m-%d"),
        "total_entries": len(v3_data["ingredients"]),
        "migration_notes": [
            "Migrated from v2.2 category-based structure to single ingredients[] list",
            "Added legal_status_enum and clinical_risk_enum for accurate classification",
            "Added match_rules for deterministic ingredient matching",
            "Added references_structured with evidence grades",
            "Added jurisdictions for state/regional ban support",
            "Added operations metadata (data_quality, last_reviewed_at, update_flags)",
            f"Merged {removed_count} duplicate entries using supersedes_ids"
        ]
    }

    if dry_run:
        print("\n[DRY RUN] Would write to:", OUTPUT_FILE)
        print(f"Total entries: {len(v3_data['ingredients'])}")
        # Show sample entry
        if v3_data["ingredients"]:
            print("\nSample migrated entry:")
            sample = v3_data["ingredients"][0]
            print(json.dumps({k: sample[k] for k in list(sample.keys())[:10]}, indent=2))
    else:
        # Backup original
        print(f"Creating backup: {BACKUP_FILE}")
        with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # Write migrated file
        print(f"Writing migrated file: {OUTPUT_FILE}")
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(v3_data, f, indent=2, ensure_ascii=False)

        print(f"\nMigration complete!")
        print(f"Total entries: {len(v3_data['ingredients'])}")
        print(f"Backup saved to: {BACKUP_FILE}")
        print(f"New file saved to: {OUTPUT_FILE}")
        print("\nNext steps:")
        print("1. Review the migrated file")
        print("2. Run validation: python validate_database.py")
        print("3. Run tests: pytest tests/test_banned_schema_v3.py -v")
        print("4. If satisfied, replace original: mv banned_recalled_ingredients_v3.json banned_recalled_ingredients.json")

    return v3_data


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    migrate_file(dry_run=dry_run)
