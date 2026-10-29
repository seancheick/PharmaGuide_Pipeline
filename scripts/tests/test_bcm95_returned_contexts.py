"""The signed BCM-95 return must reach its canonical source contexts."""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clinical_applicability import assess_clinical_source_review, reviewed_entries
from clinical_evidence_schema import validate_ingredient_context


def _record():
    data = json.loads((Path(__file__).resolve().parents[1] / "data" / "backed_clinical_studies.json").read_text())
    return next(row for row in data["backed_clinical_studies"] if row["id"] == "BRAND_BCM95")


def test_bcm95_return_covers_both_retained_sources_without_inventing_dose_curve():
    record = _record()
    contexts = record.get("study_contexts", [])
    assert len(contexts) == 2
    assert {pmid for context in contexts for pmid in context["source_pmids"]} == {
        ref["pmid"] for ref in record["references_structured"]
    } == {"30975196", "33516238"}
    assert {tuple(c["dose"]["values"]) for c in contexts} == {(1500,), (1000,)}
    assert {c["dose"]["duration_days"] for c in contexts} == {28, 42}
    assert all(c["identity"]["branded_material"] == "BCM-95/Curcugreen" for c in contexts)
    assert all(c["dose"]["dose_basis"] == "nominal_assigned_arm" for c in contexts)
    assert "minimum_daily_dose" not in record.get("applicability", {})
    assert record["total_enrollment"] is None
    assert "149 enrolled and 139 analyzed" in record["notes"]
    assert "139 randomized" not in record["notes"]
    assert record["score_contribution"] == "tier_1"  # source extraction cannot invent a grade


def test_bcm95_source_contexts_keep_active_comparator_and_scope_limits():
    contexts = _record().get("study_contexts", [])
    assert contexts
    for context in contexts:
        assert validate_ingredient_context(context) == []
        assert context["clinical_review"] == {
            "reviewer": "Dr. Pham", "reviewed_at": "2026-10-26",
            "scope": "identity_dose_outcome_applicability",
        }
        assert context["review_status"] == "clinician_approved"
        assert context["outcomes"][0]["direction"] in {"null", "mixed"}
        assert "not placebo superiority" in " ".join(context["limitations"])
        assert "product matching" in " ".join(context["limitations"])
    reviewed_entries.cache_clear()
    assert assess_clinical_source_review(_record())["is_complete"] is True


def test_magtein_signed_return_keeps_three_trial_families_and_one_correction():
    record = reviewed_entries()["BRAND_MAGTEIN"]
    contexts = record.get("study_contexts", [])
    assert len(contexts) == 3
    assert {pmid for c in contexts for pmid in c["source_pmids"]} == {
        "39252819", "40567408", "41601871", "36558392"
    }
    isolated = [c for c in contexts if c.get("scoring_eligible") is not False]
    assert len(isolated) == 2
    assert {tuple(c["dose"]["values"]) for c in isolated} == {(1000,), (2000,)}
    assert {c["dose"]["duration_days"] for c in isolated} == {21, 42}
    correction_context = next(c for c in contexts if "40567408" in c["source_pmids"])
    assert correction_context["source_pmids"] == ["39252819", "40567408"]
    assert correction_context["source_integrity"] == "corrected"
    combo = next(c for c in contexts if "36558392" in c["source_pmids"])
    assert combo["scoring_eligible"] is False
    assert combo["identity_scope"] == "combination"
    assert len(combo["components"]) == 5
    assert next(r for r in record["references_structured"] if r["pmid"] == "36558392")["scoring_eligible"] is False
    assert "cognitive age ↓" not in record["key_endpoints"]
    assert "Healthy Aging/Longevity" not in record["health_goals_supported"]
    assert set(record["health_goals_supported"]) == {"Focus & Mental Clarity", "Sleep Quality"}
    assert reviewed_entries()["BRAND_BCM95"]["health_goals_supported"] == ["Joint & Bone Health"]


