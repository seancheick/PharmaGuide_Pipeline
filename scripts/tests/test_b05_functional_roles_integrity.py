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
    # 488 after 2026-05-22 SB-4 boswellia §8.5 cleanup: boswellia_carterii added
    # — Somali frankincense (UNII R9XLF1R1WM), distinct species from B. serrata
    # (UNII 4PW41QCO2M) that owns the bonus pathway in
    # standardized_botanicals.boswellia. Migrated 'frankincense extract' alias
    # out of the species-precise B. serrata entry into this plain identity home.
    # 486 after merge-time dedup: ecklonia_radiata and ecklonia_kurome were
    # added as stubs (no UNII) in 2026-04 Sprint D2 (commit c0e1450f) and
    # then re-added as proper canonicals with UNIIs in SB-3d. The merge
    # of sb/3d into main retained both copies. The stub copies were dropped
    # in favor of the SB-3d UNII-bearing canonicals. Net: -2 entries.
    # 493 after 2026-05-22 MO-1 batch: 7 plain-identity herb entries
    # relocated from standardized_botanicals.json (no documented
    # standardization marker → no A5b bonus pathway). Moved: american_ginseng
    # (UNII 8W75VCV53Q), astaxanthin (UNII 8XPW32PR7I), bee_pollen
    # (UNII 3729L8MA2C), black_cohosh (UNII K73E24S6X9), black_musli
    # (UNII 715B59598O), blackberry (UNII 8A6OMU3I8L), caraway
    # (UNII W2FH8O2BBE). See scripts/audits/sb_moveout_inventory_20260522/.
    # 500 after 2026-05-22 MO-2 batch: 7 more plain-identity entries
    # relocated. Moved: blue_green_algae (UNII 49VG1X560X),
    # century_plant (UNII 024852X0VD), d_mannose (UNII PHA4727WTP),
    # damiana (UNII 812R0W1I3K), elder_flower (UNII 07V4DX094T),
    # galdieria (UNII 2E5CL9KYZ8), grapefruit_seed (UNII 598D944HOL).
    # 507 after 2026-05-22 MO-3 batch: 7 more relocated. Moved:
    # huperzine_a (UNII 0111871I23), inulin (UNII JOS53KRJ01),
    # l_theanine (UNII 8021PR16QO), mulungu (UNII NU815YHH1S),
    # onion (UNII 492225Q21H), phosphatidylserine (UNII 394XK0IH40),
    # pine_bark_extract (UNII 50JZ5Z98QY — dropped 'pycnogenol' alias
    # to preserve future PROMOTE_V6_BRANDED routing for Pycnogenol®).
    # 514 after 2026-05-22 MO-4 batch: 7 more relocated. Moved: saffron
    # (UNII E849G4X5YJ), slippery_elm (UNII 63POE2M46Y), spinach
    # (UNII 6WO75C6WVB), baobab (UNII D5B40OA634 — NEW), black_sesame
    # (UNII JD6YPE8XLT — NEW), mallow (UNII I01732476C — NEW), polygala
    # (UNII F6BP27WG28 — NEW). The 4 NEW UNIIs were added during this
    # batch (verified via scripts/data/fda_unii_cache.json).
    # 521 after 2026-05-22 MO-5 batch: 7 more relocated, all with NEW
    # UNIIs filled during move. Moved: african_mango (6V9H6XWU5P),
    # akarkara (E3L74Y262L), horsetail (1L0VKZ185E), muira_puama
    # (G582QI158H), rosehip (P5R39F12N2), lion_s_mane (Y62T8P9AAP —
    # fungal), camu_camu (EAG5BC91EK — 15 aliases).
    assert len(botanicals) == 521
