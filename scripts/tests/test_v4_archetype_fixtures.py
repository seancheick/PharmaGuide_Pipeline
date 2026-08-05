"""Phase 4.2 synthetic archetype validation through the production scorer."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _validation_module():
    return importlib.import_module("audit_v4_archetype_fixtures")


def test_decision_fixture_suite_uses_the_single_production_scoring_seam() -> None:
    validation = _validation_module()

    assert validation.PRODUCTION_ENTRY_POINT == (
        "scoring_v4.scored_artifact.build_scored_artifact"
    )
    assert validation.scoring_entry_point is validation.build_scored_artifact


def test_decision_fixture_suite_has_reviewed_ideal_and_failure_pairs() -> None:
    validation = _validation_module()
    fixtures = validation.load_fixture_suite()

    assert fixtures.metadata["schema_version"] == "1.0.0"
    assert fixtures.archetypes == {
        "generic_single_molecule",
        "b_complex",
        "immune_support",
        "fiber_digestive",
        "probiotic",
        "omega",
        "prenatal_multi",
        "generic_botanical_branded",
        "sports_single",
        "sports_pre_workout",
        "sports_protein",
        "sports_bcaa_eaa",
    }
    for archetype in fixtures.archetypes:
        variants = {
            fixture.variant
            for fixture in fixtures.cases
            if fixture.archetype == archetype
        }
        assert variants == {"ideal", "failure"}


@pytest.mark.parametrize(
    "case_id",
    [
        "generic_single_molecule__ideal",
        "generic_single_molecule__failure",
        "b_complex__ideal",
        "b_complex__failure",
        "immune_support__ideal",
        "immune_support__failure",
        "fiber_digestive__ideal",
        "fiber_digestive__failure",
        "probiotic__ideal",
        "probiotic__failure",
        "omega__ideal",
        "omega__failure",
        "prenatal_multi__ideal",
        "prenatal_multi__failure",
        "generic_botanical_branded__ideal",
        "generic_botanical_branded__failure",
        "sports_single__ideal",
        "sports_single__failure",
        "sports_pre_workout__ideal",
        "sports_pre_workout__failure",
        "sports_protein__ideal",
        "sports_protein__failure",
        "sports_bcaa_eaa__ideal",
        "sports_bcaa_eaa__failure",
    ],
)
def test_decision_fixture_matches_locked_production_outcome(case_id: str) -> None:
    validation = _validation_module()
    result = validation.evaluate_fixture(validation.load_fixture_suite().by_id(case_id))

    assert result.passed, result.diff


@pytest.mark.parametrize(
    ("ideal_id", "failure_id"),
    [
        ("generic_single_molecule__ideal", "generic_single_molecule__failure"),
        ("b_complex__ideal", "b_complex__failure"),
        ("immune_support__ideal", "immune_support__failure"),
        ("fiber_digestive__ideal", "fiber_digestive__failure"),
        ("probiotic__ideal", "probiotic__failure"),
        ("omega__ideal", "omega__failure"),
        ("prenatal_multi__ideal", "prenatal_multi__failure"),
        ("generic_botanical_branded__ideal", "generic_botanical_branded__failure"),
        ("sports_single__ideal", "sports_single__failure"),
        ("sports_pre_workout__ideal", "sports_pre_workout__failure"),
        ("sports_protein__ideal", "sports_protein__failure"),
        ("sports_bcaa_eaa__ideal", "sports_bcaa_eaa__failure"),
    ],
)
def test_failure_fixture_scores_below_its_ideal_pair(
    ideal_id: str,
    failure_id: str,
) -> None:
    validation = _validation_module()
    suite = validation.load_fixture_suite()

    ideal = validation.evaluate_fixture(suite.by_id(ideal_id))
    failure = validation.evaluate_fixture(suite.by_id(failure_id))

    assert ideal.actual["quality_score_v4_100"] > failure.actual[
        "quality_score_v4_100"
    ]


def test_decision_fixtures_expose_d4_d5_reference_mismatches_without_recalibrating() -> None:
    validation = _validation_module()
    suite = validation.load_fixture_suite()

    generic = validation.evaluate_fixture(
        suite.by_id("generic_single_molecule__ideal")
    ).actual
    b_complex = validation.evaluate_fixture(suite.by_id("b_complex__ideal")).actual

    assert generic["raw_dimensions"]["evidence"] == 18.0
    assert generic["normalization_references"]["evidence"] == 19.0
    assert b_complex["raw_dimensions"]["evidence"] == 15.0
    assert b_complex["normalization_references"]["evidence"] == 14.0


def test_category_fixtures_expose_reference_mismatches_without_recalibrating() -> None:
    validation = _validation_module()
    suite = validation.load_fixture_suite()

    probiotic = validation.evaluate_fixture(suite.by_id("probiotic__ideal")).actual
    omega = validation.evaluate_fixture(suite.by_id("omega__ideal")).actual
    prenatal = validation.evaluate_fixture(
        suite.by_id("prenatal_multi__ideal")
    ).actual

    assert probiotic["raw_dimensions"]["dose"] == 25.0
    assert probiotic["normalization_references"]["dose"] == 22.0
    assert omega["raw_dimensions"]["dose"] == 25.0
    assert omega["normalization_references"]["dose"] == 23.0
    assert prenatal["raw_dimensions"]["evidence"] == 18.0
    assert prenatal["normalization_references"]["evidence"] == 20.0
