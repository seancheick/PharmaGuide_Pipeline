#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = SCRIPT_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from identity.safety import normalize_safety_source, safety_normalize_text


SAFETY_IDENTITY_SOURCES = {
    "banned_recalled",
    "banned_recalled_ingredients",
    "harmful_additives",
    "allergens",
    "contaminants",
    "recalls",
}

IDENTITY_SOURCE_FILES = {
    "ingredient_quality_map.json",
    "standardized_botanicals.json",
    "botanical_ingredients.json",
    "other_ingredients.json",
}

SAFETY_SOURCE_FILES = {
    "banned_recalled_ingredients.json",
    "harmful_additives.json",
}

QUALIFIER_RE = re.compile(
    r"\b(?:high\s+dose|e\d+|extract|asbestos|monacolin|hexavalent|chromate|dichromate|vi|6\+)\b",
    re.IGNORECASE,
)


def _safe_str(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _norm(value: Any) -> str:
    text = _safe_str(value).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _iter_blob_paths(output_dir: Path) -> Iterable[Path]:
    detail_dir = output_dir / "detail_blobs"
    if detail_dir.exists():
        yield from sorted(detail_dir.glob("*.json"))
        return
    yield from sorted(output_dir.glob("*.json"))


def _iter_product_blobs(doc: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(doc, list):
        for item in doc:
            if isinstance(item, dict):
                yield item
    elif isinstance(doc, dict):
        yield doc


def _iter_ingredients(blob: Dict[str, Any]) -> Iterable[tuple[str, Dict[str, Any]]]:
    for key in (
        "ingredients",
        "inactive_ingredients",
        "activeIngredients",
        "inactiveIngredients",
        "otherIngredients",
    ):
        value = blob.get(key)
        if isinstance(value, list):
            for ing in value:
                if isinstance(ing, dict):
                    yield key, ing


def _iter_form_texts(ing: Dict[str, Any]) -> Iterable[Any]:
    for form in ing.get("forms") or []:
        if isinstance(form, dict):
            yield form.get("name")
            yield form.get("prefix")
            yield form.get("label")
        elif form:
            yield form


def _iter_raw_safety_evidence_texts(ing: Dict[str, Any]) -> Iterable[Any]:
    yield ing.get("raw_source_text")
    yield ing.get("name")
    yield ing.get("ingredient_name")
    yield ing.get("display_name")
    yield ing.get("label_text")
    yield from _iter_form_texts(ing)


def _iter_safety_flag_evidence_terms(flag: Dict[str, Any]) -> Iterable[str]:
    for key in ("evidence_text", "matched_variant", "ingredient_name", "name"):
        value = _safe_str(flag.get(key))
        if value:
            yield value


def _contains_normalized(haystack: Iterable[Any], needle: Any) -> bool:
    needle_norm = _norm(needle)
    if not needle_norm:
        return False
    return any(needle_norm in _norm(text) for text in haystack)


def _source_is_safety_identity(source: Any) -> bool:
    return normalize_safety_source(source) in SAFETY_IDENTITY_SOURCES


def _flag_matches_legacy_safety(
    flag: Dict[str, Any],
    *,
    matched_source: str,
    matched_rule_id: str,
) -> bool:
    flag_source = normalize_safety_source(flag.get("source_db") or flag.get("matched_source"))
    legacy_source = normalize_safety_source(matched_source)
    flag_rule_id = _safe_str(flag.get("entry_id") or flag.get("rule_id"))
    return bool(flag_rule_id and flag_rule_id == matched_rule_id and flag_source == legacy_source)


def _flag_supported_only_by_standard_name(ing: Dict[str, Any], flag: Dict[str, Any]) -> bool:
    source = normalize_safety_source(flag.get("source_db") or flag.get("source"))
    if source not in {"banned_recalled_ingredients", "harmful_additives"}:
        return False

    evidence_terms = list(_iter_safety_flag_evidence_terms(flag))
    if not evidence_terms:
        return False

    raw_texts = list(_iter_raw_safety_evidence_texts(ing))
    standard_texts = [ing.get("standardName"), ing.get("standard_name")]
    supported_by_raw = any(_contains_normalized(raw_texts, term) for term in evidence_terms)
    supported_by_standard_name = any(
        _contains_normalized(standard_texts, term)
        for term in evidence_terms
    )
    return supported_by_standard_name and not supported_by_raw


def _has_explicit_hexavalent_evidence(ing: Dict[str, Any]) -> bool:
    texts = [
        ing.get("raw_source_text"),
        ing.get("name"),
    ]
    for form in ing.get("forms") or []:
        if isinstance(form, dict):
            texts.extend([form.get("name"), form.get("prefix")])
    raw = " ".join(_safe_str(t) for t in texts).lower()
    return bool(
        re.search(r"\bhexavalent\b", raw)
        or re.search(r"\bchromium\s*[\(]?vi[\)]?", raw)
        or re.search(r"\bchromium\s*-\s*6\b", raw)
        or re.search(r"\bcr\s*[\(\-]?vi[\)]?\b", raw)
        or re.search(r"\bchromate\b", raw)
        or re.search(r"\bdichromate\b", raw)
    )


def _iter_reference_entries(doc: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(doc, list):
        iterable = doc
    elif isinstance(doc, dict):
        if "ingredients" in doc:
            iterable = doc.get("ingredients") or []
        elif "additives" in doc:
            iterable = doc.get("additives") or []
        else:
            iterable = [
                value for key, value in doc.items()
                if key != "_metadata" and isinstance(value, dict)
            ]
    else:
        iterable = []
    for entry in iterable:
        if isinstance(entry, dict):
            yield entry


def _entry_variants(entry: Dict[str, Any]) -> Iterable[Any]:
    yield entry.get("standard_name")
    yield entry.get("name")
    for alias in entry.get("aliases") or []:
        yield alias


def _is_qualified_safety_entry(entry: Dict[str, Any]) -> bool:
    return bool(QUALIFIER_RE.search(_safe_str(entry.get("standard_name") or entry.get("name"))))


def _identity_reference_keys(data_dir: Path) -> Dict[str, str]:
    keys: Dict[str, str] = {}
    for filename in IDENTITY_SOURCE_FILES:
        path = data_dir / filename
        if not path.exists():
            continue
        try:
            doc = json.loads(path.read_text())
        except Exception:
            continue
        for entry in _iter_reference_entries(doc):
            for variant in _entry_variants(entry):
                key = safety_normalize_text(variant)
                if key:
                    keys.setdefault(key, filename)
    return keys


def _safety_reference_keys(data_dir: Path) -> Dict[str, Dict[str, Any]]:
    keys: Dict[str, Dict[str, Any]] = {}
    for filename in SAFETY_SOURCE_FILES:
        path = data_dir / filename
        if not path.exists():
            continue
        try:
            doc = json.loads(path.read_text())
        except Exception:
            continue
        for entry in _iter_reference_entries(doc):
            for variant in _entry_variants(entry):
                key = _norm(variant)
                if key:
                    keys.setdefault(key, {
                        "source_file": filename,
                        "entry_id": entry.get("id"),
                        "standard_name": entry.get("standard_name") or entry.get("name"),
                    })
    return keys


def audit_reference_data(data_dir: Path) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    identity_keys = _identity_reference_keys(data_dir)
    if not identity_keys:
        return findings

    for filename in SAFETY_SOURCE_FILES:
        path = data_dir / filename
        if not path.exists():
            continue
        try:
            doc = json.loads(path.read_text())
        except Exception as exc:
            findings.append({
                "code": "REFERENCE_READ_ERROR",
                "path": str(path),
                "message": str(exc),
            })
            continue
        for entry in _iter_reference_entries(doc):
            if not _is_qualified_safety_entry(entry):
                continue
            standard_key = safety_normalize_text(entry.get("standard_name") or entry.get("name"))
            for variant in _entry_variants(entry):
                variant_key = safety_normalize_text(variant)
                if not variant_key or variant_key == standard_key:
                    continue
                if variant_key in identity_keys:
                    findings.append({
                        "code": "QUALIFIED_SAFETY_ALIAS_COLLAPSES_TO_IDENTITY",
                        "source_file": filename,
                        "entry_id": entry.get("id"),
                        "standard_name": entry.get("standard_name"),
                        "variant": variant,
                        "identity_source_file": identity_keys[variant_key],
                    })
    return findings


def audit(output_dir: Path, *, reference_data_dir: Path | None = None) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    safety_reference_keys = (
        _safety_reference_keys(reference_data_dir)
        if reference_data_dir
        else {}
    )
    for path in _iter_blob_paths(output_dir):
        try:
            doc = json.loads(path.read_text())
        except Exception as exc:
            findings.append({
                "code": "BLOB_READ_ERROR",
                "path": str(path),
                "message": str(exc),
            })
            continue

        for blob in _iter_product_blobs(doc):
            dsld_id = _safe_str(blob.get("dsld_id") or blob.get("id") or path.stem)
            for section, ing in _iter_ingredients(blob):
                std_camel = _safe_str(ing.get("standardName"))
                std_snake = _safe_str(ing.get("standard_name"))
                safety_flags = [f for f in ing.get("safety_flags") or [] if isinstance(f, dict)]
                matched_source = _safe_str(ing.get("matched_source"))
                matched_rule_id = _safe_str(ing.get("matched_rule_id"))
                canonical_source_db = _safe_str(ing.get("canonical_source_db") or ing.get("source_db"))

                if std_camel and std_snake and std_camel != std_snake:
                    findings.append({
                        "code": "STANDARD_NAME_ALIAS_DRIFT",
                        "dsld_id": dsld_id,
                        "section": section,
                        "ingredient": ing.get("name"),
                        "standardName": std_camel,
                        "standard_name": std_snake,
                        "path": str(path),
                    })

                if canonical_source_db and _source_is_safety_identity(canonical_source_db):
                    findings.append({
                        "code": "IDENTITY_FROM_SAFETY_SOURCE",
                        "dsld_id": dsld_id,
                        "section": section,
                        "ingredient": ing.get("name"),
                        "canonical_source_db": canonical_source_db,
                        "standardName": std_camel,
                        "path": str(path),
                    })

                raw_identity_terms = {
                    _norm(ing.get("raw_source_text")),
                    _norm(ing.get("name")),
                    _norm(ing.get("ingredient_name")),
                    _norm(ing.get("display_name")),
                }
                std_norm = _norm(std_camel)
                if (
                    safety_reference_keys
                    and std_norm
                    and std_norm in safety_reference_keys
                    and std_norm not in raw_identity_terms
                    and (
                        not canonical_source_db
                        or canonical_source_db == "unmapped"
                        or _source_is_safety_identity(canonical_source_db)
                    )
                ):
                    ref = safety_reference_keys[std_norm]
                    findings.append({
                        "code": "STANDARD_NAME_FROM_SAFETY_SOURCE",
                        "dsld_id": dsld_id,
                        "section": section,
                        "ingredient": ing.get("name"),
                        "standardName": std_camel,
                        "canonical_source_db": canonical_source_db,
                        "source_file": ref.get("source_file"),
                        "entry_id": ref.get("entry_id"),
                        "path": str(path),
                    })

                if (
                    matched_source in {"banned_recalled", "banned_recalled_ingredients", "harmful_additives"}
                    and matched_rule_id
                ):
                    if not safety_flags:
                        findings.append({
                            "code": "LEGACY_SAFETY_WITHOUT_FLAG",
                            "dsld_id": dsld_id,
                            "section": section,
                            "ingredient": ing.get("name"),
                            "matched_source": matched_source,
                            "matched_rule_id": matched_rule_id,
                            "path": str(path),
                        })
                    elif not any(
                        _flag_matches_legacy_safety(
                            flag,
                            matched_source=matched_source,
                            matched_rule_id=matched_rule_id,
                        )
                        for flag in safety_flags
                    ):
                        findings.append({
                            "code": "LEGACY_SAFETY_WITHOUT_MATCHING_FLAG",
                            "dsld_id": dsld_id,
                            "section": section,
                            "ingredient": ing.get("name"),
                            "matched_source": matched_source,
                            "matched_rule_id": matched_rule_id,
                            "flag_ids": [
                                _safe_str(flag.get("entry_id") or flag.get("rule_id"))
                                for flag in safety_flags
                            ],
                            "path": str(path),
                        })

                for flag in safety_flags:
                    if _flag_supported_only_by_standard_name(ing, flag):
                        findings.append({
                            "code": "SAFETY_FLAG_SUPPORTED_ONLY_BY_STANDARD_NAME",
                            "dsld_id": dsld_id,
                            "section": section,
                            "ingredient": ing.get("name"),
                            "entry_id": flag.get("entry_id") or flag.get("rule_id"),
                            "evidence_text": flag.get("evidence_text"),
                            "matched_variant": flag.get("matched_variant"),
                            "standardName": std_camel,
                            "path": str(path),
                        })

                flag_ids = {
                    _safe_str(flag.get("entry_id") or flag.get("rule_id"))
                    for flag in safety_flags
                }
                if "HM_CHROMIUM_HEXAVALENT" in flag_ids or matched_rule_id == "HM_CHROMIUM_HEXAVALENT":
                    if not _has_explicit_hexavalent_evidence(ing):
                        findings.append({
                            "code": "CHROMIUM_HEXAVALENT_WITHOUT_EXPLICIT_EVIDENCE",
                            "dsld_id": dsld_id,
                            "section": section,
                            "ingredient": ing.get("name"),
                            "raw_source_text": ing.get("raw_source_text"),
                            "standardName": std_camel,
                            "path": str(path),
                        })

                if (
                    _norm(ing.get("name")) == "chromium"
                    and _norm(ing.get("raw_source_text")) == "chromium"
                    and "hexavalent" in _norm(std_camel)
                    and not _has_explicit_hexavalent_evidence(ing)
                ):
                    findings.append({
                        "code": "CHROMIUM_IDENTITY_CORRUPTION",
                        "dsld_id": dsld_id,
                        "section": section,
                        "ingredient": ing.get("name"),
                        "standardName": std_camel,
                        "path": str(path),
                    })

    if reference_data_dir:
        findings.extend(audit_reference_data(reference_data_dir))

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output_dir",
        nargs="?",
        default="scripts/final_db_output",
        help="Final DB output directory containing detail_blobs/",
    )
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on findings")
    parser.add_argument(
        "--reference-data-dir",
        default=None,
        help="Optional scripts/data directory for safety alias collapse checks",
    )
    args = parser.parse_args()

    findings = audit(
        Path(args.output_dir),
        reference_data_dir=Path(args.reference_data_dir) if args.reference_data_dir else None,
    )
    print(json.dumps({
        "output_dir": args.output_dir,
        "finding_count": len(findings),
        "findings": findings[:100],
    }, indent=2, sort_keys=True))
    return 1 if args.strict and findings else 0


if __name__ == "__main__":
    sys.exit(main())
