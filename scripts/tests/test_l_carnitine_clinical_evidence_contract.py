"""Clinical-evidence and identity contracts for L-carnitine."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from enrich_supplements_v3 import SupplementEnricherV3
from scoring_v4.modules.generic_evidence import score_evidence


DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture(scope="module")
def clinical_entries() -> dict[str, dict]:
    payload = json.loads(
        (DATA_DIR / "backed_clinical_studies.json").read_text()
    )
    return {
        entry["id"]: entry
        for entry in payload["backed_clinical_studies"]
    }


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


def test_generic_l_carnitine_record_is_mixed_and_dose_scoped(
    clinical_entries: dict[str, dict],
) -> None:
    entry = clinical_entries["INGR_L_CARNITINE"]

    assert entry["evidence_level"] == "ingredient-human"
    assert entry["study_type"] == "systematic_review_meta"
    assert entry["effect_direction"] == "mixed"
    assert entry["min_clinical_dose"] == 1000
    assert entry["max_studied_clinical_dose"] == 4000
    assert entry["dose_unit"] == "mg"
    assert entry["exclude_alias_match_mode"] == "bounded_phrase"
    assert entry["evidence_group_id"] == "l_carnitine"
    assert entry["health_goals_supported"] == [
        "Muscle Growth & Recovery",
        "Weight Management",
    ]
    assert {
        ref["pmid"] for ref in entry["references_structured"]
    } == {"32958033", "32154768", "32359762"}
    assert all(
        ref["verification_source"] == "pubmed_eutils"
        for ref in entry["references_structured"]
    )
    assert all(
        ref["retracted"] is False
        for ref in entry["references_structured"]
    )


@pytest.mark.parametrize(
    "label_term",
    [
        "L-Carnitine",
        "Levocarnitine",
        "L-Carnitine Base",
        "L-Carnitine L-Tartrate",
        "L-Carnitine Tartrate",
        "Levocarnitine Tartrate",
        "LCLT",
    ],
)
def test_generic_l_carnitine_matches_reviewed_base_and_tartrate(
    enricher: SupplementEnricherV3,
    clinical_entries: dict[str, dict],
    label_term: str,
) -> None:
    entry = clinical_entries["INGR_L_CARNITINE"]
    assert enricher._clinical_study_match([label_term], entry) is not None


@pytest.mark.parametrize(
    "label_term",
    [
        "L-Carnitine Fumarate",
        "L-Carnitine HCl",
        "L-Carnitine Hydrochloride",
        "N-Acetyl L-Carnitine HCl",
        "Acetyl-L-Carnitine",
        "ArginoCarn Acetyl-L-Carnitine Arginate Dihydrochloride",
        "Acetyl-L-Carnitine HCl",
        "Propionyl-L-Carnitine",
        "GlycoCarn Glycine Propionyl L-Carnitine HCl",
        "Glycine Propionyl L-Carnitine Hydrochloride",
        "D-Carnitine",
        "DL-Carnitine",
    ],
)
def test_other_carnitines_do_not_borrow_generic_l_carnitine_evidence(
    enricher: SupplementEnricherV3,
    clinical_entries: dict[str, dict],
    label_term: str,
) -> None:
    entry = clinical_entries["INGR_L_CARNITINE"]
    assert enricher._clinical_study_match(
        [label_term, "L-Carnitine"],
        entry,
    ) is None


def test_carnipure_record_matches_its_two_small_recovery_trials(
    clinical_entries: dict[str, dict],
) -> None:
    entry = clinical_entries["BRAND_CARNIPURE"]

    assert entry["effect_direction"] == "positive_weak"
    assert entry["total_enrollment"] == 28
    assert "registry_completed_trials_count" not in entry
    assert entry["primary_outcome"] == "Muscle Growth & Recovery"
    assert entry["category"] == "sports_performance"
    assert entry["health_goals_supported"] == [
        "Muscle Growth & Recovery"
    ]
    assert entry["min_clinical_dose"] == 2000
    assert entry["max_studied_clinical_dose"] == 2000
    assert entry["external_ids"]["unii"] == "4D8F2Q45LQ"
    assert entry["evidence_group_id"] == "l_carnitine"

    combined = " ".join(
        str(entry.get(field) or "")
        for field in (
            "key_endpoints",
            "notes",
            "notable_studies",
            "effect_direction_rationale",
        )
    ).lower()
    assert "recovery" in combined
    assert "biomarker" in combined
    assert "heart health" not in combined
    assert "performance gains" not in combined


def test_from_prefixed_l_carnitine_tartrate_is_an_actual_form(
    enricher: SupplementEnricherV3,
) -> None:
    quality_map = enricher.databases["ingredient_quality_map"]
    result = enricher._match_quality_map(
        "L-Carnitine",
        "L-Carnitine",
        quality_map,
        cleaned_forms=[
            {
                "name": "L-Carnitine Tartrate",
                "prefix": "from",
                "percent": None,
                "ingredientGroup": "L-Carnitine",
            }
        ],
        cleaner_canonical_id="l_carnitine",
    )

    assert result is not None
    assert result["canonical_id"] == "l_carnitine"
    assert result["form_id"] == "l-carnitine tartrate (lclt)"
    assert result["bio_score"] == 10


def _single_l_carnitine_product(
    *,
    name: str,
    matched_form: str | None,
    product_name: str = "L-Carnitine",
) -> dict:
    ingredient = {
        "name": name,
        "raw_source_text": name,
        "standard_name": "L-Carnitine",
        "canonical_id": "l_carnitine",
        "mapped": True,
        "quantity": 2000,
        "unit": "mg",
    }
    if matched_form is not None:
        ingredient["matched_form"] = matched_form
    return {
        "status": "active",
        "product_name": product_name,
        "form_factor": "capsule",
        "supplement_type": {"type": "single_nutrient"},
        "ingredient_quality_data": {
            "ingredients_scorable": [ingredient],
            "ingredients": [ingredient],
        },
        "evidence_data": {"clinical_matches": []},
    }


@pytest.mark.parametrize(
    ("name", "matched_form"),
    [
        ("L-Carnitine", None),
        ("L-Carnitine Tartrate", "L-Carnitine Tartrate"),
    ],
)
def test_scoring_recovery_accepts_reviewed_l_carnitine_forms(
    name: str,
    matched_form: str | None,
) -> None:
    payload = score_evidence(
        _single_l_carnitine_product(
            name=name,
            matched_form=matched_form,
        ),
        apply_primary_floor=True,
    )

    assert payload["metadata"]["recovered_matches"] == [
        "INGR_L_CARNITINE"
    ]
    assert payload["score"] > 0.0


def test_scoring_recovery_rejects_excluded_l_carnitine_form() -> None:
    payload = score_evidence(
        _single_l_carnitine_product(
            name="L-Carnitine Fumarate",
            matched_form="L-Carnitine Fumarate",
        ),
        apply_primary_floor=True,
    )

    assert payload["metadata"]["recovered_matches"] == []
    assert payload["score"] == 0.0


@pytest.mark.parametrize(
    "excluded_form",
    [
        "L-Carnitine Fumarate",
        "L-Carnitine HCl",
        "Acetyl-L-Carnitine Arginate",
    ],
)
def test_scoring_recovery_uses_product_identity_when_row_lost_form(
    excluded_form: str,
) -> None:
    payload = score_evidence(
        _single_l_carnitine_product(
            name="L-Carnitine",
            matched_form="L-Carnitine Base",
            product_name=f"{excluded_form} 1000 mg",
        ),
        apply_primary_floor=True,
    )

    assert payload["metadata"]["recovered_matches"] == []
    assert payload["score"] == 0.0


def test_enrichment_deduplicates_same_study_across_active_rows(
    enricher: SupplementEnricherV3,
) -> None:
    product = {
        "fullName": "L-Carnitine Blend",
        "activeIngredients": [
            {
                "name": "L-Carnitine",
                "standardName": "L-Carnitine",
                "quantity": 1000,
                "unit": "mg",
                "mapped": True,
            },
            {
                "name": "L-Carnitine Tartrate",
                "standardName": "L-Carnitine",
                "quantity": 1000,
                "unit": "mg",
                "mapped": True,
            },
        ],
    }

    evidence = enricher._collect_evidence_data(product)
    matches = [
        match
        for match in evidence["clinical_matches"]
        if match["id"] == "INGR_L_CARNITINE"
    ]

    assert len(matches) == 1


def test_enrichment_rejects_broad_parent_for_excluded_carnitine_rows(
    enricher: SupplementEnricherV3,
) -> None:
    product = {
        "fullName": "Carnitine Complex",
        "activeIngredients": [
            {
                "name": "L-Carnitine Fumarate",
                "standardName": "L-Carnitine",
                "quantity": 500,
                "unit": "mg",
                "mapped": True,
            },
            {
                "name": "GlycoCarn Glycine Propionyl L-Carnitine HCl",
                "raw_source_text": (
                    "GlycoCarn Glycine Propionyl L-Carnitine HCl"
                ),
                "standardName": "L-Carnitine",
                "branded_token_extracted": "GlycoCarn",
                "quantity": 250,
                "unit": "mg",
                "mapped": True,
            },
        ],
    }

    evidence = enricher._collect_evidence_data(product)

    assert all(
        match["id"] != "INGR_L_CARNITINE"
        for match in evidence["clinical_matches"]
    )


def test_brand_and_generic_carnitine_evidence_share_one_ingredient_group(
    clinical_entries: dict[str, dict],
) -> None:
    product = _single_l_carnitine_product(
        name="Carnipure",
        matched_form="L-Carnitine L-Tartrate",
        product_name="Carnipure L-Carnitine 2000 mg",
    )
    product["evidence_data"]["clinical_matches"] = [
        dict(clinical_entries["BRAND_CARNIPURE"]),
        dict(clinical_entries["INGR_L_CARNITINE"]),
    ]

    payload = score_evidence(product, apply_primary_floor=True)

    assert list(payload["metadata"]["ingredient_points"]) == [
        "l carnitine"
    ]
    assert payload["metadata"]["top_n_applied"] == 1