def test_magtein_contexts_apply_current_publisher_correction_without_altering_p_values():
    record = reviewed_entries()["BRAND_MAGTEIN"]
    contexts = record.get("study_contexts", [])
    assert contexts
    cognition = next(c for c in contexts if c["source_pmids"] == ["41601871"])
    assert cognition["source_integrity"] == "corrected"
    assert "two-tailed" in " ".join(cognition["limitations"])
    assert "results unchanged" in " ".join(cognition["limitations"])
    for context in contexts:
        assert validate_ingredient_context(context) == []
        assert context["clinical_review"]["reviewed_at"] == "2026-10-26"
    assert assess_clinical_source_review(record)["is_complete"] is True


def test_scoped_approvals_do_not_validate_provisional_record_grades_or_claim_no_review():
    for key in ("BRAND_BCM95", "BRAND_MAGTEIN"):
        record = reviewed_entries()[key]
        assert record["effect_direction"] == "mixed"
        rationale = record["effect_direction_rationale"]
        assert "2026-10-26" in rationale
        assert "provisional" in rationale
        assert "does not validate" in rationale
        assert "This is not attributable clinician approval" not in rationale
        assert "None of these facts supplies clinician approval" not in record["notes"]


def test_optimsm_return_closes_exact_trial_source_without_double_counting():
    records = reviewed_entries()
    contexts = []
    for key in ('BRAND_OPTIMSM', 'INGR_MSM'):
        record = records[key]
        source = record.get('study_contexts', [])
        assert source, f'{key}: returned A015/A093 source has not been applied'
        context = next(c for c in source if c['source_pmids'] == ['37447322'])
        assert validate_ingredient_context(context, require_complete_review=True) == []
        assert context['identity']['branded_material'] == 'OptiMSM'
        assert context['dose']['values'] == [2000]
        assert context['dose']['duration_days'] == 84
        assert context['outcomes'][0]['hierarchy'] == 'primary'
        assert context['outcomes'][0]['direction'] == 'positive'
        assert context['outcomes'][1]['direction'] == 'null'
        assert assess_clinical_source_review(record)['is_complete'] is True
        assert record['health_goals_supported'] == ['Joint & Bone Health']
        assert record['reference_semantics']['curve'] == 'completed_no_benchmark_neutral'
        contexts.append(context)
    assert contexts[0]['trial_family'] == contexts[1]['trial_family']


def test_optimsm_trial_does_not_credit_generic_material_or_other_daily_regimens():
    from clinical_applicability import assess_clinical_applicability
    for key in ('BRAND_OPTIMSM', 'INGR_MSM'):
        for name, amount, expected in (
            ('OptiMSM', 2000, 'applicable'),
            ('MSM', 2000, 'not_applicable'),
            ('OptiMSM', 1000, 'not_applicable'),
            ('OptiMSM', 6000, 'not_applicable'),
        ):
            row = {'name': name, 'raw_source_text': name,
                   'canonical_id': 'msm', 'mapped': True, 'quantity': amount,
                   'unit': 'mg', 'raw_source_path': 'ingredientRows[0]'}
            product = {'serving_basis': {'min_servings_per_day': 1, 'max_servings_per_day': 1, 'servings_per_day_source': 'directions'},
                       'form_factor_canonical': 'tablet', 'activeIngredients': [row],
                       'ingredient_quality_data': {'ingredients_scorable': [row]}}
            entry = {'id': key, 'matched_canonical_ids': ['msm'],
                     'matched_source_row_refs': ['ingredientRows[0]']}
            assert assess_clinical_applicability(product, entry)['status'] == expected


