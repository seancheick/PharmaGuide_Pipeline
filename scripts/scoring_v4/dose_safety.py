"""Shared dose-safety evaluation — the single owner of over-UL scoring policy.

Three modules used to interpret ``rda_ul_data.safety_flags`` three different ways.
``generic_dose`` carried the P0-2 fail-safe ("a flag is emitted only for an over-UL
row, so a missing ``pct_ul`` must never read as under-UL"); ``multi_prenatal_dose``
and ``b_complex`` defaulted the same field to ``0.0`` and skipped the penalty.
Conversely the folate parent-total de-duplication lived only in
``multi_prenatal_dose``, so one logical exposure was charged twice everywhere else.

This module owns that policy once, including the one product-level Dose ceiling
(Dose V4.1 §2.4, Sean 2026-10-17): the strongest confirmed exceedance at maximum
directed daily use caps the public Dose pillar once, after aggregation
(``quality_score_config`` ``dose_safety_ceiling``). Nothing else deducts for it.

The typed state exists so that "confirmed over the limit" never gets conflated with
"we could not resolve this exposure"; only the first sets a ceiling:

    none                       flag present, resolved, at/below the UL
    confirmed_over_threshold   resolved above the UL and gate-eligible; sets the
                               Dose ceiling for its band
    material_but_unresolved    exposure is material but the check is incomplete
                               (magnitude absent, or the enricher marked the row
                               ineligible for the UL gate). Routes to review;
                               never claims or caps an unproven exceedance.
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
from scoring_v4.quality_score_config import block as _cfg_block
from serving_frequency import resolve_daily_serving_multiplier, resolve_daily_serving_range

_CEILING = _cfg_block("dose_safety_ceiling", "zero_at_pct")
_FLAG_REFERENCE_FIELDS = {"unit": "ul_unit"}

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

# A row the enricher anchored to a Daily Value is the label's declared nutrient
# declaration — the total an over-limit comparison is scoped to — whatever DSLD
# called it. The name vocabulary above cannot cover that: record 201420
# transcribes Solgar Male Multiple's declared Folate total as "Folic Acid", the
# same text as its own nested 800 mcg breakdown, so the declared total can only
# be identified structurally. The row that carries the %DV is it.
_FOLATE_DECLARED_TOTAL_EXPOSURE_BASES = {
    "daily_value_confirmed_nutrient_amount",
}
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
# actionable; the Dose ceiling's 150% zero band is PharmaGuide scoring policy.
_CONFIRMED_UL_EXCEEDANCE_PCT = 100.0
# Plan D1: the Dose ceiling starts at the UL itself. One meaning, two readers.
if float(_CEILING["exceeds_above_pct"]) != _CONFIRMED_UL_EXCEEDANCE_PCT:
    raise ValueError("dose_safety_ceiling.exceeds_above_pct must equal the confirmed UL exceedance (100%)")


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
    # The same exposure at minimum directed use; keep full precision for policy.
    pct_ul_at_minimum: Optional[float] = None
    # The same exposure at maximum directed use. Equal to pct_ul unless the
    # label prints a daily ceiling above its directions: flags are screened at
    # that ceiling, while Dose judges directed use (Sean 2026-10-29).
    pct_ul_at_directed_maximum: Optional[float] = None
    # The reference nutrient whose limit applies (the label text is `nutrient`).
    reference_nutrient: Optional[str] = None
    # The upper limit compared against and whose population it is (D2).
    ul: Optional[float] = None
    ul_unit: Optional[str] = None
    ul_population: Optional[str] = None


@dataclass(frozen=True)
class DoseSafetyResult:
    """Aggregate outcome for one product."""

    flags: List[DoseSafetyFlag] = field(default_factory=list)
    ignored_flags: List[Dict[str, Any]] = field(default_factory=list)
    conversion_failures: int = 0
    # No daily directions: one Facts-panel serving a day was assessed.
    frequency_defaulted: bool = False
    # Total declared daily caffeine (Dose V4.1 D3); None when none is declared.
    caffeine: Optional[Dict[str, Any]] = None

    def dose_ceiling(self) -> Optional[Dict[str, Any]]:
        """The strongest confirmed exceedance and the public Dose ceiling it sets.

        Exactly 100% is not an exceedance. Minimum-use exceedances retain
        their maximum-use ceiling; optional-only excess gets one deduction
        from earned adequacy (Sean 2026-10-22). Safety flags stay unchanged.
        """
        candidates = [ceiling for ceiling in (self._ul_ceiling(), self._caffeine_ceiling()) if ceiling]
        if not candidates:
            return None
        result = min(candidates, key=lambda ceiling: (ceiling.get("minimum_exceeds") is False, ceiling["cap_public"]))
        if result.get("minimum_exceeds") is False and not self.frequency_defaulted:
            result["deduction_public"] = float(_CEILING["optional_use_deduction_public"])
            # No absolute safety cap in the optional-only case. The existing
            # public Dose maximum is applied by its scoring owner.
            result["cap_public"] = None
        return result

    def _caffeine_ceiling(self) -> Optional[Dict[str, Any]]:
        policy = _CEILING["caffeine"]
        caffeine = self.caffeine or {}
        total = caffeine.get("confirmed_mg_day_max", caffeine.get("total_mg_day_max"))
        operator = caffeine.get("quantity_operator", "=")
        threshold = float(policy["exceeds_above_mg_day"])
        if not isinstance(total, (int, float)) or not (total > threshold or total == threshold and operator == ">"):
            return None
        minimum = caffeine.get("confirmed_mg_day_min", caffeine.get("total_mg_day_min"))
        cap = (0.0 if total >= float(policy["zero_at_mg_day"])
               else float(_CEILING["partial_ceiling_public"]))
        return {
            "cap_public": cap,
            "kind": "caffeine_daily_total",
            "nutrient": "Caffeine",
            "amount_mg_day": round(float(total), 4),
            "amount_mg_day_at_minimum": minimum,
            "minimum_exceeds": (True if minimum is not None and (minimum > threshold or minimum == threshold and operator == ">")
                                else False if minimum is not None and operator == "=" else None),
            "quantity_operator": operator,
            "frequency_defaulted": self.frequency_defaulted,
            "exceeds_above_mg_day": float(policy["exceeds_above_mg_day"]),
            "zero_at_mg_day": float(policy["zero_at_mg_day"]),
            "partial_ceiling_public": float(_CEILING["partial_ceiling_public"]),
        }

    def _ul_ceiling(self) -> Optional[Dict[str, Any]]:
        # Dose is judged at directed use. An exceedance reached only at a
        # printed daily ceiling stays a disclosed safety flag, never a Dose
        # deduction: the ceiling is a limit, not a regimen (Sean 2026-10-29).
        def directed(flag: DoseSafetyFlag) -> Any:
            return flag.pct_ul if flag.pct_ul_at_directed_maximum is None else flag.pct_ul_at_directed_maximum

        confirmed = [flag for flag in self.flags
                     if flag.state == CONFIRMED_OVER_THRESHOLD and isinstance(directed(flag), (int, float))
                     and directed(flag) > float(_CEILING["exceeds_above_pct"])]
        if not confirmed:
            return None
        driver = max(confirmed, key=lambda flag: (
            flag.pct_ul_at_minimum is None or flag.pct_ul_at_minimum > float(_CEILING["exceeds_above_pct"]),
            directed(flag), _norm_text(flag.nutrient)))
        zero_at = float(_CEILING["zero_at_pct"])
        cap = 0.0 if directed(driver) >= zero_at else float(_CEILING["partial_ceiling_public"])
        minimum = driver.pct_ul_at_minimum
        ceiling_context = ({"pct_ul_at_label_ceiling": driver.pct_ul}
                           if directed(driver) != driver.pct_ul else {})
        return {
            "cap_public": cap,
            "kind": "established_upper_limit",
            "label_nutrient": driver.nutrient,
            "ul": driver.ul,
            "ul_unit": driver.ul_unit,
            "ul_population": driver.ul_population or "general adult",
            "nutrient": driver.reference_nutrient or driver.nutrient,
            "canonical_id": driver.canonical_id,
            "pct_ul": directed(driver),
            **ceiling_context,
            "pct_ul_at_minimum": minimum,
            "minimum_exceeds": (minimum > float(_CEILING["exceeds_above_pct"])) if minimum is not None else None,
            "frequency_defaulted": self.frequency_defaulted,
            "exceeds_above_pct": float(_CEILING["exceeds_above_pct"]),
            "zero_at_pct": zero_at,
            "partial_ceiling_public": float(_CEILING["partial_ceiling_public"]),
        }

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
                    "pct_ul_at_minimum": flag.pct_ul_at_minimum,
                }
                for flag in self.flags
            ],
            "caffeine": self.caffeine,
            "dose_ceiling": self.dose_ceiling(),
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


def resolve_dose_safety(product: Dict[str, Any]) -> DoseSafetyResult:
    """Return the production-scoped result, or evaluate for a direct caller."""
    active = _ACTIVE_RESULT.get()
    if active is not None:
        return active
    return evaluate_dose_safety(product)


def dose_safety_consumer_explanation(
    state_counts: Mapping[str, Any] | None,
) -> Optional[str]:
    """Return honest consumer copy for one typed dose-safety summary.

    A ceiling alone cannot distinguish confirmed excess from an
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

    The declared total is identified by structure, not by name alone: labels and
    DSLD both transcribe it inconsistently (record 201420 names the declared
    Folate total ``Folic Acid``, exactly like the breakdown nested under it), so
    a parent-name vocabulary cannot be the only evidence. The row the enricher
    anchored to a Daily Value is the declaration; failing that, the
    declared-total (DFE) basis is. A shape that cannot be singled out — two
    Daily-Value-anchored rows, or several differently named DFE rows — is left
    unreconciled, because summing is the conservative answer there.

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
    # Current enrichment has already resolved parent/component ownership.
    # Numeric/name similarity may only reconcile legacy unqualified artifacts;
    # it cannot discard distinct source-owned exposures in a current sum.
    if rows and all(row.get("source_label_key") and row.get("dose_role") for row in rows):
        return False
    if len(rows) < 2:
        return False

    # Parse every contributing row before choosing the declared total: which row
    # owns the total is decided across the whole set, not row by row.
    parsed: List[Tuple[str, str, float, bool, bool]] = []
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
        parsed.append((
            name,
            basis,
            amount * multiplier,
            _norm_text(row.get("ul_exposure_basis"))
            in _FOLATE_DECLARED_TOTAL_EXPOSURE_BASES,
            name in _FOLATE_PARENT_NAMES or name == nutrient,
        ))
    if len(parsed) < 2:
        return False

    # The declared total is identified by the strongest evidence available, in
    # this order, and only when that evidence is unambiguous:
    #
    #   1. the label names the row as the nutrient total;
    #   2. exactly one row is anchored to a Daily Value — so it *is* the
    #      nutrient declaration, however DSLD transcribed its name;
    #   3. the rows stated in the declared-total (DFE) basis all carry one name,
    #      so they are one printed row emitted several times (the same
    #      serving-variant shape 243808 already relies on).
    #
    # A shape this contract cannot single out — two Daily-Value-anchored rows,
    # or several differently named DFE rows — is left unreconciled. Summing
    # them is conservative, and declining is the only honest answer.
    def _is_daily_value_total(row: Tuple[str, str, float, bool, bool]) -> bool:
        return row[3]

    named_totals = [
        index for index, row in enumerate(parsed) if row[4]
    ]
    daily_value_totals = [
        index for index, row in enumerate(parsed) if _is_daily_value_total(row)
    ]
    declared_basis_totals = [
        index
        for index, row in enumerate(parsed)
        if row[1] == _FOLATE_BASIS_DFE
    ]

    parent_index: Optional[int] = None
    if named_totals:
        # A declared total contains the components it discloses, so when a label
        # names more than one row as the total the largest owns it.
        parent_index = max(named_totals, key=lambda index: parsed[index][2])
    elif len(daily_value_totals) == 1:
        parent_index = daily_value_totals[0]
    elif declared_basis_totals:
        names = {parsed[index][0] for index in declared_basis_totals}
        if len(names) == 1:
            parent_index = max(
                declared_basis_totals, key=lambda index: parsed[index][2]
            )
    if parent_index is None:
        return False

    _parent_name, parent_basis, parent_amount = parsed[parent_index][:3]
    form_rows: List[Tuple[str, str, float]] = [
        (name, basis, normalized)
        for index, (name, basis, normalized, _dv, _parent_name) in enumerate(parsed)
        if index != parent_index
        and any(token in name for token in _FOLATE_FORM_TOKENS)
    ]
    if not form_rows:
        return False
    # One exposure can only be recognised within a single dose basis.
    if len({parent_basis, *(basis for _name, basis, _amount in form_rows)}) > 1:
        return False

    # A label prints ONE row per disclosed form. DSLD can emit that single
    # printed row more than once when it carries several serving-size variants
    # (GNC Bulk 1340 243808 does exactly this), which would otherwise charge the
    # same form twice. Collapse repeated declarations of the same form within
    # the declared-total basis before comparing magnitudes.
    dfe_form_totals: Dict[str, float] = {}
    mass_form_total = 0.0
    for name, basis, normalized in form_rows:
        if basis == _FOLATE_BASIS_DFE:
            dfe_form_totals[name] = max(dfe_form_totals.get(name, 0.0), normalized)
        else:
            mass_form_total += normalized
    form_sum = sum(dfe_form_totals.values()) + mass_form_total
    if form_sum <= 0:
        return False

    tolerance = max(
        _FOLATE_RECONCILE_ABS_TOLERANCE,
        parent_amount * _FOLATE_RECONCILE_REL_TOLERANCE,
    )
    if abs(parent_amount - form_sum) <= tolerance:
        return True

    # A declared DFE total may itemise only PART of itself, in which case the
    # disclosed form is a component of that total rather than a second
    # exposure (Pure Encapsulations 246430 declares 1667 mcg DFE and discloses
    # the 400 mcg of folic acid already inside it). Only a declared-total (DFE)
    # basis supports that reading: a mass-basis panel itemises form masses,
    # where a small child beside a large parent is not evidence of inclusion.
    return (
        parent_basis == _FOLATE_BASIS_DFE
        and form_sum <= parent_amount + tolerance
    )


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


