#!/usr/bin/env python3
"""Data batch: curated aliases that named a different substance (ADR-0005, receipts in research.md).

Run once from the repo root with $PG_PYTHON. Each patch asserts the state it changes.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
from data_batch import load, save  # noqa: E402

DATA = REPO / "scripts" / "data"


def move(src: list, dst: list, values: list) -> None:
    for value in values:
        assert value in src, value
        src.remove(value)
        if value.casefold() not in {v.casefold() for v in dst}:
            dst.append(value)


def drop(src: list, values: list) -> None:
    for value in values:
        assert value in src, value
        src.remove(value)


def add(dst: list, values: list) -> None:
    for value in values:
        assert value.casefold() not in {v.casefold() for v in dst}, value
        dst.append(value)


iqm_path = DATA / "ingredient_quality_map.json"
iqm = load(iqm_path)
# 1. NCBI Taxonomy 44688: L. lactis subsp. lactis bv. diacetylactis is L. lactis, not L. cremoris.
move(iqm["lactococcus_cremoris"]["forms"]["lactococcus cremoris (unspecified)"]["aliases"],
     iqm["lactococcus_lactis"]["forms"]["lactococcus lactis (unspecified)"]["aliases"],
     ["Lactococcus lactis subsp. lactis biovar diacetylactis", "L. lactis diacetylactis",
      "Lactococcus diacetylactis", "Lactococcus lactis biovar diacetylactis"])
# 2. ElevATP is ancient peat + apple extract (FutureCeuticals), not shilajit.
drop(iqm["shilajit"]["forms"]["fulvic acid"]["aliases"], ["elevATP", "elevatp ancient peat", "ancient peat and apple extract"])
# 3. Olive juice/vegetation-water extract is from the fruit (DSLD PlantPart: fruit).
move(iqm["olive_leaf"]["forms"]["olive leaf extract standardized"]["aliases"],
     iqm["olive_fruit_extract"]["forms"]["olive fruit extract standardized"]["aliases"],
     ["olive juice extract"])
add(iqm["olive_fruit_extract"]["forms"]["olive fruit extract standardized"]["aliases"], ["olive water extract"])
# 4. Sweet wormwood / Artemisia annua / qinghao is the plant; artemisinin (qinghaosu) is its compound.
drop(iqm["artemisinin"]["aliases"], ["sweet wormwood", "artemisia annua"])
drop(iqm["artemisinin"]["forms"]["artemisinin (unspecified)"]["aliases"],
     ["sweet wormwood extract", "artemisia annua extract", "artemisia annua leaf extract",
      "sweet annie extract", "qinghao"])
save(iqm_path, iqm)

bot_path = DATA / "botanical_ingredients.json"
bot = load(bot_path)
by_id = {e["id"]: e for e in bot["botanical_ingredients"]}
drop(by_id["olive_leaf_powder"]["aliases"], ["olive juice extract", "Olive Water extract"])
add(by_id["sweet_wormwood_herb"]["aliases"],
    ["sweet wormwood", "artemisia annua extract", "artemisia annua leaf extract", "sweet annie extract", "qinghao"])
save(bot_path, bot)

oi_path = DATA / "other_ingredients.json"
oi = load(oi_path)
by_id = {e["id"]: e for e in oi["other_ingredients"]}
add(by_id["PII_ELEVATP_BRANDED_BLEND"]["aliases"], ["elevatp ancient peat", "ancient peat and apple extract"])
save(oi_path, oi)
