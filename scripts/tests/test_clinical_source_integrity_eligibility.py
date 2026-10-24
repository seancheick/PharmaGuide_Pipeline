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


def _product(entry):
    rows = [{"name": "Audit Material", "standard_name": "Audit Material",
             "canonical_id": "audit_material", "mapped": True, "quantity": 100,
             "unit": "mg", "bio_score": 10}]
    return {"status": "active", "form_factor": "capsule",
            "supplement_type": {"type": "single_nutrient"},
            "ingredient_quality_data": {"ingredients": rows, "ingredients_scorable": rows},
            "evidence_data": {"clinical_matches": [entry]}}


@pytest.mark.parametrize("ref", [
    {"pmid": "41573009", "retracted": True},
    {"pmid": "41573009", "expression_of_concern": True},
    {"pmid": "41573009", "scoring_eligible": False},
])
def test_held_source_cannot_award_raw_points_or_public_primary_floor(ref):
    entry = _entry([ref])
    assert score_evidence(_product(entry), apply_primary_floor=True)["score"] == 0
    assert build_scored_artifact(_product(entry))["quality_pillars_v4"]["evidence"]["score"] == 0
    control = _product(_entry([{"pmid": "28661438", "retracted": False}]))
    assert score_evidence(control, apply_primary_floor=True)["score"] > 0


def test_mixed_record_retains_independently_eligible_source():
    entry = _entry([{"pmid": "41573009", "retracted": True},
                    {"pmid": "28661438", "retracted": False}])
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
    assert resolution.blocking_reasons == ["clinical_sources_ineligible"]
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
    assert fisetin["study_type"] == "observational"
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
    assert forbidden not in er._evidence_entry_purposes(completion_source_records[rid])


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
