#!/usr/bin/env python3
"""
Verify the Phosphorus and Vitamin C cross-parent IQM fixes by running
the actual enrichment matcher on known problem cases.
"""
import sys
import os

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from enrich_supplements_v3 import SupplementEnricherV3


def main():
    enricher = SupplementEnricherV3()
    iqm = enricher.databases.get("ingredient_quality_map", {})

    print("=== Phosphorus form matching test ===")
    test_cases = [
        # (ing_name, std_name, form_text, expected_parent, expected_form_contains)
        ("Phosphorus", "Phosphorus", "Calcium Phosphate",
         "phosphorus", "phosphate"),
        ("Phosphorus", "Phosphorus", "Tricalcium Phosphate",
         "phosphorus", "phosphate"),
        ("Phosphorus", "Phosphorus", "Microcrystalline Hydroxyapatite",
         "phosphorus", "phosphate"),
        ("Phosphorus", "Phosphorus", "DCP",
         "phosphorus", "dicalcium"),
        # Verify calcium still wins when labeled as Calcium
        ("Calcium", "Calcium", "Calcium Phosphate",
         "calcium", "phosphate"),
        ("Calcium", "Calcium", "Tricalcium Phosphate",
         "calcium", "phosphate"),
    ]

    all_pass = True
    for ing_name, std_name, form_text, exp_parent, exp_form_substr in test_cases:
        # Build a form_info dict to simulate form extraction
        form_info = {
            "original": ing_name,
            "base_name": ing_name,
            "extracted_forms": [
                {
                    "raw_form_text": form_text,
                    "match_candidates": [form_text],
                    "display_form": form_text,
                    "percent_share": 1.0,
                }
            ],
            "is_dual_form": False,
            "form_extraction_success": True,
            "has_form_evidence": True,
        }
        result = enricher._match_multi_form(form_info, iqm)
        if result and result.get("matched_forms"):
            got_parent = result["matched_forms"][0].get("canonical_id", "")
            got_form = result["matched_forms"][0].get("form_key", "")
            passed = got_parent == exp_parent and exp_form_substr in got_form
            status = "PASS" if passed else "FAIL"
            if not passed:
                all_pass = False
            print(f"  {status}: '{ing_name}' + form='{form_text}'")
            print(f"         got: {got_parent}/{got_form}")
            if not passed:
                print(f"         expected parent={exp_parent}, form contains {exp_form_substr!r}")
        else:
            all_pass = False
            print(f"  FAIL: '{ing_name}' + form='{form_text}' → no match")

    print("\n=== Vitamin C niacinamide ascorbate test ===")
    vc_cases = [
        ("Vitamin C", "Vitamin C", "Niacinamide Ascorbate",
         "vitamin_c", "niacinamide"),
        # Verify niacin still wins when labeled as Niacin
        ("Niacinamide", "Niacinamide", "Niacinamide Ascorbate",
         "vitamin_b3_niacin", "niacinamide"),
    ]
    for ing_name, std_name, form_text, exp_parent, exp_form_substr in vc_cases:
        form_info = {
            "original": ing_name,
            "base_name": ing_name,
            "extracted_forms": [
                {
                    "raw_form_text": form_text,
                    "match_candidates": [form_text],
                    "display_form": form_text,
                    "percent_share": 1.0,
                }
            ],
            "is_dual_form": False,
            "form_extraction_success": True,
            "has_form_evidence": True,
        }
        result = enricher._match_multi_form(form_info, iqm)
        if result and result.get("matched_forms"):
            got_parent = result["matched_forms"][0].get("canonical_id", "")
            got_form = result["matched_forms"][0].get("form_key", "")
            passed = got_parent == exp_parent and exp_form_substr in got_form
            status = "PASS" if passed else "FAIL"
            if not passed:
                all_pass = False
            print(f"  {status}: '{ing_name}' + form='{form_text}'")
            print(f"         got: {got_parent}/{got_form}")
            if not passed:
                print(f"         expected parent={exp_parent}")
        else:
            all_pass = False
            print(f"  FAIL: '{ing_name}' + form='{form_text}' → no match")

    print()
    print("OVERALL:", "PASS" if all_pass else "FAIL — see details above")


if __name__ == "__main__":
    main()
