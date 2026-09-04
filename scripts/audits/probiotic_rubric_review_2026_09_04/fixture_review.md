# Fixture-only correction pass — 2026-09-04

Scope: broad-fast follow-up on three stale test fixtures only. No runtime edits.

## RED

Focused reproduction:

- `PG_TEST_WORKERS=2 scripts/test.sh fast scripts/tests/test_non_scorable_safety_identity.py scripts/tests/test_quality_map_ambiguity_logging.py scripts/tests/test_v4_route_intent_unification.py`

Observed:

- `4 failed, 43 passed`

Failures were fixture drift, not new runtime defects:

1. `test_non_scorable_safety_identity.py`
   - `CBD (Cannabidiol)` fixture invented `canonical_source_db=botanical_ingredients`.
   - `Hemp Seed Oil` fixture also invented `canonical_source_db=botanical_ingredients`.
2. `test_quality_map_ambiguity_logging.py`
   - `EpiCor dried Yeast Fermentate` no longer belongs to generic yeast IQM after the exact branded-owner repair.
3. `test_v4_route_intent_unification.py`
   - structured route decision now emits `ROUTE_CLASSIFIER_VERSION = 1.3.1`; the test hardcoded `1.3.0`.

## Registry / producer evidence

- `BANNED_CBD_US` is the real local safety owner for CBD recognition.
- No valid primary `cannabidiol / botanical_ingredients` tuple exists in the current local registries.
- `hemp_seed_oil` is a real IQM parent with form `hemp seed oil (unspecified)`.
- `EpiCor dried Yeast Fermentate` is an exact branded owner in `standardized_botanicals.epicor`; `_match_quality_map(...)` now correctly returns `None` for the generic yeast IQM expectation.
- `scripts/scoring_input_contract.py` exports `ROUTE_CLASSIFIER_VERSION = "1.3.1"` and uses it in the emitted `route_decision`.

## Fixture corrections

- CBD test now asserts fail-safe safety recognition without inventing a primary canonical:
  - `canonical_id is None`
  - `canonical_source_db == "unmapped"`
  - `recognized_entry_id == safety_identity_id == "BANNED_CBD_US"`
  - `identity_decision_reason == "safety_recognition_without_primary_identity"`
- Hemp Seed Oil test now uses the real IQM tuple and asserts it remains scorable there.
- EpiCor was removed from the duplicate-IQM fixture list and replaced with a dedicated negative test asserting it cannot inherit the generic yeast IQM path.
- Route decision test now binds to `ROUTE_CLASSIFIER_VERSION` instead of a stale literal.

## Boundaries

- No assertions were weakened to hide a runtime mismatch.
- No runtime or data behavior changed.
- The tests still check the intended safety, ambiguity, and route-contract behavior against current registry truth.
