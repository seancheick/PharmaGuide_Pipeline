#!/usr/bin/env python3
"""
DSLD Pipeline Preflight Validator
==================================
Validates that all required files and directories exist before running the pipeline.

Usage:
    python preflight.py              # Run all checks
    python preflight.py --quick      # Quick check (critical files only)
    python preflight.py --verbose    # Verbose output with file sizes
    python preflight.py --json       # Output as JSON for CI integration

Exit codes:
    0 - All checks passed
    1 - Critical files missing (pipeline will fail)
    2 - Non-critical files missing (pipeline may have reduced functionality)

Author: PharmaGuide Team
Version: 1.0.0
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Tuple


# Path to scripts directory (where this file lives)
SCRIPTS_DIR = Path(__file__).parent.resolve()
DATA_DIR = SCRIPTS_DIR / "data"
CONFIG_DIR = SCRIPTS_DIR / "config"


# Critical data files - pipeline will fail without these
CRITICAL_DATA_FILES = [
    ("ingredient_quality_map.json", "Ingredient quality scoring database"),
    ("banned_recalled_ingredients.json", "Safety flags - banned substances"),
    ("harmful_additives.json", "Safety flags - harmful additives"),
    ("allergens.json", "Allergen detection database"),
    ("rda_optimal_uls.json", "RDA/UL dosage reference"),
]

# Important data files - pipeline works but functionality reduced
IMPORTANT_DATA_FILES = [
    ("standardized_botanicals.json", "Botanical standardization"),
    ("enhanced_delivery.json", "Delivery system scoring"),
    ("synergy_cluster.json", "Ingredient synergy detection"),
    ("top_manufacturers_data.json", "Brand trust scoring"),
    ("other_ingredients.json", "Excipient classification"),
    ("absorption_enhancers.json", "Absorption enhancer detection"),
    ("backed_clinical_studies.json", "Clinical evidence database"),
    ("proprietary_blends.json", "Proprietary blend detection"),
    ("cert_claim_rules.json", "Certification claim detection"),
    ("unit_conversions.json", "Unit conversion rules"),
    ("clinically_relevant_strains.json", "Clinical probiotic strain database"),
    ("clinical_risk_taxonomy.json", "Condition and medication-class enum taxonomy"),
    ("ingredient_interaction_rules.json", "Ingredient-level interaction alert rules"),
]

# Optional data files - nice to have
OPTIONAL_DATA_FILES = [
    ("botanical_ingredients.json", "Extended botanical data"),
    ("color_indicators.json", "Natural vs artificial colors"),
    ("ingredient_weights.json", "Ingredient importance weights"),
    ("functional_ingredient_groupings.json", "Functional groupings"),
    ("manufacturer_violations.json", "Manufacturer violation history"),
    ("banned_match_allowlist.json", "Banned-match false-positive controls"),
    ("id_redirects.json", "Canonical ID redirects"),
    ("ingredient_classification.json", "Ingredient taxonomy support"),
    ("manufacture_deduction_expl.json", "Manufacturer deduction explanation"),
    ("migration_report.json", "Normalization migration audit"),
    ("rda_therapeutic_dosing.json", "Therapeutic dosage references"),
    ("unit_mappings.json", "Unit alias mappings"),
    ("user_goals_to_clusters.json", "Goal-to-cluster mappings"),
]

# Required config files
CONFIG_FILES = [
    ("enrichment_config.json", "Enrichment stage configuration"),
    ("scoring_config.json", "Scoring stage configuration"),
    ("cleaning_config.json", "Cleaning stage configuration"),
    ("cleaning_config_seq_tmp.json", "Sequential cleaning config"),
]

# Required script files
SCRIPT_FILES = [
    ("clean_dsld_data.py", "Stage 1: Cleaning"),
    ("enrich_supplements_v3.py", "Stage 2: Enrichment"),
    ("score_supplements.py", "Stage 3: Scoring"),
    ("run_pipeline.py", "Pipeline orchestrator"),
    ("constants.py", "Constants and configuration"),
]


def check_file(path: Path) -> Tuple[bool, int]:
    """
    Check if file exists and return (exists, size_bytes).
    """
    if path.exists() and path.is_file():
        return True, path.stat().st_size
    return False, 0


def validate_json_file(path: Path) -> Tuple[bool, str]:
    """
    Validate that a JSON file is syntactically correct.
    Returns (valid, error_message).
    """
    if not path.exists():
        return False, "File not found"
    try:
        with open(path, 'r', encoding='utf-8') as f:
            json.load(f)
        return True, ""
    except json.JSONDecodeError as e:
        return False, f"JSON parse error: {e}"
    except Exception as e:
        return False, f"Read error: {e}"


DEPRECATED_FIELDS = {
    "risk_level",
    "synonyms",
    "canonical_name",
    "database_info",
    "violation_severity",
    "published_support",
}

# Database files expected to have _metadata wrapper with schema_version 5.x
SCHEMA_V5_DATABASES = [
    "absorption_enhancers.json",
    "allergens.json",
    "backed_clinical_studies.json",
    "banned_match_allowlist.json",
    "banned_recalled_ingredients.json",
    "botanical_ingredients.json",
    "cert_claim_rules.json",
    "clinically_relevant_strains.json",
    "clinical_risk_taxonomy.json",
    "color_indicators.json",
    "enhanced_delivery.json",
    "functional_ingredient_groupings.json",
    "harmful_additives.json",
    "id_redirects.json",
    "ingredient_classification.json",
    "ingredient_quality_map.json",
    "ingredient_interaction_rules.json",
    "ingredient_weights.json",
    "manufacture_deduction_expl.json",
    "manufacturer_violations.json",
    "migration_report.json",
    "other_ingredients.json",
    "proprietary_blends.json",
    "rda_optimal_uls.json",
    "rda_therapeutic_dosing.json",
    "standardized_botanicals.json",
    "synergy_cluster.json",
    "top_manufacturers_data.json",
    "unit_conversions.json",
    "unit_mappings.json",
    "user_goals_to_clusters.json",
]


def validate_iqm_br_collision(data_dir: Path = DATA_DIR) -> Dict:
    """
    Cross-DB safety check: verify no alias or standard_name that exists in
    IQM (scorable actives) also appears in the Banned/Recalled DB.

    A collision means a substance could be scored as beneficial AND flagged as
    banned simultaneously — the banned route must always win, and the presence
    of a collision indicates a data authoring error that must be fixed before
    the pipeline runs.

    Returns:
        Dict with 'collisions' list and 'ok' bool.
    """
    result = {"collisions": [], "ok": True}

    iqm_path = data_dir / "ingredient_quality_map.json"
    br_path = data_dir / "banned_recalled_ingredients.json"

    if not iqm_path.exists() or not br_path.exists():
        return result  # File-existence checks handled separately

    try:
        with open(iqm_path, "r", encoding="utf-8") as f:
            iqm_data = json.load(f)
        with open(br_path, "r", encoding="utf-8") as f:
            br_data = json.load(f)
    except Exception:
        return result  # JSON parse errors handled separately

    def _norm(s: str) -> str:
        return s.lower().strip()

    # Build term → (br_id, br_status) index from BR
    br_term_index: dict = {}
    for key, value in br_data.items():
        if key == "_metadata" or not isinstance(value, list):
            continue
        for entry in value:
            if not isinstance(entry, dict):
                continue
            br_id = entry.get("id", "")
            br_status = entry.get("status", "banned")
            sn = entry.get("standard_name", "")
            if sn:
                br_term_index.setdefault(_norm(sn), (br_id, br_status))
            for alias in entry.get("aliases", []) or []:
                if alias:
                    br_term_index.setdefault(_norm(alias), (br_id, br_status))

    if not br_term_index:
        return result

    # Severity levels that constitute a HARD block vs a warning
    HARD_BLOCK_STATUSES = {"banned", "recalled"}

    # IQM keys that are intentionally present in BOTH IQM and BR with high_risk/watchlist
    # status. These are real active identities that should still be recognized precisely,
    # while the BR layer adds the safety penalty/risk messaging.
    INTENTIONAL_DUAL_CLASSIFICATION = {
        "yohimbe",           # RISK_YOHIMBE high_risk — legal stimulant, well-characterized risk
        "kavalactones",      # RISK_KAVA high_risk — hepatotoxicity risk, legal in US
        "synephrine",        # RISK_BITTER_ORANGE high_risk — cardiovascular risk
        "garcinia_cambogia", # RISK_GARCINIA_CAMBOGIA high_risk — hepatotoxicity warning layer
        "7_keto_dhea",       # BANNED_7_KETO_DHEA high_risk — legal in US, banned in UK/CA/AU/NZ
        "cascara_sagrada",   # ADD_CASCARA_SAGRADA high_risk — FDA Category III, legal in supplements
    }

    # Walk IQM entries and check every standard_name + alias
    seen: set = set()  # de-duplicate (iqm_key, colliding_term_norm)
    for iqm_key, iqm_entry in iqm_data.items():
        if iqm_key.startswith("_") or not isinstance(iqm_entry, dict):
            continue
        sn = iqm_entry.get("standard_name", iqm_key)
        candidates = [sn, iqm_key]
        for form_name, form_data in (iqm_entry.get("forms", {}) or {}).items():
            candidates.append(form_name)
            for alias in (form_data.get("aliases", []) or []) if isinstance(form_data, dict) else []:
                candidates.append(alias)

        for candidate in candidates:
            if not candidate:
                continue
            norm_candidate = _norm(candidate)
            dedup_key = (iqm_key, norm_candidate)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            if norm_candidate in br_term_index:
                br_id, br_status = br_term_index[norm_candidate]
                is_critical = br_status in HARD_BLOCK_STATUSES
                is_intentional = (
                    iqm_key in INTENTIONAL_DUAL_CLASSIFICATION
                    and not is_critical
                )
                if is_intentional:
                    continue  # suppress — deliberate dual-classification, not an error
                result["collisions"].append({
                    "iqm_key": iqm_key,
                    "colliding_term": candidate,
                    "br_id": br_id,
                    "br_status": br_status,
                    "critical": is_critical,
                    "note": (
                        f"HARD BLOCK — term also in Banned/Recalled DB (status={br_status})"
                        if is_critical else
                        f"WARNING — term also in Banned/Recalled DB (status={br_status})"
                    )
                })
                if is_critical:
                    result["ok"] = False

    return result


def validate_database_schema(data_dir: Path = DATA_DIR) -> Dict:
    """
    Validate that JSON database files conform to v5.x schema conventions.

    Checks:
    - _metadata wrapper present with schema_version starting with '5.'
    - No deprecated fields (risk_level, synonyms, canonical_name, database_info, violation_severity, published_support)
    - Entity entries have standard_name where applicable

    Returns:
        Dict with 'passed', 'failed' lists and 'ok' bool.
    """
    results = {"passed": [], "failed": [], "ok": True}

    for filename in SCHEMA_V5_DATABASES:
        path = data_dir / filename
        if not path.exists():
            continue  # File existence is checked separately

        issues = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            issues.append("Could not parse JSON")
            results["failed"].append({"file": filename, "issues": issues})
            results["ok"] = False
            continue

        # Check _metadata wrapper
        metadata = data.get("_metadata")
        if not metadata:
            issues.append("Missing _metadata wrapper")
        else:
            sv = metadata.get("schema_version", "")
            if not str(sv).startswith("5."):
                issues.append(f"schema_version '{sv}' does not start with '5.'")

        # Check for deprecated fields at root level
        for dep in DEPRECATED_FIELDS:
            if dep in data:
                issues.append(f"Deprecated root field '{dep}' still present")

        # Check deprecated fields inside primary record arrays (same scope as validate_database.py).
        primary_key = None
        primary_array = None
        for key, value in data.items():
            if key == "_metadata":
                continue
            if isinstance(value, list):
                primary_key = key
                primary_array = value
                break

        if isinstance(primary_array, list):
            for idx, entry in enumerate(primary_array):
                if not isinstance(entry, dict):
                    continue
                for dep in DEPRECATED_FIELDS:
                    if dep in entry:
                        entry_id = entry.get("id", f"index {idx}")
                        issues.append(
                            f"Entry '{primary_key}[{entry_id}]' has deprecated field '{dep}'"
                        )

        if issues:
            results["failed"].append({"file": filename, "issues": issues})
            results["ok"] = False
        else:
            results["passed"].append(filename)

    return results


def run_preflight(verbose: bool = False, quick: bool = False) -> Dict:
    """
    Run preflight validation checks.

    Args:
        verbose: Include file sizes and extra info
        quick: Only check critical files

    Returns:
        Results dictionary with status and details
    """
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "scripts_dir": str(SCRIPTS_DIR),
        "critical": {"passed": [], "failed": []},
        "important": {"passed": [], "failed": []},
        "optional": {"passed": [], "failed": []},
        "configs": {"passed": [], "failed": []},
        "scripts": {"passed": [], "failed": []},
        "json_valid": {"passed": [], "failed": []},
        "summary": {
            "critical_ok": False,
            "all_ok": False,
            "exit_code": 0
        }
    }

    # Check critical data files
    for filename, description in CRITICAL_DATA_FILES:
        path = DATA_DIR / filename
        exists, size = check_file(path)
        entry = {
            "file": filename,
            "description": description,
            "path": str(path)
        }
        if verbose:
            entry["size_bytes"] = size

        if exists:
            results["critical"]["passed"].append(entry)
            # Validate JSON syntax
            valid, error = validate_json_file(path)
            if valid:
                results["json_valid"]["passed"].append(filename)
            else:
                results["json_valid"]["failed"].append({
                    "file": filename,
                    "error": error
                })
        else:
            results["critical"]["failed"].append(entry)

    if quick:
        # Quick mode: only check critical files
        results["summary"]["critical_ok"] = len(results["critical"]["failed"]) == 0
        results["summary"]["all_ok"] = results["summary"]["critical_ok"]
        results["summary"]["exit_code"] = 0 if results["summary"]["critical_ok"] else 1
        return results

    # Check important data files
    for filename, description in IMPORTANT_DATA_FILES:
        path = DATA_DIR / filename
        exists, size = check_file(path)
        entry = {
            "file": filename,
            "description": description,
            "path": str(path)
        }
        if verbose:
            entry["size_bytes"] = size

        if exists:
            results["important"]["passed"].append(entry)
            valid, error = validate_json_file(path)
            if valid:
                results["json_valid"]["passed"].append(filename)
            else:
                results["json_valid"]["failed"].append({
                    "file": filename,
                    "error": error
                })
        else:
            results["important"]["failed"].append(entry)

    # Check optional data files
    for filename, description in OPTIONAL_DATA_FILES:
        path = DATA_DIR / filename
        exists, size = check_file(path)
        entry = {
            "file": filename,
            "description": description,
            "path": str(path)
        }
        if verbose:
            entry["size_bytes"] = size

        if exists:
            results["optional"]["passed"].append(entry)
        else:
            results["optional"]["failed"].append(entry)

    # Check config files
    for filename, description in CONFIG_FILES:
        path = CONFIG_DIR / filename
        exists, size = check_file(path)
        entry = {
            "file": filename,
            "description": description,
            "path": str(path)
        }
        if verbose:
            entry["size_bytes"] = size

        if exists:
            results["configs"]["passed"].append(entry)
            valid, error = validate_json_file(path)
            if valid:
                results["json_valid"]["passed"].append(filename)
            else:
                results["json_valid"]["failed"].append({
                    "file": filename,
                    "error": error
                })
        else:
            results["configs"]["failed"].append(entry)

    # Check script files
    for filename, description in SCRIPT_FILES:
        path = SCRIPTS_DIR / filename
        exists, size = check_file(path)
        entry = {
            "file": filename,
            "description": description,
            "path": str(path)
        }
        if verbose:
            entry["size_bytes"] = size

        if exists:
            results["scripts"]["passed"].append(entry)
        else:
            results["scripts"]["failed"].append(entry)

    # Validate database schemas (v5.x compliance)
    schema_results = validate_database_schema()
    # Keep both keys for backward compatibility with existing consumers.
    results["schema_v5"] = schema_results
    results["schema_v4"] = schema_results

    # Safety cross-DB check: IQM ↔ Banned/Recalled collision guard
    collision_results = validate_iqm_br_collision()
    results["iqm_br_collision"] = collision_results

    # Compute summary
    critical_ok = len(results["critical"]["failed"]) == 0
    json_ok = len(results["json_valid"]["failed"]) == 0
    configs_ok = len(results["configs"]["failed"]) == 0
    scripts_ok = len(results["scripts"]["failed"]) == 0
    schema_ok = schema_results["ok"]
    collision_ok = collision_results["ok"]

    all_ok = critical_ok and json_ok and configs_ok and scripts_ok and schema_ok and collision_ok

    # Exit code: 0=ok, 1=critical failure, 2=non-critical issues
    # NOTE: IQM↔BR collisions are exit 2 (not exit 1) because banned routing wins
    # at priority 1 in _fast_exact_lookup — no functional incorrect routing occurs.
    # Collisions represent data authoring issues that need human review, not
    # pipeline-breaking failures.
    if not critical_ok or not json_ok:
        exit_code = 1
    elif not collision_ok or len(results["important"]["failed"]) > 0:
        exit_code = 2
    else:
        exit_code = 0

    results["summary"] = {
        "critical_ok": critical_ok,
        "json_valid": json_ok,
        "configs_ok": configs_ok,
        "scripts_ok": scripts_ok,
        "schema_v5_ok": schema_ok,
        "schema_v4_ok": schema_ok,
        "iqm_br_collision_ok": collision_ok,
        "all_ok": all_ok,
        "exit_code": exit_code,
        "counts": {
            "critical_passed": len(results["critical"]["passed"]),
            "critical_failed": len(results["critical"]["failed"]),
            "important_passed": len(results["important"]["passed"]),
            "important_failed": len(results["important"]["failed"]),
            "optional_passed": len(results["optional"]["passed"]),
            "optional_failed": len(results["optional"]["failed"]),
        }
    }

    return results


def print_results(results: Dict, verbose: bool = False):
    """Print human-readable results to stdout."""
    print("=" * 60)
    print("DSLD PIPELINE PREFLIGHT CHECK")
    print("=" * 60)
    print(f"Scripts directory: {results['scripts_dir']}")
    print(f"Timestamp: {results['timestamp']}")
    print()

    # Critical files
    print("CRITICAL DATA FILES:")
    for entry in results["critical"]["passed"]:
        size_info = f" ({entry['size_bytes']:,} bytes)" if verbose and 'size_bytes' in entry else ""
        print(f"  [OK] {entry['file']}{size_info}")
    for entry in results["critical"]["failed"]:
        print(f"  [MISSING] {entry['file']} - {entry['description']}")
    print()

    # Important files (only show failures in non-verbose)
    if results["important"]["failed"] or verbose:
        print("IMPORTANT DATA FILES:")
        if verbose:
            for entry in results["important"]["passed"]:
                size_info = f" ({entry['size_bytes']:,} bytes)" if 'size_bytes' in entry else ""
                print(f"  [OK] {entry['file']}{size_info}")
        for entry in results["important"]["failed"]:
            print(f"  [MISSING] {entry['file']} - {entry['description']}")
        print()

    # JSON validation errors
    if results["json_valid"]["failed"]:
        print("JSON VALIDATION ERRORS:")
        for entry in results["json_valid"]["failed"]:
            print(f"  [ERROR] {entry['file']}: {entry['error']}")
        print()

    # IQM ↔ BR collision guard
    collision = results.get("iqm_br_collision", {})
    all_collisions = collision.get("collisions", [])
    critical_collisions = [c for c in all_collisions if c.get("critical")]
    warning_collisions = [c for c in all_collisions if not c.get("critical")]
    if all_collisions or verbose:
        print("IQM \u2194 BANNED/RECALLED COLLISION CHECK:")
        if not all_collisions:
            if verbose:
                print("  [OK] No IQM \u2194 Banned/Recalled term collisions found")
        else:
            for c in critical_collisions:
                print(f"  [CRITICAL] IQM '{c['iqm_key']}' / term '{c['colliding_term']}' "
                      f"-> BR id={c.get('br_id','')} status={c.get('br_status','')}")
            for c in warning_collisions:
                print(f"  [WARN]     IQM '{c['iqm_key']}' / term '{c['colliding_term']}' "
                      f"-> BR id={c.get('br_id','')} status={c.get('br_status','')}")
            if critical_collisions:
                print(f"  {len(critical_collisions)} CRITICAL collision(s) must be resolved before pipeline runs.")
            if warning_collisions:
                print(f"  {len(warning_collisions)} warning collision(s) — review recommended.")
        print()

    # Schema v5 validation
    schema = results.get("schema_v5", results.get("schema_v4", {}))
    if schema.get("failed") or verbose:
        print("SCHEMA v5 VALIDATION:")
        if verbose:
            for filename in schema.get("passed", []):
                print(f"  [OK] {filename}")
        for entry in schema.get("failed", []):
            print(f"  [FAIL] {entry['file']}:")
            for issue in entry["issues"]:
                print(f"         - {issue}")
        print()

    # Config files
    if results["configs"]["failed"] or verbose:
        print("CONFIG FILES:")
        if verbose:
            for entry in results["configs"]["passed"]:
                print(f"  [OK] {entry['file']}")
        for entry in results["configs"]["failed"]:
            print(f"  [MISSING] {entry['file']} - {entry['description']}")
        print()

    # Script files
    if results["scripts"]["failed"] or verbose:
        print("SCRIPT FILES:")
        if verbose:
            for entry in results["scripts"]["passed"]:
                print(f"  [OK] {entry['file']}")
        for entry in results["scripts"]["failed"]:
            print(f"  [MISSING] {entry['file']} - {entry['description']}")
        print()

    # Summary
    summary = results["summary"]
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    counts = summary.get("counts", {})
    print(f"Critical files: {counts.get('critical_passed', 0)}/{counts.get('critical_passed', 0) + counts.get('critical_failed', 0)}")
    print(f"Important files: {counts.get('important_passed', 0)}/{counts.get('important_passed', 0) + counts.get('important_failed', 0)}")
    print(f"Optional files: {counts.get('optional_passed', 0)}/{counts.get('optional_passed', 0) + counts.get('optional_failed', 0)}")
    print()

    if summary["all_ok"]:
        print("STATUS: ALL CHECKS PASSED")
    elif summary["critical_ok"]:
        print("STATUS: CRITICAL CHECKS PASSED (some non-critical issues)")
    else:
        print("STATUS: CRITICAL CHECKS FAILED - Pipeline will not run correctly")

    print(f"Exit code: {summary['exit_code']}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description='DSLD Pipeline Preflight Validator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit codes:
    0 - All checks passed
    1 - Critical files missing (pipeline will fail)
    2 - Non-critical files missing (pipeline may have reduced functionality)
        """
    )
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Quick check (critical files only)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output with file sizes'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON for CI integration'
    )

    args = parser.parse_args()

    results = run_preflight(verbose=args.verbose, quick=args.quick)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_results(results, verbose=args.verbose)

    sys.exit(results["summary"]["exit_code"])


if __name__ == "__main__":
    main()
