"""PharmaGuide public six-pillar Quality Score — decision score assembler.

The public consumer score, separate from the raw v4 audit/math score. Six pillars:
formulation/20, dose/20, evidence/20, transparency/15, verification/15, safety_hygiene/10.

Current state: the public score is assembled from category-aware pillar adapters,
not a post-hoc display stretch. Formulation, dose, and evidence normalize against
archetype-specific achievable ceilings; verification uses hard quality signals with
a soft-signal cap; transparency remains a faithful source-dimension map because it
does not have the same structural ceiling problem.

INVARIANTS:
- ``raw_score_v4_100`` (== existing ``raw_score_v4_100``) is NEVER changed.
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


def _component_num(components: Dict[str, Any], *keys: str) -> float:
    for key in keys:
        if key in components:
            return _num(components.get(key))
    return 0.0


def _g(value: float) -> str:
    return f"{value:g}"


# ── Consumer-facing reason copy ──────────────────────────────────────────────
# The pillar ``reason`` strings ship to end users in the app's "How it scores"
# UI, so they must read as plain English a supplement shopper understands — no
# internal scoring vocabulary (archetype/breadth/phase names, raw fractions,
# arrows, module names). Each pillar maps its score → a short, honest sentence
# banded on how full the pillar is. The numeric score itself is unchanged and
# still shown separately; these strings only EXPLAIN it. When a pillar is low
# because the underlying signal is weak, the copy says so plainly (honesty over
# flattery — under-warning is the worse failure for a health product).

def _band(score: float, weight: float) -> str:
    """Coarse fullness band for a pillar's score → {high, mid, low}."""
    if weight <= 0:
        return "low"
    ratio = score / weight
    if ratio >= 0.8:
        return "high"
    if ratio >= 0.5:
        return "mid"
    return "low"


def _reason_formulation(band: str) -> str:
    return {
        "high": "Well-formulated — uses high-quality, well-absorbed ingredient forms.",
        "mid": "Uses reasonable ingredient forms, with room for more premium options.",
        "low": "Uses basic or low-cost ingredient forms.",
    }[band]


def _reason_dose(band: str) -> str:
    return {
        "high": "Doses land in the clinically studied range.",
        "mid": "Doses are reasonable but not fully in the studied range.",
        "low": "Doses fall short of the amounts shown to work.",
    }[band]


def _reason_evidence(band: str) -> str:
    return {
        "high": "Backed by strong human research.",
        "mid": "Some human research supports these ingredients.",
        "low": "Limited human evidence for these ingredients.",
    }[band]


def _reason_transparency(band: str) -> str:
    return {
        "high": "Fully transparent label — every amount is disclosed.",
        "mid": "Mostly transparent, but some amounts aren't fully disclosed.",
        "low": "Key amounts are hidden in a proprietary blend.",
    }[band]


# Generic dispatcher for any pillar that routes through the plain linear builders
# (only ``transparency`` does today). Keeps a jargon-free fallback so a future
# reconfigured pillar can never leak internal copy to consumers.
_BANDED_REASON = {
    "formulation": _reason_formulation,
    "dose": _reason_dose,
    "evidence": _reason_evidence,
    "transparency": _reason_transparency,
}


