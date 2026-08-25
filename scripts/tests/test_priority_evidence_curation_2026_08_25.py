"""Content and matcher locks for the 2026-08-25 priority evidence batch."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from enrich_supplements_v3 import SupplementEnricherV3


DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "backed_clinical_studies.json"


@pytest.fixture(scope="module")
def entries() -> dict[str, dict]:
    payload = json.loads(DATA_PATH.read_text())
    return {entry["id"]: entry for entry in payload["backed_clinical_studies"]}


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


def test_inositol_record_preserves_conflicting_guideline_evidence(entries: dict[str, dict]) -> None:
    entry = entries["INGR_INOSITOL"]

    assert entry["study_type"] == "systematic_review_meta"
    assert entry["evidence_level"] == "ingredient-human"
    assert entry["effect_direction"] == "mixed"
    assert entry["effect_direction_confidence"] == "high"
    assert {ref["pmid"] for ref in entry["references_structured"]} == {
        "35477841",
        "36703143",
        "38163998",
    }
    assert all(ref["verification_source"] == "pubmed_eutils" for ref in entry["references_structured"])
    assert all(ref["retracted"] is False for ref in entry["references_structured"])


@pytest.mark.parametrize(
    "label_term",
    ["Inositol", "Myo-Inositol", "D-Chiro-Inositol", "40:1 Inositol Blend"],
)
def test_inositol_record_matches_reviewed_isomers(
    enricher: SupplementEnricherV3,
    entries: dict[str, dict],
    label_term: str,
) -> None:
    assert enricher._clinical_study_match([label_term], entries["INGR_INOSITOL"]) is not None


@pytest.mark.parametrize(
    "label_term",
    ["Inositol Hexanicotinate", "Inositol Hexaphosphate", "IP6"],
)
def test_inositol_record_does_not_cross_into_other_compounds(
    enricher: SupplementEnricherV3,
    entries: dict[str, dict],
    label_term: str,
) -> None:
    entry = entries["INGR_INOSITOL"]
    assert enricher._clinical_study_match([label_term, "Inositol"], entry) is None


def test_l_arginine_record_is_endpoint_and_dose_scoped(entries: dict[str, dict]) -> None:
    entry = entries["INGR_L_ARGININE"]

    assert entry["study_type"] == "systematic_review_meta"
    assert entry["evidence_level"] == "ingredient-human"
    assert entry["effect_direction"] == "mixed"
    assert entry["min_clinical_dose"] == 1500
    assert entry["max_studied_clinical_dose"] == 12000
    assert entry["dose_unit"] == "mg"
    assert {ref["pmid"] for ref in entry["references_structured"]} == {
        "22137067",
        "32370176",
        "34967840",
    }


@pytest.mark.parametrize(
    "label_term",
    ["L-Arginine", "L-Arginine Base", "Free-Form Arginine", "Micronized L-Arginine"],
)
def test_l_arginine_record_matches_reviewed_free_form(
    enricher: SupplementEnricherV3,
    entries: dict[str, dict],
    label_term: str,
) -> None:
    assert enricher._clinical_study_match([label_term], entries["INGR_L_ARGININE"]) is not None


@pytest.mark.parametrize(
    "label_term",
    [
        "L-Arginine AKG",
        "Arginine Alpha-Ketoglutarate",
        "Arginine Nitrate",
        "Inositol-Stabilized Arginine Silicate",
        "Nitrosigine",
        "L-Arginine HCl",
        "Arginine Aspartate",
    ],
)
def test_l_arginine_record_does_not_borrow_to_unreviewed_forms(
    enricher: SupplementEnricherV3,
    entries: dict[str, dict],
    label_term: str,
) -> None:
    entry = entries["INGR_L_ARGININE"]
    assert enricher._clinical_study_match([label_term, "L-Arginine"], entry) is None

