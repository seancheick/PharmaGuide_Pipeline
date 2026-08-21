"""Versioned consumer projections for final catalog detail blobs.

Schema 2.4 is the additive compatibility release.  Schema 3 is a prepared
breaking projection that removes redundant consumer payloads only after the
Flutter bridge can read the canonical replacements.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Mapping


SUPPORTED_EXPORT_SCHEMA_VERSIONS = ("2.4.0", "3.0.0")


def export_schema_major(version: str) -> int:
    """Return the numeric major component of a validated export version."""
    normalized = str(version).strip()
    try:
        major = int(normalized.split(".", 1)[0])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid export schema version: {version!r}") from exc
    if normalized not in SUPPORTED_EXPORT_SCHEMA_VERSIONS:
        raise ValueError(
            f"unsupported export schema version {normalized!r}; expected one of "
            f"{SUPPORTED_EXPORT_SCHEMA_VERSIONS}"
        )
    return major


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _normalized_ids(value: Any) -> list[str]:
    return [
        str(item).strip()
        for item in _safe_list(value)
        if str(item).strip()
    ]


def _is_interaction_rule_warning(warning: Mapping[str, Any]) -> bool:
    return str(warning.get("source") or "").strip() == "interaction_rules"


_WARNING_REF_DYNAMIC_FIELDS = (
    "type",
    "severity",
    "severity_contextual",
    "display_mode_default",
    "condition_ids",
    "drug_class_ids",
    "ingredient_name",
    "ingredient_canonical_id",
    "dose_decision",
    "direction",
    "materiality",
    "min_effective_dose",
    "dose_floor_status",
    "profile_gate",
    "source_producers",
    "evidence_level",
    "sources",
)

_WARNING_COPY_FIELDS = (
    "detail",
    "action",
    "alert_headline",
    "alert_body",
    "informational_note",
)


def _warning_copy_fingerprint(copy_fields: Mapping[str, Any]) -> str:
    payload = {
        field: copy_fields.get(field)
        for field in _WARNING_COPY_FIELDS
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _warning_rule_ref(warning: Mapping[str, Any]) -> dict[str, Any]:
    rule_id = str(warning.get("source_rule_id") or "").strip()
    if not rule_id:
        raise ValueError(
            "schema 3 cannot remove interaction warning prose without a "
            "stable source_rule_id"
        )
    ref: dict[str, Any] = {
        "rule_id": rule_id,
        "copy_fingerprint": _warning_copy_fingerprint(warning),
    }
    for field in _WARNING_REF_DYNAMIC_FIELDS:
        if field in warning:
            ref[field] = copy.deepcopy(warning[field])
    return ref


def _strip_schema3_rda_duplicates(rda_ul_data: dict[str, Any]) -> None:
    rda_ul_data.pop("ingredients_with_rda", None)
    rda_ul_data.pop("adequacy_results", None)
    for row in _safe_list(rda_ul_data.get("analyzed_ingredients")):
        if not isinstance(row, dict):
            continue
        # These matrices duplicate the versioned RDA/UL reference shipped once
        # in the local reference-data surface.  Consumer calculations use the
        # already-normalized exposure and typed UL fields on the row.
        row.pop("data_by_group", None)
        row.pop("reference_data", None)
        row.pop("reference_matrix", None)


def project_detail_blob(
    blob: dict[str, Any], *, export_schema_version: str
) -> dict[str, Any]:
    """Project one freshly built detail blob into a versioned public shape.

    Schema 2.4 returns the original object unchanged so the compatibility
    release remains byte-stable.  Schema 3 works on a copy and removes only
    fields with a tested canonical replacement or no consumer references.
    """
    if export_schema_major(export_schema_version) < 3:
        return blob

    projected = copy.deepcopy(blob)
    projected["blob_version"] = 3

    for ingredient in _safe_list(projected.get("ingredients")):
        if isinstance(ingredient, dict):
            ingredient.pop("safety_hits", None)

    rda_ul_data = projected.get("rda_ul_data")
    if isinstance(rda_ul_data, dict):
        _strip_schema3_rda_duplicates(rda_ul_data)

    warnings = [
        warning
        for warning in _safe_list(projected.get("warnings"))
        if isinstance(warning, dict)
    ]
    rule_warnings = [warning for warning in warnings if _is_interaction_rule_warning(warning)]
    display_warnings = [warning for warning in warnings if not _is_interaction_rule_warning(warning)]
    projected["warnings"] = display_warnings
    projected["warning_rule_refs"] = [
        _warning_rule_ref(warning) for warning in rule_warnings
    ]
    projected.pop("warnings_profile_gated", None)

    projected.pop("section_breakdown", None)
    projected.pop("product_status", None)
    if "proprietary_blend" in projected:
        projected["has_opaque_proprietary_blend"] = projected.pop(
            "proprietary_blend"
        )
    blend_detail = projected.get("proprietary_blend_detail")
    if isinstance(blend_detail, dict) and "has_proprietary_blends" in blend_detail:
        blend_detail["has_any_proprietary_blend"] = blend_detail.pop(
            "has_proprietary_blends"
        )
    for diagnostic in (
        "non_gmo_audit",
        "omega3_audit",
        "proprietary_blend_audit",
        "supplement_type_audit",
        "audit",
    ):
        projected.pop(diagnostic, None)

    synergy = projected.get("synergy_detail")
    if isinstance(synergy, dict):
        for cluster in _safe_list(synergy.get("clusters")):
            if isinstance(cluster, dict):
                cluster.pop("id", None)

    return projected


def _candidate_rule_subentries(
    rule: Mapping[str, Any], ref: Mapping[str, Any]
) -> list[tuple[Mapping[str, Any], str]]:
    condition_ids = _normalized_ids(ref.get("condition_ids"))
    drug_class_ids = _normalized_ids(ref.get("drug_class_ids"))
    candidates: list[tuple[Mapping[str, Any], str]] = []
    if condition_ids:
        condition_id = condition_ids[0]
        for candidate in _safe_list(rule.get("condition_rules")):
            if (
                isinstance(candidate, dict)
                and str(candidate.get("condition_id") or "").strip() == condition_id
            ):
                candidates.append((candidate, "condition"))
        pregnancy_lactation = rule.get("pregnancy_lactation")
        if (
            condition_id in {"pregnancy", "lactation"}
            and isinstance(pregnancy_lactation, Mapping)
        ):
            candidates.append((pregnancy_lactation, "pregnancy_lactation"))
    if drug_class_ids:
        drug_class_id = drug_class_ids[0]
        for candidate in _safe_list(rule.get("drug_class_rules")):
            if (
                isinstance(candidate, dict)
                and str(candidate.get("drug_class_id") or "").strip()
                == drug_class_id
            ):
                candidates.append((candidate, "drug_class"))
    return candidates


def _subentry_copy(
    subentry: Mapping[str, Any], subentry_kind: str
) -> dict[str, Any]:
    return {
        "detail": str(subentry.get("mechanism") or ""),
        "action": str(
            subentry.get(
                "notes" if subentry_kind == "pregnancy_lactation" else "action"
            )
            or ""
        ),
        "alert_headline": subentry.get("alert_headline"),
        "alert_body": subentry.get("alert_body"),
        "informational_note": subentry.get("informational_note"),
    }


def _rule_subentry(
    rule: Mapping[str, Any], ref: Mapping[str, Any]
) -> tuple[Mapping[str, Any], str]:
    copy_fingerprint = str(ref.get("copy_fingerprint") or "").strip()
    if not copy_fingerprint:
        raise ValueError(
            f"warning rule ref {ref.get('rule_id')!r} is missing copy_fingerprint"
        )
    candidates = _candidate_rule_subentries(rule, ref)
    for subentry, subentry_kind in candidates:
        if (
            _warning_copy_fingerprint(_subentry_copy(subentry, subentry_kind))
            == copy_fingerprint
        ):
            return subentry, subentry_kind
    raise ValueError(
        f"warning rule ref {ref.get('rule_id')!r} has no matching reviewed copy"
    )


def _resolved_warning(
    ref: Mapping[str, Any], rule: Mapping[str, Any]
) -> dict[str, Any]:
    subentry, subentry_kind = _rule_subentry(rule, ref)
    condition_ids = _normalized_ids(ref.get("condition_ids"))
    drug_class_ids = _normalized_ids(ref.get("drug_class_ids"))
    ingredient_name = str(ref.get("ingredient_name") or "").strip()
    scope_id = (condition_ids or drug_class_ids or [""])[0]
    severity = ref.get("severity") or subentry.get("severity")
    warning_type = ref.get("type") or (
        "drug_interaction" if drug_class_ids else "interaction"
    )
    copy_fields = _subentry_copy(subentry, subentry_kind)
    resolved = {
        "type": warning_type,
        "severity": severity,
        "severity_contextual": ref.get("severity_contextual"),
        "display_mode_default": ref.get("display_mode_default"),
        "title": f"{ingredient_name} / {scope_id}",
        "detail": copy_fields["detail"],
        "action": copy_fields["action"],
        "alert_headline": copy_fields["alert_headline"],
        "alert_body": copy_fields["alert_body"],
        "informational_note": copy_fields["informational_note"],
        "condition_ids": condition_ids,
        "drug_class_ids": drug_class_ids,
        "ingredient_name": ingredient_name,
        "ingredient_canonical_id": ref.get("ingredient_canonical_id"),
        "evidence_level": str(
            ref.get("evidence_level", subentry.get("evidence_level")) or ""
        ),
        "sources": copy.deepcopy(
            _safe_list(ref.get("sources", subentry.get("sources")))
        ),
        "dose_threshold_evaluation": None,
        "dose_decision": copy.deepcopy(ref.get("dose_decision")),
        "direction": ref.get("direction", subentry.get("direction")),
        "materiality": ref.get("materiality", subentry.get("materiality")),
        "min_effective_dose": ref.get(
            "min_effective_dose", subentry.get("min_effective_dose")
        ),
        "dose_floor_status": ref.get("dose_floor_status"),
        "source": "interaction_rules",
        "source_rule_id": str(ref.get("rule_id") or ""),
        "profile_gate": copy.deepcopy(
            ref.get("profile_gate", subentry.get("profile_gate"))
        ),
    }
    if "source_producers" in ref:
        resolved["source_producers"] = copy.deepcopy(
            _safe_list(ref.get("source_producers"))
        )
    return resolved


def resolve_warning_rule_refs(
    refs: list[dict[str, Any]], *, rules_by_id: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Rehydrate schema-3 warning refs using the versioned local rule DB."""
    resolved: list[dict[str, Any]] = []
    for ref in refs:
        rule_id = str(ref.get("rule_id") or "").strip()
        rule = rules_by_id.get(rule_id)
        if not isinstance(rule, Mapping):
            raise ValueError(f"warning rule ref cannot resolve rule_id={rule_id!r}")
        resolved.append(_resolved_warning(ref, rule))
    return resolved
