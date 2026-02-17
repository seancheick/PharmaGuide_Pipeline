#!/usr/bin/env python3
"""
Merge STATE_* records into canonical entries:
1. STATE_DMAA_CALIFORNIA → merge jurisdictions into BANNED_DMAA
2. STATE_KRATOM_BANS → merge jurisdictions into RISK_KRATOM_NATURAL
3. STATE_DELTA8_THC → create new BANNED_DELTA8_THC entry

After merge, STATE_* records are removed and added to supersedes_ids.
"""

import json
import os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
BANNED_FILE = os.path.join(DATA_DIR, 'banned_recalled_ingredients.json')


def merge_jurisdictions(target_item, source_item):
    """Merge jurisdictions from source into target, avoiding duplicates."""
    target_jurisdictions = target_item.setdefault('jurisdictions', [])
    source_jurisdictions = source_item.get('jurisdictions', [])

    # Create set of existing jurisdiction keys
    existing_keys = {
        (j.get('jurisdiction_code'), j.get('status'), j.get('effective_date'))
        for j in target_jurisdictions
    }

    added = 0
    for j in source_jurisdictions:
        key = (j.get('jurisdiction_code'), j.get('status'), j.get('effective_date'))
        if key not in existing_keys:
            target_jurisdictions.append(j)
            existing_keys.add(key)
            added += 1

    return added


def add_supersedes_id(item, old_id):
    """Add old_id to supersedes_ids list."""
    supersedes = item.setdefault('supersedes_ids', [])
    if old_id not in supersedes:
        supersedes.append(old_id)


def create_delta8_thc_entry(source_item):
    """Create new canonical entry for Delta-8 THC."""
    today = datetime.now().strftime('%Y-%m-%d')

    return {
        "id": "BANNED_DELTA8_THC",
        "standard_name": "Delta-8 Tetrahydrocannabinol (Delta-8 THC)",
        "canonical_name": "Delta-8 Tetrahydrocannabinol (Delta-8 THC)",
        "aliases": [
            "delta-8 thc",
            "delta 8 thc",
            "delta8 thc",
            "delta-8-thc",
            "d8 thc",
            "d8-thc",
            "delta-8 tetrahydrocannabinol"
        ],
        "synonyms": [
            "delta-8 thc",
            "delta 8 thc",
            "delta8 thc",
            "delta-8-thc",
            "d8 thc",
            "d8-thc",
            "delta-8 tetrahydrocannabinol"
        ],
        "CUI": "",
        "ingredient_type": "synthetic",
        "class_tags": ["cannabinoid", "state_regulated"],
        "use_case_categories": ["recreational", "supplement_gray_area"],
        "supersedes_ids": ["STATE_DELTA8_THC"],
        "banned_date": "varies",
        "ban_effective_date": "varies",
        "banned_by": "State legislatures",
        "reason": "Psychoactive cannabinoid with safety concerns. Banned in many states.",
        "mechanism_of_harm": "Psychoactive cannabinoid that binds to CB1 receptors. Products often contain contaminants from synthesis process. Associated with intoxication, impaired driving, and adverse effects especially in children who consume edibles.",
        "regulatory_status": {
            "US": "Federally legal under 2018 Farm Bill if derived from hemp (<0.3% delta-9 THC), but banned or restricted in 20+ states",
            "WADA": "Not prohibited (out of competition)",
            "EU": "Varies by country"
        },
        "category": "cannabinoid",
        "severity_level": "moderate",
        "severity_score": 5,
        "fda_warning": True,
        "notes": "State-level regulation varies widely. Legal in some states, banned in others. Often sold in gas stations and smoke shops. Quality control concerns.",
        "scientific_references": [
            "FDA Consumer Update: 5 Things to Know about Delta-8 THC (2021)",
            "CDC MMWR: Adverse Health Effects of Delta-8-THC Products (2022)"
        ],
        "last_updated": today,
        "last_reviewed_at": today,
        "status": "restricted",
        "interaction_tags": ["psychoactive", "cannabinoid"],
        "detection_difficulty": "low",
        "match_rules": {
            "match_mode": "alias_and_fuzzy",
            "label_tokens": [
                "delta-8 thc",
                "delta 8 thc",
                "delta8 thc",
                "delta-8-thc",
                "d8 thc",
                "d8-thc"
            ],
            "exclusions": [],
            "case_sensitive": False,
            "priority": 1,
            "match_type": "exact",
            "confidence": "high",
            "negative_match_terms": []
        },
        "legal_status_enum": "banned_state",
        "clinical_risk_enum": "moderate",
        "jurisdictions": source_item.get('jurisdictions', []),
        "references_structured": [
            {
                "type": "fda_advisory",
                "title": "FDA Consumer Update: 5 Things to Know about Delta-8 THC",
                "year": 2021,
                "evidence_grade": "R",
                "url": "https://www.fda.gov/consumers/consumer-updates/5-things-know-about-delta-8-tetrahydrocannabinol-delta-8-thc"
            }
        ],
        "regulatory_actions": [
            {
                "action_type": "warning",
                "authority": "FDA",
                "jurisdiction_code": "US",
                "scope": "supplement",
                "effective_period": {
                    "start": "2021-09-14",
                    "end": None
                },
                "summary": "FDA issued consumer warning about delta-8 THC products",
                "reference_ids": []
            }
        ],
        "source_category": "state_regional_bans",
        "entity_type": "ingredient",
        "effective_period": {
            "start": None,
            "end": None,
            "notes": "Varies by state"
        },
        "data_quality": {
            "completeness": 0.85,
            "missing_fields": ["CUI"],
            "review_status": "validated"
        },
        "review": {
            "status": "validated",
            "last_reviewed_at": today,
            "next_review_due": "2026-07-08",
            "reviewed_by": "system",
            "change_log": []
        }
    }


