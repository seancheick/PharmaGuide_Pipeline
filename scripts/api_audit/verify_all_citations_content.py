#!/usr/bin/env python3
"""Content-verify every PubMed citation across all pipeline data files.

Goes beyond existence checks — fetches the actual article title and abstract
from PubMed, then checks whether the cited paper actually mentions the
ingredients/drugs/nutrients claimed in the data entry.

Every citation field is read: configured sources, plus (``scan_all``) every
PubMed URL, "PMID n", PMC link and DOI anywhere in an entry except the history
keys in HISTORY_KEYS. A DOI is checked against its PubMed record when PubMed
indexes it, otherwise against Crossref's title and abstract. Citations in ingredient_interaction_rules.json and
backed_clinical_studies.json have their own verifiers.
test_every_citation_in_the_data_folder_is_read_by_a_content_verifier fails on
any citation in scripts/data that no verifier reads.

Usage (source scripts/python_env.sh first; every run hits the PubMed API):
    # Release gate: every citation, failing only on new mismatches or unresolved PMIDs
    $PG_PYTHON scripts/api_audit/verify_all_citations_content.py --baseline scripts/data/citation_content_backlog.json

    # A curated-data batch: only entries changed since a ref, one line per citation
    $PG_PYTHON scripts/api_audit/verify_all_citations_content.py --changed-since origin/main

    # One file, or a JSON report
    $PG_PYTHON scripts/api_audit/verify_all_citations_content.py --file timing_rules.json
    $PG_PYTHON scripts/api_audit/verify_all_citations_content.py --report scripts/reports/citation_content_audit.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
DATA_DIR = SCRIPTS_ROOT / "data"

if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from api_audit.pubmed_xml import element_text  # noqa: E402

PMID_RE = re.compile(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)")
# Free text cites as a PubMed URL, "PMID 123" or a PMC article link; a PMC id is
# resolved to its PMID when fetched (resolve_pmc_ids).
TEXT_CITATION_RE = re.compile(
    r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)|\bPMID[:\s#]*(\d{4,9})"
    r"|(?:ncbi\.nlm\.nih\.gov/pmc/articles|pmc\.ncbi\.nlm\.nih\.gov/articles)/(PMC\d+)",
    re.I,
)
# A DOI in any form (doi.org URL, "DOI: 10...", a typed {"type": "doi", "id": ...}).
# Q57 (2026-10-02): unread DOIs let 106 registry citations point at unrelated
# or nonexistent papers.
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>,;]+)")
PMC_IDCONV = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
CROSSREF_WORKS = "https://api.crossref.org/works/"
RATE_LIMIT = 0.35  # seconds between API calls
PMC_IDCONV_MAX_ATTEMPTS = 3
PMC_IDCONV_RETRYABLE_HTTP = {429, 500, 502, 503, 504}

# SSL context — prefer verified; fall back to unverified if system certs are unavailable
try:
    SSL_CTX = ssl.create_default_context()
except ssl.SSLError:
    SSL_CTX = ssl._create_unverified_context()

# Unverified fallback for corporate proxies / macOS cert issues
SSL_CTX_UNVERIFIED = ssl._create_unverified_context()


# ── Data file definitions ─────────────────────────────────────────────


def _context_topic_texts(context: dict) -> list[str]:
    """Return context claims defensively, even when a row is malformed."""
    if not isinstance(context, dict):
        return []
    population = context.get("population")
    population_description = population.get("description", "") if isinstance(population, dict) else ""
    outcomes = context.get("outcomes")
    outcome_names = " ".join(
        str(outcome.get("name", "")) for outcome in outcomes
        if isinstance(outcome, dict)
    ) if isinstance(outcomes, list) else ""
    limitations = context.get("limitations")
    limitation_text = " ".join(item for item in limitations if isinstance(item, str)) \
        if isinstance(limitations, list) else ""
    return [context.get("condition", ""), population_description, outcome_names, limitation_text]

IDENTITY_KEYS = ("standard_name", "name", "latin_name", "aliases", "canonical_id", "canonical_ids",
                 "ingredients", "set_canonical_id", "raw_ingredient_text", "_key")


def _identity_texts(entry: dict) -> list:
    """Names an entry is about: its own name fields plus IQM form names/aliases."""
    texts = []
    for key in IDENTITY_KEYS:
        value = entry.get(key)
        texts += value if isinstance(value, list) else [value]
    for form_name, form in (entry.get("forms") or {}).items():
        texts.append(form_name)
        texts += list((form or {}).get("aliases") or [])
    return [t.replace("_", " ") if isinstance(t, str) else t for t in texts]


def _scan_all(**config) -> dict:
    """Config for a file whose citations sit in free text across each entry:
    every string is read except the history/audit keys in HISTORY_KEYS."""
    return {"id_field": "id", "topic_extractor": _identity_texts, "scan_all": True,
            "sources_field": "__none__", **config}


# History and audit fields: they name PMIDs that were screened, rejected,
# replaced or re-checked, so they are not claims. Everything else is read.
HISTORY_KEYS = {"change_log", "previous_citation", "swap_reason", "literature_review",
                "citation_review_note", "top_pubmed_pmids", "verification"}

FILE_CONFIGS = [
    {
        "file": "timing_rules.json",
        "array_key": "timing_rules",
        "id_field": "id",
        "topic_fields": ["ingredient1", "ingredient2", "advice", "mechanism"],
        "sources_field": "sources",
    },
    {
        "file": "medication_depletions.json",
        "array_key": "depletions",
        "id_field": "id",
        "topic_extractor": lambda e: [
            e.get("drug_ref", {}).get("display_name", ""),
            e.get("depleted_nutrient", {}).get("standard_name", ""),
            e.get("mechanism", ""),
        ],
        "sources_field": "sources",
        "scan_all": True,  # watch_basis, source labels
    },
    {
        "file": "curated_interactions/curated_interactions_v1.json",
        "array_key": "interactions",
        "id_field": "id",
        "topic_fields": ["agent1_name", "agent2_name", "mechanism"],
        "sources_field": "source_urls",
        "source_format": "url_list",  # list of URL strings, not dicts
        "scan_all": True,  # dose_threshold.source, mechanism text
    },
    {
        "file": "curated_interactions/batch_critical_2026_05.json",
        "array_key": "interactions",
        "id_field": "id",
        "topic_fields": ["agent1_name", "agent2_name", "mechanism"],
        "sources_field": "source_urls",
        "source_format": "url_list",
        "scan_all": True,
    },
    {
        "file": "curated_interactions/med_med_pairs_v1.json",
        "array_key": "interactions",
        "id_field": "id",
        "topic_fields": ["agent1_name", "agent2_name", "mechanism"],
        "sources_field": "source_urls",
        "source_format": "url_list",
    },
    {
        # Therapeutic dosing: references[] is a list of bare PMID strings.
        # Topic words come from the ingredient name + its aliases + common use.
        "file": "rda_therapeutic_dosing.json",
        "array_key": "therapeutic_dosing",
        "id_field": "id",
        "topic_extractor": lambda e: (
            [e.get("standard_name", ""), e.get("common_use", "")]
            + list(e.get("aliases") or [])
        ),
        "sources_field": "references",
        "source_format": "pmid_list",
    },
    {
        # Optimal RDA/UL file: only the non-DRI bioactive entries carry a
        # references[] list of bare PMID strings (DRI-backed nutrients are
        # verified separately by verify_rda_uls.py). Entries with no
        # references[] are simply skipped (no PubMed citations to check).
        "file": "rda_optimal_uls.json",
        "array_key": "nutrient_recommendations",
        "id_field": "id",
        "topic_extractor": lambda e: (
            [e.get("standard_name", ""), e.get("special_considerations", "")]
            + list(e.get("aliases") or [])
        ),
        "sources_field": "references",
        "source_format": "pmid_list",
    },
    {
        # Probiotic strain database: citations live inside
        # cfu_thresholds.evidence and the source-owned study_contexts.
        # Some entries are formula-backed (for example Seed DS-01), so include
        # notable_studies/key_benefits in topic extraction instead of checking
        # only the exact strain code.
        "file": "clinically_relevant_strains.json",
        "array_key": "clinically_relevant_strains",
        "id_field": "id",
        "topic_extractor": lambda e: (
            [
                e.get("standard_name", ""),
                e.get("notable_studies", ""),
                (e.get("cfu_thresholds") or {}).get("indication_primary", ""),
                ((e.get("cfu_thresholds") or {}).get("evidence") or {}).get("source_short", ""),
            ]
            + list(e.get("aliases") or [])
            + list(e.get("key_benefits") or [])
        ),
        "source_format": "nested_cfu_evidence_pmids",
        "context_topic_extractor": _context_topic_texts,
        "scan_all": True,  # identity_verification, dose provenance, secondary indications
    },
    _scan_all(file="ingredient_quality_map.json", map_key=""),
    _scan_all(file="botanical_ingredients.json", array_key="botanical_ingredients"),
    _scan_all(file="standardized_botanicals.json", array_key="standardized_botanicals"),
    _scan_all(file="harmful_additives.json", array_key="harmful_additives"),
    _scan_all(file="banned_recalled_ingredients.json", array_key="ingredients"),
    _scan_all(file="other_ingredients.json", array_key="other_ingredients"),
    _scan_all(file="synergy_cluster.json", array_key="synergy_clusters"),
    _scan_all(file="botanical_marker_contributions.json", map_key="botanicals"),
    _scan_all(file="branded_blend_anchor_overrides.json", array_key="anchors"),
    _scan_all(file="absorption_enhancers.json", array_key="absorption_enhancers"),
    _scan_all(file="enhanced_delivery.json", map_key=""),
    _scan_all(file="interaction_orphan_allowlist.json", array_key="allowlist"),
    _scan_all(file="curated_overrides/product_context_canonical_overrides.json", map_key="overrides"),
]
def doi_id(raw: str) -> str:
    """Citation id of a DOI: "doi:" + the lowercased DOI, without the sentence
    punctuation that free text leaves after it (an unbalanced ")" or a ".")."""
    doi = raw.rstrip(".").lower()
    while doi.endswith(")") and doi.count(")") > doi.count("("):
        doi = doi[:-1].rstrip(".")
    return "doi:" + doi


def cite_label(cid: str) -> str:
    """How a citation id prints: "PMID 123", "PMC123" or "doi:10..."."""
    return cid if not cid.isdigit() else f"PMID {cid}"


# ── PubMed API ─────────────────────────────────────────────────────────

def resolve_pmc_ids(pmc_ids: list[str]) -> dict[str, str]:
    """PMC id -> PMID through NCBI's PMC ID converter (unresolved ids are left out)."""
    resolved = {}
    for i in range(0, len(pmc_ids), 100):
        url = f"{PMC_IDCONV}?ids={','.join(pmc_ids[i:i + 100])}&format=json&tool=pharmaguide-audit"
        req = urllib.request.Request(url, headers={"User-Agent": "pharmaguide-audit/1.0"})
        for attempt in range(1, PMC_IDCONV_MAX_ATTEMPTS + 1):
            try:
                with urllib.request.urlopen(req, timeout=20, context=SSL_CTX) as resp:
                    for record in json.loads(resp.read().decode("utf-8")).get("records", []):
                        if record.get("pmcid") and record.get("pmid"):
                            resolved[record["pmcid"].upper()] = str(record["pmid"])
                break
            except urllib.error.HTTPError as error:
                retryable = error.code in PMC_IDCONV_RETRYABLE_HTTP
                if not retryable or attempt == PMC_IDCONV_MAX_ATTEMPTS:
                    print(f"  PMC ID converter error: {error}", file=sys.stderr)
                    break
                retry_after = error.headers.get("Retry-After") if error.headers else None
                try:
                    delay = max(float(retry_after), 0.0) if retry_after is not None else float(attempt)
                except ValueError:
                    delay = float(attempt)
                print(
                    f"  PMC ID converter HTTP {error.code}; retrying "
                    f"({attempt}/{PMC_IDCONV_MAX_ATTEMPTS}) in {delay:g}s",
                    file=sys.stderr,
                )
                time.sleep(delay)
            except Exception as error:
                print(f"  PMC ID converter error: {error}", file=sys.stderr)
                break
        time.sleep(RATE_LIMIT)
    return resolved


