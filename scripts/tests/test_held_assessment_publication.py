"""Exact approved unavailable assessments retain their source and safety, not a score."""
from copy import deepcopy
import json
from pathlib import Path
import pytest

IDS = ['232035','229932','251528','327907','332909','295107','80302','220046']
NEW_IDS = ['251616', '252704', '254795', '254796', '254797', '327984',
           '312024', '312025', '312026', '312027', '331202',
           '294273', '311852', '312355', '312356', '312357',
           '269718', '232921', '232928', '231921', '328831', '59635']
NEW_BLOCKERS = {
    **{pid: ['dose_benchmark_identity_unresolved'] for pid in NEW_IDS[:11]},
    **{pid: ['dose_amount_unread'] for pid in NEW_IDS[11:16]},
    **{pid: ['dose_benchmark_identity_unresolved', 'evidence_assessment_incomplete']
       for pid in NEW_IDS[16:21]},
    '59635': ['probiotic_evidence_assessment_incomplete'],
}

# 330196-330199 left this list on 2026-11-01: their exact 4:1 powder Dose
# scope completed (test_exact_approved_botanical_dose_scopes.py). The title
# and blend-total fixes resolved Dose here too; Evidence remains unfinished.
RELEASE_FAILURE_IDS = ['18551', '178728']
RELEASE_FAILURE_BLOCKERS = {pid: ['evidence_assessment_incomplete'] for pid in RELEASE_FAILURE_IDS}


@pytest.fixture(scope='module')
def release_failure_pairs():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_input_contract import score_eligible_identity_view
    from score_supplements_v4 import score_product_v4

    cleaner, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()
    pairs = {}
    for pid in RELEASE_FAILURE_IDS:
        raw = json.loads((Path(__file__).parent / 'fixtures'
                          / f'raw_held_assessment_{pid}.json').read_text())
        enriched, errors = enricher.enrich_product(cleaner.normalize_product(raw))
        assert not errors, pid
        pairs[pid] = enriched, score_product_v4(score_eligible_identity_view(enriched))
    return pairs


@pytest.mark.parametrize('pid', RELEASE_FAILURE_IDS)
def test_latest_release_hold_retains_exact_label_and_safety_without_quality(release_failure_pairs, pid):
    from build_final_db import build_core_row, build_detail_blob, validate_export_contract
    from core_export_model import PRODUCTS_CORE_COLUMNS
    from scoring_v4.scored_artifact import assemble_scored_artifact

    enriched, v4 = release_failure_pairs[pid]
    scored = assemble_scored_artifact(enriched, deepcopy(v4))
    assert scored['assessment_readiness']['release_assessment']['blockers'] == RELEASE_FAILURE_BLOCKERS[pid]
    assert scored['assessment_readiness']['release_assessment']['is_complete'] is False
    assert scored['quality_score_status'] == 'not_scored'
    assert scored['verdict'] == 'NOT_SCORED'
    assert scored['score_unavailable_reason'] == 'release_assessment_incomplete'
    for key in ('quality_score_v4_100', 'score_100_equivalent',
                'score_display_100_equivalent', 'quality_pillars_v4', 'quality_tier'):
        assert scored.get(key) is None, (pid, key)
    assert scored['_v4_safety_gate'] == v4['v4_breakdown']['safety_gate']
    assert scored['product_safety_status'] == 'no_known_catalog_concern'
    assert validate_export_contract(enriched, scored) == []
    blob = build_detail_blob(enriched, scored)
    assert blob['label_record']['source_record_id'] == pid
    assert blob['warnings'] is not None
    assert blob['allergens'] is not None
    core = dict(zip(PRODUCTS_CORE_COLUMNS,
                    build_core_row(enriched, scored, '2026-11-01', detail_blob=blob), strict=True))
    for key in ('quality_score_v4_100', 'score_100_equivalent', 'quality_tier',
                'pillar_formulation_v4', 'pillar_dose_v4', 'pillar_evidence_v4'):
        assert core[key] is None, (pid, key)


