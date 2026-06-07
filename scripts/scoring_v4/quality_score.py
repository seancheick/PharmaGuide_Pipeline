"""PharmaGuide public six-pillar Quality Score — decision score assembler.

The public consumer score, separate from the raw v4 audit/math score. Six pillars:
formulation/20, dose/20, evidence/20, transparency/15, verification/15, safety_hygiene/10.

PHASE 1 (this scaffold): each pillar is a LINEAR remap of the corresponding existing v4
module dimension/bonus into the new frame. This is deliberately faithful to current
signals so the side-by-side number ships immediately AND the structural bias (e.g.
single-ingredient products reading low on a breadth-dependent formulation dim) is visible
as a diagnostic. Category-aware pillar adapters that let a category's best-in-class EARN
the 90s land in later PRs.

INVARIANTS:
- ``raw_score_v4_100`` (== existing ``shadow_score_v4_100``) is NEVER changed.
- BLOCKED / UNSAFE suppress the public quality score (show verdict + reasons instead).
- NOT_SCORED / null raw → ``not_scored`` status, null score.
- Every pillar carries a one-line human-readable reason (white box, no black box).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "quality_score.json"
_CONFIG_CACHE: Optional[Dict[str, Any]] = None


def _config() -> Dict[str, Any]:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        _CONFIG_CACHE = json.loads(_CONFIG_PATH.read_text())
    return copy.deepcopy(_CONFIG_CACHE)


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _g(value: float) -> str:
    return f"{value:g}"


def _tier(score: float) -> str:
    bands = _config()["tiers"]  # ordered high→low min
    for band in bands:
        if score >= band["min"]:
            return band["name"]
    return bands[-1]["name"]


def _pillar_from_dim(name: str, dim: Dict[str, Any], weight: float, src: str) -> Dict[str, Any]:
    score = _num(dim.get("score"))
    mx = _num(dim.get("max"))
    val = round((score / mx) * weight, 1) if mx else 0.0
    val = max(0.0, min(float(weight), val))
    return {
        "score": val,
        "max": weight,
        "reason": f"{name.replace('_', ' ').title()} {_g(score)}/{_g(mx)} "
                  f"(Phase-1 linear map → {_g(val)}/{_g(weight)})",
        "components": {"source_dim": src, "raw_score": score, "raw_max": mx},
    }


def _pillar_from_bonuses(name: str, module_bd: Dict[str, Any],
                         sources: List[str], weight: float) -> Dict[str, Any]:
    total_score = 0.0
    total_max = 0.0
    parts: Dict[str, float] = {}
    for key in sources:
        b = module_bd.get(key) or {}
        total_score += _num(b.get("score"))
        total_max += _num(b.get("max"))
        parts[key] = _num(b.get("score"))
    val = round((total_score / total_max) * weight, 1) if total_max else 0.0
    val = max(0.0, min(float(weight), val))
    return {
        "score": val,
        "max": weight,
        "reason": f"{name.replace('_', ' ').title()} {_g(total_score)}/{_g(total_max)} "
                  f"from {'+'.join(sources)} (Phase-1 → {_g(val)}/{_g(weight)})",
        "components": parts,
    }


def _pillar_verification(module_bd: Dict[str, Any], weight: float,
                         cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Verification / quality pillar (/15). Hard third-party signals SATURATE the
    cap (over-provisioned, clamps) so a subset maxes it. Self-asserted cGMP is table
    stakes. FAIL OPEN: no cert AND no COA = data-unknown → neutral baseline (not 0),
    so the ~62% of the catalog we lack cert data on is not cratered. Soft reputation/
    region capped; physician/sustainability/prestige dropped."""
    sub = cfg["verification_subscale"]
    cap = sub["cap"]
    vb = (module_bd.get("verification_bonus") or {}).get("components") or {}
    mt = (module_bd.get("manufacturer_trust") or {}).get("components") or {}
    b4a = _num(vb.get("B4a_verified_certifications"))
    b4b = _num(vb.get("B4b_gmp"))
    b4c = _num(vb.get("B4c_batch_traceability"))
    b4d = _num(vb.get("B4d_brand_testing_posture"))

    cert = 0.0
    for tier in sub["cert_tiers"]:  # ordered high→low
        if b4a >= tier["min_b4a"]:
            cert = tier["points"]
            break
    coa_batch = round(min(sub["coa_batch_max"], (b4c / 2.0) * sub["coa_batch_max"]), 2) if b4c else 0.0
    gmp = (sub["gmp_certified_points"] if b4b >= 4.0
           else sub["gmp_registered_points"] if b4b >= 2.0 else 0.0)
    testing = sub["brand_testing_points"] if b4d > 0 else 0.0
    hard = cert + coa_batch + gmp + testing
    # soft: only reputation + region, capped; physician/sustainability/disclosure excluded
    soft = min(sub["soft_cap"],
               _num(mt.get("D1_manufacturer_reputation")) + _num(mt.get("D4_high_standard_region")))

    has_third_party_signal = (b4a > 0) or (b4c > 0)
    if has_third_party_signal:
        total = hard + soft
        reason = (f"Verification {round(min(cap, total), 1):g}/15 — third-party signals: "
                  f"cert {cert:g} + COA/batch {coa_batch:g} + GMP {gmp:g} + testing {testing:g}, "
                  f"soft {soft:g}")
        fail_open = False
    else:
        base = max(sub["neutral_baseline"], hard)
        total = base + soft
        reason = (f"Verification {round(min(cap, total), 1):g}/15 — no third-party cert/COA on file "
                  f"(data unknown → neutral baseline {sub['neutral_baseline']:g}), soft {soft:g}")
        fail_open = True

    val = round(max(0.0, min(cap, total)), 1)
    return {
        "score": val,
        "max": weight,
        "reason": reason,
        "components": {"cert": cert, "coa_batch": coa_batch, "gmp": gmp,
                       "brand_testing": testing, "soft": soft, "fail_open_neutral": fail_open},
    }


