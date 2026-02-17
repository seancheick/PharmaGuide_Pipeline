"""
Test match ledger functionality.

These tests ensure that:
1. MatchLedgerBuilder correctly tracks matches across domains
2. Coverage metrics are calculated correctly
3. Unmatched lists are properly generated
4. Ledger schema is correct
"""

import pytest
from match_ledger import (
    MatchLedgerBuilder,
    LedgerEntry,
    DOMAIN_INGREDIENTS,
    DOMAIN_ADDITIVES,
    DOMAIN_ALLERGENS,
    DOMAIN_MANUFACTURER,
    DOMAIN_DELIVERY,
    DOMAIN_CLAIMS,
    DECISION_MATCHED,
    DECISION_UNMATCHED,
    DECISION_REJECTED,
    DECISION_SKIPPED,
    DECISION_RECOGNIZED_NON_SCORABLE,
    DECISION_RECOGNIZED_BOTANICAL_UNSCORED,
    METHOD_EXACT,
    METHOD_NORMALIZED,
    METHOD_PATTERN,
    METHOD_FUZZY,
    SCHEMA_VERSION,
)


class TestLedgerEntry:
    """Test LedgerEntry dataclass."""

    def test_entry_to_dict(self):
        """Test entry serialization."""
        entry = LedgerEntry(
            domain=DOMAIN_INGREDIENTS,
            raw_source_text="Vitamin B12",
            raw_source_path="activeIngredients[0]",
            normalized_key="vitamin_b12",
            canonical_id="vitamin_b12",
            match_method=METHOD_EXACT,
            confidence=1.0,
            matched_to_name="Vitamin B12",
            decision=DECISION_MATCHED,
        )

        d = entry.to_dict()

        assert d["domain"] == DOMAIN_INGREDIENTS
        assert d["raw_source_text"] == "Vitamin B12"
        assert d["canonical_id"] == "vitamin_b12"
        assert d["decision"] == DECISION_MATCHED


