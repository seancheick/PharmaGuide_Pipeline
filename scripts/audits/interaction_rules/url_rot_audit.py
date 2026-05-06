#!/usr/bin/env python3
"""Sweep all source URLs in ingredient_interaction_rules.json and report dead/redirected ones.

Usage:
    python3 scripts/audits/interaction_rules/url_rot_audit.py

Output: scripts/audits/interaction_rules/URL_ROT_REPORT.md
"""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RULES_PATH = os.path.join(ROOT, 'data', 'ingredient_interaction_rules.json')
URL_RE = re.compile(r'https?://[^\s"]+')

with open(RULES_PATH) as f:
    data = json.load(f)

# Extract all (url, canonical_id, field_path) triples
entries = []
for i, r in enumerate(data['interaction_rules']):
    sr = r.get('subject_ref', {})
    cid = sr.get('canonical_id') if isinstance(sr, dict) else str(sr)

    def walk(node, path):
        if isinstance(node, str):
            for m in URL_RE.finditer(node):
                url = m.group(0).rstrip('.,;)')
                entries.append((url, cid, f'[{i}]{path}'))
        elif isinstance(node, dict):
            for k, v in node.items():
                walk(v, f'{path}.{k}')
        elif isinstance(node, list):
            for j, v in enumerate(node):
                walk(v, f'{path}[{j}]')

    walk(r, '')

# Deduplicate URLs (keep all entry references)
url_map = {}  # url -> [(cid, path), ...]
for url, cid, path in entries:
    url_map.setdefault(url, []).append((cid, path))

unique_urls = sorted(url_map.keys())
print(f'Found {len(entries)} URL references across {len(unique_urls)} unique URLs', file=sys.stderr)

# Curl-check each with redirect following
results = []  # (url, status, final_url, entries)
for i, url in enumerate(unique_urls):
    try:
        req = urllib.request.Request(url, method='HEAD',
                                     headers={'User-Agent': 'pharmaguide-url-audit/1.0'})
        # Don't follow redirects automatically — we want to detect them
        opener = urllib.request.build_opener(urllib.request.HTTPHandler)
        try:
            resp = opener.open(req, timeout=10)
            status = resp.status
            final = resp.url
        except urllib.error.HTTPError as e:
            status = e.code
            final = url
        # If redirect, follow it to get the final status
        if status in (301, 302, 303, 307, 308):
            try:
                req2 = urllib.request.Request(url, method='HEAD',
                                              headers={'User-Agent': 'pharmaguide-url-audit/1.0'})
                resp2 = urllib.request.urlopen(req2, timeout=10)
                final_status = resp2.status
                final = resp2.url
                status = f'{status}→{final_status}'
            except Exception:
                pass
    except urllib.error.HTTPError as e:
        status = e.code
        final = url
    except Exception as e:
        status = f'ERR:{type(e).__name__}'
        final = url

    refs = url_map[url]
    status = str(status)
    results.append((url, status, final, refs))
    tag = '✓' if status.startswith('200') else '✗' if '404' in status else '~'
    print(f'  [{i+1}/{len(unique_urls)}] {tag} {status:8s} {url[:80]}', file=sys.stderr)
    time.sleep(0.3)

# Classify
dead = [(u, s, f, r) for u, s, f, r in results if '404' in s or 'ERR' in s]
redirected = [(u, s, f, r) for u, s, f, r in results if '301' in s or '302' in s]
ok = [(u, s, f, r) for u, s, f, r in results if s == '200']

# Write report
report_path = os.path.join(os.path.dirname(__file__), 'URL_ROT_REPORT.md')
with open(report_path, 'w') as f:
    f.write('# URL Rot Audit — ingredient_interaction_rules.json\n\n')
    f.write(f'**Date**: 2026-05-06\n')
    f.write(f'**Schema**: {data["_metadata"]["schema_version"]}\n')
    f.write(f'**Total URL references**: {len(entries)}\n')
    f.write(f'**Unique URLs**: {len(unique_urls)}\n')
    f.write(f'**Results**: {len(ok)} OK, {len(redirected)} redirected, {len(dead)} dead/error\n\n')

    if dead:
        f.write('## Dead / Error URLs\n\n')
        f.write('| URL | Status | Used by |\n')
        f.write('|---|---|---|\n')
        for u, s, _, refs in dead:
            cids = ', '.join(set(c for c, _ in refs))
            f.write(f'| `{u[:80]}` | {s} | {cids} |\n')
        f.write('\n')

    if redirected:
        f.write('## Redirected URLs (update slug)\n\n')
        f.write('| URL | Status | Final URL | Used by |\n')
        f.write('|---|---|---|---|\n')
        for u, s, final, refs in redirected:
            cids = ', '.join(set(c for c, _ in refs))
            f.write(f'| `{u[:70]}` | {s} | `{final[:70]}` | {cids} |\n')
        f.write('\n')

    f.write('## OK URLs\n\n')
    f.write(f'{len(ok)} URLs returned HTTP 200.\n\n')

print(f'\nWrote {report_path}')
print(f'Dead: {len(dead)}, Redirected: {len(redirected)}, OK: {len(ok)}')
