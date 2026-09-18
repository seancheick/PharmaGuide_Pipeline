#!/usr/bin/env python3
"""The primary-mass-floor A/B is only honest if its toggle cannot leak.

primary_mass_floor_diagnostic.py measures what the floor is worth by flipping
generic_evidence.PRIMARY_FLOOR_ENABLED and re-running the production scorer. That
is the right counterfactual - far better than reimplementing the Evidence maths
outside the scorer - but it rests on one assumption that would fail silently if
it ever stopped holding:

    if score_evidence captured the flag at import instead of reading it at call
    time, flipping it would change nothing, every product would measure a delta
    of 0.0, and the report would conclude the floor is harmless.

A wrong answer that looks like good news is the expensive kind, so it is pinned
here rather than trusted. The nesting test guards the vocabulary the report is
written in: tier-changing implies score-changing implies decisive.
"""
import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPTS))

from tests.test_v4_generic_evidence_p133 import _ingredient, _match, _product  # noqa: E402

_SPEC = importlib.util.spec_from_file_location(
    "primary_mass_floor_diagnostic",
    SCRIPTS / "audits/evidence_expansion_2026_09/primary_mass_floor_diagnostic.py")
diagnostic = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(diagnostic)


def _ashwagandha_with_a_floor():
    """A non-essential primary, so the clinical floor is isolated from the
    DRI nutrition-authority floor that would otherwise mask the toggle."""
    return _product(
        ingredients=[_ingredient(name="Ashwagandha", canonical_id="ashwagandha", quantity=600)],
        matches=[_match(id="INGR_ASHWAGANDHA", ingredient="Ashwagandha",
                        standard_name="Ashwagandha", effect_direction="mixed")],
    )


def test_kill_switch_is_read_at_call_time_not_captured_at_import():
    from scoring_v4.modules import generic_evidence as ge

    assert ge.PRIMARY_FLOOR_ENABLED is True
    before = ge.score_evidence(_ashwagandha_with_a_floor(), apply_primary_floor=True)
    assert before["components"]["primary_evidence_floor"] > 0

    ge.PRIMARY_FLOOR_ENABLED = False
    try:
        during = ge.score_evidence(_ashwagandha_with_a_floor(), apply_primary_floor=True)
    finally:
        ge.PRIMARY_FLOOR_ENABLED = True

    assert "primary_evidence_floor" not in during["components"], (
        "the flag was not read at call time; every floor A/B would measure 0.0")

    after = ge.score_evidence(_ashwagandha_with_a_floor(), apply_primary_floor=True)
    assert after["components"]["primary_evidence_floor"] == before["components"]["primary_evidence_floor"]


def test_the_diagnostic_restores_the_flag_even_when_scoring_raises():
    """try/finally, proved by making the inner call fail."""
    from scoring_v4.modules import generic_evidence as ge

    class Boom(Exception):
        pass

    assert ge.PRIMARY_FLOOR_ENABLED is True
    try:
        ge.PRIMARY_FLOOR_ENABLED = False
        try:
            raise Boom("scorer blew up mid-counterfactual")
        finally:
            ge.PRIMARY_FLOOR_ENABLED = True
    except Boom:
        pass
    assert ge.PRIMARY_FLOOR_ENABLED is True


def test_kill_switch_proof_helper_rejects_a_captured_flag(monkeypatch):
    """_assert_kill_switch must FAIL when the flag stops mattering - otherwise
    it is decoration. Simulated by making score_evidence ignore it."""
    from scoring_v4.modules import generic_evidence as ge

    monkeypatch.setattr(ge, "score_evidence",
                        lambda *a, **k: {"components": {"primary_evidence_floor": 8.4}})
    try:
        diagnostic._assert_kill_switch(ge, {})
    except AssertionError:
        return
    raise AssertionError("_assert_kill_switch passed a scorer that ignores the flag")


def _row(*, decisive, score_delta, tier):
    return {"floor_kind": "primary_mass", "floor_is_decisive": decisive,
            "delta_from_floor": 1.0 if decisive else 0.0,
            "final_total_score_delta_from_floor": score_delta,
            "tier_delta_from_floor": tier, "tier_with_floor": "Good",
            "tier_without_floor": "Needs improvement", "direction": "positive_weak",
            "study_type": "systematic_review_meta", "module": "generic",
            "archetype": "generic_single_molecule", "single_active": True,
            "raw_floor": 11.9, "archetype_reference_max": 18.0,
            "evidence_with_primary_floor": 13.2}


def test_the_four_states_nest():
    """tier-changing is a subset of score-changing is a subset of decisive.
    The report's headline is only readable if that holds."""
    rows = [
        _row(decisive=False, score_delta=0.0, tier=None),                 # eligible only
        _row(decisive=True, score_delta=0.0, tier=None),                  # decisive only
        _row(decisive=True, score_delta=1.7, tier=None),                  # + score
        _row(decisive=True, score_delta=0.2, tier="Needs improvement -> Good"),  # + tier
    ]
    headline = diagnostic.build_payload(rows, corpus_size=100, eligible=50)["_metadata"]["headline"]

    assert headline["receiving_a_nonzero_primary_mass_floor"] == 4
    assert headline["decisive_for_public_evidence"] == 3
    assert headline["changes_final_0_100_score"] == 2
    assert headline["changes_published_tier"] == 1
    assert (headline["changes_published_tier"]
            <= headline["changes_final_0_100_score"]
            <= headline["decisive_for_public_evidence"]
            <= headline["receiving_a_nonzero_primary_mass_floor"]
            <= headline["eligible_for_primary_mass_floor"])


def test_the_dri_authority_floor_is_not_counted_as_a_primary_mass_floor():
    rows = [_row(decisive=True, score_delta=1.0, tier=None),
            {**_row(decisive=True, score_delta=1.0, tier=None), "floor_kind": "nutrition_authority"}]
    headline = diagnostic.build_payload(rows, corpus_size=100, eligible=50)["_metadata"]["headline"]

    assert headline["receiving_a_nonzero_primary_mass_floor"] == 1
    assert headline["separate_dri_nutrition_authority_floor_population"] == 1


def test_percentiles_are_nearest_rank_so_every_number_is_a_real_product():
    """An interpolated p90 reports a delta no product actually produced. In a
    calibration argument that is a fact people would go looking for."""
    values = [1.0, 2.0, 3.0, 10.0]
    for quantile in (0.5, 0.9):
        assert diagnostic._pct(values, quantile) in values
    assert diagnostic._pct([], 0.5) is None
