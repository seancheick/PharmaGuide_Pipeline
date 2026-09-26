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


def test_ideal_fixtures_reach_their_evidence_reference() -> None:
    """quality_score 1.1.3-achievable-ceilings: each archetype reference is the
    ceiling its engine can actually reach, so an ideal product scores 20/20.
    Before 2026-09-13 these references sat above the ceiling (generic 19 over
    an 18-point engine) and this test documented the mismatch instead of
    fixing it."""
    validation = _validation_module()
    suite = validation.load_fixture_suite()

    generic = validation.evaluate_fixture(
        suite.by_id("generic_single_molecule__ideal")
    ).actual
    b_complex = validation.evaluate_fixture(suite.by_id("b_complex__ideal")).actual

    assert generic["raw_dimensions"]["evidence"] == 18.0
    assert generic["normalization_references"]["evidence"] == 18.0
    assert generic["pillars"]["evidence"] == 20.0
    # Complete B panels earn the native 20-point authority score; no
    # denominator compression is needed to manufacture attainability.
    assert b_complex["raw_dimensions"]["evidence"] == 20.0
    assert b_complex["normalization_references"]["evidence"] == 20.0
    assert b_complex["pillars"]["evidence"] == 20.0


def test_category_fixture_contracts() -> None:
    validation = _validation_module()
    suite = validation.load_fixture_suite()

    probiotic = validation.evaluate_fixture(suite.by_id("probiotic__ideal")).actual
    omega = validation.evaluate_fixture(suite.by_id("omega__ideal")).actual
    prenatal = validation.evaluate_fixture(
        suite.by_id("prenatal_multi__ideal")
    ).actual

    # Probiotic Dose no longer rewards strain count. This fixture's disclosed
    # potency earns 20 raw points and one strong strain can carry Evidence;
    # neither pillar manufactures breadth from additional strains.
    assert probiotic["raw_dimensions"]["dose"] == 20.0
    assert probiotic["pillars"]["dose"] == 18.2
    assert probiotic["normalization_references"]["dose"] == 22.0
    assert probiotic["raw_dimensions"]["formulation"] == 15.25
    assert probiotic["normalization_references"]["formulation"] == 16.0
    assert probiotic["pillars"]["formulation"] == 19.1
    assert probiotic["raw_dimensions"]["evidence"] == 12.0
    # Omega raw dose tops out at 20 now that the EPA:DHA ratio bonus is gone
    # (quality_score 1.2.0); the reference equals that ceiling because the rubric
    # gives full band credit at 2 g/day. A complete prenatal essential-nutrient
    # panel has a native 20-point authority ceiling.
    assert omega["raw_dimensions"]["dose"] == 20.0
    assert omega["normalization_references"]["dose"] == 20.0
    assert omega["pillars"]["dose"] == 20.0
    assert prenatal["raw_dimensions"]["evidence"] == 20.0
    assert prenatal["normalization_references"]["evidence"] == 20.0
    assert prenatal["pillars"]["evidence"] == 20.0


def test_references_use_reviewed_engine_limits_not_observed_catalog_maxima() -> None:
    """A normalization divisor must not be selected from today's corpus maximum.

    Corpus maxima move as labels are added and do not define the rubric.  These
    references are pinned to the module contract or to the previously reviewed
    purpose-fit ceiling instead.
    """
    from scoring_v4.quality_score_config import config

    rubric = config()
    form = rubric["formulation_subscale"]["archetype_reference"]
    dose = rubric["dose_subscale"]["archetype_reference"]
    evidence = rubric["evidence_subscale"]["archetype_reference"]

    # The protein adapter can earn 15 + 5 + 3 + 4 + 2 = 29.  Pre-workout
    # and BCAA/EAA still use the broader generic-formulation contract; their
    # historical purpose-fit references must not be replaced by a corpus p99.
    assert form["sports_protein"] == 29.0
    assert form["sports_pre_workout"] == 30.0
    assert form["sports_bcaa_eaa"] == 25.0

    # A product classified by name as pre-workout can still be a focused
    # single and earn the sports module's full 25.  The immune adapter's own
    # component sum is capped at 22.
    assert dose["sports_pre_workout"] == 25.0
    assert dose["immune_support"] == 22.0

    # Omega explicitly reserves 15 points for clinical evidence and 5 for
    # indication relevance, so 20—not the current corpus maximum—is reachable.
    assert evidence["omega"] == 20.0
