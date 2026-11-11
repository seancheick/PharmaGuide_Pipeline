"""Integrity holds must survive both evidence resolution and public scoring."""
import copy
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import evidence_resolver as er
from clinical_evidence_schema import validate_ingredient_context
from probiotic_measurements import context_review_finished
from scoring_v4.modules.generic_evidence import score_evidence
from scoring_v4.scored_artifact import build_scored_artifact


def test_bacopa_review_keeps_primary_correction_and_shared_witness_explicit():
    from clinical_applicability import assess_clinical_source_review, reviewed_entries
    from clinical_evidence_schema import validate_ingredient_context
    record = reviewed_entries()['INGR_BACOPA']
    contexts = {c['source_pmids'][0]: c for c in record['study_contexts']}
    assert set(contexts) == {'11498727', '24252493', '27912958'}
    primary = contexts['11498727']
    assert validate_ingredient_context(primary, require_complete_review=True) == []
    assert primary['source_integrity'] == 'corrected'
    assert primary['dose']['values'] == [320]
    assert primary['dose']['duration_days'] == 84
    assert '10.1007/s00213-015-3965-3' in primary['dose']['source_provenance']['location']
    assert primary['trial_family'] == contexts['24252493']['trial_family']
    assert record['effect_direction'] == 'mixed'
    assert record['effect_direction_confidence'] == 'low'
    assert record['published_studies_count'] == 1
    assert 'total_enrollment' not in record and 'registry_completed_trials_count' not in record
    assert 'min_clinical_dose' not in record
    assert 'Healthy Aging/Longevity' not in record['health_goals_supported']
    assert assess_clinical_source_review(record)['is_complete']


def test_bacopa_syntheses_retain_nulls_and_pediatric_transfer_exclusion():
    from clinical_applicability import reviewed_entries
    from clinical_evidence_schema import validate_ingredient_context
    contexts = {c['source_pmids'][0]: c for c in reviewed_entries()['INGR_BACOPA']['study_contexts']}
    adult = contexts['24252493']
    assert validate_ingredient_context(adult, require_complete_review=True) == []
    assert any(o['direction'] == 'null' and 'choice reaction' in o['name'].lower()
               for o in adult['outcomes'])
    text = ' '.join(adult['limitations'])
    assert '11498727' in text and '10.1002/ptr.5441' in text
    assert 'not independent' in text.lower()
    pediatric = contexts['27912958']
    assert pediatric['review_status'] == 'rejected_source'
    assert pediatric['scoring_eligible'] is False
    assert validate_ingredient_context(pediatric, require_complete_review=True) == []
    text = ' '.join(pediatric['limitations']).lower()
    assert 'unpublished' in text and 'uncontrolled' in text and 'adult' in text


@pytest.mark.parametrize('name,title,physical,eligible', [
    ('Bacopa monnieri extract', 'Adult cognition supplement', 'Capsule', True),
    ('Bacopa monnieri extract', 'Adult cognition supplement', 'Tablet', True),
    ('Bacopa monnieri', 'Adult cognition supplement', 'Capsule', False),
    ('Bacopa whole herb powder', 'Adult cognition supplement', 'Capsule', False),
    ('Bacopa monnieri extract', 'Kids cognition ages 6-12', 'Capsule', False),
    ('Bacopa monnieri extract', 'Adult cognition supplement', 'Powder', False),
])
def test_bacopa_studied_extract_class_keeps_material_delivery_and_population_limits(name, title, physical, eligible):
    from clinical_applicability import filter_clinical_matches, reviewed_entries
    row = {'name': name, 'raw_source_text': name, 'source_label_name': name,
           'canonical_id': 'bacopa', 'mapped': True, 'quantity': 100, 'unit': 'mg',
           'raw_source_path': 'ingredientRows[0]'}
    product = {'fullName': title, 'physicalState': {'langualCodeDescription': physical},
               'activeIngredients': [copy.deepcopy(row)],
               'ingredient_quality_data': {'ingredients': [row], 'ingredients_scorable': [row]}}
    entry = {**reviewed_entries()['INGR_BACOPA'], 'ingredient': name,
             'matched_canonical_ids': ['bacopa'], 'matched_source_row_refs': ['ingredientRows[0]']}
    original = copy.deepcopy((product, entry))
    matches, _ = filter_clinical_matches(product, [entry], assess_amount=False,
                                          require_claim_alignment=False)
    assert bool(matches) is eligible
    if eligible:
        product['evidence_data'] = {'clinical_matches': matches}
        artifact = build_scored_artifact(product)
        assert artifact['quality_pillars_v4']['evidence']['score'] > 0
        product.pop('evidence_data')
    assert (product, entry) == original


def test_lemon_balm_unread_methods_do_not_turn_unverified_counts_into_depth():
    from clinical_applicability import assess_clinical_source_review, reviewed_entries
    record = reviewed_entries()['INGR_LEMON_BALM']
    assert 'total_enrollment' not in record and 'registry_completed_trials_count' not in record
    assert record['study_contexts'] == []
    assert not assess_clinical_source_review(record)['is_complete']
    assert '34449930' in record['notes'] and '12 databases' in record['notes']


def test_lemon_balm_unread_preparation_does_not_inherit_flower_specific_unii():
    from clinical_applicability import reviewed_entries
    record = reviewed_entries()['INGR_LEMON_BALM']
    assert 'unii' not in record['external_ids']
    assert 'RCU5REA2I1' not in str(record)


def test_bacopa_positive_task_names_keep_cognition_claim_alignment():
    from clinical_applicability import assess_clinical_applicability, reviewed_entries
    name = 'Bacopa monnieri extract'
    row = {'name': name, 'raw_source_text': name, 'source_label_name': name,
           'canonical_id': 'bacopa', 'mapped': True, 'quantity': 100, 'unit': 'mg',
           'raw_source_path': 'ingredientRows[0]'}
    product = {'fullName': 'Adult cognition supplement',
               'physicalState': {'langualCodeDescription': 'Capsule'},
               'activeIngredients': [copy.deepcopy(row)],
               'ingredient_quality_data': {'ingredients': [row], 'ingredients_scorable': [row]}}
    entry = {**reviewed_entries()['INGR_BACOPA'], 'ingredient': name,
             'matched_canonical_ids': ['bacopa'], 'matched_source_row_refs': ['ingredientRows[0]']}
    result = assess_clinical_applicability(product, entry, assess_amount=False,
                                         require_claim_alignment=True)
    assert result['status'] == 'applicable'
    assert result['claim_alignment']['state'] == 'aligned'


def _entry(refs, **extra):
    return {"id": "INGR_AUDIT_MATERIAL", "standard_name": "Audit Material",
            "study_type": "rct_single", "evidence_level": "ingredient-human",
            "effect_direction": "positive_strong", "total_enrollment": 100,
            "references_structured": refs, **extra}


def _install_audit_source(monkeypatch, entry):
    """Make provenance explicit; source holds still override this synthetic approval."""
    import clinical_applicability as ca
    from test_evidence_resolver import _approved_test_source
    contexts = [_approved_test_source(entry, name="Audit Material", pmid=ref["pmid"])["study_contexts"][0]
                for ref in entry["references_structured"]]
    source = {**entry, "study_contexts": contexts}
    records = {**ca.reviewed_entries(), source["id"]: source}
    monkeypatch.setattr(ca, "reviewed_entries", lambda: records)
    monkeypatch.setattr(er, "_backed_studies_index", lambda: {"audit_material": [source]})
    return source


def _product(entry):
    rows = [{"name": "Audit Material", "standard_name": "Audit Material",
             "canonical_id": "audit_material", "mapped": True, "quantity": 100,
             "unit": "mg", "bio_score": 10, "raw_source_path": "ingredientRows[0]"}]
    return {"status": "active", "form_factor": "capsule",
            "supplement_type": {"type": "single_nutrient"},
            "ingredient_quality_data": {"ingredients": rows, "ingredients_scorable": rows},
            "evidence_data": {"clinical_matches": [{**entry,
                "matched_source_row_refs": ["ingredientRows[0]"],
                "matched_canonical_ids": ["audit_material"], "ingredient": "Audit Material"}]}}


@pytest.mark.parametrize("ref", [
    {"pmid": "41573009", "retracted": True},
    {"pmid": "41573009", "expression_of_concern": True},
    {"pmid": "41573009", "scoring_eligible": False},
])
def test_held_source_cannot_award_raw_points_or_public_primary_floor(monkeypatch, ref):
    entry = _install_audit_source(monkeypatch, _entry([ref]))
    assert score_evidence(_product(entry), apply_primary_floor=True)["score"] == 0
    assert build_scored_artifact(_product(entry))["quality_pillars_v4"]["evidence"]["score"] == 0
    control = _product(_install_audit_source(monkeypatch, _entry([{"pmid": "28661438", "retracted": False}])))
    assert score_evidence(control, apply_primary_floor=True)["score"] > 0


def test_mixed_record_retains_independently_eligible_source(monkeypatch):
    entry = _install_audit_source(monkeypatch, _entry([{"pmid": "41573009", "retracted": True},
                    {"pmid": "28661438", "retracted": False}]))
    assert score_evidence(_product(entry), apply_primary_floor=True)["score"] > 0


@pytest.mark.parametrize("entry", [
    _entry([{"pmid": "41573009", "retracted": True}]),
    _entry([{"pmid": "28661438"}], study_type="reference"),
    _entry([{"pmid": "28661438"}], scoring_eligible=False),
])
def test_no_eligible_backed_record_does_not_resolve_as_reviewed_benefit(monkeypatch, entry):
    monkeypatch.setattr(er, "_backed_studies_index", lambda: {"audit_material": [copy.deepcopy(entry)]})
    result = er.resolve_evidence_for_canonical("audit_material", name="Audit Material")
    assert result.points_eligible is False
    assert result.applicability_status != "applicable_reviewed_trials"



def test_undecylenic_reference_cannot_resolve_oral_human_efficacy():
    import json
    from clinical_applicability import assess_clinical_applicability
    from scoring_v4.modules.generic_evidence import _is_verified_ingredient_human_entry
    data = json.loads((Path(__file__).resolve().parents[1] / "data" / "backed_clinical_studies.json").read_text())
    entry = next(r for r in data["backed_clinical_studies"] if r["id"] == "ING_UNDECYLENIC_ACID")
    assert entry["study_type"] == "reference"
    assert entry["evidence_level"] == "reference"
    assert entry["effect_direction"] == "positive_strong"  # descriptive preclinical effect retained
    assert entry["total_enrollment"] is None
    assert entry["registry_completed_trials_count"] is None
    assert entry["endpoint_relevance_tags"] == []
    assert entry["published_studies"] == ["10991877"]
    assert not er.clinical_record_sources_eligible(entry)
    assert not _is_verified_ingredient_human_entry(entry)
    resolution = er.resolve_evidence_for_canonical("undecylenic_acid", name="Undecylenic Acid")
    assert resolution.points_eligible is False
    assert resolution.blocking_reasons == ["literature_applicability_unestablished"]
    assert resolution.disposition == "research_present_applicability_unestablished"
    row = {"name": "Undecylenic Acid", "canonical_id": "undecylenic_acid", "quantity": 250, "unit": "mg", "raw_source_path": "ingredientRows[0]"}
    product = {"form_factor_canonical": "capsule", "activeIngredients": [row], "ingredient_quality_data": {"ingredients": [row], "ingredients_scorable": [row]}}
    stale = {**entry, "evidence_level": "ingredient-human", "total_enrollment": 20, "registry_completed_trials_count": 7}
    assert assess_clinical_applicability(product, stale, assess_amount=False)["reason_code"] == "reference_only_clinical_record"


@pytest.mark.parametrize("metadata", [
    {"evidence_level": "preclinical", "study_type": "animal_study"},
    {"evidence_level": "product-human", "study_type": "in_vitro"},
])
def test_brand_identifier_never_overrides_explicit_nonhuman_sources(metadata):
    from scoring_v4.modules.generic_evidence import _is_verified_product_level_entry
    entry = _entry([{"pmid": "22556508"}], id="BRAND_AUDIT_MATERIAL", **metadata)
    assert not _is_verified_product_level_entry(entry)
    control = _entry([{"pmid": "28661438"}], id="BRAND_AUDIT_MATERIAL", evidence_level="product-human")
    assert _is_verified_product_level_entry(control)


def test_backed_records_do_not_transfer_generic_or_combination_or_protocol_results():
    import json
    data = json.loads((Path(__file__).resolve().parents[1] / "data" / "backed_clinical_studies.json").read_text())
    records = {r["id"]: r for r in data["backed_clinical_studies"]}
    for key in ["BRAND_ZYLOFRESH", "PRECLIN_AKG", "PRECLIN_APIGENIN", "PRECLIN_LUTEOLIN"]:
        entry = records[key]
        assert entry["evidence_level"] == "reference"
        assert entry["total_enrollment"] is None
        assert entry["effect_direction"] == "positive_weak"
        assert not er.clinical_record_sources_eligible(entry)
    assert records["BRAND_ZYLOFRESH"]["study_type"] == "reference"
    assert records["PRECLIN_AKG"]["study_type"] == "reference"
    assert records["PRECLIN_APIGENIN"]["published_studies"] == ["19593179"]
    assert records["PRECLIN_LUTEOLIN"]["published_studies"] == ["35450527"]
    fisetin = records["PRECLIN_FISETIN"]
    assert fisetin["study_type"] == "reference"
    assert not er.clinical_record_sources_eligible(fisetin)
    assert fisetin["total_enrollment"] == 10
    assert fisetin["registry_completed_trials_count"] is None
    assert fisetin["effect_direction"] == "mixed"
    assert fisetin["published_studies"] == ["39269340"]
    assert "uncontrolled" in fisetin["notable_studies"]


@pytest.mark.parametrize("key,source,topic", [
    ("BRAND_ZYLOFRESH", "22556508", "rabbits"),
    ("PRECLIN_AKG", "37217632", "protocol"),
    ("PRECLIN_APIGENIN", "19593179", "chamomile"),
    ("PRECLIN_LUTEOLIN", "35450527", "olfactory training"),
    ("ING_UNDECYLENIC_ACID", "10991877", "Candida"),
])
def test_reference_hold_withholds_benefit_chips_and_preserves_source_context(key, source, topic):
    import json
    data = json.loads((Path(__file__).resolve().parents[1] / "data" / "backed_clinical_studies.json").read_text())
    entry = next(r for r in data["backed_clinical_studies"] if r["id"] == key)
    assert entry["key_endpoints"] == []
    assert entry["health_goals_supported"] == []
    assert entry["primary_outcome"] == ""
    assert entry["scoring_eligible"] is False
    assert source in entry["effect_direction_rationale"]
    assert topic in entry["effect_direction_rationale"]


@pytest.fixture(scope='module')
def completion_source_records():
    import json
    return {x['id']: x for x in json.loads((Path(__file__).resolve().parents[1] / 'data' / 'backed_clinical_studies.json').read_text())['backed_clinical_studies']}


@pytest.mark.parametrize('rid,wrong', [
    ('INGR_SEA_BUCKTHORN', '101 women'), ('INGR_BILBERRY', '320mg/day'),
    ('INGR_BLACK_SEED_OIL', '12 months'), ('INGR_CERAMIDES', 'Meta-analysis of 66 RCTs confirmed oral ceramide'),
    ('INGR_MAG_GLYCINATE', 'sleep quality ↑'), ('INGR_CINNAMON_EXTRACT', 'HbA1c ↓'),
    ('PRECLIN_SPERMIDINE', 'lifespan ↑'), ('PRECLIN_DGL', 'ulcer healing ↑'),
    ('PRECLIN_QUERCETIN_PHYTOSOME', 'senolysis ↑'), ('PRECLIN_SAFFRON', 'retinal protection ↑'),
    ('BRAND_TESTOFEN', 'muscle strength ↑'), ('BRAND_KANEKA_UBIQUINOL', 'statin myopathy ↓'),
    ('PRECLIN_PTEROSTILBENE', 'cognition ↑'),
])
def test_completed_source_facts_remove_unrelated_benefit_endpoints(completion_source_records, rid, wrong):
    assert wrong not in ' '.join(completion_source_records[rid]['key_endpoints'])


@pytest.mark.parametrize('rid', ['INGR_SLIPPERY_ELM', 'INGR_MOLYBDENUM', 'INGR_PROPOLIS', 'INGR_VITAMIN_E'])
def test_no_generic_benefit_from_combination_topical_risk_or_pk_reference(completion_source_records, rid):
    r = completion_source_records[rid]
    assert r['study_type'] == 'reference'
    assert r['scoring_eligible'] is False
    assert r['key_endpoints'] == []
    assert r['health_goals_supported'] == []
    assert not er.clinical_record_sources_eligible(r)


def test_source_hierarchy_and_trial_family_counts_remain_explicit(completion_source_records):
    r = completion_source_records
    assert '0.125' in r['INGR_BENFOTIAMINE']['notable_studies']
    assert 'alcohol consumption' in r['INGR_BENFOTIAMINE']['notable_studies']
    assert '100 randomized' in r['PRECLIN_SPERMIDINE']['notable_studies']
    assert '0.47 g' in ' '.join(r['INGR_BILBERRY']['key_endpoints'])
    assert '3 months' in ' '.join(r['INGR_BLACK_SEED_OIL']['key_endpoints'])
    assert r['PRECLIN_PTEROSTILBENE']['total_enrollment'] == 80
    assert r['INGR_CERAMIDES']['primary_outcome'] != 'Cardiovascular/Heart Health'


@pytest.mark.parametrize('rid,pmid,topic', [
 ('BRAND_SENSORIL','27647541','knee'),('BRAND_BCM95','30975196','open-label'),
 ('BRAND_PYCNOGENOL','18386255','osteoarthritis'),('BRAND_ASTAREAL','22428137','topical'),
 ('BRAND_CREAPURE','22971354','comparator'),('INGR_LACTOFERRIN','35276902','iron'),
 ('INGR_PHOSPHATIDYLSERINE','20523044','combination'),('BRAND_SUNTHEANINE','22214254','ADHD'),
 ('BRAND_OPTIMSM','37447322','knee'),('BRAND_LONGVIDA','25277322','mood'),
 ('BRAND_UCII','24153020','within-group'),('BRAND_NIAGEN','29992272','NAD'),
 ('BRAND_RELORA','23924268','cortisol'),('INGR_SELENIUM','38243784','thyroid'),
 ('INGR_QUERCETIN','27405810','pressure'),('INGR_COQ10','25282031','heart failure'),
 ('INGR_GINSENG','29624410','fatigue'),('INGR_FENUGREEK','32048383','testosterone'),
 ('INGR_DIGESTIVE_ENZYMES','37976892','combination'),('INGR_LEMON_BALM','34449930','anxiety'),
 ('INGR_RHODIOLA','41080184','endurance'),('INGR_ASTRAGALUS','37952511','markers'),
 ('INGR_BROMELAIN','37157782','topical'),('INGR_CHAMOMILE','39106912','sleep'),
 ('INGR_VITAMIN_B6','36719452','pregnancy'),('INGR_MAGNESIUM_GENERIC','26752497','route'),
 ('INGR_PSYLLIUM_HUSK','30239559','lipid'),('INGR_BEETROOT','33554654','nitrate'),
 ('PRECLIN_RESVERATROL','29305228','lipid'),
])
def test_retained_clinical_endpoint_scope_is_traceable_to_actual_source(completion_source_records,rid,pmid,topic):
    text = ' '.join(completion_source_records[rid]['key_endpoints'])
    assert pmid in text and topic.lower() in text.lower()


@pytest.mark.parametrize('rid,forbidden', [
 ('INGR_QUERCETIN','immune'),('BRAND_CREAPURE','cognitive_neurological'),
 ('INGR_MAGNESIUM_GENERIC','mood'),('PRECLIN_RESVERATROL','aging_longevity'),
 ('BRAND_NIAGEN','mitochondrial_energy'),('INGR_MAG_GLYCINATE','digestive'),
 ('PRECLIN_ASTAXANTHIN_GENERIC','cognitive_neurological'),
])
def test_source_exclusion_caveats_cannot_create_purpose_matches(completion_source_records,rid,forbidden):
    from clinical_applicability import qualifying_purpose_outcomes, assess_clinical_source_review
    record = completion_source_records[rid]
    if not record.get("study_contexts"):
        assert assess_clinical_source_review(record)["is_complete"] is False
        return
    # Descriptive caveats are not structured positive outcomes. Null outcomes
    # may still describe what was studied, but cannot earn benefit credit.
    for context in record.get("study_contexts") or []:
        before = qualifying_purpose_outcomes(context)
        caveat = {**context, "key_endpoints": [f"No evidence supports {forbidden}"]}
        assert qualifying_purpose_outcomes(caveat) == before


def test_source_reconciliations_rewrite_rationale_and_design(completion_source_records):
    for rid,stale in [('PRECLIN_SPERMIDINE','Retained positive_weak'),('INGR_BENFOTIAMINE','Retained positive_strong')]:
        assert stale not in completion_source_records[rid]['effect_direction_rationale']
    assert 'RCT' not in completion_source_records['INGR_SLIPPERY_ELM']['published_studies']


@pytest.mark.parametrize("rid", ['INGR_LACTOFERRIN', 'BRAND_NIAGEN', 'INGR_SELENIUM', 'INGR_MAG_GLYCINATE', 'INGR_QUERCETIN', 'INGR_FENUGREEK', 'PRECLIN_SPERMIDINE', 'PRECLIN_QUERCETIN_PHYTOSOME', 'PRECLIN_ASTAXANTHIN_GENERIC', 'PRECLIN_PTEROSTILBENE', 'BRAND_TESTOFEN', 'INGR_VITAMIN_B6', 'INGR_ASTRAGALUS', 'INGR_BROMELAIN', 'INGR_BEETROOT', 'INGR_BENFOTIAMINE', 'INGR_BLACK_SEED_OIL', 'INGR_SEA_BUCKTHORN', 'INGR_BILBERRY'])
def test_unrepresentable_outcome_uses_existing_optional_field_contract(completion_source_records, rid):
    record = completion_source_records[rid]
    assert "primary_outcome" not in record
    assert record["key_endpoints"]
    assert record["references_structured"]


