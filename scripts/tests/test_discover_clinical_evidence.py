import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_audit.discover_clinical_evidence import (
    APIClient,
    audit_all_entries,
    backfill_auditability_metadata,
    candidate_to_clinical_entry,
    discover_candidates,
    enrich_enrollment,
)


def test_candidate_to_clinical_entry_keeps_registry_and_published_counts_separate():
    candidate = {
        "standard_name": "Test Compound",
        "slug": "test_compound",
        "category": "herbs",
        "ct_total_trials": 12,
        "ct_max_enrollment": 640,
        "ct_top_trials": [
            {"nct_id": "NCT00000001", "title": "Test trial", "enrollment": 640},
        ],
        "ct_trials_with_outcomes": [
            {
                "nct_id": "NCT00000001",
                "title": "Test trial",
                "enrollment": 640,
                "primary_outcomes": ["Change in joint pain from baseline"],
            }
        ],
        "suggested_evidence_level": "ingredient-human",
        "suggested_study_type": "rct_multiple",
        "suggested_effect_direction": "positive_weak",
        "suggested_effect_direction_confidence": "low",
        "suggested_effect_direction_rationale": "Trial registry confirms completed human studies, but result direction is not verified from registry metadata alone.",
        "suggested_total_enrollment": 640,
        "endpoint_relevance_tags": ["joint_pain", "joint_health"],
    }

    entry = candidate_to_clinical_entry(candidate)

    assert entry["registry_completed_trials_count"] == 12
    assert "published_studies_count" not in entry
    assert entry["effect_direction"] == "positive_weak"
    assert entry["effect_direction_confidence"] == "low"
    assert "not verified" in entry["effect_direction_rationale"].lower()
    assert entry["endpoint_relevance_tags"] == ["joint_pain", "joint_health"]


