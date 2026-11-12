# Evidence floor, Part C: measurement and validation (2026-11-12)

Branch `claude/evidence-floor-part-c` on main `648f27224`. Authority: `DR_PHAM_ANSWERS_20261112.md`
Part C (Sean's rule) and Part B section 5 (CEE provenance). Agent work (Claude); the classification
below applies Sean's rule. It is not a clinician review.

## Rule and implementation

> A finding that demonstrates only exposure, target engagement, or an unvalidated physiological
> response cannot, by itself, unlock the primary Evidence floor.

| Seam | Owner | Change |
|---|---|---|
| Outcome contract | `clinical_evidence_schema.py::_outcome_errors` | optional `surrogate_class` (`exposure`, `target_engagement`, `unvalidated_physiological_response`), valid only on `kind: surrogate` rows |
| Clinical-outcome owner | `clinical_applicability.py::outcomes_beyond_exposure` | qualifying outcomes without a `surrogate_class` |
| Evidence owner | `generic_evidence.py::_primary_mass_floor` via `_floor_study_type` | skips a floor anchor when none of the match's own applicable, scoring-eligible contexts has such an outcome; an exposure-only trial family cannot make the floor `rct_multiple` (strong base) either |

`_applicable_contexts` (shared with `_qualified_trial_families`) reads only the match's `population_applicability.context_ids`, so a classified context
cannot borrow a functional result from another preparation or population. A match with no reviewed
context keeps today's behavior. Ordinary Evidence points, the nutrition-authority floor, the omega
floor, review status and every config magnitude are unchanged. No product override, no export field
and no rule on `purpose` or `kind`.

## Classification (12 entries, `backed_clinical_studies.json`)

Criterion: a context is classified only when every qualifying outcome shows no more than the
supplied compound or its stores (exposure), the material's direct biochemical action (target
engagement), or a physiological change that is not an established clinical measure that defines or
monitors the studied condition. A context with any qualifying functional or accepted outcome stays
unclassified. Non-qualifying surrogate rows in a classified context carry the same class for
consistency, which has no scoring effect. Each classified context records in its `limitations` that
the classification is agent work applying Sean's rule, not part of that context's clinician review.

| Entry / context | Qualifying finding | Class |
|---|---|---|
| INGR_CREATINE_ETHYL_ESTER / 19228401 | muscle total-creatine content | exposure |
| INGR_REDUCED_GLUTATHIONE / 24791752 | blood and buccal glutathione stores; lymphocyte and NK-cell markers | exposure; unvalidated response |
| PRECLIN_BETAINE_HCL / 31485804 | time to baseline gastric pH after a meal | target engagement |
| INGR_NATTOKINASE / 26109079 | coagulation and fibrinolysis markers (D-dimer, FDP, aPTT, factor VIII, antithrombin) | target engagement |
| INGR_CALCIUM_CASEINATE / 21045172 | acute muscle protein synthesis | unvalidated response |
| BRAND_TESNOR / 35129040 | serum free testosterone in healthy men aged 21-35 | unvalidated response |
| BRAND_PRIMAVIE_SHILAJIT / 26395129 | total and free testosterone, DHEAS in healthy men aged 45-55 | unvalidated response |
| INGR_BILBERRY / 32106548 | HFC-1 ciliary accommodation marker | unvalidated response |
| BRAND_KANEKA_UBIQUINOL / 32326664 | flow-mediated dilation (and NOx, LDL oxidation lag) | unvalidated response |
| BRAND_CARNIPURE / 11788381 | MRI muscle-tissue disruption | unvalidated response |
| INGR_L_CARNOSINE / 27040154 | HOMA-IR in non-diabetic adults | unvalidated response |
| PRECLIN_NMN / 39531138 | blood NAD+ (meta-analysis; no floor base) | exposure |

An independent blind classifier, given the rule and the outcome records but not my labels, agreed on
the first seven and proposed the last four. It was unsure about three contexts. I kept all three as
accepted surrogates, each a clinical measure of its studied condition:

- selenium 38243784, TSH in Hashimoto's thyroiditis
- ceramides 38999848, TEWL for the skin barrier
- carnosine 38172006, OGTT glucose

They are close calls for Sean. Selenium anchors 37 labels.

**Census.** 37 scoring-eligible contexts have qualifying outcomes that are all surrogates. 12 are
classified above. The other 25 are accepted clinical measures or functional measures recorded as
surrogates:

- blood pressure: potassium, magnesium, garlic, quercetin, arginine, taurine
- LDL cholesterol: psyllium, plant sterols, pantethine
- HbA1c in type 2 diabetes: berberine (two records)
- TSH in Hashimoto's: selenium
- OGTT glucose: carnosine 38172006
- homocysteine in hyperhomocysteinemia: Quatrefolic
- TEWL and skin hydration: ceramides (two contexts)
- lean mass: creatine monohydrate
- cognitive and psychomotor tasks: bacopa, caffeine, glycine, theanine, tyrosine (four contexts)

`test_every_surrogate_only_finding_was_reviewed_under_the_rule` pins this split. A later review that
makes a context surrogate-only must classify it or add it to the accepted list. One example is a mixed
context such as Carnipure 20045157 losing its soreness row.

