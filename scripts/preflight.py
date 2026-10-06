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
from typing import Dict, Tuple

from reference_data_schema import validate_reference_schema_version


# Path to scripts directory (where this file lives)
SCRIPTS_DIR = Path(__file__).parent.resolve()
DATA_DIR = SCRIPTS_DIR / "data"
CONFIG_DIR = SCRIPTS_DIR / "config"
V4_CONFIG_DIR = SCRIPTS_DIR / "scoring_v4" / "config"


# Critical data files - pipeline will fail without these
CRITICAL_DATA_FILES = [
    ("ingredient_quality_map.json", "Ingredient quality scoring database"),
    ("banned_recalled_ingredients.json", "Safety flags - banned substances"),
    ("harmful_additives.json", "Safety flags - harmful additives"),
    ("allergens.json", "Allergen detection database"),
    ("rda_optimal_uls.json", "RDA/UL dosage reference"),
    ("timing_rules.json", "Clinically reviewed timing guidance"),
    ("medication_depletions.json", "Clinically reviewed medication-nutrient guidance"),
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
    ("medication_profile_gate_rules.json", "Standalone medication profile-gate rules"),
]

# Optional data files - nice to have
OPTIONAL_DATA_FILES = [
    ("botanical_ingredients.json", "Extended botanical data"),
    ("color_indicators.json", "Natural vs artificial colors"),
    ("functional_ingredient_groupings.json", "Functional groupings"),
    ("manufacturer_violations.json", "Manufacturer violation history"),
    ("banned_match_allowlist.json", "Banned-match false-positive controls"),
    ("id_redirects.json", "Canonical ID redirects"),
    ("ingredient_classification.json", "Ingredient taxonomy support"),
    ("manufacture_deduction_expl.json", "Manufacturer deduction explanation"),
    ("migration_report.json", "Normalization migration audit"),
    ("rda_therapeutic_dosing.json", "Therapeutic dosage references"),
    ("user_goals_to_clusters.json", "Goal-to-cluster mappings"),
]

# Required config files
CONFIG_FILES = [
    ("enrichment_config.json", "Enrichment stage configuration"),
    ("quality_score.json", "V4 scoring configuration"),
    ("cleaning_config.json", "Cleaning stage configuration"),
]

