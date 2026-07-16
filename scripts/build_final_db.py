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
import sys
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
from audit_identity_integrity import audit_product
from inactive_ingredient_resolver import InactiveIngredientResolver
from identity.safety import (
    has_explicit_form_evidence,
    normalize_safety_source,
    safety_flag_matches_status,
    top_safety_flag as _canonical_top_safety_flag,
)
from identity.interaction import (
    interaction_tags_from_text,
    normalize_catalog_interaction_tag,
)
from scoring_input_contract import get_scoring_ingredients
from identity_integrity import is_identity_scoreable
from scoring_v4.modules.fiber_digestive_helpers import (
    fiber_rows as _fiber_goal_rows,
    has_fiber_context as _has_fiber_goal_context,
    nutrition_fiber_grams as _nutrition_fiber_goal_grams,
    total_fiber_grams as _total_fiber_goal_grams,
)
from scoring_v4.modules.generic_formulation import _dietary_sugar_penalty_detail
from scoring_v4.scored_artifact import (
    SCORING_ENGINE_VERSION,
    suppress_scored_artifact_for_hard_block,
)
# supplement_type_utils is no longer called directly — taxonomy is the
# single source of truth for classification in the final DB export.
# The import remains available for backward-compat callers but is unused.

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

EXPORT_SCHEMA_VERSION = "2.0.0"  # v4 /100 six-pillar contract + provenance cols; ranking/dedup use quality_score_v4_100. v1.6.0 added profile_gate passthrough on warnings
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
    "dose_safety": 5,
    "interaction": 6,
    "drug_interaction": 7,
    "diagnostic_interference": 8,
    "dietary": 9,
    "status": 10,
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


def _form_alias_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", safe_str(value).lower()).strip()


