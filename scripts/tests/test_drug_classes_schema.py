"""Schema validation tests for scripts/data/drug_classes.json (v1.0.0).

Guards the contract consumed by build_interaction_db.py when expanding
``class:X`` agents into RxCUI member lists. A missing or malformed class
must fail fast here, long before the pipeline builds bytes.

Covers:
- Required _metadata fields and version
- Presence of all 24 classes listed in INTERACTION_DB_SPEC.md §10.2 (+ anticoagulants)
- Class shape: display_name, description, member_rxcuis, member_names,
  rxclass_id, atc_codes
- member_rxcuis / member_names parallel arrays, same length, no duplicates
- RxCUIs are numeric strings; names are non-empty lowercase
- Deterministic ordering (sorted by name then rxcui)
- Minimum member count sanity (well-known classes have recognizable drugs)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

DRUG_CLASSES_PATH = Path(__file__).resolve().parent.parent / "data" / "drug_classes.json"

EXPECTED_CLASSES = {
    "class:statins",
    "class:ssris",
    "class:beta_blockers",
    "class:ace_inhibitors",
    "class:maois",
    "class:benzodiazepines",
    "class:nsaids",
    "class:anticonvulsants",
    "class:diabetes_meds",
    "class:insulins",
    "class:corticosteroids",
    "class:immunosuppressants",
    "class:hiv_protease_inhibitors",
    "class:antipsychotics",
    "class:triptans",
    "class:antacids",
    "class:calcium_channel_blockers",
    "class:diuretics",
    "class:oral_contraceptives",
    "class:sedatives",
    "class:stimulants",
    "class:antihypertensives",
    "class:b_vitamins",
    "class:anticoagulants",
    "class:fluoroquinolones",
    "class:proton_pump_inhibitors",
    "class:bisphosphonates",
    "class:antiplatelet_agents",
    "class:thiazide_diuretics",
}

# Sanity anchors: drugs we *must* be able to find in these classes.
# If the ATC upstream changes and drops one of these, we want to know.
CANONICAL_ANCHORS = {
    "class:statins": ["atorvastatin", "simvastatin", "rosuvastatin"],
    "class:ssris": ["sertraline", "fluoxetine", "escitalopram"],
    "class:beta_blockers": ["metoprolol", "propranolol", "atenolol"],
    "class:ace_inhibitors": ["lisinopril", "enalapril"],
    "class:maois": ["phenelzine"],
    "class:benzodiazepines": ["alprazolam", "diazepam", "lorazepam"],
    "class:nsaids": ["ibuprofen", "naproxen", "diclofenac"],
    "class:anticonvulsants": ["phenytoin", "carbamazepine"],
    "class:diabetes_meds": ["metformin"],
    "class:insulins": ["insulin glargine"],
    "class:corticosteroids": ["prednisone", "dexamethasone"],
    "class:hiv_protease_inhibitors": ["ritonavir"],
    "class:antipsychotics": ["haloperidol"],
    "class:triptans": ["sumatriptan"],
    "class:calcium_channel_blockers": ["amlodipine", "diltiazem"],
    "class:diuretics": ["furosemide", "hydrochlorothiazide"],
    "class:anticoagulants": ["warfarin"],
}

RXCUI_PATTERN = re.compile(r"^\d+$")


@pytest.fixture(scope="module")
def data() -> dict:
    assert DRUG_CLASSES_PATH.exists(), (
        f"{DRUG_CLASSES_PATH} missing — run scripts/api_audit/seed_drug_classes.py --live"
    )
    with DRUG_CLASSES_PATH.open() as f:
        return json.load(f)


@pytest.fixture(scope="module")
def metadata(data) -> dict:
    return data["_metadata"]


@pytest.fixture(scope="module")
def classes(data) -> dict:
    return data["classes"]


# --------------------------------------------------------------------------- #
# Metadata
# --------------------------------------------------------------------------- #


def test_metadata_block_present(data):
    assert "_metadata" in data
    assert "classes" in data


def test_metadata_schema_version(metadata):
    assert metadata["schema_version"] == "1.0.0"


def test_metadata_required_fields(metadata):
    required = {
        "schema_version",
        "description",
        "purpose",
        "last_updated",
        "total_classes",
        "total_members",
        "data_source_metadata",
    }
    missing = required - metadata.keys()
    assert not missing, f"Missing metadata fields: {missing}"


def test_metadata_data_source(metadata):
    dsm = metadata["data_source_metadata"]
    assert "NLM RxClass (ATC)" in dsm["sources"]
    assert dsm["relaSource"] == "ATC"
    assert dsm["ttys_filter"] == "IN"


def test_metadata_total_classes_matches_classes_dict(metadata, classes):
    assert metadata["total_classes"] == len(classes)


def test_metadata_total_members_matches_sum(metadata, classes):
    computed = sum(len(c["member_rxcuis"]) for c in classes.values())
    assert metadata["total_members"] == computed


# --------------------------------------------------------------------------- #
# Class coverage
# --------------------------------------------------------------------------- #


def test_all_expected_classes_present(classes):
    present = set(classes.keys())
    missing = EXPECTED_CLASSES - present
    extra = present - EXPECTED_CLASSES
    assert not missing, f"Missing classes: {missing}"
    assert not extra, f"Unexpected classes: {extra}"


def test_exactly_twenty_four_classes(classes):
    assert len(classes) == 29


# --------------------------------------------------------------------------- #
# Class shape
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("class_id", sorted(EXPECTED_CLASSES))
def test_class_has_required_fields(classes, class_id):
    c = classes[class_id]
    required = {"display_name", "description", "member_rxcuis", "member_names", "rxclass_id", "atc_codes"}
    missing = required - c.keys()
    assert not missing, f"{class_id} missing fields: {missing}"


@pytest.mark.parametrize("class_id", sorted(EXPECTED_CLASSES))
def test_class_has_non_empty_members(classes, class_id):
    c = classes[class_id]
    assert len(c["member_rxcuis"]) >= 1, f"{class_id} has zero members"
    assert len(c["member_rxcuis"]) == len(c["member_names"]), (
        f"{class_id} rxcui/name length mismatch"
    )


@pytest.mark.parametrize("class_id", sorted(EXPECTED_CLASSES))
def test_class_rxcuis_are_numeric_strings(classes, class_id):
    for rxcui in classes[class_id]["member_rxcuis"]:
        assert isinstance(rxcui, str)
        assert RXCUI_PATTERN.match(rxcui), f"{class_id}: non-numeric rxcui {rxcui!r}"


@pytest.mark.parametrize("class_id", sorted(EXPECTED_CLASSES))
def test_class_names_are_lowercase_non_empty(classes, class_id):
    for name in classes[class_id]["member_names"]:
        assert isinstance(name, str)
        assert name.strip(), f"{class_id}: empty name"
        assert name == name.lower(), f"{class_id}: name not lowercase: {name!r}"


@pytest.mark.parametrize("class_id", sorted(EXPECTED_CLASSES))
def test_class_rxcuis_unique(classes, class_id):
    rxcuis = classes[class_id]["member_rxcuis"]
    assert len(rxcuis) == len(set(rxcuis)), f"{class_id}: duplicate rxcuis"


@pytest.mark.parametrize("class_id", sorted(EXPECTED_CLASSES))
def test_class_sorted_deterministically(classes, class_id):
    """Names must be sorted (with rxcui tiebreak) for byte-identical builds."""
    c = classes[class_id]
    pairs = list(zip(c["member_names"], c["member_rxcuis"]))
    assert pairs == sorted(pairs), f"{class_id}: members not sorted by (name, rxcui)"


@pytest.mark.parametrize("class_id", sorted(EXPECTED_CLASSES))
def test_class_atc_codes_non_empty(classes, class_id):
    codes = classes[class_id]["atc_codes"]
    assert isinstance(codes, list) and codes, f"{class_id}: atc_codes missing or empty"


# --------------------------------------------------------------------------- #
# Canonical anchor drugs — sanity guard against upstream drift
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("class_id,expected", sorted(CANONICAL_ANCHORS.items()))
def test_canonical_anchors_present(classes, class_id, expected):
    names = " | ".join(classes[class_id]["member_names"])
    for drug in expected:
        assert drug in names, (
            f"{class_id} is missing canonical anchor {drug!r}; "
            f"RxClass ATC may have changed — re-run seed_drug_classes.py --live"
        )