def test_magtein_trial_and_correction_have_distinct_source_roles():
    import json
    records = json.loads((Path(__file__).parents[1] / 'data/backed_clinical_studies.json').read_text())['backed_clinical_studies']
    row = next(r for r in records if r['id'] == 'BRAND_MAGTEIN')
    refs = {r.get('pmid'): r for r in row['references_structured']}
    assert '39252819' in refs  # Original 21-day trial, not its correction notice.
    assert refs['40567408']['scoring_eligible'] is False
    text = row['notes'] + row['notable_studies']
    assert 'phosphatidylserine' in text and 'objective sleep outcomes' in text
    assert 'must not be counted as another trial' in text
    assert 'vitamin B6' in text
    assert 'retrospectively registered on April 15, 2024' in text
    assert 'AIDP commissioned and funded' in text
    assert 'paid relationships' in text
    for stale in ('correction content still requires verification',
                  'Full correction content remains unverified',
                  'requires content review'):
        assert stale not in str(row)
    from clinical_applicability import assess_clinical_source_review
    review = assess_clinical_source_review(row)
    assert review['is_complete'] is True
    assert set(review['context_ids']) == {'magtein_39252819', 'magtein_41601871'}
    assert refs['36558392']['scoring_eligible'] is False  # Whole formula cannot replicate isolated material.
    contexts = row['study_contexts']
    assert next(c for c in contexts if '40567408' in c['source_pmids'])['source_pmids'] == ['39252819', '40567408']
    assert next(c for c in contexts if c['source_pmids'] == ['36558392'])['scoring_eligible'] is False


# Dr. Pham, 2026-10-28: Mitopure (hierarchy kept) and sulforaphane are
# completed qualified zeros on the reference path; Lutemax 2020 is closed with
# eye-outcome credit for the exact formula; the collagen hold stands.
@pytest.mark.parametrize('record_id,required,complete,reference_only', [
    ('BRAND_MITOPURE', ['primary endpoint', 'within-group', '0.058'], True, True),
    ('BRAND_LUTEMAX_2020', ['EyePromise', 'omega-3', 'mesozeaxanthin'], True, False),
    ('PRECLIN_SULFORAPHANE', ['did not meet', '0.3 mmol/L', 'exploratory'], True, True),
    ('INGR_COLLAGEN_PEPTIDES', ['non-pharmaceutical-funded', 'high-quality', 'high risk of bias'], False, False),
])
def test_source_summaries_keep_null_endpoints_and_preparation_limits(record_id, required, complete, reference_only):
    import json
    from clinical_applicability import assess_clinical_source_review
    records = json.loads((Path(__file__).parents[1] / 'data/backed_clinical_studies.json').read_text())['backed_clinical_studies']
    row = next(r for r in records if r['id'] == record_id)
    text = row['notes'] + row['notable_studies']
    assert all(fragment in text for fragment in required)
    assert assess_clinical_source_review(row)['is_complete'] is complete
    assert (row['study_type'] == row['evidence_level'] == 'reference') is reference_only
    if record_id == 'BRAND_LUTEMAX_2020':
        # Credit is the exact Lutemax 2020 trial only, scoped to eye outcomes;
        # the EyePromise combination is not Lutemax and carries none.
        assert row['applicability']['source_pmids'] == ['28661438']
        assert row['applicability']['supported_outcomes'] == ['Eye & Vision']
        eligible = [c['source_pmids'] for c in row['study_contexts'] if c.get('scoring_eligible') is True]
        assert eligible == [['28661438']]


def test_berberine_registered_dose_conflict_is_not_a_single_daily_regimen():
    import json
    records = json.loads((Path(__file__).parents[1] / 'data/backed_clinical_studies.json').read_text())['backed_clinical_studies']
    row = next(r for r in records if r['id'] == 'INGR_BERBERINE')
    text = row['notes'] + row['notable_studies']
    assert '300mg daily' in text and '300mg twice daily' in text
    assert 'conflict' in text and 'multi-ingredient' in text
    assert 'not standalone' in text


def test_st_johns_wort_ssri_comparator_is_not_relabelled_placebo():
    import json
    records = json.loads((Path(__file__).parents[1] / 'data/backed_clinical_studies.json').read_text())['backed_clinical_studies']
    row = next(r for r in records if r['id'] == 'INGR_ST_JOHNS_WORT')
    assert 'comparing St John\'s wort with SSRIs' in row['notable_studies']
    assert 'did not establish placebo superiority' in row['notable_studies']
    assert row['notes'] == 'Consistent evidence for mild-to-moderate depression contexts, but clinically significant CYP/P-gp drug interaction risk requires caution.'


@pytest.mark.parametrize('record_id,unsupported', [
    ('INGR_RHODIOLA', 'evidence supports Rhodiola rosea for stress-related fatigue'),
    ('INGR_GINSENG', 'supportive data for selected cognitive'),
    ('INGR_LEMON_BALM', 'additional cognitive findings in small trials'),
])
def test_source_scope_corrections_remove_contradictory_opening_claims(record_id, unsupported):
    import json
    rows = json.loads((Path(__file__).parents[1] / 'data/backed_clinical_studies.json').read_text())['backed_clinical_studies']
    row = next(r for r in rows if r['id'] == record_id)
    assert unsupported not in row['notes']
    assert 'not' in row['notes'] or 'unreviewed' in row['notes']


def test_hyaluronic_retained_skin_sources_do_not_award_joint_or_longevity_scope():
    import json
    rows = json.loads((Path(__file__).parents[1] / 'data/backed_clinical_studies.json').read_text())['backed_clinical_studies']
    row = next(r for r in rows if r['id'] == 'INGR_HYALURONIC_ACID')
    assert row['health_goals_supported'] == ['Skin, Hair & Nails']
    assert row['primary_outcome'] == 'Skin, Hair & Nails'
    assert row['endpoint_relevance_tags'] == ['skin_health']
    assert not any('joint' in endpoint.lower() for endpoint in row['key_endpoints'])
    assert 'no joint research exists elsewhere' in row['notes']
    assert 'registry_completed_trials_count' not in row


def test_hn019_author_comment_access_keeps_combination_and_method_limits():
    import json
    rows = json.loads((Path(__file__).parents[1] / 'data/clinically_relevant_strains.json').read_text())['clinically_relevant_strains']
    row = next(r for r in rows if r['id'] == 'STRAIN_LACTIS_HN019')
    context = next(c for c in row['study_contexts'] if '40085083' in c['source_pmids'])
    text = ' '.join(context['limitations'])
    assert 'Comment details remain unresolved' not in text
    for fact in ('April 15, 2025', '58%', 'antipyretic', 'pre-enrollment', 'eTables 4 and 5'):
        assert fact in text
    assert 'not an independent or individual-strain result' in text
    assert context['trial_family'] == 'milan_pediatric_urti_probiotic_40085083'
    assert len(context['dose']['component_doses']) == 3
    assert context['clinical_review']['reviewed_at'] == '2026-09-14T22:23:43Z'


def test_pureway_human_pk_citation_names_actual_pubmed_authors():
    """PMID 18971870 is Pancorbo et al.; the cell source stays distinct."""
    import json

    data = json.loads((Path(__file__).resolve().parents[1] / "data" / "backed_clinical_studies.json").read_text())
    record = next(row for row in data["backed_clinical_studies"] if row["id"] == "BRAND_PUREWAY_C")
    citation = record["notable_studies"]
    assert "Pancorbo et al. (2008, PMID 18971870)" in citation
    assert "Moyad" not in citation
    assert "mechanistic" in citation and "cellular" in citation
    assert "PMID 17901843" in citation
    assert "clinical endpoint data remain limited" in citation


def test_returned_nmn_review_keeps_primary_null_and_secondary_scope(completion_source_records):
    from clinical_applicability import assess_clinical_source_review
    row = completion_source_records['PRECLIN_NMN']
    assert row['study_type'] == 'reference'
    assert not er.clinical_record_sources_eligible(row)
    assert row['health_goals_supported'] == []
    context = next(c for c in row['study_contexts'] if c['source_pmids'] == ['35215405'])
    assert [o['hierarchy'] for o in context['outcomes']] == ['primary', 'primary', 'secondary']
    assert context['dose']['values'] == [250]
    assert context['dose']['duration_days'] == 84
    assert context['outcomes'][0]['direction'] == 'null'
    assert assess_clinical_source_review(row)['is_complete'] is True


def test_returned_magnesium_review_preserves_elemental_basis_and_mixed_label_limit(completion_source_records):
    from clinical_applicability import assess_clinical_source_review
    row = completion_source_records['INGR_MAG_GLYCINATE']
    assert row['external_ids']['unii'] == 'IFN18A4Y6B'
    assert not er.clinical_record_sources_eligible(row)
    contexts = {c['source_pmids'][0]: c for c in row['study_contexts']}
    assert contexts['22909270']['dose']['values'] == [300]
    assert contexts['40918053']['dose']['values'] == [250]
    assert 'glycine' in str(contexts['40918053']).lower()
    assert contexts['40918053']['outcomes'][1]['direction'] == 'null'
    assert assess_clinical_source_review(row)['is_complete'] is True


def test_pqq_unread_corrected_table_and_combination_do_not_supply_credit(completion_source_records):
    row = completion_source_records['PRECLIN_PQQ']
    assert row['scoring_eligible'] is False
    assert not er.clinical_record_sources_eligible(row)
    assert row['health_goals_supported'] == []
    assert row['total_enrollment'] is None
    assert '35917215' in row['notes']
    assert 'combination' in row['notes'].lower()
    assert {r['pmid'] for r in row['references_structured']} >= {'34415830', '38908296'}


def test_flax_active_sources_exclude_unread_corrected_review_without_losing_history():
    import json
    data = json.loads((Path(__file__).parents[1] / 'data/literature_evidence_records.json').read_text())
    row = next(r for r in data['literature_evidence_records'] if r['canonical_id'] == 'flaxseed')
    assert {r['pmid'] for r in row['qualifying_human_studies']} == {'24126178', '26071633'}
    assert row['verification_result'] == 'authoritative_pubmed_verified'
    assert row['verification_provenance']['all_pmids_verified'] is True
    assert '25740909' in row['notes'] and '26525908' in row['notes']
    assert 'oil' in row['applicability']['excluded_form_terms']
    assert row['reference_semantics']['curve'] == 'completed_no_benchmark_neutral'
    assert 'min_effective_dose' not in row


@pytest.mark.parametrize('rid,source', [('INGR_RHODIOLA','15256690')])
def test_limited_positive_review_cannot_become_unscoped_current_product_credit(completion_source_records,rid,source):
    row = completion_source_records[rid]
    # Dr. Pham, 2026-10-28: the record hold is lifted for endurance-only credit
    # from the current review; the older limited review stays non-crediting.
    assert row['scoring_eligible'] is True
    assert row['applicability']['supported_outcomes'] == ['endurance']
    assert {'energy', 'mood', 'anti-inflammatory'} <= set(row['applicability']['excluded_claim_terms'])
    assert source not in row['applicability']['source_pmids']
    assert row['total_enrollment'] is None
    assert row['registry_completed_trials_count'] is None
    assert row['health_goals_supported'] == []
    ref = next(r for r in row['references_structured'] if r.get('pmid') == source)
    assert not er.clinical_record_sources_eligible({'references_structured': [ref]})
    limited = [c for c in row['study_contexts'] if source in c['source_pmids']]
    assert limited and all(c['scoring_eligible'] is False for c in limited)  # Retained, not declared ineffective.


def test_recovered_bc30_methods_retain_null_domains_and_trial_family(completion_source_records):
    from clinical_applicability import assess_clinical_source_review
    row = completion_source_records['STRAIN_BC30']
    context = next(c for c in row['study_contexts'] if '40707016' in c['source_pmids'])
    assert not any(o['hierarchy'] == 'unresolved' for o in context['outcomes'])
    assert any(o['direction'] == 'null' for o in context['outcomes'])
    assert context['dose']['duration_days'] == 28
    assert assess_clinical_source_review(row)['is_complete'] is True


def test_recovered_poolzyme_methods_do_not_clear_source_acceptance_hold(completion_source_records):
    from clinical_applicability import assess_clinical_source_review
    row = completion_source_records['INGR_DIGESTIVE_ENZYMES']
    # Dr. Pham, 2026-10-28: exact-brand credit needs the study material and its
    # activities identified; "Poolzyme Multi" is unverified. The unverified
    # draft context lives in the audit receipt, not production data, so the
    # record-level hold remains the only state and the review stays open.
    assert row['scoring_eligible'] is False
    assert not er.clinical_record_sources_eligible(row)
    assert '37976892' in {r['pmid'] for r in row['references_structured']}
    assert not any('37976892' in c['source_pmids'] for c in row.get('study_contexts', []))
    review = assess_clinical_source_review(row)
    assert review['is_complete'] is False
    assert 'clinical_source_contexts_missing' in review['errors']


@pytest.mark.parametrize('rid', ['BRAND_QUATREFOLIC','PRECLIN_PTEROSTILBENE','PRECLIN_SPERMIDINE','INGR_PHOSPHATIDYLSERINE','INGR_SAW_PALMETTO','STRAIN_HN019'])
def test_returned_reference_findings_complete_without_affirmative_credit(completion_source_records,rid):
    from clinical_applicability import assess_clinical_source_review
    from probiotic_measurements import context_accepted_for_scoring
    row = completion_source_records[rid]
    assert row['study_type'] == 'reference'
    assert assess_clinical_source_review(row)['is_complete'] is True
    assert not er.clinical_record_sources_eligible(row)
    for context in row['study_contexts']:
        if context.get('scoring_eligible') is False:
            assert not context_accepted_for_scoring(context)
    if rid == 'PRECLIN_SPERMIDINE':
        context = row['study_contexts'][0]
        assert context['dose']['duration_days'] is None
        assert context['dose']['duration_as_printed'] == {'value':12, 'unit':'months'}


def test_bc30_revised_source_context_links_returned_scope_not_old_engineering_approval():
    import json
    data = json.loads((Path(__file__).parents[1] / 'data/clinically_relevant_strains.json').read_text())
    row = next(r for r in data['clinically_relevant_strains'] if r['id'] == 'STRAIN_COAGULANS_GBI30')
    context = next(c for c in row['study_contexts'] if c['context_id'] == 'bc30_functional_gi_complaints_40707016')
    assert context['clinical_review']['reviewer'] == 'Dr. Pham'
    assert context['clinical_review']['reviewed_at'] == '2026-10-26'
    assert 'A144' in context['clinical_review']['basis']
    assert '2026-09-14' in context['notes']


def test_signed_isolated_lutein_transfer_rejections_are_completed_without_affirmative_credit(completion_source_records):
    from clinical_applicability import assess_clinical_source_review
    record = completion_source_records['INGR_LUTEIN']
    assert record['study_type'] == 'reference'
    assert record['evidence_level'] == 'reference'
    assert assess_clinical_source_review(record)['is_complete'] is True
    assert not er.clinical_record_sources_eligible(record)
    assert all(context['review_status'] == 'rejected_source' and context['scoring_eligible'] is False
               for context in record['study_contexts'])
    assert any(ref.get('pmid') == '41573009' and ref.get('retracted') is True
               for ref in record['references_structured'])
    assert completion_source_records['BRAND_LUTEMAX_2020']['study_type'] != 'reference'


def test_signed_riboflavin_source_closes_only_after_existing_purpose_scope_is_enforced(completion_source_records):
    from clinical_applicability import assess_clinical_source_review, assess_clinical_applicability
    record = completion_source_records['INGR_RIBOFLAVIN_B2']
    assert record.get('scoring_eligible') is not False
    assert assess_clinical_source_review(record)['is_complete'] is True
    row = {'name': 'Riboflavin', 'canonical_id': 'riboflavin', 'quantity': 400, 'unit': 'mg',
           'raw_source_path': 'ingredientRows[0]', 'mapped': True, 'score_eligible_by_cleaner': True}
    match = {'id': record['id'], 'ingredient': row['name'], 'matched_source_row_refs': ['ingredientRows[0]']}
    # An unrelated cognitive claim cannot borrow the migraine scope (October 28 rulings).
    for claim, expected in [('Migraine support', 'applicable'), ('Cognitive performance', 'not_applicable')]:
        product = {'product_name': claim, 'ingredient_quality_data': {'ingredients_scorable': [row]}}
        assert assess_clinical_applicability(product, match, assess_amount=False)['status'] == expected
    assert record['health_goals_supported'] == []


def test_theracurmin_reported_hierarchy_limit_does_not_invent_primary_credit(completion_source_records):
    from clinical_evidence_schema import validate_ingredient_context
    contexts = completion_source_records['BRAND_THERACURMIN']['study_contexts']
    selected = [context for context in contexts if context['context_id'] in {
        'theracurmin_knee_oa_25308211', 'theracurmin_post_mosaicplasty_35494290'}]
    assert len(selected) == 2
    for context in selected:
        assert context['review_status'] == 'clinician_approved'
        assert context['scoring_eligible'] is False
        assert not validate_ingredient_context(context, require_complete_review=True)
        assert not any(outcome['hierarchy'] in {'primary', 'unresolved'} for outcome in context['outcomes'])
    # The memory acceptance (29246725) is still outstanding: no approved (or
    # any) production context may exist for it, and the record stays held.
    assert not any('29246725' in context['source_pmids'] for context in contexts)
    assert completion_source_records['BRAND_THERACURMIN']['scoring_eligible'] is False


@pytest.mark.parametrize('rid,pmid', [('PRECLIN_CORDYCEPS','27408987'),
    ('INGR_ECHINACEA','24554461'), ('INGR_CHONDROITIN_SULFATE','25629804')])
def test_retrieved_full_reports_have_factual_contexts_without_invented_approval(completion_source_records, rid, pmid):
    from clinical_evidence_schema import validate_ingredient_context
    record = completion_source_records[rid]
    context = next((c for c in record.get('study_contexts', []) if pmid in c['source_pmids']), None)
    assert context is not None
    assert context['scoring_eligible'] is False
    if rid == 'INGR_CHONDROITIN_SULFATE':
        # Dr. Pham, 2026-10-28 (third ruling set): one shared no-credit OA
        # standard for chondroitin and glucosamine; approval is a completed
        # no-credit decision with the existing human research retained.
        assert context['review_status'] == 'clinician_approved'
        assert context['clinical_review']['reviewer'] == 'Dr. Pham'
        assert context['clinical_review']['reviewed_at'] == '2026-10-28'
        assert validate_ingredient_context(context, require_complete_review=True) == []
        assert record['study_type'] == record['evidence_level'] == 'reference'
        assert any(note.startswith('The reviewed research does not establish a qualifying benefit')
                   for note in context['limitations'])
        assert any('ACR 2026' in note for note in context['limitations'])
    else:
        # Dr Pham approved these non-transfer conclusions on 2026-10-28
        # (attested by Sean); approval does not make them scoring-eligible.
        assert context['review_status'] == 'clinician_approved'
        assert context['clinical_review']['reviewer'] == 'Dr. Pham'
        assert context['clinical_review']['reviewed_at'] == '2026-10-28'
        assert validate_ingredient_context(context, require_complete_review=True) == []
        assert any('cannot provide affirmative generic-ingredient credit' in note
                   for note in context['limitations'])
    if rid == 'PRECLIN_CORDYCEPS':
        assert context['identity_scope'] == 'combination'
        assert context['dose']['dose_status'] == 'combination_total_only'
        assert context['dose']['values'] == [4000]
        assert context['outcomes'][0]['direction'] == 'null'
    else:
        assert context['dose']['values'] == []
        assert context['dose']['dose_basis'] == 'not_applicable'
        assert context['included_study_pmids']
        if rid == 'INGR_CHONDROITIN_SULFATE':
            # The re-extracted context states the same limit in its own words.
            assert any('Pooled heterogeneous study regimens' in note
                       and 'not a validated efficacy minimum' in note
                       for note in context['limitations'])
        else:
            assert any('single aggregate regimen' in note for note in context['limitations'])


def test_generic_shilajit_source_review_finishes_without_borrowing_primavie_credit():
    from clinical_applicability import assess_clinical_source_review, reviewed_entries
    from clinical_evidence_schema import validate_ingredient_context
    from probiotic_measurements import context_accepted_for_scoring

    record = reviewed_entries()['PRECLIN_SHILAJIT_GENERIC']
    review = assess_clinical_source_review(record)
    assert review['is_complete'] is True, review['errors']
    assert record['study_type'] == record['evidence_level'] == 'reference'
    assert not er.clinical_record_sources_eligible(record)
    assert {pmid for context in record['study_contexts'] for pmid in context['source_pmids']} == {
        '20078516', '26395129'}
    for context in record['study_contexts']:
        assert context['components'] == ['PRECLIN_SHILAJIT_GENERIC']
        assert context['review_status'] == 'rejected_source'
        assert context['scoring_eligible'] is False
        assert validate_ingredient_context(context, require_complete_review=True) == []
        assert not context_accepted_for_scoring(context)
        assert 'Codex' in context['clinical_review']['reviewer']
        assert 'Dr. Pham' not in context['clinical_review']['reviewer']
    branded = reviewed_entries()['BRAND_PRIMAVIE_SHILAJIT']
    assert assess_clinical_source_review(branded)['is_complete'] is True
    assert any(context_accepted_for_scoring(context) for context in branded['study_contexts'])


def test_generic_shilajit_completed_source_exclusion_reaches_scored_readiness():
    row = {'name': 'Shilajit', 'standard_name': 'Shilajit', 'canonical_id': 'shilajit',
           'mapped': True, 'quantity': 500, 'unit': 'mg', 'bio_score': 10,
           'raw_source_path': 'ingredientRows[0]'}
    product = {'status': 'active', 'form_factor': 'capsule',
               'supplement_type': {'type': 'single_nutrient'},
               'activeIngredients': [row],
               'ingredient_quality_data': {'ingredients': [row], 'ingredients_scorable': [row]}}
    artifact = build_scored_artifact(product)
    assessment = artifact['assessment_readiness']['evidence']
    assert assessment['readiness'] == 'complete', assessment
    assert artifact['quality_pillars_v4']['evidence']['score'] == 0
    assert assessment['not_yet_evaluated_count'] == 0


