"""v4 Omega Trust dimension — P1.6.4.

Scores omega-3 Testing & Trust against the 15-point rubric in
omega_rubric.json:

    b4a_certifications  /10   IFOS / NSF / USP / Informed at sku or
                              curated product_line scope get full credit.
                              Product-label/rules-db quality claims get small
                              provisional credit. needs_review, brand_only,
                              claimed_only, rejected stay 0. No diminishing
                              returns — total caps at 10.
    b4b_gmp             /4    Audited GMP only (scoring_v4.cert_evidence):
                              a verified sku/product_line cert whose program
                              audits GMP, or an exact manufacturer facility
                              record = 4. Label NSF GMP marks, FDA facility
                              registration and self-attested GMP = 0.
    b4c_traceability    /1    1 point when has_coa OR has_batch_lookup
                              (the P1.8 nested QR-code rollup is honored).

  Hard-clamped at dimension_cap = 15.

The brand-level IFOS / manufacturer-cert signals go to Manufacturer Trust D1
(P1.6.6), NOT this dimension. Sustainability programs such as Friend of the
Sea / MSC stay in formulation sustainability, not purity/testing trust.

Per §13 architecture lock — no v3 imports.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from scoring_v4.cert_evidence import (
    audited_gmp_evidence,
    cert_entry_brand_matches_product,
    verified_cert_entries,
)
from scoring_v4.modules.brand_testing_posture import score_brand_testing_posture


PHASE_MARKER = "P1.6.4_omega_trust"
from scoring_v4.quality_score_config import block as _cfg_block

_VM = _cfg_block("verification_magnitudes", "omega_trust")["omega_trust"]


CAP_TRUST = _VM["cap_trust"]

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

    for entry in verified_cert_entries(product):
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
        if scope in {"sku", "product_line"} and not cert_entry_brand_matches_product(product, entry):
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
    """Score B4b GMP from the one audited-GMP decision
    (scoring_v4.cert_evidence.audited_gmp_evidence), shared with generic trust,
    the Verification pillar and the app's GMP badge.

    A label NSF GMP mark, FDA facility registration and self-attested GMP
    wording are recorded for audit and never scored.
    """
    points = float(cfg.get("audited_gmp", 4) or 4)
    cap = float(cfg.get("cap", 4) or 4)
    audited = audited_gmp_evidence(product)
    if audited:
        return min(points, cap), {
            "gmp_basis": audited["basis"], "gmp_evidence": audited["detail"], "raw": points}
    gmp = _safe_dict(_safe_dict(product.get("certification_data")).get("gmp"))
    return 0.0, {
        "gmp_basis": None,
        "raw": 0.0,
        "label_gmp_wording_not_scored": str(gmp.get("text_matched") or "").strip() or None,
    }


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
