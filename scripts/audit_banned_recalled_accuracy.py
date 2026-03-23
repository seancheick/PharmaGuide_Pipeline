#!/usr/bin/env python3
"""
One-command accuracy audit for banned_recalled_ingredients.json.

Primary operator commands:
  - Fast local audit against the current file and latest FDA sync report:
      .venv/bin/python scripts/audit_banned_recalled_accuracy.py --fda-report-in scripts/fda_sync_report_latest.json
  - Run a fresh FDA sync and then audit:
      .venv/bin/python scripts/audit_banned_recalled_accuracy.py --run-fda-sync --days 30 --fda-report-out scripts/fda_sync_report_latest.json
  - Production gate:
      .venv/bin/python scripts/audit_banned_recalled_accuracy.py --release --fda-report-in scripts/fda_sync_report_latest.json
  - Strict production gate with annotated null-CUI enforcement:
      .venv/bin/python scripts/audit_banned_recalled_accuracy.py --release-strict-cui --fda-report-in scripts/fda_sync_report_latest.json

Decision rules:
  - `--release` fails if the file has integrity/schema issues or if live CUI verification is unavailable.
  - `--release-strict-cui` also fails if any non-product entry still lacks either a real CUI or an approved annotated null CUI.
  - Annotated null CUI means `cui` is null on purpose and the record includes `cui_status` plus `cui_note`.
  - Use verify_cui.py before editing the data file whenever a null CUI might be solvable by adding a better exact alias.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from db_integrity_sanity_check import Finding, run_checks
from verify_cui import DEFAULT_API_KEY, UMLSClient, verify_cui_for_entry


ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_FILE = ROOT / "data" / "banned_recalled_ingredients.json"
DEFAULT_REPORT_FILE = ROOT / "banned_recalled_accuracy_report.json"
APPROVED_CUI_STATUSES = {
    "no_confirmed_umls_match",
    "no_single_umls_concept",
}
AUDIT_HELP_EPILOG = """Examples:
  Quick audit:
    .venv/bin/python scripts/audit_banned_recalled_accuracy.py --fda-report-in scripts/fda_sync_report_latest.json

  Fresh FDA sync plus audit:
    .venv/bin/python scripts/audit_banned_recalled_accuracy.py --run-fda-sync --days 30 --fda-report-out scripts/fda_sync_report_latest.json

  Production gate:
    .venv/bin/python scripts/audit_banned_recalled_accuracy.py --release --fda-report-in scripts/fda_sync_report_latest.json

  Strict production gate:
    .venv/bin/python scripts/audit_banned_recalled_accuracy.py --release-strict-cui --fda-report-in scripts/fda_sync_report_latest.json
