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
    # 481 after identity_bioactivity_split Phase 2: broccoli_sprout added.
    # 482 after Phase 8: marigold (Tagetes erecta) added — source botanical for
    # lutein marker contribution. Previously implicit via IQM marigold aliases
    # under lutein.forms[]; now an explicit botanical canonical per policy.
    # 483 after 2026-05-22 standardized_botanicals v6 cleanup: coffee_bean_plain
    # added — plain coffee bean / seed identity for unstandardized labels that
    # were previously routing through standardized_botanicals.green_coffee_bean
    # without marker evidence. See scripts/audits/standardized_botanicals_eligibility_20260522/REPORT.md
    # and commit eff29b3d.
    # 487 after 2026-05-22 SB-3d brown-algae §7.5/§8.5 cleanup: split four
    # species out of the previously over-broad kelp_powder entry —
    # ecklonia_radiata (UNII QVY0X8DRIA), ecklonia_kurome (UNII 802YF989GT),
    # laminaria_digitata (UNII 15E7C67EE8), saccharina_latissima
    # (UNII 68CMP2MB55, formerly Laminaria saccharina). +4 entries.
    assert len(botanicals) == 487
