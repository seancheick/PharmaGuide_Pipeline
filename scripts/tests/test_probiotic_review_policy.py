"""Native contexts require a source-bound authorized review; pending stays pending."""
from copy import deepcopy

import pytest

import probiotic_measurements as pm
import studied_formulas
from enrich_supplements_v3 import _probiotic_research_presentation, _derive_clinical_support_level
from scoring_v4.modules.probiotic_evidence import score_evidence
from test_native_study_contexts import context
from test_probiotic_applicability_rubric import strain_product

STUB = "STRAIN_ACIDOPHILUS_LA14"
REVIEW = {"reviewer": "Synthetic delegated source reviewer", "reviewed_at": "2026-09-13T12:00:00Z",
          "scope": "identity_dose_outcome_applicability"}


def positive_rct(*, approved=False, **changes):
    row = context(context_id="la14_rct", components=[STUB], study_design="rct",
                  outcomes=[{"name": "symptom_score", "hierarchy": "primary",
                             "kind": "patient_important", "direction": "positive"}])
    if approved:
        row.update(review_status="clinician_approved", clinical_review=deepcopy(REVIEW), scoring_eligible=True)
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
    product = strain_product(dose=dose, clinical_id=STUB, name="Lactobacillus acidophilus La-14")
    product["product_name"] = "Digestive Constipation probiotic"
    return product


def test_policy_accepts_authorized_existing_rubric_reviews():
    assert pm.native_context_review_policy() == "authorized_source_review"


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


def test_attributable_delegated_source_approval_can_score(registry):
    registry[STUB]["study_contexts"] = [positive_rct(approved=True)]
    entry = registry[STUB]
    derived = pm.effective_strain_evidence(entry)
    assert derived["evidence_strength"] == "medium"
    assert derived["effect_direction"] == "positive_weak"
    assert pm.identity_review_accepted(entry) is True
    row = studied_formulas.assess_probiotic_evidence(la14_product())["strain_assessments"][0]
    assert row["status"] == "strain_dose_applicable"
    evidence = score_evidence(la14_product())
    assert evidence["components"]["evidence_family_certainty"] > 0
    assert evidence["components"]["product_applicability"] == 6
    assert score_evidence(la14_product(dose=None))["components"] == evidence["components"]
    from scoring_v4.modules.probiotic_dose import score_dose
    retained = score_dose(la14_product())["metadata"]["evidence_assessment"]
    assert retained["strain_assessments"][0]["dose_applicable"] is True


def test_explicitly_ineligible_context_never_scores_after_clinician_approval(registry):
    row = positive_rct(approved=True, scoring_eligible=False)
    registry[STUB]["study_contexts"] = [row]
    assert pm.context_accepted_for_scoring(row) is False
    assert pm.effective_strain_evidence(registry[STUB]) is None
    assessed = studied_formulas.assess_probiotic_evidence(la14_product())["strain_assessments"][0]
    assert assessed["dose_applicable"] is False
    assert score_evidence(la14_product())["score"] == 0