def test_named_source_reviews_complete_only_general_dose_benchmark():
    from evidence_resolver import _load_literature_evidence
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    for canonical in ('aloe_vera', 'flaxseed', 'green_tea_leaf', 'lignans', 'pygeum', 'weeping_willow_bark', 'chopchini', 'achiote_leaf'):
        record = _load_literature_evidence()[canonical]
        semantics = record.get('reference_semantics') or {}
        assert semantics.get('reference_type') == 'no_benchmark'
        assert semantics.get('curve') == 'completed_no_benchmark_neutral'
        assert semantics['approval_status'] == 'approved_existing_neutral_dose_v41_source_review'
        assert semantics['source_ids']
        assert 'not an exhaustive' in semantics['scope']
        assert _botanical_benchmark({'canonical_id': canonical}) == 'absent'
        # A completed dose search cannot override an actual identity rejection.
        assert _botanical_benchmark({'canonical_id': canonical,
                                    'scoreable_identity': False}) == 'unresolved'
    # A preparation not reviewed in this batch retains its existing hold.
    assert _botanical_benchmark({'canonical_id': 'unreviewed_botanical_test_only'}) == 'unresolved'


def test_creatine_limited_source_scope_does_not_use_mixed_form_strength_pool():
    record = reviewed_entries()['INGR_CREATINE_MONOHYDRATE']
    contexts = record.get('study_contexts', [])
    assert contexts, 'The signed A062 limited source interpretation is not encoded'
    assert len(contexts) == 1
    c = contexts[0]
    assert c['source_pmids'] == ['39074168']
    assert validate_ingredient_context(c, require_complete_review=True) == []
    assert c['identity']['chemical_form'] == 'creatine monohydrate'
    assert len(c['included_study_pmids']) == 11
    assert c['dose']['values'] == []  # no scalar pooled regimen invented
    assert c['dose']['dose_basis'] == 'not_applicable'
    assert c['dose']['duration_days'] is None
    assert 'Andre2016' in ' '.join(c['limitations'])
    mixed = next(r for r in record['references_structured'] if r['pmid'] == '39519498')
    assert mixed['scoring_eligible'] is False
    assert 'ethyl ester' in mixed['notes']
    assert assess_clinical_source_review(record)['is_complete'] is True
    assert 'minimum_daily_dose' not in record['applicability']


def test_seed_return_keeps_symptom_trial_separate_from_mechanistic_reports():
    record = reviewed_entries()['FORMULA_SEED_DS01']
    contexts = record.get('study_contexts', [])
    assert len(contexts) == 3
    symptom = next(c for c in contexts if c['source_pmids'] == ['41599868'])
    assert validate_ingredient_context(symptom, require_complete_review=True) == []
    assert symptom['dose']['unit'] == 'AFU'
    assert symptom['dose']['values'] == [53_600_000_000]
    assert symptom['dose']['duration_days'] == 42
    assert 'first three days' in symptom['dose']['administration_frequency']
    mechanism = [c for c in contexts if c is not symptom]
    assert all(c['scoring_eligible'] is False for c in mechanism)
    assert len({c['trial_family'] for c in mechanism}) == 1
    assert mechanism[0]['trial_family'] != symptom['trial_family']
    assert all(c['dose']['duration_days'] == 91 for c in mechanism)
    assert all('first three days' not in c['dose']['administration_frequency'] for c in mechanism)
    assert assess_clinical_source_review(record)['is_complete'] is True


def test_preparation_mismatch_sources_are_retained_without_brand_credit():
    lutemax = reviewed_entries()['BRAND_LUTEMAX_2020']
    wrong = next(r for r in lutemax['references_structured'] if r['pmid'] == '25251377')
    assert wrong.get('scoring_eligible') is False
    assert 'EyePromise' in wrong['notes']
    quatrefolic = reviewed_entries()['BRAND_QUATREFOLIC']
    wrong = next(r for r in quatrefolic['references_structured'] if r['pmid'] == '23698160')
    # This source supports the completed non-equivalence finding, not brand efficacy.
    assert wrong.get('scoring_eligible') is True
    from evidence_resolver import clinical_record_sources_eligible
    assert not clinical_record_sources_eligible(quatrefolic)
    assert assess_clinical_source_review(quatrefolic)['is_complete'] is True
    assert 'Merck' in wrong['notes']
    assert '149 randomized' not in quatrefolic['notes']
    assert '149 randomized' not in quatrefolic['notable_studies']
    assert '149completers' in quatrefolic['notes']