def _get(url: str) -> bytes | None:
    """GET a URL; None on HTTP 404 (and on other errors, which are logged)."""
    req = urllib.request.Request(url, headers={"User-Agent": "pharmaguide-audit/1.0 (citation verification)"})
    try:
        with urllib.request.urlopen(req, timeout=20, context=SSL_CTX) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        if e.code != 404:
            print(f"  HTTP {e.code} for {url}", file=sys.stderr)
    except Exception as e:
        print(f"  API error for {url}: {e}", file=sys.stderr)
    return None


def resolve_doi_ids(doi_ids: list[str]) -> tuple[dict[str, str], dict[str, dict]]:
    """("doi:..." -> PMID for DOIs PubMed indexes, "doi:..." -> Crossref article
    for the rest). A DOI neither knows is left out: it does not resolve."""
    to_pmid, crossref = {}, {}
    for cid in doi_ids:
        doi = cid[len("doi:"):]
        raw = _get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&retmode=json&term="
                   + urllib.parse.quote(doi + "[doi]", safe=""))
        time.sleep(RATE_LIMIT)
        ids = json.loads(raw).get("esearchresult", {}).get("idlist", []) if raw else []
        if len(ids) == 1:
            to_pmid[cid] = ids[0]
            continue
        raw = _get(CROSSREF_WORKS + urllib.parse.quote(doi, safe=""))
        time.sleep(1)  # Crossref's public pool
        if raw:
            work = json.loads(raw).get("message", {})
            crossref[cid] = {
                "title": " ".join(work.get("title") or []),
                "abstract": re.sub(r"<[^>]+>", "", work.get("abstract") or "").strip(),
                "mesh_terms": [],
            }
    return to_pmid, crossref


