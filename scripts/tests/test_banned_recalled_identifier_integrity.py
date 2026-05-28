"""Per-entry identifier integrity tests for banned_recalled_ingredients.json.

Pattern mirrors scripts/tests/test_iqm_identifier_integrity.py: one assertion
per Wave 9.C correction, content-verified against UMLS / RxNav / PubChem
before the entry is written.

Each test locks the entry's stored identifier to the clinician-authorized
value (here: agent-authorized per the user's 2026-05-28 direction to
"use api tools and deep research to validate and advance until we
complete" on banned_recalled_ingredients.json).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BR_PATH = REPO_ROOT / "scripts" / "data" / "banned_recalled_ingredients.json"


@pytest.fixture(scope="module")
def banned_recalled() -> list[dict]:
    payload = json.loads(BR_PATH.read_text())
    return payload["ingredients"]


def _find(entries: list[dict], entry_id: str) -> dict:
    for e in entries:
        if e.get("id") == entry_id:
            return e
    raise AssertionError(f"banned_recalled_ingredients.json missing {entry_id}")


# --------------------------------------------------------------------------- #
# Wave 9.C.3 — HIGH-severity CUI/RxCUI corrections (3 entries)
# --------------------------------------------------------------------------- #


def test_banned_igf1_cui_is_canonical_substance(banned_recalled):
    """BANNED_IGF1 must use C0021665 ('Insulin-Like Growth Factor I',
    semantic types Amino Acid/Peptide/Protein, Biologically Active Substance).
    C5674892 resolved to 'primary insulin-like growth factor-1 (IGF-1)
    deficiency' (Disease or Syndrome) — the disease state, not the protein.
    Caught by the strict-mode Disease guard 2026-05-28."""
    entry = _find(banned_recalled, "BANNED_IGF1")
    assert entry["cui"] == "C0021665", (
        "BANNED_IGF1.cui must be C0021665 (the IGF-1 protein substance), "
        "not C5674892 (primary IGF-1 deficiency, a disease state)."
    )