class TestMatchLedgerBuilder:
    """Test MatchLedgerBuilder class."""

    @pytest.fixture
    def builder(self):
        return MatchLedgerBuilder()

    def test_record_match(self, builder):
        """Test recording a successful match."""
        builder.record_match(
            domain=DOMAIN_INGREDIENTS,
            raw_source_text="Vitamin B12",
            raw_source_path="activeIngredients[0]",
            canonical_id="vitamin_b12",
            match_method=METHOD_EXACT,
            matched_to_name="Vitamin B12",
            confidence=1.0,
        )

        assert len(builder.entries) == 1
        assert builder.entries[0].decision == DECISION_MATCHED
        assert builder.entries[0].canonical_id == "vitamin_b12"

    def test_record_unmatched(self, builder):
        """Test recording an unmatched item."""
        builder.record_unmatched(
            domain=DOMAIN_INGREDIENTS,
            raw_source_text="Novel Ingredient",
            raw_source_path="activeIngredients[1]",
            reason="no_match_found",
            candidates=[
                {"canonical_id": "similar_1", "confidence": 0.6},
                {"canonical_id": "similar_2", "confidence": 0.5},
            ],
        )

        assert len(builder.entries) == 1
        assert builder.entries[0].decision == DECISION_UNMATCHED
        assert builder.entries[0].canonical_id is None
        assert len(builder.entries[0].candidates_top3) == 2

    def test_record_rejected(self, builder):
        """Test recording a rejected match."""
        builder.record_rejected(
            domain=DOMAIN_MANUFACTURER,
            raw_source_text="Garden Life",
            raw_source_path="brandName",
            best_match_id="garden_of_life",
            best_match_name="Garden of Life",
            match_method=METHOD_FUZZY,
            confidence=0.7,
            rejection_reason="fuzzy_below_threshold",
        )

        assert len(builder.entries) == 1
        assert builder.entries[0].decision == DECISION_REJECTED
        assert builder.entries[0].decision_reason == "fuzzy_below_threshold"
        # Rejected entry should not have canonical_id
        assert builder.entries[0].canonical_id is None

    def test_record_skipped(self, builder):
        """Test recording a skipped item."""
        builder.record_skipped(
            domain=DOMAIN_INGREDIENTS,
            raw_source_text="Sucralose",
            raw_source_path="inactiveIngredients",
            skip_reason="additive_type_sweetener",
        )

        assert len(builder.entries) == 1
        assert builder.entries[0].decision == DECISION_SKIPPED
        assert builder.entries[0].decision_reason == "additive_type_sweetener"

    def test_coverage_calculation(self, builder):
        """Test coverage percentage calculation."""
        # Add 3 matched and 1 unmatched
        for i in range(3):
            builder.record_match(
                domain=DOMAIN_INGREDIENTS,
                raw_source_text=f"Vitamin {i}",
                raw_source_path=f"activeIngredients[{i}]",
                canonical_id=f"vitamin_{i}",
                match_method=METHOD_EXACT,
                matched_to_name=f"Vitamin {i}",
            )

        builder.record_unmatched(
            domain=DOMAIN_INGREDIENTS,
            raw_source_text="Unknown",
            raw_source_path="activeIngredients[3]",
            reason="no_match",
        )

        ledger = builder.build()
        ing_domain = ledger["domains"][DOMAIN_INGREDIENTS]

        assert ing_domain["total_raw"] == 4
        assert ing_domain["matched"] == 3
        assert ing_domain["unmatched"] == 1
        assert ing_domain["coverage_percent"] == 75.0

    def test_skipped_counts_as_covered(self, builder):
        """Test that skipped items count toward coverage."""
        # Add 1 matched and 1 skipped
        builder.record_match(
            domain=DOMAIN_INGREDIENTS,
            raw_source_text="Vitamin A",
            raw_source_path="activeIngredients[0]",
            canonical_id="vitamin_a",
            match_method=METHOD_EXACT,
            matched_to_name="Vitamin A",
        )

        builder.record_skipped(
            domain=DOMAIN_INGREDIENTS,
            raw_source_text="Gelatin",
            raw_source_path="inactiveIngredients",
            skip_reason="excipient",
        )

        ledger = builder.build()
        ing_domain = ledger["domains"][DOMAIN_INGREDIENTS]

        # 1 matched + 1 skipped = 2 covered out of 2 total = 100%
        assert ing_domain["total_raw"] == 2
        assert ing_domain["coverage_percent"] == 100.0

    def test_normalized_key_auto_computed(self, builder):
        """Test that normalized_key is auto-computed if not provided."""
        builder.record_match(
            domain=DOMAIN_INGREDIENTS,
            raw_source_text="Vitamin B12 (as Methylcobalamin)",
            raw_source_path="activeIngredients[0]",
            canonical_id="vitamin_b12",
            match_method=METHOD_EXACT,
            matched_to_name="Vitamin B12",
        )

        assert builder.entries[0].normalized_key == "vitamin_b12_as_methylcobalamin"

    def test_build_schema_version(self, builder):
        """Test that build includes schema version."""
        ledger = builder.build()
        assert ledger["schema_version"] == SCHEMA_VERSION

    def test_build_summary(self, builder):
        """Test that build includes correct summary."""
        builder.record_match(
            domain=DOMAIN_INGREDIENTS,
            raw_source_text="Vitamin A",
            raw_source_path="active",
            canonical_id="vitamin_a",
            match_method=METHOD_EXACT,
            matched_to_name="Vitamin A",
        )

        builder.record_unmatched(
            domain=DOMAIN_ADDITIVES,
            raw_source_text="Unknown Additive",
            raw_source_path="inactive",
            reason="no_match",
        )

        ledger = builder.build()
        summary = ledger["summary"]

        assert summary["total_entities"] == 2
        assert summary["total_matched"] == 1
        assert summary["total_unmatched"] == 1
        assert "coverage_by_domain" in summary


