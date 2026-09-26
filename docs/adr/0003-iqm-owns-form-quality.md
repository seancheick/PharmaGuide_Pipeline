# ADR-0003 — IQM bio_score owns form quality

**Status:** ACCEPTED (quality_score 1.7.0, 367078c4, 2026-09-15)
**Date:** 2026-09-25
**Matrix concept:** `ingredient_form_quality`

## Decision

Form quality is one fact: the IQM `forms[].bio_score` of the matched form. Scoring reads it only
through `scripts/scoring_v4/modules/generic_helpers.py::bio_score_of`, and Formulation owns the
credit for it.

## Context

Before 1.7.0, a premium-form count, a preferred-form name table and a bio_score dose multiplier each
re-ranked that same fact, so one good form earned credit more than once. The multi/prenatal and
B-complex modules were moved onto the single owner, guarded by
`scripts/tests/test_vitamin_form_ownership.py`.

## Consequences

- No pillar adds points for premium-form counts, preferred-form names or bio_score multipliers.
- Known violation when this was written: `generic_dose.py::_score_multi_form_bonus` gives up to +3
  Dose points for 2+ premium forms of one nutrient. Removing it moves shipped scores, so it is a
  separate, measured change and not part of this record.

## Rejected

Keeping the count or name bonuses as "tie-breakers"; weighting Dose coverage by bio_score.
