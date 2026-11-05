"""The documented Wave 2 curation command stays safe to rerun after later dispositions.

``wave2_contexts.py`` is a one-shot migration whose rerun verifies the
materialized rows instead of appending duplicates. Source-bound dispositions
(``apply_batch1_disposition.py``) later patch individual fields of some Wave 2
rows; the rerun must accept exactly those declared patches and nothing else.
"""
import subprocess
import sys

import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/audits/probiotic_curation_queue_2026_09_13/wave2_contexts.py"
REGISTRY = ROOT / "scripts/data/clinically_relevant_strains.json"


def test_wave2_contexts_rerun_verifies_patched_rows_without_writing():
    before = REGISTRY.read_bytes()
    result = subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "Wave 2 already applied; verified 59 contexts; no changes written" in result.stdout
    assert REGISTRY.read_bytes() == before


@pytest.mark.parametrize('context_id,field,bad_value', [
    ('is2_adult_ibs_multicenter_31434935', 'authoring_method', 'Unattributed hierarchy correction'),
    ('is2_adult_ibs_multicenter_31434935', 'outcomes', [
        {'name': 'abdominal_pain_and_discomfort', 'hierarchy': 'primary', 'kind': 'patient_important', 'direction': 'positive'},
        {'name': 'complete_spontaneous_bowel_movements', 'hierarchy': 'primary', 'kind': 'patient_important', 'direction': 'positive'},
        {'name': 'serum_cytokines', 'hierarchy': 'primary', 'kind': 'surrogate', 'direction': 'null'},
    ]),
    ('bc30_functional_gi_complaints_40707016', 'population', {'age_group': 'child', 'description': 'Children'}),
    ('bc30_functional_gi_complaints_40707016', 'dose', {'unit': 'mg', 'values': [2000]}),
    ('bc30_functional_gi_complaints_40707016', 'clinical_review', {
        'reviewer': 'Dr. Pham', 'reviewed_at': '2026-09-14',
        'scope': 'identity_dose_outcome_applicability',
    }),
    ('bc30_functional_gi_complaints_40707016', 'outcomes', [
        {'name': 'upper_gi_dyspepsia_heartburn_reflux_nausea_SODA',
         'hierarchy': 'primary', 'kind': 'patient_important', 'direction': 'positive'},
    ]),
    ('bc30_functional_gi_complaints_40707016', 'notes', 'Broad approval for all gastrointestinal conditions.'),
    ('lp299v_ibs_meta_37541528', 'limitations', ['High certainty; independent replication established.']),
    ('lp299v_iron_absorption_meta_31816981', 'population', {'age_group': 'adult', 'description': '8 studies with 950 absorption participants'}),
    ('lp299v_cancer_home_enteral_nutrition_33015813', 'outcomes', [{'name': 'vomiting', 'hierarchy': 'primary', 'kind': 'patient_important', 'direction': 'positive'}]),
    ('lp299v_exam_stress_cortisol_28101105', 'outcomes', [{'name': 'salivary_cortisol_rise_prevention', 'hierarchy': 'primary', 'kind': 'patient_important', 'direction': 'positive'}]),
    ('is2_moderate_covid19_adjunct_39866999', 'population', {'age_group': 'adult', 'description': 'B. coagulans UBBC-07'}),
    ('mtcc5856_healthy_microbiome_37335737', 'blinding', 'unreported'),
    ('mtcc5856_functional_gas_bloating_36862903', 'funding', 'industry'),
    ('lgg_bb12_preterm_administration_route_37020105', 'limitations', ['Route-comparison design without placebo']),
    ('lgg_bb12_preterm_administration_route_37020105', 'sample_size', 54),
    ('lgg_bb12_preterm_administration_route_37020105', 'source_pmids', ['33811784']),
    ('m16v_synbiotic_formula_csection_39915586', 'sample_size', 284),
    ('m16v_synbiotic_formula_csection_39915586', 'comparator', 'prebiotic-only formula'),
    ('m16v_neonatal_jaundice_adjunct_41994268', 'outcomes', [
        {'name': 'defecation_frequency', 'hierarchy': 'unresolved', 'kind': 'surrogate', 'direction': 'positive'},
        {'name': 'transcutaneous_bilirubin_decline', 'hierarchy': 'unresolved', 'kind': 'surrogate', 'direction': 'positive'},
        {'name': 'hospital_stay_duration', 'hierarchy': 'unresolved', 'kind': 'patient_important', 'direction': 'positive'},
    ]),
])
def test_wave2_rerun_rejects_drift_in_corrected_source_facts(tmp_path, monkeypatch, context_id, field, bad_value):
    import importlib.util
    import json
    spec = importlib.util.spec_from_file_location('wave2_rerun_guard', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    data = json.loads(REGISTRY.read_text())
    context = next(c for e in data['clinically_relevant_strains'] for c in e.get('study_contexts', []) if c['context_id'] == context_id)
    context[field] = bad_value
    scratch = tmp_path / 'registry.json'
    scratch.write_text(json.dumps(data))
    before = scratch.read_bytes()
    monkeypatch.setattr(module, 'REG', scratch)
    with pytest.raises(AssertionError, match=context_id):
        module.main()
    assert scratch.read_bytes() == before


@pytest.mark.parametrize('version', ['2.4.0', '2.4.1', '2.5.0'])
def test_materialized_wave2_uses_read_only_verification_after_later_registry_versions(tmp_path, monkeypatch, version):
    import importlib.util
    import json
    spec = importlib.util.spec_from_file_location('wave2_later_registry_guard', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    data = json.loads(REGISTRY.read_text())
    data['_metadata']['version'] = version
    scratch = tmp_path / 'registry.json'
    scratch.write_text(json.dumps(data))
    before = scratch.read_bytes()
    monkeypatch.setattr(module, 'REG', scratch)
    def reject_write(*args, **kwargs):
        raise AssertionError('materialized Wave 2 must not write registry data')
    monkeypatch.setattr(Path, 'write_text', reject_write)
    module.main()
    assert scratch.read_bytes() == before


def test_wave2_rerun_retains_prior_bc30_regimen_disposition(tmp_path, monkeypatch):
    import importlib.util
    import json
    from copy import deepcopy
    spec = importlib.util.spec_from_file_location('wave2_prior_bc30_guard', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    data = json.loads(REGISTRY.read_text())
    context_id = 'bc30_functional_gi_complaints_40707016'
    prior = deepcopy(next(row for owner, row in module.CONTEXTS if row['context_id'] == context_id))
    for field_path, value in module._declared_disposition_patches()[context_id]:
        module._write_path_appending(prior, field_path, value)
    current = next(c for e in data['clinically_relevant_strains']
                   for c in e.get('study_contexts', []) if c['context_id'] == context_id)
    for field in module.OWNER_DECISION_FIELDS:
        if field in current:
            prior[field] = deepcopy(current[field])
    for entry in data['clinically_relevant_strains']:
        entry['study_contexts'] = [prior if c['context_id'] == context_id else c
                                   for c in entry.get('study_contexts', [])]
    scratch = tmp_path / 'registry.json'
    scratch.write_text(json.dumps(data))
    before = scratch.read_bytes()
    monkeypatch.setattr(module, 'REG', scratch)
    def reject_write(*args, **kwargs):
        raise AssertionError('read-only rerun must preserve the prior disposition')
    monkeypatch.setattr(Path, 'write_text', reject_write)
    module.main()
    assert scratch.read_bytes() == before


@pytest.mark.parametrize('hierarchy', ['unresolved', 'secondary'])
def test_wave2_rerun_preserves_original_and_source_qualified_is2_hierarchy(tmp_path, monkeypatch, hierarchy):
    import importlib.util
    import json
    spec = importlib.util.spec_from_file_location('wave2_is2_hierarchy_guard', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    data = json.loads(REGISTRY.read_text())
    context = next(c for e in data['clinically_relevant_strains'] for c in e.get('study_contexts', [])
                   if c['context_id'] == 'is2_adult_ibs_multicenter_31434935')
    next(o for o in context['outcomes'] if o['name'] == 'serum_cytokines')['hierarchy'] = hierarchy
    if hierarchy == 'unresolved':
        context['authoring_method'] = next(row['authoring_method'] for _, row in module.CONTEXTS
                                           if row['context_id'] == context['context_id'])
    scratch = tmp_path / 'registry.json'
    scratch.write_text(json.dumps(data))
    before = scratch.read_bytes()
    monkeypatch.setattr(module, 'REG', scratch)
    module.main()
    assert scratch.read_bytes() == before


@pytest.mark.parametrize('context_id,source_url,locator', [
    ('is2_adult_ibs_multicenter_31434935', 'https://pmc.ncbi.nlm.nih.gov/articles/PMC6704184/',
     'Efficacy and safety measurement criteria'),
    ('p299v_ibs_rome3_22912552', 'https://www.wjgnet.com/1007-9327/full/v18/i30/4012.htm',
     'Assessments and study endpoints'),
])
def test_hierarchy_corrections_retain_specific_factual_review_trail(context_id, source_url, locator):
    import json
    data = json.loads(REGISTRY.read_text())
    context = next(c for e in data['clinically_relevant_strains'] for c in e.get('study_contexts', [])
                   if c['context_id'] == context_id)
    trail = context['authoring_method']
    for fact in ('2026-11-05', 'Codex agent', source_url, locator,
                 'COMPLETION_TRUTH_RECEIPTS_20261105.md', 'original clinical approval unchanged'):
        assert fact in trail
