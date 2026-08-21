#!/usr/bin/env python3
"""Canonical source-row reconciliation for scoring and export.

The ledger is deliberately independent of catalog eligibility.  Callers may
build and summarize it in shadow mode, while release code can additionally run
``validate_row_ledger`` as a strict gate.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Iterable, Mapping, Optional


ROW_LEDGER_REQUIRED_FIELDS = frozenset({
    "row_ref",
    "source_section",
    "source_role",
    "score_eligible",
    "mapping_disposition",
    "reason_code",
    "final_destination",
    "owner_row_ref",
})

ROW_LEDGER_DESTINATIONS = frozenset({
    "ingredients",
    "inactive_ingredients",
    "display_ingredients",
    "label_ledger_omissions",
    "owner_row",
})

ROW_LEDGER_DISPOSITIONS = frozenset({
    "mapped_score_active",
    "unresolved_score_active",
    "excluded_non_scorable",
    "source_inactive_row",
    "active_reclassified_inactive",
    "owned_component",
    "explicit_omission",
    "unresolved_source_row",
})

_ACTIVE_SECTIONS = frozenset({"active", "activeingredients"})
_INACTIVE_SECTIONS = frozenset({"inactive", "inactiveingredients"})
_NON_SCORABLE_DISPLAY_REASONS = {
    "nutrition_fact": "DROPPED_NUTRITION_FACT",
    "structural_container": "DROPPED_STRUCTURAL_HEADER",
    "summary_wrapper": "DROPPED_SUMMARY_WRAPPER",
}
_OWNER_SUFFIX = re.compile(r"\.(?:forms|nestedRows)\[\d+\]$")


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _section(value: Any) -> str:
    return _text(value)


def _is_active_section(value: Any) -> bool:
    return _section(value).lower() in _ACTIVE_SECTIONS


def _is_inactive_section(value: Any) -> bool:
    return _section(value).lower() in _INACTIVE_SECTIONS


def _row_ref(row: Mapping[str, Any]) -> str:
    return _text(row.get("raw_source_path") or row.get("row_ref"))


def _owner_ref(row_ref: str) -> Optional[str]:
    match = _OWNER_SUFFIX.search(row_ref)
    if not match:
        return None
    owner = row_ref[: match.start()]
    return owner or None


def _index_by_ref(rows: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        ref = _row_ref(row)
        if ref and ref not in result:
            result[ref] = row
    return result


def _canonical_id(*rows: Optional[Mapping[str, Any]]) -> Optional[str]:
    for row in rows:
        if not row:
            continue
        for key in (
            "canonical_id",
            "analysis_canonical_id",
            "resolved_canonical_id",
            "canonicalId",
        ):
            value = _text(row.get(key))
            if value:
                return value
        analysis = row.get("analysis")
        if isinstance(analysis, Mapping):
            value = _text(
                analysis.get("canonical_id")
                or analysis.get("canonicalId")
            )
            if value:
                return value
    return None


def _omission_reason(row: Mapping[str, Any]) -> str:
    return _text(
        row.get("omission_reason")
        or row.get("reason_code")
        or row.get("reason")
        or "EXPLICIT_LABEL_OMISSION"
    ).upper()


def build_row_ledger(
    source_rows: Iterable[Mapping[str, Any]],
    display_rows: Iterable[Mapping[str, Any]],
    omissions: Iterable[Mapping[str, Any]],
    ingredients: Iterable[Mapping[str, Any]],
    inactive_ingredients: Iterable[Mapping[str, Any]],
    *,
    scoring_rows: Iterable[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Build exactly one reconciliation record per supplied source row.

    Duplicate source references are intentionally retained.  The strict
    validator reports them; silently deduplicating here would hide source
    corruption.
    """

    display_by_ref = _index_by_ref(display_rows)
    omission_by_ref = _index_by_ref(omissions)
    ingredient_by_ref = _index_by_ref(ingredients)
    inactive_by_ref = _index_by_ref(inactive_ingredients)
    scoring_by_ref = _index_by_ref(scoring_rows)
    ledger: list[dict[str, Any]] = []

    for source in source_rows:
        if not isinstance(source, Mapping):
            ledger.append({
                "row_ref": "",
                "source_label": "",
                "source_section": "",
                "source_role": "unknown",
                "score_eligible": False,
                "mapping_disposition": "unresolved_source_row",
                "reason_code": "INVALID_SOURCE_ROW",
                "final_destination": "label_ledger_omissions",
                "owner_row_ref": None,
                "canonical_id": None,
            })
            continue

        ref = _row_ref(source)
        section = _section(source.get("source_section"))
        display = display_by_ref.get(ref)
        omission = omission_by_ref.get(ref)
        ingredient = ingredient_by_ref.get(ref)
        inactive = inactive_by_ref.get(ref)
        scoring = scoring_by_ref.get(ref)
        owner = _owner_ref(ref)
        is_form = ".forms[" in ref
        is_nested = ".nestedRows[" in ref
        display_type = _text(display.get("display_type")) if display else ""
        display_disposition = (
            _text(display.get("display_disposition")) if display else ""
        )
        score_included = (
            display.get("score_included") is True if display else False
        )
        cleaner_eligibility = source.get("score_eligible_by_cleaner")
        if not isinstance(cleaner_eligibility, bool):
            cleaner_eligibility = None
        cleaner_exclusion = _text(
            source.get("score_exclusion_reason")
            or source.get("identity_decision_reason")
            or source.get("skip_reason")
        ).upper()
        canonical_id = _canonical_id(ingredient, scoring, display, source)

        if is_form:
            role = "owned_form"
            eligible = False
            disposition = "owned_component"
            reason = "OWNED_FORM_COMPONENT"
            destination = "owner_row"
        elif _is_inactive_section(section):
            role = "source_inactive"
            eligible = False
            disposition = "source_inactive_row"
            reason = "SOURCE_INACTIVE_ROW"
            destination = "inactive_ingredients"
        elif _is_active_section(section) and (
            inactive is not None or display_type == "inactive_ingredient"
        ):
            role = "active_reclassified_inactive"
            eligible = False
            disposition = "active_reclassified_inactive"
            reason = "ACTIVE_RECLASSIFIED_AS_INACTIVE"
            destination = "inactive_ingredients"
        elif display_type in _NON_SCORABLE_DISPLAY_REASONS:
            role = display_type
            eligible = False
            disposition = "excluded_non_scorable"
            reason = _NON_SCORABLE_DISPLAY_REASONS[display_type]
            destination = "display_ingredients"
        elif omission is not None:
            role = "explicit_omission"
            eligible = False
            disposition = "explicit_omission"
            reason = _omission_reason(omission)
            destination = "label_ledger_omissions"
        elif is_nested and cleaner_eligibility is False:
            # Cleaner eligibility owns the scoring denominator. Display rows
            # may still carry ``score_included=True`` so the app can render a
            # mapped blend child with analysis; that presentation flag must
            # never promote the child into an independent scoring input.
            role = "owned_child"
            eligible = False
            disposition = "owned_component"
            reason = cleaner_exclusion or "OWNED_NESTED_COMPONENT"
            destination = (
                "display_ingredients" if display is not None else "owner_row"
            )
        elif is_nested and not score_included:
            role = "owned_child"
            eligible = False
            disposition = "owned_component"
            reason = "OWNED_NESTED_COMPONENT"
            destination = "owner_row"
        elif _is_active_section(section) and cleaner_eligibility is False:
            role = "excluded_active"
            eligible = False
            disposition = "excluded_non_scorable"
            reason = cleaner_exclusion or "CLEANER_EXCLUDED_ACTIVE"
            destination = (
                "display_ingredients"
                if display is not None
                else "label_ledger_omissions"
            )
        elif _is_active_section(section) and cleaner_eligibility is True:
            role = "score_active"
            eligible = True
            if canonical_id:
                disposition = "mapped_score_active"
                reason = "MAPPED_CANONICAL_IDENTITY"
                destination = (
                    "ingredients" if ingredient is not None
                    else "display_ingredients"
                )
            else:
                disposition = "unresolved_score_active"
                reason = "UNRESOLVED_CANONICAL_IDENTITY"
                destination = "display_ingredients"
        elif _is_active_section(section) and ingredient is not None:
            role = "score_active"
            eligible = True
            if canonical_id:
                disposition = "mapped_score_active"
                reason = "MAPPED_CANONICAL_IDENTITY"
                destination = "ingredients"
            else:
                disposition = "unresolved_score_active"
                reason = "UNRESOLVED_CANONICAL_IDENTITY"
                destination = "display_ingredients"
        elif (
            _is_active_section(section)
            and scoring is not None
            and _text(scoring.get("scoring_input_kind"))
            != "product_level_evidence"
        ):
            role = "score_active"
            eligible = True
            if canonical_id:
                disposition = "mapped_score_active"
                reason = "MAPPED_CANONICAL_IDENTITY"
                destination = "display_ingredients"
            else:
                disposition = "unresolved_score_active"
                reason = "UNRESOLVED_CANONICAL_IDENTITY"
                destination = "display_ingredients"
        elif _is_active_section(section) and display is not None:
            role = "display_only_active"
            eligible = False
            disposition = "excluded_non_scorable"
            reason = (
                _text(display.get("score_exclusion_reason"))
                or _text(display.get("identity_decision_reason"))
                or _text(display.get("skip_reason"))
                or "DISPLAY_ONLY_SOURCE_ROW"
            ).upper()
            destination = "display_ingredients"
        else:
            role = "unresolved_source"
            eligible = _is_active_section(section)
            disposition = (
                "unresolved_score_active" if eligible else "unresolved_source_row"
            )
            reason = (
                "UNRESOLVED_CANONICAL_IDENTITY"
                if eligible
                else "UNEXPLAINED_SOURCE_ROW"
            )
            destination = "label_ledger_omissions"

        ledger.append({
            "row_ref": ref,
            "source_label": _text(
                source.get("raw_source_text")
                or source.get("source_label")
                or source.get("name")
            ),
            "source_section": section,
            "source_role": role,
            "score_eligible": eligible,
            "mapping_disposition": disposition,
            "reason_code": reason,
            "final_destination": destination,
            "owner_row_ref": owner,
            "canonical_id": canonical_id,
            "display_disposition": display_disposition or None,
        })

    return ledger


