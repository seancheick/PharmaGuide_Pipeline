#!/usr/bin/env python3
"""Import UPC overrides from the manually-curated Markdown/CSV file.

Reads: ~/Downloads/UPC_Found_PharmaGuide_Pipeline.md
Writes: scripts/data/curated_overrides/upc_overrides.json

For dsld_ids with multiple UPCs (reformulations), keeps ALL UPCs as a
list so the scanner can match any packaging version. For conflicting
entries, prefers high-confidence over medium.

Usage:
    python3 scripts/tools/import_upc_overrides.py [--source PATH]

The output file is consumed by build_final_db.py during the final
DB build step. Re-run this script whenever the source file is updated.
"""
import json, os, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SOURCE = os.path.expanduser('~/Downloads/UPC_Found_PharmaGuide_Pipeline.md')
OUTPUT = os.path.join(ROOT, 'data', 'curated_overrides', 'upc_overrides.json')


def parse_source(path):
    """Parse the CSV-in-Markdown source file."""
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('dsld_id,found_upc'):
                continue
            parts = line.split(',', 5)
            if len(parts) < 3:
                continue
            dsld_id = parts[0].strip()
            upc = parts[1].strip()
            confidence = parts[2].strip()
            notes = parts[5].strip() if len(parts) > 5 else ''
            if not dsld_id.isdigit() or not upc:
                continue
            # Normalize: strip leading zeros beyond 12 digits
            if len(upc) > 12:
                upc = upc.lstrip('0')
            entries.append({
                'dsld_id': dsld_id,
                'upc': upc,
                'confidence': confidence,
                'notes': notes[:120],
            })
    return entries


def build_overrides(entries):
    """Build the override map: dsld_id → primary_upc + all_upcs."""
    by_dsld = defaultdict(list)
    seen = set()
    for e in entries:
        key = (e['dsld_id'], e['upc'])
        if key in seen:
            continue
        seen.add(key)
        by_dsld[e['dsld_id']].append(e)

    overrides = {}
    for dsld_id, items in sorted(by_dsld.items()):
        # Prefer high confidence as primary
        items.sort(key=lambda x: (0 if x['confidence'] == 'high' else 1))
        primary = items[0]
        all_upcs = sorted(set(i['upc'] for i in items))
        overrides[dsld_id] = {
            'upc': primary['upc'],
            'confidence': primary['confidence'],
            'all_upcs': all_upcs if len(all_upcs) > 1 else None,
        }
    return overrides


def main():
    source = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == '--source' else DEFAULT_SOURCE
    if not os.path.exists(source):
        print(f'Source not found: {source}', file=sys.stderr)
        sys.exit(1)

    entries = parse_source(source)
    overrides = build_overrides(entries)

    output_data = {
        '_metadata': {
            'description': 'Manually curated UPC overrides for DSLD products missing barcode data',
            'source': os.path.basename(source),
            'total_overrides': len(overrides),
            'last_updated': '2026-05-06',
            'usage': 'Applied by build_final_db.py to populate upc_sku on products_core rows',
        },
        'overrides': overrides,
    }

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
        f.write('\n')

    high = sum(1 for v in overrides.values() if v['confidence'] == 'high')
    med = sum(1 for v in overrides.values() if v['confidence'] == 'medium')
    multi = sum(1 for v in overrides.values() if v.get('all_upcs'))
    print(f'Imported {len(overrides)} UPC overrides ({high} high, {med} medium, {multi} multi-UPC)')
    print(f'Written to {OUTPUT}')


if __name__ == '__main__':
    main()
