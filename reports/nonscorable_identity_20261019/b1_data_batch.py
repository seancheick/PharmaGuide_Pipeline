"""#196 audit B1 data batch (October 20, 2026). Run from the repo root with $PG_PYTHON."""
import sys
sys.path.insert(0, "scripts")
import data_batch  # noqa: E402

BOT = "scripts/data/botanical_ingredients.json"
bot = data_batch.load(BOT)
entries = {e["id"]: e for e in bot["botanical_ingredients"]}

# century_plant is Agave americana (UNII 024852X0VD). "agave extract" names only the
# genus; through the cleaner's suffix stripping it turned 31062's "Agave powder"
# (DSLD group "Agave", genus only) into Agave americana. The species stays unknown.
century = entries["century_plant"]
assert "agave extract" in century["aliases"]
century["aliases"].remove("agave extract")
century["last_updated"] = "2026-10-20"

# 59766 prints "Sawasabi Wasabi powder" in DSLD group "Japanese Horseradish" (wasabi);
# "Wasabi powder" already maps to wasabi_root. Unmatched, the cleaner took the
# identity from the marker form "Total Isothiocyanate".
wasabi = entries["wasabi_root"]
assert "sawasabi wasabi powder" not in [a.lower() for a in wasabi["aliases"]]
wasabi["aliases"].append("sawasabi wasabi powder")
wasabi["last_updated"] = "2026-10-20"

data_batch.save(BOT, bot)
