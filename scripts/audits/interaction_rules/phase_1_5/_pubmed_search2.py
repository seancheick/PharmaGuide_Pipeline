#!/usr/bin/env python3
"""Round 2 — narrower PubMed queries for the items round 1 missed."""
import json, os, sys, time, urllib.request, urllib.parse, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
def env():
    keys={}
    p=os.path.join(ROOT,'.env')
    if os.path.exists(p):
        for L in open(p):
            L=L.strip()
            if L and '=' in L and not L.startswith('#'):
                k,v=L.split('=',1); keys[k.strip()]=v.strip().strip('"').strip("'")
    return keys
KEY=env().get('PUBMED_API_KEY','')
def G(u,p,r=4):
    if KEY: p={**p,'api_key':KEY}
    qs=urllib.parse.urlencode(p)
    req=urllib.request.Request(f'{u}?{qs}',headers={'User-Agent':'pharmaguide-audit/1.0'})
    last=None
    for a in range(r):
        try: return urllib.request.urlopen(req,timeout=15).read()
        except urllib.error.HTTPError as e:
            last=e
            if e.code==429: time.sleep(2**a); continue
            raise
    raise last

def search(t,n=8): return json.loads(G('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi',dict(db='pubmed',term=t,retmode='json',retmax=n,sort='relevance'))).get('esearchresult',{}).get('idlist',[])
def summary(ids):
    if not ids: return {}
    return json.loads(G('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi',dict(db='pubmed',id=','.join(ids),retmode='json'))).get('result',{})
def absx(pmid): return G('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi',dict(db='pubmed',id=str(pmid),rettype='abstract',retmode='text')).decode('utf-8','replace').strip()

QUERIES = [
  ('SAMe_serotonin',         'SAMe AND serotonin syndrome AND case'),
  ('SAMe_antidepressant',    '"S-adenosyl-L-methionine" AND antidepressant AND review'),
  ('sodium_lithium_diet',    'lithium toxicity AND (sodium restriction OR low-salt OR salt intake)'),
  ('sodium_lithium_review',  'lithium therapy AND sodium AND (toxicity OR safety) AND review'),
  ('tyramine_MAOI_review',   'tyramine AND MAOI AND (cheese reaction OR hypertensive crisis)'),
]

results={}
for label,q in QUERIES:
    print(f'\n## {label}',file=sys.stderr); print(f'   query: {q}',file=sys.stderr)
    try: ids=search(q,6)
    except Exception as e: print(f'   ERROR {e}',file=sys.stderr); continue
    if not ids: print('   (no hits)',file=sys.stderr); continue
    sums=summary(ids)
    for pid in ids:
        e=sums.get(pid,{})
        print(f'   {pid}  ({e.get("pubdate","")}, {e.get("source","")})',file=sys.stderr)
        print(f'     {e.get("title","")[:160]}',file=sys.stderr)
    time.sleep(0.7)