def fetch_articles(pmids: list[str], abstract_chars: int | None = 800) -> dict[str, dict]:
    """Fetch title + abstract for a batch of PMIDs via efetch.

    ``abstract_chars=None`` keeps the whole abstract. A PMC id ("PMC123") is
    resolved to its PMID first and its article is returned under both ids; a
    DOI id ("doi:10...") likewise, or from Crossref when PubMed lacks it.
    """
    articles = {}
    pmc_ids = sorted({p for p in pmids if str(p).upper().startswith("PMC")})
    pmc_to_pmid = resolve_pmc_ids(pmc_ids) if pmc_ids else {}
    doi_ids = sorted({p for p in pmids if str(p).startswith("doi:")})
    doi_to_pmid, crossref = resolve_doi_ids(doi_ids) if doi_ids else ({}, {})
    articles.update(crossref)
    pmids = list(dict.fromkeys([p for p in pmids if p not in pmc_ids and p not in doi_ids]
                               + list(pmc_to_pmid.values()) + list(doi_to_pmid.values())))
    for i in range(0, len(pmids), 8):
        batch = pmids[i:i + 8]
        ids_str = ",".join(batch)
        url = (
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            f"?db=pubmed&id={ids_str}&retmode=xml"
        )
        api_key = os.environ.get("NCBI_API_KEY") or os.environ.get("PUBMED_API_KEY", "")
        if api_key:
            url += f"&api_key={api_key}"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "pharmaguide-audit/1.0"})
            try:
                with urllib.request.urlopen(req, timeout=20, context=SSL_CTX) as resp:
                    raw = resp.read().decode("utf-8")
            except Exception as _ssl_err:
                if "SSL" in str(_ssl_err) or "certificate" in str(_ssl_err).lower():
                    with urllib.request.urlopen(req, timeout=20, context=SSL_CTX_UNVERIFIED) as resp:
                        raw = resp.read().decode("utf-8")
                else:
                    raise
            root = ET.fromstring(raw)

            # A book record (PubmedBookArticle: NBK chapters, HTA dossiers) has a
            # BookTitle instead of an ArticleTitle; without it, it read as "not found".
            for article in root.findall(".//PubmedArticle") + root.findall(".//PubmedBookArticle"):
                pmid_el = article.find(".//PMID")
                if pmid_el is None:
                    continue
                pmid = pmid_el.text.strip()

                title = element_text(article.find(".//ArticleTitle")) or element_text(article.find(".//BookTitle"))

                # Collect all abstract sections
                abstract_parts = []
                for abs_el in article.findall(".//AbstractText"):
                    text = element_text(abs_el)
                    if text:
                        abstract_parts.append(text)
                abstract = " ".join(abstract_parts)

                # Collect MeSH terms
                mesh_terms = []
                for mesh in article.findall(".//MeshHeading/DescriptorName"):
                    if mesh.text:
                        mesh_terms.append(mesh.text.lower())

                articles[pmid] = {
                    "title": title,
                    "abstract": abstract if abstract_chars is None else abstract[:abstract_chars],
                    "mesh_terms": mesh_terms,
                }
        except Exception as e:
            print(f"  API error batch {i}: {e}", file=sys.stderr)

        time.sleep(RATE_LIMIT)

    for alias, pmid in [*pmc_to_pmid.items(), *doi_to_pmid.items()]:
        if pmid in articles:
            articles[alias] = articles[pmid]
    return articles


