#!/usr/bin/env python3
"""Strict source-of-truth gates for the PharmaGuide pipeline.

This script intentionally keeps release checks boring and explicit. The matrix
declares ownership; these subcommands verify that current artifacts still obey
the cleaner-first and export contracts before snapshot/release stages ship.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MATRIX = REPO_ROOT / "scripts" / "contracts" / "source_of_truth_matrix.json"

ALLOWED_FALLBACK_CLASSES = {
    "clinical_fail_safe",
    "old_batch_compatibility",
    "dev_only_missing_vocab",
    "flutter_backward_compat",
    "retire_candidate",
}

REQUIRED_MATRIX_FIELDS = {
    "concept_id",
    "owner",
    "first_created_stage",
    "field_kind",
    "source_data_files",
    "consumers",
    "forbidden_recomputation",
    "fallback_class",
    "release_gate",
    "tests",
    "retirement_status",
}

REQUIRED_CONCEPTS = {
    "source_section",
    "raw_source_path",
    "cleaner_row_role",
    "score_eligible_by_cleaner",
    "score_exclusion_reason",
    "dose_class",
    "raw_taxonomy",
    "normalized_text",
    "normalized_key",
    "canonical_ingredient_id",
    "ingredient_category",
    "form_factor_canonical",
    "supplement_taxonomy",
    "legacy_supplement_type",
    "active_safety_classification",
    "inactive_safety_classification",
    "interaction_rules",
    "interaction_db",
    "scoring_input_contract",
    "mapping_coverage_contract",
    "section_a_ingredient_quality_score",
    "section_b_safety_purity_score",
    "section_c_evidence_score",
    "section_d_brand_trust_score",
    "verdict_contract",
    "score_diagnostics_contract",
    "scoring_fallback_policy",
    "legacy_scoring_compat_outputs",
    "product_level_scoring_evidence",
    "nutrition_only_scoring_class",
    "score_verdict",
    "final_db_export",
    "flutter_bundled_assets",
    "ingredient_identity_resolution",
    "ingredient_quality_data_contract",
    "taxonomy_input_contract",
    "enriched_active_safety_contract",
    "enriched_inactive_safety_contract",
    "interaction_profile_contract",
    "enrichment_fallback_policy",
    "display_ingredient_contract",
}

SCORABLE_BLOCKED_ROLES = {
    "blend_header_total",
    "nested_display_only",
    "composition_leaf",
    "source_descriptor",
    "excipient",
    "inactive",
    "label_header",
}

ACTIVITY_UNITS = {"SPU", "HUT", "FCC", "SU", "DU", "ALU", "FIP", "SAPU", "CU", "FU"}
VALID_NON_MASS_DOSE_CLASSES = {"enzyme_activity", "probiotic_cfu"}
REQUIRED_ENRICHMENT_ROW_FIELDS = {
    "source_section",
    "raw_source_path",
    "cleaner_row_role",
    "score_eligible_by_cleaner",
    "score_exclusion_reason",
    "dose_class",
    "raw_taxonomy",
    "canonical_id",
    "canonical_source_db",
    "normalized_key",
    "match_tier",
    "matched_alias",
    "matched_target",
    "identity_confidence",
    "identity_decision_reason",
    "mapped",
    "mapped_identity",
    "scoreable_identity",
    "role_classification",
    "recognition_source",
    "recognition_type",
    "recognition_reason",
    "form_id",
    "form_source",
    "form_unmapped",
    "delivers_markers",
}
REQUIRED_CLEANER_ROW_FIELDS = {
    "source_section",
    "raw_source_path",
    "cleaner_row_role",
    "score_eligible_by_cleaner",
    "score_exclusion_reason",
    "dose_class",
    "raw_taxonomy",
}
FALLBACK_DECISION_REASONS = {
    "recognized_non_scorable",
    "proprietary_blend_member",
    "source_descriptor_child_row",
    "form_unmapped_fallback",
    "parent_form_fallback",
    "cleaner_safety_canonical_preservation",
    "cleaner_botanical_canonical_preservation",
    "no_dose_evidence",
    "absorption_enhancer_sub_threshold",
}
OMEGA_CANONICAL_HINTS = {"omega_3", "epa", "dha", "fish_oil", "krill_oil", "cod_liver_oil", "algae_oil"}
SLEEP_CANONICAL_HINTS = {"melatonin", "valerian", "gaba", "l_theanine", "5_htp", "magnesium_glycinate"}
SLEEP_TEXT_RE = re.compile(r"\b(sleep|rest|restful|nighttime|night|bedtime|melatonin|valerian|gaba|5-htp)\b", re.I)
CRVI_TEXT_RE = re.compile(r"\b(cr\s*\(?vi\)?|chromium\s*(vi|6)|hexavalent|chromate|dichromate)\b", re.I)
GENERIC_CHROMIUM_RE = re.compile(r"\bchromium\b", re.I)


@dataclass(frozen=True)
class Finding:
    code: str
    message: str
    path: str | None = None

    def render(self) -> str:
        prefix = f"{self.code}: {self.message}"
        return f"{prefix} [{self.path}]" if self.path else prefix


def repo_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return REPO_ROOT / candidate


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def strip_sha256_prefix(value: Any) -> str | None:
    if value is None or not isinstance(value, str):
        return None
    value = value.strip()
    if value.lower().startswith("sha256:"):
        return value.split(":", 1)[1].strip()
    return value


def numeric_value(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def positive_number_in_text(value: Any) -> bool:
    """Return True only for a positive numeric token, not any digit-like text."""
    if isinstance(value, (int, float)):
        return value > 0
    if not isinstance(value, str):
        return False
    match = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?", value)
    if not match:
        return False
    try:
        return float(match.group(0).replace(",", "")) > 0
    except ValueError:
        return False


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_products(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [p for p in payload if isinstance(p, dict)]
    if isinstance(payload, dict):
        for key in ("products", "records", "items"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [p for p in rows if isinstance(p, dict)]
        return [payload]
    return []


def iter_json_files(paths: Iterable[Path]) -> Iterable[Path]:
    for path in paths:
        if path.is_file() and path.suffix.lower() == ".json":
            yield path
        elif path.is_dir():
            yield from sorted(p for p in path.rglob("*.json") if p.is_file())


def enriched_files_from_products_dir(products_dir: Path) -> list[Path]:
    if not products_dir.exists():
        return []
    return sorted(products_dir.glob("*_enriched/enriched/*.json"))


def scored_files_from_products_dir(products_dir: Path) -> list[Path]:
    if not products_dir.exists():
        return []
    return sorted(products_dir.glob("*_scored/scored/*.json"))


def collect_product_files(args: argparse.Namespace, *, prefer_enriched: bool = True) -> list[Path]:
    files: list[Path] = []
    for value in getattr(args, "enriched_file", []) or []:
        files.append(repo_path(value))
    for value in getattr(args, "product_file", []) or []:
        files.append(repo_path(value))
    for value in getattr(args, "enriched_dir", []) or []:
        files.extend(iter_json_files([repo_path(value)]))
    products_dir = getattr(args, "products_dir", None)
    if products_dir:
        root = repo_path(products_dir)
        if prefer_enriched:
            files.extend(enriched_files_from_products_dir(root))
        elif getattr(args, "prefer_scored", False):
            files.extend(scored_files_from_products_dir(root))
        else:
            files.extend(iter_json_files([root]))
    dist_dir = getattr(args, "dist_dir", None)
    if dist_dir and not files:
        dist_path = repo_path(dist_dir)
        detail_blobs_dir = dist_path / "detail_blobs"
        if detail_blobs_dir.exists():
            files.extend(iter_json_files([detail_blobs_dir]))
            return sorted(dict.fromkeys(files))
        db_path = dist_path / "pharmaguide_core.db"
        if db_path.exists():
            files.extend(extract_detail_blobs(db_path))
    return sorted(dict.fromkeys(files))


def extract_detail_blobs(db_path: Path) -> list[Path]:
    """Extract final DB detail blobs into a temp-ish sibling folder for audits.

    Release strict cleaner/clinical audits should normally run on enriched
    products. This fallback lets export audits inspect final DB content when
    explicit enriched artifacts are not supplied.
    """
    out_dir = db_path.parent / ".contract_detail_blobs"
    out_dir.mkdir(exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        table_names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "products" not in table_names:
            return []
        columns = {row[1] for row in conn.execute("PRAGMA table_info(products)")}
        if not {"id", "detail_blob"}.issubset(columns):
            return []
        rows = conn.execute("SELECT id, detail_blob FROM products WHERE detail_blob IS NOT NULL").fetchall()
    files: list[Path] = []
    for row in rows:
        product_id = str(row["id"] or "unknown")
        path = out_dir / f"{product_id}.json"
        try:
            payload = json.loads(row["detail_blob"])
        except Exception:
            continue
        write_json(path, payload)
        files.append(path)
    return files


def is_enzyme_identity(row: dict[str, Any]) -> bool:
    text = " ".join(
        str(row.get(key) or "")
        for key in ("name", "ingredient_name", "display_name", "raw_name", "label", "canonical_id", "iqm_parent_id")
    )
    return bool(re.search(r"\b(serrapeptase|nattokinase|enzyme|protease|amylase|lipase|bromelain|papain)\b", text, re.I))


def has_activity_dose_evidence(row: dict[str, Any]) -> bool:
    if str(row.get("dose_class") or "") == "enzyme_activity":
        return True
    text = " ".join(str(row.get(key) or "") for key in ("quantity_text", "amount_text", "unit", "units", "quantity", "amount"))
    return any(re.search(rf"\b{re.escape(unit)}\b", text, re.I) for unit in ACTIVITY_UNITS)


def find_iqd(product: dict[str, Any]) -> dict[str, Any]:
    iqd = product.get("ingredient_quality_data")
    return iqd if isinstance(iqd, dict) else {}


def scorable_rows(product: dict[str, Any]) -> list[dict[str, Any]]:
    iqd = find_iqd(product)
    rows = iqd.get("ingredients_scorable")
    if isinstance(rows, list):
        return [r for r in rows if isinstance(r, dict)]
    rows = product.get("ingredients_scorable")
    if isinstance(rows, list):
        return [r for r in rows if isinstance(r, dict)]
    return []


def all_iqd_rows(product: dict[str, Any]) -> list[dict[str, Any]]:
    iqd = find_iqd(product)
    rows: list[dict[str, Any]] = []
    for key in ("ingredients", "ingredients_scorable", "ingredients_recognized_non_scorable", "ingredients_skipped"):
        value = iqd.get(key)
        if isinstance(value, list):
            rows.extend(r for r in value if isinstance(r, dict))
    return rows


def cleaner_source_rows(product: dict[str, Any]) -> Iterable[tuple[str, int, dict[str, Any]]]:
    for section in ("activeIngredients", "inactiveIngredients"):
        value = product.get(section)
        if not isinstance(value, list):
            continue
        for idx, row in enumerate(value):
            if isinstance(row, dict):
                yield section, idx, row


def row_name(row: dict[str, Any]) -> str:
    for key in ("name", "ingredient_name", "label", "display_name", "raw_name", "name_original"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def canonical_id(row: dict[str, Any]) -> str:
    for key in ("canonical_id", "iqm_parent_id", "ingredient_id", "matched_parent_id"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return ""


def has_dose_evidence(row: dict[str, Any]) -> bool:
    dose_class = str(row.get("dose_class") or "").strip()
    if dose_class in VALID_NON_MASS_DOSE_CLASSES:
        return True
    if dose_class == "percent_dv_only":
        return numeric_value(
            row.get("percent_daily_value")
            or row.get("daily_value_percent")
            or row.get("percent_dv")
        ) > 0
    for key in ("quantity", "amount", "dose_amount", "value", "activity_value"):
        value = row.get(key)
        if positive_number_in_text(value):
            return True
    text = " ".join(str(row.get(key) or "") for key in ("quantity_text", "amount_text", "unit", "units"))
    return any(re.search(rf"\b{re.escape(unit)}\b", text, re.I) for unit in ACTIVITY_UNITS)


def row_is_fallback_decision(row: dict[str, Any]) -> bool:
    reason = str(row.get("fallback_reason") or row.get("identity_decision_reason") or row.get("recognition_reason") or "")
    return bool(
        row.get("fallback_class")
        or row.get("recognized_non_scorable")
        or any(token in reason for token in FALLBACK_DECISION_REASONS)
    )


def product_identity(product: dict[str, Any]) -> str:
    for key in ("id", "product_id", "dsld_id", "entry_id", "fullName", "name", "product_name"):
        value = product.get(key)
        if value not in (None, ""):
            return str(value)
    return "unknown"


def audit_matrix(args: argparse.Namespace) -> list[Finding]:
    matrix_path = repo_path(args.matrix)
    findings: list[Finding] = []
    if not matrix_path.exists():
        return [Finding("MATRIX_MISSING", "source-of-truth matrix file is missing", str(matrix_path))]
    try:
        matrix = load_json(matrix_path)
    except Exception as exc:
        return [Finding("MATRIX_INVALID_JSON", f"cannot parse matrix JSON: {exc}", str(matrix_path))]

    metadata = matrix.get("_metadata") if isinstance(matrix, dict) else None
    if not isinstance(metadata, dict) or not metadata.get("schema_version"):
        findings.append(Finding("MATRIX_METADATA", "matrix must declare _metadata.schema_version", str(matrix_path)))

    allowed = set(matrix.get("allowed_fallback_classes") or [])
    missing_allowed = ALLOWED_FALLBACK_CLASSES - allowed
    if missing_allowed:
        findings.append(Finding("MATRIX_FALLBACK_ENUM", f"missing allowed fallback classes: {sorted(missing_allowed)}", str(matrix_path)))

    declared_required = set(matrix.get("required_concepts") or [])
    missing_declared = REQUIRED_CONCEPTS - declared_required
    if missing_declared:
        findings.append(Finding("MATRIX_REQUIRED_DECLARATION", f"required_concepts omits: {sorted(missing_declared)}", str(matrix_path)))

    concepts = matrix.get("concepts")
    if not isinstance(concepts, list):
        return findings + [Finding("MATRIX_CONCEPTS", "matrix.concepts must be a list", str(matrix_path))]

    by_id: dict[str, dict[str, Any]] = {}
    for idx, concept in enumerate(concepts):
        path = f"{matrix_path}#/concepts/{idx}"
        if not isinstance(concept, dict):
            findings.append(Finding("MATRIX_CONCEPT_TYPE", "concept entry must be an object", path))
            continue
        concept_id = concept.get("concept_id")
        if not isinstance(concept_id, str) or not concept_id:
            findings.append(Finding("MATRIX_CONCEPT_ID", "concept entry must have concept_id", path))
            continue
        if concept_id in by_id:
            findings.append(Finding("MATRIX_DUPLICATE_CONCEPT", f"duplicate concept_id {concept_id}", path))
        by_id[concept_id] = concept
        missing_fields = sorted(field for field in REQUIRED_MATRIX_FIELDS if concept.get(field) in (None, "", [], {}))
        if missing_fields:
            findings.append(Finding("MATRIX_CONCEPT_FIELDS", f"{concept_id} missing fields: {missing_fields}", path))
        fallback = concept.get("fallback_class")
        if fallback not in ALLOWED_FALLBACK_CLASSES:
            findings.append(Finding("MATRIX_FALLBACK_CLASS", f"{concept_id} uses invalid fallback_class {fallback!r}", path))
        if args.strict_release and fallback == "dev_only_missing_vocab" and concept.get("retirement_status") != "retired":
            findings.append(Finding("MATRIX_DEV_FALLBACK_RELEASE", f"{concept_id} uses dev_only_missing_vocab in strict release mode", path))

        for ref_key in ("owner", "release_gate"):
            ref = concept.get(ref_key)
            if isinstance(ref, str):
                check_repo_reference(ref, findings, concept_id, ref_key, path)
        for ref_key in ("source_data_files", "tests"):
            for ref in concept.get(ref_key) or []:
                if isinstance(ref, str):
                    check_repo_reference(ref, findings, concept_id, ref_key, path)

    missing_concepts = REQUIRED_CONCEPTS - set(by_id)
    if missing_concepts:
        findings.append(Finding("MATRIX_REQUIRED_CONCEPTS", f"matrix missing required concepts: {sorted(missing_concepts)}", str(matrix_path)))
    return findings


def check_repo_reference(ref: str, findings: list[Finding], concept_id: str, ref_key: str, path: str) -> None:
    if ref.startswith(("scripts/", "README.md", "AGENTS.md", "docs/")):
        target = repo_path(ref.split()[0])
        if not target.exists():
            findings.append(Finding("MATRIX_BROKEN_REFERENCE", f"{concept_id}.{ref_key} references missing file {ref}", path))


def audit_cleaner(args: argparse.Namespace) -> list[Finding]:
    files = collect_product_files(args)
    findings: list[Finding] = []
    if not files:
        return [Finding("CLEANER_NO_INPUT", "no enriched product files found for cleaner contract audit")]
    for file_path in files:
        try:
            products = as_products(load_json(file_path))
        except Exception as exc:
            findings.append(Finding("CLEANER_JSON_ERROR", f"cannot read product JSON: {exc}", str(file_path)))
            continue
        for product in products:
            pid = product_identity(product)
            for section, idx, row in cleaner_source_rows(product):
                missing = sorted(field for field in REQUIRED_CLEANER_ROW_FIELDS if field not in row)
                if missing:
                    findings.append(Finding(
                        "CLEANER_SOURCE_ROW_FIELD_MISSING",
                        f"{pid}: {section}[{idx}] missing cleaner contract fields {missing} ({row_name(row)})",
                        str(file_path),
                    ))
            if not find_iqd(product):
                findings.append(Finding("IQD_MISSING", f"{pid}: product lacks ingredient_quality_data for cleaner contract enforcement", str(file_path)))
                continue
            for row in all_iqd_rows(product):
                name = row_name(row)
                if not row.get("raw_source_path"):
                    findings.append(Finding("IQD_MISSING_RAW_SOURCE_PATH", f"{pid}: IQD row lacks raw_source_path ({name})", str(file_path)))
                if not row.get("source_section"):
                    findings.append(Finding("IQD_MISSING_SOURCE_SECTION", f"{pid}: IQD row lacks source_section ({name})", str(file_path)))
            for row in scorable_rows(product):
                role = str(row.get("cleaner_row_role") or "").strip()
                name = row_name(row)
                eligible = row.get("score_eligible_by_cleaner") is True
                allowed_misfiled = role == "active_misfiled_in_inactive" and has_dose_evidence(row)
                if not eligible and not allowed_misfiled:
                    findings.append(Finding("IQD_SCORABLE_NOT_CLEANER_ELIGIBLE", f"{pid}: scorable row not cleaner eligible ({name})", str(file_path)))
                if role in SCORABLE_BLOCKED_ROLES:
                    findings.append(Finding("IQD_BLOCKED_ROLE_SCORABLE", f"{pid}: non-scorable cleaner role entered IQD scorable ({role}: {name})", str(file_path)))
                if row.get("source_section") == "inactive" and not allowed_misfiled:
                    findings.append(Finding("IQD_INACTIVE_PROMOTED", f"{pid}: inactive row promoted without active_misfiled_in_inactive dose evidence ({name})", str(file_path)))
                if row.get("scoreable_identity") is not True:
                    findings.append(Finding("IQD_SCORABLE_NOT_SCOREABLE_IDENTITY", f"{pid}: scorable row lacks scoreable_identity=true ({name})", str(file_path)))
                if str(row.get("role_classification") or "") != "active_scorable":
                    findings.append(Finding("IQD_SCORABLE_ROLE_NOT_ACTIVE", f"{pid}: scorable row role_classification is not active_scorable ({name})", str(file_path)))
                if not has_dose_evidence(row):
                    findings.append(Finding("IQD_SCORABLE_MISSING_DOSE_EVIDENCE", f"{pid}: scorable row lacks dose evidence ({name})", str(file_path)))
    return findings


def audit_enrichment(args: argparse.Namespace) -> list[Finding]:
    files = collect_product_files(args)
    findings: list[Finding] = []
    if not files:
        return [Finding("ENRICHMENT_NO_INPUT", "no enriched product files found for enrichment contract audit")]
    for file_path in files:
        try:
            products = as_products(load_json(file_path))
        except Exception as exc:
            findings.append(Finding("ENRICHMENT_JSON_ERROR", f"cannot read product JSON: {exc}", str(file_path)))
            continue
        for product in products:
            pid = product_identity(product)
            iqd = find_iqd(product)
            if not iqd:
                findings.append(Finding("ENRICHMENT_IQD_MISSING", f"{pid}: product lacks ingredient_quality_data", str(file_path)))
                continue
            if not isinstance(iqd.get("ingredients_scorable"), list):
                findings.append(Finding("ENRICHMENT_IQD_SCORABLE_LIST", f"{pid}: ingredients_scorable must be a list", str(file_path)))
            if not isinstance(iqd.get("ingredients_recognized_non_scorable"), list):
                findings.append(Finding("ENRICHMENT_IQD_RECOGNIZED_LIST", f"{pid}: ingredients_recognized_non_scorable must be a list", str(file_path)))
            if not isinstance(iqd.get("ingredients_skipped"), list):
                findings.append(Finding("ENRICHMENT_IQD_SKIPPED_LIST", f"{pid}: ingredients_skipped must be a list", str(file_path)))

            for idx, row in enumerate(all_iqd_rows(product)):
                name = row_name(row)
                missing = sorted(field for field in REQUIRED_ENRICHMENT_ROW_FIELDS if field not in row)
                if missing:
                    findings.append(Finding("ENRICHMENT_ROW_FIELD_MISSING", f"{pid}: IQD row missing enrichment fields {missing} ({name})", str(file_path)))
                if row.get("cleaner_contract_fallback_used") is True:
                    fields = row.get("cleaner_contract_missing_fields") or []
                    findings.append(Finding(
                        "ENRICHMENT_CLEANER_CONTRACT_FALLBACK_USED",
                        f"{pid}: IQD row used old-batch cleaner defaults {fields} ({name})",
                        str(file_path),
                    ))
                if row_is_fallback_decision(row) and (not row.get("fallback_class") or not row.get("fallback_reason")):
                    findings.append(Finding("ENRICHMENT_FALLBACK_DIAGNOSTICS_MISSING", f"{pid}: fallback IQD decision lacks fallback_class/fallback_reason ({name})", str(file_path)))

            for row in scorable_rows(product):
                name = row_name(row)
                if row.get("recognized_non_scorable") or str(row.get("role_classification") or "") == "recognized_non_scorable":
                    findings.append(Finding("ENRICHMENT_RECOGNIZED_IN_SCORABLE", f"{pid}: recognized non-scorable row entered ingredients_scorable ({name})", str(file_path)))
                if row.get("score_eligible_by_cleaner") is not True:
                    findings.append(Finding("ENRICHMENT_SCORABLE_NOT_CLEANER_ELIGIBLE", f"{pid}: scorable row not cleaner eligible ({name})", str(file_path)))
                if row.get("scoreable_identity") is not True:
                    findings.append(Finding("ENRICHMENT_SCORABLE_NOT_SCOREABLE_IDENTITY", f"{pid}: scorable row lacks scoreable_identity=true ({name})", str(file_path)))
                if str(row.get("role_classification") or "") != "active_scorable":
                    findings.append(Finding("ENRICHMENT_SCORABLE_ROLE_NOT_ACTIVE", f"{pid}: scorable row role_classification is not active_scorable ({name})", str(file_path)))
                if not has_dose_evidence(row):
                    findings.append(Finding("ENRICHMENT_SCORABLE_MISSING_DOSE", f"{pid}: scorable row lacks dose evidence ({name})", str(file_path)))

            taxonomy = product.get("supplement_taxonomy")
            if isinstance(taxonomy, dict) and taxonomy.get("classification_input_source") == "ingredient_quality_data.ingredients_fallback":
                findings.append(Finding("ENRICHMENT_TAXONOMY_USED_IQD_FALLBACK", f"{pid}: taxonomy consumed IQD ingredients fallback", str(file_path)))

            scoring_diag = product.get("iqd_contract_diagnostics")
            if not isinstance(scoring_diag, dict):
                scoring_meta = product.get("scoring_metadata")
                if isinstance(scoring_meta, dict):
                    scoring_diag = scoring_meta.get("iqd_contract_diagnostics")
            if isinstance(scoring_diag, dict) and scoring_diag.get("iqd_ingredients_fallback_used") is True:
                findings.append(Finding("ENRICHMENT_SCORING_USED_IQD_FALLBACK", f"{pid}: scoring consumed IQD ingredients fallback", str(file_path)))

            product_evidence = product.get("product_scoring_evidence") or []
            if isinstance(product_evidence, dict):
                product_evidence = product_evidence.get("items") or product_evidence.get("evidence") or [product_evidence]
            if not isinstance(product_evidence, list):
                findings.append(Finding("ENRICHMENT_PRODUCT_EVIDENCE_SHAPE", f"{pid}: product_scoring_evidence must be a list/object", str(file_path)))
                product_evidence = []
            for idx, evidence in enumerate(product_evidence):
                if not isinstance(evidence, dict):
                    findings.append(Finding("ENRICHMENT_PRODUCT_EVIDENCE_SHAPE", f"{pid}: product evidence #{idx} is not an object", str(file_path)))
                    continue
                if evidence.get("scoreable") is True:
                    missing = [
                        field
                        for field in (
                            "evidence_type",
                            "scoreable_identity",
                            "score_eligible_by_cleaner",
                            "dose_class",
                            "dose_value",
                            "dose_unit",
                            "source",
                            "raw_source_path",
                            "evidence_scope",
                            "linked_rows",
                            "confidence",
                            "reason",
                        )
                        if evidence.get(field) in (None, "", [])
                    ]
                    if missing:
                        findings.append(Finding("ENRICHMENT_PRODUCT_EVIDENCE_FIELD_MISSING", f"{pid}: scoreable product evidence missing {missing}", str(file_path)))
                    if evidence.get("evidence_type") == "probiotic_cfu":
                        taxonomy_primary_type = str(_safe_dict(product.get("supplement_taxonomy")).get("primary_type") or "").lower()
                        if taxonomy_primary_type != "probiotic":
                            findings.append(Finding("ENRICHMENT_PRODUCT_CFU_FALSE_POSITIVE", f"{pid}: scoreable probiotic_cfu evidence on non-probiotic taxonomy {taxonomy_primary_type!r}", str(file_path)))
                elif evidence.get("evidence_type") == "probiotic_cfu" and not evidence.get("rejection_reason"):
                    findings.append(Finding("ENRICHMENT_PRODUCT_CFU_REJECTION_REASON_MISSING", f"{pid}: rejected probiotic_cfu evidence lacks rejection_reason", str(file_path)))

            probiotic_data = _safe_dict(product.get("probiotic_data"))
            total_cfu = numeric_value(probiotic_data.get("total_cfu"))
            if total_cfu > 0 and not any(isinstance(e, dict) and e.get("evidence_type") == "probiotic_cfu" for e in product_evidence):
                findings.append(Finding("ENRICHMENT_PRODUCT_CFU_EVIDENCE_MISSING", f"{pid}: probiotic_data.total_cfu has no probiotic_cfu product_scoring_evidence diagnostic", str(file_path)))
    return findings


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _scoring_diag(product: dict[str, Any]) -> dict[str, Any]:
    diag = product.get("iqd_contract_diagnostics")
    if isinstance(diag, dict):
        return diag
    meta = product.get("scoring_metadata")
    if isinstance(meta, dict):
        diag = meta.get("iqd_contract_diagnostics")
        if isinstance(diag, dict):
            return diag
    return {}


def audit_scoring(args: argparse.Namespace) -> list[Finding]:
    files = collect_product_files(args, prefer_enriched=False)
    findings: list[Finding] = []
    if not files:
        return [Finding("SCORING_NO_INPUT", "no scored product files found for scoring contract audit")]

    allowed_sources = {
        "ingredient_quality_data.ingredients_scorable",
        "ingredient_quality_data.ingredients_scorable+product_scoring_evidence",
    }
    for file_path in files:
        try:
            products = as_products(load_json(file_path))
        except Exception as exc:
            findings.append(Finding("SCORING_JSON_ERROR", f"cannot read scored product JSON: {exc}", str(file_path)))
            continue
        for product in products:
            pid = product_identity(product)
            verdict = str(product.get("verdict") or "").upper()
            diag = _scoring_diag(product)
            source = (
                product.get("scoring_ingredients_source")
                or diag.get("scoring_ingredients_source")
                or _safe_dict(product.get("scoring_metadata")).get("scoring_ingredients_source")
            )
            if source not in allowed_sources and verdict not in {"BLOCKED", "UNSAFE", "NUTRITION_ONLY"}:
                findings.append(Finding("SCORING_SOURCE_FORBIDDEN", f"{pid}: scoring source {source!r} is not strict scorable input", str(file_path)))
            if diag.get("iqd_ingredients_fallback_used") is True:
                findings.append(Finding("SCORING_USED_IQD_FALLBACK", f"{pid}: scoring consumed ingredient_quality_data.ingredients fallback", str(file_path)))

            fallback_rows = product.get("scoring_fallbacks_used") or diag.get("scoring_fallbacks_used") or []
            for fallback in fallback_rows:
                if not isinstance(fallback, dict):
                    continue
                if fallback.get("fallback_class") == "dev_only_missing_vocab":
                    findings.append(Finding("SCORING_DEV_FALLBACK", f"{pid}: dev_only_missing_vocab fallback used in scoring", str(file_path)))
                if not fallback.get("fallback_class") or not fallback.get("fallback_reason"):
                    findings.append(Finding("SCORING_FALLBACK_DIAGNOSTICS_MISSING", f"{pid}: scoring fallback lacks class/reason", str(file_path)))

            strict_contract = product.get("strict_scoring_contract")
            if not isinstance(strict_contract, dict):
                strict_contract = _safe_dict(_safe_dict(product.get("scoring_metadata")).get("strict_scoring_contract"))
            if not strict_contract:
                findings.append(Finding("SCORING_STRICT_CONTRACT_MISSING", f"{pid}: missing strict_scoring_contract diagnostics", str(file_path)))
            elif strict_contract.get("passed") is not True:
                findings.append(Finding(
                    "SCORING_STRICT_CONTRACT_FAILED",
                    f"{pid}: strict scoring contract did not pass: {strict_contract.get('findings') or strict_contract.get('reason')}",
                    str(file_path),
                ))

            coverage = mapped_coverage_value(product)
            if verdict == "SAFE" and coverage is not None and coverage < 0.3:
                findings.append(Finding("SCORING_SAFE_LOW_COVERAGE", f"{pid}: SAFE with mapped_coverage={coverage}", str(file_path)))
            if verdict == "NUTRITION_ONLY":
                if product.get("scoring_status") != "not_applicable":
                    findings.append(Finding("SCORING_NUTRITION_STATUS", f"{pid}: NUTRITION_ONLY must use scoring_status=not_applicable", str(file_path)))
                if product.get("score_basis") != "nutrition_only_food_shape":
                    findings.append(Finding("SCORING_NUTRITION_BASIS", f"{pid}: NUTRITION_ONLY must use score_basis=nutrition_only_food_shape", str(file_path)))
                if product.get("quality_score") is not None or product.get("score_80") is not None or product.get("score_100_equivalent") is not None:
                    findings.append(Finding("SCORING_NUTRITION_SCORE_NULL", f"{pid}: NUTRITION_ONLY must have null score fields", str(file_path)))
                if product.get("mapped_coverage_applicable") is not False:
                    findings.append(Finding("SCORING_NUTRITION_COVERAGE_APPLICABILITY", f"{pid}: NUTRITION_ONLY must set mapped_coverage_applicable=false", str(file_path)))
    return findings


STATIC_FORBIDDEN_PATTERNS = [
    ("V4_IQD_INGREDIENTS_FALLBACK", re.compile(r"iqd\.get\([\"']ingredients[\"']\)")),
    ("V4_RAW_ACTIVE_FALLBACK", re.compile(r"product\.get\([\"'](?:activeIngredients|active_ingredients)[\"']\)")),
    ("V4_PRIMARY_CATEGORY_ROUTING", re.compile(r"\.get\([\"']primary_category[\"']\)")),
]


def audit_scoring_static(args: argparse.Namespace) -> list[Finding]:
    findings: list[Finding] = []
    files: list[Path] = []
    for value in getattr(args, "path", None) or ["scripts/scoring_v4"]:
        root = repo_path(value)
        if root.is_file() and root.suffix == ".py":
            files.append(root)
        elif root.is_dir():
            files.extend(sorted(root.rglob("*.py")))
    for file_path in files:
        if file_path.name in {"generic_helpers.py"}:
            continue
        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
        except Exception as exc:
            findings.append(Finding("SCORING_STATIC_READ_ERROR", f"cannot read {file_path}: {exc}", str(file_path)))
            continue
        for line_no, line in enumerate(lines, start=1):
            if "scoring-contract-legacy-compat" in line or "display/search" in line:
                continue
            for code, pattern in STATIC_FORBIDDEN_PATTERNS:
                if pattern.search(line):
                    try:
                        rel = file_path.relative_to(REPO_ROOT)
                    except ValueError:
                        rel = file_path
                    findings.append(Finding(code, f"{rel}:{line_no} reads forbidden scoring fallback field", str(file_path)))
    return findings


def taxonomy_primary(product: dict[str, Any]) -> str:
    taxonomy = product.get("supplement_taxonomy")
    if isinstance(taxonomy, dict):
        for key in ("primary_type", "percentile_category", "category"):
            value = taxonomy.get(key)
            if isinstance(value, str) and value:
                return value
    for key in ("primary_type", "percentile_category", "supplement_type"):
        value = product.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def product_text(product: dict[str, Any]) -> str:
    pieces: list[str] = []
    for key in ("name", "fullName", "product_name", "brandName", "manufacturer", "description"):
        value = product.get(key)
        if isinstance(value, str):
            pieces.append(value)
    return " ".join(pieces)


def safety_text(product: dict[str, Any]) -> str:
    pieces: list[str] = []
    for key in ("banned_substances", "contaminant_data", "safety_flags", "warnings"):
        value = product.get(key)
        if value:
            pieces.append(json.dumps(value, ensure_ascii=True, sort_keys=True))
    for row in scorable_rows(product):
        pieces.append(json.dumps(row, ensure_ascii=True, sort_keys=True))
    return " ".join(pieces)


def taxonomy_has_omega_scorable_evidence(product: dict[str, Any]) -> bool:
    """Return true when taxonomy preserved explicit omega ingredient evidence.

    Scored artifacts do not always carry full IQD rows. In that shape, the
    clinical drift gate should still accept taxonomy that declares strict
    scorable input plus EPA/DHA/fish-oil evidence in its structured reasons.
    """
    taxonomy = product.get("supplement_taxonomy")
    if not isinstance(taxonomy, dict):
        return False
    if taxonomy.get("classification_input_source") != "ingredient_quality_data.ingredients_scorable":
        return False
    breakdown = taxonomy.get("category_breakdown")
    if isinstance(breakdown, dict) and numeric_value(breakdown.get("fatty_acid"), 0.0) > 0:
        return True
    reasons = taxonomy.get("classification_reasons")
    if not isinstance(reasons, list):
        return False
    reason_text = " ".join(str(item) for item in reasons).lower()
    return (
        "omega-3:" in reason_text
        and "ids=" in reason_text
        and any(hint in reason_text for hint in OMEGA_CANONICAL_HINTS)
    )


def audit_clinical(args: argparse.Namespace) -> list[Finding]:
    files = collect_product_files(args)
    findings: list[Finding] = []
    if not files:
        return [Finding("CLINICAL_NO_INPUT", "no product files found for clinical drift audit")]
    for file_path in files:
        try:
            products = as_products(load_json(file_path))
        except Exception as exc:
            findings.append(Finding("CLINICAL_JSON_ERROR", f"cannot read product JSON: {exc}", str(file_path)))
            continue
        for product in products:
            pid = product_identity(product)
            rows = scorable_rows(product)
            row_ids = {canonical_id(row) for row in rows}
            text = product_text(product)
            safety = safety_text(product)

            chromium_label_text = " ".join(
                [text]
                + [
                    " ".join(str(row.get(key) or "") for key in ("name", "ingredient_name", "display_name", "raw_name", "label"))
                    for row in rows + all_iqd_rows(product)
                ]
            )
            if "HM_CHROMIUM_HEXAVALENT" in safety and GENERIC_CHROMIUM_RE.search(chromium_label_text) and not CRVI_TEXT_RE.search(chromium_label_text):
                findings.append(Finding("GENERIC_CHROMIUM_CRVI", f"{pid}: generic chromium appears to match Cr(VI) safety rule", str(file_path)))

            primary = taxonomy_primary(product).lower()
            has_omega_row = any(any(hint in cid for hint in OMEGA_CANONICAL_HINTS) for cid in row_ids)
            if primary == "omega_3" and not (has_omega_row or taxonomy_has_omega_scorable_evidence(product)):
                findings.append(Finding("PRODUCT_NAME_ONLY_OMEGA3", f"{pid}: omega_3 taxonomy lacks scorable omega canonical evidence", str(file_path)))

            if primary == "sleep_support":
                has_sleep_identity = bool(SLEEP_TEXT_RE.search(text)) or any(any(hint in cid for hint in SLEEP_CANONICAL_HINTS) for cid in row_ids)
                pm_only = re.search(r"\bPM\b", text) is not None and not SLEEP_TEXT_RE.search(text.replace("PM", ""))
                if pm_only and not has_sleep_identity:
                    findings.append(Finding("PM_ONLY_SLEEP_SUPPORT", f"{pid}: PM-only token drove sleep_support taxonomy", str(file_path)))

            all_rows = rows + all_iqd_rows(product)
            has_enzyme_activity_source = any(is_enzyme_identity(row) and has_activity_dose_evidence(row) for row in all_rows)
            if has_enzyme_activity_source:
                has_enzyme_activity_row = any(is_enzyme_identity(row) and has_activity_dose_evidence(row) for row in rows)
                if not has_enzyme_activity_row:
                    findings.append(Finding("ENZYME_ACTIVITY_NOT_DOSE_EVIDENCE", f"{pid}: enzyme activity units did not survive as scorable dose evidence", str(file_path)))

            legacy_form = str(product.get("form_factor") or "").lower()
            canonical_form = str(product.get("form_factor_canonical") or "").lower()
            if "softgel" in legacy_form and canonical_form and canonical_form != "softgel":
                findings.append(Finding("FORM_FACTOR_CANONICAL_NOT_SOFTGEL", f"{pid}: softgel legacy form exported with canonical {canonical_form}", str(file_path)))
    return findings


def audit_export(args: argparse.Namespace) -> list[Finding]:
    dist_dir = repo_path(args.dist_dir)
    manifest_path = dist_dir / "export_manifest.json"
    db_path = dist_dir / "pharmaguide_core.db"
    findings: list[Finding] = []
    if not manifest_path.exists():
        findings.append(Finding("EXPORT_MANIFEST_MISSING", "export manifest missing", str(manifest_path)))
    if not db_path.exists():
        findings.append(Finding("EXPORT_DB_MISSING", "catalog DB missing", str(db_path)))
    if findings:
        return findings
    manifest = load_json(manifest_path)
    for key in ("schema_version", "product_count", "checksum_sha256"):
        if not manifest.get(key):
            findings.append(Finding("EXPORT_MANIFEST_FIELD", f"export manifest missing {key}", str(manifest_path)))
    actual_checksum = sha256_file(db_path)
    if manifest.get("checksum_sha256") and manifest.get("checksum_sha256") != actual_checksum:
        findings.append(Finding("EXPORT_DB_CHECKSUM_MISMATCH", "export manifest checksum does not match pharmaguide_core.db", str(db_path)))

    interaction_manifest_path = dist_dir / "interaction_db_manifest.json"
    if interaction_manifest_path.exists():
        interaction_manifest = load_json(interaction_manifest_path)
        if manifest.get("interaction_db_checksum") not in (None, interaction_manifest.get("checksum_sha256")):
            findings.append(Finding("EXPORT_INTERACTION_CHECKSUM_MISMATCH", "export manifest interaction_db_checksum differs from interaction manifest", str(manifest_path)))
        if manifest.get("interaction_db_version") not in (None, interaction_manifest.get("interaction_db_version")):
            findings.append(Finding("EXPORT_INTERACTION_VERSION_MISMATCH", "export manifest interaction_db_version differs from interaction manifest", str(manifest_path)))

    if args.require_stamped_manifest:
        for key in (
            "pipeline_contract_version",
            "source_of_truth_matrix_version",
            "strict_gate_summary",
            "artifact_freshness_status",
            "interaction_db_checksum",
            "interaction_db_version",
        ):
            if key not in manifest:
                findings.append(Finding("EXPORT_MANIFEST_CONTRACT_FIELD", f"stamped export manifest missing {key}", str(manifest_path)))
    return findings


def load_severity_vocab(path: Path) -> set[str]:
    payload = load_json(path)
    severities = payload.get("severities") if isinstance(payload, dict) else None
    if isinstance(severities, list):
        return {str(item.get("id")) for item in severities if isinstance(item, dict) and item.get("id")}
    values = payload.get("severity_levels") if isinstance(payload, dict) else None
    if isinstance(values, list):
        return {str(value) for value in values}
    return set()


def source_rule_count(path: Path) -> int:
    payload = load_json(path)
    if isinstance(payload, dict):
        for key in ("interaction_rules", "rules", "interactions"):
            value = payload.get(key)
            if isinstance(value, list):
                return len(value)
    if isinstance(payload, list):
        return len(payload)
    return 0


def audit_interaction(args: argparse.Namespace) -> list[Finding]:
    dist_dir = repo_path(args.dist_dir)
    db_path = dist_dir / "interaction_db.sqlite"
    manifest_path = dist_dir / "interaction_db_manifest.json"
    source_rules = repo_path(args.source_rules)
    severity_vocab = repo_path(args.severity_vocab)
    findings: list[Finding] = []
    for path, code in ((db_path, "INTERACTION_DB_MISSING"), (manifest_path, "INTERACTION_MANIFEST_MISSING"), (source_rules, "INTERACTION_RULES_MISSING"), (severity_vocab, "INTERACTION_SEVERITY_VOCAB_MISSING")):
        if not path.exists():
            findings.append(Finding(code, f"missing required interaction artifact {path}", str(path)))
    if findings:
        return findings

    manifest = load_json(manifest_path)
    if manifest.get("checksum_sha256") != sha256_file(db_path):
        findings.append(Finding("INTERACTION_CHECKSUM_MISMATCH", "interaction DB checksum does not match manifest", str(db_path)))

    with sqlite3.connect(db_path) as conn:
        interaction_count = conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]
        retired_count = conn.execute("SELECT COUNT(*) FROM interactions WHERE retired_at IS NOT NULL OR retired_reason IS NOT NULL").fetchone()[0]
        severities = {row[0] for row in conn.execute("SELECT DISTINCT severity FROM interactions WHERE severity IS NOT NULL")}
        metadata_rows = dict(conn.execute("SELECT key, value FROM interaction_db_metadata").fetchall())

    if interaction_count <= 0:
        findings.append(Finding("INTERACTION_EMPTY", "interaction DB has no active interactions", str(db_path)))
    if manifest.get("total_interactions") != interaction_count:
        findings.append(Finding("INTERACTION_COUNT_MISMATCH", f"manifest total_interactions={manifest.get('total_interactions')} but DB has {interaction_count}", str(manifest_path)))
    if retired_count:
        findings.append(Finding("INTERACTION_RETIRED_INCLUDED", f"retired interaction rows included in release DB: {retired_count}", str(db_path)))
    allowed_severities = load_severity_vocab(severity_vocab)
    invalid_severities = severities - allowed_severities
    if invalid_severities:
        findings.append(Finding("INTERACTION_SEVERITY_INVALID", f"invalid severities in DB: {sorted(invalid_severities)}", str(db_path)))
    if source_rule_count(source_rules) <= 0:
        findings.append(Finding("INTERACTION_SOURCE_RULES_EMPTY", "source rule file has no rules", str(source_rules)))
    source_count = source_rule_count(source_rules)
    source_drafts = int(metadata_rows.get("source_drafts_count") or manifest.get("source_drafts_count") or 0)
    if source_drafts <= 0:
        findings.append(Finding("INTERACTION_SOURCE_COUNT_MISSING", "interaction DB manifest/metadata lacks source_drafts_count", str(manifest_path)))
    elif source_count and source_drafts > source_count:
        findings.append(Finding("INTERACTION_SOURCE_COUNT_EXCEEDS_RULES", f"source_drafts_count={source_drafts} exceeds source rule count={source_count}", str(manifest_path)))
    manifest_suppai = str(manifest.get("source_suppai_count") or "")
    metadata_suppai = str(metadata_rows.get("source_suppai_count") or "")
    if manifest_suppai and metadata_suppai and manifest_suppai != metadata_suppai:
        findings.append(Finding("INTERACTION_SUPPAI_COUNT_MISMATCH", "manifest source_suppai_count differs from DB metadata", str(manifest_path)))
    db_version = metadata_rows.get("interaction_db_version") or metadata_rows.get("version")
    if str(manifest.get("interaction_db_version") or "") != str(db_version or ""):
        findings.append(Finding("INTERACTION_VERSION_MISMATCH", "manifest interaction_db_version differs from DB metadata", str(manifest_path)))
    return findings


def audit_freshness(args: argparse.Namespace) -> list[Finding]:
    dist_dir = repo_path(args.dist_dir)
    final_db_dir = repo_path(args.final_db_dir)
    products_dir = repo_path(args.products_dir)
    findings: list[Finding] = []
    catalog_db = dist_dir / "pharmaguide_core.db"
    export_manifest = dist_dir / "export_manifest.json"
    if not catalog_db.exists() or not export_manifest.exists():
        return [Finding("FRESHNESS_DIST_MISSING", "dist catalog DB or manifest missing", str(dist_dir))]

    final_manifest = final_db_dir / "export_manifest.json"
    if final_manifest.exists():
        try:
            if load_json(final_manifest).get("checksum_sha256") != load_json(export_manifest).get("checksum_sha256"):
                findings.append(Finding("FRESHNESS_FINAL_DB_MISMATCH", "final_db_output manifest checksum differs from dist manifest", str(final_manifest)))
        except Exception as exc:
            findings.append(Finding("FRESHNESS_FINAL_DB_READ_ERROR", f"cannot compare final_db_output manifest: {exc}", str(final_manifest)))

    product_files = []
    if products_dir.exists():
        product_files = sorted(products_dir.glob("*_enriched/enriched/*.json")) + sorted(products_dir.glob("*_scored/scored/*.json"))
    newest_product = newest_mtime(product_files)
    if newest_product and newest_product > catalog_db.stat().st_mtime:
        findings.append(Finding("FRESHNESS_PRODUCTS_NEWER_THAN_DIST", "enriched/scored outputs are newer than scripts/dist catalog DB", str(products_dir)))

    interaction_db = dist_dir / "interaction_db.sqlite"
    interaction_inputs = [repo_path(path) for path in getattr(args, "interaction_input", []) or []]
    if not getattr(args, "skip_interaction_inputs", False) and interaction_db.exists():
        newer_interaction_inputs = [path for path in interaction_inputs if path.exists() and path.stat().st_mtime > interaction_db.stat().st_mtime]
        if newer_interaction_inputs:
            findings.append(Finding("FRESHNESS_INTERACTION_INPUT_NEWER", "interaction source input is newer than scripts/dist interaction DB", str(newer_interaction_inputs[0])))

    return findings


def newest_mtime(paths: Iterable[Path]) -> float | None:
    mtimes = [path.stat().st_mtime for path in paths if path.exists()]
    return max(mtimes) if mtimes else None


def audit_artifact_lineage(args: argparse.Namespace) -> list[Finding]:
    enriched_dir = repo_path(args.enriched_dir)
    scored_dir = repo_path(args.scored_dir)
    if not enriched_dir.exists():
        return [Finding("ARTIFACT_LINEAGE_ENRICHED_MISSING", f"missing enriched dir {enriched_dir}", str(enriched_dir))]
    if not scored_dir.exists():
        return [Finding("ARTIFACT_LINEAGE_SCORED_MISSING", f"missing scored dir {scored_dir}", str(scored_dir))]
    findings: list[Finding] = []
    enriched_by_name = {path.name.replace("enriched_", "", 1): path for path in iter_json_files([enriched_dir])}
    scored_files = list(iter_json_files([scored_dir]))
    if not scored_files:
        return [Finding("ARTIFACT_LINEAGE_SCORED_EMPTY", f"no scored JSON artifacts under {scored_dir}", str(scored_dir))]
    for scored_path in scored_files:
        key = scored_path.name.replace("scored_", "", 1)
        enriched_path = enriched_by_name.get(key)
        if not enriched_path:
            findings.append(Finding("ARTIFACT_LINEAGE_MATCH_MISSING", f"{scored_path.name}: no matching enriched artifact", str(scored_path)))
            continue
        if scored_path.stat().st_mtime < enriched_path.stat().st_mtime:
            findings.append(Finding("ARTIFACT_LINEAGE_SCORED_STALE", f"{scored_path.name}: scored artifact older than matching enriched artifact", str(scored_path)))
    return findings


def audit_flutter(args: argparse.Namespace) -> list[Finding]:
    dist_dir = repo_path(args.dist_dir)
    flutter_assets = repo_path(args.flutter_repo) / "assets" / "db"
    findings: list[Finding] = []
    pairs = (
        ("export_manifest.json", "pharmaguide_core.db"),
        ("interaction_db_manifest.json", "interaction_db.sqlite"),
    )
    for manifest_name, db_name in pairs:
        dist_manifest = dist_dir / manifest_name
        flutter_manifest = flutter_assets / manifest_name
        dist_db = dist_dir / db_name
        flutter_db = flutter_assets / db_name
        for path in (dist_manifest, flutter_manifest, dist_db, flutter_db):
            if not path.exists():
                findings.append(Finding("FLUTTER_ARTIFACT_MISSING", f"missing Flutter parity artifact {path}", str(path)))
        if any(not path.exists() for path in (dist_manifest, flutter_manifest, dist_db, flutter_db)):
            continue
        dist_payload = load_json(dist_manifest)
        flutter_payload = load_json(flutter_manifest)
        if dist_payload.get("checksum_sha256") != flutter_payload.get("checksum_sha256"):
            findings.append(Finding("FLUTTER_MANIFEST_CHECKSUM_MISMATCH", f"{manifest_name} checksum differs between dist and Flutter", str(flutter_manifest)))
        if sha256_file(dist_manifest) != sha256_file(flutter_manifest):
            findings.append(Finding("FLUTTER_MANIFEST_FILE_MISMATCH", f"{manifest_name} file differs between dist and Flutter", str(flutter_manifest)))
        if sha256_file(dist_db) != sha256_file(flutter_db):
            findings.append(Finding("FLUTTER_DB_CHECKSUM_MISMATCH", f"{db_name} differs between dist and Flutter", str(flutter_db)))
    return findings


def product_map_from_files(files: list[Path]) -> dict[str, dict[str, Any]]:
    products: dict[str, dict[str, Any]] = {}
    for file_path in files:
        try:
            for product in as_products(load_json(file_path)):
                products[product_identity(product)] = product
        except Exception:
            continue
    return products


def iqd_count(product: dict[str, Any], key: str) -> int:
    rows = find_iqd(product).get(key)
    return len(rows) if isinstance(rows, list) else 0


def mapped_coverage_value(product: dict[str, Any]) -> float | None:
    for key in ("mapped_coverage", "coverage"):
        value = product.get(key)
        try:
            if value is not None:
                return float(value)
        except (TypeError, ValueError):
            pass
    iqd = find_iqd(product)
    rows = iqd.get("ingredients_scorable")
    if isinstance(rows, list) and rows:
        mapped = sum(1 for row in rows if isinstance(row, dict) and row.get("mapped_identity"))
        return mapped / len(rows)
    return None


def audit_shadow_diff(args: argparse.Namespace) -> list[Finding]:
    old_files = list(iter_json_files([repo_path(args.old_dir)]))
    new_files = list(iter_json_files([repo_path(args.new_dir)]))
    old_products = product_map_from_files(old_files)
    new_products = product_map_from_files(new_files)
    findings: list[Finding] = []
    shared_ids = sorted(set(old_products) & set(new_products))
    if not shared_ids:
        return [Finding("SHADOW_DIFF_NO_OVERLAP", "old/new inputs have no overlapping product IDs")]

    taxonomy_shifts = 0
    verdict_shifts = 0
    safety_shifts = 0
    coverage_drops = 0
    max_drop = 0.0
    review_rows: list[dict[str, Any]] = []
    for pid in shared_ids:
        old = old_products[pid]
        new = new_products[pid]
        old_verdict = str(old.get("verdict") or old.get("safety_verdict") or "")
        new_verdict = str(new.get("verdict") or new.get("safety_verdict") or "")
        old_taxonomy = taxonomy_primary(old)
        new_taxonomy = taxonomy_primary(new)
        material_blocked_coverage_only = old_verdict == new_verdict == "BLOCKED" and safety_text(old) == safety_text(new)
        shifted = False
        if old_taxonomy != new_taxonomy:
            taxonomy_shifts += 1
            shifted = True
        if old_verdict != new_verdict:
            verdict_shifts += 1
            shifted = True
        if safety_text(old) != safety_text(new):
            safety_shifts += 1
            shifted = True
        old_cov = mapped_coverage_value(old)
        new_cov = mapped_coverage_value(new)
        if old_cov is not None and new_cov is not None:
            drop = old_cov - new_cov
            if drop > args.max_mapped_coverage_drop and not material_blocked_coverage_only:
                coverage_drops += 1
                max_drop = max(max_drop, drop)
                shifted = True
        if shifted:
            review_rows.append({
                "product_id": pid,
                "product_name": new.get("product_name") or new.get("fullName") or old.get("product_name") or old.get("fullName"),
                "old_verdict": old_verdict,
                "new_verdict": new_verdict,
                "old_score": old.get("score_100_equivalent") or old.get("score_display_100_equivalent"),
                "new_score": new.get("score_100_equivalent") or new.get("score_display_100_equivalent"),
                "old_taxonomy": old_taxonomy,
                "new_taxonomy": new_taxonomy,
                "old_mapped_coverage": old_cov,
                "new_mapped_coverage": new_cov,
                "shift_reason": "pending_review",
                "approval_status": "pending",
                "reviewer_note": "",
            })

    review_output = getattr(args, "review_output", None)
    if review_output:
        try:
            git_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
        except Exception:
            git_commit = None
        output_path = repo_path(review_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(output_path, {
            "git_commit": git_commit,
            "command": getattr(args, "command_text", None),
            "old_dir": str(repo_path(args.old_dir)),
            "new_dir": str(repo_path(args.new_dir)),
            "old_dir_mtime": newest_mtime(old_files),
            "new_dir_mtime": newest_mtime(new_files),
            "shared_product_count": len(shared_ids),
            "taxonomy_shifts": taxonomy_shifts,
            "verdict_shifts": verdict_shifts,
            "safety_shifts": safety_shifts,
            "coverage_drops": coverage_drops,
            "rows": review_rows,
        })

    if getattr(args, "manual_approval", False):
        return []
    if taxonomy_shifts > args.max_taxonomy_shifts:
        findings.append(Finding("SHADOW_TAXONOMY_SHIFT", f"taxonomy shifts={taxonomy_shifts} exceeds threshold={args.max_taxonomy_shifts}"))
    if verdict_shifts > args.max_verdict_shifts:
        findings.append(Finding("SHADOW_VERDICT_SHIFT", f"score/verdict shifts={verdict_shifts} exceeds threshold={args.max_verdict_shifts}"))
    if safety_shifts > args.max_safety_shifts:
        findings.append(Finding("SHADOW_SAFETY_SHIFT", f"safety-hit shifts={safety_shifts} exceeds threshold={args.max_safety_shifts}"))
    if coverage_drops:
        findings.append(Finding("SHADOW_MAPPED_COVERAGE_DROP", f"mapped-coverage drops={coverage_drops}, max_drop={max_drop:.4f} exceeds threshold={args.max_mapped_coverage_drop}"))
    return findings


def stamp_manifest(args: argparse.Namespace) -> list[Finding]:
    dist_dir = repo_path(args.dist_dir)
    manifest_path = dist_dir / "export_manifest.json"
    interaction_manifest_path = dist_dir / "interaction_db_manifest.json"
    matrix_path = repo_path(args.matrix)
    manifest = load_json(manifest_path)
    db_path = dist_dir / "pharmaguide_core.db"
    if db_path.exists() and not manifest.get("checksum_sha256"):
        manifest["checksum_sha256"] = strip_sha256_prefix(manifest.get("checksum")) or sha256_file(db_path)
        if not manifest.get("checksum"):
            manifest["checksum"] = f"sha256:{manifest['checksum_sha256']}"
        write_json(manifest_path, manifest)

    findings = audit_export(args)
    if findings:
        return findings
    matrix = load_json(matrix_path) if matrix_path.exists() else {}
    interaction_manifest = load_json(interaction_manifest_path) if interaction_manifest_path.exists() else {}
    manifest["pipeline_contract_version"] = "cleaner_first_source_of_truth_v1"
    manifest["source_of_truth_matrix_version"] = (matrix.get("_metadata") or {}).get("schema_version")
    manifest["strict_gate_summary"] = {
        "strict_mode": bool(args.strict_release),
        "gates": [
            "source_of_truth_matrix",
            "cleaner_contract",
            "enrichment_contract",
            "scoring_contract",
            "export_contract",
            "clinical_drift",
            "interaction_db_parity",
            "artifact_freshness",
            "flutter_bundle_parity"
        ],
        "stamped_by": "scripts/audit_source_of_truth_contract.py stamp-manifest"
    }
    manifest["interaction_db_checksum"] = interaction_manifest.get("checksum_sha256")
    manifest["interaction_db_version"] = interaction_manifest.get("interaction_db_version")
    manifest["artifact_freshness_status"] = "checked_by_release_strict_gate"
    write_json(manifest_path, manifest)
    return []


def run_all(args: argparse.Namespace) -> list[Finding]:
    findings: list[Finding] = []
    for func in (audit_matrix, audit_cleaner, audit_enrichment, audit_scoring, audit_scoring_static, audit_clinical, audit_export, audit_interaction, audit_freshness):
        findings.extend(func(args))
    if getattr(args, "flutter_repo", None):
        findings.extend(audit_flutter(args))
    return findings


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--matrix", default=str(DEFAULT_MATRIX))
    parser.add_argument("--strict-release", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    matrix = subparsers.add_parser("matrix", help="validate source-of-truth matrix")
    add_common(matrix)
    matrix.set_defaults(func=audit_matrix)

    cleaner = subparsers.add_parser("cleaner", help="validate cleaner/IQD row contract")
    add_common(cleaner)
    cleaner.add_argument("--products-dir", default=None)
    cleaner.add_argument("--enriched-dir", action="append", default=[])
    cleaner.add_argument("--enriched-file", action="append", default=[])
    cleaner.add_argument("--product-file", action="append", default=[])
    cleaner.add_argument("--dist-dir", default=None)
    cleaner.set_defaults(func=audit_cleaner)

    clinical = subparsers.add_parser("clinical", help="validate clinical drift gates")
    add_common(clinical)
    clinical.add_argument("--products-dir", default=None)
    clinical.add_argument("--enriched-dir", action="append", default=[])
    clinical.add_argument("--enriched-file", action="append", default=[])
    clinical.add_argument("--product-file", action="append", default=[])
    clinical.add_argument("--dist-dir", default=None)
    clinical.set_defaults(func=audit_clinical)

    enrichment = subparsers.add_parser("enrichment", help="validate enrichment-owned IQD and identity contracts")
    add_common(enrichment)
    enrichment.add_argument("--products-dir", default=None)
    enrichment.add_argument("--enriched-dir", action="append", default=[])
    enrichment.add_argument("--enriched-file", action="append", default=[])
    enrichment.add_argument("--product-file", action="append", default=[])
    enrichment.add_argument("--dist-dir", default=None)
    enrichment.set_defaults(func=audit_enrichment)

    scoring = subparsers.add_parser("scoring", help="validate scored artifact scoring contract")
    add_common(scoring)
    scoring.add_argument("--products-dir", default=None)
    scoring.add_argument("--scored-dir", dest="enriched_dir", action="append", default=[])
    scoring.add_argument("--scored-file", dest="product_file", action="append", default=[])
    scoring.add_argument("--product-file", action="append", default=[])
    scoring.add_argument("--dist-dir", default=None)
    scoring.set_defaults(prefer_scored=True)
    scoring.set_defaults(func=audit_scoring)

    scoring_static = subparsers.add_parser("scoring-static", help="validate strict scoring modules do not read forbidden fallback fields")
    add_common(scoring_static)
    scoring_static.add_argument("--path", action="append", default=[])
    scoring_static.set_defaults(func=audit_scoring_static)

    export = subparsers.add_parser("export", help="validate final catalog export")
    add_common(export)
    export.add_argument("--dist-dir", default="scripts/dist")
    export.add_argument("--require-stamped-manifest", action="store_true")
    export.set_defaults(func=audit_export)

    interaction = subparsers.add_parser("interaction", help="validate interaction DB release parity")
    add_common(interaction)
    interaction.add_argument("--dist-dir", default="scripts/dist")
    interaction.add_argument("--source-rules", default="scripts/data/ingredient_interaction_rules.json")
    interaction.add_argument("--severity-vocab", default="scripts/data/severity_vocab.json")
    interaction.set_defaults(func=audit_interaction)

    freshness = subparsers.add_parser("freshness", help="validate artifact freshness")
    add_common(freshness)
    freshness.add_argument("--dist-dir", default="scripts/dist")
    freshness.add_argument("--final-db-dir", default="scripts/final_db_output")
    freshness.add_argument("--products-dir", default="scripts/products")
    freshness.add_argument("--interaction-input", action="append", default=[
        "scripts/data/curated_interactions/curated_interactions_v1.json",
        "scripts/data/curated_interactions/med_med_pairs_v1.json",
        "scripts/data/ingredient_interaction_rules.json",
        "scripts/data/drug_classes.json",
        "scripts/interaction_db_output/research_pairs.json",
    ])
    freshness.add_argument("--skip-interaction-inputs", action="store_true")
    freshness.set_defaults(func=audit_freshness)

    lineage = subparsers.add_parser("artifact-lineage", help="validate enriched/scored artifact lineage for shadow review")
    add_common(lineage)
    lineage.add_argument("--enriched-dir", required=True)
    lineage.add_argument("--scored-dir", required=True)
    lineage.set_defaults(func=audit_artifact_lineage)

    flutter = subparsers.add_parser("flutter", help="validate Flutter bundled DB parity")
    add_common(flutter)
    flutter.add_argument("--dist-dir", default="scripts/dist")
    flutter.add_argument("--flutter-repo", required=True)
    flutter.set_defaults(func=audit_flutter)

    shadow = subparsers.add_parser("shadow-diff", help="compare old vs new enrichment/scoring outputs before behavior changes")
    add_common(shadow)
    shadow.add_argument("--old-dir", required=True)
    shadow.add_argument("--new-dir", required=True)
    shadow.add_argument("--max-taxonomy-shifts", type=int, default=0)
    shadow.add_argument("--max-verdict-shifts", type=int, default=0)
    shadow.add_argument("--max-safety-shifts", type=int, default=0)
    shadow.add_argument("--max-mapped-coverage-drop", type=float, default=0.0)
    shadow.add_argument("--manual-approval", action="store_true")
    shadow.add_argument("--review-output", default=None)
    shadow.add_argument("--command-text", default=None)
    shadow.set_defaults(func=audit_shadow_diff)

    stamp = subparsers.add_parser("stamp-manifest", help="stamp export manifest with contract release metadata")
    add_common(stamp)
    stamp.add_argument("--dist-dir", default="scripts/dist")
    stamp.set_defaults(require_stamped_manifest=False)
    stamp.set_defaults(func=stamp_manifest)

    all_cmd = subparsers.add_parser("all", help="run all strict gates except Flutter unless --flutter-repo is supplied")
    add_common(all_cmd)
    all_cmd.add_argument("--products-dir", default="scripts/products")
    all_cmd.add_argument("--dist-dir", default="scripts/dist")
    all_cmd.add_argument("--final-db-dir", default="scripts/final_db_output")
    all_cmd.add_argument("--source-rules", default="scripts/data/ingredient_interaction_rules.json")
    all_cmd.add_argument("--severity-vocab", default="scripts/data/severity_vocab.json")
    all_cmd.add_argument("--flutter-repo", default=None)
    all_cmd.add_argument("--interaction-input", action="append", default=[
        "scripts/data/curated_interactions/curated_interactions_v1.json",
        "scripts/data/curated_interactions/med_med_pairs_v1.json",
        "scripts/data/ingredient_interaction_rules.json",
        "scripts/data/drug_classes.json",
        "scripts/interaction_db_output/research_pairs.json",
    ])
    all_cmd.add_argument("--require-stamped-manifest", action="store_true")
    all_cmd.set_defaults(func=run_all)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    findings = args.func(args)
    if findings:
        for finding in findings:
            print(finding.render(), file=sys.stderr)
        print(f"FAIL: {len(findings)} source-of-truth finding(s)", file=sys.stderr)
        return 1
    print(f"OK: {args.command} source-of-truth audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
