# Probiotic Evidence model replay

Status: corrected measurement complete; no production magnitude approved or integrated.

## Owner Check

- Owner: `scripts/scoring_v4/modules/probiotic_evidence.py::score_evidence` — the production probiotic Evidence result used by the public v4 scorer.
- Owner: `scripts/studied_formulas.py::assess_studied_formula` and the same module's native-context validation — formula identity and accepted study-context ownership.
- Owner: `scripts/scoring_v4/modules/probiotic_dose.py::score_dose` — the existing Dose consumer that must receive reviewed trial-range assessment in the production transfer.
- Will NOT create: a second scorer, evidence registry, probiotic identity owner, post-route Dose engine, or app-side calculation.

## Reproducible inputs

- Baseline commit: `880b17a7be94d515ca9b526b6d9b1300bcdd26ed`.
- Corrected scoring-experiment commit: `1f1f2d1808073435a8a77cad9310c26f75ec23bf`.
- Hardened analysis-tool commit: `211706aec26b4c40061cb24c2e6e3263077684bc`.
- Frozen manifest: 1,259 labels, including all 542 manifested probiotic labels; manifest SHA-256 `cbe041440eb1eb565edf2564298e106adfc35175f413d1aab26782447a1e8286`.
- Comparable probiotic scores: 535; every arm retains 535 scored, 2 not scored and 5 suppressed-safety labels.
- Candidate A receipt: `699a323ff59f2c593655998c12cad2704913a5ece5df2a76b9d1744405f2b7f5`.
- Candidate B receipt: `c5897920230311c04d86d7301b1786d2d3abf1d37bf2ad78dc35d5c62fc2acbc`.
- Normalized diagnostic receipt: `c7154cbd71e0d4eab1edc5aadff402fc720842637db5b26a22151f8dbb97605a`.
- Full per-label results and every quality-tier crossing: `PROBIOTIC_MODEL_REPLAY.json`.

Every arm ran Clean -> Enrich -> the public scoring seam. Each captured 1,259/1,259 products at the corrected scoring commit with the same input-manifest hash. All 717 non-probiotic rows are exactly unchanged. Route, status, Safety pillar and Safety verdict movements are zero across the full cohort.

## Models measured

### Candidate A — amount-free current core plus applicability

- 0–12: the current probiotic-owned clinical result with amount gates disabled.
- 0–8: product applicability, available only after positive probiotic-owned Evidence.
- No new replication component because the current core already contains top-N and research-depth signals.

An accepted exact studied formula receives direct applicability based on formula identity, preparation and source ownership without consulting its label amount. Otherwise the existing purpose-alignment result supplies direct, partial, broad or no applicability. Companion ingredients remain visible in diagnostics but cannot create probiotic core or applicability points.

### Candidate B — separated 10/6/4 facts

- 0–10: strongest single applicable probiotic evidence-family certainty/effect result, with no enrollment, top-N, depth or multiple-RCT bonus.
- 0–6: direct product applicability, available only after positive probiotic-owned certainty.
- 0–4: two accepted positive RCT families addressing the same applicable condition.

Replication is grouped by the registry's `trial_family`. Multiple publications from one trial count once. Exact-strain scope, valid native-context structure, clinician acceptance, primary patient-important between-group outcomes, purpose and population applicability are required. A pooled context prevents a second award for its constituent trials unless future curation proves independence.

### Diagnostic — normalize the amount-free current core

The probiotic-owned current 0–12 clinical result is multiplied to 0–20. This adds no new evidence fact and remains rejected as a production policy.

## Results

| Result | Candidate A | Candidate B | Normalized diagnostic |
|---|---:|---:|---:|
| Mean Evidence | 9.25 | 6.48 | 9.08 |
| Median Evidence | 10.6 | 6.0 | 12.0 |
| Maximum observed Evidence | 20.0 | 20.0 | 20.0 |
| Products at 20 Evidence | 1 | 4 | 2 |
| Products whose total moved | 344 | 412 | 419 |
| Mean total delta, all scored | +2.89 | +0.12 | +2.73 |
| Total delta range | -12.0 to +8.0 | -12.0 to +11.5 | -12.0 to +8.0 |
| Production-rounded quality-tier crossings | 125 | 103 | 106 |
| Safety pillar movements | 0 | 0 | 0 |
| Safety verdict movements | 0 | 0 | 0 |
| Status movements | 0 | 0 | 0 |
| Route movements | 0 | 0 | 0 |
| Non-probiotic controls changed | 0 / 717 | 0 / 717 | 0 / 717 |

Candidate A quality-tier movement:

- 47 Poor -> Needs improvement;
- 9 Needs improvement -> Poor;
- 45 Needs improvement -> Good;
- 2 Good -> Needs improvement;
- 22 Good -> Very good.

Candidate B quality-tier movement:

- 22 Poor -> Needs improvement;
- 36 Needs improvement -> Poor;
- 28 Needs improvement -> Good;
- 12 Good -> Needs improvement;
- 4 Good -> Very good;
- 1 Very good -> Good.

The normalized diagnostic causes 49 Poor -> Needs improvement, 10 Needs improvement -> Poor, 29 Needs improvement -> Good, 2 Good -> Needs improvement and 16 Good -> Very good crossings. It remains an unsupported numerical rescale.