def search_pubmed(query: str, max_results: int = 3) -> list[dict]:
    """Search PubMed for papers matching a query. Returns [{pmid, title}]."""
    encoded = urllib.parse.quote(query)
    url = (
        f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        f"?db=pubmed&term={encoded}&retmax={max_results}&sort=relevance&retmode=xml"
    )
    api_key = os.environ.get("NCBI_API_KEY") or os.environ.get("PUBMED_API_KEY", "")
    if api_key:
        url += f"&api_key={api_key}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "pharmaguide-audit/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15, context=SSL_CTX) as resp:
                raw = resp.read().decode("utf-8")
        except Exception as _ssl_err:
            if "SSL" in str(_ssl_err) or "certificate" in str(_ssl_err).lower():
                with urllib.request.urlopen(req, timeout=15, context=SSL_CTX_UNVERIFIED) as resp:
                    raw = resp.read().decode("utf-8")
            else:
                raise
        root = ET.fromstring(raw)
        pmids = [el.text for el in root.findall(".//Id")]
        time.sleep(RATE_LIMIT)

        if not pmids:
            return []

        articles = fetch_articles(pmids)
        return [
            {"pmid": p, "title": articles.get(p, {}).get("title", "")}
            for p in pmids
            if p in articles
        ]
    except Exception as e:
        print(f"  Search error: {e}", file=sys.stderr)
        return []


