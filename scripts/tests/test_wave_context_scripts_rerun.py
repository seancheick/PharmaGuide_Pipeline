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
    ('bc30_functional_gi_complaints_40707016', 'population', {'age_group': 'child', 'description': 'Children'}),
    ('bc30_functional_gi_complaints_40707016', 'dose', {'unit': 'mg', 'values': [2000]}),
    ('lp299v_ibs_meta_37541528', 'limitations', ['High certainty; independent replication established.']),
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
