"""Per-entry identifier integrity tests for harmful_additives.json.

Pattern mirrors scripts/tests/test_banned_recalled_identifier_integrity.py and
scripts/tests/test_iqm_identifier_integrity.py: one assertion per Wave 9.D
correction, content-verified against UMLS / RxNav / FDA GSRS / PubChem before
the entry is written.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HA_PATH = REPO_ROOT / "scripts" / "data" / "harmful_additives.json"


@pytest.fixture(scope="module")
def harmful_additives() -> list[dict]:
    payload = json.loads(HA_PATH.read_text())
    return payload["harmful_additives"]


def _find(entries: list[dict], entry_id: str) -> dict:
    for e in entries:
        if e.get("id") == entry_id:
            return e
    raise AssertionError(f"harmful_additives.json missing {entry_id}")


# --------------------------------------------------------------------------- #
# Wave 9.D.2 — HIGH-severity corrections (UNII + RxCUI)
# --------------------------------------------------------------------------- #


def test_add_polysorbate_20_unii_is_canonical_gsrs_record(harmful_additives):
    """ADD_POLYSORBATE_20 must use UNII 7T1F30V5YH ('POLYSORBATE 20' per
    FDA GSRS). The stored 4R0MI3KBZF returned no record from GSRS on
    2026-05-28 (deprecated or never-registered UNII). GSRS substance
    name search resolved 'Polysorbate 20' AND its synonym 'Tween 20'
    to the same UNII 7T1F30V5YH — content-verified via live GSRS REST API."""
    entry = _find(harmful_additives, "ADD_POLYSORBATE_20")
    assert (entry.get("external_ids") or {}).get("unii") == "7T1F30V5YH", (
        "ADD_POLYSORBATE_20.external_ids.unii must be 7T1F30V5YH "
        "(GSRS-registered POLYSORBATE 20), not the deprecated 4R0MI3KBZF."
    )


def test_add_senna_rxcui_cleared_to_null(harmful_additives):
    """ADD_SENNA must not carry rxcui '237929' — that RxCUI returns no
    record from RxNav (/REST/rxcui/237929/properties.json → 404 on
    2026-05-28). Cleared to null with rxcui_note documenting the
    deprecation. cui (C0330722) and unii (AK7JF626KX) remain valid and
    untouched."""
    entry = _find(harmful_additives, "ADD_SENNA")
    assert entry.get("rxcui") is None, (
        "ADD_SENNA.rxcui must be null (RxNav 404 on 237929)."
    )
    assert entry.get("rxcui_note"), (
        "ADD_SENNA must have an rxcui_note explaining the deprecation."
    )
