"""Frozen-input replay of the real scorer; no scoring policy lives here."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import math
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS))
from stage_manifest import MANIFEST_NAME, select_stage_input_files


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def payloads(path):
    value = json.loads(path.read_text())
    if not isinstance(value, list) or not value:
        raise ValueError(f'Empty or invalid product payload: {path}')
    return value


def unique(rows):
    seen = set()
    for source, digest, product in rows:
        identifier = str(product.get('id') or '')
        if not identifier:
            raise ValueError(f'Missing product ID: {source}')
        if identifier in seen:
            raise ValueError(f'Duplicate product ID: {identifier}')
        seen.add(identifier)
        yield source, digest, product


def freeze(products_root, frozen_root, manifest):
    products_root, frozen_root = Path(products_root).resolve(), Path(frozen_root).resolve()
    if frozen_root.exists():
        raise ValueError('Frozen destination already exists; use a new directory')
    stages = sorted(products_root.glob('*/enriched'))
    files = []
    for stage in stages:
        owned = select_stage_input_files(stage, 'enrich', require_manifest=True)
        files.extend(owned + [stage / MANIFEST_NAME])
    if not files:
        raise ValueError('No enrichment stage inputs')
    records = []
    count = 0
    for path in files:
        records.append({'path': str(path.relative_to(products_root)), 'sha256': sha(path), 'kind': 'manifest' if path.name == MANIFEST_NAME else 'products'})
    for _ in unique((item['path'], item['sha256'], p) for item in records if item['kind'] == 'products' for p in payloads(products_root / item['path'])):
        count += 1
    for item in records:
        source, target = products_root / item['path'], frozen_root / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if sha(source) != item['sha256'] or sha(target) != item['sha256']:
            raise ValueError(f'Input mutated during freeze: {source}')
    result = {'schema_version': 1, 'source_root': str(products_root), 'created_at': datetime.now(timezone.utc).isoformat(), 'product_count': count, 'files': records}
    write_json(manifest, result)
    return result


def verified_files(root, manifest):
    root = Path(root).resolve()
    spec = json.loads(Path(manifest).read_text())
    files = spec['files']
    if not files:
        raise ValueError('Empty input manifest')
    names = [item['path'] for item in files]
    if len(names) != len(set(names)):
        raise ValueError('Duplicate input paths')
    for item in files:
        path = (root / item['path']).resolve()
        if not path.is_relative_to(root) or sha(path) != item['sha256']:
            raise ValueError(f'Input hash mismatch: {path}')
    product_files = [item for item in files if item['kind'] == 'products']
    for stage in sorted({(root / item['path']).parent for item in product_files}):
        selected = select_stage_input_files(stage, 'enrich', require_manifest=True)
        if {str(p.relative_to(root)) for p in selected} != {item['path'] for item in product_files if (root / item['path']).parent == stage}:
            raise ValueError('Input manifest does not match stage ownership')
        if str((stage / MANIFEST_NAME).relative_to(root)) not in names:
            raise ValueError('Missing enrichment stage manifest ownership')
    return product_files, spec


def inputs(root, manifest):
    root = Path(root).resolve()
    product_files, spec = verified_files(root, manifest)
    count = 0
    for record in unique((item['path'], item['sha256'], p) for item in product_files for p in payloads(root / item['path'])):
        count += 1
        yield record
    if not count or count != spec['product_count']:
        raise ValueError('Input product count mismatch')


def project_record(record):
    """Project diagnostic fields from captured scorer output, never recompute policy."""
    module = record.get('reasons', {}).get('module', {})
    metadata = module.get('metadata', {})
    dimensions = module.get('dimensions', {})
    formulation = dimensions.get('formulation', {}).get('metadata', {})
    dose = dimensions.get('dose', {}).get('metadata', {})
    components = (record.get('pillars') or {}).get('formulation', {}).get('components', {})
    record['subtype'] = metadata.get('sports_subtype')
    record['formulation_profile'] = formulation.get('formulation_profile') or components.get('formulation_profile')
    method = dose.get('method') or ''
    profile = next((name for name in ('sleep_support', 'immune_support', 'joint_support') if method.startswith(name + '_')), None)
    record['subroute'] = record['subtype'] or profile or record['formulation_profile'] or components.get('archetype')
    return record


def captured_subroute(record):
    return project_record(dict(record))['subroute']


def score_records(rows, scorer):
    results = []
    for source, digest, product in rows:
        record = {'id': str(product['id']), 'input_path': source, 'input_sha256': digest, 'name': product.get('fullName'), 'label_source': product.get('imageUrl'), 'label_source_path': source + '#id=' + str(product['id']) + '/label_source_rows'}
        try:
            result = scorer(product)
            if not result or 'quality_score_status' not in result:
                raise ValueError('Empty or invalid scorer success')
            breakdown = result.get('v4_breakdown', {})
            record.update(total=result.get('quality_score_v4_100'), pillars=result.get('quality_pillars_v4'), status=result['quality_score_status'], route=result.get('v4_module'), purpose=result.get('quality_purpose_id') or breakdown.get('module', {}).get('metadata', {}).get('purpose'), reasons=breakdown, provenance=breakdown.get('provenance'))
            project_record(record)
        except Exception as exc:
            record['error'] = f'{type(exc).__name__}: {exc}'
        results.append(record)
    return results


def reproject(path):
    """Upgrade diagnostic projections while retaining the original scorer capture."""
    path = Path(path)
    raw = Path(str(path) + '.raw.jsonl')
    if raw.exists():
        raise ValueError('Raw capture already exists; refusing to overwrite')
    rows = read_rows(path)
    metadata_path = Path(str(path) + '.meta.json')
    metadata = json.loads(metadata_path.read_text())
    raw_hash = sha(path)
    path.rename(raw)
    with path.open('w') as handle:
        for row in rows:
            handle.write(json.dumps(project_record(row), sort_keys=True) + '\n')
    metadata['output_sha256'] = sha(path)
    metadata['projection'] = {'version': 2, 'raw_capture': str(raw), 'raw_sha256': raw_hash, 'projected_sha256': sha(path), 'harness_sha256': sha(__file__), 'reason': 'Add explicit subtype/formulation_profile and correct nested-profile projection; scorer output retained unchanged.'}
    write_json(metadata_path, metadata)


def require_success(rows):
    if not rows or any('error' in row for row in rows):
        raise ValueError('Empty replay or failed scorer calls; inspect persisted records')


def read_rows(path, project=None):
    """Verified snapshot rows; `project` slims each row while streaming."""
    metadata = json.loads(Path(str(path) + '.meta.json').read_text())
    if metadata.get('exit_code') != 0 or metadata.get('source_unchanged') is not True:
        raise ValueError('Snapshot metadata records a failed run')
    if metadata.get('output_sha256') != sha(path):
        raise ValueError('Snapshot output hash mismatch or missing receipt')
    with Path(path).open() as handle:
        rows = [(project or (lambda row: row))(json.loads(line)) for line in handle if line.strip()]
    require_success(rows)
    if len(rows) != metadata.get('product_count') or len(rows) != metadata.get('expected_product_count'):
        raise ValueError('Snapshot product count mismatch')
    if len({row['id'] for row in rows}) != len(rows):
        raise ValueError('Duplicate snapshot IDs')
    return rows


def compare_records(baseline, candidate):
    require_success(baseline)
    require_success(candidate)
    left, right = {p['id']: p for p in baseline}, {p['id']: p for p in candidate}
    if len(left) != len(baseline) or len(right) != len(candidate) or left.keys() != right.keys():
        raise ValueError('Snapshot product IDs differ or duplicate')
    for key in left:
        if left[key]['input_sha256'] != right[key]['input_sha256']:
            raise ValueError(f'Snapshot input hashes differ: {key}')
    return [{'id': key, 'baseline': left[key], 'candidate': right[key]} for key in sorted(left) if left[key] != right[key]]


def check_records(rows, cases):
    require_success(rows)
    if not any(case.get('required') for case in cases):
        return [{'error': 'No required reference comparisons; acceptance is unresolved'}]
    indexed = {row['id']: row for row in rows}
    failures = []
    for case in cases:
        if not case.get('required'):
            continue
        try:
            if case.get('review_status') != 'approved':
                raise ValueError('required reference is unresolved')
            a, b = indexed[case['left']], indexed[case['right']]
            for part in case['field'].split('.'):
                a, b = a[part], b[part]
            if any(type(value) not in (int, float) or not math.isfinite(value) for value in (a, b)):
                raise ValueError('Required numeric comparison needs finite numbers, not null/bool/text')
            passed = {'gt': lambda: a > b, 'ge': lambda: a >= b, 'eq': lambda: a == b, 'lt': lambda: a < b, 'le': lambda: a <= b}[case['relation']]()
            if not passed:
                raise ValueError('required relational claim failed')
        except (KeyError, TypeError, ValueError) as exc:
            failures.append({'case': case, 'error': str(exc)})
    return failures


THRESHOLDS = (55, 70, 80, 90)
PILLARS = ('formulation', 'dose', 'evidence', 'transparency', 'verification', 'safety_hygiene')
RAW_KEYS = ('raw_formulation', 'raw_dose', 'raw_evidence', 'raw_score')
MATERIAL_DELTA = 2.0


def slim(row):
    """The fields a calibration report reads; everything else is dropped while streaming."""
    if 'error' in row:
        return row
    dims = ((row.get('reasons') or {}).get('module') or {}).get('dimensions') or {}
    return {'id': row['id'], 'name': row.get('name'), 'route': row.get('route'), 'subroute': row.get('subroute'),
            'total': row.get('total'), 'input_sha256': row.get('input_sha256'),
            'pillars': {k: {'score': v.get('score'), 'components': {c: x for c, x in (v.get('components') or {}).items() if not isinstance(x, (dict, list))}}
                        for k, v in (row.get('pillars') or {}).items()},
            'dims': {k: {'components': dict(v.get('components') or {}), 'penalties': dict(v.get('penalties') or {})}
                     for k, v in dims.items() if isinstance(v, dict)}}


def _changed(before, after):
    return sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))


def reason_codes(before, after, eps=0.05):
    """Per pillar that moved: the reference, component and penalty keys that changed."""
    codes = []
    for pillar in PILLARS:
        b, a = before['pillars'].get(pillar) or {}, after['pillars'].get(pillar) or {}
        delta = round((a.get('score') or 0) - (b.get('score') or 0), 2)
        if abs(delta) < eps:
            continue
        bc, ac = b.get('components') or {}, a.get('components') or {}
        causes = []
        if bc.get('reference') != ac.get('reference') or bc.get('raw_max') != ac.get('raw_max'):
            causes.append('reference')
        dim = 'transparency' if pillar == 'transparency' else pillar
        raw_moved = any(bc.get(k) != ac.get(k) for k in RAW_KEYS)
        if raw_moved and dim in before['dims']:
            bd, ad = before['dims'].get(dim) or {}, after['dims'].get(dim) or {}
            causes += ['component:' + k for k in _changed(bd.get('components') or {}, ad.get('components') or {})]
            causes += ['penalty:' + k for k in _changed(bd.get('penalties') or {}, ad.get('penalties') or {})]
            if not causes:
                # Same inputs, different raw: the pillar's own aggregation changed.
                causes.append('formula')
        if pillar in ('verification', 'safety_hygiene'):
            causes += ['component:' + k for k in _changed(bc, ac)]
        codes.append({'pillar': pillar, 'delta': delta, 'causes': causes or ['unattributed']})
    return codes


def _quantile(values, q):
    return values[min(len(values) - 1, int(q * len(values)))] if values else None


def distribution(scores):
    values = sorted(scores)
    return {'n': len(values), 'p10': _quantile(values, .1), 'median': _quantile(values, .5), 'p90': _quantile(values, .9),
            'max': values[-1] if values else None, **{f'ge_{t}': sum(v >= t for v in values) for t in THRESHOLDS}}


def arm_report(baseline, candidate, reference_ids):
    left = {r['id']: r for r in baseline}
    right = {r['id']: r for r in candidate}
    if left.keys() != right.keys() or any(left[k]['input_sha256'] != right[k]['input_sha256'] for k in left):
        raise ValueError('Snapshot product IDs or input hashes differ')
    scored = [k for k in left if left[k]['total'] is not None and right[k]['total'] is not None]
    groups = {}
    movers, causes = [], {}
    crossings = {t: {'up': 0, 'down': 0} for t in THRESHOLDS}
    denominator_only = unexplained = 0
    for key in scored:
        b, a = left[key], right[key]
        delta = round(a['total'] - b['total'], 1)
        for level in ('route', 'subroute'):
            name = b['route'] if level == 'route' else f"{b['route']}/{b['subroute']}"
            groups.setdefault(name, {'before': [], 'after': []})
            groups[name]['before'].append(b['total'])
            groups[name]['after'].append(a['total'])
        for t in THRESHOLDS:
            if b['total'] < t <= a['total']:
                crossings[t]['up'] += 1
            elif a['total'] < t <= b['total']:
                crossings[t]['down'] += 1
        if delta == 0:
            continue
        codes = reason_codes(b, a)
        flat = sorted({f"{c['pillar']}:{cause}" for c in codes for cause in c['causes']})
        if not codes or any('unattributed' in c['causes'] for c in codes):
            unexplained += abs(delta) >= MATERIAL_DELTA
        if codes and all(c['causes'] == ['reference'] for c in codes):
            denominator_only += 1
        for code in flat:
            entry = causes.setdefault(code, {'products': 0, 'delta_sum': 0.0})
            entry['products'] += 1
            entry['delta_sum'] += delta
        movers.append({'id': key, 'name': b['name'], 'route': b['route'], 'subroute': b['subroute'],
                       'before': b['total'], 'after': a['total'], 'delta': delta, 'reasons': codes})
    movers.sort(key=lambda m: m['delta'])
    deltas = sorted(m['delta'] for m in movers)
    return {
        'scored': len(scored), 'changed': len(movers),
        'material_changes': sum(abs(d) >= MATERIAL_DELTA for d in deltas),
        'unexplained_material_changes': unexplained, 'denominator_only_changes': denominator_only,
        'mean_delta_all': round(sum(deltas) / len(scored), 2) if scored else 0,
        'crossings': crossings,
        'groups': {name: {'before': distribution(v['before']), 'after': distribution(v['after'])} for name, v in sorted(groups.items())},
        'causes': {k: {'products': v['products'], 'mean_delta': round(v['delta_sum'] / v['products'], 2)}
                   for k, v in sorted(causes.items(), key=lambda kv: -kv[1]['products'])},
        'largest_decreases': movers[:25], 'largest_increases': movers[::-1][:25],
        'reference_products': [{'id': k, 'name': left[k]['name'], 'subroute': f"{left[k]['route']}/{left[k]['subroute']}",
                                'before': left[k]['total'], 'after': right[k]['total'],
                                'reasons': reason_codes(left[k], right[k])} for k in reference_ids if k in left],
    }


def reference_ids(baseline, reference_cases=None):
    """Coverage references plus the top and median product of every subroute."""
    ids = list((reference_cases or {}).get('coverage', {}).values())
    groups = {}
    for row in baseline:
        if row['total'] is not None:
            groups.setdefault((row['route'], row['subroute']), []).append(row)
    for rows in groups.values():
        rows.sort(key=lambda r: (r['total'], r['id']))
        ids += [rows[-1]['id'], rows[len(rows) // 2]['id']]
    return list(dict.fromkeys(ids))


def build_report(baseline_path, candidates, reference_cases=None):
    base_meta = json.loads(Path(str(baseline_path) + '.meta.json').read_text())
    baseline = read_rows(baseline_path, slim)
    refs = reference_ids(baseline, reference_cases)
    report = {'baseline': {'path': str(baseline_path), 'output_sha256': base_meta['output_sha256'],
                           'head': base_meta['repository']['head']}, 'arms': {}}
    for name, path in candidates:
        meta = json.loads(Path(str(path) + '.meta.json').read_text())
        if meta['inputs_manifest_sha256'] != base_meta['inputs_manifest_sha256']:
            raise ValueError('Snapshot input manifest hashes differ')
        report['arms'][name] = {'path': str(path), 'output_sha256': meta['output_sha256'],
                                'head': meta['repository']['head'],
                                **arm_report(baseline, read_rows(path, slim), refs)}
    return report

def repository_provenance(checkout):
    checkout = Path(checkout)
    scripts = checkout / 'scripts'
    excluded = {'tests', 'audits', 'logs', 'reports', 'products', '__pycache__', '.venv'}
    python_files = {p for p in scripts.rglob('*.py') if not excluded.intersection(p.relative_to(scripts).parts)}
    files = sorted(python_files | set((scripts / 'scoring_v4/config').rglob('*.json')) | set((scripts / 'data').rglob('*.json')))
    return {'head': subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], text=True).strip(), 'source_sha256': {str(p.relative_to(checkout)): sha(p) for p in files}}


def snapshot(checkout, products_root, manifest, out, workers=1):
    checkout = Path(checkout).resolve()
    before = repository_provenance(checkout)
    command = [sys.executable, str(Path(__file__).resolve()), '_worker', '--checkout', str(checkout), '--products-root', str(products_root), '--manifest', str(manifest), '--out', str(out), '--workers', str(workers)]
    result = subprocess.run(command, cwd=checkout)
    after = repository_provenance(checkout)
    metadata = {'created_at': datetime.now(timezone.utc).isoformat(), 'checkout': str(checkout), 'repository': before, 'inputs_manifest_sha256': sha(manifest), 'exit_code': result.returncode, 'source_unchanged': before == after, 'expected_product_count': json.loads(Path(manifest).read_text())['product_count'], 'product_count': sum(1 for line in Path(out).open() if line.strip()) if Path(out).exists() else 0, 'output_sha256': sha(out) if Path(out).exists() else None, 'workers': workers, 'capture_version': 2}
    write_json(str(out) + '.meta.json', metadata)
    if before != after:
        raise ValueError('Scoring source mutated during snapshot')
    if result.returncode:
        raise ValueError('Snapshot worker failed; inspect output and metadata')
    read_rows(out)


def score_batch(task):
    checkout, root, item = task
    sys.path.insert(0, str(Path(checkout).resolve() / 'scripts'))
    from score_supplements_v4 import score_product_v4
    return score_records(((item['path'], item['sha256'], p) for p in payloads(Path(root) / item['path'])), score_product_v4)


def worker(args):
    before = sha(args.manifest)
    files, spec = verified_files(args.products_root, args.manifest)
    tasks = [(args.checkout, args.products_root, item) for item in files]
    rows = []
    if args.workers == 1:
        batches = map(score_batch, tasks)
        for batch in batches:
            rows.extend(batch)
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            for batch in pool.map(score_batch, tasks):
                rows.extend(batch)
                print(f'{len(rows)}/{spec["product_count"]} products captured', file=sys.stderr, flush=True)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w') as handle:
        for row in sorted(rows, key=lambda row: row['id']):
            handle.write(json.dumps(row, sort_keys=True) + '\n')
    verified_files(args.products_root, args.manifest)
    if before != sha(args.manifest):
        raise ValueError('Input manifest mutated during snapshot')
    if len(rows) != spec['product_count'] or len({row['id'] for row in rows}) != len(rows):
        raise ValueError('Duplicate product IDs or input product count mismatch')
    require_success(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    freeze_p = subs.add_parser('freeze')
    for flag in ('products-root', 'frozen-root', 'manifest'):
        freeze_p.add_argument('--' + flag, required=True)
    for name in ('snapshot', '_worker'):
        p = subs.add_parser(name)
        p.add_argument('--workers', type=int, choices=range(1, 5), default=1)
        for flag in ('checkout', 'products-root', 'manifest', 'out'):
            p.add_argument('--' + flag, required=True)
    p = subs.add_parser('compare')
    for flag in ('baseline', 'candidate', 'out'):
        p.add_argument('--' + flag, required=True)
    p = subs.add_parser('report')
    p.add_argument('--baseline', required=True)
    p.add_argument('--candidate', action='append', required=True, help='name=path; repeatable')
    p.add_argument('--reference-cases')
    p.add_argument('--out', required=True)
    p = subs.add_parser('check')
    p.add_argument('--candidate', required=True)
    p.add_argument('--reference-cases', required=True)
    args = parser.parse_args()
    if args.command == 'freeze':
        freeze(args.products_root, args.frozen_root, args.manifest)
    elif args.command == 'snapshot':
        snapshot(args.checkout, args.products_root, args.manifest, args.out, args.workers)
    elif args.command == '_worker':
        worker(args)
    elif args.command == 'compare':
        baseline_meta = json.loads(Path(args.baseline + '.meta.json').read_text())
        candidate_meta = json.loads(Path(args.candidate + '.meta.json').read_text())
        if baseline_meta['inputs_manifest_sha256'] != candidate_meta['inputs_manifest_sha256']:
            raise ValueError('Snapshot input manifest hashes differ')
        write_json(args.out, compare_records(read_rows(args.baseline), read_rows(args.candidate)))
    elif args.command == 'report':
        cases = json.loads(Path(args.reference_cases).read_text()) if args.reference_cases else None
        arms = [tuple(item.split('=', 1)) for item in args.candidate]
        write_json(args.out, build_report(args.baseline, arms, cases))
    else:
        failures = check_records(read_rows(args.candidate), json.loads(Path(args.reference_cases).read_text())['comparisons'])
        print(json.dumps({'failures': failures}, indent=2))
        if failures:
            return 1
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
