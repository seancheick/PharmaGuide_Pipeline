#!/usr/bin/env python3
"""Regression pins for verified CUI corrections.

Originally these were all in standardized_botanicals.json; the MO-1..MO-6
move-out batches relocated many plain-identity entries to
botanical_ingredients.json (CUIs preserved through the moves). This test
now reads from BOTH files so the CUI invariants survive the relocations.
"""

import json
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
STD_PATH = DATA_DIR / "standardized_botanicals.json"
BOT_PATH = DATA_DIR / "botanical_ingredients.json"


def _rows_by_id() -> dict[str, dict]:
    """Combined std + bot lookup. Entries with the same id (rare)
    prefer std side (where the original CUI assertions targeted)."""
    rows = {}
    for row in json.loads(BOT_PATH.read_text())["botanical_ingredients"]:
        rows[row["id"]] = row
    # std overrides bot if duplicate id exists (preserves original intent)
    for row in json.loads(STD_PATH.read_text())["standardized_botanicals"]:
        rows[row["id"]] = row
    return rows


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
    # NOTE: 'garlic' id was retired in DM-3 (merged into bot.garlic_bulb).
    # The CUI assertion has moved to test_dm3_id_mapped_merge.py if needed.
    assert rows["ginger_extract"].get("cui") == "C1879327"            # Zingiber officinale (Plant)
    assert rows["ginkgo_biloba"].get("cui") == "C0330206"             # Ginkgo biloba (Plant)
    assert rows["goldenseal"].get("cui") == "C3500453"                # Hydrastis canadensis whole preparation
    assert rows["gotu_kola"].get("cui") == "C2948088"                 # Centella asiatica extract
    assert rows["gynostemma"].get("cui") == "C0950016"                # Gynostemma pentaphyllum (Plant)
    assert rows["horsetail"].get("cui") == "C0331745"                 # Equisetum (Plant)
    assert rows["lemon_balm"].get("cui") == "C1008143"                # Melissa officinalis (Plant)
    assert rows["linden_flower"].get("cui") == "C0771627"             # Tilia extract
    assert rows["nettle"].get("cui") == "C0600609"                    # Urtica dioica (Plant)
    # NOTE: 'oregano' id retired in DM-3 (merged into bot.oregano_herb).
    assert rows["peppermint"].get("cui") == "C0697157"                # Mentha piperita (Plant)
    assert rows["pumpkin_seed"].get("cui") == "C0487824"              # Cucurbita pepo (Plant)
    assert rows["red_clover"].get("cui") == "C0330783"                # Trifolium pratense (Plant)
    assert rows["rosehip"].get("cui") == "C1030673"                   # Rosa canina (Plant)
    assert rows["sarsaparilla"].get("cui") == "C1014795"              # Smilax (Plant)
    assert rows["shiitake"].get("cui") == "C0752328"                  # Lentinula edodes (Fungus)
    assert rows["spirulina"].get("cui") == "C1005844"                 # Arthrospira (Bacterium)
    assert rows["tart_cherry"].get("cui") == "C0330657"               # Prunus cerasus (Plant)
    assert rows["thyme"].get("cui") == "C0697238"                     # Thymus vulgaris (Plant)
    # NOTE: 'wheatgrass' id retired in DM-3 (merged into bot.wheatgrass_powder).
    assert rows["wild_yam"].get("cui") == "C0697076"                  # Dioscorea villosa (Plant)
    # NOTE: 'yellow_dock' id retired in DM-3 (merged into bot.yellow_dock_root).


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