These are quality-tier movements only. The replay does not claim a measured legacy `POOR -> SAFE` transition. Safety is a separate axis and did not change.

## Ceiling and calibration canaries

Neither candidate has a probiotic category ceiling. Candidate A reaches 20 through a 12-point clinical core plus 8-point applicability. Candidate B reaches 20 through 10 certainty + 6 applicability + 4 independent replication. Four infant-targeted labels reach Candidate B's 20-point Evidence ceiling; all use two distinct accepted BB-12 infant-colic `trial_family` values and matching infant positioning.

The highest observed overall total is 88.1 under Candidate A and 83.0 under Candidate B. Those are corpus observations, not mathematical category caps. Products can still lose points in Formulation, Dose, Transparency, Verification or Safety.

### Seed DS-01 Daily Synbiotic

| | Baseline | Candidate A | Candidate B | Diagnostic |
|---|---:|---:|---:|---:|
| Evidence | 13.6 | 14.8 | 12.0 | 11.4 |
| Total | 83.6 | 84.8 | 82.0 | 81.4 |
| Quality tier | Very good | Very good | Very good | Very good |

Candidate A gives 6.84 amount-free clinical-core points plus 8 direct-applicability points because this is an accepted exact studied commercial formula. Candidate B gives 6 certainty points plus 6 direct-applicability points and no independent-replication points. The registry describes independent confirmation as limited.

A focused mutation halves every declared AFU measurement. The production dose-qualified formula assessment then becomes unresolved, while the identity-only formula assessment remains accepted and both candidates' Evidence score and components remain exactly unchanged. This enforces the transfer boundary: amount can change Dose but cannot change Evidence identity or literature applicability.

Seed's remaining deductions remain visible in other pillars. A competitor's 99 is a calibration canary, not a target score.

## Reviewer findings and corrections

A fresh reviewer rejected the prior packet. The corrected replay closes each reproducible finding:

1. **Companion leakage:** labels `83159` and `326769` previously had 10.638 points entirely from companion evidence while probiotic strain points were zero. Both candidates now assign 0 probiotic Evidence and 0 applicability to those labels.
2. **Overlapping Candidate B core:** Candidate B no longer reads the aggregate native support score, enrollment, top-N, depth or the multiple-RCT base. Its core uses the strongest single applicable family; replication is a separate fact.
3. **Amount-dependent exact-formula precedence:** exact-formula Evidence now uses the existing formula owner's identity/preparation/source checks without its amount check. The Seed mutation proves the result is amount-independent.
4. **Replication leakage:** exact-strain scope, native-context validity, clinician acceptance, canonical outcome role, purpose, structured population and `trial_family` deduplication are enforced. Adult labels cannot inherit infant replication; pooled evidence cannot also create constituent-trial credit.
5. **Missing regressions:** focused tests cover companion-only credit, single versus multiple-RCT core equivalence, infant/adult population separation, same-family publication deduplication, invalid scope, non-efficacy outcomes, unapproved contexts and exact-formula amount independence.
6. **Native amount leakage:** Candidate A initially selected and stacked native strain research using the amount-derived `dose_applicable` flag. The final model ignores native dose status, keeps the strongest research record, and has a mixed-strain regression proving dose-flag changes cannot move Evidence.
7. **Misleading audit terminology:** the analyzer now reports quality-tier exits and full-cohort controls. It no longer infers a legacy `POOR -> SAFE` field from quality thresholds.

## Decision packet

The permanent 12/20 ceiling and automatic 12-to-20 rescale remain rejected.

Candidate A is the continuity comparison. It preserves the present clinical-core behavior after removing companion and amount leakage, but its eight-point applicability component moves 125 labels across quality tiers and still relies on a core whose internal research-depth signals are bundled.

Candidate B has the clearer numerical ownership: strongest single-family certainty, applicability and independently replicated applicable evidence are separate. It produces 103 quality-tier crossings and reaches 20/20 without a category cap. It also moves more individual labels and produces more downward crossings because it removes bundled depth and companion credit rather than preserving them.

Recommended production direction: Candidate B's non-overlapping fact model, exact-formula precedence and positive-evidence/population gates. The exact 10/6/4 magnitudes are still a Sean policy decision. Before integration, review the 103 crossings in the JSON and approve or revise those magnitudes. The same production change must move reviewed trial-range assessment into the existing Dose owner and replace the old dose-based Evidence explanation/state; code and copy must agree.

## Verification

- Focused experimental regressions: 11 passed.
- Broader probiotic Evidence focused rung: 132 passed, 7 corpus-output skips.
- Full fast checkpoint: 17,847 passed, 168 skipped, 1 existing Ravage cinnamon expected failure.
- Snapshot integrity: 1,259/1,259 products in every arm; identical manifest and per-label input hashes; successful metadata receipts.
- Cross-route controls: 0/717 non-probiotic rows changed; zero route, status, Safety pillar or Safety verdict changes.
- Candidate B replication: four infant-targeted products, each backed by two distinct accepted BB-12 infant-colic trial families.
- No production scoring/config change is present on `codex/quality-completion`; the experiment remains isolated on `codex/probiotic-model-measurement`.
