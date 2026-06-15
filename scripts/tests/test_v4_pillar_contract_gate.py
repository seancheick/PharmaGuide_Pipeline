"""Unit tests for the V4 pillar DB-contract release gate.

check_v4_pillar_contract inspects the shipped products_core and fails the
release if the six pillar columns are absent, NULL on a scored product, out of
range, fail to reconcile with the total, or populated on a suppressed product.

Closes the 2026-06-14 stale-DB hole: a DB built before the pillar-projection
commit shipped with the six columns absent, and the freshness/checksum gates
didn't catch it because they compare timestamps/hashes, not schema/population.
"""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from audit_source_of_truth_contract import check_v4_pillar_contract  # noqa: E402

PILLAR_COLS = [
    "pillar_formulation_v4", "pillar_dose_v4", "pillar_evidence_v4",
    "pillar_transparency_v4", "pillar_verification_v4", "pillar_safety_hygiene_v4",
]


def _make_db(rows, with_pillars=True):
    tmp = tempfile.mkdtemp()
    db = Path(tmp) / "pharmaguide_core.db"
    cols = "dsld_id TEXT, quality_score_status TEXT, quality_score_v4_100 REAL"
    if with_pillars:
        cols += ", " + ", ".join(f"{c} REAL" for c in PILLAR_COLS)
    ncol = 3 + (len(PILLAR_COLS) if with_pillars else 0)
    with sqlite3.connect(db) as conn:
        conn.execute(f"CREATE TABLE products_core ({cols})")
        if rows:
            ph = ",".join(["?"] * ncol)
            conn.executemany(f"INSERT INTO products_core VALUES ({ph})", rows)
    return db


def _scored(dsld, total, f, d, e, t, v, s):
    return (dsld, "scored", total, f, d, e, t, v, s)


def _suppressed(dsld, f=None, d=None, e=None, t=None, v=None, s=None):
    return (dsld, "suppressed_safety", None, f, d, e, t, v, s)


def _codes(findings):
    return {fnd.code for fnd in findings}


def test_clean_scored_and_suppressed_db_passes():
    # 11.2+20+18.9+15+6+10 = 81.1 (reconciles); suppressed row all NULL.
    db = _make_db([
        _scored("1", 81.1, 11.2, 20.0, 18.9, 15.0, 6.0, 10.0),
        _suppressed("2"),
    ])
    assert check_v4_pillar_contract(db) == []


def test_missing_pillar_columns_flags():
    db = _make_db([("1", "scored", 81.1)], with_pillars=False)
    assert "EXPORT_V4_PILLAR_COLS_MISSING" in _codes(check_v4_pillar_contract(db))


def test_scored_null_pillar_flags():
    db = _make_db([_scored("1", 71.1, None, 20.0, 18.9, 15.0, 6.0, 10.0)])
    assert "EXPORT_V4_PILLAR_NULL_ON_SCORED" in _codes(check_v4_pillar_contract(db))


def test_pillar_out_of_range_flags():
    # formulation 25 > max 20; total set to the (out-of-range) sum so only the
    # range finding fires, not recon.
    db = _make_db([_scored("1", 94.9, 25.0, 20.0, 18.9, 15.0, 6.0, 10.0)])
    assert "EXPORT_V4_PILLAR_OUT_OF_RANGE" in _codes(check_v4_pillar_contract(db))


def test_total_out_of_range_flags():
    db = _make_db([_scored("1", 120.0, 11.2, 20.0, 18.9, 15.0, 6.0, 10.0)])
    assert "EXPORT_V4_TOTAL_OUT_OF_RANGE" in _codes(check_v4_pillar_contract(db))


def test_recon_mismatch_flags():
    # pillars sum to 81.1 but total claims 90.0
    db = _make_db([_scored("1", 90.0, 11.2, 20.0, 18.9, 15.0, 6.0, 10.0)])
    assert "EXPORT_V4_PILLAR_RECON_MISMATCH" in _codes(check_v4_pillar_contract(db))


def test_suppressed_with_populated_pillar_flags():
    db = _make_db([_suppressed("1", f=12.0)])
    assert "EXPORT_V4_PILLAR_ON_UNSCORED" in _codes(check_v4_pillar_contract(db))


def test_unreadable_db_flags():
    # A shipped file that isn't a valid SQLite catalog must block the release,
    # not crash the gate.
    tmp = tempfile.mkdtemp()
    db = Path(tmp) / "pharmaguide_core.db"
    db.write_bytes(b"catalog")
    assert "EXPORT_V4_DB_UNREADABLE" in _codes(check_v4_pillar_contract(db))