"""


def load_banned_data(file_path: Path) -> dict[str, Any]:
    return json.loads(file_path.read_text())


def filter_integrity_findings(findings: list[Finding], file_name: str) -> list[Finding]:
    return [finding for finding in findings if finding.file == file_name]


def has_approved_cui_annotation(entry: dict[str, Any]) -> bool:
    if entry.get("cui"):
        return True
    status = entry.get("cui_status")
    note = entry.get("cui_note")
    return (
        isinstance(status, str)
        and status in APPROVED_CUI_STATUSES
        and isinstance(note, str)
        and bool(note.strip())
    )


def _collect_reference_urls(entry: dict[str, Any]) -> list[str]:
    urls: list[str] = []

    for ref in entry.get("references_structured", []):
        if not isinstance(ref, dict):
            continue
        for key in ("url", "fda_recall_url"):
            value = ref.get(key)
            if isinstance(value, str) and value.strip():
                urls.append(value.strip())

    for jurisdiction in entry.get("jurisdictions", []):
        if not isinstance(jurisdiction, dict):
            continue
        source = jurisdiction.get("source")
        if not isinstance(source, dict):
            continue
        for key in ("url", "fda_recall_url"):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                urls.append(value.strip())

    return urls


def _change_log_issues(review: Any) -> list[str]:
    if not isinstance(review, dict):
        return []

    issues: list[str] = []
    change_log = review.get("change_log")
    if not isinstance(change_log, list):
        return issues

    for idx, item in enumerate(change_log):
        prefix = f"change_log[{idx}]"
        if isinstance(item, str):
            issues.append(prefix)
            continue
        if not isinstance(item, dict):
            issues.append(prefix)
            continue
        for field in ("date", "change", "by"):
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                issues.append(f"{prefix}.{field}")

    return issues


def _missing_review_fields(review: Any) -> list[str]:
    if not isinstance(review, dict):
        return ["status", "last_reviewed_at", "next_review_due", "reviewed_by", "change_log"]

    missing: list[str] = []
    for field in ("status", "last_reviewed_at", "next_review_due", "reviewed_by"):
        value = review.get(field)
        if not isinstance(value, str) or not value.strip():
            missing.append(field)

    change_log = review.get("change_log")
    if not isinstance(change_log, list) or not change_log:
        missing.append("change_log")

    return missing


def audit_entry_quality(entries: list[dict[str, Any]]) -> dict[str, Any]:
    report = {
        "missing_source_category": [],
        "missing_reference_urls": [],
        "product_missing_recall_scope": [],
        "review_gaps": {},
        "missing_entity_type": [],
        "missing_cui_annotations": [],
        "legacy_reference_blocks": [],
        "empty_reference_urls": [],
        "malformed_change_log": {},
    }

    for entry in entries:
        entry_id = entry.get("id", "UNKNOWN")
        if not entry.get("entity_type"):
            report["missing_entity_type"].append(entry_id)

        if entry.get("entity_type") != "product" and not has_approved_cui_annotation(entry):
            report["missing_cui_annotations"].append(entry_id)

        if not entry.get("source_category"):
            report["missing_source_category"].append(entry_id)

        if not _collect_reference_urls(entry):
            report["missing_reference_urls"].append(entry_id)

        if entry.get("references") is not None:
            report["legacy_reference_blocks"].append(entry_id)

        for ref in entry.get("references_structured", []) or []:
            if isinstance(ref, dict):
                for key in ("url", "fda_recall_url"):
                    if key in ref and ref.get(key) == "":
                        report["empty_reference_urls"].append(entry_id)
                        break

        if entry.get("entity_type") == "product" and not entry.get("recall_scope"):
            report["product_missing_recall_scope"].append(entry_id)

        review_gaps = _missing_review_fields(entry.get("review"))
        if review_gaps:
            report["review_gaps"][entry_id] = review_gaps

        change_log_issues = _change_log_issues(entry.get("review"))
        if change_log_issues:
            report["malformed_change_log"][entry_id] = change_log_issues

    return report


def audit_cui_accuracy(entries: list[dict[str, Any]], client: UMLSClient | None) -> dict[str, Any]:
    report = {
        "enabled": client is not None,
        "counts": {
            "verified": 0,
            "invalid_cui": 0,
            "mismatched_cui": 0,
            "name_variants": 0,
            "annotated_no_cui": 0,
            "missing_cui_non_product": 0,
            "not_found": 0,
            "safe_missing_exact_matches": 0,
        },
        "invalid_cui": [],
        "mismatched_cui": [],
        "name_variants": [],
        "missing_cui_non_product": [],
        "safe_to_apply": [],
        "skipped_reason": None,
    }

    if client is None:
        report["skipped_reason"] = "UMLS_API_KEY not configured"
        return report

    for entry in entries:
        if getattr(client, "circuit_open", False):
            report["skipped_reason"] = "UMLS API circuit opened after repeated transport failures"
            break

        if entry.get("entity_type") == "product":
            continue

        if not entry.get("cui") and has_approved_cui_annotation(entry):
            report["counts"]["annotated_no_cui"] += 1
            continue

        entry_id = entry.get("id", "UNKNOWN")
        standard_name = entry.get("standard_name", "")
        aliases = entry.get("aliases", [])
        current_cui = entry.get("cui")

        if not isinstance(aliases, list):
            aliases = []

        verification = verify_cui_for_entry(client, entry_id, standard_name, current_cui, aliases)
        status = verification["status"]

        if status == "VERIFIED":
            report["counts"]["verified"] += 1
        elif status == "INVALID_CUI":
            report["counts"]["invalid_cui"] += 1
            report["invalid_cui"].append(verification)
        elif status == "MISMATCH":
            if verification.get("suggested_cui") and verification["suggested_cui"] == current_cui:
                report["counts"]["name_variants"] += 1
                report["name_variants"].append(verification)
            else:
                report["counts"]["mismatched_cui"] += 1
                report["mismatched_cui"].append(verification)
        elif status == "MISSING_CUI":
            report["counts"]["missing_cui_non_product"] += 1
            report["missing_cui_non_product"].append(entry_id)

            suggested_name = str(verification.get("suggested_name") or "").strip().lower()
            standard_name_lc = str(standard_name).strip().lower()
            if suggested_name and suggested_name == standard_name_lc:
                report["counts"]["safe_missing_exact_matches"] += 1
                report["safe_to_apply"].append(
                    {
                        "id": entry_id,
                        "suggested_cui": verification["suggested_cui"],
                        "suggested_name": verification["suggested_name"],
                    }
                )
        elif status == "NOT_FOUND":
            report["counts"]["missing_cui_non_product"] += 1
            report["counts"]["not_found"] += 1
            report["missing_cui_non_product"].append(entry_id)

    return report


def is_umls_available(client: UMLSClient | None) -> bool:
    if client is None:
        return False
    if hasattr(client, "probe"):
        return bool(client.probe("Sildenafil"))
    probe = client.search_exact("Sildenafil")
    return bool(probe and probe.get("cui"))


def apply_safe_cui_updates(entries: list[dict[str, Any]], safe_updates: list[dict[str, str]]) -> int:
    updates_by_id = {
        update["id"]: update["suggested_cui"]
        for update in safe_updates
        if update.get("id") and update.get("suggested_cui")
    }

    applied = 0
    for entry in entries:
        entry_id = entry.get("id")
        if entry.get("cui") or entry_id not in updates_by_id:
            continue
        entry["cui"] = updates_by_id[entry_id]
        applied += 1

    return applied


def determine_overall_status(
    integrity_findings: list[Finding],
    entry_quality: dict[str, Any],
    cui_audit: dict[str, Any],
) -> str:
    if any(finding.severity == "error" for finding in integrity_findings):
        return "fail"

    has_warnings = any(finding.severity == "warning" for finding in integrity_findings)
    has_content_issues = any(
        [
            entry_quality["missing_source_category"],
            entry_quality["missing_reference_urls"],
            entry_quality["product_missing_recall_scope"],
            entry_quality["review_gaps"],
            entry_quality["missing_entity_type"],
            entry_quality["missing_cui_annotations"],
            entry_quality["legacy_reference_blocks"],
            entry_quality["empty_reference_urls"],
            entry_quality["malformed_change_log"],
            cui_audit["counts"]["invalid_cui"] > 0,
            cui_audit["counts"]["mismatched_cui"] > 0,
            cui_audit["counts"]["name_variants"] > 0,
        ]
    )

    if has_warnings or has_content_issues:
        return "warn"

    return "pass"


def run_fda_sync(days: int, output_path: Path) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(ROOT / "fda_weekly_sync.py"),
        "--days",
        str(days),
        "--output",
        str(output_path),
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True)
    result = {
        "enabled": True,
        "command": cmd,
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-1000:],
        "stderr_tail": completed.stderr[-1000:],
        "report_path": str(output_path),
        "summary": None,
    }

    if completed.returncode == 0 and output_path.exists():
        try:
            summary = json.loads(output_path.read_text()).get("summary", {})
            result["summary"] = summary
        except json.JSONDecodeError:
            result["stderr_tail"] += "\nFailed to parse FDA sync output."

    return result


def load_fda_sync_report(report_path: Path) -> dict[str, Any] | None:
    if not report_path.exists():
        return None

    try:
        data = json.loads(report_path.read_text())
    except json.JSONDecodeError:
        return None

    return {
        "enabled": False,
        "command": None,
        "returncode": 0,
        "stdout_tail": "",
        "stderr_tail": "",
        "report_path": str(report_path),
        "summary": data.get("summary", {}),
        "new_records_requiring_review_count": len(data.get("new_records_requiring_review", [])),
    }


def build_report(
    file_path: Path,
    integrity_findings: list[Finding],
    entry_quality: dict[str, Any],
    cui_audit: dict[str, Any],
    fda_sync_result: dict[str, Any] | None,
    applied_safe_cui_updates: int,
) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "file": str(file_path),
        "status": determine_overall_status(integrity_findings, entry_quality, cui_audit),
        "integrity": {
            "errors": sum(1 for finding in integrity_findings if finding.severity == "error"),
            "warnings": sum(1 for finding in integrity_findings if finding.severity == "warning"),
            "findings": [finding.__dict__ for finding in integrity_findings],
        },
        "entry_quality": entry_quality,
        "cui_audit": cui_audit,
        "applied_safe_cui_updates": applied_safe_cui_updates,
        "fda_sync": fda_sync_result,
    }


def should_fail_release_gate(report: dict[str, Any], *, strict_cui: bool = False) -> bool:
    if report["status"] == "fail":
        return True

    cui_audit = report["cui_audit"]
    counts = cui_audit["counts"]

    if not cui_audit.get("enabled"):
        return True

    if counts["invalid_cui"] > 0 or counts["mismatched_cui"] > 0 or counts["name_variants"] > 0:
        return True

    if any(
        [
            report["entry_quality"]["missing_source_category"],
            report["entry_quality"]["missing_reference_urls"],
            report["entry_quality"]["product_missing_recall_scope"],
            report["entry_quality"]["review_gaps"],
            report["entry_quality"]["missing_entity_type"],
            report["entry_quality"]["missing_cui_annotations"],
            report["entry_quality"]["legacy_reference_blocks"],
            report["entry_quality"]["empty_reference_urls"],
            report["entry_quality"]["malformed_change_log"],
        ]
    ):
        return True

    if report["integrity"]["errors"] > 0 or report["integrity"]["warnings"] > 0:
        return True

    if strict_cui and counts["missing_cui_non_product"] > 0:
        return True

    return False


def print_summary(report: dict[str, Any]) -> None:
    print(f"Status: {report['status']}")
    print(f"Report: {report['file']}")
    print(
        "Integrity:"
        f" {report['integrity']['errors']} error(s),"
        f" {report['integrity']['warnings']} warning(s)"
    )
    print(
        "Entry quality:"
        f" missing_source_category={len(report['entry_quality']['missing_source_category'])},"
        f" missing_reference_urls={len(report['entry_quality']['missing_reference_urls'])},"
        f" product_missing_recall_scope={len(report['entry_quality']['product_missing_recall_scope'])},"
        f" review_gaps={len(report['entry_quality']['review_gaps'])},"
        f" missing_entity_type={len(report['entry_quality']['missing_entity_type'])},"
        f" missing_cui_annotations={len(report['entry_quality']['missing_cui_annotations'])},"
        f" legacy_reference_blocks={len(report['entry_quality']['legacy_reference_blocks'])},"
        f" empty_reference_urls={len(report['entry_quality']['empty_reference_urls'])},"
        f" malformed_change_log={len(report['entry_quality']['malformed_change_log'])}"
    )
    cui_counts = report["cui_audit"]["counts"]
    print(
        "CUI audit:"
        f" invalid={cui_counts['invalid_cui']},"
        f" mismatch={cui_counts['mismatched_cui']},"
        f" name_variants={cui_counts['name_variants']},"
        f" annotated_no_cui={cui_counts['annotated_no_cui']},"
        f" missing_non_product={cui_counts['missing_cui_non_product']},"
        f" safe_exact={cui_counts['safe_missing_exact_matches']}"
    )

    if report["fda_sync"]:
        fda_sync = report["fda_sync"]
        print(
            "FDA sync:"
            f" returncode={fda_sync['returncode']},"
            f" report_path={fda_sync['report_path']}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit banned_recalled_ingredients.json for local accuracy.",
        epilog=AUDIT_HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--file", default=str(DEFAULT_DATA_FILE), help="JSON file to audit")
    parser.add_argument("--report-out", default=str(DEFAULT_REPORT_FILE), help="Where to write the JSON audit report")
    parser.add_argument("--run-fda-sync", action="store_true", help="Run FDA sync before auditing")
    parser.add_argument("--days", type=int, default=30, help="FDA sync lookback window when --run-fda-sync is used")
    parser.add_argument("--fda-report-out", default=str(ROOT / "fda_sync_report_latest.json"), help="Path for FDA sync output")
    parser.add_argument("--fda-report-in", help="Read an existing FDA sync report into the audit summary")
    parser.add_argument("--umls-api-key", default=DEFAULT_API_KEY, help="UMLS API key override")
    parser.add_argument("--umls-timeout-seconds", type=float, default=5.0, help="Per-request timeout for UMLS API calls")
    parser.add_argument("--umls-failure-limit", type=int, default=2, help="Open the UMLS transport circuit after this many consecutive failures")
    parser.add_argument("--umls-cache-file", default=str(ROOT / ".cache" / "umls_api_cache.json"), help="JSON cache file for successful UMLS responses")
    parser.add_argument("--umls-cache-ttl-seconds", type=int, default=60 * 60 * 24 * 30, help="TTL for cached UMLS API responses")
    parser.add_argument("--skip-cui-audit", action="store_true", help="Skip CUI verification entirely")
    parser.add_argument("--apply-safe-cui-fixes", action="store_true", help="Fill only missing CUIs with exact safe matches")
    parser.add_argument("--release", action="store_true", help="Production gate: require live CUI audit success and zero warnings")
    parser.add_argument("--release-strict-cui", action="store_true", help="Production gate plus strict no-unannotated-missing-CUI enforcement for non-product entries")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on warnings")
    args = parser.parse_args()

    file_path = Path(args.file)
    report_path = Path(args.report_out)

    fda_sync_result = None
    if args.run_fda_sync:
        fda_sync_result = run_fda_sync(args.days, Path(args.fda_report_out))
    elif args.fda_report_in:
        fda_sync_result = load_fda_sync_report(Path(args.fda_report_in))

    data = load_banned_data(file_path)
    entries = data.get("ingredients", [])

    integrity_findings = filter_integrity_findings(run_checks(), file_path.name)
    entry_quality = audit_entry_quality(entries)

    client = None
    if not args.skip_cui_audit and args.umls_api_key:
        client = UMLSClient(
            args.umls_api_key,
            timeout_seconds=args.umls_timeout_seconds,
            failure_limit=args.umls_failure_limit,
            cache_path=Path(args.umls_cache_file) if args.umls_cache_file else None,
            cache_ttl_seconds=args.umls_cache_ttl_seconds,
            emit_errors=False,
        )
        if not is_umls_available(client):
            client = None
    cui_audit = audit_cui_accuracy(entries, client)
    if args.skip_cui_audit:
        cui_audit["skipped_reason"] = "CUI audit skipped by flag"
    elif client is None and args.umls_api_key:
        cui_audit["skipped_reason"] = "UMLS API unavailable"

    applied_safe_cui_updates = 0
    if args.apply_safe_cui_fixes and cui_audit["safe_to_apply"]:
        applied_safe_cui_updates = apply_safe_cui_updates(entries, cui_audit["safe_to_apply"])
        if applied_safe_cui_updates:
            file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    report = build_report(
        file_path,
        integrity_findings,
        entry_quality,
        cui_audit,
        fda_sync_result,
        applied_safe_cui_updates,
    )
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n")
    print_summary(report)

    if (args.release or args.release_strict_cui) and should_fail_release_gate(report, strict_cui=args.release_strict_cui):
        return 3
    if report["status"] == "fail":
        return 2
    if args.strict and report["status"] == "warn":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