@pytest.mark.parametrize('pid', RELEASE_FAILURE_IDS)
@pytest.mark.parametrize('alteration', ['source_text', 'quantity'])
def test_latest_release_hold_rejects_changed_original_label(release_failure_pairs, pid, alteration):
    from scoring_v4.scored_artifact import assemble_scored_artifact

    enriched, v4 = deepcopy(release_failure_pairs[pid])
    before = assemble_scored_artifact(enriched, deepcopy(v4))
    assert before['quality_score_status'] == 'not_scored'
    if alteration == 'source_text':
        enriched['activeIngredients'][0]['raw_source_text'] += ' altered'
    else:
        enriched['activeIngredients'][0]['quantity'] += 1
    changed = assemble_scored_artifact(enriched, deepcopy(v4))
    assert changed['quality_score_status'] == 'scored'
    assert changed['assessment_readiness']['release_assessment']['is_complete'] is False


@pytest.mark.parametrize('pid', RELEASE_FAILURE_IDS)
def test_latest_release_hold_keeps_safety_and_allergen_consumers(release_failure_pairs, pid, monkeypatch):
    from build_final_db import build_detail_blob
    from scoring_v4 import quality_score_config
    from scoring_v4.scored_artifact import assemble_scored_artifact

    enriched, v4 = release_failure_pairs[pid]
    held = assemble_scored_artifact(enriched, deepcopy(v4))
    held_blob = build_detail_blob(enriched, held)
    cfg = deepcopy(quality_score_config.config())
    del cfg['suppression']['held_assessment_labels'][pid]
    monkeypatch.setattr(quality_score_config, 'config', lambda: cfg)
    prior = assemble_scored_artifact(enriched, deepcopy(v4))
    prior_blob = build_detail_blob(enriched, prior)
    assert prior['quality_score_status'] == 'scored'
    assert held['product_safety_status'] == prior['product_safety_status']
    for key in ('warnings', 'warnings_profile_gated', 'allergens', 'warning_rule_refs'):
        assert held_blob.get(key) == prior_blob.get(key), (pid, key)

SUBMISSION_HOLDS = [
    ('PG_SUB_1A28723DBDAF4AC1897AA5FF156FACA1', 'no_known_catalog_concern'),
    ('PG_SUB_C926B40D83F1491CB6CD3EEBEBC73FC7', 'caution'),
]


@pytest.mark.parametrize('pid,safety_status', SUBMISSION_HOLDS)
def test_verified_submission_science_hold_has_no_public_score(pid, safety_status):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact
    from build_final_db import build_detail_blob, validate_export_contract

    raw = json.loads((Path(__file__).parents[2] / 'manual_labels/product_submissions'
                      / f'{pid}.json').read_text())
    assert raw['manual_product_provenance']['review_status'] == 'verified'
    enriched, errors = SupplementEnricherV3().enrich_product(
        EnhancedDSLDNormalizer().normalize_product(raw))
    assert not errors
    scored = build_scored_artifact(enriched)
    assert scored['assessment_readiness']['release_assessment']['is_complete'] is False
    assert scored['quality_score_status'] == 'not_scored'
    assert scored['verdict'] == 'NOT_SCORED'
    assert scored['score_unavailable_reason'] == 'release_assessment_incomplete'
    assert scored['product_safety_status'] == safety_status
    for key in ('quality_score_v4_100', 'score_100_equivalent',
                'score_display_100_equivalent', 'quality_pillars_v4', 'quality_tier'):
        assert scored.get(key) is None
    assert validate_export_contract(enriched, scored) == []
    blob = build_detail_blob(enriched, scored)
    assert blob['label_record']['source_record_id'] == raw['label_record_metadata']['source_record_id']