@pytest.mark.parametrize("review", [
    None,
    {},
    {"reviewer": "pending", "reviewed_at": "2026-09-13T12:00:00Z",
     "scope": "identity_dose_outcome_applicability"},
    {"reviewer": "Synthetic delegated source reviewer", "reviewed_at": "2026-09-13T12:00:00",
     "scope": "identity_dose_outcome_applicability"},
    {"reviewer": "Synthetic delegated source reviewer", "reviewed_at": "2026-09-13T12:00:00Z",
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


@pytest.mark.parametrize("value", [None, False, 0, "false", "no", 1, "true"])
def test_scoring_eligible_requires_explicit_boolean_true(registry, value):
    registry[STUB]["study_contexts"] = [positive_rct(approved=True)]
    row = positive_rct(approved=True, scoring_eligible=value)
    assert pm.context_accepted_for_scoring(row) is False
    assert pm.context_accepted_for_scoring(positive_rct(approved=True)) is True
    assert pm.context_accepted_for_scoring(positive_rct(approved=True, scoring_eligible=True)) is True
    row.pop("scoring_eligible")
    assert pm.context_accepted_for_scoring(row) is False


def test_unrelated_claim_preserves_ingredient_credit_but_delivery_still_matters(registry):
    registry[STUB]["study_contexts"] = [positive_rct(approved=True)]
    scores = []
    for amount in (None, 1e9):
        product = la14_product(dose=amount)
        product["product_name"] = "Women vaginal probiotic"
        product["probiotic_data"]["is_probiotic_product"] = True
        evidence = score_evidence(product)
        assert evidence["score"] > 0
        assert evidence["metadata"]["claim_alignment"]["level"] == "none"
        scores.append(evidence["score"])
        # Marketing vaginal health is distinct from actual vaginal delivery.
        product["form_factor_canonical"] = "vaginal"
        assert score_evidence(product)["score"] == 0
    assert scores[0] == scores[1]


def test_pediatric_context_cannot_supply_adult_summary_applicability(registry):
    from test_v4_probiotic_evidence_p23 import _match
    row = positive_rct(approved=True)
    row["population"] = {**row["population"], "age_group": "child", "description": "Children with constipation"}
    registry[STUB]["study_contexts"] = [row]
    product = la14_product()
    product["product_name"] = "Adult Digestive Constipation probiotic"
    product["evidence_data"] = {"clinical_matches": [_match(id=STUB,
        ingredient="Lactobacillus acidophilus La-14", standard_name="Lactobacillus acidophilus La-14")]}
    evidence = score_evidence(product)
    # The pediatric study is real research, but it does not apply to an adult
    # product, so its certainty earns nothing here (V4.1 applicability gate).
    assert evidence["components"]["evidence_family_certainty"] == 0
    assert evidence["components"]["product_applicability"] == 0
    assert evidence["components"]["independent_replication_consistency"] == 0
    assert evidence["score"] == 0
    assert evidence["metadata"]["evidence_result_state"] == "research_present_applicability_unestablished"


@pytest.mark.parametrize("recorded", [True, False])
@pytest.mark.parametrize("scoring_eligible", [True, False])
def test_finished_individual_review_preserves_combination_research(registry, recorded, scoring_eligible):
    # The literature conclusion concerns individual-strain attribution, while
    # combination research remains a distinct, reviewed research context.
    registry[STUB]["literature_review"] = deepcopy(
        registry["STRAIN_RHAMNOSUS_GR1"]["literature_review"])
    registry[STUB]["study_contexts"] = ([positive_rct(
        approved=True, identity_scope="combination", components=[STUB, "STRAIN_LGG"],
        scoring_eligible=scoring_eligible)]
        if recorded else [])
    product = la14_product(dose=None)
    product["probiotic_data"]["is_probiotic_product"] = True
    assessed = studied_formulas.assess_probiotic_evidence(product)
    evidence = score_evidence(product)
    assert evidence["score"] == 0
    assert assessed["strain_assessments"][0]["dose_applicable"] is False
    expected = ("research_present_applicability_unestablished" if recorded
                else "no_qualifying_human_evidence")
    assert evidence["metadata"]["evidence_result_state"] == expected
    assert studied_formulas.assess_probiotic_component_disposition(product)["disposition_state"] == expected


@pytest.mark.parametrize("value,accepted", [("2026-09-13", True), ("2999-01-01", False), ("2026-02-30", False)])
def test_dated_approval_preserves_supplied_date_precision(registry, value, accepted):
    row = positive_rct(approved=True)
    row["clinical_review"]["reviewed_at"] = value
    registry[STUB]["study_contexts"] = [deepcopy(row)]
    assert pm.context_accepted_for_scoring(row) is accepted
    row["scoring_eligible"] = False
    assert pm.context_accepted_for_scoring(row) is False


@pytest.mark.parametrize('field', ['reviewer', 'basis', 'context_id', 'outcomes', 'population', 'source_pmids', 'applicability'])
def test_approved_review_cannot_be_forged_by_caller_metadata(field):
    canonical = next(c for c in studied_formulas._clinical_strain_registry()['STRAIN_LGG']['study_contexts']
                     if c['context_id'] == 'lgg_pediatric_aad_guideline_26756877')
    forged = deepcopy(canonical)
    if field == 'reviewer':
        forged['clinical_review']['reviewer'] = 'Unapproved arbitrary reviewer'
    elif field == 'basis':
        forged['clinical_review']['basis'] = 'unverified made-up response'
    elif field == 'context_id':
        forged['context_id'] = 'unregistered-context'
    elif field == 'outcomes':
        forged['outcomes'][0]['direction'] = 'negative'
    elif field == 'population':
        forged['population']['age_group'] = 'adult'
    elif field == 'source_pmids':
        forged['source_pmids'] = ['12345678']
    else:
        forged['applicability'] = {'status': 'applicable'}
    assert not pm.clinical_review_provenance_valid(forged)
    assert not pm.context_accepted_for_scoring(forged)


def test_real_agent_review_and_legitimate_derived_context_keep_current_scope():
    canonical = next(c for c in studied_formulas._clinical_strain_registry()['STRAIN_LGG']['study_contexts']
                     if c['context_id'] == 'lgg_pediatric_aad_guideline_26756877')
    assert 'engineering owner' in canonical['clinical_review']['reviewer']
    assert pm.clinical_review_provenance_valid(canonical)
    derived = {**deepcopy(canonical), 'status': 'source_context_recorded',
               'dose_comparison': 'study_daily_dose_unresolved',
               'label_daily_cfu': None, 'source_row_ref': 'ingredientRows[0]',
               'clinical_applicability': 'not_established',
               'applicability_reason': 'study_daily_dose_unresolved'}
    assert pm.clinical_review_provenance_valid(derived)
    assert pm.context_accepted_for_scoring(derived)


def _prospective_review_fixture(tmp_path, monkeypatch):
    import hashlib
    import importlib.util
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / 'audits/probiotic_curation_queue_2026_09_13/apply_review_response_2026_09_14.py'
    spec = importlib.util.spec_from_file_location('source_bound_review_authoring_test', path)
    authoring = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(authoring)
    source = {'clinically_relevant_strains': [deepcopy(
        studied_formulas._clinical_strain_registry()['STRAIN_LGG'])]}
    row = source['clinically_relevant_strains'][0]['study_contexts'][0]
    row.update(review_status='source_verified_pending_clinical_review', scoring_eligible=False)
    row.pop('clinical_review', None)
    source['clinically_relevant_strains'][0]['study_contexts'] = [row]
    source_path = tmp_path / 'clinically_relevant_strains.json'
    source_path.write_text(json.dumps(source))
    monkeypatch.setattr(authoring, 'REGISTRY', source_path)
    response = {'_metadata': {'dataset_sha256': hashlib.sha256(source_path.read_bytes()).hexdigest()},
                'reviews': {row['context_id']: {'decision': 'approve_as_written', 'patches': [],
                                                'reason': 'Synthetic independently checked source decision'}}}
    return authoring, source, response, row


def test_verified_authoring_candidate_is_not_a_public_runtime_bypass(tmp_path, monkeypatch):
    authoring, source, response, row = _prospective_review_fixture(tmp_path, monkeypatch)
    candidate, summary = authoring.validate(source, response,
        reviewer='Agent source reviewer, independently checked under existing rubric',
        reviewed_at='2026-11-06')
    approved = candidate['clinically_relevant_strains'][0]['study_contexts'][0]
    assert summary['approved'] == 1
    assert approved['review_status'] == 'clinician_approved'  # legacy enum, not clinician attribution
    assert approved['clinical_review']['reviewer'].startswith('Agent source reviewer')
    assert not pm.context_accepted_for_scoring(approved)  # not current canonical approval
    canonical = {entry['id']: entry for entry in candidate['clinically_relevant_strains']}
    monkeypatch.setattr(studied_formulas, '_clinical_strain_registry', lambda: canonical)
    assert pm.clinical_review_provenance_valid(approved)
    assert approved['scoring_eligible'] is False  # authoring cannot erase the explicit exclusion
    assert not pm.context_accepted_for_scoring(approved)


@pytest.mark.parametrize('failure', ['missing_hash', 'wrong_hash', 'unknown_context', 'foreign_pmid', 'mutated_payload', 'mutated_boolean_type'])
def test_prospective_authoring_requires_exact_source_response(tmp_path, monkeypatch, failure):
    authoring, source, response, row = _prospective_review_fixture(tmp_path, monkeypatch)
    if failure == 'missing_hash':
        response['_metadata'].pop('dataset_sha256')
    elif failure == 'wrong_hash':
        response['_metadata']['dataset_sha256'] = '0' * 64
    elif failure == 'unknown_context':
        response['reviews'] = {'not-in-source': next(iter(response['reviews'].values()))}
    elif failure == 'mutated_payload':
        row['condition'] = 'unreviewed-new-condition'
    elif failure == 'mutated_boolean_type':
        thresholds = source['clinically_relevant_strains'][0]['cfu_thresholds']
        assert isinstance(thresholds['dr_pham_signoff'], bool)
        thresholds['dr_pham_signoff'] = int(thresholds['dr_pham_signoff'])
    else:
        response['reviews'][row['context_id']]['patches'] = [{
            'source_pmid': '12345678', 'field_path': 'purpose',
            'old_value': row['purpose'], 'new_value': row['purpose']}]
    with pytest.raises(ValueError):
        authoring.validate(source, response, reviewer='Agent source reviewer', reviewed_at='2026-11-06')


@pytest.mark.parametrize('conflict', [False, True])
def test_combination_context_copies_require_one_semantic_source_scope(registry, conflict):
    source = positive_rct(approved=True, identity_scope='combination', components=[STUB, 'STRAIN_LGG'])
    duplicate = deepcopy(source)
    if conflict:
        duplicate['population']['age_group'] = 'child'
    registry[STUB]['study_contexts'] = [source]
    registry['STRAIN_LGG']['study_contexts'] = [duplicate]
    assert pm.clinical_review_provenance_valid(source) is (not conflict)


def test_actual_formula_owned_context_uses_existing_formula_reference():
    from clinical_applicability import reviewed_entries
    contexts = reviewed_entries()['FORMULA_SEED_DS01']['study_contexts']
    assert contexts
    for row in contexts:
        assert pm.clinical_review_provenance_valid(row)
        assert pm.context_accepted_for_scoring(row) is (row.get('scoring_eligible') is True)


def test_all_actual_native_contexts_retain_explicit_approval_and_eligibility_scope():
    contexts = [c for entry in studied_formulas._clinical_strain_registry().values()
                for c in entry.get('study_contexts', [])]
    assert contexts
    for row in contexts:
        expected = (row.get('review_status') == 'clinician_approved'
                    and row.get('scoring_eligible') is True
                    and row.get('evidence_role') != 'uncontrolled_intervention')
        assert pm.context_accepted_for_scoring(row) is expected, row['context_id']