# ── Content matching ───────────────────────────────────────────────────

def extract_topic_words(entry: dict, config: dict) -> list[str]:
    """Extract topic words from an entry for content matching."""
    texts = []
    if "topic_extractor" in config:
        texts = config["topic_extractor"](entry)
    else:
        for field in config.get("topic_fields", []):
            val = entry.get(field, "")
            if isinstance(val, str):
                texts.append(val)

    words = set()
    for text in texts:
        # Topic extractors may intentionally return optional fields as None.
        # Treat those as absent instead of crashing the whole citation audit.
        if not isinstance(text, str):
            continue
        for word in re.split(r"[\s/,\(\)_\-]+", text.lower()):
            if len(word) > 3 and word not in {
                "with", "that", "this", "from", "into", "when", "your",
                "take", "avoid", "class", "drug", "both", "risk", "does",
                "have", "been", "also", "most", "more", "used", "than",
                "some", "very", "only", "such", "each", "which", "their",
                "other", "about", "supplement", "supplements", "medication",
                "medications",
            }:
                words.add(word)
    return list(words)


def extract_context_topic_words(context: dict, config: dict) -> list[str]:
    """Extract terms for a citation attached to a specific study context.

    Context PMIDs often concern a condition that is unrelated to the parent
    strain's general ``notable_studies`` text.  Verifying those PMIDs against
    only the parent terms creates false mismatches (and can hide a real check
    failure in a noisy report), so use the context's own condition, population,
    outcomes and limitations when available.
    """
    extractor = config.get("context_topic_extractor")
    if not callable(extractor):
        return []
    return extract_topic_words(context, {
        "topic_extractor": extractor,
    })


