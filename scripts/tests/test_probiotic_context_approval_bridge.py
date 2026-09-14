"""A clinician-approved study context is the only native path to dose applicability.

Before 2026-09-13 every native strain row ended at ``strain_context_review_pending``
or ``strain_dose_reference_unreviewed``: ``dose_applicable`` could never be True
for a strain, so ``dose_applicability`` points existed only for Seed's whole-formula
path. This bridge reads an approved context, compares the label's owned daily dose
to the studied arms, and requires a positive primary patient-important outcome.
Pending, adjudication-required and rejected sources never score.
"""
from copy import deepcopy

import pytest

import studied_formulas
from scoring_v4.modules.probiotic_evidence import score_evidence
from test_native_study_contexts import context
from test_probiotic_applicability_rubric import strain_product


@pytest.fixture
def registry(monkeypatch):
    rows = deepcopy(studied_formulas._clinical_strain_registry())
    # Real combination contexts owned by other identities join STRAIN_LGG at
    # assessment time (Wave 2 curation). These unit tests isolate the bridge on
    # the contexts each test injects onto STRAIN_LGG.
    for rid, row in rows.items():
        if rid != "STRAIN_LGG" and row.get("study_contexts"):
            row["study_contexts"] = [c for c in row["study_contexts"]
                                     if "STRAIN_LGG" not in c.get("components", [])]
    monkeypatch.setattr(studied_formulas, "_clinical_strain_registry", lambda: rows)
    return rows


def approved(**changes):
    row = context(review_status="clinician_approved", outcomes=[
        {"name": "stool_frequency", "hierarchy": "primary",
         "kind": "patient_important", "direction": "positive"}])
    row["clinical_review"] = {
        "reviewer": "Dr Test Reviewer",
        "reviewed_at": "2026-09-13T12:00:00Z",
        "scope": "identity_dose_outcome_applicability",
    }
    row.update(changes)
    return row


def assessment(product):
    return studied_formulas.assess_probiotic_evidence(product)["strain_assessments"][0]


def test_approved_context_with_matching_dose_and_positive_primary_outcome_is_applicable(registry):
    registry["STRAIN_LGG"]["study_contexts"] = [approved()]
    row = assessment(strain_product(dose=1e9))
    assert row["status"] == "strain_dose_applicable"
    assert row["dose_applicable"] is True
    ctx = row["study_contexts"][0]
    assert ctx["clinical_applicability"] == "established"
    assert ctx["applicability_reason"] == "clinician_approved_context_dose_and_outcome_match"
    assert ctx["dose_applicability_class"] == "EXACT_TESTED_DOSE"
    assert ctx["dose_applicability_credit"] == 1.0
    evidence = score_evidence(strain_product(dose=1e9))
    assert evidence["components"]["dose_applicability"] > 0


@pytest.mark.parametrize("dose,reason", [
    (5e9, "outside_tested_daily_doses"),
    (None, "label_dose_unknown"),
])
def test_approved_context_without_dose_match_is_not_applicable(registry, dose, reason):
    registry["STRAIN_LGG"]["study_contexts"] = [approved()]
    row = assessment(strain_product(dose=dose))
    assert row["dose_applicable"] is False
    assert row["status"] != "strain_dose_applicable"
    assert row["study_contexts"][0]["clinical_applicability"] == "not_established"
    assert row["study_contexts"][0]["applicability_reason"] == reason


@pytest.mark.parametrize("outcomes", [
    [{"name": "stool_frequency", "hierarchy": "primary", "kind": "patient_important", "direction": "null"}],
    [{"name": "stool_frequency", "hierarchy": "secondary", "kind": "patient_important", "direction": "positive"}],
    [{"name": "microbiome_shift", "hierarchy": "primary", "kind": "surrogate", "direction": "positive"}],
])
def test_approved_context_needs_a_positive_primary_patient_important_outcome(registry, outcomes):
    registry["STRAIN_LGG"]["study_contexts"] = [approved(outcomes=outcomes)]
    row = assessment(strain_product(dose=1e9))
    assert row["dose_applicable"] is False
    assert row["status"] == "strain_context_not_applicable"
    assert row["study_contexts"][0]["applicability_reason"] == "no_positive_primary_patient_important_outcome"


@pytest.mark.parametrize("scope", ["combination", "species_general"])
def test_combination_and_species_contexts_never_become_individual_applicability(registry, scope):
    components = ["STRAIN_LGG", "STRAIN_LACTIS_BB12"] if scope == "combination" else ["STRAIN_LGG"]
    registry["STRAIN_LGG"]["study_contexts"] = [approved(identity_scope=scope, components=components)]
    row = assessment(strain_product(dose=1e9))
    assert row["dose_applicable"] is False
    assert row["status"] == "strain_context_not_applicable"