@pytest.mark.parametrize('alteration', [
    'review_status', 'source_record_id', 'source_path', 'label_record_id',
    'source_type', 'source_quantity',
])
def test_submission_hold_rejects_changed_source_or_unverified_review(alteration):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_input_contract import score_eligible_identity_view
    from score_supplements_v4 import score_product_v4
    from scoring_v4.scored_artifact import assemble_scored_artifact

    pid = 'PG_SUB_1A28723DBDAF4AC1897AA5FF156FACA1'
    raw = json.loads((Path(__file__).parents[2] / 'manual_labels/product_submissions'
                      / f'{pid}.json').read_text())
    enriched, errors = SupplementEnricherV3().enrich_product(
        EnhancedDSLDNormalizer().normalize_product(raw))
    assert not errors
    v4 = score_product_v4(score_eligible_identity_view(enriched))
    assert assemble_scored_artifact(enriched, deepcopy(v4))['quality_score_status'] == 'not_scored'
    changed = deepcopy(enriched)
    if alteration == 'review_status':
        changed['manual_product_provenance']['review_status'] = 'pending'
    elif alteration == 'source_record_id':
        changed['manual_product_provenance']['source_record_id'] = 'other-record'
    elif alteration == 'source_path':
        changed['manual_product_provenance']['source_path'] = 'local/other-label'
    elif alteration == 'label_record_id':
        changed['label_record_metadata']['source_record_id'] = 'other-record'
    elif alteration == 'source_type':
        changed['source_type'] = 'NIH DSLD'
    else:
        changed['activeIngredients'][0]['raw_source_text'] = 'changed source row'
    assert assemble_scored_artifact(changed, deepcopy(v4))['quality_score_status'] == 'scored'

@pytest.fixture(scope='module')
def pairs():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_input_contract import score_eligible_identity_view
    from score_supplements_v4 import score_product_v4
    owner, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()
    result = {}
    for pid in IDS:
        raw = json.loads((Path(__file__).parent/'fixtures'/f'raw_held_assessment_{pid}.json').read_text())
        enriched, errors = enricher.enrich_product(owner.normalize_product(raw))
        assert not errors
        result[pid] = enriched, score_product_v4(score_eligible_identity_view(enriched))
    return result


@pytest.fixture(scope='module')
def newly_approved_pairs():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_input_contract import score_eligible_identity_view
    from score_supplements_v4 import score_product_v4
    owner, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()
    result = {}
    for pid in NEW_IDS:
        raw = json.loads((Path(__file__).parent/'fixtures'/f'raw_held_assessment_{pid}.json').read_text())
        enriched, errors = enricher.enrich_product(owner.normalize_product(raw))
        assert not errors, pid
        result[pid] = enriched, score_product_v4(score_eligible_identity_view(enriched))
    return result


@pytest.mark.parametrize('pid', NEW_IDS)
def test_newly_approved_raw_label_remains_held_without_public_quality(newly_approved_pairs, pid):
    from scoring_v4.scored_artifact import assemble_scored_artifact
    from build_final_db import build_core_row, build_detail_blob, validate_export_contract
    from core_export_model import PRODUCTS_CORE_COLUMNS
    enriched, v4 = newly_approved_pairs[pid]
    before = deepcopy(enriched)
    scored = assemble_scored_artifact(enriched, deepcopy(v4))
    release = scored['assessment_readiness']['release_assessment']
    assert release['is_complete'] is False
    assert release['blockers'] == NEW_BLOCKERS[pid]
    assert scored['quality_score_status'] == 'not_scored'
    assert scored['verdict'] == 'NOT_SCORED'
    assert scored['score_unavailable_reason'] == 'release_assessment_incomplete'
    for key in ['quality_score_v4_100', 'score_100_equivalent', 'score_display_100_equivalent',
                'quality_tier', 'quality_pillars_v4']:
        assert scored.get(key) is None, (pid, key)
    assert scored['_v4_safety_gate'] == v4['v4_breakdown']['safety_gate']
    assert enriched == before
    assert validate_export_contract(enriched, scored) == []
    blob = build_detail_blob(enriched, scored)
    assert blob['label_record']['source_record_id'] == pid
    core = dict(zip(PRODUCTS_CORE_COLUMNS,
                    build_core_row(enriched, scored, '2026-10-30', detail_blob=blob), strict=True))
    assert core['quality_score_status'] == 'not_scored'
    assert core['verdict'] == 'NOT_SCORED'
    for key in ['quality_score_v4_100', 'score_100_equivalent', 'quality_tier',
                'pillar_formulation_v4', 'pillar_dose_v4', 'pillar_evidence_v4',
                'pillar_transparency_v4', 'pillar_verification_v4', 'pillar_safety_hygiene_v4']:
        assert core[key] is None, (pid, key)
    if pid in NEW_IDS[11:16]:
        assert any(a['allergen_id'] == 'ALLERGEN_MILK' for a in blob['allergens'])