def content_matches(article: dict, topic_words: list[str]) -> tuple[str, float]:
    """Check if an article's content matches the claimed topic.

    Returns (status, confidence):
    - "match" (>= 2 topic words found in title+abstract+mesh)
    - "partial" (1 topic word found)
    - "mismatch" (0 topic words found)
    """
    if not article:
        return "not_found", 0.0

    text = (
        article.get("title", "")
        + " "
        + article.get("abstract", "")
        + " "
        + " ".join(article.get("mesh_terms", []))
    ).lower()

    matches = [w for w in topic_words if w in text]
    ratio = len(matches) / max(len(topic_words), 1)

    if len(matches) >= 2:
        return "match", ratio
    elif len(matches) == 1:
        return "partial", ratio
    else:
        return "mismatch", 0.0


# ── Extract PMIDs from entries ─────────────────────────────────────────

def scan_citations(value, exempt: set, key: str = "") -> list[str]:
    """Every PubMed/PMC/DOI citation in a nested value, skipping ``exempt`` keys.

    Strings are read for PubMed URLs, "PMID 123", PMC links and DOIs; a bare number
    counts only under a key naming a PMID ("pmid", "source_pmids").
    """
    found = []
    if isinstance(value, dict):
        for k, v in value.items():
            if k != "_metadata" and k not in exempt:
                found += scan_citations(v, exempt, k)
    elif isinstance(value, list):
        for v in value:
            found += scan_citations(v, exempt, key)
    elif isinstance(value, (str, int)) and not isinstance(value, bool):
        text = str(value)
        here = [a or b or c.upper() for a, b, c in TEXT_CITATION_RE.findall(text)]
        here += [doi_id(doi) for doi in DOI_RE.findall(text)]
        if not here and "pmid" in key.lower() and re.fullmatch(r"\s*(?:PMID:?\s*)?\d{4,9}\s*", text, re.I):
            here = [re.sub(r"\D", "", text)]
        found += here
    return found


def entries_of(data: dict, config: dict) -> list[dict]:
    """A file's entries: a list under ``array_key`` or a map under ``map_key``
    ("" for a top-level map), each map value tagged with its key as ``_key``."""
    if "map_key" in config:
        container = data.get(config["map_key"]) if config["map_key"] else data
        return [{**value, "_key": key} for key, value in (container or {}).items()
                if key != "_metadata" and isinstance(value, dict)]
    return data.get(config["array_key"], [])


def extract_pmids_from_entry(entry: dict, config: dict) -> list[dict]:
    """Extract PMID citations from an entry."""
    results = []
    sources_field = config.get("sources_field", "sources")
    source_format = config.get("source_format", "dict_list")

    def add_pmid(pmid: str, url: str | None = None) -> None:
        if not pmid or any(ref["pmid"] == pmid for ref in results):
            return
        results.append({
            "pmid": pmid,
            "url": url or f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        })

    sources = entry.get(sources_field, [])
    if source_format == "nested_cfu_evidence_pmids":
        evidence = ((entry.get("cfu_thresholds") or {}).get("evidence") or {})
        candidates = [
            evidence.get("pmid"),
            evidence.get("secondary_pmid"),
            *list(evidence.get("additional_pmids") or []),
        ]
        for context in entry.get("study_contexts") or []:
            if isinstance(context, dict):
                candidates.extend(context.get("source_pmids") or [])
        for candidate in candidates:
            pmid = re.sub(r"[^0-9]", "", str(candidate or ""))
            if pmid:
                add_pmid(pmid)
        sources = []

    if not isinstance(sources, list):
        sources = []

    for s in sources:
        url = ""
        if source_format == "pmid_list":
            # Bare PMID string (e.g. "24401291"); tolerate "PMID:123" / int.
            pmid = re.sub(r"[^0-9]", "", str(s))
            if pmid:
                add_pmid(pmid)
            continue
        if source_format == "url_list":
            url = s if isinstance(s, str) else ""
        else:
            if not isinstance(s, dict):
                continue
            # The URL is the ground truth, whatever the source_type label says
            # (15 depletion sources labelled "reference" were never read).
            url = s.get("url", "")

        m = PMID_RE.search(url)
        if m:
            add_pmid(m.group(1), url)

    # Curated interaction files historically carry PMID identifiers in both
    # source_urls and source_pmids. Include the explicit field as a first-class
    # verification input so a PMID cannot influence SP-6 grading while bypassing
    # the content verifier.
    for source_pmid in entry.get("source_pmids") or []:
        pmid = re.sub(r"[^0-9]", "", str(source_pmid))
        if pmid:
            add_pmid(pmid)

    if config.get("scan_all"):
        for citation in scan_citations(entry, HISTORY_KEYS):
            add_pmid(citation)

    return results


