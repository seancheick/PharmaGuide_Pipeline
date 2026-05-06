#!/usr/bin/env python3
"""Fetch + print abstract for a small set of candidate PMIDs."""
import os, sys, time, urllib.request, urllib.parse, urllib.error

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

KEY = load_env().get('PUBMED_API_KEY', '')

def _get(url, params, retries=4):
    if KEY: params = {**params, 'api_key': KEY}
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(f'{url}?{qs}', headers={'User-Agent': 'pharmaguide-audit/1.0'})
    last = None
    for a in range(retries):
        try:
            return urllib.request.urlopen(req, timeout=15).read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429:
                time.sleep(2**a); continue
            raise
    raise last

def abstract(pmid):
    raw = _get('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi',
               dict(db='pubmed', id=str(pmid), rettype='abstract', retmode='text'))
    return raw.decode('utf-8', errors='replace').strip()

PMIDS = [
    ('pennyroyal',           '8633832'),
    ('pennyroyal_v2',        '25512112'),
    ('tansy',                '28472675'),
    ('maca',                 '31951246'),
    ('maca_v2',              '38440178'),
    ('tryptophan_MAOI',      '31523132'),
    ('mulberry',             '27974904'),
    ('bupleurum_CYP2D6',     '33273809'),
    ('bupleurum_CYP3A4',     '33369126'),
    ('hordenine_MAO',        '2570842'),
    ('PEA_MAOI',             '28655495'),
    ('PEA_MAOI_v2',          '37966854'),
]
for label, pid in PMIDS:
    print(f'\n========== {label}  PMID:{pid} ==========')
    try:
        print(abstract(pid)[:1800])
    except Exception as e:
        print(f'ERROR: {e}')
    time.sleep(0.6)
