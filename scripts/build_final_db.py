#!/usr/bin/env python3
from __future__ import annotations
"""
PharmaGuide Final DB Builder v1.1.0
====================================
Reads enriched + scored pipeline outputs and produces:
  1. pharmaguide_core.db  — SQLite database for the phone
  2. detail_blobs/        — per-product JSON files for Supabase
  3. export_manifest.json — version/checksum metadata

v1.1.0 Changelog (2026-04-07):
  - Added ingredient_fingerprint for stack interaction checking
  - Added social sharing metadata (share_title, share_description, share_highlights)
  - Added search/filter optimization (primary_category, contains_* flags, key_ingredient_tags)
  - Added goal matching preview (goal_matches, goal_match_confidence)
  - Added dosing summary (dosing_summary, servings_per_container)
  - Added allergen summary string
  - Schema now has 87 columns (up from 65)

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

Follows: FINAL_EXPORT_SCHEMA_V1.md (v1.1.0)
"""

import argparse
import hashlib
import json
import logging
import math as _math
import os
import re
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from audit_evidence_utils import (
    derive_non_gmo_audit,
    derive_omega3_audit,
    derive_proprietary_blend_audit,
)
from inactive_ingredient_resolver import InactiveIngredientResolver
from supplement_type_utils import infer_supplement_type

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

EXPORT_SCHEMA_VERSION = "1.6.0"  # v1.6.0 adds profile_gate passthrough on warnings (interaction + drug_interaction); v1.5.0 added canonical form/dose/severity contract on active+inactive rows
PIPELINE_VERSION = "3.4.0"
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


def normalize_upc(value: Any) -> str:
    """Normalize a UPC/EAN barcode to digits-only.

    Returns empty string for missing, garbage, or invalid-length barcodes.
    Accepts 12-digit UPC-A and 13-digit EAN-13 only.
    """
    if value is None:
        return ""
    import re
    digits = re.sub(r"[^0-9]", "", str(value))
    if len(digits) not in (12, 13):
        return ""
    return digits


def safe_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def safe_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _first_form_name(forms: Any) -> str:
    """Return the first DSLD-declared form name, e.g. 'Palmitate'.

    The cleaner emits forms[] from DSLD's parsed forms array or from
    name-extraction. When it succeeds, this is the user-visible label form.
    When it fails (cleaner regex misses inline forms like
    'Vitamin A Palmitate'), the canonical contract falls back to the
    enricher's matched_form via _compute_form_contract.
    """
    if forms and isinstance(forms, list) and isinstance(forms[0], dict):
        return safe_str(forms[0].get("name"))
    return ""


# Placeholder tokens IQM uses when no specific form was matched. A
# matched_form equal to any of these (or carrying an "(unspecified)"
# parenthetical) means the enricher fell back to the parent canonical
# and does NOT carry a real label form.
_FORM_PLACEHOLDER_TOKENS = {"", "standard", "unspecified", "default", "generic"}
_FORM_PLACEHOLDER_PARENS = ("(unspecified)", "(unmapped)", "(generic)")

# Common parent-nutrient prefixes stripped from matched_form when
# prettifying for display. e.g. 'vitamin a palmitate' -> 'Palmitate'.
_FORM_PARENT_PREFIXES = (
    "vitamin a ", "vitamin d ", "vitamin e ", "vitamin k ",
    "vitamin b1 ", "vitamin b2 ", "vitamin b3 ", "vitamin b5 ",
    "vitamin b6 ", "vitamin b7 ", "vitamin b9 ", "vitamin b12 ",
    "vitamin c ",
)


def _is_placeholder_form(matched_form: str) -> bool:
    if not matched_form:
        return True
    s = matched_form.strip().lower()
    if s in _FORM_PLACEHOLDER_TOKENS:
        return True
    return any(tag in s for tag in _FORM_PLACEHOLDER_PARENS)


def _prettify_matched_form(matched_form: str) -> str:
    """Convert IQM canonical form ('retinyl palmitate') to display label
    ('Retinyl Palmitate'). Strips parent-nutrient prefix when the form
    string redundantly carries it (e.g. 'vitamin a palmitate' -> 'Palmitate').
    Preserves alphanumeric tokens like D3/K2/MK-7/B12 in upper case.
    """
    s = safe_str(matched_form).strip()
    if not s:
        return ""
    low = s.lower()
    for prefix in _FORM_PARENT_PREFIXES:
        if low.startswith(prefix):
            s = s[len(prefix):]
            break
    return " ".join(_prettify_token(tok) for tok in s.split())


def _prettify_token(tok: str) -> str:
    """Title-case one whitespace-separated token. Hyphen segments
    handled independently so 'menaquinone-7' becomes 'Menaquinone-7'
    while short identifiers (D3, K2, MK-7, B12) stay upper.
    """
    if "-" in tok:
        return "-".join(_prettify_token(p) for p in tok.split("-"))
    if not tok:
        return tok
    if tok.isdigit():
        return tok
    alpha = "".join(c for c in tok if c.isalpha())
    has_digit = any(c.isdigit() for c in tok)
    # Short identifier (≤3 alpha chars): D3, K2, MK, B12 -> upper.
    if len(alpha) <= 3 and (has_digit or len(alpha) <= 2):
        return tok.upper()
    return tok.capitalize()


def _compute_form_contract(
    ingredient: Dict[str, Any], match: Dict[str, Any]
) -> Dict[str, Any]:
    """Canonical form-disclosure contract for one active ingredient.

    Three fields, always set together so Flutter never has to decide
    whether a form is known or where to read it:

      display_form_label  user-visible form, or None when truly unknown
      form_status         'known' | 'unknown'
      form_match_status   'mapped' | 'unmapped' | 'n/a' (n/a when unknown)

    Resolution order:
      1. Cleaner forms[0].name present     -> known
      2. Enricher matched_form non-placeholder -> known (bridge for cleaner gaps)
      3. Otherwise                          -> unknown
    """
    label_form = _first_form_name(ingredient.get("forms"))
    matched = safe_str(match.get("matched_form") or ingredient.get("matched_form"))
    matched_is_real = not _is_placeholder_form(matched)

    if label_form:
        return {
            "display_form_label": label_form,
            "form_status": "known",
            "form_match_status": "mapped" if matched_is_real else "unmapped",
        }
    if matched_is_real:
        return {
            "display_form_label": _prettify_matched_form(matched),
            "form_status": "known",
            "form_match_status": "mapped",
        }
    return {
        "display_form_label": None,
        "form_status": "unknown",
        "form_match_status": "n/a",
    }


# NOTE: the legacy `_INACTIVE_ROLE_LABELS` table, `_INACTIVE_ROLE_SENTINELS`,
# and the helpers `_compute_inactive_role_label`, `_compute_inactive_severity_status`,
# `_compute_is_safety_concern` were removed 2026-05-12 after the unified
# `InactiveIngredientResolver` (`scripts/inactive_ingredient_resolver.py`)
# and `_resolve_active_safety_contract` (below) became the single source of
# truth for inactive AND active safety/role classification. The role-label
# table now lives only in inactive_ingredient_resolver._ROLE_LABEL_TABLE.


# Banned/recalled status values that escalate an active ingredient to
# is_safety_concern=True. 'watchlist' is intentionally excluded — it
# signals "track but do not block" and surfaces as informational only.
_ACTIVE_BANNED_RECALLED_SAFETY_STATUSES = frozenset({"banned", "high_risk", "recalled"})


def _resolve_active_safety_contract(
    harmful_hit: Optional[Dict],
    harmful_ref: Dict,
    ingredient_hits: List[Dict],
    *,
    name_terms: Optional[List[str]] = None,
    banned_recalled_index: Optional[Dict[str, Dict]] = None,
) -> Dict[str, Any]:
    """Unified safety contract for one active ingredient. Mirrors the
    inactive resolver's output shape (is_safety_concern / is_banned /
    safety_reason / matched_source / matched_rule_id) so Flutter reads
    the same fields on both active and inactive rows.

    Resolution precedence (highest authority wins):
      1. ingredient_hits with status='banned'    → is_banned=True, is_safety_concern=True, matched_source='banned_recalled'
      2. ingredient_hits with status in {high_risk, recalled}
         → is_safety_concern=True, matched_source='banned_recalled'
      3. Direct banned_recalled alias lookup on the ingredient name +
         raw_source_text + standard_name (FALLBACK — covers alias
         variants that the enricher's contaminant_lookup missed, e.g.
         "Garcinia Cambogia fruit extract" → alias of `garcinia cambogia`
         which the enricher's name-match didn't catch).
      4. harmful_hit with severity in {moderate, high, critical}
         → is_safety_concern=True, matched_source='harmful_additives'
      5. ingredient_hits with status='watchlist'
         → is_safety_concern=False (informational only), matched_source='banned_recalled'
      6. None of the above → is_safety_concern=False, all provenance fields None.

    Architectural note: this exists because the previous active-path code
    computed is_safety_concern from harmful_additives ONLY, ignoring
    banned_recalled. Yohimbe (high_risk × 82 products), Cannabidiol
    (banned × 30), Garcinia Cambogia (high_risk × 11), Red Yeast Rice
    (banned × 9), Cascara Sagrada, Bitter Orange, etc. all shipped with
    is_safety_concern=False on the per-ingredient blob entry — Flutter's
    Review-Before-Use gate silently missed them. The contaminant hits
    (sourced from banned_recalled at enrich time) WERE in
    `safety_hits[]`, just not consulted by the flag derivation. The
    direct banned_recalled_index fallback (step 3) closes the second
    gap: alias variants the enricher's name-match missed entirely.
    """
    # 1. + 2. — banned_recalled hits via enricher's contaminant_lookup
    banned_hit = None
    elevated_hit = None
    watchlist_hit = None
    for hit in ingredient_hits or []:
        if not isinstance(hit, dict):
            continue
        s = normalize_text(hit.get("status"))
        if s == "banned":
            banned_hit = hit
            break  # banned is the strongest signal; stop
        if s in _ACTIVE_BANNED_RECALLED_SAFETY_STATUSES and elevated_hit is None:
            elevated_hit = hit
        elif s == "watchlist" and watchlist_hit is None:
            watchlist_hit = hit

    # 3. — direct banned_recalled alias lookup fallback. Required because
    # the enricher's contaminant_data is built with a stricter name match
    # that misses alias variants (e.g. "Garcinia Cambogia fruit extract"
    # — `garcinia cambogia` is an alias of RISK_GARCINIA_CAMBOGIA but the
    # enricher didn't synthesize a contaminant_hit for the extract form).
    # We replicate the inactive resolver's strict standard_name+aliases
    # lookup so the active path has the same alias coverage.
    if banned_hit is None and elevated_hit is None and banned_recalled_index is not None:
        for term in (name_terms or []):
            entry = banned_recalled_index.get(term)
            if not entry:
                continue
            s = (entry.get("status") or "").strip().lower()
            if s == "banned":
                banned_hit = entry
                break
            if s in _ACTIVE_BANNED_RECALLED_SAFETY_STATUSES and elevated_hit is None:
                elevated_hit = entry
            elif s == "watchlist" and watchlist_hit is None:
                watchlist_hit = entry

    if banned_hit is not None:
        return {
            "is_safety_concern": True,
            "is_banned": True,
            "safety_reason": safe_str(
                banned_hit.get("reason")
                or banned_hit.get("safety_warning_one_liner")
                or banned_hit.get("safety_warning")
            ) or None,
            "matched_source": "banned_recalled",
            "matched_rule_id": safe_str(banned_hit.get("id") or banned_hit.get("rule_id")) or None,
        }
    if elevated_hit is not None:
        return {
            "is_safety_concern": True,
            "is_banned": False,
            "safety_reason": safe_str(
                elevated_hit.get("reason")
                or elevated_hit.get("safety_warning_one_liner")
                or elevated_hit.get("safety_warning")
            ) or None,
            "matched_source": "banned_recalled",
            "matched_rule_id": safe_str(elevated_hit.get("id") or elevated_hit.get("rule_id")) or None,
        }
    # 3. — harmful_additives moderate+
    if harmful_hit is not None:
        sev = (harmful_hit.get("severity_level") or "").strip().lower()
        if sev in ("moderate", "high", "critical"):
            reason = safe_str(
                harmful_ref.get("safety_summary_one_liner")
                or harmful_ref.get("safety_summary")
                or harmful_hit.get("safety_summary_one_liner")
                or harmful_hit.get("mechanism_of_harm")
            )
            return {
                "is_safety_concern": True,
                "is_banned": False,
                "safety_reason": reason or None,
                "matched_source": "harmful_additives",
                "matched_rule_id": safe_str(harmful_hit.get("id") or harmful_ref.get("id")) or None,
            }
    # 4. — watchlist informational only
    if watchlist_hit is not None:
        return {
            "is_safety_concern": False,
            "is_banned": False,
            "safety_reason": safe_str(
                watchlist_hit.get("reason")
                or watchlist_hit.get("safety_warning_one_liner")
            ) or None,
            "matched_source": "banned_recalled",
            "matched_rule_id": safe_str(watchlist_hit.get("id") or watchlist_hit.get("rule_id")) or None,
        }
    # 5. — nothing
    return {
        "is_safety_concern": False,
        "is_banned": False,
        "safety_reason": None,
        "matched_source": None,
        "matched_rule_id": None,
    }


def normalize_text(value: Any) -> str:
    """Normalize free text for tolerant cross-structure matching."""
    return safe_str(value).lower()


def build_supplement_type_audit(enriched: Dict, scored: Optional[Dict] = None) -> Dict[str, Any]:
    supplement_type = enriched.get("supplement_type")
    enriched_type = ""
    if isinstance(supplement_type, dict):
        enriched_type = safe_str(supplement_type.get("type"))
    elif supplement_type is not None:
        enriched_type = safe_str(supplement_type)
    inferred = infer_supplement_type(enriched)
    return {
        "enriched_type": enriched_type,
        "scored_type": safe_str((scored or {}).get("supp_type")),
        "inferred_type": safe_str(inferred.get("type")),
        "export_type": resolve_export_supplement_type(enriched, scored),
        "active_count": inferred.get("active_count"),
        "source": safe_str(inferred.get("source")),
        "category_breakdown": safe_dict(inferred.get("category_breakdown")),
        "probiotic_signal": safe_bool(inferred.get("probiotic_signal")),
    }


def resolve_export_supplement_type(enriched: Dict, scored: Optional[Dict] = None) -> str:
    enriched_type = ""
    supplement_type = enriched.get("supplement_type")
    if isinstance(supplement_type, dict):
        enriched_type = normalize_text(supplement_type.get("type"))
    elif supplement_type is not None:
        enriched_type = normalize_text(supplement_type)

    scored_type = normalize_text((scored or {}).get("supp_type"))
    inferred_type = normalize_text(infer_supplement_type(enriched).get("type"))

    if enriched_type and enriched_type not in {"unknown"}:
        if enriched_type == "specialty" and scored_type not in {"", "unknown", "specialty"}:
            return scored_type
        if enriched_type == "specialty" and inferred_type not in {"", "unknown", "specialty"}:
            return inferred_type
        return enriched_type

    if scored_type and scored_type != "unknown":
        return scored_type
    if inferred_type and inferred_type != "unknown":
        return inferred_type
    return enriched_type or scored_type or inferred_type or "unknown"


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


def collect_match_terms(*values: Any) -> list[str]:
    """Collect normalized match terms in stable first-seen order."""
    terms: list[str] = []
    seen: set[str] = set()
    for value in values:
        term = normalize_text(value)
        if not term or term in seen:
            continue
        seen.add(term)
        terms.append(term)
    return terms


def iter_match_terms(*values: Any) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        term = normalize_text(value)
        if not term or term in seen:
            continue
        seen.add(term)
        ordered.append(term)
    return ordered


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
    """Validate the minimum upstream contract needed for final DB export.

    Includes the Batch 3 data-integrity gate:

    Products SHIP (verdict appears in app, with reason) for verdicts:
        SAFE, CAUTION, POOR, BLOCKED, UNSAFE, NUTRITION_ONLY

    Products are QUARANTINED (excluded_by_gate; never reach Flutter) when:
      - verdict == NOT_SCORED  (mapping/dosage gate failure upstream)
      - score_100_equivalent is None on a non-BLOCKED/UNSAFE verdict
      - any breakdown.{A,B,C,D}.score is missing or non-numeric on
        non-BLOCKED/UNSAFE verdicts

    BLOCKED/UNSAFE products may legitimately have null scores — the recall
    or ban reason is the data the user needs.

    Gate failure messages contain the phrase 'review_queue' so the existing
    `_classify_export_error` taxonomy routes them into the
    `excluded_by_gate` bucket (non-blocking quarantine that doesn't fail
    the Supabase sync gate).
    """
    import math

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

    # ── Batch 3 data integrity gate ────────────────────────────────────
    verdict = safe_str(scored.get("verdict")).upper()
    score_optional = verdict in {"BLOCKED", "UNSAFE"}

    if verdict == "NOT_SCORED":
        issues.append(
            "review_queue: NOT_SCORED verdict — mapping/dosage gate "
            "failed upstream; product cannot ship without a coherent "
            "score (Batch 3 data integrity gate)."
        )
    elif not score_optional:
        s100 = scored.get("score_100_equivalent")
        if s100 is None:
            issues.append(
                f"review_queue: verdict={verdict} requires score_100_equivalent "
                "but field is null (Batch 3 data integrity gate)."
            )
        else:
            try:
                f = float(s100)
                if not math.isfinite(f):
                    issues.append(
                        f"review_queue: score_100_equivalent={s100!r} is not "
                        "finite (Batch 3 data integrity gate)."
                    )
            except (TypeError, ValueError):
                issues.append(
                    f"review_queue: score_100_equivalent={s100!r} is not "
                    "a number (Batch 3 data integrity gate)."
                )

        # Section scores: the public-facing score breakdown that
        # build_core_row writes into products_core. Each must carry a
        # finite numeric score.
        ss = safe_dict(scored.get("section_scores"))
        section_keys = (
            "A_ingredient_quality",
            "B_safety_purity",
            "C_evidence_research",
            "D_brand_trust",
        )
        for sk in section_keys:
            sec_obj = ss.get(sk)
            if not isinstance(sec_obj, dict):
                issues.append(
                    f"review_queue: section_scores.{sk} missing or not an "
                    "object (Batch 3 data integrity gate)."
                )
                continue
            sec_score = sec_obj.get("score")
            if sec_score is None:
                issues.append(
                    f"review_queue: section_scores.{sk}.score is null "
                    "(Batch 3 data integrity gate)."
                )
                continue
            try:
                f = float(sec_score)
                if not math.isfinite(f):
                    issues.append(
                        f"review_queue: section_scores.{sk}.score="
                        f"{sec_score!r} is not finite "
                        "(Batch 3 data integrity gate)."
                    )
            except (TypeError, ValueError):
                issues.append(
                    f"review_queue: section_scores.{sk}.score="
                    f"{sec_score!r} is not a number "
                    "(Batch 3 data integrity gate)."
                )

    return issues


HARMFUL_REFERENCE_INDEX: Optional[Dict[str, Dict]] = None
IQM_REFERENCE_INDEX: Optional[Dict[str, Dict]] = None
_SHARED_INACTIVE_RESOLVER: Optional[InactiveIngredientResolver] = None


