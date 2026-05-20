#!/usr/bin/env python3
"""Omega-3 RDA/AI integrity guards.

The U.S. DRI Adequate Intake values for "omega-3" are alpha-linolenic acid
(ALA) values. EPA, DHA, combined EPA+DHA, and fish-oil parent mass must stay
out of the official RDA/UL resolver and use their separate omega dosing logic.
"""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from rda_ul_calculator import RDAULCalculator


@pytest.fixture(scope="module")
def calculator() -> RDAULCalculator:
    return RDAULCalculator()


def test_ala_has_the_official_ai_values(calculator: RDAULCalculator) -> None:
    result = calculator.compute_nutrient_adequacy(
        nutrient="Alpha-Linolenic Acid",
        amount=1.6,
        unit="g",
        age_group="19-30",
        sex="male",
    )

    assert result.rda_ai == pytest.approx(1.6)
    assert result.rda_ai_source == "rda"
    assert result.scoring_eligible is True
    assert result.pct_rda == pytest.approx(100.0)


@pytest.mark.parametrize(
    "nutrient_name",
    [
        "ALA",
        "alpha-linolenic acid",
        "alpha linolenic acid",
        "linolenic acid (n-3)",
    ],
)
def test_ala_aliases_resolve_only_to_ala_ai(
    calculator: RDAULCalculator,
    nutrient_name: str,
) -> None:
    result = calculator.compute_nutrient_adequacy(
        nutrient=nutrient_name,
        amount=1.1,
        unit="g",
        age_group="19-30",
        sex="female",
    )

    assert result.rda_ai == pytest.approx(1.1)
    assert result.scoring_eligible is True


@pytest.mark.parametrize(
    "nutrient_name",
    [
        "Omega-3 Fatty Acids",
        "omega_3_fatty_acids",
        "EPA",
        "Eicosapentaenoic Acid",
        "DHA",
        "Docosahexaenoic Acid",
        "EPA+DHA",
        "epa_dha",
        "Fish Oil",
        "fish_oil",
    ],
)
def test_epa_dha_and_fish_oil_do_not_resolve_to_ala_rda(
    calculator: RDAULCalculator,
    nutrient_name: str,
) -> None:
    result = calculator.compute_nutrient_adequacy(
        nutrient=nutrient_name,
        amount=3_000,
        unit="mg",
        age_group="19-30",
        sex="male",
    )

    assert result.rda_ai is None
    assert result.pct_rda is None
    assert result.scoring_eligible is False
    assert result.adequacy_band == "unknown"
    assert result.notes == [f"Nutrient '{nutrient_name}' not found in RDA database"]


def test_rda_lookup_has_no_ambiguous_omega3_entry(calculator: RDAULCalculator) -> None:
    assert "alpha_linolenic_acid" in calculator.nutrient_lookup
    assert "omega_3_fatty_acids" not in calculator.nutrient_lookup
