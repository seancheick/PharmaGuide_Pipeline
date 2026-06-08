"""PharmaGuide public six-pillar Quality Score — decision score assembler.

The public consumer score, separate from the raw v4 audit/math score. Six pillars:
formulation/20, dose/20, evidence/20, transparency/15, verification/15, safety_hygiene/10.

Current state: the public score is assembled from category-aware pillar adapters,
not a post-hoc display stretch. Formulation, dose, and evidence normalize against
archetype-specific achievable ceilings; verification uses hard quality signals with
a soft-signal cap; transparency remains a faithful source-dimension map because it
does not have the same structural ceiling problem.

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


def _manuf_violation_split(module_bd: Dict[str, Any]) -> Dict[str, float]:
    """PR3: route a maker's violation deduction into ONE pillar by type.

    The raw ``manufacturer_violations`` deduction lives in the raw score but in NO
    pillar, so the public quality score is currently BLIND to maker violations (a
    product with an FDA violation scores identical to a clean one). Split it:
      - Class I / critical recall in 3y (``class_i_count_3y`` > 0) = safety/contamination
        → the SAFETY pillar absorbs the deduction.
      - otherwise (GMP / labeling / quality-system) → the VERIFICATION pillar.
    Magnitude = the raw deduction itself (same /100 scale), so nothing is invented.
    B1 (harmful additive) and B7 (overdose) are NOT here — they already lower the
    formulation/dose pillars (single-count)."""
    mv = module_bd.get("manufacturer_violations") or {}
    score = _num(mv.get("score"))  # negative deduction or 0
    if score >= 0:
        return {"safety": 0.0, "verification": 0.0}
    penalty = abs(score)
    class_i = _num((mv.get("metadata") or {}).get("class_i_count_3y"))
    if class_i > 0:
        return {"safety": penalty, "verification": 0.0}
    return {"safety": 0.0, "verification": penalty}


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


def _clean_label_penalty(hits: Any, cfg: Dict[str, Any]) -> tuple[float, List[Dict[str, Any]]]:
    """Graduated clean-label additive penalty + per-hit enrichment.

    penalty = penalty_base (per-additive, from the entry's clean_label.penalty_base;
    falls back to config tier_base) × role_multiplier[role]. Summed across flagged
    additives and clamped to the per-product cap. Pure function of the gate's
    clean_label_hits + config. Returns (total_penalty, enriched_hits) where each
    enriched hit carries `penalty_applied` (its own pre-cap contribution) for the flag.

    Magnitudes are config-driven (clean_label_subscale) and PENDING user/advisor
    sign-off (spec §7). The raw shadow score is never touched by this.
    """
    sub = cfg.get("clean_label_subscale") or {}
    if not sub or not isinstance(hits, list) or not hits:
        return 0.0, []
    role_mult = sub.get("role_multiplier") or {}
    tier_base = sub.get("tier_base") or {}
    cap = _num(sub.get("max_total_penalty"))
    enriched: List[Dict[str, Any]] = []
    running = 0.0
    for h in hits:
        if not isinstance(h, dict):
            continue
        base = h.get("penalty_base")
        if base is None:
            base = tier_base.get(str(h.get("tier") or "").lower())
        mult = role_mult.get(str(h.get("role") or "").lower())
        if mult is None:
            mult = 0.5  # conservative default for an unmapped role
        pen = round(_num(base) * _num(mult), 1)
        enriched.append({**h, "penalty_applied": pen})
        running += pen
    total = round(min(running, cap) if cap else running, 1)
    return total, enriched


def _build_clean_label_flags(enriched_hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Public Flutter-facing clean_label_flags_v4 (the 'inform' half). All fields are
    data-sourced from the resolved entry — no invented status strings."""
    flags: List[Dict[str, Any]] = []
    for h in enriched_hits:
        flags.append({
            "additive": h.get("name"),
            "standard_name": h.get("standard_name"),
            "role": h.get("role"),
            "tier": h.get("tier"),
            "consumer_note": h.get("consumer_note"),
            "status": h.get("status"),
            "penalty_applied": h.get("penalty_applied"),
            "matched_rule_id": h.get("matched_rule_id"),
            # Step 3b: clickable regulation citation (null when the entry has none).
            # Stable keys so Flutter can rely on the contract.
            "eu_status": h.get("eu_status"),
            "regulation_citation": h.get("regulation_citation"),
            "regulation_url": h.get("regulation_url"),
        })
    return flags


