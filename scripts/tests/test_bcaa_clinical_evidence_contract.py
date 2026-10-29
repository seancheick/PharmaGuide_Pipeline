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
from scoring_v4.modules.generic_dose import score_dose  # noqa: E402
from scoring_v4.modules.generic_helpers import unbenchmarked_dose_credit  # noqa: E402


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
    source_rows = [{**row, "raw_source_path": f"ingredientRows[{index}]",
                    "source_section": "active", "cleaner_row_role": "active_scorable",
                    "score_eligible_by_cleaner": True, "scoreable_identity": True,
                    "identity_disposition": "clean", "role_classification": "active_scorable",
                    "dose_class": "therapeutic_mass",
                    "raw_taxonomy": {"category": row["raw_category"], "forms": []}}
                   for index, row in enumerate(rows)]
    return {"fullName": name, "product_name": name, "activeIngredients": source_rows,
            "ingredient_quality_data": {"ingredients": source_rows, "ingredients_scorable": source_rows}}


def _bcaa_matches(enricher: SupplementEnricherV3, name: str, rows: list[dict]) -> list[dict]:
    evidence = enricher._collect_evidence_data(_enrichment_product(name, rows))
    return [
        match
        for match in evidence["clinical_matches"]
        if match["id"] == "INGR_BRANCHED_CHAIN_AMINO_ACIDS"
    ]


def _scoring_product(
    rows: list[dict],
    match: dict,
    servings_per_day: float = 1.0,
    name: str = "BCAA test product",
) -> dict:
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
        "product_name": name,
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


def test_general_bcaa_dose_is_neutral_at_different_daily_exposures(entries: dict[str, dict]) -> None:
    match = dict(entries["INGR_BRANCHED_CHAIN_AMINO_ACIDS"])
    match.update({
        "matched_term": "Branched Chain Amino Acids",
        "ingredient": "Branched Chain Amino Acids",
    })
    rows = [_active("l_leucine", 1500), _active("l_isoleucine", 750), _active("l_valine", 750)]

    once_product = _scoring_product(rows, match, servings_per_day=1)
    twice_product = _scoring_product(rows, match, servings_per_day=2)
    once = score_dose(once_product)
    twice = score_dose(twice_product)

    # Source amounts remain descriptive. They establish no general minimum
    # and no proportional efficacy or adequacy curve.
    assert "aggregate_clinical_benchmark" not in once["metadata"]
    assert "aggregate_clinical_benchmark" not in twice["metadata"]
    assert once["score"] == twice["score"] == unbenchmarked_dose_credit()
    # Evidence strength is independent of the formula amount.
    assert score_evidence(once_product)["score"] == score_evidence(twice_product)["score"]


def test_bcaa_formula_and_another_declared_purpose_are_averaged_equally(
    entries: dict[str, dict],
) -> None:
    match = dict(entries["INGR_BRANCHED_CHAIN_AMINO_ACIDS"])
    match.update({
        "matched_term": "Branched Chain Amino Acids",
        "ingredient": "Branched Chain Amino Acids",
    })
    rows = [
        _active("l_leucine", 3000),
        _active("l_isoleucine", 1500),
        _active("l_valine", 1500),
        _active("l_glutamine", 1000),
    ]

    payload = score_dose(_scoring_product(rows, match, name="BCAA + L-Glutamine"))

    assert payload["metadata"]["purpose_ingredient_count"] == 2
    assert "aggregate_clinical_benchmark" not in payload["metadata"]
    assert payload["metadata"]["unbenchmarked_purpose_ingredients"] == ["bcaa", "l_glutamine"]
    # Glutamine has no benchmark: the shared unbenchmarked neutral (V4.1 Step 4).
    assert payload["score"] == pytest.approx(
        unbenchmarked_dose_credit(), abs=1e-4
    )


def test_studied_bcaa_high_amount_does_not_become_a_dose_ceiling(entries: dict[str, dict]) -> None:
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

    payload = score_dose(_scoring_product(rows, match))

    # Highest studied amount is preserved as a fact, never a Dose ceiling.
    assert entries["INGR_BRANCHED_CHAIN_AMINO_ACIDS"]["max_studied_clinical_dose"] == 29300
    assert "aggregate_clinical_benchmark" not in payload["metadata"]
    assert payload["score"] == unbenchmarked_dose_credit()


@pytest.mark.parametrize('declared', [False, True])
def test_bcaa_group_purpose_does_not_depend_on_a_clinical_record(declared):
    rows = [_active('l_leucine', 3000), _active('l_isoleucine', 1500),
            _active('l_valine', 1500), _active('l_glutamine', 1000)]
    product = _scoring_product(rows, {}, name='BCAA + L-Glutamine' if declared else 'L-Glutamine')
    product.pop('evidence_data')
    result = score_dose(product)
    assert result['metadata']['purpose_ingredient_count'] == (2 if declared else 1)
    contributions = result['metadata']['dose_contributions']
    assert ('bcaa' in {row['ingredient'] for row in contributions}) is declared
    assert result['score'] == unbenchmarked_dose_credit()


@pytest.mark.parametrize('hidden', [False, True])
def test_missing_bcaa_member_requires_positive_label_hiding_for_neutral(hidden):
    rows = [_active('l_leucine', 3000), _active('l_isoleucine', 1500),
            _active('l_valine', 1500)]
    product = _scoring_product(rows, {})
    row = product['ingredient_quality_data']['ingredients_scorable'][-1]
    row['quantity'] = None
    if hidden:
        row['isNestedIngredient'] = True
    result = score_dose(product)
    if hidden:
        assert result['score'] == unbenchmarked_dose_credit()
    else:
        assert result['score'] is None
        assert result['metadata']['assessment_status'] == 'incomplete'
