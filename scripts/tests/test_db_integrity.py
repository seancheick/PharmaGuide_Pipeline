#!/usr/bin/env python3
"""
Pytest wrapper for db_integrity_sanity_check.py.

Validates all JSON data files in scripts/data/ against the schemas
expected by the clean→enrich→score pipeline. Catches silent failures
like missing keys, type mismatches, enum drift, and camelCase leaks.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from db_integrity_sanity_check import run_checks


class TestDBIntegrity:
    """All data JSON files must pass schema validation with zero errors."""

    def test_no_errors(self):
        findings = run_checks()
        errors = [f for f in findings if f.severity == "error"]
        if errors:
            msg_lines = [f"DB integrity check found {len(errors)} error(s):"]
            for e in errors[:20]:
                msg_lines.append(
                    f"  {e.file}:{e.path} — {e.issue} "
                    f"(expected={e.expected}, actual={e.actual})"
                )
            if len(errors) > 20:
                msg_lines.append(f"  ... and {len(errors) - 20} more")
            pytest.fail("\n".join(msg_lines))

    def test_no_warnings(self):
        findings = run_checks()
        warnings = [f for f in findings if f.severity == "warning"]
        if warnings:
            msg_lines = [f"DB integrity check found {len(warnings)} warning(s):"]
            for w in warnings[:20]:
                msg_lines.append(
                    f"  {w.file}:{w.path} — {w.issue} "
                    f"(expected={w.expected}, actual={w.actual})"
                )
            if len(warnings) > 20:
                msg_lines.append(f"  ... and {len(warnings) - 20} more")
            pytest.fail("\n".join(msg_lines))

    def test_all_required_files_exist(self):
        data_dir = Path(__file__).parent.parent / "data"
        required = [
            "ingredient_quality_map.json",
            "allergens.json",
            "harmful_additives.json",
            "banned_recalled_ingredients.json",
            "other_ingredients.json",
            "absorption_enhancers.json",
            "standardized_botanicals.json",
            "synergy_cluster.json",
            "backed_clinical_studies.json",
            "top_manufacturers_data.json",
            "cert_claim_rules.json",
            "rda_optimal_uls.json",
            "rda_therapeutic_dosing.json",
            "unit_conversions.json",
            "botanical_ingredients.json",
            "clinically_relevant_strains.json",
            "proprietary_blends_penalty.json",
            "manufacturer_violations.json",
            "ingredient_classification.json",
            "enhanced_delivery.json",
            "color_indicators.json",
            "id_redirects.json",
            "cross_db_overlap_allowlist.json",
            "banned_match_allowlist.json",
            "functional_ingredient_groupings.json",
            "ingredient_weights.json",
            "manufacture_deduction_expl.json",
            "user_goals_to_clusters.json",
            "percentile_categories.json",
            "clinical_risk_taxonomy.json",
            "ingredient_interaction_rules.json",
        ]
        missing = [f for f in required if not (data_dir / f).exists()]
        if missing:
            pytest.fail(f"Missing data files: {missing}")
