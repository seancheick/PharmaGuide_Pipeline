#!/usr/bin/env python3
"""Tests for deterministic prose alignment auditing."""

import os
import sys


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_check_study_type_contradiction_flags_meta_claim_in_notes():
    from api_audit.audit_notes_alignment import check_study_type_contradiction

    issues = check_study_type_contradiction(
        {
            "study_type": "rct_single",
            "notes": "This meta-analysis demonstrates clear benefits in humans.",
        }
    )

    assert len(issues) == 1
    assert issues[0]["subtype"] == "meta_claim_vs_study_type"


def test_check_stale_claims_flags_retracted_reference_when_entry_still_makes_study_claims():
    from api_audit.audit_notes_alignment import check_stale_claims

    issues = check_stale_claims(
        {
            "notes": "A study showed improved outcomes in patients.",
            "references_structured": [
                {
                    "pmid": "12345",
                    "retracted": True,
                }
            ],
        }
    )

    assert len(issues) == 1
    assert issues[0]["subtype"] == "retracted_reference_present"


def test_check_stale_claims_does_not_flag_negated_gras_statement():
    from api_audit.audit_notes_alignment import check_stale_claims

    issues = check_stale_claims(
        {
            "status": "banned",
            "reason": "FDA determined this substance is not GRAS and removed it from the food supply.",
        }
    )

    assert issues == []


def test_check_severity_alignment_allows_rare_anaphylaxis_context_for_low_severity():
    from api_audit.audit_notes_alignment import check_severity_alignment

    issues = check_severity_alignment(
        {
            "severity_level": "low",
            "mechanism_of_harm": "Rare but documented IgE-mediated allergic reactions and anaphylaxis in sensitive individuals.",
        }
    )

    assert issues == []


def test_build_summary_rolls_up_multiple_db_results():
    from api_audit.audit_notes_alignment import _build_summary

    summary = _build_summary(
        {
            "clinical": {
                "total_entries": 10,
                "entries_with_issues": 2,
                "total_issues": 3,
                "by_type": {"CONTRADICTION": 2, "STALE_CLAIM": 1},
            },
            "banned": {
                "total_entries": 5,
                "entries_with_issues": 1,
                "total_issues": 2,
                "by_type": {"CONTRADICTION": 1, "OVERSTATEMENT": 1},
            },
        }
    )

    assert summary["total_entries"] == 15
    assert summary["entries_with_issues"] == 3
    assert summary["total_issues"] == 5
    assert summary["by_type"] == {
        "CONTRADICTION": 3,
        "STALE_CLAIM": 1,
        "OVERSTATEMENT": 1,
    }
