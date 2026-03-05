#!/usr/bin/env python3
"""
Database-to-script integrity sanity check.

Purpose:
- Catch silent failures between scripts and JSON databases.
- Validate key presence, type expectations, enum compatibility, and null/empty edge cases.

Usage:
  python3 scripts/db_integrity_sanity_check.py
  python3 scripts/db_integrity_sanity_check.py --json
  python3 scripts/db_integrity_sanity_check.py --strict
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"


@dataclass
class Finding:
    severity: str  # error|warning|info
    file: str
    path: str
    issue: str
    expected: str
    actual: str


def _load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:  # pragma: no cover
        return {"__load_error__": str(exc)}


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    return type(value).__name__


def _iter_entries(data: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    raw = data.get(key, [])
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    return []


def _check_required(
    findings: List[Finding],
    file: str,
    entry: Dict[str, Any],
    idx: int,
    required: Sequence[Tuple[str, type]],
) -> None:
    for key, expected_type in required:
        if key not in entry:
            findings.append(
                Finding(
                    "error",
                    file,
                    f"[{idx}].{key}",
                    "missing_required_key",
                    expected_type.__name__,
                    "missing",
                )
            )
            continue
        value = entry.get(key)
        if value is None:
            findings.append(
                Finding(
                    "error",
                    file,
                    f"[{idx}].{key}",
                    "null_required_key",
                    expected_type.__name__,
                    "null",
                )
            )
            continue
        if not isinstance(value, expected_type):
            findings.append(
                Finding(
                    "error",
                    file,
                    f"[{idx}].{key}",
                    "type_mismatch",
                    expected_type.__name__,
                    _type_name(value),
                )
            )


def _check_enum(
    findings: List[Finding],
    file: str,
    entry: Dict[str, Any],
    idx: int,
    key: str,
    allowed: Iterable[str],
    severity: str = "error",
) -> None:
    value = entry.get(key)
    if value is None:
        return
    if not isinstance(value, str):
        findings.append(
            Finding(severity, file, f"[{idx}].{key}", "enum_type_mismatch", "str", _type_name(value))
        )
        return
    if value not in set(allowed):
        findings.append(
            Finding(
                severity,
                file,
                f"[{idx}].{key}",
                "enum_value_not_supported",
                "|".join(sorted(set(allowed))),
                value,
            )
        )


def _check_list_of_strings(
    findings: List[Finding],
    file: str,
    entry: Dict[str, Any],
    idx: int,
    key: str,
    required: bool = False,
    allow_empty: bool = True,
) -> None:
    if key not in entry:
        if required:
            findings.append(Finding("error", file, f"[{idx}].{key}", "missing_required_key", "list[str]", "missing"))
        return
    value = entry.get(key)
    if value is None:
        findings.append(Finding("error", file, f"[{idx}].{key}", "null_list", "list[str]", "null"))
        return
    if not isinstance(value, list):
        findings.append(Finding("error", file, f"[{idx}].{key}", "type_mismatch", "list[str]", _type_name(value)))
        return
    if not allow_empty and not value:
        findings.append(Finding("warning", file, f"[{idx}].{key}", "empty_list", "non-empty list[str]", "[]"))
        return
    for j, item in enumerate(value):
        if not isinstance(item, str):
            findings.append(
                Finding("error", file, f"[{idx}].{key}[{j}]", "type_mismatch", "str", _type_name(item))
            )


def _check_camel_case_drift(
    findings: List[Finding],
    file: str,
    entries: List[Dict[str, Any]],
    drift_map: Dict[str, str],
) -> None:
    for i, entry in enumerate(entries):
        for camel, snake in drift_map.items():
            if camel in entry and snake not in entry:
                findings.append(
                    Finding(
                        "warning",
                        file,
                        f"[{i}].{camel}",
                        "key_drift_camel_without_snake",
                        snake,
                        camel,
                    )
                )


def check_absorption_enhancers(findings: List[Finding], data: Dict[str, Any], file: str) -> None:
    entries = _iter_entries(data, "absorption_enhancers")
    if not isinstance(data.get("absorption_enhancers"), list):
        findings.append(Finding("error", file, "absorption_enhancers", "missing_or_non_list", "list", _type_name(data.get("absorption_enhancers"))))
        return
    for i, e in enumerate(entries):
        _check_required(findings, file, e, i, [("id", str), ("standard_name", str)])
        _check_list_of_strings(findings, file, e, i, "aliases", required=True)
        _check_list_of_strings(findings, file, e, i, "enhances", required=True)


def check_synergy_cluster(findings: List[Finding], data: Dict[str, Any], file: str) -> None:
    raw = data.get("synergy_clusters")
    allowed_source_types = {"pubmed", "nih_ods", "fda", "nccih"}
    if not isinstance(raw, list):
        findings.append(Finding("error", file, "synergy_clusters", "missing_or_non_list", "list", _type_name(raw)))
        return
    for i, e in enumerate(raw):
        if not isinstance(e, dict):
            findings.append(Finding("error", file, f"[{i}]", "entry_not_object", "dict", _type_name(e)))
            continue
        _check_required(findings, file, e, i, [("id", str), ("standard_name", str)])
        ingredients = e.get("ingredients")
        _check_list_of_strings(findings, file, e, i, "ingredients", required=True, allow_empty=False)
        normalized_ingredients = set()
        if isinstance(ingredients, list):
            for ing in ingredients:
                if isinstance(ing, str):
                    normalized = " ".join(ing.strip().lower().split())
                    if normalized:
                        normalized_ingredients.add(normalized)

        evidence_tier = e.get("evidence_tier")
        if evidence_tier is None:
            findings.append(
                Finding(
                    "error",
                    file,
                    f"[{i}].evidence_tier",
                    "missing_required_key",
                    "int(1|2|3)",
                    "missing",
                )
            )
        elif not isinstance(evidence_tier, int):
            findings.append(
                Finding(
                    "error",
                    file,
                    f"[{i}].evidence_tier",
                    "type_mismatch",
                    "int(1|2|3)",
                    _type_name(evidence_tier),
                )
            )
        elif evidence_tier not in {1, 2, 3}:
            findings.append(
                Finding(
                    "error",
                    file,
                    f"[{i}].evidence_tier",
                    "invalid_enum",
                    "1|2|3",
                    str(evidence_tier),
                )
            )

        mechanism = e.get("synergy_mechanism")
        if mechanism is not None and not isinstance(mechanism, str):
            findings.append(
                Finding(
                    "error",
                    file,
                    f"[{i}].synergy_mechanism",
                    "type_mismatch",
                    "str|null",
                    _type_name(mechanism),
                )
            )

        note = e.get("note")
        if note is None:
            findings.append(
                Finding(
                    "error",
                    file,
                    f"[{i}].note",
                    "missing_required_key",
                    "str",
                    "missing",
                )
            )
        elif not isinstance(note, str):
            findings.append(
                Finding(
                    "error",
                    file,
                    f"[{i}].note",
                    "type_mismatch",
                    "str",
                    _type_name(note),
                )
            )
        elif not note.strip():
            findings.append(
                Finding(
                    "error",
                    file,
                    f"[{i}].note",
                    "empty_string",
                    "non-empty str",
                    "empty",
                )
            )

        sources = e.get("sources")
        if sources is None:
            findings.append(
                Finding(
                    "error",
                    file,
                    f"[{i}].sources",
                    "missing_required_key",
                    "list[object]",
                    "missing",
                )
            )
        elif not isinstance(sources, list):
            findings.append(
                Finding(
                    "error",
                    file,
                    f"[{i}].sources",
                    "type_mismatch",
                    "list[object]",
                    _type_name(sources),
                )
            )
        else:
            if len(sources) == 0:
                findings.append(
                    Finding(
                        "error",
                        file,
                        f"[{i}].sources",
                        "empty_list",
                        "at least 1 source object",
                        "0",
                    )
                )
            for j, source in enumerate(sources):
                if not isinstance(source, dict):
                    findings.append(
                        Finding(
                            "error",
                            file,
                            f"[{i}].sources[{j}]",
                            "entry_not_object",
                            "dict",
                            _type_name(source),
                        )
                    )
                    continue
                source_type = source.get("source_type")
                label = source.get("label")
                url = source.get("url")
                if not isinstance(source_type, str) or not source_type.strip():
                    findings.append(
                        Finding(
                            "error",
                            file,
                            f"[{i}].sources[{j}].source_type",
                            "missing_or_empty",
                            "non-empty str",
                            _type_name(source_type),
                        )
                    )
                elif source_type not in allowed_source_types:
                    findings.append(
                        Finding(
                            "error",
                            file,
                            f"[{i}].sources[{j}].source_type",
                            "invalid_enum",
                            "|".join(sorted(allowed_source_types)),
                            str(source_type),
                        )
                    )
                if not isinstance(label, str) or not label.strip():
                    findings.append(
                        Finding(
                            "error",
                            file,
                            f"[{i}].sources[{j}].label",
                            "missing_or_empty",
                            "non-empty str",
                            _type_name(label),
                        )
                    )
                if not isinstance(url, str) or not url.strip():
                    findings.append(
                        Finding(
                            "error",
                            file,
                            f"[{i}].sources[{j}].url",
                            "missing_or_empty",
                            "non-empty str",
                            _type_name(url),
                        )
                    )
                elif not (url.startswith("http://") or url.startswith("https://")):
                    findings.append(
                        Finding(
                            "error",
                            file,
                            f"[{i}].sources[{j}].url",
                            "invalid_url_scheme",
                            "http:// or https://",
                            url,
                        )
                    )
                elif "pubmed.ncbi.nlm.nih.gov/?term=" in url:
                    findings.append(
                        Finding(
                            "error",
                            file,
                            f"[{i}].sources[{j}].url",
                            "query_placeholder_not_allowed",
                            "specific source URL (not search query)",
                            url,
                        )
                    )

        med = e.get("min_effective_doses")
        if med is None:
            findings.append(Finding("error", file, f"[{i}].min_effective_doses", "null_map", "dict", "null"))
        elif not isinstance(med, dict):
            findings.append(Finding("error", file, f"[{i}].min_effective_doses", "type_mismatch", "dict", _type_name(med)))
        else:
            for k, v in med.items():
                if not isinstance(k, str):
                    findings.append(Finding("error", file, f"[{i}].min_effective_doses", "non_string_key", "str", _type_name(k)))
                    continue
                normalized_key = " ".join(k.strip().lower().split())
                if normalized_ingredients and normalized_key not in normalized_ingredients:
                    findings.append(
                        Finding(
                            "error",
                            file,
                            f"[{i}].min_effective_doses.{k}",
                            "key_not_in_ingredients",
                            "must reference listed cluster ingredient",
                            k,
                        )
                    )
                if not isinstance(v, (int, float)):
                    findings.append(Finding("error", file, f"[{i}].min_effective_doses.{k}", "type_mismatch", "number", _type_name(v)))
                elif not math.isfinite(float(v)) or float(v) <= 0:
                    findings.append(
                        Finding(
                            "error",
                            file,
                            f"[{i}].min_effective_doses.{k}",
                            "invalid_dose_value",
                            "finite number > 0",
                            str(v),
                        )
                    )


def check_standardized_botanicals(findings: List[Finding], data: Dict[str, Any], file: str) -> None:
    raw = data.get("standardized_botanicals")
    if not isinstance(raw, list):
        findings.append(Finding("error", file, "standardized_botanicals", "missing_or_non_list", "list", _type_name(raw)))
        return
    for i, e in enumerate(raw):
        if not isinstance(e, dict):
            findings.append(Finding("error", file, f"[{i}]", "entry_not_object", "dict", _type_name(e)))
            continue
        _check_required(findings, file, e, i, [("id", str), ("standard_name", str)])
        _check_list_of_strings(findings, file, e, i, "aliases", required=True)
        _check_list_of_strings(findings, file, e, i, "markers", required=True)


def check_cert_claim_rules(findings: List[Finding], data: Dict[str, Any], file: str) -> None:
    rules = data.get("rules")
    if not isinstance(rules, dict):
        findings.append(Finding("error", file, "rules", "missing_or_non_object", "dict", _type_name(rules)))
        return

    if "third_party_programs" not in rules:
        findings.append(
            Finding(
                "warning",
                file,
                "rules.third_party_programs",
                "missing_category",
                "present",
                "missing",
            )
        )

    for category, cat_rules in rules.items():
        if str(category).startswith("_"):
            continue
        if not isinstance(cat_rules, dict):
            findings.append(Finding("error", file, f"rules.{category}", "non_object_category", "dict", _type_name(cat_rules)))
            continue
        for rid, rule in cat_rules.items():
            if str(rid).startswith("_"):
                continue
            if not isinstance(rule, dict):
                findings.append(Finding("error", file, f"rules.{category}.{rid}", "rule_not_object", "dict", _type_name(rule)))
                continue
            for key in ("positive_patterns", "negative_patterns"):
                val = rule.get(key)
                if val is None:
                    findings.append(Finding("error", file, f"rules.{category}.{rid}.{key}", "null_patterns", "list[str]", "null"))
                elif not isinstance(val, list):
                    findings.append(Finding("error", file, f"rules.{category}.{rid}.{key}", "type_mismatch", "list[str]", _type_name(val)))


def check_clinical_db(findings: List[Finding], data: Dict[str, Any], file: str) -> None:
    raw = data.get("backed_clinical_studies")
    if not isinstance(raw, list):
        findings.append(Finding("error", file, "backed_clinical_studies", "missing_or_non_list", "list", _type_name(raw)))
        return

    valid_study_types = {
        "systematic_review_meta",
        "rct_multiple",
        "rct_single",
        "clinical_strain",
        "observational",
        "animal_study",
        "in_vitro",
    }
    valid_evidence_levels = {
        "product-human",
        "product-rct",
        "product",
        "branded-rct",
        "ingredient-human",
        "strain-clinical",
        "preclinical",
        "unknown",
    }

    for i, e in enumerate(raw):
        if not isinstance(e, dict):
            findings.append(Finding("error", file, f"[{i}]", "entry_not_object", "dict", _type_name(e)))
            continue
        _check_required(findings, file, e, i, [("id", str), ("standard_name", str), ("study_type", str), ("evidence_level", str)])
        _check_list_of_strings(findings, file, e, i, "aliases", required=False)
        _check_list_of_strings(findings, file, e, i, "aliases_normalized", required=False)
        _check_list_of_strings(findings, file, e, i, "exclude_aliases", required=False)
        _check_enum(findings, file, e, i, "study_type", valid_study_types)
        _check_enum(findings, file, e, i, "evidence_level", valid_evidence_levels)
        _check_enum(findings, file, e, i, "score_contribution", {"tier_1", "tier_2", "tier_3"})
        _check_list_of_strings(findings, file, e, i, "health_goals_supported", required=True, allow_empty=False)
        _check_list_of_strings(findings, file, e, i, "key_endpoints", required=True, allow_empty=False)


def check_iqm(findings: List[Finding], data: Dict[str, Any], file: str) -> None:
    if not isinstance(data, dict):
        findings.append(Finding("error", file, "$", "non_object_root", "dict", _type_name(data)))
        return

    valid_match_modes = {"exact", "normalized", "alias_and_fuzzy"}
    valid_priorities = {0, 1, 2}
    valid_abs_quality = {"unknown", "poor", "low", "moderate", "good", "very_good", "excellent", "variable"}
    valid_review_statuses = {"stub", "draft", "reviewed", "verified", "validated", "needs_review", "pending", "provisional"}

    ingredient_keys = [k for k in data.keys() if not str(k).startswith("_")]
    for ing_key in ingredient_keys:
        entry = data.get(ing_key)
        if not isinstance(entry, dict):
            findings.append(Finding("error", file, ing_key, "entry_not_object", "dict", _type_name(entry)))
            continue

        # standard_name required on every parent.
        sn = entry.get("standard_name")
        if sn is None or not isinstance(sn, str):
            findings.append(Finding("error", file, f"{ing_key}.standard_name", "missing_or_wrong_type", "str", _type_name(sn)))

        # category_enum: must be one of the 12 canonical categories.
        VALID_CATEGORIES = {
            "amino_acids", "antioxidants", "enzymes", "fatty_acids",
            "fibers", "functional_foods", "herbs", "minerals",
            "other", "probiotics", "proteins", "vitamins",
        }
        ce = entry.get("category_enum")
        if ce is None or not isinstance(ce, str):
            findings.append(Finding("error", file, f"{ing_key}.category_enum", "missing_or_wrong_type", "str", _type_name(ce)))
        elif ce not in VALID_CATEGORIES:
            findings.append(Finding("error", file, f"{ing_key}.category_enum", "invalid_category", f"one of {sorted(VALID_CATEGORIES)}", ce))

        # data_quality block.
        dq = entry.get("data_quality")
        if not isinstance(dq, dict):
            findings.append(Finding("warning", file, f"{ing_key}.data_quality", "missing_or_non_object", "dict", _type_name(dq)))
        else:
            rs = dq.get("review_status")
            if rs is not None and rs not in valid_review_statuses:
                findings.append(Finding("warning", file, f"{ing_key}.data_quality.review_status", "enum_value_not_supported", "|".join(sorted(valid_review_statuses)), str(rs)))
            comp = dq.get("completeness")
            if comp is not None and not isinstance(comp, (int, float)):
                findings.append(Finding("warning", file, f"{ing_key}.data_quality.completeness", "type_mismatch", "number", _type_name(comp)))

        mr = entry.get("match_rules")
        if not isinstance(mr, dict):
            findings.append(Finding("error", file, f"{ing_key}.match_rules", "missing_or_non_object", "dict", _type_name(mr)))
        else:
            mode = mr.get("match_mode")
            if mode not in valid_match_modes:
                findings.append(Finding("error", file, f"{ing_key}.match_rules.match_mode", "enum_value_not_supported", "exact|normalized|alias_and_fuzzy", str(mode)))
            pr = mr.get("priority")
            if pr not in valid_priorities:
                findings.append(Finding("error", file, f"{ing_key}.match_rules.priority", "enum_value_not_supported", "0|1|2", str(pr)))

        forms = entry.get("forms")
        # Routing stubs with parent_id are allowed to have empty forms
        has_parent_id = entry.get("match_rules", {}).get("parent_id") is not None
        if not isinstance(forms, dict) or (not forms and not has_parent_id):
            findings.append(Finding("error", file, f"{ing_key}.forms", "missing_or_empty_forms", "non-empty dict", _type_name(forms)))
            continue

        for form_name, form in forms.items():
            if not isinstance(form, dict):
                findings.append(Finding("error", file, f"{ing_key}.forms.{form_name}", "form_not_object", "dict", _type_name(form)))
                continue
            aliases = form.get("aliases")
            if not isinstance(aliases, list) or not aliases:
                findings.append(Finding("error", file, f"{ing_key}.forms.{form_name}.aliases", "missing_or_empty_aliases", "non-empty list[str]", _type_name(aliases)))
            ab = form.get("absorption_structured")
            if not isinstance(ab, dict):
                findings.append(Finding("error", file, f"{ing_key}.forms.{form_name}.absorption_structured", "missing_or_non_object", "dict", _type_name(ab)))
            else:
                q = ab.get("quality")
                if q not in valid_abs_quality:
                    findings.append(Finding("error", file, f"{ing_key}.forms.{form_name}.absorption_structured.quality", "enum_value_not_supported", "|".join(sorted(valid_abs_quality)), str(q)))

            # bio_score must be a number (used directly by scorer).
            bs = form.get("bio_score")
            if bs is None:
                findings.append(Finding("error", file, f"{ing_key}.forms.{form_name}.bio_score", "missing_required_key", "number", "missing"))
            elif not isinstance(bs, (int, float)):
                findings.append(Finding("error", file, f"{ing_key}.forms.{form_name}.bio_score", "type_mismatch", "number", _type_name(bs)))

            # natural must be a boolean.
            nat = form.get("natural")
            if nat is None:
                findings.append(Finding("error", file, f"{ing_key}.forms.{form_name}.natural", "missing_required_key", "bool", "missing"))
            elif not isinstance(nat, bool):
                findings.append(Finding("error", file, f"{ing_key}.forms.{form_name}.natural", "type_mismatch", "bool", _type_name(nat)))

            # score must be a number.
            sc = form.get("score")
            if sc is None:
                findings.append(Finding("error", file, f"{ing_key}.forms.{form_name}.score", "missing_required_key", "number", "missing"))
            elif not isinstance(sc, (int, float)):
                findings.append(Finding("error", file, f"{ing_key}.forms.{form_name}.score", "type_mismatch", "number", _type_name(sc)))

            # score = bio_score + 3 when natural=True, else bio_score.
            if isinstance(bs, (int, float)) and isinstance(sc, (int, float)) and isinstance(nat, bool):
                expected_score = bs + 3 if nat else bs
                if abs(sc - expected_score) > 0.01:
                    findings.append(Finding(
                        "error", file,
                        f"{ing_key}.forms.{form_name}.score",
                        "score_formula_mismatch",
                        f"bio_score({bs})+{'3' if nat else '0'}={expected_score}",
                        str(sc),
                    ))

            # absorption: optional string.
            abs_val = form.get("absorption")
            if abs_val is not None and not isinstance(abs_val, str):
                findings.append(Finding("warning", file, f"{ing_key}.forms.{form_name}.absorption", "type_mismatch", "str|null", _type_name(abs_val)))

            # notes: optional string.
            notes_val = form.get("notes")
            if notes_val is not None and not isinstance(notes_val, str):
                findings.append(Finding("warning", file, f"{ing_key}.forms.{form_name}.notes", "type_mismatch", "str|null", _type_name(notes_val)))

            # dosage_importance: script coerces, but type drift is a silent fallback risk.
            di = form.get("dosage_importance")
            if di is not None and not isinstance(di, (int, float, str)):
                findings.append(Finding("warning", file, f"{ing_key}.forms.{form_name}.dosage_importance", "type_fallback_risk", "number|string", _type_name(di)))


def check_allergens(findings: List[Finding], data: Dict[str, Any], file: str) -> None:
    raw = data.get("allergens")
    if not isinstance(raw, list):
        findings.append(Finding("error", file, "allergens", "missing_or_non_list", "list", _type_name(raw)))
        return
    for i, e in enumerate(raw):
        if not isinstance(e, dict):
            findings.append(Finding("error", file, f"[{i}]", "entry_not_object", "dict", _type_name(e)))
            continue
        _check_required(findings, file, e, i, [("id", str), ("standard_name", str), ("severity_level", str)])
        _check_list_of_strings(findings, file, e, i, "aliases", required=True)
        _check_enum(findings, file, e, i, "severity_level", {"high", "moderate", "low"})


def check_harmful_additives(findings: List[Finding], data: Dict[str, Any], file: str) -> None:
    raw = data.get("harmful_additives")
    if not isinstance(raw, list):
        findings.append(Finding("error", file, "harmful_additives", "missing_or_non_list", "list", _type_name(raw)))
        return
    for i, e in enumerate(raw):
        if not isinstance(e, dict):
            findings.append(Finding("error", file, f"[{i}]", "entry_not_object", "dict", _type_name(e)))
            continue
        _check_required(findings, file, e, i, [("id", str), ("standard_name", str), ("severity_level", str)])
        _check_list_of_strings(findings, file, e, i, "aliases", required=True)
        _check_enum(findings, file, e, i, "severity_level", {"critical", "high", "moderate", "low", "none"})


def check_banned(findings: List[Finding], data: Dict[str, Any], file: str) -> None:
    raw = data.get("ingredients")
    if not isinstance(raw, list):
        findings.append(Finding("error", file, "ingredients", "missing_or_non_list", "list", _type_name(raw)))
        return

    legal_values = {
        "banned_federal",
        "banned_state",
        "not_lawful_as_supplement",
        "controlled_substance",
        "restricted",
        "under_review",
        "lawful",
        "adulterant",
        "contaminant_risk",
        "wada_prohibited",
        "high_risk",
    }

    for i, e in enumerate(raw):
        if not isinstance(e, dict):
            findings.append(Finding("error", file, f"[{i}]", "entry_not_object", "dict", _type_name(e)))
            continue
        _check_required(findings, file, e, i, [("id", str), ("standard_name", str), ("status", str), ("match_mode", str)])
        _check_list_of_strings(findings, file, e, i, "aliases", required=True)
        _check_enum(findings, file, e, i, "status", {"banned", "recalled", "high_risk", "watchlist"})
        _check_enum(findings, file, e, i, "match_mode", {"active", "disabled", "historical"})
        _check_enum(findings, file, e, i, "legal_status_enum", legal_values)


def check_other_ingredients(findings: List[Finding], data: Dict[str, Any], file: str) -> None:
    raw = data.get("other_ingredients")
    if not isinstance(raw, list):
        findings.append(Finding("error", file, "other_ingredients", "missing_or_non_list", "list", _type_name(raw)))
        return
    for i, e in enumerate(raw):
        if not isinstance(e, dict):
            findings.append(Finding("error", file, f"[{i}]", "entry_not_object", "dict", _type_name(e)))
            continue
        # enhanced_normalizer uses direct indexing e["standard_name"]
        _check_required(findings, file, e, i, [("id", str), ("standard_name", str)])
        _check_list_of_strings(findings, file, e, i, "aliases", required=True)


def check_top_manufacturers(findings: List[Finding], data: Dict[str, Any], file: str) -> None:
    raw = data.get("top_manufacturers")
    if not isinstance(raw, list):
        findings.append(Finding("error", file, "top_manufacturers", "missing_or_non_list", "list", _type_name(raw)))
        return
    seen_ids: set = set()
    for i, e in enumerate(raw):
        if not isinstance(e, dict):
            findings.append(Finding("error", file, f"[{i}]", "entry_not_object", "dict", _type_name(e)))
            continue
        _check_required(findings, file, e, i, [("id", str), ("standard_name", str)])
        _check_list_of_strings(findings, file, e, i, "aliases", required=False)
        # Duplicate ID check.
        mid = e.get("id")
        if mid and mid in seen_ids:
            findings.append(Finding("error", file, f"[{i}].id", "duplicate_id", "unique", mid))
        if mid:
            seen_ids.add(mid)
        # evidence should be a list if present.
        ev = e.get("evidence")
        if ev is not None and not isinstance(ev, list):
            findings.append(Finding("warning", file, f"[{i}].evidence", "type_mismatch", "list|null", _type_name(ev)))


def check_rda_optimal_uls(findings: List[Finding], data: Dict[str, Any], file: str) -> None:
    raw = data.get("nutrient_recommendations")
    if not isinstance(raw, list):
        findings.append(Finding("error", file, "nutrient_recommendations", "missing_or_non_list", "list", _type_name(raw)))
        return
    for i, e in enumerate(raw):
        if not isinstance(e, dict):
            findings.append(Finding("error", file, f"[{i}]", "entry_not_object", "dict", _type_name(e)))
            continue
        _check_required(findings, file, e, i, [("standard_name", str)])
        if "warnings" in e and e.get("warnings") is not None and not isinstance(e.get("warnings"), list):
            findings.append(Finding("warning", file, f"[{i}].warnings", "type_fallback_risk", "list", _type_name(e.get("warnings"))))


def check_rda_therapeutic(findings: List[Finding], data: Dict[str, Any], file: str) -> None:
    raw = data.get("therapeutic_dosing")
    if not isinstance(raw, list):
        findings.append(Finding("error", file, "therapeutic_dosing", "missing_or_non_list", "list", _type_name(raw)))
        return
    for i, e in enumerate(raw):
        if not isinstance(e, dict):
            findings.append(Finding("error", file, f"[{i}]", "entry_not_object", "dict", _type_name(e)))
            continue
        _check_required(findings, file, e, i, [("standard_name", str)])


def check_unit_conversions(findings: List[Finding], data: Dict[str, Any], file: str) -> None:
    vitamin = data.get("vitamin_conversions")
    if not isinstance(vitamin, dict):
        findings.append(Finding("error", file, "vitamin_conversions", "type_mismatch", "dict", _type_name(vitamin)))

    mass = data.get("mass_conversions")
    if not isinstance(mass, dict):
        findings.append(Finding("error", file, "mass_conversions", "type_mismatch", "dict", _type_name(mass)))
    else:
        rules = mass.get("rules")
        if not isinstance(rules, dict):
            findings.append(Finding("error", file, "mass_conversions.rules", "type_mismatch", "dict", _type_name(rules)))

    probiotic = data.get("probiotic_conversions")
    if not isinstance(probiotic, dict):
        findings.append(Finding("error", file, "probiotic_conversions", "type_mismatch", "dict", _type_name(probiotic)))

    form_patterns = data.get("form_detection_patterns")
    if not isinstance(form_patterns, dict):
        findings.append(Finding("error", file, "form_detection_patterns", "type_mismatch", "dict", _type_name(form_patterns)))


def check_botanical_ingredients(findings: List[Finding], data: Dict[str, Any], file: str) -> None:
    raw = data.get("botanical_ingredients")
    if not isinstance(raw, list):
        findings.append(Finding("error", file, "botanical_ingredients", "missing_or_non_list", "list", _type_name(raw)))
        return
    for i, e in enumerate(raw):
        if not isinstance(e, dict):
            findings.append(Finding("error", file, f"[{i}]", "entry_not_object", "dict", _type_name(e)))
            continue
        _check_required(findings, file, e, i, [("id", str), ("standard_name", str), ("category", str)])
        _check_list_of_strings(findings, file, e, i, "aliases", required=True)


def check_clinically_relevant_strains(findings: List[Finding], data: Dict[str, Any], file: str) -> None:
    raw = data.get("clinically_relevant_strains")
    if not isinstance(raw, list):
        findings.append(Finding("error", file, "clinically_relevant_strains", "missing_or_non_list", "list", _type_name(raw)))
        return
    for i, e in enumerate(raw):
        if not isinstance(e, dict):
            findings.append(Finding("error", file, f"[{i}]", "entry_not_object", "dict", _type_name(e)))
            continue
        _check_required(findings, file, e, i, [("id", str), ("standard_name", str)])
        _check_list_of_strings(findings, file, e, i, "aliases", required=False)
        _check_enum(findings, file, e, i, "evidence_level", {"high", "moderate", "low"}, severity="warning")


def check_proprietary_blends(findings: List[Finding], data: Dict[str, Any], file: str) -> None:
    raw = data.get("proprietary_blend_concerns")
    if not isinstance(raw, list):
        findings.append(Finding("error", file, "proprietary_blend_concerns", "missing_or_non_list", "list", _type_name(raw)))
        return
    for i, e in enumerate(raw):
        if not isinstance(e, dict):
            findings.append(Finding("error", file, f"[{i}]", "entry_not_object", "dict", _type_name(e)))
            continue
        _check_required(findings, file, e, i, [("id", str), ("standard_name", str)])
        terms = e.get("blend_terms")
        if terms is not None and not isinstance(terms, list):
            findings.append(Finding("warning", file, f"[{i}].blend_terms", "type_fallback_risk", "list|null", _type_name(terms)))
        risks = e.get("risk_factors")
        if risks is not None and not isinstance(risks, list):
            findings.append(Finding("warning", file, f"[{i}].risk_factors", "type_fallback_risk", "list|null", _type_name(risks)))


def check_manufacturer_violations(findings: List[Finding], data: Dict[str, Any], file: str) -> None:
    raw = data.get("manufacturer_violations")
    if not isinstance(raw, list):
        findings.append(Finding("error", file, "manufacturer_violations", "missing_or_non_list", "list", _type_name(raw)))
        return
    for i, e in enumerate(raw):
        if not isinstance(e, dict):
            findings.append(Finding("error", file, f"[{i}]", "entry_not_object", "dict", _type_name(e)))
            continue
        _check_required(findings, file, e, i, [("id", str), ("manufacturer", str), ("severity_level", str)])
        _check_enum(findings, file, e, i, "severity_level", {"critical", "high", "moderate", "low"}, severity="warning")
        tda = e.get("total_deduction_applied")
        if tda is not None and not isinstance(tda, (int, float)):
            findings.append(Finding("warning", file, f"[{i}].total_deduction_applied", "type_fallback_risk", "number", _type_name(tda)))


def check_ingredient_classification(findings: List[Finding], data: Dict[str, Any], file: str) -> None:
    skip_exact = data.get("skip_exact")
    if not isinstance(skip_exact, list):
        findings.append(Finding("error", file, "skip_exact", "missing_or_non_list", "list[str]", _type_name(skip_exact)))
    classifications = data.get("classifications")
    if not isinstance(classifications, dict):
        findings.append(Finding("error", file, "classifications", "missing_or_non_object", "dict", _type_name(classifications)))


def check_enhanced_delivery(findings: List[Finding], data: Dict[str, Any], file: str) -> None:
    non_meta = {k: v for k, v in data.items() if not str(k).startswith("_")}
    if not non_meta:
        findings.append(Finding("warning", file, "$", "no_delivery_entries", ">=1 entries", "0"))
        return
    for key, value in non_meta.items():
        if not isinstance(value, dict):
            findings.append(Finding("warning", file, key, "delivery_entry_not_object", "dict", _type_name(value)))
            continue
        tier = value.get("tier")
        if tier is not None and not isinstance(tier, (int, float)):
            findings.append(Finding("warning", file, f"{key}.tier", "type_fallback_risk", "number", _type_name(tier)))


def check_color_indicators(findings: List[Finding], data: Dict[str, Any], file: str) -> None:
    for key in ("natural_indicators", "artificial_indicators", "explicit_natural_dyes", "explicit_artificial_dyes"):
        value = data.get(key)
        if not isinstance(value, list):
            findings.append(Finding("error", file, key, "missing_or_non_list", "list[str]", _type_name(value)))


def check_id_redirects(findings: List[Finding], data: Dict[str, Any], file: str) -> None:
    raw = data.get("redirects")
    if not isinstance(raw, list):
        findings.append(Finding("error", file, "redirects", "missing_or_non_list", "list", _type_name(raw)))
        return
    for i, e in enumerate(raw):
        if not isinstance(e, dict):
            findings.append(Finding("error", file, f"[{i}]", "entry_not_object", "dict", _type_name(e)))
            continue
        _check_required(findings, file, e, i, [("deprecated_id", str), ("canonical_id", str)])


def check_banned_match_allowlist(findings: List[Finding], data: Dict[str, Any], file: str) -> None:
    for key in ("allowlist", "denylist"):
        raw = data.get(key)
        if not isinstance(raw, list):
            findings.append(Finding("error", file, key, "missing_or_non_list", "list", _type_name(raw)))
            continue
        for i, e in enumerate(raw):
            if not isinstance(e, dict):
                findings.append(Finding("error", file, f"{key}[{i}]", "entry_not_object", "dict", _type_name(e)))
                continue
            _check_required(findings, file, e, i, [("id", str), ("canonical_term", str)])


def check_functional_ingredient_groupings(findings: List[Finding], data: Dict[str, Any], file: str) -> None:
    fg = data.get("functional_groupings")
    if not isinstance(fg, list):
        findings.append(Finding("error", file, "functional_groupings", "missing_or_non_list", "list", _type_name(fg)))
    else:
        for i, e in enumerate(fg):
            if not isinstance(e, dict):
                findings.append(Finding("error", file, f"functional_groupings[{i}]", "entry_not_object", "dict", _type_name(e)))
                continue
            _check_required(findings, file, e, i, [("id", str), ("type", str)])

    vt = data.get("vague_terms_to_flag")
    if not isinstance(vt, list):
        findings.append(Finding("error", file, "vague_terms_to_flag", "missing_or_non_list", "list", _type_name(vt)))
    else:
        for i, e in enumerate(vt):
            if not isinstance(e, dict):
                findings.append(Finding("error", file, f"vague_terms_to_flag[{i}]", "entry_not_object", "dict", _type_name(e)))
                continue
            term = e.get("term")
            if not isinstance(term, str):
                findings.append(Finding("error", file, f"vague_terms_to_flag[{i}].term", "missing_or_wrong_type", "str", _type_name(term)))


def check_ingredient_weights(findings: List[Finding], data: Dict[str, Any], file: str) -> None:
    for key in ("category_weights", "dosage_weights", "ingredient_priorities"):
        val = data.get(key)
        if not isinstance(val, dict):
            findings.append(Finding("error", file, key, "missing_or_non_object", "dict", _type_name(val)))


def check_manufacture_deduction_expl(findings: List[Finding], data: Dict[str, Any], file: str) -> None:
    cap = data.get("total_deduction_cap")
    if not isinstance(cap, (int, float)):
        findings.append(Finding("error", file, "total_deduction_cap", "missing_or_wrong_type", "number", _type_name(cap)))
    vc = data.get("violation_categories")
    if not isinstance(vc, dict):
        findings.append(Finding("error", file, "violation_categories", "missing_or_non_object", "dict", _type_name(vc)))
    else:
        for sev in ("CRITICAL", "HIGH", "MODERATE", "LOW"):
            if sev not in vc:
                findings.append(Finding("warning", file, f"violation_categories.{sev}", "missing_severity_category", "present", "missing"))


def check_user_goals_to_clusters(findings: List[Finding], data: Dict[str, Any], file: str) -> None:
    raw = data.get("user_goal_mappings")
    if not isinstance(raw, list):
        findings.append(Finding("error", file, "user_goal_mappings", "missing_or_non_list", "list", _type_name(raw)))
        return
    for i, e in enumerate(raw):
        if not isinstance(e, dict):
            findings.append(Finding("error", file, f"user_goal_mappings[{i}]", "entry_not_object", "dict", _type_name(e)))
            continue
        _check_required(findings, file, e, i, [("id", str), ("user_facing_goal", str)])
        _check_list_of_strings(findings, file, e, i, "primary_clusters", required=True, allow_empty=False)


def check_overlap_allowlist(findings: List[Finding], data: Dict[str, Any], file: str) -> None:
    raw = data.get("allowed_overlaps")
    if not isinstance(raw, list):
        findings.append(Finding("error", file, "allowed_overlaps", "missing_or_non_list", "list", _type_name(raw)))
        return
    for i, e in enumerate(raw):
        if not isinstance(e, dict):
            findings.append(Finding("error", file, f"[{i}]", "entry_not_object", "dict", _type_name(e)))
            continue
        _check_required(findings, file, e, i, [("term_normalized", str), ("reason", str)])
        pairs = e.get("db_pairs")
        if not isinstance(pairs, list):
            findings.append(Finding("error", file, f"[{i}].db_pairs", "type_mismatch", "list", _type_name(pairs)))


def check_percentile_categories(findings: List[Finding], data: Dict[str, Any], file: str) -> None:
    categories = data.get("categories")
    if not isinstance(categories, dict):
        findings.append(Finding("error", file, "categories", "missing_or_non_object", "dict", _type_name(categories)))
        return

    rules = data.get("classification_rules")
    if not isinstance(rules, dict):
        findings.append(Finding("error", file, "classification_rules", "missing_or_non_object", "dict", _type_name(rules)))
    else:
        for key in ("confidence_threshold", "margin_threshold", "score_normalizer"):
            value = rules.get(key)
            if not isinstance(value, (int, float)):
                findings.append(Finding("error", file, f"classification_rules.{key}", "type_mismatch", "number", _type_name(value)))

    fallback_count = 0
    for category_id, category in categories.items():
        if not isinstance(category, dict):
            findings.append(Finding("error", file, f"categories.{category_id}", "entry_not_object", "dict", _type_name(category)))
            continue
        label = category.get("label")
        if not isinstance(label, str) or not label.strip():
            findings.append(Finding("error", file, f"categories.{category_id}.label", "missing_or_wrong_type", "str", _type_name(label)))
        priority = category.get("priority")
        if not isinstance(priority, int):
            findings.append(Finding("error", file, f"categories.{category_id}.priority", "type_mismatch", "int", _type_name(priority)))
        if category.get("is_fallback"):
            fallback_count += 1
            continue
        min_score = category.get("min_evidence_score")
        if not isinstance(min_score, (int, float)):
            findings.append(Finding("error", file, f"categories.{category_id}.min_evidence_score", "type_mismatch", "number", _type_name(min_score)))
        required = category.get("required")
        if required is not None and not isinstance(required, dict):
            findings.append(Finding("error", file, f"categories.{category_id}.required", "type_mismatch", "dict|null", _type_name(required)))
        evidence = category.get("evidence")
        if evidence is not None and not isinstance(evidence, dict):
            findings.append(Finding("error", file, f"categories.{category_id}.evidence", "type_mismatch", "dict|null", _type_name(evidence)))

    if fallback_count != 1:
        findings.append(Finding("error", file, "categories", "invalid_fallback_count", "exactly 1 fallback category", str(fallback_count)))


def check_clinical_risk_taxonomy(findings: List[Finding], data: Dict[str, Any], file: str) -> None:
    if not isinstance(data, dict):
        findings.append(Finding("error", file, "$", "non_object_root", "dict", _type_name(data)))
        return

    def _validate_catalog(key: str, require_label: bool = True) -> None:
        raw = data.get(key)
        if not isinstance(raw, list):
            findings.append(Finding("error", file, key, "missing_or_non_list", "list", _type_name(raw)))
            return
        seen: set = set()
        for i, entry in enumerate(raw):
            if not isinstance(entry, dict):
                findings.append(Finding("error", file, f"{key}[{i}]", "entry_not_object", "dict", _type_name(entry)))
                continue
            _check_required(findings, file, entry, i, [("id", str)])
            if require_label:
                _check_required(findings, file, entry, i, [("label", str)])
            entry_id = str(entry.get("id", "")).strip().lower()
            if entry_id:
                if entry_id in seen:
                    findings.append(Finding("error", file, f"{key}[{i}].id", "duplicate_id", "unique id", entry_id))
                seen.add(entry_id)

    _validate_catalog("conditions", require_label=True)
    _validate_catalog("drug_classes", require_label=True)
    _validate_catalog("severity_levels", require_label=True)
    _validate_catalog("evidence_levels", require_label=False)

    for i, entry in enumerate(data.get("severity_levels", []) or []):
        if not isinstance(entry, dict):
            continue
        weight = entry.get("weight")
        if not isinstance(weight, (int, float)):
            findings.append(Finding("error", file, f"severity_levels[{i}].weight", "type_mismatch", "number", _type_name(weight)))


def check_ingredient_interaction_rules(findings: List[Finding], data: Dict[str, Any], file: str) -> None:
    raw = data.get("interaction_rules")
    if not isinstance(raw, list):
        findings.append(Finding("error", file, "interaction_rules", "missing_or_non_list", "list", _type_name(raw)))
        return

    taxonomy = _load_json(DATA_DIR / "clinical_risk_taxonomy.json")
    valid_conditions = {
        str(e.get("id")).strip().lower()
        for e in (taxonomy.get("conditions", []) if isinstance(taxonomy, dict) else [])
        if isinstance(e, dict) and e.get("id")
    }
    valid_drug_classes = {
        str(e.get("id")).strip().lower()
        for e in (taxonomy.get("drug_classes", []) if isinstance(taxonomy, dict) else [])
        if isinstance(e, dict) and e.get("id")
    }
    valid_severity = {
        str(e.get("id")).strip().lower()
        for e in (taxonomy.get("severity_levels", []) if isinstance(taxonomy, dict) else [])
        if isinstance(e, dict) and e.get("id")
    }
    valid_evidence = {
        str(e.get("id")).strip().lower()
        for e in (taxonomy.get("evidence_levels", []) if isinstance(taxonomy, dict) else [])
        if isinstance(e, dict) and e.get("id")
    }

    iqm = _load_json(DATA_DIR / "ingredient_quality_map.json")
    iqm_ids = {k for k in iqm.keys() if isinstance(iqm, dict) and not str(k).startswith("_")}
    other = _load_json(DATA_DIR / "other_ingredients.json")
    other_ids = {
        e.get("id")
        for e in (other.get("other_ingredients", []) if isinstance(other, dict) else [])
        if isinstance(e, dict) and e.get("id")
    }
    harmful = _load_json(DATA_DIR / "harmful_additives.json")
    harmful_ids = {
        e.get("id")
        for e in (harmful.get("harmful_additives", []) if isinstance(harmful, dict) else [])
        if isinstance(e, dict) and e.get("id")
    }
    banned = _load_json(DATA_DIR / "banned_recalled_ingredients.json")
    banned_ids = {
        e.get("id")
        for e in (banned.get("ingredients", []) if isinstance(banned, dict) else [])
        if isinstance(e, dict) and e.get("id")
    }
    botanical = _load_json(DATA_DIR / "botanical_ingredients.json")
    botanical_ids = {
        e.get("id")
        for e in (botanical.get("botanical_ingredients", []) if isinstance(botanical, dict) else [])
        if isinstance(e, dict) and e.get("id")
    }
    source_id_map = {
        "ingredient_quality_map": iqm_ids,
        "other_ingredients": other_ids,
        "harmful_additives": harmful_ids,
        "banned_recalled_ingredients": banned_ids,
        "botanical_ingredients": botanical_ids,
    }

    valid_db_keys = set(source_id_map.keys())
    valid_comparators = {">", ">=", "<", "<=", "=="}
    valid_basis = {"per_day", "per_serving"}
    valid_scope = {"condition", "drug_class"}
    seen_ids: set = set()

    for i, rule in enumerate(raw):
        if not isinstance(rule, dict):
            findings.append(Finding("error", file, f"[{i}]", "entry_not_object", "dict", _type_name(rule)))
            continue
        _check_required(findings, file, rule, i, [("id", str), ("subject_ref", dict), ("last_reviewed", str), ("review_owner", str)])
        rule_id = str(rule.get("id", "")).strip()
        if rule_id:
            if rule_id in seen_ids:
                findings.append(Finding("error", file, f"[{i}].id", "duplicate_id", "unique id", rule_id))
            seen_ids.add(rule_id)

        subject_ref = rule.get("subject_ref", {})
        if not isinstance(subject_ref, dict):
            findings.append(Finding("error", file, f"[{i}].subject_ref", "type_mismatch", "dict", _type_name(subject_ref)))
            continue

        db_key = str(subject_ref.get("db", "")).strip().lower()
        canonical_id = str(subject_ref.get("canonical_id", "")).strip()
        if db_key not in valid_db_keys:
            findings.append(Finding("error", file, f"[{i}].subject_ref.db", "enum_value_not_supported", "|".join(sorted(valid_db_keys)), db_key))
        if not canonical_id:
            findings.append(Finding("error", file, f"[{i}].subject_ref.canonical_id", "missing_required_key", "non-empty string", "missing_or_empty"))
        elif db_key in source_id_map and canonical_id not in source_id_map[db_key]:
            findings.append(Finding("error", file, f"[{i}].subject_ref.canonical_id", "unresolved_subject_ref", f"existing id in {db_key}", canonical_id))

        form_scope = rule.get("form_scope")
        if form_scope is not None:
            if not isinstance(form_scope, list):
                findings.append(Finding("error", file, f"[{i}].form_scope", "type_mismatch", "list[str]|null", _type_name(form_scope)))
            else:
                for j, item in enumerate(form_scope):
                    if not isinstance(item, str) or not item.strip():
                        findings.append(Finding("error", file, f"[{i}].form_scope[{j}]", "invalid_form_scope_value", "non-empty str", _type_name(item)))

        dose_thresholds = rule.get("dose_thresholds")
        if dose_thresholds is not None:
            if not isinstance(dose_thresholds, list):
                findings.append(Finding("error", file, f"[{i}].dose_thresholds", "type_mismatch", "list[dict]|null", _type_name(dose_thresholds)))
                dose_thresholds = []
            for j, threshold in enumerate(dose_thresholds):
                if not isinstance(threshold, dict):
                    findings.append(Finding("error", file, f"[{i}].dose_thresholds[{j}]", "entry_not_object", "dict", _type_name(threshold)))
                    continue
                for key in ("scope", "target_id", "basis", "comparator", "unit", "severity_if_met"):
                    if key not in threshold:
                        findings.append(Finding("error", file, f"[{i}].dose_thresholds[{j}].{key}", "missing_required_key", "non-empty string", "missing"))
                    elif not isinstance(threshold.get(key), str) or not str(threshold.get(key)).strip():
                        findings.append(Finding("error", file, f"[{i}].dose_thresholds[{j}].{key}", "type_mismatch", "non-empty string", _type_name(threshold.get(key))))
                value = threshold.get("value")
                if not isinstance(value, (int, float)):
                    findings.append(Finding("error", file, f"[{i}].dose_thresholds[{j}].value", "type_mismatch", "number", _type_name(value)))

                scope = str(threshold.get("scope", "")).strip().lower()
                target_id = str(threshold.get("target_id", "")).strip().lower()
                basis = str(threshold.get("basis", "")).strip().lower()
                comparator = str(threshold.get("comparator", "")).strip()
                severity_if_met = str(threshold.get("severity_if_met", "")).strip().lower()
                severity_if_not_met = str(threshold.get("severity_if_not_met", "")).strip().lower()

                if scope not in valid_scope:
                    findings.append(Finding("error", file, f"[{i}].dose_thresholds[{j}].scope", "enum_value_not_supported", "|".join(sorted(valid_scope)), scope))
                if basis not in valid_basis:
                    findings.append(Finding("error", file, f"[{i}].dose_thresholds[{j}].basis", "enum_value_not_supported", "|".join(sorted(valid_basis)), basis))
                if comparator not in valid_comparators:
                    findings.append(Finding("error", file, f"[{i}].dose_thresholds[{j}].comparator", "enum_value_not_supported", "|".join(sorted(valid_comparators)), comparator))
                if severity_if_met not in valid_severity:
                    findings.append(Finding("error", file, f"[{i}].dose_thresholds[{j}].severity_if_met", "enum_value_not_supported", "valid severity id", severity_if_met))
                if severity_if_not_met and severity_if_not_met not in valid_severity:
                    findings.append(Finding("error", file, f"[{i}].dose_thresholds[{j}].severity_if_not_met", "enum_value_not_supported", "valid severity id", severity_if_not_met))
                if scope == "condition" and target_id not in valid_conditions:
                    findings.append(Finding("error", file, f"[{i}].dose_thresholds[{j}].target_id", "enum_value_not_supported", "valid condition id", target_id))
                if scope == "drug_class" and target_id not in valid_drug_classes:
                    findings.append(Finding("error", file, f"[{i}].dose_thresholds[{j}].target_id", "enum_value_not_supported", "valid drug_class id", target_id))

        all_sources: List[str] = []
        condition_rules = rule.get("condition_rules", [])
        drug_rules = rule.get("drug_class_rules", [])
        pregnancy_block = rule.get("pregnancy_lactation")
        if not isinstance(condition_rules, list):
            findings.append(Finding("error", file, f"[{i}].condition_rules", "type_mismatch", "list", _type_name(condition_rules)))
            condition_rules = []
        if not isinstance(drug_rules, list):
            findings.append(Finding("error", file, f"[{i}].drug_class_rules", "type_mismatch", "list", _type_name(drug_rules)))
            drug_rules = []

        for j, cond in enumerate(condition_rules):
            if not isinstance(cond, dict):
                findings.append(Finding("error", file, f"[{i}].condition_rules[{j}]", "entry_not_object", "dict", _type_name(cond)))
                continue
            _check_required(findings, file, cond, i, [("condition_id", str), ("severity", str), ("evidence_level", str), ("action", str)])
            cid = str(cond.get("condition_id", "")).strip().lower()
            sev = str(cond.get("severity", "")).strip().lower()
            ev = str(cond.get("evidence_level", "")).strip().lower()
            if cid not in valid_conditions:
                findings.append(Finding("error", file, f"[{i}].condition_rules[{j}].condition_id", "enum_value_not_supported", "valid condition id", cid))
            if sev not in valid_severity:
                findings.append(Finding("error", file, f"[{i}].condition_rules[{j}].severity", "enum_value_not_supported", "valid severity id", sev))
            if ev not in valid_evidence:
                findings.append(Finding("error", file, f"[{i}].condition_rules[{j}].evidence_level", "enum_value_not_supported", "valid evidence id", ev))
            sources = cond.get("sources")
            if not isinstance(sources, list) or not sources:
                findings.append(Finding("error", file, f"[{i}].condition_rules[{j}].sources", "missing_or_non_list", "non-empty list[str]", _type_name(sources)))
            else:
                for k, src in enumerate(sources):
                    if not isinstance(src, str) or not src.strip().startswith(("http://", "https://")):
                        findings.append(Finding("error", file, f"[{i}].condition_rules[{j}].sources[{k}]", "invalid_source_url", "http(s) url string", _type_name(src)))
                    elif isinstance(src, str):
                        all_sources.append(src.strip())

        for j, drug in enumerate(drug_rules):
            if not isinstance(drug, dict):
                findings.append(Finding("error", file, f"[{i}].drug_class_rules[{j}]", "entry_not_object", "dict", _type_name(drug)))
                continue
            _check_required(findings, file, drug, i, [("drug_class_id", str), ("severity", str), ("evidence_level", str), ("action", str)])
            did = str(drug.get("drug_class_id", "")).strip().lower()
            sev = str(drug.get("severity", "")).strip().lower()
            ev = str(drug.get("evidence_level", "")).strip().lower()
            if did not in valid_drug_classes:
                findings.append(Finding("error", file, f"[{i}].drug_class_rules[{j}].drug_class_id", "enum_value_not_supported", "valid drug_class id", did))
            if sev not in valid_severity:
                findings.append(Finding("error", file, f"[{i}].drug_class_rules[{j}].severity", "enum_value_not_supported", "valid severity id", sev))
            if ev not in valid_evidence:
                findings.append(Finding("error", file, f"[{i}].drug_class_rules[{j}].evidence_level", "enum_value_not_supported", "valid evidence id", ev))
            sources = drug.get("sources")
            if not isinstance(sources, list) or not sources:
                findings.append(Finding("error", file, f"[{i}].drug_class_rules[{j}].sources", "missing_or_non_list", "non-empty list[str]", _type_name(sources)))
            else:
                for k, src in enumerate(sources):
                    if not isinstance(src, str) or not src.strip().startswith(("http://", "https://")):
                        findings.append(Finding("error", file, f"[{i}].drug_class_rules[{j}].sources[{k}]", "invalid_source_url", "http(s) url string", _type_name(src)))
                    elif isinstance(src, str):
                        all_sources.append(src.strip())

        if pregnancy_block is not None:
            if not isinstance(pregnancy_block, dict):
                findings.append(Finding("error", file, f"[{i}].pregnancy_lactation", "type_mismatch", "dict|null", _type_name(pregnancy_block)))
            else:
                for field in ("pregnancy_category", "lactation_category"):
                    value = pregnancy_block.get(field)
                    if value is not None:
                        sev = str(value).strip().lower()
                        if sev not in valid_severity:
                            findings.append(Finding("error", file, f"[{i}].pregnancy_lactation.{field}", "enum_value_not_supported", "valid severity id", sev))
                sources = pregnancy_block.get("sources")
                if sources is not None:
                    if not isinstance(sources, list) or not sources:
                        findings.append(Finding("error", file, f"[{i}].pregnancy_lactation.sources", "missing_or_non_list", "non-empty list[str]", _type_name(sources)))
                    else:
                        for k, src in enumerate(sources):
                            if not isinstance(src, str) or not src.strip().startswith(("http://", "https://")):
                                findings.append(Finding("error", file, f"[{i}].pregnancy_lactation.sources[{k}]", "invalid_source_url", "http(s) url string", _type_name(src)))
                            elif isinstance(src, str):
                                all_sources.append(src.strip())

        if not all_sources:
            findings.append(Finding("error", file, f"[{i}]", "missing_provenance_sources", "at least one http(s) source URL", "none"))


def run_checks() -> List[Finding]:
    findings: List[Finding] = []

    required_files = {
        "ingredient_quality_map.json": check_iqm,
        "allergens.json": check_allergens,
        "harmful_additives.json": check_harmful_additives,
        "banned_recalled_ingredients.json": check_banned,
        "other_ingredients.json": check_other_ingredients,
        "absorption_enhancers.json": check_absorption_enhancers,
        "standardized_botanicals.json": check_standardized_botanicals,
        "synergy_cluster.json": check_synergy_cluster,
        "backed_clinical_studies.json": check_clinical_db,
        "top_manufacturers_data.json": check_top_manufacturers,
        "cert_claim_rules.json": check_cert_claim_rules,
        "rda_optimal_uls.json": check_rda_optimal_uls,
        "rda_therapeutic_dosing.json": check_rda_therapeutic,
        "unit_conversions.json": check_unit_conversions,
        "botanical_ingredients.json": check_botanical_ingredients,
        "clinically_relevant_strains.json": check_clinically_relevant_strains,
        "proprietary_blends.json": check_proprietary_blends,
        "manufacturer_violations.json": check_manufacturer_violations,
        "ingredient_classification.json": check_ingredient_classification,
        "enhanced_delivery.json": check_enhanced_delivery,
        "color_indicators.json": check_color_indicators,
        "id_redirects.json": check_id_redirects,
        "cross_db_overlap_allowlist.json": check_overlap_allowlist,
        "banned_match_allowlist.json": check_banned_match_allowlist,
        "functional_ingredient_groupings.json": check_functional_ingredient_groupings,
        "ingredient_weights.json": check_ingredient_weights,
        "manufacture_deduction_expl.json": check_manufacture_deduction_expl,
        "user_goals_to_clusters.json": check_user_goals_to_clusters,
        "percentile_categories.json": check_percentile_categories,
        "clinical_risk_taxonomy.json": check_clinical_risk_taxonomy,
        "ingredient_interaction_rules.json": check_ingredient_interaction_rules,
    }

    for name, checker in required_files.items():
        path = DATA_DIR / name
        if not path.exists():
            findings.append(Finding("error", name, "$", "file_missing", "present", "missing"))
            continue
        data = _load_json(path)
        if isinstance(data, dict) and "__load_error__" in data:
            findings.append(Finding("error", name, "$", "json_load_failed", "valid JSON", data["__load_error__"]))
            continue
        checker(findings, data, name)

        # Generic key-drift scan for common camelCase variants.
        for container_key in (
            "allergens",
            "harmful_additives",
            "other_ingredients",
            "standardized_botanicals",
            "backed_clinical_studies",
            "top_manufacturers",
            "absorption_enhancers",
            "therapeutic_dosing",
            "nutrient_recommendations",
            "ingredients",
        ):
            entries = _iter_entries(data, container_key)
            if entries:
                _check_camel_case_drift(
                    findings,
                    name,
                    entries,
                    {
                        "standardName": "standard_name",
                        "severityLevel": "severity_level",
                        "reviewStatus": "review_status",
                        "matchMode": "match_mode",
                        "legalStatusEnum": "legal_status_enum",
                        "clinicalRiskEnum": "clinical_risk_enum",
                        "studyType": "study_type",
                        "evidenceLevel": "evidence_level",
                    },
                )

    # Generic parse/metadata check for remaining data files not explicitly modeled.
    modeled = set(required_files.keys())
    for path in sorted(DATA_DIR.glob("*.json")):
        name = path.name
        if name in modeled:
            continue
        data = _load_json(path)
        if isinstance(data, dict) and "__load_error__" in data:
            findings.append(Finding("error", name, "$", "json_load_failed", "valid JSON", data["__load_error__"]))
            continue
        if not isinstance(data, dict):
            findings.append(Finding("warning", name, "$", "unexpected_root_type", "dict", _type_name(data)))
            continue
        if "_metadata" not in data:
            findings.append(Finding("warning", name, "_metadata", "missing_metadata_block", "present", "missing"))

    return findings


def print_text_report(findings: List[Finding]) -> None:
    by_severity = {"error": [], "warning": [], "info": []}
    for f in findings:
        by_severity.setdefault(f.severity, []).append(f)

    total = len(findings)
    print(f"\nDB Integrity Sanity Report")
    print(f"Total findings: {total} | errors={len(by_severity.get('error', []))} warnings={len(by_severity.get('warning', []))} info={len(by_severity.get('info', []))}\n")

    for sev in ("error", "warning", "info"):
        rows = by_severity.get(sev, [])
        if not rows:
            continue
        print(f"[{sev.upper()}] {len(rows)}")
        for item in rows[:300]:
            print(
                f"- {item.file}:{item.path} | {item.issue} | expected={item.expected} | actual={item.actual}"
            )
        if len(rows) > 300:
            print(f"... ({len(rows) - 300} more)")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description="DB/schema sanity check for clean→enrich→score compatibility")
    parser.add_argument("--json", action="store_true", help="Emit findings as JSON")
    parser.add_argument("--strict", action="store_true", help="Fail on warnings too")
    args = parser.parse_args()

    findings = run_checks()

    if args.json:
        print(json.dumps([f.__dict__ for f in findings], indent=2))
    else:
        print_text_report(findings)

    has_error = any(f.severity == "error" for f in findings)
    has_warning = any(f.severity == "warning" for f in findings)

    if has_error:
        return 2
    if args.strict and has_warning:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
