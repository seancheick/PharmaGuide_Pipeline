"""Content-verify every PMID in the 2026-09-14 identity batch.

Run from the repo root. Each evidence quote must appear in the PubMed title/abstract
or the Europe PMC open-access full text, and each source PMID listed on an
identity must name one of that identity's registered designations or deposits."""
import json, re, time, unicodedata, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
spec = json.load(open('scripts/audits/probiotic_registry_expansion_2026_09_14/identity_batch_2026_09_14.json'))
def norm(s):
    s = unicodedata.normalize('NFKC', s or '').replace('®', '').replace('™', '')
    return re.sub(r'[^a-z0-9]+', '', s.lower())
def tokens_for(op):
    if op['op'] == 'merge_duplicate': return {norm(op['deposit'].replace('ATCC', ''))}
    if op['op'] == 'correct_deposit': return {'30153', '30172'}
    names = [op['standard_name'], *op['aliases']] if op['op'] == 'add_identity' else op['aliases']
    out = set()
    for n in names:
        for t in re.findall(r'(?:[A-Za-z]+[-\s]?)?\d[\w/]*(?:\s?\d+[A-Z]?)?', n):
            if re.search(r'\d', t) and not re.fullmatch(r'(dsm|lmg|ncimb|atcc)\s?[-\s]?p?[-\s]?\d+', t.lower()):
                out.add(norm(t))
        for m in re.finditer(r'I[-\s]?(\d{3,4})', n):
            out.add('i' + m.group(1))
    return out
def get(url, tries=4):
    for i in range(tries):
        try: return urllib.request.urlopen(url, timeout=90).read()
        except Exception as ex: err = ex; time.sleep(2 * (i + 1))
    raise RuntimeError(f'fetch failed {url}: {err}')
pmids = sorted({e['pmid'] for op in spec['operations'] for e in op['evidence']} | {p for op in spec['operations'] for p in op.get('pmids') or []})
root = ET.fromstring(get('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?' + urllib.parse.urlencode({'db':'pubmed','id':','.join(pmids),'retmode':'xml'})))
abstract, pmc = {}, {}
for art in root.findall('.//PubmedArticle'):
    p = art.findtext('.//MedlineCitation/PMID'); a = art.find('.//Article')
    abstract[p] = (''.join(a.find('ArticleTitle').itertext()) if a.find('ArticleTitle') is not None else '') + ' ' + ' '.join(''.join(x.itertext()) for x in a.findall('Abstract/AbstractText'))
    pmc[p] = next((x.text for x in art.findall('PubmedData/ArticleIdList/ArticleId') if x.get('IdType') == 'pmc'), None)
for op in spec['operations']:
    for e in op['evidence']:
        if e.get('pmcid'): pmc.setdefault(e['pmid'], e['pmcid']); pmc[e['pmid']] = pmc[e['pmid']] or e['pmcid']
full, fetch_err = {}, {}
def fulltext(p):
    if p in full: return full[p]
    full[p] = ''
    if pmc.get(p):
        try:
            full[p] = re.sub(r'<[^>]+>', ' ', get(f'https://www.ebi.ac.uk/europepmc/webservices/rest/{pmc[p]}/fullTextXML').decode('utf-8', 'ignore'))
        except Exception as ex:
            fetch_err[p] = str(ex)[:120]
        time.sleep(0.4)
    return full[p]
fails, checked, via_full = [], 0, 0
for op in spec['operations']:
    toks = tokens_for(op)
    for e in op['evidence']:
        checked += 1; q = norm(e['quote'])
        if q in norm(abstract.get(e['pmid'])): continue
        if q in norm(fulltext(e['pmid'])): via_full += 1; continue
        fails.append((op['key'], e['pmid'], pmc.get(e['pmid']), 'QUOTE_NOT_FOUND', e['quote'][:70]))
    for p in op.get('pmids') or []:
        checked += 1
        if any(t in norm(abstract.get(p)) for t in toks): continue
        if any(t in norm(fulltext(p)) for t in toks): via_full += 1; continue
        fails.append((op['key'], p, pmc.get(p), 'DESIGNATION_NOT_IN_SOURCE', sorted(toks)))
print(f'PMIDs requested {len(pmids)}; returned by PubMed {len(abstract)}; missing {sorted(set(pmids) - set(abstract))}')
print(f'checks {checked}; passed via full text {via_full}; full-text fetch errors {len(fetch_err)} {list(fetch_err.items())[:3]}')
print(f'FAILURES {len(fails)}')
for f in fails: print('  ', f)
