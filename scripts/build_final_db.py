#!/usr/bin/env python3
"""
PharmaGuide Final DB Builder v1.0.0
====================================
Reads enriched + scored pipeline outputs and produces:
  1. pharmaguide_core.db  — SQLite database for the phone
  2. detail_blobs/        — per-product JSON files for Supabase
  3. export_manifest.json — version/checksum metadata

Usage:
    python build_final_db.py --enriched-dir output_Brand_enriched/enriched \
                             --scored-dir output_Brand_scored/scored \
                             --output-dir final_db_output

    # Process multiple brands at once:
    python build_final_db.py --enriched-dir output_Thorne_enriched/enriched \
                                            output_Olly_enriched/enriched \
                             --scored-dir   output_Thorne_scored/scored \
                                            output_Olly_scored/scored \
                             --output-dir final_db_output

Follows: FINAL_EXPORT_SCHEMA_V1.md
"""

import argparse
import hashlib
import json
import logging
import math as _math
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

EXPORT_SCHEMA_VERSION = 1
PIPELINE_VERSION = "3.1.0"
TOP_WARNINGS_MAX = 5
MIN_APP_VERSION = "1.0.0"
EXPORT_COMMIT_EVERY = 2000
DETAIL_BLOB_STORAGE_PREFIX = "shared/details/sha256"

# ─── Warning priority for top_warnings ───
WARNING_PRIORITY = {
    "banned_substance": 0,
    "recalled_ingredient": 1,
    "watchlist_substance": 2,
    "allergen": 3,
    "harmful_additive": 4,
    "interaction": 5,
    "drug_interaction": 6,
    "dietary": 7,
    "status": 8,
}

SEVERITY_PRIORITY = {
    "critical": 0, "contraindicated": 0,
    "high": 1, "avoid": 1,
    "moderate": 2, "caution": 2,
    "monitor": 3,
    "low": 4,
    "info": 5,
}


def build_db_version(now: datetime) -> str:
    """Return a UTC build version that changes on every export."""
    return now.astimezone(timezone.utc).strftime("%Y.%m.%d.%H%M%S")


def compute_file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def remote_blob_storage_path(blob_sha256: str) -> str:
    """Return the shared remote storage path for a hashed detail blob."""
    shard = blob_sha256[:2]
    return f"{DETAIL_BLOB_STORAGE_PREFIX}/{shard}/{blob_sha256}.json"


def safe_bool(value: Any) -> int:
    """Convert any value to 0/1 integer."""
    return 1 if value else 0


def safe_float(value: Any, default: float = None) -> Optional[float]:
    if value is None:
        return default
    try:
        result = float(value)
        return result if _math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def safe_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def safe_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def normalize_text(value: Any) -> str:
    """Normalize free text for tolerant cross-structure matching."""
    return safe_str(value).lower()


def contaminant_matches(enriched: Dict) -> List[Dict]:
    """Return exact/alias contaminant matches only."""
    matches = []
    banned_subs = safe_list(
        safe_dict(safe_dict(enriched.get("contaminant_data")).get("banned_substances")).get("substances")
    )
    for sub in banned_subs:
        if not isinstance(sub, dict):
            continue
        match_type = normalize_text(sub.get("match_type") or sub.get("match_method"))
        if match_type not in ("exact", "alias"):
            continue
        matches.append(sub)
    return matches


def contaminant_status_matches(enriched: Dict, *statuses: str) -> List[Dict]:
    wanted = {normalize_text(status) for status in statuses}
    return [match for match in contaminant_matches(enriched)
            if normalize_text(match.get("status")) in wanted]


def has_banned_substance(enriched: Dict) -> bool:
    """True only for exact/alias banned ingredient hits, not recalls/high-risk reviews."""
    return bool(contaminant_status_matches(enriched, "banned"))


def collect_match_terms(*values: Any) -> set:
    return {normalize_text(value) for value in values if normalize_text(value)}


def build_harmful_lookup(enriched: Dict) -> Dict[str, Dict]:
    lookup = {}
    for hit in safe_list(enriched.get("harmful_additives")):
        if not isinstance(hit, dict):
            continue
        for term in collect_match_terms(
            hit.get("raw_source_text"),
            hit.get("ingredient"),
            hit.get("additive_name"),
            hit.get("canonical_name"),
        ):
            lookup[term] = hit
    return lookup


def build_contaminant_lookup(enriched: Dict) -> Dict[str, List[Dict]]:
    lookup = {}
    for hit in contaminant_matches(enriched):
        for term in collect_match_terms(
            hit.get("ingredient"),
            hit.get("banned_name"),
            hit.get("name"),
            hit.get("matched_variant"),
        ):
            lookup.setdefault(term, []).append(hit)
    return lookup


def matching_contaminant_hits(lookup: Dict[str, List[Dict]], *ingredient_terms: Any) -> List[Dict]:
    matches = []
    seen = set()
    for term in collect_match_terms(*ingredient_terms):
        for hit in lookup.get(term, []):
            key = id(hit)
            if key in seen:
                continue
            seen.add(key)
            matches.append(hit)
    return matches


def build_allergen_patterns(enriched: Dict) -> List[Dict]:
    patterns = []
    for hit in safe_list(enriched.get("allergen_hits")):
        if not isinstance(hit, dict):
            continue
        patterns.append({
            "pattern": normalize_text(hit.get("matched_text") or hit.get("allergen_name")),
            "hit": hit,
        })
    return patterns


def matching_allergen_hits(patterns: List[Dict], *ingredient_terms: Any) -> List[Dict]:
    matches = []
    seen = set()
    normalized_terms = [term for term in collect_match_terms(*ingredient_terms) if term]
    for item in patterns:
        pattern = item.get("pattern", "")
        if not pattern:
            continue
        if any(pattern in term or term in pattern for term in normalized_terms):
            hit = item["hit"]
            key = id(hit)
            if key not in seen:
                seen.add(key)
                matches.append(hit)
    return matches


EXPORT_REQUIRED_IQD_FIELDS = {
    "raw_source_text",
    "name",
    "standard_name",
    "bio_score",
    "natural",
    "score",
    "notes",
    "category",
    "mapped",
    "safety_hits",
}


def validate_export_contract(enriched: Dict, scored: Dict) -> List[str]:
    """Validate the minimum upstream contract needed for final DB export."""
    issues = []

    if not safe_str(enriched.get("dsld_id")):
        issues.append("missing enriched.dsld_id")
    if not safe_str(enriched.get("product_name")):
        issues.append("missing enriched.product_name")

    iqd = safe_dict(enriched.get("ingredient_quality_data"))
    ingredients = safe_list(iqd.get("ingredients"))

    for idx, ingredient in enumerate(ingredients):
        if not isinstance(ingredient, dict):
            issues.append(f"ingredient_quality_data.ingredients[{idx}] is not an object")
            continue
        missing = sorted(field for field in EXPORT_REQUIRED_IQD_FIELDS if field not in ingredient)
        for field in missing:
            issues.append(f"missing ingredient_quality_data.ingredients[{idx}].{field}")

    if "section_scores" not in scored:
        issues.append("missing scored.section_scores")
    if "scoring_metadata" not in scored:
        issues.append("missing scored.scoring_metadata")

    return issues


HARMFUL_REFERENCE_INDEX: Optional[Dict[str, Dict]] = None
IQM_REFERENCE_INDEX: Optional[Dict[str, Dict]] = None


def extract_identifiers(entry: Dict) -> Optional[Dict]:
    """Extract a compact identifiers block from a data file entry.

    Returns None if no identifiers are present; otherwise returns only
    non-null fields to keep blob size minimal.  Handles both lowercase
    ``cui`` (IQM, harmful_additives) and uppercase ``CUI`` (other_ingredients).
    """
    if not isinstance(entry, dict):
        return None
    ids: Dict[str, Any] = {}
    cui = entry.get("cui") or entry.get("CUI")
    if cui:
        ids["cui"] = cui
    ext = entry.get("external_ids") or {}
    if isinstance(ext, dict):
        for key in ("cas", "pubchem_cid", "unii"):
            val = ext.get(key)
            if val is not None:
                ids[key] = val
    return ids if ids else None


def load_iqm_reference_index() -> Dict[str, Dict]:
    """Load ingredient_quality_map.json and build an index by parent key."""
    global IQM_REFERENCE_INDEX
    if IQM_REFERENCE_INDEX is not None:
        return IQM_REFERENCE_INDEX

    path = Path(__file__).parent / "data" / "ingredient_quality_map.json"
    index: Dict[str, Dict] = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key, entry in data.items():
            if key == "_metadata" or not isinstance(entry, dict):
                continue
            index[key] = entry
    except Exception as exc:
        logger.warning("Failed to load ingredient_quality_map reference data: %s", exc)
    IQM_REFERENCE_INDEX = index
    return IQM_REFERENCE_INDEX


def load_harmful_reference_index() -> Dict[str, Dict]:
    global HARMFUL_REFERENCE_INDEX
    if HARMFUL_REFERENCE_INDEX is not None:
        return HARMFUL_REFERENCE_INDEX

    path = Path(__file__).parent / "data" / "harmful_additives.json"
    index: Dict[str, Dict] = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        entries = safe_list(safe_dict(data).get("harmful_additives"))
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for term in collect_match_terms(entry.get("standard_name"), *safe_list(entry.get("aliases"))):
                index.setdefault(term, entry)
    except Exception as exc:
        logger.warning("Failed to load harmful_additives reference data: %s", exc)
    HARMFUL_REFERENCE_INDEX = index
    return HARMFUL_REFERENCE_INDEX


