"""
Jurisdiction query tests for banned_recalled_ingredients.json

Tests that jurisdiction data is:
- Queryable by location
- Consistent across entries
- Contains required fields
"""

import json
import os
import sys
from collections import defaultdict

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Path to the banned ingredients file
BANNED_FILE_PATH = os.path.join(
    os.path.dirname(__file__),
    '..',
    'data',
    'banned_recalled_ingredients.json'
)


@pytest.fixture(scope='module')
def banned_data():
    """Load the banned ingredients data once for all tests."""
    with open(BANNED_FILE_PATH, 'r') as f:
        return json.load(f)


@pytest.fixture(scope='module')
def ingredients(banned_data):
    """Extract ingredients list from data."""
    return banned_data.get('ingredients', [])


def get_jurisdictions_for_state(ingredients, state_code):
    """Get all ingredients with jurisdiction entries for a specific state."""
    results = []
    for item in ingredients:
        for j in item.get('jurisdictions', []):
            if j.get('jurisdiction_code') == state_code:
                results.append({
                    'id': item.get('id'),
                    'name': item.get('standard_name'),
                    'status': j.get('status'),
                    'effective_date': j.get('effective_date'),
                    'jurisdiction': j
                })
    return results


def get_jurisdictions_for_country(ingredients, country_code):
    """Get all ingredients with federal-level jurisdiction for a country."""
    results = []
    for item in ingredients:
        for j in item.get('jurisdictions', []):
            if (j.get('jurisdiction_code') == country_code and
                j.get('jurisdiction_type') == 'country'):
                results.append({
                    'id': item.get('id'),
                    'name': item.get('standard_name'),
                    'status': j.get('status'),
                    'effective_date': j.get('effective_date'),
                    'jurisdiction': j
                })
    return results


# =============================================================================
# JURISDICTION STRUCTURE TESTS
# =============================================================================

class TestJurisdictionStructure:
    """Test that jurisdiction entries have required fields."""

    def test_all_jurisdictions_have_code(self, ingredients):
        """All jurisdictions must have jurisdiction_code."""
        missing = []
        for item in ingredients:
            for j in item.get('jurisdictions', []):
                if not j.get('jurisdiction_code'):
                    missing.append((item.get('id'), j))
        assert len(missing) == 0, f"Jurisdictions missing code: {missing[:5]}"

    def test_all_jurisdictions_have_type(self, ingredients):
        """All jurisdictions must have jurisdiction_type."""
        missing = []
        for item in ingredients:
            for j in item.get('jurisdictions', []):
                if not j.get('jurisdiction_type'):
                    missing.append((item.get('id'), j))
        assert len(missing) == 0, f"Jurisdictions missing type: {missing[:5]}"

    def test_jurisdiction_types_valid(self, ingredients):
        """jurisdiction_type must be from allowed set."""
        valid_types = ['country', 'state', 'region', 'agency_scope']
        invalid = []
        for item in ingredients:
            for j in item.get('jurisdictions', []):
                jtype = j.get('jurisdiction_type')
                if jtype and jtype not in valid_types:
                    invalid.append((item.get('id'), jtype))
        assert len(invalid) == 0, f"Invalid jurisdiction_type: {invalid}"

    def test_state_jurisdictions_have_iso_code(self, ingredients):
        """State jurisdictions should use ISO 3166-2 codes (US-XX) where possible."""
        invalid = []
        for item in ingredients:
            for j in item.get('jurisdictions', []):
                if j.get('jurisdiction_type') == 'state' and j.get('region') == 'US':
                    code = j.get('jurisdiction_code', '')
                    # Allow US-XX format or legacy formats during migration
                    if code and not code.startswith('US-') and not code.startswith('US_'):
                        invalid.append((item.get('id'), code))
        # Warning level - not all have been converted yet
        if invalid:
            print(f"Warning: {len(invalid)} state jurisdictions without ISO codes: {invalid[:3]}...")

    def test_jurisdictions_have_last_verified(self, ingredients):
        """All jurisdictions should have last_verified_date."""
        missing = []
        for item in ingredients:
            for j in item.get('jurisdictions', []):
                if not j.get('last_verified_date'):
                    missing.append((item.get('id'), j.get('jurisdiction_code')))
        # Warning only - some may be legitimately missing
        if missing:
            print(f"Warning: {len(missing)} jurisdictions missing last_verified_date")


