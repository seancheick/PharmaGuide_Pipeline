"""KSM-66 trial credit stays attached to its actual root-extract exposure."""

from copy import deepcopy
import json

import pytest

from clinical_applicability import reviewed_entries
from scoring_v4.modules.generic_evidence import resolved_clinical_matches, score_evidence
from scoring_v4.modules.generic_dose import score_dose


def ksm_product(amount: float, *, with_powder: bool = False, multiple_refs: bool = False) -> dict:
    extract = {
        "name": "KSM-66 Ashwagandha root extract", "standard_name": "Ashwagandha",
        "canonical_id": "ashwagandha", "quantity": amount, "unit": "mg",
        "raw_source_path": "ingredientRows[0]", "mapped": True, "bio_score": 12,
        "source_section": "active", "cleaner_row_role": "active_scorable",
        "role_classification": "active_scorable", "score_eligible_by_cleaner": True,
        "scoreable_identity": True, "dose_class": "quantified_mass",
    }
    rows = [extract]
    if with_powder:
        rows.append({**extract, "name": "Ashwagandha root powder", "quantity": 600,
                     "raw_source_path": "ingredientRows[1]"})
    entry = deepcopy(reviewed_entries()["BRAND_KSM66"])
    entry.update(
        ingredient=extract["name"], matched_term="ashwagandha",
        matched_canonical_ids=["ashwagandha"],
        matched_source_row_refs=[row["raw_source_path"] for row in rows]
        if multiple_refs else ["ingredientRows[0]"],
    )
    return {
        "fullName": "KSM-66 root extract test", "form_factor_canonical": "capsule",
        "activeIngredients": deepcopy(rows),
        "ingredient_quality_data": {"ingredients_scorable": rows},
        "evidence_data": {"clinical_matches": [entry]},
    }


def test_ksm66_reference_is_limited_to_verified_root_extract_stress_trials() -> None:
    entry = reviewed_entries()["BRAND_KSM66"]
    assert entry["total_enrollment"] == 124
    assert entry["min_clinical_dose"] == 250
    assert entry["max_studied_clinical_dose"] == 600
    assert entry["dose_unit"] == "mg"
    assert entry["study_type"] == "rct_multiple"
    assert entry["effect_direction"] == "positive_strong"
    assert entry["applicability"]["scope"] == "ingredient"
    assert "dose_unit" not in entry["applicability"]
    assert set(entry["endpoint_relevance_tags"]) == {"stress_mood", "sleep"}
    assert "registry_completed_trials_count" not in entry
    assert {ref["pmid"] for ref in entry["references_structured"]} == {"23439798", "32021735"}
    text = json.dumps(entry).lower()
    for unsupported in ("strength", "libido", "increase energy", "mental clarity", "muscle_recovery"):
        assert unsupported not in text


@pytest.mark.parametrize("with_powder,multiple_refs", [(False, False), (True, False), (True, True)])
def test_reviewed_ksm66_regimen_does_not_borrow_plain_ashwagandha_powder(
    with_powder: bool, multiple_refs: bool
) -> None:
    product = ksm_product(100, with_powder=with_powder, multiple_refs=multiple_refs)
    matches, _ = resolved_clinical_matches(product)
    assert len(matches) == 1  # A known low dose is graded, not erased as an unknown form.
    assert matches[0]["matched_source_row_refs"] == ["ingredientRows[0]"]
    evidence = score_evidence(product, apply_primary_floor=True)
    dose = score_dose(product)
    assert evidence["score"] > 0
    assert not evidence["metadata"]["flags"]
    assert dose["metadata"]["botanical_dose_band"] == "disclosed_no_reference"
    # The source amount is retained, while the retired study-dose window
    # cannot classify it as clinically insufficient or award efficacy points.
    from scoring_v4.exposure import row_exposure
    from scoring_v4.modules.generic_helpers import unbenchmarked_dose_credit
    own_row=product['ingredient_quality_data']['ingredients_scorable'][0]
    exposure=row_exposure(product, own_row, basis='daily', unit='mg')
    assert exposure.per_serving_amount == 100.0
    assert exposure.benchmark_amount == 100.0
    assert exposure.frequency_defaulted is True
    # A plain-powder companion has no completed general benchmark review.
    # The branded extract's completed review cannot complete its sibling.
    assert dose["score"] == (0.0 if with_powder else unbenchmarked_dose_credit())
    assert dose["metadata"]["botanical_dose"] == {
        "benchmark": "unresolved" if with_powder else "absent"
    }



@pytest.mark.parametrize("amount", [250, 600])
def test_studied_ksm66_dose_remains_eligible(amount: float) -> None:
    product = ksm_product(amount)
    matches, _ = resolved_clinical_matches(product)
    assert matches[0]["applicability_assessment"]["status"] == "applicable"
    scored = score_dose(product)
    assert scored["metadata"]["botanical_dose_band"] == "disclosed_no_reference"


def test_branded_study_cannot_apply_to_plain_powder_source_row() -> None:
    product = ksm_product(600)
    for rows in (product["activeIngredients"], product["ingredient_quality_data"]["ingredients_scorable"]):
        rows[0]["name"] = "Ashwagandha root powder"
    assert resolved_clinical_matches(product)[0] == []