def resolve_harmful_reference(hit: Optional[Dict]) -> Dict:
    if not isinstance(hit, dict):
        return {}
    index = load_harmful_reference_index()
    for term in collect_match_terms(
        hit.get("canonical_name"),
        hit.get("additive_name"),
        hit.get("ingredient"),
        hit.get("matched_alias"),
    ):
        if term in index:
            return index[term]
    return {}


OTHER_INGREDIENTS_INDEX: Optional[Dict[str, Dict]] = None


def load_other_ingredients_index() -> Dict[str, Dict]:
    global OTHER_INGREDIENTS_INDEX
    if OTHER_INGREDIENTS_INDEX is not None:
        return OTHER_INGREDIENTS_INDEX

    path = Path(__file__).parent / "data" / "other_ingredients.json"
    index: Dict[str, Dict] = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        entries = safe_list(safe_dict(data).get("other_ingredients"))
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for term in collect_match_terms(entry.get("standard_name"), *safe_list(entry.get("aliases"))):
                index.setdefault(term, entry)
    except Exception as exc:
        logger.warning("Failed to load other_ingredients reference data: %s", exc)
    OTHER_INGREDIENTS_INDEX = index
    return OTHER_INGREDIENTS_INDEX


def resolve_other_ingredient_reference(name: str, standard_name: str = "") -> Dict:
    index = load_other_ingredients_index()
    for term in collect_match_terms(name, standard_name):
        if term in index:
            return index[term]
    return {}


def build_combined_safety_hits(
    base_hits: Any,
    contaminant_hits: List[Dict],
    allergen_hits: List[Dict],
    harmful_hit: Optional[Dict],
) -> List[Dict]:
    combined = []
    for hit in safe_list(base_hits):
        if isinstance(hit, dict):
            combined.append(hit)

    for hit in contaminant_hits:
        combined.append({
            "kind": "contaminant",
            "status": safe_str(hit.get("status")),
            "severity_level": safe_str(hit.get("severity_level")),
            "ingredient": safe_str(hit.get("ingredient") or hit.get("banned_name") or hit.get("name")),
            "reason": safe_str(hit.get("reason")),
            "match_type": safe_str(hit.get("match_type") or hit.get("match_method")),
        })

    for hit in allergen_hits:
        combined.append({
            "kind": "allergen",
            "allergen_id": safe_str(hit.get("allergen_id")),
            "allergen_name": safe_str(hit.get("allergen_name")),
            "presence_type": safe_str(hit.get("presence_type")),
            "severity_level": safe_str(hit.get("severity_level")),
            "evidence": safe_str(hit.get("evidence")),
        })

    if harmful_hit:
        harmful_ref = resolve_harmful_reference(harmful_hit)
        combined.append({
            "kind": "harmful_additive",
            "standard_name": safe_str(
                harmful_ref.get("standard_name")
                or harmful_hit.get("canonical_name")
                or harmful_hit.get("additive_name")
                or harmful_hit.get("ingredient")
            ),
            "severity_level": safe_str(harmful_hit.get("severity_level")),
            "category": safe_str(harmful_hit.get("category")),
            "notes": safe_str(harmful_hit.get("notes") or harmful_ref.get("notes")),
            "mechanism_of_harm": safe_str(harmful_hit.get("mechanism_of_harm") or harmful_ref.get("mechanism_of_harm")),
            "population_warnings": safe_list(harmful_hit.get("population_warnings") or harmful_ref.get("population_warnings")),
            "classification_evidence": safe_str(harmful_hit.get("classification_evidence")),
            "match_method": safe_str(harmful_hit.get("match_method")),
            "matched_alias": safe_str(harmful_hit.get("matched_alias")),
        })

    return combined


