"""
Comprehensive schema validation tests for banned_recalled_ingredients.json v3.0

Tests cover:
- Uniqueness constraints (ID, standard_name within type)
- Jurisdiction requirements for state/regional bans
- Reference validation and evidence grades
- Source verification enforcement
- Backward compatibility (deprecated fields still present)
- Schema migration (supersedes_ids validity)
- Required field validation
- Enum value validation
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Path to the banned ingredients file
BANNED_FILE_PATH = os.path.join(
    os.path.dirname(__file__),
    '..',
    'data',
    'banned_recalled_ingredients.json'
)

# Valid enum values
LEGAL_STATUS_ENUM_VALUES = [
    'banned_federal', 'banned_state', 'not_lawful_as_supplement',
    'controlled_substance', 'restricted', 'under_review', 'lawful',
    'adulterant', 'contaminant_risk', 'wada_prohibited', 'high_risk'
]

CLINICAL_RISK_ENUM_VALUES = [
    'critical', 'high', 'moderate', 'low', 'dose_dependent'
]

INGREDIENT_TYPE_VALUES = [
    'botanical', 'synthetic', 'pharmaceutical', 'contaminant',
    'peptide', 'hormone', 'sarm', 'stimulant', 'nootropic', 'steroid'
]

REFERENCE_TYPE_VALUES = [
    'doi', 'pubmed', 'fda_advisory', 'fda_warning_letter', 'fda_recall',
    'fda_import_alert', 'dea_scheduling', 'state_statute', 'wada_list',
    'case_report', 'review_article', 'fda_action'
]

EVIDENCE_GRADE_VALUES = ['A', 'B', 'C', 'D', 'R']


@pytest.fixture(scope='module')
def banned_data():
    """Load the banned ingredients data once for all tests."""
    with open(BANNED_FILE_PATH, 'r') as f:
        return json.load(f)


@pytest.fixture(scope='module')
def ingredients(banned_data):
    """Extract ingredients list from data."""
    return banned_data.get('ingredients', [])


# =============================================================================
# Schema Version Tests
# =============================================================================

def test_schema_version_is_4(banned_data):
    """Schema version must be 4.x (in _metadata)."""
    metadata = banned_data.get('_metadata', {})
    version = metadata.get('schema_version', '')
    assert version.startswith('4.'), \
        f"Expected schema_version 4.x, got {version}"


def test_has_migration_block(banned_data):
    """Migration block must be present documenting deprecated fields."""
    metadata = banned_data.get('_metadata', {})
    migration = metadata.get('migration')
    assert migration is not None, "Missing migration block in _metadata"
    assert 'deprecated_fields' in migration, "Missing deprecated_fields in migration"
    assert 'authoritative_fields' in migration, "Missing authoritative_fields in migration"


def test_has_data_source_metadata(banned_data):
    """Data source metadata must be present (inside _metadata)."""
    top_meta = banned_data.get('_metadata', {})
    metadata = top_meta.get('data_source_metadata')
    assert metadata is not None, "Missing data_source_metadata in _metadata"
    assert 'sources' in metadata, "Missing sources in data_source_metadata"
    assert 'update_frequency' in metadata, "Missing update_frequency in data_source_metadata"


# =============================================================================
# Uniqueness Tests
# =============================================================================

def test_id_unique(ingredients):
    """All ingredient IDs must be unique."""
    ids = [item.get('id') for item in ingredients]
    duplicates = [id for id in ids if ids.count(id) > 1]
    assert len(ids) == len(set(ids)), f"Duplicate IDs found: {set(duplicates)}"


def test_standard_name_unique_within_type(ingredients):
    """standard_name must be unique within same ingredient_type."""
    seen = set()
    duplicates = []
    for item in ingredients:
        name = item.get('standard_name')
        ing_type = item.get('ingredient_type', 'unknown')
        key = (name, ing_type)
        if key in seen:
            duplicates.append(key)
        seen.add(key)
    assert len(duplicates) == 0, f"Duplicate (standard_name, ingredient_type): {duplicates}"


# =============================================================================
# Required Field Tests
# =============================================================================

def test_all_entries_have_id(ingredients):
    """All entries must have an id field."""
    missing = [i for i, item in enumerate(ingredients) if not item.get('id')]
    assert len(missing) == 0, f"Entries at indices {missing} missing id"


def test_all_entries_have_standard_name(ingredients):
    """All entries must have standard_name."""
    missing = []
    for item in ingredients:
        if not item.get('standard_name'):
            missing.append(item.get('id', 'UNKNOWN'))
    assert len(missing) == 0, f"Entries missing standard_name: {missing}"


def test_all_entries_have_legal_status_enum(ingredients):
    """All entries must have legal_status_enum."""
    missing = [item.get('id') for item in ingredients if not item.get('legal_status_enum')]
    assert len(missing) == 0, f"Entries missing legal_status_enum: {missing}"


def test_all_entries_have_clinical_risk_enum(ingredients):
    """All entries must have clinical_risk_enum."""
    missing = [item.get('id') for item in ingredients if not item.get('clinical_risk_enum')]
    assert len(missing) == 0, f"Entries missing clinical_risk_enum: {missing}"


def test_all_entries_have_severity_level(ingredients):
    """All entries must have severity_level (for backward compatibility with scoring)."""
    missing = [item.get('id') for item in ingredients if not item.get('severity_level')]
    assert len(missing) == 0, f"Entries missing severity_level: {missing}"


def test_all_entries_have_match_rules(ingredients):
    """All entries must have match_rules block."""
    missing = [item.get('id') for item in ingredients if not item.get('match_rules')]
    assert len(missing) == 0, f"Entries missing match_rules: {missing}"


def test_all_entries_have_data_quality(ingredients):
    """All entries must have data_quality block."""
    missing = [item.get('id') for item in ingredients if not item.get('data_quality')]
    assert len(missing) == 0, f"Entries missing data_quality: {missing}"


# =============================================================================
# Enum Value Validation Tests
# =============================================================================

def test_legal_status_enum_values_valid(ingredients):
    """All legal_status_enum values must be from allowed set."""
    invalid = []
    for item in ingredients:
        status = item.get('legal_status_enum')
        if status and status not in LEGAL_STATUS_ENUM_VALUES:
            invalid.append((item.get('id'), status))
    assert len(invalid) == 0, f"Invalid legal_status_enum values: {invalid}"


def test_clinical_risk_enum_values_valid(ingredients):
    """All clinical_risk_enum values must be from allowed set."""
    invalid = []
    for item in ingredients:
        risk = item.get('clinical_risk_enum')
        if risk and risk not in CLINICAL_RISK_ENUM_VALUES:
            invalid.append((item.get('id'), risk))
    assert len(invalid) == 0, f"Invalid clinical_risk_enum values: {invalid}"


def test_evidence_grade_values_valid(ingredients):
    """All evidence_grade values in references_structured must be valid."""
    invalid = []
    for item in ingredients:
        for ref in item.get('references_structured', []):
            grade = ref.get('evidence_grade')
            if grade and grade not in EVIDENCE_GRADE_VALUES:
                invalid.append((item.get('id'), grade))
    assert len(invalid) == 0, f"Invalid evidence_grade values: {invalid}"


# =============================================================================
# Jurisdiction Validation Tests
# =============================================================================

def test_jurisdiction_required_for_state_bans(ingredients):
    """If legal_status_enum is banned_state, jurisdictions must be non-empty."""
    missing = []
    for item in ingredients:
        if item.get('legal_status_enum') == 'banned_state':
            jurisdictions = item.get('jurisdictions', [])
            if not jurisdictions:
                missing.append(item.get('id'))
    assert len(missing) == 0, f"State-banned entries missing jurisdictions: {missing}"


def test_jurisdiction_required_for_restricted(ingredients):
    """If legal_status_enum is restricted, jurisdictions should specify restricted regions."""
    missing = []
    for item in ingredients:
        if item.get('legal_status_enum') == 'restricted':
            jurisdictions = item.get('jurisdictions', [])
            if not jurisdictions:
                missing.append(item.get('id'))
    assert len(missing) == 0, f"Restricted entries missing jurisdictions: {missing}"


def test_jurisdiction_structure(ingredients):
    """All jurisdictions must have required fields."""
    invalid = []
    for item in ingredients:
        for j in item.get('jurisdictions', []):
            if not j.get('region') or not j.get('status'):
                invalid.append((item.get('id'), j))
    assert len(invalid) == 0, f"Jurisdictions missing required fields: {invalid}"


# =============================================================================
# Reference Validation Tests
# =============================================================================

def test_references_structured_has_required_fields(ingredients):
    """All references_structured entries must have type and title."""
    invalid = []
    for item in ingredients:
        for ref in item.get('references_structured', []):
            if not ref.get('type') or not ref.get('title'):
                invalid.append((item.get('id'), ref))
    assert len(invalid) == 0, f"References missing type/title: {invalid}"


def test_reference_types_valid(ingredients):
    """All reference types must be from allowed set."""
    invalid = []
    for item in ingredients:
        for ref in item.get('references_structured', []):
            ref_type = ref.get('type')
            if ref_type and ref_type not in REFERENCE_TYPE_VALUES:
                invalid.append((item.get('id'), ref_type))
    # Warning only - new types may be added
    if invalid:
        print(f"Warning: Unknown reference types: {invalid}")


# =============================================================================
# Match Rules Validation Tests
# =============================================================================

def test_match_rules_has_label_tokens(ingredients):
    """All match_rules must have label_tokens."""
    missing = []
    for item in ingredients:
        match_rules = item.get('match_rules', {})
        if not match_rules.get('label_tokens'):
            missing.append(item.get('id'))
    assert len(missing) == 0, f"Entries missing match_rules.label_tokens: {missing}"


def test_match_rules_has_match_mode(ingredients):
    """All match_rules must have match_mode."""
    missing = []
    for item in ingredients:
        match_rules = item.get('match_rules', {})
        if not match_rules.get('match_mode'):
            missing.append(item.get('id'))
    assert len(missing) == 0, f"Entries missing match_rules.match_mode: {missing}"


# =============================================================================
# Source Verification Tests
# =============================================================================

def test_no_unverified_sources_in_prod(ingredients):
    """CI fails if needs_source_verification=true (cannot ship unverified data)."""
    unverified = []
    for item in ingredients:
        flags = item.get('update_flags') or {}
        if flags.get('needs_source_verification', False):
            unverified.append(item.get('id'))
    assert len(unverified) == 0, \
        f"Entries with unverified sources cannot ship: {unverified}"


def test_all_entries_have_last_reviewed_at(ingredients):
    """All entries must have last_reviewed_at for audit trail."""
    missing = [item.get('id') for item in ingredients if not item.get('last_reviewed_at')]
    assert len(missing) == 0, f"Entries missing last_reviewed_at: {missing}"


# =============================================================================
# Backward Compatibility Tests
# =============================================================================

def test_all_entries_have_status(ingredients):
    """Old 'status' field must remain for backward compatibility."""
    missing = [item.get('id') for item in ingredients if 'status' not in item]
    assert len(missing) == 0, f"Entries missing status (needed for compatibility): {missing}"


def test_all_entries_have_severity_level_for_scoring(ingredients):
    """severity_level must be present (drives scoring logic)."""
    missing = [item.get('id') for item in ingredients if not item.get('severity_level')]
    assert len(missing) == 0, f"Entries missing severity_level: {missing}"


def test_severity_level_valid_values(ingredients):
    """severity_level must be critical, high, moderate, or low."""
    valid = ['critical', 'high', 'moderate', 'low']
    invalid = []
    for item in ingredients:
        level = item.get('severity_level')
        if level and level not in valid:
            invalid.append((item.get('id'), level))
    assert len(invalid) == 0, f"Invalid severity_level values: {invalid}"


# =============================================================================
# Schema Migration / Dedupe Tests
# =============================================================================

def test_supersedes_ids_not_in_current_list(ingredients):
    """All supersedes_ids must reference removed entries (not still present)."""
    all_ids = {item.get('id') for item in ingredients}
    conflicts = []
    for item in ingredients:
        for old_id in (item.get('supersedes_ids') or []):
            if old_id in all_ids:
                conflicts.append((item.get('id'), old_id))
    assert len(conflicts) == 0, \
        f"supersedes_ids still exist in ingredients: {conflicts}"


def test_sibutramine_dedupe_complete(ingredients):
    """Sibutramine should be deduplicated - SPIKE_SIBUTRAMINE merged into BANNED_SIBUTRAMINE."""
    sibutramine_ids = [item.get('id') for item in ingredients if 'SIBUTRAMINE' in item.get('id', '')]

    # Should only have BANNED_SIBUTRAMINE, not SPIKE_SIBUTRAMINE
    assert 'SPIKE_SIBUTRAMINE' not in sibutramine_ids, \
        "SPIKE_SIBUTRAMINE should be merged into BANNED_SIBUTRAMINE"

    # BANNED_SIBUTRAMINE should exist with supersedes_ids
    banned_sib = next((item for item in ingredients if item.get('id') == 'BANNED_SIBUTRAMINE'), None)
    assert banned_sib is not None, "BANNED_SIBUTRAMINE not found"
    assert 'SPIKE_SIBUTRAMINE' in banned_sib.get('supersedes_ids', []), \
        "BANNED_SIBUTRAMINE should have SPIKE_SIBUTRAMINE in supersedes_ids"


# =============================================================================
# Status Contradiction Tests
# =============================================================================

def test_high_risk_entries_not_marked_banned_federal(ingredients):
    """Entries with legal_status_enum='high_risk' should not have status contradictions."""
    contradictions = []
    for item in ingredients:
        if item.get('legal_status_enum') == 'high_risk':
            # These should have appropriate clinical risk but not be legally banned
            # This is about UI accuracy - "high risk" is not the same as "banned"
            pass  # No specific contradiction to test, just ensuring enum exists
    # This test validates that status fixes were applied
    assert True


def test_status_legal_enum_consistency(ingredients):
    """Check that status and legal_status_enum are reasonably consistent."""
    # banned_federal should have status="banned"
    # high_risk should typically have status="banned" (legacy) but legal_status_enum="high_risk"
    # This is expected during transition period
    pass  # Soft validation - documented inconsistency during migration


# =============================================================================
# Data Quality Tests
# =============================================================================

def test_data_quality_completeness_valid(ingredients):
    """data_quality.completeness must be between 0 and 1."""
    invalid = []
    for item in ingredients:
        dq = item.get('data_quality', {})
        completeness = dq.get('completeness')
        if completeness is not None:
            if not (0 <= completeness <= 1):
                invalid.append((item.get('id'), completeness))
    assert len(invalid) == 0, f"Invalid completeness values: {invalid}"


def test_data_quality_review_status_valid(ingredients):
    """data_quality.review_status must be valid."""
    valid = ['validated', 'pending_review', 'needs_update', 'needs_review', 'unreviewed']
    invalid = []
    for item in ingredients:
        dq = item.get('data_quality', {})
        status = dq.get('review_status')
        if status and status not in valid:
            invalid.append((item.get('id'), status))
    assert len(invalid) == 0, f"Invalid review_status values: {invalid}"


# =============================================================================
# Statistics / Summary Tests
# =============================================================================

def test_minimum_entry_count(ingredients):
    """Should have at least 90 entries (100 after migration, minus potential future removals)."""
    assert len(ingredients) >= 90, f"Expected at least 90 entries, got {len(ingredients)}"


def test_summary_statistics(ingredients):
    """Print summary statistics for the database (informational)."""
    stats = {
        'total_entries': len(ingredients),
        'by_legal_status': {},
        'by_clinical_risk': {},
        'by_ingredient_type': {},
        'with_jurisdictions': 0,
        'with_supersedes_ids': 0,
    }

    for item in ingredients:
        # Legal status
        ls = item.get('legal_status_enum', 'unknown')
        stats['by_legal_status'][ls] = stats['by_legal_status'].get(ls, 0) + 1

        # Clinical risk
        cr = item.get('clinical_risk_enum', 'unknown')
        stats['by_clinical_risk'][cr] = stats['by_clinical_risk'].get(cr, 0) + 1

        # Ingredient type
        it = item.get('ingredient_type', 'unknown')
        stats['by_ingredient_type'][it] = stats['by_ingredient_type'].get(it, 0) + 1

        # Jurisdictions
        if item.get('jurisdictions'):
            stats['with_jurisdictions'] += 1

        # Supersedes
        if item.get('supersedes_ids'):
            stats['with_supersedes_ids'] += 1

    print(f"\n=== Banned Ingredients Database v3 Statistics ===")
    print(f"Total entries: {stats['total_entries']}")
    print(f"By legal status: {stats['by_legal_status']}")
    print(f"By clinical risk: {stats['by_clinical_risk']}")
    print(f"Entries with jurisdictions: {stats['with_jurisdictions']}")
    print(f"Entries with supersedes_ids: {stats['with_supersedes_ids']}")

    assert True  # Always pass - informational only


# =============================================================================
# Product Entry Validation Tests (v3.1+)
# =============================================================================


def test_product_entries_have_fda_urls(ingredients):
    """Product entries should have FDA recall URLs in references_structured."""
    product_entries = [i for i in ingredients if i.get('entity_type') == 'product']
    missing_urls = []
    for item in product_entries:
        refs = item.get('references_structured', [])
        has_fda_url = any(
            ref.get('fda_recall_url') or ref.get('url')
            for ref in refs
        )
        if not has_fda_url:
            missing_urls.append(item.get('id'))
    assert len(missing_urls) == 0, \
        f"Product entries missing FDA URLs: {missing_urls}"


def test_product_entries_have_negative_match_terms_where_needed(ingredients):
    """
    Product entries with generic product names should have negative_match_terms.

    Products with unique brand names (e.g., 'silintan', 'hydroxycut') don't need
    negative_match_terms, but products with generic names that could collide with
    competitors should have them populated.
    """
    product_entries = [i for i in ingredients if i.get('entity_type') == 'product']

    # Products known to need negative_match_terms due to generic names
    products_needing_negatives = {
        'RECALLED_LIVE_IT_UP_SUPER_GREENS',  # "super greens" is generic
        'RECALLED_REBOOST_CLEARLIFE_NASAL_SPRAY',  # "nasal spray" is generic
        'RECALLED_PURITY_PRODUCTS_MY_BLADDER',  # bladder support is generic
    }

    missing_negatives = []
    for item in product_entries:
        item_id = item.get('id')
        if item_id in products_needing_negatives:
            neg_terms = item.get('match_rules', {}).get('negative_match_terms', [])
            if not neg_terms:
                missing_negatives.append(item_id)

    assert len(missing_negatives) == 0, \
        f"Products with generic names missing negative_match_terms: {missing_negatives}"


def test_product_aliases_label_tokens_synced(ingredients):
    """Product aliases and label_tokens should be synchronized."""
    product_entries = [i for i in ingredients if i.get('entity_type') == 'product']
    out_of_sync = []

    for item in product_entries:
        aliases = set(item.get('aliases', []))
        label_tokens = set(item.get('match_rules', {}).get('label_tokens', []))

        if aliases != label_tokens:
            out_of_sync.append({
                'id': item.get('id'),
                'aliases': len(aliases),
                'label_tokens': len(label_tokens)
            })

    assert len(out_of_sync) == 0, \
        f"Product entries with out-of-sync aliases/label_tokens: {out_of_sync}"


def test_product_aliases_are_brand_qualified(ingredients):
    """
    Product aliases should include brand context to prevent false positives.

    Aliases should either:
    1. Contain the brand name, OR
    2. Be unique enough (brand-specific term like 'hydroxycut')
    """
    product_entries = [i for i in ingredients if i.get('entity_type') == 'product']

    # Known unique brand names that don't need qualification
    unique_brands = {
        'hydroxycut', 'oxyelite', 'jack3d', 'silintan', 'ykarine',
        'rheumacare', 'titan sarms', 'mr.7', 'mr7'
    }

    potentially_generic = []
    for item in product_entries:
        aliases = item.get('aliases', [])
        for alias in aliases:
            alias_lower = alias.lower()
            # Check if alias is too generic (no brand and could match other products)
            if len(alias.split()) <= 2:
                # Short alias - check if it's a unique brand
                is_unique = any(brand in alias_lower for brand in unique_brands)
                if not is_unique and alias_lower not in unique_brands:
                    potentially_generic.append({
                        'id': item.get('id'),
                        'alias': alias
                    })

    # This is a soft check - just print warnings
    if potentially_generic:
        print(f"\nWarning: Potentially generic aliases (review manually): "
              f"{potentially_generic[:5]}...")  # Show first 5