def test_hyaluronan_source_limitation_is_complete_without_generic_material_transfer():
    from clinical_applicability import assess_clinical_applicability
    record = reviewed_entries()['INGR_HYALURONIC_ACID']
    contexts = record.get('study_contexts', [])
    assert contexts
    c = next(c for c in contexts if c['source_pmids'] == ['34203487'])
    assert c['outcomes'][0]['hierarchy'] == 'not_reported'
    assert validate_ingredient_context(c, require_complete_review=True) == []
    assert c['dose']['values'] == [120]
    assert c['dose']['duration_days'] == 84
    assert c['identity']['branded_material'] == 'Hyabest (S) LF-P'
    assert assess_clinical_source_review(record)['is_complete'] is True
    # A complete review and exact material do not turn a mixed cosmetic
    # surrogate into an independently positive qualifying endpoint.
    assert c['outcomes'][0]['direction'] == 'mixed'
    assert c['outcomes'][0]['kind'] == 'surrogate'
    for name, amount, reason in [('Hyaluronic acid', 120, 'clinical_form_mismatch'),
                                 ('Hyabest S LF-P Hyaluronic Acid', 120, 'clinical_outcome_not_qualified'),
                                 ('Hyabest S LF-P Hyaluronic Acid', 60, 'below_applicable_clinical_dose')]:
        row = {'name': name, 'raw_source_text': name, 'canonical_id': 'hyaluronic_acid',
               'quantity': amount, 'unit': 'mg', 'raw_source_path': 'ingredientRows[0]'}
        product = {'activeIngredients': [row], 'physicalState': {'name': 'Capsule'},
                   'serving_basis': {'min_servings_per_day': 1, 'max_servings_per_day': 1,
                                     'servings_per_day_source': 'directions'},
                   'ingredient_quality_data': {'ingredients_scorable': [row]}}
        decision = assess_clinical_applicability(product, {'id': record['id'],
            'matched_source_row_refs': ['ingredientRows[0]'],
            'matched_canonical_ids': ['hyaluronic_acid']})
        assert decision['status'] == 'not_applicable'
        assert decision['reason_code'] == reason


def test_reviewed_disease_only_reference_is_complete_but_never_healthy_focus_credit():
    from evidence_resolver import resolve_evidence_for_row
    from assessment_readiness import _resolved_evidence_assessment
    record = reviewed_entries()['INGR_ALPHA_GPC']
    assert record['study_type'] == 'reference'
    assert assess_clinical_source_review(record)['is_complete'] is True
    row = {'name': 'Alpha GPC', 'canonical_id': 'alpha_gpc', 'quantity': 600, 'unit': 'mg'}
    resolution = resolve_evidence_for_row(row)
    assert resolution.points_eligible is False
    assert resolution.reason_code == 'reference_only_clinical_record'
    assert not resolution.blocking_reasons
    status, reason, _ = _resolved_evidence_assessment(resolution)
    assert status == 'evaluated_limited_or_negative'
    assert reason == 'reference_only_clinical_record'


def test_reference_label_alone_cannot_close_unfinished_or_ineligible_sources(monkeypatch):
    from copy import deepcopy
    import clinical_applicability
    record = deepcopy(reviewed_entries()['INGR_ALPHA_GPC'])
    assert record.get('study_contexts')
    for c in record['study_contexts']:
        c['review_status'] = 'source_verified_pending_clinical_review'
    monkeypatch.setattr(clinical_applicability, 'reviewed_entries', lambda: {record['id']: record})
    assert assess_clinical_source_review(record)['is_complete'] is False


