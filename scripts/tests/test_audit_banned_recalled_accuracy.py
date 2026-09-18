#!/usr/bin/env python3
"""Tests for the banned/recalled accuracy audit workflow and runbook text."""

import os
import sys
import json

import pytest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import audit_banned_recalled_accuracy
from audit_banned_recalled_accuracy import (
    apply_safe_cui_updates,
    audit_cui_accuracy,
    audit_entry_quality,
    determine_overall_status,
    is_umls_available,
    fda_sync_release_blocker,
    load_fda_sync_report,
    should_fail_release_gate,
)
from db_integrity_sanity_check import Finding


class FakeUMLSClient:
    def lookup_cui(self, cui):
        return {
            "C_BAD": {"cui": "C_BAD", "name": "Wrong Substance"},
            "C_GOOD": {"cui": "C_GOOD", "name": "Meloxicam"},
            "C_VARIANT": {"cui": "C_VARIANT", "name": "Example Variant Expanded"},
        }.get(cui)

    def search_exact(self, term):
        return {
            "Sildenafil": {"cui": "C_SILD", "name": "Sildenafil"},
            "Meloxicam": {"cui": "C_GOOD", "name": "Meloxicam"},
            "XV": {"cui": "C_VARIANT", "name": "Example Variant Expanded"},
        }.get(term)

    def search(self, term, max_results=3):
        if term == "Unknown Compound":
            return []
        return [{"cui": "C_FALLBACK", "name": f"{term} fallback"}]


class UnreachableUMLSClient:
    def search_exact(self, term):
        return None


def test_audit_entry_quality_flags_expected_gaps():
    entries = [
        {
            "id": "RECALLED_TEST_PRODUCT",
            "standard_name": "Test Product",
            "entity_type": "product",
            "source_category": None,
            "references_structured": [],
            "review": {"status": "validated", "change_log": []},
            "recall_scope": None,
            "cui": None,
        },
        {
            "id": "LEGACY_BAD_ENTRY",
            "standard_name": "Legacy Entry",
            "entity_type": None,
            "source_category": "high_risk_ingredients",
            "references_structured": [{"type": "regulatory", "title": "FDA", "url": ""}],
            "references": [{"title": "Old ref", "url": "https://example.com"}],
            "review": {
                "status": "validated",
                "last_reviewed_at": "2026-03-20",
                "next_review_due": "2026-09-20",
                "reviewed_by": "manual",
                "change_log": [{"date": "2026-03-20", "change": "Added", "reason": "manual"}],
            },
            "recall_scope": None,
            "cui": None,
        },
        {
            "id": "CLASS_WITH_APPROVED_NULL_CUI",
            "standard_name": "Policy Watchlist: Example",
            "entity_type": "class",
            "source_category": "high_risk_ingredients",
            "references_structured": [{"type": "regulatory", "title": "FDA", "url": "https://example.com"}],
            "review": {
                "status": "validated",
                "last_reviewed_at": "2026-03-20",
                "next_review_due": "2026-09-20",
                "reviewed_by": "manual",
                "change_log": [{"date": "2026-03-20", "change": "Added", "by": "manual"}],
            },
            "recall_scope": None,
            "cui": None,
            "cui_status": "no_single_umls_concept",
            "cui_note": "Multi-substance policy entry; null CUI is intentional.",
        },
        {
            "id": "ADULTERANT_OK",
            "standard_name": "Meloxicam",
            "entity_type": "contaminant",
            "source_category": "pharmaceutical_adulterants",
            "references_structured": [{"type": "fda_advisory", "title": "FDA", "url": "https://example.com"}],
            "review": {
                "status": "validated",
                "last_reviewed_at": "2026-03-20",
                "next_review_due": "2026-09-20",
                "reviewed_by": "manual",
                "change_log": [{"date": "2026-03-20", "change": "Added", "by": "manual"}],
            },
            "recall_scope": None,
            "cui": "C_GOOD",
        },
    ]

    report = audit_entry_quality(entries)

    assert "RECALLED_TEST_PRODUCT" in report["missing_source_category"]
    assert "RECALLED_TEST_PRODUCT" in report["missing_reference_urls"]
    assert "RECALLED_TEST_PRODUCT" in report["product_missing_recall_scope"]
    assert "LEGACY_BAD_ENTRY" in report["missing_entity_type"]
    assert "LEGACY_BAD_ENTRY" in report["missing_cui_annotations"]
    assert "CLASS_WITH_APPROVED_NULL_CUI" not in report["missing_cui_annotations"]
    assert "LEGACY_BAD_ENTRY" in report["legacy_reference_blocks"]
    assert "LEGACY_BAD_ENTRY" in report["empty_reference_urls"]
    assert report["malformed_change_log"]["LEGACY_BAD_ENTRY"] == ["change_log[0].by"]
    assert report["review_gaps"]["RECALLED_TEST_PRODUCT"] == [
        "last_reviewed_at",
        "next_review_due",
        "reviewed_by",
        "change_log",
    ]


