#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List


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


def _iter_ingredients(blob: Dict[str, Any]) -> Iterable[tuple[str, Dict[str, Any]]]:
    for key in ("ingredients", "inactive_ingredients", "activeIngredients", "inactiveIngredients"):
        value = blob.get(key)
        if isinstance(value, list):
            for ing in value:
                if isinstance(ing, dict):
                    yield key, ing


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


def audit(output_dir: Path) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for path in _iter_blob_paths(output_dir):
        try:
            blob = json.loads(path.read_text())
        except Exception as exc:
            findings.append({
                "code": "BLOB_READ_ERROR",
                "path": str(path),
                "message": str(exc),
            })
            continue

        dsld_id = _safe_str(blob.get("dsld_id") or blob.get("id") or path.stem)
        for section, ing in _iter_ingredients(blob):
            std_camel = _safe_str(ing.get("standardName"))
            std_snake = _safe_str(ing.get("standard_name"))
            safety_flags = [f for f in ing.get("safety_flags") or [] if isinstance(f, dict)]
            matched_source = _safe_str(ing.get("matched_source"))
            matched_rule_id = _safe_str(ing.get("matched_rule_id"))

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

            if (
                matched_source in {"banned_recalled", "banned_recalled_ingredients", "harmful_additives"}
                and matched_rule_id
                and not safety_flags
            ):
                findings.append({
                    "code": "LEGACY_SAFETY_WITHOUT_FLAG",
                    "dsld_id": dsld_id,
                    "section": section,
                    "ingredient": ing.get("name"),
                    "matched_source": matched_source,
                    "matched_rule_id": matched_rule_id,
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
    args = parser.parse_args()

    findings = audit(Path(args.output_dir))
    print(json.dumps({
        "output_dir": args.output_dir,
        "finding_count": len(findings),
        "findings": findings[:100],
    }, indent=2, sort_keys=True))
    return 1 if args.strict and findings else 0


if __name__ == "__main__":
    sys.exit(main())