class TestUnmatchedLists:
    """Test unmatched list generation."""

    @pytest.fixture
    def builder(self):
        return MatchLedgerBuilder()

    def test_unmatched_ingredients_list(self, builder):
        """Test unmatched ingredients list generation."""
        builder.record_unmatched(
            domain=DOMAIN_INGREDIENTS,
            raw_source_text="Novel Ingredient",
            raw_source_path="activeIngredients[0]",
            reason="no_match_found",
        )

        builder.record_match(
            domain=DOMAIN_INGREDIENTS,
            raw_source_text="Vitamin A",
            raw_source_path="activeIngredients[1]",
            canonical_id="vitamin_a",
            match_method=METHOD_EXACT,
            matched_to_name="Vitamin A",
        )

        lists = builder.build_unmatched_lists()

        assert len(lists["unmatched_ingredients"]) == 1
        assert lists["unmatched_ingredients"][0]["raw_source_text"] == "Novel Ingredient"

    def test_rejected_manufacturer_list(self, builder):
        """Test rejected manufacturer list generation."""
        builder.record_rejected(
            domain=DOMAIN_MANUFACTURER,
            raw_source_text="Garden Life",
            raw_source_path="brandName",
            best_match_id="garden_of_life",
            best_match_name="Garden of Life",
            match_method=METHOD_FUZZY,
            confidence=0.7,
            rejection_reason="fuzzy_below_threshold",
        )

        lists = builder.build_unmatched_lists()

        assert len(lists["rejected_manufacturer_matches"]) == 1
        assert lists["rejected_manufacturer_matches"][0]["decision_reason"] == "fuzzy_below_threshold"


