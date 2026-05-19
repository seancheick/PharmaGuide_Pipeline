"""v4 Layer 1 — Safety Gate.

Decides verdict from hard safety signals before any quality scoring runs.

Per SCORING_V4_PROPOSAL.md §4 Layer 1, precedence:

  BLOCKED > UNSAFE > CAUTION > None (None = scoring continues, verdict
                                     resolved by score band in P1.3+)

Trigger map:

  status == "banned"     (exact / alias match)  →  BLOCKED  (short-circuit)
  status == "recalled"   (exact / alias match)  →  UNSAFE   (short-circuit)
  status == "high_risk"  (exact / alias match)  →  CAUTION  (scoring continues)
  status == "watchlist"  (exact / alias match)  →  CAUTION  (scoring continues)
  has_disease_claims                            →  CAUTION  (scoring continues)
  fuzzy / partial match                         →  needs_review (no verdict)

This module reads ONLY enriched-product fields. It does not duplicate v3's
B0 penalty computation — v4 owns its own scoring policy in `scoring_v4/`.
The signal source (`contaminant_data.banned_substances.substances`) IS
shared with v3, but the verdict logic here is independent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# Verdict precedence — index = severity rank.
_VERDICT_PRECEDENCE = ("BLOCKED", "UNSAFE", "CAUTION")


def _verdict_rank(v: Optional[str]) -> int:
    """Lower index = more severe. None = no verdict (least severe)."""
    if v is None:
        return len(_VERDICT_PRECEDENCE)
    try:
        return _VERDICT_PRECEDENCE.index(v)
    except ValueError:
        return len(_VERDICT_PRECEDENCE)


def _max_verdict(a: Optional[str], b: Optional[str]) -> Optional[str]:
    """Return the more severe of two verdicts (lower rank wins)."""
    if _verdict_rank(a) <= _verdict_rank(b):
        return a
    return b


@dataclass
class SafetyResult:
    """Outcome of the Layer 1 safety gate.

    Attributes:
        verdict: 'BLOCKED' | 'UNSAFE' | 'CAUTION' | None. None means
            no safety trigger fired; the final verdict will be resolved
            later by the score-band rules (POOR / SAFE) in the scoring
            module.
        short_circuits_scoring: True when verdict is BLOCKED or UNSAFE.
            Caller must skip the scoring math entirely and emit the
            shadow score with score=None. The shadow `anchored` flag is
            reserved for canary-set membership, not safety finality.
        blocking_reason: A stable code for explainability and Flutter
            UI ('banned_ingredient' / 'recalled_ingredient' / etc.) when
            the verdict short-circuits; None otherwise.
        matched_substance: Name of the specific substance that triggered
            the verdict, when known. For explainability.
        safety_signals: List of trigger codes captured during evaluation
            (e.g., 'B0_HIGH_RISK_SUBSTANCE', 'DISEASE_CLAIM_DETECTED').
            Carries the full picture even when the verdict is just one
            value.
        needs_review: True when any fuzzy/partial match fired without
            crossing the exact/alias threshold; routes the product to
            the cert/safety review queue rather than auto-blocking.
    """

    verdict: Optional[str] = None
    short_circuits_scoring: bool = False
    blocking_reason: Optional[str] = None
    matched_substance: Optional[str] = None
    safety_signals: List[str] = field(default_factory=list)
    needs_review: bool = False


# Match types that authorize a verdict change. Other match types (fuzzy,
# partial, token, etc.) route to the review queue without auto-blocking.
_VERDICT_MATCH_TYPES = frozenset({"exact", "alias"})


def _safe_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _extract_substances(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    cd = product.get("contaminant_data")
    if not isinstance(cd, dict):
        return []
    bs = cd.get("banned_substances")
    if not isinstance(bs, dict):
        return []
    return [s for s in _safe_list(bs.get("substances")) if isinstance(s, dict)]


def _substance_name(s: Dict[str, Any]) -> str:
    return (
        s.get("banned_name")
        or s.get("ingredient")
        or s.get("name")
        or "unknown"
    )


def evaluate_safety_gate(product: Dict[str, Any]) -> SafetyResult:
    """Evaluate the v4 Layer 1 safety gate on an enriched product.

    Never raises. Resilient to missing / malformed fields. Returns a
    SafetyResult — the caller (shadow entry point) decides how to apply
    the verdict and short-circuit logic.
    """
    if not isinstance(product, dict):
        return SafetyResult()

    result = SafetyResult()

    substances = _extract_substances(product)
    for s in substances:
        match_type = _norm(s.get("match_type") or s.get("match_method"))
        # Non-exact/alias hits don't auto-trigger a verdict change — they
        # mark the product as needing reviewer attention. Matches v3's
        # _evaluate_safety_gate review-only policy on fuzzy hits.
        if match_type not in _VERDICT_MATCH_TYPES:
            result.needs_review = True
            continue

        status = _norm(s.get("status") or s.get("recall_status"))
        name = _substance_name(s)

        if status == "banned":
            new_verdict = "BLOCKED"
            if _verdict_rank(new_verdict) < _verdict_rank(result.verdict):
                result.verdict = new_verdict
                result.blocking_reason = "banned_ingredient"
                result.matched_substance = name
        elif status == "recalled":
            new_verdict = "UNSAFE"
            if _verdict_rank(new_verdict) < _verdict_rank(result.verdict):
                result.verdict = new_verdict
                result.blocking_reason = "recalled_ingredient"
                result.matched_substance = name
        elif status == "high_risk":
            result.verdict = _max_verdict(result.verdict, "CAUTION")
            if "B0_HIGH_RISK_SUBSTANCE" not in result.safety_signals:
                result.safety_signals.append("B0_HIGH_RISK_SUBSTANCE")
        elif status == "watchlist":
            result.verdict = _max_verdict(result.verdict, "CAUTION")
            if "B0_WATCHLIST_SUBSTANCE" not in result.safety_signals:
                result.safety_signals.append("B0_WATCHLIST_SUBSTANCE")
        # Other / unknown status: ignore for verdict, but record signal
        elif status:
            sig = f"B0_STATUS_{status.upper()}"
            if sig not in result.safety_signals:
                result.safety_signals.append(sig)

    # Top-level enricher flags — defense in depth. If contaminant_data
    # was somehow empty but the enricher set the boolean (older blob
    # shapes), still honor the safety signal.
    if product.get("has_banned_substance") and result.verdict != "BLOCKED":
        if _verdict_rank("BLOCKED") < _verdict_rank(result.verdict):
            result.verdict = "BLOCKED"
            result.blocking_reason = result.blocking_reason or "banned_ingredient"

    if product.get("has_recalled_ingredient") and result.verdict not in {"BLOCKED"}:
        if _verdict_rank("UNSAFE") < _verdict_rank(result.verdict):
            result.verdict = "UNSAFE"
            result.blocking_reason = result.blocking_reason or "recalled_ingredient"

    # Disease claims → CAUTION. v3 routes this through B6 marketing
    # penalty + verdict adjustment; v4 surfaces it as a Layer 1 signal.
    has_disease_claims = bool(product.get("has_disease_claims", False))
    if not has_disease_claims:
        # Some enriched blobs nest the flag under product_signals or
        # evidence_data — check both for compatibility.
        ps = product.get("product_signals") or {}
        if isinstance(ps, dict) and ps.get("has_disease_claims"):
            has_disease_claims = True
        if not has_disease_claims:
            ed = product.get("evidence_data") or {}
            if isinstance(ed, dict):
                uc = ed.get("unsubstantiated_claims") or {}
                if isinstance(uc, dict) and uc.get("found"):
                    has_disease_claims = True

    if has_disease_claims:
        result.verdict = _max_verdict(result.verdict, "CAUTION")
        if "DISEASE_CLAIM_DETECTED" not in result.safety_signals:
            result.safety_signals.append("DISEASE_CLAIM_DETECTED")

    # short_circuits_scoring is purely a function of verdict severity.
    result.short_circuits_scoring = result.verdict in {"BLOCKED", "UNSAFE"}
    return result