def _classify(flag: Dict[str, Any], minimum_share: float = 1.0,
              directed_ratio: tuple[float, float] = (1.0, 1.0)) -> DoseSafetyFlag:
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
        )

    if pct_ul is not None and pct_ul <= _CONFIRMED_UL_EXCEEDANCE_PCT:
        return DoseSafetyFlag(
            state=NONE,
            nutrient=nutrient,
            canonical_id=canonical_id,
            pct_ul=pct_ul,
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
        )

    if pct_ul is None:
        return DoseSafetyFlag(
            state=MATERIAL_BUT_UNRESOLVED,
            nutrient=nutrient,
            canonical_id=canonical_id,
            pct_ul=None,
            reason=_norm_text(flag.get("ul_gate_ineligible_reason")) or REASON_PCT_UL_NOT_RESOLVED,
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
        )

    return DoseSafetyFlag(
        state=CONFIRMED_OVER_THRESHOLD,
        nutrient=nutrient,
        canonical_id=canonical_id,
        pct_ul=pct_ul,
        pct_ul_at_minimum=pct_ul * minimum_share,
        pct_ul_at_directed_maximum=pct_ul * directed_ratio[0] / directed_ratio[1],
        reference_nutrient=str(flag.get("reference_nutrient") or "") or None,
        ul=_as_float(flag.get("ul"), None),
        # The flag's own reference unit, projected from the rda_ul_data record.
        ul_unit={name: flag.get(key) for key, name in _FLAG_REFERENCE_FIELDS.items()}.get("ul_unit") or None,
        ul_population=(flag.get("ul_population") or {}).get("label")
        if isinstance(flag.get("ul_population"), Mapping) else None,
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


def evaluate_dose_safety(product: Dict[str, Any]) -> DoseSafetyResult:
    """Classify every safety flag on a product (flags are at maximum daily use).

    Never raises. Malformed entries are contained, not guessed at.
    """
    rda_ul = product.get("rda_ul_data") if isinstance(product, dict) else None
    raw_flags = _safe_list(rda_ul.get("safety_flags")) if isinstance(rda_ul, dict) else []

    flags: List[DoseSafetyFlag] = []
    ignored: List[Dict[str, Any]] = []
    conversion_failures = 0
    record = product if isinstance(product, dict) else {}
    low, high, defaulted = resolve_daily_serving_range(record)
    # Flags are screened at conservative exposure: the label's printed daily
    # ceiling when it has one, else the directed maximum (the same number).
    exposure = resolve_daily_serving_multiplier(record)
    minimum_share = (low / exposure) if exposure else 1.0

    for raw in raw_flags:
        if not isinstance(raw, dict):
            continue
        # Unit ratio without a ceiling, so those flags keep their exact values.
        classified = _classify(raw, minimum_share, (high, exposure) if exposure and exposure != high else (1.0, 1.0))
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

    caffeine = _declared_daily_caffeine(product) if isinstance(product, dict) else None
    if caffeine and caffeine["unknown_rows"]:
        flags.append(DoseSafetyFlag(
            state=MATERIAL_BUT_UNRESOLVED, nutrient="Caffeine", canonical_id="caffeine",
            reason="caffeine_daily_total_not_exact",
        ))
    return DoseSafetyResult(
        flags=flags,
        ignored_flags=ignored,
        conversion_failures=conversion_failures,
        frequency_defaulted=bool(defaulted),
        caffeine=caffeine,
    )


def _declared_caffeine_rows(product: Dict[str, Any]) -> tuple[list, dict, int]:
    """Caffeine's analyte total, preserving declarations and confirmed bounds.

    Ingredient-count deduplication is not analyte deduplication: a quantified
    caffeine projection from guarana is the caffeine exposure even though its
    carrier is already an ingredient. A declared total owns its components.
    Qualified or missing amounts never become an exact daily total; only their
    confirmed lower bound can establish a ceiling.
    """
    from scoring_input_contract import get_scoring_ingredients, is_lent_blend_mass, source_linked_rows
    from scoring_v4.exposure import row_exposure
    from scoring_v4.modules.sports_helpers import CAFFEINE_CANONICALS

    try:
        rows = [row for row in get_scoring_ingredients(product, strict=True).rows if isinstance(row, dict)]
    except Exception:
        return [], {}, 0
    caffeine = [row for row in rows if _norm_text(row.get("canonical_id")) in CAFFEINE_CANONICALS]
    if not caffeine:
        return [], {}, 0
    candidates = [row for row in caffeine if not (row.get("is_compound_duplicate") or is_lent_blend_mass(row))]
    counted = []
    for row in candidates:
        # Skip a projection only if its physical source already supplies counted
        # caffeine. A non-caffeine carrier cannot stand in for its analyte.
        if row.get("scoring_input_kind") == "product_level_evidence" and any(
            any(other is candidate for candidate in candidates)
            and other.get("scoring_input_kind") != "product_level_evidence"
            and _norm_text(other.get("canonical_id")) in CAFFEINE_CANONICALS
            and not other.get("is_compound_duplicate") and not is_lent_blend_mass(other)
            for other in source_linked_rows(product, row, candidates)
        ):
            continue
        counted.append(row)

    totals = [row for row in counted if row.get("is_parent_total")]
    excluded = set()
    total_bounds = {}
    for total in totals:
        name = _norm_text(total.get("name") or total.get("standard_name"))
        path = str(total.get("raw_source_path") or "")
        parent_exposure = row_exposure(product, total, basis="per_use", unit="mg")
        children = [row for row in counted if row is not total and not row.get("is_parent_total") and (
            name and _norm_text(row.get("parent_blend")) == name
            or path and str(row.get("raw_source_path") or "").startswith(path + ".")
            # The enricher also marks an exact top-level/nested restatement as
            # a parent even when its wrapper has a different name. Keep the
            # duplicate in that source group, not every independent caffeine.
            or row.get("is_nested_ingredient") and name == _norm_text(row.get("name") or row.get("standard_name"))
            and parent_exposure.exact
            and (child_exposure := row_exposure(product, row, basis="per_use", unit="mg")).exact
            and child_exposure.per_serving_amount == parent_exposure.per_serving_amount
        )]
        # Older scoring rows retain the total marker without the child links.
        # A sole unscoped total owns the analyte declaration, including a partial
        # or unquantified breakdown. Scoped totals leave independent sources in.
        if not children and len(totals) == 1:
            children = [row for row in counted if row is not total]
        if not parent_exposure.exact:
            # An upper-qualified or unread total may still disclose a useful
            # component floor. They describe one exposure: take the stronger
            # bound, rather than adding total and components or losing either.
            child_exposures = [row_exposure(product, row, basis="per_use", unit="mg") for row in children]
            parent_floor = parent_exposure.minimum or 0.0
            child_floor = sum(exposure.minimum or 0.0 for exposure in child_exposures)
            floor = max(parent_floor, child_floor)
            strict = (parent_floor == floor and parent_exposure.quantity_operator == ">"
                      or child_floor == floor and any(exposure.quantity_operator == ">"
                                                     and exposure.minimum is not None for exposure in child_exposures))
            total_bounds[id(total)] = (floor, strict)
        excluded.update(id(row) for row in children)
    counted = [row for row in counted if id(row) not in excluded]

    return counted, total_bounds, len(caffeine)


def _declared_daily_caffeine(product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Daily safety totals from the shared caffeine analyte declarations."""
    from scoring_v4.exposure import row_exposure

    counted, total_bounds, source_count = _declared_caffeine_rows(product)
    if not source_count:
        return None
    low, high, _defaulted = resolve_daily_serving_range(product)
    per_serving_lower = 0.0
    strict_lower = False
    unknown = 0
    for row in counted:
        if id(row) in total_bounds:
            floor, strict = total_bounds[id(row)]
            per_serving_lower += floor
            strict_lower = strict_lower or strict
            unknown += 1
            continue
        exposure = row_exposure(product, row, basis="per_use", unit="mg")
        operator = exposure.quantity_operator
        if exposure.minimum is None:
            unknown += 1
            continue
        per_serving_lower += exposure.minimum
        if operator not in {"", "="}:
            unknown += 1
            strict_lower = strict_lower or operator == ">"
    confirmed_min = per_serving_lower * low
    confirmed_max = per_serving_lower * high
    return {
        "total_mg_day_min": confirmed_min if not unknown else None,
        "total_mg_day_max": confirmed_max if not unknown else None,
        "confirmed_mg_day_min": confirmed_min,
        "confirmed_mg_day_max": confirmed_max,
        "quantity_operator": ">" if strict_lower else ">=" if unknown else "=",
        "rows": len(counted), "unknown_rows": unknown,
        "excluded_duplicate_rows": source_count - len(counted),
    }
