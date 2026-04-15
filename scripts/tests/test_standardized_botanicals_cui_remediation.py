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

    assert rows["artichoke"].get("cui") == "C0453108"                 # Artichoke (Food)
    assert rows["astragalus"].get("cui") == "C0330845"                # Astragalus Plant
    assert rows["blue_green_algae"].get("cui") == "C0304057"          # Blue-green algae agent
    assert rows["burdock_root"].get("cui") == "C0873127"              # Burdock preparation
    assert rows["chaga"].get("cui") == "C1079248"                     # Inonotus obliquus (Fungus)
    assert rows["cinnamon"].get("cui") == "C0939899"                  # cinnamon preparation
    assert rows["cissus_quadrangularis"].get("cui") == "C1078516"     # Cissus quadrangularis (Plant)
    assert rows["cucumber"].get("cui") == "C0973457"                  # Cucumber - dietary (Food)
    assert rows["echinacea_angustifolia"].get("cui") == "C0697080"    # Echinacea angustifolia (Plant)
    assert rows["elderberry"].get("cui") == "C0331059"                # Sambucus nigra (Plant)
    assert rows["elderberry_extract"].get("cui") == "C3486741"        # Sambucus nigra flower extract
    assert rows["eucalyptus"].get("cui") == "C0015148"                # Eucalyptus (Plant)
    assert rows["fennel"].get("cui") == "C0553175"                    # Foeniculum vulgare (Plant)
    assert rows["feverfew"].get("cui") == "C0697198"                  # Tanacetum parthenium (Plant)
    assert rows["garlic"].get("cui") == "C0017102"                    # Allium sativum (Plant)
    assert rows["ginger_extract"].get("cui") == "C1879327"            # Zingiber officinale (Plant)
    assert rows["ginkgo_biloba"].get("cui") == "C0330206"             # Ginkgo biloba (Plant)
    assert rows["goldenseal"].get("cui") == "C3500453"                # Hydrastis canadensis whole preparation
    assert rows["gotu_kola"].get("cui") == "C2948088"                 # Centella asiatica extract
    assert rows["gynostemma"].get("cui") == "C0950016"                # Gynostemma pentaphyllum (Plant)
    assert rows["horsetail"].get("cui") == "C0331745"                 # Equisetum (Plant)
    assert rows["lemon_balm"].get("cui") == "C1008143"                # Melissa officinalis (Plant)
    assert rows["linden_flower"].get("cui") == "C0771627"             # Tilia extract
    assert rows["nettle"].get("cui") == "C0600609"                    # Urtica dioica (Plant)
    assert rows["oregano"].get("cui") == "C0946715"                   # Origanum vulgare (Plant)
    assert rows["peppermint"].get("cui") == "C0697157"                # Mentha piperita (Plant)
    assert rows["pumpkin_seed"].get("cui") == "C0487824"              # Cucurbita pepo (Plant)
    assert rows["red_clover"].get("cui") == "C0330783"                # Trifolium pratense (Plant)
    assert rows["rosehip"].get("cui") == "C1030673"                   # Rosa canina (Plant)
    assert rows["sarsaparilla"].get("cui") == "C1014795"              # Smilax (Plant)
    assert rows["shiitake"].get("cui") == "C0752328"                  # Lentinula edodes (Fungus)
    assert rows["spirulina"].get("cui") == "C1005844"                 # Arthrospira (Bacterium)
    assert rows["tart_cherry"].get("cui") == "C0330657"               # Prunus cerasus (Plant)
    assert rows["thyme"].get("cui") == "C0697238"                     # Thymus vulgaris (Plant)
    assert rows["wheatgrass"].get("cui") == "C1123020"                # Triticum aestivum (Plant)
    assert rows["wild_yam"].get("cui") == "C0697076"                  # Dioscorea villosa (Plant)
    assert rows["yellow_dock"].get("cui") == "C1200905"               # Rumex crispus


def test_verified_standardized_botanicals_branded_nulls():
    """8 branded concentrates/extracts with no single UMLS concept."""
    rows = _rows_by_id()

    branded_nulls = [
        "bil_max", "blue_max", "cran_max", "flowens", "pacran",
        "cranrx", "ksm_66_ashwagandha", "life_s_dha",
    ]
    for eid in branded_nulls:
        assert rows[eid].get("cui") is None, f"{eid} should have null cui (branded extract)"


def test_verified_standardized_botanicals_shogaols_fill():
    """Shogaols compound class filled with verified CUI."""
    rows = _rows_by_id()

    assert rows["shogaols"].get("cui") == "C0074460"  # shogaol
