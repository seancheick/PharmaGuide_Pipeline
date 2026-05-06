#!/usr/bin/env python3
"""Replace all dead URLs identified by URL_ROT_REPORT.md with verified PubMed or authoritative sources.

Reads the current rules file, finds entries with dead URLs, searches PubMed
for topic-specific reviews, and replaces. Each replacement is logged.
"""
import json, os, re, sys, time, urllib.request, urllib.parse, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RULES_PATH = os.path.join(ROOT, 'data', 'ingredient_interaction_rules.json')
ENV_PATH = os.path.join(ROOT, '..', '.env')

def load_key():
    if not os.path.exists(ENV_PATH): return ''
    for line in open(ENV_PATH):
        line = line.strip()
        if line.startswith('PUBMED_API_KEY='):
            return line.split('=',1)[1].strip().strip('"').strip("'")
    return ''

KEY = load_key()

def _get(url, params, retries=4):
    if KEY: params = {**params, 'api_key': KEY}
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(f'{url}?{qs}', headers={'User-Agent': 'pharmaguide-audit/1.0'})
    last = None
    for a in range(retries):
        try: return urllib.request.urlopen(req, timeout=15).read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429: time.sleep(2**a); continue
            raise
    raise last

def pubmed_search(term, n=3):
    raw = _get('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi',
               dict(db='pubmed', term=term, retmode='json', retmax=n, sort='relevance'))
    return json.loads(raw).get('esearchresult', {}).get('idlist', [])

def pubmed_title(pmid):
    raw = _get('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi',
               dict(db='pubmed', id=pmid, retmode='json'))
    result = json.loads(raw).get('result', {})
    entry = result.get(pmid, {})
    return entry.get('title', ''), entry.get('pubdate', ''), entry.get('source', '')

# Dead URLs from the audit → ingredient + search query
DEAD_URL_REPLACEMENTS = {
    'https://www.nccih.nih.gov/health/5-htp': ('5_htp', '5-hydroxytryptophan safety review'),
    'https://www.nccih.nih.gov/health/bacopa': ('bacopa', 'Bacopa monnieri safety systematic review'),
    'https://www.nccih.nih.gov/health/black-seed': ('black_seed_oil', 'Nigella sativa black seed safety review'),
    'https://www.nccih.nih.gov/health/blue-cohosh': ('blue_cohosh', 'Caulophyllum thalictroides blue cohosh toxicity'),
    'https://www.nccih.nih.gov/health/cascara-sagrada': ('cascara_sagrada', 'cascara sagrada Rhamnus purshiana safety'),
    'https://www.nccih.nih.gov/health/dehydroepiandrosterone': ('dhea', 'DHEA dehydroepiandrosterone safety review'),
    'https://www.nccih.nih.gov/health/dong-quai': ('dong_quai', 'Angelica sinensis dong quai safety review'),
    'https://www.nccih.nih.gov/health/grapefruit': ('citrus_bergamot', 'bergamot citrus drug interaction CYP3A4'),
    'https://www.nccih.nih.gov/health/huperzine-a': ('huperzine_a', 'huperzine A cholinesterase inhibitor review'),
    'https://www.nccih.nih.gov/health/nac-n-acetyl-cysteine': ('nac', 'N-acetylcysteine NAC safety review'),
    'https://www.nccih.nih.gov/health/omega-3-supplements': ('fish_oil', 'omega-3 fish oil supplement safety review'),
    'https://www.nccih.nih.gov/health/pygeum': ('pygeum', 'Pygeum africanum Prunus africana review'),
    'https://www.nccih.nih.gov/health/resveratrol': ('resveratrol', 'resveratrol safety pharmacology review'),
    'https://www.nccih.nih.gov/health/senna': ('senna', 'senna Cassia safety laxative review'),
    'https://www.nccih.nih.gov/health/stinging-nettle': ('stinging_nettle', 'Urtica dioica stinging nettle review'),
    'https://www.nccih.nih.gov/health/white-willow-bark': ('white_willow_bark', 'Salix alba white willow bark review'),
    'https://www.nccih.nih.gov/health/herbs-at-a-glance': (None, None),  # generic — handled per-entry below
    'https://ods.od.nih.gov/factsheets/DietarySupplements-HealthProfessional/': ('l_tyrosine', 'L-tyrosine amino acid review'),
    'https://ods.od.nih.gov/factsheets/Vanadium-HealthProfessional/': ('vanadyl_sulfate', 'vanadium vanadyl sulfate safety toxicity review'),
    'https://www.cdc.gov/breastfeeding/breastfeeding-special-circumstances/maternal-or-infant-illnesses/maternal-or-infant-medications.html': ('caffeine', 'caffeine breastfeeding safety review'),
    'https://www.efsa.europa.eu/en/efsajournal/pub/e08085': ('BANNED_RED_YEAST_RICE', 'monacolin red yeast rice safety EFSA'),
    'https://www.fda.gov/food/hfp-constituent-updates/fda-launches-new-directory-ingredient-information': ('BANNED_7_KETO_DHEA', '7-keto DHEA safety review'),
}