def run_merge():
    """Execute the STATE_* merge operation."""

    with open(BANNED_FILE, 'r') as f:
        data = json.load(f)

    ingredients = data.get('ingredients', [])

    # Build lookup by ID
    by_id = {item.get('id'): item for item in ingredients}

    stats = {
        'jurisdictions_merged': 0,
        'entries_created': 0,
        'entries_removed': 0
    }

    # 1. Merge STATE_DMAA_CALIFORNIA into BANNED_DMAA
    if 'STATE_DMAA_CALIFORNIA' in by_id and 'BANNED_DMAA' in by_id:
        source = by_id['STATE_DMAA_CALIFORNIA']
        target = by_id['BANNED_DMAA']
        added = merge_jurisdictions(target, source)
        add_supersedes_id(target, 'STATE_DMAA_CALIFORNIA')
        print(f"Merged {added} jurisdictions from STATE_DMAA_CALIFORNIA into BANNED_DMAA")
        stats['jurisdictions_merged'] += added

    # 2. Merge STATE_KRATOM_BANS into RISK_KRATOM_NATURAL
    if 'STATE_KRATOM_BANS' in by_id and 'RISK_KRATOM_NATURAL' in by_id:
        source = by_id['STATE_KRATOM_BANS']
        target = by_id['RISK_KRATOM_NATURAL']
        added = merge_jurisdictions(target, source)
        add_supersedes_id(target, 'STATE_KRATOM_BANS')
        print(f"Merged {added} jurisdictions from STATE_KRATOM_BANS into RISK_KRATOM_NATURAL")
        stats['jurisdictions_merged'] += added

    # 3. Create BANNED_DELTA8_THC from STATE_DELTA8_THC
    if 'STATE_DELTA8_THC' in by_id and 'BANNED_DELTA8_THC' not in by_id:
        source = by_id['STATE_DELTA8_THC']
        new_entry = create_delta8_thc_entry(source)
        ingredients.append(new_entry)
        by_id['BANNED_DELTA8_THC'] = new_entry
        print(f"Created BANNED_DELTA8_THC with {len(source.get('jurisdictions', []))} jurisdictions")
        stats['entries_created'] += 1

    # 4. Remove STATE_* entries
    state_ids_to_remove = ['STATE_DMAA_CALIFORNIA', 'STATE_KRATOM_BANS', 'STATE_DELTA8_THC']
    original_count = len(ingredients)
    ingredients = [item for item in ingredients if item.get('id') not in state_ids_to_remove]
    stats['entries_removed'] = original_count - len(ingredients)
    print(f"Removed {stats['entries_removed']} STATE_* entries")

    # Update data
    data['ingredients'] = ingredients

    # Save
    with open(BANNED_FILE, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"\nMerge complete:")
    print(f"  Jurisdictions merged: {stats['jurisdictions_merged']}")
    print(f"  Entries created: {stats['entries_created']}")
    print(f"  Entries removed: {stats['entries_removed']}")
    print(f"  Total entries: {len(ingredients)}")

    return stats


if __name__ == '__main__':
    print("Merging STATE_* records into canonical entries...\n")
    run_merge()
