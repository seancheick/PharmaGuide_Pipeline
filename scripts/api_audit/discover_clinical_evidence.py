#!/usr/bin/env python3
"""
Clinical evidence discovery and audit tool for PharmaGuide.

===========================================================================
QUICK START — copy-paste these commands from the repo root
===========================================================================

  # 1. AUDIT — check all clinical entries for data bugs
  #    (notes vs classification contradictions, enrollment plausibility,
  #     BRAND_ misclassification, PRECLIN_ with human trial data)
  python3 scripts/api_audit/discover_clinical_evidence.py audit

  # 2. AUDIT — save full JSON report
  python3 scripts/api_audit/discover_clinical_evidence.py audit \
      --output scripts/api_audit/reports/clinical_audit_report.json

  # 3. DISCOVER — find top 20 IQM compounds missing from clinical DB
  #    (queries ClinicalTrials.gov + ChEMBL for trial counts, enrollment,
  #     phase data, safety flags; generates candidate entries for review)
  python3 scripts/api_audit/discover_clinical_evidence.py discover --limit 20

  # 4. DISCOVER — search a single compound
  python3 scripts/api_audit/discover_clinical_evidence.py discover \
      --compound "spirulina"

  # 5. DISCOVER — save candidates to file for review
  python3 scripts/api_audit/discover_clinical_evidence.py discover \
      --limit 50 --output scripts/api_audit/reports/discovery_candidates.json

  # 5b. DISCOVER + AUTO-ADD — search AND add qualifying entries to DB
  #     (only adds compounds with >= 3 completed trials, no safety flags)
  #     Key endpoints auto-populated from ClinicalTrials.gov outcome measures
  #     with PubMed PMID cross-references (requires NCBI_API_KEY in .env)
  python3 scripts/api_audit/discover_clinical_evidence.py discover \
      --limit 20 --apply

  # 5c. DISCOVER + AUTO-ADD — stricter (10+ trials required)
  python3 scripts/api_audit/discover_clinical_evidence.py discover \
      --limit 50 --apply --min-trials 10

  # 6. ENRICH — find entries with low/missing total_enrollment and
  #    query ClinicalTrials.gov for the real largest trial (dry-run)
  python3 scripts/api_audit/discover_clinical_evidence.py enrich

  # 7. ENRICH — apply enrollment updates to backed_clinical_studies.json
  python3 scripts/api_audit/discover_clinical_evidence.py enrich --apply

  # 8. ENRICH — save enrichment report
  python3 scripts/api_audit/discover_clinical_evidence.py enrich \
      --output scripts/api_audit/reports/enrollment_enrichment.json

  # 9. BACKFILL-AUDITABILITY — add rationale/confidence/tags on the
  #    highest-impact entries first (dry-run)
  python3 scripts/api_audit/discover_clinical_evidence.py backfill-auditability --limit 50

  # 10. BACKFILL-AUDITABILITY — write auditability metadata to the DB
  python3 scripts/api_audit/discover_clinical_evidence.py backfill-auditability --limit 50 --apply

===========================================================================
WHAT THIS SCRIPT DOES
===========================================================================

  Mode        What it checks / does
  --------    ----------------------------------------------------------
  audit       - Notes text vs effect_direction (null/mixed/weak signals)
              - study_type vs published_studies metadata consistency
              - Enrollment plausibility for well-known compounds
              - PRECLIN_ entries with human trial mentions in notes
              - BRAND_ entries still using ingredient-human level
              Reports: HIGH / MEDIUM / LOW severity issues

  discover    - Scans ingredient_quality_map.json for compounds NOT in
                backed_clinical_studies.json (411 gaps as of 2026-04)
              - Queries ClinicalTrials.gov for completed trial count,
                max enrollment, phase advancement, and primary/secondary
                outcome measures
              - Queries ChEMBL for compound data (max_phase, safety flags,
                withdrawn_flag, black_box_warning)
              - With --apply: cross-references NCT IDs against PubMed to
                find published PMIDs and auto-populates key_endpoints
              - Generates candidate entries with suggested evidence_level,
                study_type, effect_direction, total_enrollment
              - All candidates flagged requires_human_review=true

  enrich      - Finds entries with total_enrollment < 50 or missing
              - Queries ClinicalTrials.gov for real largest trial
              - Dry-run by default; --apply to write changes
              - Also backfills registry_completed_trials_count broadly for
                RCT/meta entries without regressing stronger local enrollment

  backfill-auditability
              - Prioritizes the highest-impact clinical entries missing
                rationale/confidence/tags
              - Queries ClinicalTrials.gov for completed-trial counts and
                outcome measures
              - Derives operator-facing endpoint_relevance_tags plus
                effect_direction rationale/confidence without changing score math

===========================================================================
API DETAILS
===========================================================================

  ClinicalTrials.gov API v2 — free, no key needed
  ChEMBL REST API (EMBL-EBI) — free, no key needed
  NCBI PubMed E-utilities — requires NCBI_API_KEY in .env (for PMID lookup)
  Rate limit: self-imposed 0.35s between requests (~2.8 req/s)
  Caching: 30-day disk cache in scripts/api_audit/.cache/
  Circuit breaker: stops after 3 consecutive failures

===========================================================================
REQUIREMENTS
===========================================================================

  Python >= 3.9
  pip install requests
  (rapidfuzz not needed for this script)
"""

import argparse
import json
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

# Python 3.9 compat (UTC added in 3.11)
UTC = timezone.utc
from pathlib import Path
from typing import Any, Optional

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import env_loader  # noqa: F401
from api_audit.pubmed_client import PubMedClient, parse_pubmed_article_xml

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CT_BASE_URL = "https://clinicaltrials.gov/api/v2"
CHEMBL_BASE_URL = "https://www.ebi.ac.uk/chembl/api/data"
RATE_LIMIT_DELAY = 0.35
DEFAULT_CACHE_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days
CACHE_DIR = SCRIPTS_ROOT / "api_audit" / ".cache"

DEFAULT_CLINICAL_DB = SCRIPTS_ROOT / "data" / "backed_clinical_studies.json"
DEFAULT_IQM_DB = SCRIPTS_ROOT / "data" / "ingredient_quality_map.json"

# Signals for automated notes-vs-classification audit
NULL_SIGNALS = [
    "no benefit", "no significant", "not superior to placebo",
    "null result", "ineffective", "no improvement", "failed to demonstrate",
    "did not show", "did not demonstrate", "no effect", "not effective",
    "no consistent", "does not consistently",
]
MIXED_SIGNALS = [
    "mixed", "inconsistent", "conflicting", "controversial",
    "uncertain", "limited and not conclusive", "debated", "equivocal",
    "heterogeneous", "not definitive",
]
WEAK_SIGNALS = [
    "modest", "marginal", "small effect", "weak evidence",
    "preliminary", "limited evidence", "modest benefit", "small but",
    "slight", "minor improvement", "borderline",
]

OUTCOME_TAG_KEYWORDS = {
    "joint_pain": ("joint pain", "osteoarthritis", "knee pain", "pain score"),
    "joint_health": ("joint function", "joint stiffness", "cartilage"),
    "immune_support": ("immune", "infection", "upper respiratory", "cold incidence"),
    "stress_mood": ("stress", "anxiety", "cortisol", "perceived stress"),
    "sleep": ("sleep", "insomnia", "sleep latency", "sleep quality"),
    "focus_memory": ("cognition", "memory", "attention", "mental clarity", "focus"),
    "energy_metabolism": ("fatigue", "energy", "vitality", "physical function", "tiredness"),
    "eye_vision": ("visual acuity", "contrast sensitivity", "eye strain", "macular", "retina", "vision"),
    "hormone_balance": ("testosterone", "estradiol", "hormone", "androgen", "prostate symptom"),
    "cardiovascular": ("cholesterol", "ldl", "hdl", "triglyceride", "blood pressure"),
    "glycemic_control": ("glucose", "hba1c", "insulin", "glycemic"),
    "digestive_health": ("bloating", "stool", "bowel", "digestive", "gut"),
    "muscle_recovery": ("muscle", "strength", "recovery", "fatigue", "exercise performance"),
}

