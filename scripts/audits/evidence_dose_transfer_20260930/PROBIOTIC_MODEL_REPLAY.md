# Probiotic Evidence model replay

Status: measurement complete; no production magnitude approved or integrated.

## Owner Check

- Owner: `scripts/scoring_v4/modules/probiotic_evidence.py::score_evidence` — the production probiotic Evidence result used by the public v4 scorer.
- Owner: `scripts/scoring_v4/modules/probiotic_dose.py::score_dose` plus reviewed contexts in `scripts/studied_formulas.py` — the existing Dose consumer that must receive trial-range assessment in the integration change.
- Will NOT create: a second scorer, evidence registry, probiotic identity owner, post-route Dose engine, or app-side calculation.

## Reproducible inputs

- Baseline commit: `880b17a7be94d515ca9b526b6d9b1300bcdd26ed`.
- Measurement-only branch commit: `84b4902b`.
- Frozen manifest: 1,259 labels, including all 542 manifested probiotic labels; manifest SHA-256 `cbe041440eb1eb565edf2564298e106adfc35175f413d1aab26782447a1e8286`.
- Comparable probiotic scores: 535; statuses remain 535 scored, 2 not scored and 5 suppressed safety in every arm.
- Candidate A receipt: `d1113ef3ef9b72a7999fc082ada0c23077203dcc019c91d80c7b92a01784e50a`.
- Candidate B receipt: `0ea549b61bf450f01002d68e29e6bdbe86775b462b69fce2e916582cfe144a68`.
- Normalized diagnostic receipt: `8bfe9baa0bc0d25429c5bd0bc7b923df81aeda6a67c2c71b6fdcc136a3793872`.
- Full per-label results and every tier crossing: `PROBIOTIC_MODEL_REPLAY.json`.

All arms ran Clean -> Enrich -> the public scoring seam. Frozen-input hashes remained unchanged. No non-probiotic total, pillar, status or route changed.

## Models measured

### Candidate A — preserve the current clinical core

- 0–12: the current clinical result with the generic amount gate disabled.
- 0–8: direct product applicability.
- No new replication component because the generic core already contains top-N and research-depth signals.

Applicability requires positive clinical credit owned by a probiotic strain or exact formula. An accepted exact studied formula receives direct applicability. Otherwise the existing purpose alignment result supplies direct, partial, broad or no applicability; generic species-level identity receives reduced weight.

### Candidate B — separated 10/6/4 facts

- 0–10: strongest applicable evidence-family certainty/effect result, with no top-N or depth bonus.
- 0–6: direct product applicability under the same positive-evidence and ownership gates.
- 0–4: two accepted positive RCT families addressing the same applicable condition.

Replication is grouped by `trial_family`. Multiple publications from one trial count once. Pooled evidence does not also earn constituent-trial replication credit. Population-specific replication requires the matching product population.

### Diagnostic — normalize the current core

The amount-free current 0–12 clinical result is multiplied to 0–20. This adds no new evidence distinction and is not a recommendation.

## Results

| Result | Candidate A | Candidate B | Normalized diagnostic |
|---|---:|---:|---:|
| Mean Evidence | 10.29 | 8.79 | 10.50 |
| Median Evidence | 12.0 | 9.8 | 12.8 |
| Maximum observed Evidence | 20.0 | 19.0 | 20.0 |
| Products at 20 Evidence | 4 | 0 | 27 |
| Products whose total moved | 290 | 419 | 419 |
| Mean total delta, all scored | +3.94 | +2.43 | +4.14 |
| Total delta range | 0.0 to +8.5 | -3.8 to +9.9 | -2.2 to +8.0 |
| Production-rounded tier crossings | 125 | 88 | 123 |
| Safety pillar movements | 0 | 0 | 0 |
| Safety verdict movements | 0 | 0 | 0 |
| Status movements | 0 | 0 | 0 |
| Route movements | 0 | 0 | 0 |

Candidate A tier movement:

- 58 Poor -> Needs improvement;
- 45 Needs improvement -> Good;
- 22 Good -> Very good.

Candidate B tier movement:

- 40 Poor -> Needs improvement;
- 4 Needs improvement -> Poor;
- 28 Needs improvement -> Good;
- 3 Very good -> Good;
- 14 Good -> Very good.

The normalized diagnostic causes 71 Poor -> Needs improvement, 36 Needs improvement -> Good and 16 Good -> Very good crossings. It is broad inflation from a numerical rescale, without a new evidence fact.

The compatibility alias would report 58, 40 and 71 `POOR -> SAFE` movements respectively. Those are quality `Poor -> Needs improvement` crossings. Safety did not change.

## Calibration canary: Seed DS-01 Daily Synbiotic

The frozen raw label identifies product `PG_SUB_35E0BD3374BF494B80FEABE87FC559E7` as Seed DS-01.

| | Baseline | Candidate A | Candidate B | Diagnostic |
|---|---:|---:|---:|---:|
| Evidence | 13.6 | 14.8 | 12.0 | 11.4 |
| Total | 83.6 | 84.8 | 82.0 | 81.4 |
| Quality tier | Very good | Very good | Very good | Very good |

Candidate A gives 6.84 clinical-core points plus 8 direct-applicability points because this is an accepted exact studied commercial formula. Candidate B gives 6 certainty points plus 6 direct-applicability points and no independent replication points. The registry currently describes independent confirmation as limited.

Seed's score is not constrained by a probiotic category ceiling in either candidate. Its remaining deductions are visible: Verification 8/15, Transparency 12/15 and the measured Evidence result. A competitor's 99 is a calibration canary, not a target score.

## Defects caught during measurement

Three draft defects were found and corrected before the final receipts:

1. Companion-ingredient evidence could initially unlock probiotic applicability. The final arms require probiotic-owned strain/formula evidence.
2. Replication initially credited adult products with BB-12 infant-colic trials. The final arm requires purpose and population applicability; only four infant-targeted products receive that replication credit.
3. Identity plus claim alignment could initially award applicability when clinical certainty was zero. The final arms require positive Evidence first; null, negative, unresolved and no-qualifying-evidence results receive zero applicability.

The Seed replay found the inverse precedence issue: broad marketing copy had reduced an accepted exact-formula result. The final arms let the stronger exact-formula owner determine direct applicability.

## Decision

The permanent 12/20 ceiling and automatic 12-to-20 rescale remain rejected.

Candidate A is useful as the continuity/upper comparison, but an eight-point applicability component moves 125 products across quality tiers and concentrates large awards in 290 products. It should not land unchanged.

Candidate B has the cleaner numerical ownership: certainty, applicability and independently replicated applicable evidence are separate. It also produces fewer tier crossings and can mathematically reach 20/20, although no current frozen label satisfies all three maxima. The exact 10/6/4 magnitudes remain a calibration choice and are not approved by this replay alone.

Recommended production direction: use Candidate B's non-overlapping fact model, retain exact-formula precedence and the positive-evidence/population gates, then review the 88 listed crossings before approving magnitudes. The same integration must move reviewed trial-range assessment into the existing Dose owner and replace the old dose-based Evidence explanation/state; scoring and copy cannot disagree.

## Verification

- Focused default-behavior rung: 121 passed, 7 corpus-output skips.
- Snapshot integrity: 1,259/1,259 products in every arm, matching input hashes and successful metadata receipts.
- Cross-route control: zero non-probiotic score, pillar, status or route changes.
- Candidate B replication: four products, all backed by two distinct accepted BB-12 infant-colic `trial_family` values and an infant-targeted product context.
- No production scoring/config change was retained on `codex/quality-completion`.