def test_audit_cui_accuracy_identifies_safe_fills_and_mismatches():
    entries = [
        {
            "id": "ADULTERANT_SILD",
            "standard_name": "Sildenafil",
            "aliases": ["Viagra"],
            "entity_type": "ingredient",
            "cui": None,
        },
        {
            "id": "ADULTERANT_MELOXICAM",
            "standard_name": "Meloxicam",
            "aliases": [],
            "entity_type": "contaminant",
            "cui": "C_BAD",
        },
        {
            "id": "RECALLED_PRODUCT",
            "standard_name": "Brand Recall",
            "aliases": [],
            "entity_type": "product",
            "cui": None,
        },
        {
            "id": "VARIANT_EV",
            "standard_name": "XV",
            "aliases": [],
            "entity_type": "ingredient",
            "cui": "C_VARIANT",
        },
        {
            "id": "CLASS_NO_SINGLE_CUI",
            "standard_name": "Policy Watchlist: Example",
            "aliases": [],
            "entity_type": "class",
            "cui": None,
            "cui_status": "no_single_umls_concept",
            "cui_note": "Multi-substance policy entry; null CUI is intentional.",
        },
    ]

    report = audit_cui_accuracy(entries, FakeUMLSClient())

    assert report["counts"]["safe_missing_exact_matches"] == 1
    assert report["counts"]["annotated_no_cui"] == 1
    assert report["counts"]["verified"] == 1
    assert report["safe_to_apply"][0]["id"] == "ADULTERANT_SILD"
    assert report["mismatched_cui"][0]["id"] == "ADULTERANT_MELOXICAM"
    assert report["counts"]["name_variants"] == 0
    assert report["counts"]["not_found"] == 0
    assert "RECALLED_PRODUCT" not in report["missing_cui_non_product"]
    assert "CLASS_NO_SINGLE_CUI" not in report["missing_cui_non_product"]


def test_apply_safe_cui_updates_only_updates_missing_values():
    entries = [
        {"id": "ADULTERANT_SILD", "cui": None},
        {"id": "ADULTERANT_MELOXICAM", "cui": "C_BAD"},
    ]
    safe_updates = [
        {"id": "ADULTERANT_SILD", "suggested_cui": "C_SILD"},
        {"id": "ADULTERANT_MELOXICAM", "suggested_cui": "C_GOOD"},
    ]

    applied = apply_safe_cui_updates(entries, safe_updates)

    assert applied == 1
    assert entries[0]["cui"] == "C_SILD"
    assert entries[1]["cui"] == "C_BAD"


def test_is_umls_available_false_when_probe_fails():
    assert is_umls_available(UnreachableUMLSClient()) is False
    assert is_umls_available(FakeUMLSClient()) is True


def test_load_fda_sync_report_reads_summary_and_new_record_count(tmp_path):
    report_path = tmp_path / "fda_report.json"
    report_path.write_text(
        json.dumps(
            {
                "summary": {"requiring_claude_review": 2, "already_tracked": 5},
                "new_records_requiring_review": [{"id": 1}, {"id": 2}],
            }
        )
    )

    report = load_fda_sync_report(report_path)

    assert report["summary"]["requiring_claude_review"] == 2
    assert report["new_records_requiring_review_count"] == 2
    assert report["report_path"] == str(report_path)


def test_hexavalent_chromium_does_not_reuse_elemental_chromium_identifiers():
    data_path = Path(__file__).resolve().parents[1] / "data" / "banned_recalled_ingredients.json"
    data = json.loads(data_path.read_text())
    entry = next(
        row for row in data["ingredients"]
        if row["id"] == "HM_CHROMIUM_HEXAVALENT"
    )

    assert entry["cui"] == "C1707393"
    assert (entry.get("external_ids") or {}).get("unii") in (None, "")
    assert entry.get("rxcui") in (None, "")
    assert entry.get("gsrs") is None


