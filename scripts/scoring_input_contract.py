#!/usr/bin/env python3
"""Version-neutral scoring input contract.

Scoring consumes cleaner/enrichment decisions from this module instead of
rediscovering active rows from labels or legacy raw fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


SCORING_SOURCE = "ingredient_quality_data.ingredients_scorable"
LEGACY_IQD_SOURCE = "ingredient_quality_data.ingredients"
PRODUCT_EVIDENCE_SOURCE = "product_scoring_evidence"

VALID_DOSE_CLASSES = {
    "therapeutic_mass",
    "enzyme_activity",
    "probiotic_cfu",
    "percent_dv_only",
}

VALID_NON_MASS_DOSE_CLASSES = {"enzyme_activity", "probiotic_cfu"}

EXCLUDED_CLEANER_ROLES = {
    "blend_header_total",
    "nested_display_only",
    "composition_leaf",
    "source_descriptor",
    "nutrition_rollup",
    "excipient",
    "inactive",
    "label_header",
}

VALID_ACTIVE_ROLES = {"active_scorable", "active_misfiled_in_inactive"}


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass
class ScoringFallback:
    fallback_class: str
    fallback_reason: str
    source: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "fallback_class": self.fallback_class,
            "fallback_reason": self.fallback_reason,
            "source": self.source,
        }


@dataclass
class RejectedScoringRow:
    row: Dict[str, Any]
    reason: str
    missing_fields: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.row.get("name") or self.row.get("standard_name"),
            "canonical_id": self.row.get("canonical_id"),
            "reason": self.reason,
            "missing_fields": list(self.missing_fields),
            "raw_source_path": self.row.get("raw_source_path"),
            "cleaner_row_role": self.row.get("cleaner_row_role"),
            "role_classification": self.row.get("role_classification"),
        }


@dataclass
class ScoringInputResult:
    rows: List[Dict[str, Any]]
    rejected_rows: List[RejectedScoringRow]
    source: str
    fallbacks_used: List[ScoringFallback]
    strict_contract_passed: bool
    zero_scorable_reason: Optional[str]
    mapped_count: int
    unmapped_count: int
    mapped_coverage: Optional[float]
    contract_findings: List[str]
    mapped_coverage_applicable: bool = True

    @property
    def unmapped_actives(self) -> List[str]:
        names: List[str] = []
        for rejected in self.rejected_rows:
            if rejected.reason == "missing_scoring_identity":
                row = rejected.row
                names.append(
                    row.get("name")
                    or row.get("standard_name")
                    or row.get("raw_source_text")
                    or "unknown"
                )
        return names

    def diagnostics(self) -> Dict[str, Any]:
        return {
            "scoring_ingredients_source": self.source,
            "iqd_ingredients_fallback_used": any(
                fallback.source == LEGACY_IQD_SOURCE for fallback in self.fallbacks_used
            ),
            "ingredients_scorable_count": self.mapped_count + self.unmapped_count,
            "scoring_rows_count": len(self.rows),
            "rejected_rows_count": len(self.rejected_rows),
            "rejected_rows": [row.to_dict() for row in self.rejected_rows[:25]],
            "scoring_fallbacks_used": [fallback.to_dict() for fallback in self.fallbacks_used],
            "strict_contract_passed": self.strict_contract_passed,
            "strict_scoring_contract": {
                "passed": self.strict_contract_passed,
                "findings": list(self.contract_findings),
                "zero_scorable_reason": self.zero_scorable_reason,
                "mapped_coverage_applicable": self.mapped_coverage_applicable,
            },
            "zero_scorable_reason": self.zero_scorable_reason,
            "mapped_count": self.mapped_count,
            "unmapped_count": self.unmapped_count,
            "mapped_coverage": self.mapped_coverage,
            "mapped_coverage_applicable": self.mapped_coverage_applicable,
            "contract_findings": list(self.contract_findings),
        }


def _has_identity(row: Dict[str, Any]) -> bool:
    if row.get("mapped_identity") is False:
        return False
    return bool(
        row.get("canonical_id")
        or row.get("mapped_identity")
        or row.get("matched_target")
        or row.get("matched_alias")
        or row.get("mapped") is True
    )


def _has_dose_evidence(row: Dict[str, Any]) -> bool:
    dose_class = _norm(row.get("dose_class"))
    if dose_class in VALID_NON_MASS_DOSE_CLASSES:
        return True
    if row.get("has_dose") is True:
        return True
    quantity = _as_float(
        row.get("quantity", row.get("amount", row.get("dose", row.get("dosage")))),
        None,
    )
    if quantity is None or quantity <= 0:
        return False
    unit = _norm(
        row.get("unit")
        or row.get("unit_normalized")
        or row.get("normalized_unit")
        or row.get("dose_unit")
    )
    return unit not in {"", "np", "n/a", "na", "none", "0"}


def _product_scoring_evidence_rows(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    evidence = product.get("product_scoring_evidence")
    if isinstance(evidence, dict):
        evidence_rows = _safe_list(evidence.get("items") or evidence.get("evidence"))
        if not evidence_rows and evidence:
            evidence_rows = [evidence]
    else:
        evidence_rows = _safe_list(evidence)

    rows: List[Dict[str, Any]] = []
    for idx, item in enumerate(evidence_rows):
        if not isinstance(item, dict):
            continue
        dose_class = _norm(item.get("dose_class"))
        if dose_class not in VALID_NON_MASS_DOSE_CLASSES:
            continue
        row = dict(item)
        row.setdefault("name", item.get("name") or item.get("label") or dose_class)
        row.setdefault("canonical_id", item.get("canonical_id") or dose_class)
        row.setdefault("mapped", True)
        row.setdefault("scoreable_identity", True)
        row.setdefault("role_classification", "active_scorable")
        row.setdefault("cleaner_row_role", "active_scorable")
        row.setdefault("score_eligible_by_cleaner", True)
        row.setdefault("dose_class", dose_class)
        row.setdefault("raw_source_path", f"product_scoring_evidence[{idx}]")
        rows.append(row)
    return rows


def _reject(row: Dict[str, Any], reason: str, missing_fields: Optional[List[str]] = None) -> RejectedScoringRow:
    return RejectedScoringRow(row=row, reason=reason, missing_fields=missing_fields or [])


def _evaluate_row(row: Dict[str, Any], *, strict: bool) -> tuple[bool, Optional[RejectedScoringRow], List[str]]:
    findings: List[str] = []
    missing: List[str] = []
    for field_name in (
        "source_section",
        "raw_source_path",
        "cleaner_row_role",
        "score_eligible_by_cleaner",
        "dose_class",
        "role_classification",
        "scoreable_identity",
    ):
        if field_name not in row:
            missing.append(field_name)
    if strict and missing:
        findings.append(f"missing_required_fields:{','.join(missing)}")

    cleaner_role = _norm(row.get("cleaner_row_role"))
    if cleaner_role in EXCLUDED_CLEANER_ROLES:
        return False, _reject(row, f"excluded_cleaner_role:{cleaner_role}"), findings
    if row.get("is_blend_header") or row.get("blend_total_weight_only"):
        return False, _reject(row, "excluded_blend_total_or_header"), findings
    if row.get("is_proprietary_blend") and not _has_identity(row):
        return False, _reject(row, "excluded_unmapped_proprietary_blend"), findings

    if row.get("score_eligible_by_cleaner") is False:
        return False, _reject(row, "cleaner_marked_not_score_eligible"), findings

    role = _norm(row.get("role_classification") or cleaner_role)
    if role and role not in VALID_ACTIVE_ROLES:
        return False, _reject(row, f"excluded_role_classification:{role}"), findings

    if row.get("scoreable_identity") is False:
        return False, _reject(row, "identity_marked_not_scoreable"), findings

    if not _has_dose_evidence(row):
        return False, _reject(row, "missing_dose_evidence"), findings

    if not _has_identity(row):
        return False, _reject(row, "missing_scoring_identity"), findings

    return True, None, findings


def get_scoring_ingredients(
    product: Dict[str, Any],
    *,
    strict: bool = True,
    allow_legacy_fallback: bool = False,
) -> ScoringInputResult:
    """Return the single validated scoring input contract for v3 and v4.

    Strict mode never silently falls back to legacy IQD/raw active rows.
    Missing cleaner/enrichment fields are surfaced as contract findings so
    release audits can fail current artifacts while old unit fixtures remain
    inspectable during migration.
    """
    product = product or {}
    iqd = _safe_dict(product.get("ingredient_quality_data"))
    source = SCORING_SOURCE
    fallbacks: List[ScoringFallback] = []
    contract_findings: List[str] = []

    if strict and not isinstance(iqd.get("ingredients_scorable"), list):
        contract_findings.append("missing_iqd_ingredients_scorable_list")
    candidates = [row for row in _safe_list(iqd.get("ingredients_scorable")) if isinstance(row, dict)]
    product_evidence_rows = _product_scoring_evidence_rows(product)
    if product_evidence_rows:
        candidates.extend(product_evidence_rows)
        source = f"{SCORING_SOURCE}+{PRODUCT_EVIDENCE_SOURCE}"

    if not candidates and allow_legacy_fallback:
        legacy = [row for row in _safe_list(iqd.get("ingredients")) if isinstance(row, dict)]
        if legacy:
            candidates = legacy
            source = LEGACY_IQD_SOURCE
            fallbacks.append(ScoringFallback(
                fallback_class="old_batch_compatibility",
                fallback_reason="ingredients_scorable_empty_used_legacy_iqd_ingredients",
                source=LEGACY_IQD_SOURCE,
            ))
    rows: List[Dict[str, Any]] = []
    rejected: List[RejectedScoringRow] = []
    row_findings: List[str] = []
    for row in candidates:
        ok, rejection, findings = _evaluate_row(row, strict=strict)
        row_findings.extend(findings)
        if ok:
            rows.append(row)
        elif rejection is not None:
            rejected.append(rejection)

    unmapped_count = sum(1 for item in rejected if item.reason == "missing_scoring_identity")
    mapped_count = len(rows)
    denominator = mapped_count + unmapped_count
    mapped_coverage = (mapped_count / denominator) if denominator else 0.0

    contract_findings.extend(sorted(set(row_findings)))
    if strict and fallbacks:
        contract_findings.append("strict_mode_used_legacy_fallback")

    zero_reason: Optional[str] = None
    if not rows:
        if not candidates:
            zero_reason = "no_strict_scoring_candidates"
        elif rejected:
            zero_reason = "all_scoring_candidates_rejected"
        else:
            zero_reason = "no_scorable_rows"

    strict_passed = not contract_findings and not fallbacks
    return ScoringInputResult(
        rows=rows,
        rejected_rows=rejected,
        source=source,
        fallbacks_used=fallbacks,
        strict_contract_passed=strict_passed,
        zero_scorable_reason=zero_reason,
        mapped_count=mapped_count,
        unmapped_count=unmapped_count,
        mapped_coverage=mapped_coverage,
        contract_findings=contract_findings,
    )


def is_nutrition_only_product(product: Dict[str, Any], *, allow_legacy_keyword_fallback: bool = False) -> bool:
    """Return True only for explicit enrichment/taxonomy nutrition-only facts.

    Keyword fallback is retained for old batches when callers explicitly opt in.
    """
    product = product or {}
    for value in (
        product.get("product_scoring_class"),
        _safe_dict(product.get("supplement_taxonomy")).get("product_scoring_class"),
        _safe_dict(product.get("scoring_contract")).get("product_scoring_class"),
    ):
        if _norm(value) == "nutrition_only":
            return True

    if not allow_legacy_keyword_fallback:
        return False

    name = _norm(product.get("product_name") or product.get("fullName"))
    return any(
        keyword in name
        for keyword in (
            "whey",
            "casein",
            "pea protein",
            "soy protein",
            "rice protein",
            "hemp protein",
            "plant protein",
            "plant-based protein",
            "protein powder",
            "protein shake",
            "protein blend",
            "meal replacement",
            "mass gainer",
            "weight gainer",
            "smoothie mix",
        )
    )