def test_reviewed_reference_scope_cannot_override_missing_or_held_source_proof(monkeypatch):
    from copy import deepcopy
    import clinical_applicability
    original = deepcopy(reviewed_entries()['INGR_ALPHA_GPC'])
    for mutation in ('pending', 'missing', 'record_hold', 'references_held', 'retracted', 'unrelated', 'future'):
        record = deepcopy(original)
        if mutation == 'pending':
            record['study_contexts'][0]['review_status'] = 'source_verified_pending_clinical_review'
        elif mutation == 'missing':
            record['study_contexts'] = []
        elif mutation == 'record_hold':
            record['scoring_eligible'] = False
        elif mutation in ('references_held', 'retracted'):
            for reference in record['references_structured']:
                reference['scoring_eligible' if mutation == 'references_held' else 'retracted'] = False if mutation == 'references_held' else True
        elif mutation == 'unrelated':
            record['study_contexts'][0]['source_pmids'] = ['12345678']
        else:
            record['study_contexts'][0]['clinical_review']['reviewed_at'] = '2099-01-01'
        monkeypatch.setattr(clinical_applicability, 'reviewed_entries', lambda record=record: {record['id']: record})
        assert clinical_applicability.assess_clinical_source_review(record)['is_complete'] is False, mutation


def test_bc30_recovered_paper_hierarchy_preserves_retrospective_registration_limits():
    data = json.loads((Path(__file__).resolve().parents[1] / 'data' / 'clinically_relevant_strains.json').read_text())
    entry = next(e for e in data['clinically_relevant_strains'] if e['id'] == 'STRAIN_COAGULANS_GBI30')
    c = next(c for c in entry['study_contexts'] if c['context_id'] == 'bc30_functional_gi_complaints_40707016')
    assert c['dose']['dosage_forms'] == ['oral powder sachet']
    assert c['dose']['values'] == [1_000_000_000]
    assert c['dose']['duration_days'] == 28
    assert 'before a meal' in c['dose']['administration_frequency']
    assert all(o['hierarchy'] in {'primary', 'secondary'} for o in c['outcomes'])
    assert any(o['direction'] == 'null' for o in c['outcomes'])
    assert 'retrospective' in ' '.join(c['limitations']).lower()
    assert '40707016' in c['source_pmids']
    # Paper-stated hierarchy is verified, not prospectively prespecified by assumption.
    assert 'prospectiveprespecificationnotestablished' in ' '.join(c['limitations'])
    assert assess_clinical_source_review(reviewed_entries()['STRAIN_BC30'])['is_complete'] is True
    from clinical_evidence_schema import validate_frozen_context
    assert validate_frozen_context(c, require_complete_review=True) == []


def test_applied_source_scope_has_no_stale_positive_or_unverified_prose():
    alpha = reviewed_entries()['INGR_ALPHA_GPC']
    assert 'study_type=systematic_review_meta' not in alpha['effect_direction_rationale']
    assert 'primary_outcome=Focus & Mental Clarity' not in alpha['effect_direction_rationale']
    assert 'reference-only' in alpha['effect_direction_rationale'].lower()
    for key in ('BRAND_OPTIMSM', 'INGR_MSM'):
        record = reviewed_entries()[key]
        assert record['total_enrollment'] == 88
        assert 'Exact branded preparation and unique aggregate require methods-level verification' not in record['notes']