@pytest.mark.parametrize('pid', NEW_IDS)
def test_new_hold_does_not_change_safety_or_allergen_blob(newly_approved_pairs, pid, monkeypatch):
    from scoring_v4.scored_artifact import assemble_scored_artifact
    from scoring_v4 import quality_score_config
    from build_final_db import build_detail_blob
    enriched, v4 = newly_approved_pairs[pid]
    held = assemble_scored_artifact(enriched, deepcopy(v4))
    held_blob = build_detail_blob(enriched, held)
    cfg = deepcopy(quality_score_config.config())
    del cfg['suppression']['held_assessment_labels'][pid]
    monkeypatch.setattr(quality_score_config, 'config', lambda: cfg)
    prior = assemble_scored_artifact(enriched, deepcopy(v4))
    prior_blob = build_detail_blob(enriched, prior)
    for key in ['warnings', 'warnings_profile_gated', 'allergens', 'warning_rule_refs']:
        assert held_blob.get(key) == prior_blob.get(key), (pid, key)
    assert held['product_safety_status'] == prior['product_safety_status']


@pytest.mark.parametrize('pid', NEW_IDS)
def test_new_hold_rejects_stale_source_fingerprint(newly_approved_pairs, pid, monkeypatch):
    from scoring_v4.scored_artifact import assemble_scored_artifact
    from scoring_v4 import quality_score_config
    cfg = deepcopy(quality_score_config.config())
    cfg['suppression']['held_assessment_labels'][pid]['formula_fingerprint'] = 'stale'
    monkeypatch.setattr(quality_score_config, 'config', lambda: cfg)
    enriched, v4 = deepcopy(newly_approved_pairs[pid])
    scored = assemble_scored_artifact(enriched, v4)
    assert scored['quality_score_status'] == 'scored'
    assert scored['assessment_readiness']['release_assessment']['is_complete'] is False


def test_new_whey_hold_rejects_changed_printed_quantity(newly_approved_pairs):
    from scoring_v4.scored_artifact import assemble_scored_artifact
    enriched, v4 = deepcopy(newly_approved_pairs['294273'])
    enriched['activeIngredients'][0]['quantity'] += 1
    scored = assemble_scored_artifact(enriched, v4)
    assert scored['quality_score_status'] == 'scored'
    assert scored['assessment_readiness']['release_assessment']['is_complete'] is False


@pytest.mark.parametrize('change', ['completed', 'unrelated_blocker', 'failed_safety'])
def test_new_hold_cannot_hide_other_release_states(newly_approved_pairs, monkeypatch, change):
    from scoring_v4.scored_artifact import assemble_scored_artifact
    import assessment_readiness
    enriched, v4 = deepcopy(newly_approved_pairs['59635'])
    if change == 'failed_safety':
        v4['v4_breakdown']['safety_gate']['ingredient_assessment_complete'] = False
        v4['v4_breakdown']['safety_gate']['ingredient_assessment_errors'] = ['resolver unavailable']
    else:
        owner = assessment_readiness.evaluate_release_assessment

        def changed_release(*args, **kwargs):
            result = owner(*args, **kwargs)
            if change == 'completed':
                return {**result, 'is_complete': True, 'blockers': [],
                        'unfinished_source_assessment': None}
            return {**result, 'blockers': result['blockers'] + ['verification_assessment_incomplete']}

        monkeypatch.setattr(assessment_readiness, 'evaluate_release_assessment', changed_release)
    scored = assemble_scored_artifact(enriched, v4)
    assert scored['quality_score_status'] == 'scored'


def test_new_hold_rejects_invalid_numeric_export(newly_approved_pairs):
    from scoring_v4.scored_artifact import assemble_scored_artifact
    from build_final_db import validate_export_contract
    enriched, v4 = newly_approved_pairs['294273']
    scored = assemble_scored_artifact(enriched, deepcopy(v4))
    scored['quality_score_v4_100'] = 63.9
    assert validate_export_contract(enriched, scored)