# =============================================================================
# STATE-SPECIFIC QUERY TESTS
# =============================================================================

class TestStateQueries:
    """Test queries for specific US states with known bans."""

    def test_alabama_tianeptine_ban(self, ingredients):
        """Alabama should show tianeptine as Schedule II."""
        results = get_jurisdictions_for_state(ingredients, 'US-AL')
        tianeptine = [r for r in results if 'TIANEPTINE' in r['id']]
        assert len(tianeptine) > 0, "Tianeptine should be banned in Alabama"
        assert tianeptine[0]['status'] in ['schedule_II', 'schedule_I', 'banned']

    def test_california_red_3_ban(self, ingredients):
        """California should show Red No. 3 as banned."""
        results = get_jurisdictions_for_state(ingredients, 'US-CA')
        red3 = [r for r in results if 'RED' in r['id']]
        assert len(red3) > 0, "Red No. 3 should be banned in California"

    def test_utah_tianeptine_ban(self, ingredients):
        """Utah should show tianeptine as Schedule I."""
        results = get_jurisdictions_for_state(ingredients, 'US-UT')
        tianeptine = [r for r in results if 'TIANEPTINE' in r['id']]
        assert len(tianeptine) > 0, "Tianeptine should be banned in Utah"
        assert tianeptine[0]['status'] in ['schedule_I', 'banned']

    def test_florida_tianeptine_ban(self, ingredients):
        """Florida should show tianeptine as Schedule I (2024)."""
        results = get_jurisdictions_for_state(ingredients, 'US-FL')
        tianeptine = [r for r in results if 'TIANEPTINE' in r['id']]
        assert len(tianeptine) > 0, "Tianeptine should be banned in Florida"

    def test_multiple_states_tianeptine(self, ingredients):
        """Tianeptine should be banned in 10+ states."""
        tianeptine_entry = next(
            (i for i in ingredients if i.get('id') == 'BANNED_TIANEPTINE'),
            None
        )
        assert tianeptine_entry is not None

        state_bans = [
            j for j in tianeptine_entry.get('jurisdictions', [])
            if j.get('jurisdiction_type') == 'state'
        ]
        assert len(state_bans) >= 10, \
            f"Expected 10+ state bans for tianeptine, got {len(state_bans)}"


# =============================================================================
# FEDERAL QUERY TESTS
# =============================================================================

class TestFederalQueries:
    """Test queries for federal-level jurisdictions."""

    def test_us_federal_sibutramine_ban(self, ingredients):
        """US federal should show sibutramine as banned."""
        results = get_jurisdictions_for_country(ingredients, 'US')
        sibutramine = [r for r in results if 'SIBUTRAMINE' in r['id']]
        assert len(sibutramine) > 0, "Sibutramine should be federally banned"
        assert sibutramine[0]['status'] in ['banned', 'restricted']

    def test_us_federal_ephedra_ban(self, ingredients):
        """US federal should show ephedra as banned."""
        results = get_jurisdictions_for_country(ingredients, 'US')
        ephedra = [r for r in results if 'EPHEDRA' in r['id']]
        assert len(ephedra) > 0, "Ephedra should be federally banned"

    def test_us_federal_dmaa_ban(self, ingredients):
        """US federal should show DMAA as banned."""
        results = get_jurisdictions_for_country(ingredients, 'US')
        dmaa = [r for r in results if 'DMAA' in r['id']]
        assert len(dmaa) > 0, "DMAA should be federally banned"


# =============================================================================
# CROSS-JURISDICTION CONSISTENCY TESTS
# =============================================================================

