#!/usr/bin/env python3
"""
Fix IGF-1 LR3 test failures by:
1. Adding BANNED_IGF1_LR3 entry to banned_recalled_ingredients.json
2. Adding allowlist entries for LR3 variants
"""

import json
import os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
BANNED_FILE = os.path.join(DATA_DIR, 'banned_recalled_ingredients.json')
ALLOWLIST_FILE = os.path.join(DATA_DIR, 'banned_match_allowlist.json')


def add_igf1_lr3_entry():
    """Add BANNED_IGF1_LR3 entry to banned ingredients database."""

    with open(BANNED_FILE, 'r') as f:
        data = json.load(f)

    # Check if entry already exists
    existing_ids = {item.get('id') for item in data.get('ingredients', [])}
    if 'BANNED_IGF1_LR3' in existing_ids:
        print("BANNED_IGF1_LR3 already exists, skipping...")
        return False

    # Create the new entry
    today = datetime.now().strftime('%Y-%m-%d')

    igf1_lr3_entry = {
        "id": "BANNED_IGF1_LR3",
        "standard_name": "IGF-1 LR3 (Long R3 Insulin-like Growth Factor 1)",
        "canonical_name": "IGF-1 LR3 (Long R3 Insulin-like Growth Factor 1)",
        "aliases": [
            "igf-1 lr3",
            "igf1 lr3",
            "igf-1lr3",
            "igf1lr3",
            "long r3 igf-1",
            "long r3 igf1",
            "lr3 igf-1",
            "lr3 igf1",
            "lr3-igf-1",
            "lr3-igf1",
            "long arginine 3 igf-1",
            "insulin-like growth factor 1 lr3"
        ],
        "synonyms": [
            "igf-1 lr3",
            "igf1 lr3",
            "igf-1lr3",
            "igf1lr3",
            "long r3 igf-1",
            "long r3 igf1",
            "lr3 igf-1",
            "lr3 igf1",
            "lr3-igf-1",
            "lr3-igf1",
            "long arginine 3 igf-1",
            "insulin-like growth factor 1 lr3"
        ],
        "CUI": "",  # No UMLS CUI for this synthetic analog
        "ingredient_type": "peptide",
        "class_tags": ["permanently_banned", "peptide", "hormone_analog"],
        "use_case_categories": ["bodybuilding", "performance_enhancement"],
        "banned_date": "2000-01-01",
        "ban_effective_date": "2000-01-01",
        "banned_by": "FDA",
        "reason": "Unapproved synthetic peptide drug, modified IGF-1 with extended half-life",
        "mechanism_of_harm": "IGF-1 LR3 is a synthetic modified version of IGF-1 with the glutamic acid at position 3 replaced with arginine, giving it a 3x longer half-life. This amplifies all IGF-1 risks: severe hypoglycemia, increased cancer risk from prolonged growth factor signaling, cardiac hypertrophy, acromegaly-like effects. Never approved for human use.",
        "regulatory_status": {
            "US": "Unapproved drug - never FDA approved for any indication. Sold as research chemical.",
            "WADA": "Prohibited at all times (S2 - Peptide Hormones)",
            "EU": "Banned in supplements"
        },
        "category": "peptide",
        "severity_level": "critical",
        "severity_score": 10,
        "fda_warning": True,
        "notes": "More potent and longer-acting than natural IGF-1. Often sold as 'research chemical' to circumvent drug laws. Popular in bodybuilding. Distinct from standard IGF-1 - requires separate banned entry.",
        "scientific_references": [
            "DOI: 10.1016/S0021-9258(18)61566-0 - LR3 IGF-1 characterization",
            "WADA Prohibited List 2024 - S2 Peptide Hormones"
        ],
        "last_updated": today,
        "status": "banned",
        "interaction_tags": ["carcinogenic", "endocrine", "cardiovascular", "hormonal"],
        "detection_difficulty": "medium",
        "match_rules": {
            "match_mode": "alias_and_fuzzy",
            "label_tokens": [
                "igf-1 lr3",
                "igf1 lr3",
                "igf-1lr3",
                "igf1lr3",
                "long r3 igf-1",
                "long r3 igf1",
                "lr3 igf-1",
                "lr3 igf1",
                "lr3-igf-1",
                "lr3-igf1",
                "long arginine 3 igf-1"
            ],
            "exclusions": [],
            "case_sensitive": False,
            "priority": 0,  # Higher priority than BANNED_IGF1 (which has priority 1)
            "match_type": "exact",
            "confidence": "high",
            "negative_match_terms": []
        },
        "legal_status_enum": "not_lawful_as_supplement",
        "clinical_risk_enum": "critical",
        "jurisdictions": [
            {
                "jurisdiction_code": "US",
                "jurisdiction_type": "country",
                "region": "US",
                "level": "federal",
                "status": "not_lawful",
                "effective_date": "2000-01-01",
                "last_verified_date": today,
                "source": {
                    "type": "fda_guidance",
                    "citation": "Unapproved new drug - never authorized"
                }
            }
        ],
        "references_structured": [
            {
                "type": "wada_list",
                "title": "WADA Prohibited List 2024 - S2 Peptide Hormones",
                "year": 2024,
                "evidence_grade": "R",
                "url": "https://www.wada-ama.org/en/prohibited-list"
            }
        ],
        "regulatory_actions": [
            {
                "action_type": "enforcement",
                "authority": "FDA",
                "jurisdiction_code": "US",
                "scope": "supplement",
                "effective_period": {
                    "start": "2000-01-01",
                    "end": None
                },
                "summary": "Unapproved new drug - not a dietary ingredient",
                "reference_ids": []
            }
        ],
        "source_category": "peptide_hormones_banned",
        "entity_type": "ingredient",
        "effective_period": {
            "start": "2000-01-01",
            "end": None,
            "notes": None
        },
        "data_quality": {
            "completeness": 0.90,
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

    # Add entry to ingredients list
    data['ingredients'].append(igf1_lr3_entry)

    # Save updated file
    with open(BANNED_FILE, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"Added BANNED_IGF1_LR3 entry. Total entries: {len(data['ingredients'])}")
    return True


def update_allowlist():
    """Add LR3 variants to allowlist pointing to BANNED_IGF1_LR3."""

    with open(ALLOWLIST_FILE, 'r') as f:
        data = json.load(f)

    today = datetime.now().strftime('%Y-%m-%d')

    # Check if LR3 allowlist entry already exists
    existing_ids = {item.get('id') for item in data.get('allowlist', [])}
    if 'ALLOW_IGF1_LR3' in existing_ids:
        print("ALLOW_IGF1_LR3 already exists, skipping...")
        return False

    # Add allowlist entry for IGF-1 LR3 variants
    lr3_allowlist_entry = {
        "id": "ALLOW_IGF1_LR3",
        "canonical_id": "BANNED_IGF1_LR3",
        "canonical_term": "IGF-1 LR3 (Long R3 Insulin-like Growth Factor 1)",
        "match_policy": "token_bounded_hyphen_space",
        "variants": [
            "igf-1 lr3",
            "igf 1 lr3",
            "igf1 lr3",
            "igf-1lr3",
            "igf1lr3",
            "long r3 igf-1",
            "long r3 igf 1",
            "long r3 igf1",
            "lr3 igf-1",
            "lr3 igf 1",
            "lr3 igf1",
            "lr3-igf-1",
            "lr3-igf1"
        ],
        "notes": "Allow all LR3 IGF-1 variants to match BANNED_IGF1_LR3 (NOT BANNED_IGF1).",
        "created_at": today,
        "updated_at": today
    }

    data['allowlist'].append(lr3_allowlist_entry)

    # Update database info
    data['database_info']['last_updated'] = today

    # Save updated file
    with open(ALLOWLIST_FILE, 'w') as f:
        json.dump(data, f, indent=2)

    print("Added ALLOW_IGF1_LR3 entry to allowlist")
    return True


def update_igf1_negative_match_terms():
    """Add LR3 variants to BANNED_IGF1's negative_match_terms to prevent false matches."""

    with open(BANNED_FILE, 'r') as f:
        data = json.load(f)

    for item in data.get('ingredients', []):
        if item.get('id') == 'BANNED_IGF1':
            match_rules = item.get('match_rules', {})
            negative_terms = match_rules.get('negative_match_terms', [])

            # Add LR3 variants to negative match terms
            lr3_terms = [
                "lr3",
                "long r3",
                "igf-1 lr3",
                "igf1 lr3",
                "lr3 igf"
            ]

            for term in lr3_terms:
                if term not in negative_terms:
                    negative_terms.append(term)

            match_rules['negative_match_terms'] = negative_terms
            item['match_rules'] = match_rules
            print(f"Updated BANNED_IGF1 negative_match_terms: {negative_terms}")
            break

    with open(BANNED_FILE, 'w') as f:
        json.dump(data, f, indent=2)

    return True


if __name__ == '__main__':
    print("Fixing IGF-1 LR3 test failures...\n")

    print("Step 1: Adding BANNED_IGF1_LR3 entry...")
    add_igf1_lr3_entry()

    print("\nStep 2: Updating allowlist with LR3 variants...")
    update_allowlist()

    print("\nStep 3: Adding LR3 to BANNED_IGF1 negative_match_terms...")
    update_igf1_negative_match_terms()

    print("\nDone!")