def _pillar_safety_hygiene(module_bd: Dict[str, Any], weight: float,
                           cfg: Dict[str, Any],
                           clean_label_penalty: float = 0.0) -> Dict[str, Any]:
    """Product-level safety pillar (/10). Clean base (no banned/recalled/watchlist) maps
    to full credit; banned/recalled/watchlist present already zeroes the raw base. PR3:
    a Class I (critical) manufacturer recall deducts the raw violation magnitude here (the
    safety/contamination half of the violation split). Step 3a: a clean-label additive
    (titanium dioxide / E171) deducts a SMALL graduated penalty here (inform + penalize,
    no forced CAUTION). B1 harmful additive and B7 overdose are intentionally absent —
    they already lower the formulation/dose pillars, so re-deducting would double-count."""
    base = module_bd.get("safety_hygiene_base") or {}
    bscore = _num(base.get("score"))
    bmax = _num(base.get("max"))
    clean = round((bscore / bmax) * weight, 1) if bmax else 0.0
    clean = max(0.0, min(float(weight), clean))
    safety_pen = _manuf_violation_split(module_bd)["safety"]
    cl_pen = max(0.0, _num(clean_label_penalty))
    val = round(max(0.0, min(float(weight), clean - safety_pen - cl_pen)), 1)
    deductions = []
    if safety_pen > 0:
        deductions.append(f"Class I recall {_g(safety_pen)}")
    if cl_pen > 0:
        deductions.append(f"clean-label additive {_g(cl_pen)}")
    if deductions:
        reason = (f"Safety {_g(val)}/{_g(weight)} — clean base {_g(clean)} "
                  f"− {', '.join(deductions)}")
    elif bscore <= 0:
        reason = f"Safety {_g(val)}/{_g(weight)} — banned/recalled/watchlist signal present"
    else:
        reason = f"Safety {_g(val)}/{_g(weight)} — no banned/recalled/watchlist, no safety recall"
    components = {"clean_base": clean, "class_i_recall_penalty": safety_pen}
    if cl_pen > 0:
        components["clean_label_penalty"] = cl_pen
    return {
        "score": val,
        "max": weight,
        "reason": reason,
        "components": components,
    }


def _archetype(module: Optional[str], module_bd: Dict[str, Any]) -> str:
    if module == "sports":
        return "sports_single"
    if module == "omega":
        return "omega"
    if module == "probiotic":
        return "probiotic"
    if module == "multi_or_prenatal":
        return "prenatal_multi"
    form = (module_bd.get("dimensions", {}) or {}).get("formulation") or {}
    meta = form.get("metadata") or {}
    if meta.get("botanical_profile_applied") or meta.get("collagen_profile_applied"):
        return "generic_botanical_branded"
    return "generic_single_molecule"


