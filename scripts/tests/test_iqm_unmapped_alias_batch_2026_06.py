"""IQM verified-alias batch (2026-06 unmapped triage).

Unmapped DSLD labels whose compound IS an existing IQM identity get aliased onto
the parent so they SCORE correctly — NOT recognized as non-scorable markers (that
would under-credit the active). Each is per-item chemistry-verified against the
existing IQM parent before aliasing.

  - "Silibinins" (plural) == the silibinin / silybin flavonolignan group
    (silibinin A + B), the milk_thistle active. "Silibinin" singular already maps
    to milk_thistle and "silybins" plural is already an alias; the plural
    "silibinins" was the actual unmapped DSLD label (per Codex review).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


@pytest.mark.parametrize("label", ["Silibinins", "silibinins", "Silibinin"])
def test_silibinin_forms_map_to_milk_thistle(enricher, label):
    iqm = enricher.databases["ingredient_quality_map"]
    m = enricher._match_quality_map(label, label, iqm)
    assert m is not None and m.get("canonical_id") == "milk_thistle", (
        f"{label!r} must map to the milk_thistle IQM active (silibinin flavonolignan); got {m}"
    )