@pytest.mark.parametrize('pid', IDS)
def test_exact_approved_held_label_is_unscored_and_exportable(pairs, pid):
    from scoring_v4.scored_artifact import assemble_scored_artifact
    from build_final_db import validate_export_contract
    enriched, v4 = pairs[pid]
    if pid == '80302':
        assert enriched['display_ingredients'][0]['exact_dose_text'] == '<1 g'
    before = deepcopy(enriched)
    scored = assemble_scored_artifact(enriched, deepcopy(v4))
    assert scored['quality_score_status'] == 'not_scored'
    assert scored['verdict'] == 'NOT_SCORED'
    for key in ['quality_score_v4_100','score_100_equivalent','quality_tier','grade','quality_pillars_v4']:
        assert scored[key] is None, key
    assert scored['display_100'] == 'N/A'
    assert scored['score_unavailable_reason']
    release = scored['assessment_readiness']['release_assessment']
    assert release['is_complete'] is False
    assert 'dose_benchmark_identity_unresolved' in release['blockers']
    assert release['unfinished_source_assessment'] == 'dose_benchmark_identity_unresolved'
    assert scored['_v4_safety_gate'] == v4['v4_breakdown']['safety_gate']
    assert enriched == before
    assert validate_export_contract(enriched, scored) == []

@pytest.mark.parametrize('pid', IDS[1:7])
def test_species_undeclared_cascara_retains_actionable_uncertainty_warnings(pairs, pid):
    from scoring_v4.scored_artifact import assemble_scored_artifact
    from build_final_db import build_detail_blob
    enriched, v4 = pairs[pid]
    scored = assemble_scored_artifact(enriched, deepcopy(v4))
    blob = build_detail_blob(enriched, scored)
    text = json.dumps({'warnings':blob.get('warnings'), 'profile':blob.get('warnings_profile_gated'),
                       'ingredients':blob.get('ingredients')}).lower()
    for term in ['cascaroside','electrolyte','digoxin','breast milk','breastmilk']:
        assert term not in text, term
    assert 'does not declare its species' in text
    assert 'any medicine' in text
    assert 'avoid during pregnancy' in text
    assert 'breastfeeding' in text
    alerts = [a for a in enriched['interaction_profile']['ingredient_alerts']
              if a['rule_id'] == 'RULE_CASCARA_UNRESOLVED_IDENTITY']
    assert alerts
    conditions = {r['condition_id']:r for a in alerts for r in a['condition_hits']}
    for condition in ['pregnancy','lactation']:
        assert conditions[condition]['severity'] == 'avoid'
    for condition in ['kidney_disease','liver_disease']:
        assert conditions[condition]['severity'] == 'caution'
    assert not any(a.get('drug_class_hits') for a in alerts)


def test_reishi_unscored_label_retains_wheat(pairs):
    from scoring_v4.scored_artifact import assemble_scored_artifact
    from build_final_db import build_detail_blob
    enriched, v4 = pairs['220046']
    blob = build_detail_blob(enriched, assemble_scored_artifact(enriched, deepcopy(v4)))
    assert any(a['allergen_id']=='ALLERGEN_WHEAT' and a['presence_type']=='contains'
               for a in blob['allergens'])

@pytest.mark.parametrize('mutation', ['foreign_id','amount','form','species','fingerprint'])
def test_unreviewed_source_cannot_inherit_unavailable_disposition(pairs, mutation, monkeypatch):
    from scoring_v4.scored_artifact import assemble_scored_artifact
    from scoring_v4 import quality_score_config
    enriched, v4 = deepcopy(pairs['229932'])
    if mutation == 'foreign_id':
        enriched['dsld_id'] = 'unapproved-label'
    elif mutation == 'fingerprint':
        cfg = deepcopy(quality_score_config.config())
        cfg['suppression']['held_assessment_labels']['229932']['formula_fingerprint'] = 'stale'
        monkeypatch.setattr(quality_score_config, 'config', lambda: cfg)
    else:
        row = enriched['activeIngredients'][0]
        if mutation == 'amount': row['quantity'] += 1
        if mutation == 'form': row['forms'] = [{'name':'unreviewed extract'}]
        if mutation == 'species': row['notes'] = 'Rhamnus purshiana'
    scored = assemble_scored_artifact(enriched, v4)
    assert scored['quality_score_status'] == 'scored'
    assert scored['quality_score_v4_100'] is not None
    assert scored['assessment_readiness']['release_assessment']['is_complete'] is False


