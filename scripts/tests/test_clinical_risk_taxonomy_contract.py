"""Metadata contract for `clinical_risk_taxonomy.json`.

This file is the canonical taxonomy for interaction-rule processing in
``enrich_supplements_v3._collect_interaction_profile``. It carries 7
top-level arrays — each enumerates a distinct dimension of the
interaction model:

* ``conditions`` — recognized medical conditions (hypertension, kidney_disease, …)
* ``drug_classes`` — recognized drug class buckets (anticoagulants, statins, …)
* ``severity_levels`` — severity scale (contraindicated → info)
* ``evidence_levels`` — evidence quality (established → no_data)
* ``profile_flags`` — user-profile flags (pregnant, lactating, …)
* ``product_forms`` — supplement forms (capsule, softgel, …)
* ``sources`` — citation source IDs (DailyMed, NCCIH, …)

Convention (UNIQUE among the multi-array files):
    ``_metadata.total_entries`` = SUM of all 7 arrays. This file uses a
    sum convention because each array contributes equally to the taxonomy
    — no single array is "primary".

If you add an entry to ANY array, bump ``total_entries`` by 1.
"""

import json
from pathlib import Path

import pytest

PATH = Path(__file__).parent.parent / "data" / "clinical_risk_taxonomy.json"

REQUIRED_ARRAYS = (
    "conditions",
    "drug_classes",
    "severity_levels",
    "evidence_levels",
    "profile_flags",
    "product_forms",
    "sources",
)


@pytest.fixture(scope="module")
def blob():
    return json.loads(PATH.read_text(encoding="utf-8"))


def test_total_entries_is_sum_of_all_taxonomy_arrays(blob):
    expected = sum(
        len(v) for k, v in blob.items() if k != "_metadata" and isinstance(v, list)
    )
    actual = blob["_metadata"]["total_entries"]
    assert actual == expected, (
        f"_metadata.total_entries={actual} but sum of all 7 taxonomy "
        f"arrays = {expected}. Bump total_entries to {expected}."
    )


def test_all_seven_taxonomy_arrays_present(blob):
    """Defensive: ``_collect_interaction_profile`` reads each of these by
    name. If any disappears, the interaction engine loses a dimension."""
    missing = [a for a in REQUIRED_ARRAYS if a not in blob]
    assert not missing, f"required taxonomy arrays missing: {missing}"
    for a in REQUIRED_ARRAYS:
        assert isinstance(blob[a], list), f"{a!r} must be a list"
        assert blob[a], f"{a!r} cannot be empty"
