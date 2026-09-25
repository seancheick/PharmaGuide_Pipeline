"""v4 Omega Evidence dimension — P1.6.3.

Scores omega-3 evidence against the 20-point rubric in omega_rubric.json:

    clinical_evidence    /15  Generic multiplicative evidence pipeline
                              (study_type × evidence_level × effect_direction
                              × enrollment × dose_guard × top_N + depth_bonus,
                              cap_per_ingredient = 7) capped at 15. EPA/DHA
                              evidence is well-established AHA/EFSA-backed
                              so the pipeline produces meaningful credit
                              when clinical_matches are present.
    indication_relevance /5   Bonus when a prenatal DHA product meets the
                              prenatal DHA target already used by omega_dose.
                              0 otherwise. The bare >= 1000 mg/day branch was
                              retired 2026-09-18 as duplicate Dose credit.

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

from typing import Any, Dict

from scoring_v4.modules.generic_evidence import score_evidence as score_generic_evidence
from evidence_resolver import resolve_omega_evidence_standard


PHASE_MARKER = "P1.6.3_omega_evidence"
from scoring_v4.quality_score_config import block as _cfg_block

_EM = _cfg_block("evidence_magnitudes", "omega")["omega"]


CAP_EVIDENCE = _EM["cap_evidence"]


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


def score_evidence(product: Any) -> Dict[str, Any]:
    """Score omega-class Evidence dimension."""
    if not isinstance(product, dict):
        product = {}

    rubric = _load_rubric()
    ev_cfg = rubric["evidence"]
    total_cap = float(ev_cfg.get("cap", 20) or 20)
    # Keep the generic engine's output for audit continuity.  It no longer
    # awards omega points: adjunct D3/CoQ10 records and breadth must not own an
    # omega product's Evidence pillar.
    generic_payload = score_generic_evidence(product)
    raw_generic_score = _as_float(generic_payload.get("score"), 0.0)
    resolved = resolve_omega_evidence_standard(product)
    clinical_score = min(total_cap, _as_float(resolved.get("score"), 0.0))

    components: Dict[str, float] = {}
    if clinical_score > 0:
        components["clinical_evidence"] = round(clinical_score, 2)
    raw_score = clinical_score
    score = max(0.0, min(CAP_EVIDENCE, raw_score))

    per_day_min = _as_float(resolved.get("minimum_daily_epa_dha_mg"), 0.0)
    per_day_max = _as_float(resolved.get("maximum_daily_epa_dha_mg"), 0.0)
    per_day_mid = (per_day_min + per_day_max) / 2.0
    prenatal_authority = resolved.get("record_id") == "prenatal_dha_intake_authority"

    metadata: Dict[str, Any] = {
        "phase": PHASE_MARKER,
        "raw_score": round(raw_score, 4),
        "cap_applied": raw_score > CAP_EVIDENCE,
        "clinical_sub_cap": total_cap,
        "generic_evidence_raw_score": round(raw_generic_score, 4),
        "disclosed_epa_dha_clinical_floor_score": 0.0,
        "disclosed_epa_dha_clinical_floor_awarded": False,
        "disclosed_epa_dha_clinical_floor_threshold_mg_day": None,
        "clinical_evidence_after_cap": round(clinical_score, 4),
        "per_day_epa_dha_mg": round(per_day_mid, 2),
        "per_day_epa_dha_min_mg": round(per_day_min, 2),
        "per_day_epa_dha_max_mg": round(per_day_max, 2),
        "per_day_dha_mg": round(_as_float(resolved.get("minimum_daily_dha_mg"), 0.0), 2),
        "servings_defaulted": bool(resolved.get("servings_defaulted")),
        "applicability_qualified": bool(resolved.get("applicability_qualified")),
        "evidence_standard": resolved.get("record_id"),
        "evidence_source_pmids": list(resolved.get("record_source_pmids") or []),
        "prenatal_outcome_credit_awarded": bool(resolved.get("prenatal_outcome_credit_awarded")),
        "indication_threshold_mg_day": 200.0 if prenatal_authority else None,
        "indication_relevance_awarded": prenatal_authority,
        "indication_relevance_reason": "prenatal_dha_intake_authority" if prenatal_authority else "none",
        "generic_evidence_metadata": generic_payload.get("metadata", {}),
    }

    return {
        "score": round(score, 2),
        "max": CAP_EVIDENCE,
        "components": components,
        "penalties": dict(generic_payload.get("penalties") or {}),
        "metadata": metadata,
    }
