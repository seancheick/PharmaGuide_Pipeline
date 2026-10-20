"""Species-swap alias batch (October 19, 2026): printed spellings of the cleaner's own plant.
Run from the repo root with $PG_PYTHON."""
import sys
sys.path.insert(0, "scripts")
import data_batch  # noqa: E402

IQM = "scripts/data/ingredient_quality_map.json"
BOT = "scripts/data/botanical_ingredients.json"


def add(aliases, new):
    for alias in new:
        assert alias.lower() not in {a.lower() for a in aliases}, alias
        aliases.append(alias)


iqm = data_batch.load(IQM)
add(iqm["wheatgrass"]["aliases"], ["wheat grass juice powder", "organic wheat grass juice powder", "wheatgrass juice"])
add(iqm["barley_grass"]["aliases"], ["barley grass juice"])
data_batch.save(IQM, iqm)

bot = data_batch.load(BOT)
[pepper] = [e for e in bot["botanical_ingredients"] if e["id"] == "green_bell_pepper"]
add(pepper["aliases"], ["green bell pepper powder"])
data_batch.save(BOT, bot)