def test_determine_overall_status_prefers_fail_then_warn_then_pass():
    assert determine_overall_status(
        [Finding("error", "banned_recalled_ingredients.json", "$", "bad", "x", "y")],
        {
            "missing_source_category": [],
            "missing_reference_urls": [],
            "product_missing_recall_scope": [],
            "review_gaps": {},
            "missing_entity_type": [],
            "missing_cui_annotations": [],
            "legacy_reference_blocks": [],
            "empty_reference_urls": [],
            "malformed_change_log": {},
        },
        {"counts": {"invalid_cui": 0, "mismatched_cui": 0, "name_variants": 0, "missing_cui_non_product": 0}},
    ) == "fail"

    assert determine_overall_status(
        [],
        {
            "missing_source_category": ["X"],
            "missing_reference_urls": [],
            "product_missing_recall_scope": [],
            "review_gaps": {},
            "missing_entity_type": [],
            "missing_cui_annotations": [],
            "legacy_reference_blocks": [],
            "empty_reference_urls": [],
            "malformed_change_log": {},
        },
        {"counts": {"invalid_cui": 0, "mismatched_cui": 0, "name_variants": 0, "missing_cui_non_product": 0}},
    ) == "warn"

    assert determine_overall_status(
        [],
        {
            "missing_source_category": [],
            "missing_reference_urls": [],
            "product_missing_recall_scope": [],
            "review_gaps": {},
            "missing_entity_type": [],
            "missing_cui_annotations": [],
            "legacy_reference_blocks": [],
            "empty_reference_urls": [],
            "malformed_change_log": {},
        },
        {"counts": {"invalid_cui": 0, "mismatched_cui": 0, "name_variants": 0, "missing_cui_non_product": 0}},
    ) == "pass"


def test_release_gate_blocks_when_cui_audit_is_unavailable():
    report = {
        "status": "pass",
        "cui_audit": {
            "enabled": False,
            "counts": {
                "invalid_cui": 0,
                "mismatched_cui": 0,
                "name_variants": 0,
                "missing_cui_non_product": 0,
            },
            "skipped_reason": "UMLS API unavailable",
        },
        "entry_quality": {
            "missing_source_category": [],
            "missing_reference_urls": [],
            "product_missing_recall_scope": [],
            "review_gaps": {},
            "missing_entity_type": [],
            "missing_cui_annotations": [],
            "legacy_reference_blocks": [],
            "empty_reference_urls": [],
            "malformed_change_log": {},
        },
        "integrity": {"errors": 0, "warnings": 0},
    }

    assert should_fail_release_gate(report) is True


def test_release_gate_allows_clean_live_report():
    report = {
        "status": "pass",
        "cui_audit": {
            "enabled": True,
            "counts": {
                "invalid_cui": 0,
                "mismatched_cui": 0,
                "name_variants": 0,
                "missing_cui_non_product": 0,
            },
            "skipped_reason": None,
        },
        "entry_quality": {
            "missing_source_category": [],
            "missing_reference_urls": [],
            "product_missing_recall_scope": [],
            "review_gaps": {},
            "missing_entity_type": [],
            "missing_cui_annotations": [],
            "legacy_reference_blocks": [],
            "empty_reference_urls": [],
            "malformed_change_log": {},
        },
        "integrity": {"errors": 0, "warnings": 0},
    }

    assert should_fail_release_gate(report) is False


def test_release_strict_cui_blocks_unannotated_missing_non_product():
    report = {
        "status": "pass",
        "cui_audit": {
            "enabled": True,
            "counts": {
                "invalid_cui": 0,
                "mismatched_cui": 0,
                "name_variants": 0,
                "missing_cui_non_product": 1,
            },
            "skipped_reason": None,
        },
        "entry_quality": {
            "missing_source_category": [],
            "missing_reference_urls": [],
            "product_missing_recall_scope": [],
            "review_gaps": {},
            "missing_entity_type": [],
            "missing_cui_annotations": [],
            "legacy_reference_blocks": [],
            "empty_reference_urls": [],
            "malformed_change_log": {},
        },
        "integrity": {"errors": 0, "warnings": 0},
    }

    assert should_fail_release_gate(report) is False
    assert should_fail_release_gate(report, strict_cui=True) is True


