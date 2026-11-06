"""Integrity holds must survive both evidence resolution and public scoring."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import evidence_resolver as er
from scoring_v4.modules.generic_evidence import score_evidence
from scoring_v4.scored_artifact import build_scored_artifact


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


@pytest.mark.parametrize('rid', ['INGR_SLIPPERY_ELM', 'INGR_MOLYBDENUM', 'INGR_PROPOLIS', 'INGR_VITAMIN_E', 'PRECLIN_BETAINE_HCL'])
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
    assert contexts['ingr_elderberry_33827515_scoped_source']['clinical_review']['reviewer'] == 'Dr. Pham'
    assert not er.clinical_record_sources_eligible(record)
    assert not assess_clinical_source_review(record)['is_complete']
    assert reviewed['trial_family'] == 'elderberry_respiratory_trials_1995_2016'
    assert reviewed['dose']['values'] == []
    assert '176' in reviewed['population']['description'] and '180' in reviewed['population']['description']
    assert 'Cochrane/GRADE review' not in ' '.join(reviewed['limitations'])


def test_taurine_integrity_review_preserves_hold_without_inferred_longevity_or_pool_contamination():
    from clinical_applicability import assess_clinical_source_review, reviewed_entries
    record = reviewed_entries()['INGR_TAURINE']
    text = record['notes'] + ' ' + record['notable_studies']
    assert '28118062' in text and '41943494' in text
    assert '2026-04-06' in text
    assert 'not contribution to any particular pooled estimate' in text
    assert 'Healthy Aging/Longevity' not in record['health_goals_supported']
    assert not {'focus_memory', 'digestive_health'} & set(record['endpoint_relevance_tags'])
    assert record['effect_direction'] == 'positive_weak'
    assert record['study_contexts'] == []
    assert not assess_clinical_source_review(record)['is_complete']
    assert {ref['pmid'] for ref in record['references_structured']} == {'32871172', '41275513'}
    assert not er.resolve_evidence_for_canonical('taurine', name='Taurine').points_eligible


def _glutamine_scoring_product(name='L-Glutamine', claim='', amount=500):
    row = {'name': name, 'raw_source_text': name, 'standard_name': 'L-Glutamine',
           'canonical_id': 'l_glutamine', 'mapped': True, 'bio_score': 11,
           'matched_form': 'l-glutamine powder' if name == 'L-Glutamine' else name,
           'quantity': amount, 'unit': 'mg', 'raw_source_path': 'ingredientRows[0]'}
    return {'product_name': claim or name, 'status': 'active', 'form_factor': 'capsule',
            'activeIngredients': [row],
            'ingredient_quality_data': {'ingredients': [row], 'ingredients_scorable': [row]}}


@pytest.mark.parametrize('claim', ['', 'L-Glutamine Muscle Recovery', 'L-Glutamine IBS Support'])
def test_approved_glutamine_context_earns_claim_independent_credit_while_other_review_stays_open(claim):
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
def test_glutamine_derivatives_do_not_borrow_trial_or_finish_their_pending_research(name):
    product = _glutamine_scoring_product(name=name)
    artifact = build_scored_artifact(product)
    assert artifact['quality_pillars_v4']['evidence']['score'] == 0
    assert artifact['assessment_readiness']['evidence']['readiness'] == 'incomplete'
    assert artifact['quality_assessment_status'] == 'partial'


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
    assert not assess_clinical_source_review(record)['is_complete']
    assert len([c for c in record['study_contexts'] if not context_review_finished(c)]) == 8


def test_betaine_exercise_prose_keeps_positive_and_null_outcomes_scoped():
    from clinical_applicability import reviewed_entries, assess_clinical_source_review
    record = reviewed_entries()['PRECLIN_BETAINE_ANHYDROUS']
    assert 'not general exercise or cardiovascular efficacy' in record['notes']
    assert 'strength/power did not show superior between-group effects' in record['notes']
    assert 'Fight Gone Bad repetitions positive' in record['notable_studies']
    assert 'Wingate/body-composition null' in record['notable_studies']
    assert 'FDA-approved' not in record['notes']
    assert all(c['scoring_eligible'] is False for c in record['study_contexts'])
    assert not assess_clinical_source_review(record)['is_complete']
