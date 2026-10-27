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
    monkeypatch.setattr(verifier, 'fetch_articles', lambda ids, **kwargs: {'1': {
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
    monkeypatch.setattr(verifier, 'fetch_articles', lambda ids, **kwargs: {'14521988': {
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


@pytest.fixture
def audit_source(tmp_path, monkeypatch):
    path = tmp_path / 'literature.json'
    path.write_text(json.dumps({'_metadata': {}, 'literature_evidence_records': [
        {'canonical_id': cid, 'qualifying_human_studies': [{'pmid': pmid, 'title': f'{cid} clinical outcomes'}]}
        for cid, pmid in [('melon', '1'), ('cherry', '2')]
    ]}))
    monkeypatch.setattr(verifier, 'LITERATURE_RECORDS_PATH', path)
    monkeypatch.setattr(verifier, 'fetch_articles', lambda ids, **kwargs: {
        p: {'title': f'{dict([( "1", "melon"), ("2", "cherry")])[p]} clinical outcomes',
            'abstract': 'Participants received treatment.', 'mesh_terms': ['Humans']}
        for p in ids
    })
    return path


def test_default_audit_never_changes_source(audit_source):
    before = audit_source.read_bytes()
    report = verifier.verify_literature_file()
    assert audit_source.read_bytes() == before
    assert report['mode'] == 'read_only'


def test_selected_records_and_unknown_ids_fail_closed(audit_source):
    report = verifier.verify_literature_file(record_ids={'melon'})
    assert report['records_checked'] == 1
    assert report['studies_checked'] == 1
    assert [r['canonical_id'] for r in report['records']] == ['melon']
    with pytest.raises(ValueError, match='Unknown'):
        verifier.verify_literature_file(record_ids={'typo'})


def test_cli_default_read_only_report_and_selection(audit_source, tmp_path):
    before = audit_source.read_bytes()
    report = tmp_path / 'report.json'
    assert verifier.main(['--record-id', 'melon', '--report', str(report)]) == 0
    assert audit_source.read_bytes() == before
    result = json.loads(report.read_text())
    assert result['records_checked'] == 1
    assert result['clinical_applicability_verified'] is False


def test_retracted_publication_type_blocks_verification(audit_source, monkeypatch):
    monkeypatch.setattr(verifier, 'fetch_articles', lambda ids, **kw: {
        '1': {'title': 'melon clinical outcomes', 'abstract': 'Melon effects.',
              'mesh_terms': ['Humans'], 'publication_types': ['Retracted Publication']}})
    report = verifier.verify_literature_file(record_ids={'melon'})
    assert report['retractions_count'] == 1


def test_unresolved_title_search_is_not_applied(audit_source, monkeypatch):
    before = audit_source.read_bytes()
    monkeypatch.setattr(verifier, 'fetch_articles', lambda ids, **kw: {})
    # No speculative title-search replacement is permitted.
    report = verifier.verify_literature_file(record_ids={'melon'})
    assert report['verification_failures_count'] > 0
    assert audit_source.read_bytes() == before


def test_empty_studies_are_not_verified(audit_source):
    data = json.loads(audit_source.read_text())
    data['literature_evidence_records'][0]['qualifying_human_studies'] = []
    audit_source.write_text(json.dumps(data))
    report = verifier.verify_literature_file(record_ids={'melon'})
    assert report['verification_failures_count'] == 1
    assert report['records'][0]['verification_result'] == 'verification_failure_unresolved'


def test_cli_missing_source_fails_and_protects_data(audit_source, monkeypatch):
    monkeypatch.setattr(verifier, 'fetch_articles', lambda *a, **kw: {})
    assert verifier.main(['--record-id', 'melon']) == 1
    before = audit_source.read_bytes()
    with pytest.raises(SystemExit):
        verifier.main(['--report', str(audit_source)])
    assert audit_source.read_bytes() == before


@pytest.mark.parametrize('flag', ['expression_of_concern', 'has_erratum'])
def test_source_notices_require_review(audit_source, monkeypatch, flag):
    monkeypatch.setattr(verifier, 'fetch_articles', lambda *a, **kw: {
        '1': {'title': 'melon clinical outcomes', 'abstract': 'Melon trial',
              'mesh_terms': ['Humans'], flag: True}})
    report = verifier.verify_literature_file(record_ids={'melon'})
    assert any(f['error'] == flag + '_requires_review' for f in report['failures'])


@pytest.mark.parametrize('case', ['missing', 'retracted', 'correction'])
def test_dose_reference_citations_are_read_without_promoting_them_to_clinical_evidence(audit_source, monkeypatch, case):
    data = json.loads(audit_source.read_text())
    data['literature_evidence_records'] = data['literature_evidence_records'][:1]
    data['literature_evidence_records'][0]['reference_semantics'] = {'source_ids': ['PMID:9999']}
    audit_source.write_text(json.dumps(data))
    seen = []
    def fetch(ids, **kwargs):
        seen.extend(ids)
        articles = {'1': {'title': 'melon clinical outcomes', 'abstract': 'Melon intervention.',
                          'mesh_terms': ['Humans']}}
        if case != 'missing':
            articles['9999'] = {'title': 'Melon related preparation study', 'abstract': 'Melon exposure.',
                                'retracted': case == 'retracted', 'has_erratum': case == 'correction'}
        return articles
    monkeypatch.setattr(verifier, 'fetch_articles', fetch)
    before = audit_source.read_bytes()
    result = verifier.verify_literature_file()
    assert '9999' in seen
    assert result['verification_failures_count'] or result['retractions_count']
    assert result['studies_checked'] == 1
    from dose_assessment import verified_reference_citations
    assert not verified_reference_citations(result['records'][0])
    assert result['clinical_applicability_verified'] is False
    assert audit_source.read_bytes() == before


def test_dose_source_proof_is_bound_and_independent_of_empty_trials(audit_source, monkeypatch):
    from dose_assessment import verified_reference_citations
    data = json.loads(audit_source.read_text())
    record = data['literature_evidence_records'][0]
    record['qualifying_human_studies'] = []
    record['reference_semantics'] = {'source_ids': ['PMID:9999'], 'preparation': 'melon'}
    audit_source.write_text(json.dumps(data))
    monkeypatch.setattr(verifier, 'fetch_articles', lambda *a, **kw: {
        '9999': {'title': 'Melon preparation', 'abstract': 'Melon exposure.'}})
    result = verifier.verify_literature_file(record_ids={'melon'})['records'][0]
    assert verified_reference_citations(result)
    assert result['verification_result'] == 'verification_failure_unresolved'
    result['reference_semantics']['preparation'] = 'different preparation'
    assert not verified_reference_citations(result)
    result['verification_provenance'].pop('reference_citations')
    assert not verified_reference_citations(result)


@pytest.mark.parametrize('mutation', ['future', 'missing_result', 'wrong_source', 'changed_binding',
                                      'missing_hash', 'retracted', 'expression_of_concern', 'has_erratum'])
def test_reference_proof_rejects_incomplete_or_stale_dependencies(mutation):
    from dose_assessment import verified_reference_citations
    record = {'canonical_id': 'melon', 'reference_semantics': {'source_ids': ['PMID:9999']}}
    proof = verifier.verify_reference_citations(record, {
        '9999': {'title': 'Melon preparation', 'abstract': 'Melon source.'}}, '2026-01-01T00:00:00+00:00')
    record['verification_provenance'] = {'reference_citations': proof}
    assert verified_reference_citations(record)
    if mutation == 'future': proof['verified_at'] = '2999-01-01T00:00:00+00:00'
    elif mutation == 'missing_result': proof['results'] = []
    elif mutation == 'wrong_source': proof['results'][0]['source_id'] = 'PMID:8888'
    elif mutation == 'changed_binding': record['reference_semantics']['notes'] = 'Changed source interpretation'
    elif mutation == 'missing_hash': proof['results'][0].pop('content_sha256')
    else: proof['results'][0][mutation] = True
    assert not verified_reference_citations(record)


def test_reference_proof_accepts_exact_article_url_but_not_search_url():
    article = {'1': {'title': 'Melon preparation', 'abstract': 'Melon source.'}}
    now = '2026-01-01T00:00:00+00:00'
    exact = {'canonical_id': 'melon', 'reference_semantics': {'source_ids': ['https://pubmed.ncbi.nlm.nih.gov/1/']}}
    assert verifier.verify_reference_citations(exact, article, now)['is_complete']
    exact['reference_semantics']['source_ids'] = ['https://pubmed.ncbi.nlm.nih.gov/?term=melon']
    assert not verifier.verify_reference_citations(exact, article, now)['is_complete']


def test_reference_recheck_preserves_reviewed_scope_only_for_identical_source():
    article = {'1': {'title': 'A specific related preparation', 'abstract': 'No general numerical curve.'}}
    record = {'canonical_id': 'melon', 'reference_semantics': {'source_ids': ['PMID:1']}}
    proof = verifier.verify_reference_citations(record, article, '2026-01-01T00:00:00+00:00')
    assert not proof['is_complete']  # keyword screening cannot establish this relation
    proof['results'][0].update(verified=True, notes='Source content reviewed: nontransferable preparation; Dose only.')
    proof['is_complete'] = True
    record['verification_provenance'] = {'reference_citations': proof}
    assert verifier.verify_reference_citations(record, article, '2026-01-02T00:00:00+00:00')['is_complete']
    article['1']['abstract'] = 'Changed source content.'
    assert not verifier.verify_reference_citations(record, article, '2026-01-02T00:00:00+00:00')['is_complete']


def test_reviewed_correction_is_source_bound_and_never_clears_retraction():
    from dose_assessment import verified_reference_citations
    source = {'1': {'title': 'Melon study', 'has_erratum': True}}
    record = {'canonical_id': 'melon', 'reference_semantics': {'source_ids': ['PMID:1']}}
    proof = verifier.verify_reference_citations(record, source, '2026-01-01T00:00:00+00:00')
    record['verification_provenance'] = {'reference_citations': proof}
    assert not verified_reference_citations(record)
    result = proof['results'][0]
    result.update(verified=True, correction_review={
        'source_sha256': result['content_sha256'], 'source_ids': ['PMID:2'],
        'verified_at': '2026-01-01T00:00:00+00:00', 'reviewed_by': 'Test source reviewer',
        'is_complete': True, 'notes': 'Full notice reviewed: affiliation only; Dose source only.'})
    proof['is_complete'] = True
    assert verified_reference_citations(record)
    assert verifier.verify_reference_citations(record, source, '2026-01-02T00:00:00+00:00')['is_complete']
    result['retracted'] = True
    assert not verified_reference_citations(record)
    result['retracted'] = False
    result['correction_review']['source_sha256'] = '0' * 64
    assert not verified_reference_citations(record)


def test_invalidated_reference_receipt_cannot_self_approve_on_retry():
    from dose_assessment import verified_reference_citations
    article = {'1': {'title': 'Melon study', 'abstract': 'Melon source.'}}
    record = {'canonical_id': 'melon', 'reference_semantics': {'source_ids': ['PMID:1']}}
    record['verification_provenance'] = {'reference_citations': verifier.verify_reference_citations(record, article, '2026-01-01T00:00:00+00:00')}
    assert verified_reference_citations(record)
    article['1']['abstract'] = 'Changed melon source.'
    for _ in range(3):
        record['verification_provenance']['reference_citations'] = verifier.verify_reference_citations(record, article, '2026-01-02T00:00:00+00:00')
        assert not verified_reference_citations(record)


def test_generic_preparation_words_cannot_verify_a_different_ingredient():
    record = {'canonical_id': 'garlic', 'reference_semantics': {
        'source_ids': ['PMID:1'], 'preparation': 'garlic root powder'}}
    proof = verifier.verify_reference_citations(record, {'1': {
        'title': 'Ginger root powder in adults', 'abstract': 'Ginger root supplementation.'}},
        '2026-01-01T00:00:00+00:00')
    assert not proof['is_complete']


@pytest.mark.parametrize('canonical,title', [('red_clover', 'Red wine polyphenols in adults'),
                                             ('black_cohosh', 'Black tea consumption in adults')])
def test_partial_identity_token_cannot_verify_a_different_ingredient(canonical, title):
    record = {'canonical_id': canonical, 'reference_semantics': {'source_ids': ['PMID:1']}}
    assert not verifier.verify_reference_citations(record, {'1': {'title': title}},
                                                   '2026-01-01T00:00:00+00:00')['is_complete']


def test_malformed_prior_results_return_incomplete_proof():
    record = {'canonical_id': 'melon', 'reference_semantics': {'source_ids': ['PMID:1']},
              'verification_provenance': {'reference_citations': {'results': None}}}
    assert not verifier.verify_reference_citations(record, {'1': {'title': 'Melon study'}},
                                                   '2026-01-01T00:00:00+00:00')['is_complete']