@pytest.mark.parametrize('missing_pmid', ['20078516', '26395129'])
def test_generic_shilajit_review_cannot_finish_with_an_unread_sibling(monkeypatch, missing_pmid):
    import clinical_applicability as ca
    records = copy.deepcopy(ca.reviewed_entries())
    record = records['PRECLIN_SHILAJIT_GENERIC']
    record['study_contexts'] = [context for context in record['study_contexts']
                                if missing_pmid not in context['source_pmids']]
    monkeypatch.setattr(ca, 'reviewed_entries', lambda: records)
    result = ca.assess_clinical_source_review(record)
    assert result['is_complete'] is False
    assert 'clinical_source_rejection_coverage_incomplete' in result['errors']
    # Finishing the generic preparation question cannot complete other research.
    assert ca.assess_clinical_source_review(records['INGR_UBIQUINOL'])['is_complete'] is False


def test_elderberry_completed_synthesis_review_does_not_invent_generic_credit():
    from clinical_applicability import assess_clinical_source_review, reviewed_entries
    from clinical_evidence_schema import validate_ingredient_context
    record = reviewed_entries()['INGR_ELDERBERRY']
    contexts = {c['context_id']: c for c in record['study_contexts']}
    reviewed = contexts.get('ingr_elderberry_30670267_reviewed_synthesis')
    assert reviewed is not None
    assert reviewed['review_status'] == 'clinician_approved'  # compatibility enum; agent review
    assert reviewed['scoring_eligible'] is False
    assert validate_ingredient_context(reviewed, require_complete_review=True) == []
    assert 'Codex' in reviewed['clinical_review']['reviewer']
    assert record['effect_direction'] == 'mixed'
    assert record['endpoint_relevance_tags'] == []
    assert 'immune response ↑' not in record['key_endpoints']
    assert record['health_goals_supported'] == ['Immune Support']
    assert contexts['ingr_elderberry_33827515_scoped_source']['clinical_review']['reviewer'] == 'Dr. Pham'
    assert not er.clinical_record_sources_eligible(record)
    assert assess_clinical_source_review(record)['is_complete']
    assert reviewed['trial_family'] == 'elderberry_respiratory_trials_1995_2016'
    assert reviewed['dose']['values'] == []
    assert '176' in reviewed['population']['description'] and '180' in reviewed['population']['description']
    assert 'Cochrane/GRADE review' not in ' '.join(reviewed['limitations'])


def test_taurine_bounded_transfer_preserves_integrity_without_inferred_longevity_or_pool_contamination():
    from clinical_applicability import assess_clinical_source_review, reviewed_entries
    record = reviewed_entries()['INGR_TAURINE']
    text = record['notes'] + ' ' + record['notable_studies']
    assert '28118062' in text and '41943494' in text
    assert '2026-04-06' in text
    assert 'not contribution to any particular pooled estimate' in text
    assert 'Healthy Aging/Longevity' not in record['health_goals_supported']
    assert not {'focus_memory', 'digestive_health'} & set(record['endpoint_relevance_tags'])
    assert record['effect_direction'] == 'positive_weak'
    contexts = {p: c for c in record['study_contexts'] for p in c['source_pmids']}
    assert assess_clinical_source_review(record)['is_complete']
    assert set(contexts) == {'26781281', '32871172', '41275513', '39148075'}
    assert {ref['pmid'] for ref in record['references_structured']} == set(contexts)
    assert [p for p, c in contexts.items() if c['scoring_eligible']] == ['26781281']
    for pmid in ['32871172', '41275513', '39148075']:
        assert contexts[pmid]['review_status'] == 'rejected_source'
        assert contexts[pmid]['scoring_eligible'] is False
    assert er.resolve_evidence_for_canonical('taurine', name='Taurine').points_eligible



def _glutamine_scoring_product(name='L-Glutamine', claim='', amount=500):
    row = {'name': name, 'raw_source_text': name, 'standard_name': 'L-Glutamine',
           'canonical_id': 'l_glutamine', 'mapped': True, 'bio_score': 11,
           'matched_form': 'l-glutamine powder' if name == 'L-Glutamine' else name,
           'quantity': amount, 'unit': 'mg', 'raw_source_path': 'ingredientRows[0]'}
    return {'product_name': claim or name, 'status': 'active', 'form_factor': 'capsule',
            'activeIngredients': [row],
            'ingredient_quality_data': {'ingredients': [row], 'ingredients_scorable': [row]}}


def _tyrosine_scoring_product(name='L-Tyrosine', claim=''):
    row = {'name': name, 'raw_source_text': name, 'standard_name': 'L-Tyrosine',
           'canonical_id': 'l_tyrosine', 'mapped': True, 'bio_score': 10,
           'matched_form': 'l-tyrosine', 'quantity': 500, 'unit': 'mg',
           'raw_source_path': 'ingredientRows[0]'}
    return {'product_name': claim or name, 'status': 'active', 'form_factor': 'capsule',
            'activeIngredients': [row],
            'ingredient_quality_data': {'ingredients': [row], 'ingredients_scorable': [row]}}


@pytest.mark.parametrize('claim', ['', 'L-Tyrosine Mood Support', 'L-Tyrosine Muscle Recovery'])
def test_tyrosine_acute_research_credit_keeps_unfinished_sources_open(claim):
    from clinical_applicability import reviewed_entries, assess_clinical_source_review
    from dose_assessment import positive_clinical_benchmark
    record = reviewed_entries().get('INGR_L_TYROSINE')
    assert record is not None
    assert record['study_type'] == 'rct_multiple' and record['effect_direction'] == 'mixed'
    assert record['published_studies_count'] == 3
    assert 'total_enrollment' not in record  # Never sum independent trials into a largest-trial field.
    assert {p for c in record['study_contexts'] for p in c['source_pmids']} == {
        '24433977', '25598314', '36548401', '39820592', '29980424', '38290812',
        '26424423', '10230711', '42275440',
    }
    assert not assess_clinical_source_review(record)['is_complete']
    context = next(c for c in record['study_contexts'] if c['source_pmids'] == ['24433977'])
    assert context['scoring_eligible'] is True
    assert context['source_pmids'] == ['24433977']
    assert context['dose']['values'] == [2000]
    assert {o['direction'] for o in context['outcomes']} == {'positive', 'null'}
    assert all(o['hierarchy'] == 'not_reported' for o in context['outcomes'])
    assert 'min_clinical_dose' not in record
    product = _tyrosine_scoring_product(claim=claim)
    assert positive_clinical_benchmark(product, product['activeIngredients'][0]) is None
    artifact = build_scored_artifact(product)
    assert artifact['quality_pillars_v4']['evidence']['score'] > 0
    assert artifact['quality_assessment_status'] == 'partial'
    result = score_evidence(product)
    receipt = next(r for r in result['metadata']['contributing_record_assessments']
                   if r['id'] == 'INGR_L_TYROSINE')
    assert {str(r['pmid']) for r in receipt['source_references']} == {'24433977', '25598314', '36548401', '42275440'}
    assert receipt['source_review']['is_complete'] is False


@pytest.mark.parametrize('name', ['Tyrosine', 'D-Tyrosine', 'DL-Tyrosine',
                                  'D,L-Tyrosine', 'N-Acetyl-L-Tyrosine', 'NALT'])
def test_tyrosine_derivatives_and_unspecified_stereochemistry_do_not_borrow_source(name):
    artifact = build_scored_artifact(_tyrosine_scoring_product(name=name))
    assert artifact['quality_pillars_v4']['evidence']['score'] == 0


@pytest.mark.parametrize('name', ['N-Acetyl L-Tyrosine', 'N-Acetyl Tyrosine', 'NALT'])
def test_free_tyrosine_pending_sources_cannot_reopen_finished_nalt_exclusion(name):
    product = _tyrosine_scoring_product(name=name)
    resolution = er.resolve_product_evidence(product)
    assert resolution.is_assessment_complete
    assert all(not r.points_eligible for r in resolution.resolutions)
    artifact = build_scored_artifact(product)
    assert artifact['quality_pillars_v4']['evidence']['score'] == 0
    assert artifact['assessment_readiness']['evidence']['readiness'] == 'complete'


@pytest.mark.parametrize('specific_owner', ['absent', 'unfinished'])
def test_tyrosine_denylist_alone_cannot_finish_unread_preparation(monkeypatch, specific_owner):
    from copy import deepcopy
    index = deepcopy(er._backed_studies_index())
    for key, studies in index.items():
        if specific_owner == 'absent':
            index[key] = [s for s in studies if s['id'] != 'INGR_N_ACETYL_L_TYROSINE']
        else:
            for study in studies:
                if study['id'] == 'INGR_N_ACETYL_L_TYROSINE':
                    study['study_contexts'] = [{'review_status': 'source_verified_pending_clinical_review'}]
    monkeypatch.setattr(er, '_backed_studies_index', lambda: index)
    result = er.resolve_product_evidence(_tyrosine_scoring_product(name='NALT'))
    assert not result.is_assessment_complete
    assert all(not row.points_eligible for row in result.resolutions)


def test_distinct_nalt_row_does_not_exclude_a_separate_free_tyrosine_source():
    from clinical_applicability import reviewed_entries
    from scoring_v4.modules.generic_evidence import _entry_excludes_recovery_context
    product = _tyrosine_scoring_product(claim='NALT and L-Tyrosine')
    free_row = product['activeIngredients'][0]
    derivative = {**free_row, 'name': 'N-Acetyl L-Tyrosine',
                  'raw_source_text': 'N-Acetyl L-Tyrosine', 'raw_source_path': 'ingredientRows[1]'}
    product['activeIngredients'].append(derivative)
    product['ingredient_quality_data']['ingredients'] = [free_row, derivative]
    product['ingredient_quality_data']['ingredients_scorable'] = [free_row, derivative]
    record = reviewed_entries()['INGR_L_TYROSINE']
    assert not _entry_excludes_recovery_context(record, free_row, product)
    assert _entry_excludes_recovery_context(record, derivative, product)
    assert score_evidence(product)['score'] > 0


def test_cadet_protein_drink_review_rejects_only_isolated_tyrosine_transfer():
    from clinical_applicability import reviewed_entries, assess_clinical_source_review
    from clinical_evidence_schema import validate_ingredient_context
    from probiotic_measurements import context_review_finished
    record = reviewed_entries()['INGR_L_TYROSINE']
    context = next(c for c in record['study_contexts'] if c['source_pmids'] == ['10230711'])
    assert context['review_status'] == 'rejected_source'
    assert context_review_finished(context)
    assert validate_ingredient_context(context, require_complete_review=True) == []
    assert context['scoring_eligible'] is False
    assert 'PROTIFAR' in ' '.join(context['limitations'])
    assert 'FANTOMALT' in ' '.join(context['limitations'])
    assert not assess_clinical_source_review(record)['is_complete']


def test_tyrosine_narrative_review_is_finished_without_becoming_independent_trial():
    from clinical_applicability import reviewed_entries, assess_clinical_source_review
    from probiotic_measurements import context_review_finished
    from clinical_evidence_schema import validate_ingredient_context
    record = reviewed_entries()['INGR_L_TYROSINE']
    context = next(c for c in record['study_contexts'] if c['source_pmids'] == ['26424423'])
    assert context['review_status'] == 'rejected_source'
    assert context['scoring_eligible'] is False
    assert context_review_finished(context)
    assert validate_ingredient_context(context, require_complete_review=True) == []
    assert record['published_studies_count'] == 3
    assert 'total_enrollment' not in record  # Never sum independent trials into a largest-trial field.
    assert {p for c in record['study_contexts'] if not context_review_finished(c)
            for p in c['source_pmids']} == {'29980424'}
    assert not assess_clinical_source_review(record)['is_complete']


def test_tyrosine_planned_long_interval_source_preserves_independence_limits():
    from clinical_applicability import reviewed_entries, qualifying_purpose_outcomes, _context_trial_families
    from clinical_evidence_schema import validate_ingredient_context
    record = reviewed_entries()['INGR_L_TYROSINE']
    contexts = {c['source_pmids'][0]: c for c in record['study_contexts']}
    context = contexts['25598314']
    assert context['scoring_eligible'] is True
    assert validate_ingredient_context(context, require_complete_review=True) == []
    outcomes, held = qualifying_purpose_outcomes(context)
    assert not held and len(outcomes) == 1
    assert '1200' in outcomes[0]['name']
    assert outcomes[0]['hierarchy'] == 'not_reported'
    assert context['population']['age_group'] == 'mixed'
    assert '17' in context['population']['description']
    assert {o['direction'] for o in context['outcomes']} >= {'positive', 'null'}
    assert contexts['24433977']['trial_family'] == context['trial_family']
    assert len(_context_trial_families([contexts[p] for p in ['24433977', '25598314', '36548401']])) == 2
    assert record['published_studies_count'] == 3
    assert 'total_enrollment' not in record and 'min_clinical_dose' not in record
    assert record['effect_direction'] == 'mixed'


def test_tyrosine_published_endurance_null_review_is_finished_without_efficacy_zero():
    from clinical_applicability import reviewed_entries, qualifying_purpose_outcomes
    from clinical_evidence_schema import validate_ingredient_context
    from probiotic_measurements import context_review_finished
    record = reviewed_entries()['INGR_L_TYROSINE']
    context = next(c for c in record['study_contexts'] if c['source_pmids'] == ['38290812'])
    assert context_review_finished(context)
    assert validate_ingredient_context(context, require_complete_review=True) == []
    assert context['scoring_eligible'] is False
    assert qualifying_purpose_outcomes(context)[0] == []
    assert all(o['direction'] == 'null' for o in context['outcomes'])
    assert 'Sutton' in ' '.join(context['limitations'])
    assert 'total_enrollment' not in record
    assert record['effect_direction'] == 'mixed'  # Acute cognitive findings remain qualified.


@pytest.mark.parametrize('groups,title,expected', [
    (['Children 4–8'], 'Kids Focus', 'explicit_conflict'),
    (['Children 14–18'], 'Teen Focus', 'unresolved'),
    (['Children 17–18'], 'Teen Focus', 'eligible'),
    ([], 'Kids Focus', 'unresolved'),
    (['Women 18–50'], 'Women Focus', 'eligible'),
    (['Men 18–50'], 'Men Focus', 'explicit_conflict'),
])
def test_qualified_tyrosine_long_interval_uses_actual_source_population(groups, title, expected):
    from clinical_applicability import reviewed_entries, assess_context_population
    context = next(c for c in reviewed_entries()['INGR_L_TYROSINE']['study_contexts']
                   if c['source_pmids'] == ['25598314'])
    assert assess_context_population({'targetGroups': groups, 'fullName': title}, context) == expected


def test_new_tyrosine_trial_uses_canonical_name_without_borrowing_enrollment():
    from clinical_applicability import reviewed_entries, assess_clinical_source_review, qualifying_purpose_outcomes
    from clinical_evidence_schema import validate_ingredient_context
    record = reviewed_entries()['INGR_L_TYROSINE']
    context = next(c for c in record['study_contexts'] if c['source_pmids'] == ['42275440'])
    assert validate_ingredient_context(context) == []
    assert context['scoring_eligible'] is True
    assert context['component_registration_status'] == 'fully_registered'
    assert context['sample_size'] == 63
    assert {o['direction'] for o in context['outcomes']} >= {'positive', 'negative', 'null'}
    assert context['outcomes'][0]['hierarchy'] == 'not_reported'
    outcomes, held = qualifying_purpose_outcomes(context)
    assert not held and len(outcomes) == 1
    assert 'highest-value' in outcomes[0]['name'].lower()
    assert '6057' in context['identity']['chemical_form']
    assert not assess_clinical_source_review(record)['is_complete']
    assert 'total_enrollment' not in record
    receipt = next(r for r in score_evidence(_tyrosine_scoring_product())['metadata']['contributing_record_assessments']
                   if r['id'] == record['id'])
    assert '42275440' in {str(r['pmid']) for r in receipt['source_references']}


@pytest.mark.parametrize('pmid', ['36548401', '39820592'])
def test_tyrosine_limitations_belong_to_their_actual_trial_family(pmid):
    from clinical_applicability import reviewed_entries
    context = next(c for c in reviewed_entries()['INGR_L_TYROSINE']['study_contexts']
                   if c['source_pmids'] == [pmid])
    text = ' '.join(context['limitations'])
    assert 'Leiden female-sample' not in text
    if pmid == '36548401':
        assert 'same 28 analyzed men' in text
        assert 'not independently enrolled trials' in text
    else:
        assert 'Part A' in text and 'same sample' in text
        assert 'not an independent replication' in text
    assert context['scoring_eligible'] is (pmid == '36548401')


def test_tyrosine_provenance_identifies_articles_and_actual_reading_basis():
    from clinical_applicability import reviewed_entries
    contexts = reviewed_entries()['INGR_L_TYROSINE']['study_contexts']
    for pmid in ['24433977', '25598314', '26424423', '10230711']:
        context = next(c for c in contexts if c['source_pmids'] == [pmid])
        provenance = context['dose']['source_provenance']
        assert provenance['source_url'] == f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/'
        location = provenance['location']
        assert 'mirror' in location.lower()
        if pmid in {'24433977', '26424423'}:
            assert 'SHA256' in location
        else:
            assert 'receipt' in location.lower()


def test_tyrosine_unread_methods_remain_open_until_their_own_review(monkeypatch):
    from copy import deepcopy
    import clinical_applicability as ca
    from clinical_applicability import reviewed_entries, assess_clinical_source_review
    from clinical_evidence_schema import validate_ingredient_context
    record = deepcopy(reviewed_entries()['INGR_L_TYROSINE'])
    monkeypatch.setattr(ca, 'reviewed_entries', lambda: {record['id']: record})
    template = next(c for c in record['study_contexts'] if c['source_pmids'] == ['26424423'])

    def close_sources(pmids):
        for index, context in enumerate(record['study_contexts']):
            pmid, = context['source_pmids']
            if pmid not in pmids:
                continue
            closed = deepcopy(template)
            closed.update(context_id=context['context_id'], source_pmids=[pmid])
            closed['clinical_review']['reviewer'] = 'Synthetic completion-mechanics control, not a clinical finding'
            closed['dose']['source_provenance'].update(
                pmid=pmid, source_url=f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/',
                location='Synthetic completed-sibling control; no new scientific approval')
            assert validate_ingredient_context(closed, require_complete_review=True) == []
            record['study_contexts'][index] = closed

    assert not assess_clinical_source_review(record)['is_complete']
    close_sources({'29980424'})
    assert assess_clinical_source_review(record)['is_complete']
    assert {p for c in record['study_contexts'] if c['scoring_eligible']
            for p in c['source_pmids']} == {'24433977', '25598314', '36548401', '42275440'}


@pytest.mark.parametrize('claim', ['', 'L-Glutamine Muscle Recovery', 'L-Glutamine IBS Support'])
def test_approved_glutamine_context_earns_claim_independent_credit_while_other_review_stays_open(claim, monkeypatch):
    import clinical_applicability as ca
    entries = ca.reviewed_entries()
    pending = copy.deepcopy(entries['INGR_L_GLUTAMINE'])
    sibling = next(c for c in pending['study_contexts'] if c['source_pmids'] == ['34844156'])
    sibling['review_status'] = 'source_verified_pending_clinical_review'
    sibling['clinical_review']['reviewer'] = 'Synthetic unread-sibling mechanics control, not current scientific status'
    monkeypatch.setattr(ca, 'reviewed_entries', lambda: {**entries, pending['id']: pending})
    index = er._backed_studies_index()
    patched = {key: [pending if r.get('id') == pending['id'] else r for r in rows]
               for key, rows in index.items()}
    monkeypatch.setattr(er, '_backed_studies_index', lambda: patched)
    from clinical_applicability import reviewed_entries, assess_clinical_source_review
    record = reviewed_entries().get('INGR_L_GLUTAMINE')
    assert record is not None
    assert record['effect_direction'] == 'positive_moderate'
    context = next(c for c in record['study_contexts'] if c['source_pmids'] == ['30108163'])
    assert context['dose']['values'] == [15]
    assert context['dose']['unit'] == 'g'
    assert context['dose']['duration_days'] == 56
    assert 'enteric infection' in context['population']['description'].lower()
    assert 'increased intestinal permeability' in context['population']['description'].lower()
    assert not assess_clinical_source_review(record)['is_complete']
    artifact = build_scored_artifact(_glutamine_scoring_product(claim=claim))
    assert artifact['quality_pillars_v4']['evidence']['score'] > 0
    assert artifact['assessment_readiness']['evidence']['readiness'] == 'incomplete'
    assert artifact['quality_assessment_status'] == 'partial'
    result = score_evidence(_glutamine_scoring_product(claim=claim), apply_primary_floor=True)
    receipt = next(r for r in result['metadata']['contributing_record_assessments']
                   if r['id'] == 'INGR_L_GLUTAMINE')
    assert {str(r['pmid']) for r in receipt['source_references']} == {'30108163'}
    assert receipt['source_review']['is_complete'] is False


@pytest.mark.parametrize('name', ['N-Acetyl-L-Glutamine', 'Sustamine L-Alanyl-L-Glutamine',
                                  'Glutamine Complex', 'D-Glutamine', 'L-Glutamine Hydrochloride',
                                  'L-Glutamine HCl', 'L-Glutamine Ethyl Ester', 'Glutamine AKG', 'Glutamine Peptide'])
def test_glutamine_derivatives_finish_only_parent_transfer_scope_without_borrowing_ibs_trial(name):
    product = _glutamine_scoring_product(name=name)
    artifact = build_scored_artifact(product)
    assert artifact['quality_pillars_v4']['evidence']['score'] == 0
    assert artifact['assessment_readiness']['evidence']['readiness'] == 'complete'
    assert 'evidence_assessment_incomplete' not in artifact['assessment_readiness']['release_assessment']['blockers']


