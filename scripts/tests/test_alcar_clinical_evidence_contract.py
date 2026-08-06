"""Clinical-evidence contract for acetyl-L-carnitine (ALCAR).

The 2026-08 zero-Evidence triage found that real ALCAR hydrochloride labels
did not link to the clinical database.  The existing record could not simply
be aliased more broadly: its clinical summary overstated condition-specific,
conflicting evidence as broad cognitive/energy efficacy.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from enrich_supplements_v3 import SupplementEnricherV3
from scoring_v4.modules.generic_evidence import EVIDENCE_LEVEL_MULTIPLIERS


DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture(scope="module")
def clinical_data() -> dict:
    return json.loads((DATA_DIR / "backed_clinical_studies.json").read_text())


@pytest.fixture(scope="module")
def alcar_entry(clinical_data: dict) -> dict:
    entries = {
        entry["id"]: entry
        for entry in clinical_data["backed_clinical_studies"]
    }
    assert "PRECLIN_ALCAR" not in entries
    return entries["INGR_ACETYL_L_CARNITINE"]


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


def test_alcar_record_is_mixed_condition_specific_human_evidence(
    alcar_entry: dict,
) -> None:
    assert alcar_entry["evidence_level"] == "ingredient-human"
    assert alcar_entry["study_type"] == "systematic_review_meta"
    assert alcar_entry["effect_direction"] == "mixed"
    assert alcar_entry["score_contribution"] == "tier_2"
    assert alcar_entry["health_goals_supported"] == ["Focus & Mental Clarity"]
    assert alcar_entry["min_clinical_dose"] == 1000
    assert alcar_entry["max_studied_clinical_dose"] == 3000
    assert alcar_entry["dose_unit"] == "mg"

    combined = " ".join(
        str(alcar_entry.get(field) or "")
        for field in (
            "notes",
            "notable_studies",
            "effect_direction_rationale",
        )
    ).lower()
    assert "very low certainty" in combined
    assert "healthy adults" in combined
    assert "condition-specific" in combined
    assert "confirm acetyl-l-carnitine efficacy" not in combined
    assert "positive_strong" not in combined


def test_alcar_pubmed_set_contains_positive_and_limiting_reviews(
    alcar_entry: dict,
) -> None:
    refs = {
        ref["pmid"]: ref
        for ref in alcar_entry["references_structured"]
    }
    assert {
        "31201734",  # Cochrane: DPN evidence very uncertain
        "31118753",  # Peripheral-neuropathy review: positive pain estimate
        "28349514",  # Cochrane: healthy cognition evidence insufficient
        "12804452",  # Cochrane: no objective dementia benefit
        "12598816",  # MCI/early-AD meta-analysis: positive estimate
    } <= refs.keys()
    assert all(ref["verification_source"] == "pubmed_eutils" for ref in refs.values())
    assert all(ref["retracted"] is False for ref in refs.values())


@pytest.mark.parametrize(
    "label_term",
    [
        "Acetyl-L-Carnitine",
        "Acetyl L Carnitine",
        "Acetyl-L-Carnitine Hydrochloride",
        "Acetyl L-Carnitine HCl",
        "ALCAR",
        "ALCAR HCl",
    ],
)
def test_alcar_exact_base_and_hydrochloride_labels_match(
    enricher: SupplementEnricherV3,
    alcar_entry: dict,
    label_term: str,
) -> None:
    assert enricher._clinical_study_match([label_term], alcar_entry) is not None


@pytest.mark.parametrize(
    "label_term",
    [
        "L-Carnitine",
        "L-Carnitine Tartrate",
        "Acetyl-L-Carnitine Arginate",
        "Acetyl-L-Carnitine Arginate Dihydrochloride",
        "Glycine Propionyl L-Carnitine Hydrochloride",
        "Acetyl L-carnitine taurinate",
    ],
)
def test_alcar_other_carnitines_and_unstudied_salts_do_not_borrow_evidence(
    enricher: SupplementEnricherV3,
    alcar_entry: dict,
    label_term: str,
) -> None:
    assert enricher._clinical_study_match([label_term], alcar_entry) is None


def test_clinical_metadata_multipliers_match_production_scorer(
    clinical_data: dict,
) -> None:
    descriptions = clinical_data["_metadata"]["evidence_level_values"]
    expected = {
        "product-human": EVIDENCE_LEVEL_MULTIPLIERS["product-human"],
        "branded-rct": EVIDENCE_LEVEL_MULTIPLIERS["branded-rct"],
        "ingredient-human": EVIDENCE_LEVEL_MULTIPLIERS["ingredient-human"],
        "strain-clinical": EVIDENCE_LEVEL_MULTIPLIERS["strain-clinical"],
        "preclinical": EVIDENCE_LEVEL_MULTIPLIERS["preclinical"],
    }
    for evidence_level, multiplier in expected.items():
        assert f"({multiplier}x multiplier)" in descriptions[evidence_level]


def test_alcar_quality_map_prose_does_not_overstate_pk_or_clinical_effect() -> None:
    iqm = json.loads((DATA_DIR / "ingredient_quality_map.json").read_text())
    canonical = iqm["l_carnitine"]["forms"]["acetyl-l-carnitine (alcar)"]
    deprecated = iqm["acetyl_l_carnitine"]["forms"]["alcar"]
    combined = " ".join(
        [
            canonical["absorption"],
            canonical["notes"],
            deprecated["absorption"],
            deprecated["notes"],
        ]
    ).lower()

    assert "direct oral bioavailability for alcar has not been established" in combined
    assert "class estimate" in combined
    assert "well-studied for cognitive function" not in combined
    assert "clinically effective for cognitive support" not in combined
    assert "head-to-head pk study" not in combined
