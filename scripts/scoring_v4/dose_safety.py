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

    none                       flag present, resolved, at/below the UL
    confirmed_over_threshold   resolved above the UL and gate-eligible; the
                               ``penalized`` field records whether it also
                               crosses the configured B7 scoring threshold
    material_but_unresolved    exposure is material but the check is incomplete
                               (magnitude absent, or the enricher marked the row
                               ineligible for the UL gate). Routes to review;
                               never claims or deducts an unproven exceedance.
    not_applicable             not a distinct exposure (a declared total plus its
                               own disclosed form breakdown). Never deducts.
    conversion_failed          a magnitude was supplied that cannot be parsed.
                               An engineering defect: surfaced, never deducted.
"""

from __future__ import annotations

import math
from collections import Counter
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Mapping, Optional

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

# Folate is stated in two non-interchangeable bases: dietary folate equivalents
# (mcg DFE) and the mass of the form supplying them. Folic acid converts at
# 1.7 mcg DFE per mcg, so a numeric match across the two bases is a coincidence,
# not evidence that the rows describe one exposure.
_FOLATE_DFE_TOKEN = "dfe"
_FOLATE_MASS_TO_MCG = {
    "mcg": 1.0,
    "ug": 1.0,
    "µg": 1.0,
    "μg": 1.0,
    "microgram": 1.0,
    "micrograms": 1.0,
    "mg": 1000.0,
    "milligram": 1000.0,
    "milligrams": 1000.0,
}
_FOLATE_BASIS_UNSTATED = ""
_FOLATE_BASIS_DFE = "dfe"
_FOLATE_BASIS_MASS = "mass"

# A UL is the highest daily intake expected to pose no risk for nearly all
# healthy people. A confirmed exposure above 100% is therefore consumer-
# actionable even when the separate B7 scoring penalty starts at 150%.
_CONFIRMED_UL_EXCEEDANCE_PCT = 100.0


def _folate_dose_basis(value: Any) -> tuple[str, Optional[float]]:
    """Return ``(basis, multiplier_to_mcg)`` for one contributing-row unit.

    ``multiplier`` is ``None`` when the unit is stated but not a recognised
    folate mass unit — that row cannot be reconciled against anything, so the
    caller must decline rather than guess. An unstated unit is reported as the
    ``unstated`` basis with a neutral multiplier, preserving the behaviour of
    older artifacts whose contributing rows carry no unit at all.
    """
    text = _norm_text(value)
    if not text:
        return _FOLATE_BASIS_UNSTATED, 1.0

    parts = text.replace("(s)", " ").replace("/", " ").split()
    mass_token = next((part for part in parts if part in _FOLATE_MASS_TO_MCG), None)
    if mass_token is None:
        return "unknown", None
    basis = _FOLATE_BASIS_DFE if _FOLATE_DFE_TOKEN in parts else _FOLATE_BASIS_MASS
    return basis, _FOLATE_MASS_TO_MCG[mass_token]


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

    def audit_metadata(self) -> Dict[str, Any]:
        """Stable, JSON-ready detail for module breakdowns and corpus audits."""
        return {
            "state_counts": dict(Counter(flag.state for flag in self.flags)),
            "conversion_failures": self.conversion_failures,
            "flags": [
                {
                    "state": flag.state,
                    "nutrient": flag.nutrient,
                    "canonical_id": flag.canonical_id,
                    "pct_ul": flag.pct_ul,
                    "reason": flag.reason,
                    "penalized": flag.penalized,
                }
                for flag in self.flags
            ],
        }


_ACTIVE_RESULT: ContextVar[Optional[DoseSafetyResult]] = ContextVar(
    "v4_active_dose_safety_result",
    default=None,
)


@contextmanager
def dose_safety_scope(result: DoseSafetyResult) -> Iterator[None]:
    """Share one immutable evaluation across the gate and routed module.

    Direct module tests may still call :func:`resolve_dose_safety` without a
    scope; production scoring opens this scope once per product so no module can
    quietly become a second interpreter of the same enriched safety flags.
    """
    token = _ACTIVE_RESULT.set(result)
    try:
        yield
    finally:
        _ACTIVE_RESULT.reset(token)


def resolve_dose_safety(
    product: Dict[str, Any],
    *,
    threshold: float,
    per_flag_penalty: float,
    cap: float,
) -> DoseSafetyResult:
    """Return the production-scoped result, or evaluate for a direct caller."""
    active = _ACTIVE_RESULT.get()
    if active is not None:
        return active
    return evaluate_dose_safety(
        product,
        threshold=threshold,
        per_flag_penalty=per_flag_penalty,
        cap=cap,
    )


def dose_safety_consumer_explanation(
    state_counts: Mapping[str, Any] | None,
) -> Optional[str]:
    """Return honest consumer copy for one typed dose-safety summary.

    The penalty magnitude cannot distinguish confirmed excess from an
    unresolved comparison. Consumer language must therefore use the typed
    states emitted by :meth:`DoseSafetyResult.audit_metadata`.
    """

    counts = state_counts if isinstance(state_counts, Mapping) else {}

    def present(state: str) -> bool:
        value = counts.get(state, 0)
        return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0

    confirmed = present(CONFIRMED_OVER_THRESHOLD)
    unresolved = present(MATERIAL_BUT_UNRESOLVED)
    if confirmed and unresolved:
        return (
            "one or more supplemental amounts exceed an established upper "
            "limit, and additional dose-safety checks remain unresolved"
        )
    if confirmed:
        return "one or more supplemental amounts exceed an established upper limit"
    if unresolved:
        return (
            "one or more dose-safety checks could not be completed because "
            "the amount, form, or comparison basis was unresolved"
        )
    return None


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
    parent_basis: Optional[str] = None
    form_amounts: List[float] = []
    form_bases: List[str] = []
    for row in rows:
        name = _norm_text(row.get("ingredient"))
        amount = _as_float(row.get("amount"), None)
        if amount is None or amount <= 0:
            continue
        basis, multiplier = _folate_dose_basis(row.get("unit"))
        if multiplier is None:
            # A stated unit we cannot interpret. Reconciling against it would be
            # a guess, and a guess must never suppress an over-limit warning.
            return False
        normalized = amount * multiplier
        if name in _FOLATE_PARENT_NAMES or name == nutrient:
            if parent_amount is None or normalized > parent_amount:
                parent_amount = normalized
                parent_basis = basis
        elif any(token in name for token in _FOLATE_FORM_TOKENS):
            form_amounts.append(normalized)
            form_bases.append(basis)

    if parent_amount is None or not form_amounts:
        return False
    # One exposure can only be recognised within a single dose basis.
    if len({parent_basis, *form_bases}) > 1:
        return False
    form_sum = sum(form_amounts)
    if form_sum <= 0:
        return False
    tolerance = max(
        _FOLATE_RECONCILE_ABS_TOLERANCE,
        parent_amount * _FOLATE_RECONCILE_REL_TOLERANCE,
    )
    return abs(parent_amount - form_sum) <= tolerance


def _resolve_pct_ul(flag: Dict[str, Any]) -> tuple[Optional[float], Optional[str]]:
    """Return ``(pct_ul, failure_reason)``.

    A magnitude that is absent or explicitly null is unresolved, not broken. A
    magnitude that is present but unparseable, non-finite, boolean, or negative
    is an engineering defect. Python's ``float()`` accepts all of NaN, Infinity,
    and booleans; the dose-safety contract must not.
    """
    raw = flag.get("pct_ul")
    if raw is None:
        return None, None
    if isinstance(raw, bool):
        return None, "pct_ul_boolean"
    value = _as_float(raw, None)
    if value is None:
        return None, "pct_ul_not_numeric"
    if not math.isfinite(value):
        return None, "pct_ul_not_finite"
    if value < 0:
        return None, "pct_ul_negative"
    return value, None


def _classify(flag: Dict[str, Any], threshold: float) -> DoseSafetyFlag:
    nutrient = flag.get("nutrient")
    canonical_id = flag.get("canonical_id")
    pct_ul, failure_reason = _resolve_pct_ul(flag)

    if failure_reason is not None:
        return DoseSafetyFlag(
            state=CONVERSION_FAILED,
            nutrient=nutrient,
            canonical_id=canonical_id,
            pct_ul=flag.get("pct_ul"),
            reason=failure_reason,
            penalized=False,
        )

    if pct_ul is not None and pct_ul <= _CONFIRMED_UL_EXCEEDANCE_PCT:
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
            penalized=False,
        )

    # Same eligibility contract the safety gate applies to the UL verdict. An
    # ineligible row (compound mass rather than elemental, or no daily-value
    # anchor) is not a confirmed exceedance. It routes to review but cannot
    # incur an over-limit deduction: the comparison has not been established.
    if flag.get("ul_gate_eligible") is not True:
        return DoseSafetyFlag(
            state=MATERIAL_BUT_UNRESOLVED,
            nutrient=nutrient,
            canonical_id=canonical_id,
            pct_ul=pct_ul,
            reason=_norm_text(flag.get("ul_gate_ineligible_reason")) or "ul_gate_not_eligible",
            penalized=False,
        )

    return DoseSafetyFlag(
        state=CONFIRMED_OVER_THRESHOLD,
        nutrient=nutrient,
        canonical_id=canonical_id,
        pct_ul=pct_ul,
        penalized=pct_ul >= threshold,
    )


def dose_safety_contract_issues(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return fail-closed structural/numeric defects in the enriched B7 input.

    Missing ``pct_ul`` remains a supported unresolved state. Present-but-invalid
    values are engineering defects and must stop Stage 3 before any artifact is
    published.
    """
    if not isinstance(product, dict):
        return [{"path": "$", "reason": "product_not_object"}]

    raw_rda_ul = product.get("rda_ul_data")
    if raw_rda_ul is None:
        return []
    if not isinstance(raw_rda_ul, dict):
        return [{"path": "rda_ul_data", "reason": "rda_ul_data_not_object"}]

    raw_flags = raw_rda_ul.get("safety_flags")
    if raw_flags is None:
        return []
    if not isinstance(raw_flags, list):
        return [{
            "path": "rda_ul_data.safety_flags",
            "reason": "safety_flags_not_array",
        }]

    issues: List[Dict[str, Any]] = []
    for index, raw_flag in enumerate(raw_flags):
        path = f"rda_ul_data.safety_flags[{index}]"
        if not isinstance(raw_flag, dict):
            issues.append({"path": path, "reason": "safety_flag_not_object"})
            continue
        _, failure_reason = _resolve_pct_ul(raw_flag)
        if failure_reason is not None:
            issues.append({
                "path": f"{path}.pct_ul",
                "reason": failure_reason,
                "nutrient": raw_flag.get("nutrient"),
                "value": raw_flag.get("pct_ul"),
            })
    return issues


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