def test_glutamine_interpretation_needs_exact_verified_selected_context():
    from scoring_v4.modules.generic_evidence import _entry_raw_points, resolved_clinical_matches
    product = _glutamine_scoring_product()
    matches = resolved_clinical_matches(product, owner_scoped=True, assess_amount=False)[0]
    selected = next((r for r in matches if r.get('id') == 'INGR_L_GLUTAMINE'), None)
    assert selected is not None
    assert selected['effect_direction'] == 'positive_moderate'
    assert _entry_raw_points(selected) > 0
    forged = copy.deepcopy(selected)
    forged['applicability_assessment']['population_applicability']['context_ids'] = ['different_context']
    assert _entry_raw_points(forged) == 0
    unscoped = {k:v for k,v in selected.items() if k != 'applicability_assessment'}
    assert _entry_raw_points(unscoped) == 0
    assert _entry_raw_points({**selected, 'id':'OTHER_RECORD', 'source_data':'backed_clinical_studies:OTHER_RECORD'}) == 0
    from scoring_v4.modules.generic_evidence import EFFECT_DIRECTION_MULTIPLIERS
    assert 'positive_moderate' not in EFFECT_DIRECTION_MULTIPLIERS


def test_pending_source_context_can_retain_unknown_facts_without_inventing_a_regimen():
    from clinical_evidence_schema import validate_ingredient_context
    context = {'context_schema_version':'1.1.0', 'context_id':'unread_source',
               'components':['INGR_L_GLUTAMINE'], 'source_pmids':['42366260'],
               'review_status':'source_verified_pending_clinical_review', 'scoring_eligible':False,
               'clinical_review':{'reviewer':'Codex source inventory', 'reviewed_at':'2026-11-06',
                                  'scope':'identity_dose_outcome_applicability'},
               'dose':{'source_provenance':{'pmid':'42366260',
                      'source_url':'https://pubmed.ncbi.nlm.nih.gov/42366260/',
                      'location':'Bibliographic identity/abstract; full-methods qualification pending'}},
               'limitations':['Preparation, route-specific outcomes and regimen remain unqualified.']}
    assert validate_ingredient_context(context) == []
    assert 'review.approval_required' in validate_ingredient_context(context, require_complete_review=True)
    forged = {**context, 'scoring_eligible':True}
    assert validate_ingredient_context(forged)
    asserted = {**context, 'dose':{**context['dose'], 'values':[15000]}}
    assert validate_ingredient_context(asserted)


def test_glutamine_older_women_review_finishes_without_borrowing_ibs_credit():
    from clinical_applicability import reviewed_entries, assess_clinical_source_review
    from clinical_evidence_schema import validate_ingredient_context
    from probiotic_measurements import context_review_finished
    from clinical_applicability import qualifying_purpose_outcomes
    record = reviewed_entries()['INGR_L_GLUTAMINE']
    context = next(c for c in record['study_contexts'] if c['source_pmids'] == ['33809996'])
    assert context_review_finished(context)
    assert validate_ingredient_context(context, require_complete_review=True) == []
    assert context['scoring_eligible'] is False
    assert context['dose']['values'] == [10000]
    assert context['dose']['duration_days'] == 30
    assert {o['outcome_role'] for o in context['outcomes']} == {'within_group_change'}
    assert qualifying_purpose_outcomes(context) == ([], False)
    assert assess_clinical_source_review(record)['is_complete']
    assert all(context_review_finished(c) for c in record['study_contexts'])


def test_betaine_limited_published_finding_finishes_with_scoped_positive_and_null_outcomes():
    from clinical_applicability import reviewed_entries, assess_clinical_source_review
    from clinical_evidence_schema import validate_ingredient_context
    record = reviewed_entries()['PRECLIN_BETAINE_ANHYDROUS']
    context = next(c for c in record['study_contexts'] if c['source_pmids'] == ['39514262'])
    assert record['notes'].startswith('Limited evidence for lower-body strength.')
    assert (record['effect_direction'], record['effect_direction_confidence']) == ('positive_weak', 'low')
    assert record['study_type'] == 'systematic_review_meta'
    assert record['total_enrollment'] is None  # The historical 100 is not the qualified pool.
    assert validate_ingredient_context(context, require_complete_review=True) == []
    assert context['review_status'] == 'clinician_approved' and context['scoring_eligible'] is True
    assert context['evidence_role'] == 'meta_analysis'
    assert {o['direction'] for o in context['outcomes']} >= {'positive', 'null'}
    assert 'eligibility' in context['population']['description'].lower()
    assert 'adult-only' in context['population']['description'].lower()
    assert 'not general exercise or cardiovascular efficacy' in record['notes']
    assert 'Fight Gone Bad repetitions positive' in record['notable_studies']
    assert 'Wingate/body-composition null' in record['notable_studies']
    assert 'FDA-approved' not in record['notes']
    assert record['health_goals_supported'] == []
    assert record['endpoint_relevance_tags'] == []
    assert 'primary_outcome' not in record  # no single health category across these trials
    assert record['category'] == 'sports_performance'
    assert not any('homocysteine' in e.lower() for e in record['key_endpoints'])
    assert 'sensitive to individual studies' in record['effect_direction_rationale'].lower()
    assert all(c['scoring_eligible'] is False for c in record['study_contexts'] if c is not context)
    assert assess_clinical_source_review(record)['is_complete']


@pytest.mark.parametrize('name,groups,eligible', [
    ('Betaine Anhydrous', ['Adults 18–50'], True),
    ('Betaine Hydrochloride', ['Adults 18–50'], False),
    ('Liposomal Betaine', ['Adults 18–50'], False),
    ('Kids Betaine Anhydrous', ['Children 4–8'], False),
])
def test_tmg_limited_finding_is_adult_form_scoped_without_a_claim_or_dose_benchmark(name, groups, eligible):
    from clinical_applicability import reviewed_entries
    from dose_assessment import positive_clinical_benchmark
    record = reviewed_entries()['PRECLIN_BETAINE_ANHYDROUS']
    product = _tyrosine_scoring_product(name=name)
    row = product['activeIngredients'][0]
    row.update(canonical_id='tmg_betaine', standard_name='Betaine', matched_form=name)
    product['targetGroups'] = groups
    product['evidence_data'] = {'clinical_matches': [{
        **record, 'ingredient': name, 'matched_canonical_ids': ['tmg_betaine'],
        'matched_source_row_refs': [row['raw_source_path']],
    }]}
    points = score_evidence(product, apply_primary_floor=False)['score']
    assert (points > 0) is eligible
    assert positive_clinical_benchmark(product, row) is None


@pytest.mark.parametrize('pmid', ['35106632', '39397201', '40748005'])
def test_glutamine_bounded_transfer_reviews_finish_without_lending_combination_or_pool_credit(pmid):
    from clinical_applicability import reviewed_entries, assess_clinical_source_review
    from clinical_evidence_schema import validate_ingredient_context
    from probiotic_measurements import context_review_finished
    record = reviewed_entries()['INGR_L_GLUTAMINE']
    context = next(c for c in record['study_contexts'] if c['source_pmids'] == [pmid])
    assert context_review_finished(context)
    assert context['review_status'] == 'rejected_source' and context['scoring_eligible'] is False
    assert validate_ingredient_context(context, require_complete_review=True) == []
    assert 'not clinician' in context['clinical_review']['reviewer']
    if pmid == '40748005':
        assert 'abstract' in context['clinical_review']['basis'].lower()
    # Other source obligations and the original narrow IBS decision remain separate.
    assert assess_clinical_source_review(record)['is_complete']
    ibs = next(c for c in record['study_contexts'] if c['source_pmids'] == ['30108163'])
    assert ibs['scoring_eligible'] is True
    assert record['effect_direction'] == 'positive_moderate'


def test_l_carnitine_finished_sources_keep_integrity_and_preparation_exclusions():
    from clinical_applicability import assess_clinical_source_review, reviewed_entries
    from clinical_evidence_schema import validate_ingredient_context
    record = reviewed_entries()["INGR_L_CARNITINE"]
    contexts = {c["context_id"]: c for c in record["study_contexts"]}
    recovery = contexts["ingr_l_carnitine_32154768_recovery_source_review"]
    assert validate_ingredient_context(recovery, require_complete_review=True) == []
    assert recovery["scoring_eligible"] is False
    assert any(o["direction"] == "positive" for o in recovery["outcomes"])
    assert "Codex" in recovery["clinical_review"]["reviewer"]
    weight = contexts["ingr_l_carnitine_32359762_weight_source_review"]
    assert validate_ingredient_context(weight, require_complete_review=True) == []
    assert weight["scoring_eligible"] is False
    assert weight["source_integrity"] == "none"
    assert "36852455" in " ".join(weight["limitations"])
    assert assess_clinical_source_review(record)["is_complete"]
    assert not er.clinical_record_sources_eligible(record)


def test_glycine_qualified_human_source_keeps_rat_and_review_transfer_exclusions():
    from clinical_applicability import assess_clinical_source_review, reviewed_entries
    from clinical_evidence_schema import validate_ingredient_context
    record = reviewed_entries()["INGR_GLYCINE"]
    contexts = {pmid: c for c in record["study_contexts"] for pmid in c["source_pmids"]}
    human = contexts["22529837"]
    assert validate_ingredient_context(human, require_complete_review=True) == []
    assert human["dose"]["values"] == [3000]
    assert human["dose"]["duration_days"] == 3
    assert human["scoring_eligible"] is True
    assert contexts["25533534"]["scoring_eligible"] is False
    assert contexts["37851316"]["review_status"] == "rejected_source"
    assert record["effect_direction"] == "positive_weak"
    assert record["effect_direction_confidence"] == "low"
    assert assess_clinical_source_review(record)["is_complete"]
    assert er.clinical_record_sources_eligible(record)


def test_grape_seed_source_preserves_preparation_and_analysis_distinctions():
    from clinical_applicability import reviewed_entries
    record = reviewed_entries()["INGR_GRAPE_SEED_EXTRACT"]
    context = next(c for c in record["study_contexts"] if c["source_pmids"] == ["33671310"])
    assert "15.0%" in context["identity"]["standardization"]
    assert "Introduction" in context["identity"]["standardization"]
    text = " ".join(o["name"]for o in context["outcomes"])
    assert "-3.76" in text and "-2.98" in text and "0.0252" in text
    assert context["scoring_eligible"] is False


def test_plant_sterol_capsule_synthesis_keeps_other_source_scopes_and_unread_hold():
    from clinical_applicability import assess_clinical_source_review, reviewed_entries
    from clinical_evidence_schema import validate_ingredient_context
    record = reviewed_entries()["INGR_PLANT_STEROLS"]
    contexts = {pmid: c for c in record["study_contexts"]for pmid in c["source_pmids"]}
    for pmid in ["24144075", "24287284"]:
        assert validate_ingredient_context(contexts[pmid], require_complete_review=True) == []
        assert contexts[pmid]["scoring_eligible"] is (pmid == "24144075")
        assert "Codex" in contexts[pmid]["clinical_review"]["reviewer"]
    assert contexts["37739728"]["review_status"] == "source_verified_pending_clinical_review"
    assert "identity_scope" not in contexts["37739728"]
    assert not assess_clinical_source_review(record)["is_complete"]
    assert er.clinical_record_sources_eligible(record)


def _betaine_with_pending_published_source(monkeypatch, record):
    import clinical_applicability as ca
    records = ca.reviewed_entries()
    pending = copy.deepcopy(record)
    context = next(c for c in pending['study_contexts'] if c['source_pmids'] == ['39514262'])
    context['review_status'] = 'source_verified_pending_clinical_review'
    context['scoring_eligible'] = False
    monkeypatch.setattr(ca, 'reviewed_entries', lambda: {**records, pending['id']: pending})
    return pending


def test_machek_finished_primary_review_cannot_clear_betaine_pool_hold(monkeypatch):
    from clinical_applicability import assess_clinical_source_review, reviewed_entries
    from clinical_evidence_schema import validate_ingredient_context
    from probiotic_measurements import context_review_finished, clinical_review_provenance_valid
    record = reviewed_entries()["PRECLIN_BETAINE_ANHYDROUS"]
    contexts = [c for c in record["study_contexts"] if "36501070" in c["source_pmids"]]
    assert len(contexts) == 1  # Legs/exercise conditions are not independent trial families.
    context = contexts[0]
    assert validate_ingredient_context(context, require_complete_review=True) == []
    assert context_review_finished(context)
    assert clinical_review_provenance_valid(context)
    assert context["scoring_eligible"] is False
    assert assess_clinical_source_review(record)["is_complete"]
    # Its own finished review cannot substitute for the independent synthesis review.
    pending = _betaine_with_pending_published_source(monkeypatch, record)
    assert not assess_clinical_source_review(pending)["is_complete"]
    assert not er.clinical_record_sources_eligible(pending)


def test_yang_rct_transfer_exclusion_preserves_human_research_and_parent_hold(monkeypatch):
    from clinical_applicability import assess_clinical_source_review, reviewed_entries
    from clinical_evidence_schema import validate_ingredient_context
    from probiotic_measurements import context_review_finished, clinical_review_provenance_valid
    record = reviewed_entries()["PRECLIN_BETAINE_ANHYDROUS"]
    contexts = [c for c in record["study_contexts"] if "36009767" in c["source_pmids"]]
    assert len(contexts) == 1
    context = contexts[0]
    assert context["review_status"] == "rejected_source"
    assert context["scoring_eligible"] is False
    assert "evidence_role" not in context  # Unverified allocation is not a fabricated design.
    assert set(context["dose"]) == {"source_provenance"}
    assert validate_ingredient_context(context, require_complete_review=True) == []
    assert context_review_finished(context) and clinical_review_provenance_valid(context)
    reference = next(r for r in record["references_structured"] if r.get("pmid") == "36009767")
    assert reference["pmid_verified"] and reference["topic_match_verified"]
    assert assess_clinical_source_review(record)["is_complete"]
    pending = _betaine_with_pending_published_source(monkeypatch, record)
    assert not assess_clinical_source_review(pending)["is_complete"]
    assert not er.clinical_record_sources_eligible(pending)


@pytest.mark.parametrize("label, expected_sources", [
    ("L-Tyrosine", {"24433977", "25598314", "36548401", "42275440"}),
    ("Men L-Tyrosine", {"36548401", "42275440"}),
    ("Women L-Tyrosine", {"24433977", "25598314", "42275440"}),
])
def test_tyrosine_reviewed_reaction_time_source_is_population_scoped(label, expected_sources):
    from clinical_applicability import reviewed_entries, assess_clinical_source_review
    from clinical_evidence_schema import validate_ingredient_context
    from dose_assessment import positive_clinical_benchmark
    record = reviewed_entries()["INGR_L_TYROSINE"]
    context = next(c for c in record["study_contexts"] if c["source_pmids"] == ["36548401"])
    assert context["review_status"] == "clinician_approved"
    assert context["scoring_eligible"] is True
    assert validate_ingredient_context(context, require_complete_review=True) == []
    assert context["dose"]["values"] == [2000]
    assert context["dose"]["dose_basis"] == "single_challenge"
    assert {o["direction"] for o in context["outcomes"]} == {"positive", "null", "mixed"}
    assert all(o["hierarchy"] == "not_reported" for o in context["outcomes"])
    assert record["study_type"] == "rct_multiple"
    assert record["published_studies_count"] == 3
    assert "total_enrollment" not in record
    assert context["sample_size"] == 28
    assert record["effect_direction"] == "mixed"
    assert not assess_clinical_source_review(record)["is_complete"]
    product = _tyrosine_scoring_product(claim=label)
    assert positive_clinical_benchmark(product, product["activeIngredients"][0]) is None
    artifact = build_scored_artifact(product)
    assert artifact["quality_assessment_status"] == "partial"
    result = score_evidence(product)
    receipt = next(r for r in result["metadata"]["contributing_record_assessments"]
                   if r["id"] == "INGR_L_TYROSINE")
    assert {str(r["pmid"]) for r in receipt["source_references"]} == expected_sources
    assert receipt["source_review"]["is_complete"] is False


@pytest.mark.parametrize("record_id, canonical, label, pmid, excluded", [
    ("INGR_REDUCED_GLUTATHIONE", "glutathione", "Setria Reduced L-Glutathione", "24791752", "Liposomal Setria Glutathione"),
    ("INGR_NATTOKINASE", "nattokinase", "Nattokinase NSK-SD", "26109079", "Natto extract"),
])
def test_exact_reviewed_biomarker_sources_keep_scope_and_no_dose_curve(record_id, canonical, label, pmid, excluded):
    from clinical_applicability import reviewed_entries, assess_clinical_source_review, qualifying_purpose_outcomes
    from clinical_evidence_schema import validate_ingredient_context
    from dose_assessment import positive_clinical_benchmark
    record = reviewed_entries().get(record_id)
    assert record is not None
    assert record["published_studies_count"] == 1
    assert record["effect_direction"] == "mixed"
    assert assess_clinical_source_review(record)["is_complete"]
    context, = record["study_contexts"]
    assert context["source_pmids"] == [pmid]
    assert validate_ingredient_context(context, require_complete_review=True) == []
    outcomes, held = qualifying_purpose_outcomes(context)
    assert outcomes and not held
    if canonical == "glutathione":
        assert context["trial_registration"] == "NCT01044277"
        assert record["total_enrollment"] == 61 and context["sample_size"] == 54
        assert all(o["hierarchy"] == "primary" for o in outcomes)
        assert all("NK-cell" not in o["name"] for o in outcomes)
    else:
        assert context["dose"]["measurement_type"] == "enzyme_activity"
        assert context["dose"]["unit"] == "FU"
        assert context["dose"]["values"] == [2000]
        assert context["dose"]["dose_basis"] == "single_challenge"
    product = _tyrosine_scoring_product(name=label)
    row = product["activeIngredients"][0]
    row.update(canonical_id=canonical, standard_name=record["standard_name"], matched_form=label,
               form_match_status="mapped")
    assert positive_clinical_benchmark(product, row) is None
    result = score_evidence(product)
    receipt = next(r for r in result["metadata"]["contributing_record_assessments"] if r["id"] == record_id)
    assert result["score"] > 0
    assert {str(r["pmid"]) for r in receipt["source_references"]} == {pmid}
    assert receipt["source_review"]["is_complete"] is True
    assert build_scored_artifact(product)["assessment_readiness"]["evidence"]["readiness"] == "complete"
    row.update(name=excluded, raw_source_text=excluded, matched_form=excluded)
    assert score_evidence(product)["score"] == 0
    row.update(name=label, raw_source_text=label, matched_form=label)
    product["targetGroups"] = ["Children 4–8"]
    assert score_evidence(product)["score"] == 0


@pytest.mark.parametrize("canonical, retained_pmid", [
    ("l_norvaline", "39330485"), ("catuaba", "22669143"),
    ("cnidium", "37328084"), ("eyebright", "32850558"),
    ("phenylethylamine", "9081552"),
])
def test_bounded_oral_evidence_gaps_preserve_related_human_research(canonical, retained_pmid):
    from evidence_resolver import _load_literature_evidence, resolve_evidence_for_canonical
    record = _load_literature_evidence()[canonical]
    assert record["applicability_status"] == "no_qualifying_human_evidence"
    assert record["effect_direction"] is None
    assert record["qualifying_human_studies"] == []
    assert retained_pmid in record["applicability_decision"]
    assert "oral" in record["applicability_decision"].lower()
    assert record["records_screened"] > 0
    assert "Codex" in record["verification_provenance"]["verified_by"]
    assert "independent" in record["verification_provenance"]["verified_by"].lower()
    resolution = resolve_evidence_for_canonical(canonical, name=canonical.replace("_", " "))
    assert resolution.disposition == "no_qualifying_human_evidence"
    assert resolution.points_eligible is False


@pytest.mark.parametrize("label, eligible", [
    ("Reduced L-Glutathione", True), ("L-Glutathione (Reduced Form)", True),
    ("Reduced Glutathione (GSH)", True), ("Setria Reduced L-Glutathione", True),
    ("Glutathione", False), ("Liposomal Reduced L-Glutathione", False),
    ("S-Acetyl L-Glutathione", False), ("Oxidized L-Glutathione (GSSG)", False),
    ("L-Glutathione Disulfide", False), ("D-Glutathione", False),
    ("DL-Glutathione", False), ("Sublingual Reduced L-Glutathione", False),
    ("Modified-release Reduced L-Glutathione", False),
])
def test_glutathione_chemical_form_proof_is_row_grounded_not_brand_inferred(label, eligible):
    product = _tyrosine_scoring_product(name=label, claim="Setria antioxidant support")
    row = product["activeIngredients"][0]
    # A stale/inferred prepared form and brand-bearing title cannot supply the label proof.
    row.update(canonical_id="glutathione", standard_name="Reduced L-Glutathione",
               matched_form="reduced l-glutathione", form_match_status="mapped")
    result = score_evidence(product)
    assert (result["score"] > 0) is eligible


@pytest.mark.parametrize("source_case, eligible", [
    ("sole_active", False), ("other_row", True),
    ("stale_marker", True), ("negated_marker", True),
])
def test_clinical_preparation_exclusion_uses_bound_delivery_source(source_case, eligible):
    product = _tyrosine_scoring_product(name="Setria Reduced L-Glutathione")
    row = product["activeIngredients"][0]
    row.update(canonical_id="glutathione", standard_name="Reduced L-Glutathione",
               matched_form="reduced l-glutathione", form_match_status="mapped")
    product["fullName"] = "Liposomal Setria Reduced L-Glutathione"
    match_source = "fullName"
    if source_case == "other_row":
        extra = {**row, "canonical_id": "vitamin_c", "name": "Liposomal Vitamin C",
                 "raw_source_text": "Liposomal Vitamin C", "standard_name": "Vitamin C",
                 "raw_source_path": "ingredientRows[1]"}
        product["activeIngredients"].append(extra)
        product["ingredient_quality_data"]["ingredients"].append(extra)
        product["ingredient_quality_data"]["ingredients_scorable"].append(extra)
        match_source = "activeIngredients[1]"
    elif source_case == "stale_marker":
        product["fullName"] = "Setria Reduced L-Glutathione"
    elif source_case == "negated_marker":
        product["fullName"] = "Non-liposomal Setria Reduced L-Glutathione"
    product["delivery_data"] = {"systems": [{
        "canonical_name": "liposomal", "raw_source_text": "liposomal",
        "match_source": match_source,
    }]}
    result = score_evidence(product)
    receipts = result["metadata"]["contributing_record_assessments"]
    assert any(r["id"] == "INGR_REDUCED_GLUTATHIONE" for r in receipts) is eligible