def test_discover_candidates_defaults_to_conservative_effect_direction(monkeypatch):
    def fake_ct_search_trials(client, intervention, *, max_results=5):
        return {
            "total": 9,
            "trials": [
                {
                    "nct_id": "NCT00000001",
                    "title": "Compound X for stress",
                    "enrollment": 180,
                    "phases": ["PHASE3"],
                    "primary_outcomes": ["Change in perceived stress score"],
                    "secondary_outcomes": [],
                }
            ],
        }

    def fake_chembl_search_compound(client, name):
        return {"chembl_id": "CHEMBL1", "max_phase": 3, "withdrawn_flag": False, "black_box_warning": False}

    monkeypatch.setattr("api_audit.discover_clinical_evidence.ct_search_trials", fake_ct_search_trials)
    monkeypatch.setattr("api_audit.discover_clinical_evidence.chembl_search_compound", fake_chembl_search_compound)

    candidates = discover_candidates(
        APIClient(cache_path=None),
        [{"slug": "compound_x", "standard_name": "Compound X", "category": "herbs", "form_count": 10}],
        limit=1,
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["suggested_effect_direction"] == "positive_weak"
    assert candidate["suggested_effect_direction_confidence"] == "low"
    assert "registry" in candidate["suggested_effect_direction_rationale"].lower()
    assert candidate["endpoint_relevance_tags"]


def test_audit_flags_missing_effect_direction_auditability():
    issues = audit_all_entries(
        {
            "backed_clinical_studies": [
                {
                    "id": "INGR_TEST",
                    "standard_name": "Test",
                    "evidence_level": "ingredient-human",
                    "study_type": "rct_multiple",
                    "effect_direction": "positive_strong",
                    "notes": "PMID 12345678 showed a reduction in symptoms.",
                    "notable_studies": "PMID 12345678",
                    "published_studies": ["RCT"],
                }
            ]
        }
    )

    checks = {(issue["id"], issue["check"]) for issue in issues}
    assert ("INGR_TEST", "missing_effect_direction_rationale") in checks
    assert ("INGR_TEST", "missing_effect_direction_confidence") in checks


def test_audit_enrollment_plausibility_skips_live_verified_well_known_entry():
    issues = audit_all_entries(
        {
            "backed_clinical_studies": [
                {
                    "id": "BRAND_MAGTEIN",
                    "standard_name": "Magtein Magnesium L-Threonate",
                    "evidence_level": "branded-rct",
                    "study_type": "rct_multiple",
                    "effect_direction": "positive_strong",
                    "notes": "Randomized human evidence for cognition.",
                    "notable_studies": "NCT02363634; NCT02210286",
                    "published_studies": ["RCT"],
                    "total_enrollment": 50,
                    "registry_completed_trials_count": 2,
                }
            ]
        }
    )

    checks = {(issue["id"], issue["check"]) for issue in issues}
    assert ("BRAND_MAGTEIN", "enrollment_plausibility") not in checks


def test_enrich_enrollment_refreshes_registry_counts_broadly(monkeypatch):
    monkeypatch.setattr(
        "api_audit.discover_clinical_evidence.ct_search_trials",
        lambda client, intervention, max_results=10: {
            "total": 14,
            "trials": [{"enrollment": 120}, {"enrollment": 450}],
        },
    )

    clinical_db = {
        "backed_clinical_studies": [
            {
                "id": "INGR_TEST",
                "standard_name": "Test Compound",
                "study_type": "rct_multiple",
                "total_enrollment": 640,
            }
        ]
    }

    enrichments = enrich_enrollment(APIClient(cache_path=None), clinical_db, apply=True)

    assert len(enrichments) == 1
    assert enrichments[0]["new_registry_completed_trials_count"] == 14
    assert clinical_db["backed_clinical_studies"][0]["registry_completed_trials_count"] == 14
    assert clinical_db["backed_clinical_studies"][0]["total_enrollment"] == 640


def test_enrich_enrollment_uses_conservative_brand_alias_terms(monkeypatch):
    seen = []

    def fake_ct_search_trials(client, intervention, max_results=10):
        seen.append(intervention)
        if intervention == "Magtein Magnesium L-Threonate":
            return {"total": 1, "trials": [{"nct_id": "NCT1", "enrollment": 17}]}
        if intervention == "magtein":
            return {"total": 2, "trials": [{"nct_id": "NCT1", "enrollment": 17}, {"nct_id": "NCT2", "enrollment": 50}]}
        pytest.fail(f"unexpected search term: {intervention}")

    monkeypatch.setattr("api_audit.discover_clinical_evidence.ct_search_trials", fake_ct_search_trials)

    clinical_db = {
        "backed_clinical_studies": [
            {
                "id": "BRAND_MAGTEIN",
                "standard_name": "Magtein Magnesium L-Threonate",
                "aliases": ["magtein", "magnesium l-threonate", "mgt"],
                "evidence_level": "branded-rct",
                "study_type": "rct_multiple",
                "total_enrollment": 44,
                "registry_completed_trials_count": 1,
            }
        ]
    }

    enrichments = enrich_enrollment(APIClient(cache_path=None), clinical_db, apply=True)

    assert len(enrichments) == 1
    assert seen == ["Magtein Magnesium L-Threonate", "magtein"]
    assert clinical_db["backed_clinical_studies"][0]["total_enrollment"] == 50
    assert clinical_db["backed_clinical_studies"][0]["registry_completed_trials_count"] == 2


def test_backfill_auditability_targets_highest_impact_entries_first(monkeypatch):
    def fake_ct_search_trials(client, intervention, max_results=8):
        if intervention == "High Impact":
            return {
                "total": 11,
                "trials": [
                    {
                        "enrollment": 320,
                        "primary_outcomes": ["Change in LDL cholesterol from baseline"],
                        "secondary_outcomes": ["Triglycerides"],
                    }
                ],
            }
        return {"total": 2, "trials": [{"enrollment": 40, "primary_outcomes": ["Mood scale"], "secondary_outcomes": []}]}

    monkeypatch.setattr("api_audit.discover_clinical_evidence.ct_search_trials", fake_ct_search_trials)

    clinical_db = {
        "backed_clinical_studies": [
            {
                "id": "HIGH_IMPACT",
                "standard_name": "High Impact",
                "study_type": "systematic_review_meta",
                "evidence_level": "product-human",
                "effect_direction": "positive_strong",
                "published_studies": ["meta-analysis", "RCT"],
                "key_endpoints": ["Reduced LDL cholesterol (PMID: 12345678)"],
                "primary_outcome": "Cardiovascular/Heart Health",
                "total_enrollment": 950,
                "notes": "Multiple randomized trials showed improved lipid outcomes.",
            },
            {
                "id": "LOW_IMPACT",
                "standard_name": "Low Impact",
                "study_type": "animal_study",
                "evidence_level": "preclinical",
                "effect_direction": "positive_weak",
                "published_studies": ["animal study"],
                "primary_outcome": "Healthy Aging/Longevity",
                "notes": "Animal model only.",
            },
        ]
    }

    updates = backfill_auditability_metadata(
        APIClient(cache_path=None),
        clinical_db,
        apply=True,
        limit=1,
    )

    assert [u["id"] for u in updates] == ["HIGH_IMPACT"]
    high = clinical_db["backed_clinical_studies"][0]
    low = clinical_db["backed_clinical_studies"][1]
    assert high["effect_direction_confidence"] == "high"
    assert "registry_completed_trials_count=11" in high["effect_direction_rationale"]
    assert "Cardiovascular/Heart Health" in high["effect_direction_rationale"]
    assert high["endpoint_relevance_tags"] == ["cardiovascular"]
    assert high["registry_completed_trials_count"] == 11
    assert "effect_direction_confidence" not in low


def test_backfill_auditability_skips_entries_with_existing_rationale_and_confidence(monkeypatch):
    monkeypatch.setattr(
        "api_audit.discover_clinical_evidence.ct_search_trials",
        lambda client, intervention, max_results=8: {"total": 4, "trials": []},
    )

    clinical_db = {
        "backed_clinical_studies": [
            {
                "id": "ALREADY_DONE",
                "standard_name": "Already Done",
                "study_type": "rct_multiple",
                "evidence_level": "ingredient-human",
                "effect_direction": "positive_strong",
                "effect_direction_confidence": "high",
                "effect_direction_rationale": "Already curated.",
            },
            {
                "id": "NEEDS_WORK",
                "standard_name": "Needs Work",
                "study_type": "rct_multiple",
                "evidence_level": "ingredient-human",
                "effect_direction": "positive_weak",
            },
        ]
    }

    updates = backfill_auditability_metadata(
        APIClient(cache_path=None),
        clinical_db,
        apply=False,
        limit=10,
    )

    assert [u["id"] for u in updates] == ["NEEDS_WORK"]
