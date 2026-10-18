"""replay.py `snapshot --full [--blob]` and the record-level `compare` (AUDIT 2026-10-17 F.3).

Whole cleaned / enriched / scored / blob records are hashed without their clock stamps, kept
under <out>.records/, and compare names the changed record and its first differing JSON path.
The score-only capture (no --full) is covered by test_quality_redesign_replay.py and must not move.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import pytest
from audits.quality_redesign import replay
from stage_manifest import write_stage_manifest

HARNESS = replay.__file__


def test_volatile_field_list_is_exactly_the_documented_one():
    assert {stage: sorted(paths) for stage, paths in replay.VOLATILE_FIELDS.items()} == {
        'cleaned': ['metadata.lastCleaned'],
        'enriched': ['enriched_date', 'enrichment_metadata.generated_at', 'match_ledger.generated_at'],
        'scored': ['scoring_metadata.scored_date'],
        'blob': [],
    }
    assert all(isinstance(reason, str) and reason for paths in replay.VOLATILE_FIELDS.values() for reason in paths.values())
    assert replay.FULL_WORKER_ENV == {'PYTHONHASHSEED': '0'}


def test_hash_ignores_only_the_clock_stamps_and_leaves_absent_paths_alone():
    record = {'id': '1', 'enriched_date': 'T1', 'enrichment_metadata': {'generated_at': 'T1', 'enrichment_version': '3'},
              'match_ledger': {'generated_at': 'T1', 'rows': [1]}, 'ingredient_quality_data': {'ingredients': [{'name': 'zinc'}]}}
    restamped = json.loads(json.dumps(record).replace('T1', 'T2'))
    assert replay.record_hash(record, 'enriched') == replay.record_hash(restamped, 'enriched')
    changed = json.loads(json.dumps(record))
    changed['ingredient_quality_data']['ingredients'][0]['name'] = 'zinc picolinate'
    assert replay.record_hash(changed, 'enriched') != replay.record_hash(record, 'enriched')
    assert record['enriched_date'] == 'T1'  # the input is not edited
    assert replay.without_volatile({'id': '1'}, 'enriched') == {'id': '1'}
    assert replay.without_volatile({'metadata': 'not a dict'}, 'cleaned') == {'metadata': 'not a dict'}
    assert replay.record_hash({'a': 1, 'b': 2}, 'blob') == replay.record_hash({'b': 2, 'a': 1}, 'blob')
    assert replay.record_hash({'a': 1}, 'blob') != replay.record_hash({'a': 1.0}, 'blob')


def test_full_rows_are_the_score_only_rows_plus_hashes_and_records_are_kept():
    result = {'quality_score_status': 'scored', 'quality_score_v4_100': 50, 'v4_module': 'generic', 'v4_breakdown': {}}
    stages = {'cleaned': {'id': '1', 'metadata': {'lastCleaned': 'T'}}, 'enriched': {'id': '1', 'enriched_date': 'T'}, 'scored': {'quality_score_v4_100': 50}}
    rows = [('A/1.json', 'hash', {'id': '1', 'fullName': 'One'})]
    plain = replay.score_records(rows, lambda p: result)[0]
    kept = {}
    full = replay.score_records(rows, lambda p: (result, stages), kept.__setitem__)[0]
    assert full.pop('hashes') == {stage: replay.record_hash(value, stage) for stage, value in stages.items()}
    assert full == plain
    assert kept == {'1': stages}


def test_full_capture_keeps_a_failed_product_with_its_error():
    def broken(product):
        raise RuntimeError('enricher down')
    rows = replay.score_records([('A/1.json', 'h', {'id': '1'})], broken, lambda pid, stages: None)
    assert rows[0]['error'] == 'RuntimeError: enricher down' and 'hashes' not in rows[0]


@pytest.mark.parametrize('left,right,expected', [
    ({'a': {'b': [1, {'c': 'x'}]}}, {'a': {'b': [1, {'c': 'y'}]}}, {'path': '$.a.b[1].c', 'baseline': '"x"', 'candidate': '"y"'}),
    ({'a': 1}, {'a': 1, 'z': 2}, {'path': '$.z', 'baseline': '<absent>', 'candidate': '2'}),
    ({'a': [1, 2]}, {'a': [1, 2, 3]}, {'path': '$.a', 'baseline': '2 items', 'candidate': '3 items'}),
    ({'a': [1, 2]}, {'a': [1, 3, 4]}, {'path': '$.a[1]', 'baseline': '2', 'candidate': '3'}),
    ({'a': 1}, {'a': 1.0}, {'path': '$.a', 'baseline': '1', 'candidate': '1.0'}),
    ({'a': True}, {'a': 1}, {'path': '$.a', 'baseline': 'true', 'candidate': '1'}),
    ({'b': 1, 'a': {}}, {'b': 2, 'a': []}, {'path': '$.a', 'baseline': '{}', 'candidate': '[]'}),
])
def test_first_difference_names_the_first_path_in_sorted_key_order(left, right, expected):
    assert replay.first_difference(left, right) == expected


def test_first_difference_is_none_for_equal_values_including_nan_and_bounds_long_values():
    assert replay.first_difference({'a': float('nan'), 'b': [1]}, {'a': float('nan'), 'b': [1]}) is None
    found = replay.first_difference({'a': 'x' * 1000}, {'a': 'y' * 1000})
    assert len(found['baseline']) < 300 and found['baseline'].endswith('... (1002 chars)')


def _full_row(pid, stages):
    return {'id': pid, 'input_sha256': 'h' + pid, 'total': 50.0, 'hashes': {stage: replay.record_hash(value, stage) for stage, value in stages.items()}}


def _store(tmp_path, name, products):
    directory = tmp_path / f'{name}.jsonl.records'
    keep = replay.keep_records(directory)
    rows = []
    for pid, stages in products.items():
        keep(pid, stages)
        rows.append(_full_row(pid, stages))
    return rows, directory


def test_compare_names_the_changed_record_and_first_differing_path(tmp_path):
    base = {'cleaned': {'id': '1', 'metadata': {'lastCleaned': 'T1'}}, 'scored': {'quality_score_v4_100': 50}, 'blob': {'dsld_id': '1'},
            'enriched': {'id': '1', 'enriched_date': 'T1', 'ingredient_quality_data': {'ingredients': [{'name': 'zinc', 'amount': 10}]}}}
    cand = json.loads(json.dumps(base).replace('T1', 'T2'))
    cand['enriched']['ingredient_quality_data']['ingredients'][0]['name'] = 'zinc picolinate'
    control = {'cleaned': {'id': '2'}, 'enriched': {'id': '2', 'enriched_date': 'T1'}, 'scored': {}, 'blob': {}}
    b_rows, b_dir = _store(tmp_path, 'base', {'1': base, '2': control})
    c_rows, c_dir = _store(tmp_path, 'cand', {'1': cand, '2': json.loads(json.dumps(control).replace('T1', 'T2'))})
    diffs = replay.compare_records(b_rows, c_rows, (b_dir, c_dir))
    assert [d['id'] for d in diffs] == ['1']  # the restamped control is not a difference
    assert diffs[0]['changed'] == ['enriched']
    assert diffs[0]['first_difference'] == {'enriched': {'path': '$.ingredient_quality_data.ingredients[0].name', 'baseline': '"zinc"', 'candidate': '"zinc picolinate"'}}
    assert diffs[0]['baseline'] == b_rows[0] and diffs[0]['candidate'] == c_rows[0]


def test_compare_rejects_a_stored_record_that_does_not_match_its_hash(tmp_path):
    stages = {'cleaned': {'id': '1'}, 'enriched': {'id': '1', 'x': 1}, 'scored': {}}
    b_rows, b_dir = _store(tmp_path, 'base', {'1': stages})
    c_rows, c_dir = _store(tmp_path, 'cand', {'1': {**stages, 'enriched': {'id': '1', 'x': 2}}})
    replay.keep_records(c_dir)('1', stages)  # the stored candidate record no longer matches its row
    with pytest.raises(ValueError, match='does not match its snapshot hash'):
        replay.compare_records(b_rows, c_rows, (b_dir, c_dir))
    with pytest.raises(ValueError, match='different records'):
        replay.compare_records(b_rows, [dict(c_rows[0], hashes={'scored': 'x'})], (b_dir, c_dir))


def test_compare_without_records_keeps_the_score_only_output_shape():
    a = {'id': '1', 'input_sha256': 'a', 'total': 50}
    b = dict(a, total=51)
    assert replay.compare_records([a], [b]) == [{'id': '1', 'baseline': a, 'candidate': b}]
    assert replay.compare_records([a], [dict(a)]) == []


ENRICHER = '''from datetime import datetime
class SupplementEnricherV3:
    def enrich_product(self, product):
        product["safety_flags"] = []  # the real enricher edits its input in place
        product.pop("metadata")  # and drops Clean's metadata block (enrich_supplements_v3 `enriched.pop("metadata", None)`)
        now = datetime.now().isoformat()
        rows = [{"name": product["fullName"].lower() + "SUFFIX"}]
        return {**product, "enriched_date": now, "enrichment_metadata": {"generated_at": now},
                "match_ledger": {"generated_at": now}, "ingredient_quality_data": {"ingredients": rows}}, {}
'''


def fake_checkout(tmp_path, ingredient_suffix=''):
    """A checkout whose stage modules stamp the clock like the real ones and read nothing else."""
    checkout = tmp_path / 'checkout'
    scripts = checkout / 'scripts'
    (scripts / 'scoring_v4').mkdir(parents=True, exist_ok=True)
    (scripts / 'enhanced_normalizer.py').write_text(
        'from datetime import datetime\nclass EnhancedDSLDNormalizer:\n    def normalize_product(self, label):\n'
        '        return {**label, "metadata": {"lastCleaned": datetime.now().isoformat(), "cleaningVersion": "fixture"}}\n')
    (scripts / 'enrich_supplements_v3.py').write_text(ENRICHER.replace('SUFFIX', ingredient_suffix))
    (scripts / 'score_supplements_v4.py').write_text(
        'def score_product_v4(product):\n    assert "enriched_date" in product\n'
        '    return {"quality_score_status": "scored", "quality_score_v4_100": 50.0, "v4_module": "fixture"}\n')
    (scripts / 'scoring_v4' / '__init__.py').write_text('')
    (scripts / 'scoring_v4' / 'scored_artifact.py').write_text(
        'from datetime import datetime\nfrom score_supplements_v4 import score_product_v4\n'
        'def build_scored_artifact(enriched):\n'
        '    return {**score_product_v4(enriched), "dsld_id": str(enriched["id"]), "scoring_metadata": {"scored_date": datetime.now().isoformat()}}\n')
    (scripts / 'build_final_db.py').write_text(
        'def build_detail_blob(enriched, scored):\n'
        '    return {"dsld_id": scored["dsld_id"], "name": enriched["fullName"], "quality_score_v4_100": scored["quality_score_v4_100"]}\n')
    if not (checkout / '.git').exists():
        subprocess.run(['git', 'init', str(checkout)], check=True, capture_output=True)
        subprocess.run(['git', '-C', str(checkout), '-c', 'user.name=T', '-c', 'user.email=t@example.invalid', 'commit', '--allow-empty', '-m', 'fixture'], check=True, capture_output=True)
    return checkout


def frozen_labels(tmp_path):
    root = tmp_path / 'raw'
    (root / 'A').mkdir(parents=True)
    for pid, name in ((1, 'One'), (2, 'Two')):
        (root / 'A' / f'{pid}.json').write_text(json.dumps({'id': pid, 'fullName': name}))
    frozen, manifest = tmp_path / 'frozen', tmp_path / 'manifest.json'
    replay.freeze_raw(root, [1, 2], frozen, manifest)
    return frozen, manifest


def compare_cli(baseline, candidate, out):
    proc = subprocess.run([sys.executable, HARNESS, 'compare', '--baseline', str(baseline), '--candidate', str(candidate), '--out', str(out)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return json.loads(Path(out).read_text()), json.loads(proc.stderr.strip().splitlines()[-1])


@pytest.mark.parametrize('workers', [1, 2])
def test_full_snapshot_hashes_every_stage_and_two_runs_agree(tmp_path, workers):
    checkout = fake_checkout(tmp_path)
    frozen, manifest = frozen_labels(tmp_path)
    outs = [tmp_path / 'one.jsonl', tmp_path / 'two.jsonl']
    for out in outs:
        replay.snapshot(checkout, frozen, manifest, out, workers, full=True, blob=True)
    rows = replay.read_rows(outs[0])
    assert [(r['id'], r['total'], r['route']) for r in rows] == [('1', 50.0, 'fixture'), ('2', 50.0, 'fixture')]
    assert set(rows[0]['hashes']) == {'cleaned', 'enriched', 'scored', 'blob'}
    records = replay.load_records(replay.records_dir(outs[0]), '1')
    assert 'safety_flags' not in records['cleaned'] and records['enriched']['safety_flags'] == []  # Clean's own record, not the enricher's edit
    assert records['enriched']['ingredient_quality_data'] == {'ingredients': [{'name': 'one'}]}
    assert records['blob'] == {'dsld_id': '1', 'name': 'One', 'quality_score_v4_100': 50.0}
    assert all(replay.record_hash(records[stage], stage) == rows[0]['hashes'][stage] for stage in rows[0]['hashes'])
    second = replay.load_records(replay.records_dir(outs[1]), '1')
    assert second['enriched']['enriched_date'] != records['enriched']['enriched_date']  # stamps moved, rows did not
    assert replay.read_rows(outs[1]) == rows
    meta = json.loads(Path(str(outs[0]) + '.meta.json').read_text())
    assert meta['full'] == {'blob': True, 'records_dir': str(replay.records_dir(outs[0])), 'volatile_fields': replay.VOLATILE_FIELDS,
                            'worker_env': {'PYTHONHASHSEED': '0'}, 'harness_sha256': replay.sha(HARNESS)}
    assert compare_cli(outs[0], outs[1], tmp_path / 'delta.json') == ([], {'products': 2, 'changed': 0, 'by_record': {}})


def test_full_compare_reports_the_changed_record_and_path_for_an_enricher_change(tmp_path):
    frozen, manifest = frozen_labels(tmp_path)
    checkout = fake_checkout(tmp_path)
    base = tmp_path / 'base.jsonl'
    replay.snapshot(checkout, frozen, manifest, base, 1, full=True, blob=True)
    fake_checkout(tmp_path, ingredient_suffix=' (changed)')  # only the enricher module changes
    cand = tmp_path / 'cand.jsonl'
    replay.snapshot(checkout, frozen, manifest, cand, 1, full=True, blob=True)
    diffs, summary = compare_cli(base, cand, tmp_path / 'delta.json')
    assert [(d['id'], d['changed']) for d in diffs] == [('1', ['enriched']), ('2', ['enriched'])]
    assert diffs[0]['first_difference'] == {'enriched': {'path': '$.ingredient_quality_data.ingredients[0].name', 'baseline': '"one"', 'candidate': '"one (changed)"'}}
    assert summary == {'products': 2, 'changed': 2, 'by_record': {'enriched': 2}}
    plain = tmp_path / 'plain.jsonl'
    replay.snapshot(checkout, frozen, manifest, plain, 1)
    proc = subprocess.run([sys.executable, HARNESS, 'compare', '--baseline', str(base), '--candidate', str(plain), '--out', str(tmp_path / 'x.json')], capture_output=True, text=True)
    assert proc.returncode == 1 and 'both be --full' in proc.stderr
    meta_path = Path(str(cand) + '.meta.json')
    meta = json.loads(meta_path.read_text())
    meta['full']['volatile_fields'] = {**meta['full']['volatile_fields'], 'blob': {'generated_at': 'from an older harness'}}
    meta_path.write_text(json.dumps(meta))
    proc = subprocess.run([sys.executable, HARNESS, 'compare', '--baseline', str(base), '--candidate', str(cand), '--out', str(tmp_path / 'y.json')], capture_output=True, text=True)
    assert proc.returncode == 1 and 'volatile_fields' in proc.stderr and not (tmp_path / 'y.json').exists()


def test_score_only_capture_has_no_hashes_records_or_full_receipt(tmp_path):
    checkout = fake_checkout(tmp_path)
    frozen, manifest = frozen_labels(tmp_path)
    out = tmp_path / 'plain.jsonl'
    replay.snapshot(checkout, frozen, manifest, out, 1)
    rows = replay.read_rows(out)
    assert [r['total'] for r in rows] == [50.0, 50.0] and all('hashes' not in r for r in rows)
    assert not replay.records_dir(out).exists()
    assert 'full' not in json.loads(Path(str(out) + '.meta.json').read_text())


def test_full_mode_refusals(tmp_path):
    frozen, manifest = frozen_labels(tmp_path)
    checkout = fake_checkout(tmp_path)
    out = tmp_path / 'out.jsonl'
    replay.snapshot(checkout, frozen, manifest, out, 1, full=True)
    worker = [sys.executable, HARNESS, '_worker', '--checkout', str(checkout), '--products-root', str(frozen), '--manifest', str(manifest), '--out', str(out)]
    proc = subprocess.run(worker + ['--full'], capture_output=True, text=True)
    assert proc.returncode == 1 and 'Records directory already exists' in proc.stderr
    with pytest.raises(ValueError, match='worker failed'):
        replay.snapshot(checkout, frozen, manifest, out, 1, full=True)
    proc = subprocess.run(worker + ['--blob'], capture_output=True, text=True)
    assert proc.returncode == 2 and '--blob needs --full' in proc.stderr


def test_full_mode_replays_raw_labels_only(tmp_path):
    root = tmp_path / 'products'
    stage = root / 'brand_enriched' / 'enriched'
    stage.mkdir(parents=True)
    source = stage / 'batch.json'
    source.write_text(json.dumps([{'id': '1'}]))
    write_stage_manifest(stage, 'enrich', [source])
    frozen, manifest = tmp_path / 'frozen', tmp_path / 'manifest.json'
    replay.freeze(root, frozen, manifest)
    proc = subprocess.run([sys.executable, HARNESS, '_worker', '--checkout', str(tmp_path), '--products-root', str(frozen), '--manifest', str(manifest), '--out', str(tmp_path / 'out.jsonl'), '--full'], capture_output=True, text=True)
    assert proc.returncode == 1 and 'raw labels only' in proc.stderr


def test_worker_accepts_the_dead_code_auditors_bare_namespace(tmp_path, monkeypatch):
    frozen, manifest = frozen_labels(tmp_path)
    monkeypatch.setattr(replay, 'score_batch', lambda task: [{'id': str(p['id']), 'input_sha256': task[2]['sha256'], 'total': 1}
                                                              for p in replay.payloads(Path(task[1]) / task[2]['path'], raw=True)])
    out = tmp_path / 'out.jsonl'
    replay.worker(argparse.Namespace(checkout='unused', products_root=str(frozen), manifest=str(manifest), out=str(out), workers=1))
    assert [json.loads(line)['id'] for line in out.read_text().splitlines()] == ['1', '2']
    assert not replay.records_dir(out).exists()
