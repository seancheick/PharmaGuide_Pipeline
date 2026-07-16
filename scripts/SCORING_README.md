# PharmaGuide Scoring README

> Operational summary | Last verified: 2026-07-16

## The short version

PharmaGuide ships one public score: the v4 six-pillar `/100` quality score.

```text
Enriched product
  → score_products_v4.py (Stage-3 batch owner)
  → scoring_v4.scored_artifact.build_scored_artifact()
  → one v4 score + pillars + status + diagnostics
  → final SQLite + detail blob
```

`score_supplements.py` is no longer an operational entrypoint. It may remain in
the tree temporarily for post-rebuild test disposition, but production,
preflight, release, export, and audit-preview paths do not invoke it.

## Public export contract

| Field | Meaning |
|---|---|
| `quality_score_v4_100` | Canonical shipped score, finite only when status is `scored` |
| `quality_score_status` | `scored`, `suppressed_safety`, or `not_scored` |
| `quality_pillars_v4` | Six consumer-facing pillar scores and explanations |
| `quality_tier` | Elite, Excellent, Strong, Acceptable, Weak, or Poor |
| `raw_score_v4_100` | Audit-only module math; never a display fallback |
| `score_100_equivalent` | Compatibility mirror of `quality_score_v4_100` |
| `score_display_100_equivalent` | Compatibility display mirror of the v4 score |

Frozen rule: `score_quality_80` and `score_display_80` are retired export
fields and must not return.

## Six pillars

| Pillar | Max | Purpose |
|---|---:|---|
| Formulation | 20 | Form quality, delivery, and formulation fit |
| Dose | 20 | Category-aware dose adequacy and excessive-dose handling |
| Evidence | 20 | Verified human evidence and category fit |
| Transparency | 15 | Amount disclosure, proprietary blend opacity, completeness |
| Verification | 15 | Verified third-party testing, COA, GMP, certifications |
| Safety/Hygiene | 10 | Product safety hygiene and bounded clean-label concerns |

The score is the bounded sum of the six category-aware pillars. Pillar
adapters normalize against what each product archetype can honestly achieve;
they are not a cosmetic stretch of legacy section totals.

## Runtime ownership

| Concern | Authority |
|---|---|
| Cleaner row role and score eligibility | `enhanced_normalizer.py` |
| Canonical enriched scoring rows | `scoring_input_contract.py` |
| Product taxonomy | `supplement_taxonomy.py` |
| V4 module dispatch | `scoring_v4/router.py` |
| Safety identity normalization | `identity/safety.py` |
| V4 safety policy | `scoring_v4/gate_safety.py` |
| Completeness policy | `scoring_v4/gate_completeness.py` |
| V4 scoring configuration | `scoring_v4/config/quality_score.json` |
| Public score assembly | `scoring_v4/quality_score.py` |
| Complete Stage-3 artifact | `scoring_v4/scored_artifact.py` |
| Stage-3 batch I/O + atomic writes | `score_products_v4.py` |
| Final contract and quarantine | `build_final_db.py` |

Do not add a second classifier in a scorer or exporter. When classification is
wrong, fix the owning taxonomy/scoring-input/router boundary and add a
cross-stage regression test.

## V4 execution order

1. `class_for_product()` selects one module.
2. The safety gate consumes canonical safety signals.
3. BLOCKED or UNSAFE short-circuits numeric scoring.
4. CAUTION is carried forward while score math continues.
5. The completeness gate excludes rows without a usable product/ingredient
   contract; missing disclosure that can be represented honestly remains soft
   debt instead of being invented.
6. One category module computes its rubric result.
7. Confidence and provenance are attached.
8. The six public pillars and tier are assembled.
9. `scored_artifact.py` projects the result, shared coverage, strict diagnostics,
   compatibility mirrors, safety precedence, and provenance exactly once.
10. `build_final_db.py` consumes that artifact without rescoring, validates the
    frozen export, and quarantines products
    that cannot ship truthfully.

## Module routing