def _reason_generic(name: str, band: str) -> str:
    fn = _BANDED_REASON.get(name)
    if fn is not None:
        return fn(band)
    label = name.replace("_", " ")
    return {
        "high": f"Strong {label}.",
        "mid": f"Moderate {label}.",
        "low": f"Limited {label}.",
    }[band]


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
    B7 (overdose) is NOT here — it already lowers the dose pillar."""
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
        "reason": _reason_generic(name, _band(val, weight)),
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
        "reason": _reason_generic(name, _band(val, weight)),
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
    sign-off (spec §7). The raw v4 score is never touched by this.
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


def _formulation_additive_safety_penalty(module_bd: Dict[str, Any], cfg: Dict[str, Any]) -> float:
    """Small public Safety Hygiene deduction for additive/sweetener concerns.

    The underlying B1 formulation penalties remain the main scoring signal. This
    separate, capped deduction prevents the public Safety Hygiene pillar from
    claiming 10/10 when the product carries additive or glycemic-sweetener flags.
    """
    formulation = ((module_bd.get("dimensions") or {}).get("formulation") or {})
    penalties = formulation.get("penalties") or {}
    raw = 0.0
    for key in (
        "B1_harmful_additives",
        "B1_dietary_sugar",
        "B1_sleep_melatonin_gummy",
    ):
        value = _num(penalties.get(key))
        if value < 0:
            raw += abs(value)
    sub = cfg.get("safety_hygiene_subscale") or {}
    cap = _num(sub.get("additive_or_sweetener_max_penalty"), 4.0)
    return round(min(raw, cap), 1) if raw > 0 else 0.0


def _dose_safety_penalty(module_bd: Dict[str, Any], cfg: Dict[str, Any]) -> float:
    """Small public Safety Hygiene deduction for over-UL dose flags.

    The Dose pillar remains the main overdose penalty. This capped cross-pillar
    deduction only prevents Safety Hygiene from displaying 10/10 when the same
    product carries an explicit B7 dose-safety flag.
    """
    dose = ((module_bd.get("dimensions") or {}).get("dose") or {})
    penalties = dose.get("penalties") or {}
    raw = 0.0
    value = _num(penalties.get("B7_dose_safety"))
    if value < 0:
        raw += abs(value)
    sub = cfg.get("safety_hygiene_subscale") or {}
    cap = _num(sub.get("over_ul_max_penalty"), 3.0)
    return round(min(raw, cap), 1) if raw > 0 else 0.0


def _pillar_safety_hygiene(module_bd: Dict[str, Any], weight: float,
                           cfg: Dict[str, Any],
                           clean_label_penalty: float = 0.0) -> Dict[str, Any]:
    """Product-level safety pillar (/10). Clean base (no banned/recalled/watchlist) maps
    to full credit; banned/recalled/watchlist present already zeroes the raw base. PR3:
    a Class I (critical) manufacturer recall deducts the raw violation magnitude here (the
    safety/contamination half of the violation split). Step 3a: a clean-label additive
    (titanium dioxide / E171) deducts a SMALL graduated penalty here (inform + penalize,
    no forced CAUTION). B1 additive/sweetener concerns also deduct a capped public
    truthfulness penalty so the Safety Hygiene pillar cannot remain perfect when
    additive concerns are present. B7 overdose stays in dose only."""
    base = module_bd.get("safety_hygiene_base") or {}
    bscore = _num(base.get("score"))
    bmax = _num(base.get("max"))
    clean = round((bscore / bmax) * weight, 1) if bmax else 0.0
    clean = max(0.0, min(float(weight), clean))
    safety_pen = _manuf_violation_split(module_bd)["safety"]
    cl_pen = max(0.0, _num(clean_label_penalty))
    additive_pen = _formulation_additive_safety_penalty(module_bd, cfg)
    over_ul_pen = _dose_safety_penalty(module_bd, cfg)
    val = round(max(0.0, min(float(weight), clean - safety_pen - cl_pen - additive_pen - over_ul_pen)), 1)
    deductions = []
    if safety_pen > 0:
        deductions.append("the maker had a serious product recall")
    if cl_pen > 0:
        deductions.append("it contains a restricted additive")
    if additive_pen > 0:
        deductions.append("it contains additive or sweetener/form-factor concerns")
    if over_ul_pen > 0:
        deductions.append("one or more nutrients are above established upper limits")
    if deductions:
        # Plain-English join: "A and B" rather than a comma list.
        reason = "Safety concern: " + " and ".join(deductions) + "."
    elif bscore <= 0:
        reason = "Contains a banned, recalled, or watchlisted ingredient."
    else:
        reason = "No banned, recalled, or watchlisted ingredients."
    components = {"clean_base": clean, "class_i_recall_penalty": safety_pen}
    if cl_pen > 0:
        components["clean_label_penalty"] = cl_pen
    if additive_pen > 0:
        components["additive_or_sweetener_penalty"] = additive_pen
    if over_ul_pen > 0:
        components["over_ul_penalty"] = over_ul_pen
    return {
        "score": val,
        "max": weight,
        "reason": reason,
        "components": components,
    }


def _archetype(module: Optional[str], module_bd: Dict[str, Any]) -> str:
    if module == "sports":
        return "sports_single"
    if module == "fiber_digestive":
        return "fiber_digestive"
    if module == "omega":
        return "omega"
    if module == "probiotic":
        return "probiotic"
    if module == "multi_or_prenatal":
        return "prenatal_multi"
    form = (module_bd.get("dimensions", {}) or {}).get("formulation") or {}
    meta = form.get("metadata") or {}
    if (meta.get("immune_support") or {}).get("profile_applied"):
        return "immune_support"
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
        "reason": _reason_formulation(_band(val, weight)),
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
        "reason": _reason_evidence(_band(val, weight)),
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
        "reason": _reason_dose(_band(val, weight)),
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
    vb_payload = module_bd.get("verification_bonus") or {}
    vb = vb_payload.get("components") or {}
    trust_meta = ((vb_payload.get("metadata") or {}).get("trust_metadata") or {})
    mt = (module_bd.get("manufacturer_trust") or {}).get("components") or {}
    b4a = _component_num(vb, "B4a_verified_certifications", "b4a_verified_certifications")
    b4b = _component_num(vb, "B4b_gmp", "b4b_gmp")
    b4c = _component_num(vb, "B4c_batch_traceability", "b4c_batch_traceability")
    b4d = _component_num(vb, "B4d_brand_testing_posture", "b4d_brand_testing_posture")
    scored_scopes = _verification_scope_counts(trust_meta)
    has_registry_cert = (
        _num(scored_scopes.get("sku")) > 0
        or _num(scored_scopes.get("product_line")) > 0
    )
    has_label_asserted_cert = _num(scored_scopes.get("label_asserted_product")) > 0
    unscored_scopes = trust_meta.get("verified_unscored_scope_counts") or {}
    brand_only_count = int(_num(unscored_scopes.get("brand_only")))

    cert = 0.0
    if has_registry_cert:
        for tier in sub["cert_tiers"]:  # ordered high→low
            if b4a >= tier["min_b4a"]:
                cert = tier["points"]
                break
    elif has_label_asserted_cert:
        cert = _num(sub.get("label_asserted_cert_points"))
    coa_batch = round(min(sub["coa_batch_max"], (b4c / 2.0) * sub["coa_batch_max"]), 2) if b4c else 0.0
    gmp = (sub["gmp_certified_points"] if b4b >= 4.0
           else sub["gmp_registered_points"] if b4b >= 2.0 else 0.0)
    testing = sub["brand_testing_points"] if b4d > 0 else 0.0
    # PR2.1: a verified brand/facility scoped cert is a real third-party
    # verification signal, but weaker than sku/product_line certification and
    # not evidence for this SKU. It fills the unknown-data gap only; it does not
    # stack on top of product-level cert/COA and never changes raw B4a.
    brand_only_cert = (
        _num(sub.get("brand_only_cert_points"))
        if brand_only_count > 0 and b4a <= 0 and b4c <= 0
        else 0.0
    )
    hard = cert + coa_batch + gmp + testing + brand_only_cert
    # soft: only reputation + region, capped; physician/sustainability/disclosure excluded
    soft = min(sub["soft_cap"],
               _num(mt.get("D1_manufacturer_reputation")) + _num(mt.get("D4_high_standard_region")))

    has_product_third_party_signal = (b4a > 0) or (b4c > 0)
    has_third_party_signal = has_product_third_party_signal or (brand_only_cert > 0)
    if has_product_third_party_signal:
        total = hard + soft
        # Name the actual third-party signals present, in plain English. No raw
        # numbers — "neutral" is intentionally absent (this is the real-signal
        # path, not the unknown fail-open path).
        signals = []
        if cert > 0:
            if has_registry_cert:
                signals.append("third-party certified")
            elif has_label_asserted_cert:
                signals.append("label claims third-party certification")
        if coa_batch > 0:
            signals.append("publishes batch test results")
        if testing > 0:
            signals.append("does its own purity testing")
        if not signals and gmp > 0:
            signals.append("made in a GMP-registered facility")
        # "Independently verified" only when an independent party actually
        # verified the product (registry-matched cert or batch COA). A
        # label-asserted claim or self-run testing gets a neutral header —
        # the old prefix contradicted its own clause ("Independently
        # verified — label claims third-party certification").
        independently_verified = has_registry_cert or coa_batch > 0
        prefix = (
            "Independently verified — " if independently_verified
            else "Quality signals on file — "
        )
        if signals:
            reason = prefix + ", ".join(signals) + "."
        elif independently_verified:
            reason = "Independently verified for quality."
        else:
            reason = "Quality signals on file."
        fail_open = False
    elif brand_only_cert > 0:
        base = max(sub["neutral_baseline"], cert + coa_batch + gmp + testing)
        total = base + brand_only_cert + soft
        # Keep the literal "brand/facility cert" wording the contract relies on.
        reason = "Holds a brand/facility certification verified by a third party."
        fail_open = False
    else:
        base = max(sub["neutral_baseline"], hard)
        total = base + soft
        # Fail-open: no testing data on file. Say it's unknown, not that the
        # product failed — and make clear it isn't penalized for the gap.
        reason = "No third-party testing on file — treated as unknown, not penalized."
        fail_open = True

    # PR3: a quality-system (non-critical) manufacturer violation lowers verification.
    # Applied AFTER the positive cert logic + clamp so it composes with future baseline
    # changes (PR2.1) as an independent negative term.
    qs_pen = _manuf_violation_split(module_bd)["verification"]
    positive = min(cap, total)
    val = round(max(0.0, positive - qs_pen), 1)
    if qs_pen > 0:
        reason += " Maker has an open quality-system violation."
    return {
        "score": val,
        "max": weight,
        "reason": reason,
        "components": {"cert": cert, "coa_batch": coa_batch, "gmp": gmp,
                       "brand_testing": testing, "brand_only_cert": brand_only_cert,
                       "soft": soft, "fail_open_neutral": fail_open,
                       "quality_system_violation_penalty": qs_pen},
    }


def _verification_scope_counts(trust_meta: Dict[str, Any]) -> Dict[str, int]:
    """Return B4a scope counts across generic and omega trust metadata shapes."""
    direct = trust_meta.get("verified_scope_counts")
    if isinstance(direct, dict) and direct:
        return {str(key): int(_num(value)) for key, value in direct.items()}

    b4a = trust_meta.get("b4a")
    entries = (b4a or {}).get("B4a_scored_entries") if isinstance(b4a, dict) else None
    if not isinstance(entries, list):
        return {}

    counts: Dict[str, int] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        scope = str(entry.get("scope") or "")
        if not scope:
            continue
        counts[scope] = counts.get(scope, 0) + 1
    return counts


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


def assemble_quality_score(result: Dict[str, Any]) -> Dict[str, Any]:
    """Add public six-pillar quality fields. Mutates & returns ``result``.
    ``raw_score_v4_100`` (raw) is never modified."""
    cfg = _config()
    raw = result.get("raw_score_v4_100")
    verdict = str(result.get("v4_verdict") or "")
    module = result.get("v4_module")
    breakdown = result.get("v4_breakdown") or {}
    module_bd = breakdown.get("module") or {}
    supp = cfg["suppression"]
    blocking_reason = (breakdown.get("safety_gate") or {}).get("blocking_reason")

    # Public-contract aliases / provenance (always emitted)
    result["raw_score_v4_100"] = raw
    result["quality_score_version"] = cfg["_metadata"]["version"]
    # Clean-label additive flags (titanium dioxide / E171). Emit the consumer
    # "inform" flag for every status, including BLOCKED/UNSAFE suppressed rows;
    # the numeric penalty only applies on the scored path below.
    clean_label_hits = (breakdown.get("safety_gate") or {}).get("clean_label_hits") or []
    cl_penalty, cl_enriched = _clean_label_penalty(clean_label_hits, cfg)
    result["clean_label_flags_v4"] = _build_clean_label_flags(cl_enriched) or None

    # Hard safety failure FIRST (BLOCKED/UNSAFE have raw=None but are NOT "not_scored").
    # Suppress the public number; keep pillars if a breakdown exists (audit trail).
    if verdict in supp["suppressed_safety_verdicts"]:
        result["quality_score_v4_100"] = None
        result["quality_pillars_v4"] = _build_pillars(module_bd, cfg, module) if module_bd.get("dimensions") else None
        result["quality_tier"] = None
        result["quality_score_status"] = "suppressed_safety"
        result["quality_score_suppressed_reason"] = blocking_reason or verdict
        return result

    # NOT_SCORED / no usable score
    if raw is None or verdict in supp["not_scored_verdicts"]:
        result["quality_score_v4_100"] = None
        result["quality_pillars_v4"] = None
        result["quality_tier"] = None
        result["quality_score_status"] = "not_scored"
        result["quality_score_suppressed_reason"] = blocking_reason or (verdict or None)
        return result

    pillars = _build_pillars(module_bd, cfg, module, clean_label_penalty=cl_penalty)
    total = max(0.0, min(100.0, round(sum(p["score"] for p in pillars.values()), 1)))

    # Scored (SAFE / CAUTION — CAUTION keeps the score, verdict stays prominent elsewhere)
    result["quality_score_v4_100"] = total
    result["quality_pillars_v4"] = pillars
    result["quality_tier"] = _tier(total)
    result["quality_score_status"] = "scored"
    result["quality_score_suppressed_reason"] = None
    return result
