#!/usr/bin/env python3
"""Topic-targeted PubMed search + abstract fetch for Phase 1.5 replacements.

Uses PUBMED_API_KEY (10 req/s vs 3) loaded from .env at repo root.
"""
import json, os, sys, time, urllib.request, urllib.parse, re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def load_env():
    env_path = os.path.join(ROOT, '.env')
    keys = {}
    if not os.path.exists(env_path): return keys
    for line in open(env_path):
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line: continue
        k, v = line.split('=', 1)
        keys[k.strip()] = v.strip().strip('"').strip("'")
    return keys

ENV = load_env()
KEY = ENV.get('PUBMED_API_KEY', '')

def _get(url, params):
    if KEY:
        params = {**params, 'api_key': KEY}
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(f'{url}?{qs}', headers={'User-Agent': 'pharmaguide-audit/1.0'})
    last_exc = None
    for attempt in range(5):
        try:
            return urllib.request.urlopen(req, timeout=15).read()
        except urllib.error.HTTPError as e:
            last_exc = e
            if e.code == 429:
                time.sleep(2 ** attempt)
                continue
            raise
    raise last_exc

def search(term, n=8):
    raw = _get('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi',
               dict(db='pubmed', term=term, retmode='json', retmax=n, sort='relevance'))
    return json.loads(raw).get('esearchresult', {}).get('idlist', [])

def summary(pmids):
    if not pmids: return {}
    raw = _get('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi',
               dict(db='pubmed', id=','.join(pmids), retmode='json'))
    return json.loads(raw).get('result', {})

def abstract(pmid):
    raw = _get('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi',
               dict(db='pubmed', id=pmid, rettype='abstract', retmode='text'))
    return raw.decode('utf-8', errors='replace')

QUERIES = [
    ('pennyroyal_pulegone_hepatotox', 'pennyroyal AND (pulegone OR hepatotoxicity) AND review[pt]'),
    ('tansy_thujone_tox',             'Tanacetum vulgare AND (thujone OR toxicity)'),
    ('maca_pregnancy_safety',         'Lepidium meyenii AND (safety OR toxicity OR review)'),
    ('tryptophan_serotonin_MAOI',     '(L-tryptophan OR tryptophan) AND (MAOI OR "serotonin syndrome")'),
    ('SAMe_serotonin_MAOI',           '(S-adenosylmethionine OR SAMe) AND (serotonin syndrome OR MAOI)'),
    ('sodium_lithium_clearance',      'sodium AND lithium AND (clearance OR toxicity OR pharmacokinetics)'),
    ('mulberry_alpha_glucosidase',    '(white mulberry OR Morus alba) AND alpha-glucosidase AND (postprandial OR randomized)'),
    ('bromelain_warfarin_bleeding',   'bromelain AND (warfarin OR bleeding OR hemorrhage)'),
    ('bupleurum_CYP3A4',              '(bupleurum OR saikosaponin) AND CYP3A4'),
    ('bupleurum_CYP2D6',              '(bupleurum OR saikosaponin) AND CYP2D6'),
    ('hordenine_MAOI',                'hordenine AND (monoamine oxidase OR MAO OR sympathomimetic)'),
    ('phenylethylamine_MAOI',         'phenylethylamine AND (MAOI OR "monoamine oxidase inhibitor" OR "hypertensive crisis")'),
]

results = {}
for label, q in QUERIES:
    print(f'\n## {label}', file=sys.stderr)
    print(f'   query: {q}', file=sys.stderr)
    try:
        ids = search(q, 6)
    except Exception as e:
        print(f'   ERROR: {e}', file=sys.stderr)
        results[label] = {'query': q, 'error': str(e), 'hits': []}
        continue
    if not ids:
        print('   (no hits)', file=sys.stderr)
        results[label] = {'query': q, 'hits': []}
        continue
    sums = summary(ids)
    hits = []
    for pid in ids:
        e = sums.get(pid, {})
        hits.append({
            'pmid': pid,
            'title': e.get('title', ''),
            'source': e.get('fulljournalname') or e.get('source', ''),
            'pubdate': e.get('pubdate', ''),
        })
        print(f'   {pid}  ({e.get("pubdate","")}, {e.get("source","")})', file=sys.stderr)
        print(f'     {e.get("title","")[:160]}', file=sys.stderr)
    results[label] = {'query': q, 'hits': hits}
    time.sleep(0.5)

dest = os.path.join(os.path.dirname(__file__), 'pubmed_candidates.json')
with open(dest, 'w') as f:
    json.dump(results, f, indent=2)
print(f'\nwrote {dest}', file=sys.stderr)
