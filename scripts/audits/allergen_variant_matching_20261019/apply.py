#!/usr/bin/env python3
"""Allergen negative_match_terms batch (2026-10-19). Receipts: research.md."""
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS))
import data_batch

PATH = SCRIPTS / "data" / "allergens.json"
HIGHLY_REFINED = "highly refined"  # FDA allergen Q&A Ed. 5, D.9: RBD oils exempt
NEGATIVE_TERMS = {
    "ALLERGEN_MILK": ["milk thistle", "coconut milk", "coconut cream", "dairy digestive", "biocore dairy"],
    "ALLERGEN_TREE_NUTS": ["horse chestnut", "tropical almond", "almond mushroom", HIGHLY_REFINED],
    "ALLERGEN_WHEAT": ["gluten enzyme", "mannitol", "xylitol", HIGHLY_REFINED],  # polyols: protein-free (Q&A B.8)
    "ALLERGEN_RYE": ["rye flower", "pollen"],
    "ALLERGEN_MUSTARD": ["mustard greens"],
    "ALLERGEN_FISH": [HIGHLY_REFINED],
    "ALLERGEN_SOY": [HIGHLY_REFINED],
    "ALLERGEN_PEANUTS": [HIGHLY_REFINED],
    "ALLERGEN_SESAME": [HIGHLY_REFINED],
}
OLD_FISH_NOTE = ("they are flagged via the enricher's allergen cross-reference, "
                 "not normalizer interception.")
NEW_FISH_NOTE = ("the enricher flags them by matching an alias as a whole word in the "
                 "row name or its forms (\"Purified Fish Oil\", form \"Fish Oil\"), never "
                 "from the canonical identity alone. FDA guidance D.9 exempts highly "
                 "refined (refined, bleached, deodorized) oils, so a row labelled "
                 "\"highly refined\" is not flagged.")

blob = data_batch.load(PATH)
by_id = {e["id"]: e for e in blob["allergens"]}
for allergen_id, terms in NEGATIVE_TERMS.items():
    entry = by_id[allergen_id]
    assert "match_rules" not in entry, allergen_id
    entry["match_rules"] = {"negative_match_terms": terms}
fish = by_id["ALLERGEN_FISH"]
assert fish["notes"].count(OLD_FISH_NOTE) == 1
fish["notes"] = fish["notes"].replace(OLD_FISH_NOTE, NEW_FISH_NOTE)
print(data_batch.save(PATH, blob))