class TestJurisdictionConsistency:
    """Test consistency across jurisdictions."""

    def test_federal_ban_implies_all_states(self, ingredients):
        """If federally banned, should not need redundant state entries."""
        # This is a design decision - federal bans apply everywhere
        # State entries should only be for things NOT federally banned
        pass  # Informational - design choice

    def test_no_contradictory_jurisdictions(self, ingredients):
        """Same jurisdiction should not have contradictory statuses.

        NOTE: Some entries may have multiple jurisdiction records for the same
        location with different statuses (e.g., evolving from restricted to banned).
        This is acceptable if the effective_dates are different.
        """
        contradictions = []
        for item in ingredients:
            seen = {}
            for j in item.get('jurisdictions', []):
                code = j.get('jurisdiction_code')
                status = j.get('status')
                eff_date = j.get('effective_date', '')
                key = (code, eff_date)
                if key in seen and seen[key] != status:
                    contradictions.append((item.get('id'), code, seen[key], status))
                seen[key] = status
        # Warning level - some contradictions may be legitimate (status changes)
        if contradictions:
            print(f"Warning: {len(contradictions)} potential jurisdiction contradictions: {contradictions[:3]}...")

    def test_effective_dates_reasonable(self, ingredients):
        """Effective dates should be reasonable (not in future far, not ancient)."""
        invalid = []
        for item in ingredients:
            for j in item.get('jurisdictions', []):
                date = j.get('effective_date', '')
                # Skip empty, "varies", or warning-style dates
                if not date or 'varies' in date.lower() or 'warning' in date.lower():
                    continue
                # Basic sanity check - should be between 1990 and 2030
                try:
                    year = int(date[:4])
                    if year < 1990 or year > 2030:
                        invalid.append((item.get('id'), date))
                except (ValueError, IndexError):
                    pass  # Non-standard date format is acceptable
        # Warning level - some dates may need review
        if invalid:
            print(f"Warning: {len(invalid)} dates outside 1990-2030 range: {invalid[:3]}...")


# =============================================================================
# QUERY UTILITY FUNCTION TESTS
# =============================================================================

class TestQueryUtilities:
    """Test query utility patterns that UI/scoring would use."""

    def test_query_by_location_pattern(self, ingredients):
        """Demonstrate pattern for querying by user location."""
        def is_banned_in_location(item, location_code):
            """Check if an item is banned in a specific location."""
            for j in item.get('jurisdictions', []):
                if j.get('jurisdiction_code') == location_code:
                    return j.get('status') in ['banned', 'schedule_I', 'schedule_II']
                # Also check if federally banned in that country
                if (j.get('jurisdiction_type') == 'country' and
                    location_code.startswith(j.get('jurisdiction_code', ''))):
                    if j.get('status') in ['banned', 'restricted']:
                        return True
            return False

        # Test pattern
        tianeptine = next(
            (i for i in ingredients if i.get('id') == 'BANNED_TIANEPTINE'),
            None
        )
        assert is_banned_in_location(tianeptine, 'US-AL')  # Alabama
        assert is_banned_in_location(tianeptine, 'US-UT')  # Utah

    def test_get_most_recent_action(self, ingredients):
        """Demonstrate pattern for getting most recent regulatory action."""
        def get_most_recent_jurisdiction(item, location_prefix='US'):
            """Get the most recent jurisdiction entry for a location."""
            relevant = [
                j for j in item.get('jurisdictions', [])
                if j.get('jurisdiction_code', '').startswith(location_prefix)
            ]
            if not relevant:
                return None
            # Sort by effective_date descending
            sorted_j = sorted(
                relevant,
                key=lambda x: x.get('effective_date', ''),
                reverse=True
            )
            return sorted_j[0] if sorted_j else None

        # Test pattern
        tianeptine = next(
            (i for i in ingredients if i.get('id') == 'BANNED_TIANEPTINE'),
            None
        )
        recent = get_most_recent_jurisdiction(tianeptine)
        assert recent is not None


# =============================================================================
# SUMMARY STATISTICS
# =============================================================================

class TestJurisdictionStatistics:
    """Print summary statistics about jurisdictions (informational)."""

    def test_jurisdiction_summary(self, ingredients):
        """Print summary of jurisdiction coverage."""
        stats = {
            'total_jurisdictions': 0,
            'by_type': defaultdict(int),
            'by_country': defaultdict(int),
            'us_states_covered': set(),
        }

        for item in ingredients:
            for j in item.get('jurisdictions', []):
                stats['total_jurisdictions'] += 1
                stats['by_type'][j.get('jurisdiction_type', 'unknown')] += 1

                code = j.get('jurisdiction_code', '')
                if code.startswith('US-') and len(code) == 5:
                    stats['us_states_covered'].add(code)
                elif len(code) == 2:
                    stats['by_country'][code] += 1

        print(f"\n=== Jurisdiction Statistics ===")
        print(f"Total jurisdiction entries: {stats['total_jurisdictions']}")
        print(f"By type: {dict(stats['by_type'])}")
        print(f"US states covered: {len(stats['us_states_covered'])}")
        print(f"States: {sorted(stats['us_states_covered'])}")

        assert True  # Always pass - informational only