# Required script files
SCRIPT_FILES = [
    ("clean_dsld_data.py", "Stage 1: Cleaning"),
    ("enrich_supplements_v3.py", "Stage 2: Enrichment"),
    ("score_products_v4.py", "Stage 3: v4 scored-artifact production"),
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

# Reference databases checked for metadata and deprecated root fields.
REFERENCE_DATABASES = [
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
    "manufacture_deduction_expl.json",
    "manufacturer_violations.json",
    "medication_profile_gate_rules.json",
    "migration_report.json",
    "other_ingredients.json",
    "proprietary_blends.json",
    "rda_optimal_uls.json",
    "rda_therapeutic_dosing.json",
    "standardized_botanicals.json",
    "synergy_cluster.json",
    "top_manufacturers_data.json",
    "unit_conversions.json",
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
        "aloe_ferox",        # RISK_ALOE_LATEX high_risk — same 2002 FDA OTC rule as cascara; EFSA: genotoxic HADs
        "senna",             # WATCH_SENNA watchlist — FDA OTC category III; EU Union scrutiny (Part C)
        "frangula",          # WATCH_FRANGULA watchlist — EU Union scrutiny (Part C); EFSA 2024 safety not established
        "chinese_rhubarb",   # WATCH_RHUBARB_ROOT watchlist — EU Union scrutiny (Part C); EFSA 2024 safety not established
        "dhea",              # BANNED_DHEA high_risk — legal in US (DSHEA), Rx-only abroad (CA/UK/AU); WADA-banned
        "vinpocetine",       # NOOTROPIC_VINPOCETINE high_risk — FDA legal conclusion tentative; reproductive-risk CAUTION
        "withaferin_a",      # WATCH_WITHAFERIN_A watchlist — standardization marker; dose-dependent caution layer
        "miroestrol",        # RISK_MIROESTROL high_risk — standardization marker; estrogenic/endocrine caution layer
        "citrus_bioflavonoids",  # RISK_BITTER_ORANGE high_risk — "bitter orange citrus bioflavonoids" (Life Extension Mix)
        "germanium",         # RISK_GERMANIUM high_risk — Ge-132 sold as a supplement; renal toxicity warning layer
        "silver",            # ADD_COLLOIDAL_SILVER high_risk — colloidal silver; argyria warning layer
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
    Validate that JSON database files conform to shared schema conventions.

    Checks:
    - _metadata wrapper present with a version in the file-owned namespace
    - No deprecated fields (risk_level, synonyms, canonical_name, database_info, violation_severity, published_support)
    - Entity entries have standard_name where applicable

    Returns:
        Dict with 'passed', 'failed' lists and 'ok' bool.
    """
    results = {"passed": [], "failed": [], "ok": True}

    for filename in REFERENCE_DATABASES:
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
            schema_issue = validate_reference_schema_version(filename, sv)
            if schema_issue:
                issues.append(schema_issue)

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
                    # The condition taxonomy owns aliases as synonyms; the
                    # ingredient/root deprecation contract still applies.
                    if dep == 'synonyms' and filename == 'clinical_risk_taxonomy.json' and primary_key == 'conditions':
                        continue
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
        # Quick mode still validates critical JSON content; existence alone is
        # not sufficient for a clinical-data preflight.
        critical_ok = len(results["critical"]["failed"]) == 0
        json_ok = len(results["json_valid"]["failed"]) == 0
        results["summary"].update({
            "critical_ok": critical_ok,
            "json_valid": json_ok,
            "all_ok": critical_ok and json_ok,
            "exit_code": 0 if critical_ok and json_ok else 1,
        })
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
        path = (
            V4_CONFIG_DIR / filename
            if filename == "quality_score.json"
            else CONFIG_DIR / filename
        )
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
    if not critical_ok or not json_ok or not configs_ok or not scripts_ok or not schema_ok:
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


def _digest(value):
    import hashlib
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _atomic_report(path, value):
    import os
    import tempfile
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f'.{path.name}.')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _preparation_inputs(repo_root, raw_root, *, operational_paths=()):
    """Hash a complete path inventory; keep only one raw label in memory."""
    import hashlib
    from batch_processor import BatchProcessor
    validator = object.__new__(BatchProcessor)
    validator.config = {'validation': {'check_input_integrity': True}}
    files, errors, identities = {}, [], {}
    operational_paths = {Path(path).resolve() for path in operational_paths}
    def record(path, key):
        try:
            with path.open('rb') as stream:
                files[key] = hashlib.file_digest(stream, 'sha256').hexdigest()
        except OSError as exc:
            errors.append(f'{key}: {exc}')
    import os
    import subprocess
    def discover(root, fallback, *, flutter=False):
        # Git owns committed source/fixture discovery across all extensions and
        # directories. Operational reports that are not tracked stay outside it.
        inventory = subprocess.run(['git', '-C', str(root), 'ls-files', '-z',
                                    '--cached', '--others', '--exclude-standard'],
                                   capture_output=True, check=False)
        if inventory.returncode == 0:
            relative_paths = {Path(os.fsdecode(name)) for name in inventory.stdout.split(b'\0') if name}
        else:
            relative_paths = {path.relative_to(root) for directory in fallback
                              for path in (root / directory).rglob('*') if path.is_file()
                              and not any(part in {'reports', '.cache', '__pycache__', '.pytest_cache'}
                                          for part in path.relative_to(root).parts)}
            relative_paths |= {path.relative_to(root) for path in root.glob('*') if path.is_file()
                               and (path.suffix in {'.sh', '.ini', '.toml'} or path.name in {'.python-version', 'requirements.txt'})}
        # These existing input owners intentionally live outside Git inventory.
        relative_paths |= {path.relative_to(root) for path in (root / 'manual_labels').rglob('*') if path.is_file()}
        relative_paths |= {Path(name) for name in ('.env', 'scripts/.env') if (root / name).is_file()}
        if not flutter:
            # This ignored FDA bulk map is an existing source-test dependency,
            # distinct from volatile API transport caches in .cache.
            relative_paths.add(Path('scripts/data/fda_unii_cache.json'))
        for relative in sorted(relative_paths):
            parts = relative.parts
            generated = (parts[:2] in {('scripts', 'products'), ('scripts', 'dist'), ('scripts', 'final_db_output')}
                         or (flutter and parts[:2] == ('assets', 'db'))
                         or any(part in {'.git', '.cache', '__pycache__', '.pytest_cache', 'node_modules', 'build', '.dart_tool'} for part in parts))
            operational = (relative.name in {'LEDGER.md', 'CURRENT_HANDOFF.md', '.DS_Store'}
                           or relative.as_posix() == 'docs/plans/PHARMAGUIDE_MASTER_COMPLETION_PLAN.md')
            if generated or operational:
                continue
            path = root / relative
            if path.resolve() in operational_paths:
                continue
            key = ('flutter/' if flutter else 'repo/') + relative.as_posix()
            if not path.is_file():
                # Preserved tracked deletions participate without declaring an
                # unrelated missing source file to be a required-input defect.
                files[key] = 'MISSING'
            else:
                record(path, key)
    discover(repo_root, ('scripts', '.claude/rules', '.github', 'manual_labels', 'docs'))
    flutter = Path(os.environ.get('FLUTTER_REPO', '/Users/seancheick/PharmaGuide ai'))
    if flutter.is_dir():
        discover(flutter, ('lib', 'test', 'supabase', 'assets/data'), flutter=True)
    paths = sorted(raw_root.rglob('*.json')) if raw_root.is_dir() else []
    if not paths:
        errors.append(f'No raw JSON labels found under {raw_root}')
    for path in paths:
        key = 'raw/' + str(path.relative_to(raw_root))
        record(path, key)
        valid, issue = validator.validate_input_file(path)
        if not valid:
            errors.append(f'{key}: {issue}')
            continue
        try:
            payload = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(payload, dict):
                errors.append(f'{key}: raw label must be a JSON object')
                continue
            identity = payload.get('id')
            if isinstance(identity, bool) or not str(identity).isdigit() or int(identity) <= 0:
                errors.append(f'{key}: missing or invalid product identity {identity!r}')
                continue
            identity = str(int(identity))
            if path.stem.isdigit() and str(int(path.stem)) != identity:
                errors.append(f'{key}: filename identity does not match label id {identity}')
            if identity in identities:
                errors.append(f'Duplicate raw identity {identity}: {identities[identity]}, {key}')
            else:
                identities[identity] = key
        except (OSError, ValueError, TypeError) as exc:
            errors.append(f'{key}: {exc}')
    return {'files': files, 'raw_count': len(paths), 'errors': errors}


def _preparation_runtime():
    """Bind effective environment without persisting credentials."""
    import os
    import platform
    import importlib.metadata
    import hashlib
    import shutil
    executables = {}
    for name, filename in [('python', sys.executable), ('bash', shutil.which('bash')), ('node', shutil.which('node'))]:
        if filename:
            path = Path(filename).resolve()
            with path.open('rb') as stream:
                executables[name] = {'path': str(path), 'sha256': hashlib.file_digest(stream, 'sha256').hexdigest()}
        else:
            executables[name] = None
    packages = sorted((d.metadata['Name'], d.version) for d in importlib.metadata.distributions()
                      if d.metadata.get('Name'))
    # Report paths and lock bookkeeping change between runs without changing
    # test semantics. Every other variable participates, including opt-ins,
    # config locations and secrets (hash only).
    ignored = {'PG_PREPARATION_REPORT', 'PG_PREPARATION_MODE', 'PG_TEST_LOCK_HELD',
               'PG_TEST_CONCURRENT_RUNS', 'PG_TEST_LOCK_FDS', 'SHLVL', '_', 'PWD', 'OLDPWD'}
    environment = {key: _digest(value) for key, value in os.environ.items() if key not in ignored}
    return {'python': str(Path(sys.executable).resolve()), 'version': sys.version,
            'platform': platform.platform(), 'executables': executables, 'freshness_date': datetime.now(timezone.utc).date().isoformat(), 'packages': packages, 'environment': environment}


def _valid_test_evidence(evidence, *, inventory=False):
    """Validate complete collected coverage and all setup/call/teardown outcomes."""
    if not isinstance(evidence, dict) or evidence.get('completed') is not True:
        return False
    nodes = evidence.get('nodes')
    if not isinstance(nodes, list) or not nodes or evidence.get('collection_errors') or evidence.get('collection_skips'):
        return False
    selection = evidence.get('selection')
    if not isinstance(selection, dict) or selection.get('args') != ['scripts/tests']:
        return False
    if any(selection.get(key) for key in ('keyword', 'markexpr', 'deselect', 'ignore', 'ignore_glob')):
        return False
    identifiers = [node.get('nodeid') for node in nodes if isinstance(node, dict)]
    if (len(identifiers) != len(nodes) or not all(isinstance(identifier, str) and identifier for identifier in identifiers)
            or len(set(identifiers)) != len(nodes)):
        return False
    if any(node.get('phase') not in ('source', 'artifact', 'external')
           or not isinstance(node.get('reason'), str) or not node['reason'] for node in nodes):
        return False
    if inventory:
        return evidence.get('exit_code') == 0
    expected = {node['nodeid'] for node in nodes if node['phase'] == 'source'}
    outcomes = evidence.get('outcomes', {})
    if not isinstance(outcomes, dict) or not expected or set(outcomes) != expected or evidence.get('exit_code') != 0:
        return False
    for nodeid, stages in outcomes.items():
        if (not isinstance(stages, list) or not all(isinstance(row, dict) and
                isinstance(row.get('when'), str) and isinstance(row.get('outcome'), str) for row in stages)):
            return False
        actual = sorted((row.get('when'), row.get('outcome')) for row in stages)
        if actual == [('call', 'passed'), ('setup', 'passed'), ('teardown', 'passed')]:
            continue
        # Existing metadata exceptions have bespoke owner assertions; they are
        # source-grounded coverage policy, not missing corpus/external skips.
        from test_profiles import CI_SKIP_ALLOWED_REASONS
        import re
        filename = Path(nodeid.split('::')[0]).name
        skipped = [row for row in stages if row.get('outcome') == 'skipped']
        allowed = CI_SKIP_ALLOWED_REASONS.get(filename, ()) if filename == 'test_data_file_metadata_contract.py' else ()
        reason = skipped[0].get('reason', '') if len(skipped) == 1 else ''
        reason = reason.removeprefix('Skipped: ') if isinstance(reason, str) else ''
        if (actual != [('call', 'skipped'), ('setup', 'passed'), ('teardown', 'passed')]
                or not any(re.fullmatch(pattern, reason) for pattern in allowed)):
            return False
    return True


def _same_preparation_inventory(collected, executed):
    return ({row['nodeid']: row for row in collected.get('nodes', [])}
            == {row['nodeid']: row for row in executed.get('nodes', [])})


def _valid_preparation_check(check, specification):
    if not isinstance(check, dict) or check.get('status') != 'passed' or check.get('exit_code') != 0:
        return False
    if check.get('command') != specification['command'] or not check.get('completed'):
        return False
    import math
    if (not isinstance(check.get('duration_seconds'), (int, float))
            or isinstance(check['duration_seconds'], bool) or not math.isfinite(check['duration_seconds'])
            or check['duration_seconds'] < 0):
        return False
    if not isinstance(check.get('stdout'), str) or not isinstance(check.get('stderr'), str):
        return False
    payload = {key: value for key, value in check.items() if key not in {'integrity', 'reused'}}
    if check.get('integrity') != _digest(payload):
        return False
    if specification.get('evidence') == 'pytest':
        return _valid_test_evidence(check.get('evidence'), inventory=specification.get('inventory', False))
    if specification.get('evidence') == 'references':
        try:
            payload = json.loads(check.get('stdout', ''))
            return (payload['summary']['all_ok'] is True and payload['summary']['exit_code'] == 0
                    and all(not payload[key]['failed'] for key in ('critical', 'configs', 'scripts', 'json_valid')))
        except (KeyError, TypeError, ValueError):
            return False
    if specification.get('evidence') == 'canaries':
        import re
        match = re.search(r'Checked: (\d+)  Failed: (\d+)  Total: (\d+)', check.get('stdout', ''))
        observed = re.findall(r'^\[\s*(\d+)\] UNCHANGED$', check.get('stdout', ''), re.MULTILINE)
        return bool(match and int(match[1]) > 0 and int(match[2]) == 0 and int(match[1]) == int(match[3])
                    and len(observed) == int(match[1]) and len(set(observed)) == len(observed)
                    and set(observed) == set(specification.get('identifiers', observed)))
    return isinstance(check.get('stdout'), str) and isinstance(check.get('stderr'), str)


def _preparation_canary_identifiers(repo_root):
    try:
        manifest = json.loads((repo_root / 'scripts/tests/fixtures/contract_snapshots/_manifest.json').read_text(encoding='utf-8'))
        return [str(product['dsld_id']) for product in manifest['products']]
    except (OSError, ValueError, KeyError, TypeError):
        return []


def run_preparation(repo_root, raw_root, *, checks=None, runner=None, report_path=None):
    """Aggregate read-only checks. Readiness permits regeneration, never publication.

    CLI callers use the pinned test runner and its suite lock. Injectable checks
    and runner are the orchestration test seam, not a receipt-import API.
    """
    import os
    import subprocess
    import time
    import tempfile
    from test_lock import inherited_lock_fds
    from pipeline_freshness import STAGES, RERUN_STAGES, stage_freshness_issues
    repo_root, raw_root = Path(repo_root).resolve(), Path(raw_root).resolve()
    runner = runner or subprocess.run
    lock_fds = inherited_lock_fds()
    operational_paths = [Path(report_path), Path(report_path).with_suffix('.pytest.json')] if report_path else []
    before = _preparation_inputs(repo_root, raw_root, operational_paths=operational_paths)
    runtime = _preparation_runtime()
    fingerprint = _digest({'inputs': before, 'runtime': runtime, 'raw_root': str(raw_root)})
    previous = {}
    if report_path and Path(report_path).is_file():
        try:
            previous = json.loads(Path(report_path).read_text(encoding='utf-8'))
        except (OSError, ValueError):
            pass
    if not isinstance(previous, dict):
        previous = {}
    result = {'timestamp': datetime.now(timezone.utc).isoformat(), 'fingerprint': fingerprint,
              'runtime': runtime, 'inputs': before, 'checks': [], 'ready': False,
              'publication_ready': False, 'completed': False}
    result['checks'].append({'name': 'raw_inputs', 'status': 'failed' if before['errors'] else 'passed',
                             'issues': before['errors']})
    try:
        issues = stage_freshness_issues(repo_root)
        earliest = next((s for s in STAGES if any(i.startswith(s + ': ') for i in issues)), None)
        # The existing freshness owner defines every JSON/JSONL output shape.
        # Missing stages need regeneration even when no stale manifest exists.
        products = repo_root / 'scripts/products'
        missing = [stage for stage, spec in STAGES.items()
                   if not any(path.is_file() and not path.name.startswith('.')
                              for pattern in spec['outputs'] for path in products.glob(pattern))]
        earliest = next((stage for stage in STAGES if stage in missing or
                         any(issue.startswith(stage + ': ') for issue in issues)), None)
        result['regeneration'] = {'issues': issues, 'missing_stages': missing, 'earliest_stage': earliest,
                                  'stages': RERUN_STAGES.get(earliest),
                                  'basis': 'Existing stage code/reference fingerprints and missing output patterns',
                                  'limits': ['Raw-to-Clean provenance is not established by these manifests; raw dataset changes require Clean unless existing evidence proves reuse']}
    except Exception as exc:
        result['checks'].append({'name': 'stage_freshness', 'status': 'failed', 'issues': [str(exc)]})
    with tempfile.TemporaryDirectory(prefix='pg-preparation-') as temporary:
        evidence_path = (Path(report_path).with_suffix('.pytest.json') if report_path
                         else Path(temporary) / 'pytest.json')
        if report_path:
            result['evidence_path'] = str(evidence_path)
            _atomic_report(report_path, result)
        if checks is None:
            checks = [
                {'name': 'references', 'command': [sys.executable, 'scripts/preflight.py', '--json'], 'evidence': 'references'},
                {'name': 'ownership_matrix', 'command': [sys.executable, 'scripts/audit_source_of_truth_contract.py', 'matrix', '--strict-release']},
                {'name': 'fda_freshness', 'command': [sys.executable, 'scripts/api_audit/fda_manufacturer_violations_sync.py', '--check']},
                {'name': 'raw_canaries', 'command': [sys.executable, 'scripts/tests/freeze_contract_snapshots.py',
                    '--check', '--raw-root', str(raw_root)], 'requires': ['raw_inputs', 'references'], 'evidence': 'canaries',
                    'identifiers': _preparation_canary_identifiers(repo_root)},
                {'name': 'pytest_inventory', 'command': ['bash', 'scripts/test.sh', 'preparation', '--collect-only'],
                    'evidence': 'pytest', 'inventory': True, 'reuse': False},
                {'name': 'source_tests', 'command': ['bash', 'scripts/test.sh', 'preparation'],
                    'requires': ['pytest_inventory'], 'evidence': 'pytest'},
            ]
            # The release runner owns these commands. Inventory mode never
            # invokes the gates, live identifiers, OCR or remote writes.
            try:
                gates = runner(['bash', 'scripts/test.sh', 'preparation-gates'], cwd=repo_root,
                               capture_output=True, text=True, encoding='utf-8', check=False, pass_fds=lock_fds)
                if gates.returncode:
                    raise ValueError(gates.stderr)
                inventory = [json.loads(line) for line in gates.stdout.splitlines() if line.strip()]
                if not inventory or any(g.get('phase') not in {'source', 'artifact', 'live'} for g in inventory):
                    raise ValueError('Incomplete release-gate inventory')
                result['post_run_gates'] = [g for g in inventory if g['phase'] == 'artifact']
                result['live_verification'] = [g for g in inventory if g['phase'] == 'live']
                checks += [{'name': g['phase'] + '_gate_' + str(i), 'command': g['command'],
                            'reuse': g['phase'] != 'live'}
                           for i, g in enumerate(inventory) if g['phase'] in {'source', 'live'}]
            except Exception as exc:
                result['checks'].append({'name': 'release_gate_inventory', 'status': 'failed', 'issues': [str(exc)]})
        prior_checks = previous.get('checks', [])
        if not isinstance(prior_checks, list):
            prior_checks = []
        prior = {check.get('name'): check for check in prior_checks if isinstance(check, dict) and isinstance(check.get('name'), str)}
        previous_payload = {k: v for k, v in previous.items() if k != 'integrity'}
        reusable = (previous.get('completed') is True and previous.get('fingerprint') == fingerprint
                    and previous.get('integrity') == _digest(previous_payload)
                    and len(prior) == len(prior_checks)
                    and prior.get('inputs_stable', {}).get('status') == 'passed')
        for specification in checks:
            name = specification['name']
            states = {check['name']: check['status'] for check in result['checks']}
            blocked = [dep for dep in specification.get('requires', []) if states.get(dep) != 'passed']
            if report_path:
                _atomic_report(report_path, result)
            if blocked:
                result['checks'].append({'name': name, 'status': 'blocked', 'prerequisites': blocked})
                continue
            if reusable and specification.get('reuse', True) and _valid_preparation_check(prior.get(name), specification):
                check = dict(prior[name], reused=True)
            else:
                evidence_path.unlink(missing_ok=True)
                started = time.monotonic()
                environment = dict(os.environ, PG_PREPARATION_REPORT=str(evidence_path),
                    PG_PREPARATION_MODE='inventory' if specification.get('inventory') else 'source')
                check = {'name': name, 'command': specification['command'], 'completed': False}
                try:
                    process = runner(specification['command'], cwd=repo_root, env=environment,
                                     capture_output=True, text=True, encoding='utf-8', check=False, pass_fds=lock_fds)
                    check.update(exit_code=process.returncode, stdout=process.stdout, stderr=process.stderr,
                                 completed=True, status='passed' if process.returncode == 0 else 'failed')
                    if specification.get('evidence') == 'pytest':
                        check['evidence'] = json.loads(evidence_path.read_text(encoding='utf-8')) if evidence_path.exists() else None
                except Exception as exc:
                    check.update(exit_code=None, stdout='', stderr=str(exc), status='failed')
                check['duration_seconds'] = round(time.monotonic() - started, 3)
                check['integrity'] = _digest(check)
                if not _valid_preparation_check(check, specification):
                    check['status'] = 'failed'
                    check['integrity'] = _digest({k: v for k, v in check.items() if k != 'integrity'})
            if name == 'raw_canaries' and check['status'] == 'failed' and 'DRIFT' in check.get('stdout', ''):
                check['category'] = 'expectation_drift_requires_source_review'
                check['integrity'] = _digest({k: v for k, v in check.items() if k not in {'integrity', 'reused'}})
            result['checks'].append(check)
            if report_path:
                _atomic_report(report_path, result)
        inventories = [c.get('evidence') for c in result['checks'] if c['name'] == 'pytest_inventory' and c['status'] == 'passed']
        executed = [c.get('evidence') for c in result['checks'] if c['name'] == 'source_tests' and c['status'] == 'passed']
        if inventories and executed and isinstance(inventories[0], dict) and isinstance(executed[0], dict):
            if not _same_preparation_inventory(inventories[0], executed[0]):
                result['checks'].append({'name': 'node_inventory_stable', 'status': 'failed',
                    'issues': ['Source execution did not cover the collected inventory']})
        if inventories and isinstance(inventories[0], dict):
            result['deferred_tests'] = [n for n in inventories[0].get('nodes', []) if n['phase'] != 'source']
    after = _preparation_inputs(repo_root, raw_root, operational_paths=operational_paths)
    stable = before == after and runtime == _preparation_runtime()
    result['checks'].append({'name': 'inputs_stable', 'status': 'passed' if stable else 'failed',
                             'issues': [] if stable else ['Input inventory/content or runtime/environment changed during preparation']})
    result['ready'] = all(check['status'] == 'passed' for check in result['checks'])
    result['completed'] = True
    result['integrity'] = _digest(result)
    if report_path:
        _atomic_report(report_path, result)
    return result


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

    parser.add_argument('--prepare', action='store_true', help='Aggregate read-only source readiness before regeneration')
    parser.add_argument('--raw-root', type=Path)
    parser.add_argument('--report', type=Path, default=SCRIPTS_DIR / 'reports/pipeline_preparation.json')
    args = parser.parse_args()
    if args.prepare:
        if args.raw_root is None:
            parser.error('--prepare requires --raw-root')
        import os
        import subprocess
        from test_lock import inherited_lock_fds
        if not inherited_lock_fds(exclusive=True):
            # Preparation is a broad workload even when its inventory expands
            # into explicit nodes. Hold the existing exclusive machine lock.
            environment = dict(os.environ, PG_TEST_LOCK_HELD='1', PG_TEST_WORKERS='1')
            return_code = subprocess.call([sys.executable, str(SCRIPTS_DIR / 'test_lock.py'),
                'exclusive', '--', sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]], env=environment)
            sys.exit(return_code)
        results = run_preparation(SCRIPTS_DIR.parent, args.raw_root, report_path=args.report)
        print(json.dumps(results, indent=2) if args.json else
              '\n'.join(f"{check['status'].upper()}: {check['name']}" for check in results['checks']))
        sys.exit(0 if results['ready'] else 1)

    results = run_preflight(verbose=args.verbose, quick=args.quick)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_results(results, verbose=args.verbose)

    sys.exit(results["summary"]["exit_code"])


if __name__ == "__main__":
    main()
