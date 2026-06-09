"""v4 Omega Trust dimension — P1.6.4.

Scores omega-3 Testing & Trust against the 15-point rubric in
omega_rubric.json:

    b4a_certifications  /10   IFOS / NSF / USP / Informed at sku or
                              curated product_line scope get full credit.
                              Product-label/rules-db quality claims get small
                              provisional credit. needs_review, brand_only,
                              claimed_only, rejected stay 0. No diminishing
                              returns — total caps at 10.
    b4b_gmp             /4    nsf_gmp (NSF/ANSI 173 audit) = 4.
                              Verified sku/product_line certs that imply GMP
                              per cert_claim_rules.json = 4. fda_registered
                              = 2. self-attested only = 0 (per P1.8 enricher
                              hardening — Codex caught the
                              laboratory-vs-facility false-positive).
    b4c_traceability    /1    1 point when has_coa OR has_batch_lookup
                              (the P1.8 nested QR-code rollup is honored).

  Hard-clamped at dimension_cap = 15.

The brand-level IFOS / manufacturer-cert signals go to Manufacturer Trust D1
(P1.6.6), NOT this dimension. Sustainability programs such as Friend of the
Sea / MSC stay in formulation sustainability, not purity/testing trust.

Per §13 architecture lock — no v3 imports.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from scoring_v4.modules.brand_testing_posture import (
    gmp_facility_evidence,
    score_brand_testing_posture,
)


REPO_ROOT = Path(__file__).resolve().parents[3]


PHASE_MARKER = "P1.6.4_omega_trust"
CAP_TRUST = 15.0

LABEL_ASSERTED_QUALITY_PROGRAMS = frozenset(
    {
        "ifos",
        "ifos certified",
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
SUSTAINABILITY_ONLY_PROGRAMS = frozenset(
    {"friend of the sea", "msc", "msc certified", "goed", "goed certified"}
)


def _load_rubric() -> Dict[str, Any]:
    from scoring_v4.config_registry import load_rubric
    return load_rubric("omega")  # Phase 0: shared registry (validated + fingerprinted)


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _get_verified_cert_programs(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Find verified_cert_programs at either top-level or under
    certification_data. The enricher normalizes both shapes."""
    direct = product.get("verified_cert_programs")
    if isinstance(direct, list):
        return [e for e in direct if isinstance(e, dict)]
    cert_data = _safe_dict(product.get("certification_data"))
    nested = cert_data.get("verified_cert_programs")
    if isinstance(nested, list):
        return [e for e in nested if isinstance(e, dict)]
    return []


def _score_b4a(
    product: Dict[str, Any],
    scope_policy: Dict[str, Any],
    cap: float,
) -> Tuple[float, Dict[str, Any]]:
    """Score B4a verified certifications under the omega module's
    verified-scopes-only policy.

    Per-entry: scope ∈ {sku, product_line} earns the policy value.
    Anything else (needs_review, brand_only, claimed_only, rejected,
    or missing) earns 0. Total caps at b4a_cap (10).

    Returns (score, audit_metadata).
    """
    scored_entries: List[Dict[str, Any]] = []
    skipped_entries: List[Dict[str, Any]] = []
    scored_programs: set[str] = set()
    raw = 0.0

    for entry in _get_verified_cert_programs(product):
        # Reject entries with a scoring-blocked reason (e.g. stale snapshot
        # from the resolver). Per generic_trust pattern.
        if entry.get("scoring_blocked_reason"):
            skipped_entries.append({
                "program": entry.get("program"),
                "scope": entry.get("scope"),
                "reason": entry.get("scoring_blocked_reason"),
            })
            continue
        scope = _norm(entry.get("scope"))
        if not scope:
            continue
        pts = float(scope_policy.get(scope, 0) or 0)
        if pts <= 0:
            skipped_entries.append({
                "program": entry.get("program"),
                "scope": scope,
                "reason": "scope_not_in_verified_set",
            })
            continue
        if scope in {"sku", "product_line"} and not _cert_entry_brand_matches_product(product, entry):
            skipped_entries.append({
                "program": entry.get("program"),
                "scope": scope,
                "reason": "brand_mismatch",
            })
            continue
        raw += pts
        scored_programs.add(_cert_program_key(_norm(entry.get("program")), ""))
        scored_entries.append({
            "program": entry.get("program"),
            "scope": scope,
            "pts": pts,
        })

    for program in _label_asserted_quality_programs(product):
        if program in scored_programs:
            continue
        pts = float(scope_policy.get("label_asserted_product", 0) or 0)
        if pts <= 0:
            skipped_entries.append({
                "program": program,
                "scope": "label_asserted_product",
                "reason": "scope_not_in_verified_set",
            })
            continue
        raw += pts
        scored_programs.add(program)
        scored_entries.append({
            "program": program,
            "scope": "label_asserted_product",
            "pts": pts,
        })

    score = max(0.0, min(cap, raw))
    metadata = {
        "B4a_raw": round(raw, 4),
        "B4a_cap_applied": raw > cap,
        "B4a_scored_entries": scored_entries,
        "B4a_skipped_entries": skipped_entries,
    }
    return score, metadata