PRIMARY_OUTCOME_TAGS = {
    "Immune Support": ["immune_support"],
    "Healthy Aging/Longevity": ["healthy_aging"],
    "Muscle Growth & Recovery": ["muscle_recovery"],
    "Digestive Health": ["digestive_health"],
    "Cardiovascular/Heart Health": ["cardiovascular"],
    "Focus & Mental Clarity": ["focus_memory"],
    "Increase Energy": ["energy_metabolism"],
    "Joint & Bone Health": ["joint_health"],
    "Eye & Vision": ["eye_vision"],
    "Hormone Balance": ["hormone_balance"],
}

# Enrollment quality bands (used for candidate generation)
ENROLLMENT_BANDS = [
    (50, "pilot"),
    (200, "small"),
    (500, "adequate"),
    (1000, "well_powered"),
]

# Evidence level mapping from ChEMBL max_phase
CHEMBL_PHASE_TO_EVIDENCE = {
    4: "ingredient-human",
    3: "ingredient-human",
    2: "ingredient-human",
    1: "preclinical",
    0: "preclinical",
}


# ---------------------------------------------------------------------------
# HTTP client with caching and circuit breaker
# ---------------------------------------------------------------------------

class APIClient:
    """Shared HTTP client for ClinicalTrials.gov and ChEMBL."""

    def __init__(self, cache_path: Optional[Path] = None):
        self.cache_path = cache_path
        self._cache: dict[str, dict] = {}
        self._request_count = 0
        self._consecutive_failures = 0
        self.circuit_open = False
        if self.cache_path and self.cache_path.exists():
            try:
                self._cache = json.loads(self.cache_path.read_text())
            except (json.JSONDecodeError, OSError):
                self._cache = {}

    def _cache_get(self, key: str) -> Optional[dict]:
        cached = self._cache.get(key)
        if not isinstance(cached, dict):
            return None
        expires_at = cached.get("expires_at")
        if isinstance(expires_at, str):
            try:
                if datetime.fromisoformat(expires_at) <= datetime.now(UTC):
                    self._cache.pop(key, None)
                    return None
            except ValueError:
                self._cache.pop(key, None)
                return None
        return cached.get("payload")

    def _cache_set(self, key: str, payload: dict) -> None:
        self._cache[key] = {
            "payload": payload,
            "expires_at": (
                datetime.now(UTC) + timedelta(seconds=DEFAULT_CACHE_TTL_SECONDS)
            ).isoformat(),
        }

    def save_cache(self) -> None:
        if self.cache_path:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self._cache, indent=1))

    def get(self, url: str) -> Optional[dict]:
        if self.circuit_open:
            return None
        cached = self._cache_get(url)
        if cached is not None:
            return cached

        for attempt in range(1, 4):
            try:
                self._request_count += 1
                time.sleep(RATE_LIMIT_DELAY)
                resp = requests.get(
                    url,
                    headers={"Accept": "application/json"},
                    timeout=15.0,
                )
                if resp.status_code == 404:
                    not_found = {"_not_found": True}
                    self._cache_set(url, not_found)
                    self._consecutive_failures = 0
                    return not_found
                if resp.status_code in (429, 500, 502, 503, 504):
                    wait = RATE_LIMIT_DELAY * (2 ** attempt)
                    print(f"  [RETRY {attempt}/3] HTTP {resp.status_code}, waiting {wait:.1f}s...", file=sys.stderr)
                    time.sleep(wait)
                    continue
                if resp.status_code != 200:
                    print(f"  [ERROR] HTTP {resp.status_code} for {url}", file=sys.stderr)
                    return None
                data = resp.json()
                self._consecutive_failures = 0
                self._cache_set(url, data)
                return data
            except (requests.ConnectionError, requests.Timeout, OSError) as e:
                self._consecutive_failures += 1
                if self._consecutive_failures >= 3:
                    print(f"  [CIRCUIT OPEN] {self._consecutive_failures} consecutive failures", file=sys.stderr)
                    self.circuit_open = True
                    return None
                wait = RATE_LIMIT_DELAY * (2 ** attempt)
                print(f"  [RETRY {attempt}/3] {e}, waiting {wait:.1f}s...", file=sys.stderr)
                time.sleep(wait)
        return None


# ---------------------------------------------------------------------------
# ClinicalTrials.gov queries
# ---------------------------------------------------------------------------

def ct_search_trials(client: APIClient, intervention: str, *, max_results: int = 5) -> dict:
    """Search ClinicalTrials.gov for completed trials by intervention name.

    Returns: {"total": int, "trials": [{"nct_id", "title", "enrollment", "phase",
              "primary_outcomes": [str], ...}]}
    """
    from urllib.parse import quote
    encoded = quote(intervention, safe="")
    url = (
        f"{CT_BASE_URL}/studies?query.intr={encoded}"
        f"&filter.overallStatus=COMPLETED"
        f"&countTotal=true&pageSize={max_results}"
        f"&fields=NCTId,BriefTitle,EnrollmentCount,Phase,StudyType,StartDate,"
        f"PrimaryOutcomeMeasure,SecondaryOutcomeMeasure"
    )
    data = client.get(url)
    if data is None:
        return {"total": 0, "trials": []}

    total = data.get("totalCount", 0)
    studies = data.get("studies", [])
    trials = []
    for study in studies:
        proto = study.get("protocolSection", {})
        ident = proto.get("identificationModule", {})
        design = proto.get("designModule", {})
        status_mod = proto.get("statusModule", {})
        outcomes_mod = proto.get("outcomesModule", {})

        enrollment_info = design.get("enrollmentInfo", {})
        enrollment = enrollment_info.get("count", 0) if isinstance(enrollment_info, dict) else 0

        phases = design.get("phases", [])

        # Extract primary outcome measure text
        primary_outcomes = []
        for outcome in outcomes_mod.get("primaryOutcomes", []):
            measure = outcome.get("measure", "").strip()
            if measure:
                primary_outcomes.append(measure)

        # Extract secondary outcome measure text (top 3)
        secondary_outcomes = []
        for outcome in outcomes_mod.get("secondaryOutcomes", [])[:3]:
            measure = outcome.get("measure", "").strip()
            if measure:
                secondary_outcomes.append(measure)

        trials.append({
            "nct_id": ident.get("nctId", ""),
            "title": ident.get("briefTitle", ""),
            "enrollment": enrollment,
            "phases": phases,
            "study_type": design.get("studyType", ""),
            "start_date": status_mod.get("startDateStruct", {}).get("date", ""),
            "primary_outcomes": primary_outcomes,
            "secondary_outcomes": secondary_outcomes,
        })

    return {"total": total, "trials": trials}


def ct_get_max_enrollment(client: APIClient, intervention: str) -> int:
    """Get the largest enrollment from completed trials for an intervention."""
    result = ct_search_trials(client, intervention, max_results=10)
    if not result["trials"]:
        return 0
    return max(t.get("enrollment", 0) for t in result["trials"])