# ─── Schema Creation ───

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS products_core (
    dsld_id                       TEXT PRIMARY KEY,
    product_name                  TEXT NOT NULL,
    brand_name                    TEXT,
    upc_sku                       TEXT,
    image_url                     TEXT,
    image_is_pdf                  INTEGER DEFAULT 0,
    thumbnail_key                 TEXT,
    detail_blob_sha256            TEXT,
    interaction_summary_hint      TEXT,
    decision_highlights           TEXT,

    product_status                TEXT,
    discontinued_date             TEXT,
    form_factor                   TEXT,
    supplement_type               TEXT,

    score_quality_80              REAL,
    score_display_80              TEXT,
    score_display_100_equivalent  TEXT,
    score_100_equivalent          REAL,
    grade                         TEXT,
    verdict                       TEXT,
    safety_verdict                TEXT,
    mapped_coverage               REAL,

    score_ingredient_quality      REAL,
    score_ingredient_quality_max  REAL,
    score_safety_purity           REAL,
    score_safety_purity_max       REAL,
    score_evidence_research       REAL,
    score_evidence_research_max   REAL,
    score_brand_trust             REAL,
    score_brand_trust_max         REAL,

    percentile_rank               REAL,
    percentile_top_pct            REAL,
    percentile_category           TEXT,
    percentile_label              TEXT,
    percentile_cohort             INTEGER,

    is_gluten_free                INTEGER DEFAULT 0,
    is_dairy_free                 INTEGER DEFAULT 0,
    is_soy_free                   INTEGER DEFAULT 0,
    is_vegan                      INTEGER DEFAULT 0,
    is_vegetarian                 INTEGER DEFAULT 0,
    is_organic                    INTEGER DEFAULT 0,
    is_non_gmo                    INTEGER DEFAULT 0,

    has_banned_substance          INTEGER DEFAULT 0,
    has_recalled_ingredient       INTEGER DEFAULT 0,
    has_harmful_additives         INTEGER DEFAULT 0,
    has_allergen_risks            INTEGER DEFAULT 0,
    blocking_reason               TEXT,

    is_probiotic                  INTEGER DEFAULT 0,
    contains_sugar                INTEGER DEFAULT 0,
    contains_sodium               INTEGER DEFAULT 0,
    diabetes_friendly             INTEGER DEFAULT 0,
    hypertension_friendly         INTEGER DEFAULT 0,

    is_trusted_manufacturer       INTEGER DEFAULT 0,
    has_third_party_testing       INTEGER DEFAULT 0,
    has_full_disclosure           INTEGER DEFAULT 0,

    cert_programs                 TEXT,
    badges                        TEXT,
    top_warnings                  TEXT,
    flags                         TEXT,

    scoring_version               TEXT,
    output_schema_version         TEXT,
    enrichment_version            TEXT,
    scored_date                   TEXT,
    export_version                TEXT NOT NULL,
    exported_at                   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reference_data (
    key         TEXT PRIMARY KEY,
    version     TEXT NOT NULL,
    data        TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS export_manifest (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

CORE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_core_upc ON products_core(upc_sku);
CREATE INDEX IF NOT EXISTS idx_core_name ON products_core(product_name);
CREATE INDEX IF NOT EXISTS idx_core_brand ON products_core(brand_name);
CREATE INDEX IF NOT EXISTS idx_core_verdict ON products_core(verdict);
CREATE INDEX IF NOT EXISTS idx_core_score ON products_core(score_quality_80);
CREATE INDEX IF NOT EXISTS idx_core_status ON products_core(product_status);
CREATE INDEX IF NOT EXISTS idx_core_type ON products_core(supplement_type);
"""

FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS products_fts USING fts5(
    product_name, brand_name,
    content='products_core', content_rowid='rowid',
    tokenize='porter unicode61'
);
"""


def image_url_is_pdf(image_url: Any) -> int:
    """Return 1 when the image URL points to a PDF, else 0."""
    value = safe_str(image_url)
    if not value:
        return 0
    parsed = urlparse(value)
    path = parsed.path or value
    return 1 if path.lower().endswith(".pdf") else 0


def build_interaction_summary_hint(enriched: Dict) -> Dict[str, Any]:
    """Build a compact interaction hint for instant result-card decisions."""
    interaction_profile = safe_dict(enriched.get("interaction_profile"))
    condition_summary = safe_dict(interaction_profile.get("condition_summary"))
    drug_class_summary = safe_dict(interaction_profile.get("drug_class_summary"))
    ingredient_alerts = safe_list(interaction_profile.get("ingredient_alerts"))

    condition_ids = {safe_str(key) for key in condition_summary.keys() if safe_str(key)}
    drug_class_ids = {safe_str(key) for key in drug_class_summary.keys() if safe_str(key)}
    severity_candidates = [safe_str(interaction_profile.get("highest_severity"))]

    for alert in ingredient_alerts:
        if not isinstance(alert, dict):
            continue
        for hit in safe_list(alert.get("condition_hits")):
            if isinstance(hit, dict):
                condition_id = safe_str(hit.get("condition_id"))
                if condition_id:
                    condition_ids.add(condition_id)
                severity_candidates.append(safe_str(hit.get("severity")))
        for hit in safe_list(alert.get("drug_class_hits")):
            if isinstance(hit, dict):
                drug_class_id = safe_str(hit.get("drug_class_id"))
                if drug_class_id:
                    drug_class_ids.add(drug_class_id)
                severity_candidates.append(safe_str(hit.get("severity")))

    severity_rank = {
        "contraindicated": 6,
        "avoid": 5,
        "high": 4,
        "caution": 3,
        "moderate": 2,
        "monitor": 1,
        "low": 0,
    }
    highest_severity = ""
    for severity in severity_candidates:
        if not severity:
            continue
        if severity_rank.get(severity, -1) > severity_rank.get(highest_severity, -1):
            highest_severity = severity

    return {
        "has_any": bool(condition_ids or drug_class_ids),
        "highest_severity": highest_severity,
        "condition_ids": sorted(condition_ids),
        "drug_class_ids": sorted(drug_class_ids),
    }


def build_decision_highlights(enriched: Dict, scored: Dict, blocking_reason: Optional[str]) -> Dict[str, str]:
    """Build concise hero highlights so Flutter doesn't need to improvise them."""
    named_programs = safe_list(enriched.get("named_cert_programs"))
    section_scores = safe_dict(scored.get("section_scores"))
    verdict = safe_str(scored.get("verdict")).upper()
    score_80 = safe_float(scored.get("score_80"), 0) or 0

    if safe_bool(enriched.get("is_trusted_manufacturer")) and safe_bool(enriched.get("has_full_disclosure")):
        positive = "Trusted manufacturer with full label disclosure."
    elif safe_float(safe_dict(section_scores.get("C_evidence_research")).get("score"), 0) >= 12:
        positive = "Backed by meaningful clinical evidence."
    elif score_80 >= 60:
        positive = "Strong overall quality profile."
    else:
        positive = "Some quality signals are present, but this product needs a closer look."

    if blocking_reason == "banned_substance":
        caution = "Contains a banned substance match."
    elif blocking_reason == "recalled_ingredient":
        caution = "Contains a recalled ingredient match."
    elif blocking_reason == "high_risk_ingredient":
        caution = "Contains an ingredient flagged as high risk."
    elif safe_list(enriched.get("harmful_additives")):
        caution = "Includes additives with known safety concerns."
    elif safe_list(enriched.get("allergen_hits")):
        caution = "Contains allergen risks that may matter for sensitive users."
    elif verdict in {"CAUTION", "POOR", "UNSAFE", "BLOCKED"}:
        caution = "Safety or quality signals lower confidence in this product."
    else:
        caution = "No major caution signal surfaced in the quick review."

    if named_programs:
        trust = f"Third-party programs listed: {', '.join(str(program) for program in named_programs[:2])}."
    elif safe_bool(enriched.get("has_full_disclosure")):
        trust = "Formula is fully disclosed for easier review."
    elif safe_bool(enriched.get("is_trusted_manufacturer")):
        trust = "Manufacturer reputation supports baseline trust."
    else:
        trust = "Trust signals are limited in the current export."

    return {
        "positive": positive,
        "caution": caution,
        "trust": trust,
    }


# ─── Data Loading ───

def iter_json_products(directories: List[str]):
    """Yield product dicts from JSON files without materializing whole corpora."""
    for dir_path in directories:
        if not os.path.isdir(dir_path):
            logger.warning("Directory not found: %s", dir_path)
            continue
        for fname in sorted(os.listdir(dir_path)):
            if not fname.endswith(".json") or fname.startswith("."):
                continue
            fpath = os.path.join(dir_path, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            yield item
                elif isinstance(data, dict):
                    yield data
            except (json.JSONDecodeError, OSError) as e:
                logger.error("Failed to load %s: %s", fpath, e)

def index_by_id(products: List[Dict], id_field: str = "dsld_id") -> Dict[str, Dict]:
    """Index a list of product dicts by dsld_id."""
    index = {}
    for p in products:
        pid = str(p.get(id_field, ""))
        if pid:
            index[pid] = p
    return index


def initialize_stage_table(conn: sqlite3.Connection, table_name: str) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            dsld_id TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            matched INTEGER NOT NULL DEFAULT 0
        )
        """
    )


def stage_products_by_id(conn: sqlite3.Connection, table_name: str, directories: List[str]) -> int:
    """Stage products in SQLite so the main export can stream lookups by dsld_id."""
    initialize_stage_table(conn, table_name)
    staged = 0
    for product in iter_json_products(directories):
        dsld_id = safe_str(product.get("dsld_id"))
        if not dsld_id:
            continue
        conn.execute(
            f"INSERT OR REPLACE INTO {table_name} (dsld_id, payload, matched) VALUES (?, ?, 0)",
            (dsld_id, json.dumps(product, ensure_ascii=False, separators=(",", ":"))),
        )
        staged += 1
    conn.commit()
    return staged


def fetch_staged_product(conn: sqlite3.Connection, table_name: str, dsld_id: str) -> Optional[Dict]:
    row = conn.execute(
        f"SELECT payload FROM {table_name} WHERE dsld_id = ?",
        (str(dsld_id),),
    ).fetchone()
    if not row:
        return None
    return json.loads(row[0])


def mark_staged_product_matched(conn: sqlite3.Connection, table_name: str, dsld_id: str) -> bool:
    cursor = conn.execute(
        f"UPDATE {table_name} SET matched = 1 WHERE dsld_id = ?",
        (str(dsld_id),),
    )
    return cursor.rowcount > 0


def iter_staged_products(conn: sqlite3.Connection, table_name: str):
    """Yield staged products in stable dsld_id order."""
    cursor = conn.execute(
        f"SELECT dsld_id, payload FROM {table_name} ORDER BY dsld_id"
    )
    for dsld_id, payload in cursor:
        yield dsld_id, json.loads(payload)


def apply_sqlite_build_pragmas(conn: sqlite3.Connection) -> None:
    """Tune SQLite for large one-writer export builds."""
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA cache_size = -200000")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA journal_mode = MEMORY")


# ─── Warning Builder ───

def build_top_warnings(enriched: Dict) -> List[str]:
    """Build prioritized warning list from enriched product data."""
    raw_warnings = []

    # Banned substances
    for sub in contaminant_matches(enriched):
        status = safe_str(sub.get("status")).lower()
        name = safe_str(sub.get("ingredient") or sub.get("banned_name") or sub.get("name"))
        if status == "banned":
            raw_warnings.append(("banned_substance", "critical", f"Banned substance: {name}"))
        elif status == "recalled":
            raw_warnings.append(("recalled_ingredient", "high", f"Recalled ingredient: {name}"))
        elif status == "high_risk":
            raw_warnings.append(("banned_substance", "high", f"High-risk ingredient: {name}"))
        elif status == "watchlist":
            raw_warnings.append(("watchlist_substance", safe_str(sub.get("severity_level"), "moderate"),
                                 f"Watchlist ingredient: {name}"))

    # Allergens
    for a in safe_list(enriched.get("allergen_hits")):
        if not isinstance(a, dict):
            continue
        raw_warnings.append((
            "allergen",
            safe_str(a.get("severity_level"), "moderate"),
            f"Allergen: {safe_str(a.get('allergen_name'))} ({safe_str(a.get('presence_type'), 'contains')})"
        ))

    # Harmful additives
    for h in safe_list(enriched.get("harmful_additives")):
        if not isinstance(h, dict):
            continue
        sev = safe_str(h.get("severity_level"), "moderate")
        name = safe_str(h.get("additive_name") or h.get("ingredient"))
        raw_warnings.append(("harmful_additive", sev, f"{sev.title()}-risk additive: {name}"))

    # Interaction alerts
    for alert in safe_list(safe_dict(enriched.get("interaction_profile")).get("ingredient_alerts")):
        if not isinstance(alert, dict):
            continue
        ing_name = safe_str(alert.get("ingredient_name"))
        for ch in safe_list(alert.get("condition_hits")):
            if not isinstance(ch, dict):
                continue
            sev = safe_str(ch.get("severity"), "moderate")
            cond = safe_str(ch.get("condition_id"))
            if sev in ("contraindicated", "avoid", "critical", "high"):
                raw_warnings.append(("interaction", sev, f"Interaction: {ing_name} / {cond}"))

    # Dietary sensitivity
    ds = safe_dict(enriched.get("dietary_sensitivity_data"))
    dietary_warnings = safe_list(ds.get("warnings"))
    for warning in dietary_warnings:
        if not isinstance(warning, dict):
            continue
        raw_warnings.append((
            "dietary",
            safe_str(warning.get("severity"), "info"),
            safe_str(warning.get("message")),
        ))
    if not dietary_warnings:
        sugar = safe_dict(ds.get("sugar"))
        sodium = safe_dict(ds.get("sodium"))
        if sugar.get("level") in ("moderate", "high"):
            raw_warnings.append((
                "dietary", "info",
                f"Sugar: {sugar.get('amount_g', 0)}g ({safe_str(sugar.get('level_display'))})"
            ))
        if sodium.get("level") in ("moderate", "high"):
            raw_warnings.append((
                "dietary", "info",
                f"Sodium: {sodium.get('amount_mg', 0)}mg ({safe_str(sodium.get('level_display'))})"
            ))

    # Product status
    product_status = safe_str(enriched.get("status")).lower()
    if product_status == "discontinued":
        disc_date = safe_str(enriched.get("discontinuedDate"))[:10]
        raw_warnings.append(("status", "info", f"Discontinued ({disc_date})"))
    elif product_status == "off_market":
        raw_warnings.append(("status", "info", "Off market"))

    # Sort by priority
    raw_warnings.sort(key=lambda w: (
        WARNING_PRIORITY.get(w[0], 99),
        SEVERITY_PRIORITY.get(w[1], 99),
    ))

    return [w[2] for w in raw_warnings[:TOP_WARNINGS_MAX]]


# ─── Blocking Reason ───

def derive_blocking_reason(enriched: Dict, scored: Dict) -> Optional[str]:
    """Derive blocking_reason from B0 gate results."""
    verdict = safe_str(scored.get("verdict"))
    if verdict not in ("BLOCKED", "UNSAFE", "CAUTION"):
        return None

    for sub in contaminant_matches(enriched):
        status = safe_str(sub.get("status")).lower()
        if status == "banned":
            return "banned_ingredient"
        if status == "recalled":
            return "recalled_ingredient"
        if status == "high_risk":
            return "high_risk_ingredient"

    return "safety_block" if verdict in ("BLOCKED", "UNSAFE") else None


# ─── Has Recalled Ingredient ───

def has_recalled_ingredient(enriched: Dict) -> bool:
    """Check if any ingredient has recalled status with exact/alias match."""
    return bool(contaminant_status_matches(enriched, "recalled"))


# ─── Detail Blob Builder ───

def build_detail_blob(enriched: Dict, scored: Dict) -> Dict:
    """Build the per-product detail blob for caching/Supabase."""
    # Active ingredients
    iqd = safe_dict(enriched.get("ingredient_quality_data"))
    iqd_by_raw = {}
    for si in safe_list(iqd.get("ingredients")):
        if isinstance(si, dict):
            key = safe_str(si.get("raw_source_text"))
            if key:
                iqd_by_raw[key] = si
    skipped_by_raw = {}
    for si in safe_list(iqd.get("ingredients_skipped")):
        if isinstance(si, dict):
            key = safe_str(si.get("raw_source_text"))
            if key and key not in iqd_by_raw:
                skipped_by_raw[key] = si

    harmful_lookup = build_harmful_lookup(enriched)
    contaminant_lookup = build_contaminant_lookup(enriched)
    allergen_patterns = build_allergen_patterns(enriched)
    iqm_index = load_iqm_reference_index()

    # Dosage normalization
    norm_raw = safe_dict(enriched.get("dosage_normalization")).get("normalized_ingredients", {})
    norm_data = {}
    if isinstance(norm_raw, list):
        for item in norm_raw:
            if isinstance(item, dict):
                key = safe_str(item.get("original_name"))
                if key:
                    norm_data[key] = item
    elif isinstance(norm_raw, dict):
        norm_data = norm_raw

    # Build ingredients
    ingredients = []
    for ing in safe_list(enriched.get("activeIngredients")):
        if not isinstance(ing, dict):
            continue
        raw = safe_str(ing.get("raw_source_text"))
        name = safe_str(ing.get("name"), raw)
        m = iqd_by_raw.get(raw, skipped_by_raw.get(raw, {}))
        ne = norm_data.get(raw, norm_data.get(name, {}))
        if not isinstance(ne, dict):
            ne = {}
        standard_name = safe_str(ing.get("standardName"))
        ingredient_hits = matching_contaminant_hits(contaminant_lookup, raw, name, standard_name)
        allergen_hits = matching_allergen_hits(allergen_patterns, raw, name, standard_name)
        harmful_hit = None
        for term in collect_match_terms(raw, name, standard_name):
            harmful_hit = harmful_lookup.get(term)
            if harmful_hit:
                break
        harmful_ref = resolve_harmful_reference(harmful_hit)
        combined_safety_hits = build_combined_safety_hits(
            m.get("safety_hits"),
            ingredient_hits,
            allergen_hits,
            harmful_hit,
        )

        qty = ing.get("quantity")
        ingredients.append({
            "raw_source_text": raw,
            "name": name,
            "standardName": standard_name,
            "normalized_key": safe_str(ing.get("normalized_key")),
            "forms": safe_list(ing.get("forms")),
            "quantity": safe_float(qty),
            "unit": safe_str(ing.get("unit")),
            "standard_name": safe_str(m.get("standard_name")),
            "form": safe_str(m.get("form")),
            "matched_form": safe_str(m.get("matched_form")),
            "matched_forms": safe_list(m.get("matched_forms")),
            "extracted_forms": safe_list(m.get("extracted_forms")),
            "category": safe_str(m.get("category")),
            "bio_score": safe_float(m.get("bio_score")),
            "natural": bool(m.get("natural")),
            "score": safe_float(m.get("score")),
            "notes": safe_str(m.get("notes")),
            "mapped": safe_bool(m.get("mapped", ing.get("mapped"))),
            "safety_hits": combined_safety_hits,
            "normalized_amount": safe_float(ne.get("normalized_amount")),
            "normalized_unit": safe_str(ne.get("normalized_unit")),
            "role": "active",
            "parent_key": safe_str(m.get("parent_key") or ing.get("normalized_key")),
            "dosage": safe_float(qty),
            "dosage_unit": safe_str(ing.get("unit")),
            "normalized_value": safe_float(ne.get("normalized_amount")),
            "is_mapped": safe_bool(m.get("mapped", ing.get("mapped"))),
            "is_harmful": bool(harmful_hit),
            "harmful_severity": harmful_hit.get("severity_level") if harmful_hit else None,
            "harmful_notes": (
                safe_str(harmful_ref.get("mechanism_of_harm"))
                or safe_str(harmful_ref.get("notes"))
                or safe_str(harmful_hit.get("classification_evidence"))
                or safe_str(harmful_hit.get("category"))
            ) if harmful_hit else None,
            "is_banned": any(normalize_text(hit.get("status")) == "banned" for hit in ingredient_hits),
            "is_allergen": bool(allergen_hits),
            "identifiers": extract_identifiers(
                iqm_index.get(safe_str(m.get("parent_key") or ing.get("normalized_key")), {})
            ),
        })

    # Inactive ingredients
    inactive = []
    for ing in safe_list(enriched.get("inactiveIngredients")):
        if not isinstance(ing, dict):
            continue
        raw = safe_str(ing.get("raw_source_text"))
        name = safe_str(ing.get("name"), raw)
        std_name_ing = safe_str(ing.get("standardName"))
        harmful_hit = None
        for term in collect_match_terms(raw, name, std_name_ing):
            harmful_hit = harmful_lookup.get(term)
            if harmful_hit:
                break
        harmful_ref = resolve_harmful_reference(harmful_hit)
        other_ref = resolve_other_ingredient_reference(name, std_name_ing)

        # Notes priority: harmful_ref (safety) > enrichment-embedded > other_ingredients ref
        notes_text = (
            safe_str(harmful_ref.get("notes"))
            or safe_str(harmful_hit.get("notes") if harmful_hit else "")
            or safe_str(other_ref.get("notes"))
        )
        mechanism_text = safe_str(harmful_ref.get("mechanism_of_harm"))

        inactive.append({
            "raw_source_text": raw,
            "name": name,
            "standardName": std_name_ing,
            "normalized_key": safe_str(ing.get("normalized_key")),
            "forms": safe_list(ing.get("forms")),
            "category": safe_str(ing.get("category") or other_ref.get("category")),
            "is_additive": safe_bool(ing.get("isAdditive") or other_ref.get("is_additive")),
            "additive_type": safe_str(
                ing.get("additiveType")
                or other_ref.get("additive_type")
            ),
            "standard_name": safe_str(
                harmful_ref.get("standard_name")
                or (harmful_hit or {}).get("canonical_name")
                or (harmful_hit or {}).get("additive_name")
                or other_ref.get("standard_name")
            ),
            "severity_level": safe_str((harmful_hit or {}).get("severity_level")),
            "match_method": safe_str((harmful_hit or {}).get("match_method")),
            "matched_alias": safe_str((harmful_hit or {}).get("matched_alias")),
            "notes": notes_text,
            "mechanism_of_harm": mechanism_text,
            "common_uses": safe_list(other_ref.get("common_uses")),
            "population_warnings": safe_list(
                harmful_ref.get("population_warnings")
                or (harmful_hit or {}).get("population_warnings")
            ),
            "is_harmful": bool(harmful_hit),
            "harmful_severity": harmful_hit.get("severity_level") if harmful_hit else None,
            "harmful_notes": (
                mechanism_text
                or notes_text
                or safe_str((harmful_hit or {}).get("classification_evidence"))
                or safe_str((harmful_hit or {}).get("category"))
            ) if harmful_hit else None,
            "identifiers": extract_identifiers(harmful_ref or other_ref),
        })

    # Warnings
    warnings = []
    for sub in contaminant_matches(enriched):
        status = normalize_text(sub.get("status"))
        name = safe_str(sub.get("ingredient") or sub.get("banned_name") or sub.get("name"))
        reason = safe_str(sub.get("reason"))
        severity = safe_str(
            sub.get("severity_level"),
            "critical" if status == "banned" else "high" if status == "recalled" else "moderate",
        )
        warning_type = {
            "banned": "banned_substance",
            "recalled": "recalled_ingredient",
            "high_risk": "high_risk_ingredient",
            "watchlist": "watchlist_substance",
        }.get(status, "safety")
        title_prefix = {
            "banned": "Banned substance",
            "recalled": "Recalled ingredient",
            "high_risk": "High-risk ingredient",
            "watchlist": "Watchlist ingredient",
        }.get(status, "Safety issue")
        warnings.append({
            "type": warning_type,
            "severity": severity,
            "title": f"{title_prefix}: {name}",
            "detail": reason or safe_str(sub.get("category")),
            "source": "banned_recalled_ingredients",
            "date": sub.get("regulatory_date"),
            "regulatory_date_label": safe_str(sub.get("regulatory_date_label")),
            "clinical_risk": safe_str(sub.get("clinical_risk_enum")),
            "identifiers": extract_identifiers(sub),
        })

    for h in safe_list(enriched.get("harmful_additives")):
        if not isinstance(h, dict):
            continue
        # Prefer notes/mechanism emitted by enrichment; fallback to runtime resolution
        h_ref = resolve_harmful_reference(h)
        h_notes = safe_str(h.get("notes") or h_ref.get("notes"))
        h_mechanism = safe_str(h.get("mechanism_of_harm") or h_ref.get("mechanism_of_harm"))
        h_pop_warnings = h.get("population_warnings") or h_ref.get("population_warnings") or []
        warnings.append({
            "type": "harmful_additive",
            "severity": safe_str(h.get("severity_level"), "moderate"),
            "title": f"Contains {safe_str(h.get('additive_name') or h.get('ingredient'))}",
            "detail": h_mechanism or h_notes or f"Category: {safe_str(h.get('category'))}",
            "notes": h_notes,
            "mechanism_of_harm": h_mechanism,
            "population_warnings": safe_list(h_pop_warnings),
            "category": safe_str(h.get("category")),
            "source": "harmful_additives_db",
            "identifiers": extract_identifiers(h_ref),
        })

    for a in safe_list(enriched.get("allergen_hits")):
        if not isinstance(a, dict):
            continue
        warnings.append({
            "type": "allergen",
            "severity": safe_str(a.get("severity_level"), "moderate"),
            "title": f"Allergen: {safe_str(a.get('allergen_name'))}",
            "detail": f"Presence: {safe_str(a.get('presence_type'))}. {safe_str(a.get('evidence'))}",
            "notes": safe_str(a.get("notes")),
            "supplement_context": safe_str(a.get("supplement_context")),
            "prevalence": safe_str(a.get("prevalence")),
            "source": "allergen_db",
        })

    for alert in safe_list(safe_dict(enriched.get("interaction_profile")).get("ingredient_alerts")):
        if not isinstance(alert, dict):
            continue
        ing_name = safe_str(alert.get("ingredient_name"))
        for ch in safe_list(alert.get("condition_hits")):
            if isinstance(ch, dict):
                dose_eval = ch.get("dose_threshold_evaluation")
                warnings.append({
                    "type": "interaction",
                    "severity": safe_str(ch.get("severity"), "moderate"),
                    "title": f"{ing_name} / {safe_str(ch.get('condition_id'))}",
                    "detail": safe_str(ch.get("mechanism")),
                    "action": safe_str(ch.get("action")),
                    "condition_id": safe_str(ch.get("condition_id")),
                    "ingredient_name": ing_name,
                    "evidence_level": safe_str(ch.get("evidence_level")),
                    "sources": safe_list(ch.get("sources")),
                    "dose_threshold_evaluation": dose_eval if isinstance(dose_eval, dict) else None,
                    "source": "interaction_rules",
                })
        for dh in safe_list(alert.get("drug_class_hits")):
            if isinstance(dh, dict):
                dose_eval = dh.get("dose_threshold_evaluation")
                warnings.append({
                    "type": "drug_interaction",
                    "severity": safe_str(dh.get("severity"), "moderate"),
                    "title": f"{ing_name} / {safe_str(dh.get('drug_class_id'))}",
                    "detail": safe_str(dh.get("mechanism")),
                    "action": safe_str(dh.get("action")),
                    "drug_class_id": safe_str(dh.get("drug_class_id")),
                    "ingredient_name": ing_name,
                    "evidence_level": safe_str(dh.get("evidence_level")),
                    "sources": safe_list(dh.get("sources")),
                    "dose_threshold_evaluation": dose_eval if isinstance(dose_eval, dict) else None,
                    "source": "interaction_rules",
                })

    ds = safe_dict(enriched.get("dietary_sensitivity_data"))
    dietary_warnings = safe_list(ds.get("warnings"))
    for warning in dietary_warnings:
        if not isinstance(warning, dict):
            continue
        warnings.append({
            "type": "dietary",
            "severity": safe_str(warning.get("severity"), "moderate"),
            "title": safe_str(warning.get("type"), "dietary").replace("_", " ").title(),
            "detail": safe_str(warning.get("message") or warning.get("recommendation")),
            "source": "dietary_sensitivity_data",
        })
    if not dietary_warnings:
        sugar = safe_dict(ds.get("sugar"))
        sodium = safe_dict(ds.get("sodium"))
        if sugar.get("level") in ("moderate", "high"):
            warnings.append({
                "type": "dietary",
                "severity": "moderate",
                "title": "Sugar Content",
                "detail": f"{sugar.get('amount_g', 0)}g sugar per serving ({safe_str(sugar.get('level_display'))})",
                "source": "dietary_sensitivity_data",
            })
        if sodium.get("level") in ("moderate", "high"):
            warnings.append({
                "type": "dietary",
                "severity": "moderate",
                "title": "Sodium Content",
                "detail": f"{sodium.get('amount_mg', 0)}mg sodium per serving ({safe_str(sodium.get('level_display'))})",
                "source": "dietary_sensitivity_data",
            })

    product_status = normalize_text(enriched.get("status"))
    if product_status == "discontinued":
        warnings.append({
            "type": "status",
            "severity": "info",
            "title": "Discontinued Product",
            "detail": safe_str(enriched.get("discontinuedDate"))[:10],
            "source": "dsld",
        })
    elif product_status == "off_market":
        warnings.append({
            "type": "status",
            "severity": "info",
            "title": "Off-Market Product",
            "detail": "Product is no longer marketed.",
            "source": "dsld",
        })

    # Section breakdown — rename to descriptive, preserve all sub-scores
    breakdown_raw = safe_dict(scored.get("breakdown"))
    a_raw = safe_dict(breakdown_raw.get("A"))
    section_breakdown = {
        "ingredient_quality": {
            "score": safe_float(a_raw.get("score"), 0),
            "max": safe_float(a_raw.get("max"), 25),
            "sub": {k: v for k, v in a_raw.items()
                    if k not in ("score", "max")},
        },
        "safety_purity": {
            "score": safe_float(safe_dict(breakdown_raw.get("B")).get("score"), 0),
            "max": safe_float(safe_dict(breakdown_raw.get("B")).get("max"), 30),
            "sub": {k: v for k, v in safe_dict(breakdown_raw.get("B")).items()
                    if k not in ("score", "max", "raw")},
        },
        "evidence_research": {
            "score": safe_float(safe_dict(breakdown_raw.get("C")).get("score"), 0),
            "max": safe_float(safe_dict(breakdown_raw.get("C")).get("max"), 20),
            "matched_entries": safe_dict(breakdown_raw.get("C")).get("matched_entries"),
            "ingredient_points": safe_dict(breakdown_raw.get("C")).get("ingredient_points"),
        },
        "brand_trust": {
            "score": safe_float(safe_dict(breakdown_raw.get("D")).get("score"), 0),
            "max": safe_float(safe_dict(breakdown_raw.get("D")).get("max"), 5),
            "sub": {k: v for k, v in safe_dict(breakdown_raw.get("D")).items()
                    if k not in ("score", "max")},
        },
        "violation_penalty": safe_float(breakdown_raw.get("violation_penalty"), 0),
    }

    cd = safe_dict(enriched.get("certification_data"))
    serving = safe_dict(enriched.get("serving_basis"))
    evidence_data = safe_dict(enriched.get("evidence_data"))
    rda_ul_data = safe_dict(enriched.get("rda_ul_data"))

    blob = {
        "dsld_id": safe_str(enriched.get("dsld_id")),
        "blob_version": 1,
        "ingredients": ingredients,
        "inactive_ingredients": inactive,
        "warnings": warnings,
        "section_breakdown": section_breakdown,
        "compliance_detail": safe_dict(enriched.get("compliance_data")),
        "certification_detail": {
            "third_party_programs": cd.get("third_party_programs"),
            "gmp": cd.get("gmp"),
            "purity_verified": safe_bool(cd.get("purity_verified")),
            "heavy_metal_tested": safe_bool(cd.get("heavy_metal_tested")),
            "label_accuracy_verified": safe_bool(cd.get("label_accuracy_verified")),
        },
        "proprietary_blend_detail": {
            "has_proprietary_blends": safe_bool(safe_dict(enriched.get("proprietary_data")).get("has_proprietary_blends")),
            "blends": safe_list(safe_dict(enriched.get("proprietary_data")).get("blends")),
        },
        "dietary_sensitivity_detail": {
            "sugar": safe_dict(ds.get("sugar")),
            "sodium": safe_dict(ds.get("sodium")),
            "sweeteners": safe_dict(ds.get("sweeteners")),
        },
        "serving_info": {
            "basis_count": serving.get("basis_count"),
            "basis_unit": serving.get("basis_unit"),
            "min_servings_per_day": serving.get("min_servings_per_day"),
            "max_servings_per_day": serving.get("max_servings_per_day"),
        },
        "manufacturer_detail": {
            "brand_name": safe_str(enriched.get("brandName")),
            "is_trusted": safe_bool(enriched.get("is_trusted_manufacturer")),
            "manufacturing_region": safe_str(enriched.get("manufacturing_region")),
            "violations": safe_dict(safe_dict(enriched.get("manufacturer_data")).get("violations")),
        },
    }
    if evidence_data:
        blob["evidence_data"] = {
            "match_count": evidence_data.get("match_count"),
            "clinical_matches": safe_list(evidence_data.get("clinical_matches")),
            "unsubstantiated_claims": safe_list(evidence_data.get("unsubstantiated_claims")),
        }
    if rda_ul_data and (
        rda_ul_data.get("collection_enabled") is not None
        or rda_ul_data.get("adequacy_results")
        or rda_ul_data.get("count")
    ):
        blob["rda_ul_data"] = {
            "collection_enabled": rda_ul_data.get("collection_enabled"),
            "collection_reason": rda_ul_data.get("collection_reason"),
            "ingredients_with_rda": rda_ul_data.get("ingredients_with_rda"),
            "analyzed_ingredients": rda_ul_data.get("analyzed_ingredients"),
            "count": rda_ul_data.get("count"),
            "adequacy_results": safe_list(rda_ul_data.get("adequacy_results")),
            "conversion_evidence": safe_list(rda_ul_data.get("conversion_evidence")),
            "safety_flags": safe_list(rda_ul_data.get("safety_flags")),
            "has_over_ul": rda_ul_data.get("has_over_ul"),
        }

    # Probiotic detail — strains, CFU, clinical matches
    probiotic_data = safe_dict(enriched.get("probiotic_data"))
    if probiotic_data.get("is_probiotic_product"):
        blob["probiotic_detail"] = {
            "is_probiotic": True,
            "total_strain_count": probiotic_data.get("total_strain_count"),
            "total_cfu": probiotic_data.get("total_cfu"),
            "total_billion_count": probiotic_data.get("total_billion_count"),
            "guarantee_type": probiotic_data.get("guarantee_type"),
            "has_cfu": probiotic_data.get("has_cfu"),
            "clinical_strains": safe_list(probiotic_data.get("clinical_strains")),
            "clinical_strain_count": probiotic_data.get("clinical_strain_count", 0),
            "prebiotic_present": probiotic_data.get("prebiotic_present", False),
            "prebiotic_name": safe_str(probiotic_data.get("prebiotic_name")),
            "has_survivability_coating": probiotic_data.get("has_survivability_coating", False),
            "survivability_reason": safe_str(probiotic_data.get("survivability_reason")),
            "probiotic_blends": safe_list(probiotic_data.get("probiotic_blends")),
        }

    # Synergy cluster detail — matched clusters with ingredient doses
    formulation_data = safe_dict(enriched.get("formulation_data"))
    synergy_clusters = safe_list(formulation_data.get("synergy_clusters"))
    if synergy_clusters:
        blob["synergy_detail"] = {
            "qualified": safe_bool(enriched.get("synergy_cluster_qualified")),
            "clusters": synergy_clusters,
        }

    # Interaction profile summary — grouped by condition and drug class
    # This is what the app uses to instantly flag products for user conditions
    interaction_profile = safe_dict(enriched.get("interaction_profile"))
    condition_summary = safe_dict(interaction_profile.get("condition_summary"))
    drug_class_summary = safe_dict(interaction_profile.get("drug_class_summary"))
    if condition_summary or drug_class_summary:
        blob["interaction_summary"] = {
            "highest_severity": safe_str(interaction_profile.get("highest_severity")),
            "condition_summary": condition_summary,
            "drug_class_summary": drug_class_summary,
        }

    # Formulation context — explains A3/A4/A5a/A5b bonus reasons
    delivery_data = safe_dict(enriched.get("delivery_data"))
    absorption_data = safe_dict(enriched.get("absorption_data"))
    blob["formulation_detail"] = {
        "delivery_tier": safe_str(
            enriched.get("delivery_tier")
            or delivery_data.get("highest_tier")
        ),
        "delivery_form": safe_str(delivery_data.get("delivery_form")),
        "absorption_enhancer_paired": safe_bool(
            enriched.get("absorption_enhancer_paired")
            or absorption_data.get("qualifies_for_bonus")
        ),
        "absorption_enhancers": safe_list(absorption_data.get("enhancers_found")),
        "is_certified_organic": safe_bool(enriched.get("is_certified_organic")),
        "organic_verification": safe_str(
            formulation_data.get("organic", {}).get("verification_status")
            if isinstance(formulation_data.get("organic"), dict) else ""
        ),
        "standardized_botanicals": safe_list(formulation_data.get("standardized_botanicals")),
        "synergy_cluster_qualified": safe_bool(enriched.get("synergy_cluster_qualified")),
        "claim_non_gmo_verified": safe_bool(enriched.get("claim_non_gmo_project_verified")),
    }

    # Score reasons — structured bonus/penalty lists for the app
    # Bonuses: everything that earned positive points
    bonuses = []
    a_sub = section_breakdown.get("ingredient_quality", {}).get("sub", {})
    if safe_float(a_sub.get("A2"), 0) > 0:
        bonuses.append({"id": "A2", "label": "Premium ingredient forms", "score": a_sub["A2"]})
    if safe_float(a_sub.get("A3"), 0) > 0:
        bonuses.append({"id": "A3", "label": "Advanced delivery system", "score": a_sub["A3"],
                        "detail": safe_str(enriched.get("delivery_tier") or delivery_data.get("highest_tier"))})
    if safe_float(a_sub.get("A4"), 0) > 0:
        bonuses.append({"id": "A4", "label": "Absorption enhancer present", "score": a_sub["A4"]})
    if safe_float(a_sub.get("A5a"), 0) > 0:
        bonuses.append({"id": "A5a", "label": "Certified organic", "score": a_sub["A5a"]})
    if safe_float(a_sub.get("A5b"), 0) > 0:
        bonuses.append({"id": "A5b", "label": "Standardized botanicals", "score": a_sub["A5b"]})
    if safe_float(a_sub.get("A5c"), 0) > 0:
        bonuses.append({"id": "A5c", "label": "Synergy cluster qualified", "score": a_sub["A5c"]})
    if safe_float(a_sub.get("A5d"), 0) > 0:
        bonuses.append({"id": "A5d", "label": "Non-GMO Project Verified", "score": a_sub["A5d"]})
    if safe_float(a_sub.get("A6"), 0) > 0:
        bonuses.append({"id": "A6", "label": "Single-nutrient premium form", "score": a_sub["A6"]})
    if safe_float(a_sub.get("probiotic_bonus"), 0) > 0:
        bonuses.append({"id": "probiotic", "label": "Probiotic quality bonus", "score": a_sub["probiotic_bonus"]})
    b_sub = section_breakdown.get("safety_purity", {}).get("sub", {})
    if safe_float(b_sub.get("B4a"), 0) > 0:
        bonuses.append({"id": "B4a", "label": "Third-party purity testing", "score": b_sub["B4a"]})
    if safe_float(b_sub.get("B4b"), 0) > 0:
        bonuses.append({"id": "B4b", "label": "GMP certified facility", "score": b_sub["B4b"]})
    if safe_float(b_sub.get("B4c"), 0) > 0:
        bonuses.append({"id": "B4c", "label": "Heavy metal tested", "score": b_sub["B4c"]})
    if safe_float(b_sub.get("B_hypoallergenic"), 0) > 0:
        bonuses.append({"id": "B_hypo", "label": "Hypoallergenic verified", "score": b_sub["B_hypoallergenic"]})

    # Penalties: everything that cost points
    penalties = []
    if safe_float(b_sub.get("B0_moderate_penalty"), 0) > 0:
        # Build per-item list from contaminant matches
        for sub in contaminant_matches(enriched):
            status = normalize_text(sub.get("status"))
            name = safe_str(sub.get("ingredient") or sub.get("banned_name"))
            penalties.append({
                "id": "B0", "label": f"{status.title()}: {name}",
                "status": status,
                "reason": safe_str(sub.get("reason"))[:200],
            })
    if safe_float(b_sub.get("B1_penalty"), 0) > 0:
        for h in safe_list(enriched.get("harmful_additives")):
            if isinstance(h, dict):
                penalties.append({
                    "id": "B1", "label": f"Harmful additive: {safe_str(h.get('additive_name') or h.get('ingredient'))}",
                    "severity": safe_str(h.get("severity_level")),
                    "reason": safe_str(h.get("mechanism_of_harm") or h.get("notes") or h.get("category"))[:200],
                })
    if safe_float(b_sub.get("B2_penalty"), 0) > 0:
        for a in safe_list(enriched.get("allergen_hits")):
            if isinstance(a, dict):
                penalties.append({
                    "id": "B2", "label": f"Allergen: {safe_str(a.get('allergen_name'))}",
                    "severity": safe_str(a.get("severity_level")),
                    "presence": safe_str(a.get("presence_type")),
                })
    if safe_float(b_sub.get("B3"), 0) < 0:
        penalties.append({"id": "B3", "label": "Compliance claim violation", "score": b_sub["B3"]})
    if safe_float(b_sub.get("B5_penalty"), 0) > 0:
        penalties.append({"id": "B5", "label": "Proprietary blend opacity",
                          "score": b_sub["B5_penalty"],
                          "blend_count": len(safe_list(b_sub.get("B5_blend_evidence")))})
    if safe_float(b_sub.get("B6_penalty"), 0) > 0:
        penalties.append({"id": "B6", "label": "Unsubstantiated disease claims", "score": b_sub["B6_penalty"]})
    if safe_float(b_sub.get("B7_penalty"), 0) > 0:
        b7_evidence = safe_list(b_sub.get("B7_dose_safety_evidence"))
        for ev in b7_evidence:
            penalties.append({
                "id": "B7",
                "label": f"Exceeds safe dose limit: {ev.get('nutrient', 'unknown')} at {ev.get('pct_ul', 0):.0f}% of UL",
                "severity": "critical" if ev.get("pct_ul", 0) >= 200 else "warning",
                "reason": f"{ev.get('nutrient')}: {ev.get('amount')} vs UL {ev.get('ul')}",
            })
    vp = section_breakdown.get("violation_penalty", 0)
    if vp and safe_float(vp, 0) != 0:
        penalties.append({"id": "violation", "label": "Scoring violation penalty", "score": vp})

    blob["score_bonuses"] = bonuses
    blob["score_penalties"] = penalties

    return blob


# ─── Core Row Builder ───

def build_core_row(
    enriched: Dict,
    scored: Dict,
    exported_at: str,
    detail_blob_sha256: Optional[str] = None,
) -> tuple:
    """Build a products_core row tuple from enriched + scored product data."""
    comp = safe_dict(enriched.get("compliance_data"))
    ds = safe_dict(enriched.get("dietary_sensitivity_data"))
    ss = safe_dict(scored.get("section_scores"))
    cp = safe_dict(scored.get("category_percentile"))
    st = enriched.get("supplement_type")
    st_str = st.get("type", "") if isinstance(st, dict) else safe_str(st)
    sm = safe_dict(scored.get("scoring_metadata"))

    disc_date = safe_str(enriched.get("discontinuedDate"))[:10] or None
    score_80 = safe_float(scored.get("score_80"))
    score_100 = safe_float(scored.get("score_100_equivalent"))

    top_warnings = build_top_warnings(enriched)
    blocking = derive_blocking_reason(enriched, scored)
    interaction_hint = build_interaction_summary_hint(enriched)
    decision_highlights = build_decision_highlights(enriched, scored, blocking)

    return (
        safe_str(enriched.get("dsld_id")),
        safe_str(enriched.get("product_name")),
        safe_str(enriched.get("brandName")),
        safe_str(enriched.get("upcSku")),
        safe_str(enriched.get("imageUrl")),
        image_url_is_pdf(enriched.get("imageUrl")),
        None,  # thumbnail_key — populated at runtime
        detail_blob_sha256,
        json.dumps(interaction_hint, ensure_ascii=False),
        json.dumps(decision_highlights, ensure_ascii=False),
        # Product status
        safe_str(enriched.get("status")),
        disc_date,
        safe_str(enriched.get("form_factor")),
        st_str,
        # Scores
        score_80,
        safe_str(scored.get("display")),
        safe_str(scored.get("display_100")),
        score_100,
        safe_str(scored.get("grade")),
        safe_str(scored.get("verdict")),
        safe_str(scored.get("safety_verdict")),
        safe_float(scored.get("mapped_coverage")),
        # Section scores
        safe_float(safe_dict(ss.get("A_ingredient_quality")).get("score")),
        safe_float(safe_dict(ss.get("A_ingredient_quality")).get("max")),
        safe_float(safe_dict(ss.get("B_safety_purity")).get("score")),
        safe_float(safe_dict(ss.get("B_safety_purity")).get("max")),
        safe_float(safe_dict(ss.get("C_evidence_research")).get("score")),
        safe_float(safe_dict(ss.get("C_evidence_research")).get("max")),
        safe_float(safe_dict(ss.get("D_brand_trust")).get("score")),
        safe_float(safe_dict(ss.get("D_brand_trust")).get("max")),
        # Percentile
        safe_float(cp.get("percentile_rank")) if cp.get("available") else None,
        safe_float(cp.get("top_percent")) if cp.get("available") else None,
        safe_str(cp.get("category_key")),
        safe_str(cp.get("category_label")),
        cp.get("cohort_size", 0) if cp.get("available") else None,
        # Compliance
        safe_bool(comp.get("gluten_free")),
        safe_bool(comp.get("dairy_free")),
        safe_bool(comp.get("soy_free")),
        safe_bool(comp.get("vegan")),
        safe_bool(comp.get("vegetarian")),
        safe_bool(enriched.get("is_certified_organic")),
        0,  # is_non_gmo — gap, not yet normalized
        # Safety outcomes
        safe_bool(has_banned_substance(enriched)),
        safe_bool(has_recalled_ingredient(enriched)),
        safe_bool(safe_list(enriched.get("harmful_additives"))),
        safe_bool(safe_list(enriched.get("allergen_hits"))),
        blocking,
        # Quick info
        safe_bool(safe_dict(enriched.get("probiotic_data")).get("is_probiotic_product")),
        safe_bool(ds.get("contains_sugar")),
        safe_bool(ds.get("contains_sodium")),
        safe_bool(ds.get("diabetes_friendly", False)),
        safe_bool(ds.get("hypertension_friendly", False)),
        safe_bool(enriched.get("is_trusted_manufacturer")),
        safe_bool(enriched.get("named_cert_programs")),
        safe_bool(enriched.get("has_full_disclosure")),
        # JSON columns
        json.dumps(enriched.get("named_cert_programs", []), ensure_ascii=False),
        json.dumps(scored.get("badges", []), ensure_ascii=False),
        json.dumps(top_warnings, ensure_ascii=False),
        json.dumps(scored.get("flags", []), ensure_ascii=False),
        # Metadata
        safe_str(sm.get("scoring_version")),
        safe_str(sm.get("output_schema_version", scored.get("output_schema_version"))),
        safe_str(enriched.get("enrichment_version")),
        safe_str(sm.get("scored_date")),
        str(EXPORT_SCHEMA_VERSION),
        exported_at,
    )


CORE_COLUMN_COUNT = 65  # Must match the tuple above and SCHEMA_SQL


# ─── Reference Data Loader ───

REFERENCE_FILES = {
    "rda_optimal_uls": "data/rda_optimal_uls.json",
    "interaction_rules": "data/ingredient_interaction_rules.json",
    "clinical_risk_taxonomy": "data/clinical_risk_taxonomy.json",
    "user_goals_clusters": "data/user_goals_to_clusters.json",
}


def load_reference_data(script_dir: str) -> List[tuple]:
    """Load reference data files and return rows for reference_data table."""
    rows = []
    now = datetime.now(timezone.utc).isoformat()
    for key, rel_path in REFERENCE_FILES.items():
        fpath = os.path.join(script_dir, rel_path)
        if not os.path.exists(fpath):
            logger.warning("Reference file not found: %s", fpath)
            continue
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
        version = "unknown"
        if isinstance(data, dict):
            meta = data.get("_metadata", {})
            version = meta.get("schema_version", meta.get("last_updated", "unknown"))
        rows.append((key, version, json.dumps(data, ensure_ascii=False), now))
    return rows


# ─── Audit Report ───

def init_audit_counts() -> Dict[str, int]:
    return {
        "total_exported": 0,
        "total_errors": 0,
        "enriched_only": 0,
        "scored_only": 0,
        "has_banned_substance": 0,
        "has_recalled_ingredient": 0,
        "has_harmful_additives": 0,
        "has_allergen_risks": 0,
        "has_watchlist_hit": 0,
        "has_high_risk_hit": 0,
        "export_contract_invalid": 0,
        "verdict_blocked": 0,
        "verdict_unsafe": 0,
        "verdict_caution": 0,
        "verdict_not_scored": 0,
    }


def update_audit_state(
    counts: Dict[str, int],
    products_with_warnings_sample: List[Dict],
    contract_failures_sample: List[Dict],
    products_with_warnings_count: int,
    contract_failures_count: int,
    pid: str,
    enriched: Dict,
    scored: Dict,
) -> tuple[int, int]:
    """Update audit counters incrementally for a matched enriched/scored product."""
    issues = validate_export_contract(enriched, scored)
    if issues:
        counts["export_contract_invalid"] += 1
        contract_failures_count += 1
        if len(contract_failures_sample) < 50:
            contract_failures_sample.append({"dsld_id": pid, "issues": issues[:5]})

    if has_banned_substance(enriched):
        counts["has_banned_substance"] += 1
    if has_recalled_ingredient(enriched):
        counts["has_recalled_ingredient"] += 1
    if safe_list(enriched.get("harmful_additives")):
        counts["has_harmful_additives"] += 1
    if safe_list(enriched.get("allergen_hits")):
        counts["has_allergen_risks"] += 1

    for sub in contaminant_matches(enriched):
        status = normalize_text(sub.get("status"))
        if status == "watchlist":
            counts["has_watchlist_hit"] += 1
            break
    for sub in contaminant_matches(enriched):
        status = normalize_text(sub.get("status"))
        if status == "high_risk":
            counts["has_high_risk_hit"] += 1
            break

    verdict = safe_str(scored.get("verdict")).upper()
    if verdict == "BLOCKED":
        counts["verdict_blocked"] += 1
    elif verdict == "UNSAFE":
        counts["verdict_unsafe"] += 1
    elif verdict == "CAUTION":
        counts["verdict_caution"] += 1
    elif verdict == "NOT_SCORED":
        counts["verdict_not_scored"] += 1

    top = build_top_warnings(enriched)
    if top:
        products_with_warnings_count += 1
        if len(products_with_warnings_sample) < 100:
            products_with_warnings_sample.append({
                "dsld_id": pid,
                "product_name": safe_str(enriched.get("product_name")),
                "brand": safe_str(enriched.get("brandName")),
                "verdict": verdict,
                "warnings": top,
            })

    return products_with_warnings_count, contract_failures_count


def write_audit_report(
    output_dir: str,
    exported_at: str,
    counts: Dict[str, int],
    contract_failures_sample: List[Dict],
    contract_failures_count: int,
    products_with_warnings_count: int,
    products_with_warnings_sample: List[Dict],
) -> Dict:
    """Write the final audit report from incremental state."""
    counts = {
        **counts,
    }

    report = {
        "exported_at": exported_at,
        "pipeline_version": PIPELINE_VERSION,
        "export_schema_version": EXPORT_SCHEMA_VERSION,
        "counts": counts,
        "contract_failures": contract_failures_sample[:50],
        "products_with_warnings_count": products_with_warnings_count,
        "products_with_warnings_sample": products_with_warnings_sample[:100],
    }

    audit_path = os.path.join(output_dir, "export_audit_report.json")
    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    logger.info("Audit report: %s (%d products with warnings, %d contract failures)",
                audit_path, products_with_warnings_count, contract_failures_count)

    return {"audit_path": audit_path, "report": report}


# ─── Main Builder ───

def build_final_db(
    enriched_dirs: List[str],
    scored_dirs: List[str],
    output_dir: str,
    script_dir: str,
):
    os.makedirs(output_dir, exist_ok=True)
    detail_dir = os.path.join(output_dir, "detail_blobs")
    os.makedirs(detail_dir, exist_ok=True)
    for entry in os.scandir(detail_dir):
        if entry.is_file() and entry.name.endswith((".json", ".tmp")):
            os.remove(entry.path)

    # Create SQLite DB
    db_path = os.path.join(output_dir, "pharmaguide_core.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    apply_sqlite_build_pragmas(conn)
    c = conn.cursor()
    c.executescript(SCHEMA_SQL)

    stage_fd, stage_db_path = tempfile.mkstemp(prefix="pg_stage_", suffix=".sqlite3", dir=output_dir)
    os.close(stage_fd)
    stage_conn = sqlite3.connect(stage_db_path)
    try:
        logger.info("Staging enriched products...")
        staged_enriched = stage_products_by_id(stage_conn, "enriched_stage", enriched_dirs)
        logger.info("Staged %d enriched products", staged_enriched)

        logger.info("Staging scored products...")
        staged_scored = stage_products_by_id(stage_conn, "scored_stage", scored_dirs)
        logger.info("Staged %d scored products", staged_scored)

        enriched_unique = stage_conn.execute("SELECT COUNT(*) FROM enriched_stage").fetchone()[0]
        scored_unique = stage_conn.execute("SELECT COUNT(*) FROM scored_stage").fetchone()[0]
        logger.info(
            "Building DB from staged products (%d enriched unique, %d scored unique)",
            enriched_unique,
            scored_unique,
        )

        placeholders = ",".join(["?"] * CORE_COLUMN_COUNT)
        insert_sql = f"INSERT OR REPLACE INTO products_core VALUES ({placeholders})"

        inserted = 0
        errors = 0
        error_details: List[Dict[str, str]] = []
        detail_index: Dict[str, Dict[str, Any]] = {}
        unique_blob_hashes = set()
        since_commit = 0
        exported_at = datetime.now(timezone.utc).isoformat()
        audit_counts = init_audit_counts()
        products_with_warnings_sample: List[Dict] = []
        contract_failures_sample: List[Dict] = []
        products_with_warnings_count = 0
        contract_failures_count = 0
        enriched_only_samples: List[str] = []

        for pid, enriched in iter_staged_products(stage_conn, "enriched_stage"):
            scored = fetch_staged_product(stage_conn, "scored_stage", pid)
            if scored is None:
                audit_counts["enriched_only"] += 1
                if len(enriched_only_samples) < 5:
                    enriched_only_samples.append(pid)
                continue

            mark_staged_product_matched(stage_conn, "scored_stage", pid)
            products_with_warnings_count, contract_failures_count = update_audit_state(
                audit_counts,
                products_with_warnings_sample,
                contract_failures_sample,
                products_with_warnings_count,
                contract_failures_count,
                pid,
                enriched,
                scored,
            )

            blob_path = os.path.join(detail_dir, f"{pid}.json")
            tmp_blob_path = f"{blob_path}.tmp"
            try:
                contract_issues = validate_export_contract(enriched, scored)
                if contract_issues:
                    raise ValueError("; ".join(contract_issues[:10]))
                blob = build_detail_blob(enriched, scored)
                blob_json = json.dumps(blob, ensure_ascii=False, separators=(",", ":"))
                blob_sha256 = hashlib.sha256(blob_json.encode("utf-8")).hexdigest()
                row = build_core_row(enriched, scored, exported_at, detail_blob_sha256=blob_sha256)
                if len(row) != CORE_COLUMN_COUNT:
                    logger.error(
                        "Product %s: row has %d columns, expected %d",
                        pid,
                        len(row),
                        CORE_COLUMN_COUNT,
                    )
                    errors += 1
                    error_details.append({
                        "dsld_id": str(pid),
                        "error": f"row has {len(row)} columns, expected {CORE_COLUMN_COUNT}",
                    })
                    continue
                with open(tmp_blob_path, "w", encoding="utf-8") as f:
                    f.write(blob_json)
                c.execute(insert_sql, row)
                os.replace(tmp_blob_path, blob_path)
                detail_index[str(pid)] = {
                    "blob_sha256": blob_sha256,
                    "storage_path": remote_blob_storage_path(blob_sha256),
                    "blob_version": int(blob.get("blob_version", 1)),
                }
                unique_blob_hashes.add(blob_sha256)

                inserted += 1
                since_commit += 1
                if since_commit >= EXPORT_COMMIT_EVERY:
                    conn.commit()
                    since_commit = 0
            except Exception as e:
                if os.path.exists(tmp_blob_path):
                    os.remove(tmp_blob_path)
                if os.path.exists(blob_path):
                    os.remove(blob_path)
                c.execute("DELETE FROM products_core WHERE dsld_id = ?", (str(pid),))
                logger.error("Product %s failed: %s", pid, e, exc_info=True)
                errors += 1
                error_details.append({
                    "dsld_id": str(pid),
                    "error": str(e),
                })

        scored_only_rows = stage_conn.execute(
            "SELECT dsld_id FROM scored_stage WHERE matched = 0 ORDER BY dsld_id LIMIT 5"
        ).fetchall()
        scored_only_count = stage_conn.execute(
            "SELECT COUNT(*) FROM scored_stage WHERE matched = 0"
        ).fetchone()[0]
        audit_counts["scored_only"] = scored_only_count
        audit_counts["total_exported"] = inserted
        audit_counts["total_errors"] = errors

        if enriched_only_samples:
            logger.warning(
                "%d products in enriched but not scored: %s",
                audit_counts["enriched_only"],
                enriched_only_samples,
            )
        if scored_only_count:
            logger.warning(
                "%d products in scored but not enriched: %s",
                scored_only_count,
                [row[0] for row in scored_only_rows],
            )

        logger.info("Inserted %d products, %d errors", inserted, errors)
    finally:
        stage_conn.close()
        if os.path.exists(stage_db_path):
            os.remove(stage_db_path)

    # Create read-path indexes after bulk insert to avoid incremental index churn.
    c.executescript(CORE_INDEX_SQL)

    # FTS sync
    c.executescript(FTS_SQL)
    c.execute("INSERT INTO products_fts(products_fts) VALUES ('rebuild')")

    # Reference data
    ref_rows = load_reference_data(script_dir)
    for row in ref_rows:
        c.execute("INSERT OR REPLACE INTO reference_data VALUES (?,?,?,?)", row)
    logger.info("Loaded %d reference data entries", len(ref_rows))

    # Local export manifest for on-device metadata. Keep checksum out of SQLite to
    # avoid a self-referential hash problem; the standalone JSON manifest carries
    # the final artifact checksum used for distribution verification.
    manifest_now = datetime.now(timezone.utc)
    db_version = build_db_version(manifest_now)
    local_manifest_rows = [
        ("db_version", db_version),
        ("pipeline_version", PIPELINE_VERSION),
        ("scoring_version", PIPELINE_VERSION),
        ("generated_at", manifest_now.isoformat()),
        ("product_count", str(inserted)),
        ("min_app_version", MIN_APP_VERSION),
        ("schema_version", str(EXPORT_SCHEMA_VERSION)),
    ]
    for key, value in local_manifest_rows:
        c.execute("INSERT OR REPLACE INTO export_manifest VALUES (?,?)", (key, value))
    conn.commit()
    conn.close()

    db_checksum = compute_file_sha256(db_path)

    detail_index_path = os.path.join(output_dir, "detail_index.json")
    with open(detail_index_path, "w", encoding="utf-8") as f:
        json.dump(detail_index, f, indent=2, sort_keys=True)
    detail_index_checksum = compute_file_sha256(detail_index_path)

    # Also write manifest as standalone JSON
    manifest_dict = {
        "db_version": db_version,
        "pipeline_version": PIPELINE_VERSION,
        "scoring_version": PIPELINE_VERSION,
        "generated_at": manifest_now.isoformat(),
        "product_count": inserted,
        "checksum": f"sha256:{db_checksum}",
        "detail_blob_count": inserted,
        "detail_blob_unique_count": len(unique_blob_hashes),
        "detail_index_checksum": f"sha256:{detail_index_checksum}",
        "min_app_version": MIN_APP_VERSION,
        "schema_version": EXPORT_SCHEMA_VERSION,
        "errors": error_details,
    }
    manifest_path = os.path.join(output_dir, "export_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_dict, f, indent=2)

    db_size_mb = os.path.getsize(db_path) / (1024 * 1024)
    logger.info("Final DB: %s (%.2f MB, %d products)", db_path, db_size_mb, inserted)
    logger.info("Detail blobs: %s (%d files)", detail_dir, inserted)
    logger.info("Detail index: %s", detail_index_path)
    logger.info("Manifest: %s", manifest_path)

    # Build audit report
    audit = write_audit_report(
        output_dir=output_dir,
        exported_at=exported_at,
        counts=audit_counts,
        contract_failures_sample=contract_failures_sample,
        contract_failures_count=contract_failures_count,
        products_with_warnings_count=products_with_warnings_count,
        products_with_warnings_sample=products_with_warnings_sample,
    )

    return {
        "db_path": db_path,
        "detail_dir": detail_dir,
        "detail_index_path": detail_index_path,
        "manifest_path": manifest_path,
        "product_count": inserted,
        "error_count": errors,
        "db_size_mb": round(db_size_mb, 2),
        "audit_path": audit["audit_path"],
    }


def main():
    parser = argparse.ArgumentParser(description="Build PharmaGuide final SQLite DB")
    parser.add_argument("--enriched-dir", nargs="+", required=True,
                        help="Directories containing enriched JSON files")
    parser.add_argument("--scored-dir", nargs="+", required=True,
                        help="Directories containing scored JSON files")
    parser.add_argument("--output-dir", default="final_db_output",
                        help="Output directory for DB + blobs + manifest")
    args = parser.parse_args()

    script_dir = str(Path(__file__).parent)
    result = build_final_db(args.enriched_dir, args.scored_dir, args.output_dir, script_dir)

    print(f"\nDone. {result['product_count']} products, {result['error_count']} errors.")
    print(f"DB: {result['db_path']} ({result['db_size_mb']} MB)")


if __name__ == "__main__":
    main()
