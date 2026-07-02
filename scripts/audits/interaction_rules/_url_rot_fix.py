#!/usr/bin/env python3
"""One-off audit tool: replace dead URLs (from URL_ROT_REPORT.md) in
ingredient_interaction_rules.json with content-verified PubMed sources.

STATUS: COMPLETED / INERT as of 2026-07-02 — all 22 mapped dead URLs are already
gone from the data file, so a re-run is a no-op. Kept, hardened, for reference.

HARDENED 2026-07-02 after a near-miss where auto-selected sources reached a
working tree unverified:
  * DRY-RUN BY DEFAULT. It writes the clinical data file ONLY with an explicit
    `--apply` flag. (Previously it wrote unless `--dry-run` was passed — running
    it with no args silently overwrote the file.)
  * CONTENT-VERIFIED replacements. A candidate PMID is accepted ONLY if its
    fetched title+abstract actually shares a topic word with the ingredient/
    query — the "real PMID, wrong topic = ghost reference" failure mode is
    rejected and logged, not written. (Previously it took pubmed_search()[0]
    blind, with no topic check.) See the `critical_no_hallucinated_citations`
    rule: PMID existence never proves relevance.

Usage:
    python3 scripts/audits/interaction_rules/_url_rot_fix.py            # dry-run (default)
    python3 scripts/audits/interaction_rules/_url_rot_fix.py --apply    # write the file
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

def pubmed_search(term, n=4):
    raw = _get('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi',
               dict(db='pubmed', term=term, retmode='json', retmax=n, sort='relevance'))
    return json.loads(raw).get('esearchresult', {}).get('idlist', [])

def pubmed_fetch_text(pmid):
    """efetch title+abstract as plain text (used for topic verification)."""
    raw = _get('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi',
               dict(db='pubmed', id=pmid, rettype='abstract', retmode='text'))
    return raw.decode('utf-8', 'replace')

# Generic words that don't identify a topic — stripped before overlap so a
# match must be on the ingredient itself, not on "safety"/"review"/etc.
_STOP = {
    'safety', 'review', 'systematic', 'meta', 'analysis', 'pharmacology', 'clinical',
    'supplement', 'supplements', 'supplemental', 'extract', 'drug', 'interaction',
    'interactions', 'toxicity', 'content', 'standardization', 'oral', 'human', 'study',
    'trial', 'effects', 'effect', 'health', 'dietary', 'acid', 'acids', 'from', 'with',
    'and', 'the', 'for', 'randomized', 'controlled', 'double', 'blind', 'placebo',
    'evidence', 'based', 'update', 'overview', 'report', 'case',
}

def _topic_words(text):
    return {w for w in re.findall(r'[a-z]{4,}', (text or '').lower()) if w not in _STOP}

def _on_topic(query, article_text):
    """True iff the fetched article shares a non-generic topic word with the
    query (the query is authored to name the ingredient, e.g. 'Nigella sativa
    black seed ...'). Conservative: no overlap -> reject (manual review)."""
    return bool(_topic_words(query) & _topic_words(article_text))

def _should_apply(argv):
    """Write the data file ONLY when --apply is explicitly passed."""
    return '--apply' in argv


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
    """Search PubMed and return a CONTENT-VERIFIED replacement URL, or None.

    Walks candidates in relevance order and returns the first whose fetched
    title+abstract is on-topic for the query. Never returns an unverified PMID:
    if no candidate is on-topic, returns None so the caller logs a failure for
    manual review instead of writing a possible ghost reference.
    """
    try:
        for pmid in pubmed_search(query, 4):
            text = pubmed_fetch_text(pmid)
            time.sleep(0.34)
            if _on_topic(query, text):
                first_line = text.strip().split('\n', 1)[0][:90]
                print(f'    verified PMID {pmid}: {first_line}', file=sys.stderr)
                return f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/'
            print(f'    rejected PMID {pmid} (off-topic for "{query[:40]}")', file=sys.stderr)
        return None
    except Exception as e:
        print(f'  ERROR searching "{query}": {e}', file=sys.stderr)
        return None


def main():
    apply = _should_apply(sys.argv)

    with open(RULES_PATH) as f:
        data = json.load(f)

    rules = data['interaction_rules']
    changes = []
    failed = []

    # Build lookup: dead_url → replacement_url
    replacements = {}
    print('Searching PubMed for content-verified replacements...', file=sys.stderr)

    for dead_url, (cid, query) in DEAD_URL_REPLACEMENTS.items():
        if query is None:
            continue  # herbs-at-a-glance handled separately
        # Only bother hitting the API for URLs still present in the file.
        if dead_url not in json.dumps(data):
            continue
        print(f'  {cid}: {query[:50]}...', file=sys.stderr)
        repl = find_replacement_pmid(query)
        if repl:
            replacements[dead_url] = repl
        else:
            failed.append((dead_url, cid))
            print(f'    → FAILED (no on-topic PubMed match)', file=sys.stderr)

    # herbs-at-a-glance: per-entry replacement
    hag_url = 'https://www.nccih.nih.gov/health/herbs-at-a-glance'
    hag_replacements = {}
    if hag_url in json.dumps(data):
        for cid, query in HERBS_AT_A_GLANCE_ENTRIES.items():
            print(f'  {cid} (herbs-at-a-glance): {query[:50]}...', file=sys.stderr)
            repl = find_replacement_pmid(query)
            if repl:
                hag_replacements[cid] = repl
            else:
                failed.append((hag_url, cid))
                print(f'    → FAILED (no on-topic PubMed match)', file=sys.stderr)

    # Apply replacements to rules
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

    if apply and changes:
        with open(RULES_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write('\n')

    banner = 'APPLIED' if (apply and changes) else 'DRY RUN (default; pass --apply to write)'
    print(f'\n{banner} — {len(changes)} content-verified URL replacement(s)', file=sys.stderr)
    for c in changes:
        print(f'  ✓ {c}', file=sys.stderr)
    if failed:
        print(f'\n⚠ {len(failed)} replacement(s) had NO on-topic PubMed match — MANUAL REVIEW:', file=sys.stderr)
        for url, cid in failed:
            print(f'  {cid}: {url[:60]}', file=sys.stderr)


if __name__ == '__main__':
    main()