Current routing priority is implemented only in `scoring_v4/router.py`:

1. probiotic
2. prenatal multi intent
3. B-complex
4. multivitamin
5. sports
6. fiber/digestive
7. omega-3
8. generic fallback

The router uses canonical taxonomy and panel composition before guarded label
signals. `general_supplement` is a fallback identity, not evidence that a
product belongs in the generic module.

## Status and verdict rules

| Condition | Status | Public score |
|---|---|---|
| Confirmed banned or recalled safety condition | `suppressed_safety` | null |
| Required identity/payload is unusable | `not_scored` | null and quarantined |
| Scoreable SAFE, POOR, or CAUTION product | `scored` | finite `/100` |

Verdict precedence is:

```text
BLOCKED > UNSAFE > NOT_SCORED > CAUTION > POOR > SAFE
```

Never replace a null suppressed score with `raw_score_v4_100`, zero, or a
cohort fallback. Safety verdict and evidence remain visible without
a rankable number.

## Safety applicability

The primary verdict is based on US federal/state applicability. Safety matches
retain:

- `jurisdictions`
- `us_applicable`
- `regional_advisories`

Non-US restrictions remain evidence/advisory metadata; they do not silently
become a US ban. CBD and similarly non-scorable supplement identities retain
canonical identity and interaction metadata while remaining ineligible for
quality scoring; B0/safety precedence remains authoritative.

## Dose, RDA/AI, and UL policy

- Adequacy uses minimum/recommended daily exposure (`per_day_min`).
- UL and safety checks use maximum daily exposure (`per_day_max`).
- `rda_ul_data.data_by_group` preserves demographic references.
- `reference_profile` names the adult-neutral compatibility summary.
- Unit input must pass through the shared canonicalizer before conversion.
- A malformed row is contained; it must not erase unrelated adequacy or safety
  findings.

### Folate and folinic forms

The pipeline applies the folic-acid UL only to an identified folic-acid
contribution.

- Label-declared mcg DFE is preserved for adequacy.
- Explicit mcg DFE folinic acid/folinate/leucovorin rows may retain adequacy,
  but the folic-acid UL is not applied.
- Bare mcg folinic/folinate/leucovorin without a verified DFE conversion has
  adequacy `unknown` and `scoring_eligible=false`.
- Absent or inconsistent `%DV` does not authorize a guessed conversion.
- No folinic UL is invented.
- A future `%DV` recovery rule must be named, tested, and consistency-checked.
- Unknown-form folate at a clinically material level produces an indeterminate
  UL review signal rather than a guessed exceedance or silent clearance.

## Config discipline

`scoring_v4/config/quality_score.json` is the public scoring configuration.
Every live key must have a behavioral test. Remove obsolete knobs instead of
wiring them merely because they exist.

`config/scoring_config.json` is retained only for non-production historical
tests until the retired scorer is deleted. It is not read by the Stage-3
producer, final export, or release path.

## Making a scoring change

1. Identify the owning layer in the table above.
2. Add a focused regression test and confirm it fails for the intended reason.
3. Make the smallest owner-level change.
4. Run the focused test through `scripts/test.sh fast`.
5. Run `scripts/test.sh fast` at the phase boundary.
6. For a release candidate, run `scripts/test.sh release` and then the required
   full profile.
7. Rebuild only through the canonical snapshot/release workflow.
8. Review per-product score, status, verdict, safety, module, and pillar deltas.
9. Re-freeze `test_scoring_snapshot_v1.py` only for named, reviewed changes.

Never accept an aggregate-only comparison: offsetting product changes can hide
clinical or classification drift.

## Supported verification commands

```bash
scripts/test.sh fast -k scoring_v4
scripts/test.sh fast scripts/tests/test_scoring_snapshot_v1.py
scripts/test.sh release
scripts/test.sh full
```

Operational pipeline, snapshot, and release commands are documented in
`PIPELINE_OPERATIONS_README.md`. Do not use raw pytest or direct ad-hoc export
commands as release evidence.
