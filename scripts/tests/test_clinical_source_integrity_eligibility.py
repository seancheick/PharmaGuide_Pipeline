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
    assert record['endpoint_relevance_tags'] == []
    assert 'immune response ↑' not in record['key_endpoints']
    assert record['health_goals_supported'] == ['Immune Support']
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
    assert record['published_studies_count'] == 2
    assert 'total_enrollment' not in record  # Never sum independent trials into a largest-trial field.
    assert {p for c in record['study_contexts'] for p in c['source_pmids']} == {
        '24433977', '25598314', '36548401', '39820592', '29980424', '38290812',
        '26424423', '10230711',
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
    assert {str(r['pmid']) for r in receipt['source_references']} == {'24433977', '36548401'}
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
    assert record['published_studies_count'] == 2
    assert 'total_enrollment' not in record  # Never sum independent trials into a largest-trial field.
    assert {p for c in record['study_contexts'] if not context_review_finished(c)
            for p in c['source_pmids']} == {'25598314', '29980424', '38290812'}
    assert not assess_clinical_source_review(record)['is_complete']


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


def test_tyrosine_unmade_applicability_decisions_survive_other_source_closures(monkeypatch):
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

    close_sources({'29980424', '38290812'})
    assert not assess_clinical_source_review(record)['is_complete']
    close_sources({'25598314'})
    assert assess_clinical_source_review(record)['is_complete']
    assert {p for c in record['study_contexts'] if c['scoring_eligible']
            for p in c['source_pmids']} == {'24433977', '36548401'}


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
    assert record['health_goals_supported'] == []
    assert record['endpoint_relevance_tags'] == []
    assert 'primary_outcome' not in record  # no single health category across these trials
    assert record['category'] == 'sports_performance'
    assert not any('homocysteine' in e.lower() for e in record['key_endpoints'])
    assert 'historical' in record['effect_direction_rationale'].lower()
    assert all(c['scoring_eligible'] is False for c in record['study_contexts'])
    assert not assess_clinical_source_review(record)['is_complete']


def test_l_carnitine_finished_recovery_source_keeps_weight_and_preparation_holds():
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
    assert weight["review_status"] == "source_verified_pending_clinical_review"
    assert weight["source_integrity"] == "none"
    assert "36852455" in " ".join(weight["limitations"])
    assert not assess_clinical_source_review(record)["is_complete"]
    assert not er.clinical_record_sources_eligible(record)


def test_glycine_finished_factual_sources_do_not_complete_unread_review_or_activate_grade():
    from clinical_applicability import assess_clinical_source_review, reviewed_entries
    from clinical_evidence_schema import validate_ingredient_context
    record = reviewed_entries()["INGR_GLYCINE"]
    contexts = {pmid: c for c in record["study_contexts"] for pmid in c["source_pmids"]}
    human = contexts["22529837"]
    assert validate_ingredient_context(human, require_complete_review=True) == []
    assert human["dose"]["values"] == [3000]
    assert human["dose"]["duration_days"] == 3
    assert human["scoring_eligible"] is False
    assert contexts["25533534"]["scoring_eligible"] is False
    assert contexts["37851316"]["review_status"] == "source_verified_pending_clinical_review"
    assert record["scoring_eligible"] is False
    assert not assess_clinical_source_review(record)["is_complete"]
    assert not er.clinical_record_sources_eligible(record)


def test_grape_seed_source_preserves_preparation_and_analysis_distinctions():
    from clinical_applicability import reviewed_entries
    record = reviewed_entries()["INGR_GRAPE_SEED_EXTRACT"]
    context = next(c for c in record["study_contexts"] if c["source_pmids"] == ["33671310"])
    assert "15.0%" in context["identity"]["standardization"]
    assert "Introduction" in context["identity"]["standardization"]
    text = " ".join(o["name"]for o in context["outcomes"])
    assert "-3.76" in text and "-2.98" in text and "0.0252" in text
    assert context["scoring_eligible"] is False


def test_plant_sterol_completed_source_extractions_preserve_unread_synthesis():
    from clinical_applicability import assess_clinical_source_review, reviewed_entries
    from clinical_evidence_schema import validate_ingredient_context
    record = reviewed_entries()["INGR_PLANT_STEROLS"]
    contexts = {pmid: c for c in record["study_contexts"]for pmid in c["source_pmids"]}
    for pmid in ["24144075", "24287284"]:
        assert validate_ingredient_context(contexts[pmid], require_complete_review=True) == []
        assert contexts[pmid]["scoring_eligible"] is False
        assert "Codex" in contexts[pmid]["clinical_review"]["reviewer"]
    assert contexts["37739728"]["review_status"] == "source_verified_pending_clinical_review"
    assert "identity_scope" not in contexts["37739728"]
    assert not assess_clinical_source_review(record)["is_complete"]
    assert not er.clinical_record_sources_eligible(record)


def test_machek_finished_primary_review_cannot_clear_betaine_pool_hold():
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
    assert not assess_clinical_source_review(record)["is_complete"]
    assert not er.clinical_record_sources_eligible(record)


def test_yang_rct_transfer_exclusion_preserves_human_research_and_parent_hold():
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
    assert not assess_clinical_source_review(record)["is_complete"]
    assert not er.clinical_record_sources_eligible(record)


@pytest.mark.parametrize("label, expected_sources", [
    ("L-Tyrosine", {"24433977", "36548401"}),
    ("Men L-Tyrosine", {"36548401"}),
    ("Women L-Tyrosine", {"24433977"}),
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
    assert record["published_studies_count"] == 2
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
    assert "25598314" in pending
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


def test_msm_retains_one_qualified_trial_and_unfinished_sources():
    from clinical_applicability import reviewed_entries, assess_clinical_source_review
    entries = reviewed_entries()
    for key in ('INGR_MSM', 'BRAND_OPTIMSM'):
        assert entries[key]['study_type'] == 'rct_single'
        assert entries[key]['effect_direction'] == 'mixed'
    source = entries['INGR_MSM']
    assert source['applicability']['required_form_terms'] == ['OptiMSM', 'MSM', 'methylsulfonylmethane']
    assert source['applicability']['minimum_daily_dose'] == 2000
    assert source['applicability']['maximum_daily_dose'] == 2000
    pending = {p for c in source['study_contexts']
               if c['review_status'] == 'source_verified_pending_clinical_review'
               for p in c['source_pmids']}
    assert pending == {'16309928', '21708034', '17516722'}
    assert assess_clinical_source_review({'id': 'INGR_MSM'})['is_complete'] is False
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
    assert generic['source_review']['is_complete'] is False


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


def test_msm_recovered_175_methods_preserve_positive_findings_and_reporting_hold():
    from clinical_applicability import reviewed_entries, assess_clinical_source_review
    record = reviewed_entries()['INGR_MSM']
    context = next(c for c in record['study_contexts'] if c['source_pmids'] == ['17516722'])
    assert context['review_status'] == 'source_verified_pending_clinical_review'
    assert context['scoring_eligible'] is False
    assert 'full primary' in context['dose']['source_provenance']['location'].lower()
    text = ' '.join(context['limitations'])
    assert 'principal' in text and 'unreported' in text
    assert 'positive' in text and 'placebo' in text
    assert '30' in text and '28' in text
    assert 'unread' not in text.lower()
    assert not assess_clinical_source_review(record)['is_complete']
