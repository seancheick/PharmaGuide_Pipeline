"""v4 → final-DB export adapter.

The single seam between the v4 scorer (`score_supplements_v4`) and the
frozen `products_core` export. `build_final_db.py` calls `overlay_v4_scored(
enriched, scored_v3)` once per product for the production v4 catalog.

Design (see docs/plans/V4_CUTOVER_HANDOFF.md and the approved cutover plan):
  - The export still consumes v3 *scaffolding* off the scored blob (section_scores
    for the review-queue gate, badges, flags, category_percentile,
    breakdown.B.B8_caers_evidence, strict_scoring_contract, scoring_metadata).
    v4 scores the SAME enriched corpus but produces a /100 six-pillar public score.
  - So we OVERLAY v4's public score/verdict onto a *shallow copy* of the v3 scored
    dict (keeping the scaffolding by reference) and STASH the full v4 public
    contract under reserved ``_v4_*`` keys. Downstream readers (`build_core_row`,
    `build_detail_blob`, `validate_export_contract`) pick them up with the same
    ``scored.get(...)`` idiom they already use — no signature churn, one channel.
  - Inputs are NEVER mutated. The v4 scorer runs exactly once per product here.

Suppression contract (honors ``quality_score_status``):
  - ``scored``           → finite /100 score; all fields populated.
  - ``suppressed_safety`` (BLOCKED/UNSAFE) → null score, ``display_100="N/A"``,
    reason set. This null is LEGITIMATE — the gate must not quarantine it.
  - ``not_scored``       → verdict ``NOT_SCORED``, null score — quarantined by the gate.

``raw_score_v4_100`` is exported for audit/debug only and is NEVER the shipped score.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from score_supplements_v4 import score_product_v4

SCORE_MODEL_V4 = "v4"


def _fmt_display_100(quality_score: Any) -> str:
    """Render the consumer-facing ``NN/100`` display string, or ``N/A``."""
    try:
        return f"{round(float(quality_score))}/100"
    except (TypeError, ValueError):
        return "N/A"


def overlay_v4_scored(enriched: Dict[str, Any], scored_v3: Dict[str, Any]) -> Dict[str, Any]:
    """Run v4 on ``enriched`` and overlay its public contract onto a copy of
    ``scored_v3``. Returns the new dict; never mutates either input."""
    v4 = score_product_v4(enriched if isinstance(enriched, dict) else {})
    scored = dict(scored_v3) if isinstance(scored_v3, dict) else {}

    breakdown = v4.get("v4_breakdown") or {}
    safety_gate = breakdown.get("safety_gate") or {}
    completeness_gate = breakdown.get("completeness_gate") or {}
    provenance = breakdown.get("provenance") or {}

    status = v4.get("quality_score_status")
    quality_100 = v4.get("quality_score_v4_100")
    verdict = v4.get("v4_verdict")
    is_scored = status == "scored"

    config_versions = provenance.get("config_versions")
    config_fingerprint = (
        json.dumps(config_versions, sort_keys=True, ensure_ascii=False)
        if config_versions is not None
        else None
    )
    v3_blocking = scored_v3.get("blocking_reason") if isinstance(scored_v3, dict) else None
    safety_signals = safety_gate.get("safety_signals") or []
    safety_signal_reason = None
    if is_scored and verdict == "CAUTION":
        if isinstance(safety_signals, list) and safety_signals:
            safety_signal_reason = str(safety_signals[0])
        else:
            safety_signal_reason = safety_gate.get("blocking_reason") or v3_blocking

    # ── Overlay the legacy keys the frozen export already reads ──────────────
    # v4 is authoritative under v4. score_100_equivalent / score_display_100_equivalent
    # become honest /100 compat mirrors of the public six-pillar score.
    scored["verdict"] = verdict
    scored["safety_verdict"] = safety_gate.get("verdict") or "SAFE"
    scored["score_100_equivalent"] = quality_100  # None when suppressed/not_scored
    scored["display_100"] = _fmt_display_100(quality_100) if is_scored else "N/A"
    scored["grade"] = v4.get("quality_tier")  # legacy `grade` column now carries the v4 tier
    scored["blocking_reason"] = safety_gate.get("blocking_reason") or v3_blocking
    scored["safety_signal_reason"] = safety_signal_reason
    # NOTE: `score_80` is intentionally left as the v3 scorer wrote it — the shallow
    # copy preserves it so build_decision_highlights keeps working off v3 scaffolding.
    # The /80 export column is dropped; only the /100 mirrors ship.

    # ── Stash the full v4 public contract under reserved keys ────────────────
    scored["_score_model_version"] = SCORE_MODEL_V4
    scored["_v4_quality_score_100"] = quality_100
    scored["_v4_quality_status"] = status
    scored["_v4_quality_tier"] = v4.get("quality_tier")
    scored["_v4_suppressed_reason"] = v4.get("quality_score_suppressed_reason")
    scored["_v4_raw_score_100"] = v4.get("raw_score_v4_100")
    scored["_v4_module"] = v4.get("v4_module")
    # Full module sub-breakdown (dimensions.*.penalties / verification_bonus.components)
    # so derive_v4_tradeoffs can re-source the B-code penalties from v4, not v3.
    scored["_v4_module_breakdown"] = breakdown.get("module") or None
    scored["_v4_confidence"] = v4.get("v4_confidence")
    scored["_v4_confidence_detail"] = breakdown.get("confidence") or None
    scored["_v4_quality_version"] = v4.get("quality_score_version")
    scored["_v4_pillars"] = v4.get("quality_pillars_v4")
    scored["_v4_clean_label_flags"] = v4.get("clean_label_flags_v4")
    scored["_v4_safety_gate"] = safety_gate or None
    scored["_v4_safety_signal_reason"] = safety_signal_reason
    scored["_v4_completeness_gate"] = completeness_gate or None
    scored["_v4_provenance"] = provenance or None
    scored["_v4_scoring_engine_version"] = provenance.get("scoring_engine_version")
    scored["_v4_classification_schema_version"] = provenance.get("classification_schema_version")
    scored["_v4_config_fingerprint"] = config_fingerprint

    return scored


def suppress_v4_for_hard_block(scored: Dict[str, Any], reason: str) -> Dict[str, Any]:
    """Force an already-overlaid ``scored`` dict into the v4 ``suppressed_safety`` +
    BLOCKED state. Mutates & returns ``scored``.

    The export's banned-substance gate (``banned_recalled_ingredients.json`` via
    ``has_banned_substance``) is BROADER than the v4 *scoring* safety gate — v4 does
    not block every substance the regulatory data flags (e.g. Boron / Sodium
    Tetraborate, partially-hydrogenated oils). When the two diverge, v4 hands back a
    finite ``scored`` result for a product the export will hard-block as BLOCKED. The
    v3 invariant — *a banned product ships no consumer score* — must hold under v4, or
    the catalog index/dedup would rank that product by a live ``quality_score_v4_100``.

    This collapses the overlaid contract to look exactly like a natively v4-suppressed
    (BLOCKED) product across BOTH export surfaces (``build_core_row`` reads the row
    fields, ``build_detail_blob`` reads the ``_v4_*`` keys). ``_v4_pillars`` and
    ``_v4_raw_score_100`` are kept as an audit trail, matching the v4 scorer's own
    ``suppressed_safety`` contract (see ``quality_score.assemble_quality_score``).
    """
    scored["verdict"] = "BLOCKED"
    scored["safety_verdict"] = "BLOCKED"
    scored["score_100_equivalent"] = None
    scored["display_100"] = "N/A"
    scored["grade"] = None
    scored["blocking_reason"] = scored.get("blocking_reason") or reason
    scored["safety_signal_reason"] = scored.get("safety_signal_reason") or reason
    scored["_v4_quality_score_100"] = None
    scored["_v4_quality_status"] = "suppressed_safety"
    scored["_v4_quality_tier"] = None
    scored["_v4_suppressed_reason"] = scored.get("_v4_suppressed_reason") or reason
    scored["_v4_safety_signal_reason"] = scored.get("_v4_safety_signal_reason") or reason
    return scored
