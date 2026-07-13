"""Source-descriptor / branded-additive recognition batch (2026-06 unmapped triage).

Unmapped DSLD labels whose identity is an EXISTING non-scorable excipient/additive
— added the missing label aliases so they recognize (non-scorable; no scoring
over-credit, these are excipients/penalty additives, not actives). Collision check
showed all three targets already existed.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


@pytest.mark.parametrize(
    "label,source,entry_id",
    [
        ("Millers Bran", "other_ingredients", "OI_WHEAT_BRAN"),                 # miller's bran = wheat bran
        ("Calcium Caseinate and Gelatin", "other_ingredients", "NHA_CALCIUM_CASEINATE"),  # casein/gelatin excipient blend
        ("Litesse Polydextrose", "harmful_additives", "ADD_POLYDEXTROSE"),      # Litesse = branded polydextrose
        ("Litesse Polydextrose Fiber", "harmful_additives", "ADD_POLYDEXTROSE"),
        ("Polyphenolic Flavones", "other_ingredients", "NHA_BERGAMOT_POLYPHENOLIC_FLAVONES_MARKER"),
        ("Glycoside Conjugates", "other_ingredients", "NHA_WITHANOLIDE_GLYCOSIDE_CONJUGATES_MARKER"),
        ("40% MCTs", "other_ingredients", "NHA_MCT_PERCENT_COMPOSITION_DESCRIPTOR"),
        ("Bioactive Ribetril-A", "other_ingredients", "PII_BRAND_COMPLEX_DESCRIPTOR"),
    ],
)
def test_source_descriptor_recognized(enricher, label, source, entry_id):
    r = enricher._is_recognized_non_scorable(label, label)
    assert r is not None, f"{label!r} should be recognized (non-scorable); got None"
    assert r.get("recognition_source") == source and r.get("matched_entry_id") == entry_id, (
        f"{label!r} should recognize as {source}/{entry_id}; got {r}"
    )