def _get_shared_inactive_resolver() -> InactiveIngredientResolver:
    """Lazily build the inactive-ingredient resolver once per process.
    Indices for banned_recalled + harmful_additives + other_ingredients
    are built on first call and reused across every product in the
    build run. O(total_aliases) on init, O(1) lookups thereafter.
    """
    global _SHARED_INACTIVE_RESOLVER
    if _SHARED_INACTIVE_RESOLVER is None:
        _SHARED_INACTIVE_RESOLVER = InactiveIngredientResolver()
    return _SHARED_INACTIVE_RESOLVER


_ACTIVE_BANNED_RECALLED_INDEX: Optional[Dict[str, Dict]] = None


def _get_active_banned_recalled_index() -> Dict[str, Dict]:
    """Lazily build a normalized alias → banned_recalled-entry index for
    the active-ingredient path. Shares the inactive resolver's
    filter-and-normalize rules so active and inactive paths see the
    same set of banned/high_risk/recalled/watchlist entries.

    Reuses the inactive resolver's already-loaded entries (skipping
    match_mode in {disabled, historical}) so we don't re-parse the
    file or implement a second normalization.
    """
    global _ACTIVE_BANNED_RECALLED_INDEX
    if _ACTIVE_BANNED_RECALLED_INDEX is None:
        resolver = _get_shared_inactive_resolver()
        idx: Dict[str, Dict] = {}
        # Import here to avoid a circular import at module load.
        from inactive_ingredient_resolver import _normalize as _ir_normalize
        for entry in resolver.iter_banned_recalled_entries_for_audit():
            for n in [entry.get("standard_name")] + (entry.get("aliases") or []):
                if isinstance(n, str):
                    t = _ir_normalize(n)
                    if t and t not in idx:
                        idx[t] = entry
        _ACTIVE_BANNED_RECALLED_INDEX = idx
    return _ACTIVE_BANNED_RECALLED_INDEX


def _active_banned_recall_terms(*values: str) -> List[str]:
    """Normalize a small list of name candidates for direct alias lookup
    against the active banned_recalled index. Uses the same normalizer
    the inactive resolver uses, so a name that resolves on the inactive
    path resolves identically here."""
    from inactive_ingredient_resolver import _normalize as _ir_normalize
    seen: set = set()
    out: List[str] = []
    for v in values:
        n = _ir_normalize(v)
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


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
            standard_term = normalize_text(entry.get("standard_name"))
            if standard_term:
                index[standard_term] = entry
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for alias in safe_list(entry.get("aliases")):
                alias_term = normalize_text(alias)
                if alias_term and alias_term not in index:
                    index[alias_term] = entry
    except Exception as exc:
        logger.warning("Failed to load harmful_additives reference data: %s", exc)
    HARMFUL_REFERENCE_INDEX = index
    return HARMFUL_REFERENCE_INDEX