def _label_asserted_quality_programs(product: Dict[str, Any]) -> List[str]:
    cert_data = _safe_dict(product.get("certification_data"))
    evidence = _safe_dict(cert_data.get("evidence_based"))
    programs: List[str] = []
    seen: set[str] = set()
    for entry in _safe_list(evidence.get("third_party_programs")):
        if not isinstance(entry, dict) or not entry.get("score_eligible"):
            continue
        display = _norm(entry.get("display_name") or entry.get("program") or "")
        rule_id = _norm(entry.get("rule_id") or "")
        program = _cert_program_key(display, rule_id)
        if not program:
            continue
        if not _is_label_asserted_quality_program(display, rule_id):
            continue
        if program in seen:
            continue
        seen.add(program)
        programs.append(program)
    return programs


def _is_label_asserted_quality_program(display: str, rule_id: str) -> bool:
    haystack = f"{display} {rule_id}"
    if any(program in haystack for program in SUSTAINABILITY_ONLY_PROGRAMS):
        return False
    return any(program in haystack for program in LABEL_ASSERTED_QUALITY_PROGRAMS)


def _cert_program_key(display: str, rule_id: str) -> str:
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


def _score_b4b(product: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    """Score B4b GMP under the omega-specific stricter policy:
      - nsf_gmp=True → 4 (NSF/ANSI 173 audit, real third-party verification)
      - verified sku/product_line cert with cert_claim_rules.implies_gmp → 4
      - fda_registered=True → 2 (registered facility, weaker signal)
      - self-attested only (gmp.claimed=True, no NSF/FDA backing) → 0

    This is STRICTER than generic_trust which credits gmp_level=certified.
    The omega module won't credit self-attested GMP. It will, however, credit
    GMP from a product-specific verified cert whose rules-db policy says the
    cert requires an audited GMP/facility process. Conservative:
    brand_only/claimed_only/needs_review and blocked rows never imply GMP.
    """
    nsf_gmp_pts = float(cfg.get("nsf_gmp", 4) or 4)
    fda_pts = float(cfg.get("fda_registered", 2) or 2)
    cap = float(cfg.get("cap", 4) or 4)

    cert_data = _safe_dict(product.get("certification_data"))
    gmp = _safe_dict(cert_data.get("gmp"))

    if bool(gmp.get("nsf_gmp")):
        return min(nsf_gmp_pts, cap), {"source": "nsf_gmp", "raw": nsf_gmp_pts}
    inferred = _gmp_implied_by_verified_cert(product)
    if inferred:
        return min(nsf_gmp_pts, cap), {
            "source": "verified_cert_implies_gmp",
            "program": inferred,
            "raw": nsf_gmp_pts,
        }
    # Facility-level GMP: exact-matched manufacturer evidence can fill B4b only
    # when the manufacturer corpus explicitly says GMP/cGMP/facility/manufacturing
    # quality. Product-only NSF/USP wording stays in B4a or product-cert→GMP.
    facility = gmp_facility_evidence(product)
    if facility:
        return min(nsf_gmp_pts, cap), {
            "source": "manufacturer_facility_gmp",
            "program": facility,
            "raw": nsf_gmp_pts,
        }
    if bool(gmp.get("fda_registered")):
        return min(fda_pts, cap), {"source": "fda_registered", "raw": fda_pts}
    return 0.0, {
        "source": None,
        "raw": 0.0,
        "self_attested_only_no_credit": bool(gmp.get("claimed")),
    }


def _gmp_implied_by_verified_cert(product: Dict[str, Any]) -> str | None:
    """Return the verified cert program that implies GMP, or None.

    Mirrors B4a's product-specific gate: only sku/product_line cert rows count,
    and rows blocked by the resolver never count. The program list is loaded
    from cert_claim_rules.json so the policy stays data-driven.
    """
    gmp_programs = _get_gmp_implying_programs()
    if not gmp_programs:
        return None

    for entry in _get_verified_cert_programs(product):
        if entry.get("scoring_blocked_reason"):
            continue
        scope = _norm(entry.get("scope"))
        if scope not in {"sku", "product_line"}:
            continue
        if not _cert_entry_brand_matches_product(product, entry):
            continue
        program = _norm(entry.get("program"))
        if program in gmp_programs:
            return entry.get("program") or program
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
    global _GMP_IMPLYING_PROGRAMS_CACHE
    if _GMP_IMPLYING_PROGRAMS_CACHE is not None:
        return _GMP_IMPLYING_PROGRAMS_CACHE

    tokens: set[str] = set()
    try:
        rules_path = REPO_ROOT / "scripts" / "data" / "cert_claim_rules.json"
        data = json.loads(rules_path.read_text()) if rules_path.exists() else {}
        programs = data.get("rules", {}).get("third_party_programs", {})
        if isinstance(programs, dict):
            for key, entry in programs.items():
                if key.startswith("_") or not isinstance(entry, dict):
                    continue
                policy = entry.get("implies_gmp")
                if not isinstance(policy, dict):
                    continue
                program = _norm(policy.get("verified_program"))
                if program:
                    tokens.add(program)
    except Exception:
        tokens = set()

    _GMP_IMPLYING_PROGRAMS_CACHE = frozenset(tokens)
    return _GMP_IMPLYING_PROGRAMS_CACHE


def _score_b4c(product: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    """Score B4c batch traceability. 1 point if has_coa OR has_batch_lookup.

    Honors the P1.8 nested QR-code rollup — `batch_traceability.has_qr_code`
    counts as batch_lookup since it links to lot-specific data.
    """
    score_if_present = float(cfg.get("score_if_present", 1) or 1)
    cap = float(cfg.get("cap", 1) or 1)

    cert_data = _safe_dict(product.get("certification_data"))
    bt = _safe_dict(cert_data.get("batch_traceability"))

    has_coa = bool(product.get("has_coa") or bt.get("has_coa"))
    has_batch = bool(
        product.get("has_batch_lookup")
        or bt.get("has_batch_lookup")
        or bt.get("has_qr_code")
    )

    if has_coa or has_batch:
        return min(score_if_present, cap), {
            "has_coa": has_coa,
            "has_batch_lookup": has_batch,
            "source": "has_coa" if has_coa else "has_batch_lookup",
        }
    return 0.0, {"has_coa": False, "has_batch_lookup": False}


def score_trust(product: Any) -> Dict[str, Any]:
    """Score omega-class Trust dimension."""
    if not isinstance(product, dict):
        product = {}

    rubric = _load_rubric()
    trust_cfg = rubric["trust"]
    scope_policy = _safe_dict(trust_cfg.get("b4a_scope_policy"))
    b4a_cap = float(trust_cfg.get("b4a_cap", 10) or 10)
    dim_cap = float(trust_cfg.get("dimension_cap", 15) or 15)

    b4a_score, b4a_meta = _score_b4a(product, scope_policy, b4a_cap)
    b4b_score, b4b_meta = _score_b4b(product, _safe_dict(trust_cfg.get("b4b_gmp")))
    b4c_score, b4c_meta = _score_b4c(product, _safe_dict(trust_cfg.get("b4c_traceability")))
    b4d_score, b4d_meta = score_brand_testing_posture(product)

    components: Dict[str, float] = {}
    if b4a_score > 0:
        components["b4a_verified_certifications"] = round(b4a_score, 2)
    if b4b_score > 0:
        components["b4b_gmp"] = round(b4b_score, 2)
    if b4c_score > 0:
        components["b4c_batch_traceability"] = round(b4c_score, 2)
    if b4d_score > 0:
        components["b4d_brand_testing_posture"] = round(b4d_score, 2)

    raw_score = b4a_score + b4b_score + b4c_score + b4d_score
    score = max(0.0, min(dim_cap, raw_score))

    metadata = {
        "phase": PHASE_MARKER,
        "raw_score": round(raw_score, 4),
        "cap_applied": raw_score > dim_cap,
        "b4a": b4a_meta,
        "b4b": b4b_meta,
        "b4c": b4c_meta,
        "b4d": b4d_meta,
    }

    return {
        "score": round(score, 2),
        "max": dim_cap,
        "components": components,
        "penalties": {},
        "metadata": metadata,
    }
