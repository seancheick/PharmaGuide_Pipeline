from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_final_db import _suppress_zero_dose_duplicate_active_rows  # noqa: E402


def test_suppresses_zero_unspecified_duplicate_when_positive_same_canonical_exists() -> None:
    rows = [
        {
            "name": "Eicosapentaenoic Acid",
            "canonical_id": "epa",
            "quantity": 0.0,
            "unit": "unspecified",
            "dose_status": "missing",
            "role": "active",
        },
        {
            "name": "Eicosapentaenoic Acid",
            "canonical_id": "epa",
            "quantity": 650.0,
            "unit": "mg",
            "dose_status": "disclosed",
            "role": "active",
        },
        {
            "name": "Docosahexaenoic Acid",
            "canonical_id": "dha",
            "quantity": 450.0,
            "unit": "mg",
            "dose_status": "disclosed",
            "role": "active",
        },
    ]

    cleaned = _suppress_zero_dose_duplicate_active_rows(rows)

    assert [r["quantity"] for r in cleaned if r["canonical_id"] == "epa"] == [650.0]
    assert [r["canonical_id"] for r in cleaned] == ["epa", "dha"]


def test_keeps_missing_dose_row_when_no_positive_same_canonical_exists() -> None:
    rows = [
        {
            "name": "Eicosapentaenoic Acid",
            "canonical_id": "epa",
            "quantity": 0.0,
            "unit": "unspecified",
            "dose_status": "missing",
            "role": "active",
        },
        {
            "name": "Docosahexaenoic Acid",
            "canonical_id": "dha",
            "quantity": 450.0,
            "unit": "mg",
            "dose_status": "disclosed",
            "role": "active",
        },
    ]

    cleaned = _suppress_zero_dose_duplicate_active_rows(rows)

    assert cleaned == rows


def test_keeps_undisclosed_blend_member_even_with_positive_same_canonical() -> None:
    rows = [
        {
            "name": "Lactobacillus rhamnosus GG",
            "canonical_id": "lactobacillus_rhamnosus_gg",
            "quantity": 0.0,
            "unit": "NP",
            "dose_status": "not_disclosed_blend",
            "role": "active",
        },
        {
            "name": "Lactobacillus rhamnosus GG",
            "canonical_id": "lactobacillus_rhamnosus_gg",
            "quantity": 40.0,
            "unit": "mg",
            "dose_status": "disclosed",
            "role": "active",
        },
    ]

    cleaned = _suppress_zero_dose_duplicate_active_rows(rows)

    assert cleaned == rows


def test_keeps_safety_row_even_when_it_looks_like_a_duplicate_placeholder() -> None:
    rows = [
        {
            "name": "High Risk Active",
            "canonical_id": "high_risk_active",
            "quantity": 0.0,
            "unit": "unspecified",
            "dose_status": "missing",
            "role": "active",
            "is_safety_concern": True,
        },
        {
            "name": "High Risk Active",
            "canonical_id": "high_risk_active",
            "quantity": 10.0,
            "unit": "mg",
            "dose_status": "disclosed",
            "role": "active",
        },
    ]

    cleaned = _suppress_zero_dose_duplicate_active_rows(rows)

    assert cleaned == rows
