import json
import pytest
from audits.quality_redesign import replay
from stage_manifest import write_stage_manifest


def corpus(tmp_path, products):
    root = tmp_path / 'products'
    stage = root / 'brand_enriched' / 'enriched'
    stage.mkdir(parents=True)
    source = stage / 'batch.json'
    source.write_text(json.dumps(products))
    write_stage_manifest(stage, 'enrich', [source])
    return root, source


def test_duplicate_ids_rejected(tmp_path):
    root, _ = corpus(tmp_path, [{'id': '1'}, {'id': '1'}])
    with pytest.raises(ValueError, match='Duplicate'):
        replay.freeze(root, tmp_path / 'frozen', tmp_path / 'manifest.json')


def test_missing_ownership_rejected(tmp_path):
    root, source = corpus(tmp_path, [{'id': '1'}])
    (source.parent / '.stage_manifest.json').unlink()
    with pytest.raises(ValueError, match='manifest'):
        replay.freeze(root, tmp_path / 'frozen', tmp_path / 'manifest.json')


def test_mutation_rejected(tmp_path):
    root, source = corpus(tmp_path, [{'id': '1'}])
    frozen, manifest = tmp_path / 'frozen', tmp_path / 'manifest.json'
    replay.freeze(root, frozen, manifest)
    (frozen / source.relative_to(root)).write_text('[]')
    with pytest.raises(ValueError, match='hash|checksum'):
        list(replay.inputs(frozen, manifest))


def test_failed_scorer_preserved():
    def fail(product):
        raise RuntimeError('broken scorer')
    rows = replay.score_records([('batch.json', 'hash', {'id': '1'})], fail)
    assert rows[0]['id'] == '1'
    assert rows[0]['error'] == 'RuntimeError: broken scorer'
    with pytest.raises(ValueError):
        replay.require_success(rows)


def test_empty_success_rejected():
    with pytest.raises(ValueError):
        replay.require_success([])
    with pytest.raises(ValueError):
        replay.require_success(replay.score_records([('batch.json', 'hash', {'id': '1'})], lambda p: {}))


def test_compare_rejects_changed_input():
    a = {'id': '1', 'input_sha256': 'a'}
    with pytest.raises(ValueError, match='input'):
        replay.compare_records([a], [dict(a, input_sha256='b')])


def test_reference_required_pending_and_failed_relation():
    rows = [{'id': '1', 'total': 40}, {'id': '2', 'total': 60}]
    assert replay.check_records(rows, [{'required': True, 'review_status': 'pending'}])
    claim = {'required': True, 'review_status': 'approved', 'left': '1', 'right': '2', 'field': 'total', 'relation': 'gt'}
    assert replay.check_records(rows, [claim])
    claim['relation'] = 'lt'
    assert replay.check_records(rows, [claim]) == []


@pytest.mark.parametrize('workers', [1, 2])
def test_snapshot_child_uses_selected_checkout_and_keeps_failure(tmp_path, workers):
    from types import SimpleNamespace
    root, _ = corpus(tmp_path, [{'id': '1'}, {'id': '2'}])
    manifest = tmp_path / 'manifest.json'
    frozen = tmp_path / 'frozen'
    replay.freeze(root, frozen, manifest)
    checkout = tmp_path / 'checkout'
    (checkout / 'scripts').mkdir(parents=True)
    (checkout / 'scripts/score_supplements_v4.py').write_text('''
def score_product_v4(product):
    if product['id'] == '2':
        raise RuntimeError('intentional failure')
    return {'quality_score_status': 'not_scored', 'v4_module': 'fixture'}
''')
    import subprocess, sys
    out = tmp_path / 'out.jsonl'
    proc = subprocess.run([sys.executable, replay.__file__, '_worker', '--checkout', str(checkout), '--products-root', str(frozen), '--manifest', str(manifest), '--out', str(out), '--workers', str(workers)], capture_output=True, text=True)
    assert proc.returncode != 0
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert [row['id'] for row in rows] == ['1', '2']
    assert rows[0]['route'] == 'fixture'
    assert rows[1]['error'] == 'RuntimeError: intentional failure'


def test_missing_product_in_comparison_rejected():
    a = {'id': '1', 'input_sha256': 'a'}
    with pytest.raises(ValueError, match='IDs'):
        replay.compare_records([a], [dict(a, id='2')])


