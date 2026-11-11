"""ADR-0007 close-out batch (2026-11-10): source-verified age groups and signed-decision text."""
import json
import logging
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[1] / "data" / "backed_clinical_studies.json"


@pytest.fixture(scope="module")
def records():
    return {r["id"]: r for r in json.loads(DATA.read_text(encoding="utf-8"))["backed_clinical_studies"]}


@pytest.mark.parametrize("rid, ctx_id, age", [
    ("INGR_HYALURONIC_ACID", "ingr_hyaluronic_acid_34203487", "adult"),          # aged 35-64
    ("INGR_NAC", "nac_oral_exercise_soreness_subset_39632267", "adult"),         # mean ages ~20-30
    ("INGR_PASSIONFLOWER", "passionflower_short_term_anxiety_review_33352740", "adult"),  # >=18
    ("INGR_HONEY", "honey_child_nocturnal_cough_22869830", "child"),            # aged 1-5
    ("INGR_CREATINE_MONOHYDRATE", "creatine_monohydrate_resistance_training_body_composition_39074168", "adult"),
    ("INGR_ALPHA_GPC", "alpha_gpc_alzheimer_monotherapy_subset_36683513", "adult"),  # adult-onset disorders
])
def test_scoring_contexts_carry_their_source_age_group(records, rid, ctx_id, age):
    [ctx] = [c for c in records[rid]["study_contexts"] if c["context_id"] == ctx_id]
    assert ctx["population"]["age_group"] == age


def test_every_scoring_eligible_context_has_an_age_group(records):
    missing = [(r, c["context_id"]) for r, rec in records.items() for c in rec.get("study_contexts") or []
               if c.get("scoring_eligible") is True and not (c.get("population") or {}).get("age_group")]
    assert missing == []


def test_child_honey_study_does_not_apply_to_an_adult_product():
    """A trial in children aged 1-5 cannot credit an adult honey product."""
    from clinical_applicability import _special_population, reviewed_entries
    [ctx] = [c for c in reviewed_entries()["INGR_HONEY"]["study_contexts"]
             if c["context_id"] == "honey_child_nocturnal_cough_22869830"]
    assert _special_population(ctx, ctx["population"]["description"]) == "pediatric"


@pytest.mark.parametrize("rid, decision", [("PRECLIN_CURCUMIN_GENERIC", "A130"), ("INGR_TURMERIC", "A115")])
def test_curcumin_records_match_their_signed_decision(records, rid, decision):
    r = records[rid]
    assert r["study_type"] == "reference"
    assert r["effect_direction"] == "mixed"
    assert decision in r["effect_direction_rationale"]
    assert "40615851" in r["effect_direction_rationale"]
    assert r["total_enrollment"] is None and r["registry_completed_trials_count"] is None
    for stale in ("no automated downgrade signals", "have not been reassessed"):
        assert stale not in r["effect_direction_rationale"]


def test_generic_curcumin_carries_no_rejected_benefit_claim(records):
    r = records["PRECLIN_CURCUMIN_GENERIC"]
    assert r["key_endpoints"] == [] and r["health_goals_supported"] == []
    assert "primary_outcome" not in r
    assert "broad meta-analytic support" not in r["notes"] and "A130" in r["notes"]
    for stale in ("high-credibility", "supports anti-inflammatory", "symptom benefit"):
        assert stale not in r["notable_studies"]
    assert "A130" in r["notable_studies"] and "noncredit" in r["notable_studies"]


def test_reference_only_rice_protein_lists_no_supported_goal(records):
    """Both rice-protein contexts are rejected sources, so no goal is supported."""
    r = records["INGR_RICE_PROTEIN"]
    assert not any(c.get("scoring_eligible") for c in r["study_contexts"])
    assert r["health_goals_supported"] == []


def test_curcumin_text_reconciliation_moves_no_evidence():
    from assessment_readiness import _resolved_evidence_assessment
    from evidence_resolver import resolve_evidence_for_canonical
    previous = logging.root.manager.disable
    logging.disable(logging.WARNING)
    try:
        resolution = resolve_evidence_for_canonical("curcumin", name="Curcumin")
    finally:
        logging.disable(previous)
    assert resolution.points_eligible is False
    assert _resolved_evidence_assessment(resolution)[0] == "evaluated_limited_or_negative"
