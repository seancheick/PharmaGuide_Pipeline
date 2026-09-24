"""Regenerate frozen products with the current cleaner and enricher (audit overlay).

Reads each frozen brand directory's product IDs, re-runs normalize + enrich on
the raw DSLD record, and writes one overlay file per brand to --out-dir
(coverage_report.py --overlay reads them; regenerated records replace the same
IDs). Resumable: a brand whose overlay file exists is skipped. One process,
brand at a time, so memory stays bounded. Never touches scripts/products.

  python scripts/audits/quality_redesign/regenerate.py \
      --frozen-root /tmp/pg_quality/frozen-products \
      --raw-root ~/Downloads/PharmaGuide_Datasets/staging/brands \
      --out-dir ~/pg_quality/regen
"""
from __future__ import annotations

import argparse
import glob
import json
import logging
import os
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frozen-root', required=True)
    parser.add_argument('--raw-root', required=True)
    parser.add_argument('--out-dir', required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    logging.disable(logging.CRITICAL)
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    raw = {Path(p).stem: p for p in glob.glob(os.path.join(os.path.expanduser(args.raw_root), '*', '*.json'))}
    out_dir = Path(os.path.expanduser(args.out_dir))
    out_dir.mkdir(parents=True, exist_ok=True)
    normalizer, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()
    totals = {'products': 0, 'regenerated': 0, 'missing_raw': 0, 'errors': 0}
    for brand_dir in sorted(Path(args.frozen_root).iterdir()):
        target = out_dir / f'{brand_dir.name}.json'
        if target.exists():
            continue
        ids = []
        for payload in sorted(brand_dir.glob('**/*.json')):
            data = json.loads(payload.read_text())
            if isinstance(data, list):
                ids.extend(str(p['id']) for p in data if isinstance(p, dict) and 'id' in p)
        started, records, missing, errors = time.time(), [], [], []
        for product_id in ids:
            if product_id not in raw:
                missing.append(product_id)
                continue
            try:
                source = json.loads(Path(raw[product_id]).read_text())
                records.append(enricher.enrich_product(normalizer.normalize_product(source))[0])
            except Exception as error:  # recorded, never silently dropped
                errors.append({'id': product_id, 'error': str(error)[:300]})
        tmp = target.with_suffix('.tmp')
        tmp.write_text(json.dumps(records))
        tmp.replace(target)
        (out_dir / f'{brand_dir.name}.receipt.json').write_text(json.dumps(
            {'products': len(ids), 'regenerated': len(records), 'missing_raw': missing, 'errors': errors,
             'seconds': round(time.time() - started)}, indent=1))
        for key, value in (('products', len(ids)), ('regenerated', len(records)),
                           ('missing_raw', len(missing)), ('errors', len(errors))):
            totals[key] += value
        print(brand_dir.name, len(ids), len(records), len(missing), len(errors), round(time.time() - started), flush=True)
    print('TOTAL', json.dumps(totals), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
