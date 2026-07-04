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
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict

from scoring_v4.modules.generic_helpers import (
    _as_float,
    _norm_text,
    _safe_dict,
    _safe_list,
    get_active_ingredients,
)
from scoring_v4.modules.brand_testing_posture import (
    gmp_facility_evidence,
    score_brand_testing_posture,
)


_DHA_EPA_WORD_BOUNDARY_RE = re.compile(r"\b(epa|dha)\b", re.IGNORECASE)

PHASE_MARKER = "P1.3.4_testing_trust"

from scoring_v4.quality_score_config import block as _cfg_block

_VM = _cfg_block("verification_magnitudes", "generic_trust")["generic_trust"]


DIMENSION_CAP = _VM["dimension_cap"]
B4A_CAP = _VM["b4a_cap"]

B4A_SCOPE_POINTS = {k: list(v) for k, v in _VM["b4a_scope_points"].items()}

B4A_SCOPE_STRENGTH = dict(_VM["b4a_scope_strength"])

LABEL_ASSERTED_WHITELIST = frozenset(
    {
        "usp verified",
        "informed choice",
        "informed sport",
        "bscg",
        "bscg certified drug free",
        "nsf certified",
        "nsf contents certified",
        "nsf sport",
        "nsf certified for sport",
        "labdoor tested",
    }
)
LABEL_ASSERTED_OMEGA_ONLY_WHITELIST = frozenset({"ifos", "ifos certified"})
SUSTAINABILITY_ONLY_CERTS = frozenset(
    {"friend of the sea", "msc", "msc certified", "goed", "goed certified"}
)
MARINE_CERTS_FALLBACK = frozenset({"ifos", "friend of the sea", "msc", "goed"})

B4B_GMP_CERTIFIED = _VM["b4b_gmp_certified"]
B4B_FDA_REGISTERED = _VM["b4b_fda_registered"]
B4C_COA = _VM["b4c_coa"]
B4C_BATCH_LOOKUP = _VM["b4c_batch_lookup"]


def score_trust(product: Dict[str, Any]) -> Dict[str, Any]:
    """Compute generic Testing & Trust."""
    if not isinstance(product, dict):
        product = {}

    b4a, cert_metadata = _score_b4a(product)
    b4b, b4b_metadata = _score_b4b(product)
    b4c = _score_b4c(product)
    b4d, b4d_metadata = score_brand_testing_posture(product)

    components = {
        "B4a_verified_certifications": round(b4a, 4),
        "B4b_gmp": round(b4b, 4),
        "B4c_batch_traceability": round(b4c, 4),
        "B4d_brand_testing_posture": round(b4d, 4),
    }
    raw_total = sum(components.values())
    score = _clamp(0.0, DIMENSION_CAP, raw_total)

    metadata = {
        "phase": PHASE_MARKER,
        "raw_testing_trust": round(raw_total, 4),
        "cap_applied": raw_total > DIMENSION_CAP,
        **cert_metadata,
        **b4b_metadata,
        "B4d_source": b4d_metadata.get("source"),
        "B4d_manufacturer_id": b4d_metadata.get("manufacturer_id"),
        "B4d_matched_evidence": b4d_metadata.get("matched_evidence", []),
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
    unscored_scope_counts: Dict[str, int] = defaultdict(int)
    skipped_reasons: Dict[str, int] = defaultdict(int)
    brand_only_programs: set[str] = set()

    for entry in verified:
        if not isinstance(entry, dict):
            continue
        scope = entry.get("scope") or ""
        if scope not in ("sku", "product_line", "label_asserted_product"):
            if scope in ("brand_only", "needs_review", "claimed_only"):
                if entry.get("scoring_blocked_reason"):
                    continue
                program = _norm_text(entry.get("program") or "")
                if not program:
                    continue
                if any(token in program for token in marine_tokens) and not omega_like:
                    continue
                unscored_scope_counts[scope] += 1
                if scope == "brand_only":
                    brand_only_programs.add(program)
            continue
        if entry.get("scoring_blocked_reason"):
            skipped_reasons["scoring_blocked"] += 1
            continue
        program = _norm_text(entry.get("program") or "")
        if not program:
            continue

        if scope in ("sku", "product_line") and not _cert_entry_brand_matches_product(product, entry):
            skipped_reasons["brand_mismatch"] += 1
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

    for program in _label_asserted_quality_programs(product, omega_like):
        existing = best_scope_by_program.get(program)
        if (
            existing is None
            or B4A_SCOPE_STRENGTH["label_asserted_product"]
            > B4A_SCOPE_STRENGTH[existing]
        ):
            best_scope_by_program[program] = "label_asserted_product"

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
        "verified_unscored_scope_counts": {
            key: value
            for key, value in sorted(unscored_scope_counts.items())
            if value > 0
        },
        "verified_skipped_reasons": {
            key: value for key, value in sorted(skipped_reasons.items()) if value > 0
        },
        "verified_brand_only_programs": sorted(brand_only_programs),
    }
    return score, metadata