# ── Main verification ──────────────────────────────────────────────────

def entry_id_of(entry: dict, config: dict) -> str:
    return str(entry.get(config["id_field"]) or entry.get("_key", "unknown"))


def changed_entry_ids(config: dict, ref: str) -> set[str]:
    """Ids of the entries in ``config``'s file added or changed since git ``ref``."""
    from data_batch import at_ref, changed_keys

    filepath = DATA_DIR / config["file"]
    if not filepath.exists():
        return set()
    with open(filepath) as f:
        now = json.load(f)
    by_id = lambda blob: {entry_id_of(e, config): e for e in entries_of(blob or {}, config)}  # noqa: E731
    added, _removed, modified = changed_keys(by_id(at_ref(ref, filepath)), by_id(now))
    return set(added) | set(modified)


def verify_file(config: dict, only_ids: set[str] | None = None) -> dict:
    """Verify the PubMed citations in one data file (only ``only_ids`` when given)."""
    filepath = DATA_DIR / config["file"]
    if not filepath.exists():
        return {"file": config["file"], "status": "not_found", "entries": []}

    with open(filepath) as f:
        data = json.load(f)

    entries = entries_of(data, config)
    if only_ids is not None:
        entries = [e for e in entries if entry_id_of(e, config) in only_ids]
    results = []
    all_pmids = {}  # pmid → list of entry contexts

    # Collect all PMIDs
    for entry in entries:
        entry_id = entry_id_of(entry, config)
        topic_words = extract_topic_words(entry, config)
        pmid_refs = extract_pmids_from_entry(entry, config)

        for ref in pmid_refs:
            pmid = ref["pmid"]
            if pmid not in all_pmids:
                all_pmids[pmid] = []
            topic_words_for_ref = topic_words
            if config.get("source_format") == "nested_cfu_evidence_pmids":
                matching_contexts = [
                    context for context in entry.get("study_contexts") or []
                    if isinstance(context, dict)
                    and pmid in {str(p) for p in context.get("source_pmids") or []}
                ]
                if matching_contexts:
                    # Keep the entry-level identity terms as a weak anchor, but
                    # add only the context terms for this PMID—not every other
                    # condition in the strain's literature.
                    context_words = set()
                    for context in matching_contexts:
                        context_words.update(extract_context_topic_words(context, config))
                    topic_words_for_ref = list(set(topic_words) | context_words)
            all_pmids[pmid].append({
                "entry_id": entry_id,
                "topic_words": topic_words_for_ref,
            })

    if not all_pmids:
        return {"file": config["file"], "status": "no_pubmed_citations", "entries": []}

    # Fetch all articles
    print(f"\n  {config['file']}: fetching {len(all_pmids)} unique PMIDs...")
    articles = fetch_articles(list(all_pmids.keys()))

    # Verify content match
    for pmid, contexts in all_pmids.items():
        article = articles.get(pmid)
        for ctx in contexts:
            status, confidence = content_matches(article, ctx["topic_words"])
            result = {
                "entry_id": ctx["entry_id"],
                "pmid": pmid,
                "status": status,
                "confidence": round(confidence, 2),
                "topic_words_checked": ctx["topic_words"][:10],
                "article_title": article.get("title", "NOT FOUND") if article else "NOT FOUND",
            }
            if status == "mismatch":
                result["suggestion"] = "REPLACE — paper does not mention claimed topic"
            elif status == "partial":
                result["suggestion"] = "REVIEW — only partial topic match"
            results.append(result)

    match_count = sum(1 for r in results if r["status"] == "match")
    partial_count = sum(1 for r in results if r["status"] == "partial")
    mismatch_count = sum(1 for r in results if r["status"] == "mismatch")
    notfound_count = sum(1 for r in results if r["status"] == "not_found")

    return {
        "file": config["file"],
        "total_citations": len(results),
        "match": match_count,
        "partial": partial_count,
        "mismatch": mismatch_count,
        "not_found": notfound_count,
        "pass_rate": f"{(match_count + partial_count) / max(len(results), 1):.0%}",
        "entries": results,
    }


