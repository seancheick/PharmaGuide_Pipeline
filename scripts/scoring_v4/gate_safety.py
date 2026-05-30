"""v4 Layer 1 — Safety Gate.

Decides verdict from hard safety signals before any quality scoring runs.

Per SCORING_V4_PROPOSAL.md §4 Layer 1, precedence:

  BLOCKED > UNSAFE > CAUTION > None (None = scoring continues, verdict
                                     resolved by score band in P1.3+)

This gate consumes the canonical SafetySignal v1 contract from the kernel
(identity/safety.py::normalize_safety_signals). It branches ONLY on the
stable `match_resolution` enum + `status` — it NEVER sees a raw matcher name
(exact / alias / token_bounded / fuzzy). All matcher-internal knowledge lives
in the kernel's `match_resolution_for`. The architecture lock is enforced by
test_safety_signal_contract.py::test_gate_safety_has_no_raw_match_type_branching.

Policy (see _apply_signal_policy for the authoritative implementation):

  confirmed       + banned                  →  BLOCKED  (short-circuit)
  confirmed       + recalled                →  UNSAFE   (short-circuit)
  confirmed/likely + high_risk / watchlist  →  CAUTION  (scoring continues)
  likely          + banned / recalled       →  CAUTION + needs_review
                                               (force CAUTION so it can never
                                                score SAFE; hard BLOCK still
                                                requires a CONFIRMED match)
  review_only     (weak / fuzzy / no id)    →  needs_review, no verdict
  low_confidence                            →  audit signal only
  inactive excipient_acceptable + high_risk/watchlist  →  warning only
  has_disease_claims                        →  CAUTION  (scoring continues)

The signal SOURCE is shared with v3, but the verdict policy here is v4-owned.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Dict, List, Optional

from inactive_ingredient_resolver import (
    InactiveIngredientResolver,
    SOURCE_BANNED_RECALLED,
)
from identity.safety import (
    SafetySignal,
    normalize_safety_signals,
)


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


# NOTE: match-type → trust mapping moved to the SafetySignal v1 kernel
# (identity/safety.py::match_resolution_for). This gate consumes the stable
# `match_resolution` enum (confirmed / likely / review_only / low_confidence)
# and MUST NOT branch on raw matcher names — enforced by
# test_gate_safety_has_no_raw_match_type.


def _safe_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


@lru_cache(maxsize=1)
def _inactive_resolver() -> InactiveIngredientResolver:
    return InactiveIngredientResolver()


def _ingredient_name_terms(ingredient: Dict[str, Any]) -> tuple[str, Optional[str]]:
    raw_name = (
        ingredient.get("name")
        or ingredient.get("raw_source_text")
        or ingredient.get("standardName")
        or ingredient.get("standard_name")
    )
    standard_name = ingredient.get("standardName") or ingredient.get("standard_name")
    return str(raw_name or ""), str(standard_name) if standard_name else None


def _iter_resolver_safety_hits(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return banned_recalled resolver hits from active + inactive rows.

    v3/final DB already use the unified inactive resolver to close the gap
    where banned inactives (for example BVO or FD&C Red No. 3) are absent from
    contaminant_data.banned_substances. v4 owns its verdict policy, but it must
    consume the same canonical safety identity source.
    """
    try:
        resolver = _inactive_resolver()
    except Exception:
        return []

    hits: List[Dict[str, Any]] = []
    for source_key, role in (
        ("activeIngredients", "active"),
        ("inactiveIngredients", "inactive"),
    ):
        for ingredient in _safe_list((product or {}).get(source_key)):
            if not isinstance(ingredient, dict):
                continue
            raw_name, standard_name = _ingredient_name_terms(ingredient)
            if not raw_name:
                continue
            try:
                resolution = resolver.resolve(
                    raw_name=raw_name,
                    standard_name=standard_name,
                )
            except Exception:
                continue
            if resolution.matched_source != SOURCE_BANNED_RECALLED:
                continue
            if not (resolution.is_safety_concern or resolution.is_banned):
                continue
            hits.append({
                "name": resolution.display_label or raw_name,
                "status": resolution.regulatory_status,
                "inactive_policy": resolution.inactive_policy,
                "role": role,
                "matched_rule_id": resolution.matched_rule_id,
            })
    return hits


def _append_signal(result: SafetyResult, code: str) -> None:
    if code not in result.safety_signals:
        result.safety_signals.append(code)