def _label_asserted_quality_programs(product: Dict[str, Any], omega_like: bool) -> list[str]:
    """Return rules-db/product-label quality programs eligible for small B4a.

    This fills the registry-incomplete gap: a product can have a score-eligible
    label/rules evidence row even when no live SKU registry row was loaded. It
    remains low-weight and never credits sustainability-only programs.
    """
    cert = _safe_dict(product.get("certification_data"))
    evidence = _safe_dict(cert.get("evidence_based"))
    programs: list[str] = []
    seen: set[str] = set()
    for entry in _safe_list(evidence.get("third_party_programs")):
        if not isinstance(entry, dict) or not entry.get("score_eligible"):
            continue
        display = _norm_text(entry.get("display_name") or entry.get("program") or "")
        rule_id = _norm_text(entry.get("rule_id") or "")
        program = display or rule_id
        if not program or not _is_label_asserted_quality_program(display, rule_id, omega_like):
            continue
        program = _label_asserted_program_key(display, rule_id)
        if program in seen:
            continue
        seen.add(program)
        programs.append(program)
    return programs


def _is_label_asserted_quality_program(display: str, rule_id: str, omega_like: bool) -> bool:
    haystack = f"{display} {rule_id}"
    if any(token in haystack for token in SUSTAINABILITY_ONLY_CERTS):
        return False
    if any(token in haystack for token in LABEL_ASSERTED_WHITELIST):
        return True
    return omega_like and any(
        token in haystack for token in LABEL_ASSERTED_OMEGA_ONLY_WHITELIST
    )


def _label_asserted_program_key(display: str, rule_id: str) -> str:
    haystack = f"{display} {rule_id}"
    if "ifos" in haystack:
        return "ifos"
    if "usp" in haystack:
        return "usp verified"
    if "informed choice" in haystack:
        return "informed choice"
    if "informed sport" in haystack:
        return "informed sport"
    if "bscg" in haystack:
        return "bscg"
    if "labdoor" in haystack:
        return "labdoor tested"
    if "nsf" in haystack and "sport" in haystack:
        return "nsf sport"
    if "nsf" in haystack:
        return "nsf certified"
    return display or rule_id


def _score_b4b(product: Dict[str, Any]) -> tuple[float, Dict[str, Any]]:
    """Score GMP / facility quality.

    Order of evidence (strongest first):
      1. Direct GMP signal (gmp_level=certified / nsf_gmp / compliant / claimed)
      2. cert→GMP implication: a VERIFIED sku/product_line cert whose program
         requires a GMP facility audit (NSF Sport/Contents, USP Verified,
         Informed Sport/Choice, BSCG — policy in cert_claim_rules.json). The
         cert is a stronger third-party signal than an empty gmp_level field,
         so we credit GMP from it rather than zeroing a product we KNOW is made
         under audited GMP. Conservative: brand_only/claimed_only/needs_review
         and stale/blocked rows never imply GMP.
      3. FDA-registered only (weakest).
    """
    cert = _safe_dict(product.get("certification_data"))
    gmp = _safe_dict(cert.get("gmp"))
    gmp_level = _norm_text(product.get("gmp_level"))
    if gmp_level == "certified" or bool(
        gmp.get("nsf_gmp")
        or gmp.get("gmp_certified_or_compliant")
        or (gmp.get("claimed") and not gmp.get("fda_registered"))
    ):
        return B4B_GMP_CERTIFIED, {}
    inferred = _gmp_implied_by_verified_cert(product)
    if inferred:
        return B4B_GMP_CERTIFIED, {"B4b_gmp_inferred_from_cert": inferred}
    # Facility-level GMP: exact-matched manufacturer evidence can fill B4b only
    # when the manufacturer corpus explicitly says GMP/cGMP/facility/manufacturing
    # quality. Product-only NSF/USP wording stays in B4a or product-cert→GMP.
    facility = gmp_facility_evidence(product)
    if facility:
        return B4B_GMP_CERTIFIED, {"B4b_gmp_inferred_from_manufacturer_facility": facility}
    if gmp_level == "fda_registered" or bool(gmp.get("fda_registered")):
        return B4B_FDA_REGISTERED, {}
    return 0.0, {}