def baseline_failures(results: list[dict], baseline: dict) -> tuple[list, list]:
    """(new mismatches, unresolved citations) against a known-backlog baseline.

    A mismatch listed in the baseline is backlog: reported, not a failure. A
    mismatch not listed, or a citation that does not resolve, is a failure.
    """
    known = {(item["file"], item["entry_id"], item["pmid"])
             for item in baseline.get("backlog", []) if item.get("status") == "mismatch"}
    new, unresolved = [], []
    for result in results:
        for entry in result.get("entries", []):
            if entry["status"] == "not_found":
                unresolved.append((result["file"], entry))
            elif entry["status"] == "mismatch" and (result["file"], entry["entry_id"], entry["pmid"]) not in known:
                new.append((result["file"], entry))
    return new, unresolved


def main():
    parser = argparse.ArgumentParser(description="Content-verify all PubMed citations")
    parser.add_argument("--file", help="Verify only this file (e.g., timing_rules.json)")
    parser.add_argument("--report", type=Path, help="Write JSON report to this path")
    parser.add_argument("--baseline", type=Path,
                        help="known backlog (scripts/data/citation_content_backlog.json): fail only on "
                             "an unresolved citation or a mismatch not listed there")
    parser.add_argument("--changed-since", metavar="REF",
                        help="check only entries added or changed since this git ref (e.g. origin/main), "
                             "printing one result line per citation; for curated-data batches")
    args = parser.parse_args()

    # Load env
    sys.path.insert(0, str(SCRIPTS_ROOT))
    try:
        import env_loader  # noqa: F401
    except ImportError:
        pass

    configs = FILE_CONFIGS
    if args.file:
        configs = [c for c in configs if args.file in c["file"]]
        if not configs:
            print(f"ERROR: no config for file '{args.file}'", file=sys.stderr)
            return 1

    print("=" * 60)
    print("PubMed Citation Content Verification")
    print("=" * 60)

    all_results = []
    total_match = 0
    total_mismatch = 0

    for config in configs:
        only_ids = changed_entry_ids(config, args.changed_since) if args.changed_since else None
        if only_ids is not None and not only_ids:
            continue
        result = verify_file(config, only_ids)
        all_results.append(result)
        total_match += result.get("match", 0)
        total_mismatch += result.get("mismatch", 0)

        print(f"\n  {result['file']}:")
        print(f"    Citations: {result.get('total_citations', 0)}")
        print(f"    ✅ Match: {result.get('match', 0)}")
        print(f"    ⚠️  Partial: {result.get('partial', 0)}")
        print(f"    ❌ Mismatch: {result.get('mismatch', 0)}")
        print(f"    Pass rate: {result.get('pass_rate', 'N/A')}")

        # Print mismatches (every citation when checking a batch)
        for entry in result.get("entries", []):
            if only_ids is not None:
                print(f"    {entry['status'].upper():<9} {entry['entry_id']} {cite_label(entry['pmid'])}: "
                      f"{entry['article_title'][:100]}")
            elif entry["status"] == "mismatch":
                print(f"    ❌ {entry['entry_id']} {cite_label(entry['pmid'])}: {entry['article_title']}")

    print(f"\n{'=' * 60}")
    print(f"TOTAL: ✅ {total_match} match  ❌ {total_mismatch} mismatch")

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with open(args.report, "w") as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)
        print(f"Report: {args.report}")

    if args.baseline:
        new, unresolved = baseline_failures(all_results, json.loads(args.baseline.read_text()))
        print(f"BASELINE: {len(new)} new mismatch(es), {len(unresolved)} unresolved citation(s); "
              f"{total_mismatch - len(new)} backlog mismatch(es) reported, not blocking")
        for file, entry in unresolved:
            print(f"  UNRESOLVED {file} {entry['entry_id']} {cite_label(entry['pmid'])}")
        for file, entry in new:
            print(f"  NEW MISMATCH {file} {entry['entry_id']} {cite_label(entry['pmid'])}: {entry['article_title']}")
        return 1 if new or unresolved else 0

    return 1 if total_mismatch > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
