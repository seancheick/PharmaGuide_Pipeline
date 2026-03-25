#!/usr/bin/env python3
"""Regression pins for verified standardized_botanicals CUI corrections."""

import json
from pathlib import Path


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "standardized_botanicals.json"


def _rows_by_id() -> dict[str, dict]:
    rows = json.loads(DATA_PATH.read_text())["standardized_botanicals"]
    return {row["id"]: row for row in rows}


def test_verified_standardized_botanicals_invalid_cui_replacements():
    """37 retired CUIs replaced with current UMLS concepts (semantic types verified)."""
    rows = _rows_by_id()

    assert rows["artichoke"]["CUI"] == "C0453108"                 # Artichoke (Food)
    assert rows["astragalus"]["CUI"] == "C0330845"                # Astragalus Plant
    assert rows["blue_green_algae"]["CUI"] == "C0304057"          # Blue-green algae agent
    assert rows["burdock_root"]["CUI"] == "C0873127"              # Burdock preparation
    assert rows["chaga"]["CUI"] == "C1079248"                     # Inonotus obliquus (Fungus)
    assert rows["cinnamon"]["CUI"] == "C0939899"                  # cinnamon preparation
    assert rows["cissus_quadrangularis"]["CUI"] == "C1078516"     # Cissus quadrangularis (Plant)
    assert rows["cucumber"]["CUI"] == "C0973457"                  # Cucumber - dietary (Food)
    assert rows["echinacea_angustifolia"]["CUI"] == "C0697080"    # Echinacea angustifolia (Plant)
    assert rows["elderberry"]["CUI"] == "C0331059"                # Sambucus nigra (Plant)
    assert rows["elderberry_extract"]["CUI"] == "C3486741"        # Sambucus nigra flower extract
    assert rows["eucalyptus"]["CUI"] == "C0015148"                # Eucalyptus (Plant)
    assert rows["fennel"]["CUI"] == "C0553175"                    # Foeniculum vulgare (Plant)
    assert rows["feverfew"]["CUI"] == "C0697198"                  # Tanacetum parthenium (Plant)
    assert rows["garlic"]["CUI"] == "C0017102"                    # Allium sativum (Plant)
    assert rows["ginger_extract"]["CUI"] == "C1879327"            # Zingiber officinale (Plant)
    assert rows["ginkgo_biloba"]["CUI"] == "C0330206"             # Ginkgo biloba (Plant)
    assert rows["goldenseal"]["CUI"] == "C3500453"                # Hydrastis canadensis whole preparation
    assert rows["gotu_kola"]["CUI"] == "C2948088"                 # Centella asiatica extract
    assert rows["gynostemma"]["CUI"] == "C0950016"                # Gynostemma pentaphyllum (Plant)
    assert rows["horsetail"]["CUI"] == "C0331745"                 # Equisetum (Plant)
    assert rows["lemon_balm"]["CUI"] == "C1008143"                # Melissa officinalis (Plant)
    assert rows["linden_flower"]["CUI"] == "C0771627"             # Tilia extract
    assert rows["nettle"]["CUI"] == "C0600609"                    # Urtica dioica (Plant)
    assert rows["oregano"]["CUI"] == "C0946715"                   # Origanum vulgare (Plant)
    assert rows["peppermint"]["CUI"] == "C0697157"                # Mentha piperita (Plant)
    assert rows["pumpkin_seed"]["CUI"] == "C0487824"              # Cucurbita pepo (Plant)
    assert rows["red_clover"]["CUI"] == "C0330783"                # Trifolium pratense (Plant)
    assert rows["rosehip"]["CUI"] == "C1030673"                   # Rosa canina (Plant)
    assert rows["sarsaparilla"]["CUI"] == "C1014795"              # Smilax (Plant)
    assert rows["shiitake"]["CUI"] == "C0752328"                  # Lentinula edodes (Fungus)
    assert rows["spirulina"]["CUI"] == "C1005844"                 # Arthrospira (Bacterium)
    assert rows["tart_cherry"]["CUI"] == "C0330657"               # Prunus cerasus (Plant)
    assert rows["thyme"]["CUI"] == "C0697238"                     # Thymus vulgaris (Plant)
    assert rows["wheatgrass"]["CUI"] == "C1123020"                # Triticum aestivum (Plant)
    assert rows["wild_yam"]["CUI"] == "C0697076"                  # Dioscorea villosa (Plant)
    assert rows["yellow_dock"]["CUI"] == "C1200905"               # Rumex crispus


def test_verified_standardized_botanicals_branded_nulls():
    """8 branded concentrates/extracts with no single UMLS concept."""
    rows = _rows_by_id()

    branded_nulls = [
        "bil_max", "blue_max", "cran_max", "flowens", "pacran",
        "cranrx", "ksm_66_ashwagandha", "life_s_dha",
    ]
    for eid in branded_nulls:
        assert rows[eid].get("CUI") is None, f"{eid} should have null CUI (branded extract)"


def test_verified_standardized_botanicals_shogaols_fill():
    """Shogaols compound class filled with verified CUI."""
    rows = _rows_by_id()

    assert rows["shogaols"]["CUI"] == "C0074460"  # shogaol
