#!/usr/bin/env python3
"""Audit FDA %DV-backed dose plausibility in pipeline outputs.

Scans final detail blobs or intermediate JSON products for:
  - rows corrected by the cleaner's dose_data_quality contract
  - remaining mg-for-mcg suspects on nutrients whose FDA labeling DV unit is mcg
  - uncorrected rows where %DV metadata proves a likely unit mismatch

The audit is intentionally report-only. Corrections happen in the cleaner.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DAILY_VALUES_PATH = ROOT / "scripts" / "data" / "daily_values.json"
DEFAULT_INPUT = ROOT / "scripts" / "final_db_output" / "detail_blobs"
DEFAULT_OUTPUT = ROOT / "reports" / "dv_plausibility_audit.csv"


def _normalize_key(value: Any) -> str:
    if not value:
        return ""
    text = str(value).lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def _normalize_unit(value: Any) -> str:
    unit = str(value or "").strip().lower().replace("µg", "mcg").replace("μg", "mcg")
    unit = unit.replace("micrograms", "mcg").replace("microgram", "mcg")
    unit = unit.replace("milligrams", "mg").replace("milligram", "mg")
    return re.sub(r"\s+", " ", unit).strip()


def _normalize_target_group(value: Any) -> str | None:
    key = _normalize_key(value)
    if not key:
        return None
    if key in {"adult_4_plus", "adults_4_plus", "adults_and_children_4_plus"}:
        return "adult_4_plus"
    if key in {"pregnant_lactating", "pregnant_women_and_lactating_women"}:
        return "pregnant_lactating"
    if key in {"children_1_3", "children_1_through_3"}:
        return "children_1_3"
    if key in {"infants", "infants_through_12_months"}:
        return "infants"
    if "preg" in key or "lactat" in key:
        return "pregnant_lactating"
    if "infant" in key or "12_month" in key:
        return "infants"
    if "children" in key and ("1_3" in key or "1_through_3" in key):
        return "children_1_3"
    if "adult" in key or "4" in key:
        return "adult_4_plus"
    return None


def _load_daily_values(path: Path) -> tuple[dict[str, Any], dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        doc = json.load(f)
    nutrients = doc.get("nutrients") or {}
    lookup: dict[str, str] = {}
    for key, record in nutrients.items():
        if not isinstance(record, dict):
            continue
        terms = [key, record.get("standard_name")]
        terms.extend(record.get("aliases") or [])
        for term in terms:
            norm = _normalize_key(term)
            if norm:
                lookup.setdefault(norm, key)
    return nutrients, lookup


def _iter_json_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if (path / "detail_blobs").is_dir():
        path = path / "detail_blobs"
    return sorted(p for p in path.glob("*.json") if p.is_file())


def _resolve_nutrient_key(row: dict[str, Any], lookup: dict[str, str]) -> str | None:
    for field in ("canonical_id", "standardName", "standard_name", "name", "raw_source_text"):
        key = lookup.get(_normalize_key(row.get(field)))
        if key:
            return key
    return None


def _daily_value_from_row(row: dict[str, Any]) -> tuple[float | None, str | None]:
    daily_value = row.get("dailyValue") or row.get("daily_value") or row.get("percent_daily_value")
    try:
        percent = float(daily_value) if daily_value is not None else None
    except (TypeError, ValueError):
        percent = None

    target_group = (
        row.get("daily_value_target_group")
        or row.get("dailyValueTargetGroup")
        or row.get("targetGroup")
    )
    normalized_target = _normalize_target_group(target_group)
    return percent, normalized_target


def _classify_row(
    *,
    product: dict[str, Any],
    row: dict[str, Any],
    nutrient_key: str,
    nutrient_record: dict[str, Any],
) -> dict[str, Any] | None:
    dose_quality = row.get("dose_data_quality") if isinstance(row.get("dose_data_quality"), dict) else {}
    if dose_quality.get("status") == "corrected":
        return {
            "status": "corrected",
            "reason": dose_quality.get("reason"),
            "mismatch_ratio": dose_quality.get("mismatch_ratio"),
            "daily_value_target_group": dose_quality.get("daily_value_target_group"),
            "daily_value_reference_amount": dose_quality.get("daily_value_reference_amount"),
            "daily_value_reference_unit": dose_quality.get("daily_value_reference_unit"),
        }

    target_unit = _normalize_unit(nutrient_record.get("unit"))
    row_unit = _normalize_unit(row.get("unit") or row.get("dosage_unit"))
    if target_unit != "mcg" or row_unit != "mg":
        return None

    try:
        amount = float(row.get("quantity") if row.get("quantity") is not None else row.get("dosage"))
    except (TypeError, ValueError):
        return None
    if amount <= 0:
        return None

    percent_dv, target_group = _daily_value_from_row(row)
    target_groups = nutrient_record.get("target_groups") or {}
    if percent_dv and target_group in target_groups:
        expected = (percent_dv / 100.0) * float(target_groups[target_group])
        declared_mcg = amount * 1000.0
        mismatch_ratio = declared_mcg / expected if expected > 0 else None
        relative_error = abs(amount - expected) / expected if expected > 0 else None
        if mismatch_ratio and mismatch_ratio >= 100 and relative_error is not None and relative_error <= 0.20:
            return {
                "status": "uncorrected_dv_mismatch",
                "reason": "daily_value_unit_mismatch",
                "mismatch_ratio": mismatch_ratio,
                "daily_value_target_group": target_group,
                "daily_value_reference_amount": target_groups[target_group],
                "daily_value_reference_unit": target_unit,
            }

    if amount >= 10 and nutrient_key in {"vitamin_d", "iodine"}:
        return {
            "status": "suspect_no_dv_evidence",
            "reason": "mg_unit_for_mcg_dv_nutrient",
            "mismatch_ratio": None,
            "daily_value_target_group": target_group,
            "daily_value_reference_amount": None,
            "daily_value_reference_unit": target_unit,
        }
    return None


def audit(input_path: Path, output_path: Path, daily_values_path: Path = DAILY_VALUES_PATH) -> dict[str, int]:
    nutrients, lookup = _load_daily_values(daily_values_path)
    rows_out: list[dict[str, Any]] = []
    counts = {"files": 0, "corrected": 0, "uncorrected_dv_mismatch": 0, "suspect_no_dv_evidence": 0}

    for file_path in _iter_json_files(input_path):
        try:
            with file_path.open("r", encoding="utf-8") as f:
                product = json.load(f)
        except Exception:
            continue
        counts["files"] += 1
        ingredients = product.get("ingredients") or product.get("activeIngredients") or []
        if not isinstance(ingredients, list):
            continue
        for row in ingredients:
            if not isinstance(row, dict):
                continue
            nutrient_key = _resolve_nutrient_key(row, lookup)
            if not nutrient_key:
                continue
            classification = _classify_row(
                product=product,
                row=row,
                nutrient_key=nutrient_key,
                nutrient_record=nutrients[nutrient_key],
            )
            if not classification:
                continue
            status = classification["status"]
            counts[status] = counts.get(status, 0) + 1
            rows_out.append({
                "status": status,
                "reason": classification.get("reason"),
                "dsld_id": product.get("dsld_id") or product.get("id"),
                "product_name": product.get("product_name") or product.get("fullName"),
                "brand_name": product.get("brand_name") or product.get("brandName"),
                "nutrient_key": nutrient_key,
                "ingredient_name": row.get("name") or row.get("raw_source_text"),
                "standard_name": row.get("standardName") or row.get("standard_name"),
                "quantity": row.get("quantity") if row.get("quantity") is not None else row.get("dosage"),
                "unit": row.get("unit") or row.get("dosage_unit"),
                "daily_value": row.get("dailyValue") or row.get("daily_value") or row.get("percent_daily_value"),
                "daily_value_target_group": classification.get("daily_value_target_group"),
                "daily_value_reference_amount": classification.get("daily_value_reference_amount"),
                "daily_value_reference_unit": classification.get("daily_value_reference_unit"),
                "mismatch_ratio": classification.get("mismatch_ratio"),
                "source_file": str(file_path),
            })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "status",
        "reason",
        "dsld_id",
        "product_name",
        "brand_name",
        "nutrient_key",
        "ingredient_name",
        "standard_name",
        "quantity",
        "unit",
        "daily_value",
        "daily_value_target_group",
        "daily_value_reference_amount",
        "daily_value_reference_unit",
        "mismatch_ratio",
        "source_file",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)
    counts["rows"] = len(rows_out)
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--daily-values", type=Path, default=DAILY_VALUES_PATH)
    args = parser.parse_args()

    counts = audit(args.input, args.output, args.daily_values)
    print(
        "DV plausibility audit: "
        f"files={counts.get('files', 0)} rows={counts.get('rows', 0)} "
        f"corrected={counts.get('corrected', 0)} "
        f"uncorrected_dv_mismatch={counts.get('uncorrected_dv_mismatch', 0)} "
        f"suspect_no_dv_evidence={counts.get('suspect_no_dv_evidence', 0)} "
        f"output={args.output}"
    )
    return 1 if counts.get("uncorrected_dv_mismatch", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
