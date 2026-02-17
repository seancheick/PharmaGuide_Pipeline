#!/usr/bin/env python3
"""
P0 and P1 updates for banned_recalled_ingredients.json

P0:
- Add entity_type to all entries (ingredient|product|class|contaminant|threat)

P1:
- Add regulatory_actions[] as canonical action timeline
- Normalize dates with effective_period object
- Add entry-level review block with next_review_due
"""

import json
import os
import re
from datetime import datetime, timedelta

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
BANNED_FILE = os.path.join(DATA_DIR, 'banned_recalled_ingredients.json')

# =============================================================================
# P0: Entity Type Classification
# =============================================================================

# Entity type by ID prefix
ENTITY_TYPE_BY_PREFIX = {
    # Ingredients (actual substances)
    "BANNED": "ingredient",
    "HIGH": "ingredient",      # HIGH_RISK_*
    "NOOTROPIC": "ingredient",
    "PEPTIDE": "ingredient",
    "PHARMA": "ingredient",
    "RISK": "ingredient",
    "SARM": "ingredient",
    "SCHED": "ingredient",     # Scheduled substances
    "STIM": "ingredient",      # Stimulants
    "SYNTH": "ingredient",     # Synthetic cannabinoids
    "WADA": "ingredient",
    "ADD": "ingredient",       # Additives (still ingredients)

    # Contaminants (adulterants, heavy metals, spiking agents)
    "ADULTERANT": "contaminant",
    "HM": "contaminant",       # Heavy metals
    "SPIKE": "contaminant",    # Spiking agents

    # Products (recalled product brands)
    "RECALLED": "product",

    # Classes (umbrella categories)
    "RC": "class",             # Research chemical analogs
    "STATE": "class",          # State-specific (should merge later)

    # Threats (emerging/surveillance)
    "THREAT": "threat",
}

# Override specific IDs that don't fit prefix pattern
ENTITY_TYPE_OVERRIDES = {
    # Contamination categories (not specific ingredients)
    "BANNED_CONTAMINATED_GLP1": "contaminant",
    "BANNED_METAL_FIBERS": "contaminant",

    # Classes that use BANNED prefix
    "SPIKE_ANABOLIC_STEROIDS": "class",  # Category, not specific compound
    "SPIKE_TIANEPTINE_ANALOGUES": "class",
    "STIM_METHYLHEXANAMINE_ANALOGS": "class",
    "RC_CARDARINE_ANALOGS": "class",
}

ENTITY_TYPE_ENUM = ["ingredient", "product", "class", "contaminant", "threat"]


def get_entity_type(item):
    """Determine entity_type for an item."""
    item_id = item.get('id', '')

    # Check overrides first
    if item_id in ENTITY_TYPE_OVERRIDES:
        return ENTITY_TYPE_OVERRIDES[item_id]

    # Check by prefix
    prefix = item_id.split('_')[0] if '_' in item_id else item_id
    if prefix in ENTITY_TYPE_BY_PREFIX:
        return ENTITY_TYPE_BY_PREFIX[prefix]

    # Default to ingredient
    return "ingredient"


# =============================================================================
# P1: Regulatory Actions Timeline
# =============================================================================

def parse_date_string(date_str):
    """Parse various date formats to ISO or None."""
    if not date_str:
        return None

    date_str = str(date_str).strip()

    # Skip non-date values
    skip_patterns = ['varies', 'ongoing', 'warning', 'n/a', 'unknown', 'pending']
    if any(p in date_str.lower() for p in skip_patterns):
        return None

    # Try ISO format (YYYY-MM-DD)
    iso_match = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', date_str)
    if iso_match:
        return date_str

    # Try year-only (YYYY)
    year_match = re.match(r'^(\d{4})$', date_str)
    if year_match:
        return f"{date_str}-01-01"

    # Try YYYY-MM
    ym_match = re.match(r'^(\d{4})-(\d{2})$', date_str)
    if ym_match:
        return f"{date_str}-01"

    return None


def build_regulatory_actions(item):
    """Build regulatory_actions[] from existing data."""
    actions = []
    item_id = item.get('id', '')

    # Extract from existing regulatory_actions if present
    existing = item.get('regulatory_actions', [])
    for action in existing:
        # Normalize the action
        normalized = {
            "action_type": action.get('action_type', 'unknown'),
            "authority": action.get('agency', 'unknown'),
            "jurisdiction_code": None,
            "scope": determine_scope(item),
            "effective_period": {
                "start": parse_date_string(action.get('date')),
                "end": None
            },
            "summary": action.get('summary', ''),
            "reference_ids": []
        }
        actions.append(normalized)

    # If no existing actions, create from banned_date/banned_by
    if not actions and item.get('banned_date'):
        start_date = parse_date_string(item.get('banned_date'))
        if start_date or item.get('banned_by'):
            actions.append({
                "action_type": determine_action_type(item),
                "authority": item.get('banned_by', 'FDA'),
                "jurisdiction_code": "US",
                "scope": determine_scope(item),
                "effective_period": {
                    "start": start_date,
                    "end": None
                },
                "summary": item.get('reason', ''),
                "reference_ids": []
            })

    return actions


def determine_action_type(item):
    """Determine action type from item data."""
    status = item.get('legal_status_enum', '')
    category = item.get('category', '')
    item_id = item.get('id', '')

    if 'RECALLED' in item_id:
        return 'recall'
    if status == 'banned_federal':
        return 'ban'
    if status == 'controlled_substance':
        return 'scheduling'
    if status in ['not_lawful_as_supplement', 'adulterant']:
        return 'enforcement'
    if status == 'high_risk':
        return 'warning'
    if status == 'restricted':
        return 'restriction'

    return 'warning'