@pytest.mark.parametrize("canonical, retained_source", [
    ("maca_root", "36593713"), ("olive_leaf_powder", "21036583"),
    ("collagen", "33301004"), ("l_proline", "41290715"),
    ("l_phenylalanine", "32560181"), ("lithium", "39356507"),
    ("paba", "14794992"), ("chaga", "18416085"),
    ("raspberry_ketones", "26317375"),
])
def test_read_human_source_facts_preserve_unfinished_ingredient_assessment(canonical, retained_source):
    from evidence_resolver import _load_literature_evidence
    record = _load_literature_evidence()[canonical]
    assert record["applicability_status"] == "applicability_unestablished"
    narrative = record.get("applicability_decision", "") + " " + record.get("notes", "")
    assert retained_source in narrative
    assert "independent" in record["verification_provenance"]["verified_by"].lower()
    if canonical in {"l_proline", "paba"}:
        assert not record["studied_dose_exposure"]
    if canonical == "maca_root":
        assert record["reason_code"] != "crude_material_lacks_standardization"
        study = next(s for s in record["qualifying_human_studies"] if s["pmid"] == "36593713")
        assert "833" in study["dose"] and "5g" in study["dose"].replace(" ", "")
    if canonical == "l_phenylalanine":
        study = next(s for s in record["qualifying_human_studies"] if s["pmid"] == "32560181")
        assert study["sample_size"] == 27 and "intragastric" in study["dose"].lower()
    if canonical == "lithium":
        study = next(s for s in record["qualifying_human_studies"] if s["pmid"] == "39356507")
        assert "elemental" in study["dose"].lower()
        assert ".59" in study["outcome"]
    if canonical == "collagen":
        assert "unread corrigendum" not in narrative.lower()
        assert "no changed study methods" in narrative.lower()


@pytest.mark.parametrize("canonical, label, expected", [
    ("nattokinase", "Nattokinase", "not_yet_evaluated"),
    ("nattokinase", "Natto extract", "not_yet_evaluated"),
    ("glutathione", "Glutathione", "not_yet_evaluated"),
    ("glutathione", "S-Acetyl L-Glutathione", "evaluated_limited_or_negative"),
    ("glutathione", "Liposomal Reduced L-Glutathione", "evaluated_limited_or_negative"),
])
def test_missing_studied_preparation_proof_cannot_finish_zero_credit(canonical, label, expected):
    from evidence_resolver import resolve_evidence_for_row
    from assessment_readiness import _resolved_evidence_assessment
    product = _tyrosine_scoring_product(name=label)
    row = product["activeIngredients"][0]
    row.update(canonical_id=canonical, standard_name=canonical,
               matched_form=label, form_match_status="mapped")
    result = resolve_evidence_for_row(row, product)
    assert not result.points_eligible
    assert _resolved_evidence_assessment(result)[0] == expected
    artifact = build_scored_artifact(product)
    assert (artifact["assessment_readiness"]["evidence"]["readiness"] == "complete") == (expected != "not_yet_evaluated")
    if expected == "not_yet_evaluated":
        assert "clinical_source_label_unresolved" in result.blocking_reasons


@pytest.mark.parametrize("unknown_first", [True, False])
def test_an_excluded_sibling_does_not_finish_an_unresolved_preparation(unknown_first):
    from clinical_applicability import assess_clinical_applicability
    product = _tyrosine_scoring_product(name="Glutathione")
    row = product["activeIngredients"][0]
    row.update(canonical_id="glutathione", standard_name="Glutathione",
               matched_form="Glutathione", form_match_status="mapped")
    excluded = {**row, "name": "S-Acetyl L-Glutathione", "raw_source_text": "S-Acetyl L-Glutathione",
                "matched_form": "S-Acetyl L-Glutathione", "raw_source_path": "ingredientRows[1]"}
    rows = [row, excluded] if unknown_first else [excluded, row]
    product["activeIngredients"] = rows
    product["ingredient_quality_data"]["ingredients"] = rows
    product["ingredient_quality_data"]["ingredients_scorable"] = rows
    decision = assess_clinical_applicability(product, {"id": "INGR_REDUCED_GLUTATHIONE",
        "matched_canonical_ids": ["glutathione"],
        "matched_source_row_refs": ["ingredientRows[0]", "ingredientRows[1]"]},
        assess_amount=False, require_claim_alignment=False)
    assert decision["status"] == "unresolved"
    assert decision["reason_code"] == "clinical_source_label_unresolved"


@pytest.mark.parametrize("notes,source,eligible", [
    ("Liposomal", "ingredientRows[0]", False),
    ("Liposomal", "activeIngredients[0]", False),
    ("Non-liposomal", "ingredientRows[0]", True),
    ("Ordinary capsules", "ingredientRows[0]", True),
    ("Liposomal", "activeIngredients[1]", True),
])
def test_clinical_exclusion_checks_only_delivery_bound_row_notes(notes, source, eligible):
    product = _tyrosine_scoring_product(name="Setria Reduced L-Glutathione")
    row = product["activeIngredients"][0]
    row.update(canonical_id="glutathione", standard_name="Reduced L-Glutathione",
               matched_form="reduced l-glutathione", form_match_status="mapped", notes=notes)
    extra = {**row, "canonical_id": "vitamin_c", "name": "Vitamin C",
             "raw_source_text": "Vitamin C", "raw_source_path": "ingredientRows[1]"}
    product["activeIngredients"].append(extra)
    product["delivery_data"] = {"systems": [{"canonical_name": "liposomal",
        "raw_source_text": "liposomal", "match_source": source}]}
    result = score_evidence(product)
    receipts = result["metadata"]["contributing_record_assessments"]
    assert any(r["id"] == "INGR_REDUCED_GLUTATHIONE" for r in receipts) is eligible


def test_grouped_source_review_prose_keeps_limits_readable_and_status_current():
    import json
    data = Path(__file__).resolve().parents[1] / "data"
    backed = json.loads((data / "backed_clinical_studies.json").read_text())
    literature = json.loads((data / "literature_evidence_records.json").read_text())
    text = json.dumps([backed, literature], ensure_ascii=False)
    for unreadable in ("Sixhealthyyoungmen", "Capsuleseachcontained",
                       "doesnotestablishstandalonefreePABA", "healthyadultsexual",
                       "mgELEMENTALlithiumaslithiumaspartate", "notindependentrandomizedreplication"):
        assert unreadable not in text
    assert "Only PMID 24433977 is proposed to contribute" not in text
    tyrosine = next(r for r in backed["backed_clinical_studies"] if r["id"] == "INGR_L_TYROSINE")
    pending = {pmid for c in tyrosine["study_contexts"]
               if c.get("review_status") == "source_verified_pending_clinical_review"
               for pmid in c.get("source_pmids", [])}
    assert pending == {"29980424"}
    for cid in ("paba", "lithium"):
        record = next(r for r in literature["literature_evidence_records"] if r["canonical_id"] == cid)
        assert "independent source-content check completed" in record["applicability_decision"]
        assert "applicability review stay open" in record["applicability_decision"]
        assert record["applicability_status"] == "applicability_unestablished"


@pytest.mark.parametrize('entry_id,pmids', [
    ('BRAND_CREAPURE', {'22971354', '24568653'}),
    ('PRECLIN_BETAINE_ANHYDROUS', {'21744011'}),
])
def test_five_family_bounded_noncredit_sources_are_finished(entry_id, pmids):
    from clinical_applicability import reviewed_entries
    entry = reviewed_entries()[entry_id]
    contexts = [c for c in entry.get('study_contexts', [])
                if set(c.get('source_pmids', [])) & pmids]
    assert {p for c in contexts for p in c['source_pmids']} == pmids
    assert all(c['review_status'] == 'clinician_approved' and c['scoring_eligible'] is False
               for c in contexts)
    assert all('Codex' in c['clinical_review']['reviewer'] for c in contexts)


def test_msm_keeps_three_distinct_generic_trials_without_inventing_a_dose_range():
    from clinical_applicability import reviewed_entries, assess_clinical_source_review
    entries = reviewed_entries()
    for key in ('INGR_MSM', 'BRAND_OPTIMSM'):
        assert entries[key]['study_type'] == 'rct_multiple'
        assert entries[key]['effect_direction'] == 'mixed'
        assert entries[key]['total_enrollment'] == 88  # Largest study, never 88 + 50.
    source = entries['INGR_MSM']
    assert source['applicability']['required_form_terms'] == ['OptiMSM', 'MSM', 'methylsulfonylmethane']
    assert 'minimum_daily_dose' not in source['applicability']
    assert {context['applicability']['minimum_daily_dose'] for context in source['study_contexts']
            if context['scoring_eligible']} == {1500, 2000, 6000}
    pending = {p for c in source['study_contexts']
               if c['review_status'] == 'source_verified_pending_clinical_review'
               for p in c['source_pmids']}
    assert pending == set()
    assert assess_clinical_source_review({'id': 'INGR_MSM'})['is_complete'] is True
    assert entries['BRAND_OPTIMSM']['study_contexts'][0]['clinical_review']['reviewer'] == 'Dr. Pham'


@pytest.mark.parametrize('entry_ids', [
    ['BRAND_OPTIMSM', 'INGR_MSM'], ['INGR_MSM', 'BRAND_OPTIMSM'],
])
@pytest.mark.parametrize('floor', [False, True])
def test_shared_msm_trial_cannot_earn_points_twice(entry_ids, floor):
    from clinical_applicability import reviewed_entries
    product = _tyrosine_scoring_product(name='OptiMSM Methylsulfonylmethane')
    row = product['activeIngredients'][0]
    row.update(canonical_id='msm', standard_name='MSM', matched_form='msm')
    entries = reviewed_entries()

    def measured(ids):
        candidate = copy.deepcopy(product)
        matches = [{**entries[key], 'ingredient': row['name'],
                    'matched_source_row_refs': [row['raw_source_path']],
                    'matched_canonical_ids': ['msm']} for key in ids]
        candidate['evidence_data'] = {'clinical_matches': matches}
        return score_evidence(candidate, accepted_matches=matches, apply_primary_floor=floor)

    single = max(measured([key])['score'] for key in entry_ids)
    combined = measured(entry_ids)
    assert combined['score'] == single
    # Both records still carry review obligations and source provenance.
    assert {r['id'] for r in combined['metadata']['contributing_record_assessments']} == set(entry_ids)

    assert combined['components']['clinical_evidence_pipeline'] == max(
        measured([key])['components']['clinical_evidence_pipeline'] for key in entry_ids)
    assert sum(combined['metadata']['ingredient_points'].values()) == max(
        sum(measured([key])['metadata']['ingredient_points'].values()) for key in entry_ids)
    generic = next(r for r in combined['metadata']['contributing_record_assessments'] if r['id'] == 'INGR_MSM')
    assert generic['source_review']['is_complete'] is True


def test_trial_family_dedup_keeps_independent_sources_and_identity_scopes(monkeypatch):
    import clinical_applicability as ca
    from scoring_v4.modules import generic_evidence as ge
    product = _tyrosine_scoring_product(name='OptiMSM Methylsulfonylmethane')
    row = product['activeIngredients'][0]
    row.update(canonical_id='msm', standard_name='MSM', matched_form='msm')
    entries = copy.deepcopy(ca.reviewed_entries())
    originals = ca.reviewed_entries()
    monkeypatch.setattr(ca, 'reviewed_entries', lambda: entries)
    def measure(ids):
        matches = [{**entries[key], 'ingredient': row['name'],
                    'matched_source_row_refs': [row['raw_source_path']],
                    'matched_canonical_ids': ['msm']} for key in ids]
        candidate = copy.deepcopy(product)
        candidate['evidence_data'] = {'clinical_matches': matches}
        return score_evidence(candidate, accepted_matches=matches)
    ids = ['BRAND_OPTIMSM', 'INGR_MSM']
    for c in entries['INGR_MSM']['study_contexts']:
        if c['scoring_eligible']:
            c['trial_family'] = 'independent_test_trial'
    result = measure(ids)
    expected = sum(sum(measure([key])['metadata']['ingredient_points'].values()) for key in ids)
    assert sum(result['metadata']['ingredient_points'].values()) == pytest.approx(expected)
    assert expected > 0
    # Isolate the already-qualified numerical aggregation seam: the same family
    # tag must not collapse two different physical ingredient owners.
    entries['INGR_MSM'] = copy.deepcopy(originals['INGR_MSM'])
    matches = [{**entries[key], 'matched_canonical_ids': [canonical],
                'applicability_assessment': {'population_applicability': {
                    'context_ids': [entries[key]['study_contexts'][0]['context_id']]}}}
               for key, canonical in zip(ids, ['msm', 'separate_test_identity'])]
    selected_matches = list(matches)
    monkeypatch.setattr(ge, 'resolved_clinical_matches', lambda *a, **kw: (selected_matches, []))
    monkeypatch.setattr(ge, '_matched_active_canonical', lambda e, *a, **kw: e['matched_canonical_ids'][0])
    result = score_evidence(copy.deepcopy(product), accepted_matches=matches)
    assert len(result['metadata']['ingredient_points']) == 2
    separate = 0
    for match in matches:
        selected_matches[:] = [match]
        separate += sum(score_evidence(copy.deepcopy(product), accepted_matches=[match])['metadata']['ingredient_points'].values())
    assert separate > 0
    assert sum(result['metadata']['ingredient_points'].values()) == pytest.approx(separate)


def test_inulin_source_completion_preserves_preparation_and_unread_source_holds():
    from clinical_applicability import reviewed_entries, assess_clinical_source_review
    record = reviewed_entries()['INGR_INULIN']
    contexts = {c['source_pmids'][0]: c for c in record['study_contexts']}
    for pmid in ('27492975', '38309832'):
        assert contexts[pmid]['review_status'] == 'clinician_approved'
        assert contexts[pmid]['scoring_eligible'] is False
        assert 'Codex /root' in contexts[pmid]['clinical_review']['reviewer']
    assert contexts['27492975']['dose']['values'] == [12]
    assert contexts['27492975']['population']['sample_size'] == 44
    assert 'Orafti GR' in contexts['27492975']['identity']['preparation']
    assert {o['direction'] for o in contexts['27492975']['outcomes']} == {'positive', 'null', 'negative'}
    assert len(contexts['38309832']['included_study_pmids']) == 47
    assert not assess_clinical_source_review(record)['is_complete']


def test_inulin_fernandes_pointer_keeps_actual_doi_and_unresolved_cohort():
    from clinical_applicability import reviewed_entries
    context = next(c for c in reviewed_entries()['INGR_INULIN']['study_contexts']
                   if c['source_pmids'] == ['38309832'])
    text = ' '.join(context['limitations'])
    assert '10.1097/MCG.0000000000000328' in text
    assert '10.1007/s11695-015-1574-x' not in text
    assert 'healthy' in text and 'RYGB' in text
    assert 'not established' in text


def test_chicory_factual_source_update_preserves_approved_neutral_dose_proof():
    from evidence_resolver import _load_literature_evidence
    from dose_assessment import verified_reference_citations
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    record = _load_literature_evidence()['chicory_root']
    assert record['reference_semantics']['curve'] == 'completed_no_benchmark_neutral'
    assert verified_reference_citations(record)
    assert _botanical_benchmark({'canonical_id': 'chicory_root'}) == 'absent'


def _creapure_scoring_product():
    product = _tyrosine_scoring_product(name='Creapure')
    product['activeIngredients'][0].update(canonical_id='creatine_monohydrate',
        standard_name='Creatine', matched_form='creatine monohydrate', quantity=5000)
    return product


def test_completed_creapure_reference_preserves_generic_trial_credit():
    from clinical_applicability import reviewed_entries, assess_clinical_source_review
    from evidence_resolver import resolve_evidence_for_row
    from assessment_readiness import _resolved_evidence_assessment, EVIDENCE_EVALUATED_SUPPORTED
    entries = reviewed_entries()
    brand = entries['BRAND_CREAPURE']
    assert brand['study_type'] == brand['evidence_level'] == 'reference'
    assert brand['effect_direction'] == 'positive_strong'  # Historical description retained.
    assert all('scoring_eligible' not in ref for ref in brand['references_structured'])
    assert all(c['scoring_eligible'] is False for c in brand['study_contexts'])
    assert assess_clinical_source_review(brand)['is_complete']
    product = _creapure_scoring_product()
    row = product['activeIngredients'][0]
    def measured(ids):
        candidate = copy.deepcopy(product)
        matches = [{**entries[key], 'ingredient': row['name'],
                    'matched_source_row_refs': [row['raw_source_path']],
                    'matched_canonical_ids': ['creatine_monohydrate']} for key in ids]
        candidate['evidence_data'] = {'clinical_matches': matches}
        return score_evidence(candidate, accepted_matches=matches)
    ingredient = measured(['INGR_CREATINE_MONOHYDRATE'])
    both = measured(['INGR_CREATINE_MONOHYDRATE', 'BRAND_CREAPURE'])
    assert ingredient['score'] > 0
    assert both['score'] == ingredient['score']
    assert both['metadata']['ingredient_points'] == ingredient['metadata']['ingredient_points']
    assert measured(['BRAND_CREAPURE'])['score'] == 0
    resolution = resolve_evidence_for_row(row, product)
    assert resolution.points_eligible and resolution.blocking_reasons == []
    assert _resolved_evidence_assessment(resolution)[0] == EVIDENCE_EVALUATED_SUPPORTED


@pytest.mark.parametrize('source_label_present', [True, False])
def test_kre_alkalyn_finished_limited_reference_does_not_borrow_monohydrate_credit(source_label_present):
    from clinical_applicability import reviewed_entries, assess_clinical_source_review
    from clinical_evidence_schema import validate_ingredient_context
    from evidence_resolver import resolve_evidence_for_row
    from assessment_readiness import _resolved_evidence_assessment, EVIDENCE_EVALUATED_LIMITED_OR_NEGATIVE
    entry = reviewed_entries().get('BRAND_KRE_ALKALYN')
    assert entry is not None
    assert entry['study_type'] == entry['evidence_level'] == 'reference'
    assert entry['total_enrollment'] is None
    assert entry['health_goals_supported'] == []
    assert 'primary_outcome' not in entry  # No primary rank was established by the source.
    assert len(entry['study_contexts']) == 1
    context = entry['study_contexts'][0]
    assert context['source_pmids'] == ['22971354'] and context['scoring_eligible'] is False
    assert validate_ingredient_context(context, require_complete_review=True) == []
    assert assess_clinical_source_review(entry)['is_complete']
    assert {o['outcome_role'] for o in context['outcomes']} >= {
        'direct_between_group_effect', 'within_group_change'}
    product = _creapure_scoring_product()
    row = product['activeIngredients'][0]
    row.update(name='Kre-Alkalyn', raw_source_text='Kre-Alkalyn', matched_form='Kre-Alkalyn')
    product['product_name'] = 'Kre-Alkalyn'
    if not source_label_present:
        row.pop('raw_source_text')
    resolution = resolve_evidence_for_row(row, product)
    assert resolution.points_eligible is False
    if not source_label_present:
        assert 'clinical_source_label_unresolved' in resolution.blocking_reasons
        return
    assert resolution.blocking_reasons == []
    assert _resolved_evidence_assessment(resolution)[0] == EVIDENCE_EVALUATED_LIMITED_OR_NEGATIVE
    assert score_evidence(product)['score'] == 0
    # A distinct monohydrate row keeps its own research even under this title.
    mixed = copy.deepcopy(product)
    monohydrate = {**mixed['activeIngredients'][0], 'name': 'Creatine Monohydrate',
                   'raw_source_text': 'Creatine Monohydrate', 'matched_form': 'creatine monohydrate',
                   'raw_source_path': 'ingredientRows[1]', 'quantity': 3000}
    mixed['activeIngredients'].append(monohydrate)
    for key in ('ingredients', 'ingredients_scorable'):
        mixed['ingredient_quality_data'][key].append(monohydrate)
    assert resolve_evidence_for_row(monohydrate, mixed).points_eligible
    mixed['evidence_data'] = {'clinical_matches': [{
        **reviewed_entries()['INGR_CREATINE_MONOHYDRATE'],
        'ingredient': monohydrate['name'], 'matched_canonical_ids': ['creatine_monohydrate'],
        'matched_source_row_refs': [monohydrate['raw_source_path']],
    }]}
    assert score_evidence(mixed)['score'] > 0


@pytest.mark.parametrize('change', ['pending', 'malformed'])
def test_kre_reference_cannot_finish_while_its_own_review_is_incomplete(monkeypatch, change):
    import clinical_applicability as ca
    from evidence_resolver import resolve_evidence_for_row
    from assessment_readiness import _resolved_evidence_assessment, EVIDENCE_NOT_YET_EVALUATED
    records = ca.reviewed_entries()
    pending = copy.deepcopy(records['BRAND_KRE_ALKALYN'])
    context = pending['study_contexts'][0]
    if change == 'pending':
        context['review_status'] = 'source_verified_pending_clinical_review'
    else:
        context['clinical_review'] = {}
    monkeypatch.setattr(ca, 'reviewed_entries', lambda: {**records, pending['id']: pending})
    product = _creapure_scoring_product()
    row = product['activeIngredients'][0]
    row.update(name='Kre-Alkalyn', raw_source_text='Kre-Alkalyn', matched_form='Kre-Alkalyn')
    product['product_name'] = 'Kre-Alkalyn'
    resolution = resolve_evidence_for_row(row, product)
    assert not resolution.points_eligible and resolution.blocking_reasons
    assert _resolved_evidence_assessment(resolution)[0] == EVIDENCE_NOT_YET_EVALUATED


@pytest.mark.parametrize('change', ['pending', 'malformed'])
def test_creapure_reference_cannot_hide_unfinished_or_invalid_source(monkeypatch, change):
    import clinical_applicability as ca
    from evidence_resolver import resolve_evidence_for_row
    entries = copy.deepcopy(ca.reviewed_entries())
    brand = entries['BRAND_CREAPURE']
    if change == 'pending':
        extra = copy.deepcopy(brand['study_contexts'][0])
        extra['context_id'] += '_pending_control'
        extra['review_status'] = 'source_verified_pending_clinical_review'
        brand['study_contexts'].append(extra)
    else:
        brand['study_contexts'][0]['clinical_review'] = {}
    monkeypatch.setattr(ca, 'reviewed_entries', lambda: entries)
    assert not ca.assess_clinical_source_review(brand)['is_complete']
    product = _creapure_scoring_product()
    assert 'clinical_sources_ineligible' in resolve_evidence_for_row(
        product['activeIngredients'][0], product).blocking_reasons


