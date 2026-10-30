"""Exact approved unavailable assessments retain their source and safety, not a score."""
from copy import deepcopy
import json
from pathlib import Path
import pytest

IDS = ['232035','229932','251528','327907','332909','295107','80302','220046']

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

@pytest.mark.parametrize('pid', IDS)
def test_exact_approved_held_label_is_unscored_and_exportable(pairs, pid):
    from scoring_v4.scored_artifact import assemble_scored_artifact
    from build_final_db import validate_export_contract
    enriched, v4 = pairs[pid]
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