def _gmp_implied_by_verified_cert(product: Dict[str, Any]) -> str | None:
    """Return the program name of a verified sku/product_line cert that implies
    GMP (per cert_claim_rules.json), or None. Mirrors B4a's verified-cert
    gating: scope must be sku/product_line and the row must not be blocked."""
    verified = product.get("verified_cert_programs")
    if verified is None:
        verified = _safe_dict(product.get("certification_data")).get("verified_cert_programs")
    if not isinstance(verified, list):
        return None
    gmp_programs = _get_gmp_implying_programs()
    for entry in verified:
        if not isinstance(entry, dict):
            continue
        if entry.get("scope") not in ("sku", "product_line"):
            continue
        if entry.get("scoring_blocked_reason"):
            continue
        if not _cert_entry_brand_matches_product(product, entry):
            continue
        if _norm_text(entry.get("program") or "") in gmp_programs:
            return entry.get("program")
    return None


def _cert_entry_brand_matches_product(product: Dict[str, Any], entry: Dict[str, Any]) -> bool:
    matched_brand = _brand_key(entry.get("matched_brand"))
    if not matched_brand:
        return True
    product_brand = _brand_key(
        product.get("brandName")
        or product.get("brand_name")
        or product.get("brand")
        or ""
    )
    if not product_brand:
        return True
    product_tokens = _brand_tokens(product_brand)
    matched_tokens = _brand_tokens(matched_brand)
    if not product_tokens or not matched_tokens:
        return False
    return product_tokens.issubset(matched_tokens) or matched_tokens.issubset(product_tokens)


def _brand_key(value: Any) -> str:
    text = str(value or "").lower().strip()
    text = re.sub(r"[®™©]", " ", text)
    text = re.sub(
        r"\b(inc|incorporated|llc|ltd|limited|corp|corporation|company|co|gmbh|holdings|group|brands|brand)\b",
        " ",
        text,
    )
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _brand_tokens(value: str) -> set[str]:
    return {token for token in value.split() if len(token) >= 2}


_GMP_IMPLYING_PROGRAMS_CACHE: frozenset[str] | None = None


def _get_gmp_implying_programs() -> frozenset[str]:
    """Normalized canonical program names whose certification requires a GMP
    facility audit. Loaded from cert_claim_rules.json (implies_gmp policy) so
    the rule is data-driven, not hardcoded in the scorer."""
    global _GMP_IMPLYING_PROGRAMS_CACHE
    if _GMP_IMPLYING_PROGRAMS_CACHE is not None:
        return _GMP_IMPLYING_PROGRAMS_CACHE

    tokens: set[str] = set()
    try:
        rules_path = Path(__file__).resolve().parents[2] / "data" / "cert_claim_rules.json"
        data = json.loads(rules_path.read_text()) if rules_path.exists() else {}
        programs = data.get("rules", {}).get("third_party_programs", {})
        if isinstance(programs, dict):
            for key, entry in programs.items():
                if key.startswith("_") or not isinstance(entry, dict):
                    continue
                policy = entry.get("implies_gmp")
                if not isinstance(policy, dict):
                    continue
                program = _norm_text(policy.get("verified_program"))
                if program:
                    tokens.add(program)
    except Exception:
        tokens = set()

    _GMP_IMPLYING_PROGRAMS_CACHE = frozenset(tokens)
    return _GMP_IMPLYING_PROGRAMS_CACHE


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
    """Return True when marine-cert programs are relevant to this product.

    Taxonomy `primary_type == omega_3` is the canonical current-batch signal.
    The ingredient-text fallback exists for old batches and for physical panel
    facts that should override stale taxonomy. It intentionally does not use
    `supplement_type == specialty`, and it does not treat the word "marine"
    alone as omega-like because marine collagen is not EPA/DHA fish oil.
    """
    if not isinstance(product, dict):
        return False

    direct = product.get("primary_type")
    if isinstance(direct, str) and _norm_text(direct) == "omega_3":
        return True

    taxonomy = product.get("supplement_taxonomy")
    if isinstance(taxonomy, dict):
        nested = taxonomy.get("primary_type")
        if isinstance(nested, str) and _norm_text(nested) == "omega_3":
            return True

    omega_terms = ("omega", "fish oil", "krill", "cod liver")
    for ing in get_active_ingredients(product):
        text = " ".join(
            _norm_text(ing.get(field))
            for field in ("name", "standard_name", "raw_source_text", "canonical_id")
        )
        if any(term in text for term in omega_terms):
            return True
        if _DHA_EPA_WORD_BOUNDARY_RE.search(text):
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