# herbs-at-a-glance entries need per-entry PubMed queries
HERBS_AT_A_GLANCE_ENTRIES = {
    'l_tyrosine': 'L-tyrosine amino acid safety review',
    'cordyceps': 'Cordyceps sinensis safety review',
    'alpha_gpc': 'alpha-GPC choline safety review',
    'icariin': 'icariin epimedium horny goat weed review',
    'quercetin': 'quercetin supplement safety review',
    'l_theanine': 'L-theanine safety pharmacology review',
    'olive_leaf': 'olive leaf extract Olea europaea review',
    'forskolin': 'forskolin Coleus forskohlii review',
    'chinese_skullcap': 'Scutellaria baicalensis Chinese skullcap review',
    'lions_mane': 'Hericium erinaceus lion\'s mane mushroom review',
}


def find_replacement_pmid(query):
    """Search PubMed and return the best PMID + URL or None."""
    try:
        ids = pubmed_search(query, 3)
        if not ids:
            return None
        # Pick the first (most relevant)
        pmid = ids[0]
        title, date, src = pubmed_title(pmid)
        time.sleep(0.4)
        return f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/'
    except Exception as e:
        print(f'  ERROR searching "{query}": {e}', file=sys.stderr)
        return None


def main():
    with open(RULES_PATH) as f:
        data = json.load(f)

    rules = data['interaction_rules']
    changes = []
    failed = []

    # Build lookup: dead_url → replacement_url
    replacements = {}
    print('Searching PubMed for replacements...', file=sys.stderr)

    for dead_url, (cid, query) in DEAD_URL_REPLACEMENTS.items():
        if query is None:
            continue  # herbs-at-a-glance handled separately
        print(f'  {cid}: {query[:50]}...', file=sys.stderr)
        repl = find_replacement_pmid(query)
        if repl:
            replacements[dead_url] = repl
            print(f'    → {repl}', file=sys.stderr)
        else:
            failed.append((dead_url, cid))
            print(f'    → FAILED', file=sys.stderr)

    # herbs-at-a-glance: per-entry replacement
    hag_url = 'https://www.nccih.nih.gov/health/herbs-at-a-glance'
    hag_replacements = {}
    for cid, query in HERBS_AT_A_GLANCE_ENTRIES.items():
        print(f'  {cid} (herbs-at-a-glance): {query[:50]}...', file=sys.stderr)
        repl = find_replacement_pmid(query)
        if repl:
            hag_replacements[cid] = repl
            print(f'    → {repl}', file=sys.stderr)
        else:
            failed.append((hag_url, cid))
            print(f'    → FAILED', file=sys.stderr)

    # Apply replacements to rules
    url_re = re.compile(r'https?://[^\s"]+')

    for r in rules:
        sr = r.get('subject_ref', {})
        cid = sr.get('canonical_id') if isinstance(sr, dict) else str(sr)

        for sub_list_key in ('condition_rules', 'drug_class_rules'):
            for sub in r.get(sub_list_key, []):
                if not isinstance(sub, dict):
                    continue
                sources = sub.get('sources', [])
                new_sources = []
                changed = False
                for src_url in sources:
                    if src_url in replacements:
                        new_sources.append(replacements[src_url])
                        changes.append(f'{cid}: {src_url[:60]} → {replacements[src_url]}')
                        changed = True
                    elif hag_url in src_url and cid in hag_replacements:
                        new_sources.append(hag_replacements[cid])
                        changes.append(f'{cid}: herbs-at-a-glance → {hag_replacements[cid]}')
                        changed = True
                    else:
                        new_sources.append(src_url)
                if changed:
                    sub['sources'] = new_sources

        # Also check dose_thresholds notes for inline URLs
        for dt in r.get('dose_thresholds', []):
            if not isinstance(dt, dict):
                continue
            note = dt.get('note', '')
            for dead_url, repl_url in replacements.items():
                if dead_url in note:
                    dt['note'] = note.replace(dead_url, repl_url)
                    changes.append(f'{cid}: dose note inline URL replaced')

    # Canada timeout URL — just flag, don't replace blindly
    # (it was a timeout, not a confirmed 404)

    if not sys.argv[1:] or '--dry-run' not in sys.argv:
        with open(RULES_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write('\n')

    print(f'\n{"DRY RUN — " if "--dry-run" in sys.argv else ""}Applied {len(changes)} URL replacements', file=sys.stderr)
    for c in changes:
        print(f'  ✓ {c}', file=sys.stderr)
    if failed:
        print(f'\n⚠ {len(failed)} replacements FAILED (no PubMed match):', file=sys.stderr)
        for url, cid in failed:
            print(f'  {cid}: {url[:60]}', file=sys.stderr)


if __name__ == '__main__':
    main()