def test_unread_flaxseed_correction_is_not_an_active_supporting_source(monkeypatch):
    from copy import deepcopy
    import evidence_resolver as owner
    record = owner._load_literature_evidence()['flaxseed']
    assert record['verification_result'] == 'authoritative_pubmed_verified'
    assert record['verification_provenance']['all_pmids_verified'] is True
    assert '25740909' in record['notes'] and '26525908' in record['notes']
    assert {s['pmid'] for s in record['qualifying_human_studies']} == {'24126178','26071633'}
    assert record['applicability']['source_pmids'] == ['24126178','26071633']
    # Retiring one unread source never allows an unverified replacement to qualify.
    pending = deepcopy(record)
    pending['verification_provenance']['all_pmids_verified'] = False
    monkeypatch.setattr(owner, '_load_literature_evidence', lambda:{'flaxseed':pending})
    result = owner.resolve_evidence_for_row({'name':'Ground Flaxseed','canonical_id':'flaxseed'})
    assert result.points_eligible is False
    assert result.blocking_reasons


def test_an_adult_only_source_cannot_qualify_the_same_material_for_children():
    from clinical_applicability import assess_clinical_applicability
    row = {'name': 'OptiMSM', 'raw_source_text': 'OptiMSM', 'canonical_id': 'msm',
           'quantity': 2000, 'unit': 'mg', 'raw_source_path': 'ingredientRows[0]'}
    product = {'fullName': 'Kids Joint Comfort', 'targetGroups': [{'name': 'Children 4-12 years'}],
               'activeIngredients': [row], 'ingredient_quality_data': {'ingredients_scorable': [row]},
               'serving_basis': {'min_servings_per_day': 1, 'max_servings_per_day': 1,
                                 'servings_per_day_source': 'directions'}}
    entry = {'id': 'BRAND_OPTIMSM', 'matched_canonical_ids': ['msm'],
             'matched_source_row_refs': ['ingredientRows[0]']}
    decision = assess_clinical_applicability(product, entry)
    assert decision['status'] == 'not_applicable'
    assert decision['reason_code'] == 'clinical_population_mismatch'
    product['fullName'] = 'Adult Joint Comfort'
    product['targetGroups'] = [{'name': 'Adults'}]
    assert assess_clinical_applicability(product, entry)['status'] == 'applicable'



def test_preparation_plus_sign_is_not_erased_or_rescued_by_a_negated_name(monkeypatch):
    import clinical_applicability
    from test_evidence_resolver import _approved_test_source
    policy = _approved_test_source({'id': 'TEST_PLUS_FORM', 'standard_name': 'Levagen+',
        'study_type': 'rct_single', 'evidence_level': 'ingredient-human', 'effect_direction': 'positive_strong',
        'applicability': {'scope': 'ingredient', 'require_source_label_form': True,
                          'required_form_terms': ['Levagen+']}}, name='Levagen+')
    monkeypatch.setattr(clinical_applicability, 'reviewed_entries', lambda: {policy['id']: policy})
    for name, expected in [('Levagen+', 'applicable'), ('Levagen®+', 'applicable'), ('Levagen', 'not_applicable'),
                           ('not Levagen+', 'not_applicable')]:
        row = {'name': name, 'raw_source_text': name, 'canonical_id': 'palmitoylethanolamide',
               'quantity': 600, 'unit': 'mg', 'raw_source_path': 'ingredientRows[0]'}
        product = {'activeIngredients': [row], 'ingredient_quality_data': {'ingredients_scorable': [row]}}
        entry = {'id': policy['id'], 'matched_source_row_refs': ['ingredientRows[0]'],
                 'matched_canonical_ids': ['palmitoylethanolamide']}
        assert clinical_applicability.assess_clinical_applicability(product, entry)['status'] == expected


