"""Per-entry CUI integrity tests — one assertion per Wave-6.Y correction.

Each test:
  1. Locks the IQM parent's `cui` to the clinician-authorized value.
  2. Locks `scripts/data/curated_interactions/curated_interactions_v1.json` to
     not reference the prior (wrong) CUI as `agent2_id`.

Pattern (per CLAUDE.md "small batches, decomposed problems" and
"write the failing regression assertion … BEFORE the fix"):

  - Failing tests land in this file before the IQM / curated_interactions
    edits are applied for that entry.
  - When the edit is applied, the assertion flips green.
  - Each correction is its own atomic commit.

Source of authority for the corrections: clinician review of
`reports/iqm_identifier_sweep/reviewed_queue.csv` produced by
`scripts/api_audit/iqm_identifier_sweep.py`. The wrong-CUI evidence for each
test is content-verified via UMLS REST API (see per_parent/<id>.json snapshot
for the cached response).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
IQM_PATH = REPO_ROOT / "scripts" / "data" / "ingredient_quality_map.json"
CI_PATH = REPO_ROOT / "scripts" / "data" / "curated_interactions" / "curated_interactions_v1.json"


@pytest.fixture(scope="module")
def iqm():
    return json.loads(IQM_PATH.read_text())


@pytest.fixture(scope="module")
def curated_interactions():
    return json.loads(CI_PATH.read_text())


def _agent2_ids(curated: dict) -> list[str]:
    """Collect every agent2_id value across all entries in curated_interactions_v1.json."""
    out: list[str] = []
    # Schema: top-level object with 'entries' or array of rules; iterate generously.
    if isinstance(curated, dict):
        for v in curated.values():
            if isinstance(v, list):
                for row in v:
                    if isinstance(row, dict) and "agent2_id" in row:
                        out.append(str(row["agent2_id"]))
    return out


# --------------------------------------------------------------------------- #
# Batch 1 — Seed fixes from reviewed_queue.csv (status=fix_cui)
# --------------------------------------------------------------------------- #


def test_coq10_cui_is_canonical_ubidecarenone(iqm):
    """coq10 must use UMLS C0041536 (ubidecarenone) — the Organic Chemical /
    Pharmacologic Substance CUI for the actual compound. C1843920 was the
    'COENZYME Q10 DEFICIENCY' Disease-or-Syndrome CUI (hallucination caught
    by the 2026-05-27 IQM identifier sweep, strict-mode Disease guard)."""
    assert iqm["coq10"]["cui"] == "C0041536", (
        "coq10.cui must be the substance CUI (C0041536, ubidecarenone), "
        "not the disease CUI (C1843920, 'COENZYME Q10 DEFICIENCY')."
    )


def test_no_curated_interaction_uses_coq10_disease_cui(curated_interactions):
    """No row in curated_interactions_v1.json may have agent2_id=C1843920
    (the 'COENZYME Q10 DEFICIENCY' disease CUI). Any such row would resolve
    to the wrong concept through `verify_interactions.build_iqm_cui_index`.
    """
    bad = "C1843920"
    matches = [a for a in _agent2_ids(curated_interactions) if a == bad]
    assert not matches, (
        f"Found {len(matches)} curated_interactions rows still using the "
        f"disease CUI {bad}. They must be updated to C0041536 (ubidecarenone)."
    )

def test_5_htp_cui_is_canonical_5_hydroxytryptophan(iqm):
    """5_htp must use UMLS C0000578 (5-hydroxytryptophan) — the Organic
    Chemical CUI for the compound. C5815882 was the 'Natrol Melatonin + 5-HTP'
    combo product CUI (hallucination caught by the 2026-05-27 sweep, strict-
    mode multi-compound combo guard via the ' + ' marker in the candidate name)."""
    assert iqm["5_htp"]["cui"] == "C0000578", (
        "5_htp.cui must be the generic compound CUI (C0000578, "
        "5-hydroxytryptophan), not the branded combo CUI (C5815882, "
        "'Natrol Melatonin + 5-HTP')."
    )


def test_no_curated_interaction_uses_5_htp_combo_cui(curated_interactions):
    """No row may reference C5815882, the branded combo product CUI for 5-HTP.
    """
    bad = "C5815882"
    matches = [a for a in _agent2_ids(curated_interactions) if a == bad]
    assert not matches, (
        f"Found {len(matches)} curated_interactions rows still using the "
        f"branded combo CUI {bad}. They must be updated to C0000578."
    )


# --------------------------------------------------------------------------- #
# Batch 2A — Wrong-concept CUI corrections (no curated_interactions impact)
# --------------------------------------------------------------------------- #


def test_acacia_catechu_cui_is_canonical_plant(iqm):
    """acacia_catechu must use C1135823 (Acacia catechu, Plant semantic type).
    C0949533 resolved to 'Australian bat lyssavirus' — a virus, not the plant.
    Caught by no-token-overlap guard."""
    assert iqm["acacia_catechu"]["cui"] == "C1135823", (
        "acacia_catechu.cui must be C1135823 (Acacia catechu, Plant), not "
        "C0949533 ('Australian bat lyssavirus')."
    )