def _clinical_trial_search_terms(entry: dict) -> list[str]:
    """Return conservative ClinicalTrials.gov search terms for an entry.

    For branded evidence we include short brand aliases to avoid undercounting
    registry coverage when the formal ingredient name is overly specific.
    We intentionally avoid broad multi-word aliases here because they can pull
    in compound-level trials unrelated to the branded evidence record.
    """
    terms: list[str] = []

    name = (entry.get("standard_name") or "").strip()
    if name:
        terms.append(name)

    if entry.get("evidence_level") == "branded-rct":
        for alias in entry.get("aliases", []) or []:
            alias = (alias or "").strip()
            if not alias:
                continue
            if " " in alias:
                continue
            if len(alias) < 5:
                continue
            if not any(ch.isalpha() for ch in alias):
                continue
            terms.append(alias)

    return list(dict.fromkeys(terms))


def _ct_search_trials_merged(client: APIClient, search_terms: list[str], *, max_results: int = 10) -> dict:
    """Query ClinicalTrials.gov across multiple terms and merge unique trials."""
    merged: dict[str, dict] = {}
    max_reported_total = 0
    saw_real_nct = False

    for term in search_terms:
        result = ct_search_trials(client, term, max_results=max_results)
        max_reported_total = max(max_reported_total, result.get("total", 0) or 0)
        for idx, trial in enumerate(result.get("trials", [])):
            nct_id = trial.get("nct_id") or ""
            if not nct_id:
                title = (trial.get("title") or "").strip().lower()
                enrollment = trial.get("enrollment", 0) or 0
                nct_id = f"{term.lower()}::{title or 'untitled'}::{enrollment}::{idx}"
            else:
                saw_real_nct = True
            existing = merged.get(nct_id)
            if existing is None:
                merged[nct_id] = dict(trial)
                continue
            if (trial.get("enrollment", 0) or 0) > (existing.get("enrollment", 0) or 0):
                merged[nct_id] = dict(trial)

    merged_trials = list(merged.values())
    total = len(merged_trials) if saw_real_nct else max(max_reported_total, len(merged_trials))
    return {"total": total, "trials": merged_trials}


# ---------------------------------------------------------------------------
# PubMed PMID lookup for NCT IDs
# ---------------------------------------------------------------------------

def _get_pubmed_client() -> PubMedClient:
    """Lazy-init a shared PubMedClient with disk cache."""
    cache_path = CACHE_DIR / "pubmed_nct_cache.json"
    return PubMedClient(cache_path=cache_path)


def pubmed_find_pmid_for_nct(
    pm_client: PubMedClient,
    nct_id: str,
) -> Optional[str]:
    """Search PubMed for the published article linked to an NCT ID.

    Uses the secondary source ID index: "{NCT_ID}"[si]
    Returns the PMID string or None if not found.
    """
    if not nct_id:
        return None
    try:
        result = pm_client.esearch(f'"{nct_id}"[si]', retmax="3")
        id_list = result.get("esearchresult", {}).get("idlist", [])
        if id_list:
            return id_list[0]
    except Exception as e:
        print(f"  [PUBMED] Failed to find PMID for {nct_id}: {e}", file=sys.stderr)
    return None


def pubmed_get_article_title(
    pm_client: PubMedClient,
    pmid: str,
) -> str:
    """Fetch the article title for a given PMID."""
    if not pmid:
        return ""
    try:
        xml_text = pm_client.efetch(pmid, rettype="abstract")
        articles = parse_pubmed_article_xml(xml_text)
        if articles:
            return articles[0].get("title", "")
    except Exception as e:
        print(f"  [PUBMED] Failed to fetch title for PMID {pmid}: {e}", file=sys.stderr)
    return ""


# ---------------------------------------------------------------------------
# Key endpoint builder
# ---------------------------------------------------------------------------

def build_key_endpoints(
    trials: list[dict],
    pm_client: Optional[PubMedClient] = None,
    *,
    max_endpoints: int = 4,
) -> list[str]:
    """Build key_endpoints from ClinicalTrials.gov outcome measures + PubMed PMIDs.

    For each of the top trials (sorted by enrollment), extracts the primary
    outcome measure text and attempts to find the corresponding PMID via PubMed.

    Returns a list of formatted endpoint strings like:
        "Change in LDL cholesterol from baseline (NCT01234567, n=500, PMID: 12345678)"
    """
    if not trials:
        return []

    # Sort by enrollment descending to get the most impactful trials first
    ranked = sorted(trials, key=lambda t: t.get("enrollment", 0), reverse=True)

    endpoints: list[str] = []
    seen_measures: set[str] = set()

    for trial in ranked:
        if len(endpoints) >= max_endpoints:
            break

        nct_id = trial.get("nct_id", "")
        enrollment = trial.get("enrollment", 0)
        primary_outcomes = trial.get("primary_outcomes", [])

        if not primary_outcomes:
            continue

        # Take the first primary outcome (most important)
        measure = primary_outcomes[0]

        # Skip near-duplicate measures
        measure_key = measure.lower().strip()[:60]
        if measure_key in seen_measures:
            continue
        seen_measures.add(measure_key)

        # Try to find PMID for this NCT
        pmid = None
        if pm_client and nct_id:
            pmid = pubmed_find_pmid_for_nct(pm_client, nct_id)

        # Format the endpoint string
        parts = [measure]
        ref_parts = []
        if nct_id:
            ref_parts.append(nct_id)
        if enrollment:
            ref_parts.append(f"n={enrollment}")
        if pmid:
            ref_parts.append(f"PMID: {pmid}")

        if ref_parts:
            parts.append(f"({', '.join(ref_parts)})")

        endpoints.append(" ".join(parts))

    return endpoints


def derive_endpoint_relevance_tags(
    trials: list[dict],
    *,
    primary_outcome: Optional[str] = None,
) -> list[str]:
    """Derive coarse endpoint relevance tags from registered outcome text.

    This is intentionally conservative and audit-friendly: it derives broad
    clinical intent tags from ClinicalTrials.gov outcome strings and falls back
    to the entry's mapped primary outcome category when no direct keyword match
    is available.
    """
    text_parts: list[str] = []
    for trial in trials:
        text_parts.extend(trial.get("primary_outcomes", []) or [])
        text_parts.extend(trial.get("secondary_outcomes", []) or [])
    haystack = " ".join(text_parts).lower()

    tags: list[str] = []
    for tag, keywords in OUTCOME_TAG_KEYWORDS.items():
        if any(keyword in haystack for keyword in keywords):
            tags.append(tag)

    if not tags and primary_outcome:
        tags.extend(PRIMARY_OUTCOME_TAGS.get(primary_outcome, []))

    return list(dict.fromkeys(tags))


def derive_endpoint_relevance_tags_from_strings(
    texts: list[str],
    *,
    primary_outcome: Optional[str] = None,
) -> list[str]:
    """Derive coarse endpoint tags from existing endpoint strings."""
    pseudo_trials = [{
        "primary_outcomes": texts,
        "secondary_outcomes": [],
    }]
    return derive_endpoint_relevance_tags(pseudo_trials, primary_outcome=primary_outcome)


def _evidence_impact_score(entry: dict) -> float:
    """Return the Section C pre-adjustment impact score for prioritization."""
    base_points = {
        "systematic_review_meta": 6,
        "rct_multiple": 5,
        "rct_single": 4,
        "clinical_strain": 4,
        "observational": 2,
        "animal_study": 2,
        "in_vitro": 1,
    }
    evidence_multiplier = {
        "product-human": 1.0,
        "branded-rct": 0.8,
        "ingredient-human": 0.65,
        "strain-clinical": 0.6,
        "preclinical": 0.3,
    }
    return base_points.get(entry.get("study_type"), 0) * evidence_multiplier.get(entry.get("evidence_level"), 0)


def _note_signal_flags(entry: dict) -> dict[str, bool]:
    notes = ((entry.get("notes") or "") + " " + (entry.get("notable_studies") or "")).lower()
    return {
        "has_null": any(s in notes for s in NULL_SIGNALS),
        "has_mixed": any(s in notes for s in MIXED_SIGNALS),
        "has_weak": any(s in notes for s in WEAK_SIGNALS),
    }