class TestDualCoverageMetrics:
    """Test the dual coverage metrics (recognition vs scorable)."""

    @pytest.fixture
    def builder(self):
        return MatchLedgerBuilder()

    def test_scorable_total_excludes_non_scorable(self, builder):
        """
        Test that scorable_total correctly excludes recognized_non_scorable items.

        Scenario: Product with 1 bioactive + 1 blend header + 1 carrier oil
        - Vitamin D3: matched (bioactive, scorable)
        - "Proprietary Blend": skipped (blend header)
        - Sunflower Oil: recognized_non_scorable (carrier, not therapeutic)

        Expected:
        - total_raw = 3
        - scorable_total = 1 (only Vitamin D3)
        - scorable_coverage = 100% (1/1 = 100%)
        """
        # Record a matched bioactive ingredient
        builder.record_match(
            domain=DOMAIN_INGREDIENTS,
            raw_source_text="Vitamin D3 (as Cholecalciferol)",
            raw_source_path="activeIngredients[0]",
            canonical_id="vitamin_d3",
            match_method=METHOD_EXACT,
            matched_to_name="Vitamin D3",
            confidence=1.0,
        )

        # Record a skipped blend header
        builder.record_skipped(
            domain=DOMAIN_INGREDIENTS,
            raw_source_text="Proprietary Blend",
            raw_source_path="activeIngredients[1]",
            skip_reason="blend_header",
        )

        # Record a recognized non-scorable (carrier oil)
        builder.record_recognized_non_scorable(
            domain=DOMAIN_INGREDIENTS,
            raw_source_text="Sunflower Oil",
            raw_source_path="activeIngredients[2]",
            recognition_source="excipient_list",
            recognition_reason="carrier_oil",
        )

        ledger = builder.build()
        ing_domain = ledger["domains"][DOMAIN_INGREDIENTS]

        # Verify counts
        assert ing_domain["total_raw"] == 3
        assert ing_domain["matched"] == 1
        assert ing_domain["skipped"] == 1
        assert ing_domain["recognized_non_scorable"] == 1
        assert ing_domain["unmatched"] == 0

        # CRITICAL: scorable_total should be 1, not 3
        # scorable_total = total - skipped - recognized_non_scorable = 3 - 1 - 1 = 1
        assert ing_domain["scorable_total"] == 1

        # Scorable coverage should be 100% (1 matched / 1 scorable = 100%)
        assert ing_domain["scorable_coverage_percent"] == 100.0

        # Recognition coverage should be 100% (3 recognized / 3 total = 100%)
        assert ing_domain["recognition_coverage_percent"] == 100.0

    def test_recognition_vs_scorable_coverage_distinction(self, builder):
        """
        Test that recognition and scorable coverage are distinct metrics.

        Scenario: Product with 2 bioactives (1 matched, 1 unmatched) + 1 oil (recognized)
        - Vitamin C: matched (bioactive)
        - Novel Extract: unmatched (bioactive, should be scored but isn't)
        - Coconut Oil: recognized_non_scorable (not therapeutic)

        Expected:
        - recognition_coverage = 66.67% (2/3 recognized)
        - scorable_coverage = 50% (1/2 scorable items matched)
        """
        # Matched bioactive
        builder.record_match(
            domain=DOMAIN_INGREDIENTS,
            raw_source_text="Vitamin C",
            raw_source_path="active[0]",
            canonical_id="vitamin_c",
            match_method=METHOD_EXACT,
            matched_to_name="Vitamin C",
        )

        # Unmatched bioactive (should be scored but isn't in quality_map)
        builder.record_unmatched(
            domain=DOMAIN_INGREDIENTS,
            raw_source_text="Novel Adaptogen Extract",
            raw_source_path="active[1]",
            reason="no_match_in_quality_map",
        )

        # Recognized non-scorable (oil)
        builder.record_recognized_non_scorable(
            domain=DOMAIN_INGREDIENTS,
            raw_source_text="Coconut Oil",
            raw_source_path="active[2]",
            recognition_source="excipient_list",
            recognition_reason="carrier_oil",
        )

        ledger = builder.build()
        ing_domain = ledger["domains"][DOMAIN_INGREDIENTS]

        # Recognition: 2 out of 3 (matched + recognized_non_scorable)
        assert ing_domain["recognition_coverage_percent"] == pytest.approx(66.67, rel=0.01)

        # Scorable: 1 out of 2 (matched / (total - skipped - recognized_non_scorable))
        assert ing_domain["scorable_total"] == 2
        assert ing_domain["scorable_coverage_percent"] == 50.0

    def test_scorable_coverage_is_gate_metric(self, builder):
        """
        Test that coverage_percent (used by gates) equals scorable_coverage.

        This ensures gates use the correct denominator that excludes
        non-therapeutic ingredients.
        """
        builder.record_match(
            domain=DOMAIN_INGREDIENTS,
            raw_source_text="Zinc",
            raw_source_path="active[0]",
            canonical_id="zinc",
            match_method=METHOD_EXACT,
            matched_to_name="Zinc",
        )

        builder.record_recognized_non_scorable(
            domain=DOMAIN_INGREDIENTS,
            raw_source_text="MCT Oil",
            raw_source_path="active[1]",
            recognition_source="excipient_list",
            recognition_reason="carrier_oil",
        )

        ledger = builder.build()
        ing_domain = ledger["domains"][DOMAIN_INGREDIENTS]

        # coverage_percent should equal scorable_coverage_percent (not recognition)
        assert ing_domain["coverage_percent"] == ing_domain["scorable_coverage_percent"]
        assert ing_domain["coverage_percent"] == 100.0  # 1/1, not 50% (1/2)

    def test_botanical_unscored_excluded_from_scorable_denominator(self, builder):
        """
        Test that recognized_botanical_unscored items are EXCLUDED from scorable_total.

        BOTANICAL POLICY:
        - Botanicals are NOT scored in the core scoring system
        - They are EXCLUDED from scorable_total (and gate denominators)
        - They are INCLUDED in recognition_coverage (tracks mapping progress)
        - Bonus points awarded only when standardization evidence present

        Scenario: 1 matched + 1 botanical (recognized, not scored) + 1 oil (non-scorable)
        - Vitamin C: matched
        - Ashwagandha: recognized_botanical_unscored (bonus-only, not core scored)
        - Coconut Oil: recognized_non_scorable (never should be scored)

        Expected:
        - scorable_total = 1 (only Vitamin C - botanicals and oils excluded)
        - scorable_coverage = 100% (1/1)
        - recognition_coverage = 100% (3/3)
        """
        # Matched bioactive
        builder.record_match(
            domain=DOMAIN_INGREDIENTS,
            raw_source_text="Vitamin C",
            raw_source_path="active[0]",
            canonical_id="vitamin_c",
            match_method=METHOD_EXACT,
            matched_to_name="Vitamin C",
        )

        # Botanical recognized but NOT core-scored (bonus-only)
        builder.record_recognized_botanical_unscored(
            domain=DOMAIN_INGREDIENTS,
            raw_source_text="Ashwagandha Root Extract",
            raw_source_path="active[1]",
            botanical_db_match="Withania somnifera",
            reason="botanical_not_scored",
        )

        # Non-scorable carrier oil
        builder.record_recognized_non_scorable(
            domain=DOMAIN_INGREDIENTS,
            raw_source_text="Coconut Oil",
            raw_source_path="active[2]",
            recognition_source="excipient_list",
            recognition_reason="carrier_oil",
        )

        ledger = builder.build()
        ing_domain = ledger["domains"][DOMAIN_INGREDIENTS]

        # Counts
        assert ing_domain["total_raw"] == 3
        assert ing_domain["matched"] == 1
        assert ing_domain["recognized_botanical_unscored"] == 1
        assert ing_domain["recognized_non_scorable"] == 1

        # CRITICAL: scorable_total should EXCLUDE botanical (per policy)
        # scorable_total = 3 - 0 skipped - 1 non_scorable - 1 botanical = 1
        assert ing_domain["scorable_total"] == 1

        # Scorable coverage: 1 matched / 1 scorable = 100%
        assert ing_domain["scorable_coverage_percent"] == 100.0

        # Recognition coverage: all 3 are recognized = 100%
        assert ing_domain["recognition_coverage_percent"] == 100.0

        # Verify the entry has correct decision type
        botanical_entries = [
            e for e in ing_domain["entries"]
            if e["decision"] == DECISION_RECOGNIZED_BOTANICAL_UNSCORED
        ]
        assert len(botanical_entries) == 1
        assert botanical_entries[0]["raw_source_text"] == "Ashwagandha Root Extract"
        assert botanical_entries[0]["matched_to_name"] == "Withania somnifera"

    def test_botanical_only_product_has_zero_scorable(self, builder):
        """
        Test that a product with only botanicals has scorable_total = 0.

        SCORABLE_TOTAL=0 CONTRACT:
        - scorable_total = 0
        - scorable_coverage = 100% (vacuously true - nothing to score was missed)
        - Gate: PASS (not blocked)

        This ensures botanical-only products pass the gate - they're not
        "failing" coverage, they simply have no scorable items.
        """
        # Botanical 1
        builder.record_recognized_botanical_unscored(
            domain=DOMAIN_INGREDIENTS,
            raw_source_text="Ashwagandha Root Extract",
            raw_source_path="active[0]",
            botanical_db_match="Withania somnifera",
        )

        # Botanical 2
        builder.record_recognized_botanical_unscored(
            domain=DOMAIN_INGREDIENTS,
            raw_source_text="Rhodiola Rosea Extract",
            raw_source_path="active[1]",
            botanical_db_match="Rhodiola rosea",
        )

        ledger = builder.build()
        ing_domain = ledger["domains"][DOMAIN_INGREDIENTS]

        # Both are recognized
        assert ing_domain["total_raw"] == 2
        assert ing_domain["recognized_botanical_unscored"] == 2

        # Scorable total should be 0 (both are botanicals)
        assert ing_domain["scorable_total"] == 0

        # SCORABLE_TOTAL=0 CONTRACT:
        # Scorable coverage = 100% (vacuously true - we didn't miss any scorable items)
        assert ing_domain["scorable_coverage_percent"] == 100.0, \
            "When scorable_total=0, scorable_coverage must be 100% (vacuous truth)"

        # coverage_percent (gate metric) must also be 100%
        assert ing_domain["coverage_percent"] == 100.0, \
            "Gate metric must be 100% when scorable_total=0"

        # Recognition coverage should be 100% (all recognized)
        assert ing_domain["recognition_coverage_percent"] == 100.0


