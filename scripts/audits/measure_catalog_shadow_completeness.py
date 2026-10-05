#!/usr/bin/env python3
"""Census the shared Evidence subjects, retaining every disposition and source row.

A raw frozen input runs the existing Clean/Enrich owners in memory. Stored
Enrich inputs are diagnostic only, never proof of current-source release coverage.
No scoring, catalog publication, or independent subject classification occurs here.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import evidence_resolver as er
from scoring_input_contract import get_evidence_subject_rows
from audits.quality_redesign import replay

_RAW_OWNERS = None


def census_product(product):
    rows = get_evidence_subject_rows(product)
    subjects = []
    for row in rows:
        result = er.resolve_evidence_for_row(row, product)
        subjects.append({
            'canonical_id': result.canonical_id, 'name': result.ingredient_name,
            'source_row_ref': row.get('raw_source_path') or row.get('source_row_ref'),
            'source_section': row.get('source_section'), 'matched_form': row.get('matched_form'),
            'disposition': result.disposition, 'reason_code': result.reason_code,
            'points_eligible': result.points_eligible, 'blocking_reasons': result.blocking_reasons,
        })
    overall, complete = er.compose_product_resolution_state([s['disposition'] for s in subjects])
    return {'id': str(product.get('id') or product.get('dsld_id') or ''),
            'name': product.get('product_name') or product.get('name'),
            'subject_count': len(subjects), 'subjects': subjects,
            'overall_disposition': overall, 'is_assessment_complete': complete}


def census_file(task):
    global _RAW_OWNERS
    root, item = task
    products = replay.payloads(Path(root) / item['path'], raw=item['kind'] == 'raw')
    if item['kind'] == 'raw':
        if _RAW_OWNERS is None:
            logging.disable(logging.CRITICAL)
            from enhanced_normalizer import EnhancedDSLDNormalizer
            from enrich_supplements_v3 import SupplementEnricherV3
            _RAW_OWNERS = EnhancedDSLDNormalizer(), SupplementEnricherV3()
        normalizer, enricher = _RAW_OWNERS
        products = [enricher.enrich_product(normalizer.normalize_product(p))[0] for p in products]
    return [{**census_product(p), 'input_sha256': item['sha256'], 'input_path': item['path']} for p in products]


def summarize(products):
    if not products or any(not p['id'] for p in products):
        raise ValueError('Empty census or missing product ID')
    if len({p['id'] for p in products}) != len(products):
        raise ValueError('Duplicate census product IDs')
    counts = Counter(s['disposition'] for p in products for s in p['subjects'])
    pending = [dict(s, product_id=p['id']) for p in products for s in p['subjects']
               if s['disposition'] in {er.EvidenceDisposition.IDENTITY_INSUFFICIENT.value,
                                       er.EvidenceDisposition.LITERATURE_RESOLUTION_REQUIRED.value}]
    return {'total_products': len(products), 'subject_count': sum(p['subject_count'] for p in products),
            'complete_products': sum(p['is_assessment_complete'] for p in products),
            'partial_products': sum(not p['is_assessment_complete'] for p in products),
            'dispositions': dict(sorted(counts.items())), 'unresolved_subjects': pending,
            'products': sorted(products, key=lambda p: p['id'])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--products-root', default='scripts/products')
    parser.add_argument('--manifest', help='Existing frozen raw or manifest-owned Enrich input manifest')
    parser.add_argument('--workers', type=int, choices=range(1, 5), default=1)
    parser.add_argument('--out', default='scripts/reports/phase4_final_sweep_completeness.json')
    args = parser.parse_args(argv)
    root = Path(args.products_root).resolve()
    manifest = args.manifest
    if not manifest:
        # Reuse the established freezer/ownership validator; never glob stale
        # product files or silently skip malformed records.
        frozen = Path(args.out).with_suffix('.inputs')
        manifest = frozen / 'manifest.json'
        replay.freeze(root, frozen, manifest)
        root = frozen
    before = replay.repository_provenance(SCRIPTS_DIR.parent)
    audit_hashes = {str(path): replay.sha(path) for path in (Path(__file__), Path(replay.__file__))}
    manifest_hash = replay.sha(manifest)
    files, spec = replay.verified_files(root, manifest)
    kinds = {item['kind'] for item in files}
    if not kinds <= {'raw', 'products'} or len(kinds) != 1:
        raise ValueError('Census inputs must have one supported input kind')
    products = []
    tasks = [(str(root), item) for item in files]
    if args.workers == 1:
        batches = map(census_file, tasks)
        for batch in batches:
            products.extend(batch)
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            for batch in pool.map(census_file, tasks, chunksize=8):
                products.extend(batch)
                if len(products) % 100 == 0:
                    print(f'{len(products)}/{spec["product_count"]} labels assessed', flush=True)
    report = summarize(products)
    if report['total_products'] != spec['product_count']:
        raise ValueError('Census input product count mismatch')
    replay.verified_files(root, manifest)
    if replay.sha(manifest) != manifest_hash or replay.repository_provenance(SCRIPTS_DIR.parent) != before:
        raise ValueError('Census source/input mutated during assessment')
    if any(replay.sha(path) != digest for path, digest in audit_hashes.items()):
        raise ValueError('Census audit implementation mutated during assessment')
    report.update({'created_at': datetime.now(timezone.utc).isoformat(), 'repository': before,
                   'input_manifest_sha256': manifest_hash, 'input_kind': next(iter(kinds)),
                   'audit_implementation_sha256': audit_hashes,
                   'scope': 'current_source_raw_subject_census' if kinds == {'raw'} else 'stored_enrichment_diagnostic',
                   'release_validated': False})
    replay.write_json(args.out, report)
    print(json.dumps({k:v for k,v in report.items() if k not in {'products','unresolved_subjects','repository'}}, indent=2))


if __name__ == '__main__':
    main()
