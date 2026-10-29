"""Phase 4.2 synthetic archetype validation through the production scorer."""

from __future__ import annotations

import importlib
from copy import deepcopy
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


def test_immune_failure_retains_adequacy_before_one_final_ul_ceiling() -> None:
    validation = _validation_module()
    fixture = validation.load_fixture_suite().by_id("immune_support__failure")
    artifact = validation.build_scored_artifact(fixture.product)
    dose = artifact["quality_pillars_v4"]["dose"]
    receipt = dose["explanation"]["dose_receipt"]

    # Approved nutritional credit plateaus at its target, before one final
    # safety ceiling. Elderberry has no general benchmark and stays neutral.
    # The recorded 200% UL flag still sets public Dose to zero once.
    assert {item["ingredient"]: item["points"] for item in receipt["contributions"]} == {
        "vitamin_c": 20.0, "vitamin_d3": 20.0, "zinc": 20.0, "elderberry": 11.4,
    }
    assert receipt["adequacy_before_safety"] == 17.9
    assert receipt["upper_reference"]["pct_ul"] == 200.0
    assert receipt["upper_reference"]["cap_public"] == 0.0
    assert receipt["final"] == dose["score"] == 0.0
    assert receipt["reconciles"] is True


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


def test_context_free_ideal_matches_cannot_manufacture_clinical_floors() -> None:
    """Arithmetic ceilings do not approve a context-free clinical source.

    Magnesium's nutritional authority remains; complete B panels retain their
    native authority ceiling. Explicit reviewed floor arithmetic lives in P8.
    """
    from scoring_v4.modules import generic_evidence as ge

    validation = _validation_module()
    suite = validation.load_fixture_suite()
    case = suite.by_id("generic_single_molecule__ideal")
    generic = validation.evaluate_fixture(case).actual
    b_complex = validation.evaluate_fixture(suite.by_id("b_complex__ideal")).actual

    engine_ceiling = ge.CAP_PER_INGREDIENT * sum(ge.TOP_N_WEIGHTS) + max(v for _, v in ge.DEPTH_BONUS_BANDS)
    assert engine_ceiling == generic["normalization_references"]["evidence"] == 18.0
    assert generic["raw_dimensions"]["evidence"] == 10.0
    assert generic["raw_dimensions"]["evidence"] < ge.PRIMARY_FLOOR_STRONG == 14.0
    assert generic["pillars"]["evidence"] == 11.1
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

    # General CFU tiers do not establish clinical dose curves. The completed
    # review takes neutral 11.4 (raw 8.55 at reference 15); disclosure remains
    # a Transparency fact. Formulation is canonical form quality: the
    # unrated-strain neutral 9 plus tier-2 delayed-release delivery 2.
    assert probiotic["raw_dimensions"]["dose"] == 8.55
    assert probiotic["pillars"]["dose"] == 11.4
    assert probiotic["normalization_references"]["dose"] == 15.0
    assert probiotic["raw_dimensions"]["formulation"] == 11.0
    assert probiotic["normalization_references"]["formulation"] == 15.0
    assert probiotic["pillars"]["formulation"] == 14.7
    # The digestive label reaches LGG's approved GI/respiratory meta-analysis
    # (10 certainty, direct 6 applicability); extra strain names do not
    # establish trial replication.
    assert probiotic["raw_dimensions"]["evidence"] == 16.0
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


def test_protein_fixtures_require_actual_protein_facts_instead_of_powder_mass():
    validation = _validation_module()
    suite = validation.load_fixture_suite()
    ideal = deepcopy(suite.by_id("sports_protein__ideal").product)
    assert ideal["nutrition_summary"]["protein_g"] == 27
    assert ideal["display_ingredients"][0]["exact_dose_text"] == "27 g"
    artifact = validation.build_scored_artifact(ideal)
    entry = artifact["_v4_module_breakdown"]["dimensions"]["dose"]["metadata"]["dose_contributions"][0]
    assert entry["assessment"] == "protein_contribution_policy"
    assert entry["amount_per_serving"] == 27
    assert artifact["quality_pillars_v4"]["dose"]["score"] == 20

    ideal.pop("nutrition_summary")
    ideal.pop("display_ingredients")
    # The 27 g whey powder row remains, but cannot stand in for protein grams.
    missing = validation.build_scored_artifact(ideal)
    dose = missing["_v4_module_breakdown"]["dimensions"]["dose"]
    assert dose["score"] is None
    assert dose["metadata"]["reason_code"] == "unresolved_source_quantity"
    assert missing["quality_assessment_status"] == "partial"


