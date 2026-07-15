"""Scorable-row and multi-form boundaries remain conservative (H8)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3
from enhanced_normalizer import EnhancedDSLDNormalizer


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


def test_explicit_partial_form_percentages_are_not_renormalized(enricher) -> None:
    form_info = enricher._extract_form_from_label(
        "Vitamin B12 (as 20% methylcobalamin and 30% mystery form)"
    )

    assert [row["percent_share"] for row in form_info["extracted_forms"]] == [
        pytest.approx(0.2),
        pytest.approx(0.3),
    ]


def test_unmatched_form_mass_remains_in_multi_form_aggregation(enricher) -> None:
    quality_map = enricher.databases["ingredient_quality_map"]
    form_info = enricher._extract_form_from_label(
        "Vitamin B12 (as 20% methylcobalamin and 30% mystery form)"
    )

    result = enricher._match_multi_form(
        form_info,
        quality_map,
        cleaner_canonical_id="vitamin_b12_cobalamin",
    )

    assert result is not None
    assert result["matched_percent_total"] == pytest.approx(0.2)
    assert result["unmatched_percent_total"] == pytest.approx(0.8)
    assert result["matched_forms"][0]["percent_share"] == pytest.approx(0.2)


def test_potency_unit_requires_a_token_boundary(enricher) -> None:
    assert enricher._has_high_signal_potency("Omega-3 Gold") is False
    assert enricher._has_high_signal_potency("Serves 5 guests") is False
    assert enricher._has_high_signal_potency("Omega-3 500 mg") is True


def test_dict_hierarchy_blend_header_with_dose_is_not_scorable(enricher) -> None:
    ingredient = {
        "name": "Energy Complex",
        "quantity": 500,
        "unit": "mg",
        "amount": {"value": 500, "unit": "mg"},
        "hierarchyType": {"type": "blend_header"},
    }

    reason = enricher._should_skip_from_scoring(
        ingredient,
        enricher.databases["ingredient_quality_map"],
        enricher.databases["standardized_botanicals"],
    )

    assert reason == "blend_header_total_weight_only"


def test_dosed_energy_blend_suffix_is_structural_header(enricher) -> None:
    ingredient = {
        "name": "Energy Blend",
        "ingredientGroup": "Proprietary Blend",
        "quantity": 500,
        "unit": "mg",
        "amount": {"value": 500, "unit": "mg"},
    }

    reason = enricher._should_skip_from_scoring(
        ingredient,
        enricher.databases["ingredient_quality_map"],
        enricher.databases["standardized_botanicals"],
    )

    assert reason == "blend_header_total_weight_only"


def test_amino_acids_text_does_not_synthesize_soy_free_claim(enricher) -> None:
    claims = EnhancedDSLDNormalizer()._extract_clean_claims(
        "Contains Amino Acids, Soy Lecithin."
    )

    assert "Soy Free" not in claims
