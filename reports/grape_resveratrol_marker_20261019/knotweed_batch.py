"""Japanese knotweed keeps its plant identity (Sean, ADR-0005 amendment, 2026-10-19).
Hu Zhang is the root and rhizome of Polygonum cuspidatum (PMID 33388645), a plant whose
constituents include resveratrol, emodin and polydatin: its names belong to the plant entry,
not the resveratrol compound. Marker gate: the same declared-percentage standard as grape.
Run from the repo root with $PG_PYTHON."""
import sys
sys.path.insert(0, "scripts")
import data_batch  # noqa: E402

PLANT_NAMES = ["hu zhang", "hu zhang extract", "hu zhang root extract", "hu zhang hydroethanolic extract",
               "Reynoutria japonica root extract"]

IQM = "scripts/data/ingredient_quality_map.json"
iqm = data_batch.load(IQM)
form = iqm["resveratrol"]["forms"]["resveratrol (unspecified)"]
for name in PLANT_NAMES:
    form["aliases"].remove(name)
data_batch.save(IQM, iqm)

BOT = "scripts/data/botanical_ingredients.json"
bot = data_batch.load(BOT)
[knotweed] = [e for e in bot["botanical_ingredients"] if e["id"] == "japanese_knotweed"]
have = {a.lower() for a in knotweed["aliases"]}
knotweed["aliases"] += [n for n in PLANT_NAMES if n.lower() not in have]
data_batch.save(BOT, bot)

BMC = "scripts/data/botanical_marker_contributions.json"
bmc = data_batch.load(BMC)
[contrib] = bmc["botanicals"]["japanese_knotweed"]["delivers"]
contrib["min_standardization_pct_required"] = 1.0
contrib["notes"] = ("Polygonum cuspidatum (Japanese knotweed) is the commercial source of resveratrol. Raw root "
                    "contains 0.1-1.5% resveratrol; standardized extracts are 50-98% pure. Credit only when the "
                    "label declares a resveratrol percentage of at least 1% (the same standard as grape); the "
                    "identity stays japanese_knotweed.")
data_batch.save(BMC, bmc)
