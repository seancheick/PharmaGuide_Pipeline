#!/usr/bin/env python3
"""Release gate: banned-substance signals must never ship as SAFE."""

import json
import sqlite3
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_DIR = REPO_ROOT / "scripts" / "final_db_output"
CORE_DB = BUILD_DIR / "pharmaguide_core.db"
BLOB_DIR = BUILD_DIR / "detail_blobs"


pytestmark = pytest.mark.skipif(
    not CORE_DB.exists() or not BLOB_DIR.exists(),
    reason="final_db_output artifacts not present",
)


def _core_rows_by_id() -> dict[str, dict]:
    conn = sqlite3.connect(CORE_DB)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT
              dsld_id,
              verdict,
              safety_verdict,
              has_banned_substance,
              score_safety_purity,
              blocking_reason
            FROM products_core
            """
        ).fetchall()
    finally:
        conn.close()
    return {str(row["dsld_id"]): dict(row) for row in rows}


def test_no_safe_core_row_with_banned_substance_flag():
    conn = sqlite3.connect(CORE_DB)
    try:
        offenders = conn.execute(
            """
            SELECT dsld_id, verdict, safety_verdict
            FROM products_core
            WHERE has_banned_substance = 1
              AND (verdict = 'SAFE' OR safety_verdict = 'SAFE')
            ORDER BY dsld_id
            """
        ).fetchall()
    finally:
        conn.close()

    assert offenders == []


def test_no_critical_banned_warning_with_safe_core_verdict():
    rows_by_id = _core_rows_by_id()
    offenders: list[tuple[str, str, str, str]] = []

    for path in BLOB_DIR.glob("*.json"):
        dsld_id = path.stem
        core = rows_by_id.get(dsld_id)
        if not core or (
            core.get("verdict") != "SAFE"
            and core.get("safety_verdict") != "SAFE"
        ):
            continue

        blob = json.loads(path.read_text(encoding="utf-8"))
        warnings = (blob.get("warnings") or []) + (
            blob.get("warnings_profile_gated") or []
        )
        for warning in warnings:
            if not isinstance(warning, dict):
                continue
            if (
                warning.get("type") == "banned_substance"
                and str(warning.get("severity", "")).lower() == "critical"
            ):
                offenders.append((
                    dsld_id,
                    str(core.get("verdict")),
                    str(core.get("safety_verdict")),
                    str(warning.get("title")),
                ))
                break

    assert offenders == []


def test_no_banned_substance_flag_with_nonzero_safety_score():
    conn = sqlite3.connect(CORE_DB)
    try:
        offenders = conn.execute(
            """
            SELECT dsld_id, score_safety_purity, blocking_reason
            FROM products_core
            WHERE has_banned_substance = 1
              AND COALESCE(score_safety_purity, 0) <> 0
            ORDER BY dsld_id
            """
        ).fetchall()
    finally:
        conn.close()

    assert offenders == []


def test_no_critical_banned_warning_with_nonzero_safety_score_or_missing_blocking_reason():
    rows_by_id = _core_rows_by_id()
    offenders: list[tuple[str, object, object, str]] = []

    for path in BLOB_DIR.glob("*.json"):
        dsld_id = path.stem
        core = rows_by_id.get(dsld_id)
        if not core:
            continue
        blob = json.loads(path.read_text(encoding="utf-8"))
        warnings = (blob.get("warnings") or []) + (
            blob.get("warnings_profile_gated") or []
        )
        has_critical_banned = any(
            isinstance(warning, dict)
            and warning.get("type") == "banned_substance"
            and str(warning.get("severity", "")).lower() == "critical"
            for warning in warnings
        )
        if not has_critical_banned:
            continue
        if (
            float(core.get("score_safety_purity") or 0) != 0.0
            or core.get("blocking_reason") != "banned_ingredient"
        ):
            offenders.append((
                dsld_id,
                core.get("score_safety_purity"),
                core.get("blocking_reason"),
                str(core.get("verdict")),
            ))

    assert offenders == []


def test_no_safe_core_row_when_scorer_emits_blocking_reason():
    conn = sqlite3.connect(CORE_DB)
    try:
        offenders = conn.execute(
            """
            SELECT dsld_id, verdict, safety_verdict, blocking_reason
            FROM products_core
            WHERE blocking_reason IS NOT NULL
              AND (verdict = 'SAFE' OR safety_verdict = 'SAFE')
            ORDER BY dsld_id
            """
        ).fetchall()
    finally:
        conn.close()

    assert offenders == []


def test_no_safe_core_row_with_profile_gated_critical_safety_warning():
    rows_by_id = _core_rows_by_id()
    hard_safety_types = {
        "banned_substance",
        "recalled_ingredient",
        "adulterant",
        "contraindicated",
        "high_risk_ingredient",
    }
    hard_severities = {"critical", "high", "contraindicated", "avoid"}
    offenders: list[tuple[str, str, str, str]] = []

    for path in BLOB_DIR.glob("*.json"):
        dsld_id = path.stem
        core = rows_by_id.get(dsld_id)
        if not core or (
            core.get("verdict") != "SAFE"
            and core.get("safety_verdict") != "SAFE"
        ):
            continue
        blob = json.loads(path.read_text(encoding="utf-8"))
        for warning in blob.get("warnings_profile_gated") or []:
            if not isinstance(warning, dict):
                continue
            warning_type = str(warning.get("type") or "")
            severity = str(warning.get("severity") or "").lower()
            if warning_type in hard_safety_types and severity in hard_severities:
                offenders.append((
                    dsld_id,
                    warning_type,
                    severity,
                    str(warning.get("matched_rule_id") or warning.get("title")),
                ))
                break

    assert offenders == []