def test_completed_dose_does_not_keep_old_unavailable_disposition(pairs):
    from scoring_v4.scored_artifact import assemble_scored_artifact
    enriched, v4 = deepcopy(pairs['229932'])
    meta = v4['v4_breakdown']['module']['dimensions']['dose']['metadata']
    def complete(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == 'benchmark' and child == 'unresolved': value[key] = 'no_reference'
                else: complete(child)
        elif isinstance(value, list):
            for child in value: complete(child)
    complete(meta)
    scored = assemble_scored_artifact(enriched, v4)
    assert 'dose_benchmark_identity_unresolved' not in scored['assessment_readiness']['release_assessment']['blockers']
    assert scored['quality_score_status'] == 'scored'


@pytest.mark.parametrize('blockers,unfinished', [
    (['dose_amount_unread'], 'dose_amount_unread'),
    (['probiotic_evidence_assessment_incomplete'], None),
    (['dose_benchmark_identity_unresolved', 'evidence_assessment_incomplete'],
     'dose_benchmark_identity_unresolved'),
])
def test_exact_approved_hold_uses_its_recorded_blockers(pairs, monkeypatch, blockers, unfinished):
    from scoring_v4.scored_artifact import assemble_scored_artifact
    from scoring_v4 import quality_score_config
    import assessment_readiness
    enriched, v4 = deepcopy(pairs['229932'])
    cfg = deepcopy(quality_score_config.config())
    cfg['suppression']['held_assessment_labels']['229932']['blockers'] = blockers
    monkeypatch.setattr(quality_score_config, 'config', lambda: cfg)
    owner = assessment_readiness.evaluate_release_assessment

    def with_exact_hold(*args, **kwargs):
        result = owner(*args, **kwargs)
        return {**result, 'is_complete': False, 'blockers': blockers,
                'unfinished_source_assessment': unfinished}

    monkeypatch.setattr(assessment_readiness, 'evaluate_release_assessment', with_exact_hold)
    scored = assemble_scored_artifact(enriched, v4)
    assert scored['quality_score_status'] == 'not_scored'
    assert scored['quality_score_v4_100'] is None
    assert scored['assessment_readiness']['release_assessment']['blockers'] == blockers

@pytest.mark.parametrize('verdict', ['BLOCKED','UNSAFE'])
def test_held_label_never_overrides_hard_safety_precedence(pairs, verdict):
    from scoring_v4.scored_artifact import assemble_scored_artifact
    enriched, v4 = deepcopy(pairs['229932'])
    v4.update(quality_score_status='suppressed_safety', quality_score_v4_100=None,
              quality_tier=None, raw_score_v4_100=None, v4_verdict=verdict)
    v4['v4_breakdown']['safety_gate']['verdict'] = verdict
    scored = assemble_scored_artifact(enriched, v4)
    assert scored['quality_score_status']=='suppressed_safety'
    assert scored['verdict']==verdict
    assert scored['quality_score_v4_100'] is None

@pytest.mark.parametrize('failure', ['unrelated_blocker','safety_resolver','quarantine'])
def test_held_disposition_cannot_hide_independent_failures(pairs, monkeypatch, failure):
    from scoring_v4.scored_artifact import assemble_scored_artifact
    import assessment_readiness
    enriched, v4 = deepcopy(pairs['229932'])
    if failure == 'unrelated_blocker':
        owner = assessment_readiness.evaluate_release_assessment
        def with_failure(*args, **kwargs):
            result = owner(*args, **kwargs)
            result['blockers'].append('verification_assessment_incomplete')
            return result
        monkeypatch.setattr(assessment_readiness, 'evaluate_release_assessment', with_failure)
    elif failure == 'safety_resolver':
        v4['v4_breakdown']['safety_gate']['ingredient_assessment_complete'] = False
        v4['v4_breakdown']['safety_gate']['ingredient_assessment_errors'] = ['resolver unavailable']
    else:
        v4['v4_breakdown']['safety_gate']['quarantine_required'] = True
    scored = assemble_scored_artifact(enriched, v4)
    assert scored['quality_score_status'] == 'scored'
    assert scored['assessment_readiness']['release_assessment']['is_complete'] is False
    assert scored['quality_score_v4_100'] is not None


def test_held_publication_still_requires_actual_candidate_proof(pairs):
    from scoring_v4.scored_artifact import assemble_scored_artifact
    from audit_source_of_truth_contract import _release_assessment_export_contained
    enriched, v4 = pairs['229932']
    scored = assemble_scored_artifact(enriched, deepcopy(v4))
    before = deepcopy(scored['assessment_readiness']['release_assessment'])
    assert _release_assessment_export_contained(scored, enriched, completion_only=True,
        warning_only=set(), blocked_warning_only=set(), quarantines={})
    assert not _release_assessment_export_contained(scored, enriched, completion_only=False,
        warning_only=set(), blocked_warning_only=set(), quarantines={})
    assert scored['assessment_readiness']['release_assessment'] == before

@pytest.mark.parametrize('fixture,blocked', [('raw_cascara_18313.json',False),
    ('raw_held_assessment_banned_control_252358.json',True)])
def test_species_proven_and_confirmed_ban_controls_keep_existing_policy(fixture, blocked, monkeypatch):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact
    from scoring_v4 import quality_score_config
    from build_final_db import build_detail_blob
    raw = json.loads((Path(__file__).parent/'fixtures'/fixture).read_text())
    owner, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()
    after, errors = enricher.enrich_product(owner.normalize_product(deepcopy(raw)))
    assert not errors
    scored_after = build_scored_artifact(after)
    blob_after = build_detail_blob(after, scored_after)
    cfg = deepcopy(quality_score_config.config())
    cfg['suppression']['held_assessment_labels'] = {}
    monkeypatch.setattr(quality_score_config, 'config', lambda: cfg)
    before, errors = enricher.enrich_product(owner.normalize_product(deepcopy(raw)))
    assert not errors
    scored_before = build_scored_artifact(before)
    blob_before = build_detail_blob(before, scored_before)
    for field in ['activeIngredients', 'display_ingredients', 'ingredient_quality_data', 'interaction_profile']:
        assert before[field] == after[field], field
    for field in ['quality_score_status','quality_score_v4_100','quality_pillars_v4',
                  'quality_tier','verdict','product_safety_status','assessment_readiness','_v4_safety_gate']:
        assert scored_before[field] == scored_after[field], field
    for field in ['warnings','warnings_profile_gated','allergens','ingredients']:
        assert blob_before.get(field) == blob_after.get(field), field
    if blocked:
        assert scored_after['verdict'] == 'BLOCKED'
        assert scored_after['quality_score_status'] == 'suppressed_safety'
    else:
        assert 'cascaroside' in json.dumps(blob_after).lower()
        assert 'RULE_CASCARA_UNRESOLVED_IDENTITY' not in json.dumps(blob_after)

@pytest.mark.parametrize('pid', IDS)
def test_held_core_and_share_publish_no_numeric_quality_or_reassurance(pairs, pid):
    from scoring_v4.scored_artifact import assemble_scored_artifact
    from build_final_db import build_detail_blob, build_core_row, generate_share_metadata
    from core_export_model import PRODUCTS_CORE_COLUMNS
    enriched, v4 = pairs[pid]
    scored = assemble_scored_artifact(enriched, deepcopy(v4))
    blob = build_detail_blob(enriched, scored)
    row = dict(zip(PRODUCTS_CORE_COLUMNS, build_core_row(enriched, scored, '2026-10-29', detail_blob=blob), strict=True))
    for field in ['quality_score_v4_100','score_100_equivalent','grade','quality_tier',
                  'pillar_formulation_v4','pillar_dose_v4','pillar_evidence_v4',
                  'pillar_transparency_v4','pillar_verification_v4','pillar_safety_hygiene_v4']:
        assert row[field] is None, field
    assert row['score_display_100_equivalent'] in [None,'N/A']
    assert row['verdict']=='NOT_SCORED'
    assert row['quality_score_status']=='not_scored'
    assert row['score_unavailable_reason']
    assert 'Quality score unavailable' in json.loads(row['decision_highlights'])['positive']
    assert blob['label_record']['source_record_id']==pid
    share = generate_share_metadata(enriched, scored)
    assert 'Quality score unavailable' in share['share_description']
    assert 'Clinically-backed ingredients' not in share['share_highlights']
    assert not any('Premium' in h for h in share['share_highlights'])
    assert 'RULE_CASCARA_UNRESOLVED_IDENTITY' not in json.dumps(blob.get('warning_rule_refs'))
