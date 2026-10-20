#!/usr/bin/env python3
"""Fish-species and krill phrase_match_terms batch (2026-10-19). Receipts: research.md."""
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS))
import data_batch

PATH = SCRIPTS / "data" / "allergens.json"
PHRASE_TERMS = {
    # FDA allergen Q&A Ed. 5 B.10 examples, plus FDA Seafood List Type V market names
    # found on corpus labels (cusk, haddock, hake, pollock, sole, herring, dogfish,
    # anchovy, sardine). Plurals are the "Contains:" statement spellings.
    "ALLERGEN_FISH": [
        "anchovies", "anchovy", "cod", "cusk", "dogfish", "flounder", "grouper", "haddock",
        "hake", "herring", "mackerel", "pollock", "salmon", "sardine", "sardines", "shark",
        "sole", "tilapia", "trout", "tuna",
    ],
    # FDA Seafood List: Krill (Euphausia spp.) Type I(C), crustacean.
    "ALLERGEN_CRUSTACEANS": ["crustaceans", "krill"],
}
# Non-fish phrases that contain a species word (none occurs in the corpus yet):
# Erythronium americanum is a plant; "sole source/ingredient" and
# "salmon-colored" are wording, not fish.
FISH_NEGATIVE_TERMS = ["trout lily", "sole source", "sole ingredient", "salmon-colored", "salmon colored"]
OLD_FISH_NOTE = ("the enricher flags them by matching an alias as a whole word in the "
                 "row name or its forms (\"Purified Fish Oil\", form \"Fish Oil\"), never "
                 "from the canonical identity alone.")
NEW_FISH_NOTE = ("the enricher flags them by matching an alias, or a species in "
                 "match_rules.phrase_match_terms (FDA requires the species on labels, e.g. "
                 "\"Cod Liver Oil\", gelatin \"(cod, haddock, pollock)\"), as a whole word in "
                 "the row name, its forms or a Contains statement, never from the canonical "
                 "identity alone.")

blob = data_batch.load(PATH)
by_id = {e["id"]: e for e in blob["allergens"]}
for allergen_id, terms in PHRASE_TERMS.items():
    rules = by_id[allergen_id].setdefault("match_rules", {})
    assert "phrase_match_terms" not in rules, allergen_id
    rules["phrase_match_terms"] = terms
    by_id[allergen_id]["last_updated"] = "2026-10-19"
fish = by_id["ALLERGEN_FISH"]
fish["match_rules"]["negative_match_terms"] = [
    *fish["match_rules"]["negative_match_terms"], *FISH_NEGATIVE_TERMS,
]
assert fish["notes"].count(OLD_FISH_NOTE) == 1
fish["notes"] = fish["notes"].replace(OLD_FISH_NOTE, NEW_FISH_NOTE)
print(data_batch.save(PATH, blob))
