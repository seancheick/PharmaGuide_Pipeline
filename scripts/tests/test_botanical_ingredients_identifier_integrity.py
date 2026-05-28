"""Per-entry identifier integrity tests for botanical_ingredients.json.

Pattern mirrors the IQM / banned_recalled / harmful_additives /
other_ingredients integrity tests: one assertion per Wave 9.F correction,
content-verified against live UMLS / RxNav / FDA GSRS / PubChem before the
entry is written.

Wave 9.F.2 — Retired-CUI propagation. A cluster of stored CUIs in
botanical_ingredients.json no longer resolve in live UMLS (retired/merged
concepts). The correct, currently-resolving concept already existed in the
sibling standardized_botanicals.json (locked by
test_standardized_botanicals_cui_remediation.py) but was never propagated to
the botanical_ingredients.json copy when the MO move-out batches ran. Each
replacement below was confirmed live on 2026-05-28: the old CUI returns
NOT FOUND from the UMLS /CUI/<id> endpoint, and the new CUI resolves to the
correct botanical concept (semantic type Plant or extract-substance).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BOT_PATH = REPO_ROOT / "scripts" / "data" / "botanical_ingredients.json"


@pytest.fixture(scope="module")
def botanicals() -> list[dict]:
    payload = json.loads(BOT_PATH.read_text())
    return payload["botanical_ingredients"]


def _find(entries: list[dict], entry_id: str) -> dict:
    for e in entries:
        if e.get("id") == entry_id:
            return e
    raise AssertionError(f"botanical_ingredients.json missing {entry_id}")


# --------------------------------------------------------------------------- #
# Wave 9.F.2 — Retired CUI → verified resolving concept (11 entries)
# --------------------------------------------------------------------------- #
#
# (entry_id, retired_cui, correct_cui, umls_name)
_WAVE_9F2_RETIRED_CUI = [
    ("echinacea_angustifolia", "C0013479", "C0697080", "Echinacea angustifolia (Plant)"),
    ("eucalyptus", "C0015143", "C0015148", "Eucalyptus (Plant)"),
    ("feverfew", "C0015636", "C0697198", "Tanacetum parthenium (Plant)"),
    ("ginger_extract", "C0017149", "C1879327", "Zingiber officinale (Plant)"),
    ("goldenseal", "C0330520", "C3500453", "Hydrastis canadensis whole preparation"),
    ("gotu_kola", "C0007037", "C2948088", "Centella asiatica extract"),
    ("gynostemma", "C0949828", "C0950016", "Gynostemma pentaphyllum (Plant)"),
    ("marigold", "C0938046", "C1000850", "Tagetes erecta (Plant)"),
    ("peppermint", "C0025757", "C0697157", "Mentha piperita (Plant)"),
    ("red_clover", "C0040718", "C0330783", "Trifolium pratense (Plant)"),
    ("thyme", "C0040081", "C0697238", "Thymus vulgaris (Plant)"),
    # Sibling plant-part / oil entries that carried the SAME retired CUI as
    # their parent species entry above. Each fixed to the matching verified
    # concept (leaf/root/flower → species Plant CUI; the globulus oil entry
    # → its own species concept C1005038).
    ("eucalyptus_leaf_oil", "C0015143", "C1005038", "Eucalyptus globulus (Plant)"),
    ("ginger_root", "C0017149", "C1879327", "Zingiber officinale (Plant)"),
    ("jiaogulan_leaf", "C0949828", "C0950016", "Gynostemma pentaphyllum (Plant)"),
    ("peppermint_leaf", "C0025757", "C0697157", "Mentha piperita (Plant)"),
    ("red_clover_flower", "C0040718", "C0330783", "Trifolium pratense (Plant)"),
]


@pytest.mark.parametrize("entry_id,retired_cui,correct_cui,umls_name", _WAVE_9F2_RETIRED_CUI)
def test_wave_9f2_retired_cui_replaced(
    botanicals, entry_id, retired_cui, correct_cui, umls_name
):
    """The retired CUI (UMLS /CUI/<id> → NOT FOUND on 2026-05-28) is replaced
    with the currently-resolving concept that already exists in
    standardized_botanicals.json for the same botanical."""
    e = _find(botanicals, entry_id)
    assert e.get("cui") == correct_cui, (
        f"{entry_id}.cui must be {correct_cui} (UMLS '{umls_name}'), not the "
        f"retired {retired_cui} which no longer resolves in UMLS."
    )
