"""Machine source verification cannot promote animal/cell evidence to human trials."""
import json

import pytest

from api_audit import verify_literature_records as verifier


@pytest.mark.parametrize('abstract, mesh, expected', [
    ('Animals received supplementation for 28 days.', ['Animals', 'Mice'], False),
    ('Treatment improved experimental outcomes in rats.', ['animals'], False),
    ('Human blood-derived cells and human chondrosarcoma cells were tested in vitro.', ['Humans', 'Animals', 'Cells, Cultured'], False),
    ('This may benefit patients; experiments used rats.', ['Animals', 'Rats'], False),
    ('Thirty participants were enrolled in a randomized trial.', ['Humans'], True),
    ('Participants received supplementation.', ['Humans'], True),
    ('A randomized trial in adults.', [], False),
])
def test_verifier_requires_indexed_human_population(tmp_path, monkeypatch, abstract, mesh, expected):
    path = tmp_path / 'literature.json'
    title = 'Effects of melon extract'
    path.write_text(json.dumps({'_metadata': {}, 'literature_evidence_records': [{
        'canonical_id': 'melon', 'qualifying_human_studies': [{'pmid': '1', 'title': title}],
    }]}))
    monkeypatch.setattr(verifier, 'LITERATURE_RECORDS_PATH', path)
    monkeypatch.setattr(verifier, 'fetch_articles', lambda ids: {'1': {
        'title': title, 'abstract': abstract, 'mesh_terms': mesh,
    }})
    verifier.verify_literature_file(apply_fixes=True)
    record, = json.loads(path.read_text())['literature_evidence_records']
    study, = record['qualifying_human_studies']
    assert study['verification_provenance']['human_subjects_verified'] is expected
    if not expected:
        assert record['verification_result'] == 'verification_failure_unresolved'


@pytest.mark.parametrize('cid, pmid', [('boswellia_serrata_resin', '32565872'), ('superoxide_dismutase', '15742357')])
def test_retained_animal_citations_do_not_claim_human_verification(cid, pmid):
    payload = json.loads(verifier.LITERATURE_RECORDS_PATH.read_text())
    record = next(r for r in payload['literature_evidence_records'] if r['canonical_id'] == cid)
    study = next(s for s in record['qualifying_human_studies'] if s['pmid'] == pmid)
    assert study['verification_provenance']['human_subjects_verified'] is False
    assert study['scoring_eligible'] is False
    assert record['verification_result'] == 'verification_failure_unresolved'


def test_graviola_lab_source_remains_a_negative_safety_finding():
    payload = json.loads(verifier.LITERATURE_RECORDS_PATH.read_text())
    record = next(r for r in payload['literature_evidence_records'] if r['canonical_id'] == 'graviola')
    study, = record['qualifying_human_studies']
    assert study['verification_provenance']['human_subjects_verified'] is False
    assert record['effect_direction'] == 'negative'
    assert record['applicability_status'] == 'reviewed_null_evidence'
    assert 'toxic to cultured dopaminergic neurons' in record['applicability_decision']


def test_verifier_preserves_reviewed_nonhuman_negative_evidence(tmp_path, monkeypatch):
    payload = json.loads(verifier.LITERATURE_RECORDS_PATH.read_text())
    record = next(r for r in payload['literature_evidence_records'] if r['canonical_id'] == 'graviola')
    path = tmp_path / 'literature.json'
    path.write_text(json.dumps({'_metadata': {}, 'literature_evidence_records': [record]}))
    monkeypatch.setattr(verifier, 'LITERATURE_RECORDS_PATH', path)
    monkeypatch.setattr(verifier, 'fetch_articles', lambda ids: {'14521988': {
        'title': record['qualifying_human_studies'][0]['title'],
        'abstract': 'Annonacin killed cultured mesencephalic neurons.',
        'mesh_terms': ['Animals', 'Cells, Cultured'],
    }})
    verifier.verify_literature_file(apply_fixes=True)
    verified, = json.loads(path.read_text())['literature_evidence_records']
    assert verified['qualifying_human_studies'][0]['verification_provenance']['human_subjects_verified'] is False
    assert verified['verification_result'] == record['verification_result']
    assert verified['applicability_status'] == record['applicability_status']
    assert verified['effect_direction'] == record['effect_direction']
