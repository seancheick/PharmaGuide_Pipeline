#!/usr/bin/env python3
"""Regression checks for the dedicated api_audit namespace."""

import os
import importlib.util
from pathlib import Path
import sys


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def _root_wrapper(name):
    # Collection can prepend api_audit to sys.path. Load the actual root file,
    # rather than accidentally comparing a second import of the implementation.
    path = Path(__file__).resolve().parents[1] / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"root_wrapper_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_verify_cui_root_wrapper_matches_api_audit_module():
    verify_cui = _root_wrapper("verify_cui")
    from api_audit import verify_cui as packaged_verify_cui

    assert verify_cui.UMLSClient is packaged_verify_cui.UMLSClient
    assert verify_cui.verify_cui_for_entry is packaged_verify_cui.verify_cui_for_entry


def test_banned_recalled_audit_root_wrapper_matches_api_audit_module():
    audit_banned_recalled_accuracy = _root_wrapper("audit_banned_recalled_accuracy")
    from api_audit import audit_banned_recalled_accuracy as packaged_audit

    assert audit_banned_recalled_accuracy.audit_entry_quality is packaged_audit.audit_entry_quality
    assert audit_banned_recalled_accuracy.audit_cui_accuracy is packaged_audit.audit_cui_accuracy


def test_fda_sync_root_wrapper_matches_api_audit_module():
    fda_weekly_sync = _root_wrapper("fda_weekly_sync")
    from api_audit import fda_weekly_sync as packaged_sync

    assert fda_weekly_sync.classify_record is packaged_sync.classify_record
    assert fda_weekly_sync.extract_substances is packaged_sync.extract_substances
