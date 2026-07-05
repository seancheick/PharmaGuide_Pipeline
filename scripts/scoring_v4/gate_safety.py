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
            v4 score with score=None. The v4 `anchored` flag is
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
        clean_label_hits: Flagged additives (e.g. titanium dioxide) that
            INFORM + carry a small graduated penalty but do NOT drive the
            verdict. Orthogonal to the safety-verdict lane: a product can
            be SAFE and still carry clean_label_hits. Consumed by the
            six-pillar quality_score (safety_hygiene penalty) and emitted
            to Flutter as clean_label_flags_v4. NEVER touches the verdict.
    """

    verdict: Optional[str] = None
    short_circuits_scoring: bool = False
    blocking_reason: Optional[str] = None
    matched_substance: Optional[str] = None
    safety_signals: List[str] = field(default_factory=list)
    needs_review: bool = False
    clean_label_hits: List[Dict[str, Any]] = field(default_factory=list)


# NOTE: match-type → trust mapping moved to the SafetySignal v1 kernel
# (identity/safety.py::match_resolution_for). This gate consumes the stable
# `match_resolution` enum (confirmed / likely / review_only / low_confidence)
# and MUST NOT branch on raw matcher names — enforced by
# test_gate_safety_has_no_raw_match_type.


def _safe_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _safe_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _as_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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


def _ingredient_safety_terms(
    ingredient: Dict[str, Any],
) -> tuple[str, Optional[str], List[str]]:
    """Banned/recalled evidence terms for the resolver, aligned with the export.

    Returns (raw_name, standard_name, additional_terms). The additional terms
    add ``raw_source_text`` AND every ``forms[].name`` / ``forms[].prefix`` —
    mirroring ``build_final_db._active_banned_recall_evidence_terms`` so the v4
    gate sees the SAME banned signal as the export's ``has_banned_substance``.

    Why this exists: a banned *form* of a generic active (Boron carrying the
    banned salt ``Sodium Tetraborate``) or a banned substance the cleaner moved
    into ``raw_source_text`` while leaving a generic ``name`` (Partially
    Hydrogenated Soybean Oil) lives ONLY in forms/raw_source_text. The earlier
    name-only path missed them, so export-banned products scored SAFE/CAUTION
    under v4. The resolver's banned index and the export's index are built from
    the same filtered entries with the same normalizer, so feeding the same
    terms yields parity. Purely additive — no existing term is dropped.

    NOTE: kept in sync with the export term builder by intent. If the export's
    evidence-term policy changes (e.g. the mapped-active standardName rule),
    revisit this helper and the parity coverage in
    test_v4_banned_form_evidence_gate.py / test_v4_safety_parity_release.py.
    """
    raw_name, standard_name = _ingredient_name_terms(ingredient)
    extra: List[str] = []
    raw_source_text = ingredient.get("raw_source_text")
    if raw_source_text:
        extra.append(str(raw_source_text))
    for form in _safe_list(ingredient.get("forms")):
        if isinstance(form, dict):
            for key in ("name", "prefix"):
                value = form.get(key)
                if value:
                    extra.append(str(value))
        elif form:
            extra.append(str(form))
    return raw_name, standard_name, extra


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
            raw_name, standard_name, extra_terms = _ingredient_safety_terms(ingredient)
            if not raw_name and not extra_terms:
                continue
            try:
                resolution = resolver.resolve(
                    raw_name=raw_name,
                    standard_name=standard_name,
                    additional_terms=extra_terms,
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


def _iter_resolver_clean_label_hits(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Collect clean-label additive concerns (e.g. titanium dioxide / E171).

    A SEPARATE pass from `_iter_resolver_safety_hits` on purpose: clean-label
    concerns are orthogonal to the safety verdict. Titanium dioxide as an
    `excipient_acceptable` coating resolves with `is_safety_concern=True` yet
    is exempted from CAUTION downstream — but it is ALSO an
    `is_clean_label_concern`, which this lane surfaces for the six-pillar
    penalty + the Flutter flag. Keeping this independent guarantees the
    verdict path (`_iter_resolver_safety_hits`) stays byte-identical.

    Never raises. Returns one hit per flagged additive row with enough fields
    for the graduated safety_hygiene penalty (tier, penalty_base, role) and
    the consumer-facing flag (consumer_note, status).
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
            if not resolution.is_clean_label_concern:
                continue
            hits.append({
                "name": resolution.display_label or raw_name,
                "standard_name": standard_name or resolution.display_label or raw_name,
                "role": role,
                "tier": resolution.clean_label_tier,
                "consumer_note": resolution.clean_label_note,
                "penalty_base": resolution.clean_label_penalty_base,
                "status": resolution.regulatory_status,
                "matched_rule_id": resolution.matched_rule_id,
                # Step 3b: structured citation (surfaced from the entry's verified refs)
                "eu_status": resolution.clean_label_eu_status,
                "regulation_citation": resolution.clean_label_citation,
                "regulation_url": resolution.clean_label_url,
            })
    return hits


def _append_signal(result: SafetyResult, code: str) -> None:
    if code not in result.safety_signals:
        result.safety_signals.append(code)


def _dose_mg(row: Dict[str, Any]) -> Optional[float]:
    quantity = _as_float(
        row.get("quantity")
        if row.get("quantity") is not None
        else row.get("amount")
        if row.get("amount") is not None
        else row.get("dose")
    )
    if quantity is None or quantity <= 0:
        return None
    unit = _norm(row.get("unit_normalized") or row.get("unit"))
    compact = unit.replace(" ", "")
    if compact in {"mg", "milligram", "milligrams", "milligram(s)"}:
        return quantity
    if compact in {"g", "gram", "grams", "gram(s)"}:
        return quantity * 1000.0
    if compact in {"mcg", "ug", "µg", "μg", "microgram", "micrograms", "microgram(s)"}:
        return quantity / 1000.0
    return None


def _iter_active_rows(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for key in ("activeIngredients", "display_ingredients"):
        for row in _safe_list(product.get(key)):
            if isinstance(row, dict):
                rows.append(row)
    iqd = _safe_dict(product.get("ingredient_quality_data"))
    for key in ("ingredients_scorable", "ingredients_skipped"):
        for row in _safe_list(iqd.get(key)):
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _is_caffeine_row(row: Dict[str, Any]) -> bool:
    text = " ".join(
        _norm(row.get(field))
        for field in (
            "canonical_id",
            "name",
            "standard_name",
            "standardName",
            "raw_source_text",
            "matched_form",
            "form_name",
        )
    )
    return "caffeine" in text


def _is_stimulant_context(product: Dict[str, Any]) -> bool:
    fields = [
        product.get("product_name"),
        product.get("fullName"),
        product.get("primary_type"),
        _safe_dict(product.get("supplement_taxonomy")).get("primary_type"),
    ]
    text = " ".join(_norm(value) for value in fields)
    if any(
        token in text
        for token in (
            "pre_workout",
            "pre workout",
            "pre-workout",
            "energy",
            "thermogenic",
            "fat burner",
            "stimulant",
        )
    ):
        return True
    for blend in _safe_list(product.get("proprietary_blends")):
        if not isinstance(blend, dict):
            continue
        blend_text = " ".join(_norm(blend.get(field)) for field in ("name", "raw_name", "purpose"))
        if any(token in blend_text for token in ("energy", "stimulant", "pre workout", "pre-workout", "thermogenic")):
            return True
    return False


# Opaque-blend stimulant detection (P0 fix). A proprietary blend with
# disclosure_level in {none, partial} HIDES its per-ingredient doses, so a
# stimulant inside it is undisclosed — the user cannot judge safe use.
_STRONG_STIM_BLEND_NAMES = (
    "stimulant", "thermogenic", "fat burner", "fat-burner",
    "pre workout", "pre-workout", "preworkout",
)
_ENERGY_BLEND_NAMES = ("energy", "metabolism", "metabolic", "weight loss", "weight-loss")
_HIDDEN_STIMULANT_TOKENS = (
    "guarana", "yerba mate", "synephrine", "green tea", "green coffee",
    "kola nut", "kola seed", "theacrine", "dmaa", "bitter orange", "ephedra",
)


def _blend_children_text(blend: Dict[str, Any]) -> str:
    parts = []
    for child in _safe_list(blend.get("child_ingredients")):
        if isinstance(child, dict):
            parts.append(_norm(child.get("name") or child.get("ingredient")
                               or child.get("standard_name") or child.get("raw_source_text")))
        else:
            parts.append(_norm(child))
    return " ".join(parts)


def _has_undisclosed_stimulant_blend(product: Dict[str, Any]) -> bool:
    """True when an OPAQUE proprietary blend (disclosure none/partial) hides a
    stimulant whose dose the consumer cannot see. Precise (no over-warning on
    benign B-vitamin 'energy' blends): fires only when the blend is named for a
    stimulant, OR caffeine is among its hidden children, OR an energy/metabolism
    blend hides another stimulant (guarana/green tea/synephrine/...)."""
    for blend in _safe_list(product.get("proprietary_blends")):
        if not isinstance(blend, dict):
            continue
        if _norm(blend.get("disclosure_level") or blend.get("disclosure")) not in ("none", "partial"):
            continue
        name = _norm(blend.get("name") or blend.get("raw_name"))
        kids = _blend_children_text(blend)
        if any(token in name for token in _STRONG_STIM_BLEND_NAMES):
            return True
        if "caffeine" in kids:
            return True
        if any(token in name for token in _ENERGY_BLEND_NAMES) and \
                any(token in kids for token in _HIDDEN_STIMULANT_TOKENS):
            return True
    return False


def _apply_stimulant_policy(result: SafetyResult, product: Dict[str, Any]) -> None:
    """Surface caffeine safety only when it is a consumer-action issue.

    Moderate disclosed caffeine is not a global CAUTION. A high per-serving
    caffeine dose (>400 mg) or undisclosed caffeine in a stimulant/pre-workout
    context is different: the user cannot judge safe use without taking action.
    """
    caffeine_rows = [row for row in _iter_active_rows(product) if _is_caffeine_row(row)]
    if not caffeine_rows:
        # No SURFACED caffeine row — but a stimulant may be HIDDEN inside an
        # opaque proprietary blend (undisclosed dose). That is exactly the
        # consumer-action concern the stimulant policy exists to catch. P0 fix:
        # close the false-negative where hidden-in-blend caffeine read SAFE.
        if _has_undisclosed_stimulant_blend(product):
            result.verdict = _max_verdict(result.verdict, "CAUTION")
            result.needs_review = True
            _append_signal(result, "STIMULANT_UNDISCLOSED_BLEND")
        return

    doses = [_dose_mg(row) for row in caffeine_rows]
    known_doses = [dose for dose in doses if dose is not None]
    unknown_dose = len(known_doses) < len(caffeine_rows)

    if known_doses:
        total_mg = sum(known_doses)
        if total_mg > 400.0:
            result.verdict = _max_verdict(result.verdict, "CAUTION")
            _append_signal(result, "STIMULANT_CAFFEINE_HIGH_DOSE")
        elif total_mg > 300.0:
            _append_signal(result, "STIMULANT_CAFFEINE_ELEVATED_DOSE")
        else:
            _append_signal(result, "STIMULANT_CAFFEINE_MODERATE_DOSE")

    if unknown_dose:
        result.needs_review = True
        if _is_stimulant_context(product):
            result.verdict = _max_verdict(result.verdict, "CAUTION")
            _append_signal(result, "STIMULANT_CAFFEINE_UNDISCLOSED_PREWORKOUT")
        else:
            _append_signal(result, "STIMULANT_CAFFEINE_UNDISCLOSED_REVIEW")


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


def _apply_ul_dose_policy(result: SafetyResult, product: Dict[str, Any]) -> None:
    """UL dose severity → verdict (P0-1b).

    A GATE-ELIGIBLE over-UL flag (``pct_ul >= 150``) cannot ship SAFE:
      - 150–199% → CAUTION
      - >= 200%  → CAUTION + a critical dose signal
    Dose excess NEVER escalates past CAUTION — BLOCKED/UNSAFE stay for
    banned/recalled/adulterated substances.

    Flags marked ``ul_gate_eligible: False`` (compound_mass_not_elemental — e.g.
    Magtein, whose label states compound not elemental mass) are excluded so the
    gate never fires a false CAUTION. Missing key defaults to eligible
    (back-compat with older enrich output). ``pct_ul is None`` is not evaluable
    and never treated as over.
    """
    rda_ul = _safe_dict(product.get("rda_ul_data"))
    max_pct = 0.0
    for flag in _safe_list(rda_ul.get("safety_flags")):
        if not isinstance(flag, dict):
            continue
        if flag.get("ul_gate_eligible") is False:
            continue
        pct = _as_float(flag.get("pct_ul"))
        if pct is None:
            continue
        if pct >= 150.0 and pct > max_pct:
            max_pct = pct
    if max_pct >= 150.0:
        result.verdict = _max_verdict(result.verdict, "CAUTION")
        _append_signal(
            result,
            "DOSE_OVER_UL_CRITICAL" if max_pct >= 200.0 else "DOSE_OVER_UL_CAUTION",
        )


def evaluate_safety_gate(product: Dict[str, Any]) -> SafetyResult:
    """Evaluate the v4 Layer 1 safety gate on an enriched product.

    Never raises. Resilient to missing / malformed fields. Returns a
    SafetyResult — the caller (v4 entry point) decides how to apply
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

    _apply_stimulant_policy(result, product)
    _apply_ul_dose_policy(result, product)

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

    # Clean-label additive flags (e.g. titanium dioxide). Collected on a
    # SEPARATE lane that never touches the verdict — inform + small graduated
    # penalty, applied later by the six-pillar quality_score. Verdict-independent.
    result.clean_label_hits = _iter_resolver_clean_label_hits(product)

    # short_circuits_scoring is purely a function of verdict severity.
    result.short_circuits_scoring = result.verdict in {"BLOCKED", "UNSAFE"}
    return result
