"""V4 display-layer calibration — archetype-anchored top-band normalization.

WHY: v4 raw dimension caps are structurally unreachable by an archetype's own
best-in-class (a single ingredient can't earn formulation 30 / evidence 20; a
probiotic/multi can't max dose-adequacy). So creatine-93 reads as "perfect for
type" while a premium multivitamin caps ~88 — cross-category-unfair for consumers.

WHAT: a DISPLAY-ONLY transform. ``raw_score_100`` (the audit/math score) is NEVER
changed. We add ``shadow_score_v4_display_100`` + a ``display_calibration``
provenance block. Each archetype has a FROZEN reference best-in-class raw ``R_a``
(curated constant, not a corpus percentile, so it doesn't drift). For a product
that passes ``top_band_eligibility``, the display score is lifted toward ~95 via a
conservative k=3 convex LIFT:

    display = raw + (target - R_a) * t**k ,  t = clamp((raw-80)/(R_a-80), 0, 1)

The lift form (added to raw) guarantees ``display >= raw`` — it never lowers a
score, and the 80-85 band moves only mildly. Clamped at a 96 ceiling (100 stays
reserved). Everything below raw 80, every non-SAFE verdict, and every poorly
disclosed / safety-flagged product is left at ``display = raw``.

The ``confidence`` band is intentionally NOT a gate — it is artifact-prone
(FloraSport 20B reports ``low`` despite evidence 20 + transparency 15). Genuine
low-data products already fail the evidence / transparency / dose gates here.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "display_calibration.json"
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


def _transform(
    raw: float,
    *,
    R_a: float,
    k: Optional[float] = None,
    floor: Optional[float] = None,
    target: Optional[float] = None,
    ceiling: Optional[float] = None,
) -> float:
    """Conservative convex LIFT. display = raw + (target - R_a) * t**k, t in [0,1].

    Never lowers (lift >= 0), identity at/below the floor, clamped at ceiling.
    """
    t_cfg = _config()["transform"]
    k = t_cfg["k"] if k is None else k
    floor = t_cfg["floor"] if floor is None else floor
    target = t_cfg["target"] if target is None else target
    ceiling = t_cfg["ceiling"] if ceiling is None else ceiling
    if raw <= floor or R_a <= floor:
        return round(raw, 1)
    span = R_a - floor
    t = (raw - floor) / span
    if t < 0.0:
        t = 0.0
    elif t > 1.0:
        t = 1.0
    lift = (target - R_a) * (t ** k)
    display = raw + lift
    if display > ceiling:
        display = ceiling
    if display < raw:  # lift form is always >= 0, but guard regardless
        display = raw
    return round(display, 1)


def _archetype(module: Optional[str], module_breakdown: Dict[str, Any]) -> str:
    if module == "sports":
        return "sports_single"
    if module == "omega":
        return "omega"
    if module == "probiotic":
        return "probiotic"
    if module == "multi_or_prenatal":
        return "prenatal_multi"
    # generic is split: botanical/branded-extract must not share the single-molecule curve
    form = (module_breakdown.get("dimensions", {}) or {}).get("formulation") or {}
    meta = form.get("metadata") or {}
    if meta.get("botanical_profile_applied") or meta.get("collagen_profile_applied"):
        return "generic_botanical_branded"
    return "generic_single_molecule"


def _eligible(
    *,
    verdict: Any,
    raw: Any,
    dims: Dict[str, Any],
    safety_signals: List[Any],
) -> Tuple[bool, str]:
    """top_band_eligibility — only well-disclosed, SAFE, high-raw products lift.

    Returns (eligible, reason). The confidence band is deliberately NOT checked.
    """
    cfg = _config()["eligibility"]
    if cfg.get("require_verdict_safe", True) and str(verdict) != "SAFE":
        return False, "verdict_not_safe"
    if raw is None or _num(raw, -1) < cfg["min_raw"]:
        return False, "raw_below_floor"
    evidence = _num((dims.get("evidence") or {}).get("score"))
    if evidence <= cfg.get("require_evidence_gt", 0.0):
        return False, "evidence_absent"
    tr = dims.get("transparency") or {}
    trs = _num(tr.get("score"))
    trc = _num(tr.get("max"), 10.0) or 10.0
    if trs < cfg.get("min_transparency_fraction", 0.5) * trc:
        return False, "transparency_low_or_opaque"
    dose = _num((dims.get("dose") or {}).get("score"))
    if dose <= cfg.get("require_dose_gt", 0.0):
        return False, "dose_disclosure_absent"
    if cfg.get("require_no_safety_signals", True) and safety_signals:
        return False, "safety_signals_present"
    return True, "eligible"


def calibrate_display(shadow: Dict[str, Any]) -> Dict[str, Any]:
    """Add ``shadow_score_v4_display_100`` + a provenance block. Mutates & returns
    ``shadow``. ``shadow_score_v4_100`` (raw) is never modified."""
    raw = shadow.get("shadow_score_v4_100")
    if raw is None:
        shadow["shadow_score_v4_display_100"] = None
        return shadow

    cfg = _config()
    module = shadow.get("shadow_score_v4_module")
    breakdown = shadow.get("shadow_score_v4_breakdown") or {}
    module_bd = breakdown.get("module") or {}
    dims = module_bd.get("dimensions") or {}
    verdict = shadow.get("shadow_score_v4_verdict")
    safety_signals = (breakdown.get("safety_gate") or {}).get("safety_signals") or []

    archetype = _archetype(module, module_bd)
    R_a = (cfg["archetypes"].get(archetype) or {}).get("R_a")
    eligible, reason = _eligible(
        verdict=verdict, raw=raw, dims=dims, safety_signals=safety_signals
    )

    raw_f = round(_num(raw), 1)
    if eligible and R_a:
        display = _transform(_num(raw), R_a=_num(R_a))
    else:
        display = raw_f

    applied = bool(eligible and R_a and display > raw_f)
    shadow["shadow_score_v4_display_100"] = display
    breakdown["display_calibration"] = {
        "applied": applied,
        "archetype": archetype,
        "R_a": R_a,
        "raw_score_100": raw_f,
        "display_score_100": display,
        "k": cfg["transform"]["k"],
        "ceiling": cfg["transform"]["ceiling"],
        "version": cfg["_metadata"]["version"],
        "reason": "top_band_lift" if applied else reason,
    }
    shadow["shadow_score_v4_breakdown"] = breakdown
    return shadow