def _label_form_is_iqm_alias(label_form: str, ingredient: Dict[str, Any], match: Dict[str, Any]) -> bool:
    """Return True when the cleaner-disclosed label form is known by IQM.

    The selected ``matched_form`` may be an "(unspecified)" scoring fallback
    even though the label form itself is an alias on the same IQM parent
    (for example Silica with form "Silicon Dioxide"). The export contract
    should call that form mapped because it is present in our reference data.
    Keep the lookup parent-scoped so unrelated terms never become globally
    mapped just because another ingredient has a matching alias.
    """
    label_key = _form_alias_key(label_form)
    if not label_key:
        return False

    parent_keys = []
    for value in (
        match.get("parent_key"),
        match.get("canonical_id"),
        ingredient.get("parent_key"),
        ingredient.get("canonical_id"),
        ingredient.get("normalized_key"),
    ):
        key = safe_str(value)
        if key and key not in parent_keys:
            parent_keys.append(key)

    iqm_index = load_iqm_reference_index()
    for parent_key in parent_keys:
        entry = iqm_index.get(parent_key)
        if not isinstance(entry, dict):
            continue
        for form_key, form in safe_dict(entry.get("forms")).items():
            terms = [form_key]
            if isinstance(form, dict):
                terms.extend(safe_list(form.get("aliases")))
                terms.extend([
                    form.get("standard_name"),
                    form.get("display_name"),
                    form.get("name"),
                ])
            for term in terms:
                if label_key == _form_alias_key(term):
                    return True
    return False


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
    # Label-native form (label-first export): the identity contract's approved
    # display form wins for resolved rows, so "as Ethyl Esters" survives instead
    # of collapsing to a bare "Ethyl Esters" reconstruction.
    label_display_form = safe_str(match.get("label_display_form"))
    if label_display_form and is_identity_scoreable(safe_str(match.get("identity_disposition"))):
        label_form = label_display_form
    matched = safe_str(match.get("matched_form") or ingredient.get("matched_form"))
    matched_is_real = not _is_placeholder_form(matched)

    if label_form:
        return {
            "display_form_label": label_form,
            "form_status": "known",
            "form_match_status": (
                "mapped"
                if matched_is_real or _label_form_is_iqm_alias(label_form, ingredient, match)
                else "unmapped"
            ),
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
    safety_flags: Optional[List[Dict]] = None,
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
    # 0. — canonical safety flags, when present. Legacy fields are
    # projections of this contract.
    top_flag = _top_safety_flag(safety_flags or [])
    if top_flag is not None:
        status = normalize_text(top_flag.get("status"))
        source = safe_str(top_flag.get("source_db") or top_flag.get("matched_source"))
        rule_id = safe_str(top_flag.get("entry_id") or top_flag.get("rule_id"))
        reference_hit = _banned_recalled_reference_for_rule_id(
            rule_id,
            ingredient_hits=ingredient_hits,
            banned_recalled_index=banned_recalled_index,
        )
        reason = safe_str(
            top_flag.get("reason")
            or top_flag.get("evidence_text")
            or safe_dict(reference_hit).get("reason")
            or safe_dict(reference_hit).get("safety_warning_one_liner")
        )
        if source == "banned_recalled_ingredients":
            source = "banned_recalled"
        return {
            "is_safety_concern": status in _ACTIVE_BANNED_RECALLED_SAFETY_STATUSES,
            "is_banned": status == "banned",
            "safety_reason": reason or None,
            "matched_source": source or None,
            "matched_rule_id": rule_id or None,
            "safety_warning_one_liner": safe_str(
                top_flag.get("safety_warning_one_liner")
                or safe_dict(reference_hit).get("safety_warning_one_liner")
            ) or None,
            "safety_warning": safe_str(
                top_flag.get("safety_warning")
                or safe_dict(reference_hit).get("safety_warning")
            ) or None,
        }

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
            # Sprint E1.1.4 / 2026-05-13 — thread Dr Pham authored copy so
            # the active-side warning emitter can populate the preflight
            # banned_substance_detail blob field without re-fetching the
            # source data.
            "safety_warning_one_liner": safe_str(banned_hit.get("safety_warning_one_liner")) or None,
            "safety_warning": safe_str(banned_hit.get("safety_warning")) or None,
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
            # User-facing reason copy: high_risk and recalled hits MUST carry
            # the authored Dr-Pham one-liner + full safety_warning so Flutter
            # can render "why this is high-risk" under the warning title. Prior
            # version omitted these fields, leaving bitter orange / yohimbe /
            # garcinia warnings with an empty body (just the title). The source
            # data already authors them on each banned_recalled_ingredients.json
            # entry — no derivation, just thread them through.
            "safety_warning_one_liner": safe_str(elevated_hit.get("safety_warning_one_liner")) or None,
            "safety_warning": safe_str(elevated_hit.get("safety_warning")) or None,
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
            # Same pattern as banned/elevated paths: thread the authored copy
            # through so Flutter can show "EU-banned white pigment. Avoid when
            # possible." instead of an empty body under the title.
            "safety_warning_one_liner": safe_str(watchlist_hit.get("safety_warning_one_liner")) or None,
            "safety_warning": safe_str(watchlist_hit.get("safety_warning")) or None,
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


def _banned_recalled_reference_for_rule_id(
    rule_id: str,
    *,
    ingredient_hits: Optional[List[Dict]] = None,
    banned_recalled_index: Optional[Dict[str, Dict]] = None,
) -> Optional[Dict[str, Any]]:
    """Find authored banned/recalled reference data for a canonical flag.

    Canonical safety_flags are intentionally compact. Older enriched files may
    carry the flag id but omit the authored warning copy required by the
    Flutter banned-substance preflight sheet. This helper lets the export
    projection fill that copy from the legacy contaminant hit or reference
    entry without treating safety data as ingredient identity.
    """
    normalized_rule_id = safe_str(rule_id)
    if not normalized_rule_id:
        return None
    for hit in ingredient_hits or []:
        if not isinstance(hit, dict):
            continue
        hit_id = safe_str(hit.get("id") or hit.get("rule_id") or hit.get("banned_id"))
        if hit_id == normalized_rule_id:
            return hit
    seen_entry_ids: set[int] = set()
    for entry in (banned_recalled_index or {}).values():
        if not isinstance(entry, dict):
            continue
        obj_id = id(entry)
        if obj_id in seen_entry_ids:
            continue
        seen_entry_ids.add(obj_id)
        if safe_str(entry.get("id") or entry.get("rule_id")) == normalized_rule_id:
            return entry
    return None


_SAFETY_ONLY_IDENTITY_SOURCES = frozenset({
    "banned_recalled",
    "banned_recalled_ingredients",
    "harmful_additives",
})

_BANNED_RECALLED_SOURCES = frozenset({
    "banned_recalled",
    "banned_recalled_ingredients",
})


def _inactive_identity_name_for_export(
    *,
    name: str,
    upstream_standard_name: str,
    resolver_standard_name: str,
    matched_source: str,
) -> str:
    """Return the inactive ingredient identity name for the Flutter blob.

    The inactive resolver intentionally consults safety sources first so it
    can project safety flags and warning metadata. Those safety sources do
    not own identity fields. If the resolver match came from banned/recalled
    or harmful-additives, preserve the label identity instead of exporting a
    safety table's standard_name as standardName/standard_name.
    """
    if matched_source in _SAFETY_ONLY_IDENTITY_SOURCES:
        return name or upstream_standard_name or resolver_standard_name
    return resolver_standard_name or upstream_standard_name or name


def _safety_flag_sources_identity_only_table(flag: Dict[str, Any]) -> bool:
    source = normalize_safety_source(flag.get("source_db") or flag.get("matched_source"))
    return source in _SAFETY_ONLY_IDENTITY_SOURCES


def _active_identity_name_for_export(
    *,
    name: str,
    upstream_standard_name: str,
    canonical_id: str,
    safety_flags: List[Dict[str, Any]],
) -> str:
    """Return active ingredient identity without safety-source name bleed.

    If an active ingredient is not canonically mapped and the only pressure to
    standardize the name comes from a safety flag, keep the label identity in
    `standardName`/`standard_name`. The safety fact still ships in
    `safety_flags`; it just cannot overwrite identity.
    """
    if canonical_id:
        return upstream_standard_name or name
    if upstream_standard_name and upstream_standard_name != name:
        if any(
            isinstance(flag, dict) and _safety_flag_sources_identity_only_table(flag)
            for flag in safety_flags or []
        ):
            return name or upstream_standard_name
    return upstream_standard_name or name


def _form_match_terms(forms: Any) -> List[str]:
    terms: List[str] = []
    for form in safe_list(forms):
        if isinstance(form, dict):
            terms.extend([
                safe_str(form.get("name")),
                safe_str(form.get("prefix")),
                safe_str(form.get("label")),
                safe_str(form.get("ingredientGroup")),
            ])
        elif form:
            terms.append(safe_str(form))
    return [term for term in terms if term]


def _active_duplicate_identity_key(value: Any) -> str:
    text = safe_str(value).lower()
    if not text:
        return ""
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _add_active_duplicate_term(terms: set[str], value: Any) -> None:
    text = safe_str(value)
    if not text:
        return
    lowered = " ".join(text.lower().replace("_", " ").split())
    if lowered:
        terms.add(lowered)
    identity_key = _active_duplicate_identity_key(text)
    if identity_key:
        terms.add(identity_key)


def _active_form_duplicate_terms_for_product(ingredients: List[Dict[str, Any]]) -> set[str]:
    """Build exact product-active identity terms for inactive form dedup.

    This deliberately uses only the already-exported active rows for this one
    product. It prevents global IQM matches such as "Leucine" or "Potassium
    Chloride" from being tagged unless the matching parent is actually present
    in the same active panel.
    """
    terms: set[str] = set()
    for ing in ingredients:
        if not isinstance(ing, dict):
            continue
        for key in (
            "canonical_id",
            "parent_key",
            "normalized_key",
            "name",
            "standardName",
            "standard_name",
            "matched_form",
            "display_form_label",
        ):
            _add_active_duplicate_term(terms, ing.get(key))
        for form in safe_list(ing.get("forms")):
            if isinstance(form, dict):
                for key in ("name", "label", "ingredientGroup"):
                    _add_active_duplicate_term(terms, form.get(key))
            else:
                _add_active_duplicate_term(terms, form)
        for match in safe_list(ing.get("matched_forms")):
            if isinstance(match, dict):
                for key in ("form_key", "standard_name", "name"):
                    _add_active_duplicate_term(terms, match.get(key))
    return terms


def _candidate_matches_product_active(candidate: Dict[str, Any], active_terms: set[str]) -> bool:
    candidate_terms: set[str] = set()
    for key in ("parent", "standard_name"):
        _add_active_duplicate_term(candidate_terms, candidate.get(key))
    for parent in safe_list(candidate.get("parents")):
        _add_active_duplicate_term(candidate_terms, parent)
    for term in safe_list(candidate.get("identity_terms")):
        _add_active_duplicate_term(candidate_terms, term)
    return bool(candidate_terms & active_terms)


def _product_active_form_duplicate_candidate(
    *,
    inactive_resolver: InactiveIngredientResolver,
    active_terms: set[str],
    raw_name: str,
    additional_terms: List[str],
) -> Optional[Dict[str, Any]]:
    """Return the IQM candidate only if product context proves the duplicate.

    Upstream inactive ``standardName`` is intentionally not used here. It can
    already contain broad active normalization ("Leucine" -> "L-Leucine") and
    would reintroduce the same product-blind bug through a different path.
    """
    if not active_terms:
        return None
    for candidate in inactive_resolver.active_form_candidates(
        raw_name=raw_name,
        additional_terms=additional_terms,
    ):
        if _candidate_matches_product_active(candidate, active_terms):
            return candidate
    return None


def _is_short_acronym_alias(value: Any) -> bool:
    text = safe_str(value)
    compact = re.sub(r"[^A-Za-z0-9]", "", text)
    if compact.lower() in {"pho", "phos"}:
        return True
    if not (2 <= len(compact) <= 5):
        return False
    uppercase_count = sum(1 for ch in compact if ch.isupper())
    return compact.isupper() or uppercase_count >= 2


def _literal_short_alias_evidence_match(evidence_text: Any, alias: Any) -> bool:
    evidence = safe_str(evidence_text)
    alias_text = safe_str(alias)
    if not evidence or not alias_text:
        return False
    pattern = re.compile(
        r"(?<![A-Za-z0-9-])" + re.escape(alias_text) + r"(?![A-Za-z0-9-])",
        re.IGNORECASE,
    )
    return bool(pattern.search(evidence))


def _safety_flag_has_supported_evidence(flag: Dict[str, Any]) -> bool:
    """Reject known low-precision token matches that lack raw evidence.

    The canonical example is `Iso-Phos` matching the PHO/PHOs acronym for
    partially hydrogenated oils after hyphen normalization. A short acronym
    token is acceptable only when the raw evidence contains that acronym as a
    standalone token, not as the suffix of a branded/compound term.
    """
    if not isinstance(flag, dict):
        return False
    match_type = normalize_text(flag.get("match_type"))
    matched_variant = safe_str(flag.get("matched_variant"))
    if match_type == "token_bounded" and _is_short_acronym_alias(matched_variant):
        return _literal_short_alias_evidence_match(flag.get("evidence_text"), matched_variant)
    return True


def _supported_safety_flags(flags: Any) -> List[Dict[str, Any]]:
    return [
        flag
        for flag in safe_list(flags)
        if isinstance(flag, dict) and _safety_flag_has_supported_evidence(flag)
    ]


def build_supplement_type_audit(enriched: Dict, scored: Optional[Dict] = None) -> Dict[str, Any]:
    """Expose canonical taxonomy plus its compatibility projection for audit."""
    supplement_type = enriched.get("supplement_type")
    mirror_type = ""
    if isinstance(supplement_type, dict):
        mirror_type = safe_str(supplement_type.get("type"))
    elif supplement_type is not None:
        mirror_type = safe_str(supplement_type)

    taxonomy = enriched.get("supplement_taxonomy") or (scored or {}).get("supplement_taxonomy") or {}

    return {
        # Retained as an additive compatibility alias for existing audit
        # consumers. It is never used to resolve the exported type.
        "enriched_type": mirror_type,
        "compatibility_mirror_type": mirror_type,
        "compatibility_mirror_matches_taxonomy": (
            not mirror_type or mirror_type == safe_str(taxonomy.get("primary_type"))
        ),
        "scored_type": safe_str((scored or {}).get("supp_type")),
        "export_type": resolve_export_supplement_type(enriched, scored),
        "primary_type": safe_str(taxonomy.get("primary_type")),
        "secondary_type": taxonomy.get("secondary_type"),
        "classification_confidence": taxonomy.get("classification_confidence"),
        "classification_reasons": taxonomy.get("classification_reasons"),
        "quantified_active_count": taxonomy.get("quantified_active_count"),
        "non_quantified_base_count": taxonomy.get("non_quantified_base_count"),
        "category_breakdown": safe_dict(taxonomy.get("category_breakdown")),
    }


def resolve_export_supplement_type(enriched: Dict, scored: Optional[Dict] = None) -> str:
    """Return the canonical taxonomy type, never a legacy rescue value."""
    taxonomy = enriched.get("supplement_taxonomy") or (scored or {}).get("supplement_taxonomy") or {}
    primary_type = normalize_text(taxonomy.get("primary_type"))
    return primary_type or "unknown"


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


def contaminant_safety_flags(enriched: Dict) -> List[Dict]:
    """Return canonical banned/recalled safety flags from contaminant_data.

    The enricher now emits `contaminant_data.banned_substances.safety_flags[]`
    while preserving the legacy `substances[]` list. Some intermediate
    fixtures may only carry `substances[].safety_flag`, so read both shapes.
    """
    flags: List[Dict] = []
    banned_substances = safe_dict(
        safe_dict(enriched.get("contaminant_data")).get("banned_substances")
    )
    for flag in safe_list(banned_substances.get("safety_flags")):
        if isinstance(flag, dict) and _safety_flag_has_supported_evidence(flag):
            flags.append(flag)
    for sub in safe_list(banned_substances.get("substances")):
        if not isinstance(sub, dict):
            continue
        flag = sub.get("safety_flag")
        if isinstance(flag, dict) and _safety_flag_has_supported_evidence(flag):
            flags.append(flag)
    return flags


def safety_flag_status_matches(enriched: Dict, *statuses: str) -> List[Dict]:
    matches: List[Dict] = []
    for flag in contaminant_safety_flags(enriched):
        source = normalize_safety_source(flag.get("source_db") or flag.get("matched_source"))
        if source == "banned_recalled_ingredients" and safety_flag_matches_status(flag, statuses):
            matches.append(flag)
    for src_key in ("activeIngredients", "inactiveIngredients"):
        for ing in safe_list(enriched.get(src_key)):
            if not isinstance(ing, dict):
                continue
            for flag in safe_list(ing.get("safety_flags")):
                if not isinstance(flag, dict):
                    continue
                if not _safety_flag_has_supported_evidence(flag):
                    continue
                source = normalize_safety_source(flag.get("source_db") or flag.get("matched_source"))
                if source != "banned_recalled_ingredients":
                    continue
                if safety_flag_matches_status(flag, statuses):
                    matches.append(flag)
    return matches


def _safety_flag_display_name(flag: Dict[str, Any]) -> str:
    return safe_str(
        flag.get("matched_variant")
        or flag.get("evidence_text")
        or flag.get("entry_id")
        or flag.get("rule_id")
        or "Unknown ingredient"
    )


def _banned_warning_type_for_status(status: str) -> str:
    return {
        "banned": "banned_substance",
        "recalled": "recalled_ingredient",
        "high_risk": "high_risk_ingredient",
        "watchlist": "watchlist_substance",
    }.get(status, "safety")


def _banned_warning_title_prefix_for_status(status: str) -> str:
    return {
        "banned": "Banned substance",
        "recalled": "Recalled ingredient",
        "high_risk": "High-risk ingredient",
        "watchlist": "Watchlist ingredient",
    }.get(status, "Safety issue")


def _resolver_status_in(
    enriched: Dict, target_statuses: tuple,
) -> bool:
    """Walk both active and inactive ingredients in the enriched product
    and run them through the InactiveIngredientResolver's banned_recalled
    alias index. Returns True if any ingredient matches a rule whose
    status is in ``target_statuses``.

    Bridges the gap where ``enriched.contaminant_data`` didn't catch the
    hit (the enricher's name-match misses inactives + alias variants on
    actives like 'Garcinia Cambogia fruit extract'), but the unified
    resolver's normalized-alias index does. Same alias coverage the per-
    ingredient blob entries use, applied at the product-level flag layer.
    """
    try:
        index = _get_active_banned_recalled_index()
    except Exception:
        # Defensive fallback — never crash a build because the resolver
        # index couldn't load. Original contaminant_data path still runs.
        return False
    for src_key in ("activeIngredients", "inactiveIngredients"):
        for ing in safe_list(enriched.get(src_key)):
            if not isinstance(ing, dict):
                continue
            for flag in safe_list(ing.get("safety_flags")):
                if not isinstance(flag, dict):
                    continue
                if not _safety_flag_has_supported_evidence(flag):
                    continue
                source = normalize_safety_source(flag.get("source_db") or flag.get("matched_source"))
                if (
                    source == "banned_recalled_ingredients"
                    and safety_flag_matches_status(flag, target_statuses)
                ):
                    return True
            terms = _active_banned_recall_evidence_terms(
                raw_source_text=safe_str(ing.get("raw_source_text")),
                name=safe_str(ing.get("name")),
                standard_name=safe_str(ing.get("standardName")),
                forms=safe_list(ing.get("forms")),
                identity_mapped=safe_bool(ing.get("mapped")),
            )
            for t in terms:
                entry = index.get(t)
                if entry and safety_flag_matches_status(entry, target_statuses):
                    if entry.get("requires_explicit_form_evidence"):
                        evidence_values = [
                            ing.get("raw_source_text"),
                            ing.get("name"),
                            ing.get("ingredientGroup"),
                        ]
                        for form in safe_list(ing.get("forms")):
                            if isinstance(form, dict):
                                evidence_values.extend([
                                    form.get("name"),
                                    form.get("prefix"),
                                    form.get("label"),
                                ])
                            elif form:
                                evidence_values.append(form)
                        if not has_explicit_form_evidence(
                            evidence_values,
                            entry.get("form_evidence_patterns") or [],
                        ):
                            continue
                    return True
    return False


def has_banned_substance(enriched: Dict) -> bool:
    """True for exact/alias banned ingredient hits, not recalls/high-risk reviews.

    Reads BOTH the enricher's contaminant_data (legacy path) AND the
    unified resolver's banned_recalled index applied to actives + inactives.
    The resolver-side path catches: (a) inactive ingredients flagged in
    banned_recalled, which the enricher historically didn't scan, and
    (b) alias variants the enricher's name-match missed on actives.
    """
    if contaminant_status_matches(enriched, "banned"):
        return True
    if safety_flag_status_matches(enriched, "banned"):
        return True
    return _resolver_status_in(enriched, ("banned",))


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


def _top_safety_flag(flags: List[Dict]) -> Optional[Dict]:
    return _canonical_top_safety_flag(safe_list(flags))


def _safety_flags_from_contract(contract: Dict[str, Any]) -> List[Dict[str, Any]]:
    source = safe_str(contract.get("matched_source"))
    rule_id = safe_str(contract.get("matched_rule_id"))
    if not source or not rule_id:
        return []
    if source not in {"banned_recalled", "banned_recalled_ingredients", "harmful_additives"}:
        return []
    if contract.get("is_banned"):
        status = "banned"
        severity = "critical"
    elif contract.get("is_safety_concern"):
        status = "high_risk"
        severity = "high"
    else:
        status = "watchlist"
        severity = "low"
    source_db = "banned_recalled_ingredients" if source == "banned_recalled" else source
    return [{
        "entry_id": rule_id,
        "source_db": source_db,
        "status": status,
        "severity": severity,
        "match_type": "legacy_projection",
        "matched_variant": rule_id,
        "evidence_text": safe_str(contract.get("safety_reason")),
        "confidence": "medium",
    }]


def _inactive_display_tone(
    matched_source: Optional[str],
    matched_rule_id: Optional[str],
    b1_applied_tier: Dict[str, str],
    harmful_severity: Optional[str] = None,
) -> str:
    """Penalty-aware dot tone for an 'Other ingredients' row.

    Reflects the harmful-additive penalty B1 ACTUALLY applied (post-exemption),
    NOT the additive's file severity — the two diverge (a capsule shell resolves
    to MCC for display but is never penalized → green, while disclosed
    maltodextrin costs 0.5 → light orange).

    ``b1_applied_tier`` is the scorer's per-additive applied tier keyed by
    additive id (== ``matched_rule_id`` for harmful rows). The applied tier is
    authoritative when present. When B1 missed a resolver-only moderate/high
    concern, ``harmful_severity`` supplies a safety floor so green still means
    "no penalty AND no safety/regulatory concern". Low unpenalized excipients
    remain green. banned_recalled rows floor at red regardless because B0 (not
    B1) owns their penalty. Tones: green < light_orange < dark_orange < red.
    """
    if safe_str(matched_source) == "banned_recalled":
        return "red"
    tier = b1_applied_tier.get(safe_str(matched_rule_id) or "")
    if tier in ("high", "critical"):
        return "red"
    if tier == "moderate":
        return "dark_orange"
    if tier == "low":
        return "light_orange"
    if safe_str(matched_source) == "harmful_additives":
        fallback_tier = safe_str(harmful_severity).lower()
        if fallback_tier in ("high", "critical"):
            return "red"
        if fallback_tier == "moderate":
            return "dark_orange"
    return "green"


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


def _active_export_contract(enriched: Dict) -> Dict[str, Any]:
    """Return the strict scoring rows that should drive app-facing active identity.

    Product-level evidence rows can legitimately support scoring, but they are
    not label ingredients and must not render as active ingredient rows or key
    search tags.
    """
    iqd = safe_dict(enriched.get("ingredient_quality_data"))
    contract_available = isinstance(iqd.get("ingredients_scorable"), list)
    try:
        result = get_scoring_ingredients(enriched, strict=True, allow_legacy_fallback=False)
    except Exception as exc:  # pragma: no cover - defensive export fallback.
        logger.debug("strict scoring contract unavailable for export: %s", exc)
        return {"available": False, "source_paths": set(), "terms": set(), "canonical_ids": set()}

    rows = [
        row for row in result.rows
        if (
            safe_str(row.get("scoring_input_kind")) != "product_level_evidence"
            and not _is_display_only_blend_scoring_row(row)
        )
    ]
    source_paths: set[str] = set()
    terms: set[str] = set()
    canonical_ids: set[str] = set()
    for row in rows:
        path = safe_str(row.get("raw_source_path") or row.get("source_path"))
        if path:
            source_paths.add(path)
        for key in (
            "raw_source_text",
            "name",
            "standard_name",
            "standardName",
            "matched_name",
            "display_label",
        ):
            value = safe_str(row.get(key))
            if value:
                terms.add(value.casefold())
        canonical_id = normalize_catalog_interaction_tag(
            row.get("canonical_id") or row.get("parent_key") or row.get("normalized_key")
        )
        if canonical_id:
            canonical_ids.add(canonical_id)

    return {
        "available": contract_available,
        "source_paths": source_paths,
        "terms": terms,
        "canonical_ids": canonical_ids,
    }


def _is_display_only_blend_scoring_row(row: Dict[str, Any]) -> bool:
    if safe_str(row.get("scoring_input_kind")) != "recovered_active_identity":
        return False
    path = safe_str(row.get("raw_source_path") or row.get("source_path")).lower()
    exclusion = safe_str(row.get("score_exclusion_reason")).lower()
    return (
        exclusion == "nested_display_only"
        or "nestedrows" in path
        or "child_ingredients" in path
    )


def _active_row_has_explicit_safety_export_signal(
    ing: Dict[str, Any],
    *,
    harmful_lookup: Optional[Dict[str, Dict]] = None,
    contaminant_lookup: Optional[Dict[str, List[Dict]]] = None,
    allergen_patterns: Optional[List[Dict]] = None,
) -> bool:
    if ing.get("is_safety_concern") or ing.get("is_banned") or safe_list(ing.get("safety_flags")):
        return True
    canonical_id = safe_str(ing.get("canonical_id") or ing.get("parent_key") or ing.get("normalized_key"))
    if canonical_id.upper().startswith(("BANNED_", "RECALLED_", "HIGH_RISK_", "WATCHLIST_")):
        return True

    raw = safe_str(ing.get("raw_source_text"))
    name = safe_str(ing.get("name") or ing.get("standardName") or ing.get("standard_name"))
    standard_name = safe_str(ing.get("standardName") or ing.get("standard_name"))
    if contaminant_lookup and matching_contaminant_hits(contaminant_lookup, raw, name, standard_name):
        return True
    if allergen_patterns and matching_allergen_hits(allergen_patterns, raw, name, standard_name):
        return True
    if harmful_lookup:
        for term in collect_match_terms(raw, name, standard_name, canonical_id):
            if harmful_lookup.get(term):
                return True
    return False


def _active_row_allowed_for_primary_export(
    ing: Dict[str, Any],
    contract: Dict[str, Any],
    *,
    harmful_lookup: Optional[Dict[str, Dict]] = None,
    contaminant_lookup: Optional[Dict[str, List[Dict]]] = None,
    allergen_patterns: Optional[List[Dict]] = None,
) -> bool:
    if not contract.get("available"):
        return True
    # An "available" but EMPTY contract identifies no strict primary active (every
    # disclosed active was recognized-but-non-scorable / unmapped / additive, e.g.
    # a single-botanical BulkSupplements SKU). It provides no basis to filter, so a
    # real LABEL row must still render — the product ships as opaque/POOR rather
    # than being dropped to a 0-active blob the reconciliation gate then quarantines
    # (see build_detail_blob gate intent: opaque actives SHIP). Nested blend
    # children fall through to the safety-signal check below so they never surface
    # as top-level actives unless they carry an explicit safety signal.
    if not (
        contract.get("source_paths")
        or contract.get("terms")
        or contract.get("canonical_ids")
    ):
        empty_path = safe_str(ing.get("raw_source_path") or ing.get("source_path")).lower()
        if "child_ingredients" not in empty_path and "nestedrows" not in empty_path:
            return True
    path = safe_str(ing.get("raw_source_path") or ing.get("source_path"))
    if path and path in contract.get("source_paths", set()):
        return True
    for key in (
        "raw_source_text",
        "name",
        "standardName",
        "standard_name",
        "matched_name",
        "display_label",
    ):
        value = safe_str(ing.get(key))
        if value and value.casefold() in contract.get("terms", set()):
            return True
    canonical_id = normalize_catalog_interaction_tag(
        ing.get("canonical_id") or ing.get("parent_key") or ing.get("normalized_key")
    )
    if canonical_id and canonical_id in contract.get("canonical_ids", set()):
        return True
    return _active_row_has_explicit_safety_export_signal(
        ing,
        harmful_lookup=harmful_lookup,
        contaminant_lookup=contaminant_lookup,
        allergen_patterns=allergen_patterns,
    )


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
      - the Stage-3 artifact is not the v4-native six-pillar contract

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

    source_type = safe_str(
        enriched.get("source_type")
        or scored.get("source_type")
        or enriched.get("_source")
        or scored.get("_source")
    ).lower()
    provenance = safe_dict(
        enriched.get("manual_product_provenance")
        or scored.get("manual_product_provenance")
    )
    if source_type == "external_manual" or provenance:
        required = ("source_url", "label_verified_at", "review_status", "reviewer")
        missing = [field for field in required if not safe_str(provenance.get(field))]
        if missing:
            issues.append(
                "review_queue: external manual product missing provenance "
                f"field(s): {', '.join(missing)}."
            )
        review_status = safe_str(provenance.get("review_status")).lower()
        if review_status not in {"verified", "validated", "approved"}:
            issues.append(
                "review_queue: external manual product cannot ship until "
                "manual_product_provenance.review_status is verified."
            )

    iqd = safe_dict(enriched.get("ingredient_quality_data"))
    ingredients = safe_list(iqd.get("ingredients"))

    # Fresh enriched rows carry the shared identity disposition. Reuse the
    # release audit rather than reproducing its identity rules here: direct
    # final-DB builds then fail closed on a stamped conflict or missing label,
    # while legacy fixtures/artifacts without any identity stamps retain their
    # explicit compatibility path.
    if any(
        isinstance(ingredient, dict) and "identity_disposition" in ingredient
        for ingredient in ingredients
    ):
        for record in audit_product(enriched):
            if record.failed:
                issues.append(
                    "review_queue: identity integrity "
                    f"{record.source_path or 'unknown'}:{record.violation}"
                )

    for idx, ingredient in enumerate(ingredients):
        if not isinstance(ingredient, dict):
            issues.append(f"ingredient_quality_data.ingredients[{idx}] is not an object")
            continue
        missing = sorted(field for field in EXPORT_REQUIRED_IQD_FIELDS if field not in ingredient)
        for field in missing:
            issues.append(f"missing ingredient_quality_data.ingredients[{idx}].{field}")

    active_ingredients = [
        ing for ing in safe_list(enriched.get("activeIngredients"))
        if isinstance(ing, dict)
    ]
    has_active_identity = any(
        safe_str(ing.get("canonical_id") or ing.get("parent_key"))
        for ing in ingredients
        if isinstance(ing, dict)
    ) or any(safe_str(ing.get("canonical_id")) for ing in active_ingredients)

    if scored.get("score_basis") != "v4_six_pillar":
        issues.append(
            "review_queue: scored artifact is not v4-native "
            "(score_basis must equal v4_six_pillar)."
        )
    if "scoring_metadata" not in scored:
        issues.append("missing scored.scoring_metadata")
    scoring_diag = safe_dict(scored.get("iqd_contract_diagnostics"))
    scoring_meta = safe_dict(scored.get("scoring_metadata"))
    if not scoring_diag:
        scoring_diag = safe_dict(scoring_meta.get("iqd_contract_diagnostics"))
    strict_scoring_contract = safe_dict(
        scored.get("strict_scoring_contract")
        or scoring_meta.get("strict_scoring_contract")
    )
    if not strict_scoring_contract:
        issues.append("missing scored.strict_scoring_contract")
    elif strict_scoring_contract.get("passed") is not True:
        issues.append(
            "review_queue: export cannot ship score with failed strict "
            "scoring contract."
        )
    source = (
        scored.get("scoring_ingredients_source")
        or scoring_diag.get("scoring_ingredients_source")
        or scoring_meta.get("scoring_ingredients_source")
    )
    if source == "ingredient_quality_data.ingredients":
        issues.append(
            "review_queue: export cannot ship score derived from legacy "
            "ingredient_quality_data.ingredients fallback."
        )
    if scoring_diag.get("iqd_ingredients_fallback_used") is True:
        issues.append(
            "review_queue: export cannot ship score with IQD ingredients "
            "fallback reliance."
        )

    # ── Batch 3 data integrity gate ────────────────────────────────────
    verdict = safe_str(scored.get("verdict")).upper()
    score_optional = verdict in {"BLOCKED", "UNSAFE"}

    # The v4 export adapter stamps _v4_quality_status; it is authoritative
    # for the ship/quarantine decision.
    #   scored           → require a finite quality_score_v4_100 (asserted here);
    #   suppressed_safety → BLOCKED/UNSAFE, null score is legitimate (score_optional below);
    #   not_scored        → verdict is NOT_SCORED, quarantined by the block below.
    # The verdict-keyed checks still apply to the v4-native Stage-3 artifact.
    v4_status = scored.get("_v4_quality_status")
    if v4_status not in {"scored", "suppressed_safety", "not_scored"}:
        issues.append(
            "review_queue: missing or invalid v4 quality_score_status on "
            "Stage-3 artifact."
        )
    if v4_status == "scored":
        q = scored.get("_v4_quality_score_100")
        try:
            q_ok = q is not None and math.isfinite(float(q))
        except (TypeError, ValueError):
            q_ok = False
        if not q_ok:
            issues.append(
                f"review_queue: v4 quality_score_status=scored requires a finite "
                f"quality_score_v4_100 but got {q!r} (v4 data integrity gate)."
            )
        pillar_keys = (
            "formulation",
            "dose",
            "evidence",
            "transparency",
            "verification",
            "safety_hygiene",
        )
        pillars = safe_dict(scored.get("_v4_pillars"))
        pillar_scores: List[float] = []
        for pillar_key in pillar_keys:
            value = safe_dict(pillars.get(pillar_key)).get("score")
            try:
                number = float(value)
            except (TypeError, ValueError):
                issues.append(
                    f"review_queue: quality_pillars_v4.{pillar_key}.score "
                    "is missing or non-numeric."
                )
                continue
            if not math.isfinite(number):
                issues.append(
                    f"review_queue: quality_pillars_v4.{pillar_key}.score is not finite."
                )
                continue
            pillar_scores.append(number)
        if q_ok and len(pillar_scores) == len(pillar_keys):
            if abs(sum(pillar_scores) - float(q)) > 0.011:
                issues.append(
                    "review_queue: six v4 pillars do not reconcile to "
                    "quality_score_v4_100."
                )

    coverage = scored.get("mapped_coverage")
    try:
        coverage_number = float(coverage)
        coverage_ok = math.isfinite(coverage_number) and 0.0 <= coverage_number <= 1.0
    except (TypeError, ValueError):
        coverage_number = 0.0
        coverage_ok = False
    if not coverage_ok:
        issues.append("review_queue: mapped_coverage must be numeric within [0,1].")
    elif safe_str(scored.get("verdict")).upper() == "SAFE" and coverage_number < 0.3:
        issues.append("review_queue: SAFE verdict is forbidden below mapped_coverage 0.3.")

    if verdict == "NOT_SCORED":
        issues.append(
            "review_queue: NOT_SCORED verdict — mapping/dosage gate "
            "failed upstream; product cannot ship without a coherent "
            "score (Batch 3 data integrity gate)."
        )
    # NOTE: a product whose actives carry no canonical identity is OPAQUE, not
    # unscoreable. The scorer rates it POOR/CAUTION via the transparency penalty,
    # and that low rating IS the consumer-relevant signal ("we can't verify what's
    # in this product"). So it SHIPS (with a `proprietary_blend` or
    # `unverified_ingredient` flag set in build_detail_blob — split by why the
    # active is unidentifiable), rather than being silently quarantined. Genuinely
    # unscoreable products are NOT_SCORED (handled above) and still quarantine.
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


def _active_banned_recall_evidence_terms(
    *,
    raw_source_text: str,
    name: str,
    standard_name: str = "",
    forms: Optional[List[Any]] = None,
    identity_mapped: bool = False,
) -> List[str]:
    """Build banned/recalled evidence terms from label evidence.

    Derived identity is not safety evidence for a mapped active ingredient.
    This prevents an upstream corrupted `standardName` from creating a
    safety chip when the raw label only says a generic nutrient name.
    """
    values: List[Any] = [raw_source_text, name]
    for form in safe_list(forms):
        if isinstance(form, dict):
            values.extend([form.get("name"), form.get("prefix")])
        elif form:
            values.append(form)
    if not identity_mapped:
        values.append(standard_name)
    return _active_banned_recall_terms(*values)


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


def _nutrient_group_id(source_canonical_id: str) -> Optional[str]:
    """Return the IQM-authored nutrient display group for a matched source id.

    Driven by the IQM ``match_rules.target_id`` redirect (currently only
    ``vitamin_k1 -> vitamin_k``). The enricher may already emit the target as
    ``canonical_id`` for interaction/evidence correctness; this field remains a
    display/dual-read hint for the app's Nutrients tab and should never drive
    deduplication.

    Returns the redirect target only when it differs from the matched source id;
    otherwise ``None`` (the common case), so the blob stays lean and the app
    falls back to ``canonical_id``.
    """
    if not source_canonical_id:
        return None
    entry = (IQM_REFERENCE_INDEX or load_iqm_reference_index()).get(source_canonical_id)
    if isinstance(entry, dict):
        target = safe_str(safe_dict(entry.get("match_rules")).get("target_id"))
        if target and target != source_canonical_id:
            return target
    return None


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

    score_display_100_equivalent  TEXT,
    score_100_equivalent          REAL,
    grade                         TEXT,
    verdict                       TEXT,
    safety_verdict                TEXT,
    mapped_coverage               REAL,

    -- V4 SCORING (export schema v2.0.0) — canonical /100 six-pillar contract.
    -- quality_score_v4_100 is the shipped score; score_100_equivalent mirrors it.
    -- raw_score_v4_100 is audit/debug only and is NEVER the shipped score.
    quality_score_v4_100            REAL,
    quality_score_status            TEXT,
    quality_tier                    TEXT,
    quality_score_suppressed_reason TEXT,
    raw_score_v4_100                REAL,
    v4_module                       TEXT,
    v4_confidence                   TEXT,
    score_model_version             TEXT,
    quality_score_version           TEXT,
    scoring_engine_version          TEXT,
    classification_schema_version   TEXT,
    v4_config_fingerprint           TEXT,

    -- V4 six-pillar component scores (bulk-audit projection of quality_pillars_v4).
    -- Maxes: formulation 20, dose 20, evidence 20, transparency 15, verification 15,
    -- safety_hygiene 10 (= 100). Nullable: NULL when a product is not v4-scored.
    pillar_formulation_v4           REAL,
    pillar_dose_v4                  REAL,
    pillar_evidence_v4              REAL,
    pillar_transparency_v4          REAL,
    pillar_verification_v4          REAL,
    pillar_safety_hygiene_v4        REAL,

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
    safety_signal_reason          TEXT,

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

    -- 2026-05-12: searchable ingredient text. Aggregates active + inactive
    -- ingredient display labels into a single space-separated string so
    -- products_fts can match by ingredient name (e.g. "Capsimax" finds
    -- products listing it as an active even when product_name + brand_name
    -- don't carry the brand). Indexed via products_fts below.
    ingredients_text              TEXT,

    -- ====================================================================
    -- Enhancement 4: Goal Matching Preview
    -- ====================================================================
    goal_matches                  TEXT,  -- JSON array: dose-adequate goal IDs
    goal_match_confidence         REAL,  -- 0.0-1.0: average cluster weight
    goal_matches_underdosed       TEXT,  -- JSON array: goals present but below effective dose

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
CREATE INDEX IF NOT EXISTS idx_core_score ON products_core(quality_score_v4_100);
CREATE INDEX IF NOT EXISTS idx_core_status ON products_core(product_status);
CREATE INDEX IF NOT EXISTS idx_core_type ON products_core(supplement_type);
-- New indexes for v1.1.0 enhancements
CREATE INDEX IF NOT EXISTS idx_core_primary_category ON products_core(primary_category);
CREATE INDEX IF NOT EXISTS idx_core_contains_omega3 ON products_core(contains_omega3) WHERE contains_omega3 = 1;
CREATE INDEX IF NOT EXISTS idx_core_contains_probiotics ON products_core(contains_probiotics) WHERE contains_probiotics = 1;
CREATE INDEX IF NOT EXISTS idx_core_contains_collagen ON products_core(contains_collagen) WHERE contains_collagen = 1;
CREATE INDEX IF NOT EXISTS idx_core_contains_adaptogens ON products_core(contains_adaptogens) WHERE contains_adaptogens = 1;
CREATE INDEX IF NOT EXISTS idx_core_contains_nootropics ON products_core(contains_nootropics) WHERE contains_nootropics = 1;
-- App hot-path indexes (mirror Flutter _ensureAppIndexes in
-- lib/data/database/core_database.dart — the expressions must stay
-- char-identical or SQLite will not match them to the app's queries).
-- findByUpc wraps upc_sku in this REPLACE chain; without the expression
-- index the lookup is a full table scan (verified via EXPLAIN QUERY PLAN).
CREATE INDEX IF NOT EXISTS idx_core_upc_normalized ON products_core (REPLACE(REPLACE(REPLACE(REPLACE(upc_sku, ' ', ''), '-', ''), '.', ''), '/', ''));
-- fetchBetterAlternativesPool: partial composite so the category branch
-- resolves via SEARCH with the score range folded into the same index.
CREATE INDEX IF NOT EXISTS idx_core_cat_score ON products_core (primary_category, quality_score_v4_100 DESC) WHERE quality_score_status = 'scored';
"""

FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS products_fts USING fts5(
    product_name, brand_name, ingredients_text,
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
      2. Keep the **best** row per group: active > discontinued, then a
         scored product over a suppressed/not-scored one, then highest
         quality_score_v4_100 (falling back to score_100_equivalent for the
         v3 path), then newest dsld_id (lexicographic).
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
                "       COALESCE(quality_score_v4_100, score_100_equivalent, 0), "
                "       quality_score_status "
                "  FROM products_core WHERE dsld_id = ?",
                (did,),
            ).fetchone()
            if row:
                candidates.append(row)

        if len(candidates) < 2:
            continue

        # Sort: active first, a scored product over a suppressed/not-scored one,
        # highest /100 score, newest dsld_id. A BLOCKED/UNSAFE twin (null score,
        # status != 'scored') always loses to a scored sibling.
        candidates.sort(
            key=lambda r: (
                1 if r[1] == "active" else 0,        # active wins
                1 if r[3] == "scored" else 0,        # scored beats suppressed/not_scored
                r[2],                                 # highest /100 score
                r[0],                                 # newest dsld_id (lexicographic)
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


def derive_v4_tradeoffs(
    scored: Dict[str, Any], enriched: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Build (score_bonuses, score_penalties) for the Tradeoffs section from the
    v4 contract + enriched safety data, with ZERO v3 section-score dependency.

    Flutter renders only ``label``(/``reason``) and ``detail``(/``description``)
    per item (see tradeoffs_section.dart ``_toTradeoff``); other fields are
    diagnostic. Bonuses + nuanced transparency penalties are sourced from v4
    (faithful to whether v4 scored them); safety penalties (B0/B1/B7/B8) gate on
    enriched presence so they never under-warn, and preserve per-item detail."""
    mb = safe_dict(scored.get("_v4_module_breakdown"))
    dims = safe_dict(mb.get("dimensions"))
    form = safe_dict(safe_dict(dims.get("formulation")).get("components"))
    transp = safe_dict(dims.get("transparency"))
    transp_pen = safe_dict(transp.get("penalties"))
    transp_comp = safe_dict(transp.get("components"))
    transp_meta = safe_dict(transp.get("metadata"))
    verif = safe_dict(safe_dict(mb.get("verification_bonus")).get("components"))
    dose = safe_dict(dims.get("dose"))
    dose_c = safe_dict(dose.get("components"))
    dose_m = safe_dict(dose.get("metadata"))
    delivery_data = safe_dict(enriched.get("delivery_data"))

    def _pos(d: Dict[str, Any], k: str) -> bool:
        return safe_float(d.get(k), 0) > 0

    def _neg(d: Dict[str, Any], k: str) -> bool:
        return safe_float(d.get(k), 0) < 0

    # ── Bonuses — gate on the v4 component that actually scored them ──────────
    bonuses: List[Dict[str, Any]] = []
    if _pos(form, "A2_premium_forms"):
        bonuses.append({"id": "A2", "label": "Premium ingredient forms", "score": form["A2_premium_forms"]})
    if _pos(form, "A3_delivery_system"):
        bonuses.append({"id": "A3", "label": "Advanced delivery system", "score": form["A3_delivery_system"],
                        "detail": safe_str(enriched.get("delivery_tier") or delivery_data.get("highest_tier"))})
    if _pos(form, "A4_absorption_enhancer"):
        bonuses.append({"id": "A4", "label": "Absorption enhancer present", "score": form["A4_absorption_enhancer"]})
    if _pos(form, "A5a_organic"):
        bonuses.append({"id": "A5a", "label": "Certified organic", "score": form["A5a_organic"]})
    if _pos(form, "A5b_standardized_botanical"):
        bonuses.append({"id": "A5b", "label": "Standardized botanicals", "score": form["A5b_standardized_botanical"]})
    if _pos(form, "A5c_synergy_cluster"):
        bonuses.append({"id": "A5c", "label": "Synergy cluster qualified", "score": form["A5c_synergy_cluster"]})
    if _pos(form, "A5d_non_gmo"):
        bonuses.append({"id": "A5d", "label": "Non-GMO Project Verified", "score": form["A5d_non_gmo"]})
    if _pos(form, "A6_single_ingredient"):
        bonuses.append({"id": "A6", "label": "Single-nutrient premium form", "score": form["A6_single_ingredient"]})
    # A5e natural-source: scored by v4 but intentionally NOT surfaced (cosmetic).
    if _pos(verif, "B4a_verified_certifications"):
        bonuses.append({"id": "B4a", "label": "Third-party purity testing", "score": verif["B4a_verified_certifications"]})
    if _pos(verif, "B4b_gmp"):
        bonuses.append({"id": "B4b", "label": "GMP certified facility", "score": verif["B4b_gmp"]})
    if _pos(verif, "B4c_batch_traceability"):
        bonuses.append({"id": "B4c", "label": "Heavy metal tested", "score": verif["B4c_batch_traceability"]})

    # Module-specific quality bonuses — the omega and probiotic modules credit
    # their own positive components (not the generic A-codes), so surface them as
    # the dedicated chips v3 carried (omega-3 dose, probiotic quality).
    if _pos(dose_c, "epa_dha_band"):
        omega_bonus = {"id": "omega3", "label": "Omega-3 dose bonus", "score": dose_c["epa_dha_band"]}
        band = safe_str(dose_m.get("epa_dha_band_label")).replace("_", " ")
        if band:
            omega_bonus["detail"] = band
        bonuses.append(omega_bonus)
    _prob_signals = ("clinical_strain_codes", "cfu_amount", "named_species_diversity")
    if any(_pos(form, k) for k in _prob_signals):
        bonuses.append({"id": "probiotic", "label": "Probiotic quality bonus",
                        "score": sum(safe_float(form.get(k), 0) for k in _prob_signals)})

    # ── Penalties ────────────────────────────────────────────────────────────
    penalties: List[Dict[str, Any]] = []

    # Safety — gate on ENRICHED presence (never under-warn), detail preserved.
    for sub in contaminant_matches(enriched):
        status = normalize_text(sub.get("status"))
        name = safe_str(sub.get("ingredient") or sub.get("banned_name"))
        penalties.append({"id": "B0", "label": f"{status.title()}: {name}",
                          "status": status, "reason": safe_str(sub.get("reason"))[:200]})
    for h in safe_list(enriched.get("harmful_additives")):
        if isinstance(h, dict):
            harmful_ref = resolve_harmful_reference(h)
            penalties.append({
                "id": "B1",
                "label": f"Harmful additive: {safe_str(h.get('additive_name') or h.get('ingredient'))}",
                "severity": safe_str(h.get("severity_level")),
                "reason": safe_str(
                    harmful_ref.get("safety_summary_one_liner")
                    or harmful_ref.get("safety_summary")
                    or h.get("safety_summary_one_liner")
                    or h.get("safety_summary")
                    or h.get("mechanism_of_harm")
                    or h.get("notes")
                    or h.get("category")
                )[:200],
            })
    # B2 declared allergen source — gate on enriched allergen presence (the v3
    # user-facing meaning, neutral label). v4's narrower B2 (false allergen-free
    # claim) is a different signal; allergen *presence* is what users consider.
    for a in safe_list(enriched.get("allergen_hits")):
        if isinstance(a, dict):
            penalties.append({
                "id": "B2",
                "label": f"Declared allergen source: {safe_str(a.get('allergen_name'))}",
                "severity": safe_str(a.get("severity_level")),
                "presence": safe_str(a.get("presence_type")),
            })
    # B1 dietary sugar — already enriched-gated in v3; carried over verbatim.
    sugar_penalty = _dietary_sugar_penalty_detail(enriched)
    sugar_penalty_score = safe_float(sugar_penalty.get("penalty"), 0)
    if sugar_penalty_score > 0:
        sugar_reason = safe_str(sugar_penalty.get("reason"))
        sugar = safe_dict(safe_dict(enriched.get("dietary_sensitivity_data")).get("sugar"))
        sources = safe_list(sugar_penalty.get("sugar_sources"))
        high_glycemic = safe_list(sugar_penalty.get("high_glycemic_sweeteners"))
        sugar_alcohols = safe_list(sugar_penalty.get("sugar_alcohols"))
        if sugar_reason == "high_sugar_grams":
            sugar_label = "High sugar content"
        elif sugar_reason == "moderate_sugar_grams":
            sugar_label = "Moderate sugar content"
        elif sugar_reason == "high_glycemic_or_syrup":
            sugar_label = "High-glycemic sweetener or syrup"
        elif sugar_reason == "sugar_alcohol_source":
            sugar_label = "Sugar alcohol"
        else:
            sugar_label = "Added sugar source"
        detail_parts: List[str] = []
        amount_g = safe_float(sugar.get("amount_g"))
        if amount_g:
            detail_parts.append(f"{amount_g:g}g sugar per serving")
        named_sources = high_glycemic or sugar_alcohols or sources
        if named_sources:
            detail_parts.append(", ".join(safe_str(s) for s in named_sources if safe_str(s)))
        penalties.append({
            "id": "B1_dietary_sugar", "label": sugar_label, "score": -sugar_penalty_score,
            "severity": "high" if sugar_penalty_score >= 4 else ("moderate" if sugar_penalty_score >= 2 else "low"),
            "reason": sugar_reason, "detail": "; ".join(detail_parts),
        })
    # B7 dose-over-UL — enriched safety flags (Flutter also surfaces these from rda_ul_data).
    for ev in safe_list(safe_dict(enriched.get("rda_ul_data")).get("safety_flags")):
        if not isinstance(ev, dict):
            continue
        nutrient = safe_str(ev.get("nutrient")) or "unknown"
        pct = safe_float(ev.get("pct_ul"), 0)
        penalties.append({
            "id": "B7",
            "label": f"Exceeds safe dose limit: {nutrient} at {pct:.0f}% of UL",
            "severity": "critical" if pct >= 200 else "warning",
            "reason": f"{nutrient}: {ev.get('amount')} vs UL {ev.get('ul')}",
        })
    # B8 CAERS is intentionally NOT surfaced: it has been dead in production
    # (the v3 scorer read a non-existent active key, so 0 shipped blobs carry
    # it) and v4 does not score CAERS. Its count-based "signal strength" tracks
    # how common an ingredient is, not its risk (e.g. calcium's reports are
    # pill-choking, not toxicity), so surfacing it would over-warn on safe
    # staples. Activating CAERS is a deliberate, risk-calibrated future feature.

    # Transparency nuance — gate on v4 (faithful to whether v4 penalised it).
    if _neg(transp_comp, "B3_claim_compliance"):
        penalties.append({"id": "B3", "label": "Compliance claim violation",
                          "score": safe_float(transp_comp.get("B3_claim_compliance"), 0)})
    if _neg(transp_pen, "B5_proprietary_blend_opacity"):
        penalties.append({"id": "B5", "label": "Proprietary blend opacity",
                          "score": safe_float(transp_pen.get("B5_proprietary_blend_opacity"), 0),
                          "blend_count": int(safe_float(transp_meta.get("B5_blend_count"), 0))})
    if _neg(transp_pen, "B6_marketing_claims"):
        penalties.append({"id": "B6", "label": "Unsubstantiated disease claims",
                          "score": safe_float(transp_pen.get("B6_marketing_claims"), 0)})

    # Manufacturer / quality-system violation (enriched manufacturer data).
    mv = safe_dict(safe_dict(enriched.get("manufacturer_data")).get("violations"))
    if safe_bool(mv.get("found")):
        item = {"id": "violation", "label": "Scoring violation penalty"}
        mv_score = safe_float(mv.get("total_deduction_applied"), 0)
        if mv_score:
            item["score"] = -abs(mv_score)
        penalties.append(item)

    return bonuses, penalties


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
    verdict = safe_str(scored.get("verdict")).upper()
    # V4 cutover: the shipped /100 score (overlay sets score_100_equivalent
    # from quality_score_v4_100); 75/100 mirrors the retired V3 score_80>=60.
    score_100 = safe_float(scored.get("score_100_equivalent"), 0) or 0
    # Evidence copy reads the v4 evidence pillar (/20), not the retired v3
    # section_scores.C — keeps the user-facing string aligned with the shipped score.
    v4_evidence = safe_float(safe_dict(safe_dict(scored.get("_v4_pillars")).get("evidence")).get("score"), 0)

    if safe_bool(enriched.get("is_trusted_manufacturer")) and safe_bool(enriched.get("has_full_disclosure")):
        positive = "Trusted manufacturer with full label disclosure."
    elif v4_evidence >= 12:
        positive = "Backed by meaningful clinical evidence."
    elif score_100 >= 75:
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

    Sprint C (2026-05-13) — also forwards the additional context fields
    the warning dict already carries (``ban_context``, ``detail``,
    ``regulatory_date_label``, ``date``, ``source_urls``) so Flutter's
    blocked-product view can render the regulatory date line, mechanism
    paragraph, and real citation URLs instead of falling back to the
    generic FDA CDER index. The three legacy fields
    (``safety_warning_one_liner`` / ``safety_warning`` / ``substance_name``)
    remain MANDATORY and are validated by
    ``_validate_banned_preflight_propagation``. The new fields are
    OPTIONAL — only forwarded when the warning dict has them populated,
    and Flutter must tolerate any subset being absent. This keeps the
    blob lean and avoids empty-string footguns on the consumer side.
    """
    if not has_banned_substance(enriched):
        return None
    for w in warnings_list or []:
        if not isinstance(w, dict) or w.get("type") != "banned_substance":
            continue
        one = w.get("safety_warning_one_liner")
        body = w.get("safety_warning")
        if not (
            isinstance(one, str) and one.strip()
            and isinstance(body, str) and body.strip()
        ):
            continue
        title = safe_str(w.get("title"))
        substance = title.split(":", 1)[-1].strip() if ":" in title else title or None
        bsd: Dict[str, Any] = {
            "safety_warning_one_liner": one.strip(),
            "safety_warning": body.strip(),
            "substance_name": substance,
        }
        ban_context = w.get("ban_context")
        if isinstance(ban_context, str) and ban_context.strip():
            bsd["ban_context"] = ban_context.strip()
        detail_text = w.get("detail")
        if isinstance(detail_text, str) and detail_text.strip():
            bsd["detail"] = detail_text.strip()
        reg_label = w.get("regulatory_date_label")
        if isinstance(reg_label, str) and reg_label.strip():
            bsd["regulatory_date_label"] = reg_label.strip()
        reg_date = w.get("date")
        if isinstance(reg_date, str) and reg_date.strip():
            bsd["date"] = reg_date.strip()
        source_urls = w.get("source_urls")
        if isinstance(source_urls, list):
            cleaned = [u.strip() for u in source_urls
                       if isinstance(u, str) and u.strip()]
            if cleaned:
                bsd["source_urls"] = cleaned
        return bsd
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


def _compute_display_label(ingredient: Dict[str, Any], match: Optional[Dict[str, Any]] = None) -> str:
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
    match = match if isinstance(match, dict) else {}
    label_display_name = safe_str(match.get("label_display_name"))
    if label_display_name:
        # Label-native identity: authoritative over the heuristic and over the
        # canonical standard_name. Repaired -> corrected label ("EPA"); clean ->
        # literal label text (branded tokens and plant parts preserved).
        return label_display_name
    disposition = safe_str(match.get("identity_disposition"))
    if disposition in ("identity_conflict", "missing_display_label"):
        # Never let an unresolved/undisplayable identity borrow the canonical
        # standard_name as a display; keep the literal label or nothing. The
        # release audit blocks these before ship; Flutter shows "Identity needs
        # review".
        return (
            safe_str(match.get("source_label_name"))
            or safe_str(ingredient.get("raw_source_text"))
            or safe_str(ingredient.get("name"))
        )
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
# Sprint E1.2.5 follow-up (2026-05-13): "nutrition_fact" was added to
# the cleaner's display trail so the E1.6 defense gate below can
# distinguish a real classifier bug from a legitimate-nutrition-facts
# product whose actives panel is entirely macronutrient rows.
_DISPLAY_TYPE_TO_REASON = {
    "structural_container": _DROP_REASON_STRUCTURAL_HEADER,
    "summary_wrapper": _DROP_REASON_SUMMARY_WRAPPER,
    "inactive_ingredient": _DROP_REASON_CLASSIFIED_INACTIVE,
    "nutrition_fact": _DROP_REASON_NUTRITION_FACT,
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
# a validator asserts that the blob does not silently drop the entire
# label-facing inactive surface. Row-level canaries cover partial loss.
_NONE_PLACEHOLDER_NAMES = {"none", "n/a", "na", ""}


def _validate_inactive_preservation(
    blob: Dict[str, Any],
    raw_inactives_count: int,
    dsld_id: str,
    intentional_drops: int = 0,
) -> None:
    """Raise ``ValueError`` if raw DSLD had ≥1 real inactive but the
    blob emits an empty inactive_ingredients list. Also enforces: the
    literal "None" placeholder must never leak into a blob entry.

    ``intentional_drops`` is retained for backwards-compatible tests and
    historical blobs. Current export keeps descriptor / active-only rows
    visible in `inactive_ingredients[]` and marks their disposition instead
    of dropping them from the label-facing surface.
    """
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
    effective_raw_inactives = raw_inactives_count - intentional_drops
    if effective_raw_inactives > 0 and len(blob_inactives) == 0:
        raise ValueError(
            f"[{dsld_id}] raw DSLD disclosed {raw_inactives_count} real "
            f"inactive(s) ({intentional_drops} intentionally dropped as "
            f"label_descriptor/active_only; {effective_raw_inactives} "
            f"net) but blob emits 0. Filter regression — inspect "
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

    # Per-ingredient identity: include matched_rule_id (when present) or
    # ingredient_name so two resolver-synthesized warnings for DIFFERENT
    # banned actives (e.g. 7-Keto-DHEA + Garcinia on the same product)
    # don't collapse into one entry just because they share
    # severity/type/source. Interaction warnings already differ by
    # condition_id / drug_class_id so the addition is a no-op for them.
    return (
        _norm(w.get("severity")),
        _norm(w.get("canonical_id") or w.get("type")),
        _norm(w.get("condition_id") or w.get("condition_ids")),
        _norm(w.get("drug_class_id") or w.get("drug_class_ids")),
        _norm(w.get("source_rule") or w.get("source")),
        _norm(w.get("matched_rule_id") or w.get("ingredient_name")),
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
    "withanolide glycosides", "withanolides", "boswellic acids",
    "boswellic acid", "curcuminoids", "ginsenosides", "rosavins",
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
    r"(?<![\d\-\.])(\d{1,3})%\+?\s+("
    + "|".join(re.escape(c) for c in sorted(_STANDARDIZATION_COMPOUNDS, key=len, reverse=True))
    + r")\b",
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


_ZERO_DOSE_DUPLICATE_UNITS = _NP_SENTINELS | {"unspecified", "unknown", "not specified"}


def _ingredient_export_dedup_key(ingredient: Dict[str, Any]) -> str:
    """Stable identity for final-blob duplicate cleanup.

    Prefer canonical_id because this is a display/export hygiene pass, not a
    matcher. Falling back to names is intentionally conservative: only exact
    normalized label identity suppresses a placeholder row.
    """
    canonical_id = safe_str(ingredient.get("canonical_id")).lower()
    if canonical_id:
        return f"canonical:{canonical_id}"
    name = (
        safe_str(ingredient.get("standardName"))
        or safe_str(ingredient.get("standard_name"))
        or safe_str(ingredient.get("name"))
        or safe_str(ingredient.get("raw_source_text"))
    ).lower()
    return f"name:{re.sub(r'[^a-z0-9]+', ' ', name).strip()}" if name else ""


def _has_positive_export_dose(ingredient: Dict[str, Any]) -> bool:
    qty = safe_float(ingredient.get("quantity"), 0) or 0.0
    unit = safe_str(ingredient.get("unit")).strip().lower()
    return qty > 0 and unit not in _ZERO_DOSE_DUPLICATE_UNITS


def _is_zero_dose_placeholder_duplicate(
    ingredient: Dict[str, Any],
    positive_dose_keys: set[str],
) -> bool:
    key = _ingredient_export_dedup_key(ingredient)
    if not key or key not in positive_dose_keys:
        return False

    qty = safe_float(ingredient.get("quantity"), 0) or 0.0
    unit = safe_str(ingredient.get("unit")).strip().lower()
    if qty > 0 or unit not in _ZERO_DOSE_DUPLICATE_UNITS:
        return False

    # Keep truly undisclosed blend members. They carry transparency meaning
    # even when a separate positive-dose row for the same canonical exists.
    if safe_str(ingredient.get("dose_status")) == "not_disclosed_blend":
        return False

    # Never drop a row that carries a product-safety concern. Informational
    # safety_hits are canonical-level payloads and remain attached to the
    # retained positive-dose duplicate for the same canonical.
    if ingredient.get("is_safety_concern") or ingredient.get("is_banned"):
        return False
    if safe_list(ingredient.get("safety_flags")):
        return False

    return True


def _suppress_zero_dose_duplicate_active_rows(
    ingredients: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Remove stale zero-dose placeholders when a real same-active row exists.

    Some enriched products carry both a recognized non-scorable active row
    (`quantity=0`, `unit=unspecified`) and the later recovered dose-bearing row
    for the same canonical, e.g. EPA/DHA in omega labels. Strict v4 scoring
    already consumes `ingredients_scorable`, so the duplicate does not change
    scores. This cleanup prevents final detail blobs, explain tools, and UI
    surfaces from showing both rows as if the label had two EPA/DHA entries.
    """
    positive_dose_keys = {
        _ingredient_export_dedup_key(ing)
        for ing in ingredients
        if isinstance(ing, dict) and _has_positive_export_dose(ing)
    }
    positive_dose_keys.discard("")
    if not positive_dose_keys:
        return ingredients

    return [
        ing for ing in ingredients
        if not (
            isinstance(ing, dict)
            and _is_zero_dose_placeholder_duplicate(ing, positive_dose_keys)
        )
    ]


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
    warning_messages = set()

    def add_warning(kind: str, severity: str, message: str) -> None:
        if not message or message in warning_messages:
            return
        warning_messages.add(message)
        raw_warnings.append((kind, severity, message))

    # Banned substances
    for sub in contaminant_matches(enriched):
        status = safe_str(sub.get("status")).lower()
        name = safe_str(sub.get("ingredient") or sub.get("banned_name") or sub.get("name"))
        if status == "banned":
            add_warning("banned_substance", "critical", f"Banned substance: {name}")
        elif status == "recalled":
            add_warning("recalled_ingredient", "high", f"Recalled ingredient: {name}")
        elif status == "high_risk":
            add_warning("banned_substance", "high", f"High-risk ingredient: {name}")
        elif status == "watchlist":
            add_warning(
                "watchlist_substance",
                safe_str(sub.get("severity_level"), "moderate"),
                f"Watchlist ingredient: {name}",
            )

    for flag in contaminant_safety_flags(enriched):
        source = normalize_safety_source(flag.get("source_db") or flag.get("matched_source"))
        if source != "banned_recalled_ingredients":
            continue
        status = safe_str(flag.get("status")).lower()
        name = _safety_flag_display_name(flag)
        warning_type = _banned_warning_type_for_status(status)
        title_prefix = _banned_warning_title_prefix_for_status(status)
        severity = safe_str(
            flag.get("severity"),
            "critical" if status == "banned" else "high" if status == "recalled" else "moderate",
        )
        add_warning(warning_type, severity, f"{title_prefix}: {name}")

    # Harmful additives
    for h in safe_list(enriched.get("harmful_additives")):
        if not isinstance(h, dict):
            continue
        sev = safe_str(h.get("severity_level"), "moderate")
        name = safe_str(h.get("additive_name") or h.get("ingredient"))
        add_warning("harmful_additive", sev, f"{sev.title()}-risk additive: {name}")

    # RDA/UL dose safety flags
    for flag in safe_list(safe_dict(enriched.get("rda_ul_data")).get("safety_flags")):
        if not isinstance(flag, dict):
            continue
        nutrient = safe_str(flag.get("nutrient") or flag.get("standard_name") or flag.get("canonical_id"))
        if not nutrient:
            continue
        pct_ul = safe_float(flag.get("pct_ul"))
        sev = safe_str(flag.get("severity"))
        if not sev:
            sev = "high" if pct_ul is not None and pct_ul >= 150 else "moderate"
        if pct_ul is not None:
            message = f"Upper-limit warning: {nutrient} at {pct_ul:.0f}% of UL"
        else:
            message = f"Upper-limit warning: {nutrient}"
        add_warning("dose_safety", sev, message)

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
                warning_type = safe_str(ch.get("warning_type"), "interaction")
                add_warning(warning_type, sev, f"Interaction: {ing_name} / {cond}")

    # Dietary sensitivity
    ds = safe_dict(enriched.get("dietary_sensitivity_data"))
    dietary_warnings = safe_list(ds.get("warnings"))
    for warning in dietary_warnings:
        if not isinstance(warning, dict):
            continue
        add_warning(
            "dietary",
            safe_str(warning.get("severity"), "informational"),
            safe_str(warning.get("message")),
        )
    if not dietary_warnings:
        sugar = safe_dict(ds.get("sugar"))
        sodium = safe_dict(ds.get("sodium"))
        if sugar.get("level") in ("moderate", "high"):
            add_warning(
                "dietary", "informational",
                f"Sugar: {sugar.get('amount_g', 0)}g ({safe_str(sugar.get('level_display'))})"
            )
        if sodium.get("level") in ("moderate", "high"):
            add_warning(
                "dietary", "info",
                f"Sodium: {sodium.get('amount_mg', 0)}mg ({safe_str(sodium.get('level_display'))})"
            )

    # Product status
    product_status = safe_str(enriched.get("status")).lower()
    if product_status == "discontinued":
        disc_date = safe_str(enriched.get("discontinuedDate"))[:10]
        add_warning("status", "info", f"Discontinued ({disc_date})")
    elif product_status == "off_market":
        add_warning("status", "info", "Off market")

    # Sort by priority
    raw_warnings.sort(key=lambda w: (
        WARNING_PRIORITY.get(w[0], 99),
        SEVERITY_PRIORITY.get(w[1], 99),
    ))

    return [w[2] for w in raw_warnings[:TOP_WARNINGS_MAX]]


# ─── Blocking Reason ───

def blob_has_critical_banned_warning(detail_blob: Optional[Dict]) -> bool:
    """True when a detail blob carries a critical banned-substance warning."""
    if not isinstance(detail_blob, dict):
        return False
    for list_key in ("warnings", "warnings_profile_gated"):
        for warning in safe_list(detail_blob.get(list_key)):
            if not isinstance(warning, dict):
                continue
            if (
                safe_str(warning.get("type")) == "banned_substance"
                and safe_str(warning.get("severity")).lower() == "critical"
            ):
                return True
    return False


def blob_has_safety_blocking_warning(detail_blob: Optional[Dict]) -> bool:
    if not isinstance(detail_blob, dict):
        return False
    blocking_types = {"banned_substance", "recalled_ingredient", "high_risk_ingredient"}
    for list_key in ("warnings", "warnings_profile_gated"):
        for warning in safe_list(detail_blob.get(list_key)):
            if not isinstance(warning, dict):
                continue
            if safe_str(warning.get("type")) in blocking_types:
                return True
    return False


# Hard-safety types that disqualify a base SAFE verdict.
#
# Two tiers govern this contract:
#   1. ALWAYS_DISQUALIFY types — the regulatory classification itself implies the
#      product cannot honestly read SAFE regardless of warning severity. A
#      watchlist substance (titanium dioxide, phthalates, anatabine, octopamine,
#      etc.) is by definition under regulatory observation — moderate severity
#      is normal for these and the type tells the whole story.
#   2. SEVERITY_GATED types — severity classifies the impact. High-risk
#      ingredients, contraindications, and adulterants only disqualify SAFE
#      when the severity is in the hard set (high/critical/contraindicated/avoid).
#      A "low" severity high_risk warning is informational; we keep SAFE.
#
# banned_substance and recalled_ingredient also live in ALWAYS_DISQUALIFY but
# generally route through the banned-override path before this helper runs —
# they are kept here for defense in depth so a stray profile-gated emission
# never lets a banned signal ship as SAFE.
#
# Mirrors the contract enforced by test_release_gate_banned_safe_contradictions.py
# and extends it to cover the watchlist/regulatory-observation surface raised
# during the post-DV release-gate audit (Titanium Dioxide E171 etc.).
_HARD_SAFETY_TYPES_ALWAYS_DISQUALIFY = frozenset({
    "banned_substance",
    "recalled_ingredient",
    "adulterant",
    "watchlist_substance",
})
_HARD_SAFETY_TYPES_SEVERITY_GATED = frozenset({
    "contraindicated",
    "high_risk_ingredient",
})
_HARD_SAFETY_SEVERITIES = frozenset({
    "critical",
    "high",
    "contraindicated",
    "avoid",
})


def blob_has_profile_gated_hard_safety_warning(detail_blob: Optional[Dict]) -> bool:
    """True when a detail blob carries a hard-safety warning that disqualifies SAFE.

    Scans BOTH warnings[] and warnings_profile_gated[] (the per-user-condition
    list and the general list — a hard-safety signal in either disqualifies the
    base SAFE verdict). See _HARD_SAFETY_TYPES_ALWAYS_DISQUALIFY and
    _HARD_SAFETY_TYPES_SEVERITY_GATED for the tier rules.
    """
    if not isinstance(detail_blob, dict):
        return False
    for list_key in ("warnings", "warnings_profile_gated"):
        for warning in safe_list(detail_blob.get(list_key)):
            if not isinstance(warning, dict):
                continue
            warning_type = safe_str(warning.get("type"))
            if (
                warning_type == "watchlist_substance"
                and safe_str(warning.get("ingredient_role")).lower() == "inactive"
                and safe_str(warning.get("inactive_policy")).lower() == "excipient_acceptable"
                and safe_str(warning.get("display_mode_default")).lower() == "informational"
            ):
                continue
            if warning_type in _HARD_SAFETY_TYPES_ALWAYS_DISQUALIFY:
                return True
            if warning_type in _HARD_SAFETY_TYPES_SEVERITY_GATED:
                severity = safe_str(warning.get("severity")).lower()
                if severity in _HARD_SAFETY_SEVERITIES:
                    return True
    return False


def derive_blocking_reason(enriched: Dict, scored: Dict) -> Optional[str]:
    """Derive blocking_reason from B0 gate results."""
    if has_banned_substance(enriched):
        return "banned_ingredient"

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

    for flag in safety_flag_status_matches(enriched, "banned", "recalled", "high_risk"):
        status = safe_str(flag.get("status")).lower()
        if status == "banned":
            return "banned_ingredient"
        if status == "recalled":
            return "recalled_ingredient"
        if status == "high_risk":
            return "high_risk_ingredient"

    return "safety_block" if verdict in ("BLOCKED", "UNSAFE") else None


# ─── Has Recalled Ingredient ───

def has_recalled_ingredient(enriched: Dict) -> bool:
    """True ONLY for status='recalled' ingredient hits.

    Per the export-gate contract, the three banned_recalled statuses route
    to three distinct surfaces:
      * status='banned'    → has_banned_substance=1
      * status='recalled'  → has_recalled_ingredient=1
      * status='high_risk' → neither flag; surfaced via warnings[] +
                             blocking_reason='high_risk_ingredient'

    So high_risk inactives like Titanium Dioxide and Talc remain visible
    via the warnings synthesizer (see build_detail_blob → warnings loop)
    rather than co-opting the recalled flag. Falls back to the resolver
    index for recalled aliases the contaminant_data path missed.
    """
    if contaminant_status_matches(enriched, "recalled"):
        return True
    if safety_flag_status_matches(enriched, "recalled"):
        return True
    return _resolver_status_in(enriched, ("recalled",))


# ─── Detail Blob Builder ───

def _build_v4_score_explanation(pillars: Any) -> Optional[Dict[str, Any]]:
    """Top strength / drag pillar reasons — the consumer "how it scored X".

    Ranks the six v4 pillars by their (score - max) delta: the fullest pillars
    are strengths, the largest gaps are drags. Returns None for a non-scored
    product (no pillars)."""
    if not isinstance(pillars, dict) or not pillars:
        return None
    ranked = []
    for name, p in pillars.items():
        if not isinstance(p, dict):
            continue
        try:
            delta = float(p.get("score")) - float(p.get("max"))
        except (TypeError, ValueError):
            continue
        ranked.append((delta, name, p.get("reason")))
    if not ranked:
        return None
    ranked.sort(key=lambda r: r[0])  # ascending: biggest drags first
    drags = [{"pillar": n, "reason": rs} for d, n, rs in ranked if d < -1e-9][:3]
    strengths = [{"pillar": n, "reason": rs} for d, n, rs in reversed(ranked)][:3]
    return {"strengths": strengths, "drags": drags}


_PRENATAL_POSITIONING_RE = re.compile(
    r"\b(prenatal|pre[\s-]?natal|pregnancy|pregnant|preconception|"
    r"pre[\s-]?conception|trying\s+to\s+conceive|ttc|maternal|expecting|"
    r"gestation)\b",
    re.IGNORECASE,
)
_PRENATAL_UNAMBIGUOUS_RE = re.compile(
    r"\b(prenatal|pre[\s-]?natal|preconception|pre[\s-]?conception|"
    r"trying\s+to\s+conceive|ttc|maternal|expecting)\b",
    re.IGNORECASE,
)
_PREGNANCY_NEGATION_RE = re.compile(
    r"\b(not|non|avoid|contraindicated|do\s+not\s+use|should\s+not\s+use|"
    r"consult)\b[^.;:,]{0,60}\b(pregnant|pregnancy|lactating|breastfeeding)\b",
    re.IGNORECASE,
)
_COMPLETENESS_CLAIM_RE = re.compile(
    r"\b(complete|all[\s-]?in[\s-]?one|comprehensive|full[\s-]?spectrum|"
    r"total|whole\s+prenatal)\b",
    re.IGNORECASE,
)

_PRENATAL_CORE_ANCHORS = ("folate", "iron", "iodine", "vitamin_d", "vitamin_b12")
_PRENATAL_COMPLEMENT_ANCHORS = ("choline", "dha")
_PRENATAL_ANCHORS = (
    {
        "id": "folate",
        "label": "Folate",
        "target": 600.0,
        "unit": "mcg DFE",
        "ul": 1667.0,
        "terms": ("folate", "folic acid", "vitamin b9", "5 mthf", "methylfolate"),
    },
    {
        "id": "iron",
        "label": "Iron",
        "target": 27.0,
        "unit": "mg",
        "ul": 45.0,
        "terms": ("iron",),
    },
    {
        "id": "iodine",
        "label": "Iodine",
        "target": 220.0,
        "unit": "mcg",
        "ul": 1100.0,
        "terms": ("iodine", "iodide"),
    },
    {
        "id": "vitamin_d",
        "label": "Vitamin D",
        "target": 15.0,
        "unit": "mcg",
        "ul": 100.0,
        "terms": ("vitamin d", "vitamin d3", "cholecalciferol"),
    },
    {
        "id": "vitamin_b12",
        "label": "Vitamin B12",
        "target": 2.6,
        "unit": "mcg",
        "ul": None,
        "terms": ("vitamin b12", "b12", "cobalamin", "methylcobalamin"),
    },
    {
        "id": "choline",
        "label": "Choline",
        "target": 450.0,
        "unit": "mg",
        "ul": 3500.0,
        "terms": ("choline", "phosphatidylcholine"),
    },
    {
        "id": "dha",
        "label": "DHA",
        "target": 200.0,
        "unit": "mg",
        "ul": None,
        "terms": ("dha", "docosahexaenoic", "docosahexaenoic acid"),
    },
    {
        "id": "vitamin_a",
        "label": "Vitamin A",
        "target": 770.0,
        "unit": "mcg RAE",
        # UL depends on preformed vitamin A form; the existing RDA/UL engine
        # owns that form-sensitive over-UL decision.
        "ul": None,
        "terms": ("vitamin a", "retinol", "retinyl", "beta carotene"),
    },
)
_ADULT_MULTI_CORE_ANCHORS = (
    "vitamin_a",
    "vitamin_c",
    "vitamin_d",
    "vitamin_e",
    "vitamin_k",
    "vitamin_b1_thiamine",
    "vitamin_b2_riboflavin",
    "vitamin_b3_niacin",
    "vitamin_b6",
    "folate",
    "vitamin_b12",
    "biotin",
    "pantothenic_acid",
    "iodine",
    "zinc",
    "selenium",
    "copper",
)
_ADULT_MULTI_ANCHORS = (
    {
        "id": "vitamin_a",
        "label": "Vitamin A",
        "target": 900.0,
        "unit": "mcg RAE",
        "ul": None,
        "terms": ("vitamin a", "retinol", "retinyl", "beta carotene"),
    },
    {
        "id": "vitamin_c",
        "label": "Vitamin C",
        "target": 90.0,
        "unit": "mg",
        "ul": None,
        "terms": ("vitamin c", "ascorbic acid", "ascorbate"),
    },
    {
        "id": "vitamin_d",
        "label": "Vitamin D",
        "target": 20.0,
        "unit": "mcg",
        "ul": 100.0,
        "terms": ("vitamin d", "vitamin d3", "cholecalciferol"),
    },
    {
        "id": "vitamin_e",
        "label": "Vitamin E",
        "target": 15.0,
        "unit": "mg",
        "ul": None,
        "terms": ("vitamin e", "tocopherol", "tocotrienol"),
    },
    {
        "id": "vitamin_k",
        "label": "Vitamin K",
        "target": 120.0,
        "unit": "mcg",
        "ul": None,
        "terms": ("vitamin k", "phylloquinone", "menaquinone", "mk 7", "mk7"),
    },
    {
        "id": "vitamin_b1_thiamine",
        "label": "Thiamin",
        "target": 1.2,
        "unit": "mg",
        "ul": None,
        "terms": ("thiamin", "thiamine", "vitamin b1"),
    },
    {
        "id": "vitamin_b2_riboflavin",
        "label": "Riboflavin",
        "target": 1.3,
        "unit": "mg",
        "ul": None,
        "terms": ("riboflavin", "vitamin b2"),
    },
    {
        "id": "vitamin_b3_niacin",
        "label": "Niacin",
        "target": 16.0,
        "unit": "mg",
        "ul": None,
        "terms": ("niacin", "niacinamide", "vitamin b3"),
    },
    {
        "id": "vitamin_b6",
        "label": "Vitamin B6",
        "target": 1.7,
        "unit": "mg",
        "ul": 100.0,
        "terms": ("vitamin b6", "pyridoxine", "pyridoxal"),
    },
    {
        "id": "folate",
        "label": "Folate",
        "target": 400.0,
        "unit": "mcg DFE",
        "ul": None,
        "terms": ("folate", "folic acid", "vitamin b9", "5 mthf", "methylfolate"),
    },
    {
        "id": "vitamin_b12",
        "label": "Vitamin B12",
        "target": 2.4,
        "unit": "mcg",
        "ul": None,
        "terms": ("vitamin b12", "b12", "cobalamin", "methylcobalamin"),
    },
    {
        "id": "biotin",
        "label": "Biotin",
        "target": 30.0,
        "unit": "mcg",
        "ul": None,
        "terms": ("biotin", "vitamin b7"),
    },
    {
        "id": "pantothenic_acid",
        "label": "Pantothenic Acid",
        "target": 5.0,
        "unit": "mg",
        "ul": None,
        "terms": ("pantothenic acid", "pantothenate", "vitamin b5"),
    },
    {
        "id": "iodine",
        "label": "Iodine",
        "target": 150.0,
        "unit": "mcg",
        "ul": 1100.0,
        "terms": ("iodine", "iodide"),
    },
    {
        "id": "zinc",
        "label": "Zinc",
        "target": 11.0,
        "unit": "mg",
        "ul": 40.0,
        "terms": ("zinc",),
    },
    {
        "id": "selenium",
        "label": "Selenium",
        "target": 55.0,
        "unit": "mcg",
        "ul": 400.0,
        "terms": ("selenium", "selenomethionine", "selenite"),
    },
    {
        "id": "copper",
        "label": "Copper",
        "target": 0.9,
        "unit": "mg",
        "ul": 10.0,
        "terms": ("copper",),
    },
)
_IRON_ANCHOR = {
    "id": "iron",
    "label": "Iron",
    "target": 18.0,
    "unit": "mg",
    "ul": 45.0,
    "terms": ("iron",),
}


def _space_normalized(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", safe_str(value).lower()).strip()


def _flatten_text(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        out: List[str] = []
        for item in value.values():
            out.extend(_flatten_text(item))
        return out
    if isinstance(value, (list, tuple, set)):
        out = []
        for item in value:
            out.extend(_flatten_text(item))
        return out
    return [str(value)]


def _term_present(haystack: str, terms: Tuple[str, ...]) -> bool:
    padded = f" {_space_normalized(haystack)} "
    for term in terms:
        normalized = _space_normalized(term)
        if normalized and f" {normalized} " in padded:
            return True
    return False


def _product_positioning_text(enriched: Dict) -> Tuple[str, str]:
    name_text = " ".join(
        safe_str(enriched.get(key))
        for key in ("product_name", "fullName", "displayName", "name")
        if safe_str(enriched.get(key))
    )
    context_parts = [name_text]
    for key in (
        "targetGroups",
        "target_groups",
        "intended_use",
        "intendedUse",
        "audience",
        "population",
    ):
        context_parts.extend(_flatten_text(enriched.get(key)))
    return name_text, " ".join(part for part in context_parts if safe_str(part))


def _is_prenatal_positioned(enriched: Dict) -> bool:
    name_text, context_text = _product_positioning_text(enriched)
    if _PRENATAL_UNAMBIGUOUS_RE.search(name_text):
        return True
    if _PREGNANCY_NEGATION_RE.search(context_text):
        return False
    return bool(_PRENATAL_POSITIONING_RE.search(context_text))


def _ingredient_anchor_key(ingredient: Dict[str, Any]) -> str:
    fields = (
        ingredient.get("canonical_id"),
        ingredient.get("nutrient_group_id"),
        ingredient.get("standard_name"),
        ingredient.get("standardName"),
        ingredient.get("name"),
        ingredient.get("display_label"),
        ingredient.get("raw_source_text"),
    )
    return " ".join(_space_normalized(field) for field in fields if safe_str(field))


def _ingredient_matches_anchor(ingredient: Dict[str, Any], anchor: Dict[str, Any]) -> bool:
    canonical = _space_normalized(ingredient.get("canonical_id")).replace(" ", "_")
    group = _space_normalized(ingredient.get("nutrient_group_id")).replace(" ", "_")
    anchor_id = safe_str(anchor.get("id"))
    if canonical == anchor_id or group == anchor_id:
        return True
    if anchor_id == "folate" and canonical in {"vitamin_b9_folate", "vitamin_b9"}:
        return True
    if anchor_id == "vitamin_b12" and canonical in {"vitamin_b12_cobalamin", "cobalamin"}:
        return True
    if anchor_id == "dha" and canonical in {"dha", "docosahexaenoic_acid"}:
        return True
    return _term_present(_ingredient_anchor_key(ingredient), tuple(anchor.get("terms") or ()))


def _amount_in_unit(amount: Any, source_unit: Any, target_unit: str) -> Optional[float]:
    value = safe_float(amount)
    if value is None:
        return None
    source = _space_normalized(source_unit)
    target = _space_normalized(target_unit)
    if not source or not target:
        return value
    if source == target or source.startswith(target) or target.startswith(source):
        return value
    source_is_mcg = source.startswith("mcg") or source.startswith("ug")
    target_is_mcg = target.startswith("mcg") or target.startswith("ug")
    source_is_mg = source.startswith("mg")
    target_is_mg = target.startswith("mg")
    source_is_g = source == "g" or source.startswith("gram")
    if source_is_mcg and target_is_mg:
        return value / 1000.0
    if source_is_mg and target_is_mcg:
        return value * 1000.0
    if source_is_g and target_is_mg:
        return value * 1000.0
    if source_is_g and target_is_mcg:
        return value * 1_000_000.0
    return value


def _anchor_amount(ingredients: List[Dict], anchor: Dict[str, Any]) -> Tuple[Optional[float], Optional[str]]:
    best_amount = None
    best_unit = None
    for ingredient in ingredients:
        if not isinstance(ingredient, dict) or not _ingredient_matches_anchor(ingredient, anchor):
            continue
        raw_amount = (
            ingredient.get("normalized_amount")
            if ingredient.get("normalized_amount") is not None
            else ingredient.get("normalized_value")
            if ingredient.get("normalized_value") is not None
            else ingredient.get("quantity")
            if ingredient.get("quantity") is not None
            else ingredient.get("dosage")
        )
        raw_unit = (
            ingredient.get("normalized_unit")
            or ingredient.get("dosage_unit")
            or ingredient.get("unit")
        )
        converted = _amount_in_unit(raw_amount, raw_unit, safe_str(anchor.get("unit")))
        if converted is None:
            continue
        if best_amount is None or converted > best_amount:
            best_amount = converted
            best_unit = safe_str(anchor.get("unit") or raw_unit)
    return best_amount, best_unit


def _build_anchor_coverage(
    ingredients: List[Dict],
    rda_ul_data: Dict,
    anchors_source: Tuple[Dict[str, Any], ...],
    *,
    source: str,
) -> Dict[str, Any]:
    anchors = []
    summary = {
        "missing": [],
        "below_target": [],
        "covered": [],
        "near_ul": [],
        "above_ul": [],
    }
    present_any = False
    safety_rows = {
        _space_normalized(row.get("nutrient") or row.get("ingredient_name")): row
        for row in safe_list(rda_ul_data.get("adequacy_results"))
        if isinstance(row, dict)
    }

    for anchor in anchors_source:
        anchor_id = safe_str(anchor["id"])
        amount, unit = _anchor_amount(ingredients, anchor)
        present = amount is not None and amount > 0
        present_any = present_any or present
        target = safe_float(anchor.get("target"))
        ul = safe_float(anchor.get("ul"))
        status = "missing"
        if present:
            status = "covered"
            if target and amount < target:
                status = "below_target"
            if ul and amount >= ul:
                status = "above_ul"
            elif ul and amount >= ul * 0.8:
                status = "near_ul"

        row = safety_rows.get(_space_normalized(anchor.get("label")))
        if isinstance(row, dict) and row.get("over_ul"):
            status = "above_ul"

        anchors.append({
            "nutrient_id": anchor_id,
            "label": anchor["label"],
            "status": status,
            "amount": round(amount, 4) if amount is not None else None,
            "unit": unit or anchor["unit"],
            "target": target,
            "target_unit": anchor["unit"],
            "ul": ul,
            "source": source,
        })
        summary[status].append(anchor_id)

    return {
        "scoring_impact": "none",
        "anchors": anchors,
        "summary": summary,
        "has_any_anchor": present_any,
    }


def _build_prenatal_coverage(ingredients: List[Dict], rda_ul_data: Dict) -> Dict[str, Any]:
    return _build_anchor_coverage(
        ingredients,
        rda_ul_data,
        _PRENATAL_ANCHORS,
        source="prenatal_anchor_table",
    )


def _build_adult_multi_coverage(ingredients: List[Dict], rda_ul_data: Dict) -> Dict[str, Any]:
    return _build_anchor_coverage(
        ingredients,
        rda_ul_data,
        _ADULT_MULTI_ANCHORS,
        source="adult_multi_anchor_table",
    )


def _present_only_coverage(coverage: Dict[str, Any]) -> Dict[str, Any]:
    anchors = [
        row for row in safe_list(coverage.get("anchors"))
        if isinstance(row, dict) and safe_str(row.get("status")) != "missing"
    ]
    summary = {
        "missing": [],
        "below_target": [],
        "covered": [],
        "near_ul": [],
        "above_ul": [],
    }
    for row in anchors:
        status = safe_str(row.get("status"))
        nutrient_id = safe_str(row.get("nutrient_id"))
        if status in summary and nutrient_id:
            summary[status].append(nutrient_id)
    return {
        "scoring_impact": coverage.get("scoring_impact", "none"),
        "anchors": anchors,
        "summary": summary,
        "has_any_anchor": bool(anchors),
    }


def _has_multivitamin_shape(enriched: Dict, ingredients: List[Dict]) -> bool:
    taxonomy = safe_dict(enriched.get("supplement_taxonomy"))
    text = " ".join(
        safe_str(value)
        for value in (
            taxonomy.get("primary_type"),
            taxonomy.get("secondary_type"),
            enriched.get("product_name"),
        )
    )
    if re.search(r"\b(multivitamin|multi[\s-]?vitamin|multi_or_prenatal|prenatal_multi)\b", text, re.IGNORECASE):
        return True
    disclosed = [
        ing for ing in ingredients
        if isinstance(ing, dict) and safe_float(ing.get("quantity") or ing.get("normalized_amount"), 0) > 0
    ]
    return len(disclosed) >= 6


def _anchor_summary_present(coverage: Dict[str, Any]) -> set:
    summary = safe_dict(coverage.get("summary"))
    return (
        set(safe_list(summary.get("covered")))
        | set(safe_list(summary.get("below_target")))
        | set(safe_list(summary.get("near_ul")))
        | set(safe_list(summary.get("above_ul")))
    )


def _has_anchor_ingredient(ingredients: List[Dict], anchor: Dict[str, Any]) -> bool:
    for ingredient in ingredients:
        if isinstance(ingredient, dict) and _ingredient_matches_anchor(ingredient, anchor):
            amount, _unit = _anchor_amount([ingredient], anchor)
            if amount is not None and amount > 0:
                return True
    return False


def _classify_product_role(
    enriched: Dict,
    ingredients: List[Dict],
    prenatal_coverage: Dict[str, Any],
    adult_multi_coverage: Dict[str, Any],
) -> Dict[str, Any]:
    prenatal = _is_prenatal_positioned(enriched)
    present = _anchor_summary_present(prenatal_coverage)
    adult_present = _anchor_summary_present(adult_multi_coverage)
    core_present = sum(1 for anchor in _PRENATAL_CORE_ANCHORS if anchor in present)
    complement_present = sum(1 for anchor in _PRENATAL_COMPLEMENT_ANCHORS if anchor in present)
    adult_anchor_count = sum(1 for anchor in _ADULT_MULTI_CORE_ANCHORS if anchor in adult_present)
    iron_present = _has_anchor_ingredient(ingredients, _IRON_ANCHOR)
    role = "targeted_gap_filler"

    if prenatal:
        if core_present <= 1 and "dha" in present:
            role = "prenatal_dha_companion"
        elif core_present <= 1 and "choline" in present:
            role = "prenatal_choline_companion"
        elif core_present >= 4:
            role = "prenatal_complete" if complement_present == len(_PRENATAL_COMPLEMENT_ANCHORS) else "prenatal_base"
        else:
            role = "prenatal_support"
    elif _has_multivitamin_shape(enriched, ingredients):
        role = (
            "adult_multi_with_iron"
            if adult_anchor_count >= 12 and iron_present
            else "adult_multi_iron_free"
            if adult_anchor_count >= 12
            else "general_multi"
        )

    name_text, context_text = _product_positioning_text(enriched)
    claim_text = f"{name_text} {context_text}"
    mismatch = bool(
        role == "prenatal_base"
        and _COMPLETENESS_CLAIM_RE.search(claim_text)
        and ({"dha", "choline"} - present)
    )

    return {
        "product_role": role,
        "completeness_claim_mismatch": mismatch,
        "role_evidence": {
            "prenatal_positioned": prenatal,
            "core_anchor_count": core_present,
            "complement_anchor_count": complement_present,
            "present_prenatal_anchors": sorted(present),
            "adult_anchor_count": adult_anchor_count,
            "iron_present": iron_present,
            "present_adult_multi_anchors": sorted(adult_present),
        },
    }


def build_detail_blob(enriched: Dict, scored: Dict) -> Dict:
    """Build the per-product detail blob for caching/Supabase."""
    non_gmo_audit = derive_non_gmo_audit(enriched)
    omega3_audit = derive_omega3_audit(enriched, scored)
    proprietary_blend_audit = derive_proprietary_blend_audit(enriched, scored)
    supplement_type_audit = build_supplement_type_audit(enriched, scored)

    # Active ingredients
    iqd = safe_dict(enriched.get("ingredient_quality_data"))
    iqd_rows = [
        row for row in safe_list(iqd.get("ingredients")) if isinstance(row, dict)
    ]
    if not iqd_rows:
        iqd_rows = [
            row
            for row in safe_list(iqd.get("ingredients_skipped"))
            if isinstance(row, dict)
        ]
    used_iqd_rows: set[int] = set()

    def take_iqd_match(ingredient: Dict[str, Any]) -> Dict[str, Any]:
        """Return one unused IQD row for an active label row.

        Source path is the identity contract's stable row linkage. The label key
        and literal text fallbacks retain compatibility with older artifacts,
        while consuming each candidate prevents duplicate raw text from sharing
        a later row's repaired identity or display form.
        """
        source_path = safe_str(ingredient.get("raw_source_path"))
        source_label_key = safe_str(ingredient.get("source_label_key"))
        raw_source = safe_str(
            ingredient.get("raw_source_text") or ingredient.get("name")
        )

        def claim(predicate) -> Optional[Dict[str, Any]]:
            for index, row in enumerate(iqd_rows):
                if index not in used_iqd_rows and predicate(row):
                    used_iqd_rows.add(index)
                    return row
            return None

        if source_path:
            matched = claim(
                lambda row: safe_str(row.get("raw_source_path")) == source_path
            )
            if matched:
                return matched
        if source_label_key:
            matched = claim(
                lambda row: safe_str(row.get("source_label_key")) == source_label_key
            )
            if matched:
                return matched
        if raw_source:
            matched = claim(
                lambda row: safe_str(row.get("raw_source_text")) == raw_source
            )
            if matched:
                return matched
        return {}

    harmful_lookup = build_harmful_lookup(enriched)
    contaminant_lookup = build_contaminant_lookup(enriched)
    allergen_patterns = build_allergen_patterns(enriched)
    active_export_contract = _active_export_contract(enriched)
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
        if not _active_row_allowed_for_primary_export(
            ing,
            active_export_contract,
            harmful_lookup=harmful_lookup,
            contaminant_lookup=contaminant_lookup,
            allergen_patterns=allergen_patterns,
        ):
            continue
        raw = safe_str(ing.get("raw_source_text"))
        name = safe_str(ing.get("name"), raw)
        m = take_iqd_match(ing)
        ne = norm_data.get(raw, norm_data.get(name, {}))
        if not isinstance(ne, dict):
            ne = {}
        canonical_standard_name = safe_str(
            m.get("standard_name")
            or ing.get("standard_name")
            or ing.get("standardName")
            or name
        )
        standard_name = canonical_standard_name
        safety_flags = _supported_safety_flags(ing.get("safety_flags"))
        evidence_terms = _active_banned_recall_evidence_terms(
            raw_source_text=raw,
            name=name,
            standard_name=standard_name,
            forms=safe_list(ing.get("forms")),
            identity_mapped=safe_bool(m.get("mapped", ing.get("mapped"))),
        )
        ingredient_hits = matching_contaminant_hits(contaminant_lookup, raw, name)
        allergen_hits = matching_allergen_hits(allergen_patterns, raw, name)
        harmful_hit = None
        for term in collect_match_terms(raw, name):
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
        canonical_id = safe_str(m.get("canonical_id") or ing.get("canonical_id"))
        is_mapped = safe_bool(m.get("mapped", ing.get("mapped")))
        if not canonical_id:
            is_mapped = False
        active_safety_contract = _resolve_active_safety_contract(
            harmful_hit, harmful_ref, ingredient_hits,
            name_terms=evidence_terms,
            banned_recalled_index=_get_active_banned_recalled_index(),
            safety_flags=safety_flags,
        )
        projected_safety_flags = safety_flags or _safety_flags_from_contract(active_safety_contract)
        standard_name = _active_identity_name_for_export(
            name=name,
            upstream_standard_name=standard_name,
            canonical_id=canonical_id,
            safety_flags=projected_safety_flags,
        )
        dose_data_quality = (
            safe_dict(ing.get("dose_data_quality"))
            or safe_dict(m.get("dose_data_quality"))
            or safe_dict(safe_dict(ne.get("conversion_evidence")).get("dose_data_quality"))
        )
        ingredients.append({
            "raw_source_text": raw,
            "name": name,
            "standardName": standard_name,
            "normalized_key": safe_str(ing.get("normalized_key")),
            "forms": safe_list(ing.get("forms")),
            "quantity": safe_float(qty),
            "unit": safe_str(ing.get("unit")),
            "dailyValue": safe_float(ing.get("dailyValue")),
            "dose_data_quality": dose_data_quality or None,
            "standard_name": standard_name,
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
            "mapped": is_mapped,
            "safety_hits": combined_safety_hits,
            "safety_flags": projected_safety_flags,
            "normalized_amount": safe_float(ne.get("normalized_amount")),
            "normalized_unit": safe_str(ne.get("normalized_unit")),
            "conversion_evidence": safe_dict(ne.get("conversion_evidence")) or None,
            "role": "active",
            "parent_key": safe_str(m.get("parent_key") or ing.get("normalized_key")),
            "dosage": safe_float(qty),
            "dosage_unit": safe_str(ing.get("unit")),
            "normalized_value": safe_float(ne.get("normalized_amount")),
            "is_mapped": is_mapped,
            # canonical_id — foundational identifier for interactions, stack
            # logic, evidence routing, biomarker scoring, dedup, and analytics.
            # The enricher writes it into both activeIngredients[].canonical_id
            # AND ingredient_quality_data.ingredients[].canonical_id (`m`).
            # Prefer `m` (post-enrichment match) over `ing` (raw label entry).
            "canonical_id": canonical_id,
            # nutrient_group_id — display/dual-read roll-up of authored
            # target redirects (e.g. vitamin_k1 -> vitamin_k) so the Nutrients
            # tab aggregates K1 + K2 as one "Vitamin K". Null unless a
            # redirect applies; the app groups by `nutrient_group_id ??
            # canonical_id`. NEVER use this for dedup.
            "nutrient_group_id": _nutrient_group_id(
                safe_str(m.get("canonical_redirect_from") or m.get("matched_entry_id") or canonical_id)
            ),
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
            "is_safety_concern": active_safety_contract["is_safety_concern"],
            "is_banned": active_safety_contract["is_banned"],
            "safety_reason": active_safety_contract["safety_reason"],
            "matched_source": active_safety_contract["matched_source"],
            "matched_rule_id": active_safety_contract["matched_rule_id"],
            # Sprint E1.1.4 / 2026-05-13 — pass authored Dr Pham copy
            # through to the warning emitter. None when the safety contract
            # didn't fire on a banned-recalled hit.
            "safety_warning_one_liner": active_safety_contract.get("safety_warning_one_liner"),
            "safety_warning": active_safety_contract.get("safety_warning"),
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
            # Label-native identity audit trail (label-first export). Sourced
            # from the IQD identity stamp so the blob carries how the display was
            # derived and what canonical was supplied before any repair.
            "source_label_key": safe_str(m.get("source_label_key")) or None,
            "source_label_name": m.get("source_label_name"),
            "source_label_form": m.get("source_label_form"),
            "label_display_name": m.get("label_display_name"),
            "label_display_form": m.get("label_display_form"),
            "identity_disposition": safe_str(m.get("identity_disposition")) or None,
            "identity_resolution_rationale": m.get("identity_resolution_rationale"),
            "canonical_id_before": m.get("canonical_id_before"),
            # Sprint E1.2.2.a — pre-computed Flutter display label
            "display_label": _compute_display_label(ing, m),
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
    ingredients = _suppress_zero_dose_duplicate_active_rows(ingredients)
    active_form_duplicate_terms = _active_form_duplicate_terms_for_product(ingredients)

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
    # Per-additive B1 applied-penalty tier (post-exemption) stashed by the scorer.
    # Drives display_tone so the dot reflects the penalty actually applied.
    # Emit display_tone ONLY when the scorer stash is present: a build over stale
    # scored output (no stash) would otherwise mis-green real additives (e.g.
    # titanium dioxide). Absent stash → omit display_tone so Flutter falls back to
    # severity_status (safe, prior behavior).
    _has_b1_tier = isinstance(scored, dict) and "_inactive_b1_applied_tier" in scored
    _b1_applied_tier = scored.get("_inactive_b1_applied_tier") if _has_b1_tier else {}
    if not isinstance(_b1_applied_tier, dict):
        _b1_applied_tier = {}
    # Sprint E1.2.4 reconciliation (2026-05-14):
    # Count entries that were intentionally dropped here via the Phase 4a
    # label-descriptor / active-only filter. The downstream validator
    # `_validate_inactive_preservation` subtracts this from
    # raw_inactives_count so that "1 raw inactive → 0 blob inactives"
    # doesn't fire as a regression when the only raw inactive was a
    # source descriptor (e.g., "Coconut" for an MCT oil product).
    intentional_inactive_drops = 0
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
            additional_terms=_form_match_terms(ing.get("forms")),
        )
        if res.matched_source is None:
            active_form_candidate = _product_active_form_duplicate_candidate(
                inactive_resolver=inactive_resolver,
                active_terms=active_form_duplicate_terms,
                raw_name=name or raw,
                additional_terms=_form_match_terms(ing.get("forms")),
            )
            if active_form_candidate:
                res = inactive_resolver.active_form_duplicate_resolution(
                    name or raw,
                    active_form_candidate,
                )

        # Label fidelity contract (2026-06-15): inactive_ingredients[] is
        # the user-visible "Other Ingredients" surface, so resolver flags
        # must not delete rows that appeared on the label. Keep the row and
        # expose disposition metadata for scoring / secondary UI decisions.
        if res.is_label_descriptor:
            label_row_disposition = "label_descriptor"
        elif res.is_active_only:
            label_row_disposition = "active_only"
        else:
            label_row_disposition = "standard"
        inactive_standard_name = _inactive_identity_name_for_export(
            name=name,
            upstream_standard_name=std_name_ing,
            resolver_standard_name=safe_str(res.standard_name),
            matched_source=safe_str(res.matched_source),
        )
        resolved_display_label = safe_str(res.display_label)
        inactive_display_label = name or raw or resolved_display_label
        inactive_contract = {
            "is_safety_concern": res.is_safety_concern,
            "is_banned": res.is_banned,
            "safety_reason": res.safety_reason,
            "matched_source": res.matched_source,
            "matched_rule_id": res.matched_rule_id,
        }

        inactive.append({
            "raw_source_text": raw,
            "name": name,
            "label_display": inactive_display_label,
            "standardName": inactive_standard_name,
            "normalized_key": safe_str(ing.get("normalized_key")),
            "forms": safe_list(ing.get("forms")),
            "category": res.category or safe_str(ing.get("category")),
            "is_additive": res.is_additive or safe_bool(ing.get("isAdditive")),
            "functional_roles": res.functional_roles,
            "standard_name": inactive_standard_name,
            "safety_flags": (
                safe_list(ing.get("safety_flags"))
                or safe_list(res.safety_flags)
                or _safety_flags_from_contract(inactive_contract)
            ),
            "notes": res.notes,
            "mechanism_of_harm": res.mechanism_of_harm or "",
            "common_uses": res.common_uses,
            "population_warnings": res.population_warnings,
            "harmful_severity": res.harmful_severity,
            "harmful_notes": res.harmful_notes,
            "identifiers": res.identifiers or {},
            # Canonical inactive contract (v1.5.0+) — Flutter renders
            # these directly without local inference.
            "display_label": inactive_display_label,
            "resolved_display_label": resolved_display_label,
            "display_role_label": res.display_role_label,
            "severity_status": res.severity_status,
            # Penalty-aware dot tone (green/light_orange/dark_orange/red): reflects
            # the B1 penalty actually applied, not file severity. Flutter renders
            # this; severity_status is kept for the inactive-safety CI audit.
            "display_tone": (
                _inactive_display_tone(
                    res.matched_source,
                    res.matched_rule_id,
                    _b1_applied_tier,
                    harmful_severity=res.harmful_severity,
                )
                if _has_b1_tier
                else None
            ),
            "is_safety_concern": res.is_safety_concern,
            "label_row_disposition": label_row_disposition,
            "is_label_descriptor": res.is_label_descriptor,
            "is_active_only": res.is_active_only,
            # v1.6.0+ unified contract additions:
            "is_banned": res.is_banned,
            "safety_reason": res.safety_reason,
            "matched_source": res.matched_source,
            "matched_rule_id": res.matched_rule_id,
            "regulatory_status": res.regulatory_status,
            "inactive_policy": res.inactive_policy,
            "safety_display_name": (
                safe_str(res.standard_name)
                if safe_str(res.matched_source) in _SAFETY_ONLY_IDENTITY_SOURCES
                else None
            ),
            # Sprint E1.1.4 / 2026-05-13 — Dr Pham authored copy threaded
            # from banned_recalled_ingredients.json through the resolver
            # to the warning emitter. None on harmful-additive /
            # other-ingredient / unmatched branches.
            "safety_warning_one_liner": res.safety_warning_one_liner,
            "safety_warning":          res.safety_warning,
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

    for flag in contaminant_safety_flags(enriched):
        source = normalize_safety_source(flag.get("source_db") or flag.get("matched_source"))
        if source != "banned_recalled_ingredients":
            continue
        status = normalize_text(flag.get("status"))
        name = _safety_flag_display_name(flag)
        warning_type = _banned_warning_type_for_status(status)
        title_prefix = _banned_warning_title_prefix_for_status(status)
        severity = safe_str(
            flag.get("severity"),
            "critical" if status == "banned" else "high" if status == "recalled" else "moderate",
        )
        dm_default = "critical" if status in ("banned", "recalled", "high_risk") else "informational"
        warnings.append({
            "type": warning_type,
            "severity": severity,
            "title": f"{title_prefix}: {name}",
            "detail": safe_str(flag.get("evidence_text")),
            "source": "banned_recalled_ingredients",
            "matched_rule_id": safe_str(flag.get("entry_id") or flag.get("rule_id")) or None,
            "ingredient_name": name,
            "safety_warning": flag.get("safety_warning"),
            "safety_warning_one_liner": flag.get("safety_warning_one_liner"),
            "display_mode_default": dm_default,
        })

    for h in safe_list(enriched.get("harmful_additives")):
        if not isinstance(h, dict):
            continue
        # Sprint E1.1.2 (2026-05-13): prefer the live data file (h_ref)
        # over the enricher's snapshot (h) for static reference fields.
        # The enricher copies mechanism_of_harm / notes / population_warnings
        # from harmful_additives.json verbatim at enrich-time, so an update
        # to the data file would otherwise sit dormant until a full
        # re-enrichment cycle. For medical-grade safety copy this is
        # unacceptable — corrections must flow into the next build.
        # The enricher's snapshot is kept as a fallback for cases where
        # the runtime reference lookup fails (e.g. additive_id renamed).
        h_ref = resolve_harmful_reference(h)
        h_notes = safe_str(h_ref.get("notes") or h.get("notes"))
        h_mechanism = safe_str(h_ref.get("mechanism_of_harm") or h.get("mechanism_of_harm"))
        h_pop_warnings = h_ref.get("population_warnings") or h.get("population_warnings") or []
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
                warning_type = safe_str(ch.get("warning_type"), "interaction").lower()
                if warning_type not in {"interaction", "diagnostic_interference"}:
                    warning_type = "interaction"
                warnings.append({
                    "type": warning_type,
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
                    "direction": ch.get("direction"),
                    "materiality": ch.get("materiality"),
                    "min_effective_dose": ch.get("min_effective_dose"),
                    "dose_floor_status": ch.get("dose_floor_status"),
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
                    "direction": dh.get("direction"),
                    "materiality": dh.get("materiality"),
                    "min_effective_dose": dh.get("min_effective_dose"),
                    "dose_floor_status": dh.get("dose_floor_status"),
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

    # Diabetes-specific added-sugar flag (presence-matters, harmful). A
    # diabetic should be flagged that a product contains added sugar,
    # regardless of amount. Distinct from the general dietary note above and
    # from the B1 sugar score penalty — scoring reads dietary_sensitivity_data.
    # sugar directly, so this warning does NOT touch it (score-neutral).
    # Suppressed by default; the app promotes it on a diabetes profile match,
    # and materiality=presence means it is never dose-suppressed.
    _sugar = safe_dict(ds.get("sugar"))
    _has_added = bool(_sugar.get("has_added_sugar"))
    if _has_added or _sugar.get("level") in ("moderate", "high"):
        _amt = _sugar.get("amount_g")
        # `level` is computed from TOTAL sugar grams, independent of whether an
        # added-sugar ingredient was found. Only call it "added" when it truly is;
        # a whole-food/fruit powder with no added-sugar ingredient is "Sugar".
        _label = "Added sugar" if _has_added else "Sugar"
        _lead = "Contains added sugar" if _has_added else "Contains sugar"
        warnings.append({
            "type": "dietary",
            "severity": "monitor",
            "title": _label,
            "detail": _lead
            + (f" ({_amt} g/serving)" if _amt else "")
            + " - relevant if you have diabetes.",
            "condition_ids": ["diabetes"],
            "direction": "harmful",
            "materiality": "presence",
            "display_mode_default": "suppress",
            "source": "dietary_sensitivity_data",
        })

    # Sprint E1.5.X-4 — discontinued/off-market no longer emitted into
    # warnings[]. Status is now exposed as a top-level `product_status_detail`
    # field so Flutter can render it as a small neutral "concern" chip
    # (not a safety warning, not a green-safe tag). Separation of concerns:
    # warnings[] = safety/interactions; product_status_detail = availability.
    pass  # intentionally no warning emission for discontinued/off_market

    # 2026-05-12 — resolver-synthesized banned_recalled warnings.
    # Closes the gap where per-ingredient blob entries are correctly
    # flagged is_safety_concern=True (via the resolver) but the warnings[]
    # array was empty for that ingredient because build_top_warnings()
    # reads from enriched.contaminant_data which misses inactives + alias
    # variants on actives. Titanium Dioxide × 1,178 inactive occurrences
    # are the canary. The dedup below collapses any overlap with the
    # contaminant_matches() output above.
    for ing_list, role in ((ingredients, "active"), (inactive, "inactive")):
        for ing in ing_list:
            if not isinstance(ing, dict):
                continue
            if ing.get("matched_source") != "banned_recalled":
                continue
            if not (ing.get("is_safety_concern") or ing.get("is_banned")):
                continue  # watchlist/informational — top warning not required
            name = (
                ing.get("safety_display_name")
                or ing.get("display_label")
                or ing.get("name")
                or ing.get("raw_source_text")
                or "Unknown ingredient"
            )
            if bool(ing.get("is_banned")):
                w_type = "banned_substance"
                w_severity = "critical"
                w_title = f"Banned substance: {name}"
                dm_default = "critical"
            else:
                inactive_policy = normalize_text(ing.get("inactive_policy"))
                regulatory_status = normalize_text(ing.get("regulatory_status"))
                if regulatory_status == "watchlist" or (
                    role == "inactive" and inactive_policy == "excipient_acceptable"
                ):
                    w_type = "watchlist_substance"
                    w_severity = "moderate"
                    w_title = (
                        f"Excipient watchlist: {name}"
                        if role == "inactive" and inactive_policy == "excipient_acceptable"
                        else f"Watchlist ingredient: {name}"
                    )
                    dm_default = "informational"
                else:
                    # high_risk / recalled — both surface as high_risk_ingredient
                    w_type = "high_risk_ingredient"
                    w_severity = "high"
                    w_title = f"High-risk ingredient: {name}"
                    dm_default = "critical"
            warning_entry = {
                "type": w_type,
                "severity": w_severity,
                "title": w_title,
                "detail": safe_str(ing.get("safety_reason")) or "",
                "ingredient_name": safe_str(ing.get("name") or name),
                "ingredient_role": role,  # 'active' | 'inactive' — for Flutter routing
                "matched_rule_id": safe_str(ing.get("matched_rule_id")) or None,
                "source": "inactive_ingredient_resolver",
                "display_mode_default": dm_default,
                "clinical_risk": safe_str(ing.get("harmful_severity")) or None,
                "inactive_policy": safe_str(ing.get("inactive_policy")) or None,
            }
            # Sprint E1.1.4 / 2026-05-13 — thread Dr Pham authored preflight
            # copy into warnings emitted for banned-recalled hits. Without
            # this, build_banned_substance_detail() (which scans
            # warnings[].type=='banned_substance' for safety_warning_one_liner
            # + safety_warning) gets an empty result and the preflight
            # validator in _validate_banned_preflight_propagation fires.
            # The fields are populated upstream by:
            #   - InactiveResolution._from_banned (inactive path), and
            #   - _resolve_active_safety_contract banned branch (active path).
            # Empty string never returned — None falls through cleanly so
            # build_banned_substance_detail's `isinstance(one, str) and one.strip()`
            # guard skips entries that lack authored copy (e.g. high_risk).
            one_liner = ing.get("safety_warning_one_liner")
            safety_warning = ing.get("safety_warning")
            if one_liner:
                warning_entry["safety_warning_one_liner"] = one_liner
            if safety_warning:
                warning_entry["safety_warning"] = safety_warning
            warnings.append(warning_entry)

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
    prenatal_coverage = _build_prenatal_coverage(ingredients, rda_ul_data)
    adult_multi_coverage = _build_adult_multi_coverage(ingredients, rda_ul_data)
    role_context = _classify_product_role(
        enriched,
        ingredients,
        prenatal_coverage,
        adult_multi_coverage,
    )

    blob = {
        "dsld_id": safe_str(enriched.get("dsld_id")),
        "product_name": safe_str(enriched.get("product_name")),
        "brand_name": safe_str(enriched.get("brand_name") or enriched.get("brandName")),
        "primary_type": safe_str((enriched.get("supplement_taxonomy") or {}).get("primary_type")),
        "secondary_type": (enriched.get("supplement_taxonomy") or {}).get("secondary_type"),
        "classification_confidence": (enriched.get("supplement_taxonomy") or {}).get("classification_confidence"),
        "classification_reasons": (enriched.get("supplement_taxonomy") or {}).get("classification_reasons"),
        "product_role": role_context["product_role"],
        "completeness_claim_mismatch": role_context["completeness_claim_mismatch"],
        "product_role_evidence": role_context["role_evidence"],
        "blob_version": 1,
        "ingredients": ingredients,
        "inactive_ingredients": inactive,
        "warnings": warnings,
        # Phase 8: structured per-allergen array for client-side
        # personalized matching against profile.allergens. Exact
        # allergen_id matching only. Allergen facts intentionally do not
        # duplicate into warnings[]; Flutter promotes them only when they
        # match the user's declared allergens.
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
            "brand_name": safe_str(enriched.get("brand_name") or enriched.get("brandName")),
            "is_trusted": safe_bool(enriched.get("is_trusted_manufacturer")),
            "manufacturing_region": safe_str(enriched.get("manufacturing_region")),
            "violations": safe_dict(safe_dict(enriched.get("manufacturer_data")).get("violations")),
        },
        "non_gmo_audit": non_gmo_audit,
        "omega3_audit": omega3_audit,
        "proprietary_blend_audit": proprietary_blend_audit,
        "supplement_type_audit": supplement_type_audit,
    }
    if prenatal_coverage.get("has_any_anchor") or role_context["product_role"] in {
        "prenatal_base",
        "prenatal_complete",
        "prenatal_dha_companion",
        "prenatal_choline_companion",
    }:
        blob["prenatal_coverage"] = prenatal_coverage
    if adult_multi_coverage.get("has_any_anchor"):
        adult_role = safe_str(role_context["product_role"]).startswith("adult_multi_")
        blob["adult_multi_coverage"] = (
            adult_multi_coverage if adult_role else _present_only_coverage(adult_multi_coverage)
        )
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
            "reference_data_version": rda_ul_data.get("reference_data_version"),
            "reference_data_fingerprint": rda_ul_data.get("reference_data_fingerprint"),
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
            "ul_review_flags": safe_list(rda_ul_data.get("ul_review_flags")),
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
            # Present-but-underdosed sole-primary clusters are not real
            # synergies — they exist only to feed goal matching's "partially
            # supported" state (goal_matches_underdosed). Keep them out of the
            # user-facing synergy detail and the display bonus tier.
            if safe_bool(sc.get("underdosed_single")):
                continue
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

    # Score reasons — Tradeoffs bonus/penalty lists. v4 cutover: these are now
    # sourced from the v4 contract + enriched safety data via
    # derive_v4_tradeoffs (no v3 section-score dependency). a_sub is retained
    # only for the diagnostic gate_audit.probiotic_eligibility emitted below.
    a_sub = section_breakdown.get("ingredient_quality", {}).get("sub", {})
    bonuses, penalties = derive_v4_tradeoffs(scored, enriched)

    # v1.3.2: Nutrition detail — all five macros for the Flutter transparency panel
    ns = safe_dict(enriched.get("nutrition_summary"))
    blob["nutrition_detail"] = {
        "calories_per_serving": safe_float(ns.get("calories_per_serving")),
        "total_carbohydrates_g": safe_float(ns.get("total_carbohydrates_g")),
        "total_fat_g": safe_float(ns.get("total_fat_g")),
        "protein_g": safe_float(ns.get("protein_g")),
        "dietary_fiber_g": safe_float(ns.get("dietary_fiber_g")),
        "total_sugars_g": safe_float(ns.get("total_sugars_g")),
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
    }

    # Sprint E1.1.4 — top-level banned-substance preflight detail for
    # Flutter Sprint 27.7's stack-add CRITICAL banner.
    blob["banned_substance_detail"] = build_banned_substance_detail(enriched, warnings)
    _validate_banned_preflight_propagation(blob, enriched, dsld_id_for_validation)

    # Sprint E1.2.4 — raw-inactive preservation invariant.
    raw_inactives_count = int(enriched.get("raw_inactives_count") or 0)
    blob["raw_inactives_count"] = raw_inactives_count
    # 2026-05-14 — pass intentional Phase 4a drops so the invariant
    # doesn't fire on products where the only raw inactive was a
    # legitimate source-descriptor (e.g., "Coconut" on an MCT oil
    # product). See bucket 2 closure for full rationale.
    _validate_inactive_preservation(
        blob,
        raw_inactives_count,
        dsld_id_for_validation,
        intentional_drops=intentional_inactive_drops,
    )

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

    # Opaque-product flags: split by WHY the active is unidentifiable so Flutter
    # shows the correct consumer message. The product ships with its POOR/CAUTION
    # verdict (the transparency penalty caps opaque labels low) instead of being
    # silently quarantined; the flag tells the app which copy to render.
    #
    #   • proprietary_blend     — a disclosed blend with undisclosed per-ingredient
    #                             amounts (TRISYNEX, Tea Trio). NOT a data gap; the
    #                             opacity IS the consumer signal.
    #                             Copy: "Contains an undisclosed proprietary blend"
    #   • unverified_ingredient — a single named ingredient we couldn't map to a
    #                             canonical identity (Silver, Germanium). A mapping
    #                             gap, not a blend — must not be mislabeled "blend".
    #                             Copy: "Ingredient not yet verified"
    #
    # Both default False for identified products. Mirrors validate_export_contract's
    # has_active_identity logic for the opacity test.
    _active_rows = [a for a in safe_list(enriched.get("activeIngredients")) if isinstance(a, dict)]
    _iqd_rows = safe_list(safe_dict(enriched.get("ingredient_quality_data")).get("ingredients"))
    _has_active_identity = any(
        safe_str(i.get("canonical_id") or i.get("parent_key"))
        for i in _iqd_rows if isinstance(i, dict)
    ) or any(safe_str(a.get("canonical_id")) for a in _active_rows)
    _is_opaque = bool(_active_rows) and not _has_active_identity
    _has_blend = bool(safe_bool(safe_dict(enriched.get("proprietary_data")).get("has_proprietary_blends")))
    blob["proprietary_blend"] = bool(_is_opaque and _has_blend)
    blob["unverified_ingredient"] = bool(_is_opaque and not _has_blend)

    # ── v4 detail-blob fields ────────────────────────────────────────────────
    # The export adapter stashes the public v4 contract under _v4_* keys. Surface
    # the six pillars (with reasons), clean-label flags, the audit raw score, the
    # gate breakdowns, and a provenance/explanation trail ("why did this score X?").
    if scored.get("_v4_quality_status") is not None:
        pillars = scored.get("_v4_pillars")
        blob["quality_pillars_v4"] = pillars
        blob["quality_score_cap_v4"] = scored.get("_v4_quality_score_cap")
        blob["clean_label_flags_v4"] = scored.get("_v4_clean_label_flags")
        blob["raw_score_v4_100"] = scored.get("_v4_raw_score_100")
        blob["v4_safety_gate"] = scored.get("_v4_safety_gate")
        blob["v4_completeness_gate"] = scored.get("_v4_completeness_gate")
        blob["v4_confidence_detail"] = scored.get("_v4_confidence_detail")
        blob["v4_score_provenance"] = {
            "score_model_version": scored.get("_score_model_version"),
            "quality_score_status": scored.get("_v4_quality_status"),
            "quality_tier": scored.get("_v4_quality_tier"),
            "quality_score_version": scored.get("_v4_quality_version"),
            "scoring_engine_version": scored.get("_v4_scoring_engine_version"),
            "classification_schema_version": scored.get("_v4_classification_schema_version"),
            "module": scored.get("_v4_module"),
            "confidence": scored.get("_v4_confidence"),
            "config_fingerprint": scored.get("_v4_config_fingerprint"),
            "suppressed_reason": scored.get("_v4_suppressed_reason"),
            "safety_signal_reason": scored.get("_v4_safety_signal_reason"),
        }
        blob["v4_score_explanation"] = _build_v4_score_explanation(pillars)

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

    nutrient_categories = {"vitamin", "vitamins", "mineral", "minerals", "amino_acid", "amino_acids", "fatty_acid", "fatty_acids"}
    herb_categories = {"botanical", "botanicals", "herb", "herbs", "plant_extract", "plant_extracts"}

    for ing in ingredients:
        if not isinstance(ing, dict):
            continue

        standard_name = safe_str(ing.get("standard_name")).lower()
        category = safe_str(ing.get("category")).lower()
        canonical_id = safe_str(ing.get("canonical_id") or ing.get("parent_key")).lower()

        ingredient_id = canonical_id or standard_name.replace(" ", "_")
        if not ingredient_id:
            continue

        all_ingredient_names.add(ingredient_id)
        if standard_name:
            all_ingredient_names.add(standard_name.replace(" ", "_"))

        # Extract nutrients with doses
        if category in nutrient_categories:
            normalized_amount = ing.get("normalized_amount") or ing.get("dosage") or ing.get("quantity")
            normalized_unit = safe_str(ing.get("normalized_unit") or ing.get("dosage_unit") or ing.get("unit"))

            if normalized_amount is not None:
                amount = float(normalized_amount)
                existing = fingerprint["nutrients"].get(ingredient_id)
                if existing is None:
                    fingerprint["nutrients"][ingredient_id] = {
                        "amount": amount,
                        "unit": normalized_unit,
                    }
                elif safe_str(existing.get("unit")).strip().lower() == normalized_unit.strip().lower():
                    # Multiple label forms can share one interaction canonical
                    # (e.g. K1 + K2 -> vitamin_k). The fingerprint must retain
                    # their total, rather than silently letting the last form win.
                    existing["amount"] = float(existing["amount"]) + amount

        # Track herbs
        if category in herb_categories:
            fingerprint["herbs"].append(ingredient_id)

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
    ingredients = safe_list(iqd.get("ingredients_scorable")) or safe_list(iqd.get("ingredients"))

    # Priority order for display
    priority_nutrients = [
        "dietary fiber", "fiber", "psyllium husk", "psyllium",
        "niacin", "vitamin b6", "folate", "vitamin b12", "biotin",
        "vitamin b1", "vitamin b2", "pantothenic acid", "choline",
        "vitamin d", "vitamin c", "magnesium", "zinc",
        "omega-3", "iron", "calcium", "vitamin a", "vitamin e",
    ]

    nutrition = safe_dict(enriched.get("nutrition_detail")) or safe_dict(enriched.get("nutrition_summary"))
    dietary_fiber_g = safe_float(nutrition.get("dietary_fiber_g"))
    if dietary_fiber_g and dietary_fiber_g > 0:
        nutrients.append({
            "name": "Dietary Fiber",
            "amount": float(dietary_fiber_g),
            "unit": "g",
            "priority": priority_nutrients.index("dietary fiber"),
        })

    for ing in ingredients:
        if not isinstance(ing, dict):
            continue

        standard_name = safe_str(ing.get("standard_name")).lower()
        category = safe_str(ing.get("category")).lower()

        if category not in ["vitamins", "minerals", "amino_acids", "fatty_acids", "fiber", "fibers"]:
            continue

        normalized_amount = ing.get("normalized_amount") or ing.get("dosage") or ing.get("quantity")
        normalized_unit = safe_str(
            ing.get("normalized_unit")
            or ing.get("dosage_unit")
            or ing.get("unit_normalized")
            or ing.get("unit")
        )

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
    brand_name = safe_str(enriched.get("brand_name") or enriched.get("brandName"))
    score_100 = safe_float(scored.get("score_100_equivalent"))
    grade = safe_str(scored.get("grade"))
    verdict = safe_str(scored.get("verdict")).upper()
    # V4 cutover: evidence copy reads the v4 evidence pillar (/20), not v3 section C.
    v4_evidence = safe_float(safe_dict(safe_dict(scored.get("_v4_pillars")).get("evidence")).get("score"), 0)

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
    if v4_evidence >= 15:
        positive_signals.append("clinical evidence")
    if safe_list(enriched.get("named_cert_programs")):
        positive_signals.append("third-party testing")
    # Dietary signals come from compliance_data (the canonical source for
    # vegan / gluten_free / etc. flags). dietary_sensitivity_data carries
    # only sugar / sodium per `_collect_dietary_sensitivity_data` and never
    # had `vegan` or `gluten_free` populated — the prior reads against
    # `dietary_sensitivity_data` were silently always-false dead paths.
    if safe_dict(enriched.get("compliance_data")).get("vegan"):
        positive_signals.append("vegan-friendly formulation")

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

    # Clinical evidence — v4 evidence pillar (>= 12 of /20) stands in for the
    # retired v3 C.matched_entries; avoids over-claiming on the evidence floor.
    if v4_evidence >= 12:
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

    # Extract ingredient names and canonical ids. `key_ingredient_tags` is a
    # safety carrier used by Flutter interaction lookup, so it must include all
    # mapped active canonical IDs, not just a short display-priority subset.
    ingredient_names = set()
    key_tags = []
    seen_key_tags = set()
    active_export_contract = _active_export_contract(enriched)

    def normalize_interaction_tag(value: Any) -> str:
        return normalize_catalog_interaction_tag(value) or ""

    def add_interaction_tag(value: Any) -> None:
        canonical_id = normalize_interaction_tag(value)
        if not canonical_id:
            return
        ingredient_names.add(canonical_id)
        if canonical_id not in seen_key_tags:
            seen_key_tags.add(canonical_id)
            key_tags.append(canonical_id)

    def add_interaction_tags_from_text(*values: Any) -> None:
        for canonical_id in interaction_tags_from_text(*values):
            add_interaction_tag(canonical_id)

    add_interaction_tags_from_text(
        enriched.get("product_name"),
        enriched.get("label_text"),
        enriched.get("search_text"),
    )

    for ing in ingredients:
        if not isinstance(ing, dict):
            continue
        if not _active_row_allowed_for_primary_export(ing, active_export_contract):
            continue
        name = safe_str(ing.get("standard_name") or ing.get("name")).lower().replace(" ", "_")
        if name:
            ingredient_names.add(name)
        add_interaction_tag(ing.get("canonical_id") or ing.get("parent_key"))
        add_interaction_tags_from_text(
            ing.get("name"),
            ing.get("standard_name"),
            ing.get("raw_source_text"),
            ing.get("normalized_key"),
        )

    # Some safety/resolver canonicals live only on activeIngredients when the
    # active is recognized but not IQM-scorable (for example CBD, red yeast
    # rice, vinpocetine, and botanical source identities). These canonicals are
    # still required by Flutter interaction lookup and stack storage, so export
    # them into the core carrier as well.
    for ing in safe_list(enriched.get("activeIngredients")):
        if not isinstance(ing, dict):
            continue
        if not _active_row_allowed_for_primary_export(ing, active_export_contract):
            continue
        name = safe_str(ing.get("standardName") or ing.get("name")).lower().replace(" ", "_")
        if name:
            ingredient_names.add(name)
        add_interaction_tag(ing.get("canonical_id") or ing.get("normalized_key"))
        add_interaction_tags_from_text(
            ing.get("name"),
            ing.get("standardName"),
            ing.get("raw_source_text"),
            ing.get("normalized_key"),
        )

    # Primary category — sourced from supplement_taxonomy (single source of truth)
    taxonomy = enriched.get("supplement_taxonomy") or (scored or {}).get("supplement_taxonomy") or {}
    primary_type = safe_str(taxonomy.get("primary_type"))
    secondary_type = safe_str(taxonomy.get("secondary_type"))

    # Map taxonomy primary_type to Flutter-facing primary_category.
    # Flutter uses this for search filtering and UI badges.
    primary_category = primary_type or resolve_export_supplement_type(enriched, scored) or None

    # Secondary categories — combine taxonomy secondary_type with
    # composition-derived tags (adaptogens, nootropics, synergy clusters)
    secondary_categories = []
    if secondary_type:
        secondary_categories.append(secondary_type)

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
    contains_probiotics = (
        primary_type == "probiotic"
        or any("probiotic" in name or "bacillus" in name or "lactobacillus" in name for name in ingredient_names)
        or (
            not active_export_contract.get("available")
            and bool(safe_dict(enriched.get("probiotic_data")).get("is_probiotic_product"))
        )
    )
    contains_collagen = any(name in ingredient_names for name in ["collagen", "collagen_peptides"])
    contains_adaptogens = bool(ingredient_names & adaptogens)
    contains_nootropics = bool(ingredient_names & nootropics)

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
PROBIOTIC_GOAL_CLUSTER_ID = "probiotic_and_gut_health"
FIBER_GOAL_CLUSTER_ID = "gut_barrier"
CREATINE_GOAL_CLUSTER_ID = "muscle_building_recovery"
SLEEP_GOAL_CLUSTER_ID = "sleep_stack"
JOINT_GOAL_CLUSTER_ID = "joint_inflammation"
FIBER_GOAL_MIN_DOSE_G = 3.0
CREATINE_GOAL_MIN_DOSE_G = 3.0
CREATINE_GOAL_MIN_BIO_SCORE = 10.0
CREATINE_GOAL_CANONICALS = frozenset({
    "creatine",
    "creatine_monohydrate",
    "creatine_anhydrous",
    "creatine_hydrochloride",
    "creatine_hcl",
    "creatine_nitrate",
    "creatine_citrate",
    "buffered_creatine",
    "magnesium_creatine_chelate",
})
PROTEIN_GOAL_MIN_DOSE_G = 20.0
PROTEIN_COMPLETE_CANONICALS = frozenset({
    "whey_protein",
    "casein",
    "soy_protein",
})
PROTEIN_PLANT_BLEND_CANONICALS = frozenset({
    "pea_protein",
    "rice_protein",
})
JOINT_GOAL_MIN_DOSE_MG = {
    "glucosamine": 1500.0,
    "chondroitin": 1200.0,
    "msm": 1000.0,
    "uc_ii": 40.0,
    "hyaluronic_acid": 120.0,
}

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


def _probiotic_has_named_identity(pdata: Dict[str, Any]) -> bool:
    if safe_float(pdata.get("total_strain_count"), 0.0) > 0:
        return True
    if safe_float(pdata.get("clinical_strain_count"), 0.0) > 0:
        return True
    for blend in safe_list(pdata.get("probiotic_blends")):
        blend = safe_dict(blend)
        if safe_list(blend.get("strains")):
            return True
    return False


def _probiotic_goal_cluster_applies(enriched: Dict, *, enforce_dose_gate: bool) -> bool:
    pdata = safe_dict(enriched.get("probiotic_data") or enriched.get("probiotic_detail"))
    if not safe_bool(pdata.get("is_probiotic_product") or pdata.get("is_probiotic")):
        return False
    if not _probiotic_has_named_identity(pdata):
        return False
    total_billion = safe_float(pdata.get("total_billion_count"))
    if total_billion is None:
        total_cfu = safe_float(pdata.get("total_cfu"))
        total_billion = (total_cfu / 1_000_000_000.0) if total_cfu else None
    if enforce_dose_gate:
        return total_billion is not None and total_billion >= 1.0
    return True


def _fiber_goal_cluster_applies(enriched: Dict, *, enforce_dose_gate: bool) -> bool:
    """Direct digestive-health goal extraction for fiber products.

    Fiber products should not need a probiotic or enzyme synergy cluster to
    reach the digestive-health goal surface. Keep the override conservative:
    require an explicit fiber context from the product name or scorable rows,
    then dose-gate supported vs present-but-underdosed using grams per serving.
    """
    rows = _fiber_goal_rows(enriched)
    if not rows and not _has_fiber_goal_context(enriched):
        return False

    if not enforce_dose_gate:
        return True

    label_grams = _nutrition_fiber_goal_grams(enriched)
    grams = label_grams if label_grams is not None else _total_fiber_goal_grams(rows)
    return grams >= FIBER_GOAL_MIN_DOSE_G


def _mass_dose_g(row: Dict[str, Any]) -> Optional[float]:
    quantity = safe_float((row or {}).get("quantity"))
    if quantity is None or quantity <= 0:
        return None
    unit = safe_str((row or {}).get("unit_normalized") or (row or {}).get("unit")).lower()
    compact = unit.replace(" ", "")
    if unit in {"g", "gram", "grams", "gram(s)"} or compact in {"g", "gram", "grams", "gram(s)"}:
        return quantity
    if unit in {"mg", "milligram", "milligrams", "milligram(s)"}:
        return quantity / 1000.0
    if unit in {"mcg", "ug", "µg", "μg", "microgram", "micrograms", "microgram(s)"}:
        return quantity / 1_000_000.0
    return None


def _mass_dose_mg(row: Dict[str, Any]) -> Optional[float]:
    grams = _mass_dose_g(row)
    if grams is None:
        return None
    return grams * 1000.0


def _creatine_row_text(row: Dict[str, Any]) -> str:
    fields = (
        "name",
        "standard_name",
        "canonical_id",
        "matched_form",
        "form",
        "ingredient_form",
        "raw_source_text",
    )
    return " ".join(safe_str((row or {}).get(field)).lower() for field in fields)


def _protein_row_text(row: Dict[str, Any]) -> str:
    fields = (
        "name",
        "standard_name",
        "canonical_id",
        "matched_form",
        "form",
        "ingredient_form",
        "raw_source_text",
    )
    return " ".join(safe_str((row or {}).get(field)).lower() for field in fields)


def _sleep_row_text(row: Dict[str, Any]) -> str:
    fields = (
        "name",
        "standard_name",
        "canonical_id",
        "matched_form",
        "form",
        "ingredient_form",
        "raw_source_text",
    )
    return " ".join(safe_str((row or {}).get(field)).lower() for field in fields)


def _joint_row_text(row: Dict[str, Any]) -> str:
    fields = (
        "name",
        "standard_name",
        "canonical_id",
        "matched_form",
        "form",
        "ingredient_form",
        "raw_source_text",
    )
    return " ".join(safe_str((row or {}).get(field)).lower() for field in fields)


def _creatine_goal_cluster_applies(enriched: Dict, *, enforce_dose_gate: bool) -> bool:
    iqd = safe_dict(enriched.get("ingredient_quality_data"))
    rows = safe_list(iqd.get("ingredients_scorable")) or safe_list(iqd.get("ingredients"))
    for row in rows:
        if not isinstance(row, dict):
            continue
        canonical = safe_str(row.get("canonical_id")).lower()
        text = _creatine_row_text(row)
        if canonical not in CREATINE_GOAL_CANONICALS and "creatine" not in text:
            continue

        if not enforce_dose_gate:
            return True

        if "ethyl ester" in text:
            continue
        bio_score = safe_float(row.get("bio_score"))
        if bio_score is not None and bio_score < CREATINE_GOAL_MIN_BIO_SCORE:
            continue
        grams = _mass_dose_g(row)
        if grams is not None and grams >= CREATINE_GOAL_MIN_DOSE_G:
            return True

    return False


def _protein_goal_cluster_applies(enriched: Dict, *, enforce_dose_gate: bool) -> bool:
    """Direct muscle/recovery goal extraction for complete protein products.

    Protein powders should not depend on broad synergy clusters to surface the
    muscle recovery goal. The gate is intentionally conservative: complete dairy
    or soy protein, or a pea+rice plant blend, can qualify at a meaningful dose.
    Collagen/gelatin never qualifies for this muscle-protein direct path.
    """
    iqd = safe_dict(enriched.get("ingredient_quality_data"))
    rows = [
        row
        for row in (safe_list(iqd.get("ingredients_scorable")) or safe_list(iqd.get("ingredients")))
        if isinstance(row, dict)
    ]
    if not rows:
        return False

    plant_canons: set[str] = set()
    qualifying_rows: List[Dict[str, Any]] = []
    for row in rows:
        canonical = safe_str(row.get("canonical_id")).lower()
        text = _protein_row_text(row)
        if "collagen" in text or "gelatin" in text:
            continue

        is_complete = canonical in PROTEIN_COMPLETE_CANONICALS or any(
            term in text
            for term in (
                "whey protein",
                "whey isolate",
                "casein",
                "soy protein",
            )
        )
        if canonical in PROTEIN_PLANT_BLEND_CANONICALS:
            plant_canons.add(canonical)
        if is_complete:
            qualifying_rows.append(row)

    if PROTEIN_PLANT_BLEND_CANONICALS.issubset(plant_canons):
        qualifying_rows.extend(
            row
            for row in rows
            if safe_str(row.get("canonical_id")).lower() in PROTEIN_PLANT_BLEND_CANONICALS
        )

    if not qualifying_rows:
        return False
    if not enforce_dose_gate:
        return True

    total_plant_g = 0.0
    for row in qualifying_rows:
        grams = _mass_dose_g(row)
        if grams is None:
            continue
        canonical = safe_str(row.get("canonical_id")).lower()
        if canonical in PROTEIN_PLANT_BLEND_CANONICALS:
            total_plant_g += grams
        elif grams >= PROTEIN_GOAL_MIN_DOSE_G:
            return True

    return total_plant_g >= PROTEIN_GOAL_MIN_DOSE_G


def _pre_workout_goal_cluster_ids(enriched: Dict, *, enforce_dose_gate: bool) -> set:
    """Direct sports goal extraction for disclosed pre-workout formulas."""
    try:
        from scoring_v4.modules.sports_helpers import pre_workout_goal_cluster_ids

        return set(pre_workout_goal_cluster_ids(enriched, enforce_dose_gate=enforce_dose_gate))
    except Exception as exc:
        logger.debug("pre-workout goal cluster extraction skipped: %s", exc)
        return set()


def _sleep_goal_cluster_applies(enriched: Dict, *, enforce_dose_gate: bool) -> bool:
    """Direct sleep-quality cluster extraction for focused sleep actives.

    Melatonin and 5-HTP products can be legitimately sleep-positioned without a
    precomputed synergy cluster. Dose gating keeps trace/unclear rows out of
    supported goals while preserving the present-but-underdosed surface.
    """
    taxonomy = safe_dict(enriched.get("supplement_taxonomy"))
    if safe_str(enriched.get("primary_type") or taxonomy.get("primary_type")).lower() != "sleep_support":
        return False

    iqd = safe_dict(enriched.get("ingredient_quality_data"))
    rows = [
        row
        for row in (safe_list(iqd.get("ingredients_scorable")) or safe_list(iqd.get("ingredients")))
        if isinstance(row, dict)
    ]
    for row in rows:
        canonical = safe_str(row.get("canonical_id")).lower()
        text = _sleep_row_text(row)
        is_melatonin = canonical == "melatonin" or "melatonin" in text
        is_5htp = canonical == "5_htp" or "5-htp" in text or "5 htp" in text
        if not is_melatonin and not is_5htp:
            continue

        if not enforce_dose_gate:
            return True

        mg = _mass_dose_mg(row)
        if mg is None:
            continue
        if is_melatonin and 0.3 <= mg <= 10.0:
            return True
        if is_5htp and 50.0 <= mg <= 400.0:
            return True

    return False


def _joint_goal_cluster_applies(enriched: Dict, *, enforce_dose_gate: bool) -> bool:
    taxonomy = safe_dict(enriched.get("supplement_taxonomy"))
    if safe_str(enriched.get("primary_type") or taxonomy.get("primary_type")).lower() != "joint_support":
        return False

    iqd = safe_dict(enriched.get("ingredient_quality_data"))
    rows = [
        row
        for row in (safe_list(iqd.get("ingredients_scorable")) or safe_list(iqd.get("ingredients")))
        if isinstance(row, dict)
    ]
    for row in rows:
        active = _joint_active_id(row)
        if not active:
            continue
        if not enforce_dose_gate:
            return True

        mg = _mass_dose_mg(row)
        if mg is not None and mg >= JOINT_GOAL_MIN_DOSE_MG[active]:
            return True

    return False


def _joint_active_id(row: Dict[str, Any]) -> Optional[str]:
    canonical = safe_str(row.get("canonical_id")).lower()
    text = _joint_row_text(row)
    if canonical == "glucosamine" or "glucosamine" in text:
        return "glucosamine"
    if canonical == "chondroitin" or "chondroitin" in text:
        return "chondroitin"
    if canonical == "msm" or "methylsulfonylmethane" in text or "msm" in text:
        return "msm"
    if canonical in {"uc_ii", "collagen"} and (
        "uc-ii" in text
        or "uc ii" in text
        or "type ii collagen" in text
        or "undenatured type ii" in text
    ):
        return "uc_ii"
    if canonical == "hyaluronic_acid" or "hyaluronic acid" in text or "hyaluronan" in text:
        return "hyaluronic_acid"
    return None


# Goal-emission anchors (goal correctness, 2026-07-03). A cluster's GOAL is only
# claimed when a DEFINING "anchor" ingredient is present at an adequate dose —
# not when incidental broad cofactors (zinc, selenium, copper, vitamin E,
# omega-3, iron...) merely overlap. Without this, a pre-workout that only
# contains trace zinc+selenium was mapped to eye/immune/liver/thyroid/skin/
# hormonal goals (P0 data-correctness bug: ~2k products per weak goal).
#
# Scope note: GOAL-EMISSION POLICY ONLY. This gate feeds `goal_matches`; it does
# NOT touch the synergy DISPLAY or the A5c synergy score (both read the enriched
# clusters directly and are unaffected). Anchor strings are lower-cased and match
# synergy_cluster.json `ingredients`. Curated only for the clusters that drove
# false goals; every other cluster keeps the legacy "any adequate match" gate.
# (Interim home: belongs beside the cluster defs in synergy_cluster.json, but
# that file is under concurrent edit — migrate when reconciling.)
_GOAL_CLUSTER_ANCHORS: Dict[str, set] = {
    "eye_health": {"lutein", "zeaxanthin", "astaxanthin", "bilberry", "saffron"},
    "immune_defense": {
        "vitamin c", "ascorbic acid", "ester-c", "vitamin d", "vitamin d3",
        "cholecalciferol", "elderberry", "sambucus", "echinacea", "beta glucans",
        "beta-glucan", "astragalus", "colostrum", "epicor", "quercetin",
        "mushroom complex",
    },
    "hair_skin_nutrition": {
        "biotin", "vitamin b7", "collagen", "collagen peptides", "keratin",
        "silica", "bamboo extract", "hyaluronic acid", "msm",
        "methylsulfonylmethane",
    },
    "liver_support": {
        "milk thistle", "silymarin", "nac", "n-acetyl-cysteine",
        "alpha-lipoic acid", "ala", "artichoke extract", "cynara scolymus",
        "dandelion root", "turmeric", "curcumin", "glutathione", "schisandra",
        "burdock root", "tudca",
    },
    "thyroid_support": {
        "iodine", "kelp", "bladderwrack", "tyrosine", "l-tyrosine", "guggul",
    },
    "wound_healing": {
        "collagen", "collagen peptides", "l-arginine", "arginine", "bromelain",
        "aloe vera",
    },
    "fertility_female": {
        "myo-inositol", "inositol", "d-chiro-inositol", "coq10", "coenzyme q10",
        "ubiquinol", "vitex", "chasteberry",
    },
    "prenatal_pregnancy_support": {
        "folate", "folic acid", "methylfolate", "5-mthf", "quatrefolic", "dha",
        "choline", "iron", "iodine", "vitamin d", "vitamin d3",
    },
    "hormone_balance_men": {
        "ashwagandha", "ksm-66", "tongkat ali", "eurycoma longifolia",
        "tribulus terrestris", "d-aspartic acid", "daa", "boron", "saw palmetto",
        "nettle root", "dim", "diindolylmethane", "maca", "fenugreek",
    },
    "hormone_balance_women": {
        "chasteberry", "vitex", "dim", "diindolylmethane", "black cohosh",
        "red clover", "evening primrose oil", "dong quai", "wild yam",
        "shatavari", "maca", "calcium d-glucarate",
    },
    "skin_health_complex": {
        "hyaluronic acid", "ceramides", "marine collagen", "type i collagen",
        "biotin",
    },
    "collagen_synthesis_support": {
        "collagen peptides", "type i collagen", "type ii collagen",
        "type iii collagen", "lysine", "l-lysine", "proline", "l-proline",
        "hydroxyproline", "glycine", "silica", "silicon", "bamboo extract",
        "hyaluronic acid",
    },
    "antioxidant_defense": {
        "glutathione", "nac", "alpha-lipoic acid", "resveratrol",
        "green tea extract", "egcg", "grape seed extract", "pycnogenol",
        "astaxanthin", "bilberry", "coq10", "ubiquinol",
    },
    "adrenal_support": {
        "ashwagandha", "rhodiola", "rhodiola rosea", "holy basil", "ginseng",
        "panax ginseng", "licorice",
    },
    "respiratory_health_lung_support": {
        "nac", "n-acetyl cysteine", "n-acetylcysteine", "bromelain",
        "elderberry", "sambucus", "cordyceps", "mullein", "ivy leaf extract",
        "pelargonium sidoides", "quercetin",
    },
    "prostate_health": {
        "saw palmetto", "serenoa repens", "beta-sitosterol", "plant sterols",
        "pygeum", "pygeum africanum", "nettle root", "stinging nettle",
        "pumpkin seed oil", "pumpkin seed extract", "lycopene",
    },
    "menopause_perimenopause_support": {
        "black cohosh", "cimicifuga racemosa", "red clover", "isoflavones",
        "soy isoflavones", "genistein", "evening primrose oil", "maca",
        "lepidium meyenii", "sage", "dong quai", "shatavari",
    },
    "blood_sugar_regulation": {
        "berberine", "berberine hcl", "chromium", "chromium picolinate",
        "alpha-lipoic acid", "ala", "cinnamon", "cinnamon extract", "gymnema",
        "gymnema sylvestre", "bitter melon", "vanadyl sulfate", "banaba leaf",
        "fenugreek",
    },
}

# Product-intent tier-2: a handful of BROAD micronutrients that genuinely ARE
# the primary actor for a few nutrient-defined goals (zinc for immune, vitamin
# C/E/selenium for antioxidant, zinc lozenges for respiratory). They are
# EXCLUDED from the anchor sets above on purpose — as an incidental cofactor in
# a loaded pre-workout or a 95-ingredient multivitamin they are noise. They
# should only claim the goal when the product is FOCUSED on them: a standalone
# "Zinc 30", "Vitamin C & E", "Zinc Lozenges". The active-count ceiling is the
# dominance proxy — a bare mineral pill has ~1-3 actives; a multi/pre-workout
# has many. (Specific goals like eye/liver/thyroid never get a tier-2 entry —
# a broad micronutrient is never their primary actor.)
_GOAL_CLUSTER_FOCUSED_NUTRIENTS: Dict[str, set] = {
    "immune_defense": {
        "zinc", "zinc picolinate", "zinc bisglycinate", "vitamin a", "retinol",
    },
    "antioxidant_defense": {
        "vitamin c", "ascorbic acid", "ester-c", "vitamin e", "alpha-tocopherol",
        "selenium", "selenomethionine",
    },
    "respiratory_health_lung_support": {
        "zinc", "zinc picolinate", "vitamin c", "ascorbic acid",
    },
}
# A product with more disclosed actives than this is not "focused" on a tier-2
# micronutrient — the nutrient is incidental, so it does not claim the goal.
_GOAL_CLUSTER_FOCUS_MAX_ACTIVES = 3

_GOAL_CLUSTER_INTENT_KEYWORDS: Dict[str, tuple] = {
    # Iodine/selenium in multis and sports formulas should not imply a hormonal
    # or thyroid goal. Keep thyroid support for focused iodine/kelp products or
    # formulas explicitly positioned around thyroid support.
    "thyroid_support": ("thyroid", "iodine", "kelp", "bladderwrack", "guggul"),
}
_PRENATAL_GOAL_INTENT_KEYWORDS = (
    "prenatal",
    "pre-natal",
    "pregnancy",
    "pregnant",
    "maternal",
    "ttc",
    "trying to conceive",
)
_PRENATAL_GOAL_ANCHOR_GROUPS = {
    "folate": {"folate", "folic acid", "methylfolate", "5-mthf", "quatrefolic"},
    "dha": {"dha"},
    "choline": {"choline"},
    "iron": {"iron"},
    "iodine": {"iodine"},
    "vitamin_d": {"vitamin d", "vitamin d3"},
}
_PRENATAL_GOAL_MIN_ANCHOR_GROUPS = 3


def _goal_cluster_active_count(enriched: Dict[str, Any]) -> int:
    """Best available active-count proxy for focused-nutrient goal gating."""
    active_rows = [
        row for row in safe_list(enriched.get("activeIngredients"))
        if isinstance(row, dict)
    ]
    if active_rows:
        return len(active_rows)

    raw_count = safe_float(enriched.get("raw_actives_count"))
    if raw_count is not None and raw_count > 0:
        return int(raw_count)

    detail_rows = [
        row for row in safe_list(enriched.get("ingredients"))
        if isinstance(row, dict)
    ]
    if detail_rows:
        return len(detail_rows)

    # Unknown breadth should not qualify as "focused"; this prevents legacy
    # detail-blob shapes from leaking broad micronutrient goals.
    return _GOAL_CLUSTER_FOCUS_MAX_ACTIVES + 1


def _goal_cluster_match_name(match: Any) -> str:
    if isinstance(match, dict):
        for key in ("cluster_ingredient", "name", "standard_name", "standardName"):
            value = safe_str(match.get(key)).strip().lower()
            if value:
                return value
        return ""
    return safe_str(match).strip().lower()


def _goal_cluster_all_adequate(cluster: Dict[str, Any]) -> Optional[bool]:
    if "all_adequate" not in cluster:
        return None
    value = cluster.get("all_adequate")
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _goal_cluster_match_adequacy(match: Any, cluster_all_adequate: Optional[bool]) -> Optional[bool]:
    if isinstance(match, dict) and match.get("meets_minimum") is not None:
        return bool(match.get("meets_minimum"))
    return cluster_all_adequate


def _goal_cluster_product_text(enriched: Dict[str, Any]) -> str:
    taxonomy = safe_dict(enriched.get("supplement_taxonomy"))
    parts = [
        enriched.get("product_name"),
        enriched.get("brand_name"),
        enriched.get("product_role"),
        taxonomy.get("primary_type"),
        taxonomy.get("secondary_type"),
    ]
    return " ".join(safe_str(part).lower() for part in parts if safe_str(part))


def _goal_cluster_intent_allowed(cid: str, active_count: int, product_text: str) -> bool:
    keywords = _GOAL_CLUSTER_INTENT_KEYWORDS.get(cid)
    if not keywords:
        return True
    if active_count <= _GOAL_CLUSTER_FOCUS_MAX_ACTIVES:
        return True
    return any(keyword in product_text for keyword in keywords)


def _prenatal_goal_cluster_allowed(
    matched: list,
    *,
    require_adequate_dose: bool,
    cluster_all_adequate: Optional[bool],
    product_text: str,
) -> bool:
    """Full prenatal goal support requires prenatal positioning or a panel.

    A plain B-complex with folate/B12 should not become a full prenatal match.
    A prenatal-positioned product (e.g. Prenatal DHA, Prenatal Multi) can claim
    the cluster with its relevant prenatal anchor; otherwise require a broader
    prenatal anchor panel so a general nutrient product is not over-promoted.
    """
    if any(keyword in product_text for keyword in _PRENATAL_GOAL_INTENT_KEYWORDS):
        return True

    groups: set[str] = set()
    for m in matched:
        adequacy = _goal_cluster_match_adequacy(m, cluster_all_adequate)
        if require_adequate_dose and adequacy is False:
            continue
        ing = _goal_cluster_match_name(m)
        for group, aliases in _PRENATAL_GOAL_ANCHOR_GROUPS.items():
            if ing in aliases:
                groups.add(group)
                break
    return len(groups) >= _PRENATAL_GOAL_MIN_ANCHOR_GROUPS


def _extract_product_cluster_ids(enriched: Dict, enforce_dose_gate: bool = True) -> set:
    """Flatten product cluster IDs from the enrichment output.

    Source of truth from ``enrich_supplements_v3.py``:
      ``enriched["formulation_data"]["synergy_clusters"]`` is a list of cluster
      dicts each containing ``cluster_id`` (e.g. ``"sleep_stack"``).

    Dose-adequacy gate (``enforce_dose_gate=True``, default): a cluster counts
    only when at least one of its ``matched_ingredients`` meets the
    ingredient's minimum effective dose (``meets_minimum``). This prevents
    trace-mineral over-matching from promoting clusters to goals — e.g. 17 mg
    of magnesium in a whey protein powder must not earn the product a "Sleep
    Quality" match, because the sleep-effective magnesium dose is ~200 mg.
    Clusters without dose data (no ``matched_ingredients`` key, or all entries
    with ``meets_minimum`` missing/null) pass through — legacy shape tolerance.

    Pass ``enforce_dose_gate=False`` to get the presence-only set (every
    matched cluster regardless of dose). ``compute_goal_matches`` runs both:
    the gated set drives ``goal_matches`` (dose-adequate support) and the
    presence-only set surfaces goals that match but are below effective dose
    (``goal_matches_underdosed``). The presence-only set is always a superset
    of the gated set.

    Also tolerates a ``synergy_detail.clusters_matched`` flat list if present
    (legacy/alternate path), so callers can feed either the raw enrichment
    object or the post-build detail blob.

    Returns a deduplicated set of non-empty cluster ID strings.
    """
    ids: set = set()
    # Product breadth — the dominance proxy for the tier-2 focused-nutrient gate.
    active_count = _goal_cluster_active_count(enriched)
    product_text = _goal_cluster_product_text(enriched)

    def _cluster_passes_goal_gate(cluster: Dict, *, require_adequate_dose: bool) -> bool:
        """True iff the cluster is goal-relevant.

        Curated clusters require a defining anchor match for both supported and
        underdosed goal surfaces. ``require_adequate_dose`` only decides whether
        that anchor must meet its effective dose, or whether presence is enough
        for the underdosed surface.
        """
        matched = cluster.get("matched_ingredients")
        if not isinstance(matched, list) or not matched:
            # No per-ingredient data → trust the cluster (legacy tolerance).
            return True
        # Anchor set for this cluster (None = uncurated → legacy behavior).
        cid = safe_str(cluster.get("cluster_id") or cluster.get("id"))
        anchors = _GOAL_CLUSTER_ANCHORS.get(cid)
        focused = _GOAL_CLUSTER_FOCUSED_NUTRIENTS.get(cid)
        is_focused_product = active_count <= _GOAL_CLUSTER_FOCUS_MAX_ACTIVES
        cluster_all_adequate = _goal_cluster_all_adequate(cluster)
        if cid == "prenatal_pregnancy_support":
            return _prenatal_goal_cluster_allowed(
                matched,
                require_adequate_dose=require_adequate_dose,
                cluster_all_adequate=cluster_all_adequate,
                product_text=product_text,
            )
        has_dose_info = False
        for m in matched:
            adequacy = _goal_cluster_match_adequacy(m, cluster_all_adequate)
            if adequacy is not None:
                has_dose_info = True
            if require_adequate_dose and adequacy is False:
                continue
            # Relevant match. For a curated cluster it only counts toward the
            # GOAL when it is a defining anchor — an incidental cofactor
            # (zinc/selenium/vitamin E/omega-3...) is not evidence the product
            # is FORMULATED for that goal. Keep scanning for an anchor;
            # uncurated clusters accept any adequate match.
            if anchors is not None:
                ing = _goal_cluster_match_name(m)
                if ing in anchors:
                    return _goal_cluster_intent_allowed(cid, active_count, product_text)
                # Tier-2: a broad micronutrient that IS the primary actor for
                # this goal (zinc→immune, vit C/E→antioxidant) counts only when
                # the product is focused on it — not incidental in a multi/stack.
                if focused is not None and is_focused_product and ing in focused:
                    return True
                continue
            return True
        # Rich dose data present and no adequate (anchor) match → filter out.
        # If dose data is absent across all matches, be lenient.
        if anchors is not None:
            return False
        return not has_dose_info

    # Primary path: formulation_data.synergy_clusters[*].cluster_id
    formulation = safe_dict(enriched.get("formulation_data"))
    for cluster in safe_list(formulation.get("synergy_clusters")):
        if isinstance(cluster, dict):
            cid = safe_str(cluster.get("cluster_id"))
            if not cid:
                continue
            if not _cluster_passes_goal_gate(
                cluster,
                require_adequate_dose=enforce_dose_gate,
            ):
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
            if not _cluster_passes_goal_gate(
                cluster,
                require_adequate_dose=enforce_dose_gate,
            ):
                continue
            ids.add(cid)

    if _probiotic_goal_cluster_applies(enriched, enforce_dose_gate=enforce_dose_gate):
        ids.add(PROBIOTIC_GOAL_CLUSTER_ID)
    if _fiber_goal_cluster_applies(enriched, enforce_dose_gate=enforce_dose_gate):
        ids.add(FIBER_GOAL_CLUSTER_ID)
    if _creatine_goal_cluster_applies(enriched, enforce_dose_gate=enforce_dose_gate):
        ids.add(CREATINE_GOAL_CLUSTER_ID)
    if _protein_goal_cluster_applies(enriched, enforce_dose_gate=enforce_dose_gate):
        ids.add(CREATINE_GOAL_CLUSTER_ID)
    ids.update(_pre_workout_goal_cluster_ids(enriched, enforce_dose_gate=enforce_dose_gate))
    if _sleep_goal_cluster_applies(enriched, enforce_dose_gate=enforce_dose_gate):
        ids.add(SLEEP_GOAL_CLUSTER_ID)
    if _joint_goal_cluster_applies(enriched, enforce_dose_gate=enforce_dose_gate):
        ids.add(JOINT_GOAL_CLUSTER_ID)

    return ids


def _evaluate_goal_match(goal_mapping: Dict, product_clusters: set) -> Optional[float]:
    """Score one goal against a set of product clusters.

    Returns the normalized match score (0.0..1.0) when the goal qualifies, or
    ``None`` when any gate fails. Pure function of ``(mapping, clusters)`` so
    ``compute_goal_matches`` can call it twice — once with the dose-adequate
    cluster set (→ ``goal_matches``) and once with the presence-only set
    (→ ``goal_matches_underdosed``) — without duplicating the gate logic.

    Gates (v6.0.0):
      1. blocked_by_clusters present → disqualify regardless of score.
      2. required_clusters non-empty AND none present → disqualify.
      3. normalized weighted score < min_match_score → disqualify.
    """
    cluster_weights = safe_dict(goal_mapping.get("cluster_weights"))
    if not cluster_weights:
        return None

    required = {safe_str(c) for c in safe_list(goal_mapping.get("required_clusters")) if safe_str(c)}
    blocked = {safe_str(c) for c in safe_list(goal_mapping.get("blocked_by_clusters")) if safe_str(c)}
    min_score = safe_float(goal_mapping.get("min_match_score"), 0.5)

    # Gate 1: blocked clusters disqualify regardless of score
    if blocked and (product_clusters & blocked):
        return None

    # Gate 2: required clusters must have at least one present (when list is non-empty)
    if required and not (product_clusters & required):
        return None

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
        return None
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
    return score if score >= min_score else None


def compute_goal_matches(enriched: Dict) -> Dict:
    """Pre-compute which goals this product matches based on synergy clusters.

    Contract (schema v6.0.0 — pipeline-owned, Flutter consumes results only):
      * Reads product cluster IDs from the enrichment output
        (primary: ``formulation_data.synergy_clusters[*].cluster_id``;
        fallback: ``synergy_detail.clusters_matched`` or
        ``synergy_detail.clusters[*].id``).
      * For each goal in ``user_goal_mappings`` (gates in ``_evaluate_goal_match``):
          - Skip if ANY of ``blocked_by_clusters`` is present in product clusters.
          - Skip if ``required_clusters`` is non-empty AND none are present.
          - ``score = max(score_full, score_required)`` (normalized 0.0..1.0).
          - Include goal iff ``score >= min_match_score``.
      * Runs the gates twice: over the dose-adequate cluster set
        (→ ``goal_matches``) and over the presence-only superset. Goals that
        qualify only on presence — matched ingredient(s) present but below the
        effective dose — route to ``goal_matches_underdosed`` instead. The two
        lists are mutually exclusive.
      * ``goal_match_confidence`` is the average matched score across the
        SUPPORTED (dose-adequate) goals only, rounded to 2 decimals.

    Returns dict with keys: ``goal_matches``, ``goal_match_confidence``,
    ``goal_matches_underdosed``.
    """
    goal_mappings = _load_goal_mappings()
    if not goal_mappings:
        return {
            "goal_matches": [],
            "goal_match_confidence": 0.0,
            "goal_matches_underdosed": [],
        }

    # Two cluster sets drive the two-tier match. The dose-adequate (gated) set
    # produces supported goals; the presence-only superset surfaces goals that
    # match on ingredient presence but sit below their effective dose. A goal
    # qualifying only on the presence set routes to goal_matches_underdosed —
    # the pipeline source of truth for the app's "Partially supported" bucket.
    adequate_clusters = _extract_product_cluster_ids(enriched, enforce_dose_gate=True)
    present_clusters = _extract_product_cluster_ids(enriched, enforce_dose_gate=False)

    if not present_clusters:
        return {
            "goal_matches": [],
            "goal_match_confidence": 0.0,
            "goal_matches_underdosed": [],
        }

    matched_goals: List[str] = []
    matched_scores: List[float] = []
    underdosed_goals: List[str] = []

    for goal_mapping in goal_mappings:
        if not isinstance(goal_mapping, dict):
            continue

        goal_id = safe_str(goal_mapping.get("id"))
        if not goal_id:
            continue

        # Tier 1 — dose-adequate support. Confidence is averaged over these
        # (the supported goals) only, preserving the prior contract.
        adequate_score = _evaluate_goal_match(goal_mapping, adequate_clusters)
        if adequate_score is not None:
            matched_goals.append(goal_id)
            matched_scores.append(adequate_score)
            continue

        # Tier 2 — qualifies on presence but failed the dose gate above:
        # present-but-underdosed. Never both supported and underdosed (the
        # ``continue`` above guarantees mutual exclusion).
        if _evaluate_goal_match(goal_mapping, present_clusters) is not None:
            underdosed_goals.append(goal_id)

    if matched_goals:
        avg_confidence = sum(matched_scores) / len(matched_scores)
    else:
        avg_confidence = 0.0

    return {
        "goal_matches": matched_goals,
        "goal_match_confidence": round(avg_confidence, 2),
        "goal_matches_underdosed": underdosed_goals,
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


def _normalize_weight_serving_for_display(
    min_qty: Optional[float],
    max_qty: Optional[float],
    unit: str,
) -> tuple[Optional[float], Optional[float], str]:
    """Keep weight serving summaries in human units without changing dose math."""
    unit_l = safe_str(unit).strip().lower()
    compact = unit_l.replace(".", "").replace(" ", "")
    if compact in {"mg", "milligram", "milligrams", "milligram(s)"}:
        finite_values = [
            abs(q) for q in (min_qty, max_qty)
            if q is not None and _math.isfinite(q)
        ]
        if not finite_values:
            return min_qty, max_qty, unit
        largest = max(finite_values)
        if largest >= 1000:
            return (
                None if min_qty is None else min_qty / 1000.0,
                None if max_qty is None else max_qty / 1000.0,
                "g",
            )
    return min_qty, max_qty, unit


def _collagen_serving_looks_implausible(
    enriched: Dict,
    max_qty: Optional[float],
    unit: str,
    max_daily: Any,
) -> bool:
    """Hide clearly broken collagen serving summaries before export."""
    if max_qty is None or not _math.isfinite(max_qty):
        return False

    haystack_parts = [
        safe_str(enriched.get("product_name")),
        safe_str(enriched.get("brand_name")),
        safe_str(enriched.get("form_factor")),
        safe_str(enriched.get("form_factor_canonical")),
    ]
    ingredient_quality = safe_dict(enriched.get("ingredient_quality_data"))
    for ing in safe_list(ingredient_quality.get("ingredients_scorable")):
        ing = safe_dict(ing)
        haystack_parts.extend([
            safe_str(ing.get("name")),
            safe_str(ing.get("standard_name")),
            safe_str(ing.get("canonical_id")),
        ])
    haystack = " ".join(haystack_parts).lower()
    if "collagen" not in haystack:
        return False

    unit_l = safe_str(unit).strip().lower().replace(".", "").replace(" ", "")
    if unit_l in {"g", "gram", "grams", "gram(s)"}:
        grams_per_serving = max_qty
    elif unit_l in {"mg", "milligram", "milligrams", "milligram(s)"}:
        grams_per_serving = max_qty / 1000.0
    else:
        return False

    daily_multiplier = safe_float(max_daily, 1.0) or 1.0
    daily_multiplier = max(daily_multiplier, 1)
    return grams_per_serving * daily_multiplier > 50


def _diabetes_friendly_from_dietary(ds: Dict[str, Any]) -> bool:
    if not safe_bool(ds.get("diabetes_friendly", False)):
        return False

    sugar = safe_dict(ds.get("sugar"))
    if safe_bool(sugar.get("has_added_sugar")):
        return False
    if safe_bool(sugar.get("exceeds_diabetic_threshold")):
        return False

    sweeteners = safe_dict(ds.get("sweeteners"))
    if safe_bool(sweeteners.get("has_high_glycemic")):
        return False

    for warning in safe_list(ds.get("warnings")):
        warning = safe_dict(warning)
        if safe_str(warning.get("type")).lower() == "diabetes":
            return False

    return True


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
    # Weight units — must come before powder/scoop fallback.
    if "milligram" in unit_l or unit_l.strip() in ("mg", "mg."):
        return ("Mix", "mg", "mg")
    if (
        "gram" in unit_l
        or unit_l.strip() in ("g", "g.")
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

    Prefers enriched["serving_basis"] (enricher-computed, same source the
    scorer uses for dose adequacy) over raw enriched["servingSizes"].
    Falls back to servingSizes for backward compat with pre-serving_basis data.

    Returns dict with keys: dosing_summary, servings_per_container
    """
    # SP-3 (2026-05-21): prefer canonical form_factor for serving-verb derivation.
    # Falls back to legacy free-text field for old enriched batches.
    canonical = safe_str(enriched.get("form_factor_canonical")).lower()
    form_factor = (
        canonical
        if canonical and canonical != "unknown"
        else safe_str(enriched.get("form_factor")).lower()
    )

    # Primary source: serving_basis (enricher-computed, scorer-aligned)
    sb = safe_dict(enriched.get("serving_basis"))
    if sb.get("basis_count") is not None:
        min_qty_raw = sb.get("basis_count")
        max_qty_raw = sb.get("basis_count")
        unit = safe_str(sb.get("basis_unit"))
        max_daily = sb.get("max_servings_per_day")
    else:
        # Fallback: raw servingSizes from cleaner
        serving_sizes = safe_list(enriched.get("servingSizes"))
        serving = safe_dict(serving_sizes[0]) if serving_sizes else {}
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

        min_qty, max_qty, unit = _normalize_weight_serving_for_display(
            min_qty, max_qty, unit,
        )

        verb, noun_singular, noun_plural = _derive_serving_verb_and_noun(unit, form_factor)

        if _collagen_serving_looks_implausible(enriched, max_qty, unit, max_daily):
            summary = "See product label"
        elif min_qty == max_qty:
            qty_text = _format_quantity(min_qty)
            noun = noun_singular if min_qty == 1 else noun_plural
            cadence = _frequency_phrase(max_daily)
            summary = f"{verb} {qty_text} {noun} {cadence}".strip()
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

    This array is the structured contract for Flutter's personalized
    allergen matcher (matchAllergens against profile.allergens). Exact
    `allergen_id` matching only — no substring. Allergen facts are not
    duplicated into warning channels, which are reserved for global
    hazards and profile-gated interaction warnings.

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


def registry_verified_cert_display_programs(enriched: Dict) -> List[str]:
    """Registry-verified (sku/product_line) cert program names whose
    matched_brand agrees with the product brand.

    Mirrors the scoring-layer brand guard in scoring_v4 trust modules —
    deliberately duplicated per the stale-artifact defense doctrine, so a
    stale enriched artifact carrying a cross-brand registry row can light
    neither score nor display badge. claimed_only / needs_review /
    brand_only rows never reach display: a claim is not verification.
    """
    from scoring_v4.modules.generic_trust import _brand_key, _brand_tokens

    out: List[str] = []
    product_brand = _brand_key(
        enriched.get("brandName") or enriched.get("brand_name") or enriched.get("brand") or ""
    )
    for entry in safe_list(enriched.get("verified_cert_programs")):
        if not isinstance(entry, dict) or entry.get("scoring_blocked_reason"):
            continue
        if str(entry.get("scope") or "").strip().lower() not in ("sku", "product_line"):
            continue
        matched_brand = _brand_key(entry.get("matched_brand"))
        if matched_brand and product_brand:
            mt, pt = _brand_tokens(matched_brand), _brand_tokens(product_brand)
            if not (mt and pt and (mt <= pt or pt <= mt)):
                continue
        name = str(entry.get("program") or "").strip()
        if name and name not in out:
            out.append(name)
    return out


def compute_v4_category_percentiles(
    rows: List[Tuple[str, Optional[str], float]],
    min_cohort: int = 5,
) -> List[Tuple[float, float, int, str]]:
    """Rank shipped v4 /100 scores within each percentile-category cohort.

    Mirrors ``score_supplements._attach_category_percentiles`` exactly, but over
    the actually-exported ``quality_score_v4_100`` instead of the retired V3
    ``score_100_equivalent``. Products in a cohort smaller than ``min_cohort``
    are left unranked (no tuple emitted -> percentile columns stay NULL, which
    matches the V3 "insufficient_cohort_size" behaviour).

    Args:
        rows: ``(dsld_id, percentile_category, quality_score_v4_100)`` for
            products that are v4-scored (``quality_score_status == 'scored'``).
            Rows with an empty/None category are ignored (no cohort to rank in).
        min_cohort: smallest cohort that gets ranked (default 5, matching
            ``score_supplements._CATEGORY_PERCENTILE_MIN_COHORT``).

    Returns:
        ``(percentile_rank, top_pct, cohort_size, dsld_id)`` per ranked product.
    """
    cohorts: Dict[str, List[Tuple[str, float]]] = {}
    for dsld_id, category, score in rows:
        if not category or score is None:
            continue
        cohorts.setdefault(category, []).append((dsld_id, float(score)))

    updates: List[Tuple[float, float, int, str]] = []
    for members in cohorts.values():
        cohort_size = len(members)
        if cohort_size < min_cohort:
            continue
        scores = [s for _, s in members]
        for dsld_id, score in members:
            higher = sum(1 for v in scores if v > score)
            equal = sum(1 for v in scores if v == score)
            rank = higher + ((equal + 1.0) / 2.0)
            top_pct = round(max(0.0, min(100.0, (rank / cohort_size) * 100.0)), 1)
            percentile_rank = round(100.0 - top_pct, 1)
            updates.append((percentile_rank, top_pct, cohort_size, dsld_id))
    return updates


def build_core_row(
    enriched: Dict,
    scored: Dict,
    exported_at: str,
    detail_blob_sha256: Optional[str] = None,
    detail_blob: Optional[Dict] = None,
) -> tuple:
    """Build a products_core row tuple from enriched + scored product data."""
    comp = safe_dict(enriched.get("compliance_data"))
    ds = safe_dict(enriched.get("dietary_sensitivity_data"))
    cp = safe_dict(scored.get("category_percentile"))
    st_str = resolve_export_supplement_type(enriched, scored)
    sm = safe_dict(scored.get("scoring_metadata"))

    # cert_programs / has_third_party_testing: union of label-named programs
    # and registry-verified (sku/product_line) certs. Label-only sourcing
    # inverted the badge — Thorne Super EPA (two NSF SKU registry matches)
    # shipped has_third_party_testing=0 while label-claim-only products
    # showed the badge (2026-06-09 audit).
    cert_display_programs = [
        str(p) for p in safe_list(enriched.get("named_cert_programs")) if str(p).strip()
    ]
    for _prog in registry_verified_cert_display_programs(enriched):
        if _prog not in cert_display_programs:
            cert_display_programs.append(_prog)

    disc_date = safe_str(enriched.get("discontinuedDate"))[:10] or None
    has_export_banned_signal = (
        has_banned_substance(enriched)
        or blob_has_critical_banned_warning(detail_blob)
    )
    effective_scored = dict(scored)
    if has_export_banned_signal:
        # The blob resolver can detect a broader hard-block signal than the
        # scorer. Collapse every public score surface through the same v4-native
        # artifact boundary so core rows and detail blobs cannot disagree.
        effective_scored = suppress_scored_artifact_for_hard_block(
            effective_scored, reason="banned_substance"
        )
    elif blob_has_profile_gated_hard_safety_warning(detail_blob):
        # Release-gate invariant: SAFE on either verdict or safety_verdict is
        # incompatible with a hard-safety warning (banned/recalled/adulterant/
        # watchlist always; high_risk_ingredient/contraindicated when severity is
        # high/critical/contraindicated/avoid). Bitter orange, DHEA, Titanium
        # Dioxide watchlist, etc. cannot ship as SAFE on the catalog row.
        #
        # Two v4-artifact paths to SAFE need to be guarded:
        #   1. verdict == "SAFE"          → catalog reads SAFE directly.
        #   2. verdict == "POOR"          → safety_verdict may still be "SAFE"
        #                                   when the quality drop did not come
        #                                   from a safety signal. A hard-safety
        #                                   warning must override that projection
        #                                   so safety_verdict no longer says SAFE.
        # In both cases the verdict drops to CAUTION (clear non-SAFE signal
        # short of a hard block) — keeping POOR-verdict products at POOR would
        # leave safety_verdict=SAFE under the derivation rule and re-introduce
        # the contradiction.
        verdict_now = safe_str(effective_scored.get("verdict")).upper()
        safety_now = safe_str(effective_scored.get("safety_verdict")).upper()
        if verdict_now == "SAFE" or safety_now == "SAFE":
            effective_scored.update({
                "verdict": "CAUTION",
                "safety_verdict": "CAUTION",
            })

    score_100 = safe_float(effective_scored.get("score_100_equivalent"))
    ss = safe_dict(effective_scored.get("section_scores"))
    v4_pillars = safe_dict(effective_scored.get("_v4_pillars"))

    top_warnings = build_top_warnings(enriched)

    derived_blocking = derive_blocking_reason(enriched, scored)
    scored_blocking = safe_str(scored.get("blocking_reason"))
    safety_signal_reason = (
        safe_str(effective_scored.get("safety_signal_reason"))
        or safe_str(effective_scored.get("_v4_safety_signal_reason"))
        or None
    )
    stale_safety_blocking = (
        scored_blocking in {"banned_ingredient", "recalled_ingredient", "high_risk_ingredient"}
        and derived_blocking is None
        and not blob_has_safety_blocking_warning(detail_blob)
    )
    blocking = (
        "banned_ingredient"
        if has_export_banned_signal
        else derived_blocking or (None if stale_safety_blocking or not scored_blocking else scored_blocking)
    )
    interaction_hint = build_interaction_summary_hint(enriched)
    decision_highlights = build_decision_highlights(enriched, effective_scored, blocking)
    _validate_decision_highlights(decision_highlights, safe_str(enriched.get("dsld_id")))

    # ─── v1.1.0 Enhancements ───
    fingerprint = generate_ingredient_fingerprint(enriched)
    key_nutrients = generate_key_nutrients_summary(enriched)
    share_meta = generate_share_metadata(enriched, effective_scored)
    categories = classify_product_categories(enriched, effective_scored)
    goal_data = compute_goal_matches(enriched)
    dosing = generate_dosing_summary(enriched)
    net_contents = generate_net_contents_summary(enriched)
    allergen_summ = generate_allergen_summary(enriched)
    non_gmo_audit = derive_non_gmo_audit(enriched)

    # 2026-05-12 — searchable ingredient text. Aggregate all ingredient
    # display names (active + inactive) so products_fts can match by
    # ingredient. Use a set to dedup, sort for deterministic builds.
    ing_tokens: set[str] = set()
    iqd = safe_dict(enriched.get("ingredient_quality_data"))
    active_export_contract = _active_export_contract(enriched)
    iqd_search_rows = safe_list(iqd.get("ingredients_scorable")) + safe_list(iqd.get("ingredients_recognized_non_scorable"))
    if not iqd_search_rows:
        iqd_search_rows = safe_list(iqd.get("ingredients"))
    for ing in iqd_search_rows:
        if not isinstance(ing, dict):
            continue
        if not _active_row_allowed_for_primary_export(ing, active_export_contract):
            continue
        for k in ("standard_name", "matched_name", "name", "raw_source_text",
                  "canonical_id", "display_label"):
            v = ing.get(k)
            if isinstance(v, str) and v.strip() and v.strip().lower() not in {"unknown", "n/a", "none"}:
                ing_tokens.add(v.strip())
    # Active ingredients can be recognized by the resolver yet absent from IQM
    # scoring rows (banned/not-lawful actives, non-scorable botanical source
    # identities, etc.). FTS must still expose those names and canonicals.
    for ing in safe_list(enriched.get("activeIngredients")):
        if not isinstance(ing, dict):
            continue
        if not _active_row_allowed_for_primary_export(ing, active_export_contract):
            continue
        for k in ("standardName", "name", "raw_source_text", "canonical_id", "normalized_key"):
            v = ing.get(k)
            if isinstance(v, str) and v.strip() and v.strip().lower() not in {"unknown", "n/a", "none"}:
                ing_tokens.add(v.strip())
        # DSLD lists Sodium/mineral compounds as a bare mineral name with the real
        # compound in an "as" form (e.g. name="Sodium", forms=["Sodium Beta-
        # Hydroxybutyrate"]). For non-IQD actives the bare name is all FTS would
        # see; surface the form name so the compound is searchable.
        for form in safe_list(ing.get("forms")):
            fn = form.get("name") if isinstance(form, dict) else None
            if isinstance(fn, str) and fn.strip() and fn.strip().lower() not in {"unknown", "n/a", "none"}:
                ing_tokens.add(fn.strip())
    # Inactives — pull from canonical inactiveIngredients list (label-fidelity)
    for ing in safe_list(enriched.get("inactiveIngredients")):
        if isinstance(ing, dict):
            for k in ("standardName", "name", "raw_source_text"):
                v = ing.get(k)
                if isinstance(v, str) and v.strip():
                    ing_tokens.add(v.strip())
    ingredients_text = " ".join(sorted(ing_tokens))

    return (
        safe_str(enriched.get("dsld_id")),
        safe_str(enriched.get("product_name")),
        safe_str(enriched.get("brand_name") or enriched.get("brandName")),
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
        # SP-3 (2026-05-21): write canonical form_factor when available.
        # Avoids a column rename / migration by reusing the products_core
        # form_factor column. New batches store the canonical id; old
        # batches preserve the legacy free-text value.
        safe_str(
            enriched.get("form_factor_canonical")
            if (
                safe_str(enriched.get("form_factor_canonical")).lower()
                not in {"", "unknown"}
            )
            else enriched.get("form_factor")
        ),
        st_str,
        # Scores (export schema v2.0.0 — canonical /100; legacy /80 columns dropped)
        safe_str(effective_scored.get("display_100")),
        score_100,
        safe_str(effective_scored.get("grade")),
        safe_str(effective_scored.get("verdict")),
        safe_str(effective_scored.get("safety_verdict")),
        safe_float(effective_scored.get("mapped_coverage")),
        # V4 scoring contract — populated by the Stage-3 artifact assembler.
        safe_float(effective_scored.get("_v4_quality_score_100")),
        safe_str(effective_scored.get("_v4_quality_status")) or None,
        safe_str(effective_scored.get("_v4_quality_tier")) or None,
        safe_str(effective_scored.get("_v4_suppressed_reason")) or None,
        safe_float(effective_scored.get("_v4_raw_score_100")),
        safe_str(effective_scored.get("_v4_module")) or None,
        safe_str(effective_scored.get("_v4_confidence")) or None,
        safe_str(effective_scored.get("_score_model_version")) or None,
        safe_str(effective_scored.get("_v4_quality_version")) or None,
        safe_str(effective_scored.get("_v4_scoring_engine_version")) or None,
        safe_str(effective_scored.get("_v4_classification_schema_version")) or None,
        safe_str(effective_scored.get("_v4_config_fingerprint")) or None,
        # V4 six-pillar component scores (from _v4_pillars; NULL when not scored).
        safe_float(safe_dict(v4_pillars.get("formulation")).get("score")),
        safe_float(safe_dict(v4_pillars.get("dose")).get("score")),
        safe_float(safe_dict(v4_pillars.get("evidence")).get("score")),
        safe_float(safe_dict(v4_pillars.get("transparency")).get("score")),
        safe_float(safe_dict(v4_pillars.get("verification")).get("score")),
        safe_float(safe_dict(v4_pillars.get("safety_hygiene")).get("score")),
        # Section scores
        safe_float(safe_dict(ss.get("A_ingredient_quality")).get("score")),
        safe_float(safe_dict(ss.get("A_ingredient_quality")).get("max")),
        safe_float(safe_dict(ss.get("B_safety_purity")).get("score")),
        safe_float(safe_dict(ss.get("B_safety_purity")).get("max")),
        safe_float(safe_dict(ss.get("C_evidence_research")).get("score")),
        safe_float(safe_dict(ss.get("C_evidence_research")).get("max")),
        safe_float(safe_dict(ss.get("D_brand_trust")).get("score")),
        safe_float(safe_dict(ss.get("D_brand_trust")).get("max")),
        # Percentile — rank/top_pct/cohort are emitted NULL here and BACKFILLED
        # after the insert loop by compute_v4_category_percentiles(), which ranks
        # the actually-shipped quality_score_v4_100 within each percentile_category
        # cohort. The frozen category_percentile (score_supplements) ranks on the
        # retired V3 score_100_equivalent and its cohort_size counts the V3-scored
        # set, so neither its rank NOR its cohort can ship next to a V4 score.
        # Category/label (cohort identity) come from canonical taxonomy.
        None,  # percentile_rank      (backfilled: V4 recompute)
        None,  # percentile_top_pct   (backfilled: V4 recompute)
        safe_str((enriched.get("supplement_taxonomy") or {}).get("percentile_category")) or safe_str(cp.get("category_key")),
        safe_str(cp.get("category_label")),
        None,  # percentile_cohort    (backfilled: V4 recompute; V3 cohort is stale)
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
        safety_signal_reason,
        # Quick info
        safe_bool(safe_dict(enriched.get("probiotic_data")).get("is_probiotic_product")),
        safe_bool(ds.get("contains_sugar")),
        safe_bool(ds.get("contains_sodium")),
        safe_bool(_diabetes_friendly_from_dietary(ds)),
        safe_bool(ds.get("hypertension_friendly", False)),
        safe_bool(enriched.get("is_trusted_manufacturer")),
        safe_bool(cert_display_programs),
        safe_bool(enriched.get("has_full_disclosure")),
        # JSON columns
        json.dumps(cert_display_programs, ensure_ascii=False),
        json.dumps(scored.get("badges", []), ensure_ascii=False),
        json.dumps(top_warnings, ensure_ascii=False),
        json.dumps(effective_scored.get("flags", []), ensure_ascii=False),
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
        ingredients_text,
        # Enhancement 4: Goal Matching
        json.dumps(goal_data["goal_matches"], ensure_ascii=False),
        goal_data["goal_match_confidence"],
        json.dumps(goal_data["goal_matches_underdosed"], ensure_ascii=False),
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


CORE_COLUMN_COUNT = 110  # Must match the tuple above and SCHEMA_SQL (v2.0.0: −2 legacy /80 cols, +12 v4 cols, +6 v4 pillar cols, + safety signal reason, + goal_matches_underdosed)


# ─── Reference Data Loader ───

REFERENCE_FILES = {
    "rda_optimal_uls": "data/rda_optimal_uls.json",
    "interaction_rules": "data/ingredient_interaction_rules.json",
    "clinical_risk_taxonomy": "data/clinical_risk_taxonomy.json",
    "medication_profile_gate_rules": "data/medication_profile_gate_rules.json",
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
        "export_contract_quarantined": 0,
        "verdict_blocked": 0,
        "verdict_unsafe": 0,
        "verdict_caution": 0,
        "verdict_not_scored": 0,
    }


def update_audit_state(
    counts: Dict[str, int],
    products_with_warnings_sample: List[Dict],
    contract_quarantines: List[Dict],
    contract_failures: List[Dict],
    products_with_warnings_count: int,
    contract_quarantine_count: int,
    contract_failure_count: int,
    pid: str,
    enriched: Dict,
    scored: Dict,
) -> tuple[int, int]:
    """Update audit counters incrementally for a matched enriched/scored product."""
    issues = validate_export_contract(enriched, scored)
    if issues:
        entry = {"dsld_id": pid, "issues": issues[:5]}
        if _classify_export_error("; ".join(issues)) == "excluded_by_gate":
            counts["export_contract_quarantined"] += 1
            contract_quarantine_count += 1
            contract_quarantines.append(entry)
        else:
            counts["export_contract_invalid"] += 1
            contract_failure_count += 1
            contract_failures.append(entry)

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
                "brand": safe_str(enriched.get("brand_name") or enriched.get("brandName")),
                "verdict": verdict,
                "warnings": top,
            })

    return (
        products_with_warnings_count,
        contract_quarantine_count,
        contract_failure_count,
    )


def write_audit_report(
    output_dir: str,
    exported_at: str,
    counts: Dict[str, int],
    contract_quarantines: List[Dict],
    contract_quarantine_count: int,
    contract_failures: List[Dict],
    contract_failure_count: int,
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
        "contract_failures": contract_failures,
        "contract_quarantines": contract_quarantines,
        "products_with_warnings_count": products_with_warnings_count,
        "products_with_warnings_sample": products_with_warnings_sample[:100],
    }

    audit_path = os.path.join(output_dir, "export_audit_report.json")
    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    logger.info(
        "Audit report: %s (%d products with warnings, %d contract quarantines, "
        "%d contract failures)",
        audit_path,
        products_with_warnings_count,
        contract_quarantine_count,
        contract_failure_count,
    )

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
    score_model = "v4"
    logger.info("Scoring model for export: v4")

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
        contract_quarantines: List[Dict] = []
        contract_failures: List[Dict] = []
        products_with_warnings_count = 0
        contract_quarantine_count = 0
        contract_failure_count = 0
        enriched_only_samples: List[str] = []

        for pid, enriched in iter_staged_products(stage_conn, "enriched_stage"):
            scored = fetch_staged_product(stage_conn, "scored_stage", pid)
            if scored is None:
                audit_counts["enriched_only"] += 1
                if len(enriched_only_samples) < 5:
                    enriched_only_samples.append(pid)
                continue

            # Stage 3 now emits the complete v4-native scored artifact. Final
            # export consumes it directly and never runs a second scorer.
            # The export's banned-substance gate is broader than the v4 scoring
            # safety gate (v4 doesn't block every banned_recalled substance, e.g.
            # Boron / PHOs). When the export will hard-block a banned product, the
            # v4 public contract MUST be suppressed to match — else the catalog
            # ranks a banned product by a finite quality_score_v4_100. Done here,
            # before build_detail_blob / build_core_row, so both surfaces agree.
            if has_banned_substance(enriched):
                scored = suppress_scored_artifact_for_hard_block(
                    scored, reason="banned_substance"
                )

            mark_staged_product_matched(stage_conn, "scored_stage", pid)
            (
                products_with_warnings_count,
                contract_quarantine_count,
                contract_failure_count,
            ) = update_audit_state(
                audit_counts,
                products_with_warnings_sample,
                contract_quarantines,
                contract_failures,
                products_with_warnings_count,
                contract_quarantine_count,
                contract_failure_count,
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
                row = build_core_row(
                    enriched,
                    scored,
                    exported_at,
                    detail_blob_sha256=blob_sha256,
                    detail_blob=blob,
                )
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

    # FTS release gate: the Flutter app's primary search path is products_fts;
    # a catalog shipped without a populated FTS table silently degrades every
    # client to the prefix-LIKE fallback. Fail the build, never ship it.
    fts_count = c.execute("SELECT count(*) FROM products_fts").fetchone()[0]
    core_count = c.execute("SELECT count(*) FROM products_core").fetchone()[0]
    if core_count > 0 and fts_count != core_count:
        raise RuntimeError(
            f"products_fts row count {fts_count} != products_core {core_count} "
            "— FTS rebuild incomplete; refusing to ship a catalog without "
            "full-text search."
        )

    # Reference data
    ref_rows = load_reference_data(script_dir)

    # Canonical v4 scoring-config fingerprint for build reproducibility.
    quality_config_path = os.path.join(
        script_dir, "scoring_v4", "config", "quality_score.json"
    )
    quality_score_config_checksum = None
    if os.path.exists(quality_config_path):
        quality_score_config_checksum = (
            f"sha256:{compute_file_sha256(quality_config_path)}"
        )

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
        ("scoring_version", SCORING_ENGINE_VERSION),
        ("generated_at", manifest_now.isoformat()),
        ("product_count", str(inserted)),
        ("min_app_version", MIN_APP_VERSION),
        ("schema_version", str(EXPORT_SCHEMA_VERSION)),
        ("score_model", str(score_model)),
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

    # ── V4 category percentiles (backfill, ranked over the shipped cohort) ──
    # Runs LAST — after UPC dedup and the NOT_SCORED sweep — so each cohort
    # counts only rows that actually ship. Ranks quality_score_v4_100 within
    # percentile_category, mirroring score_supplements._attach_category_percentiles.
    # Reading products_core means banned-/safety-suppressed products (status !=
    # 'scored') self-exclude; cohorts smaller than 5 stay NULL (unranked).
    pct_rows = c.execute(
        "SELECT dsld_id, percentile_category, quality_score_v4_100 "
        "FROM products_core "
        "WHERE quality_score_status = 'scored' "
        "AND quality_score_v4_100 IS NOT NULL "
        "AND percentile_category IS NOT NULL AND percentile_category != ''"
    ).fetchall()
    pct_updates = compute_v4_category_percentiles(
        [(str(r[0]), str(r[1]), float(r[2])) for r in pct_rows]
    )
    if pct_updates:
        c.executemany(
            "UPDATE products_core SET percentile_rank = ?, percentile_top_pct = ?, "
            "percentile_cohort = ? WHERE dsld_id = ?",
            pct_updates,
        )
    logger.info(
        "V4 percentiles: ranked %d of %d scored products (cohorts >= 5)",
        len(pct_updates), len(pct_rows),
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
        "scoring_version": SCORING_ENGINE_VERSION,
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
        "score_model": score_model,
        "quality_score_config_checksum": quality_score_config_checksum,
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
            "contract_quarantine_count": audit_counts.get(
                "export_contract_quarantined", 0
            ),
            "quality_score_config_checksum": quality_score_config_checksum,
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
        contract_quarantines=contract_quarantines,
        contract_quarantine_count=contract_quarantine_count,
        contract_failures=contract_failures,
        contract_failure_count=contract_failure_count,
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
    parser.add_argument("--output-dir", default=None,
                        help=("Output directory for DB + blobs + manifest. "
                              "If omitted, defaults to legacy 'final_db_output/' "
                              "with a warning — production builds should pass "
                              "an explicit --output-dir (rebuild_dashboard_snapshot.sh "
                              "writes to /tmp)."))
    parser.add_argument("--strict", action="store_true",
                        help="Fail build if any enriched/scored mismatch (production mode)")
    args = parser.parse_args()

    # 2026-05-14 — emit a loud warning when the legacy default is used.
    # The production flow (rebuild_dashboard_snapshot.sh) always passes
    # --output-dir explicitly. A bare invocation without --output-dir is
    # almost always a dev running build_final_db.py directly, and the
    # legacy scripts/final_db_output/ path has been a recurring source of
    # stale-data footguns. Warning visibility prevents the foot-shoot.
    if args.output_dir is None:
        args.output_dir = "final_db_output"
        # ANSI yellow for terminal visibility; same style as batch_run_all_datasets.sh.
        print(
            "\033[1;33m"
            "[build_final_db] WARNING: No --output-dir passed; using legacy "
            "default 'final_db_output/'. Production builds use "
            "rebuild_dashboard_snapshot.sh (which stages to /tmp and then to "
            "scripts/dist). Pass --output-dir explicitly to silence this warning."
            "\033[0m",
            file=sys.stderr,
        )

    script_dir = str(Path(__file__).parent)
    result = build_final_db(
        args.enriched_dir, args.scored_dir, args.output_dir, script_dir,
        strict=args.strict,
    )

    print(f"\nDone. {result['product_count']} products, {result['error_count']} errors.")
    print(f"DB: {result['db_path']} ({result['db_size_mb']} MB)")


if __name__ == "__main__":
    main()