def _pillar_formulation(dim: Dict[str, Any], weight: float, archetype: str,
                        cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Category-aware purpose-fit formulation. Normalize to the archetype's ACHIEVABLE
    form ceiling (single ingredients can't earn breadth components A2-A5), so a
    best-in-class form earns ~19-20 by being optimal, not by faking breadth. A cheap
    form (low raw formulation) still scores low — this discriminates within the
    archetype, it does not anchor on corpus best-in-class."""
    sub = cfg["formulation_subscale"]
    ref = sub["archetype_reference"].get(archetype, sub["default_reference"])
    score = _num(dim.get("score"))
    val = round(max(0.0, min(float(weight), (score / ref) * weight)), 1) if ref else 0.0
    return {
        "score": val,
        "max": weight,
        "reason": f"Purpose-fit formulation {_g(score)}/{_g(ref)} for "
                  f"{archetype.replace('_', ' ')} (archetype form ceiling, not breadth-30 "
                  f"→ {_g(val)}/{_g(weight)})",
        "components": {"raw_formulation": score, "archetype": archetype, "reference": ref},
    }


def _pillar_evidence(dim: Dict[str, Any], weight: float, archetype: str,
                     cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Category-aware evidence fit. The branded-RCT/consensus floor caps a single
    ingredient at 18 (reserving 19-20 for multi-active breadth); the spec forbids
    capping single-ingredient evidence. Normalize single-purpose archetypes to a 19
    ceiling so a strong branded/consensus single earns ~19 by HAVING the evidence. A
    weak-evidence single (low raw) still scores low — focused != automatically high."""
    sub = cfg["evidence_subscale"]
    ref = sub["archetype_reference"].get(archetype, sub["default_reference"])
    score = _num(dim.get("score"))
    val = round(max(0.0, min(float(weight), (score / ref) * weight)), 1) if ref else 0.0
    return {
        "score": val,
        "max": weight,
        "reason": f"Evidence fit {_g(score)}/{_g(ref)} for {archetype.replace('_', ' ')} "
                  f"(single-ingredient evidence not capped → {_g(val)}/{_g(weight)})",
        "components": {"raw_evidence": score, "archetype": archetype, "reference": ref},
    }


def _pillar_dose(dim: Dict[str, Any], weight: float, archetype: str,
                 cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Category-aware purpose-fit dose. Normalize to the archetype's APPROPRIATE-dose
    ceiling (a single nutrient/botanical in its clinical window caps ~22; the top 3 is
    multi-form/completion). Megadose-safe: an overdosed product already has low raw
    dose (overdose half-credit), a sub-clinical one is proportional-low — normalizing
    only lifts appropriately-dosed products, never rewards excess."""
    sub = cfg["dose_subscale"]
    ref = sub["archetype_reference"].get(archetype, sub["default_reference"])
    score = _num(dim.get("score"))
    val = round(max(0.0, min(float(weight), (score / ref) * weight)), 1) if ref else 0.0
    return {
        "score": val,
        "max": weight,
        "reason": f"Dose adequacy {_g(score)}/{_g(ref)} for {archetype.replace('_', ' ')} "
                  f"(appropriate-dose ceiling, no megadose reward → {_g(val)}/{_g(weight)})",
        "components": {"raw_dose": score, "archetype": archetype, "reference": ref},
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

    # PR3: a quality-system (non-critical) manufacturer violation lowers verification.
    # Applied AFTER the positive cert logic + clamp so it composes with future baseline
    # changes (PR2.1) as an independent negative term.
    qs_pen = _manuf_violation_split(module_bd)["verification"]
    positive = min(cap, total)
    val = round(max(0.0, positive - qs_pen), 1)
    if qs_pen > 0:
        reason += f"; − quality-system violation {qs_pen:g}"
    return {
        "score": val,
        "max": weight,
        "reason": reason,
        "components": {"cert": cert, "coa_batch": coa_batch, "gmp": gmp,
                       "brand_testing": testing, "soft": soft, "fail_open_neutral": fail_open,
                       "quality_system_violation_penalty": qs_pen},
    }


def _build_pillars(module_bd: Dict[str, Any], cfg: Dict[str, Any],
                   module: Optional[str],
                   clean_label_penalty: float = 0.0) -> Dict[str, Any]:
    dims = module_bd.get("dimensions") or {}
    archetype = _archetype(module, module_bd)
    pillars: Dict[str, Any] = {}
    for name, spec in cfg["pillars"].items():
        weight = spec["weight"]
        assembler = spec.get("assembler")
        if assembler == "verification":
            pillars[name] = _pillar_verification(module_bd, weight, cfg)
        elif assembler == "safety_hygiene":
            pillars[name] = _pillar_safety_hygiene(module_bd, weight, cfg,
                                                   clean_label_penalty)
        elif assembler == "formulation":
            pillars[name] = _pillar_formulation(dims.get("formulation") or {},
                                                weight, archetype, cfg)
        elif assembler == "dose":
            pillars[name] = _pillar_dose(dims.get("dose") or {}, weight, archetype, cfg)
        elif assembler == "evidence":
            pillars[name] = _pillar_evidence(dims.get("evidence") or {}, weight, archetype, cfg)
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
    module = shadow.get("shadow_score_v4_module")
    breakdown = shadow.get("shadow_score_v4_breakdown") or {}
    module_bd = breakdown.get("module") or {}
    supp = cfg["suppression"]
    blocking_reason = (breakdown.get("safety_gate") or {}).get("blocking_reason")

    # Public-contract aliases / provenance (always emitted)
    shadow["raw_score_v4_100"] = raw
    shadow["quality_score_version"] = cfg["_metadata"]["version"]
    # Clean-label additive flags (titanium dioxide / E171). Emit the consumer
    # "inform" flag for every status, including BLOCKED/UNSAFE suppressed rows;
    # the numeric penalty only applies on the scored path below.
    clean_label_hits = (breakdown.get("safety_gate") or {}).get("clean_label_hits") or []
    cl_penalty, cl_enriched = _clean_label_penalty(clean_label_hits, cfg)
    shadow["clean_label_flags_v4"] = _build_clean_label_flags(cl_enriched) or None

    # Hard safety failure FIRST (BLOCKED/UNSAFE have raw=None but are NOT "not_scored").
    # Suppress the public number; keep pillars if a breakdown exists (audit trail).
    if verdict in supp["suppressed_safety_verdicts"]:
        shadow["quality_score_v4_100"] = None
        shadow["quality_pillars_v4"] = _build_pillars(module_bd, cfg, module) if module_bd.get("dimensions") else None
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

    pillars = _build_pillars(module_bd, cfg, module, clean_label_penalty=cl_penalty)
    total = max(0.0, min(100.0, round(sum(p["score"] for p in pillars.values()), 1)))

    # Scored (SAFE / CAUTION — CAUTION keeps the score, verdict stays prominent elsewhere)
    shadow["quality_score_v4_100"] = total
    shadow["quality_pillars_v4"] = pillars
    shadow["quality_tier"] = _tier(total)
    shadow["quality_score_status"] = "scored"
    shadow["quality_score_suppressed_reason"] = None
    return shadow
