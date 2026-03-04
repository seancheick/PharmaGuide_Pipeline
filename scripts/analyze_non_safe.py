#!/usr/bin/env python3
"""Analyze all non-SAFE products across six brands."""

import json
from pathlib import Path
from collections import defaultdict

BRANDS = {
    'Thorne': 'output_Thorne_scored',
    'Nordic Naturals': 'output_Nordic_Naturals_scored',
    'Garden of Life': 'output_Garden_of_Life_scored',
    'Nature Made': 'output_Nature_Made_scored',
    'Olly': 'output_Olly_scored',
    'Life Extension': 'output_Life_Extension_scored',
}

def load_products(scored_dir):
    products = []
    for f in sorted(Path(scored_dir).glob('**/*.json')):
        if 'report' in str(f) or 'summary' in str(f):
            continue
        with open(f) as fh:
            data = json.load(fh)
            if isinstance(data, list):
                products.extend(data)
            else:
                products.append(data)
    return products


def analyze_product(p):
    name = p.get('product_name', '?')
    verdict = p.get('verdict', '?')
    qs = p.get('quality_score') or 0
    dsld_id = p.get('dsld_id', '?')
    flags = p.get('flags', [])
    bd = p.get('breakdown', {})

    print(f"\n  --- {verdict} | {name} (ID:{dsld_id}) | score={qs:.1f}/80 ---")

    # Section scores with subsection details
    for sec in ['A', 'B', 'C', 'D']:
        sd = bd.get(sec, {})
        if not isinstance(sd, dict):
            continue
        score = sd.get('score', 0)
        mx = sd.get('max', '?')

        # Collect nonzero subsections
        details = []
        for k, v in sd.items():
            if k in ('score', 'max', 'B5_blend_evidence', 'probiotic_breakdown'):
                continue
            if isinstance(v, (int, float)) and v != 0:
                details.append(f"{k}={v}")
            elif k == 'reason' and v:
                details.append(f'reason="{v}"')
            elif k == 'B0' and v:
                details.append(f"B0={v}")

        detail_str = "  [" + "  ".join(details[:10]) + "]" if details else ""
        print(f"    {sec}: {score}/{mx}{detail_str}")

    vp = bd.get('violation_penalty', 0)
    if vp:
        print(f"    violation_penalty: {vp}")

    if flags:
        print(f"    flags: {flags}")

    # B5 blend evidence
    b_data = bd.get('B', {})
    if isinstance(b_data, dict):
        blends = b_data.get('B5_blend_evidence', [])
        for bl in blends:
            bn = bl.get('blend_name', '?')
            tier = bl.get('disclosure_tier', '?')
            pen = bl.get('computed_blend_penalty_magnitude', 0)
            children_with = bl.get('children_with_amount_count', 0)
            children_without = bl.get('children_without_amount_count', 0)
            impact = bl.get('impact_ratio', 0)
            print(f"    B5 blend: \"{bn}\" tier={tier} penalty=-{pen:.1f} "
                  f"impact={impact:.2f} children={children_with}w/{children_without}wo")

    # C section ingredient matches
    c_data = bd.get('C', {})
    if isinstance(c_data, dict):
        ing_pts = c_data.get('ingredient_points', {})
        if ing_pts:
            top = sorted(ing_pts.items(), key=lambda x: x[1], reverse=True)[:5]
            parts = [f"{k}={v}" for k, v in top]
            print(f"    C matches: {', '.join(parts)}")


def main():
    for brand, folder in BRANDS.items():
        scored_dir = Path('shadow_six_brand') / folder
        products = load_products(scored_dir)

        non_safe = [p for p in products if p.get('verdict') in ('UNSAFE', 'CAUTION', 'POOR')]
        if not non_safe:
            print(f"\n{'='*90}")
            print(f"{brand.upper()} — 0 non-SAFE products (all SAFE)")
            print(f"{'='*90}")
            continue

        print(f"\n{'='*90}")
        print(f"{brand.upper()} — {len(non_safe)} non-SAFE products")
        print(f"{'='*90}")

        # Group by verdict
        for verdict_type in ['UNSAFE', 'CAUTION', 'POOR']:
            group = [p for p in non_safe if p.get('verdict') == verdict_type]
            if not group:
                continue
            print(f"\n  [{verdict_type}] ({len(group)} products)")

            for p in sorted(group, key=lambda x: x.get('quality_score') or 0):
                analyze_product(p)


if __name__ == "__main__":
    main()