def _build_pillars(module_bd: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    dims = module_bd.get("dimensions") or {}
    pillars: Dict[str, Any] = {}
    for name, spec in cfg["pillars"].items():
        weight = spec["weight"]
        if spec.get("assembler") == "verification":
            pillars[name] = _pillar_verification(module_bd, weight, cfg)
        elif "source_dim" in spec:
            pillars[name] = _pillar_from_dim(name, dims.get(spec["source_dim"]) or {},
                                             weight, spec["source_dim"])
        else:
            pillars[name] = _pillar_from_bonuses(name, module_bd,
                                                 spec["source_bonuses"], weight)
    return pillars


def assemble_quality_score(shadow: Dict[str, Any]) -> Dict[str, Any]:
    """Add public six-pillar quality fields. Mutates & returns ``shadow``.
    ``shadow_score_v4_100`` (raw) is never modified."""
    cfg = _config()
    raw = shadow.get("shadow_score_v4_100")
    verdict = str(shadow.get("shadow_score_v4_verdict") or "")
    breakdown = shadow.get("shadow_score_v4_breakdown") or {}
    module_bd = breakdown.get("module") or {}
    supp = cfg["suppression"]
    blocking_reason = (breakdown.get("safety_gate") or {}).get("blocking_reason")

    # Public-contract aliases / provenance (always emitted)
    shadow["raw_score_v4_100"] = raw
    shadow["quality_score_version"] = cfg["_metadata"]["version"]

    # Hard safety failure FIRST (BLOCKED/UNSAFE have raw=None but are NOT "not_scored").
    # Suppress the public number; keep pillars if a breakdown exists (audit trail).
    if verdict in supp["suppressed_safety_verdicts"]:
        shadow["quality_score_v4_100"] = None
        shadow["quality_pillars_v4"] = _build_pillars(module_bd, cfg) if module_bd.get("dimensions") else None
        shadow["quality_tier"] = None
        shadow["quality_score_status"] = "suppressed_safety"
        shadow["quality_score_suppressed_reason"] = blocking_reason or verdict
        return shadow

    # NOT_SCORED / no usable score
    if raw is None or verdict in supp["not_scored_verdicts"]:
        shadow["quality_score_v4_100"] = None
        shadow["quality_pillars_v4"] = None
        shadow["quality_tier"] = None
        shadow["quality_score_status"] = "not_scored"
        shadow["quality_score_suppressed_reason"] = blocking_reason or (verdict or None)
        return shadow

    pillars = _build_pillars(module_bd, cfg)
    total = max(0.0, min(100.0, round(sum(p["score"] for p in pillars.values()), 1)))

    # Scored (SAFE / CAUTION — CAUTION keeps the score, verdict stays prominent elsewhere)
    shadow["quality_score_v4_100"] = total
    shadow["quality_pillars_v4"] = pillars
    shadow["quality_tier"] = _tier(total)
    shadow["quality_score_status"] = "scored"
    shadow["quality_score_suppressed_reason"] = None
    return shadow
