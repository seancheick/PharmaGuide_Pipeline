#!/usr/bin/env python3
"""Only reviewed evidence may anchor an affirmative Evidence floor.

The primary-mass floor is one of the dominant Evidence mechanics: it is decisive
for 5,029 products and moves 2,690 published tiers. A floor that rests on
evidence no reviewer owns would be an affirmative clinical claim with no
reviewed source behind it.

Nearly every anchor is a record in `clinical_applicability.reviewed_entries()`.
The exception is `_RECOVERED_COLLAGEN_PEPTIDES_MATCH`, a literal in
`generic_evidence` that the scorer synthesises when enrichment fails to copy a
collagen match. It is decisive for 24 products, and it carries
`source_data: backed_clinical_studies:INGR_COLLAGEN_PEPTIDES` — a CLAIM of
reviewed provenance.

These tests make the claim checkable. The literal may keep dose metadata the
registry record does not carry, but on the three fields that decide what a floor
is allowed to say — direction, study type, evidence level — it must agree with
the reviewed record it cites. If someone edits either side, this fails instead of
quietly promoting 24 products on evidence the registry no longer supports.

No second registry, no per-product exception: the reviewed registry stays the
owner and this only holds the copy to it.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import clinical_applicability as ca                      # noqa: E402
from scoring_v4.modules import generic_evidence as ge    # noqa: E402

#: The fields that determine whether, and how high, an anchor may set a floor.
ANCHORING_FIELDS = ("effect_direction", "study_type", "evidence_level")


def _cited_record(literal):
    source = (literal.get("source_data") or "")
    assert source.startswith("backed_clinical_studies:"), (
        f"a recovered anchor must cite the registry it claims: {source!r}")
    return source.split(":", 1)[1]


def test_the_recovered_collagen_anchor_cites_a_real_reviewed_record():
    literal = ge._RECOVERED_COLLAGEN_PEPTIDES_MATCH
    cited = _cited_record(literal)

    assert cited in ca.reviewed_entries(), (
        f"{literal['id']} claims provenance from {cited}, which is not a reviewed "
        "record. An anchor may not invent its own evidence.")


def test_the_recovered_anchor_agrees_with_the_record_it_cites():
    literal = ge._RECOVERED_COLLAGEN_PEPTIDES_MATCH
    reviewed = ca.reviewed_entries()[_cited_record(literal)]

    mismatches = {
        field: (literal.get(field), reviewed.get(field))
        for field in ANCHORING_FIELDS
        if literal.get(field) != reviewed.get(field)
    }
    assert not mismatches, (
        "the recovered anchor has drifted from the reviewed record it cites "
        f"(literal, reviewed): {mismatches}")


def test_a_direction_that_cannot_anchor_stays_unable_to_anchor():
    """null and negative must never produce an affirmative floor, under ANY
    policy. This is structural — the floor skips a multiplier of zero — so the
    two empty strata in the sanity review are empty by construction."""
    for direction in ("null", "negative"):
        assert ge._EFFECT_FLOOR_MULTIPLIER.get(direction, 0.0) <= 0.0, (
            f"{direction} evidence must not be able to anchor an Evidence floor")


def test_the_floor_never_outranks_the_direction_that_anchors_it():
    """positive_weak and mixed must not reach the strong floor base. The ceiling
    reuses EFFECT_DIRECTION_MULTIPLIERS and PRIMARY_FLOOR_MODERATE — if either
    owner moves, this moves with it rather than restating a copied number."""
    strong = ge.PRIMARY_FLOOR_STRONG
    moderate = ge.PRIMARY_FLOOR_MODERATE

    for direction in ("positive_weak", "mixed"):
        ceiling = moderate * ge.EFFECT_DIRECTION_MULTIPLIERS[direction]
        assert ceiling < strong, (
            f"{direction} could reach the strong floor base {strong}")
        assert ceiling <= moderate

    assert ge.EFFECT_DIRECTION_MULTIPLIERS["positive_strong"] == 1.0, (
        "only positive_strong may anchor at the full base")


def test_the_authority_floor_is_a_separate_owner():
    """Nutrition adequacy and clinical efficacy are different claims. The
    primary-mass floor must not duplicate or overwrite the authority floor."""
    assert ge.NUTRITION_AUTHORITY_FLOOR != ge.PRIMARY_FLOOR_MODERATE
    assert ge.NUTRITION_AUTHORITY_FLOOR != ge.PRIMARY_FLOOR_STRONG


# ── direction_ceiling, locked 2026-09-18 ─────────────────────────────────────
#
# A floor may prevent under-scoring where reviewed evidence supports an
# ingredient. It may not manufacture stronger affirmative Evidence than the
# reviewed direction supports. Locked after the 13-stratum sanity review; these
# pin the contract so a later change has to argue with a test.


def test_only_positive_strong_may_anchor_on_a_strong_base():
    """positive_strong is deliberately EXCLUDED from the ceiling — it keeps the
    strong/branded base. It is not capped at PRIMARY_FLOOR_MODERATE."""
    from scoring_v4.modules.generic_evidence import score_evidence

    strong = _floor_for("positive_strong", score_evidence)
    assert strong == ge.PRIMARY_FLOOR_STRONG
    assert strong > ge.PRIMARY_FLOOR_MODERATE


def test_non_strong_directions_are_capped_at_the_moderate_base():
    from scoring_v4.modules.generic_evidence import score_evidence

    for direction in ("positive_weak", "mixed"):
        expected = round(ge.PRIMARY_FLOOR_MODERATE
                         * ge.EFFECT_DIRECTION_MULTIPLIERS[direction], 4)
        got = _floor_for(direction, score_evidence)
        assert got == expected, f"{direction}: {got} != {expected}"
        assert got < ge.PRIMARY_FLOOR_STRONG


def test_null_and_negative_anchor_nothing_even_on_a_strong_study():
    from scoring_v4.modules.generic_evidence import score_evidence

    for direction in ("null", "negative"):
        assert _floor_for(direction, score_evidence) == 0.0


def _floor_for(direction, score_evidence):
    """A single mass-dominant active with a strong-study match in `direction`.

    Product shape mirrors test_v4_evidence_primary_floor_p8's fixtures: the floor
    reads actives from ingredient_quality_data, so a bare activeIngredients list
    never reaches the mass gate and every direction would read 0.0.
    """
    ingredient = {"name": "Ashwagandha", "standard_name": "Ashwagandha",
                  "canonical_id": "ashwagandha", "mapped": True,
                  "bio_score": 11, "score": 11, "quantity": 600, "unit": "mg"}
    product = {
        "status": "active", "form_factor": "capsule",
        "supplement_type": {"type": "single_nutrient"},
        "ingredient_quality_data": {"ingredients_scorable": [ingredient],
                                    "ingredients": [ingredient]},
        "evidence_data": {"clinical_matches": [{
            "id": "INGR_ASHWAGANDHA", "ingredient": "Ashwagandha",
            "standard_name": "Ashwagandha", "canonical_id": "ashwagandha",
            "study_type": "rct_multiple", "evidence_level": "ingredient-human",
            "effect_direction": direction, "total_enrollment": 500,
        }]},
    }
    return score_evidence(product, apply_primary_floor=True)["metadata"]["primary_evidence_floor"]
