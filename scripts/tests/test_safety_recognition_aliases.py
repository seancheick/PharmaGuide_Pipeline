"""Safety-recognition alias coverage (2026-06).

'Disodium EDTA' (chelator/preservative, harmful_additives ADD_DISODIUM_EDTA) is
recognized, but the common label word-order variant 'EDTA Disodium' (8 real
occurrences in unmapped triage artifacts) was not an alias, so it surfaced as a
false identity gap. Lock the word-order variant onto the existing safety entry.

Identity is NOT conferred by this: canonical_id never comes from safety DBs —
that invariant is enforced in test_identity_safety_separation.py.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enhanced_normalizer import EnhancedDSLDNormalizer


@pytest.fixture(scope="module")
def normalizer():
    return EnhancedDSLDNormalizer()


@pytest.mark.parametrize("label", ["EDTA Disodium", "Disodium EDTA"])
def test_edta_word_order_variants_are_safety_recognized(normalizer, label):
    key = normalizer.matcher.preprocess_text(label)
    hit = normalizer._safety_exact_lookup.get(key)
    assert hit is not None, f"{label!r} is not recognized by the safety lookup"
    assert hit.get("standard_name") == "Disodium EDTA"