def _apply_signal_policy(result: SafetyResult, sig: SafetySignal) -> None:
    """Apply pure safety policy to one normalized SafetySignal.

    Branches ONLY on the stable contract fields (match_resolution, status,
    subject_role, inactive_policy) — never on raw match_type. Policy:

        confirmed + banned        -> BLOCKED (short-circuit)
        confirmed + recalled      -> UNSAFE  (short-circuit)
        confirmed/likely + high_risk/watchlist -> CAUTION
        likely + banned/recalled  -> CAUTION + needs_review (forced CAUTION so it
                                      can never score SAFE; a hard BLOCK still
                                      requires a CONFIRMED match — a false
                                      hard-block is worse than a missed one)
        review_only               -> needs_review, no verdict
        low_confidence            -> audit signal only
        inactive excipient_acceptable + high_risk/watchlist -> warning only
    """
    status = sig.status

    # Inactive excipients with an acceptable policy are warning-only for the
    # soft statuses (e.g. a high_risk excipient used as a capsule colorant).
    if (sig.subject_role == "inactive"
            and sig.inactive_policy == "excipient_acceptable"
            and status in ("high_risk", "watchlist")):
        marker = ("B0_HIGH_RISK_EXCIPIENT_WARNING_ONLY" if status == "high_risk"
                  else "B0_WATCHLIST_EXCIPIENT_WARNING_ONLY")
        _append_signal(result, marker)
        return

    if sig.review_required:
        result.needs_review = True
        return

    if not sig.policy_eligible:
        # low_confidence: record for audit, never drive a verdict.
        if status:
            _append_signal(result, f"B0_LOWCONF_{status.upper()}")
        return

    # policy_eligible == confirmed or likely from here.
    #
    # Safety contract:
    #   - banned/recalled hard verdicts (BLOCKED/UNSAFE) require a CONFIRMED
    #     match (exact/alias). A false hard-block is worse than a missed one.
    #   - a `likely` banned/recalled hit (token_bounded with entry_id) is NOT
    #     hard-blocked, but MUST force CAUTION — it can never be allowed to
    #     score SAFE. This closes the shipped downgrade where Red Yeast Rice
    #     (banned monacolin-K source, token_bounded match) scored SAFE vs v3
    #     CAUTION. needs_review still routes it to the safety queue.
    #   - high_risk/watchlist accept `likely` → CAUTION (the DHEA/Kava fix).
    if status == "banned":
        if sig.match_resolution == "confirmed":
            if _verdict_rank("BLOCKED") < _verdict_rank(result.verdict):
                result.verdict = "BLOCKED"
                result.blocking_reason = "banned_ingredient"
                result.matched_substance = sig.evidence_text or sig.entry_id
        else:  # likely-banned: force CAUTION + review, never hard-block, never SAFE
            result.verdict = _max_verdict(result.verdict, "CAUTION")
            result.needs_review = True
            _append_signal(result, "B0_LIKELY_BANNED_REVIEW")
    elif status == "recalled":
        if sig.match_resolution == "confirmed":
            if _verdict_rank("UNSAFE") < _verdict_rank(result.verdict):
                result.verdict = "UNSAFE"
                result.blocking_reason = "recalled_ingredient"
                result.matched_substance = sig.evidence_text or sig.entry_id
        else:  # likely-recalled: force CAUTION + review, never hard-block, never SAFE
            result.verdict = _max_verdict(result.verdict, "CAUTION")
            result.needs_review = True
            _append_signal(result, "B0_LIKELY_RECALLED_REVIEW")
    elif status == "high_risk":
        result.verdict = _max_verdict(result.verdict, "CAUTION")
        _append_signal(result, "B0_HIGH_RISK_SUBSTANCE")
    elif status == "watchlist":
        result.verdict = _max_verdict(result.verdict, "CAUTION")
        _append_signal(result, "B0_WATCHLIST_SUBSTANCE")
    elif status:
        _append_signal(result, f"B0_STATUS_{status.upper()}")


def evaluate_safety_gate(product: Dict[str, Any]) -> SafetyResult:
    """Evaluate the v4 Layer 1 safety gate on an enriched product.

    Never raises. Resilient to missing / malformed fields. Returns a
    SafetyResult — the caller (shadow entry point) decides how to apply
    the verdict and short-circuit logic.
    """
    if not isinstance(product, dict):
        return SafetyResult()

    result = SafetyResult()

    # Consume the canonical SafetySignal[] contract. The kernel
    # (identity/safety.py) owns ALL matcher-internal knowledge and emits a
    # stable match_resolution enum; this gate applies pure policy on
    # (match_resolution, status) and never sees a raw match_type.
    signals = normalize_safety_signals(
        product,
        resolver_hits=_iter_resolver_safety_hits(product),
    )
    for sig in signals:
        _apply_signal_policy(result, sig)

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
