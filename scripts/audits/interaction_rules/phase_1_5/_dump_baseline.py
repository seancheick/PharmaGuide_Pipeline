#!/usr/bin/env python3
"""Dump current copy of the 16 Phase 1.5 entries to BASELINE.md."""
import json, re, os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
RULES = os.path.join(ROOT, 'data', 'ingredient_interaction_rules.json')

with open(RULES) as f:
    data = json.load(f)

rules = data['interaction_rules']
URL_RE = re.compile(r'https?://[^\s"]+')
out = ['# Phase 1.5 — Full Baseline Dump\n',
       'Reviewer baseline (5.2.0) did not include these 16 entries.',
       'Live schema is 6.0.2; we will bump after edits.\n']

for i in range(129, 145):
    r = rules[i]
    body = json.dumps(r, indent=2, ensure_ascii=False)
    urls = sorted(set(URL_RE.findall(body)))
    sr = r.get('subject_ref', {})
    cid = sr.get('canonical_id') if isinstance(sr, dict) else sr
    db = sr.get('db') if isinstance(sr, dict) else ''
    out.append(f'## [{i}] {cid}  ({db})')
    out.append(f'**URLs cited ({len(urls)}):**')
    for u in urls:
        out.append(f'- {u}')
    out.append('')
    out.append('```json')
    out.append(body)
    out.append('```')
    out.append('')

dest = os.path.join(os.path.dirname(__file__), 'BASELINE.md')
with open(dest, 'w') as f:
    f.write('\n'.join(out))
print(f'wrote {dest} bytes={os.path.getsize(dest)}')
