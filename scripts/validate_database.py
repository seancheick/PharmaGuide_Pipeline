"""
Standalone database validation script for scripts/data/*.json files.

Validates JSON integrity, metadata schema, cross-references between files,
and prints a pass/fail summary report.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Re-use the canonical DATA_DIR from constants
from constants import DATA_DIR

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
REQUIRED_SCHEMA_VERSION = "5.0.0"
SEVERITY_LEVEL_VALUES = {"critical", "high", "moderate", "low"}
DEPRECATED_FIELDS = {
    "canonical_name",
    "synonyms",
    "risk_level",
    "violation_severity",
    "database_info",
    "published_support",
}


def _load_json(path: Path):
    """Return parsed JSON or an error string."""
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        return f"Invalid JSON: {exc}"
    except Exception as exc:  # noqa: BLE001
        return f"Read error: {exc}"


def _find_primary_array(data: dict) -> list | None:
    """Heuristic: return the first top-level value that is a list."""
    for key, val in data.items():
        if key == "_metadata":
            continue
        if isinstance(val, list):
            return val
    return None


def _collect_ids(array: list) -> list[str]:
    """Extract all 'id' values from a list of dicts."""
    return [item["id"] for item in array if isinstance(item, dict) and "id" in item]


def _record_label(record: dict, index: int) -> str:
    rec_id = record.get("id")
    if isinstance(rec_id, str) and rec_id.strip():
        return rec_id
    name = record.get("standard_name") or record.get("name")
    if isinstance(name, str) and name.strip():
        return name
    return f"index {index}"


def _iter_nodes(node: Any, path: str = ""):
    """Yield (path, node) for recursive traversal of JSON-like structures."""
    yield path or "$", node
    if isinstance(node, dict):
        for key, value in node.items():
            next_path = f"{path}.{key}" if path else key
            yield from _iter_nodes(value, next_path)
    elif isinstance(node, list):
        for idx, value in enumerate(node):
            next_path = f"{path}[{idx}]" if path else f"[{idx}]"
            yield from _iter_nodes(value, next_path)


def _validate_uniform_record_keys(primary: list, filename: str) -> list[str]:
    """Ensure array-record files have identical key sets for every dict record."""
    errors: list[str] = []
    dict_records = [(idx, row) for idx, row in enumerate(primary) if isinstance(row, dict)]
    if not dict_records:
        return errors

    expected_keys = set(dict_records[0][1].keys())
    for idx, row in dict_records[1:]:
        row_keys = set(row.keys())
        if row_keys != expected_keys:
            missing = sorted(expected_keys - row_keys)
            extra = sorted(row_keys - expected_keys)
            label = _record_label(row, idx)
            parts = []
            if missing:
                parts.append(f"missing keys: {missing}")
            if extra:
                parts.append(f"extra keys: {extra}")
            errors.append(
                f"{filename}: non-uniform record keys at {label} ({'; '.join(parts)})"
            )
    return errors


def _validate_rda_optimal_uls(data: dict, filename: str) -> list[str]:
    """RDA/UL-specific checks for null/status consistency and highest_ul integrity."""
    errors: list[str] = []
    primary = data.get("nutrient_recommendations", [])
    if not isinstance(primary, list):
        return [f"{filename}: nutrient_recommendations must be an array"]

    for idx, nutrient in enumerate(primary):
        if not isinstance(nutrient, dict):
            continue
        label = _record_label(nutrient, idx)
        brackets = nutrient.get("data", [])
        if not isinstance(brackets, list):
            errors.append(f"{filename}: {label} has non-list data field")
            continue

        numeric_uls: list[float] = []
        for bidx, bracket in enumerate(brackets):
            if not isinstance(bracket, dict):
                continue

            rda_val = bracket.get("rda_ai")
            ul_val = bracket.get("ul")
            rda_status = bracket.get("rda_ai_status")
            ul_status = bracket.get("ul_status")

            if isinstance(rda_val, str) and rda_val.strip().upper() == "ND":
                errors.append(f"{filename}: {label} data[{bidx}] has deprecated ND string in rda_ai")
            if isinstance(ul_val, str) and ul_val.strip().upper() == "ND":
                errors.append(f"{filename}: {label} data[{bidx}] has deprecated ND string in ul")

            if rda_val is None:
                if rda_status != "not_determined":
                    errors.append(
                        f"{filename}: {label} data[{bidx}] rda_ai is null but rda_ai_status is {rda_status!r}"
                    )
            elif isinstance(rda_val, (int, float)):
                if rda_status is not None:
                    errors.append(
                        f"{filename}: {label} data[{bidx}] rda_ai is numeric but rda_ai_status is {rda_status!r}"
                    )
            else:
                errors.append(
                    f"{filename}: {label} data[{bidx}] rda_ai has invalid type {type(rda_val).__name__}"
                )

            if ul_val is None:
                if ul_status != "not_determined":
                    errors.append(
                        f"{filename}: {label} data[{bidx}] ul is null but ul_status is {ul_status!r}"
                    )
            elif isinstance(ul_val, (int, float)):
                numeric_uls.append(float(ul_val))
                if ul_status is not None:
                    errors.append(
                        f"{filename}: {label} data[{bidx}] ul is numeric but ul_status is {ul_status!r}"
                    )
            else:
                errors.append(
                    f"{filename}: {label} data[{bidx}] ul has invalid type {type(ul_val).__name__}"
                )

        expected_highest = max(numeric_uls) if numeric_uls else None
        actual_highest = nutrient.get("highest_ul")
        if expected_highest is None:
            if actual_highest is not None:
                errors.append(
                    f"{filename}: {label} highest_ul={actual_highest} but all data[].ul are null"
                )
        else:
            if actual_highest is None:
                errors.append(
                    f"{filename}: {label} highest_ul is null but max data[].ul is {expected_highest}"
                )
            elif float(actual_highest) != float(expected_highest):
                errors.append(
                    f"{filename}: {label} highest_ul={actual_highest} does not match max data[].ul={expected_highest}"
                )

    return errors


# ---------------------------------------------------------------------------
# Per-file validation
# ---------------------------------------------------------------------------
def validate_file(path: Path) -> list[str]:
    """Validate a single database file. Return a list of error strings (empty = pass)."""
    errors: list[str] = []
    data = _load_json(path)
    if isinstance(data, str):
        errors.append(data)
        return errors
    if not isinstance(data, dict):
        errors.append("Top-level JSON must be an object")
        return errors

    if "database_info" in data:
        errors.append("Top-level deprecated key 'database_info' is not allowed")

    # -- _metadata block -------------------------------------------------
    meta = data.get("_metadata")
    if meta is None:
        errors.append("Missing '_metadata' key")
        return errors

    for field in ("description", "purpose", "schema_version"):
        if field not in meta:
            errors.append(f"_metadata missing required field '{field}'")

    sv = meta.get("schema_version")
    if sv is not None and sv != REQUIRED_SCHEMA_VERSION:
        errors.append(
            f"schema_version is '{sv}', expected '{REQUIRED_SCHEMA_VERSION}'"
        )

    last_updated = meta.get("last_updated")
    if last_updated is not None:
        if not ISO_DATE_RE.match(str(last_updated)):
            errors.append(f"last_updated '{last_updated}' is not a valid ISO date (YYYY-MM-DD)")
        else:
            try:
                datetime.strptime(str(last_updated), "%Y-%m-%d")
            except ValueError:
                errors.append(f"last_updated '{last_updated}' is not a real calendar date")
    else:
        errors.append("_metadata missing 'last_updated'")

    # -- total_entries vs actual count -----------------------------------
    total_declared = meta.get("total_entries")
    if total_declared is not None and isinstance(total_declared, int):
        primary = _find_primary_array(data)
        if primary is not None:
            actual = len(primary)
            if actual != total_declared:
                errors.append(
                    f"total_entries mismatch: declared {total_declared}, actual {actual}"
                )

    # -- Duplicate IDs within this file ----------------------------------
    primary = _find_primary_array(data)
    if primary is not None:
        ids = _collect_ids(primary)
        seen: set[str] = set()
        dupes: list[str] = []
        for id_val in ids:
            if id_val in seen:
                dupes.append(id_val)
            seen.add(id_val)
        if dupes:
            errors.append(f"Duplicate IDs: {', '.join(dupes)}")

        # Deprecated field checks and per-record severity normalization.
        for idx, record in enumerate(primary):
            if not isinstance(record, dict):
                continue
            rec_label = _record_label(record, idx)
            for field in DEPRECATED_FIELDS:
                if field in record:
                    errors.append(
                        f"{path.name}: record {rec_label} contains deprecated field '{field}'"
                    )

            sev = record.get("severity_level")
            if sev is not None and not isinstance(sev, str):
                errors.append(
                    f"{path.name}: record {rec_label} has non-string severity_level ({type(sev).__name__})"
                )
            elif isinstance(sev, str):
                sev_norm = sev.strip()
                if sev_norm.lower() in SEVERITY_LEVEL_VALUES and sev_norm != sev_norm.lower():
                    errors.append(
                        f"{path.name}: record {rec_label} severity_level must be lowercase (found {sev!r})"
                    )

        # Uniform key-set check for array records.
        errors.extend(_validate_uniform_record_keys(primary, path.name))

    # Recursive severity-level checks for nested records too.
    for node_path, node in _iter_nodes(data):
        if isinstance(node, dict) and "severity_level" in node:
            sev = node.get("severity_level")
            if isinstance(sev, str) and sev.strip().lower() in SEVERITY_LEVEL_VALUES and sev != sev.lower():
                errors.append(
                    f"{path.name}: {node_path}.severity_level must be lowercase (found {sev!r})"
                )

    # RDA-specific validation hooks.
    if path.name == "rda_optimal_uls.json":
        errors.extend(_validate_rda_optimal_uls(data, path.name))

    return errors


# ---------------------------------------------------------------------------
# Cross-file validations
# ---------------------------------------------------------------------------
def cross_validate(data_dir: Path) -> list[str]:
    """Run cross-file checks. Return list of error strings."""
    errors: list[str] = []

    banned_path = data_dir / "banned_recalled_ingredients.json"
    redirects_path = data_dir / "id_redirects.json"

    if not banned_path.exists() or not redirects_path.exists():
        if not banned_path.exists():
            errors.append(f"Cross-val skipped: {banned_path.name} not found")
        if not redirects_path.exists():
            errors.append(f"Cross-val skipped: {redirects_path.name} not found")
        return errors

    banned_data = _load_json(banned_path)
    redirects_data = _load_json(redirects_path)

    if isinstance(banned_data, str) or isinstance(redirects_data, str):
        errors.append("Cross-val skipped: could not parse banned or id_redirects file")
        return errors

    # Build set of canonical IDs in banned DB
    banned_ingredients = banned_data.get("ingredients", [])
    banned_ids: set[str] = {
        item["id"] for item in banned_ingredients if isinstance(item, dict) and "id" in item
    }

    # Collect all supersedes_ids declared in banned DB
    all_supersedes: set[str] = set()
    for item in banned_ingredients:
        if not isinstance(item, dict):
            continue
        sids = item.get("supersedes_ids")
        if isinstance(sids, list):
            all_supersedes.update(s for s in sids if isinstance(s, str))

    # Build redirects lookup
    redirects_list = redirects_data.get("redirects", [])
    redirect_deprecated: set[str] = set()
    redirect_canonical: set[str] = set()
    for r in redirects_list:
        if not isinstance(r, dict):
            continue
        dep = r.get("deprecated_id")
        can = r.get("canonical_id")
        if dep:
            redirect_deprecated.add(dep)
        if can:
            redirect_canonical.add(can)

    # 1) Every supersedes_id should appear as a deprecated_id in id_redirects
    missing_redirects = all_supersedes - redirect_deprecated
    for mid in sorted(missing_redirects):
        errors.append(
            f"supersedes_id '{mid}' in banned DB has no corresponding entry in id_redirects.json"
        )

    # 2) Every redirect's canonical_id should exist in banned DB
    orphaned = redirect_canonical - banned_ids
    for oid in sorted(orphaned):
        errors.append(
            f"id_redirects canonical_id '{oid}' not found in banned_recalled_ingredients.json"
        )

    return errors


# ---------------------------------------------------------------------------
# Summary report
# ---------------------------------------------------------------------------
def main() -> int:
    json_files = sorted(DATA_DIR.glob("*.json"))
    if not json_files:
        print(f"No .json files found in {DATA_DIR}")
        return 1

    all_passed = True
    file_results: list[tuple[str, list[str]]] = []

    # Per-file validation
    for path in json_files:
        errs = validate_file(path)
        file_results.append((path.name, errs))
        if errs:
            all_passed = False

    # Cross-file validation
    cross_errs = cross_validate(DATA_DIR)
    if cross_errs:
        all_passed = False

    # Print report
    width = 60
    print("=" * width)
    print("  DATABASE VALIDATION REPORT")
    print("=" * width)
    print()

    pass_count = 0
    fail_count = 0

    for name, errs in file_results:
        status = "PASS" if not errs else "FAIL"
        if errs:
            fail_count += 1
        else:
            pass_count += 1
        print(f"  [{status}]  {name}")
        for e in errs:
            print(f"         - {e}")

    print()
    print("-" * width)
    print("  CROSS-FILE VALIDATION")
    print("-" * width)
    if cross_errs:
        print("  [FAIL]")
        for e in cross_errs:
            print(f"         - {e}")
    else:
        print("  [PASS]  All cross-references valid")

    print()
    print("-" * width)
    total = pass_count + fail_count
    cross_status = "FAIL" if cross_errs else "PASS"
    print(f"  Files: {pass_count}/{total} passed  |  Cross-validation: {cross_status}")
    overall = "PASS" if all_passed else "FAIL"
    print(f"  Overall: {overall}")
    print("=" * width)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