def test_excluded_claim_terms_preserve_negation_and_warning_boundaries(monkeypatch):
    import clinical_applicability as owner
    record = {'id': 'SLEEP_SCOPE', 'applicability': {'scope': 'ingredient',
              'excluded_claim_terms': ['jet lag', 'shift work']}}
    monkeypatch.setattr(owner, 'reviewed_entries', lambda: {record['id']: record})
    for text, expected in [('Supports ordinary adult sleep', 'not_curated'),
                           ('Helps jet lag', 'not_applicable'),
                           ('Supports sleep during shift work', 'not_applicable'),
                           ('Not for jet lag', 'not_curated')]:
        result = owner.assess_clinical_applicability({'product_name': text}, record)
        # With no linked ingredient this fixture otherwise stays unresolved;
        # it must never be rejected by a negated or absent excluded claim.
        if expected == 'not_applicable':
            assert result == {'status': 'not_applicable', 'reason_code': 'label_purpose_evidence_mismatch'}
        else:
            assert result.get('reason_code') != 'label_purpose_evidence_mismatch'
    result = owner.assess_clinical_applicability({'product_name': 'Adult sleep',
        'statements': [{'type': 'Precautions', 'notes': 'Do not use for jet lag'}]}, record)
    assert result.get('reason_code') != 'label_purpose_evidence_mismatch'
    for invalid in ('jet lag', [None], ['!!!']):
        record['applicability']['excluded_claim_terms'] = invalid
        assert owner.assess_clinical_applicability({}, record) == {
            'status': 'unresolved', 'reason_code': 'invalid_applicability_contract'}


def test_unresolved_scope_cannot_be_projected_as_completed_negative():
    from assessment_readiness import _resolved_evidence_assessment, EVIDENCE_NOT_YET_EVALUATED
    from evidence_resolver import EvidenceResolution, EvidenceDisposition
    result = EvidenceResolution(canonical_id='melatonin', ingredient_name='Melatonin',
        matched_owners=['backed_clinical_studies'],
        disposition=EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value,
        points_eligible=False, applicability_status='applicability_unestablished',
        reason_code='invalid_applicability_contract')
    assert _resolved_evidence_assessment(result)[0] == EVIDENCE_NOT_YET_EVALUATED


def test_returned_continuation_uses_scoped_sources_without_general_claim_transfer():
    records = reviewed_entries()
    for key in ('INGR_HONEY', 'INGR_NAC', 'INGR_ALPHA_LIPOIC_ACID'):
        assert records[key]['study_type'] == 'reference'
        assert assess_clinical_source_review(records[key])['is_complete'] is True
    sleep = records['INGR_MELATONIN']
    assert sleep['applicability']['excluded_claim_terms']
    assert 'minimum_daily_dose' not in sleep['applicability']
    assert assess_clinical_source_review(sleep)['is_complete'] is True
    pea = records['INGR_PEA']
    assert pea['applicability']['required_form_terms'] == ['LipiSperse']
    assert pea['applicability']['minimum_daily_dose'] == 600
    assert assess_clinical_source_review(pea)['is_complete'] is True


def test_resolver_preserves_unresolved_exclusion_contract(monkeypatch):
    import clinical_applicability as owner
    import evidence_resolver as resolver
    record = {'id': 'TEST_EXCLUSION', 'study_type': 'rct_single',
              'applicability': {'scope': 'ingredient', 'excluded_claim_terms': 'jet lag'}}
    monkeypatch.setattr(owner, 'reviewed_entries', lambda: {record['id']: record})
    monkeypatch.setattr(resolver, '_backed_studies_index', lambda: {'melatonin': [record]})
    row = {'canonical_id': 'melatonin', 'name': 'Melatonin', 'quantity': 3,
           'unit': 'mg', 'raw_source_path': 'ingredientRows[0]'}
    product = {'product_name': 'Adult sleep', 'activeIngredients': [row],
               'ingredient_quality_data': {'ingredients_scorable': [row]}}
    result = resolver.resolve_evidence_for_row(row, product)
    assert result.points_eligible is False
    assert result.reason_code == 'invalid_applicability_contract'
    assert result.applicability_status == 'applicability_unestablished'