def test_empty_reference_set_never_passes():
    assert replay.check_records([{'id': '1'}], [])
    with pytest.raises(ValueError):
        replay.check_records([], [])


@pytest.mark.parametrize('value', [None, True, False, float('nan'), float('inf'), float('-inf'), '10'])
def test_required_numeric_relation_rejects_nonfinite_or_non_numeric(value):
    rows = [{'id': '1', 'total': value}, {'id': '2', 'total': value}]
    claim = {'required': True, 'review_status': 'approved', 'left': '1', 'right': '2', 'field': 'total', 'relation': 'eq'}
    assert replay.check_records(rows, [claim])


def test_generic_subroute_uses_dimension_profile():
    record = {'route': 'generic', 'pillars': {'formulation': {'components': {'archetype': 'generic_botanical_branded', 'formulation_profile': 'collagen'}}}, 'reasons': {'module': {'dimensions': {'formulation': {'metadata': {'formulation_profile': 'collagen'}}}}}}
    assert replay.captured_subroute(record) == 'collagen'


def test_malformed_scorer_payload_remains_failed_product():
    rows = replay.score_records([('batch.json', 'hash', {'id': '1'})], lambda p: {'quality_score_status': 'scored', 'v4_breakdown': {'module': []}})
    assert rows[0]['id'] == '1'
    assert 'error' in rows[0]


def test_reprojection_retains_raw_hash_and_matches_fresh_capture(tmp_path):
    result = {'quality_score_status': 'scored', 'quality_score_v4_100': 50, 'v4_module': 'generic', 'v4_breakdown': {'module': {'dimensions': {'formulation': {'metadata': {'formulation_profile': 'collagen'}}}}}}
    fresh = replay.score_records([('batch.json', 'hash', {'id': '1'})], lambda p: result)[0]
    old = dict(fresh, subroute='generic_botanical_branded')
    old.pop('subtype')
    old.pop('formulation_profile')
    out = tmp_path / 'snapshot.jsonl'
    out.write_text(json.dumps(old) + '\n')
    original_hash = replay.sha(out)
    replay.write_json(str(out) + '.meta.json', {'exit_code': 0, 'source_unchanged': True, 'output_sha256': original_hash, 'product_count': 1, 'expected_product_count': 1})
    replay.reproject(out)
    metadata = json.loads((tmp_path / 'snapshot.jsonl.meta.json').read_text())
    assert metadata['projection']['raw_sha256'] == original_hash
    assert replay.sha(metadata['projection']['raw_capture']) == original_hash
    assert replay.read_rows(out) == [fresh]


def test_capture_reader_rejects_missing_receipt_and_truncation(tmp_path):
    out = tmp_path / 'snapshot.jsonl'
    out.write_text(json.dumps({'id': '1'}) + '\n' + json.dumps({'id': '2'}) + '\n')
    with pytest.raises(FileNotFoundError):
        replay.read_rows(out)
    replay.write_json(str(out) + '.meta.json', {'exit_code': 0, 'source_unchanged': True, 'output_sha256': replay.sha(out), 'product_count': 2, 'expected_product_count': 2})
    out.write_text(json.dumps({'id': '1'}) + '\n')
    with pytest.raises(ValueError, match='hash'):
        replay.read_rows(out)
    metadata = json.loads((tmp_path / 'snapshot.jsonl.meta.json').read_text())
    metadata['output_sha256'] = replay.sha(out)
    replay.write_json(str(out) + '.meta.json', metadata)
    with pytest.raises(ValueError, match='count'):
        replay.read_rows(out)


def test_provenance_includes_nested_production_package(tmp_path):
    import subprocess
    checkout = tmp_path / 'checkout'
    (checkout / 'scripts/identity').mkdir(parents=True)
    source = checkout / 'scripts/identity/safety.py'
    source.write_text('VALUE = 1\n')
    subprocess.run(['git', 'init', str(checkout)], check=True, capture_output=True)
    subprocess.run(['git', '-C', str(checkout), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '--allow-empty', '-m', 'fixture'], check=True, capture_output=True)
    before = replay.repository_provenance(checkout)
    source.write_text('VALUE = 2\n')
    after = replay.repository_provenance(checkout)
    assert before['source_sha256']['scripts/identity/safety.py'] != after['source_sha256']['scripts/identity/safety.py']