class TestBotanicalHeavyRegressionFixtures:
    """
    Regression fixtures for botanical-heavy products.

    These tests prevent botanicals from quietly sneaking back into
    scorable denominators in future changes.
    """

    @pytest.fixture
    def builder(self):
        return MatchLedgerBuilder()

    def test_50_botanicals_2_vitamins_gate_scenario(self, builder):
        """
        CRITICAL REGRESSION TEST: Gate uses scorable coverage, not recognition.

        Scenario: Product with 50 botanicals + 2 vitamins (1 matched, 1 unmatched)
        - 50 botanicals: recognized_botanical_unscored (all excluded from scoring)
        - Vitamin C: matched
        - Vitamin D: unmatched

        Expected:
        - recognition_coverage = 98% (51/52 recognized)
        - scorable_total = 2 (only vitamins)
        - scorable_coverage = 50% (1/2 vitamins matched)
        - Gate should see 50%, NOT 98%

        This is the exact scenario that tends to regress.
        """
        # Add 50 botanicals
        for i in range(50):
            builder.record_recognized_botanical_unscored(
                domain=DOMAIN_INGREDIENTS,
                raw_source_text=f"Botanical Extract {i}",
                raw_source_path=f"active[{i}]",
                botanical_db_match=f"Botanical species {i}",
            )

        # Add 1 matched vitamin
        builder.record_match(
            domain=DOMAIN_INGREDIENTS,
            raw_source_text="Vitamin C (Ascorbic Acid)",
            raw_source_path="active[50]",
            canonical_id="vitamin_c",
            match_method=METHOD_EXACT,
            matched_to_name="Vitamin C",
        )

        # Add 1 unmatched vitamin
        builder.record_unmatched(
            domain=DOMAIN_INGREDIENTS,
            raw_source_text="Vitamin D3 (Novel Form)",
            raw_source_path="active[51]",
            reason="no_match_in_quality_map",
        )

        ledger = builder.build()
        ing_domain = ledger["domains"][DOMAIN_INGREDIENTS]

        # Verify counts
        assert ing_domain["total_raw"] == 52
        assert ing_domain["recognized_botanical_unscored"] == 50
        assert ing_domain["matched"] == 1
        assert ing_domain["unmatched"] == 1

        # CRITICAL: scorable_total must be 2 (only vitamins)
        assert ing_domain["scorable_total"] == 2, \
            "scorable_total must exclude botanicals"

        # CRITICAL: scorable_coverage must be 50% (1/2), not ~98%
        assert ing_domain["scorable_coverage_percent"] == 50.0, \
            "scorable_coverage must be based on vitamins only"

        # Recognition coverage should be high (51/52 ≈ 98%)
        assert ing_domain["recognition_coverage_percent"] == pytest.approx(98.08, rel=0.01)

        # coverage_percent (used by gates) must equal scorable_coverage
        assert ing_domain["coverage_percent"] == ing_domain["scorable_coverage_percent"]
        assert ing_domain["coverage_percent"] == 50.0, \
            "Gate metric must use scorable coverage (50%), not recognition (98%)"

    def test_botanical_only_product_vacuously_passes_gate(self, builder):
        """
        Test that botanical-only products don't fail gate with "0% coverage".

        SCORABLE_TOTAL=0 CONTRACT:
        When scorable_total = 0, scorable_coverage = 100% (vacuously true).
        This ensures the gate PASSES (no scorable items were missed).
        """
        # 10 botanicals, no vitamins/minerals
        for i in range(10):
            builder.record_recognized_botanical_unscored(
                domain=DOMAIN_INGREDIENTS,
                raw_source_text=f"Herbal Extract {i}",
                raw_source_path=f"active[{i}]",
                botanical_db_match=f"Herb species {i}",
            )

        ledger = builder.build()
        ing_domain = ledger["domains"][DOMAIN_INGREDIENTS]

        # scorable_total = 0 (all botanicals excluded)
        assert ing_domain["scorable_total"] == 0

        # SCORABLE_TOTAL=0 CONTRACT: scorable_coverage = 100% (vacuously true)
        # NOT 0% - this ensures gate PASSES
        assert ing_domain["scorable_coverage_percent"] == 100.0, \
            "When scorable_total=0, scorable_coverage must be 100% (vacuous truth)"

        # coverage_percent (gate metric) must also be 100%
        assert ing_domain["coverage_percent"] == 100.0, \
            "Gate metric must be 100% when scorable_total=0"

        # recognition_coverage = 100% (all botanicals recognized)
        assert ing_domain["recognition_coverage_percent"] == 100.0

    def test_mixed_non_scorables_all_excluded(self, builder):
        """
        Test that BOTH botanicals AND excipients are excluded from scorable_total.

        Scenario: 5 botanicals + 5 excipients + 2 vitamins (1 matched)
        - scorable_total should be 2 (only vitamins)
        - scorable_coverage should be 50% (1/2)
        """
        # 5 botanicals
        for i in range(5):
            builder.record_recognized_botanical_unscored(
                domain=DOMAIN_INGREDIENTS,
                raw_source_text=f"Botanical {i}",
                raw_source_path=f"active[{i}]",
                botanical_db_match=f"Species {i}",
            )

        # 5 excipients/carriers
        for i in range(5):
            builder.record_recognized_non_scorable(
                domain=DOMAIN_INGREDIENTS,
                raw_source_text=f"Carrier Oil {i}",
                raw_source_path=f"active[{5 + i}]",
                recognition_source="excipient_list",
                recognition_reason="carrier_oil",
            )

        # 1 matched vitamin
        builder.record_match(
            domain=DOMAIN_INGREDIENTS,
            raw_source_text="Zinc",
            raw_source_path="active[10]",
            canonical_id="zinc",
            match_method=METHOD_EXACT,
            matched_to_name="Zinc",
        )

        # 1 unmatched vitamin
        builder.record_unmatched(
            domain=DOMAIN_INGREDIENTS,
            raw_source_text="Selenium (Novel Form)",
            raw_source_path="active[11]",
            reason="no_match_in_quality_map",
        )

        ledger = builder.build()
        ing_domain = ledger["domains"][DOMAIN_INGREDIENTS]

        # Verify counts
        assert ing_domain["total_raw"] == 12
        assert ing_domain["recognized_botanical_unscored"] == 5
        assert ing_domain["recognized_non_scorable"] == 5

        # scorable_total = 12 - 5 botanicals - 5 excipients = 2
        assert ing_domain["scorable_total"] == 2

        # scorable_coverage = 1/2 = 50%
        assert ing_domain["scorable_coverage_percent"] == 50.0

        # recognition = (1 matched + 5 botanicals + 5 excipients) / 12 = 11/12 ≈ 91.67%
        assert ing_domain["recognition_coverage_percent"] == pytest.approx(91.67, rel=0.01)