def test_opaque_protein_fixture_keeps_capture_hold_and_unknown_preparation_distinct():
    validation = _validation_module()
    product = deepcopy(validation.load_fixture_suite().by_id("sports_protein__failure").product)
    missing = validation.build_scored_artifact(product)
    assert missing["_v4_module_breakdown"]["dimensions"]["dose"]["score"] is None
    assert missing["quality_assessment_status"] == "partial"

    # This control authors a separate synthetic label declaration; it does not
    # infer protein purity from the unchanged 10 g proprietary matrix mass.
    product["nutrition_summary"] = {"protein_g": 10}
    product["display_ingredients"] = [{
        "display_type": "nutrition_fact", "display_name": "Protein",
        "raw_source_text": "Protein", "raw_source_path": "ingredientRows[4]",
        "source_section": "activeIngredients", "exact_dose_text": "10 g",
    }]
    declared = validation.build_scored_artifact(product)
    dose = declared["_v4_module_breakdown"]["dimensions"]["dose"]
    assert dose["metadata"].get("assessment_status") != "incomplete"
    entry = dose["metadata"]["dose_contributions"][0]
    assert entry["amount_per_serving"] == 10
    assert entry["assessment"] == "protein_completed_no_general_benchmark"
    assert declared["quality_pillars_v4"]["dose"]["score"] == 11.4
    assert declared["product_safety_status"] == missing["product_safety_status"]


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

    # V4.1 Step 4: the protein adapter is source quality alone (15). Pre-workout
    # and BCAA/EAA still use the broader generic-formulation contract; their
    # historical purpose-fit references must not be replaced by a corpus p99.
    assert form["sports_protein"] == 15.0
    assert form["sports_pre_workout"] == 30.0
    assert form["sports_bcaa_eaa"] == 25.0

    # The single-active completion bonus is retired, so every sports subtype's
    # primary dose tops out at 20; BCAA/EAA composition no longer adds Dose
    # credit. The immune adapter's own component sum is
    # capped at 22.
    assert dose["sports_pre_workout"] == 20.0
    assert dose["immune_support"] == 22.0

    # Omega explicitly reserves 15 points for clinical evidence and 5 for
    # indication relevance, so 20—not the current corpus maximum—is reachable.
    assert evidence["omega"] == 20.0


def test_single_creatine_fixture_does_not_treat_derived_identity_as_source_form():
    validation = _validation_module()
    suite = validation.load_fixture_suite()
    failure = suite.by_id("sports_single__failure")
    row = failure.product["ingredient_quality_data"]["ingredients_scorable"][0]
    assert row["name"] == "Creatine Monohydrate"
    assert not row.get("source_label_name")
    assert not row.get("raw_source_text")
    assert not row.get("raw_taxonomy")
    assert not failure.product.get("activeIngredients")
    actual = validation.evaluate_fixture(failure).actual
    assert actual["pillars"]["evidence"] == 0.0
    assert actual["raw_dimensions"]["evidence"] == 0.0
    ideal = validation.evaluate_fixture(suite.by_id("sports_single__ideal")).actual
    # Printed source identity does not approve a context-free clinical stamp.
    assert ideal["pillars"]["evidence"] == 0.0
    assert ideal["quality_score_v4_100"] == 80.0


def test_preworkout_formulation_pin_follows_corrected_citrulline_parent():
    from scoring_reference_resolver import parent_best_form_quality, parent_relative_form_quality
    from scoring_v4.modules.generic_formulation import _bio_score_assessment

    case = _validation_module().load_fixture_suite().by_id("sports_pre_workout__ideal")
    # Source correction removes the unsupported malate advantage (15→14).
    # The existing parent-relative owner changes only this fixture's A1 mean.
    assert parent_best_form_quality("l_citrulline") == 14
    assert parent_relative_form_quality("l_citrulline", 13) == pytest.approx(13 / 14 * 15)
    rows = case.product["ingredient_quality_data"]["ingredients_scorable"]
    expected = sum(parent_relative_form_quality(r["canonical_id"], r["bio_score"]) for r in rows) / 4
    actual, count = _bio_score_assessment(case.product)
    assert count == 4
    assert actual == pytest.approx(expected)
    assert actual == pytest.approx(14.175824175824177)


def test_protein_fixture_confidence_retains_unresolved_amino_acid_assessments():
    validation = _validation_module()
    artifact = validation.build_scored_artifact(validation.load_fixture_suite().by_id("sports_protein__ideal").product)
    pending = {row["canonical_id"] for row in artifact["assessment_readiness"]["evidence"]["ingredient_assessments"]
               if row["state"] == "not_yet_evaluated"}
    assert pending == {"whey_protein", "l_isoleucine", "l_valine"}
    assert artifact["quality_score_confidence"] == "moderate"
    assert artifact["quality_score_v4_100"] == 80.0
    assert artifact["assessment_readiness"]["release_assessment"]["is_complete"] is False
