#!/usr/bin/env python3
"""Data batch from the cohort replay: aliases the label-named rule made authoritative wrongly.

Receipts in research.md. Run once from the repo root with $PG_PYTHON.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
from data_batch import load, save  # noqa: E402

DATA = REPO / "scripts" / "data"


def drop(values: list, names: list) -> None:
    for name in names:
        assert name in values, name
        values.remove(name)


# BioVin (OPC grape extract) and BioVin Advanced (red-wine grape extract standardized to 5%
# trans-resveratrol) are grape extracts. Every corpus row names the brand as the ingredient
# (forms "Red Grape Extract", "Grape Whole Extract"); none uses it as a resveratrol form.
iqm_path = DATA / "ingredient_quality_map.json"
iqm = load(iqm_path)
drop(iqm["resveratrol"]["forms"]["trans-resveratrol"]["aliases"],
     ["BioVin", "biovin advanced red wine extract", "biovin advanced"])
save(iqm_path, iqm)

bot_path = DATA / "botanical_ingredients.json"
bot = load(bot_path)
grape = next(e for e in bot["botanical_ingredients"] if e["id"] == "grape")
for name in ("biovin advanced", "biovin advanced red wine extract"):
    assert name not in [a.casefold() for a in grape["aliases"]]
    grape["aliases"].append(name)
save(bot_path, bot)

# "Cabbage palm" names Sabal palmetto and acai (Euterpe oleracea), and only historically
# saw palmetto (UF/IFAS FR357); the corpus row (64382) is in a berry blend DSLD groups as Acai.
std_path = DATA / "standardized_botanicals.json"
std = load(std_path)
key = next(k for k in std if k != "_metadata")
saw = next(e for e in std[key] if e.get("id") == "saw_palmetto")
drop(saw["aliases"], ["cabbage palm"])
save(std_path, std)
