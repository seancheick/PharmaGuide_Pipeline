#!/usr/bin/env python3
"""
Batch 5 — `botanical_ingredients.json` (all 459 entries).

Per clinician guidance + V1 architectural decision: botanicals are
actives, not excipients. All entries assigned functional_roles=[].
"""

import json
from pathlib import Path
import pytest

DATA_PATH = Path(__file__).parent.parent / "data" / "botanical_ingredients.json"


@pytest.fixture(scope="module")
def botanicals():
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)["botanical_ingredients"]


def test_all_botanicals_have_functional_roles_field(botanicals):
    """Every entry must have the field (may be empty)."""
    missing = [e.get("id") for e in botanicals if "functional_roles" not in e]
    assert not missing, (
        f"{len(missing)} botanical entries missing functional_roles key: "
        f"{missing[:5]}"
    )


def test_all_botanicals_have_empty_roles_in_v1(botanicals):
    """V1 disposition: all 459 botanicals are actives, not excipients →
    functional_roles=[]. Per-product formulation-context (turmeric as
    colorant, vanilla as flavoring) is handled via other_ingredients
    mappings when applicable, not via the botanical entry."""
    populated = [(e.get("id"), e["functional_roles"])
                 for e in botanicals
                 if e.get("functional_roles")]
    assert not populated, (
        f"V1 invariant: botanicals should not carry functional_roles "
        f"(they're actives, not excipients). Found {len(populated)} "
        f"populated entries: {populated[:5]}"
    )


def test_botanical_total_count_unchanged(botanicals):
    assert len(botanicals) == 459
