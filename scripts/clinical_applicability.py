"""Apply reviewed clinical scope at one boundary shared by all score consumers.

Matching a nutrient name does not transfer a lozenge trial to a capsule, or a
combination trial to one constituent. The reference registry owns restrictions;
an old enriched match cannot broaden them by carrying a stale success stamp.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any

from serving_frequency import resolve_daily_serving_range


_UNIT_SCALE = {"g": 1000, "gram": 1000, "grams": 1000,
               "mg": 1, "milligram": 1, "milligrams": 1,
               "mcg": .001, "ug": .001, "microgram": .001, "micrograms": .001}


@lru_cache(maxsize=1)
def reviewed_entries() -> dict[str, dict]:
    payload = json.loads((Path(__file__).parent / "data/backed_clinical_studies.json").read_text())
    return {entry["id"]: entry for entry in payload["backed_clinical_studies"]}


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _row_text(row: Mapping, *, source_only: bool = False) -> str:
    if source_only:
        label = row.get("raw_source_text") or row.get("source_label_name")
        if not isinstance(label, str) or not label.strip():
            return ""
        values = [label]
        # Only the cleaner's own source taxonomy may extend the label words: a
        # source-required scope distrusts enrichment-derived form names, so a
        # row without source taxonomy contributes its printed label text alone.
        taxonomy = row.get("raw_taxonomy")
        source_forms = taxonomy.get("forms") if isinstance(taxonomy, Mapping) else None
        forms = source_forms if isinstance(source_forms, list) else []
    else:
        values = [row.get(k) for k in ("name", "raw_source_text", "matched_form", "form_id")]
        forms = row.get("forms")
    if isinstance(forms, list):
        values.extend(f.get("name") for f in forms if isinstance(f, Mapping))
    # Parent/source notation is one linked label assertion: Zinc (as acetate)
    # is zinc acetate. Never assemble this from different ingredient rows.
    return " " + _key(" ".join(str(v) for v in values if v)).replace(" as ", " ") + " "


def _is_exposure_row(row: Mapping) -> bool:
    """Exclude explicit non-exposures without imposing new legacy contracts."""
    if row.get("score_eligible_by_cleaner") is False:
        return False
    if _key(row.get("source_section") or row.get("source")) in {
        "inactive", "inactiveingredients", "other ingredients"
    }:
        return False
    roles = {_key(row.get(field)) for field in ("cleaner_row_role", "role_classification")}
    if roles & {"source descriptor", "inactive", "inactive non scorable", "recognized non scorable"}:
        return False
    return _key(row.get("dose_class")) != "source material mass"


def _valid_policy(policy: Any) -> bool:
    """Validate reviewed constraints before any matching or numeric comparisons."""
    if not isinstance(policy, Mapping) or not isinstance(policy.get("scope"), str):
        return False
    if "studied_population" in policy and not isinstance(policy["studied_population"], str):
        return False
    for field in ("dosage_forms", "required_form_terms", "supported_outcomes", "source_pmids",
                  "excluded_canonical_ids", "excluded_form_terms"):
        if field in policy and (
            not isinstance(policy[field], list)
            or any(not isinstance(value, str) or not value.strip() for value in policy[field])
        ):
            return False
        if field in {"excluded_canonical_ids", "excluded_form_terms"} and any(
            not _key(value) for value in policy.get(field, [])
        ):
            return False
    if "require_source_label_form" in policy and not isinstance(policy["require_source_label_form"], bool):
        return False
    if policy.get("require_source_label_form") and not policy.get("required_form_terms"):
        return False
    bounds = []
    for field in ("minimum_daily_dose", "maximum_daily_dose"):
        value = _number(policy[field]) if field in policy else None
        if field in policy and (value is None or value <= 0):
            return False
        bounds.append(value)
    if all(value is not None for value in bounds) and bounds[0] > bounds[1]:
        return False
    if "dose_unit" in policy or any(value is not None for value in bounds):
        if not isinstance(policy.get("dose_unit"), str) or _key(policy["dose_unit"]) not in _UNIT_SCALE:
            return False
    return True


def _rows(product: Mapping, *, source_only: bool = False):
    seen = set()

    def walk(rows):
        for row in rows or []:
            if not isinstance(row, Mapping):
                continue
            ref = row.get("raw_source_path") or row.get("source_row_ref")
            valid_reference = not source_only or (isinstance(ref, str) and bool(ref.strip()))
            identity = (ref, row.get("name"), str(row.get("quantity")), row.get("unit"))
            if valid_reference and identity not in seen and _is_exposure_row(row):
                seen.add(identity)
                yield row
            yield from walk(row.get("nestedIngredients"))

    originals = product.get("activeIngredients") or []
    yield from walk(originals)
    # Source-required scopes cannot replace an original owner with a generated
    # row, even when the generated row has a different or missing reference.
    if source_only and any(isinstance(row, Mapping) for row in originals):
        return
    iqd = product.get("ingredient_quality_data") or {}
    yield from walk(iqd.get("ingredients_scorable") or iqd.get("ingredients"))


def _linked_rows(product: Mapping, entry: Mapping, *, source_only: bool = False):
    source_refs = entry.get("matched_source_row_refs")
    if source_refs is not None and (
        not isinstance(source_refs, list)
        or any(not isinstance(ref, str) or not ref.strip() for ref in source_refs)
    ):
        return []
    refs = set(source_refs or [])
    name = _key(entry.get("ingredient"))
    canonicals = {_key(c) for c in entry.get("matched_canonical_ids") or []}
    rows = list(_rows(product, source_only=source_only))
    if refs:
        return [r for r in rows if (r.get("raw_source_path") or r.get("source_row_ref")) in refs]
    exact = [r for r in rows if name and name in {_key(r.get("name")), _key(r.get("raw_source_text"))}]
    if exact:
        return exact
    if source_only:
        # Legacy source-required matches may use an exact referenced label
        # owner, but a canonical guess is not preparation/source evidence.
        return []
    # Legacy boundary only: one canonical row is unambiguous. Multiple forms of
    # the same nutrient may not lend their amount to an unmatched source form.
    candidates = [r for r in rows if _key(r.get("canonical_id")) in canonicals]
    return candidates if len(candidates) == 1 else []


def assess_clinical_applicability(product: Mapping, entry: Mapping) -> dict:
    reference = reviewed_entries().get(str(entry.get("id") or entry.get("study_id")), {})
    policy = reference["applicability"] if "applicability" in reference else entry.get("applicability")
    if policy is None:
        return {"status": "not_curated", "reason_code": "no_reviewed_scope_constraints"}
    if not _valid_policy(policy):
        return {"status": "unresolved", "reason_code": "invalid_applicability_contract"}
    if policy.get("scope") == "formula_context_only":
        return {"status": "not_applicable", "reason_code": "formula_reference_not_individual_evidence"}
    if policy.get("scope") != "ingredient":
        return {"status": "unresolved", "reason_code": "unsupported_applicability_scope"}
    physical = product.get("physicalState") or {}
    if isinstance(physical, Mapping):
        physical = physical.get("name")
    dosage_form = _key(product.get("form_factor_canonical") or product.get("form_factor") or physical)
    allowed = {_key(f) for f in policy.get("dosage_forms") or []}
    if allowed and dosage_form not in allowed:
        return {"status": "not_applicable", "reason_code": "clinical_delivery_mismatch"}

    lower, upper, _ = resolve_daily_serving_range(dict(product))
    reasons = []
    source_only = policy.get("require_source_label_form", False)
    excluded_canonicals = {_key(value) for value in policy.get("excluded_canonical_ids", [])}
    for row in _linked_rows(product, entry, source_only=source_only):
        text = _row_text(row, source_only=source_only)
        if source_only and not text:
            reasons.append("clinical_source_label_unresolved")
            continue
        if _key(row.get("canonical_id")) in excluded_canonicals:
            reasons.append("clinical_identity_excluded")
            continue
        if any(" " + _key(term) + " " in text for term in policy.get("excluded_form_terms", [])):
            reasons.append("clinical_form_excluded")
            continue
        forms = policy.get("required_form_terms") or []
        if forms and not any(" " + _key(form) + " " in text for form in forms):
            reasons.append("clinical_form_mismatch")
            continue
        amount = _number(row.get("quantity"))
        unit = _key(row.get("unit_normalized") or row.get("unit"))
        target = _key(policy.get("dose_unit"))
        if target:
            if amount is None or amount <= 0 or unit not in _UNIT_SCALE:
                reasons.append("clinical_dose_unresolved")
                continue
            amount *= _UNIT_SCALE[unit] / _UNIT_SCALE[target]
            minimum, maximum = policy.get("minimum_daily_dose"), policy.get("maximum_daily_dose")
            if minimum is not None and amount * lower < float(minimum):
                reasons.append("below_applicable_clinical_dose")
                continue
            if maximum is not None and amount * upper > float(maximum):
                reasons.append("above_applicable_clinical_dose")
                continue
        return {"status": "applicable", "reason_code": "reviewed_scope_match",
                "source_row_ref": row.get("raw_source_path") or row.get("source_row_ref"),
                "supported_outcomes": policy.get("supported_outcomes", []),
                "studied_population": policy.get("studied_population"),
                "scope": "ingredient"}
    return {"status": "not_applicable", "reason_code": reasons[0] if reasons else "clinical_source_row_unresolved"}


def filter_clinical_matches(product: Mapping, matches: list[dict]) -> tuple[list[dict], list[dict]]:
    accepted, rejected = [], []
    for entry in matches:
        decision = assess_clinical_applicability(product, entry)
        if decision["status"] in {"applicable", "not_curated"}:
            # Preserve legacy shape for unreviewed records; never imply that a
            # missing applicability policy is a completed scientific review.
            if decision["status"] == "not_curated":
                accepted.append(entry)
                continue
            scoped_entry = {**entry, "applicability_assessment": decision}
            if decision.get("source_row_ref"):
                # Later dose and readiness consumers may use only the row that
                # passed, not a sibling admitted by broad identity matching.
                scoped_entry["matched_source_row_refs"] = [decision["source_row_ref"]]
            accepted.append(scoped_entry)
        else:
            rejected.append({"id": entry.get("id") or entry.get("study_id"),
                             "ingredient": entry.get("ingredient"), **decision})
    return accepted, rejected