def test_audit_module_docstring_includes_release_runbook():
    doc = audit_banned_recalled_accuracy.__doc__ or ""

    assert "--release-strict-cui" in doc
    assert "--run-fda-sync" in doc
    assert "annotated null cui" in doc.lower()


# ---------------------------------------------------------------------------
# FDA sync must be fail-closed in release mode.
#
# load_fda_sync_report() returns None for BOTH a missing and an unparsable
# report, and fda_sync is consumed by neither determine_overall_status() nor
# should_fail_release_gate(). So a --release run that named a report could pass
# without ever reading one: the command looked audited while fda_sync was null.
# These tests pin that absence can no longer be mistaken for a clean check.
# ---------------------------------------------------------------------------

def _blocker(**kw):
    base = dict(release_mode=True, run_fda_sync_requested=False,
                fda_report_in=None, fda_sync_result=None)
    base.update(kw)
    return fda_sync_release_blocker(**base)


def test_release_without_any_fda_argument_is_blocked():
    reason = _blocker()
    assert reason and "requires an FDA sync report" in reason


def test_release_with_missing_report_is_blocked(tmp_path):
    missing = tmp_path / "absent.json"
    reason = _blocker(fda_report_in=str(missing), fda_sync_result=None)
    assert reason and "not found" in reason


def test_release_with_malformed_report_is_blocked(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"truncated": ')
    # load_fda_sync_report swallows the JSONDecodeError and returns None; the
    # file exists, so "unreadable or malformed" is the honest reason.
    assert load_fda_sync_report(bad) is None
    reason = _blocker(fda_report_in=str(bad), fda_sync_result=None)
    assert reason and "unreadable or malformed" in reason


def test_release_with_a_valid_report_is_allowed(tmp_path):
    good = tmp_path / "good.json"
    good.write_text(json.dumps({"summary": {"total_fetched": 0}}))
    loaded = load_fda_sync_report(good)
    assert loaded is not None
    assert _blocker(fda_report_in=str(good), fda_sync_result=loaded) is None


def test_release_with_a_failed_live_sync_is_blocked():
    reason = _blocker(run_fda_sync_requested=True,
                      fda_sync_result={"returncode": 2})
    assert reason and "live FDA sync failed" in reason


def test_release_with_a_successful_live_sync_is_allowed():
    assert _blocker(run_fda_sync_requested=True,
                    fda_sync_result={"returncode": 0}) is None


def test_non_release_runs_are_not_forced_to_have_an_fda_report(tmp_path):
    """The contract binds release mode only — local audits stay convenient."""
    assert fda_sync_release_blocker(
        release_mode=False, run_fda_sync_requested=False,
        fda_report_in=str(tmp_path / "absent.json"), fda_sync_result=None) is None


def _cli_entrypoints():
    """Both shipped entry points: the api_audit implementation and the
    scripts/ compatibility wrapper. The wrapper once called main() instead of
    sys.exit(main()), so it printed "RELEASE GATE FAILED" and exited 0 -- a
    release gate that announced failure and passed anyway."""
    scripts_dir = Path(__file__).resolve().parents[1]
    wrapper = scripts_dir / "audit_banned_recalled_accuracy.py"
    real = scripts_dir / "api_audit" / "audit_banned_recalled_accuracy.py"
    found = sorted(p for p in {wrapper, real} if p.is_file())
    # An empty parametrize set SKIPS, and a skipped canary is not a passing
    # canary -- fail loudly instead of silently covering nothing.
    assert found, f"no audit entry point found under {scripts_dir}"
    return found


@pytest.mark.parametrize("entrypoint", _cli_entrypoints(), ids=lambda p: p.parent.name)
def test_release_cli_exits_nonzero_when_the_report_is_absent(entrypoint, tmp_path):
    """End-to-end: a missing FDA report must fail the gate through EVERY entry
    point, by exit code -- not merely by printing a failure message."""
    import subprocess

    proc = subprocess.run(
        [sys.executable, str(entrypoint), "--release",
         "--fda-report-in", str(tmp_path / "absent.json")],
        capture_output=True, text=True, timeout=120,
    )
    assert "RELEASE GATE FAILED" in proc.stderr, proc.stderr[-400:]
    assert proc.returncode != 0, (
        f"{entrypoint} printed the failure but exited {proc.returncode}; a gate "
        "must signal failure through its exit code"
    )
