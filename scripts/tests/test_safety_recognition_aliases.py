"""Safety-recognition alias coverage (2026-06, updated 2026-09-21).

'Disodium EDTA' (chelator/preservative, harmful_additives ADD_DISODIUM_EDTA) is
recognized, but the common label word-order variant 'EDTA Disodium' (8 real
occurrences in unmapped triage artifacts) was not an alias, so it surfaced as a
false identity gap. Lock the word-order variant onto the existing safety entry.

2026-09-21 update: the approved Phase-3 clinical policy made standalone oral
Edetate Disodium a banned_recalled policy identity
(BANNED_NON_ROUTINE_CHELATOR_EDETATE_DISODIUM, verdict BLOCKED, reason
NON_ROUTINE_CHELATOR), authored for the declared-ACTIVE role only. Because
banned_recalled takes priority over harmful_additives in the safety lookup, both
word-order variants now resolve to that policy identity instead of the
excipient-class entry. The guard this test exists for is unchanged: these label
forms must still be SAFETY-RECOGNIZED (a false identity gap is what it prevents),
and the excipient classification is retained in harmful_additives for the
inactive role (see cross_db_overlap_allowlist.json).

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
    # 2026-09-21: the declared-active non-routine-chelator policy identity now
    # owns these variants (banned_recalled outranks harmful_additives). The
    # calcium form must resolve to its OWN identity, never to this one.
    assert hit.get("standard_name") == "Edetate Disodium"


def test_calcium_disodium_edta_resolves_to_its_own_distinct_identity(normalizer):
    """The two chelating salts must never collapse into one safety identity."""
    for label in ("Calcium Disodium EDTA", "Calcium Disodium Edetate"):
        key = normalizer.matcher.preprocess_text(label)
        hit = normalizer._safety_exact_lookup.get(key)
        assert hit is not None, f"{label!r} is not recognized by the safety lookup"
        assert hit.get("standard_name") == "Edetate Calcium Disodium", label
        assert hit.get("id") != "BANNED_NON_ROUTINE_CHELATOR_EDETATE_DISODIUM", label
