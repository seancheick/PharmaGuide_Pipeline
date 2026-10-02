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
    ('is2_moderate_covid19_adjunct_39866999', 'population', {'age_group': 'adult', 'description': 'B. coagulans UBBC-07'}),
    ('mtcc5856_healthy_microbiome_37335737', 'blinding', 'unreported'),
    ('mtcc5856_functional_gas_bloating_36862903', 'funding', 'industry'),
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