def determine_scope(item):
    """Determine regulatory scope from item data."""
    category = item.get('category', '')
    class_tags = item.get('class_tags', [])

    if 'wada' in str(class_tags).lower():
        return 'sport'
    if 'food' in category.lower() or 'additive' in category.lower():
        return 'food'
    if 'drug' in category.lower() or 'pharmaceutical' in category.lower():
        return 'drug'

    return 'supplement'


# =============================================================================
# P1: Effective Period Normalization
# =============================================================================

def build_effective_period(item):
    """Build effective_period object from existing date fields."""
    start = parse_date_string(item.get('banned_date')) or \
            parse_date_string(item.get('ban_effective_date'))

    # For ongoing bans, end is None
    return {
        "start": start,
        "end": None,
        "notes": item.get('banned_date') if not start and item.get('banned_date') else None
    }


# =============================================================================
# P2: Entry-Level Review Block
# =============================================================================

def build_review_block(item):
    """Build entry-level review block."""
    # Calculate next review due (6 months from last review)
    last_reviewed = item.get('last_reviewed_at')
    if last_reviewed:
        try:
            last_date = datetime.strptime(last_reviewed, '%Y-%m-%d')
            next_due = last_date + timedelta(days=180)
            next_review_due = next_due.strftime('%Y-%m-%d')
        except ValueError:
            next_review_due = None
    else:
        next_review_due = None

    # Get existing review status
    data_quality = item.get('data_quality', {})
    review_status = data_quality.get('review_status', 'needs_review')

    return {
        "status": review_status,
        "last_reviewed_at": last_reviewed,
        "next_review_due": next_review_due,
        "reviewed_by": item.get('reviewed_by', 'system'),
        "change_log": []  # Start empty, will accumulate
    }


# =============================================================================
# Main Update Function
# =============================================================================

def apply_p0_p1_updates():
    """Apply all P0 and P1 updates."""

    # Load current data
    with open(BANNED_FILE, 'r') as f:
        data = json.load(f)

    stats = {
        'entity_type_added': 0,
        'regulatory_actions_added': 0,
        'effective_period_added': 0,
        'review_block_added': 0,
        'by_entity_type': {}
    }

    ingredients = data.get('ingredients', [])

    for item in ingredients:
        item_id = item.get('id', '')

        # P0: Add entity_type
        entity_type = get_entity_type(item)
        item['entity_type'] = entity_type
        stats['entity_type_added'] += 1
        stats['by_entity_type'][entity_type] = stats['by_entity_type'].get(entity_type, 0) + 1

        # P1: Add/enhance regulatory_actions
        if 'regulatory_actions' not in item or not item['regulatory_actions']:
            item['regulatory_actions'] = build_regulatory_actions(item)
        else:
            # Normalize existing actions
            normalized_actions = []
            for action in item['regulatory_actions']:
                normalized = {
                    "action_type": action.get('action_type', 'unknown'),
                    "authority": action.get('agency', action.get('authority', 'unknown')),
                    "jurisdiction_code": action.get('jurisdiction_code'),
                    "scope": action.get('scope', determine_scope(item)),
                    "effective_period": {
                        "start": parse_date_string(action.get('date')),
                        "end": None
                    },
                    "summary": action.get('summary', ''),
                    "reference_ids": action.get('reference_ids', [])
                }
                normalized_actions.append(normalized)
            item['regulatory_actions'] = normalized_actions
        stats['regulatory_actions_added'] += 1

        # P1: Add effective_period
        item['effective_period'] = build_effective_period(item)
        stats['effective_period_added'] += 1

        # P2: Add entry-level review block
        item['review'] = build_review_block(item)
        stats['review_block_added'] += 1

    # Update schema version
    data['schema_version'] = '3.1.0'
    data['last_updated'] = datetime.now().strftime('%Y-%m-%d')

    # Add to governance change log
    if 'governance' in data and 'change_log' in data['governance']:
        data['governance']['change_log'].append({
            "version": "3.1.0",
            "date": datetime.now().strftime('%Y-%m-%d'),
            "changes": [
                "P0: Added entity_type to all entries (ingredient|product|class|contaminant|threat)",
                "P1: Added regulatory_actions[] with authority, scope, effective_period",
                "P1: Added effective_period object with ISO dates",
                "P2: Added entry-level review block with next_review_due"
            ]
        })

    # Update schema_mappings with new fields
    if 'schema_mappings' in data:
        data['schema_mappings']['entity_type_enum'] = ENTITY_TYPE_ENUM
        data['schema_mappings']['action_type_enum'] = [
            "ban", "restriction", "recall", "warning", "scheduling",
            "enforcement", "import_alert", "scheduling_recommendation"
        ]
        data['schema_mappings']['scope_enum'] = ["supplement", "food", "drug", "sport", "cosmetic"]

    # Save updated data
    with open(BANNED_FILE, 'w') as f:
        json.dump(data, f, indent=2)

    return stats


def print_summary(stats):
    """Print summary of updates applied."""
    print("\n" + "=" * 60)
    print("P0 & P1 Update Summary")
    print("=" * 60)
    print(f"Schema version: 3.1.0")
    print(f"\nP0: entity_type added to {stats['entity_type_added']} entries")
    print(f"    Distribution: {stats['by_entity_type']}")
    print(f"\nP1: regulatory_actions[] normalized: {stats['regulatory_actions_added']}")
    print(f"P1: effective_period added: {stats['effective_period_added']}")
    print(f"\nP2: review block added: {stats['review_block_added']}")
    print("=" * 60)


if __name__ == '__main__':
    print("Applying P0 & P1 updates to banned_recalled_ingredients.json...")
    stats = apply_p0_p1_updates()
    print_summary(stats)
    print("\nDone!")