**Judgment calls for Sean:**

- **Explicitly accepted.** A reviewer's credit scope that limits a finding to its marker is not
  treated as "explicitly accepted". If it were, CEE, the case that prompted the rule, would be exempt.
  Kaneka's signed limitation reads "FMD is a surrogate; the trial does not show cardiovascular events
  … credit is limited to this endothelial-function finding". Bilberry's trial named HFC-1 as its
  evaluation outcome. Sean's yes is needed before merge, because bilberry moves 38 labels (13 of them
  down a tier).
- **FMD versus TEWL.** Both are instrument measures. TEWL is kept because it quantifies the studied
  condition itself (water loss through a dry skin barrier). FMD is classified because endothelial
  dysfunction is an intermediate pathway state without symptoms; its relevance rests on cardiovascular
  outcomes the trial did not measure.
- **PrimaVie.** The men were screened with the ADAM symptom questionnaire, not biochemically diagnosed
  as testosterone-deficient. So testosterone did not define the studied condition, and the context is
  classified.
- **Impact today.** Neither Kaneka nor PrimaVie anchors a floor on any current label.

## Floor contributors

A census re-ran the real scorer on stored enriched inputs for the 2,683 clinically anchored floor
rows and recorded each anchor's entry and contexts.

- **Classified only (95 labels):** every applicable context is classified. Bilberry 38, betaine HCl
  27, glutathione 19, CEE 5, calcium caseinate 5, nattokinase 1.
- **Mixed (86 labels):** a classified context sits beside a qualifying functional one, so the floor
  is kept. Carnipure 50 (20045157 soreness), carnosine 33 (38172006 OGTT), Tesnor 3 (35928723 AMS).
- **No current label:** PrimaVie and Kaneka anchor none.

## Replay (frozen raw labels, Clean → Enrich → Score)

127 labels: the 95 classified-only labels and 32 controls. The controls are mixed Carnipure, carnosine
and Tesnor, plus potassium, selenium, psyllium, glycine, CoQ10, ceramides and cranberry. Baseline is
`648f27224` (main); candidate is `5c6b7b763`. `compare`: **95 changed, exactly the predicted set; all
32 controls identical.** The review-fix commit `af8691468` (floor-strength fix, NMN, attribution) was
re-measured on the same frozen inputs: 0 of 127 differ from `5c6b7b763`, 0 of 15 Perilla labels differ
from main, and the raw canaries pass 33/33. Per-label values: `evidence_floor_part_c_movement_20261112.json`.

| Cause (anchor) | n | Floor raw | Evidence /20 | Ordinary points | Total Δ | Tier moves |
|---|---|---|---|---|---|---|
| bilberry | 38 | 11.0 → 0 | 12.2 → 4.3–10.3 | unchanged | −7.9 to −1.9 | Good→Needs improvement 13; Very good→Good 1; Needs improvement→Poor 1 |
| betaine HCl | 27 | 9.35 → 0 | 10.4 → 3.4 | unchanged | −7.0 | Good→Needs improvement 11 |
| reduced glutathione | 19 | 6.6 → 0 | 7.3 → 1.9 | unchanged | −5.4 | Needs improvement→Poor 5 |
| creatine ethyl ester | 5 | 6.6 → 0 | 7.3 → 2.4 | unchanged | −4.9 | Needs improvement→Poor 5 |
| calcium caseinate | 5 | 9.35 → 9.35 (betaine anhydrous, 4) or 0 (1) | 10.4–12.4 → 3.4–12.4 | unchanged | −7.0 to 0 | Good→Needs improvement 1 |
| nattokinase | 1 | 6.6 → 0 | 7.3 → 1.4 | unchanged | −5.9 | Good→Needs improvement 1 |
| controls (32) | 32 | unchanged | unchanged | unchanged | 0 | none |

**223084 Creatine Ethyl Ester:**

| | Before | After |
|---|---|---|
| Floor | 6.6 (rct_single × mixed) | none |
| Ordinary Evidence | 2.4 | 2.4 |
| Evidence | 7.3 | 2.4 |
| Total | 56.9 | 52.0 |
| Tier | Needs improvement | Poor |
| Status, Evidence state, safety | complete, `evaluated_applicable`, `no_known_catalog_concern` | unchanged |

On all 127 labels these stayed identical: ordinary Evidence points, the other five pillars,
`quality_assessment_status` (91 complete, 36 partial), `evidence_result_state` and
`product_safety_status`. The 36 partial labels were partial before, because of other uncovered
ingredients.

The Evidence reason moves from the floor sentence to the existing "Limited human evidence for these
ingredients."

The enriched record changed only on the five CEE labels: their `key_endpoints` text from the
provenance commit `b6a09dd37`.

**Raw canaries:** `freeze_contract_snapshots.py --check --raw-root` found 32 unchanged and one drift,
223084, with the values above. That canary was refreshed with a manifest changelog entry; the check
then passed 33/33.

## #455 Perilla validation (main `648f27224`)

15 frozen labels:

