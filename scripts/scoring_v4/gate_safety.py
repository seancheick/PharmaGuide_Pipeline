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
from functools import lru_cache
from typing import Any, Dict, List, Optional

from inactive_ingredient_resolver import (
    InactiveIngredientResolver,
    SOURCE_BANNED_RECALLED,
)
from identity.safety import (
    normalize_safety_source,
    safety_flag_matches_status,
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


# Match types that authorize a verdict change. Other match types (fuzzy,
# partial, token, etc.) route to the review queue without auto-blocking.
_VERDICT_MATCH_TYPES = frozenset({"exact", "alias"})
_FLAG_VERDICT_MATCH_TYPES = frozenset({"exact", "alias", "explicit_form_evidence", "legacy_projection"})
# CAUTION is non-blocking and defensive, so it honors a broader match set than
# the hard BLOCKED/UNSAFE verdicts. `token_bounded` is a resolved word-boundary
# match (populated banned_id), not a fuzzy guess — for high_risk/watchlist
# substances (DHEA, Kava, HCA) it is a genuine safety signal and v3 marks these
# CAUTION. Banned/recalled stay on the strict set to avoid false hard-blocks.
_CAUTION_MATCH_TYPES = frozenset({"exact", "alias", "token_bounded"})


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


def _extract_banned_recalled_safety_flags(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    cd = product.get("contaminant_data")
    if not isinstance(cd, dict):
        return []
    bs = cd.get("banned_substances")
    if not isinstance(bs, dict):
        return []
    flags: List[Dict[str, Any]] = [
        f for f in _safe_list(bs.get("safety_flags")) if isinstance(f, dict)
    ]
    for substance in _safe_list(bs.get("substances")):
        if isinstance(substance, dict) and isinstance(substance.get("safety_flag"), dict):
            flags.append(substance["safety_flag"])
    return [
        flag for flag in flags
        if normalize_safety_source(flag.get("source_db") or flag.get("matched_source"))
        == "banned_recalled_ingredients"
    ]


def _substance_name(s: Dict[str, Any]) -> str:
    return (
        s.get("banned_name")
        or s.get("ingredient")
        or s.get("name")
        or "unknown"
    )


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


def evaluate_safety_gate(product: Dict[str, Any]) -> SafetyResult:
    """Evaluate the v4 Layer 1 safety gate on an enriched product.

    Never raises. Resilient to missing / malformed fields. Returns a
    SafetyResult — the caller (shadow entry point) decides how to apply
    the verdict and short-circuit logic.
    """
    if not isinstance(product, dict):
        return SafetyResult()

    result = SafetyResult()

    seen_hits: set[tuple[str, str]] = set()
    for flag in _extract_banned_recalled_safety_flags(product):
        match_type = _norm(flag.get("match_type"))
        name = (
            flag.get("matched_variant")
            or flag.get("evidence_text")
            or flag.get("entry_id")
            or "unknown"
        )
        status = _norm(flag.get("status"))
        seen_hits.add((_norm(name), status))
        if match_type not in _FLAG_VERDICT_MATCH_TYPES:
            result.needs_review = True
            continue

        if safety_flag_matches_status(flag, ("banned",)):
            new_verdict = "BLOCKED"
            if _verdict_rank(new_verdict) < _verdict_rank(result.verdict):
                result.verdict = new_verdict
                result.blocking_reason = "banned_ingredient"
                result.matched_substance = str(name)
        elif safety_flag_matches_status(flag, ("recalled",)):
            new_verdict = "UNSAFE"
            if _verdict_rank(new_verdict) < _verdict_rank(result.verdict):
                result.verdict = new_verdict
                result.blocking_reason = "recalled_ingredient"
                result.matched_substance = str(name)
        elif safety_flag_matches_status(flag, ("high_risk",)):
            result.verdict = _max_verdict(result.verdict, "CAUTION")
            if "B0_HIGH_RISK_SUBSTANCE" not in result.safety_signals:
                result.safety_signals.append("B0_HIGH_RISK_SUBSTANCE")
        elif safety_flag_matches_status(flag, ("watchlist",)):
            result.verdict = _max_verdict(result.verdict, "CAUTION")
            if "B0_WATCHLIST_SUBSTANCE" not in result.safety_signals:
                result.safety_signals.append("B0_WATCHLIST_SUBSTANCE")

    substances = _extract_substances(product)
    for s in substances:
        match_type = _norm(s.get("match_type") or s.get("match_method"))
        status = _norm(s.get("status") or s.get("recall_status"))
        name = _substance_name(s)

        # Status-aware match-type policy (Phase B1 parity fix, 2026-05-29):
        #   - banned / recalled (HARD verdicts that short-circuit scoring)
        #     require an exact/alias match. A false BLOCK/UNSAFE is worse
        #     than a missed one here, so token_bounded / fuzzy banned hits
        #     route to needs_review (NOT auto-block).
        #   - high_risk / watchlist (CAUTION, non-blocking) also honor
        #     token_bounded matches, because a resolved banned_id match
        #     (e.g. DHEA, Kava, HCA) is a genuine safety signal and CAUTION
        #     is the defensive, low-harm posture. This restores v3 parity:
        #     v3 marked these CAUTION; v4 previously let them score SAFE
        #     because _VERDICT_MATCH_TYPES excluded token_bounded.
        if status in ("banned", "recalled"):
            if match_type not in _VERDICT_MATCH_TYPES:
                result.needs_review = True
                continue
            seen_hits.add((_norm(name), status))
            if status == "banned":
                new_verdict = "BLOCKED"
                if _verdict_rank(new_verdict) < _verdict_rank(result.verdict):
                    result.verdict = new_verdict
                    result.blocking_reason = "banned_ingredient"
                    result.matched_substance = name
            else:  # recalled
                new_verdict = "UNSAFE"
                if _verdict_rank(new_verdict) < _verdict_rank(result.verdict):
                    result.verdict = new_verdict
                    result.blocking_reason = "recalled_ingredient"
                    result.matched_substance = name
        elif status in ("high_risk", "watchlist"):
            if match_type not in _CAUTION_MATCH_TYPES:
                result.needs_review = True
                continue
            seen_hits.add((_norm(name), status))
            result.verdict = _max_verdict(result.verdict, "CAUTION")
            sig = "B0_HIGH_RISK_SUBSTANCE" if status == "high_risk" else "B0_WATCHLIST_SUBSTANCE"
            if sig not in result.safety_signals:
                result.safety_signals.append(sig)
        else:
            # Unknown / other status: never drives a verdict. Only record a
            # signal for an exact/alias hit; weaker matches → needs_review.
            if match_type not in _VERDICT_MATCH_TYPES:
                result.needs_review = True
                continue
            seen_hits.add((_norm(name), status))
            if status:
                sig = f"B0_STATUS_{status.upper()}"
                if sig not in result.safety_signals:
                    result.safety_signals.append(sig)

    for hit in _iter_resolver_safety_hits(product):
        status = _norm(hit.get("status"))
        name = str(hit.get("name") or "unknown")
        key = (_norm(name), status)
        if key in seen_hits:
            continue
        seen_hits.add(key)

        role = _norm(hit.get("role"))
        inactive_policy = _norm(hit.get("inactive_policy"))

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
            if role == "inactive" and inactive_policy == "excipient_acceptable":
                if "B0_HIGH_RISK_EXCIPIENT_WARNING_ONLY" not in result.safety_signals:
                    result.safety_signals.append("B0_HIGH_RISK_EXCIPIENT_WARNING_ONLY")
                continue
            result.verdict = _max_verdict(result.verdict, "CAUTION")
            if "B0_HIGH_RISK_SUBSTANCE" not in result.safety_signals:
                result.safety_signals.append("B0_HIGH_RISK_SUBSTANCE")
        elif status == "watchlist":
            if role == "inactive" and inactive_policy == "excipient_acceptable":
                if "B0_WATCHLIST_EXCIPIENT_WARNING_ONLY" not in result.safety_signals:
                    result.safety_signals.append("B0_WATCHLIST_EXCIPIENT_WARNING_ONLY")
                continue
            result.verdict = _max_verdict(result.verdict, "CAUTION")
            if "B0_WATCHLIST_SUBSTANCE" not in result.safety_signals:
                result.safety_signals.append("B0_WATCHLIST_SUBSTANCE")

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