class TestMultipleDomains:
    """Test ledger with multiple domains."""

    @pytest.fixture
    def builder(self):
        return MatchLedgerBuilder()

    def test_multiple_domains_coverage(self, builder):
        """Test coverage calculation across multiple domains."""
        # Ingredients: 2 matched, 1 unmatched = 66.67%
        builder.record_match(
            domain=DOMAIN_INGREDIENTS,
            raw_source_text="Vitamin A",
            raw_source_path="active[0]",
            canonical_id="vitamin_a",
            match_method=METHOD_EXACT,
            matched_to_name="Vitamin A",
        )
        builder.record_match(
            domain=DOMAIN_INGREDIENTS,
            raw_source_text="Vitamin B",
            raw_source_path="active[1]",
            canonical_id="vitamin_b",
            match_method=METHOD_EXACT,
            matched_to_name="Vitamin B",
        )
        builder.record_unmatched(
            domain=DOMAIN_INGREDIENTS,
            raw_source_text="Unknown",
            raw_source_path="active[2]",
            reason="no_match",
        )

        # Manufacturer: 1 matched = 100%
        builder.record_match(
            domain=DOMAIN_MANUFACTURER,
            raw_source_text="Garden of Life",
            raw_source_path="brandName",
            canonical_id="garden_of_life",
            match_method=METHOD_EXACT,
            matched_to_name="Garden of Life",
        )

        ledger = builder.build()

        # Check ingredients domain
        ing = ledger["domains"][DOMAIN_INGREDIENTS]
        assert ing["total_raw"] == 3
        assert ing["matched"] == 2
        assert ing["unmatched"] == 1
        assert ing["coverage_percent"] == pytest.approx(66.67, rel=0.01)

        # Check manufacturer domain
        mfg = ledger["domains"][DOMAIN_MANUFACTURER]
        assert mfg["total_raw"] == 1
        assert mfg["matched"] == 1
        assert mfg["coverage_percent"] == 100.0

        # Check overall summary
        summary = ledger["summary"]
        assert summary["total_entities"] == 4
        assert summary["total_matched"] == 3
        assert summary["coverage_percent"] == 75.0