def resolve_harmful_reference(hit: Optional[Dict]) -> Dict:
    if not isinstance(hit, dict):
        return {}
    index = load_harmful_reference_index()
    for term in iter_match_terms(
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
            standard_term = normalize_text(entry.get("standard_name"))
            if standard_term:
                index[standard_term] = entry
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for alias in safe_list(entry.get("aliases")):
                alias_term = normalize_text(alias)
                if alias_term and alias_term not in index:
                    index[alias_term] = entry
    except Exception as exc:
        logger.warning("Failed to load other_ingredients reference data: %s", exc)
    OTHER_INGREDIENTS_INDEX = index
    return OTHER_INGREDIENTS_INDEX


def resolve_other_ingredient_reference(name: str, standard_name: str = "") -> Dict:
    index = load_other_ingredients_index()
    for term in iter_match_terms(standard_name, name):
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

    -- ====================================================================
    -- EXPORT SCHEMA V1.1.0 ADDITIONS (2026-04-07)
    -- Enhancement 1: Stack Interaction Checking
    -- ====================================================================
    ingredient_fingerprint        TEXT,  -- JSON: compact ingredient dose map
    key_nutrients_summary         TEXT,  -- JSON: top 5-10 nutrients with doses
    contains_stimulants           INTEGER DEFAULT 0,
    contains_sedatives            INTEGER DEFAULT 0,
    contains_blood_thinners       INTEGER DEFAULT 0,

    -- ====================================================================
    -- Enhancement 2: Social Sharing Metadata
    -- ====================================================================
    share_title                   TEXT,  -- Pre-formatted share title
    share_description             TEXT,  -- Pre-formatted 2-3 sentence summary
    share_highlights              TEXT,  -- JSON array: 3-4 key positive attributes
    share_og_image_url            TEXT,  -- Open Graph optimized image URL

    -- ====================================================================
    -- Enhancement 3: Search & Filter Optimization
    -- ====================================================================
    primary_category              TEXT,  -- omega-3, probiotic, multivitamin, etc.
    secondary_categories          TEXT,  -- JSON array: anti-inflammatory, heart-health
    contains_omega3               INTEGER DEFAULT 0,
    contains_probiotics           INTEGER DEFAULT 0,
    contains_collagen             INTEGER DEFAULT 0,
    contains_adaptogens           INTEGER DEFAULT 0,
    contains_nootropics           INTEGER DEFAULT 0,
    key_ingredient_tags           TEXT,  -- JSON array: top 5 priority ingredients

    -- ====================================================================
    -- Enhancement 4: Goal Matching Preview
    -- ====================================================================
    goal_matches                  TEXT,  -- JSON array: matched goal IDs
    goal_match_confidence         REAL,  -- 0.0-1.0: average cluster weight

    -- ====================================================================
    -- Enhancement 5: Dosing Guidance
    -- ====================================================================
    dosing_summary                TEXT,  -- "Take 2 capsules daily"
    servings_per_container        INTEGER,  -- 60
    net_contents_quantity         REAL,     -- 90 (from netContents[0].quantity)
    net_contents_unit             TEXT,     -- "Capsule(s)", "mL", "Gram(s)", etc.

    -- ====================================================================
    -- Enhancement 6: Allergen Summary
    -- ====================================================================
    allergen_summary              TEXT,  -- "Contains: Soy, Tree Nuts"

    -- ====================================================================
    -- EXPORT SCHEMA V1.3.2 ADDITIONS (2026-04-10)
    -- calories_per_serving: hybrid approach — highest-value nutrition filter
    -- ====================================================================
    calories_per_serving          REAL,  -- kcal per serving (from nutritionalInfo.calories.amount)

    -- ====================================================================
    -- EXPORT SCHEMA V1.4.0 ADDITIONS (2026-04-15)
    -- Product label thumbnail (WebP from DSLD PDF, fallback for OFF images)
    -- ====================================================================
    image_thumbnail_url           TEXT,  -- Supabase Storage path: "product-images/{dsld_id}.webp"

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
-- New indexes for v1.1.0 enhancements
CREATE INDEX IF NOT EXISTS idx_core_primary_category ON products_core(primary_category);
CREATE INDEX IF NOT EXISTS idx_core_contains_omega3 ON products_core(contains_omega3) WHERE contains_omega3 = 1;
CREATE INDEX IF NOT EXISTS idx_core_contains_probiotics ON products_core(contains_probiotics) WHERE contains_probiotics = 1;
CREATE INDEX IF NOT EXISTS idx_core_contains_collagen ON products_core(contains_collagen) WHERE contains_collagen = 1;
CREATE INDEX IF NOT EXISTS idx_core_contains_adaptogens ON products_core(contains_adaptogens) WHERE contains_adaptogens = 1;
CREATE INDEX IF NOT EXISTS idx_core_contains_nootropics ON products_core(contains_nootropics) WHERE contains_nootropics = 1;
"""

FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS products_fts USING fts5(
    product_name, brand_name,
    content='products_core', content_rowid='rowid',
    tokenize='porter unicode61'
);
"""


def dedup_by_upc(
    conn,
    detail_index: Dict[str, Any],
    detail_blobs_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Remove duplicate products that share the same UPC barcode.

    DSLD registers the same physical product multiple times across years
    or formulation revisions, each with a distinct dsld_id but the same UPC.
    This confuses search results (users see "5-MTHF 1 mg" seven times).

    Strategy:
      1. GROUP BY normalised UPC (spaces stripped).
      2. Keep the **best** row per group: active > discontinued, then
         highest score_quality_80, then newest dsld_id (lexicographic).
      3. DELETE the losers from products_core, remove them from the
         detail_index dict, and unlink the corresponding blob file from
         detail_blobs_dir if provided — so the downstream sync never sees
         orphan blobs that no product references. (Pre-2026-04-18 builds
         skipped the file unlink, leaving thousands of unreferenced blobs
         on disk that the sync gate then rejected.)

    Returns a summary dict for the audit report.
    """
    c = conn.cursor()

    # Find all UPC groups with more than one product.
    # NULL / empty UPCs are excluded — they have nothing to dedup on.
    # UPCs are now stored as digits-only (normalize_upc), but keep the
    # REPLACE for backward compat with any pre-normalized rows.
    rows = c.execute("""
        SELECT REPLACE(upc_sku, ' ', '') AS upc_norm,
               GROUP_CONCAT(dsld_id, '|') AS ids,
               COUNT(*) AS cnt
          FROM products_core
         WHERE upc_sku IS NOT NULL
           AND upc_sku != ''
         GROUP BY upc_norm
        HAVING cnt > 1
         ORDER BY upc_norm
    """).fetchall()

    total_removed = 0
    groups_deduped = 0
    removed_ids = []
    orphan_files_removed = 0

    for upc_norm, id_csv, cnt in rows:
        dsld_ids = id_csv.split("|")

        # Fetch each candidate's ranking signals.
        candidates = []
        for did in dsld_ids:
            row = c.execute(
                "SELECT dsld_id, product_status, "
                "       COALESCE(score_quality_80, 0) "
                "  FROM products_core WHERE dsld_id = ?",
                (did,),
            ).fetchone()
            if row:
                candidates.append(row)

        if len(candidates) < 2:
            continue

        # Sort: active first, highest score, newest dsld_id.
        candidates.sort(
            key=lambda r: (
                1 if r[1] == "active" else 0,  # active wins
                r[2],                           # highest score
                r[0],                           # newest dsld_id (lexicographic)
            ),
            reverse=True,
        )

        winner = candidates[0][0]
        losers = [r[0] for r in candidates[1:]]

        for loser_id in losers:
            c.execute(
                "DELETE FROM products_core WHERE dsld_id = ?",
                (loser_id,),
            )
            # Remove from detail_index so the sync doesn't upload orphan blobs
            detail_index.pop(str(loser_id), None)
            # Remove the physical blob file from disk so the sync gate's
            # file-count check (len(blobs) == product_count) holds. Without
            # this, the enrichment stage's 7k+ blob files stay on disk even
            # though only ~4k survive the dedup, and sync aborts with
            # "Build output blob mismatch."
            if detail_blobs_dir is not None:
                blob_path = detail_blobs_dir / f"{loser_id}.json"
                if blob_path.exists():
                    blob_path.unlink()
                    orphan_files_removed += 1
            removed_ids.append(loser_id)

        total_removed += len(losers)
        groups_deduped += 1

    if total_removed:
        conn.commit()

    return {
        "upc_groups_deduped": groups_deduped,
        "duplicates_removed": total_removed,
        "orphan_blob_files_removed": orphan_files_removed,
        "removed_ids_sample": removed_ids[:20],
    }


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


# Sprint E1.1.1 — deny-list of tokens that must never appear in the
# user-facing ``decision_highlights.positive`` bucket. These are danger-
# valence phrases that belong under the new ``danger`` bucket (rendered
# red in Flutter) rather than under a green thumbs-up. The validator
# below enforces this invariant at build time.
_DECISION_HIGHLIGHTS_DENY_LIST_RE = re.compile(
    r"(not lawful|banned|talk to your doctor|arsenic|trace metals|"
    r"undisclosed|high glycemic|contraindicated)",
    re.IGNORECASE,
)


def build_decision_highlights(
    enriched: Dict, scored: Dict, blocking_reason: Optional[str]
) -> Dict[str, Any]:
    """Build concise hero highlights so Flutter doesn't need to improvise them.

    Four buckets (Sprint E1.1.1):

      * ``positive`` (str)      — green hero string, benign signal only.
      * ``caution`` (str)       — yellow caution, quality-level signals.
      * ``danger`` (list[str])  — red banner, safety blocking-reason
        strings. Rendered by Flutter with red tint.
      * ``trust`` (str)         — trust/certification signal.

    Blocking-reason strings (banned / recalled / high-risk) route into
    ``danger`` exclusively; ``caution`` then flows unchanged for the
    non-blocking signals (additives, allergens, verdict).
    """
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

    danger: List[str] = []
    if blocking_reason == "banned_substance":
        danger.append("Contains a banned substance match.")
    elif blocking_reason == "recalled_ingredient":
        danger.append("Contains a recalled ingredient match.")
    elif blocking_reason == "high_risk_ingredient":
        danger.append("Contains an ingredient flagged as high risk.")

    if safe_list(enriched.get("harmful_additives")):
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
        "danger": danger,
        "trust": trust,
    }


# Sprint E1.1.2 — critical-mode warnings must be profile-agnostic.
# A warning with ``display_mode_default == "critical"`` is rendered to
# every user regardless of profile. Copy referencing a specific condition
# (e.g. "during pregnancy") shown to a profile-less user is medically
# wrong. Profile-scoped warnings must default to ``suppress`` and
# rely on Flutter's on-device promotion when profile matches.
_WARNING_CONDITION_SPECIFIC_RE = re.compile(
    r"(during pregnancy|for liver disease|breastfeeding|kidney disease|"
    r"heart disease|while nursing)",
    re.IGNORECASE,
)

_WARNING_AUTHORED_COPY_FIELDS = (
    "alert_headline",
    "alert_body",
    "safety_warning",
    "safety_warning_one_liner",
    "safety_summary",
    "safety_summary_one_liner",
    "detail",
    "title",
    "informational_note",
)


# Sprint E1.1.4 — banned-substance preflight copy propagation.
# Flutter Sprint 27.7's stack-add preflight sheet renders a red CRITICAL
# banner when has_banned_substance=1, populated from Dr Pham's authored
# safety_warning_one_liner (≤80 chars) + safety_warning (≤200 chars)
# fields. The enricher (D5.4) already propagates these through to
# warning emission; E1.1.4 aggregates them into a top-level
# banned_substance_detail key so Flutter can read directly without
# iterating warnings[].
_BANNED_PREFLIGHT_ONE_LINER_MAX = 80
_BANNED_PREFLIGHT_BODY_MAX = 200


def build_banned_substance_detail(
    enriched: Dict[str, Any], warnings_list: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """Aggregate the first banned-substance warning's Dr Pham authored copy
    into a top-level detail-blob key. Returns ``None`` when the product
    does not carry a banned-substance hit (most of the catalog).
    """
    if not has_banned_substance(enriched):
        return None
    for w in warnings_list or []:
        if not isinstance(w, dict) or w.get("type") != "banned_substance":
            continue
        one = w.get("safety_warning_one_liner")
        body = w.get("safety_warning")
        if (
            isinstance(one, str) and one.strip()
            and isinstance(body, str) and body.strip()
        ):
            title = safe_str(w.get("title"))
            substance = title.split(":", 1)[-1].strip() if ":" in title else title or None
            return {
                "safety_warning_one_liner": one.strip(),
                "safety_warning": body.strip(),
                "substance_name": substance,
            }
    return None


# Sprint E1.2.2.a — display_label (Brand + Base + Form).
# Branded tokens mirror the set in label_fidelity_scope_report.py /
# test_label_fidelity_contract.py. Keep these in sync across the 3
# call sites manually — centralizing at import time adds churn for
# each sub-task without improving guarantees.
_BRANDED_TOKENS = (
    "KSM-66", "Meriva", "BioPerine", "Bioperine", "Ferrochel", "Sensoril",
    "Phytosome", "Silybin Phytosome", "Pycnogenol", "Setria", "Albion",
    "TRAACS", "Chromax", "Curcumin C3", "Longvida", "Wellmune", "CurcuWIN",
    "LJ100", "enXtra", "AstraGin", "Venetron",
    # Capsimax (capsicum extract), Carnipure (l-carnitine), Sunfiber (PHGG),
    # Lutemax/Lutemax 2020 (lutein/zeaxanthin), Suntheanine (l-theanine),
    # Cognizin (citicoline) — added 2026-05-12 after the Capsimax canary
    # surfaced display_label fidelity loss (DSLD 1181 dropped "Capsicum
    # Fruit" from the rendered string).
    "Capsimax", "Carnipure", "Sunfiber", "Lutemax", "Lutemax 2020",
    "Suntheanine", "Cognizin",
)

# Generic form words that survive the cleaner's name_extraction pass when the
# DSLD label form is too thin (e.g. "Capsimax(TM) Capsicum Fruit Extract" →
# forms[0].name='extract', source='name_extraction'). When all three signals
# line up (name_extraction source AND a generic form token AND a richer
# raw_source_text), use the cleaned raw text as the display base instead.
_GENERIC_FORM_TOKENS = frozenset({
    "extract", "powder", "complex", "blend", "concentrate", "fraction",
    "phytosome", "liposome", "tincture", "oil", "resin", "isolate",
})

_TRADEMARK_PAREN_RE = re.compile(
    r"\s*\(\s*(?:TM|R|C|SM)\s*\)", re.IGNORECASE
)
_TRADEMARK_SYMBOL_RE = re.compile(r"[™®©℠]")  # ™ ® © ℠
_WHITESPACE_RE = re.compile(r"\s+")


def _strip_trademark_markers(text: str) -> str:
    """Remove (TM), (R), (C), ™, ®, © from a label string and normalize
    whitespace. Trademark markers don't render well in Flutter and don't
    add semantic value — the brand identity comes from the token itself.
    """
    if not text:
        return ""
    text = _TRADEMARK_PAREN_RE.sub("", text)
    text = _TRADEMARK_SYMBOL_RE.sub("", text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def _compute_display_label(ingredient: Dict[str, Any]) -> str:
    """Produce the user-facing ingredient label string for Flutter.

    Format: ``Brand Base Form``. Preserves branded tokens (KSM-66,
    BioPerine, Ferrochel, Capsimax) and the DSLD-authored descriptive
    form phrase (typically ``Base PlantPart Form``, e.g. "Ashwagandha
    Root Extract" or "Capsicum Fruit Extract").

    Sprint E1.2.2 invariants this satisfies:
      #1 display_name_never_canonical — base phrase prefers the DSLD
         descriptive form over the scoring-group canonical, so we never
         collapse e.g. "KSM-66 Ashwagandha Root Extract" → "Ashwagandha".
      #4 branded_identity_preserved — if the source label carries a
         branded token (KSM-66, BioPerine, Capsimax, etc.) the output
         carries it.
      #5 plant_part_preserved — plant-part words land in ``forms[0].name``
         on DSLD data and therefore survive into the base phrase. When
         the cleaner reverse-engineered a thin form (source=
         "name_extraction", e.g. just "extract"), we fall back to the
         cleaned raw_source_text so species + plant part are not lost.
    """
    name = safe_str(ingredient.get("name"))
    raw = safe_str(ingredient.get("raw_source_text"))
    forms = ingredient.get("forms") or []
    first_form_name = ""
    first_form_source = ""
    if forms and isinstance(forms[0], dict):
        first_form_name = safe_str(forms[0].get("name"))
        first_form_source = safe_str(forms[0].get("source"))

    name_lower = name.lower()
    form_lower = first_form_name.lower()
    is_branded_name = any(t.lower() in name_lower for t in _BRANDED_TOKENS)

    # Thin-form fallback (capsules the Capsimax class of failures):
    # When the cleaner could not extract a real label form and synthesized
    # a generic one from the name AND the raw_source_text contains richer
    # descriptive content (species, plant part, branded modifiers), prefer
    # the cleaned raw text. Use it directly when it already contains the
    # name as a substring (i.e. the brand+species+part+form sequence).
    if (
        first_form_source == "name_extraction"
        and form_lower in _GENERIC_FORM_TOKENS
        and raw
    ):
        cleaned_raw = _strip_trademark_markers(raw)
        # Acceptance criteria: cleaned_raw is richer than name+form alone
        # AND contains the name token (so we're not swapping in unrelated
        # text). Word-count >= 3 ensures we don't drop into edge cases
        # where raw is also one word.
        if (
            len(cleaned_raw.split()) >= 3
            and (not name or name_lower in cleaned_raw.lower())
        ):
            return cleaned_raw

    # Word-boundary substring match so "Calcium" does NOT claim to be
    # contained in "Tricalcium Phosphate" (the user would see "Tricalcium
    # Phosphate" and not know it's Calcium).
    def _contains_word(haystack: str, needle: str) -> bool:
        if not needle:
            return False
        return bool(re.search(r"\b" + re.escape(needle) + r"\b", haystack, re.IGNORECASE))

    # Build the base phrase. Four subtypes:
    #   a) name ⊂ form (word-boundary) — form is already descriptive → use form
    #   b) form ⊂ name (word-boundary) — form is redundant             → use name
    #   c) name is brand — form carries generic base                  → use form, brand prefix below
    #   d) disjoint — chemical descriptor alone                       → composite "name (form)"
    if first_form_name and name:
        if _contains_word(first_form_name, name):
            base_phrase = first_form_name
        elif _contains_word(name, first_form_name):
            base_phrase = name
        elif is_branded_name:
            base_phrase = first_form_name
        else:
            base_phrase = f"{name} ({first_form_name})"
    elif first_form_name:
        base_phrase = first_form_name
    else:
        base_phrase = name or safe_str(ingredient.get("standard_name"))

    # Branded prefix — only when brand is on name but missing from base.
    branded = None
    base_lower = base_phrase.lower()
    for token in _BRANDED_TOKENS:
        t = token.lower()
        if t in name_lower and t not in base_lower:
            branded = token
            break

    result = f"{branded} {base_phrase}".strip() if branded else base_phrase
    # Strip any trademark markers that slipped through forms/name strings.
    return _strip_trademark_markers(result) or name


# Sprint E1.2.5 — active-count reconciliation.
# Every delta between raw_actives_count (pre-filter truth from the
# cleaner) and blob ingredients[] count must be EXPLAINED via
# reason codes aggregated from the cleaner's display_ingredients.
# Contract: if raw_actives > 0 and blob == 0, the blob MUST carry
# at least one reason code. Hard stop: unexplained drops OR the
# "PARSE_ERROR" sentinel reason must not reach release.
#
# Reason-code enum (keep tight — anything else is a bug signal):
_DROP_REASON_STRUCTURAL_HEADER = "DROPPED_STRUCTURAL_HEADER"   # "Total Omega-3", prop-blend parent
_DROP_REASON_NUTRITION_FACT = "DROPPED_NUTRITION_FACT"         # "Calories", macro rows
_DROP_REASON_CLASSIFIED_INACTIVE = "DROPPED_AS_INACTIVE"        # routed to inactive_ingredients
_DROP_REASON_SUMMARY_WRAPPER = "DROPPED_SUMMARY_WRAPPER"       # "Less than 2% of:" headers
_DROP_REASON_UNMAPPED = "DROPPED_UNMAPPED_ACTIVE"               # real active, scorer has no rule
_DROP_REASON_PARSE_ERROR = "DROPPED_PARSE_ERROR"                # bug sentinel (must be 0)

_ALLOWED_DROP_REASONS = frozenset({
    _DROP_REASON_STRUCTURAL_HEADER,
    _DROP_REASON_NUTRITION_FACT,
    _DROP_REASON_CLASSIFIED_INACTIVE,
    _DROP_REASON_SUMMARY_WRAPPER,
    _DROP_REASON_UNMAPPED,
    _DROP_REASON_PARSE_ERROR,  # allowed shape-wise but must surface in triage
})

# display_type → reason code mapping. The cleaner tags every dropped
# item via _queue_display_ingredient(display_type=...), so we derive
# reasons from the already-trusted tag rather than re-classifying.
_DISPLAY_TYPE_TO_REASON = {
    "structural_container": _DROP_REASON_STRUCTURAL_HEADER,
    "summary_wrapper": _DROP_REASON_SUMMARY_WRAPPER,
    "inactive_ingredient": _DROP_REASON_CLASSIFIED_INACTIVE,
}


def _compute_ingredients_dropped_reasons(enriched: Dict[str, Any]) -> List[str]:
    """Aggregate per-product drop reason codes from the cleaner's
    display_ingredients trail. Sorted + deduped — stable emission.
    Unmapped actives (from scored output) also surface as a reason.
    """
    reasons: set = set()
    for di in safe_list(enriched.get("display_ingredients")):
        if not isinstance(di, dict):
            continue
        dt = safe_str(di.get("display_type"))
        code = _DISPLAY_TYPE_TO_REASON.get(dt)
        if code:
            reasons.add(code)
    # Unmapped-actives list from scored output (already plumbed through
    # the pipeline) provides the UNMAPPED signal.
    # (Note: unmapped_actives is attached in build_detail_blob after
    # scored data is merged; we accept the caller to layer it in.)
    return sorted(reasons)


# Sprint E1.5 — Export-error classification taxonomy.
#
# Before E1, every ValueError raised during product export was bucketed
# as a hard "error" — and the Supabase sync gate refused any non-empty
# errors[] list. That gate was correct when errors == "catastrophic
# pipeline bug", but E1 added validators that *intentionally* exclude
# products to prevent shipping bad data (E1.2.5 coverage-gap gates) or
# to surface authoring issues (E1.1.2 tone checks). Those are by-design
# exclusions, not failures — the sync gate shouldn't block on them.
#
# This classifier splits the raised-ValueError stream into three buckets:
#
#   - 'error'             → catastrophic (schema drift, column count
#                            mismatch, unknown enum leak). BLOCKS sync.
#   - 'excluded_by_gate'  → by-design coverage gate (E1.2.5 unexplained
#                            drop, filter regression detected). Product
#                            excluded from catalog but pipeline is
#                            working as intended. Does NOT block sync.
#   - 'warning'           → content-quality issue (tone sweep gap,
#                            Dr Pham authoring backlog). Does NOT block.
#
# Patterns are ordered: first match wins. Everything unmatched defaults
# to 'error' so the gate fails-safe — new validator messages need an
# explicit taxonomy entry before they become non-blocking.
_EXPORT_ERROR_TAXONOMY: List[Tuple[str, "re.Pattern[str]"]] = [
    (
        "excluded_by_gate",
        re.compile(
            r"raw DSLD disclosed \d+ real (active|inactive)\(s\) but blob"
            r"|filter regression — inspect"
            r"|Unexplained drop — inspect normalize_product"
            # E1.6 defense gate: 100% of raw actives became inactive — almost
            # always a cleaner classifier bug (see commit 4d05a74).
            r"|all raw actives reclassified as inactive — likely cleaner classifier bug"
            # Batch 3 data integrity gate: NOT_SCORED verdicts and
            # incomplete scoring breakdowns are quarantined (never shipped
            # to Flutter) but are non-blocking by design.
            r"|review_queue:"
        ),
    ),
    (
        "warning",
        re.compile(
            r"critical-mode warning .* carries condition-specific copy"
        ),
    ),
]


def _classify_export_error(msg: str) -> str:
    """Classify an export-validator error message into one of:
    'error', 'excluded_by_gate', 'warning'. See ``_EXPORT_ERROR_TAXONOMY``
    above for pattern definitions. Unknown patterns fail-safe to 'error'
    so that new validator messages don't silently become non-blocking.
    """
    for bucket, pattern in _EXPORT_ERROR_TAXONOMY:
        if pattern.search(msg or ""):
            return bucket
    return "error"


def _validate_active_count_reconciliation(
    blob: Dict[str, Any], raw_actives_count: int, dsld_id: str
) -> None:
    """Hard stop when raw has actives but blob is empty AND no drop
    reasons are recorded. Also flags use of the PARSE_ERROR sentinel
    — that reason is allowed shape-wise but must trend to zero before
    release."""
    blob_actives = len(blob.get("ingredients") or [])
    reasons = blob.get("ingredients_dropped_reasons") or []

    if raw_actives_count > 0 and blob_actives == 0 and not reasons:
        raise ValueError(
            f"[{dsld_id}] raw DSLD disclosed {raw_actives_count} real "
            f"active(s) but blob has 0 ingredients AND 0 drop reasons. "
            f"Unexplained drop — inspect normalize_product flatten path "
            f"(Sprint E1.2.5)."
        )

    # E1.6 defense gate: catch the Bucket-B class of bug where 100% of raw
    # actives become DROPPED_AS_INACTIVE (and nothing else). That pattern
    # almost always indicates a cleaner classifier mistake — a real active
    # is being routed to the inactive bucket because of a category=fat /
    # sugar / carb misclassification (see fix at enhanced_normalizer.py
    # commit 4d05a74). Without this gate, ~186 single-active products
    # silently shipped with no score for months. Excluded products surface
    # in export_audit_report.json under excluded_by_gate; the next pipeline
    # run after a real fix recovers them.
    if (
        raw_actives_count > 0
        and blob_actives == 0
        and reasons
        and set(reasons) == {_DROP_REASON_CLASSIFIED_INACTIVE}
    ):
        raise ValueError(
            f"[{dsld_id}] all raw actives reclassified as inactive — "
            f"likely cleaner classifier bug. raw_actives={raw_actives_count}, "
            f"blob_actives={blob_actives}, drop_reasons={reasons}. "
            f"Investigate enhanced_normalizer._is_nutrition_fact for this "
            f"product's category/group combo."
        )

    for r in reasons:
        if r not in _ALLOWED_DROP_REASONS:
            raise ValueError(
                f"[{dsld_id}] unknown drop reason {r!r} in "
                f"ingredients_dropped_reasons — must be one of "
                f"{sorted(_ALLOWED_DROP_REASONS)} (Sprint E1.2.5)."
            )


# Sprint E1.2.4 — inactive-ingredient preservation invariant.
# The cleaner (enhanced_normalizer) stashes the pre-filter count of
# real raw inactives (excluding DSLD's "None" placeholder) as
# `raw_inactives_count` on its output. Build emits it on the blob and
# a validator asserts: if raw_inactives_count > 0, blob
# inactive_ingredients[] must be non-empty. Detects any future filter
# regression that silently drops real excipients.
_NONE_PLACEHOLDER_NAMES = {"none", "n/a", "na", ""}


def _validate_inactive_preservation(
    blob: Dict[str, Any], raw_inactives_count: int, dsld_id: str
) -> None:
    """Raise ``ValueError`` if raw DSLD had ≥1 real inactive but the
    blob emits an empty inactive_ingredients list. Also enforces: the
    literal "None" placeholder must never leak into a blob entry."""
    blob_inactives = blob.get("inactive_ingredients") or []

    # Hard stop: literal "None" placeholder leak.
    for ing in blob_inactives:
        if not isinstance(ing, dict):
            continue
        name = (ing.get("name") or "").strip().lower()
        if name in _NONE_PLACEHOLDER_NAMES:
            raise ValueError(
                f"[{dsld_id}] inactive_ingredients contains a placeholder "
                f"entry (name={ing.get('name')!r}); the DSLD \"None\" "
                f"placeholder must be filtered (Sprint E1.2.4)."
            )

    # Preservation invariant (contract test E1.0.1 #7).
    if raw_inactives_count > 0 and len(blob_inactives) == 0:
        raise ValueError(
            f"[{dsld_id}] raw DSLD disclosed {raw_inactives_count} real "
            f"inactive(s) but blob emits 0. Filter regression — inspect "
            f"enhanced_normalizer._process_other_ingredients_enhanced "
            f"(Sprint E1.2.4)."
        )


# Sprint E1.4.1 — plural-array normalization for condition_ids /
# drug_class_ids. Every warning entry emits the plural array only;
# legacy singular keys are migrated then dropped. Arrays are sorted
# + deduped for determinism. Applied to both warnings[] and
# warnings_profile_gated[] independently.
_WARNING_ID_KEY_PAIRS = (
    ("condition_id", "condition_ids"),
    ("drug_class_id", "drug_class_ids"),
)


def _normalize_warning_condition_keys(w: Dict[str, Any]) -> Dict[str, Any]:
    """Return a shallow copy of ``w`` with ``condition_id`` /
    ``drug_class_id`` migrated into their plural-array counterparts.
    Arrays are sorted + deduplicated with blank / None entries dropped.
    Idempotent on already-plural shape.
    """
    if not isinstance(w, dict):
        return w

    out = dict(w)
    for singular, plural in _WARNING_ID_KEY_PAIRS:
        collected: List[str] = []

        arr_val = out.get(plural)
        if isinstance(arr_val, list):
            collected.extend(arr_val)

        scalar_val = out.get(singular)
        if isinstance(scalar_val, str) and scalar_val:
            collected.append(scalar_val)
        elif scalar_val and not isinstance(scalar_val, (list, dict)):
            # Belt-and-suspenders: coerce non-string scalars to str.
            collected.append(str(scalar_val))

        cleaned = sorted({
            str(x).strip() for x in collected
            if x is not None and str(x).strip()
        })
        out[plural] = cleaned
        out.pop(singular, None)

    return out


# Sprint E1.2.3 — warning dedup at build time.
# Collapses semantically identical warnings within a single list while
# preserving the most-informative copy. NEVER merges across the two
# warning lists (warnings[] vs warnings_profile_gated[]) — those have
# different rendering contracts.
_DEDUP_COPY_SCORE_FIELDS_RICH = ("alert_headline", "alert_body")
_DEDUP_COPY_SCORE_FIELDS_AUTHORED = (
    "safety_warning",
    "safety_warning_one_liner",
    "safety_summary",
    "safety_summary_one_liner",
    "detail",
    "informational_note",
)


def _warning_dedup_key(w: Dict[str, Any]) -> tuple:
    """Normalized identity tuple used to detect duplicates.

    Normalizes:
      * None / "" / missing key → ()
      * scalar vs list values → sorted tuple of str
      * case on source labels kept as-is (identifiers are case-sensitive)
    """
    def _norm(v) -> tuple:
        if v is None:
            return ()
        if isinstance(v, (list, tuple)):
            return tuple(sorted(str(x) for x in v if x not in (None, "")))
        s = str(v)
        return (s,) if s else ()

    return (
        _norm(w.get("severity")),
        _norm(w.get("canonical_id") or w.get("type")),
        _norm(w.get("condition_id") or w.get("condition_ids")),
        _norm(w.get("drug_class_id") or w.get("drug_class_ids")),
        _norm(w.get("source_rule") or w.get("source")),
    )


def _warning_completeness_score(w: Dict[str, Any]) -> tuple:
    """Higher-is-better ordering for picking which duplicate to keep.

    Tiers (tuple, compared lexicographically by Python):
      1. # of rich alert_* fields populated (0/1/2)
      2. # of authored safety_*/detail fields populated (0-6)
      3. total char-length of all populated string fields (tiebreaker)
    """
    rich = sum(
        1 for f in _DEDUP_COPY_SCORE_FIELDS_RICH
        if isinstance(w.get(f), str) and w.get(f).strip()
    )
    authored = sum(
        1 for f in _DEDUP_COPY_SCORE_FIELDS_AUTHORED
        if isinstance(w.get(f), str) and w.get(f).strip()
    )
    total_chars = sum(
        len(w.get(f)) for f in _DEDUP_COPY_SCORE_FIELDS_RICH + _DEDUP_COPY_SCORE_FIELDS_AUTHORED
        if isinstance(w.get(f), str)
    )
    return (rich, authored, total_chars)


def _dedup_warnings(warnings_list: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Collapse duplicates within one warning list. Preserves the first-
    surviving-instance order; within a dup group, picks the entry with
    the highest completeness score."""
    if not warnings_list:
        return []

    # First pass — group by dedup key, pick best per group, record
    # earliest index for stable ordering.
    by_key: Dict[tuple, Dict[str, Any]] = {}
    first_index: Dict[tuple, int] = {}

    for idx, w in enumerate(warnings_list):
        if not isinstance(w, dict):
            continue
        key = _warning_dedup_key(w)
        best = by_key.get(key)
        if best is None:
            by_key[key] = w
            first_index[key] = idx
            continue
        if _warning_completeness_score(w) > _warning_completeness_score(best):
            by_key[key] = w
            # keep the earliest first_index — don't promote position on replacement

    # Second pass — emit in earliest-appearance order for UX stability.
    return [by_key[k] for k in sorted(by_key, key=lambda kk: first_index[kk])]


# Sprint E1.2.2.d — display_badge (adapter, not inference).
# Pure function of already-trusted fields. Dev rule: "Badges reflect
# what the system already knows — not what it guesses." If the scorer
# didn't compute adequacy, the badge stays no_data; we never infer
# well_dosed from dose magnitude alone, and we never divide blend
# totals across members.
_BADGE_WELL_DOSED = "well_dosed"
_BADGE_LOW_DOSE = "low_dose"
_BADGE_HIGH_DOSE = "high_dose"
_BADGE_NOT_DISCLOSED = "not_disclosed"
_BADGE_NO_DATA = "no_data"

# Scorer adequacy tier → badge mapping. Conservative: unknown tier
# labels fall through to no_data rather than assuming "well_dosed".
_ADEQUACY_TIER_TO_BADGE = {
    "low": _BADGE_LOW_DOSE,
    "adequate": _BADGE_WELL_DOSED,
    "good": _BADGE_WELL_DOSED,
    "excellent": _BADGE_HIGH_DOSE,
    "above_typical_range": _BADGE_HIGH_DOSE,
}


def _compute_display_badge(ingredient: Dict[str, Any]) -> str:
    """Produce the user-facing quality-tier badge. Deterministic
    short-circuit decision tree — no inference beyond what already
    exists in the ingredient dict.
    """
    qty_raw = ingredient.get("quantity")
    qty = safe_float(qty_raw, 0) if qty_raw is not None else 0.0
    unit = safe_str(ingredient.get("unit")).strip()
    unit_lower = unit.lower()
    has_real_dose = (
        isinstance(qty, (int, float)) and qty > 0
        and unit_lower not in _NP_SENTINELS
    )
    is_blend_member = bool(
        ingredient.get("isNestedIngredient")
        or ingredient.get("proprietaryBlend")
        or ingredient.get("is_in_proprietary_blend")
    )

    # Rule 1 — blend member without individual dose → not_disclosed.
    # Short-circuits first so no upstream adequacy_tier can ever promote
    # an undisclosed member to well_dosed.
    if is_blend_member and not has_real_dose:
        return _BADGE_NOT_DISCLOSED

    # Rule 2 — no dose / NP unit → no_data (on non-blend).
    if not has_real_dose:
        return _BADGE_NO_DATA

    # Rule 3 — scorer-supplied adequacy tier wins when present.
    tier = ingredient.get("adequacy_tier")
    if isinstance(tier, str):
        mapped = _ADEQUACY_TIER_TO_BADGE.get(tier.lower())
        if mapped:
            return mapped
        # Unknown tier — fall through; never invent a badge.

    # Rule 4 — dose is disclosed but scorer doesn't know adequacy.
    # Stay honest: no_data.
    return _BADGE_NO_DATA


# Sprint E1.2.2.c — standardization_note extraction.
# Tight regex (external-dev rule): "If I'm not 100% sure the % belongs
# to this compound, return null." Matches only ``<int>%`` (with optional
# "+" suffix like "95%+") followed by a whitespace + exact compound
# from the conservative starter allowlist. Everything else → None.
#
# Explicitly rejects: fractional percents, ranges ("5-10%"),
# bioavailability / absorption / survival phrases, elemental content,
# and generic marketing language ("highly standardized").
_STANDARDIZATION_COMPOUNDS = (
    "withanolides", "curcuminoids", "ginsenosides", "rosavins",
    "bacosides", "saponins", "piperine", "EGCG", "silymarin",
)
_STANDARDIZATION_RE = re.compile(
    # \b — word boundary
    # (\d{1,3}) — integer 1-3 digits  (fractional rejected by design)
    # %\+? — mandatory % with optional "+" suffix
    # [\s]+ — whitespace separator (1+)
    # NOT preceded by a hyphen (ranges like "5-10% withanolides" rejected)
    # Negative lookbehind rejects leading digit / hyphen / dot so the
    # "5" in "5.5%" or "10-20%" never matches alone.
    r"(?<![\d\-\.])(\d{1,3})%\+?\s+(" + "|".join(_STANDARDIZATION_COMPOUNDS) + r")\b",
    re.IGNORECASE,
)


def _compute_standardization_note(ingredient: Dict[str, Any]) -> Optional[str]:
    """Extract a standardization claim ("5% withanolides") from the
    ingredient's matched_form / notes / raw_source_text, in priority
    order. Returns ``None`` when no tight-regex match exists.

    Compound name is normalized to the canonical casing from the
    allowlist so downstream consumers aren't forced to case-fold.
    Does not mutate the input dict.
    """
    # Preferred source order — most structured first.
    candidates: List[str] = []
    mf = ingredient.get("matched_form")
    if isinstance(mf, str) and mf.strip():
        candidates.append(mf)

    notes = ingredient.get("notes")
    if isinstance(notes, str) and notes.strip():
        candidates.append(notes)
    elif isinstance(notes, list):
        for n in notes:
            if isinstance(n, str) and n.strip():
                candidates.append(n)

    raw = ingredient.get("raw_source_text")
    if isinstance(raw, str) and raw.strip():
        candidates.append(raw)

    compound_by_lower = {c.lower(): c for c in _STANDARDIZATION_COMPOUNDS}
    for text in candidates:
        m = _STANDARDIZATION_RE.search(text)
        if m:
            pct = m.group(1)
            compound_raw = m.group(2)
            compound_canonical = compound_by_lower.get(compound_raw.lower(), compound_raw)
            return f"{pct}% {compound_canonical}"
    return None


# Sprint E1.2.2.b — display_dose_label.
# Three allowed output classes (external-dev medical-honesty rule):
#   "600 mg"               — individually disclosed
#   "Amount not disclosed" — proprietary-blend member without own dose
#   "—"                    — truly missing
# Never infer member dose from blend total; never leak raw "NP".
_EM_DASH = "—"
_NOT_DISCLOSED_TEXT = "Amount not disclosed"
_PROBIOTIC_STRAIN_NOT_LISTED_TEXT = "Per-strain dose not listed"
_NP_SENTINELS = {"np", "n/p", "not provided", ""}


def _format_dose_number(qty: float) -> str:
    """Drop trailing .0 on integer-valued floats; keep decimals on true
    fractions. Uses ``:g`` which avoids scientific notation up to ~16
    digits, sufficient for CFU counts and mg doses."""
    if qty == int(qty):
        return str(int(qty))
    return f"{qty:g}"


def _compute_display_dose_label(
    ingredient: Dict[str, Any],
    is_probiotic_strain: bool = False,
) -> str:
    """Produce the user-facing dose string. Three classes only; never
    infers from blend totals, never leaks the internal "NP" sentinel.

    ``is_probiotic_strain`` swaps the Class-2 wording from the generic
    "Amount not disclosed" to "Per-strain dose not listed" so the user
    isn't misled into thinking the manufacturer hid information — per-
    strain CFU is rarely listed even on transparent probiotic labels
    and the product-level total appears on ProbioticDetailSection.
    """
    qty_raw = ingredient.get("quantity")
    qty = safe_float(qty_raw, 0) if qty_raw is not None else 0.0
    unit = safe_str(ingredient.get("unit")).strip()
    unit_lower = unit.lower()

    is_blend_member = bool(
        ingredient.get("isNestedIngredient")
        or ingredient.get("proprietaryBlend")
        or ingredient.get("is_in_proprietary_blend")
    )

    has_real_unit = unit_lower not in _NP_SENTINELS
    has_real_dose = isinstance(qty, (int, float)) and qty > 0 and has_real_unit

    # Class 1 — individually disclosed wins regardless of blend membership.
    if has_real_dose:
        qty_str = _format_dose_number(qty)
        # CFU count → render in billions when ≥ 1e9 for human readability.
        if unit_lower == "cfu" and qty >= 1_000_000_000:
            billions = qty / 1_000_000_000
            return f"{_format_dose_number(billions)} billion CFU"
        return f"{qty_str} {unit}"

    # Class 2 — prop-blend member without an individual dose.
    if is_blend_member:
        return (
            _PROBIOTIC_STRAIN_NOT_LISTED_TEXT if is_probiotic_strain
            else _NOT_DISCLOSED_TEXT
        )

    # Class 3 — truly missing.
    return _EM_DASH


def _compute_dose_status(ingredient: Dict[str, Any]) -> str:
    """Canonical dose-disclosure enum, mirrors _compute_display_dose_label.

    Returns one of:
      disclosed           individually disclosed quantity + therapeutic unit
      not_disclosed_blend prop-blend member with no own dose
      missing             no dose, not in a blend
    """
    qty_raw = ingredient.get("quantity")
    qty = safe_float(qty_raw, 0) if qty_raw is not None else 0.0
    unit = safe_str(ingredient.get("unit")).strip().lower()
    has_real_unit = unit not in _NP_SENTINELS
    has_real_dose = isinstance(qty, (int, float)) and qty > 0 and has_real_unit
    if has_real_dose:
        return "disclosed"
    is_blend_member = bool(
        ingredient.get("isNestedIngredient")
        or ingredient.get("proprietaryBlend")
        or ingredient.get("is_in_proprietary_blend")
    )
    if is_blend_member:
        return "not_disclosed_blend"
    return "missing"


def _validate_banned_preflight_propagation(
    blob: Dict[str, Any], enriched: Dict[str, Any], dsld_id: str
) -> None:
    """Raise ``ValueError`` if a banned product lacks preflight copy. Also
    enforces Dr Pham's char-limit contract on the authored strings
    (80 / 200) so the Flutter red-banner layout never truncates.
    """
    if not has_banned_substance(enriched):
        return
    bsd = blob.get("banned_substance_detail")
    if not isinstance(bsd, dict):
        raise ValueError(
            f"[{dsld_id}] has_banned_substance=1 but banned_substance_detail "
            f"missing from blob. Flutter Sprint 27.7 preflight sheet needs "
            f"this top-level key (Sprint E1.1.4)."
        )
    one = bsd.get("safety_warning_one_liner")
    body = bsd.get("safety_warning")
    if not isinstance(one, str) or not one.strip():
        raise ValueError(
            f"[{dsld_id}] banned_substance_detail.safety_warning_one_liner "
            f"empty — Dr Pham authored copy did not propagate from "
            f"banned_recalled_ingredients.json (Sprint E1.1.4)."
        )
    if not isinstance(body, str) or not body.strip():
        raise ValueError(
            f"[{dsld_id}] banned_substance_detail.safety_warning empty — "
            f"Dr Pham authored copy did not propagate (Sprint E1.1.4)."
        )
    if len(one) > _BANNED_PREFLIGHT_ONE_LINER_MAX:
        raise ValueError(
            f"[{dsld_id}] banned_substance_detail.safety_warning_one_liner "
            f"exceeds {_BANNED_PREFLIGHT_ONE_LINER_MAX}-char limit "
            f"({len(one)} chars): {one!r} (Sprint E1.1.4)."
        )
    if len(body) > _BANNED_PREFLIGHT_BODY_MAX:
        raise ValueError(
            f"[{dsld_id}] banned_substance_detail.safety_warning exceeds "
            f"{_BANNED_PREFLIGHT_BODY_MAX}-char limit ({len(body)} chars) "
            f"(Sprint E1.1.4)."
        )


# Sprint E1.1.3 — every warning MUST carry at least one populated authored-
# copy field. A warning where only the machine-readable ``type`` enum is
# populated renders as raw text in Flutter (user sees "ban_ingredient"
# instead of authored safety copy). The validator protects the build path
# against regressions from any new warning-emission site that forgets to
# populate authored copy.
#
# The 5 fields mirror the sprint §E1.0.2 invariant #3 set.
_WARNING_REQUIRED_COPY_FIELDS = (
    "alert_headline",
    "alert_body",
    "safety_warning",
    "safety_warning_one_liner",
    "detail",
)


def _validate_warning_has_authored_copy(
    warnings_list: List[Dict[str, Any]], dsld_id: str
) -> None:
    """Raise ``ValueError`` if any warning has all 5 required authored-copy
    fields empty. Invoked for every product at build time.

    Emits ``dsld_id + warning_type`` in the error message so Dr Pham's
    authoring queue can be populated from build-failure triage.
    """
    for w in warnings_list or []:
        if not isinstance(w, dict):
            continue
        populated = False
        for field in _WARNING_REQUIRED_COPY_FIELDS:
            text = w.get(field)
            if isinstance(text, str) and text.strip():
                populated = True
                break
        if not populated:
            raise ValueError(
                f"[{dsld_id}] warning type={w.get('type')!r} has no authored "
                f"copy in any of {_WARNING_REQUIRED_COPY_FIELDS}. Raw enum "
                f"leak — this would render as machine text in Flutter. "
                f"Populate at least one of those fields (Sprint E1.1.3). "
                f"Add to Dr Pham authoring queue."
            )


def _validate_warning_display_mode_consistency(
    warnings_list: List[Dict[str, Any]], dsld_id: str
) -> None:
    """Raise ``ValueError`` if any warning with ``display_mode_default ==
    "critical"`` carries condition-specific copy. Invoked for every
    product at build time so a future regression cannot silently ship
    "Do not use during pregnancy" as a profile-less critical banner.
    """
    for w in warnings_list or []:
        if not isinstance(w, dict):
            continue
        if w.get("display_mode_default") != "critical":
            continue
        for field in _WARNING_AUTHORED_COPY_FIELDS:
            text = w.get(field)
            if not isinstance(text, str) or not text:
                continue
            m = _WARNING_CONDITION_SPECIFIC_RE.search(text)
            if m:
                raise ValueError(
                    f"[{dsld_id}] critical-mode warning (type="
                    f"{w.get('type')!r}) carries condition-specific copy "
                    f"in {field!r}: {m.group(0)!r} — rewrite as profile-"
                    f"agnostic or set display_mode_default=\"suppress\" "
                    f"(Sprint E1.1.2)."
                )


def _validate_decision_highlights(dh: Dict[str, Any], dsld_id: str) -> None:
    """Raise ``ValueError`` if ``decision_highlights.positive`` carries any
    token from the danger deny-list. Invoked for every product during
    the final-DB build so a future regression cannot silently ship green
    thumbs-up on danger-valence copy.

    Accepts ``positive`` as either str (current shape) or list[str]
    (forward-compat for future migration).
    """
    positive = dh.get("positive")
    if isinstance(positive, str):
        candidates = [positive]
    elif isinstance(positive, list):
        candidates = [s for s in positive if isinstance(s, str)]
    else:
        candidates = []

    for s in candidates:
        m = _DECISION_HIGHLIGHTS_DENY_LIST_RE.search(s)
        if m:
            raise ValueError(
                f"[{dsld_id}] decision_highlights.positive leaks danger-"
                f"valence token {m.group(0)!r}: {s!r}. Route this copy "
                f"into the 'danger' bucket instead (Sprint E1.1.1)."
            )


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
            safe_str(warning.get("severity"), "informational"),
            safe_str(warning.get("message")),
        ))
    if not dietary_warnings:
        sugar = safe_dict(ds.get("sugar"))
        sodium = safe_dict(ds.get("sodium"))
        if sugar.get("level") in ("moderate", "high"):
            raw_warnings.append((
                "dietary", "informational",
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
    non_gmo_audit = derive_non_gmo_audit(enriched)
    omega3_audit = derive_omega3_audit(enriched, scored)
    proprietary_blend_audit = derive_proprietary_blend_audit(enriched, scored)
    supplement_type_audit = build_supplement_type_audit(enriched, scored)

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

    # Probiotic context for active-row dose-label override. When a
    # probiotic strain is a blend member without an individual dose,
    # the bare "Amount not disclosed" label implies the manufacturer
    # hid information — but for probiotics the per-strain dose is
    # rarely listed even on transparent labels, and the product-level
    # CFU is shown on the ProbioticDetailSection. Swap the wording to
    # "Per-strain dose not listed" so users don't read it as opacity.
    _probiotic_data_block = safe_dict(enriched.get("probiotic_data"))
    _is_probiotic_product = bool(_probiotic_data_block.get("is_probiotic_product"))
    probiotic_strain_names: set[str] = set()
    if _is_probiotic_product:
        for blend in safe_list(_probiotic_data_block.get("probiotic_blends")):
            if not isinstance(blend, dict):
                continue
            for s in safe_list(blend.get("strains")):
                if isinstance(s, str) and s.strip():
                    probiotic_strain_names.add(s.strip().lower())

    # Sprint E1.3.2 — per-strain probiotic adequacy lookup, keyed by the
    # strain name as matched in the enricher. Build-time adapter attaches
    # ``adequacy_tier`` + ``clinical_support_level`` onto the ingredient
    # dict so ``_compute_display_badge`` wakes up naturally.
    probiotic_strain_adequacy: Dict[str, Dict[str, Any]] = {}
    for fc in safe_list(safe_dict(enriched.get("probiotic_data")).get("clinical_strains")):
        if not isinstance(fc, dict):
            continue
        strain_name = safe_str(fc.get("strain"))
        if not strain_name:
            continue
        probiotic_strain_adequacy[strain_name.strip().lower()] = {
            "adequacy_tier": fc.get("adequacy_tier"),
            "clinical_support_level": fc.get("clinical_support_level"),
            "cfu_per_day": fc.get("cfu_per_day"),
            "clinical_id": fc.get("clinical_id"),
            # Sprint E1.3.2.b — hybrid confidence descriptors.
            "cfu_confidence": fc.get("cfu_confidence"),
            "dose_basis": fc.get("dose_basis"),
            "ui_copy_hint": fc.get("ui_copy_hint"),
        }

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
        # Sprint E1.3.2 — look up adequacy by strain name (case-insensitive).
        _strain_adequacy = probiotic_strain_adequacy.get(name.strip().lower()) or {}
        # Canonical form + dose contract for Flutter. Single source of
        # truth: pipeline emits explicit states, Flutter renders them.
        form_contract = _compute_form_contract(ing, m)
        ingredients.append({
            "raw_source_text": raw,
            "name": name,
            "standardName": standard_name,
            "normalized_key": safe_str(ing.get("normalized_key")),
            "forms": safe_list(ing.get("forms")),
            "quantity": safe_float(qty),
            "unit": safe_str(ing.get("unit")),
            "standard_name": safe_str(m.get("standard_name")),
            "matched_form": safe_str(m.get("matched_form")),
            "matched_forms": safe_list(m.get("matched_forms")),
            "extracted_forms": safe_list(m.get("extracted_forms")),
            "display_form_label": form_contract["display_form_label"],
            "form_status": form_contract["form_status"],
            "form_match_status": form_contract["form_match_status"],
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
            # canonical_id — foundational identifier for interactions, stack
            # logic, evidence routing, biomarker scoring, dedup, and analytics.
            # The enricher writes it into both activeIngredients[].canonical_id
            # AND ingredient_quality_data.ingredients[].canonical_id (`m`).
            # Prefer `m` (post-enrichment match) over `ing` (raw label entry).
            "canonical_id": safe_str(m.get("canonical_id") or ing.get("canonical_id")),
            # delivers_markers — marker-via-ingredient evidence routing payload.
            # Computed by the enricher (botanical_marker_contributions.json) and
            # attached to the IQM match record. Always emit as a list (possibly
            # empty) so Flutter consumers can iterate without null-checks.
            "delivers_markers": safe_list(m.get("delivers_markers")),
            # `is_safety_concern` is the semantic safety flag. Computed by
            # the unified safety contract resolver which consults BOTH
            # banned_recalled (ingredient_hits) AND harmful_additives
            # (harmful_hit). The previous code only checked harmful_hit
            # — that missed Yohimbe / Cannabidiol / Garcinia Cambogia /
            # Red Yeast Rice and other banned_recalled-only flags. See
            # `_resolve_active_safety_contract` docstring for precedence.
            "harmful_severity": harmful_hit.get("severity_level") if harmful_hit else None,
            **(lambda c: {
                "is_safety_concern": c["is_safety_concern"],
                "is_banned":         c["is_banned"],
                "safety_reason":     c["safety_reason"],
                "matched_source":    c["matched_source"],
                "matched_rule_id":   c["matched_rule_id"],
            })(_resolve_active_safety_contract(
                harmful_hit, harmful_ref, ingredient_hits,
                name_terms=_active_banned_recall_terms(raw, name, standard_name),
                banned_recalled_index=_get_active_banned_recalled_index(),
            )),
            "harmful_notes": (
                safe_str(harmful_ref.get("mechanism_of_harm"))
                or safe_str(harmful_ref.get("notes"))
                or safe_str(harmful_hit.get("classification_evidence"))
                or safe_str(harmful_hit.get("category"))
            ) if harmful_hit else None,
            "is_allergen": bool(allergen_hits),
            "identifiers": extract_identifiers(
                iqm_index.get(safe_str(m.get("parent_key") or ing.get("normalized_key")), {})
            ),
            # Sprint E1.2.2.a — pre-computed Flutter display label
            "display_label": _compute_display_label(ing),
            # Sprint E1.2.2.b — pre-computed Flutter dose label.
            # Probiotic blend members override the generic "Amount not
            # disclosed" copy with "Per-strain dose not listed" so users
            # don't read it as the manufacturer hiding information —
            # per-strain CFU is rarely listed even on transparent
            # probiotic labels and the product-level total is shown on
            # ProbioticDetailSection.
            "display_dose_label": _compute_display_dose_label(
                ing,
                is_probiotic_strain=name.strip().lower() in probiotic_strain_names,
            ),
            "dose_status": _compute_dose_status(ing),
            # Sprint E1.2.2.c — standardization claim (None when not known)
            "standardization_note": _compute_standardization_note({
                "matched_form": m.get("matched_form") or ing.get("matched_form"),
                "notes": m.get("notes") or ing.get("notes"),
                "raw_source_text": ing.get("raw_source_text"),
            }),
            # Sprint E1.3.2 — per-strain adequacy (None when not a
            # matched clinical strain OR when per-strain CFU isn't
            # knowable e.g. multi-strain blend).
            "adequacy_tier": _strain_adequacy.get("adequacy_tier"),
            "clinical_support_level": _strain_adequacy.get("clinical_support_level"),
            # Sprint E1.3.2.b — hybrid confidence descriptors (controlled
            # enums; None on non-probiotic ingredients so this stays off
            # generic ingredient surfaces).
            "cfu_confidence": _strain_adequacy.get("cfu_confidence"),
            "dose_basis": _strain_adequacy.get("dose_basis"),
            "ui_copy_hint": _strain_adequacy.get("ui_copy_hint"),
            # Sprint E1.2.2.d — quality-tier badge (adapter — conservative).
            # Reads adequacy_tier above, so must come AFTER the E1.3.2 fields.
            "display_badge": _compute_display_badge({**ing, "adequacy_tier": _strain_adequacy.get("adequacy_tier")}),
        })

    # Inactive ingredients
    # Inactive ingredients — unified resolver path (2026-05-12).
    # All safety + role classification flows through
    # InactiveIngredientResolver, which consults banned_recalled FIRST,
    # then harmful_additives, then other_ingredients (with notes-text
    # bleed-through prevention). Closes the "TiO2/Talc ship as
    # severity_status=n/a" gap that the previous harmful_lookup-only
    # path produced. See scripts/inactive_ingredient_resolver.py for
    # the full architectural rationale.
    inactive_resolver = _get_shared_inactive_resolver()
    inactive = []
    for ing in safe_list(enriched.get("inactiveIngredients")):
        if not isinstance(ing, dict):
            continue
        raw = safe_str(ing.get("raw_source_text"))
        name = safe_str(ing.get("name"), raw)
        std_name_ing = safe_str(ing.get("standardName"))

        # Single resolver call: returns InactiveResolution with all
        # safety + role fields populated.
        res = inactive_resolver.resolve(
            raw_name=name or raw,
            standard_name=std_name_ing,
        )

        # Phase 4a (2026-04-30): suppress label-noise + move-to-actives
        # entries from the Flutter inactive_ingredients[] blob. Entries
        # flagged is_label_descriptor=true are descriptive label fragments
        # (marketing copy, source descriptors, phytochemical markers).
        # Entries flagged is_active_only=true are bioactives that physically
        # relocate to the active-ingredient pipeline in V1.1. Either way,
        # do not render as inactive chips.
        if res.is_label_descriptor or res.is_active_only:
            continue

        inactive.append({
            "raw_source_text": raw,
            "name": name,
            "standardName": std_name_ing,
            "normalized_key": safe_str(ing.get("normalized_key")),
            "forms": safe_list(ing.get("forms")),
            "category": res.category or safe_str(ing.get("category")),
            "is_additive": res.is_additive or safe_bool(ing.get("isAdditive")),
            "functional_roles": res.functional_roles,
            "standard_name": res.standard_name or std_name_ing or name,
            "notes": res.notes,
            "mechanism_of_harm": res.mechanism_of_harm or "",
            "common_uses": res.common_uses,
            "population_warnings": res.population_warnings,
            "harmful_severity": res.harmful_severity,
            "harmful_notes": res.harmful_notes,
            "identifiers": res.identifiers or {},
            # Canonical inactive contract (v1.5.0+) — Flutter renders
            # these directly without local inference.
            "display_label": res.display_label,
            "display_role_label": res.display_role_label,
            "severity_status": res.severity_status,
            "is_safety_concern": res.is_safety_concern,
            # v1.6.0+ unified contract additions:
            "is_banned": res.is_banned,
            "safety_reason": res.safety_reason,
            "matched_source": res.matched_source,
            "matched_rule_id": res.matched_rule_id,
        })

    # Warnings
    #
    # Every warning now carries a `display_mode_default` enum that tells
    # the Flutter app how to render it when the user has NO matching
    # profile (no declared condition / drug class / pregnancy). Flutter
    # is expected to promote the display mode on-device when the user's
    # profile DOES match the warning's `condition_id` / `drug_class_id` /
    # ban_context. Values:
    #
    #   - "critical"      — always show. Substance-level hazard (banned,
    #                        adulterant, contaminant) OR severity ==
    #                        contraindicated. User profile is irrelevant.
    #   - "informational" — show as neutral note regardless of profile.
    #                        Used for rules that are material but not
    #                        alarming without matching profile (e.g.,
    #                        berberine + hypoglycemics when user has no
    #                        declared diabetes meds).
    #   - "suppress"      — do not render without profile match. On-device
    #                        filter promotes to "alert" if profile
    #                        matches.
    #
    # The pipeline also emits `warnings_profile_gated[]` = subset where
    # display_mode_default != "suppress" — apps that don't yet filter
    # client-side can render this directly without scaring the user with
    # unmatched conditional warnings.
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
        # Build references list from references_structured (FDA URLs, etc.)
        refs = sub.get("references_structured")
        source_urls = []
        if isinstance(refs, list):
            for ref in refs:
                if isinstance(ref, dict) and ref.get("url"):
                    source_urls.append({
                        "url": ref["url"],
                        "title": ref.get("title", ""),
                        "type": ref.get("type", ""),
                        "evidence_grade": ref.get("evidence_grade", ""),
                    })
        # Substance-level banned/recalled/high-risk hazards are always
        # critical — the user is exposed regardless of their profile.
        # Watchlist items are informational until a profile rule upgrades
        # them.
        ban_ctx = safe_str(sub.get("ban_context"))
        dm_default = "critical" if status in ("banned", "recalled", "high_risk") else "informational"
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
            "source_urls": source_urls,
            # Path C authored fields (optional during authoring transition).
            "ban_context": ban_ctx or None,
            "safety_warning": sub.get("safety_warning"),
            "safety_warning_one_liner": sub.get("safety_warning_one_liner"),
            "display_mode_default": dm_default,
        })

    for h in safe_list(enriched.get("harmful_additives")):
        if not isinstance(h, dict):
            continue
        # Prefer notes/mechanism emitted by enrichment; fallback to runtime resolution
        h_ref = resolve_harmful_reference(h)
        h_notes = safe_str(h.get("notes") or h_ref.get("notes"))
        h_mechanism = safe_str(h.get("mechanism_of_harm") or h_ref.get("mechanism_of_harm"))
        h_pop_warnings = h.get("population_warnings") or h_ref.get("population_warnings") or []
        h_severity = safe_str(h.get("severity_level"), "moderate").lower()
        # Tier display by severity. High/moderate additives (e.g.
        # titanium dioxide EU-ban, formaldehyde-releasing preservatives)
        # are substance-level hazards — always promote to RBU. Low
        # severity (silicon dioxide, microcrystalline cellulose, etc.)
        # are excipient quality signals tracked in `harmful_additives.json`
        # itself as "non-nutritive quality signal, not a safety risk".
        # They belong in the Tradeoffs filler-load badge, NOT in the
        # personalized Review-Before-Use card. `suppress` keeps them in
        # the catalog row but tells Flutter's profile filter to drop
        # them unless a profile rule explicitly upgrades them.
        h_dm = "suppress" if h_severity == "low" else "critical"
        warnings.append({
            "type": "harmful_additive",
            "severity": h_severity or "moderate",
            "title": f"Contains {safe_str(h.get('additive_name') or h.get('ingredient'))}",
            "detail": h_mechanism or h_notes or f"Category: {safe_str(h.get('category'))}",
            "notes": h_notes,
            "mechanism_of_harm": h_mechanism,
            "population_warnings": safe_list(h_pop_warnings),
            "category": safe_str(h.get("category")),
            "source": "harmful_additives_db",
            "identifiers": extract_identifiers(h_ref),
            # Path C authored fields (user-facing calm copy; 115 entries).
            "safety_summary": h_ref.get("safety_summary"),
            "safety_summary_one_liner": h_ref.get("safety_summary_one_liner"),
            "display_mode_default": h_dm,
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
            "allergen_id": safe_str(a.get("allergen_id") or a.get("canonical_id")),
            "source": "allergen_db",
            # Allergen presence is informational by default — only becomes
            # critical when Flutter sees a match against user's declared
            # allergens[] profile array.
            "display_mode_default": "informational",
        })

    # Interaction-rule warnings — profile-gating metadata added here.
    #
    # Each hit carries `display_mode_default` derived from rule severity.
    # Sprint E1.1.2 (2026-04-21): every entry in the loops below lives
    # inside `condition_rules[]` or `drug_class_rules[]` — by definition
    # profile-scoped. The authored copy carries condition-specific
    # language ("during pregnancy", "for liver disease", ...). Rendering
    # such copy to a profile-less user is medically wrong (e.g. a male
    # user seeing "Do not use during pregnancy"). The invariant:
    # profile-gated rules default to `suppress`; Flutter promotes to
    # alert-level severity on device when the user's profile matches
    # the rule's condition_id / drug_class_id.
    #
    #   contraindicated → "suppress" (was "critical" pre-E1.1.2; Flutter
    #                                  promotes to critical on profile match)
    #   avoid           → "informational" (show as neutral note without
    #                                       profile; Flutter promotes to
    #                                       "alert" if profile matches)
    #   caution/monitor → "suppress"    (do not show without profile)
    #   info            → "suppress"
    #
    # `severity_contextual` is the severity the app should render when NO
    # profile matches — downgraded to "informational" for avoid/caution
    # rules, untouched for contraindicated so the promoted render is
    # still alarming when profile matches.
    _INTERACTION_DISPLAY_MODE = {
        "contraindicated": "suppress",
        "avoid": "informational",
        "caution": "suppress",
        "monitor": "suppress",
        "info": "suppress",
    }
    _INTERACTION_CONTEXTUAL_SEVERITY = {
        "contraindicated": "contraindicated",
        "avoid": "informational",
        "caution": "informational",
        "monitor": "informational",
        "info": "info",
    }

    for alert in safe_list(safe_dict(enriched.get("interaction_profile")).get("ingredient_alerts")):
        if not isinstance(alert, dict):
            continue
        ing_name = safe_str(alert.get("ingredient_name"))
        for ch in safe_list(alert.get("condition_hits")):
            if isinstance(ch, dict):
                dose_eval = ch.get("dose_threshold_evaluation")
                raw_sev = safe_str(ch.get("severity"), "moderate").lower()
                warnings.append({
                    "type": "interaction",
                    "severity": raw_sev,
                    "severity_contextual": _INTERACTION_CONTEXTUAL_SEVERITY.get(
                        raw_sev, raw_sev
                    ),
                    "display_mode_default": _INTERACTION_DISPLAY_MODE.get(
                        raw_sev, "suppress"
                    ),
                    "title": f"{ing_name} / {safe_str(ch.get('condition_id'))}",
                    "detail": safe_str(ch.get("mechanism")),
                    "action": safe_str(ch.get("action")),
                    # Authored copy passthrough (optional during
                    # authoring transition).
                    "alert_headline": ch.get("alert_headline"),
                    "alert_body": ch.get("alert_body"),
                    "informational_note": ch.get("informational_note"),
                    "condition_id": safe_str(ch.get("condition_id")),
                    "ingredient_name": ing_name,
                    "evidence_level": safe_str(ch.get("evidence_level")),
                    "sources": safe_list(ch.get("sources")),
                    "dose_threshold_evaluation": dose_eval if isinstance(dose_eval, dict) else None,
                    "source": "interaction_rules",
                    "profile_gate": ch.get("profile_gate"),
                })
        for dh in safe_list(alert.get("drug_class_hits")):
            if isinstance(dh, dict):
                dose_eval = dh.get("dose_threshold_evaluation")
                raw_sev = safe_str(dh.get("severity"), "moderate").lower()
                warnings.append({
                    "type": "drug_interaction",
                    "severity": raw_sev,
                    "severity_contextual": _INTERACTION_CONTEXTUAL_SEVERITY.get(
                        raw_sev, raw_sev
                    ),
                    "display_mode_default": _INTERACTION_DISPLAY_MODE.get(
                        raw_sev, "suppress"
                    ),
                    "title": f"{ing_name} / {safe_str(dh.get('drug_class_id'))}",
                    "detail": safe_str(dh.get("mechanism")),
                    "action": safe_str(dh.get("action")),
                    "alert_headline": dh.get("alert_headline"),
                    "alert_body": dh.get("alert_body"),
                    "informational_note": dh.get("informational_note"),
                    "drug_class_id": safe_str(dh.get("drug_class_id")),
                    "ingredient_name": ing_name,
                    "evidence_level": safe_str(dh.get("evidence_level")),
                    "sources": safe_list(dh.get("sources")),
                    "dose_threshold_evaluation": dose_eval if isinstance(dose_eval, dict) else None,
                    "source": "interaction_rules",
                    "profile_gate": dh.get("profile_gate"),
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
            # Dietary warnings are profile-gated by diet preferences /
            # conditions (e.g., diabetic users care about sugar). Default
            # to informational; Flutter can promote based on user diet.
            "display_mode_default": "informational",
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
                "display_mode_default": "informational",
            })
        if sodium.get("level") in ("moderate", "high"):
            warnings.append({
                "type": "dietary",
                "severity": "moderate",
                "title": "Sodium Content",
                "detail": f"{sodium.get('amount_mg', 0)}mg sodium per serving ({safe_str(sodium.get('level_display'))})",
                "source": "dietary_sensitivity_data",
                "display_mode_default": "informational",
            })

    # Sprint E1.5.X-4 — discontinued/off-market no longer emitted into
    # warnings[]. Status is now exposed as a top-level `product_status_detail`
    # field so Flutter can render it as a small neutral "concern" chip
    # (not a safety warning, not a green-safe tag). Separation of concerns:
    # warnings[] = safety/interactions; product_status_detail = availability.
    pass  # intentionally no warning emission for discontinued/off_market

    # Build the profile-gated subset — warnings whose default treatment is
    # NOT "suppress". This is what Flutter should render by default when
    # the user has no declared profile; items with display_mode_default ==
    # "suppress" are held back until Flutter's on-device filter finds a
    # matching condition_id / drug_class_id in the user's profile and
    # promotes them to "alert".
    warnings_profile_gated = [
        w for w in warnings
        if w.get("display_mode_default", "critical") != "suppress"
    ]

    # Sprint E1.2.3 — collapse duplicates WITHIN each list independently.
    warnings = _dedup_warnings(warnings)
    warnings_profile_gated = _dedup_warnings(warnings_profile_gated)

    # Sprint E1.4.1 — migrate singular condition_id / drug_class_id to
    # plural arrays. Applied AFTER dedup so the dedup key doesn't have
    # to know about shape migration.
    warnings = [_normalize_warning_condition_keys(w) for w in warnings]
    warnings_profile_gated = [_normalize_warning_condition_keys(w) for w in warnings_profile_gated]

    # Sprint E1.1.2 — critical-mode warnings must be profile-agnostic.
    # Sprint E1.1.3 — every warning must carry at least one authored-copy field.
    dsld_id_for_validation = safe_str(enriched.get("dsld_id"))
    _validate_warning_display_mode_consistency(warnings, dsld_id_for_validation)
    _validate_warning_display_mode_consistency(warnings_profile_gated, dsld_id_for_validation)
    _validate_warning_has_authored_copy(warnings, dsld_id_for_validation)
    _validate_warning_has_authored_copy(warnings_profile_gated, dsld_id_for_validation)

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

    # Sprint 2026-05-01 — omega3 dose adequacy detail block.
    # Surfaces the EPA+DHA bonus alongside the new transparency fields
    # (`bonus_missed_due_to_opacity`, `bonus_missed_reason`) so Flutter can
    # show "EPA/DHA breakdown not disclosed" copy when the bonus is 0
    # because the omega-3 ingredient is buried in an opaque proprietary
    # blend. Score impact remains zero — informational only.
    e_raw = safe_dict(breakdown_raw.get("E"))
    omega3_detail = {
        "score": safe_float(e_raw.get("score"), 0),
        "max": safe_float(e_raw.get("max"), 0),
        "applicable": bool(e_raw.get("applicable", False)),
        "dose_band": safe_str(e_raw.get("dose_band")),
        "per_day_mid_mg": e_raw.get("per_day_mid_mg"),
        "per_day_min_mg": e_raw.get("per_day_min_mg"),
        "per_day_max_mg": e_raw.get("per_day_max_mg"),
        "epa_mg_per_unit": e_raw.get("epa_mg_per_unit"),
        "dha_mg_per_unit": e_raw.get("dha_mg_per_unit"),
        "prescription_dose": bool(e_raw.get("prescription_dose", False)),
        # Transparency flag — true when omega-3 bonus is 0 because the
        # ingredient is buried in an opaque proprietary blend.
        "bonus_missed_due_to_opacity": bool(
            e_raw.get("bonus_missed_due_to_opacity", False)
        ),
        "bonus_missed_reason": safe_str(e_raw.get("bonus_missed_reason")),
    }

    cd = safe_dict(enriched.get("certification_data"))
    serving = safe_dict(enriched.get("serving_basis"))
    evidence_data = safe_dict(enriched.get("evidence_data"))
    rda_ul_data = safe_dict(enriched.get("rda_ul_data"))

    blob = {
        "dsld_id": safe_str(enriched.get("dsld_id")),
        "product_name": safe_str(enriched.get("product_name")),
        "brand_name": safe_str(enriched.get("brandName")),
        "blob_version": 1,
        "ingredients": ingredients,
        "inactive_ingredients": inactive,
        "warnings": warnings,
        # Phase 8: structured per-allergen array for client-side
        # personalized matching against profile.allergens. Exact
        # allergen_id matching only. The display-ready summary string
        # (`allergen_summary` column on products_core) and the legacy
        # warnings[] entries with type='allergen' continue to power the
        # generic non-personalized banner.
        "allergens": build_structured_allergens(enriched),
        # Phase 8: positive gluten-free signal — orthogonal to the
        # negative allergen flow above. True when the label carries a
        # validated gluten-free claim (compliance_data.gluten_free) AND
        # no contradicting wheat/gluten ingredient hits. Surfaces as a
        # green "Gluten-Free Verified" badge; never as an allergen flag.
        "gluten_free_validated": safe_bool(
            enriched.get("claim_gluten_free_validated")
        ),
        # Profile-gated subset — see build logic above. Flutter should
        # render this by default to avoid firing scary-looking rules at
        # users who have no matching profile (e.g., berberine +
        # hypoglycemics surfacing to a user who isn't on diabetes meds).
        # Apps that have implemented on-device profile filtering can read
        # `warnings` and apply their own filter instead.
        "warnings_profile_gated": warnings_profile_gated,
        "section_breakdown": section_breakdown,
        # Sprint 2026-05-01 — omega-3 dose adequacy + transparency block.
        # Includes bonus_missed_due_to_opacity / bonus_missed_reason for
        # products with EPA/DHA hidden in opaque proprietary blends.
        "omega3_detail": omega3_detail,
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
        "non_gmo_audit": non_gmo_audit,
        "omega3_audit": omega3_audit,
        "proprietary_blend_audit": proprietary_blend_audit,
        "supplement_type_audit": supplement_type_audit,
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
        # T7A: scorer surfaces sub_clinical_canonicals at
        # scored.breakdown.C.sub_clinical_canonicals — the canonical
        # ingredient IDs that fell below the min_clinical_dose threshold.
        # Mark the matching analyzed_ingredients / adequacy_results rows
        # so Flutter can render the per-ingredient "Low dose" chip
        # without re-running the dose check client-side.
        sub_clinical_set = set(
            safe_list(
                safe_dict(safe_dict(scored.get("breakdown")).get("C"))
                .get("sub_clinical_canonicals")
            )
        )

        def _flag_below_clinical(rows):
            if not isinstance(rows, list):
                return rows
            out = []
            for row in rows:
                if not isinstance(row, dict):
                    out.append(row)
                    continue
                canon = safe_str(
                    row.get("canonical_id")
                    or row.get("ingredient_canonical")
                    or row.get("normalized_key")
                )
                marked = dict(row)
                marked["below_clinical_dose"] = bool(canon and canon in sub_clinical_set)
                out.append(marked)
            return out

        blob["rda_ul_data"] = {
            "collection_enabled": rda_ul_data.get("collection_enabled"),
            "collection_reason": rda_ul_data.get("collection_reason"),
            "ingredients_with_rda": rda_ul_data.get("ingredients_with_rda"),
            "analyzed_ingredients": _flag_below_clinical(
                rda_ul_data.get("analyzed_ingredients")
            ),
            "count": rda_ul_data.get("count"),
            "adequacy_results": _flag_below_clinical(
                safe_list(rda_ul_data.get("adequacy_results"))
            ),
            "conversion_evidence": safe_list(rda_ul_data.get("conversion_evidence")),
            "safety_flags": safe_list(rda_ul_data.get("safety_flags")),
            "has_over_ul": rda_ul_data.get("has_over_ul"),
        }

    # Probiotic detail — strains, CFU, clinical matches
    probiotic_data = safe_dict(enriched.get("probiotic_data"))
    if probiotic_data.get("is_probiotic_product"):
        # Pre-format the user-facing CFU label so Flutter renders without
        # re-deciding rounding rules — same pattern as display_dose_label
        # on ingredient rows. e.g. 25.0 → "25 billion CFU"; 5.5 → "5.5
        # billion CFU"; 0/None → "" (empty hides the chip).
        billion = probiotic_data.get("total_billion_count")
        if isinstance(billion, (int, float)) and billion > 0:
            if billion == int(billion):
                _cfu_label = f"{int(billion)} billion CFU"
            else:
                _cfu_label = f"{billion:g} billion CFU"
        else:
            _cfu_label = ""

        blob["probiotic_detail"] = {
            "is_probiotic": True,
            "total_strain_count": probiotic_data.get("total_strain_count"),
            "total_cfu": probiotic_data.get("total_cfu"),
            "total_billion_count": probiotic_data.get("total_billion_count"),
            "total_cfu_label": _cfu_label,
            "guarantee_type": probiotic_data.get("guarantee_type"),
            "has_cfu": probiotic_data.get("has_cfu"),
            # clinical_strains entries may carry per-strain is_inactivated /
            # is_postbiotic / is_blocked / postbiotic_note / block_reason flags
            # added 2026-05-01. Flutter can render strain-level postbiotic /
            # rejected badges from these fields.
            "clinical_strains": safe_list(probiotic_data.get("clinical_strains")),
            "clinical_strain_count": probiotic_data.get("clinical_strain_count", 0),
            "prebiotic_present": probiotic_data.get("prebiotic_present", False),
            "prebiotic_name": safe_str(probiotic_data.get("prebiotic_name")),
            "has_survivability_coating": probiotic_data.get("has_survivability_coating", False),
            "survivability_reason": safe_str(probiotic_data.get("survivability_reason")),
            "probiotic_blends": safe_list(probiotic_data.get("probiotic_blends")),
            # Sprint 2026-05-01 — product-level postbiotic indicator.
            # Independent of clinical_strain matching; surfaces postbiotic
            # content even when strains aren't in the high-quality clinical
            # bonus DB. Flutter can show "Contains postbiotic strains" badge.
            "has_postbiotic_strains": probiotic_data.get("has_postbiotic_strains", False),
            "detected_postbiotic_patterns": safe_list(
                probiotic_data.get("detected_postbiotic_patterns")
            ),
        }

    # Synergy cluster detail — matched clusters with ingredient doses
    formulation_data = safe_dict(enriched.get("formulation_data"))
    synergy_clusters = safe_list(formulation_data.get("synergy_clusters"))
    if synergy_clusters:
        # Build user-friendly synergy detail for Flutter
        synergy_display = []
        best_tier = 4
        for sc in synergy_clusters:
            tier = int(safe_float(sc.get("evidence_tier"), 4))
            best_tier = min(best_tier, tier)
            matched = safe_list(sc.get("matched_ingredients"))
            matched_names = [m.get("ingredient", "") for m in matched if isinstance(m, dict)]
            synergy_display.append({
                "id": safe_str(sc.get("cluster_id")),
                "name": safe_str(sc.get("cluster_name")),
                "evidence_tier": tier,
                "evidence_label": safe_str(sc.get("evidence_label", "Popular combination")),
                "mechanism": safe_str(sc.get("synergy_mechanism", sc.get("note", "")))[:300],
                # Path C authored field — layperson synergy framing for Flutter.
                "benefit_short": safe_str(sc.get("synergy_benefit_short")),
                "matched_ingredients": matched_names,
                "match_count": len(matched),
                "all_adequate": safe_bool(sc.get("all_adequate")),
                "pmids": safe_list(sc.get("pmids")),
                # Single-ingredient override signal — true when the cluster
                # qualified via a lone primary ingredient at adequate dose
                # (e.g. magnesium-only earning sleep_stack). Flutter can
                # optionally render a "solo ingredient" badge on the detail
                # card. Defaults to false for standard multi-ingredient
                # synergy matches.
                "single_ingredient_match": safe_bool(sc.get("single_ingredient_match")),
            })

        tier_bonus_map = {1: 1.0, 2: 0.75, 3: 0.5, 4: 0.25}
        blob["synergy_detail"] = {
            "qualified": len(synergy_display) > 0,
            "best_tier": best_tier,
            "bonus_awarded": tier_bonus_map.get(best_tier, 0.25),
            "bonus_explanation": {
                1: "This product contains ingredients with proven synergistic effects backed by clinical trials.",
                2: "This product combines co-dependent nutrients that work together in established biochemical pathways.",
                3: "This product contains a promising ingredient combination with early clinical support.",
                4: "This product combines complementary ingredients commonly used together, though clinical synergy data is limited.",
            }.get(best_tier, ""),
            "clusters": synergy_display,
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
        "claim_non_gmo_verified": bool(non_gmo_audit.get("project_verified")),
        "claim_non_gmo_present": bool(non_gmo_audit.get("claim_present")),
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
    if safe_float(a_sub.get("A5e"), 0) > 0:
        # v3.6.0: natural-source bonus moved here from A1.
        bonuses.append({"id": "A5e", "label": "Natural-source ingredients", "score": a_sub["A5e"]})
    if safe_float(a_sub.get("A6"), 0) > 0:
        bonuses.append({"id": "A6", "label": "Single-nutrient premium form", "score": a_sub["A6"]})
    if safe_float(a_sub.get("probiotic_bonus"), 0) > 0:
        bonuses.append({"id": "probiotic", "label": "Probiotic quality bonus", "score": a_sub["probiotic_bonus"]})
    if safe_float(a_sub.get("omega3_dose_bonus"), 0) > 0:
        bonuses.append(
            {
                "id": "omega3",
                "label": "Omega-3 dose bonus",
                "score": a_sub["omega3_dose_bonus"],
                "detail": safe_str(omega3_audit.get("dose_band")).replace("_", " "),
            }
        )
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
    # Use .get() for all b_sub key reads so a future scorer field rename
    # degrades gracefully instead of raising KeyError mid-blob-build.
    if safe_float(b_sub.get("B1_penalty"), 0) > 0:
        for h in safe_list(enriched.get("harmful_additives")):
            if isinstance(h, dict):
                penalties.append({
                    "id": "B1", "label": f"Harmful additive: {safe_str(h.get('additive_name') or h.get('ingredient'))}",
                    "score": b_sub.get("B1_penalty", 0),
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
        penalties.append({"id": "B3", "label": "Compliance claim violation", "score": b_sub.get("B3", 0)})
    if safe_float(b_sub.get("B5_penalty"), 0) > 0:
        penalties.append({"id": "B5", "label": "Proprietary blend opacity",
                          "score": b_sub.get("B5_penalty", 0),
                          "blend_count": len(safe_list(b_sub.get("B5_blend_evidence")))})
    if safe_float(b_sub.get("B6_penalty"), 0) > 0:
        penalties.append({"id": "B6", "label": "Unsubstantiated disease claims", "score": b_sub.get("B6_penalty", 0)})
    if safe_float(b_sub.get("B7_penalty"), 0) > 0:
        b7_evidence = safe_list(b_sub.get("B7_dose_safety_evidence"))
        for ev in b7_evidence:
            penalties.append({
                "id": "B7",
                "label": f"Exceeds safe dose limit: {ev.get('nutrient', 'unknown')} at {ev.get('pct_ul', 0):.0f}% of UL",
                "severity": "critical" if ev.get("pct_ul", 0) >= 200 else "warning",
                "reason": f"{ev.get('nutrient')}: {ev.get('amount')} vs UL {ev.get('ul')}",
            })
    if safe_float(b_sub.get("B8_penalty"), 0) > 0:
        b8_evidence = safe_list(b_sub.get("B8_caers_evidence"))
        for ev in b8_evidence:
            penalties.append({
                "id": "B8",
                "label": f"FDA adverse events: {ev.get('ingredient', 'unknown')} ({ev.get('serious_reports', 0)} serious reports)",
                "severity": ev.get("signal_strength", "unknown"),
                "reason": f"FDA CAERS: {ev.get('total_reports', 0)} total reports, {ev.get('serious_reports', 0)} serious",
            })
    vp = section_breakdown.get("violation_penalty", 0)
    if vp and safe_float(vp, 0) != 0:
        penalties.append({"id": "violation", "label": "Scoring violation penalty", "score": vp})

    # v1.3.2: Nutrition detail — all five macros for the Flutter transparency panel
    ns = safe_dict(enriched.get("nutrition_summary"))
    blob["nutrition_detail"] = {
        "calories_per_serving": safe_float(ns.get("calories_per_serving")),
        "total_carbohydrates_g": safe_float(ns.get("total_carbohydrates_g")),
        "total_fat_g": safe_float(ns.get("total_fat_g")),
        "protein_g": safe_float(ns.get("protein_g")),
        "dietary_fiber_g": safe_float(ns.get("dietary_fiber_g")),
    }

    # v1.3.2: Unmapped actives — transparency panel ("X ingredients could not be mapped")
    ua_names = safe_list(scored.get("unmapped_actives"))
    blob["unmapped_actives"] = {
        "names": ua_names,
        "total": int(scored.get("unmapped_actives_total") or 0),
        "excluding_banned_exact_alias": int(
            scored.get("unmapped_actives_excluding_banned_exact_alias") or 0
        ),
    }

    # Sprint E1.23 follow-up (2026-05-09) — surface demoted absorption
    # enhancers (e.g. BioPerine 5 mg below clinical threshold) under the
    # `ingredient_quality_data` blob key so Flutter's
    # `formulation_detail_section` can render them as info chips. The
    # enricher (`enrich_supplements_v3.py:2579`) already produces this
    # list inside `enriched.ingredient_quality_data`; previously the
    # build step never promoted it to the detail blob, so the Flutter
    # consumer at `formulation_detail_section.dart:60` always read null
    # and silently rendered nothing. Keeping the emission scoped to just
    # this single field — the full ingredient_quality_data object holds
    # internal scoring state we don't need on-device.
    demoted_enhancers = safe_list(iqd.get("demoted_absorption_enhancers"))
    if demoted_enhancers:
        blob["ingredient_quality_data"] = {
            "demoted_absorption_enhancers": demoted_enhancers,
        }

    blob["score_bonuses"] = bonuses
    blob["score_penalties"] = penalties
    blob["audit"] = {
        "non_gmo": non_gmo_audit,
        "omega3": omega3_audit,
        "proprietary_blend": proprietary_blend_audit,
        "supplement_type": supplement_type_audit,
        "gate_audit": {
            "blocking_reason": derive_blocking_reason(enriched, scored),
            "verdict": safe_str(scored.get("verdict")),
            "probiotic_eligibility": safe_dict(a_sub.get("probiotic_breakdown")).get("eligibility"),
        },
        "section_a_audit": {
            "score": safe_float(section_breakdown.get("ingredient_quality", {}).get("score"), 0),
            "max": safe_float(section_breakdown.get("ingredient_quality", {}).get("max"), 25),
            "ceiling_hit": (
                safe_float(section_breakdown.get("ingredient_quality", {}).get("score"), 0)
                >= safe_float(section_breakdown.get("ingredient_quality", {}).get("max"), 25)
            ),
            "core_quality": safe_float(a_sub.get("core_quality"), 0),
            "category_bonus_total": safe_float(a_sub.get("category_bonus_total"), 0),
        },
    }

    # Sprint E1.1.4 — top-level banned-substance preflight detail for
    # Flutter Sprint 27.7's stack-add CRITICAL banner.
    blob["banned_substance_detail"] = build_banned_substance_detail(enriched, warnings)
    _validate_banned_preflight_propagation(blob, enriched, dsld_id_for_validation)

    # Sprint E1.2.4 — raw-inactive preservation invariant.
    raw_inactives_count = int(enriched.get("raw_inactives_count") or 0)
    blob["raw_inactives_count"] = raw_inactives_count
    _validate_inactive_preservation(blob, raw_inactives_count, dsld_id_for_validation)

    # Sprint E1.2.5 — active-count reconciliation + reason codes.
    raw_actives_count = int(enriched.get("raw_actives_count") or 0)
    reasons = _compute_ingredients_dropped_reasons(enriched)
    # Layer in UNMAPPED signal from scored output when present.
    if safe_list(scored.get("unmapped_actives")):
        reasons = sorted(set(reasons + [_DROP_REASON_UNMAPPED]))
    blob["raw_actives_count"] = raw_actives_count
    blob["ingredients_dropped_reasons"] = reasons
    _validate_active_count_reconciliation(blob, raw_actives_count, dsld_id_for_validation)

    # Sprint E1.5.X-4 — product availability exposed as a dedicated top-level
    # field, structured so Flutter renders it in the "Consider" (soft-signal)
    # layer — NOT a safety warning, NOT a SAFE chip.
    #
    # Schema deliberately uses `type` (not `status`) so the field can grow
    # beyond discontinuation without breaking the contract. Expected future
    # values: "discontinued", "off_market", "reformulated",
    # "limited_availability", "seasonal". `display` is a pre-formatted
    # string so Flutter renders verbatim without locale-dependent date
    # formatting logic.
    #
    # Consumed by Flutter in the "⚠️ Consider" (soft signals) UI layer:
    #   • Product discontinued · Nov 28, 2017
    #   • Contains proprietary blend (from proprietary_blend_detail)
    #
    # Never styled as alert/warning/red chip. Null for active products so
    # Flutter can hide the chip entirely.
    _raw_status = normalize_text(enriched.get("status"))
    if _raw_status in ("discontinued", "off_market"):
        _disc_date = safe_str(enriched.get("discontinuedDate"))[:10] or None
        blob["product_status"] = {
            "type": _raw_status,
            "date": _disc_date,
            "display": (
                f"Discontinued · {_disc_date}" if _raw_status == "discontinued" and _disc_date
                else "Discontinued" if _raw_status == "discontinued"
                else "Off-market"
            ),
        }
    else:
        blob["product_status"] = None

    return blob


# ─── Core Row Builder ───

# ─── Export Schema v1.1.0 Enhancement Functions ───


def generate_ingredient_fingerprint(enriched: Dict) -> Dict:
    """Generate compact ingredient fingerprint for stack checking.

    Returns JSON-serializable dict with:
    - nutrients: {name: {amount, unit}}
    - herbs: [standard_names]
    - categories: [unique categories]
    - pharmacological_flags: {stimulant, sedative, blood_thinner, hormone_modulator}
    """
    fingerprint = {
        "nutrients": {},
        "herbs": [],
        "categories": set(),
        "pharmacological_flags": {
            "stimulant": False,
            "sedative": False,
            "blood_thinner": False,
            "hormone_modulator": False,
        }
    }

    iqd = safe_dict(enriched.get("ingredient_quality_data"))
    ingredients = safe_list(iqd.get("ingredients"))

    # Track pharmacological classes
    stimulants = {"caffeine", "synephrine", "bitter orange", "yohimbine", "dmaa", "ephedra"}
    sedatives = {"melatonin", "valerian", "passionflower", "lemon balm", "gaba", "5-htp"}
    blood_thinners = {"omega-3", "fish oil", "garlic", "ginkgo", "turmeric", "curcumin", "ginger", "vitamin e"}
    hormone_modulators = {"dhea", "pregnenolone", "ashwagandha", "tribulus", "maca", "fenugreek"}

    all_ingredient_names = set()

    for ing in ingredients:
        if not isinstance(ing, dict):
            continue

        standard_name = safe_str(ing.get("standard_name")).lower()
        category = safe_str(ing.get("category")).lower()

        if not standard_name:
            continue

        all_ingredient_names.add(standard_name.replace(" ", "_"))

        # Extract nutrients with doses
        if category in ["vitamins", "minerals", "amino_acids", "fatty_acids"]:
            normalized_amount = ing.get("normalized_amount") or ing.get("dosage")
            normalized_unit = safe_str(ing.get("normalized_unit") or ing.get("dosage_unit"))

            if normalized_amount is not None:
                fingerprint["nutrients"][standard_name.replace(" ", "_")] = {
                    "amount": float(normalized_amount),
                    "unit": normalized_unit,
                }

        # Track herbs
        if category in ["botanicals", "herbs", "plant_extracts"]:
            fingerprint["herbs"].append(standard_name)

        # Track categories
        if category:
            fingerprint["categories"].add(category)

    # Set pharmacological flags
    fingerprint["pharmacological_flags"]["stimulant"] = bool(all_ingredient_names & stimulants)
    fingerprint["pharmacological_flags"]["sedative"] = bool(all_ingredient_names & sedatives)
    fingerprint["pharmacological_flags"]["blood_thinner"] = bool(all_ingredient_names & blood_thinners)
    fingerprint["pharmacological_flags"]["hormone_modulator"] = bool(all_ingredient_names & hormone_modulators)

    # Convert set to list for JSON serialization
    fingerprint["categories"] = list(fingerprint["categories"])

    return fingerprint


def generate_key_nutrients_summary(enriched: Dict) -> List[Dict]:
    """Extract top 5-10 key nutrients with doses for quick display."""
    nutrients = []
    iqd = safe_dict(enriched.get("ingredient_quality_data"))
    ingredients = safe_list(iqd.get("ingredients"))

    # Priority order for display
    priority_nutrients = [
        "vitamin d", "vitamin c", "vitamin b12", "magnesium", "zinc",
        "omega-3", "iron", "calcium", "vitamin a", "vitamin e",
    ]

    for ing in ingredients:
        if not isinstance(ing, dict):
            continue

        standard_name = safe_str(ing.get("standard_name")).lower()
        category = safe_str(ing.get("category")).lower()

        if category not in ["vitamins", "minerals", "amino_acids", "fatty_acids"]:
            continue

        normalized_amount = ing.get("normalized_amount") or ing.get("dosage")
        normalized_unit = safe_str(ing.get("normalized_unit") or ing.get("dosage_unit"))

        if normalized_amount is not None:
            priority_idx = priority_nutrients.index(standard_name) if standard_name in priority_nutrients else 999
            nutrients.append({
                "name": safe_str(ing.get("standard_name")),
                "amount": float(normalized_amount),
                "unit": normalized_unit,
                "priority": priority_idx
            })

    # Sort by priority, then limit to top 10
    nutrients.sort(key=lambda x: (x["priority"], -x["amount"]))
    top_nutrients = nutrients[:10]

    # Remove priority key before export
    for n in top_nutrients:
        n.pop("priority", None)

    return top_nutrients


def generate_share_metadata(enriched: Dict, scored: Dict) -> Dict:
    """Generate social sharing metadata.

    Returns dict with keys: share_title, share_description, share_highlights, share_og_image_url
    """
    product_name = safe_str(enriched.get("product_name"))
    brand_name = safe_str(enriched.get("brandName"))
    score_100 = safe_float(scored.get("score_100_equivalent"))
    grade = safe_str(scored.get("grade"))
    verdict = safe_str(scored.get("verdict")).upper()
    section_scores = safe_dict(scored.get("section_scores"))

    # Title with score emoji
    score_emoji = ""
    if score_100:
        if score_100 >= 90:
            score_emoji = "⭐"
        elif score_100 >= 75:
            score_emoji = "✓"

    share_title = f"{brand_name} {product_name}"
    if score_100:
        share_title += f" - {int(score_100)}/100 {score_emoji}"

    # Limit title length for social platforms
    if len(share_title) > 200:
        share_title = share_title[:197] + "..."

    # Description
    positive_signals = []
    if safe_float(safe_dict(section_scores.get("C_evidence_research")).get("score"), 0) >= 15:
        positive_signals.append("clinically-backed")
    if safe_list(enriched.get("named_cert_programs")):
        positive_signals.append("third-party tested")
    # Dietary signals come from compliance_data (the canonical source for
    # vegan / gluten_free / etc. flags). dietary_sensitivity_data carries
    # only sugar / sodium per `_collect_dietary_sensitivity_data` and never
    # had `vegan` or `gluten_free` populated — the prior reads against
    # `dietary_sensitivity_data` were silently always-false dead paths.
    if safe_dict(enriched.get("compliance_data")).get("vegan"):
        positive_signals.append("vegan")

    share_description = f"A {grade.lower()} quality supplement"
    if positive_signals:
        share_description += f" with {', '.join(positive_signals[:2])}"
    share_description += ". Analyzed by PharmaGuide for safety, purity, and evidence."

    if len(share_description) > 300:
        share_description = share_description[:297] + "..."

    # Highlights (top 3-4 positive attributes)
    highlights = []

    # Top ingredient quality insight
    formulation = safe_dict(enriched.get("formulation_detail"))
    delivery_tier = safe_str(formulation.get("delivery_tier"))
    if delivery_tier in ["premium", "enhanced"]:
        highlights.append(f"Premium {delivery_tier} formulation")

    # Clinical evidence
    evidence_matched = safe_dict(section_scores.get("C_evidence_research")).get("matched_entries", 0)
    if evidence_matched > 0:
        highlights.append("Clinically-backed ingredients")

    # Certifications
    certs = safe_list(enriched.get("named_cert_programs"))
    if certs:
        highlights.append(" • ".join(str(c) for c in certs[:3]))

    # Dietary highlights — same canonical source as the description above.
    # The earlier `ds.get("gluten_free") or compliance.gluten_free` guard
    # was defensive only on paper; `dietary_sensitivity_data` never carries
    # `gluten_free`, so the OR was permanently a no-op falling through to
    # `compliance_data`. Reading compliance_data directly removes the
    # cargo-cult double-check.
    dietary_flags = []
    compliance = safe_dict(enriched.get("compliance_data"))
    if compliance.get("vegan"):
        dietary_flags.append("Vegan")
    if compliance.get("gluten_free"):
        dietary_flags.append("Gluten-Free")
    if dietary_flags:
        highlights.append(" • ".join(dietary_flags))

    # Safety
    if not safe_list(enriched.get("harmful_additives")):
        highlights.append("No harmful additives")

    return {
        "share_title": share_title,
        "share_description": share_description,
        "share_highlights": highlights[:4],  # Max 4 highlights
        "share_og_image_url": safe_str(enriched.get("imageUrl")),  # Use product image for now
    }


def classify_product_categories(enriched: Dict, scored: Optional[Dict] = None) -> Dict:
    """Classify product into primary/secondary categories and set boolean flags.

    Returns dict with keys: primary_category, secondary_categories, contains_*, key_ingredient_tags
    """
    iqd = safe_dict(enriched.get("ingredient_quality_data"))
    ingredients = safe_list(iqd.get("ingredients"))

    omega3_audit = derive_omega3_audit(enriched, scored)

    # Extract ingredient names
    ingredient_names = set()
    for ing in ingredients:
        if isinstance(ing, dict):
            name = safe_str(ing.get("standard_name") or ing.get("name")).lower().replace(" ", "_")
            if name:
                ingredient_names.add(name)
            canonical_id = safe_str(ing.get("canonical_id") or ing.get("parent_key")).lower().replace(" ", "_")
            if canonical_id:
                ingredient_names.add(canonical_id)

    # Primary category detection
    primary_category = None
    supp_type = resolve_export_supplement_type(enriched, scored)

    if supp_type == "probiotic":
        primary_category = "probiotic"
    elif omega3_audit["contains_omega3"]:
        primary_category = "omega-3"
    elif any(name in ingredient_names for name in ["collagen", "collagen_peptides"]):
        primary_category = "collagen"
    elif len(ingredients) >= 10:  # Heuristic for multivitamin
        primary_category = "multivitamin"
    elif any(name in ingredient_names for name in ["protein", "whey_protein", "casein"]):
        primary_category = "protein"

    # Secondary categories
    secondary_categories = []

    adaptogens = {"ashwagandha", "rhodiola", "holy_basil", "ginseng", "maca", "reishi"}
    nootropics = {"lion's_mane", "bacopa", "ginkgo", "alpha-gpc", "l-theanine", "citicoline"}

    if ingredient_names & adaptogens:
        secondary_categories.append("adaptogen")
    if ingredient_names & nootropics:
        secondary_categories.append("nootropic")

    # Check synergy clusters for more categories
    synergy_detail = safe_dict(enriched.get("synergy_detail"))
    clusters_matched = safe_list(synergy_detail.get("clusters_matched"))
    for cluster in clusters_matched:
        cluster_str = safe_str(cluster).lower()
        if "inflammation" in cluster_str or "joint" in cluster_str:
            secondary_categories.append("anti-inflammatory")
        if "cardiovascular" in cluster_str or "heart" in cluster_str:
            secondary_categories.append("heart-health")
        if "immune" in cluster_str:
            secondary_categories.append("immune-support")

    # Boolean flags
    contains_omega3 = omega3_audit["contains_omega3"]
    contains_probiotics = supp_type == "probiotic" or bool(
        safe_dict(enriched.get("probiotic_data")).get("is_probiotic_product")
    )
    contains_collagen = any(name in ingredient_names for name in ["collagen", "collagen_peptides"])
    contains_adaptogens = bool(ingredient_names & adaptogens)
    contains_nootropics = bool(ingredient_names & nootropics)

    # Key ingredient tags (top 5 most important)
    key_tags = []
    priority_ingredients = [
        "ashwagandha", "magnesium", "vitamin_d", "omega-3", "curcumin",
        "probiotics", "collagen", "vitamin_c", "zinc", "ginkgo"
    ]
    for priority in priority_ingredients:
        if priority in ingredient_names:
            key_tags.append(priority)
        if len(key_tags) >= 5:
            break

    return {
        "primary_category": primary_category,
        "secondary_categories": list(set(secondary_categories)),
        "contains_omega3": contains_omega3,
        "contains_probiotics": contains_probiotics,
        "contains_collagen": contains_collagen,
        "contains_adaptogens": contains_adaptogens,
        "contains_nootropics": contains_nootropics,
        "key_ingredient_tags": key_tags,
        "omega3_audit": omega3_audit,
    }


_GOAL_MAPPINGS_CACHE: Optional[List[Dict[str, Any]]] = None


def _load_goal_mappings() -> List[Dict[str, Any]]:
    """Load and cache goal-mapping contract (schema v6.0.0)."""
    global _GOAL_MAPPINGS_CACHE
    if _GOAL_MAPPINGS_CACHE is not None:
        return _GOAL_MAPPINGS_CACHE
    try:
        goals_path = Path(__file__).parent / "data" / "user_goals_to_clusters.json"
        with open(goals_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        mappings = safe_list(data.get("user_goal_mappings"))
    except Exception as exc:
        logger.warning("Failed to load user_goals_to_clusters.json: %s", exc)
        mappings = []
    _GOAL_MAPPINGS_CACHE = mappings
    return mappings


def _extract_product_cluster_ids(enriched: Dict) -> set:
    """Flatten product cluster IDs from the enrichment output.

    Source of truth from ``enrich_supplements_v3.py``:
      ``enriched["formulation_data"]["synergy_clusters"]`` is a list of cluster
      dicts each containing ``cluster_id`` (e.g. ``"sleep_stack"``).

    Dose-adequacy gate: a cluster counts toward goal matching only when at
    least one of its ``matched_ingredients`` meets the ingredient's minimum
    effective dose (``meets_minimum``). This prevents trace-mineral
    over-matching from promoting clusters to goals — e.g. 17 mg of magnesium
    in a whey protein powder must not earn the product a "Sleep Quality"
    match, because the sleep-effective magnesium dose is ~200 mg. Clusters
    without dose data (no ``matched_ingredients`` key, or all entries with
    ``meets_minimum`` missing/null) pass through — legacy shape tolerance.

    Also tolerates a ``synergy_detail.clusters_matched`` flat list if present
    (legacy/alternate path), so callers can feed either the raw enrichment
    object or the post-build detail blob.

    Returns a deduplicated set of non-empty cluster ID strings.
    """
    ids: set = set()

    def _cluster_has_adequate_dose(cluster: Dict) -> bool:
        """True iff the cluster has no dose data, OR at least one matched
        ingredient meets its minimum effective dose."""
        matched = cluster.get("matched_ingredients")
        if not isinstance(matched, list) or not matched:
            # No per-ingredient data → trust the cluster (legacy tolerance).
            return True
        has_dose_info = False
        for m in matched:
            if not isinstance(m, dict):
                continue
            meets = m.get("meets_minimum")
            if meets is None:
                continue
            has_dose_info = True
            if bool(meets):
                return True
        # Rich dose data present and no match was adequate → filter out.
        # If dose data is absent across all matches, be lenient.
        return not has_dose_info

    # Primary path: formulation_data.synergy_clusters[*].cluster_id
    formulation = safe_dict(enriched.get("formulation_data"))
    for cluster in safe_list(formulation.get("synergy_clusters")):
        if isinstance(cluster, dict):
            cid = safe_str(cluster.get("cluster_id"))
            if not cid:
                continue
            if not _cluster_has_adequate_dose(cluster):
                continue
            ids.add(cid)

    # Fallback path: synergy_detail.clusters_matched (flat list) OR
    #                synergy_detail.clusters[*].id (detail-blob shape)
    synergy_detail = safe_dict(enriched.get("synergy_detail"))
    for cluster in safe_list(synergy_detail.get("clusters_matched")):
        cid = safe_str(cluster)
        if cid:
            ids.add(cid)
    for cluster in safe_list(synergy_detail.get("clusters")):
        if isinstance(cluster, dict):
            cid = safe_str(cluster.get("id") or cluster.get("cluster_id"))
            if not cid:
                continue
            if not _cluster_has_adequate_dose(cluster):
                continue
            ids.add(cid)

    return ids


def compute_goal_matches(enriched: Dict) -> Dict:
    """Pre-compute which goals this product matches based on synergy clusters.

    Contract (schema v6.0.0 — pipeline-owned, Flutter consumes results only):
      * Reads product cluster IDs from the enrichment output
        (primary: ``formulation_data.synergy_clusters[*].cluster_id``;
        fallback: ``synergy_detail.clusters_matched`` or
        ``synergy_detail.clusters[*].id``).
      * For each goal in ``user_goal_mappings``:
          - Skip if ANY of ``blocked_by_clusters`` is present in product clusters.
          - Skip if ``required_clusters`` is non-empty AND none are present.
          - ``score = matched_weight / max_weight`` (normalized 0.0..1.0).
          - Include goal iff ``score >= min_match_score``.
      * Output ``goal_matches`` (list of goal IDs) + ``goal_match_confidence``
        (average matched score, rounded to 2 decimals).

    Returns dict with keys: ``goal_matches``, ``goal_match_confidence``.
    """
    goal_mappings = _load_goal_mappings()
    if not goal_mappings:
        return {"goal_matches": [], "goal_match_confidence": 0.0}

    product_clusters = _extract_product_cluster_ids(enriched)

    if not product_clusters:
        return {"goal_matches": [], "goal_match_confidence": 0.0}

    matched_goals: List[str] = []
    matched_scores: List[float] = []

    for goal_mapping in goal_mappings:
        if not isinstance(goal_mapping, dict):
            continue

        goal_id = safe_str(goal_mapping.get("id"))
        if not goal_id:
            continue

        cluster_weights = safe_dict(goal_mapping.get("cluster_weights"))
        if not cluster_weights:
            continue

        required = {safe_str(c) for c in safe_list(goal_mapping.get("required_clusters")) if safe_str(c)}
        blocked = {safe_str(c) for c in safe_list(goal_mapping.get("blocked_by_clusters")) if safe_str(c)}
        min_score = safe_float(goal_mapping.get("min_match_score"), 0.5)

        # Gate 1: blocked clusters disqualify regardless of score
        if blocked and (product_clusters & blocked):
            continue

        # Gate 2: required clusters must have at least one present (when list is non-empty)
        if required and not (product_clusters & required):
            continue

        # Gate 3: normalized weighted score must meet threshold.
        # We compute TWO ratios and use the more generous one:
        #
        #   score_full     = matched_weight / max_weight
        #     Rewards multivitamins for breadth — products covering many of
        #     the goal's cluster_weights score high.
        #
        #   score_required = matched_required_weight / max_required_weight
        #     Rewards focused single-purpose supplements — a DHA-only product
        #     that hits the only required cluster (prenatal_pregnancy_support)
        #     scores 1.0 even though it only covers a narrow slice of the
        #     full goal profile. Without this, single-ingredient overrides
        #     fire at the cluster level but never propagate to a goal match.
        #
        # Take the max — both signals are valid expressions of "this product
        # serves this goal". Both still respect the same min_match_score
        # threshold, so noise gets filtered.
        max_weight = sum(safe_float(w, 0.0) for w in cluster_weights.values())
        if max_weight <= 0.0:
            continue
        matched_weight = sum(
            safe_float(cluster_weights.get(c), 0.0)
            for c in product_clusters
            if c in cluster_weights
        )
        score_full = matched_weight / max_weight

        if required:
            # Use MAX (not SUM) of required weights. Rationale: when a goal
            # declares multiple required clusters (e.g. GOAL_DIGESTIVE_HEALTH
            # requires gut_barrier OR probiotic_and_gut_health OR
            # digestive_enzymes), a single-purpose probiotic that covers
            # probiotic_and_gut_health at full weight should score 1.0 on
            # the required axis — not 0.34 (which is what SUM would give,
            # under-matching every probiotic against digestive).
            #
            # Any-present semantics is already the gate (Gate 2). The score
            # should reflect "how strongly does the BEST matched required
            # cluster represent this goal" — i.e. does the product cover the
            # single most goal-relevant required cluster at its full weight?
            # MAX answers that directly. This also aligns with the
            # single-ingredient-override design: a DHA-only product earning
            # prenatal_pregnancy_support (the one required cluster) should
            # score 1.0 for PRENATAL.
            required_weights = [
                safe_float(cluster_weights.get(c), 0.0) for c in required
            ]
            matched_required_weights = [
                safe_float(cluster_weights.get(c), 0.0)
                for c in product_clusters
                if c in required
            ]
            max_single_required = max(required_weights) if required_weights else 0.0
            best_matched_required = (
                max(matched_required_weights) if matched_required_weights else 0.0
            )
            score_required = (
                best_matched_required / max_single_required
                if max_single_required > 0.0
                else 0.0
            )
        else:
            score_required = score_full

        score = max(score_full, score_required)

        if score >= min_score:
            matched_goals.append(goal_id)
            matched_scores.append(score)

    if matched_goals:
        avg_confidence = sum(matched_scores) / len(matched_scores)
    else:
        avg_confidence = 0.0

    return {
        "goal_matches": matched_goals,
        "goal_match_confidence": round(avg_confidence, 2),
    }


def _format_quantity(value: Any) -> str:
    """Render a numeric quantity without trailing .0 when it is a whole number."""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return safe_str(value)
    if not _math.isfinite(num):
        return ""
    if num == int(num):
        return str(int(num))
    return ("%g" % num)


def _derive_serving_verb_and_noun(unit: str, form_factor: str) -> tuple[str, str, str]:
    """Pick a verb ("Take"/"Chew"/"Mix"), singular noun, and plural noun.

    Checks the servingSizes unit FIRST (most specific), then falls back to
    form_factor. Order matters: more specific matches must come before broader
    ones (e.g. "gram" must be checked before "powder", which is only a fallback).
    """
    unit_l = (unit or "").lower()
    form_l = (form_factor or "").lower()

    def has(needle: str, haystack: str = None) -> bool:
        if haystack is None:
            return needle in unit_l or needle in form_l
        return needle in haystack

    # Most specific unit-driven cases first.
    if has("gummy") or has("gummie"):
        return ("Chew", "gummy", "gummies")
    if has("chewable"):
        return ("Chew", "chewable", "chewables")
    if has("lozenge") or has("troche"):
        return ("Dissolve", "lozenge", "lozenges")
    if has("softgel") or has("gelcap") or has("soft gel"):
        return ("Take", "softgel", "softgels")
    if has("liquicap") or has("liquid cap"):
        return ("Take", "liquicap", "liquicaps")
    if has("capsule"):
        return ("Take", "capsule", "capsules")
    if has("caplet"):
        return ("Take", "caplet", "caplets")
    if has("tablet"):
        return ("Take", "tablet", "tablets")
    if has("packet") or has("sachet") or has("stick pack"):
        return ("Mix", "packet", "packets")
    if has("drop"):
        return ("Take", "drop", "drops")
    if has("spray"):
        return ("Use", "spray", "sprays")
    if has("patch"):
        return ("Apply", "patch", "patches")
    # Liquid/volume units — "mL" is a constant label.
    if (
        "ml" in unit_l
        or "milliliter" in unit_l
        or "teaspoon" in unit_l
        or "tablespoon" in unit_l
        or "fl oz" in unit_l
        or "fl. oz" in unit_l
        or "fluid ounce" in unit_l
    ) or has("liquid"):
        return ("Take", "mL", "mL")
    # Weight units (grams) — must come before powder/scoop fallback.
    if (
        "gram" in unit_l
        or unit_l.strip() in ("g", "g.", "mg")
        or unit_l.strip().endswith(" g")
    ):
        return ("Mix", "gram", "grams")
    # Scoop is a unit; powder is a form_factor fallback.
    if has("scoop") or has("powder"):
        return ("Mix", "scoop", "scoops")
    return ("Take", "serving", "servings")


def _frequency_phrase(max_daily: Optional[int]) -> str:
    """Map maxDailyServings to a human cadence."""
    if max_daily is None:
        return "daily"
    try:
        n = int(max_daily)
    except (TypeError, ValueError):
        return "daily"
    if n <= 1:
        return "daily"
    if n == 2:
        return "twice daily"
    if n == 3:
        return "three times daily"
    if n == 4:
        return "four times daily"
    return f"{n} times daily"


def generate_dosing_summary(enriched: Dict) -> Dict:
    """Generate user-friendly dosing summary and servings per container.

    Reads the real cleaner-emitted fields (enhanced_normalizer._process_serving_sizes
    and raw_data.servingsPerContainer) rather than a nonexistent "serving_info" path:

      - enriched["servingsPerContainer"]  (int)
      - enriched["servingSizes"]          (list[dict]: minQuantity, maxQuantity,
                                           unit, minDailyServings, maxDailyServings,
                                           normalizedServing, ...)
      - enriched["form_factor"]           (str, e.g. "capsule", "powder")

    Returns dict with keys: dosing_summary, servings_per_container
    """
    serving_sizes = safe_list(enriched.get("servingSizes"))
    serving = safe_dict(serving_sizes[0]) if serving_sizes else {}
    form_factor = safe_str(enriched.get("form_factor")).lower()

    min_qty_raw = serving.get("minQuantity")
    max_qty_raw = serving.get("maxQuantity")
    unit = safe_str(serving.get("unit"))
    max_daily = serving.get("maxDailyServings")

    min_qty = safe_float(min_qty_raw)
    max_qty = safe_float(max_qty_raw)

    if min_qty is None and max_qty is None:
        # No usable quantity data — graceful fallback.
        summary = "See product label"
    else:
        # If only one of min/max is present, use whichever is there.
        if min_qty is None:
            min_qty = max_qty
        if max_qty is None:
            max_qty = min_qty

        verb, noun_singular, noun_plural = _derive_serving_verb_and_noun(unit, form_factor)

        if min_qty == max_qty:
            qty_text = _format_quantity(min_qty)
            noun = noun_singular if min_qty == 1 else noun_plural
        else:
            qty_text = f"{_format_quantity(min_qty)}-{_format_quantity(max_qty)}"
            noun = noun_plural

        cadence = _frequency_phrase(max_daily)
        summary = f"{verb} {qty_text} {noun} {cadence}".strip()

    # Limit length defensively.
    if len(summary) > 150:
        summary = summary[:147] + "..."

    servings_per = enriched.get("servingsPerContainer")
    servings_per_int: Optional[int]
    try:
        servings_per_int = int(servings_per) if servings_per is not None else None
    except (TypeError, ValueError):
        servings_per_int = None

    return {
        "dosing_summary": summary,
        "servings_per_container": servings_per_int,
    }


def generate_net_contents_summary(enriched: Dict) -> Dict:
    """Extract primary netContents quantity + unit for refill-reminder features.

    Cleaner-emitted shape (enhanced_normalizer._extract_net_contents):
        enriched["netContents"] = [
            {"order": 1, "quantity": 90, "unit": "Capsule(s)", "display": "..."},
            ...
        ]

    We read index [0] as the primary entry and pass the unit through unchanged
    (do NOT lowercase — the app renders this verbatim).
    """
    contents = safe_list(enriched.get("netContents"))
    if not contents:
        return {"net_contents_quantity": None, "net_contents_unit": None}

    primary = safe_dict(contents[0])
    quantity = safe_float(primary.get("quantity"))
    unit_raw = primary.get("unit")
    unit = str(unit_raw).strip() if unit_raw is not None else None
    if unit == "":
        unit = None

    return {
        "net_contents_quantity": quantity,
        "net_contents_unit": unit,
    }


def build_structured_allergens(enriched: Dict) -> List[Dict]:
    """Phase 8: structured per-allergen array for client-side personalization.

    The legacy `warnings[]` array carries display-ready strings for the
    generic AllergenSummaryBanner; this array is the structured contract
    for Flutter's personalized allergen matcher (matchAllergens against
    profile.allergens). Exact `allergen_id` matching only — no substring.

    Sort: presence_type priority (contains → may_contain →
    manufactured_in_facility) so callers can render the most actionable
    rows first without re-sorting.
    """
    presence_priority = {
        "contains": 0,
        "may_contain": 1,
        "manufactured_in_facility": 2,
    }
    severity_priority = {"high": 0, "moderate": 1, "low": 2}
    out: List[Dict] = []
    for hit in safe_list(enriched.get("allergen_hits")):
        if not isinstance(hit, dict):
            continue
        allergen_id = safe_str(hit.get("allergen_id"))
        if not allergen_id:
            continue
        out.append({
            "allergen_id": allergen_id,
            "display_name": safe_str(
                hit.get("allergen_name") or hit.get("standard_name")
            ),
            "presence_type": safe_str(hit.get("presence_type"), "contains"),
            "severity_level": safe_str(hit.get("severity_level"), "moderate"),
            "evidence": safe_str(hit.get("evidence")),
        })
    out.sort(key=lambda x: (
        presence_priority.get(x["presence_type"], 99),
        severity_priority.get(x["severity_level"], 99),
    ))
    return out


def generate_allergen_summary(enriched: Dict) -> str:
    """Generate allergen summary string.

    Returns: "Contains: Soy, Tree Nuts" or None
    """
    allergen_hits = safe_list(enriched.get("allergen_hits"))

    if not allergen_hits:
        return None

    allergen_names = []
    for hit in allergen_hits:
        if isinstance(hit, dict):
            name = safe_str(hit.get("standard_name"))
            if name:
                allergen_names.append(name)

    if not allergen_names:
        return None

    return f"Contains: {', '.join(allergen_names)}"


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
    st_str = resolve_export_supplement_type(enriched, scored)
    sm = safe_dict(scored.get("scoring_metadata"))

    disc_date = safe_str(enriched.get("discontinuedDate"))[:10] or None
    score_80 = safe_float(scored.get("score_80"))
    score_100 = safe_float(scored.get("score_100_equivalent"))

    top_warnings = build_top_warnings(enriched)

    # Inject B8 CAERS adverse event warnings from scored output
    b8_evidence = safe_list(
        safe_dict(safe_dict(scored.get("breakdown", {})).get("B", {})).get("B8_caers_evidence")
    )
    for ev in b8_evidence:
        if not isinstance(ev, dict):
            continue
        ing = safe_str(ev.get("ingredient"))
        serious = ev.get("serious_reports", 0)
        total = ev.get("total_reports", 0)
        strength = safe_str(ev.get("signal_strength"))
        if strength in ("strong", "moderate"):
            top_warnings.append(
                f"FDA adverse events: {ing.replace('_', ' ').title()} "
                f"({serious} serious of {total} reports)"
            )

    blocking = derive_blocking_reason(enriched, scored)
    interaction_hint = build_interaction_summary_hint(enriched)
    decision_highlights = build_decision_highlights(enriched, scored, blocking)
    _validate_decision_highlights(decision_highlights, safe_str(enriched.get("dsld_id")))

    # ─── v1.1.0 Enhancements ───
    fingerprint = generate_ingredient_fingerprint(enriched)
    key_nutrients = generate_key_nutrients_summary(enriched)
    share_meta = generate_share_metadata(enriched, scored)
    categories = classify_product_categories(enriched, scored)
    goal_data = compute_goal_matches(enriched)
    dosing = generate_dosing_summary(enriched)
    net_contents = generate_net_contents_summary(enriched)
    allergen_summ = generate_allergen_summary(enriched)
    non_gmo_audit = derive_non_gmo_audit(enriched)

    return (
        safe_str(enriched.get("dsld_id")),
        safe_str(enriched.get("product_name")),
        safe_str(enriched.get("brandName")),
        normalize_upc(enriched.get("upcSku")),
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
        safe_bool(non_gmo_audit["project_verified"]),
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
        # ── v1.1.0 Additions ──
        # Enhancement 1: Stack Interaction
        json.dumps(fingerprint, ensure_ascii=False),
        json.dumps(key_nutrients, ensure_ascii=False),
        safe_bool(fingerprint["pharmacological_flags"]["stimulant"]),
        safe_bool(fingerprint["pharmacological_flags"]["sedative"]),
        safe_bool(fingerprint["pharmacological_flags"]["blood_thinner"]),
        # Enhancement 2: Social Sharing
        share_meta["share_title"],
        share_meta["share_description"],
        json.dumps(share_meta["share_highlights"], ensure_ascii=False),
        share_meta["share_og_image_url"] or None,
        # Enhancement 3: Search & Filter
        categories["primary_category"],
        json.dumps(categories["secondary_categories"], ensure_ascii=False),
        safe_bool(categories["contains_omega3"]),
        safe_bool(categories["contains_probiotics"]),
        safe_bool(categories["contains_collagen"]),
        safe_bool(categories["contains_adaptogens"]),
        safe_bool(categories["contains_nootropics"]),
        json.dumps(categories["key_ingredient_tags"], ensure_ascii=False),
        # Enhancement 4: Goal Matching
        json.dumps(goal_data["goal_matches"], ensure_ascii=False),
        goal_data["goal_match_confidence"],
        # Enhancement 5: Dosing
        dosing["dosing_summary"],
        dosing["servings_per_container"],
        net_contents["net_contents_quantity"],
        net_contents["net_contents_unit"],
        # Enhancement 6: Allergen
        allergen_summ,
        # v1.3.2: Nutrition column
        safe_float(safe_dict(enriched.get("nutrition_summary")).get("calories_per_serving")),
        # v1.4.0: Image thumbnail URL (populated post-build via backfill)
        None,  # image_thumbnail_url
        # Metadata
        safe_str(sm.get("scoring_version")),
        safe_str(sm.get("output_schema_version", scored.get("output_schema_version"))),
        safe_str(enriched.get("enrichment_version")),
        safe_str(sm.get("scored_date")),
        str(EXPORT_SCHEMA_VERSION),
        exported_at,
    )


CORE_COLUMN_COUNT = 91  # Must match the tuple above and SCHEMA_SQL


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


# ─── Image Thumbnail Backfill ───


def backfill_image_thumbnails(db_path: str, image_dir: str) -> dict:
    """Populate image_thumbnail_url for products with extracted WebP thumbnails.

    Called after extract_product_images.py produces the product_images/ directory.
    Safe to call multiple times (idempotent UPDATE).

    Returns dict with updated and missing counts.
    """
    index_path = os.path.join(image_dir, "product_image_index.json")
    if not os.path.exists(index_path):
        logger.info("No product_image_index.json found at %s — skipping thumbnail backfill", image_dir)
        return {"updated": 0, "missing": 0}

    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)

    conn = sqlite3.connect(db_path)
    try:
        updated = 0
        for dsld_id, entry in index.items():
            webp_file = os.path.join(image_dir, entry["filename"])
            if os.path.exists(webp_file):
                conn.execute(
                    "UPDATE products_core SET image_thumbnail_url = ? WHERE dsld_id = ?",
                    (f"product-images/{dsld_id}.webp", str(dsld_id)),
                )
                updated += 1
        conn.commit()
    finally:
        conn.close()

    missing = len(index) - updated
    logger.info("Thumbnail backfill: %d updated, %d missing files", updated, missing)
    return {"updated": updated, "missing": missing}


# ─── Main Builder ───

def build_final_db(
    enriched_dirs: List[str],
    scored_dirs: List[str],
    output_dir: str,
    script_dir: str,
    strict: bool = False,
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
        # Sprint E1.5 — split export-failure streams so the Supabase sync
        # gate only blocks on catastrophic failures (errors[]) and not on
        # by-design exclusions (excluded_by_gate[]) or authoring
        # backlog (warnings[]). See _classify_export_error above.
        excluded_by_gate_count = 0
        excluded_by_gate_details: List[Dict[str, str]] = []
        export_warning_count = 0
        export_warning_details: List[Dict[str, str]] = []
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
                msg = str(e)
                bucket = _classify_export_error(msg)
                entry = {"dsld_id": str(pid), "error": msg}
                if bucket == "excluded_by_gate":
                    # By-design coverage gate (E1.2.5). Product correctly
                    # excluded; pipeline is working as intended.
                    logger.warning("Product %s excluded by gate: %s", pid, msg)
                    excluded_by_gate_count += 1
                    excluded_by_gate_details.append(entry)
                elif bucket == "warning":
                    # Content-quality issue (tone authoring backlog).
                    # Product excluded but flagged for Dr Pham, not a bug.
                    logger.warning("Product %s quality warning: %s", pid, msg)
                    export_warning_count += 1
                    export_warning_details.append(entry)
                else:
                    # Catastrophic — schema drift, unknown enum leak, etc.
                    # BLOCKS the Supabase sync gate. Must be fixed.
                    logger.error("Product %s failed: %s", pid, e, exc_info=True)
                    errors += 1
                    error_details.append(entry)

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

        # ── Pipeline integrity gate ──
        enriched_only_count = audit_counts["enriched_only"]
        total_input = enriched_unique
        total_skipped = enriched_only_count + scored_only_count + errors
        coverage_pct = (inserted / total_input * 100) if total_input else 0

        if strict and (enriched_only_count > 0 or scored_only_count > 0):
            raise ValueError(
                f"Strict mode: pipeline mismatch detected. "
                f"{enriched_only_count} enriched-only, {scored_only_count} scored-only. "
                f"All products must be both enriched AND scored before shipping."
            )

        logger.info(
            "Inserted %d products, %d errors, %d skipped (%.1f%% coverage)",
            inserted, errors, total_skipped, coverage_pct,
        )
    finally:
        stage_conn.close()
        if os.path.exists(stage_db_path):
            os.remove(stage_db_path)

    # ── UPC dedup: collapse same-barcode duplicates ──
    # DSLD registers the same physical product multiple times across years.
    # Keep the best row per UPC (active, highest score, newest id).
    # Passing detail_dir lets dedup unlink the losers' blob files so the
    # Supabase sync gate's len(blobs)==product_count invariant holds.
    dedup_result = dedup_by_upc(conn, detail_index, Path(detail_dir))
    if dedup_result["duplicates_removed"]:
        inserted -= dedup_result["duplicates_removed"]
        logger.info(
            "UPC dedup: removed %d duplicates across %d UPC groups "
            "(kept best per group); %d orphan blob files unlinked",
            dedup_result["duplicates_removed"],
            dedup_result["upc_groups_deduped"],
            dedup_result.get("orphan_blob_files_removed", 0),
        )
    audit_counts["upc_dedup"] = dedup_result

    # ── UPC overrides: backfill manually curated barcodes ──
    upc_override_path = os.path.join(
        script_dir, "data", "curated_overrides", "upc_overrides.json"
    )
    if os.path.exists(upc_override_path):
        with open(upc_override_path, encoding="utf-8") as _uf:
            upc_data = json.load(_uf)
        upc_overrides = upc_data.get("overrides", {})
        upc_applied = 0
        for dsld_id, entry in upc_overrides.items():
            upc_val = normalize_upc(entry.get("upc", ""))
            if not upc_val:
                continue
            # Only backfill if the product exists and has no UPC
            existing = c.execute(
                "SELECT upc_sku FROM products_core WHERE dsld_id = ?",
                (dsld_id,),
            ).fetchone()
            if existing is not None and (
                not existing[0] or existing[0].strip() == ""
            ):
                c.execute(
                    "UPDATE products_core SET upc_sku = ? WHERE dsld_id = ?",
                    (upc_val, dsld_id),
                )
                upc_applied += 1
        conn.commit()
        if upc_applied:
            logger.info(
                "UPC overrides: backfilled %d/%d products from curated_overrides/upc_overrides.json",
                upc_applied,
                len(upc_overrides),
            )
        audit_counts["upc_overrides_applied"] = upc_applied

    # Create read-path indexes after bulk insert to avoid incremental index churn.
    c.executescript(CORE_INDEX_SQL)

    # FTS sync
    c.executescript(FTS_SQL)
    c.execute("INSERT INTO products_fts(products_fts) VALUES ('rebuild')")

    # Reference data
    ref_rows = load_reference_data(script_dir)

    # Scoring config fingerprint for build reproducibility
    scoring_config_path = os.path.join(script_dir, "config", "scoring_config.json")
    scoring_config_checksum = None
    if os.path.exists(scoring_config_path):
        scoring_config_checksum = f"sha256:{compute_file_sha256(scoring_config_path)}"

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

    # Defensive sweep: NOT_SCORED products MUST NOT reach products_core per
    # validate_export_contract() review-queue gate (line 389). This sweep
    # cleans any stale rows left from builds that pre-date the gate, in case
    # the source product no longer appears in the current input batch (so
    # the per-product DELETE at line 4341 wouldn't fire). Sweep is logged
    # and counted in the manifest for observability.
    not_scored_swept = c.execute(
        "DELETE FROM products_core WHERE verdict = ?",
        ("NOT_SCORED",),
    ).rowcount
    if not_scored_swept > 0:
        logger.warning(
            "Defensive sweep removed %d stale NOT_SCORED rows from products_core "
            "(per review-queue gate; expected from pre-gate builds)",
            not_scored_swept,
        )
        c.execute(
            "INSERT OR REPLACE INTO export_manifest VALUES (?,?)",
            ("not_scored_swept_count", str(not_scored_swept)),
        )

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
        # Post-dedup unique hash count. `unique_blob_hashes` was built during
        # staging (pre UPC dedup) so it includes hashes for products that
        # were later removed as duplicates. Recompute from the surviving
        # detail_index so the Supabase sync's len(unique_blobs)==manifest
        # invariant holds.
        "detail_blob_unique_count": len({
            entry["blob_sha256"] for entry in detail_index.values()
        }),
        "detail_index_checksum": f"sha256:{detail_index_checksum}",
        "min_app_version": MIN_APP_VERSION,
        "schema_version": EXPORT_SCHEMA_VERSION,
        "scoring_config_checksum": scoring_config_checksum,
        # Pipeline integrity signals
        "integrity": {
            "enriched_input_count": enriched_unique,
            "scored_input_count": scored_unique,
            "exported_count": inserted,
            # Sprint E1.5 — split error classification. `error_count` is
            # the BLOCKING count (catastrophic failures); sync gate reads
            # manifest["errors"] which mirrors this. Excluded-by-gate and
            # warnings are non-blocking, tracked separately for audit.
            "error_count": errors,
            "excluded_by_gate_count": excluded_by_gate_count,
            "warning_count": export_warning_count,
            "total_skipped": errors + excluded_by_gate_count + export_warning_count,
            "enriched_only_count": audit_counts.get("enriched_only", 0),
            "scored_only_count": audit_counts.get("scored_only", 0),
            "skipped_count": (
                audit_counts.get("enriched_only", 0)
                + audit_counts.get("scored_only", 0)
                + errors
                + excluded_by_gate_count
                + export_warning_count
            ),
            "coverage_pct": round((inserted / enriched_unique * 100) if enriched_unique else 0, 2),
            "strict_mode": strict,
            "verdict_blocked": audit_counts.get("verdict_blocked", 0),
            "verdict_unsafe": audit_counts.get("verdict_unsafe", 0),
            "verdict_not_scored": audit_counts.get("verdict_not_scored", 0),
            "has_banned_substance": audit_counts.get("has_banned_substance", 0),
            "has_recalled_ingredient": audit_counts.get("has_recalled_ingredient", 0),
            "contract_failures": audit_counts.get("export_contract_invalid", 0),
            "scoring_config_checksum": scoring_config_checksum,
        },
        # Sprint E1.5 — three-bucket error classification. Sync gate
        # reads `errors[]` only. See _EXPORT_ERROR_TAXONOMY for the
        # pattern-matching rules that route raised ValueErrors here.
        "errors": error_details,
        "excluded_by_gate": excluded_by_gate_details,
        "warnings": export_warning_details,
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
    parser.add_argument("--strict", action="store_true",
                        help="Fail build if any enriched/scored mismatch (production mode)")
    args = parser.parse_args()

    script_dir = str(Path(__file__).parent)
    result = build_final_db(
        args.enriched_dir, args.scored_dir, args.output_dir, script_dir,
        strict=args.strict,
    )

    print(f"\nDone. {result['product_count']} products, {result['error_count']} errors.")
    print(f"DB: {result['db_path']} ({result['db_size_mb']} MB)")


if __name__ == "__main__":
    main()
