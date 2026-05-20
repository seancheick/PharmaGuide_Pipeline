"""v4 generic-module Testing & Trust dimension (P1.3.4).

Testing & Trust (15) contains the product/testing-facing B4 sub-lines:

    B4a verified certs           up to 12 (scope-aware diminishing returns)
    B4b GMP / facility quality   up to 4
    B4c batch traceability       COA + batch lookup signals

The dimension is hard-clamped at 15 across B4a + B4b + B4c. Brand-only
cert signals and manufacturer reputation belong to the separate
Manufacturer Trust slice (P1.3.6), not this dimension.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict

from scoring_v4.modules.generic_helpers import (
    _as_float,
    _norm_text,
    _safe_dict,
    get_active_ingredients,
)


PHASE_MARKER = "P1.3.4_testing_trust"

DIMENSION_CAP = 15.0
B4A_CAP = 12.0

B4A_SCOPE_POINTS = {
    "sku": [8.0, 4.0, 2.0],
    "product_line": [6.0, 3.0, 1.0],
    "label_asserted_product": [2.0, 1.0, 0.0],
    "brand_only": [0.0, 0.0, 0.0],
    "needs_review": [0.0, 0.0, 0.0],
    "claimed_only": [0.0, 0.0, 0.0],
}

B4A_SCOPE_STRENGTH = {
    "sku": 3,
    "product_line": 2,
    "label_asserted_product": 1,
}

LABEL_ASSERTED_WHITELIST = frozenset(
    {"usp verified", "informed choice", "informed sport", "bscg"}
)
LABEL_ASSERTED_OMEGA_ONLY_WHITELIST = frozenset({"ifos"})
MARINE_CERTS_FALLBACK = frozenset({"ifos", "friend of the sea", "msc", "goed"})

B4B_GMP_CERTIFIED = 4.0
B4B_FDA_REGISTERED = 2.0
B4C_COA = 1.0
B4C_BATCH_LOOKUP = 1.0


def score_trust(product: Dict[str, Any]) -> Dict[str, Any]:
    """Compute generic Testing & Trust."""
    if not isinstance(product, dict):
        product = {}

    b4a, cert_metadata = _score_b4a(product)
    b4b = _score_b4b(product)
    b4c = _score_b4c(product)

    components = {
        "B4a_verified_certifications": round(b4a, 4),
        "B4b_gmp": round(b4b, 4),
        "B4c_batch_traceability": round(b4c, 4),
    }
    raw_total = sum(components.values())
    score = _clamp(0.0, DIMENSION_CAP, raw_total)

    metadata = {
        "phase": PHASE_MARKER,
        "raw_testing_trust": round(raw_total, 4),
        "cap_applied": raw_total > DIMENSION_CAP,
        **cert_metadata,
    }

    return {
        "score": round(score, 4),
        "max": DIMENSION_CAP,
        "components": components,
        "penalties": {},
        "phase": PHASE_MARKER,
        "metadata": metadata,
    }


def _score_b4a(product: Dict[str, Any]) -> tuple[float, Dict[str, Any]]:
    verified = product.get("verified_cert_programs")
    cert = _safe_dict(product.get("certification_data"))
    if verified is None:
        verified = cert.get("verified_cert_programs")
    if not isinstance(verified, list):
        verified = []

    marine_tokens = _get_marine_cert_tokens()
    omega_like = _is_omega_like(product)
    best_scope_by_program: Dict[str, str] = {}

    for entry in verified:
        if not isinstance(entry, dict):
            continue
        scope = entry.get("scope") or ""
        if scope not in ("sku", "product_line", "label_asserted_product"):
            continue
        if entry.get("scoring_blocked_reason"):
            continue
        program = _norm_text(entry.get("program") or "")
        if not program:
            continue

        if scope == "label_asserted_product":
            if entry.get("evidence_source") != "product_label":
                continue
            in_main_whitelist = program in LABEL_ASSERTED_WHITELIST
            in_omega_whitelist = (
                program in LABEL_ASSERTED_OMEGA_ONLY_WHITELIST and omega_like
            )
            if not (in_main_whitelist or in_omega_whitelist):
                continue

        if any(token in program for token in marine_tokens) and not omega_like:
            continue

        existing = best_scope_by_program.get(program)
        if existing is None or B4A_SCOPE_STRENGTH[scope] > B4A_SCOPE_STRENGTH[existing]:
            best_scope_by_program[program] = scope

    scope_counts: Dict[str, int] = defaultdict(int)
    for scope in best_scope_by_program.values():
        scope_counts[scope] += 1

    raw = 0.0
    for scope in ("sku", "product_line", "label_asserted_product"):
        rungs = B4A_SCOPE_POINTS[scope]
        for idx in range(min(scope_counts[scope], len(rungs))):
            raw += rungs[idx]

    score = _clamp(0.0, B4A_CAP, raw)
    metadata = {
        "B4a_raw": round(raw, 4),
        "verified_programs_scored": sorted(best_scope_by_program.keys()),
        "verified_scope_counts": {
            key: value for key, value in sorted(scope_counts.items()) if value > 0
        },
    }
    return score, metadata


def _score_b4b(product: Dict[str, Any]) -> float:
    cert = _safe_dict(product.get("certification_data"))
    gmp = _safe_dict(cert.get("gmp"))
    gmp_level = _norm_text(product.get("gmp_level"))
    if gmp_level == "certified" or bool(
        gmp.get("nsf_gmp")
        or gmp.get("gmp_certified_or_compliant")
        or (gmp.get("claimed") and not gmp.get("fda_registered"))
    ):
        return B4B_GMP_CERTIFIED
    if gmp_level == "fda_registered" or bool(gmp.get("fda_registered")):
        return B4B_FDA_REGISTERED
    return 0.0


def _score_b4c(product: Dict[str, Any]) -> float:
    cert = _safe_dict(product.get("certification_data"))
    trace = _safe_dict(cert.get("batch_traceability"))
    has_coa = bool(product.get("has_coa", trace.get("has_coa", False)))
    has_lookup = bool(
        product.get(
            "has_batch_lookup",
            trace.get("has_batch_lookup", False) or trace.get("has_qr_code", False),
        )
    )
    return (B4C_COA if has_coa else 0.0) + (B4C_BATCH_LOOKUP if has_lookup else 0.0)


def _is_omega_like(product: Dict[str, Any]) -> bool:
    supp_payload = product.get("supplement_type")
    supp_type = ""
    if isinstance(supp_payload, dict):
        supp_type = _norm_text(supp_payload.get("type"))
    elif isinstance(supp_payload, str):
        supp_type = _norm_text(supp_payload)
    if supp_type == "specialty":
        return True

    for ing in get_active_ingredients(product):
        text = " ".join(
            _norm_text(ing.get(field))
            for field in ("name", "standard_name", "raw_source_text", "canonical_id")
        )
        if any(term in text for term in ("omega", "fish oil", "krill", "cod liver", "marine", "dha", "epa")):
            return True
    return False


_MARINE_CERT_TOKENS_CACHE: frozenset[str] | None = None


def _get_marine_cert_tokens() -> frozenset[str]:
    global _MARINE_CERT_TOKENS_CACHE
    if _MARINE_CERT_TOKENS_CACHE is not None:
        return _MARINE_CERT_TOKENS_CACHE

    tokens: set[str] = set()
    try:
        rules_path = Path(__file__).resolve().parents[2] / "data" / "cert_claim_rules.json"
        data = json.loads(rules_path.read_text()) if rules_path.exists() else {}
        programs = data.get("rules", {}).get("third_party_programs", {})
        if isinstance(programs, dict):
            for key, entry in programs.items():
                if key.startswith("_") or not isinstance(entry, dict):
                    continue
                if _norm_text(entry.get("product_scope")) != "marine":
                    continue
                display = _norm_text(entry.get("display_name"))
                if display:
                    tokens.add(display)
                key_norm = _norm_text(key.replace("_", " "))
                if key_norm:
                    tokens.add(key_norm)
    except Exception:
        tokens = set()

    if not tokens:
        tokens = set(MARINE_CERTS_FALLBACK)

    _MARINE_CERT_TOKENS_CACHE = frozenset(tokens)
    return _MARINE_CERT_TOKENS_CACHE


def _clamp(lo: float, hi: float, value: float) -> float:
    return max(lo, min(hi, value))
