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
                              (AHA CVD threshold — strongest clinical
                              alignment with marketed cardiovascular
                              indication). 0 below 1000 mg/day.

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
    _extract_daily_servings,
    _sum_epa_dha_per_serving,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
RUBRIC_PATH = REPO_ROOT / "scripts" / "data" / "omega_rubric.json"


PHASE_MARKER = "P1.6.3_omega_evidence"
CAP_EVIDENCE = 20.0


def _load_rubric() -> Dict[str, Any]:
    return json.loads(RUBRIC_PATH.read_text())


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _compute_per_day_epa_dha(product: Dict[str, Any]) -> float:
    """Compute EPA+DHA per_day_mid for the indication-relevance check.
    Reuses omega_dose's identical helpers — single source of truth for
    'how much EPA+DHA does this product deliver per day?' across the
    omega module."""
    epa_ps, dha_ps, combined_ps = _sum_epa_dha_per_serving(product)
    total_per_serving = max(epa_ps + dha_ps, combined_ps)
    if total_per_serving <= 0:
        return 0.0
    min_daily, max_daily, _defaulted = _extract_daily_servings(product)
    per_day_min = total_per_serving * min_daily
    per_day_max = total_per_serving * max_daily
    return (per_day_min + per_day_max) / 2.0


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

    # Clinical evidence sub-cap = total_cap - indication_score_max.
    # Keeps the dimension cap-additive (15 + 5 = 20) without hardcoding
    # constants in module-level globals.
    clinical_sub_cap = max(0.0, total_cap - indication_score_max)

    # 1) Generic multiplicative evidence pipeline.
    generic_payload = score_generic_evidence(product)
    raw_generic_score = _as_float(generic_payload.get("score"), 0.0)
    clinical_score = min(clinical_sub_cap, raw_generic_score)

    # 2) Indication relevance bonus.
    per_day_epa_dha = _compute_per_day_epa_dha(product)
    indication_score = indication_score_max if per_day_epa_dha >= indication_threshold else 0.0

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
        "clinical_evidence_after_cap": round(clinical_score, 4),
        "per_day_epa_dha_mg": round(per_day_epa_dha, 2),
        "indication_threshold_mg_day": indication_threshold,
        "indication_relevance_awarded": indication_score > 0,
        "generic_evidence_metadata": generic_payload.get("metadata", {}),
    }

    return {
        "score": round(score, 2),
        "max": CAP_EVIDENCE,
        "components": components,
        "penalties": dict(generic_payload.get("penalties") or {}),
        "metadata": metadata,
    }
