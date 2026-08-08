"""Clinical-evidence contracts for complete BCAA mixtures."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402
from scoring_v4.modules.generic_evidence import score_evidence  # noqa: E402


DATA_PATH = SCRIPTS_DIR / "data" / "backed_clinical_studies.json"
BCAA_IDS = {"l_leucine", "l_isoleucine", "l_valine"}


@pytest.fixture(scope="module")
def entries() -> dict[str, dict]:
    payload = json.loads(DATA_PATH.read_text())
    return {entry["id"]: entry for entry in payload["backed_clinical_studies"]}


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


def _active(canonical_id: str, quantity_mg: float) -> dict:
    name = canonical_id.replace("_", " ").title()
    return {
        "name": name,
        "standardName": name,
        "raw_source_text": name,
        "canonical_id": canonical_id,
        "raw_category": "amino acid",
        "ingredientGroup": "Amino Acid",
        "mapped": True,
        "quantity": quantity_mg,
        "unit": "mg",
    }


def _enrichment_product(name: str, rows: list[dict]) -> dict:
    return {"fullName": name, "product_name": name, "activeIngredients": rows}


def _bcaa_matches(enricher: SupplementEnricherV3, name: str, rows: list[dict]) -> list[dict]:
    evidence = enricher._collect_evidence_data(_enrichment_product(name, rows))
    return [
        match
        for match in evidence["clinical_matches"]
        if match["id"] == "INGR_BRANCHED_CHAIN_AMINO_ACIDS"
    ]


def _scoring_product(rows: list[dict], match: dict, servings_per_day: float = 1.0) -> dict:
    scoring_rows = [
        {
            "name": row["name"],
            "standard_name": row["standardName"],
            "raw_source_text": row["raw_source_text"],
            "canonical_id": row["canonical_id"],
            "mapped": True,
            "quantity": row["quantity"],
            "unit": row["unit"],
        }
        for row in rows
    ]
    return {
        "status": "active",
        "product_name": "BCAA test product",
        "form_factor": "powder",
        "supplement_type": {"type": "sports_nutrition"},
        "serving_basis": {
            "min_servings_per_day": servings_per_day,
            "max_servings_per_day": servings_per_day,
            "servings_per_day_source": "directions",
        },
        "ingredient_quality_data": {
            "ingredients_scorable": scoring_rows,
            "ingredients": scoring_rows,
        },
        "evidence_data": {"clinical_matches": [match]},
    }


def test_bcaa_record_is_narrow_and_content_verified(entries: dict[str, dict]) -> None:
    entry = entries["INGR_BRANCHED_CHAIN_AMINO_ACIDS"]

    assert entry["category"] == "sports_performance"
    assert entry["effect_direction"] == "positive_weak"
    assert entry["study_type"] == "systematic_review_meta"
    assert entry["min_clinical_dose"] == 5000
    assert entry["dose_unit"] == "mg"
    assert set(entry["aggregate_canonical_ids"]) == BCAA_IDS
    assert "total_enrollment" not in entry
    assert "registry_completed_trials_count" not in entry
    assert {ref["pmid"] for ref in entry["references_structured"]} == {
        "38625669", "38241335", "36235655"
    }
    assert all(ref["verification_source"] == "pubmed_eutils" for ref in entry["references_structured"])
    assert all(ref["retracted"] is False for ref in entry["references_structured"])

    text = json.dumps(entry).lower()
    for stale in ("18820", "eptifibatide", "hyperbilirubinemia", "breast cancer", "cirrhosis"):
        assert stale not in text


def test_complete_bcaa_triad_matches_once(enricher: SupplementEnricherV3) -> None:
    rows = [_active("l_leucine", 3000), _active("l_isoleucine", 1500), _active("l_valine", 1500)]

    matches = _bcaa_matches(enricher, "BCAA 2:1:1", rows)

    assert len(matches) == 1
    assert set(matches[0]["aggregate_canonical_ids"]) == BCAA_IDS
    assert matches[0]["max_studied_clinical_dose"] == 29300


def test_standalone_isoleucine_does_not_borrow_mixture_evidence(
    enricher: SupplementEnricherV3,
) -> None:
    assert not _bcaa_matches(
        enricher,
        "L-Isoleucine 2,000 mg",
        [_active("l_isoleucine", 2000)],
    )


def test_eaa_formula_does_not_borrow_bcaa_mixture_evidence(
    enricher: SupplementEnricherV3,
) -> None:
    rows = [
        _active("l_leucine", 1400),
        _active("l_isoleucine", 800),
        _active("l_valine", 800),
        _active("l_lysine", 700),
        _active("l_histidine", 300),
    ]

    assert not _bcaa_matches(enricher, "Essential Amino Acids EAA", rows)


def test_opaque_bcaa_name_without_complete_triad_is_not_enough(
    enricher: SupplementEnricherV3,
) -> None:
    assert not _bcaa_matches(
        enricher,
        "BCAA Proprietary Blend",
        [_active("bcaa", 5000)],
    )


def test_bcaa_plus_non_eaa_coingredient_remains_eligible(
    enricher: SupplementEnricherV3,
) -> None:
    rows = [
        _active("l_leucine", 3000),
        _active("l_isoleucine", 1500),
        _active("l_valine", 1500),
        _active("l_glutamine", 1000),
    ]

    assert len(_bcaa_matches(enricher, "BCAA + Glutamine", rows)) == 1


def test_scoring_sums_the_complete_daily_bcaa_dose(entries: dict[str, dict]) -> None:
    match = dict(entries["INGR_BRANCHED_CHAIN_AMINO_ACIDS"])
    match.update({
        "matched_term": "Branched Chain Amino Acids",
        "ingredient": "Branched Chain Amino Acids",
    })
    rows = [_active("l_leucine", 1500), _active("l_isoleucine", 750), _active("l_valine", 750)]

    once = score_evidence(_scoring_product(rows, match, servings_per_day=1))
    twice = score_evidence(_scoring_product(rows, match, servings_per_day=2))

    assert "SUB_CLINICAL_DOSE_DETECTED" in once["metadata"]["flags"]
    assert "SUB_CLINICAL_DOSE_DETECTED" not in twice["metadata"]["flags"]
    assert twice["score"] > once["score"] > 0.0


def test_scoring_receives_the_reviewed_bcaa_upper_range(entries: dict[str, dict]) -> None:
    match = dict(entries["INGR_BRANCHED_CHAIN_AMINO_ACIDS"])
    match.update({
        "matched_term": "Branched Chain Amino Acids",
        "ingredient": "Branched Chain Amino Acids",
    })
    rows = [
        _active("l_leucine", 45000),
        _active("l_isoleucine", 22500),
        _active("l_valine", 22500),
    ]

    payload = score_evidence(_scoring_product(rows, match))

    assert "SUPRA_CLINICAL_DOSE" in payload["metadata"]["flags"]
