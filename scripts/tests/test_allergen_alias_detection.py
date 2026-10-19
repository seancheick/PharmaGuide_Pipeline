"""Every allergens.json name and alias stays an allergen in the cleaner.

2026-10-19: PR #176 removed the cleaner's fuzzy fallback; the check that it
left banned/harmful/allergen classification unchanged lived only in a session
scratchpad. scripts/audits/clean_allergen_equivalence_20261019/ holds the
repeatable corpus probe and its receipt; this test is the CI-runnable floor:
an exact reference name or alias must always classify as its own allergen.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from constants import ALLERGENS
from enhanced_normalizer import EnhancedDSLDNormalizer

ENTRIES = json.loads(ALLERGENS.read_text(encoding="utf-8"))["allergens"]


@pytest.fixture(scope="module")
def normalizer():
    return EnhancedDSLDNormalizer()


@pytest.mark.parametrize("entry", ENTRIES, ids=[e["id"] for e in ENTRIES])
def test_every_allergen_name_and_alias_classifies_as_that_allergen(normalizer, entry):
    expected = entry["standard_name"].lower()
    wrong = {}
    for term in [entry["standard_name"], *entry.get("aliases", [])]:
        info = normalizer._priority_based_classification(term, [])["allergen_info"]
        if not info["is_allergen"] or info["type"] != expected:
            wrong[term] = info
    assert not wrong