def test_context_approval_cannot_bypass_identity_review(registry):
    # A label-only designation (no literature hit) is not a verified identity, so
    # even an approved context cannot make it score under either policy.
    registry["STRAIN_LGG"]["study_contexts"] = [approved()]
    registry["STRAIN_LGG"]["cfu_thresholds"]["dr_pham_signoff"] = False
    registry["STRAIN_LGG"]["identity_verification"] = {"status": "label_only_no_literature_hit"}
    row = assessment(strain_product(dose=1e9))
    assert row["status"] == "strain_identity_or_review_unresolved"
    assert row["dose_applicable"] is False


def test_held_contexts_never_score(registry):
    registry["STRAIN_LGG"]["study_contexts"] = [approved(review_status="adjudication_required")]
    row = assessment(strain_product(dose=1e9))
    assert row["status"] == "strain_context_review_pending"
    assert row["dose_applicable"] is False
    assert row["study_contexts"][0]["clinical_applicability"] == "not_established"


def test_source_verified_context_never_scores(registry):
    registry["STRAIN_LGG"]["study_contexts"] = [approved(review_status="source_verified_pending_clinical_review")]
    row = assessment(strain_product(dose=1e9))
    assert row["status"] == "strain_context_review_pending"
    assert row["study_contexts"][0]["applicability_reason"] == "context_not_clinician_approved"


def test_unstudied_doses_between_or_near_arms_earn_no_credit(registry):
    registry["STRAIN_LGG"]["study_contexts"] = [approved()]  # arms 1e9 and 1e10
    within = assessment(strain_product(dose=5e9))
    assert within["study_contexts"][0]["dose_applicability_class"] == "OUTSIDE_TESTED_RANGE"
    assert within["dose_applicability_credit"] == 0.0
    near = assessment(strain_product(dose=1.5e10))
    assert near["study_contexts"][0]["dose_applicability_class"] == "OUTSIDE_TESTED_RANGE"
    assert near["status"] == "strain_context_not_applicable"
    assert near["dose_applicability_credit"] == 0.0
    assert score_evidence(strain_product(dose=5e9))["components"]["dose_applicability"] == 0


def test_status_string_without_approval_provenance_is_invalid_and_cannot_score(registry):
    context_without_provenance = approved()
    context_without_provenance.pop("clinical_review")
    registry["STRAIN_LGG"]["study_contexts"] = [context_without_provenance]
    assert studied_formulas.valid_native_study_context(
        context_without_provenance, "STRAIN_LGG"
    ) is False
    row = assessment(strain_product(dose=1e9))
    assert row["dose_applicable"] is False
    assert row["study_contexts"][0]["status"] == "invalid_context"


def test_rejected_source_is_excluded_from_research_and_never_scores(registry):
    registry["STRAIN_LGG"]["study_contexts"] = [
        approved(review_status="rejected_source", source_pmids=["999"], context_id="bad"),
        approved(context_id="good"),
    ]
    row = assessment(strain_product(dose=1e9))
    statuses = {c.get("context_id"): c["status"] for c in row["study_contexts"]}
    assert statuses == {"bad": "rejected_source", "good": "source_context_recorded"}
    assert "999" not in row["source_pmids"]
    assert row["status"] == "strain_dose_applicable"


def test_one_applicable_context_is_enough_when_others_do_not_match(registry):
    registry["STRAIN_LGG"]["study_contexts"] = [
        approved(context_id="null_arm", outcomes=[{"name": "x", "hierarchy": "primary",
                                                    "kind": "patient_important", "direction": "null"}]),
        approved(context_id="match"),
    ]
    row = assessment(strain_product(dose=1e9))
    assert row["status"] == "strain_dose_applicable"
    by_id = {c["context_id"]: c["clinical_applicability"] for c in row["study_contexts"]}
    assert by_id == {"null_arm": "not_established", "match": "established"}


@pytest.mark.parametrize("field,value,valid", [
    ("study_design", "rct", True),
    ("study_design", "meta_analysis", True),
    ("study_design", "vibes", False),
    ("sample_size", 120, True),
    ("sample_size", 0, False),
    ("blinding", "double", True),
    ("blinding", "triple_secret", False),
    ("funding", "industry", True),
    ("funding", "unknown_source", False),
    ("source_tier", "C", True),
    ("source_tier", "F", False),
    ("trial_registration", "NCT03615651", True),
    ("trial_registration", 12345, False),
])
def test_optional_quality_fields_are_validated_when_present(field, value, valid):
    ctx = context(**{field: value})
    assert studied_formulas.valid_native_study_context(ctx, "STRAIN_LGG") is valid


def test_review_status_vocabulary_is_closed():
    for status in ("source_verified_pending_clinical_review",
                   "adjudication_required", "rejected_source"):
        assert studied_formulas.valid_native_study_context(context(review_status=status), "STRAIN_LGG")
    assert studied_formulas.valid_native_study_context(approved(), "STRAIN_LGG")
    assert not studied_formulas.valid_native_study_context(
        context(review_status="clinician_approved"), "STRAIN_LGG")
    for status in ("approved", "clinician_verified", "search_in_progress", ""):
        assert not studied_formulas.valid_native_study_context(context(review_status=status), "STRAIN_LGG")