def derive_effect_direction_confidence(entry: dict, registry_completed_trials_count: Optional[int] = None) -> str:
    """Derive a conservative auditability confidence label for effect_direction."""
    st = entry.get("study_type")
    ev = entry.get("evidence_level")
    enroll = entry.get("total_enrollment") or 0
    published_count = entry.get("published_studies_count") or 0
    registry_count = registry_completed_trials_count or entry.get("registry_completed_trials_count") or 0
    flags = _note_signal_flags(entry)

    if st in {"systematic_review_meta", "rct_multiple"} and ev in {"product-human", "branded-rct", "ingredient-human"}:
        if not any(flags.values()) and (enroll >= 200 or published_count >= 20 or registry_count >= 8):
            return "high"
        return "medium"
    if st in {"rct_single", "clinical_strain", "observational"} and ev != "preclinical":
        return "medium"
    return "low"


def build_effect_direction_rationale(
    entry: dict,
    *,
    registry_completed_trials_count: Optional[int] = None,
    endpoint_relevance_tags: Optional[list[str]] = None,
) -> str:
    """Build an audit-friendly rationale summary for effect_direction."""
    registry_count = registry_completed_trials_count or entry.get("registry_completed_trials_count")
    tags = endpoint_relevance_tags if endpoint_relevance_tags is not None else (entry.get("endpoint_relevance_tags") or [])
    parts = [
        f"Retained {entry.get('effect_direction', 'unclassified')} classification",
        f"study_type={entry.get('study_type', 'unknown')}",
        f"evidence_level={entry.get('evidence_level', 'unknown')}",
    ]
    if entry.get("primary_outcome"):
        parts.append(f"primary_outcome={entry['primary_outcome']}")
    if entry.get("published_studies"):
        parts.append(f"published_tags={','.join(str(v) for v in entry['published_studies'])}")
    if entry.get("published_studies_count") is not None:
        parts.append(f"published_studies_count={entry['published_studies_count']}")
    if registry_count is not None:
        parts.append(f"registry_completed_trials_count={registry_count}")
    if entry.get("total_enrollment") is not None:
        parts.append(f"total_enrollment={entry['total_enrollment']}")
    if tags:
        parts.append(f"endpoint_tags={','.join(tags)}")

    flags = _note_signal_flags(entry)
    if entry.get("effect_direction") == "positive_strong" and not any(flags.values()):
        parts.append("notes/citations contain no automated downgrade signals")
    elif entry.get("effect_direction") == "positive_weak" and flags["has_weak"]:
        parts.append("notes/citations include weak-effect language")
    elif entry.get("effect_direction") == "mixed" and flags["has_mixed"]:
        parts.append("notes/citations include mixed-evidence language")
    elif entry.get("effect_direction") == "null" and flags["has_null"]:
        parts.append("notes/citations include null-effect language")

    return "; ".join(parts) + "."


# ---------------------------------------------------------------------------
# ChEMBL queries
# ---------------------------------------------------------------------------