def test_msm_recovered_175_methods_preserve_reported_benefit_and_unreported_result_limits():
    from clinical_applicability import reviewed_entries, assess_clinical_source_review
    record = reviewed_entries()['INGR_MSM']
    context = next(c for c in record['study_contexts'] if c['source_pmids'] == ['17516722'])
    assert context['review_status'] == 'clinician_approved'
    assert context['scoring_eligible'] is True
    location = context['dose']['source_provenance']['location']
    assert 'p355' in location and 'p358' in location and 'p359' in location
    text = ' '.join(context['limitations'])
    assert 'principal' in text and 'unreported' in text
    assert 'positive' in text and 'placebo' in text
    assert '30' in context['population']['description'] and '28' in context['population']['description']
    assert 'unread' not in text.lower()
    assert assess_clinical_source_review(record)['is_complete']


def test_msm_175_main_mobility_review_finishes_without_inventing_missing_results():
    from clinical_applicability import (reviewed_entries, assess_clinical_source_review,
                                        qualifying_purpose_outcomes)
    from clinical_evidence_schema import validate_ingredient_context
    entries = reviewed_entries()
    record = entries['INGR_MSM']
    context = next(c for c in record['study_contexts'] if c['source_pmids'] == ['17516722'])
    assert context['review_status'] == 'clinician_approved'
    assert context['scoring_eligible'] is True
    assert validate_ingredient_context(context, require_complete_review=True) == []
    assert context['sample_size'] == 58
    assert context['dose']['values'] == [1500]
    assert context['dose']['duration_days'] == 84
    assert context['identity'].get('branded_material') != 'OptiMSM'
    outcomes, held = qualifying_purpose_outcomes(context)
    assert not held
    assert len(outcomes) == 1
    assert 'mobility' in outcomes[0]['name'].lower()
    assert outcomes[0]['hierarchy'] == 'primary'
    assert outcomes[0]['outcome_role'] == 'direct_between_group_effect'
    limitations = ' '.join(context['limitations']).lower()
    assert 'responder' in limitations and 'unreported' in limitations
    assert 'swelling' in limitations and '0.39' in limitations and '0.75' in limitations
    assert not any('responder' in outcome['name'].lower() for outcome in outcomes)
    assert assess_clinical_source_review(record)['is_complete'] is True
    assert record['effect_direction'] == 'mixed'
    assert record['total_enrollment'] == 88
    assert record['reference_semantics']['curve'] == 'completed_no_benchmark_neutral'
    assert not any('17516722' in c['source_pmids'] for c in entries['BRAND_OPTIMSM']['study_contexts'])


@pytest.mark.parametrize('broad_raw', [3.0, 6.0])
def test_contained_trial_witness_preserves_independent_units_in_every_order(broad_raw):
    from itertools import permutations
    from scoring_v4.modules.generic_evidence import _select_trial_family_contributions
    candidates = [
        (frozenset({'a'}), 2.0, 'msm', 'A'),
        (frozenset({'b'}), 2.0, 'msm', 'B'),
        (frozenset({'a', 'b'}), broad_raw, 'msm', 'C'),
        (frozenset({'d'}), 1.0, 'msm', 'D'),
    ]
    for ordering in permutations(candidates):
        working = list(ordering)
        before = copy.deepcopy(working)
        assert sum(row[1] for row in _select_trial_family_contributions(working)) == max(4.0, broad_raw) + 1.0
        assert working == before


@pytest.mark.parametrize('floor', [False, True])
def test_subsumed_msm_witness_keeps_its_independent_pending_review(monkeypatch, floor):
    import clinical_applicability as ca
    entries = copy.deepcopy(ca.reviewed_entries())
    pending = next(c for c in entries['INGR_MSM']['study_contexts'] if c['source_pmids'] == ['21708034'])
    pending['review_status'] = 'source_verified_pending_clinical_review'
    monkeypatch.setattr(ca, 'reviewed_entries', lambda: entries)
    product = _tyrosine_scoring_product(name='OptiMSM Methylsulfonylmethane')
    row = product['activeIngredients'][0]
    row.update(canonical_id='msm', standard_name='MSM', matched_form='msm')
    ids = ['BRAND_OPTIMSM', 'INGR_MSM']
    for order in (ids, ids[::-1]):
        candidate = copy.deepcopy(product)
        matches = [{**entries[key], 'ingredient': row['name'],
                    'matched_source_row_refs': [row['raw_source_path']],
                    'matched_canonical_ids': ['msm']} for key in order]
        candidate['evidence_data'] = {'clinical_matches': matches}
        before = copy.deepcopy(candidate)
        result = score_evidence(candidate, accepted_matches=matches, apply_primary_floor=floor)
        generic = next(r for r in result['metadata']['contributing_record_assessments'] if r['id'] == 'INGR_MSM')
        assert generic['source_review']['is_complete'] is False
        assert candidate == before


@pytest.mark.parametrize('record_id,pmid', [
    ('INGR_MSM', '17516722'), ('INGR_MSM', '37447322'), ('BRAND_OPTIMSM', '37447322'),
])
@pytest.mark.parametrize('target,expected', [
    ('Breastfeeding women', 'explicit_conflict'), ('Lactating mothers', 'explicit_conflict'),
    ('Men', 'eligible'), ('Women', 'eligible'),
])
def test_msm_documented_population_exclusions_use_existing_population_owner(record_id, pmid, target, expected):
    from clinical_applicability import reviewed_entries, assess_context_population
    context = next(c for c in reviewed_entries()[record_id]['study_contexts']
                   if c['source_pmids'] == [pmid])
    product = {'fullName': target + ' Joint Support', 'targetGroups': [target]}
    assert assess_context_population(product, context) == expected


@pytest.mark.parametrize('pmid', ['38193521', '42366260', '41053591'])
def test_registered_glutamine_review_finishes_without_raw_data_or_recursive_primary_gate(pmid):
    from clinical_applicability import reviewed_entries, assess_clinical_source_review
    record = reviewed_entries()['INGR_L_GLUTAMINE']
    context = next(c for c in record['study_contexts'] if c['source_pmids'] == [pmid])
    assert context['review_status'] == 'rejected_source'
    assert context['scoring_eligible'] is False
    assert validate_ingredient_context(context, require_complete_review=True) == []
    assert assess_clinical_source_review(record)['is_complete']
    assert all(context_review_finished(c) for c in record['study_contexts'])
    original = next(c for c in record['study_contexts'] if c['source_pmids'] == ['30108163'])
    assert original['scoring_eligible'] is True
    assert record['effect_direction'] == 'positive_moderate'


def test_betaine_hcl_uses_its_salt_identifier_and_only_qualified_primary_ph_source():
    from clinical_applicability import reviewed_entries, assess_clinical_source_review
    entries = reviewed_entries()
    record = entries['PRECLIN_BETAINE_HCL']
    assert record['external_ids']['unii'] == 'JK8U8K4D6K'
    assert record['external_ids']['unii'] != entries['PRECLIN_BETAINE_ANHYDROUS']['external_ids']['unii']
    assert record['study_type'] == 'rct_single'
    assert record['effect_direction'] == 'positive_weak'
    assert 'primary_outcome' not in record  # No coarse digestive-benefit category from a pH surrogate.
    assert record['effect_direction_confidence'] == 'low'
    eligible = [c for c in record['study_contexts'] if c['scoring_eligible']]
    assert len(eligible) == 1 and eligible[0]['source_pmids'] == ['31485804']
    assert eligible[0]['dose']['values'] == [4500]
    assert eligible[0]['dose']['dose_basis'] == 'single_challenge'
    assert all(validate_ingredient_context(c, require_complete_review=True) == []
               for c in record['study_contexts'])
    assert assess_clinical_source_review(record)['is_complete']


def test_cee_retains_mixed_published_findings_without_new_salt_prefix_or_trial_count():
    from clinical_applicability import reviewed_entries, assess_clinical_source_review
    record = reviewed_entries()['INGR_CREATINE_ETHYL_ESTER']
    assert record['effect_direction'] == 'mixed'
    assert record['effect_direction_confidence'] == 'low'
    assert record['total_enrollment'] is None
    context = record['study_contexts'][0]
    assert context['source_pmids'] == ['19228401'] and context['scoring_eligible']
    assert context['sample_size'] == 30  # Three arms of ten completers; not nine.
    assert 'matched' not in context['study_design'].casefold()
    assert context['trial_family'] == 'desai_2024_creatine_resistance_training_review'
    assert {o['direction'] for o in context['outcomes']} >= {'positive', 'null'}
    assert validate_ingredient_context(context, require_complete_review=True) == []
    assert assess_clinical_source_review(record)['is_complete']


def test_peg_finished_bounded_reviews_preserve_noncredit_findings():
    from clinical_applicability import reviewed_entries, assess_clinical_source_review
    record = reviewed_entries()['INGR_PEG_CREATINE']
    assert record['scoring_eligible'] is False
    completed = next(c for c in record['study_contexts'] if c['source_pmids'] == ['23897021'])
    assert completed['review_status'] == 'rejected_source'
    assert context_review_finished(completed)
    assert {p for c in record['study_contexts'] if not context_review_finished(c)
            for p in c['source_pmids']} == set()
    assert assess_clinical_source_review(record)['is_complete']


def test_hcl_primary_ph_research_credit_is_independent_of_claim_and_lower_retail_amount():
    from copy import deepcopy
    from clinical_applicability import reviewed_entries
    from scoring_v4.modules.generic_evidence import score_evidence
    row = {'name': 'Betaine Hydrochloride', 'standard_name': 'Betaine Hydrochloride',
           'canonical_id': 'tmg_betaine', 'quantity': 750, 'unit': 'mg',
           'raw_source_text': 'Betaine Hydrochloride', 'source_label_name': 'Betaine Hydrochloride',
           'raw_source_path': 'activeIngredients[0]', 'source_section': 'activeIngredients', 'role': 'primary'}
    product = {'fullName': 'Betaine HCl', 'targetGroups': ['Adults'], 'activeIngredients': [row],
               'ingredient_quality_data': {'ingredients_scorable': [row]}}
    match = {**deepcopy(reviewed_entries()['PRECLIN_BETAINE_HCL']), 'ingredient': row['name'],
             'matched_source_row_refs': [row['raw_source_path']], 'matched_canonical_ids': ['tmg_betaine']}
    before = deepcopy(product)
    result = score_evidence(product, accepted_matches=[match], apply_primary_floor=False)
    assert result['score'] > 0
    receipt = next(r for r in result['metadata']['contributing_record_assessments']
                   if r['id'] == 'PRECLIN_BETAINE_HCL')
    assert {str(r['pmid']) for r in receipt['source_references']} == {'31485804'}
    assert receipt['source_review']['is_complete'] is True
    assert product == before


@pytest.mark.parametrize('record_id,canonical,name,groups,eligible', [
    ('PRECLIN_BETAINE_HCL', 'tmg_betaine', 'Betaine Hydrochloride', ['Adults'], True),
    ('PRECLIN_BETAINE_HCL', 'tmg_betaine', 'Betaine Anhydrous', ['Adults'], False),
    ('PRECLIN_BETAINE_HCL', 'tmg_betaine', 'Betaine Hydrochloride', ['Children 4–8'], False),
    ('INGR_CREATINE_ETHYL_ESTER', 'creatine_monohydrate', 'Creatine Ethyl Ester', ['Adults'], True),
    ('INGR_CREATINE_ETHYL_ESTER', 'creatine_monohydrate', 'Creatine Ethyl Ester HCl', ['Adults'], True),
    ('INGR_CREATINE_ETHYL_ESTER', 'creatine_monohydrate', 'Creatine Hydrochloride', ['Adults'], False),
    ('INGR_CREATINE_ETHYL_ESTER', 'creatine_monohydrate', 'Creatine Monohydrate', ['Adults'], False),
])
def test_new_hcl_and_cee_findings_use_existing_physical_scope_without_dose_curve(record_id, canonical, name, groups, eligible):
    from clinical_applicability import reviewed_entries
    from dose_assessment import positive_clinical_benchmark
    product = _tyrosine_scoring_product(name=name)
    row = product['activeIngredients'][0]
    row.update(canonical_id=canonical, standard_name=name, matched_form=name)
    product['targetGroups'] = groups
    record = reviewed_entries()[record_id]
    matches = [{**record, 'ingredient': name, 'matched_canonical_ids': [canonical],
                'matched_source_row_refs': [row['raw_source_path']]}]
    product['evidence_data'] = {'clinical_matches': matches}
    before = copy.deepcopy(product)
    result = score_evidence(product, accepted_matches=matches, apply_primary_floor=False)
    assert (result['score'] > 0) is eligible
    assert positive_clinical_benchmark(product, row) is None
    assert product == before


def test_named_peg_system_finishes_its_noncredit_preparation_assessment():
    from assessment_readiness import _resolved_evidence_assessment
    row = {'canonical_id': 'creatine_monohydrate', 'name': 'PEG-Creatine System',
           'raw_source_text': 'PEG-Creatine System', 'source_label_name': 'PEG-Creatine System',
           'raw_source_path': 'activeIngredients[0]', 'source_section': 'activeIngredients'}
    product = {'activeIngredients': [row], 'ingredient_quality_data': {'ingredients_scorable': [row]}}
    resolution = er.resolve_evidence_for_row(row, product)
    assert not resolution.points_eligible
    assert resolution.reason_code == 'reference_only_clinical_record'
    assert _resolved_evidence_assessment(resolution)[0] == 'evaluated_limited_or_negative'


@pytest.mark.parametrize('reverse', [False, True])
def test_cee_and_monohydrate_overlap_does_not_add_independent_research_units(reverse):
    from clinical_applicability import reviewed_entries
    entries = reviewed_entries()

    def evaluate(items):
        rows, matches = [], []
        for index, (record_id, canonical, name) in enumerate(items):
            path = f'activeIngredients[{index}]'
            row = {'name': name, 'standard_name': name, 'canonical_id': canonical,
                   'raw_source_text': name, 'source_label_name': name, 'raw_source_path': path,
                   'source_section': 'activeIngredients', 'quantity': 3000, 'unit': 'mg', 'role': 'primary'}
            rows.append(row)
            matches.append({**copy.deepcopy(entries[record_id]), 'ingredient': name,
                            'matched_canonical_ids': [canonical], 'matched_source_row_refs': [path]})
        product = {'fullName': 'Ingredient research control', 'targetGroups': ['Adults 18–45'],
                   'activeIngredients': rows, 'ingredient_quality_data': {'ingredients_scorable': rows},
                   'evidence_data': {'clinical_matches': matches}}
        before = copy.deepcopy(product)
        result = score_evidence(product, accepted_matches=matches, apply_primary_floor=False)
        assert product == before
        return result

    mono = ('INGR_CREATINE_MONOHYDRATE', 'creatine_monohydrate', 'Creatine Monohydrate')
    cee = ('INGR_CREATINE_ETHYL_ESTER', 'creatine_monohydrate', 'Creatine Ethyl Ester')
    hcl = ('PRECLIN_BETAINE_HCL', 'tmg_betaine', 'Betaine Hydrochloride')
    single_mono, single_cee = evaluate([mono]), evaluate([cee])
    assert single_mono['score'] > 0 and single_cee['score'] > 0
    pair = [mono, cee]
    independent = [cee, hcl]
    if reverse:
        pair.reverse()
        independent.reverse()
    combined = evaluate(pair)
    for component in ('clinical_evidence_pipeline', 'depth_bonus'):
        assert combined['components'][component] <= max(
            single_mono['components'][component], single_cee['components'][component])
    assert combined['score'] <= max(single_mono['score'], single_cee['score'])
    assert evaluate(independent)['components']['clinical_evidence_pipeline'] > single_cee['components']['clinical_evidence_pipeline']


def test_hcl_pk_references_stay_noneligible_beside_the_new_primary_ph_finding():
    from clinical_applicability import reviewed_entries
    record = reviewed_entries()['PRECLIN_BETAINE_HCL']
    assert record['health_goals_supported'] == []
    for context in record['study_contexts']:
        expected = context['source_pmids'] == ['31485804']
        assert er.clinical_record_sources_eligible(
            record, context=context, source_pmids=context['source_pmids']) is expected
        if not expected:
            assert context_review_finished(context)
            assert context['scoring_eligible'] is False
def test_glycine_bounded_human_assessment_finishes_without_borrowed_review_depth():
    from clinical_applicability import assess_clinical_source_review, reviewed_entries
    from clinical_evidence_schema import validate_ingredient_context
    from probiotic_measurements import context_review_finished
    record = reviewed_entries()['INGR_GLYCINE']
    contexts = {c['source_pmids'][0]: c for c in record['study_contexts']}
    human = contexts['22529837']
    assert human['scoring_eligible'] is True
    assert validate_ingredient_context(human, require_complete_review=True) == []
    assert record['effect_direction'] == 'positive_weak'
    assert record['effect_direction_confidence'] == 'low'
    assert record['study_type'] == 'rct_single'
    assert record['published_studies_count'] == 1
    assert 'total_enrollment' not in record and 'registry_completed_trials_count' not in record
    assert 'min_clinical_dose' not in record
    assert all(o['hierarchy'] == 'not_reported' for o in human['outcomes'])
    assert {o['direction'] for o in human['outcomes']} >= {'positive', 'null'}
    review = contexts['37851316']
    assert review['review_status'] == 'rejected_source'
    assert context_review_finished(review)
    assert validate_ingredient_context(review, require_complete_review=True) == []
    assert review['scoring_eligible'] is False
    text = ' '.join(review['limitations'])
    assert '22293292' in text and 'Inagawa' in text and 'unread' in text
    assert contexts['25533534']['review_status'] == 'rejected_source'
    assert assess_clinical_source_review(record)['is_complete']
    assert er.clinical_record_sources_eligible(record)


def test_plant_sterol_capsule_class_source_qualifies_without_closing_unread_review():
    from clinical_applicability import assess_clinical_source_review, reviewed_entries
    from clinical_evidence_schema import validate_ingredient_context
    record = reviewed_entries()['INGR_PLANT_STEROLS']
    contexts = {c['source_pmids'][0]: c for c in record['study_contexts']}
    assert contexts['24144075']['scoring_eligible'] is True
    assert validate_ingredient_context(contexts['24144075'], require_complete_review=True) == []
    assert record['effect_direction'] == 'positive_weak'
    assert record['effect_direction_confidence'] == 'low'
    assert 'total_enrollment' not in record and 'registry_completed_trials_count' not in record
    assert record['endpoint_relevance_tags'] == ['cardiovascular']
    assert record['key_endpoints'] == ['LDL cholesterol ↓']
    assert 'FDA-approved' not in record['notes']
    assert contexts['19109655']['scoring_eligible'] is False
    assert contexts['24287284']['scoring_eligible'] is False
    assert contexts['37739728']['review_status'] == 'source_verified_pending_clinical_review'
    assert not assess_clinical_source_review(record)['is_complete']


@pytest.mark.parametrize('name,canonical,delivery,eligible', [
    ('Plant Sterols and Plant Stanols Esters', 'phytosterols', 'Softgel', True),
    ('Plant Sterols', 'phytosterols', 'Capsule', True),
    ('Phytosterols', 'phytosterols', 'Tablet', True),
    ('Plant Stanols', 'phytosterols', 'Capsule', True),
    ('Plant Sterols', 'phytosterols', 'Powder', False),
    ('Plant Sterols', 'phytosterols', 'Liquid', False),
    ('Plant Sterols', 'phytosterols', '', False),
    ('Beta-Sitosterol', 'beta_sitosterol', 'Capsule', False),
    ('Beta-Sitosterol', 'phytosterols', 'Capsule', False),
])
def test_plant_sterol_class_review_uses_retained_delivery_and_mixture_identity(name, canonical, delivery, eligible):
    from clinical_applicability import filter_clinical_matches, reviewed_entries
    record = reviewed_entries()['INGR_PLANT_STEROLS']
    row = {'name': name, 'raw_source_text': name, 'source_label_name': name,
           'canonical_id': canonical, 'mapped': True, 'quantity': 1800, 'unit': 'mg',
           'raw_source_path': 'ingredientRows[0]'}
    product = {'fullName': 'Adult lipid supplement', 'physicalState': {'name': delivery},
               'activeIngredients': [copy.deepcopy(row)],
               'ingredient_quality_data': {'ingredients': [row], 'ingredients_scorable': [row]}}
    entry = {**record, 'ingredient': name, 'matched_canonical_ids': [canonical],
             'matched_source_row_refs': ['ingredientRows[0]']}
    original = copy.deepcopy((product, entry))
    matches, _ = filter_clinical_matches(product, [entry], assess_amount=False)
    assert bool(matches) is eligible
    if eligible:
        assert matches[0]['applicability_assessment']['population_applicability']['context_ids'] == [
            'ingr_plant_sterols_24144075_bounded_source_scope']
        assert 'total_enrollment' not in matches[0]
    assert (product, entry) == original


@pytest.mark.parametrize('name,canonical,title,eligible', [
    ('L-Glycine', 'l_glycine', 'Adult Glycine', True),
    ('Glycine', 'glycine', 'Adult Glycine', True),
    ('Glycine', 'l_glycine', "Women's Glycine", False),
    ('Glycine', 'l_glycine', 'Kids Glycine', False),
    ('Magnesium Glycinate', 'magnesium', 'Adult Magnesium', False),
    ('Glycine Propionyl L-Carnitine', 'l_glycine', 'Adult Carnitine', False),
    ('GlyNAC', 'l_glycine', 'Adult GlyNAC', False),
])
def test_glycine_qualified_source_preserves_population_and_free_material_boundaries(name, canonical, title, eligible):
    from clinical_applicability import filter_clinical_matches, reviewed_entries
    record = reviewed_entries()['INGR_GLYCINE']
    row = {'name': name, 'raw_source_text': name, 'source_label_name': name,
           'canonical_id': canonical, 'mapped': True, 'quantity': 3000, 'unit': 'mg',
           'raw_source_path': 'ingredientRows[0]'}
    product = {'fullName': title, 'physicalState': {'name': 'Powder'},
               'activeIngredients': [copy.deepcopy(row)],
               'ingredient_quality_data': {'ingredients': [row], 'ingredients_scorable': [row]}}
    entry = {**record, 'ingredient': name, 'matched_canonical_ids': [canonical],
             'matched_source_row_refs': ['ingredientRows[0]']}
    original = copy.deepcopy((product, entry))
    matches, _ = filter_clinical_matches(product, [entry], assess_amount=False)
    assert bool(matches) is eligible
    if eligible:
        assert matches[0]['study_type'] == 'rct_single'
        assert matches[0]['applicability_assessment']['population_applicability']['context_ids'] == [
            'ingr_glycine_22529837_sleep_restriction_source_scope']
        assert 'total_enrollment' not in matches[0]
        product['evidence_data'] = {'clinical_matches': [entry]}
        artifact = build_scored_artifact(product)
        assert artifact['quality_pillars_v4']['evidence']['score'] > 0
        product.pop('evidence_data')
    assert (product, entry) == original


