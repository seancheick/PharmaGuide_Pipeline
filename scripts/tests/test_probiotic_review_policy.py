"""Native contexts stay non-scoring until an attributable clinical approval."""
from copy import deepcopy

import pytest

import probiotic_measurements as pm
import studied_formulas
from enrich_supplements_v3 import _probiotic_research_presentation, _derive_clinical_support_level
from scoring_v4.modules.probiotic_evidence import score_evidence
from test_native_study_contexts import context
from test_probiotic_applicability_rubric import strain_product

STUB = "STRAIN_ACIDOPHILUS_LA14"
REVIEW = {"reviewer": "Dr Test Reviewer", "reviewed_at": "2026-09-13T12:00:00Z",
          "scope": "identity_dose_outcome_applicability"}


def positive_rct(*, approved=False, **changes):
    row = context(context_id="la14_rct", components=[STUB], study_design="rct",
                  outcomes=[{"name": "symptom_score", "hierarchy": "primary",
                             "kind": "patient_important", "direction": "positive"}])
    if approved:
        row.update(review_status="clinician_approved", clinical_review=deepcopy(REVIEW))
    row.update(changes)
    return row


@pytest.fixture
def registry(monkeypatch):
    rows = deepcopy(studied_formulas._clinical_strain_registry())
    # La-14 stands in for a verified identity with no finished review. Its
    # 2026-09-22 literature review and contexts are removed so each test here
    # authors the only contexts in play.
    rows[STUB].pop("literature_review", None)
    rows[STUB].update(study_contexts=[], evidence_level="unreviewed")
    monkeypatch.setattr(studied_formulas, "_clinical_strain_registry", lambda: rows)
    return rows


def la14_product(dose=1e9):
    return strain_product(dose=dose, clinical_id=STUB, name="Lactobacillus acidophilus La-14")


def test_policy_default_is_clinician_only():
    assert pm.native_context_review_policy() == "clinician_only"


def test_verified_stub_without_contexts_stays_pending(registry):
    entry = registry[STUB]
    assert pm.identity_confidence(entry) == "deposit_crosswalk_verified"
    assert pm.effective_strain_evidence(entry) is None
    assert pm.identity_review_accepted(entry) is False
    out = _probiotic_research_presentation(entry)
    assert out["review_status"] == "pending_review"
    assert out["research_match_status"] == "pending_review"
    assert out["identity_confidence"] == "deposit_crosswalk_verified"
    assert _derive_clinical_support_level(entry) is None


def test_source_verified_rct_remains_research_only(registry):
    registry[STUB]["study_contexts"] = [positive_rct()]
    entry = registry[STUB]
    assert pm.effective_strain_evidence(entry) is None
    assert pm.identity_review_accepted(entry) is False
    assert _probiotic_research_presentation(entry)["review_status"] == "pending_review"
    assert _derive_clinical_support_level(entry) is None
    assert score_evidence(la14_product())["score"] == 0


def test_attributable_clinician_approval_can_score(registry):
    registry[STUB]["study_contexts"] = [positive_rct(approved=True)]
    entry = registry[STUB]
    derived = pm.effective_strain_evidence(entry)
    assert derived["evidence_strength"] == "medium"
    assert derived["effect_direction"] == "positive_weak"
    assert pm.identity_review_accepted(entry) is True
    row = studied_formulas.assess_probiotic_evidence(la14_product())["strain_assessments"][0]
    assert row["status"] == "strain_dose_applicable"
    assert score_evidence(la14_product())["components"]["dose_applicability"] > 0


def test_explicitly_ineligible_context_never_scores_after_clinician_approval(registry):
    row = positive_rct(approved=True, scoring_eligible=False)
    registry[STUB]["study_contexts"] = [row]
    assert pm.context_accepted_for_scoring(row) is False
    assert pm.effective_strain_evidence(registry[STUB]) is None
    assessed = studied_formulas.assess_probiotic_evidence(la14_product())["strain_assessments"][0]
    assert assessed["dose_applicable"] is False
    assert score_evidence(la14_product())["components"]["dose_applicability"] == 0


@pytest.mark.parametrize("review", [
    None,
    {},
    {"reviewer": "pending", "reviewed_at": "2026-09-13T12:00:00Z",
     "scope": "identity_dose_outcome_applicability"},
    {"reviewer": "Dr Test Reviewer", "reviewed_at": "2026-09-13T12:00:00",
     "scope": "identity_dose_outcome_applicability"},
    {"reviewer": "Dr Test Reviewer", "reviewed_at": "2026-09-13T12:00:00Z",
     "scope": "identity_only"},
])
def test_approval_status_without_valid_provenance_never_scores(registry, review):
    row = positive_rct(approved=True)
    if review is None:
        row.pop("clinical_review")
    else:
        row["clinical_review"] = review
    registry[STUB]["study_contexts"] = [row]
    assert pm.context_accepted_for_scoring(row) is False
    assert pm.identity_review_accepted(registry[STUB]) is False
    assert score_evidence(la14_product())["score"] == 0