def chembl_search_compound(client: APIClient, name: str) -> Optional[dict]:
    """Search ChEMBL for a compound by name. Returns best match or None."""
    from urllib.parse import quote
    encoded = quote(name, safe="")
    url = f"{CHEMBL_BASE_URL}/molecule/search.json?q={encoded}&limit=3"
    data = client.get(url)
    if data is None or data.get("_not_found"):
        return None
    molecules = data.get("molecules", [])
    if not molecules:
        return None
    # Return best match (first result)
    mol = molecules[0]
    return {
        "chembl_id": mol.get("molecule_chembl_id", ""),
        "pref_name": mol.get("pref_name", ""),
        "max_phase": mol.get("max_phase"),
        "natural_product": mol.get("natural_product", False),
        "withdrawn_flag": mol.get("withdrawn_flag", False),
        "black_box_warning": mol.get("black_box_warning", False),
        "molecule_type": mol.get("molecule_type", ""),
    }


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_clinical_db(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def load_iqm(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def get_clinical_names(clinical_db: dict) -> set:
    """Get all names and aliases from clinical DB (lowered)."""
    names = set()
    for entry in clinical_db.get("backed_clinical_studies", []):
        names.add((entry.get("standard_name") or "").lower().strip())
        for alias in entry.get("aliases", []):
            names.add(alias.lower().strip())
    return names


def find_gaps(iqm: dict, clinical_names: set) -> list[dict]:
    """Find IQM compounds not covered by clinical DB."""
    gaps = []
    for slug, entry in iqm.items():
        if slug == "_metadata" or not isinstance(entry, dict):
            continue
        name = entry.get("standard_name", "")
        name_lower = name.lower().strip()

        match_names = {name_lower}
        for form in entry.get("forms", {}).values():
            if isinstance(form, dict):
                fn = (form.get("form_name") or "").lower().strip()
                if fn:
                    match_names.add(fn)
                for alias in form.get("aliases", []):
                    match_names.add(alias.lower().strip())

        covered = any(mn in clinical_names for mn in match_names)
        if not covered:
            gaps.append({
                "slug": slug,
                "standard_name": name,
                "category": entry.get("category", ""),
                "form_count": len(entry.get("forms", {})),
            })
    return gaps


# ---------------------------------------------------------------------------
# DISCOVER mode
# ---------------------------------------------------------------------------

def discover_candidates(
    client: APIClient,
    gaps: list[dict],
    *,
    limit: int = 10,
    compound: Optional[str] = None,
) -> list[dict]:
    """Discover clinical evidence for IQM compounds missing from clinical DB.

    Queries ClinicalTrials.gov for completed trial count and max enrollment,
    and ChEMBL for compound data (max_phase, safety flags).

    Returns list of candidate entries ready for human review.
    """
    candidates = []

    if compound:
        # Single compound mode
        targets = [{"slug": compound.lower().replace(" ", "_"), "standard_name": compound, "category": "", "form_count": 0}]
    else:
        # Sort by form_count (proxy for importance) and take top N
        targets = sorted(gaps, key=lambda x: x["form_count"], reverse=True)[:limit]

    for i, gap in enumerate(targets):
        name = gap["standard_name"]
        print(f"  [{i+1}/{len(targets)}] Searching: {name}...", file=sys.stderr)

        if client.circuit_open:
            print("  [CIRCUIT OPEN] Stopping discovery.", file=sys.stderr)
            break

        # ClinicalTrials.gov
        ct_result = ct_search_trials(client, name, max_results=5)
        total_trials = ct_result["total"]
        max_enrollment = max((t.get("enrollment", 0) for t in ct_result["trials"]), default=0)
        top_phases = []
        for t in ct_result["trials"]:
            top_phases.extend(t.get("phases", []))

        # ChEMBL
        chembl = chembl_search_compound(client, name)

        # Determine evidence level and study type
        if total_trials == 0:
            evidence_level = "preclinical"
            study_type = "animal_study"
        elif any("PHASE3" in p or "PHASE4" in p for p in top_phases):
            evidence_level = "ingredient-human"
            study_type = "rct_multiple" if total_trials >= 5 else "rct_single"
        elif any("PHASE2" in p for p in top_phases):
            evidence_level = "ingredient-human"
            study_type = "rct_single"
        else:
            evidence_level = "ingredient-human" if total_trials >= 3 else "preclinical"
            study_type = "rct_single" if total_trials >= 3 else "animal_study"

        # Effect direction default: discovery metadata alone cannot justify
        # a strong positive classification without human review.
        effect_direction = "positive_weak"
        effect_direction_confidence = "low"
        effect_direction_rationale = (
            "Derived conservatively from ClinicalTrials.gov registry metadata "
            "and trial-count heuristics; published outcome direction is not "
            "verified from registry records alone."
        )

        # Enrollment band
        enrollment_band = "unknown"
        for threshold, band in ENROLLMENT_BANDS:
            if max_enrollment < threshold:
                enrollment_band = band
                break
        else:
            enrollment_band = "landmark"

        # Sort trials by enrollment for consistent ranking
        ranked_trials = sorted(
            ct_result["trials"],
            key=lambda x: x.get("enrollment", 0),
            reverse=True,
        )[:5]

        category_to_goal = {
            "vitamins": "Immune Support",
            "minerals": "Immune Support",
            "herbs": "Healthy Aging/Longevity",
            "amino_acids": "Muscle Growth & Recovery",
            "probiotics": "Digestive Health",
            "antioxidants": "Healthy Aging/Longevity",
            "fatty_acids": "Cardiovascular/Heart Health",
            "enzymes": "Digestive Health",
            "fibers": "Digestive Health",
            "proteins": "Muscle Growth & Recovery",
            "functional_foods": "Healthy Aging/Longevity",
            "other": "Healthy Aging/Longevity",
        }
        primary_outcome = category_to_goal.get(gap["category"], "Healthy Aging/Longevity")

        candidate = {
            "standard_name": name,
            "slug": gap["slug"],
            "category": gap["category"],
            "ct_total_trials": total_trials,
            "ct_max_enrollment": max_enrollment,
            "ct_top_phases": list(set(top_phases)),
            "ct_top_trials": [
                {"nct_id": t["nct_id"], "title": t["title"], "enrollment": t["enrollment"]}
                for t in ranked_trials[:3]
            ],
            "ct_trials_with_outcomes": ranked_trials,
            "chembl": chembl,
            "suggested_evidence_level": evidence_level,
            "suggested_study_type": study_type,
            "suggested_effect_direction": effect_direction,
            "suggested_effect_direction_confidence": effect_direction_confidence,
            "suggested_effect_direction_rationale": effect_direction_rationale,
            "suggested_total_enrollment": max_enrollment,
            "registry_completed_trials_count": total_trials,
            "primary_outcome": primary_outcome,
            "endpoint_relevance_tags": derive_endpoint_relevance_tags(
                ranked_trials,
                primary_outcome=primary_outcome,
            ),
            "enrollment_band": enrollment_band,
            "requires_human_review": True,
            "review_notes": [],
        }

        # Add review notes
        if chembl and chembl.get("withdrawn_flag"):
            candidate["review_notes"].append(f"ChEMBL withdrawn_flag=true for {chembl.get('chembl_id')} — verify safety")
        if chembl and chembl.get("black_box_warning"):
            candidate["review_notes"].append(f"ChEMBL black_box_warning=true — verify safety")
        if total_trials == 0:
            candidate["review_notes"].append("No completed trials found on ClinicalTrials.gov")
        if total_trials >= 20:
            candidate["review_notes"].append(f"High trial count ({total_trials}) — strong evidence body")

        candidates.append(candidate)

    return candidates


def candidate_to_clinical_entry(
    candidate: dict,
    pm_client: Optional[PubMedClient] = None,
) -> dict:
    """Convert a discovery candidate into a backed_clinical_studies.json entry.

    Generates a complete entry matching the schema, ready for insertion.
    Entries with zero trials or safety flags are skipped (returns None).

    If pm_client is provided, key_endpoints are auto-populated from
    ClinicalTrials.gov outcome measures with PubMed PMID cross-references.
    """
    name = candidate["standard_name"]
    slug = candidate["slug"]
    total_trials = candidate.get("ct_total_trials", 0)
    max_enrollment = candidate.get("ct_max_enrollment", 0)
    evidence_level = candidate.get("suggested_evidence_level", "preclinical")
    study_type = candidate.get("suggested_study_type", "animal_study")
    effect_direction = candidate.get("suggested_effect_direction", "positive_weak")
    effect_direction_confidence = candidate.get("suggested_effect_direction_confidence", "low")
    effect_direction_rationale = candidate.get(
        "suggested_effect_direction_rationale",
        "Derived conservatively from registry metadata; published outcome direction is not verified.",
    )
    category = candidate.get("category", "other")
    chembl = candidate.get("chembl") or {}
    top_trials = candidate.get("ct_top_trials", [])
    registry_completed_trials_count = candidate.get("registry_completed_trials_count", total_trials)

    # Skip zero-trial compounds
    if total_trials == 0:
        return None

    # Skip compounds with safety flags (require manual review)
    if chembl.get("withdrawn_flag") or chembl.get("black_box_warning"):
        return None

    # Build ID
    prefix = "INGR"
    if evidence_level == "preclinical":
        prefix = "PRECLIN"
    entry_id = f"{prefix}_{slug.upper()}"

    # Build aliases from the name
    aliases = [name.lower()]
    name_lower = name.lower()
    # Add common variations
    if "(" in name:
        # "Vitamin B3 (Niacin)" -> also add "niacin" and "vitamin b3"
        parts = name.split("(")
        aliases.append(parts[0].strip().lower())
        inner = parts[1].rstrip(")").strip().lower()
        if inner:
            aliases.append(inner)
    aliases = list(dict.fromkeys(aliases))  # dedupe preserving order

    # Determine primary_outcome from category
    category_to_goal = {
        "vitamins": "Immune Support",
        "minerals": "Immune Support",
        "herbs": "Healthy Aging/Longevity",
        "amino_acids": "Muscle Growth & Recovery",
        "probiotics": "Digestive Health",
        "antioxidants": "Healthy Aging/Longevity",
        "fatty_acids": "Cardiovascular/Heart Health",
        "enzymes": "Digestive Health",
        "fibers": "Digestive Health",
        "proteins": "Muscle Growth & Recovery",
        "functional_foods": "Healthy Aging/Longevity",
        "other": "Healthy Aging/Longevity",
    }
    primary_outcome = candidate.get("primary_outcome") or category_to_goal.get(category, "Healthy Aging/Longevity")
    endpoint_relevance_tags = candidate.get("endpoint_relevance_tags") or derive_endpoint_relevance_tags(
        candidate.get("ct_trials_with_outcomes", []),
        primary_outcome=primary_outcome,
    )

    published_study_tags = {
        "systematic_review_meta": ["systematic review", "meta-analysis"],
        "rct_multiple": ["RCT"],
        "rct_single": ["RCT"],
        "clinical_strain": ["clinical strain study"],
        "observational": ["observational"],
        "animal_study": ["animal study"],
        "in_vitro": ["in vitro"],
    }

    # Compute score_contribution tier
    base_pts = {
        "systematic_review_meta": 6, "rct_multiple": 5, "rct_single": 4,
        "clinical_strain": 4, "observational": 2, "animal_study": 2, "in_vitro": 1,
    }
    ev_mult = {
        "product-human": 1.0, "branded-rct": 0.8,
        "ingredient-human": 0.65, "strain-clinical": 0.6, "preclinical": 0.3,
    }
    computed = base_pts.get(study_type, 0) * ev_mult.get(evidence_level, 0)
    if computed >= 3.0:
        tier = "tier_1"
    elif computed >= 1.5:
        tier = "tier_2"
    else:
        tier = "tier_3"

    # Build references_structured from top trials
    refs = []
    for trial in top_trials[:3]:
        if trial.get("nct_id"):
            refs.append({
                "type": "clinical_trial",
                "nct_id": trial["nct_id"],
                "title": trial.get("title", ""),
                "evidence_grade": "rct",
                "enrollment": trial.get("enrollment", 0),
            })
    if chembl.get("chembl_id"):
        refs.append({
            "type": "chembl",
            "authority": "EMBL-EBI ChEMBL",
            "chembl_id": chembl["chembl_id"],
            "max_phase": chembl.get("max_phase"),
            "natural_product": chembl.get("natural_product", False),
        })

    # Build notable_studies text from top trials
    notable_parts = []
    for trial in top_trials[:3]:
        if trial.get("nct_id") and trial.get("enrollment"):
            notable_parts.append(
                f"{trial['nct_id']} (n={trial['enrollment']}): "
                f"{trial.get('title', 'N/A')}"
            )
    notable_studies = ". ".join(notable_parts) + "." if notable_parts else ""

    # Build key_endpoints from trial outcome measures + PubMed PMIDs
    trials_with_outcomes = candidate.get("ct_trials_with_outcomes", [])
    key_endpoints = build_key_endpoints(
        trials_with_outcomes, pm_client, max_endpoints=4
    )

    # Determine notes based on whether endpoints were populated
    if key_endpoints:
        notes = (
            f"Auto-discovered via ClinicalTrials.gov "
            f"({total_trials} completed trials, "
            f"max enrollment {max_enrollment}). "
            f"Key endpoints auto-populated from registered "
            f"outcome measures with PubMed cross-references."
        )
    else:
        notes = (
            f"Auto-discovered via ClinicalTrials.gov "
            f"({total_trials} completed trials, "
            f"max enrollment {max_enrollment}). "
            f"Requires human review for key_endpoints, "
            f"health_goals, and effect_direction refinement."
        )

    return {
        "id": entry_id,
        "standard_name": name,
        "aliases": aliases,
        "category": category,
        "evidence_level": evidence_level,
        "study_type": study_type,
        "published_studies": published_study_tags.get(study_type, ["clinical evidence"]),
        "score_contribution": tier,
        "key_endpoints": key_endpoints,
        "health_goals_supported": [primary_outcome],
        "primary_outcome": primary_outcome,
        "endpoint_relevance_tags": endpoint_relevance_tags,
        "effect_direction": effect_direction,
        "effect_direction_confidence": effect_direction_confidence,
        "effect_direction_rationale": effect_direction_rationale,
        "total_enrollment": max_enrollment if max_enrollment > 0 else None,
        "registry_completed_trials_count": registry_completed_trials_count,
        "notes": notes,
        "last_updated": datetime.now(UTC).strftime("%Y-%m-%d"),
        "notable_studies": notable_studies,
        "references_structured": refs,
    }


def apply_candidates_to_db(
    clinical_db: dict,
    candidates: list[dict],
    *,
    min_trials: int = 3,
    pm_client: Optional[PubMedClient] = None,
) -> list[dict]:
    """Convert candidates to entries and append to clinical DB.

    Only adds candidates with >= min_trials completed trials and no safety flags.
    Skips candidates whose standard_name already exists in the DB.
    If pm_client is provided, key_endpoints are auto-populated with PMIDs.
    Returns list of entries that were added.
    """
    existing_names = get_clinical_names(clinical_db)
    entries = clinical_db.get("backed_clinical_studies", [])
    existing_ids = {e.get("id") for e in entries}
    added = []

    for candidate in candidates:
        # Skip low-evidence candidates
        if candidate.get("ct_total_trials", 0) < min_trials:
            continue

        entry = candidate_to_clinical_entry(candidate, pm_client)
        if entry is None:
            continue

        # Skip duplicates
        if entry["standard_name"].lower().strip() in existing_names:
            continue
        if entry["id"] in existing_ids:
            continue

        entries.append(entry)
        existing_ids.add(entry["id"])
        existing_names.add(entry["standard_name"].lower().strip())
        added.append(entry)

    # Update metadata
    clinical_db["_metadata"]["total_entries"] = len(entries)
    clinical_db["_metadata"]["last_updated"] = datetime.now(UTC).strftime("%Y-%m-%d")

    return added


# ---------------------------------------------------------------------------
# AUDIT mode
# ---------------------------------------------------------------------------

def audit_all_entries(clinical_db: dict) -> list[dict]:
    """Audit all entries in the clinical DB for internal consistency.

    Checks:
      1. Notes text vs effect_direction contradictions
      2. study_type vs published_studies consistency
      3. Enrollment plausibility for well-known compounds
      4. PRECLIN_ entries with human trial mentions in notes
      5. product-human entries without brand-specific evidence
    """
    entries = clinical_db.get("backed_clinical_studies", [])
    issues = []

    well_known = {
        "vitamin d", "vitamin c", "vitamin e", "omega-3", "calcium", "selenium",
        "zinc", "magnesium", "iron", "creatine", "probiotics", "melatonin",
        "garlic", "st. john", "glucosamine", "fish oil", "coenzyme q10",
        "psyllium", "echinacea", "ginkgo",
    }

    for entry in entries:
        eid = entry.get("id", "")
        name = entry.get("standard_name", "")
        ed = entry.get("effect_direction", "")
        st = entry.get("study_type", "")
        ev = entry.get("evidence_level", "")
        notes = ((entry.get("notes") or "") + " " + (entry.get("notable_studies") or "")).lower()
        enroll = entry.get("total_enrollment", 0) or 0
        ps = entry.get("published_studies", [])
        ps_lower = [str(p).lower() for p in ps] if isinstance(ps, list) else []
        rationale = (entry.get("effect_direction_rationale") or "").strip()
        confidence = (entry.get("effect_direction_confidence") or "").strip()

        if ed and not rationale:
            issues.append({"id": eid, "name": name, "check": "missing_effect_direction_rationale",
                "severity": "MEDIUM", "detail": "effect_direction present without supporting rationale",
                "suggested_fix": "add effect_direction_rationale with evidence summary"})
        if ed and not confidence:
            issues.append({"id": eid, "name": name, "check": "missing_effect_direction_confidence",
                "severity": "LOW", "detail": "effect_direction present without confidence label",
                "suggested_fix": "add effect_direction_confidence"})

        # Check 1: Notes vs effect_direction
        has_null = any(s in notes for s in NULL_SIGNALS)
        has_mixed = any(s in notes for s in MIXED_SIGNALS)
        has_weak = any(s in notes for s in WEAK_SIGNALS)

        if ed == "positive_strong":
            if has_null:
                issues.append({"id": eid, "name": name, "check": "notes_contradiction",
                    "severity": "HIGH", "detail": "positive_strong but notes suggest null",
                    "suggested_fix": "effect_direction -> null"})
            elif has_mixed:
                issues.append({"id": eid, "name": name, "check": "notes_contradiction",
                    "severity": "HIGH", "detail": "positive_strong but notes suggest mixed",
                    "suggested_fix": "effect_direction -> mixed"})
            elif has_weak:
                issues.append({"id": eid, "name": name, "check": "notes_contradiction",
                    "severity": "MEDIUM", "detail": "positive_strong but notes suggest positive_weak",
                    "suggested_fix": "effect_direction -> positive_weak"})
        elif ed == "positive_weak" and has_null:
            issues.append({"id": eid, "name": name, "check": "notes_contradiction",
                "severity": "MEDIUM", "detail": "positive_weak but notes suggest null",
                "suggested_fix": "effect_direction -> null"})

        # Check 2: study_type vs published_studies
        if st == "systematic_review_meta" and ps_lower:
            if not any(kw in p for p in ps_lower for kw in ("meta", "systematic", "review")):
                issues.append({"id": eid, "name": name, "check": "study_type_vs_published",
                    "severity": "LOW", "detail": f"st={st} but published_studies={ps} (no meta/review)",
                    "suggested_fix": "add 'systematic_review' or 'meta-analysis' to published_studies"})

        # Check 3: Enrollment plausibility
        registry_count = entry.get("registry_completed_trials_count")
        if st in ("systematic_review_meta", "rct_multiple") and enroll < 100:
            is_well_known = any(comp in name.lower() for comp in well_known)
            registry_sparse = registry_count is None or registry_count <= 1
            if is_well_known and (enroll < 50 or registry_sparse):
                issues.append({"id": eid, "name": name, "check": "enrollment_plausibility",
                    "severity": "MEDIUM", "detail": f"enrollment={enroll} seems low for well-known compound",
                    "suggested_fix": f"verify total_enrollment via ClinicalTrials.gov"})

        # Check 4: PRECLIN_ with human trial mentions
        if eid.startswith("PRECLIN_") and ev == "preclinical":
            human_kw = ["rct", "randomized", "human trial", "clinical trial",
                        "placebo-controlled", "double-blind", "participants"]
            if any(kw in notes for kw in human_kw):
                issues.append({"id": eid, "name": name, "check": "preclinical_with_human_data",
                    "severity": "MEDIUM",
                    "detail": "preclinical classification but notes mention human trials",
                    "suggested_fix": "verify if evidence_level should be ingredient-human"})

        # Check 5: BRAND_ still using ingredient-human
        if eid.startswith("BRAND_") and ev == "ingredient-human":
            issues.append({"id": eid, "name": name, "check": "brand_evidence_level",
                "severity": "HIGH", "detail": "BRAND_ entry with ingredient-human (should be branded-rct?)",
                "suggested_fix": "evidence_level -> branded-rct"})

    return issues


# ---------------------------------------------------------------------------
# ENRICH mode
# ---------------------------------------------------------------------------

def enrich_enrollment(
    client: APIClient,
    clinical_db: dict,
    *,
    apply: bool = False,
) -> list[dict]:
    """Populate total_enrollment for entries missing it or with suspicious values.

    Queries ClinicalTrials.gov for the largest completed trial per compound.
    """
    entries = clinical_db.get("backed_clinical_studies", [])
    rct_types = {"systematic_review_meta", "rct_multiple", "rct_single"}
    enrichments = []

    for i, entry in enumerate(entries):
        eid = entry.get("id", "")
        name = entry.get("standard_name", "")
        st = entry.get("study_type", "")
        current_enroll = entry.get("total_enrollment")

        # Only query for RCT/meta types where enrollment matters
        if st not in rct_types:
            continue

        current_registry_count = entry.get("registry_completed_trials_count")

        # Skip only when both enrollment and registry count are already plausible.
        if current_enroll and current_enroll >= 50 and current_registry_count is not None:
            continue

        search_terms = _clinical_trial_search_terms(entry)
        print(f"  [{i+1}/{len(entries)}] Querying enrollment for: {name}...", file=sys.stderr)

        if client.circuit_open:
            print("  [CIRCUIT OPEN] Stopping enrichment.", file=sys.stderr)
            break

        ct_result = _ct_search_trials_merged(client, search_terms, max_results=10)
        max_enroll = max((trial.get("enrollment", 0) for trial in ct_result["trials"]), default=0)
        completed_trials = ct_result.get("total", 0)
        needs_count_update = completed_trials > 0 and (
            current_registry_count is None or completed_trials > current_registry_count
        )

        if (max_enroll > 0 and (current_enroll is None or max_enroll > current_enroll)) or needs_count_update:
            enrichments.append({
                "id": eid,
                "name": name,
                "old_enrollment": current_enroll,
                "new_enrollment": max_enroll,
                "old_registry_completed_trials_count": current_registry_count,
                "new_registry_completed_trials_count": completed_trials if completed_trials > 0 else current_registry_count,
            })
            if apply:
                if max_enroll > 0 and (current_enroll is None or max_enroll > current_enroll):
                    entry["total_enrollment"] = max_enroll
                if completed_trials > 0:
                    entry["registry_completed_trials_count"] = completed_trials

    return enrichments


def backfill_auditability_metadata(
    client: APIClient,
    clinical_db: dict,
    *,
    apply: bool = False,
    limit: int = 25,
) -> list[dict]:
    """Backfill operator-auditability metadata on the highest-impact entries first.

    This does not change scoring. It adds provenance fields that explain the
    current classification using live registry counts, outcome-derived tags, and
    existing curated evidence metadata.
    """
    entries = clinical_db.get("backed_clinical_studies", [])
    candidates = [
        entry for entry in entries
        if not entry.get("effect_direction_rationale")
        or not entry.get("effect_direction_confidence")
    ]
    candidates.sort(key=_evidence_impact_score, reverse=True)
    selected = candidates[:limit]
    updates: list[dict] = []

    for i, entry in enumerate(selected):
        name = entry.get("standard_name", "")
        print(f"  [{i+1}/{len(selected)}] Backfilling auditability for: {name}...", file=sys.stderr)

        if client.circuit_open:
            print("  [CIRCUIT OPEN] Stopping auditability backfill.", file=sys.stderr)
            break

        ct_result = ct_search_trials(client, name, max_results=8)
        registry_count = ct_result.get("total", 0) or entry.get("registry_completed_trials_count")
        outcome_tags = derive_endpoint_relevance_tags(
            ct_result.get("trials", []),
            primary_outcome=entry.get("primary_outcome"),
        )
        if not outcome_tags:
            outcome_tags = derive_endpoint_relevance_tags_from_strings(
                entry.get("key_endpoints", []),
                primary_outcome=entry.get("primary_outcome"),
            )

        confidence = derive_effect_direction_confidence(
            entry,
            registry_completed_trials_count=registry_count,
        )
        rationale = build_effect_direction_rationale(
            entry,
            registry_completed_trials_count=registry_count,
            endpoint_relevance_tags=outcome_tags,
        )

        update = {
            "id": entry.get("id"),
            "name": name,
            "registry_completed_trials_count": registry_count,
            "effect_direction_confidence": confidence,
            "effect_direction_rationale": rationale,
            "endpoint_relevance_tags": outcome_tags,
        }
        updates.append(update)

        if apply:
            if registry_count:
                entry["registry_completed_trials_count"] = registry_count
            entry["effect_direction_confidence"] = confidence
            entry["effect_direction_rationale"] = rationale
            if outcome_tags:
                entry["endpoint_relevance_tags"] = outcome_tags

    return updates


# ---------------------------------------------------------------------------
# Report output
# ---------------------------------------------------------------------------

DEFAULT_REPORTS_DIR = SCRIPT_DIR / "reports"


def _default_report_path(mode: str) -> Path:
    """Generate a default report path in scripts/api_audit/reports/."""
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return DEFAULT_REPORTS_DIR / f"clinical_{mode}_{ts}.json"


def save_report(report: dict, output_path: Optional[Path] = None, *, mode: str = "report") -> Path:
    """Save the report to disk. Auto-generates path if none given.

    Always saves to scripts/api_audit/reports/ — never just prints to stdout.
    Returns the path the report was saved to.
    """
    if output_path is None:
        output_path = _default_report_path(mode)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nReport saved to: {output_path}", file=sys.stderr)
    return output_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Clinical evidence discovery and audit tool for PharmaGuide",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", help="Mode to run")

    # Discover
    p_discover = subparsers.add_parser("discover", help="Find IQM compounds missing from clinical DB")
    p_discover.add_argument("--limit", type=int, default=10, help="Max compounds to search (default: 10)")
    p_discover.add_argument("--compound", type=str, help="Search a single compound by name")
    p_discover.add_argument("--apply", action="store_true", help="Auto-add qualifying candidates to clinical DB")
    p_discover.add_argument("--min-trials", type=int, default=3, help="Min completed trials to auto-add (default: 3)")
    p_discover.add_argument("--output", type=str, help="Save report to file")
    p_discover.add_argument("--clinical-db", type=str, default=str(DEFAULT_CLINICAL_DB))
    p_discover.add_argument("--iqm-db", type=str, default=str(DEFAULT_IQM_DB))

    # Audit
    p_audit = subparsers.add_parser("audit", help="Audit all entries for consistency")
    p_audit.add_argument("--output", type=str, help="Save report to file")
    p_audit.add_argument("--clinical-db", type=str, default=str(DEFAULT_CLINICAL_DB))

    # Enrich
    p_enrich = subparsers.add_parser("enrich", help="Populate enrollment data from ClinicalTrials.gov")
    p_enrich.add_argument("--apply", action="store_true", help="Write changes to clinical DB")
    p_enrich.add_argument("--output", type=str, help="Save report to file")
    p_enrich.add_argument("--clinical-db", type=str, default=str(DEFAULT_CLINICAL_DB))

    # Backfill auditability
    p_backfill = subparsers.add_parser(
        "backfill-auditability",
        help="Backfill rationale/confidence/endpoint tags on highest-impact entries first",
    )
    p_backfill.add_argument("--apply", action="store_true", help="Write changes to clinical DB")
    p_backfill.add_argument("--limit", type=int, default=50, help="Max entries to backfill (default: 50)")
    p_backfill.add_argument("--output", type=str, help="Save report to file")
    p_backfill.add_argument("--clinical-db", type=str, default=str(DEFAULT_CLINICAL_DB))

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Init client
    cache_path = CACHE_DIR / f"discover_cache_{args.command}.json"
    client = APIClient(cache_path=cache_path)

    if args.command == "discover":
        clinical_db = load_clinical_db(Path(args.clinical_db))
        iqm = load_iqm(Path(args.iqm_db))
        clinical_names = get_clinical_names(clinical_db)
        gaps = find_gaps(iqm, clinical_names)

        print(f"IQM compounds: {len(iqm) - 1}", file=sys.stderr)
        print(f"Clinical DB entries: {len(clinical_db.get('backed_clinical_studies', []))}", file=sys.stderr)
        print(f"Gaps (missing evidence): {len(gaps)}", file=sys.stderr)

        candidates = discover_candidates(
            client, gaps, limit=args.limit, compound=args.compound
        )

        added = []
        if args.apply:
            # Initialize PubMed client for PMID cross-referencing
            pm_cache = CACHE_DIR / "pubmed_nct_cache.json"
            pm_client = PubMedClient(cache_path=pm_cache)
            print(
                f"PubMed client initialized "
                f"(API key: {'yes' if pm_client.config.api_key else 'no'})",
                file=sys.stderr,
            )

            added = apply_candidates_to_db(
                clinical_db, candidates,
                min_trials=args.min_trials,
                pm_client=pm_client,
            )
            if added:
                # Count how many got endpoints populated
                with_endpoints = sum(
                    1 for e in added if e.get("key_endpoints")
                )
                # Update changelog
                names_added = ", ".join(
                    e["standard_name"] for e in added
                )
                endpoint_note = (
                    f" {with_endpoints}/{len(added)} with "
                    f"auto-populated key_endpoints."
                    if with_endpoints
                    else " All flagged for human review of "
                    "key_endpoints and effect_direction."
                )
                clinical_db["_metadata"]["changelog"].insert(0,
                    f"auto ({datetime.now(UTC).strftime('%Y-%m-%d')}): "
                    f"discover --apply added {len(added)} entries: "
                    f"{names_added}.{endpoint_note}"
                )
                with open(Path(args.clinical_db), "w") as f:
                    json.dump(clinical_db, f, indent=2, ensure_ascii=False)
                print(f"\nAdded {len(added)} entries to clinical DB (min_trials={args.min_trials}).", file=sys.stderr)
                for entry in added:
                    print(f"  + {entry['id']:40s} trials={entry['published_studies']:>5}  enrollment={entry.get('total_enrollment', 'N/A'):>6}  ({entry['standard_name']})", file=sys.stderr)
            else:
                print("\nNo candidates met the min_trials threshold.", file=sys.stderr)

        report = {
            "mode": "discover",
            "timestamp": datetime.now(UTC).isoformat(),
            "total_gaps": len(gaps),
            "searched": len(candidates),
            "candidates": candidates,
            "applied": args.apply,
            "entries_added": len(added),
            "added_ids": [e["id"] for e in added],
            "api_requests": client._request_count,
        }

        save_report(report, Path(args.output) if args.output else None, mode="discover")
        client.save_cache()

    elif args.command == "audit":
        clinical_db = load_clinical_db(Path(args.clinical_db))
        issues = audit_all_entries(clinical_db)

        by_severity = Counter(i["severity"] for i in issues)
        by_check = Counter(i["check"] for i in issues)

        report = {
            "mode": "audit",
            "timestamp": datetime.now(UTC).isoformat(),
            "total_entries": len(clinical_db.get("backed_clinical_studies", [])),
            "total_issues": len(issues),
            "by_severity": dict(by_severity),
            "by_check": dict(by_check),
            "issues": issues,
        }

        # Print summary to stderr
        print(f"\nAudit complete: {len(issues)} issues found", file=sys.stderr)
        for sev in ("HIGH", "MEDIUM", "LOW"):
            cnt = by_severity.get(sev, 0)
            if cnt:
                print(f"  {sev}: {cnt}", file=sys.stderr)

        save_report(report, Path(args.output) if args.output else None, mode="audit")

    elif args.command == "enrich":
        clinical_db = load_clinical_db(Path(args.clinical_db))
        enrichments = enrich_enrollment(client, clinical_db, apply=args.apply)

        report = {
            "mode": "enrich",
            "timestamp": datetime.now(UTC).isoformat(),
            "enrichments": enrichments,
            "api_requests": client._request_count,
            "applied": args.apply,
        }

        if args.apply and enrichments:
            clinical_db["_metadata"]["last_updated"] = datetime.now(UTC).strftime("%Y-%m-%d")
            with open(Path(args.clinical_db), "w") as f:
                json.dump(clinical_db, f, indent=2, ensure_ascii=False)
            print(f"\nApplied {len(enrichments)} enrollment updates.", file=sys.stderr)

        print(f"\nEnrichment: {len(enrichments)} entries {'applied' if args.apply else 'found (dry-run)'}.", file=sys.stderr)

        save_report(report, Path(args.output) if args.output else None, mode="enrich")

    elif args.command == "backfill-auditability":
        clinical_db = load_clinical_db(Path(args.clinical_db))
        updates = backfill_auditability_metadata(
            client,
            clinical_db,
            apply=args.apply,
            limit=args.limit,
        )

        report = {
            "mode": "backfill-auditability",
            "timestamp": datetime.now(UTC).isoformat(),
            "limit": args.limit,
            "updates": updates,
            "count": len(updates),
        }

        if args.apply and updates:
            clinical_db["_metadata"]["last_updated"] = datetime.now(UTC).strftime("%Y-%m-%d")
            clinical_db["_metadata"]["changelog"].insert(
                0,
                f"auto ({datetime.now(UTC).strftime('%Y-%m-%d')}): "
                f"backfill-auditability updated {len(updates)} high-impact entries "
                f"with registry counts, endpoint tags, and effect_direction auditability fields.",
            )
            with open(Path(args.clinical_db), "w") as f:
                json.dump(clinical_db, f, indent=2, ensure_ascii=False)
            print(f"\nApplied {len(updates)} auditability updates.", file=sys.stderr)

        print(
            f"\nBackfill auditability: {len(updates)} entries "
            f"{'applied' if args.apply else 'found (dry-run)'}.",
            file=sys.stderr,
        )
        save_report(
            report,
            Path(args.output) if args.output else None,
            mode="backfill_auditability",
        )
        client.save_cache()


if __name__ == "__main__":
    main()
