"""Shared dose-safety (B7) evaluation — the single owner of over-UL scoring policy.

Three modules used to interpret ``rda_ul_data.safety_flags`` three different ways.
``generic_dose`` carried the P0-2 fail-safe ("a flag is emitted only for an over-UL
row, so a missing ``pct_ul`` must never read as under-UL"); ``multi_prenatal_dose``
and ``b_complex`` defaulted the same field to ``0.0`` and skipped the penalty.
Conversely the folate parent-total de-duplication lived only in
``multi_prenatal_dose``, so one logical exposure was charged twice everywhere else.

This module owns that policy once. Callers supply their own configured threshold,
per-flag penalty and cap — the magnitudes stay module-owned and config-driven; only
the *interpretation* is shared.

The typed state exists so that "confirmed over the limit" never gets conflated with
"we could not resolve this exposure". Both may deduct, but they must not claim the
same thing to a reader:

    none                       flag present, resolved, under the threshold
    confirmed_over_threshold   resolved, at/over the threshold, gate-eligible
    material_but_unresolved    exposure is material but the check is incomplete
                               (magnitude absent, or the enricher marked the row
                               ineligible for the UL gate). Deducts conservatively.
    not_applicable             not a distinct exposure (a declared total plus its
                               own disclosed form breakdown). Never deducts.
    conversion_failed          a magnitude was supplied that cannot be parsed.
                               An engineering defect: surfaced, never deducted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from scoring_v4.modules.generic_helpers import _as_float, _norm_text, _safe_list

NONE = "none"
CONFIRMED_OVER_THRESHOLD = "confirmed_over_threshold"
MATERIAL_BUT_UNRESOLVED = "material_but_unresolved"
NOT_APPLICABLE = "not_applicable"
CONVERSION_FAILED = "conversion_failed"

REASON_PCT_UL_NOT_RESOLVED = "pct_ul_not_resolved"
REASON_FOLATE_PARENT_TOTAL_DUPLICATE = "folate_parent_total_plus_form_breakdown_duplicate"

# Tolerance for reconciling a declared parent total against its disclosed form
# rows. Absolute floor so small mcg panels are not held to a stricter standard
# than large ones.
_FOLATE_RECONCILE_ABS_TOLERANCE = 50.0
_FOLATE_RECONCILE_REL_TOLERANCE = 0.10

_FOLATE_CANONICALS = {"vitamin_b9_folate", "folate"}
_FOLATE_PARENT_NAMES = {"folate", "vitamin b9 folate", "vitamin b9"}
_FOLATE_FORM_TOKENS = (
    "folic acid",
    "mthf",
    "methyltetrahydrofolate",
    "methylfolate",
    "folinic",
    "folinate",
)


@dataclass(frozen=True)
class DoseSafetyFlag:
    """One classified safety flag."""

    state: str
    nutrient: Optional[str] = None
    canonical_id: Optional[str] = None
    pct_ul: Any = None
    reason: Optional[str] = None
    penalized: bool = False


@dataclass(frozen=True)
class DoseSafetyResult:
    """Aggregate outcome for one product."""

    penalty: float = 0.0
    flags: List[DoseSafetyFlag] = field(default_factory=list)
    ignored_flags: List[Dict[str, Any]] = field(default_factory=list)
    conversion_failures: int = 0


def is_folate_parent_total_duplicate_flag(flag: Dict[str, Any]) -> bool:
    """True when a folate flag is a declared total plus its own form breakdown.

    The enriched contract sums a canonical nutrient across contributing rows. When
    a label declares "Folate 1700 mcg DFE" AND itemises the forms that make it up,
    the aggregate and its children describe ONE exposure. Charging it twice is a
    double count, not a stricter reading.

    Deliberately scoped to the folate parent/form pattern. Widening it to every
    nutrient changes behaviour for exposures nobody has reviewed, so it is a
    separate, validated change.
    """
    if not isinstance(flag, dict):
        return False

    canonical = _norm_text(flag.get("canonical_id"))
    nutrient = _norm_text(flag.get("nutrient"))
    if canonical not in _FOLATE_CANONICALS and "folate" not in nutrient:
        return False
    if _norm_text(flag.get("aggregation")) != "canonical_sum":
        return False

    rows = [row for row in _safe_list(flag.get("contributing_rows")) if isinstance(row, dict)]
    if len(rows) < 2:
        return False

    parent_amount: Optional[float] = None
    form_amounts: List[float] = []
    for row in rows:
        name = _norm_text(row.get("ingredient"))
        amount = _as_float(row.get("amount"), None)
        if amount is None or amount <= 0:
            continue
        if name in _FOLATE_PARENT_NAMES or name == nutrient:
            parent_amount = max(parent_amount or 0.0, amount)
        elif any(token in name for token in _FOLATE_FORM_TOKENS):
            form_amounts.append(amount)

    if parent_amount is None or not form_amounts:
        return False
    form_sum = sum(form_amounts)
    if form_sum <= 0:
        return False
    tolerance = max(
        _FOLATE_RECONCILE_ABS_TOLERANCE,
        parent_amount * _FOLATE_RECONCILE_REL_TOLERANCE,
    )
    return abs(parent_amount - form_sum) <= tolerance


def _resolve_pct_ul(flag: Dict[str, Any]) -> tuple[Optional[float], bool]:
    """Return (pct_ul, conversion_failed).

    A magnitude that is absent or explicitly null is unresolved, not broken. A
    magnitude that is present but unparseable is an engineering defect.
    """
    raw = flag.get("pct_ul")
    if raw is None:
        return None, False
    value = _as_float(raw, None)
    if value is None:
        return None, True
    return value, False


def _classify(flag: Dict[str, Any], threshold: float) -> DoseSafetyFlag:
    nutrient = flag.get("nutrient")
    canonical_id = flag.get("canonical_id")
    pct_ul, conversion_failed = _resolve_pct_ul(flag)

    if conversion_failed:
        return DoseSafetyFlag(
            state=CONVERSION_FAILED,
            nutrient=nutrient,
            canonical_id=canonical_id,
            pct_ul=flag.get("pct_ul"),
            reason="pct_ul_not_numeric",
            penalized=False,
        )

    if pct_ul is not None and pct_ul < threshold:
        return DoseSafetyFlag(
            state=NONE,
            nutrient=nutrient,
            canonical_id=canonical_id,
            pct_ul=pct_ul,
            penalized=False,
        )

    # From here the flag would deduct. Ask first whether it is a distinct
    # exposure at all — de-duplication precedes severity.
    if is_folate_parent_total_duplicate_flag(flag):
        return DoseSafetyFlag(
            state=NOT_APPLICABLE,
            nutrient=nutrient,
            canonical_id=canonical_id,
            pct_ul=pct_ul,
            reason=REASON_FOLATE_PARENT_TOTAL_DUPLICATE,
            penalized=False,
        )

    if pct_ul is None:
        return DoseSafetyFlag(
            state=MATERIAL_BUT_UNRESOLVED,
            nutrient=nutrient,
            canonical_id=canonical_id,
            pct_ul=None,
            reason=REASON_PCT_UL_NOT_RESOLVED,
            penalized=True,
        )

    # Same eligibility contract the safety gate applies to the UL verdict. An
    # ineligible row (compound mass rather than elemental, or no daily-value
    # anchor) is not a confirmed exceedance. Scoring keeps the conservative
    # deduction for now; the state stops it claiming to be confirmed.
    if flag.get("ul_gate_eligible") is not True:
        return DoseSafetyFlag(
            state=MATERIAL_BUT_UNRESOLVED,
            nutrient=nutrient,
            canonical_id=canonical_id,
            pct_ul=pct_ul,
            reason=_norm_text(flag.get("ul_gate_ineligible_reason")) or "ul_gate_not_eligible",
            penalized=True,
        )

    return DoseSafetyFlag(
        state=CONFIRMED_OVER_THRESHOLD,
        nutrient=nutrient,
        canonical_id=canonical_id,
        pct_ul=pct_ul,
        penalized=True,
    )


def evaluate_dose_safety(
    product: Dict[str, Any],
    *,
    threshold: float,
    per_flag_penalty: float,
    cap: float,
) -> DoseSafetyResult:
    """Classify every safety flag on a product and total the B7 deduction.

    Never raises. Malformed entries are contained, not guessed at.
    """
    rda_ul = product.get("rda_ul_data") if isinstance(product, dict) else None
    raw_flags = _safe_list(rda_ul.get("safety_flags")) if isinstance(rda_ul, dict) else []

    flags: List[DoseSafetyFlag] = []
    ignored: List[Dict[str, Any]] = []
    total = 0.0
    conversion_failures = 0

    for raw in raw_flags:
        if not isinstance(raw, dict):
            continue
        classified = _classify(raw, threshold)
        flags.append(classified)
        if classified.state == CONVERSION_FAILED:
            conversion_failures += 1
        if classified.state == NOT_APPLICABLE:
            ignored.append({
                "nutrient": classified.nutrient,
                "canonical_id": classified.canonical_id,
                "pct_ul": classified.pct_ul,
                "reason": classified.reason,
            })
        if classified.penalized:
            total += per_flag_penalty

    return DoseSafetyResult(
        penalty=round(max(0.0, min(cap, total)), 4),
        flags=flags,
        ignored_flags=ignored,
        conversion_failures=conversion_failures,
    )