- the five exact labels from `perilla_exact_source_labels.json`
- 299740, the same seed extract in a combination formula
- leaf-extract controls 330235–330237 and 2514
- unspecified or Benegut preparations 61929, 277671 and 59603
- two synthetic controls: seed oil (from 299734) and an unspecified "Perilla Extract" (from 311422)

Results:

- **This branch:** 0 of 15 changed, so Part C does not touch Perilla.
- **Five exact labels:**
  - Evidence 0 (`applicability_unestablished`, no clinical match and no floor), so no affirmative
    efficacy credit.
  - Dose 11.4, `no_benchmark_neutral`.
  - Status complete.
- **Before #455 (`6c62ef493`):** these five were partial with Dose 0. The completion and the neutral
  Dose are #455's intended change.
- **Seed oil and unspecified controls:** still partial, Dose 0, Evidence 0, total unchanged. #455
  changed only their internal state label (`clinical_review_not_covered` →
  `applicability_unestablished`), which remains pending. The review does not transfer.
- **Leaf-extract and Benegut controls:** unchanged by #455. Their Dose 11.4 predates it.
- **299740:** one fewer not-yet-evaluated ingredient, with score, Dose and Evidence unchanged.

No defect found.

## Scoring performance (controlled, identical frozen inputs)

The test used 36 frozen enriched labels from the replay set (input sha256 prefix `9c874e83c9912397`):

- 9 affected anchors, including 223084
- controls, including the partial (held) Perilla seed-oil and unspecified labels
- active-row counts from 1 to 15

Each round started a fresh process per arm, ran one warm-up pass, then timed 8 `build_scored_artifact`
runs per product. The arms alternated: main `648f27224`, then this branch `a5fb8084a`, for 4 rounds.

| Arm | Sum of per-product warm medians, by round (s) | Median | Peak RSS median |
|---|---|---|---|
| main | 1.636, 1.621, 1.634, 1.647 | 1.635 s | 200.4 MiB |
| branch | 1.644, 1.691, 1.667, 1.650 | 1.659 s | 196.1 MiB |

- **Time:** +1.4%. The round-to-round spread is 1.6% on main and 2.9% on the branch, and the ranges
  overlap.
- **Peak memory:** −2.1%, also within noise.
- **Where the extra work comes from:** for each positive match, the floor reads the match's own
  applicable contexts from the lru-cached reviewed registry and checks their qualifying outcomes.
  No reusable derived view was added or changed, and the helpers are read-only. So the
  derivation-count and input-isolation guards were not extended.
- **Scores:** identical across rounds within each arm. The 9 affected labels differ between arms by
  design. The other 27 are identical.

## Limits

- The classification is agent review applying Sean's rule, with a blind second check. It is not
  clinician review.
- The census used stored enriched inputs. The final corpus build is the complete measurement. The
  canaries and the replay found no movement outside the predicted 95.
- `test_scoring_snapshot_v1.py` reads stored corpus output, so it runs only after Sean's build.
- The `local` rung in this clean worktree had 427 passed and 0 failed. 137 corpus/build-dependent
  tests were skipped because there is no `scripts/products`, and the skip guard rejects those skips.
  They read stored build artifacts that this batch cannot change before the corpus build.
- The changed entries' citations were checked by running the backed-studies verifier's own `main()`
  on the 11 entries: 72/72 PMIDs ok, with 0 title mismatches, drifts, ghost suspects or not-found.

Receipts (frozen inputs, snapshots, full records, compare reports, canary log, data patches):
`~/pg_quality/evidence_floor_part_c_20261112/`.

## Independent review (fresh context, requirement plus diff only)

No blockers. The findings and what was done with each:

1. **Agent classification inside Dr. Pham-signed contexts.** Fixed. Each classified context's
   `limitations` now says the classification is agent work and not part of that clinician review, and
   the CEE `basis` names the agent-prepared reading. The interpretation of "explicitly accepted" is
   Sean's call (see the judgment calls above).
2. **FMD versus TEWL, and PrimaVie.** The reasoning is recorded above. Neither Kaneka nor PrimaVie
   anchors any current label.
3. **Rows classified depending on their siblings.** Addressed with the census pin rather than
   piecemeal row edits: a context that becomes surrogate-only must be classified or accepted, so CI
   would fail first.
4. **NMN NAD+ unclassified.** Fixed (exposure; it has no floor base).
5. **An exposure-only trial family could still make the floor `rct_multiple`.** Fixed in
   `_floor_study_type`. The first version over-applied the downgrade to designs stated by the record
   itself. The owner slice caught it (2 failures in `test_evidence_prominence_ownership.py`), and it
   was corrected with fail-first regression cases. No current label moves.
6. **Glycemia wording, duplicated context selection, schema version.** Fixed: "glycemia in diabetes or
   prediabetes", one shared `_applicable_contexts`, and schema 5.7.0.

**Owner/consumer slice** (43 files that read the floor, schema or applicability owners):
- On the first fix version: 3,302 passed, 2 failed. Those were the over-applied downgrade.
- After the correction: those files plus the floor files, 125 + 871 passed.
