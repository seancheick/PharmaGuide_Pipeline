#!/usr/bin/env python3
"""Regression checks for the dedicated api_audit namespace."""

import os
import sys


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_verify_cui_root_wrapper_matches_api_audit_module():
    import verify_cui
    from api_audit import verify_cui as packaged_verify_cui

    assert verify_cui.UMLSClient is packaged_verify_cui.UMLSClient
    assert verify_cui.verify_cui_for_entry is packaged_verify_cui.verify_cui_for_entry


def test_banned_recalled_audit_root_wrapper_matches_api_audit_module():
    import audit_banned_recalled_accuracy
    from api_audit import audit_banned_recalled_accuracy as packaged_audit

    assert audit_banned_recalled_accuracy.audit_entry_quality is packaged_audit.audit_entry_quality
    assert audit_banned_recalled_accuracy.audit_cui_accuracy is packaged_audit.audit_cui_accuracy


def test_fda_sync_root_wrapper_matches_api_audit_module():
    import fda_weekly_sync
    from api_audit import fda_weekly_sync as packaged_sync

    assert fda_weekly_sync.classify_record is packaged_sync.classify_record
    assert fda_weekly_sync.extract_substances is packaged_sync.extract_substances
