#!/usr/bin/env python3
"""Salivarius species-name aliases move off the HA-118 strain form (2026-10-29). Receipts: research.md."""
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS))
import data_batch

PATH = SCRIPTS / "data" / "ingredient_quality_map.json"
SPECIES_ALIASES = [
    "ligilactobacillus salivarius",
    "ligilactobacillus salivarius supplement",
    "lactobacillus salivarius strain",
    "lactobacillus salivarius strain supplement",
]

blob = data_batch.load(PATH)
forms = blob["lactobacillus_salivarius"]["forms"]
strain = forms["lactobacillus salivarius ha-118"]
generic = forms["generic lactobacillus salivarius"]
for alias in SPECIES_ALIASES:
    assert strain["aliases"].count(alias) == 1, alias
    assert alias not in generic["aliases"], alias
    strain["aliases"].remove(alias)
    generic["aliases"].append(alias)
print(data_batch.save(PATH, blob))
