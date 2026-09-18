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


# ── anchor resolution: never reverse-match standard_name ──────────────────────
#
# An earlier floor audit lost 40 products by mapping the floor's canonical id
# back to a registry record through `standard_name`. Two real shapes break that,
# and both are in the shipped data:
#
#   INGR_BRANCHED_CHAIN_AMINO_ACIDS  evidence_group_id "bcaa"
#                                    standard_name     "Branched Chain Amino Acids"
#   RECOVERED_COLLAGEN_PEPTIDES_V1   a recovered match carried on the product
#                                    blob - not in reviewed_entries() at all, so
#                                    no registry lookup of any kind can find it
#
# The anchoring entry is always already in the product's resolved matches, so it
# is found there with the scorer's own accessor.

_calibration = importlib.util.module_from_spec(importlib.util.spec_from_file_location(
    "primary_mass_floor_calibration",
    SCRIPTS / "audits/evidence_expansion_2026_09/primary_mass_floor_calibration.py"))
importlib.util.spec_from_file_location(
    "primary_mass_floor_calibration",
    SCRIPTS / "audits/evidence_expansion_2026_09/primary_mass_floor_calibration.py"
).loader.exec_module(_calibration)

BCAA_MATCH = {"id": "INGR_BRANCHED_CHAIN_AMINO_ACIDS",
              "evidence_group_id": "bcaa",
              "standard_name": "Branched Chain Amino Acids",
              "study_type": "systematic_review_meta", "evidence_level": "ingredient-human",
              "effect_direction": "positive_weak"}
RECOVERED_COLLAGEN = {"id": "RECOVERED_COLLAGEN_PEPTIDES_V1", "standard_name": "Collagen",
                      "study_type": "systematic_review_meta", "evidence_level": "ingredient-human",
                      "effect_direction": "positive_strong"}


def test_anchor_resolves_through_the_products_own_match_not_a_standard_name_lookup():
    from scoring_v4.modules import generic_evidence as ge

    matches = [BCAA_MATCH, RECOVERED_COLLAGEN]
    for match in matches:
        canonical = ge._canonical_from_entry(match)
        found = _calibration.anchor_entry(ge, matches, canonical)
        assert found is match, f"{match['id']} did not resolve from canonical {canonical!r}"


def test_a_standard_name_reverse_lookup_would_have_missed_bcaa():
    """Pins WHY the accessor is used, so a future 'simplification' back to a name
    lookup fails here instead of silently dropping products from an audit."""
    from scoring_v4.modules import generic_evidence as ge

    canonical = ge._canonical_from_entry(BCAA_MATCH)
    assert canonical == "bcaa"

    reverse_lookup = {ge._canonical_text(BCAA_MATCH["standard_name"]): BCAA_MATCH}
    assert canonical not in reverse_lookup, (
        "if these ever coincide this guard is vacuous and needs a new example")
    assert _calibration.anchor_entry(ge, [BCAA_MATCH], canonical) is BCAA_MATCH


def test_a_recovered_anchor_is_not_reachable_from_the_reviewed_registry():
    """The collagen half of the same bug: the anchor is not a registry record at
    all, so no registry-side lookup could ever have found it."""
    import clinical_applicability as ca
    from scoring_v4.modules import generic_evidence as ge

    assert RECOVERED_COLLAGEN["id"] not in ca.reviewed_entries()
    canonical = ge._canonical_from_entry(RECOVERED_COLLAGEN)
    assert _calibration.anchor_entry(ge, [RECOVERED_COLLAGEN], canonical) is RECOVERED_COLLAGEN


def test_anchor_entry_prefers_the_highest_scoring_record_for_one_canonical():
    from scoring_v4.modules import generic_evidence as ge

    weak = {**BCAA_MATCH, "id": "WEAK", "study_type": "rct_single"}
    strong = {**BCAA_MATCH, "id": "STRONG", "study_type": "systematic_review_meta"}
    assert _calibration.anchor_entry(ge, [weak, strong], "bcaa") is strong
    assert _calibration.anchor_entry(ge, [strong, weak], "bcaa") is strong


def test_anchor_entry_returns_none_without_a_canonical():
    from scoring_v4.modules import generic_evidence as ge

    assert _calibration.anchor_entry(ge, [BCAA_MATCH], None) is None
    assert _calibration.anchor_entry(ge, [BCAA_MATCH], "not_an_ingredient") is None
