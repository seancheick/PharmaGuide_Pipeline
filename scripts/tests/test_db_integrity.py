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


def test_flag_only_allergen_metadata_has_no_retired_score_magnitudes():
    import json

    path = Path(__file__).parent.parent / "data" / "allergens.json"
    data = json.loads(path.read_text())
    scoring = data["_metadata"]["scoring_system"]
    assert not {"allergen_free_bonus", "severity_penalties"} & scoring.keys()
    assert all(row["general_handling"] == "flag_only" for row in data["allergens"])


@pytest.mark.parametrize("key,value", [
    ("allergen_free_bonus", 2),
    ("severity_penalties", {"low": -1, "moderate": -1.5, "high": -2}),
])
def test_allergen_validator_rejects_retired_score_magnitudes(key, value):
    from db_integrity_sanity_check import check_allergens

    findings = []
    check_allergens(findings, {
        "_metadata": {"scoring_system": {key: value}},
        "allergens": [],
    }, "allergens.json")
    assert any(
        finding.severity == "error"
        and finding.path == f"_metadata.scoring_system.{key}"
        for finding in findings
    )


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
            "proprietary_blends.json",
            "manufacturer_violations.json",
            "ingredient_classification.json",
            "enhanced_delivery.json",
            "color_indicators.json",
            "id_redirects.json",
            "cross_db_overlap_allowlist.json",
            "banned_match_allowlist.json",
            "functional_ingredient_groupings.json",
            "manufacture_deduction_expl.json",
            "user_goals_to_clusters.json",
            "clinical_risk_taxonomy.json",
            "ingredient_interaction_rules.json",
        ]
        missing = [f for f in required if not (data_dir / f).exists()]
        if missing:
            pytest.fail(f"Missing data files: {missing}")


def test_source_qualified_records_can_have_no_goal_or_endpoint_claims():
    from db_integrity_sanity_check import check_clinical_db
    row = {"id": "SOURCE_HOLD", "standard_name": "Unknown preparation",
           "study_type": "reference", "evidence_level": "reference",
           "score_contribution": None, "scoring_eligible": False,
           "health_goals_supported": [], "key_endpoints": []}
    findings = []
    check_clinical_db(findings, {"backed_clinical_studies": [row]}, "backed_clinical_studies.json")
    assert not findings
    row["health_goals_supported"] = "unsupported string"
    check_clinical_db(findings, {"backed_clinical_studies": [row]}, "backed_clinical_studies.json")
    assert any(f.severity == "error" and "health_goals_supported" in f.path for f in findings)


def test_reference_classification_must_agree_across_both_fields():
    from db_integrity_sanity_check import check_clinical_db
    base = {"id": "REF", "standard_name": "Ingredient", "scoring_eligible": False,
            "health_goals_supported": [], "key_endpoints": []}
    for study_type, evidence_level in (("reference", "ingredient-human"),
                                       ("rct_single", "reference")):
        findings = []
        check_clinical_db(findings, {"backed_clinical_studies": [
            {**base, "study_type": study_type, "evidence_level": evidence_level}]},
            "backed_clinical_studies.json")
        assert any(f.severity == "error" and f.issue == "reference_classification_conflict"
                   for f in findings), (study_type, evidence_level)


def test_reference_only_predicate_fails_closed_on_either_field():
    from clinical_evidence_schema import is_reference_only
    assert is_reference_only({"study_type": "reference", "evidence_level": "reference"})
    assert is_reference_only({"study_type": "Reference", "evidence_level": "ingredient-human"})
    assert is_reference_only({"study_type": "rct_single", "evidence_level": "reference"})
    assert not is_reference_only({"study_type": "rct_single", "evidence_level": "ingredient-human"})
    assert not is_reference_only({})


def test_eligible_trial_with_no_endpoints_or_goals_still_fails():
    from db_integrity_sanity_check import check_clinical_db
    row = {"id": "ELIGIBLE_RCT", "standard_name": "Ingredient",
           "study_type": "rct_single", "evidence_level": "ingredient-human",
           "score_contribution": "tier_3", "scoring_eligible": True,
           "health_goals_supported": [], "key_endpoints": []}
    findings = []
    check_clinical_db(findings, {"backed_clinical_studies": [row]}, "backed_clinical_studies.json")
    assert any("key_endpoints" in f.path and f.issue == "empty_list" for f in findings)
    assert any("health_goals_supported" in f.path and f.issue == "empty_list" for f in findings)
    row["key_endpoints"] = ["Measured physiological endpoint; benefit unestablished"]
    findings = []
    check_clinical_db(findings, {"backed_clinical_studies": [row]}, "backed_clinical_studies.json")
    assert not findings


def test_form_quality_null_is_explicitly_unassessed_not_a_missing_key():
    import json
    from copy import deepcopy
    from db_integrity_sanity_check import check_iqm
    parent = json.loads((Path(__file__).parents[1] / 'data/ingredient_quality_map.json').read_text())['vitamin_b7_biotin']
    data = {'vitamin_b7_biotin': deepcopy(parent)}
    findings = []
    check_iqm(findings, data, 'ingredient_quality_map.json')
    assert not [f for f in findings if f.severity == 'error']
    del data['vitamin_b7_biotin']['forms']['magnesium biotinate']['bio_score']
    findings = []
    check_iqm(findings, data, 'ingredient_quality_map.json')
    assert any(f.issue == 'missing_required_key' and f.path.endswith('bio_score') for f in findings)
