"""v4 Omega Evidence dimension — P1.6.3.

Scores omega-3 evidence against the 20-point rubric in omega_rubric.json:

    clinical_evidence    /15  Generic multiplicative evidence pipeline
                              (study_type × evidence_level × effect_direction
                              × enrollment × dose_guard × top_N + depth_bonus,
                              cap_per_ingredient = 7) capped at 15. EPA/DHA
                              evidence is well-established AHA/EFSA-backed
                              so the pipeline produces meaningful credit
                              when clinical_matches are present.
    indication_relevance /5   Bonus when EPA+DHA per_day >= 1000 mg/day
                              (AHA CVD threshold), OR when a prenatal DHA
                              product meets the prenatal DHA target already
                              used by omega_dose. 0 otherwise.

Total cap: 20.

Pattern parallels P2.3 probiotic_evidence:
- Delegate the raw multiplicative pipeline to generic_evidence
  (already verified end-to-end in P1.3.3 for v4)
- Cap the delegated contribution at clinical_evidence cap (15 for omega,
  12 for probiotic)
- Add a class-specific relevance bonus

Per Sean's 'do not invent fields' rule:
- Indication relevance does NOT require manual marketed-indication text
  matching. It uses the same EPA+DHA per_day computation as P1.6.2 Dose —
  if the dose hits AHA CVD threshold (1g+ EPA+DHA daily), the product
  is delivering evidence-aligned dosing regardless of the marketing
  blurb.

Per §13 architecture lock — no v3 imports. (omega_dose helpers are
v4-only, safe to reuse.)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from scoring_v4.modules.generic_evidence import score_evidence as score_generic_evidence
from scoring_v4.modules.omega_dose import (
    _PRENATAL_DHA_TARGET_MG,
    _PRENATAL_DOSE_RE,
    _extract_daily_servings,
    _sum_epa_dha_per_serving,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
RUBRIC_PATH = REPO_ROOT / "scripts" / "data" / "omega_rubric.json"


PHASE_MARKER = "P1.6.3_omega_evidence"
CAP_EVIDENCE = 20.0


def _load_rubric() -> Dict[str, Any]:
    from scoring_v4.config_registry import load_rubric
    return load_rubric("omega")  # Phase 0: shared registry (validated + fingerprinted)


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _compute_per_day_components(product: Dict[str, Any]) -> Dict[str, float]:
    """Compute per-day midpoint dose components for indication relevance.

    Reuses omega_dose's identical helpers — single source of truth for
    'how much EPA+DHA does this product deliver per day?' across the
    omega module.
    """
    epa_ps, dha_ps, combined_ps = _sum_epa_dha_per_serving(product)
    total_per_serving = max(epa_ps + dha_ps, combined_ps)
    if total_per_serving <= 0:
        return {"epa": 0.0, "dha": 0.0, "combined": 0.0, "total": 0.0}
    min_daily, max_daily, _defaulted = _extract_daily_servings(product)
    mid_daily = (min_daily + max_daily) / 2.0
    return {
        "epa": epa_ps * mid_daily,
        "dha": dha_ps * mid_daily,
        "combined": combined_ps * mid_daily,
        "total": total_per_serving * mid_daily,
    }


def _compute_per_day_epa_dha(product: Dict[str, Any]) -> float:
    return _compute_per_day_components(product)["total"]


def _prenatal_dha_indication_relevant(product: Dict[str, Any], dha_per_day: float) -> bool:
    name_text = " ".join(
        str(product.get(key) or "")
        for key in ("product_name", "fullName", "brand_name", "brandName")
    )
    return bool(_PRENATAL_DOSE_RE.search(name_text)) and dha_per_day >= _PRENATAL_DHA_TARGET_MG


def score_evidence(product: Any) -> Dict[str, Any]:
    """Score omega-class Evidence dimension."""
    if not isinstance(product, dict):
        product = {}

    rubric = _load_rubric()
    ev_cfg = rubric["evidence"]
    total_cap = float(ev_cfg.get("cap", 20) or 20)
    indication_cfg = ev_cfg.get("indication_relevance", {}) or {}
    indication_threshold = float(indication_cfg.get("min_epa_dha_mg_day_for_bonus", 1000) or 1000)
    indication_score_max = float(indication_cfg.get("score", 5) or 5)
    floor_cfg = ev_cfg.get("disclosed_epa_dha_clinical_floor", {}) or {}
    floor_threshold = float(floor_cfg.get("min_epa_dha_mg_day", 250) or 250)
    floor_score = float(floor_cfg.get("score", 0) or 0)

    # Clinical evidence sub-cap = total_cap - indication_score_max.
    # Keeps the dimension cap-additive (15 + 5 = 20) without hardcoding
    # constants in module-level globals.
    clinical_sub_cap = max(0.0, total_cap - indication_score_max)

    # 1) Generic multiplicative evidence pipeline.
    generic_payload = score_generic_evidence(product)
    raw_generic_score = _as_float(generic_payload.get("score"), 0.0)

    # 2) Indication relevance bonus.
    per_day = _compute_per_day_components(product)
    per_day_epa_dha = per_day["total"]
    class_floor_score = 0.0
    class_floor_awarded = False
    if floor_score > 0 and per_day_epa_dha >= floor_threshold:
        class_floor_score = min(clinical_sub_cap, floor_score)
        class_floor_awarded = True
    clinical_score = min(clinical_sub_cap, max(raw_generic_score, class_floor_score))

    indication_reason = "none"
    if per_day_epa_dha >= indication_threshold:
        indication_score = indication_score_max
        indication_reason = "cv_epa_dha_threshold"
    elif _prenatal_dha_indication_relevant(product, per_day["dha"]):
        indication_score = indication_score_max
        indication_reason = "prenatal_dha_target"
    else:
        indication_score = 0.0

    components: Dict[str, float] = {}
    if clinical_score > 0:
        components["clinical_evidence"] = round(clinical_score, 2)
    if indication_score > 0:
        components["indication_relevance"] = indication_score

    raw_score = clinical_score + indication_score
    score = max(0.0, min(CAP_EVIDENCE, raw_score))

    metadata: Dict[str, Any] = {
        "phase": PHASE_MARKER,
        "raw_score": round(raw_score, 4),
        "cap_applied": raw_score > CAP_EVIDENCE,
        "clinical_sub_cap": clinical_sub_cap,
        "generic_evidence_raw_score": round(raw_generic_score, 4),
        "disclosed_epa_dha_clinical_floor_score": round(class_floor_score, 4),
        "disclosed_epa_dha_clinical_floor_awarded": class_floor_awarded,
        "disclosed_epa_dha_clinical_floor_threshold_mg_day": floor_threshold,
        "clinical_evidence_after_cap": round(clinical_score, 4),
        "per_day_epa_dha_mg": round(per_day_epa_dha, 2),
        "per_day_dha_mg": round(per_day["dha"], 2),
        "indication_threshold_mg_day": indication_threshold,
        "indication_relevance_awarded": indication_score > 0,
        "indication_relevance_reason": indication_reason,
        "generic_evidence_metadata": generic_payload.get("metadata", {}),
    }

    return {
        "score": round(score, 2),
        "max": CAP_EVIDENCE,
        "components": components,
        "penalties": dict(generic_payload.get("penalties") or {}),
        "metadata": metadata,
    }