def test_pea_diabetic_neuropathy_reference_cannot_qualify_generic_joint_claim():
    from evidence_resolver import resolve_evidence_for_row
    row = {'canonical_id': 'palmitoylethanolamide', 'name': 'Palmitoylethanolamide',
           'raw_source_text': 'Palmitoylethanolamide (LipiSperse)',
           'raw_source_path': 'activeIngredients[0]', 'quantity': 600, 'unit': 'mg'}
    product = {'product_name': 'Joint Comfort', 'physicalState': {'name': 'Capsule'},
               'suggested_use': 'For joint comfort', 'activeIngredients': [row],
               'ingredient_quality_data': {'ingredients_scorable': [row]}}
    result = resolve_evidence_for_row(row, product)
    assert result.points_eligible is False
    assert result.reason_code == 'reference_only_clinical_record'
    assert row['quantity'] == 600


def test_reviewed_literature_exclusions_complete_but_missing_scope_stays_open():
    from assessment_readiness import _resolved_evidence_assessment, EVIDENCE_NOT_YET_EVALUATED, EVIDENCE_EVALUATED_LIMITED_OR_NEGATIVE
    from evidence_resolver import EvidenceResolution, EvidenceDisposition
    for reason in ('clinical_delivery_mismatch', 'clinical_identity_excluded',
                   'clinical_form_excluded', 'formula_reference_not_individual_evidence',
                   'clinical_form_mismatch', 'clinical_source_label_unresolved',
                   'clinical_source_row_unresolved', 'invalid_applicability_contract'):
        resolution = EvidenceResolution('fixture', 'Fixture', ['literature_evidence'],
            EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value,
            False, 'applicability_unestablished', reason,
            owner_facts={'literature_evidence': {'verification_result': 'authoritative_pubmed_verified'}})
        expected = (EVIDENCE_NOT_YET_EVALUATED if reason in {
            'clinical_source_label_unresolved', 'clinical_source_row_unresolved',
            'invalid_applicability_contract'} else EVIDENCE_EVALUATED_LIMITED_OR_NEGATIVE)
        assert _resolved_evidence_assessment(resolution)[0] == expected, reason


def test_verified_matcha_powder_review_finishes_an_extract_mismatch_without_credit():
    from evidence_resolver import resolve_evidence_for_row
    from assessment_readiness import _resolved_evidence_assessment, EVIDENCE_EVALUATED_LIMITED_OR_NEGATIVE
    row = {'canonical_id': 'matcha_tea_powder', 'name': 'Matcha Tea Extract',
           'quantity': 100, 'unit': 'mg', 'raw_source_text': 'Matcha Tea Extract',
           'raw_source_path': 'ingredientRows[0]'}
    product = {'product_name': 'Matcha Tea Extract', 'activeIngredients': [row],
               'ingredient_quality_data': {'ingredients_scorable': [row]},
               'physicalState': {'name': 'Capsule'}}
    result = resolve_evidence_for_row(row, product)
    assert result.owner_facts['literature_evidence']['verification_result'] == 'authoritative_pubmed_verified'
    assert result.reason_code == 'clinical_form_excluded'
    assert result.points_eligible is False
    assert _resolved_evidence_assessment(result)[0] == EVIDENCE_EVALUATED_LIMITED_OR_NEGATIVE
    assert row['quantity'] == 100


def test_missing_source_preparation_proof_cannot_be_completed_as_a_form_mismatch():
    from evidence_resolver import resolve_evidence_for_row
    from assessment_readiness import _resolved_evidence_assessment, EVIDENCE_NOT_YET_EVALUATED
    row = {'canonical_id': 'msm', 'name': 'OptiMSM', 'quantity': 2000,
           'unit': 'mg', 'raw_source_path': 'ingredientRows[0]'}
    product = {'product_name': 'Adult Joint Comfort', 'activeIngredients': [row],
               'ingredient_quality_data': {'ingredients_scorable': [row]}}
    result = resolve_evidence_for_row(row, product)
    assert result.points_eligible is False
    assert result.reason_code == 'clinical_source_label_unresolved'
    assert _resolved_evidence_assessment(result)[0] == EVIDENCE_NOT_YET_EVALUATED
