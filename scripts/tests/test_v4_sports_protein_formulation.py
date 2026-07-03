"""Sports protein formulation calibration tests."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scoring_v4.modules.sports import score_sports  # noqa: E402
from scoring_v4.modules.sports_formulation import score_formulation  # noqa: E402


def _row(
    canonical_id: str,
    quantity: float,
    unit: str = "Gram(s)",
    *,
    name: str | None = None,
    matched_form: str | None = None,
    bio_score: float = 12.0,
    proprietary: bool = False,
) -> dict:
    label = name or canonical_id.replace("_", " ").title()
    return {
        "name": label,
        "standard_name": label,
        "canonical_id": canonical_id,
        "quantity": quantity,
        "unit": unit,
        "unit_normalized": unit.lower(),
        "bio_score": bio_score,
        "matched_form": matched_form,
        "raw_source_text": label,
        "mapped": True,
        "mapped_identity": True,
        "scoreable_identity": True,
        "score_eligible_by_cleaner": True,
        "role_classification": "active_scorable",
        "cleaner_row_role": "active_scorable",
        "source_section": "active",
        "is_proprietary_blend": proprietary,
        "is_parent_total": False,
    }


def _protein_product(
    rows: list[dict],
    *,
    name: str = "Benchmark Whey Protein Isolate",
    sugar: dict | None = None,
    sweeteners: dict | None = None,
    additives: list[dict] | None = None,
    proprietary_blends: list[dict] | None = None,
) -> dict:
    return {
        "id": 900001,
        "fullName": name,
        "product_name": name,
        "brandName": "PharmaGuide Benchmark",
        "primary_type": "protein_powder",
        "supplement_taxonomy": {
            "primary_type": "protein_powder",
            "percentile_category": "protein_powder",
        },
        "form_factor_canonical": "powder",
        "ingredient_quality_data": {
            "ingredients_scorable": rows,
            "ingredients": rows,
        },
        "dietary_sensitivity_data": {
            "sugar": sugar
            or {
                "amount_g": 0.0,
                "level": "sugar_free",
                "contains_sugar": False,
                "has_added_sugar": False,
                "sugar_sources": [],
            },
            "sweeteners": sweeteners
            or {
                "artificial": [],
                "high_glycemic": [],
                "sugar_alcohols": [],
                "safer_alternatives": [],
            },
        },
        "contaminant_data": {
            "harmful_additives": {"found": bool(additives), "additives": additives or []},
            "banned_substances": {"found": False, "substances": []},
        },
        "proprietary_blends": proprietary_blends or [],
        "proprietary_data": {
            "blends": proprietary_blends or [],
            "total_active_ingredients": len(rows),
        },
    }


def test_clean_whey_isolate_gets_elite_protein_formulation_credit() -> None:
    payload = score_formulation(
        _protein_product(
            [
                _row(
                    "whey_protein",
                    27,
                    name="Whey Protein Isolate",
                    matched_form="whey protein isolate",
                ),
                _row("l_leucine", 2.7, name="L-Leucine"),
                _row("l_isoleucine", 1.7, name="L-Isoleucine"),
                _row("l_valine", 1.6, name="L-Valine"),
            ]
        )
    )

    assert payload["metadata"]["sports_protein_profile_applied"] is True
    assert payload["score"] >= 24.0
    assert payload["components"]["sports_protein_source_quality"] >= 15.0
    assert payload["components"]["sports_amino_profile_disclosure"] > 0.0


def test_complete_plant_blend_gets_strong_but_not_isolate_level_credit() -> None:
    payload = score_formulation(
        _protein_product(
            [
                _row("pea_protein", 15, name="Pea Protein"),
                _row("rice_protein", 10, name="Brown Rice Protein"),
            ],
            name="Benchmark Complete Plant Protein",
        )
    )

    assert 20.0 <= payload["score"] < 24.0
    assert payload["metadata"]["protein_source_class"] == "complete_plant_blend"


def test_generic_protein_row_uses_clear_casein_product_name_for_source_class() -> None:
    payload = score_formulation(
        _protein_product(
            [_row("protein", 24, name="Protein")],
            name="Casein Protein 24 g Unflavored",
        )
    )

    assert payload["metadata"]["protein_source_class"] == "casein"
    assert payload["score"] >= 24.0


def test_soy_protein_isolate_does_not_get_whey_isolate_source_class() -> None:
    payload = score_formulation(
        _protein_product(
            [
                _row(
                    "soy_protein",
                    25,
                    name="Soy Protein Isolate",
                    matched_form="soy protein isolate",
                )
            ],
            name="Soy Protein Isolate",
        )
    )

    assert payload["metadata"]["protein_source_class"] == "soy_protein"
    assert payload["metadata"]["protein_source_class"] != "whey_isolate"


def test_artificially_sweetened_whey_is_capped_below_clean_elite_band() -> None:
    payload = score_formulation(
        _protein_product(
            [_row("whey_protein", 25, name="Whey Protein Isolate", matched_form="whey protein isolate")],
            name="Flavored Whey Protein Isolate",
            sweeteners={
                "artificial": ["Sucralose", "Acesulfame Potassium"],
                "high_glycemic": [],
                "sugar_alcohols": [],
                "safer_alternatives": [],
            },
            additives=[
                {"additive_id": "ADD_SUCRALOSE", "severity_level": "moderate", "source_section": "inactive"},
                {"additive_id": "ADD_ACESULFAME_K", "severity_level": "moderate", "source_section": "inactive"},
            ],
        )
    )

    assert payload["score"] < 21.0
    assert payload["penalties"]["sports_artificial_sweeteners"] < 0


def test_opaque_proprietary_or_amino_spiked_protein_matrix_scores_low() -> None:
    payload = score_formulation(
        _protein_product(
            [
                _row("protein", 18.9, name="Proprietary Protein Matrix", proprietary=True),
                _row("l_glycine", 2.0, name="Glycine"),
                _row("taurine", 1.0, name="Taurine"),
            ],
            name="MegaPump Protein Matrix",
            proprietary_blends=[{"name": "Proprietary Protein Matrix", "disclosure_level": "partial"}],
            sugar={
                "amount_g": 10.0,
                "level": "high",
                "contains_sugar": True,
                "has_added_sugar": True,
                "sugar_sources": ["glucose syrup"],
            },
        )
    )

    assert payload["score"] <= 8.0
    assert payload["penalties"]["sports_opaque_protein_blend"] < 0
    assert payload["penalties"]["sports_amino_spiking_risk"] < 0


def test_sports_module_uses_protein_formulation_adapter() -> None:
    result = score_sports(
        _protein_product(
            [_row("whey_protein", 27, name="Whey Protein Isolate", matched_form="whey protein isolate")]
        )
    )

    formulation = result.to_breakdown()["dimensions"]["formulation"]
    assert formulation["metadata"]["sports_protein_profile_applied"] is True
    assert formulation["score"] >= 24.0