@pytest.mark.parametrize('physical,eligible', [
    ({'langualCode': 'E0161', 'langualCodeDescription': 'Softgel Capsule'}, True),
    ({'langualCode': 'E0159', 'langualCodeDescription': 'Capsule'}, True),
    ({'langualCode': 'E0155', 'langualCodeDescription': 'Tablet or Pill'}, True),
    ({'langualCode': 'E0162', 'langualCodeDescription': 'Powder'}, False),
    ({'langualCodeDescription': 'Unknown'}, False),
    ({}, False),
])
def test_clinical_source_delivery_reads_retained_dsld_description(physical, eligible):
    from clinical_applicability import filter_clinical_matches, reviewed_entries
    row = {'name': 'Plant Sterols', 'raw_source_text': 'Plant Sterols',
           'source_label_name': 'Plant Sterols', 'canonical_id': 'phytosterols',
           'mapped': True, 'quantity': 1800, 'unit': 'mg', 'raw_source_path': 'ingredientRows[0]'}
    product = {'fullName': 'Adult lipid supplement', 'physicalState': physical,
               'form_factor_canonical': 'softgel',  # A stale guess must not override retained powder/unknown.
               'activeIngredients': [copy.deepcopy(row)],
               'ingredient_quality_data': {'ingredients': [row], 'ingredients_scorable': [row]}}
    entry = {**reviewed_entries()['INGR_PLANT_STEROLS'], 'ingredient': 'Plant Sterols',
             'matched_canonical_ids': ['phytosterols'], 'matched_source_row_refs': ['ingredientRows[0]']}
    original = copy.deepcopy((product, entry))
    matches, _ = filter_clinical_matches(product, [entry], assess_amount=False)
    assert bool(matches) is eligible
    assert (product, entry) == original


@pytest.mark.parametrize('canonical,name,amount', [
    ('hyaluronic_acid', 'Hyaluronic Acid', 150),
    ('american_ginseng', 'American Ginseng', 1100),
])
def test_known_capsule_with_unestablished_preparation_is_not_a_completed_delivery_exclusion(canonical, name, amount):
    row = {'name': name, 'raw_source_text': name, 'source_label_name': name,
           'canonical_id': canonical, 'mapped': True, 'quantity': amount, 'unit': 'mg',
           'raw_source_path': 'ingredientRows[0]'}
    product = {'fullName': name, 'physicalState': {'langualCodeDescription': 'Capsule'},
               'form_factor_canonical': 'capsule', 'activeIngredients': [copy.deepcopy(row)],
               'ingredient_quality_data': {'ingredients': [row], 'ingredients_scorable': [row]}}
    original = copy.deepcopy((row, product))
    resolution = er.resolve_evidence_for_row(row, product=product)
    assert resolution.points_eligible is False
    assert resolution.reason_code != 'clinical_delivery_mismatch'
    assert resolution.applicability_status == 'applicability_unestablished'
    assert (row, product) == original


def test_sterol_source_limitations_keep_full_verifiable_identifiers():
    from clinical_applicability import reviewed_entries
    record = reviewed_entries()['INGR_PLANT_STEROLS']
    contexts = {c['source_pmids'][0]: c for c in record['study_contexts']}
    pooled = ' '.join(contexts['24144075']['limitations'])
    exact = ' '.join(contexts['24287284']['limitations'])
    assert 'PMID 24287284' in pooled and 'PMID 37739728' in pooled
    assert 'PMID 24144075' in exact
    assert 'Exact242preparation' not in pooled and 'unread377 source' not in pooled
    assert 'qualified241capsule' not in exact


@pytest.mark.parametrize('pmid', ['19387397', '21068676'])
def test_peg_reported_abstract_findings_can_finish_limited_without_causal_strength_credit(pmid):
    from clinical_applicability import reviewed_entries, assess_clinical_source_review
    record = reviewed_entries()['INGR_PEG_CREATINE']
    context = next(c for c in record['study_contexts'] if c['source_pmids'] == [pmid])
    assert context['review_status'] == 'rejected_source'
    assert context['scoring_eligible'] is False
    assert context_review_finished(context)
    assert 'abstract' in context['clinical_review']['basis'].casefold()
    assert 'within' in ' '.join(context['limitations']).casefold()
    assert validate_ingredient_context(context, require_complete_review=True) == []
    assert assess_clinical_source_review(record)['is_complete']
    assert record['scoring_eligible'] is False
    assert record['total_enrollment'] is None


def test_glutamine_burn_abstract_review_does_not_invent_route_or_erase_reported_benefits():
    from clinical_applicability import reviewed_entries, assess_clinical_source_review
    record = reviewed_entries()['INGR_L_GLUTAMINE']
    context = next(c for c in record['study_contexts'] if c['source_pmids'] == ['38243579'])
    assert context['review_status'] == 'rejected_source'
    assert context['scoring_eligible'] is False
    assert context_review_finished(context)
    assert 'abstract' in context['clinical_review']['basis'].casefold()
    text = ' '.join(context['limitations']).casefold()
    assert 'wound' in text and 'mortality' in text
    assert 'not specified' in text and 'route' in text
    assert validate_ingredient_context(context, require_complete_review=True) == []
    # A finished limited source cannot lend the one existing numerical approval to a sibling.
    assert record['effect_direction'] == 'positive_moderate'
    assert {p for c in record['study_contexts'] if c.get('scoring_eligible') is True
            for p in c['source_pmids']} == {'30108163'}
    assert assess_clinical_source_review(record)['is_complete']


@pytest.mark.parametrize('name', ['Creatine', 'Creatine Complex', 'Micronized Creatine'])
def test_finished_peg_reference_cannot_finish_unestablished_other_creatine_preparations(name):
    from assessment_readiness import _resolved_evidence_assessment
    row = {'canonical_id': 'creatine_monohydrate', 'name': name, 'raw_source_text': name,
           'source_label_name': name, 'raw_source_path': 'activeIngredients[0]',
           'source_section': 'activeIngredients', 'role': 'primary'}
    product = {'activeIngredients': [row], 'ingredient_quality_data': {'ingredients_scorable': [row]}}
    before = copy.deepcopy(product)
    resolution = er.resolve_evidence_for_row(row, product)
    assert not resolution.points_eligible
    assert _resolved_evidence_assessment(resolution)[0] == 'not_yet_evaluated'
    assert product == before


def test_glutamine_registered_secondary_review_finishes_with_numerical_hold_preserved():
    from clinical_applicability import reviewed_entries
    record = reviewed_entries()['INGR_L_GLUTAMINE']
    context = next(c for c in record['study_contexts'] if c['source_pmids'] == ['34844156'])
    assert 'one overlapping trial family' in ' '.join(context['limitations'])
    assert context['scoring_eligible'] is False
    assert context_review_finished(context)
    assert context['review_status'] == 'rejected_source'
    assert 'IRCT2016092129895N1' in str(context)
    assert 'secondary' in str(context).lower()
    assert 'retrospective' in str(context).lower()
    assert 'Exhaustive exercise time' in str(context)
    assert 'favorable between-group biomarker findings' in ' '.join(context['limitations'])
    assert 'explicitly withheld' in ' '.join(context['limitations'])
    assert 'Later publication alone does not establish' in ' '.join(context['limitations'])
    eligible = [c for c in record['study_contexts'] if c.get('scoring_eligible')]
    assert [c['source_pmids'] for c in eligible] == [['30108163']]


@pytest.mark.parametrize('name', ['Creatine Ethyl Ester', 'Creatine Ethyl Ester HCl',
    'Creatine Ethylester', 'PEG-Creatine System', 'Polyethylene Glycosylated Creatine',
    'Creatine Citrate', 'Dicreatine Malate', 'Creatine Nitrate (as NO3-T®)',
    'Creatine AKG', 'Creatine Alpha Ketoglutarate', 'Creatine MagnaPower', 'OT2(TM) Creatine'])
def test_explicit_distinct_creatine_preparations_finish_monohydrate_scope_without_transfer(name):
    from clinical_applicability import assess_clinical_applicability, reviewed_entries
    row = {'name': name, 'canonical_id': 'creatine_monohydrate',
           'raw_source_text': name, 'raw_source_path': 'ingredientRows[0]',
           'source_section': 'active', 'quantity': 3000, 'unit': 'mg'}
    product = {'fullName': name, 'activeIngredients': [row],
               'ingredient_quality_data': {'ingredients_scorable': [row]}}
    before = copy.deepcopy(product)
    record = {**reviewed_entries()['INGR_CREATINE_MONOHYDRATE'],
              'ingredient': name, 'matched_canonical_ids': ['creatine_monohydrate'],
              'matched_source_row_refs': ['ingredientRows[0]']}
    decision = assess_clinical_applicability(product, record, assess_amount=False,
                                             require_claim_alignment=False)
    assert decision['status'] == 'not_applicable'
    assert decision['reason_code'] == 'clinical_form_excluded'
    resolution = er.resolve_evidence_for_row(row, product)
    assert 'clinical_source_label_unresolved' not in resolution.blocking_reasons
    assert product == before
    artifact = build_scored_artifact(product)
    assert artifact['assessment_readiness']['evidence']['readiness'] == 'complete'
    if 'ethyl' not in name.casefold():
        assert artifact['quality_pillars_v4']['evidence']['score'] == 0


@pytest.mark.parametrize('name', ['Creatine', 'Micronized Creatine', 'Creatine Complex',
                                 'Unspecified Proprietary Creatine', 'Unspecified Release Creatine'])
def test_unspecified_creatine_and_unverified_brand_still_require_preparation(name):
    row = {'name': name, 'canonical_id': 'creatine_monohydrate', 'raw_source_text': name,
           'raw_source_path': 'ingredientRows[0]', 'source_section': 'active'}
    product = {'activeIngredients': [row], 'ingredient_quality_data': {'ingredients_scorable': [row]}}
    artifact = build_scored_artifact(product)
    assert artifact['assessment_readiness']['evidence']['readiness'] == 'incomplete'
    assert artifact['quality_pillars_v4']['evidence']['score'] == 0


@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('other_name', ['Creatine Ethyl Ester HCl', 'PEG-Creatine System',
                                       'Creatine Citrate', 'Creatine'])
def test_creatine_form_exclusions_stay_with_their_own_row_and_preserve_mono_credit(reverse, other_name):
    from clinical_applicability import assess_clinical_applicability, reviewed_entries
    from scoring_input_contract import get_evidence_subject_rows
    names = ['Creatine Monohydrate', other_name]
    if reverse:
        names.reverse()
    rows = [{'name': name, 'canonical_id': 'creatine_monohydrate', 'raw_source_text': name,
             'raw_source_path': f'ingredientRows[{i}]', 'source_section': 'active',
             'quantity': 3000, 'unit': 'mg'} for i, name in enumerate(names)]
    product = {'fullName': 'Mixed creatine preparation control', 'targetGroups': ['Adults'],
               'activeIngredients': rows, 'ingredient_quality_data': {'ingredients_scorable': rows}}
    reference = reviewed_entries()['INGR_CREATINE_MONOHYDRATE']
    mono_row = next(row for row in rows if row['name'] == 'Creatine Monohydrate')
    product['evidence_data'] = {'clinical_matches': [{**copy.deepcopy(reference),
        'ingredient': mono_row['name'], 'matched_canonical_ids': ['creatine_monohydrate'],
        'matched_source_row_refs': [mono_row['raw_source_path']]}]}
    before = copy.deepcopy(product)
    decisions = []
    for row in get_evidence_subject_rows(product):
        scoped = {**reference, 'ingredient': row['name'],
                  'matched_canonical_ids': ['creatine_monohydrate'],
                  'matched_source_row_refs': [row['raw_source_path']]}
        decisions.append((row['name'], assess_clinical_applicability(
            product, scoped, assess_amount=False, require_claim_alignment=False)))
    by_name = dict(decisions)
    assert by_name['Creatine Monohydrate']['status'] == 'applicable'
    assert by_name[other_name]['status'] == ('unresolved' if other_name == 'Creatine' else 'not_applicable')
    artifact = build_scored_artifact(product)
    assert artifact['quality_pillars_v4']['evidence']['score'] > 0
    if other_name == 'Creatine':
        assert artifact['assessment_readiness']['evidence']['readiness'] == 'incomplete'
    assert product == before


def test_psyllium_qualified_lipid_review_does_not_borrow_unread_review_or_counts():
    """Qualify one lipid source without lending unread bibliography or counts."""
    from clinical_applicability import assess_clinical_source_review, reviewed_entries
    from evidence_resolver import clinical_record_sources_eligible
    record = reviewed_entries()['INGR_PSYLLIUM_HUSK']
    assert len(record['study_contexts']) == 1
    context = record['study_contexts'][0]
    assert context['source_pmids'] == ['30239559']
    assert validate_ingredient_context(context, require_complete_review=True) == []
    assert assess_clinical_source_review(record)['is_complete']
    assert clinical_record_sources_eligible(record, context=context, source_pmids=['30239559'])
    assert not clinical_record_sources_eligible(record, context=context, source_pmids=['18985059'])
    old = next(r for r in record['references_structured'] if r['pmid'] == '18985059')
    assert old['scoring_eligible'] is False
    assert 'unread' in old['notes'].lower()
    assert record['published_studies_count'] == 1
    assert 'total_enrollment' not in record and 'registry_completed_trials_count' not in record
    assert record['primary_outcome'] == 'Cardiovascular/Heart Health'
    assert record['effect_direction_confidence'] == 'medium'
    assert context['population']['age_group'] == 'mixed'
    assert len(context['included_study_pmids']) == 25
    assert context['dose']['values'] == [] and 'min_clinical_dose' not in record
    assert sum(o['direction'] == 'positive' for o in context['outcomes']) == 3
    assert all(o['kind'] == 'surrogate' for o in context['outcomes'])
    assert 'not clinician review' in context['clinical_review']['reviewer']


@pytest.mark.parametrize('name,title,physical,eligible', [
    ('Psyllium husk', 'Fiber supplement', 'Powder', True),
    ('Psyllium husk', 'Fiber supplement', 'Capsule', True),
    ('Psyllium husk', 'Fiber supplement', 'Softgel', True),
    ('Plantago ovata whole seed', 'Fiber supplement', 'Powder', False),
    ('Psyllium fiber (whole seed)', 'Fiber supplement', 'Powder', False),
    ('Psyllium husk and whole seed', 'Fiber supplement', 'Powder', False),
    ('Psyllium', 'Fiber supplement', 'Powder', False),
    ('Other soluble fiber', 'Fiber supplement', 'Powder', False),
    ('Psyllium husk', 'Infant fiber', 'Powder', False),
    ('Psyllium husk', 'Pregnancy fiber', 'Powder', False),
])
def test_psyllium_lipid_research_keeps_material_route_and_population_scope(name, title, physical, eligible):
    """Bind research to source material and population without mutating inputs."""
    from clinical_applicability import filter_clinical_matches, reviewed_entries
    row = {'name': name, 'raw_source_text': name, 'source_label_name': name,
           'canonical_id': 'psyllium', 'mapped': True, 'quantity': 100, 'unit': 'mg',
           'raw_source_path': 'ingredientRows[0]'}
    product = {'fullName': title, 'physicalState': {'langualCodeDescription': physical},
               'activeIngredients': [copy.deepcopy(row)],
               'ingredient_quality_data': {'ingredients': [row], 'ingredients_scorable': [row]}}
    entry = {**reviewed_entries()['INGR_PSYLLIUM_HUSK'], 'ingredient': name,
             'matched_canonical_ids': ['psyllium'], 'matched_source_row_refs': ['ingredientRows[0]']}
    original = copy.deepcopy((product, entry))
    matches, rejected = filter_clinical_matches(product, [entry], assess_amount=False,
                                          require_claim_alignment=False)
    assert bool(matches) is eligible
    if "whole seed" in name:
        assert len(rejected) == 1
        assert rejected[0]["status"] == "not_applicable"
        assert rejected[0]["reason_code"] == "clinical_form_excluded"
    assert (product, entry) == original


def test_carnosine_primary_glycemic_sources_have_scoped_native_credit_without_replication_inflation():
    from clinical_applicability import reviewed_entries, assess_clinical_source_review, qualifying_purpose_outcomes
    record = reviewed_entries().get('INGR_L_CARNOSINE')
    assert record is not None
    assert record['effect_direction'] == 'mixed'
    assert record['effect_direction_confidence'] == 'low'
    eligible = [c for c in record['study_contexts'] if c['scoring_eligible']]
    assert {p for c in eligible for p in c['source_pmids']} == {'27040154', '38172006'}
    assert len({c['trial_family'] for c in eligible}) == 2
    assert all(qualifying_purpose_outcomes(c)[0] for c in eligible)
    assert assess_clinical_source_review(record)['is_complete']
    assert record['total_enrollment'] is None
    assert record['health_goals_supported'] == []
    assert all(validate_ingredient_context(c, require_complete_review=True) == []
               for c in record['study_contexts'])
    primary = next(c for c in eligible if c['source_pmids'] == ['27040154'])
    assert 'both arms' in str(primary['outcomes']).lower()
    assert 'attenuat' in str(primary['outcomes']).lower()
    main = next(c for c in eligible if c['source_pmids'] == ['38172006'])
    assert '0.055' in str(main['limitations'])  # Imputed AUC result is not uniformly significant.
    assert main['sample_size'] == 49
    assert 'not pregnant or lactating' in main['population']['description']
    row = {'name':'L-Carnosine', 'canonical_id':'l_carnosine', 'raw_source_text':'L-Carnosine',
           'raw_source_path':'ingredientRows[0]', 'source_section':'active', 'quantity':500,'unit':'mg'}
    product = {'fullName':'L-Carnosine', 'targetGroups':['Adults'], 'activeIngredients':[row],
               'ingredient_quality_data':{'ingredients_scorable':[row]}}
    before = copy.deepcopy(product)
    artifact = build_scored_artifact(product)
    assert artifact['quality_pillars_v4']['evidence']['score'] > 0
    assert artifact['assessment_readiness']['evidence']['readiness'] == 'complete'
    assert product == before


@pytest.mark.parametrize('name', ['N-Acetyl L-Carnosine', 'Zinc Carnosine', 'Anserine Carnosine Blend'])
def test_carnosine_glycemic_sources_cannot_lend_credit_to_other_preparations(name):
    row = {'name':name, 'canonical_id':'l_carnosine', 'raw_source_text':name,
           'raw_source_path':'ingredientRows[0]','source_section':'active','quantity':2000,'unit':'mg'}
    product = {'fullName':name,'activeIngredients':[row],
               'ingredient_quality_data':{'ingredients_scorable':[row]}}
    assert build_scored_artifact(product)['quality_pillars_v4']['evidence']['score'] == 0


def test_fenugreek_known_precision_hold_does_not_invent_counts_or_finished_zero():
    """A read source with disputed precision remains an unfinished review."""
    from clinical_applicability import assess_clinical_source_review, reviewed_entries
    from evidence_resolver import clinical_record_sources_eligible
    record = reviewed_entries()['INGR_FENUGREEK']
    assert 'total_enrollment' not in record and 'registry_completed_trials_count' not in record
    refs = {r['pmid']: r for r in record['references_structured']}
    assert set(refs) == {'32048383', '42688439'}
    assert all(r['scoring_eligible'] is False for r in refs.values())
    assert all(r['retracted'] is False for r in refs.values())
    assert not any(r.get('expression_of_concern') for r in refs.values())
    assert not clinical_record_sources_eligible(record)
    assert not assess_clinical_source_review(record)['is_complete']
    assert record['study_contexts'] == []
    assert record['study_type'] == 'systematic_review_meta'
    assert record['evidence_level'] == 'ingredient-human'
    assert record['effect_direction'] == 'mixed'
    assert record['effect_direction_confidence'] == 'low'
    assert 'primary_outcome' not in record and record['health_goals_supported'] == []
    text = ' '.join([record['notes'], record['notable_studies'], record['effect_direction_rationale']])
    assert 'Guo' in text and '35' in text and '70' in text
    assert 'free testosterone' in text and 'very low' in text
    assert 'not a finding of ineffectiveness' in text
    assert '41531421' not in str(record)


def test_fenugreek_stale_positive_match_cannot_bypass_quantitative_or_testofen_holds():
    """Canonical holds win over a positive stale enriched match."""
    from clinical_applicability import reviewed_entries
    from evidence_resolver import clinical_record_sources_eligible
    record = reviewed_entries()['INGR_FENUGREEK']
    row = {'name': 'Fenugreek seed extract', 'raw_source_text': 'Fenugreek seed extract',
           'canonical_id': 'fenugreek', 'mapped': True, 'quantity': 500, 'unit': 'mg',
           'raw_source_path': 'ingredientRows[0]', 'source_section': 'active'}
    product = {'fullName': 'Fenugreek seed extract', 'targetGroups': ['Adults'],
               'physicalState': {'langualCodeDescription': 'Capsule'}, 'activeIngredients': [row],
               'ingredient_quality_data': {'ingredients': [row], 'ingredients_scorable': [row]},
               'evidence_data': {'clinical_matches': [{**record, 'effect_direction': 'positive_strong',
                   'scoring_eligible': True, 'ingredient': row['name'],
                   'matched_canonical_ids': ['fenugreek'],
                   'matched_source_row_refs': ['ingredientRows[0]']}]}}
    original = copy.deepcopy(product)
    artifact = build_scored_artifact(product)
    assert artifact['quality_pillars_v4']['evidence']['score'] == 0
    assert artifact['assessment_readiness']['evidence']['readiness'] == 'incomplete'
    assert not clinical_record_sources_eligible(reviewed_entries()['BRAND_TESTOFEN'])
    assert product == original