def test_future_dated_clinical_review_never_scores(registry):
    row = positive_rct(approved=True)
    row["clinical_review"]["reviewed_at"] = "2999-01-01T00:00:00Z"
    registry[STUB]["study_contexts"] = [row]
    assert pm.context_accepted_for_scoring(row) is False
    assert score_evidence(la14_product())["score"] == 0


@pytest.mark.parametrize("status", ["designation_found_species_unconfirmed", "label_only_no_literature_hit"])
def test_unverified_designations_never_score_even_with_approved_context(registry, status):
    registry[STUB]["study_contexts"] = [positive_rct(approved=True)]
    registry[STUB]["identity_verification"]["status"] = status
    assert pm.identity_review_accepted(registry[STUB]) is False
    assert score_evidence(la14_product())["score"] == 0


def test_missing_identity_verification_never_defaults_to_verified(registry):
    entry = registry[STUB]
    entry.pop("identity_verification", None)
    entry["study_contexts"] = [positive_rct(approved=True)]
    assert pm.identity_confidence(entry) == "label_designation_recognized"
    assert pm.identity_review_accepted(entry) is False
    assert score_evidence(la14_product())["score"] == 0


def test_combination_only_evidence_does_not_accept_an_identity(registry):
    registry[STUB]["study_contexts"] = [positive_rct(
        approved=True, identity_scope="combination", components=[STUB, "STRAIN_LGG"])]
    assert pm.derived_context_evidence(registry[STUB]) is None
    assert pm.identity_review_accepted(registry[STUB]) is False


@pytest.mark.parametrize("status", ["adjudication_required", "rejected_source"])
def test_held_and_rejected_contexts_do_not_accept_an_identity(registry, status):
    registry[STUB]["study_contexts"] = [positive_rct(approved=True, review_status=status)]
    assert pm.derived_context_evidence(registry[STUB]) is None


def test_evidence_strength_counts_independent_trial_families(registry):
    first = positive_rct(approved=True, context_id="paper-a", trial_family="same-trial")
    second = positive_rct(approved=True, context_id="paper-b", trial_family="same-trial")
    registry[STUB]["study_contexts"] = [first, second]
    assert pm.derived_context_evidence(registry[STUB])["evidence_strength"] == "medium"
    second["trial_family"] = "independent-trial"
    assert pm.derived_context_evidence(registry[STUB])["evidence_strength"] == "strong"


def test_clinician_signed_summary_wins_over_contexts(registry):
    entry = registry["STRAIN_LGG"]
    assert entry["cfu_thresholds"]["dr_pham_signoff"] is True
    assert pm.effective_strain_evidence(entry)["type"] == "clinical_guideline"
    assert _probiotic_research_presentation(entry)["review_status"] == "clinician_verified"


def test_suspended_legacy_signoff_stays_under_the_clinician_gate(registry):
    # BB-12's approved exact-strain contexts cannot replace a suspended clinician
    # sign-off (its state 2026-09-04 to 2026-09-22, when Dr Pham restored it).
    from test_evidence_completeness_closure_20260921 import suspend

    entry = suspend(registry["STRAIN_LACTIS_BB12"])
    assert pm.derived_context_evidence(entry) is not None  # approved contexts exist
    assert entry["cfu_thresholds"]["dr_pham_signoff"] is False
    assert pm.effective_strain_evidence(entry)["type"] != "study_contexts_derived"
    assert pm.identity_review_accepted(entry) is False


def test_approved_context_filed_under_the_wrong_identity_never_credits_it(registry):
    # A valid-looking LGG study approved with provenance but stored under La-14.
    registry[STUB]["study_contexts"] = [positive_rct(approved=True, components=["STRAIN_LGG"])]
    entry = registry[STUB]
    assert studied_formulas.valid_native_study_context(entry["study_contexts"][0], STUB) is False
    assert pm.derived_context_evidence(entry) is None
    assert pm.identity_review_accepted(entry) is False
    assert score_evidence(la14_product())["score"] == 0
    assert _probiotic_research_presentation(entry)["review_status"] != "clinician_context_approved"


def test_spores_dose_without_measurement_type_never_credits_an_identity(registry):
    row = positive_rct(approved=True)
    row["dose"].update(unit="spores", values=[1e9])
    registry[STUB]["study_contexts"] = [row]
    assert pm.derived_context_evidence(registry[STUB]) is None
    assert score_evidence(la14_product())["score"] == 0


@pytest.mark.parametrize("value", [0, "false", "no", 1, "true"])
def test_scoring_eligible_is_only_true_or_absent(value):
    row = positive_rct(approved=True, scoring_eligible=value)
    assert pm.context_accepted_for_scoring(row) is False
    assert pm.context_accepted_for_scoring(positive_rct(approved=True)) is True
    assert pm.context_accepted_for_scoring(positive_rct(approved=True, scoring_eligible=True)) is True
