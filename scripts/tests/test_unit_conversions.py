#!/usr/bin/env python3
"""
Unit Conversion Database Tests

Tests for data/unit_conversions.json to ensure:
1. Database loads correctly
2. All conversion factors are valid
3. Form detection patterns work
4. Edge cases are handled
5. Stress test with many conversions
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from constants import UNIT_CONVERSIONS_DB


class UnitConversionTester:
    """Test harness for unit_conversions.json"""

    def __init__(self):
        self.db = None
        self.errors = []
        self.warnings = []
        self.passed = 0
        self.failed = 0

    def load_database(self) -> bool:
        """Load the unit conversions database."""
        try:
            with open(UNIT_CONVERSIONS_DB, 'r', encoding='utf-8') as f:
                self.db = json.load(f)
            print(f"✅ Loaded unit_conversions.json")
            print(f"   Version: {self.db.get('_metadata', self.db.get('database_info', {})).get('version', 'unknown')}")
            return True
        except FileNotFoundError:
            print(f"❌ File not found: {UNIT_CONVERSIONS_DB}")
            return False
        except json.JSONDecodeError as e:
            print(f"❌ JSON parse error: {e}")
            return False

    def _record_result(self, passed: bool, test_name: str, details: str = ""):
        """Record test result."""
        if passed:
            self.passed += 1
            print(f"  ✅ {test_name}")
        else:
            self.failed += 1
            print(f"  ❌ {test_name}: {details}")
            self.errors.append(f"{test_name}: {details}")

    def test_database_structure(self):
        """Test that database has required structure."""
        print("\n📋 Testing Database Structure...")

        # Check _metadata
        self._record_result(
            '_metadata' in self.db,
            "_metadata section exists"
        )

        info = self.db.get('_metadata', self.db.get('database_info', {}))
        self._record_result(
            'version' in info,
            "version field exists",
            f"Found: {list(info.keys())}"
        )

        # Check main sections
        required_sections = [
            'vitamin_conversions',
            'mass_conversions',
            'probiotic_conversions',
            'form_detection_patterns'
        ]

        for section in required_sections:
            self._record_result(
                section in self.db,
                f"Section '{section}' exists"
            )

    def test_vitamin_d_conversions(self):
        """Test Vitamin D IU <-> mcg conversions."""
        print("\n💊 Testing Vitamin D Conversions...")

        vit_d3 = self.db.get('vitamin_conversions', {}).get('vitamin_d3', {})
        conversions = vit_d3.get('conversions', {})

        # Test IU to mcg: 2000 IU = 50 mcg
        iu_to_mcg = conversions.get('iu_to_mcg', 0)
        result = 2000 * iu_to_mcg
        self._record_result(
            abs(result - 50) < 0.01,
            "2000 IU Vitamin D3 = 50 mcg",
            f"Got {result}"
        )

        # Test mcg to IU: 50 mcg = 2000 IU
        mcg_to_iu = conversions.get('mcg_to_iu', 0)
        result = 50 * mcg_to_iu
        self._record_result(
            abs(result - 2000) < 0.01,
            "50 mcg Vitamin D3 = 2000 IU",
            f"Got {result}"
        )

        # Test round-trip
        original = 5000
        converted = original * iu_to_mcg  # IU to mcg
        back = converted * mcg_to_iu      # mcg back to IU
        self._record_result(
            abs(back - original) < 0.01,
            f"Round-trip: {original} IU -> {converted} mcg -> {back} IU",
            f"Difference: {abs(back - original)}"
        )

    def test_vitamin_e_forms(self):
        """Test Vitamin E natural vs synthetic conversions."""
        print("\n🧬 Testing Vitamin E Form-Specific Conversions...")

        vit_convs = self.db.get('vitamin_conversions', {})

        # Natural (d-alpha): 400 IU = 268 mg
        natural = vit_convs.get('vitamin_e_d_alpha_tocopherol', {})
        nat_factor = natural.get('conversions', {}).get('iu_to_mg', 0)
        nat_result = 400 * nat_factor
        self._record_result(
            abs(nat_result - 268) < 1,
            f"400 IU natural Vitamin E = ~268 mg",
            f"Got {nat_result:.1f} mg"
        )

        # Synthetic (dl-alpha): 400 IU = 180 mg
        synthetic = vit_convs.get('vitamin_e_dl_alpha_tocopherol', {})
        syn_factor = synthetic.get('conversions', {}).get('iu_to_mg', 0)
        syn_result = 400 * syn_factor
        self._record_result(
            abs(syn_result - 180) < 1,
            f"400 IU synthetic Vitamin E = ~180 mg",
            f"Got {syn_result:.1f} mg"
        )

        # Verify natural > synthetic bioavailability
        self._record_result(
            nat_factor > syn_factor,
            "Natural form has higher conversion factor than synthetic",
            f"Natural: {nat_factor}, Synthetic: {syn_factor}"
        )

    def test_vitamin_a_forms(self):
        """Test Vitamin A form-specific conversions (CRITICAL)."""
        print("\n⚠️  Testing Vitamin A Form-Specific Conversions (CRITICAL)...")

        vit_convs = self.db.get('vitamin_conversions', {})

        # Test case: 10,000 IU with different forms
        test_iu = 10000

        # Retinol: 10000 IU = 3000 mcg RAE (AT the UL!)
        retinol = vit_convs.get('vitamin_a_retinol', {})
        ret_factor = retinol.get('conversions', {}).get('iu_to_mcg_rae', 0)
        ret_result = test_iu * ret_factor
        self._record_result(
            abs(ret_result - 3000) < 1,
            f"10000 IU Retinol = 3000 mcg RAE (UL level)",
            f"Got {ret_result:.0f} mcg RAE"
        )

        # Beta-carotene supplement: 10000 IU = 1000 mcg RAE
        bc_supp = vit_convs.get('vitamin_a_beta_carotene_supplement', {})
        bc_supp_factor = bc_supp.get('conversions', {}).get('iu_to_mcg_rae', 0)
        bc_supp_result = test_iu * bc_supp_factor
        self._record_result(
            abs(bc_supp_result - 1000) < 1,
            f"10000 IU Beta-carotene (supp) = 1000 mcg RAE",
            f"Got {bc_supp_result:.0f} mcg RAE"
        )

        # Beta-carotene food: 10000 IU = 500 mcg RAE
        bc_food = vit_convs.get('vitamin_a_beta_carotene_food', {})
        bc_food_factor = bc_food.get('conversions', {}).get('iu_to_mcg_rae', 0)
        bc_food_result = test_iu * bc_food_factor
        self._record_result(
            abs(bc_food_result - 500) < 1,
            f"10000 IU Beta-carotene (food) = 500 mcg RAE",
            f"Got {bc_food_result:.0f} mcg RAE"
        )

        # CRITICAL: Verify retinol gives highest mcg RAE (most conservative for UL)
        self._record_result(
            ret_result > bc_supp_result > bc_food_result,
            "Retinol > BC supplement > BC food (correct ordering)",
            f"Retinol: {ret_result}, BC supp: {bc_supp_result}, BC food: {bc_food_result}"
        )

        # Test unknown form handling
        unknown = vit_convs.get('vitamin_a_unknown', {})
        self._record_result(
            unknown.get('handling') == 'flag_for_review',
            "Unknown Vitamin A form flagged for review",
            f"Handling: {unknown.get('handling')}"
        )

    def test_folate_conversions(self):
        """Test Folate DFE conversions."""
        print("\n🧪 Testing Folate DFE Conversions...")

        vit_convs = self.db.get('vitamin_conversions', {})

        # Folic acid: 400 mcg = 680 mcg DFE
        folic = vit_convs.get('folate_folic_acid', {})
        folic_factor = folic.get('conversions', {}).get('mcg_to_mcg_dfe', 0)
        folic_result = 400 * folic_factor
        self._record_result(
            abs(folic_result - 680) < 1,
            f"400 mcg Folic Acid = 680 mcg DFE",
            f"Got {folic_result:.0f} mcg DFE"
        )

        # Food folate: 400 mcg = 400 mcg DFE
        food = vit_convs.get('folate_food', {})
        food_factor = food.get('conversions', {}).get('mcg_to_mcg_dfe', 0)
        food_result = 400 * food_factor
        self._record_result(
            abs(food_result - 400) < 1,
            f"400 mcg Food Folate = 400 mcg DFE",
            f"Got {food_result:.0f} mcg DFE"
        )

    def test_mass_conversions(self):
        """Test standard mass unit conversions."""
        print("\n⚖️  Testing Mass Unit Conversions...")

        mass = self.db.get('mass_conversions', {}).get('rules', {})

        # g to mg
        self._record_result(
            mass.get('g_to_mg') == 1000,
            "1 g = 1000 mg",
            f"Got factor: {mass.get('g_to_mg')}"
        )

        # mg to mcg
        self._record_result(
            mass.get('mg_to_mcg') == 1000,
            "1 mg = 1000 mcg",
            f"Got factor: {mass.get('mg_to_mcg')}"
        )

        # g to mcg
        self._record_result(
            mass.get('g_to_mcg') == 1000000,
            "1 g = 1000000 mcg",
            f"Got factor: {mass.get('g_to_mcg')}"
        )

        # Test chain: 0.5 g -> mg -> mcg
        g_value = 0.5
        mg_value = g_value * mass.get('g_to_mg', 0)
        mcg_value = mg_value * mass.get('mg_to_mcg', 0)
        direct_mcg = g_value * mass.get('g_to_mcg', 0)
        self._record_result(
            abs(mcg_value - direct_mcg) < 0.01,
            f"Chain conversion matches direct: {g_value}g = {mcg_value} mcg",
            f"Chain: {mcg_value}, Direct: {direct_mcg}"
        )

    def test_probiotic_conversions(self):
        """Test CFU normalization."""
        print("\n🦠 Testing Probiotic CFU Conversions...")

        prob = self.db.get('probiotic_conversions', {})
        rules = prob.get('rules', {})

        # 50 billion CFU
        billion_factor = rules.get('billion_cfu_to_cfu', 0)
        result = 50 * billion_factor
        expected = 50_000_000_000
        self._record_result(
            result == expected,
            f"50 billion CFU = 50,000,000,000 CFU",
            f"Got {result:,}"
        )

        # Viable cells = CFU
        self._record_result(
            prob.get('viable_cells_equals_cfu') == True,
            "Viable cells equals CFU",
            f"Got: {prob.get('viable_cells_equals_cfu')}"
        )

    def test_form_detection_patterns(self):
        """Test regex patterns for vitamin form detection."""
        print("\n🔍 Testing Form Detection Patterns...")

        patterns = self.db.get('form_detection_patterns', {})

        # Vitamin E natural patterns
        vit_e = patterns.get('vitamin_e', {})
        natural_patterns = vit_e.get('natural_patterns', [])

        test_natural = [
            "d-alpha-tocopherol",
            "d-alpha tocopheryl acetate",
            "Natural Vitamin E",
            "RRR-alpha-tocopherol"
        ]

        for test_str in test_natural:
            matched = any(
                re.search(p, test_str, re.IGNORECASE)
                for p in natural_patterns
            )
            self._record_result(
                matched,
                f"Natural E pattern matches: '{test_str}'",
                "No match found"
            )

        # Vitamin E synthetic patterns
        synthetic_patterns = vit_e.get('synthetic_patterns', [])

        test_synthetic = [
            "dl-alpha-tocopherol",
            "dl-alpha-tocopheryl acetate",
            "all-rac-alpha-tocopherol"
        ]

        for test_str in test_synthetic:
            matched = any(
                re.search(p, test_str, re.IGNORECASE)
                for p in synthetic_patterns
            )
            self._record_result(
                matched,
                f"Synthetic E pattern matches: '{test_str}'",
                "No match found"
            )

        # Vitamin A retinol patterns
        vit_a = patterns.get('vitamin_a', {})
        retinol_patterns = vit_a.get('retinol_patterns', [])

        test_retinol = [
            "Retinyl Palmitate",
            "Retinyl Acetate",
            "Vitamin A Palmitate",
            "preformed Vitamin A"
        ]

        for test_str in test_retinol:
            matched = any(
                re.search(p, test_str, re.IGNORECASE)
                for p in retinol_patterns
            )
            self._record_result(
                matched,
                f"Retinol pattern matches: '{test_str}'",
                "No match found"
            )

        # Vitamin A beta-carotene patterns
        bc_patterns = vit_a.get('beta_carotene_patterns', [])

        test_bc = [
            "Beta-Carotene",
            "beta carotene",
            "Provitamin A"
        ]

        for test_str in test_bc:
            matched = any(
                re.search(p, test_str, re.IGNORECASE)
                for p in bc_patterns
            )
            self._record_result(
                matched,
                f"Beta-carotene pattern matches: '{test_str}'",
                "No match found"
            )

    def stress_test_conversions(self, iterations: int = 1000):
        """Stress test with many conversions."""
        print(f"\n🏋️  Stress Testing ({iterations} iterations)...")

        import time

        vit_convs = self.db.get('vitamin_conversions', {})
        mass_rules = self.db.get('mass_conversions', {}).get('rules', {})

        # Prepare conversion factors
        d3_iu_to_mcg = vit_convs.get('vitamin_d3', {}).get('conversions', {}).get('iu_to_mcg', 0.025)
        e_nat_iu_to_mg = vit_convs.get('vitamin_e_d_alpha_tocopherol', {}).get('conversions', {}).get('iu_to_mg', 0.67)
        a_ret_iu_to_mcg = vit_convs.get('vitamin_a_retinol', {}).get('conversions', {}).get('iu_to_mcg_rae', 0.3)
        g_to_mg = mass_rules.get('g_to_mg', 1000)

        start = time.time()

        results = []
        for i in range(iterations):
            # Vitamin D conversion
            d3_mcg = (1000 + i) * d3_iu_to_mcg

            # Vitamin E conversion
            e_mg = (400 + i % 100) * e_nat_iu_to_mg

            # Vitamin A conversion
            a_mcg = (5000 + i * 10) * a_ret_iu_to_mcg

            # Mass conversion
            mass_mg = (0.5 + i * 0.001) * g_to_mg

            results.append((d3_mcg, e_mg, a_mcg, mass_mg))

        elapsed = time.time() - start

        self._record_result(
            len(results) == iterations,
            f"Completed {iterations} conversion sets",
            f"Only completed {len(results)}"
        )

        self._record_result(
            elapsed < 1.0,  # Should complete in under 1 second
            f"Performance: {elapsed*1000:.2f}ms for {iterations} iterations",
            f"Too slow: {elapsed:.2f}s"
        )

        # Verify some results
        sample = results[500]  # Middle sample
        expected_d3 = (1000 + 500) * d3_iu_to_mcg  # 1500 * 0.025 = 37.5
        self._record_result(
            abs(sample[0] - expected_d3) < 0.001,
            f"Sample result correct: 1500 IU D3 = {sample[0]} mcg",
            f"Expected {expected_d3}"
        )

    def test_edge_cases(self):
        """Test edge cases and boundary conditions."""
        print("\n🔬 Testing Edge Cases...")

        vit_convs = self.db.get('vitamin_conversions', {})

        # Zero conversion
        d3_factor = vit_convs.get('vitamin_d3', {}).get('conversions', {}).get('iu_to_mcg', 0)
        self._record_result(
            0 * d3_factor == 0,
            "Zero IU converts to zero mcg",
            f"Got: {0 * d3_factor}"
        )

        # Very large number
        large_iu = 1_000_000
        large_result = large_iu * d3_factor
        self._record_result(
            large_result == 25000,
            f"1,000,000 IU D3 = 25,000 mcg",
            f"Got: {large_result}"
        )

        # Very small number
        small_iu = 0.1
        small_result = small_iu * d3_factor
        self._record_result(
            abs(small_result - 0.0025) < 0.0001,
            f"0.1 IU D3 = 0.0025 mcg",
            f"Got: {small_result}"
        )

        # Test all conversions have both directions (where applicable)
        for vit_name, vit_data in vit_convs.items():
            convs = vit_data.get('conversions', {})
            if convs is None:
                continue  # Some vitamins have no IU conversion

            if 'iu_to_mcg' in convs:
                self._record_result(
                    'mcg_to_iu' in convs,
                    f"{vit_name}: Has reverse mcg_to_iu conversion",
                    "Missing reverse conversion"
                )

            if 'iu_to_mg' in convs:
                self._record_result(
                    'mg_to_iu' in convs,
                    f"{vit_name}: Has reverse mg_to_iu conversion",
                    "Missing reverse conversion"
                )

    def test_aliases(self):
        """Test that aliases are properly defined."""
        print("\n📝 Testing Aliases...")

        vit_convs = self.db.get('vitamin_conversions', {})

        # Check that key vitamins have aliases
        vitamins_needing_aliases = [
            'vitamin_d3',
            'vitamin_e_d_alpha_tocopherol',
            'vitamin_e_dl_alpha_tocopherol',
            'vitamin_a_retinol',
            'vitamin_a_beta_carotene_supplement'
        ]

        for vit in vitamins_needing_aliases:
            data = vit_convs.get(vit, {})
            aliases = data.get('aliases', [])
            self._record_result(
                len(aliases) > 0,
                f"{vit}: Has {len(aliases)} aliases",
                "No aliases defined"
            )

    def run_all_tests(self):
        """Run all tests and report results."""
        print("=" * 60)
        print("UNIT CONVERSION DATABASE TEST SUITE")
        print("=" * 60)

        if not self.load_database():
            print("\n❌ Cannot run tests - database failed to load")
            return False

        self.test_database_structure()
        self.test_vitamin_d_conversions()
        self.test_vitamin_e_forms()
        self.test_vitamin_a_forms()
        self.test_folate_conversions()
        self.test_mass_conversions()
        self.test_probiotic_conversions()
        self.test_form_detection_patterns()
        self.test_aliases()
        self.test_edge_cases()
        self.stress_test_conversions(1000)

        # Summary
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        total = self.passed + self.failed
        print(f"Total tests: {total}")
        print(f"Passed: {self.passed} ({self.passed/total*100:.1f}%)")
        print(f"Failed: {self.failed} ({self.failed/total*100:.1f}%)")

        if self.errors:
            print(f"\n❌ FAILURES:")
            for err in self.errors:
                print(f"   - {err}")

        if self.warnings:
            print(f"\n⚠️  WARNINGS:")
            for warn in self.warnings:
                print(f"   - {warn}")

        print("=" * 60)

        return self.failed == 0


def main():
    """Main entry point."""
    tester = UnitConversionTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