def test_guanidinoacetate_reference_finishes_source_disposition_without_primary_or_efficacy_invention():
    from clinical_applicability import reviewed_entries, assess_clinical_source_review
    from assessment_readiness import _resolved_evidence_assessment
    record = reviewed_entries()['INGR_GUANIDINOACETATE']
    assert record['evidence_level'] == record['study_type'] == 'reference'
    assert record.get('effect_direction') is None
    assert record['total_enrollment'] is None
    assert record['health_goals_supported'] == []
    assert len(record['study_contexts']) == 6
    assert all(context_review_finished(c) and c['scoring_eligible'] is False for c in record['study_contexts'])
    assert assess_clinical_source_review(record)['is_complete']
    for context in record['study_contexts']:
        if context['source_pmids'][0] in {'23351309', '27497517', '27560540'}:
            assert 'NCT01133899' not in context['clinical_review']['basis']
    serum = next(c for c in record['study_contexts'] if c['source_pmids'] == ['23329885'])
    assert 'serum creatine' in str(serum).lower()
    assert 'muscle power' in str(serum).lower()
    assert 'homocysteine' in str(serum).lower()
    row = {'canonical_id': 'guanidinoacetate', 'name': 'Guanidinoacetic Acid',
           'raw_source_text': 'Guanidinoacetic Acid', 'raw_source_path': 'ingredientRows[0]',
           'source_section': 'active', 'quantity': 500, 'unit': 'mg',
           'mapped': True, 'mapped_identity': True, 'identity_disposition': 'clean'}
    product = {'activeIngredients': [row], 'ingredient_quality_data': {'ingredients_scorable': [row]}}
    before = copy.deepcopy(product)
    result = er.resolve_evidence_for_row(row, product)
    assert result.points_eligible is False
    assert _resolved_evidence_assessment(result)[0] == 'evaluated_limited_or_negative'
    assert product == before


def test_completed_glutamine_source_review_retains_only_original_ibs_credit():
    from clinical_applicability import reviewed_entries, assess_clinical_source_review
    record = reviewed_entries()['INGR_L_GLUTAMINE']
    assert assess_clinical_source_review(record)['is_complete']
    product = _glutamine_scoring_product()
    result = score_evidence(product, apply_primary_floor=True)
    receipt = next(r for r in result['metadata']['contributing_record_assessments'] if r['id'] == record['id'])
    assert receipt['source_review']['is_complete']
    assert {str(r['pmid']) for r in receipt['source_references']} == {'30108163'}
    assert build_scored_artifact(product)['assessment_readiness']['evidence']['readiness'] == 'complete'


def test_calcium_caseinate_acute_unranked_source_never_becomes_fixed_dose_or_other_casein_credit():
    from clinical_applicability import reviewed_entries
    from dose_assessment import positive_clinical_benchmark
    record = reviewed_entries()['INGR_CALCIUM_CASEINATE']
    assert record['effect_direction'] == 'positive_weak'
    assert record['effect_direction_confidence'] == 'low'
    eligible = [c for c in record['study_contexts'] if c['scoring_eligible']]
    assert len(eligible) == 1 and eligible[0]['source_pmids'] == ['21045172']
    context = eligible[0]
    assert context['outcomes'][0]['hierarchy'] == 'not_reported'
    assert context['outcomes'][0]['kind'] == 'surrogate'
    assert context['dose']['values'] == []  # No invented absolute dose from the LBM-normalized protocol.
    assert '0.30 g/kg lean body mass' in context['dose']['administration_frequency']
    assert record['reference_semantics']['reference_type'] == 'no_benchmark'
    row = {'canonical_id': 'casein', 'name': 'Calcium Caseinate', 'raw_source_text': 'Calcium Caseinate',
           'raw_source_path': 'ingredientRows[0]', 'source_section': 'active',
           'mapped': True, 'mapped_identity': True, 'identity_disposition': 'clean',
           'quantity': 12000, 'unit': 'mg'}
    product = {'activeIngredients': [row], 'ingredient_quality_data': {'ingredients_scorable': [row]}}
    assert er.resolve_evidence_for_row(row, product).points_eligible
    assert positive_clinical_benchmark(product, row) is None
    for other in ['Micellar Casein', 'Sodium Caseinate', 'Casein Hydrolysate']:
        different = {**row, 'name': other, 'raw_source_text': other}
        from clinical_applicability import assess_clinical_applicability
        source = {**record, 'ingredient': other, 'matched_canonical_ids': ['casein'],
                  'matched_source_row_refs': [different['raw_source_path']]}
        decision = assess_clinical_applicability({'activeIngredients': [different]}, source,
                                                 assess_amount=False, require_claim_alignment=False)
        assert decision['status'] == 'not_applicable'
        assert decision['reason_code'] in {'clinical_form_excluded', 'clinical_preparation_mismatch'}


def test_taurine_primary_qualifies_only_adult_bp_without_borrowing_unread_pools():
    from clinical_applicability import reviewed_entries
    from clinical_evidence_schema import validate_ingredient_context
    record = reviewed_entries()['INGR_TAURINE']
    contexts = {p: c for c in record['study_contexts'] for p in c['source_pmids']}
    primary = contexts['26781281']
    assert validate_ingredient_context(primary, require_complete_review=True) == []
    assert {p for c in record['study_contexts'] if c['scoring_eligible'] for p in c['source_pmids']} == {'26781281'}
    assert primary['dose']['values'] == [1600] and primary['dose']['duration_days'] == 84
    assert primary['population']['age_group'] == 'adult'
    assert primary['outcomes'][0]['hierarchy'] == 'primary'
    assert primary['outcomes'][0]['direction'] == 'positive'
    assert primary['trial_family'] == 'taurine_sun_2016_NCT01816698'
    assert '97' in primary['study_design'] and '120' in primary['study_design']
    assert record['effect_direction'] == 'positive_weak'
    assert record['effect_direction_confidence'] == 'low'
    assert record['total_enrollment'] == 120 and record['published_studies_count'] == 1
    assert record['registry_completed_trials_count'] is None
    assert record['health_goals_supported'] == ['Cardiovascular/Heart Health']
    assert 'amino sulfonic acid' not in record['aliases']
    assert '2-aminoethanesulfonic acid' in record['aliases']
    for pmid in ['32871172', '41275513']:
        assert contexts[pmid]['scoring_eligible'] is False
    assert {'liposomal taurine', 'magnesium taurate', 'homotaurine'} <= set(record['applicability']['excluded_form_terms'])


def test_carnitine_weight_source_finishes_limited_review_without_clearing_constituent_integrity():
    from clinical_applicability import reviewed_entries, assess_clinical_source_review
    record = reviewed_entries()['INGR_L_CARNITINE']
    weight = next(c for c in record['study_contexts'] if c['source_pmids'] == ['32359762'])
    assert context_review_finished(weight)
    assert weight['scoring_eligible'] is False and weight['source_integrity'] == 'none'
    assert any(o['direction'] == 'positive' for o in weight['outcomes'])
    text = weight['clinical_review']['basis'] + ' '.join(weight['limitations'])
    assert '36852455' in text and '26666519' in text
    assert 'leave-one' in text and 'chemical' in text
    assert assess_clinical_source_review(record)['is_complete']
    assert not er.clinical_record_sources_eligible(record)


def test_rice_training_comparisons_finish_without_inventing_placebo_efficacy_or_equivalence():
    from clinical_applicability import reviewed_entries, assess_clinical_source_review
    record = reviewed_entries()['INGR_RICE_PROTEIN']
    assert record['study_type'] == record['evidence_level'] == 'reference'
    assert record.get('effect_direction') is None and record['total_enrollment'] is None
    assert {p for c in record['study_contexts'] for p in c['source_pmids']} == {'23782948', '33261645'}
    assert all(context_review_finished(c) and c['scoring_eligible'] is False for c in record['study_contexts'])
    assert assess_clinical_source_review(record)['is_complete']
    contexts = {c['source_pmids'][0]: c for c in record['study_contexts']}
    first = ' '.join(contexts['23782948']['limitations'])
    second = ' '.join(contexts['33261645']['limitations'])
    assert '48 g' in first and 'Training-session' in first
    assert '33.6' in second and '34 randomized' in second and '24 analyzed' in second
    assert re.search(r'p\s*=\s*\.02\b', second) and 'bone' in second
    assert 'equivalence' in first and 'equivalence' in second
    row = {'name': 'Brown Rice Protein', 'raw_source_text': 'Brown Rice Protein',
           'canonical_id': 'rice_protein', 'raw_source_path': 'ingredientRows[0]',
           'quantity': 24000, 'unit': 'mg', 'mapped': True, 'identity_disposition': 'clean'}
    result = er.resolve_evidence_for_row(row, {'activeIngredients': [row]})
    assert result.points_eligible is False


@pytest.mark.parametrize('mutation', ['pending', 'missing_source', 'unbound', 'invalid_context', 'parent_hold', 'missing_eligibility', 'undeclared_source', 'sources_none', 'sources_string'])
def test_finite_noncredit_review_cannot_hide_unfinished_or_unbound_source(monkeypatch, mutation):
    import clinical_applicability as ca
    records = copy.deepcopy(ca.reviewed_entries())
    record = records['INGR_L_CARNITINE']
    context = record['study_contexts'][-1]
    if mutation == 'pending':
        context['review_status'] = 'source_verified_pending_clinical_review'
    elif mutation == 'missing_source':
        record['study_contexts'].pop()
    elif mutation == 'unbound':
        context['clinical_review'] = {}
    elif mutation == 'invalid_context':
        context['components'] = ['INGR_TAURINE']
    elif mutation == 'parent_hold':
        record['scoring_eligible'] = False
    elif mutation == 'missing_eligibility':
        context.pop('scoring_eligible')
    elif mutation == 'sources_none':
        context['source_pmids'] = None
    elif mutation == 'sources_string':
        context['source_pmids'] = '32359762'
    else:
        context['source_pmids'] = ['30108163']  # deliberate synthetic mismatch, never production.
    monkeypatch.setattr(ca, 'reviewed_entries', lambda: records)
    assert not ca.assess_clinical_source_review(record)['is_complete']


def test_noncredit_source_rejection_cannot_append_foreign_ingredient(monkeypatch):
    import clinical_applicability as ca
    records = copy.deepcopy(ca.reviewed_entries())
    record = records['INGR_RICE_PROTEIN']
    record['study_contexts'][0]['components'].append('INGR_TAURINE')
    monkeypatch.setattr(ca, 'reviewed_entries', lambda: records)
    result = ca.assess_clinical_source_review(record)
    assert not result['is_complete']
    assert any('components_unknown' in error for error in result['errors'])


def test_grape_seed_bounded_transfer_retains_findings_without_automated_depth_credit():
    from clinical_applicability import reviewed_entries, assess_clinical_source_review
    from assessment_readiness import _resolved_evidence_assessment
    record = reviewed_entries()['INGR_GRAPE_SEED_EXTRACT']
    assert record['study_type'] == record['evidence_level'] == 'reference'
    assert record['effect_direction'] is None
    assert record['published_studies_count'] is None
    assert record['total_enrollment'] is None
    assert record['registry_completed_trials_count'] is None
    contexts = {p: c for c in record['study_contexts'] for p in c['source_pmids']}
    assert set(contexts) == {'33671310', '34798267'}
    assert all(context_review_finished(c) and c['scoring_eligible'] is False
               for c in contexts.values())
    assert assess_clinical_source_review(record)['is_complete']
    synthesis = contexts['34798267']
    assert synthesis['review_status'] == 'rejected_source'
    assert 'NOT been read' in synthesis['clinical_review']['basis']
    assert 'positive DBP/HR and null SBP/FMD' in synthesis['clinical_review']['basis']
    assert contexts['33671310']['clinical_review']['reviewer'] == 'Dr. Pham'
    result = er.resolve_evidence_for_canonical('grape_seed_extract', name='Grape Seed Extract')
    assert not result.points_eligible
    assert _resolved_evidence_assessment(result)[0] == 'evaluated_limited_or_negative'


def test_ashwagandha_v1_has_bounded_research_without_rewriting_signed_history():
    from clinical_applicability import reviewed_entries
    record = reviewed_entries()['INGR_ASHWAGANDHA']
    assert record['evidence_level'] == 'ingredient-human'
    assert record['effect_direction'] == 'positive_weak'
    assert record['effect_direction_confidence'] == 'low'
    assert record['consumer_research']['studied_uses']
    assert record['applicability']['source_pmids'] == ['23439798', '32021735']
    assert record['applicability']['required_form_groups']
    assert 'min_clinical_dose' not in record
    new = [c for c in record['study_contexts'] if '_v1_' in c['context_id']]
    assert len(new) == 2
    for context in new:
        assert validate_ingredient_context(context, require_complete_review=True) == []
        assert context['clinical_review']['reviewer'] != 'Dr. Pham'
        assert 'V1' in context['clinical_review']['basis']
        assert context['trial_family'].startswith('ksm66_')
        assert 'KSM-66' in context['identity']['preparation']
    prior = [c for c in record['study_contexts'] if 'rejected_generic_transfer' in c['context_id']]
    assert len(prior) == 2
    assert all(c['review_status'] == 'rejected_source' and not c['scoring_eligible'] for c in prior)
    assert all(c['clinical_review']['reviewer'] == 'Dr. Pham' for c in prior)


@pytest.mark.parametrize('label,credit', [
    ('Ashwagandha root extract standardized withanolides', True),
    ('Ashwagandha root powder', False),
    # PR433 review: a standardized extract supplied as a powder is the extract,
    # not crude root powder; crude powder beside an extract still never qualifies.
    ('Ashwagandha root extract powder, standardized to 5% withanolides', True),
    ('Ashwagandha powdered root extract standardized withanolides', True),
    ('Ashwagandha root powder and root extract standardized withanolides', False),
    ('Ashwagandha root powder with withanolides', False),
    ('Ashwagandha', False),
    ('Ashwagandha root and leaf extract standardized withanolides', False),
    ('Ashwagandha root extract 5:1', False),
    ('Liposomal ashwagandha root extract standardized withanolides', False),
])
def test_ashwagandha_v1_credit_is_preparation_qualified_and_claim_independent(label, credit):
    from clinical_applicability import reviewed_entries, assess_clinical_applicability
    from tests.test_v4_generic_evidence_p133 import _product, _ingredient
    row = _ingredient(name='Ashwagandha', canonical_id='ashwagandha')
    row.update(raw_source_path='activeIngredients[0]', raw_source_text=label)
    record = reviewed_entries()['INGR_ASHWAGANDHA']
    match = {**record, 'ingredient': 'Ashwagandha', 'matched_canonical_ids': ['ashwagandha'],
             'matched_source_row_refs': ['activeIngredients[0]']}
    product = _product(ingredients=[row], matches=[match], product_name='Unpositioned supplement')
    decision = assess_clinical_applicability(product, match, assess_amount=False,
                                             require_claim_alignment=False)
    assert (decision['status'] == 'applicable') is credit
    assert (score_evidence(product)['score'] > 0) is credit


def test_v1_reviewed_research_with_unknown_preparation_is_not_unread_literature():
    from clinical_applicability import reviewed_entries
    from evidence_resolver import resolve_product_evidence
    from tests.test_v4_generic_evidence_p133 import _product, _ingredient
    row = _ingredient(name='Ashwagandha', canonical_id='ashwagandha')
    row.update(raw_source_path='ingredientRows[0]', raw_source_text='Ashwagandha')
    record = reviewed_entries()['INGR_ASHWAGANDHA']
    product = _product(ingredients=[row], matches=[{**record, 'ingredient': 'Ashwagandha',
        'matched_canonical_ids': ['ashwagandha'], 'matched_source_row_refs': ['ingredientRows[0]']}])
    resolution = resolve_product_evidence(product)
    assert resolution.is_assessment_complete
    assert resolution.overall_disposition == 'research_present_applicability_unestablished'
    scored = build_scored_artifact(product)
    assert scored['quality_pillars_v4']['evidence']['score'] == 0
    assert scored['quality_pillars_v4']['evidence']['display_state'] == 'applicability_unestablished'
    assert scored['assessment_readiness']['evidence']['readiness'] == 'complete'


def test_v1_preparation_uncertainty_cannot_finish_an_unreviewed_sibling(monkeypatch):
    from clinical_applicability import reviewed_entries
    from evidence_resolver import resolve_product_evidence
    from tests.test_v4_generic_evidence_p133 import _product, _ingredient
    record = reviewed_entries()['INGR_ASHWAGANDHA']
    contexts = copy.deepcopy(record['study_contexts'])
    contexts[-1]['review_status'] = 'source_verified_pending_clinical_review'
    contexts[-1]['scoring_eligible'] = False
    monkeypatch.setitem(record, 'study_contexts', contexts)
    row = _ingredient(name='Ashwagandha', canonical_id='ashwagandha')
    row.update(raw_source_path='ingredientRows[0]', raw_source_text='Ashwagandha')
    product = _product(ingredients=[row], matches=[{**record, 'ingredient': 'Ashwagandha',
        'matched_canonical_ids': ['ashwagandha'], 'matched_source_row_refs': ['ingredientRows[0]']}])
    assert not resolve_product_evidence(product).is_assessment_complete
    assert score_evidence(product)['score'] == 0


def test_v1_clinical_match_does_not_borrow_rejected_synthesis_counts():
    from clinical_applicability import reviewed_entries, filter_clinical_matches
    from tests.test_v4_generic_evidence_p133 import _product, _ingredient
    record = reviewed_entries()['INGR_ASHWAGANDHA']
    row = _ingredient(name='Ashwagandha', canonical_id='ashwagandha')
    row.update(raw_source_path='ingredientRows[0]',
               raw_source_text='Ashwagandha root extract standardized withanolides')
    match = {**record, 'ingredient': 'Ashwagandha',
             'matched_canonical_ids': ['ashwagandha'], 'matched_source_row_refs': ['ingredientRows[0]']}
    accepted, _ = filter_clinical_matches(_product(ingredients=[row], matches=[match]),
                                         [match], assess_amount=False, require_claim_alignment=False)
    assert len(accepted) == 1
    assert {r['pmid'] for r in accepted[0]['references_structured']} == {'23439798','32021735'}
    assert record['published_studies'] == ['RCT']
    assert record['published_rct_count'] == 2
    assert record['published_meta_review_count'] == 0
    assert len(record['references_structured']) == 4  # Historical inventory remains intact.


@pytest.mark.parametrize('label,complete,credit', [
    ('Synthetic herb', True, False),                                  # preparation unknown
    ('Synthetic herb leaf extract standardized to marker', True, True),  # studied class
    ('Synthetic herb root extract standardized to marker', True, False),  # named non-equivalent
])
def test_v1_ingredient_general_path_is_record_driven_not_ashwagandha_specific(
        monkeypatch, label, complete, credit):
    """ADR-0007: any record carrying ingredient_general contexts and the reviewed
    preparation-uncertainty attestation takes the same V1 path. No ingredient
    name is special-cased in the resolver, applicability or scorer."""
    import json as _json
    import clinical_applicability as ca
    import evidence_resolver as resolver
    from tests.test_v4_generic_evidence_p133 import _product, _ingredient
    source = _json.loads(_json.dumps(ca.reviewed_entries()['INGR_ASHWAGANDHA'])
                         .replace('INGR_ASHWAGANDHA', 'INGR_SYNTHETIC_HERB'))
    source.update(standard_name='Synthetic herb', aliases=['synthetic herb'])
    source['applicability'].update(required_form_groups=[['leaf'], ['extract'], ['marker']],
                                   excluded_form_terms=['root', 'liposomal'])
    monkeypatch.setattr(ca, 'reviewed_entries', lambda: {source['id']: source})
    monkeypatch.setattr(resolver, '_backed_studies_index', lambda: {'synthetic_herb': [source]})
    row = _ingredient(name='Synthetic herb', canonical_id='synthetic_herb')
    row.update(raw_source_path='ingredientRows[0]', raw_source_text=label)
    match = {**source, 'ingredient': 'Synthetic herb', 'matched_canonical_ids': ['synthetic_herb'],
             'matched_source_row_refs': ['ingredientRows[0]']}
    product = _product(ingredients=[row], matches=[match], product_name='Unpositioned supplement')
    assert resolver.resolve_product_evidence(product).is_assessment_complete is complete
    assert (score_evidence(product)['score'] > 0) is credit


@pytest.mark.parametrize('opt_in', [False, 'missing', 'true', None])
def test_v1_preparation_completion_requires_explicit_canonical_review(monkeypatch, opt_in):
    import clinical_applicability as ca
    import evidence_resolver as resolver
    from tests.test_v4_generic_evidence_p133 import _product, _ingredient
    source = copy.deepcopy(ca.reviewed_entries()['INGR_ASHWAGANDHA'])
    if opt_in == 'missing':
        source['applicability'].pop('preparation_uncertainty_reviewed')
    else:
        source['applicability']['preparation_uncertainty_reviewed'] = opt_in
    monkeypatch.setattr(ca, 'reviewed_entries', lambda: {source['id']: source})
    monkeypatch.setattr(resolver, '_backed_studies_index', lambda: {'ashwagandha': [source]})
    row = _ingredient(name='Ashwagandha', canonical_id='ashwagandha')
    row.update(raw_source_path='ingredientRows[0]', raw_source_text='Ashwagandha')
    match = {**source, 'ingredient': 'Ashwagandha', 'matched_canonical_ids': ['ashwagandha'],
             'matched_source_row_refs': ['ingredientRows[0]']}
    # A stale enriched true flag cannot replace the canonical review decision.
    match['applicability'] = {**source['applicability'], 'preparation_uncertainty_reviewed': True}
    product = _product(ingredients=[row], matches=[match])
    assert not resolver.resolve_product_evidence(product).is_assessment_complete
    assert score_evidence(product)['score'] == 0
