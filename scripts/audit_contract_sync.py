"""
Phase 0 of the raw → Flutter data-integrity audit.

Reads every detail_blob in a build directory and reports — per contract field
defined in scripts/FINAL_EXPORT_SCHEMA_V1.md (v1.5.0) — whether the field is
actually emitted today, what fraction of records carry it, what fraction are
null, and (for enums) the value distribution observed.

This is a read-only audit. It never changes product data. The snapshot rebuild
also uses its non-zero exit status as a strict pre-promotion contract gate.

Status colors:
  GREEN  — field present in ≥95% of records OR (optional-by-contract field
           where absence is expected for some records)
  YELLOW — field present in 50-95%, may indicate partial migration or
           missing emit path for some records
  RED    — field present in <50% (contract gap — either the implementation
           has not landed or the doc is stale)
  N/A    — field is optional-by-contract and we cannot infer from the sample

Run:
  python3 scripts/audit_contract_sync.py \
      --build-dir scripts/final_db_output \
      --out reports/contract_sync_report.json
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path
from typing import Any


# v1.5.0 canonical active-ingredient contract.
# (source: scripts/FINAL_EXPORT_SCHEMA_V1.md §"Canonical active ingredient contract")
ACTIVE_CONTRACT: dict[str, dict[str, Any]] = {
    "raw_source_text":     {"required": True,  "type": "string",   "is_enum": False},
    "name":                {"required": True,  "type": "string",   "is_enum": False},
    "standard_name":       {"required": False, "type": "string?",  "is_enum": False},
    "normalized_key":      {"required": False, "type": "string?",  "is_enum": False},
    "quantity":            {"required": False, "type": "number?",  "is_enum": False},
    "unit":                {"required": False, "type": "string?",  "is_enum": False},
    "bio_score":           {"required": False, "type": "number?",  "is_enum": False},
    "form":                {"required": False, "type": "string?",  "is_enum": False, "deprecated": True},
    "is_harmful":          {"required": False, "type": "bool?",    "is_enum": False, "deprecated": True},
    # v1.5.0 canonical fields (PROMISED in doc):
    "display_label":        {"required": True,  "type": "string",   "is_enum": False, "v1_5_0": True},
    "display_form_label":   {"required": True,  "type": "string?",  "is_enum": False, "v1_5_0": True},
    "form_status":          {"required": True,  "type": "enum",     "is_enum": True,  "v1_5_0": True,
                             "values": ["known", "unknown"]},
    "form_match_status":    {"required": True,  "type": "enum",     "is_enum": True,  "v1_5_0": True,
                             "values": ["mapped", "unmapped", "n/a"]},
    "display_dose_label":   {"required": True,  "type": "string",   "is_enum": False, "v1_5_0": True},
    "dose_status":          {"required": True,  "type": "enum",     "is_enum": True,  "v1_5_0": True,
                             "values": ["disclosed", "not_disclosed_blend", "missing"]},
    "is_safety_concern":    {"required": True,  "type": "bool",     "is_enum": False, "v1_5_0": True},
    "canonical_id":         {"required": True,  "type": "string?",  "is_enum": False, "v1_5_0": True,
                             "note": "needed for interaction-rule and stack matching"},
    "delivers_markers":     {"required": False, "type": "array?",   "is_enum": False, "v1_5_0": True,
                             "note": "computed in enricher; doc§Detail Blob Contract promises propagation"},
    "standardization_note": {"required": False, "type": "string?",  "is_enum": False},
    "display_badge":        {"required": False, "type": "string?",  "is_enum": False},
    "identifiers":          {"required": False, "type": "object?",  "is_enum": False},
    # Rest of the shipped row shape (row-key census, 2026-09-25). Together with
    # the fields above this is the whole active row: a row key missing here
    # fails the gate, so a second name for an existing value cannot ship
    # unreviewed. required=True marks fields non-null on every shipped row.
    "raw_source_path":      {"required": False, "type": "string?",  "is_enum": False},
    "forms":                {"required": True,  "type": "array",    "is_enum": False,
                             "note": "label-parsed forms; extracted_forms is the IQM extraction"},
    "dailyValue":           {"required": False, "type": "number?",  "is_enum": False},
    "dose_data_quality":    {"required": False, "type": "object?",  "is_enum": False},
    "matched_form":         {"required": True,  "type": "string",   "is_enum": False},
    "matched_forms":        {"required": True,  "type": "array",    "is_enum": False},
    "extracted_forms":      {"required": True,  "type": "array",    "is_enum": False},
    "category":             {"required": True,  "type": "string",   "is_enum": False},
    "below_clinical_dose":  {"required": True,  "type": "bool",     "is_enum": False},
    "notes":                {"required": True,  "type": "string",   "is_enum": False},
    "form_note":            {"required": False, "type": "string?",  "is_enum": False},
    "form_note_preview":    {"required": False, "type": "string?",  "is_enum": False},
    "form_evidence":        {"required": False, "type": "object",   "is_enum": False,
                             "note": "conditional: only when the IQM form carries reviewed evidence"},
    "safety_flags":         {"required": True,  "type": "array",    "is_enum": False},
    "normalized_amount":    {"required": False, "type": "number?",  "is_enum": False},
    "normalized_unit":      {"required": True,  "type": "string",   "is_enum": False},
    "conversion_evidence":  {"required": False, "type": "object?",  "is_enum": False},
    "role":                 {"required": True,  "type": "string",   "is_enum": False},
    "parent_key":           {"required": True,  "type": "string",   "is_enum": False},
    "is_mapped":            {"required": True,  "type": "bool",     "is_enum": False},
    "nutrient_group_id":    {"required": False, "type": "string?",  "is_enum": False},
    "harmful_severity":     {"required": False, "type": "string?",  "is_enum": False},
    "is_banned":            {"required": True,  "type": "bool",     "is_enum": False},
    "safety_reason":        {"required": False, "type": "string?",  "is_enum": False},
    "matched_source":       {"required": False, "type": "string?",  "is_enum": False},
    "matched_rule_id":      {"required": False, "type": "string?",  "is_enum": False},
    "us_applicable":        {"required": False, "type": "bool?",    "is_enum": False},
    "jurisdictions":        {"required": True,  "type": "array",    "is_enum": False},
    "jurisdiction_scope":   {"required": False, "type": "string?",  "is_enum": False, "note": "no reader found (row-key census 2026-09-25)"},
    "safety_warning_one_liner": {"required": False, "type": "string?", "is_enum": False},
    "safety_warning":       {"required": False, "type": "string?",  "is_enum": False},
    "source_label_name":    {"required": False, "type": "string?",  "is_enum": False},
    "source_label_form":    {"required": False, "type": "string?",  "is_enum": False},
    "label_display_name":   {"required": False, "type": "string?",  "is_enum": False},
    "label_display_form":   {"required": False, "type": "string?",  "is_enum": False},
    "identity_disposition": {"required": False, "type": "string?",  "is_enum": False},
    "clinical_support_level": {"required": False, "type": "string?", "is_enum": False},
}


# v1.5.0 canonical inactive-ingredient contract.
# (source: scripts/FINAL_EXPORT_SCHEMA_V1.md §"Canonical inactive ingredient contract")
INACTIVE_CONTRACT: dict[str, dict[str, Any]] = {
    "raw_source_text":     {"required": True,  "type": "string",   "is_enum": False},
    "name":                {"required": True,  "type": "string",   "is_enum": False},
    "standard_name":       {"required": False, "type": "string?",  "is_enum": False},
    "normalized_key":      {"required": False, "type": "string?",  "is_enum": False},
    "severity_level":      {"required": False, "type": "string?",  "is_enum": False, "deprecated_note": "v1.5.0 prefers severity_status enum"},
    "is_additive":         {"required": False, "type": "bool?",    "is_enum": False},
    "additive_type":       {"required": False, "type": "string?",  "is_enum": False,
                            "deprecated_note": "retired; functional_roles is the v1.5.0 role contract"},
    "functional_roles":    {"required": False, "type": "array?",   "is_enum": False},
    "identifiers":         {"required": False, "type": "object?",  "is_enum": False},
    # v1.5.0 canonical fields (PROMISED in doc):
    "display_label":       {"required": True,  "type": "string",   "is_enum": False, "v1_5_0": True},
    "display_role_label":  {"required": True,  "type": "string?",  "is_enum": False, "v1_5_0": True},
    "severity_status":     {"required": True,  "type": "enum",     "is_enum": True,  "v1_5_0": True,
                            "values": ["critical", "suppress", "informational", "n/a"]},
    "display_tone":        {"required": True,  "type": "enum",     "is_enum": True,
                            "strict_complete": True,
                            "values": ["green", "light_orange", "dark_orange", "red"],
                            "note": "penalty-aware Other Ingredient tone from the v4 scorer ledger"},
    "is_safety_concern":   {"required": True,  "type": "bool",     "is_enum": False, "v1_5_0": True},
    # Rest of the shipped row shape (row-key census, 2026-09-25); see the note
    # in ACTIVE_CONTRACT.
    "forms":               {"required": True,  "type": "array",    "is_enum": False},
    "category":            {"required": True,  "type": "string",   "is_enum": False},
    "safety_flags":        {"required": True,  "type": "array",    "is_enum": False},
    "notes":               {"required": True,  "type": "string",   "is_enum": False},
    "mechanism_of_harm":   {"required": True,  "type": "string",   "is_enum": False, "note": "no reader found (row-key census 2026-09-25)"},
    "common_uses":         {"required": True,  "type": "array",    "is_enum": False, "note": "no reader found (row-key census 2026-09-25)"},
    "population_warnings": {"required": True,  "type": "array",    "is_enum": False},
    "harmful_severity":    {"required": False, "type": "string?",  "is_enum": False},
    "resolved_display_label": {"required": True, "type": "string", "is_enum": False, "note": "no reader found (row-key census 2026-09-25)"},
    "label_row_disposition": {"required": True, "type": "string",  "is_enum": False, "note": "no reader found (row-key census 2026-09-25)"},
    "is_label_descriptor": {"required": True,  "type": "bool",     "is_enum": False},
    "is_active_only":      {"required": True,  "type": "bool",     "is_enum": False},
    "is_banned":           {"required": True,  "type": "bool",     "is_enum": False},
    "safety_reason":       {"required": False, "type": "string?",  "is_enum": False},
    "matched_source":      {"required": False, "type": "string?",  "is_enum": False},
    "matched_rule_id":     {"required": False, "type": "string?",  "is_enum": False},
    "regulatory_status":   {"required": False, "type": "string?",  "is_enum": False},
    "us_applicable":       {"required": False, "type": "bool?",    "is_enum": False},
    "jurisdictions":       {"required": True,  "type": "array",    "is_enum": False},
    "jurisdiction_scope":  {"required": False, "type": "string?",  "is_enum": False, "note": "no reader found (row-key census 2026-09-25)"},
    "inactive_policy":     {"required": False, "type": "string?",  "is_enum": False},
    "safety_display_name": {"required": False, "type": "string?",  "is_enum": False},
    "safety_warning_one_liner": {"required": False, "type": "string?", "is_enum": False},
    "safety_warning":      {"required": False, "type": "string?",  "is_enum": False},
}


# Top-level blob keys. This is the one declaration of the detail-blob top-level
# contract (census of the full catalog, 2026-09-21): the D5.3 test and this
# gate read it, and a blob key that is not declared here fails the gate.
#   required=True  -> always present and non-null
#   required=False -> "nullable" (always emitted, may be null) or "conditional" (absent unless it applies)
# "deprecated": "schema_3" marks a key that ships for the published 2.5.0 blob
# contract but has no reader in the app, dashboard, reviewer console, edge
# functions or any gate (closure field census, 2026-09-21). It is a one-way
# copy with no scoring authority; schema 3 drops it.
BLOB_TOP_LEVEL: dict[str, dict[str, Any]] = {
    "dsld_id": {"required": True},
    "blob_version": {"required": True},
    "product_name": {"required": True},
    "brand_name": {"required": True},
    "brand_name_raw": {"required": True, "deprecated": "schema_3"},
    "brand_family": {"required": True, "deprecated": "schema_3"},
    "primary_type": {"required": True},
    "classification_confidence": {"required": True},
    "classification_reasons": {"required": True},
    "product_role": {"required": True},
    "product_role_evidence": {"required": True, "deprecated": "schema_3"},
    "completeness_claim_mismatch": {"required": True},
    "ingredients": {"required": True},
    "display_ingredients": {"required": True},
    "inactive_ingredients": {"required": True},
    "label_record": {"required": True},
    "label_source_rows": {"required": True},
    "label_ledger_audit": {"required": True},
    "label_ledger_omissions": {"required": True},
    "row_ledger": {"required": True},
    "row_ledger_summary": {"required": True, "deprecated": "schema_3"},
    "warnings": {"required": True},
    "warnings_profile_gated": {"required": True},
    "allergens": {"required": True},
    "gluten_free_validated": {"required": True, "deprecated": "schema_3"},
    "compliance_detail": {"required": True, "deprecated": "schema_3"},
    "certification_detail": {"required": True},
    "proprietary_blend_detail": {"required": True},
    "proprietary_blend": {"required": True},
    "dietary_sensitivity_detail": {"required": True, "deprecated": "schema_3"},
    "formulation_detail": {"required": True},
    "serving_info": {"required": True},
    "manufacturer_detail": {"required": True},
    "evidence_data": {"required": True},
    "rda_ul_data": {"required": True},
    "nutrition_detail": {"required": True},
    "unmapped_actives": {"required": True},
    "unverified_ingredient": {"required": True, "deprecated": "schema_3"},
    "score_bonuses": {"required": True},
    "score_penalties": {"required": True},
    "raw_actives_count": {"required": True},
    "raw_inactives_count": {"required": True},
    "ingredients_dropped_reasons": {"required": True},
    "non_gmo_audit": {"required": True},
    "omega3_audit": {"required": True},
    "proprietary_blend_audit": {"required": True},
    "supplement_type_audit": {"required": True},
    "audit": {"required": True},
    "product_safety_status": {"required": True},
    "quality_assessment_status": {"required": True},
    "v4_safety_gate": {"required": True, "deprecated": "schema_3"},
    "v4_dose_safety": {"required": True, "deprecated": "schema_3"},
    "v4_completeness_gate": {"required": True, "deprecated": "schema_3"},
    "v4_score_provenance": {"required": True, "deprecated": "schema_3"},
    "product_line": {"required": False, "presence": "nullable", "note": "null when the label names no product line"},
    "secondary_type": {"required": False, "presence": "nullable", "note": "null when the taxonomy assigns none"},
    "banned_substance_detail": {"required": False, "presence": "nullable", "note": "null unless a banned/recalled substance is present"},
    "product_status_detail": {"required": False, "presence": "nullable", "note": "null for active products; set for discontinued/off-market"},
    "product_status": {"required": False, "presence": "nullable", "note": "2.4 alias of product_status_detail for older app builds (schema 3 removes it)"},
    "quality_pillars_v4": {"required": False, "presence": "nullable", "note": "null when the score is safety-suppressed"},
    "clean_label_flags_v4": {"required": False, "presence": "nullable", "note": "null when no clean-label flag applies"},
    "v4_confidence_detail": {"required": False, "presence": "nullable", "note": "null when the score is safety-suppressed"},
    "v4_score_explanation": {"required": False, "presence": "nullable", "note": "null when the score is safety-suppressed"},
    "interaction_summary": {"required": False, "presence": "conditional", "note": "only when an interaction rule matches"},
    "synergy_detail": {"required": False, "presence": "conditional", "note": "only when a synergy cluster matches"},
    "adult_multi_coverage": {"required": False, "presence": "conditional", "note": "adult multivitamin products only"},
    "prenatal_coverage": {"required": False, "presence": "conditional", "note": "prenatal-anchor products only"},
    "probiotic_detail": {"required": False, "presence": "conditional", "note": "probiotic products only"},
    "ingredient_quality_data": {"required": False, "presence": "conditional", "note": "only when an absorption enhancer was demoted"},
}


def _classify_status(
    present_pct: float,
    required: bool,
    *,
    deprecated: bool = False,
    strict_complete: bool = False,
) -> str:
    if deprecated:
        return "DEPRECATED"
    if strict_complete:
        return "GREEN" if present_pct == 1.0 else "RED"
    if required:
        if present_pct >= 0.95:
            return "GREEN"
        if present_pct >= 0.50:
            return "YELLOW"
        return "RED"
    # optional fields: we can't fail them on presence — but if 0% emitted
    # when the contract advertises them, that's still informational.
    if present_pct == 0.0:
        return "RED_OPTIONAL"
    return "GREEN"


def _present(ingredient: dict, key: str) -> bool:
    """True iff the key is in the dict AND the value is not None.
    A null/None value counts as "field absent" for the contract — the
    user-facing fallback path triggers either way."""
    return key in ingredient and ingredient.get(key) is not None


def _audit_ingredient_contract(
    blobs: list[dict], list_key: str, contract: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    total_ingredients = 0
    presence_count: collections.Counter[str] = collections.Counter()
    undeclared: set[str] = set()
    enum_value_counts: dict[str, collections.Counter[str]] = {
        k: collections.Counter() for k, v in contract.items() if v.get("is_enum")
    }
    for blob in blobs:
        for ing in blob.get(list_key) or []:
            if not isinstance(ing, dict):
                continue
            total_ingredients += 1
            undeclared.update(key for key in ing if key not in contract)
            for field in contract:
                if _present(ing, field):
                    presence_count[field] += 1
                    if field in enum_value_counts:
                        v = ing.get(field)
                        if isinstance(v, str):
                            enum_value_counts[field][v] += 1

    result: dict[str, Any] = {
        "_total_ingredients": total_ingredients,
        "_total_blobs": len(blobs),
        "undeclared": sorted(undeclared),
        "fields": {},
    }
    for field, spec in contract.items():
        present = presence_count[field]
        pct = (present / total_ingredients) if total_ingredients else 0.0
        entry: dict[str, Any] = {
            "promised": True,
            "required": spec.get("required", False),
            "v1_5_0": spec.get("v1_5_0", False),
            "deprecated": bool(spec.get("deprecated") or spec.get("deprecated_note")),
            "present_in": round(pct, 4),
            "absent_in": round(1.0 - pct, 4),
            "status": _classify_status(
                pct,
                spec.get("required", False),
                deprecated=bool(spec.get("deprecated") or spec.get("deprecated_note")),
                strict_complete=bool(spec.get("strict_complete")),
            ),
        }
        if spec.get("note"):
            entry["note"] = spec["note"]
        if spec.get("deprecated_note"):
            entry["deprecated_note"] = spec["deprecated_note"]
        if spec.get("is_enum"):
            counts = enum_value_counts[field]
            entry["values_seen"] = dict(counts)
            entry["values_expected"] = spec.get("values", [])
            extra = set(counts) - set(spec.get("values", []))
            if extra:
                entry["unexpected_enum_values"] = sorted(extra)
                if spec.get("strict_complete"):
                    entry["status"] = "RED"
        result["fields"][field] = entry
    return result


def _audit_top_level(blobs: list[dict]) -> dict[str, Any]:
    presence: collections.Counter[str] = collections.Counter()
    for blob in blobs:
        for field in BLOB_TOP_LEVEL:
            if field in blob and blob[field] is not None:
                presence[field] += 1

    out: dict[str, Any] = {}
    n = len(blobs)
    for field, spec in BLOB_TOP_LEVEL.items():
        present = presence[field]
        pct = (present / n) if n else 0.0
        out[field] = {
            "required": spec.get("required", False),
            "present_in": round(pct, 4),
            "absent_in": round(1.0 - pct, 4),
            "status": _classify_status(pct, spec.get("required", False)),
        }
        if spec.get("note"):
            out[field]["note"] = spec["note"]
    return out


def _summarize(report: dict[str, Any]) -> dict[str, Any]:
    """Roll up the colored statuses into a top-line scorecard."""
    summary = {
        "active_RED_required": [],
        "active_RED_optional_zero_emit": [],
        "inactive_RED_required": [],
        "inactive_RED_optional_zero_emit": [],
        "top_level_RED": [],
        "top_level_undeclared": sorted(report["blob_top_level_undeclared"]),
        "active_undeclared": report["active_ingredient_contract"]["undeclared"],
        "inactive_undeclared": report["inactive_ingredient_contract"]["undeclared"],
        "v1_5_0_fields_absent": [],
    }
    for layer_key, summary_key_req, summary_key_opt in [
        ("active_ingredient_contract", "active_RED_required", "active_RED_optional_zero_emit"),
        ("inactive_ingredient_contract", "inactive_RED_required", "inactive_RED_optional_zero_emit"),
    ]:
        for field, entry in report[layer_key]["fields"].items():
            if entry["status"] == "RED":
                summary[summary_key_req].append(field)
            elif entry["status"] == "RED_OPTIONAL":
                summary[summary_key_opt].append(field)
            if entry.get("v1_5_0") and entry["present_in"] < 0.5:
                summary["v1_5_0_fields_absent"].append(f"{layer_key.split('_')[0]}.{field}")
    for field, entry in report["blob_top_level"].items():
        if entry["status"] == "RED":
            summary["top_level_RED"].append(field)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", required=True, type=Path,
                        help="path containing detail_blobs/")
    parser.add_argument("--out", required=True, type=Path,
                        help="output JSON path (will create parent dir)")
    parser.add_argument("--sample", type=int, default=0,
                        help="if > 0, sample at most N blobs (deterministic by sort order)")
    args = parser.parse_args()

    blob_dir = args.build_dir / "detail_blobs"
    if not blob_dir.is_dir():
        print(f"ERROR: {blob_dir} does not exist", file=sys.stderr)
        return 2

    blob_paths = sorted(blob_dir.glob("*.json"))
    if args.sample > 0:
        blob_paths = blob_paths[: args.sample]
    if not blob_paths:
        print("ERROR: no detail_blob JSON files found", file=sys.stderr)
        return 2

    print(f"[contract_sync] loading {len(blob_paths)} blobs from {blob_dir}", file=sys.stderr)
    blobs: list[dict] = []
    for p in blob_paths:
        try:
            blobs.append(json.loads(p.read_text()))
        except Exception as e:
            print(f"  ! skipping {p.name}: {e}", file=sys.stderr)

    report: dict[str, Any] = {
        "schema": "contract_sync_report_v1",
        "build_dir": str(args.build_dir),
        "blob_count": len(blobs),
        "active_ingredient_contract": _audit_ingredient_contract(blobs, "ingredients", ACTIVE_CONTRACT),
        "inactive_ingredient_contract": _audit_ingredient_contract(blobs, "inactive_ingredients", INACTIVE_CONTRACT),
        "blob_top_level": _audit_top_level(blobs),
        "blob_top_level_undeclared": sorted({key for blob in blobs for key in blob} - set(BLOB_TOP_LEVEL)),
    }
    report["summary"] = _summarize(report)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))
    print(f"[contract_sync] wrote {args.out}", file=sys.stderr)

    # Loud verdict to stdout
    s = report["summary"]
    print(f"\n--- CONTRACT SYNC VERDICT ---")
    print(f"blobs scanned:                {report['blob_count']}")
    print(f"active fields RED (required): {len(s['active_RED_required'])} {s['active_RED_required']}")
    print(f"active fields RED (optional): {len(s['active_RED_optional_zero_emit'])} {s['active_RED_optional_zero_emit']}")
    print(f"inactive fields RED (req):    {len(s['inactive_RED_required'])} {s['inactive_RED_required']}")
    print(f"inactive fields RED (opt):    {len(s['inactive_RED_optional_zero_emit'])} {s['inactive_RED_optional_zero_emit']}")
    print(f"top-level fields RED:         {len(s['top_level_RED'])} {s['top_level_RED']}")
    print(f"top-level keys undeclared:    {len(s['top_level_undeclared'])} {s['top_level_undeclared']}")
    print(f"active row keys undeclared:   {len(s['active_undeclared'])} {s['active_undeclared']}")
    print(f"inactive row keys undeclared: {len(s['inactive_undeclared'])} {s['inactive_undeclared']}")
    print(f"v1.5.0 fields <50% emitted:   {len(s['v1_5_0_fields_absent'])} {s['v1_5_0_fields_absent']}")
    return 1 if (
        s["active_RED_required"] or s["inactive_RED_required"]
        or s["top_level_RED"] or s["top_level_undeclared"]
        or s["active_undeclared"] or s["inactive_undeclared"]
    ) else 0


if __name__ == "__main__":
    sys.exit(main())