def summarize_row_ledger(ledger: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = list(ledger)
    eligible = [row for row in rows if row.get("score_eligible") is True]
    mapped = [
        row
        for row in eligible
        if row.get("mapping_disposition") == "mapped_score_active"
    ]
    denominator = len(eligible)
    coverage = len(mapped) / denominator if denominator else None
    return {
        "source_row_count": len(rows),
        "active_source_row_count": sum(
            1 for row in rows if _is_active_section(row.get("source_section"))
        ),
        "score_eligible_count": denominator,
        "mapped_score_eligible_count": len(mapped),
        "mapped_coverage": coverage,
        "mapping_disposition_counts": dict(sorted(Counter(
            _text(row.get("mapping_disposition")) for row in rows
        ).items())),
        "final_destination_counts": dict(sorted(Counter(
            _text(row.get("final_destination")) for row in rows
        ).items())),
        "reason_code_counts": dict(sorted(Counter(
            _text(row.get("reason_code")) for row in rows
        ).items())),
    }


def validate_row_ledger(
    ledger: Any,
    raw_actives_count: Optional[int],
) -> list[dict[str, Any]]:
    """Return deterministic strict-gate findings without raising."""

    if not isinstance(ledger, list):
        return [{"code": "INVALID_LEDGER_TYPE", "message": "row_ledger must be a list"}]

    issues: list[dict[str, Any]] = []
    seen_refs: set[str] = set()
    owner_links: list[tuple[str, str]] = []
    active_source_rows = 0

    def add(code: str, message: str, row_ref: str = "") -> None:
        issue = {"code": code, "message": message}
        if row_ref:
            issue["row_ref"] = row_ref
        issues.append(issue)

    for index, entry in enumerate(ledger):
        if not isinstance(entry, Mapping):
            add("INVALID_LEDGER_ROW", f"row_ledger[{index}] is not an object")
            continue
        missing = sorted(ROW_LEDGER_REQUIRED_FIELDS - set(entry))
        if missing:
            add(
                "MISSING_LEDGER_FIELDS",
                f"row_ledger[{index}] missing fields {missing}",
                _text(entry.get("row_ref")),
            )
            continue

        ref = _text(entry.get("row_ref"))
        if not ref:
            add("EMPTY_ROW_REF", f"row_ledger[{index}] has empty row_ref")
        elif ref in seen_refs:
            add("DUPLICATE_ROW_REF", f"duplicate row_ref {ref!r}", ref)
        else:
            seen_refs.add(ref)

        if (
            _is_active_section(entry.get("source_section"))
            and ref.startswith("ingredientRows[")
        ):
            active_source_rows += 1

        disposition = _text(entry.get("mapping_disposition"))
        destination = _text(entry.get("final_destination"))
        reason = _text(entry.get("reason_code"))
        if disposition not in ROW_LEDGER_DISPOSITIONS:
            add("UNKNOWN_MAPPING_DISPOSITION", f"unknown disposition {disposition!r}", ref)
        if destination not in ROW_LEDGER_DESTINATIONS:
            add("UNKNOWN_FINAL_DESTINATION", f"unknown destination {destination!r}", ref)
        if not reason:
            add("EMPTY_REASON_CODE", "reason_code must be non-empty", ref)
        if not isinstance(entry.get("score_eligible"), bool):
            add("INVALID_SCORE_ELIGIBILITY", "score_eligible must be boolean", ref)
        elif entry.get("score_eligible") is True and disposition != "mapped_score_active":
            add("UNRESOLVED_SCORE_ACTIVE", f"score-eligible row is {disposition!r}", ref)
        if disposition == "mapped_score_active" and destination != "ingredients":
            if destination != "display_ingredients":
                add(
                    "MAPPED_DESTINATION_MISMATCH",
                    f"mapped score row destination is {destination!r}",
                    ref,
                )
        if disposition == "unresolved_source_row":
            add(
                "UNRESOLVED_SOURCE_ROW",
                "source row has no explicit final disposition",
                ref,
            )
        if (
            disposition in {"unresolved_source_row", "explicit_omission"}
            and reason == "DROPPED_PARSE_ERROR"
        ):
            add("PARSE_ERROR_SENTINEL", "parse-error sentinel cannot ship", ref)

        owner_ref = _text(entry.get("owner_row_ref"))
        if owner_ref:
            owner_links.append((ref, owner_ref))

    for ref, owner_ref in owner_links:
        if owner_ref == ref or owner_ref not in seen_refs:
            add("INVALID_OWNER_REF", f"invalid owner_row_ref {owner_ref!r}", ref)

    if raw_actives_count is not None and active_source_rows != raw_actives_count:
        add(
            "ACTIVE_SOURCE_COUNT_MISMATCH",
            f"ledger active count {active_source_rows} != raw_actives_count {raw_actives_count}",
        )

    return issues
