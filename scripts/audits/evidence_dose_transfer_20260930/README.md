# Evidence → Dose responsibility transfer

Status: all-route owner inventory complete; approved probiotic transfer integrated and source pushed to main (Q47). Generic/omega transfer and wider Dose-policy decisions remain open. Phase2 Ravage closure is Q48; final prominence/serving corrections remain pending. Source through `3ee91eae` is pushed with Sean's approval; no catalog release.

Inventory baseline: pipeline `880b17a7`; focused owner/role suite 103 passed, 7 skipped,
1 strict xfail. The frozen 1,261-label audit sample is
`~/pg_quality/closure_20261001/deadcode_6917_1261.jsonl`.

## Invariant and owners

An amount-based adequacy or exposure judgment may leave Evidence only when the
same judgment is already made by an existing Dose owner or is added to that
owner in the same change. Clinical trial amounts remain registry source facts.
Identity, preparation, intervention, population, purpose and outcome
applicability remain Evidence judgments.

Owner: `scripts/scoring_input_contract.py::get_evidence_subject_rows` for the
subject set; `scripts/scoring_v4/exposure.py::row_exposure`, enrichment
`rda_ul_data.adequacy_results`, and the existing route Dose modules for amount
assessment. Will NOT create a second subject provider or post-route Dose engine.

## Original amount inventory at `880b17a7` — historical

The table preserves the initial findings. The probiotic row is closed by Q47 and the approved certainty/applicability/replication model; it is not a pending 12/20 ceiling decision. Generic and omega transfers remain open.

| Route / decision | Baseline Evidence owner | Baseline Dose coverage | Original transfer classification |
|---|---|---|---|
| Generic record minimum (`min_clinical_dose`) and undisclosed amount | `clinical_applicability.py::assess_clinical_applicability`; `evidence_resolver.py::resolve_evidence_for_row`; `generic_evidence.py::score_evidence` | The registry has 16 dose-bearing records: 11 top-level studied-dose records plus 5 applicability-policy dose records. Existing Dose covers KSM-66, white kidney bean, amla, MSM/OptiMSM, BCAA and official nutrient adequacy. It does not yet own equivalent benchmarks for nine named groups below. | Add a typed, audit-visible studied-dose assessment to the existing Dose result before deleting the Evidence veto. Numerical treatment of a missing benchmark remains D24 policy. Shared removal cannot land while any record lacks an owner. |
| Generic primary floor amount gate | `generic_evidence.py::_primary_mass_floor` | Route Dose owns amount adequacy; shared role classifier owns prominence | Replace its private mass-primary selection with `classify_ingredient_roles`; Evidence floor eligibility may use research/role facts but not label amount. Dose retains the exposure judgment. |
| Literature `studied_dose_exposure` gate | `evidence_resolver.py::resolve_evidence_for_row` | Partial; only routes/reference families with an existing benchmark | Same as generic record minimum. Do not discard the studied exposure from the source record. |
| Probiotic trial-dose applicability, up to 8 Evidence points | `probiotic_evidence.py::score_evidence` via native context `dose_applicability_credit` | `probiotic_dose.py::score_dose` owns disclosed CFU and adequacy, but most current adequacy tiers are industry-potency rather than trial-dose judgments | Remove dose from Evidence only with an explicit Evidence magnitude decision. Preserve trial-dose comparison in Dose metadata; do not silently convert the 12-point clinical subscale to 20. |
| Omega Evidence selected/graduated by daily EPA+DHA or DHA | `evidence_resolver.py::resolve_omega_evidence_standard` | `omega_dose.py::score_dose` already owns the same explicit EPA+DHA exposure and directed-serving interval | Remove amount thresholds from Evidence. A purpose-only record-selection rule and its magnitudes require approval; do not award 20 merely because exposure leaves Evidence. |

The uncovered generic groups are lactoferrin; Carnipure/L-carnitine; ALCAR;
the zinc-lozenge 80–207 mg intervention; L-arginine; D-mannose; D-aspartic
acid; Tesnor; and Sytrinol. Generic Dose's current no-reference disclosure
credit is not an adequacy judgment and does not satisfy the transfer invariant.

Amount comparisons in `clinical_applicability`, `evidence_resolver`, and
`generic_evidence` are shared gates. Do not introduce a record allowlist or a
route-specific exception: globally removing them before those nine groups have
an existing Dose benchmark would create an assessment gap.

## Observed baseline

In the frozen 1,261-label sample, the route distribution is small but exposes
the coupling:

- Omega: 5 products; Evidence/Dose pairs are 0/0, 0/4.3, 13.9/17.5,
  0/4.5 and 0/7.3.
- Probiotic: 8 products; reviewed clinical strength can coexist with low Dose
  (for example Evidence 5.4 with Dose 3.1), and one product receives Evidence
  9.0 with Dose 18.2.
- Generic: 1,003 products; the most common combinations include Evidence 0
  with Dose 9.5 (329), 14.5 (246), and 11.4 (113). This is not by itself proof
  of a dose-gate defect because completed negative/no-evidence reviews also
  score zero; candidate replay must classify drivers per product.

## Required implementation tests

All tests pass through `build_scored_artifact` or the route's production scorer.

1. The same reviewed evidence record produces the same Evidence score at a
   disclosed studied dose, a lower dose, and an undisclosed member dose.
2. The three labels retain distinct Dose assessments and reasons.
3. A blend total never becomes a member dose; an exact studied formula can use
   only its own declared total.
4. Preparation, intervention and population mismatches still deny Evidence.
5. Probiotic Evidence does not contain `dose_applicability`; Dose retains the
   reviewed trial comparison and ordinary CFU assessment.
6. Omega Evidence record selection is unchanged by EPA+DHA amount; omega Dose
   remains amount-sensitive and rejects carrier-oil mass.
7. Every removed config key and explanation has no production consumer.

Real seams for the generic transfer include 305203 KSM-66, 182940 MSM,
293877/307547 ALCAR, 309486 CogniPhos, 54775 Sytrinol, and 1179/2219 Ravage
blend ownership. Probiotic canaries include 250851, 299239, 307727, 326762 and
327965. Omega canaries include raw labels 224615, 206295, 35718 and 77225 plus
enriched labels 327776, 288740, 273630, 239592, 184654, 261863 and 267461.

## Decisions required before score-changing implementation

1. **Probiotic decision CLOSED (Q47):** approved certainty 0–10, applicability 0–6 and independent same-condition replication 0/2/4 are integrated. CFU/trial-amount comparison stays in Dose. No automatic 12→20 rescale or category ceiling remains. Preserve the historical experiments below.
2. **Omega Evidence purpose mapping:** approve which existing reviewed record
   applies to an ordinary omega product, an explicit triglyceride-purpose
   product, and a prenatal DHA product, independent of amount. Existing point
   values may be compared, but their amount-triggered use is not approved as a
   purpose-only policy.
3. **Generic missing benchmark:** D24 must decide whether an otherwise complete
   product retains an ordinary numeric total. Until then, the transfer can
   preserve the assessment as `unassessable`; it cannot treat missing knowledge
   as zero dose.

No implementation agent may decide these magnitudes implicitly.

## Execution boundary from this packet

Immediately landable work is regression and replay scaffolding plus relocation
of a diagnostic only where the existing Dose result receives the same
comparison. Probiotic ownership and magnitudes are now closed by Q47. Generic shared amount gates and omega amount-triggered policy remain blocked until equivalent Dose coverage and the named decisions close. Phase2 primary-selection corrections may proceed through the existing shared role owner while retaining uncovered amount safeguards; they do not authorize deleting those safeguards. A partial removal would violate the transfer
invariant even if its focused tests passed.


## Measured packet closeout

`MEASUREMENT.md` is the frozen all-route comparison produced from 1,259 raw
omega/probiotic labels and 11 real generic canaries. Report SHA-256 before
tracking: `2a13f67cc5797e337c47b69664aaa949f31fc30707f185887254d2041b595b03`.
All experimental scorer/config edits were restored; none are part of this branch.

The packet proves that removing the amount gates without extending Dose loses an
assessment. It also shows that both illustrative omega mappings and the
probiotic 12-to-20 rescale create broad numerical policy changes. This is the original experimental receipt, not today's approval state. The later approved probiotic model is integrated (Q47). Remaining transfers require omega purpose mapping/magnitudes and the generic clinical-anchor mapping,
including reviewed-null trial amounts and brand/generic precedence.


## Phase2 cleaner function correction — October1

Owner: `scripts/enhanced_normalizer.py::EnhancedDSLDNormalizer._process_single_ingredient_enhanced` and `EnhancedDSLDNormalizer._process_ingredients_sequential`, using existing `other_ingredients_exact_lookup` for declared function aliases. Matrix source_section/cleaner_row_role and raw1179 trace establish ownership. Expanded identity lookup remains; no scorer bypass, new owner, registry, parser, field or borrowed member dose.

Sourceb39328b9; baseline7262d192. Full verified capture hashes:

- baseline: head `7262d192c041314e9f3533d68f9a30e4e5a002ba`, manifest `048ffd9669499ab9f94625f7ee1b2a237a163c9310e945a6dadadc488516be67`, output `c2a80028eaf37f51b51e29d0f5a9c715e45f5d4dca70b5bff7a3fb73dc70a68a`, 6 rows, source unchanged `true`.
- candidate: head `b39328b98c7cf83fe617c032b66fc4b6bfc67532`, manifest `048ffd9669499ab9f94625f7ee1b2a237a163c9310e945a6dadadc488516be67`, output `60c23ac620761a485375138ff2668ed74f94c552176829f6683c4f235560ce7c`, 6 rows, source unchanged `true`.
- extended_candidate: head `b39328b98c7cf83fe617c032b66fc4b6bfc67532`, manifest `cbe041440eb1eb565edf2564298e106adfc35175f413d1aab26782447a1e8286`, output `a20cea182bc18ecb6eeff4dc7dc54232c6452a2631c22a53b5b11e2560c5ea72`, 1259 rows, source unchanged `true`.

Targeted outcomes: Ravage1179 raw Formulation8.2846→8.4307, public11.0→11.2, total33.5→33.7; restored cinnamon raises the existing IQM assessment count21→22. GoldenMilk243271 gains cinnamon Evidence-owner metadata6→7 without score movement.2219,221108,49630,66953 complete payloads are unchanged. All six preserve Safety, route, status, Evidence and Dose scores. Extended1259 output is identical to approved productionSHAa20cea182bc18ecb6eeff4dc7dc54232c6452a2631c22a53b5b11e2560c5ea72.

Verification: failing regression5failed27passed; focused1427passed; normalizer covering143files3153passed12artifactskips; final `scripts/test.sh fast`17906passed167skippedzero xfails,543.63seconds. Fresh reviewer independently verified source, capture/input/output hashes, every targeted movement and extended equality. No clinical policy/data edited. Existing dual-use amount overrides and other Phase2 prominence/serving defects are separate open work; this checkpoint does not validate release.


## Phase2 shared EAA purpose correction — October 1

Owner: `scripts/scoring_input_contract.py::classify_ingredient_roles` — existing role/title-alias owner, matrix and raw `66953` production-boundary tests. Consumers `sports_helpers::primary_sports_identity`, `sports_subtype`, `sports_formulation::_is_protein_context` and `sports_dose::_best_primary_score` consume that purpose. Will NOT create another classifier, scorer, Dose engine, registry, public field or numerical policy.

Source `3ee91eae` fixes Q39(b). The label declares a 1,600 mg verified nine-EAA mixture and a separate 100 mg whey line. Named EAA/BCAA purpose no longer becomes protein purpose merely because whey exists. Co-named protein and genuine protein products remain protected; protein/stimulant subtype coexistence is explicitly tested. Dose still compares existing eligible anchors using unchanged bands. Blend totals remain formula totals, never member doses.

| Product `66953` | Before | After | Classification |
|---|---:|---:|---|
| Dose | 6.4 | 4.7 | Actual owner becomes `eaa` / `eaa_under_5_g`; existing partial-dose and completeness rules |
| Evidence | 7.2 | 0 | Incidental whey stops owning Evidence; EAA/member subjects retained |
| Formulation | 15.2 | 12 | Protein adapter no longer applies; existing generic rubric |
| Transparency | 3.3 | 3.3 | Unchanged |
| Verification | 8 | 8 | Unchanged |
| Safety/Hygiene | 9 | 9 | Unchanged |
| Total | 49.1 | 37.0 | Explained quality-tier change: Needs improvement → Poor |

Status remains `scored`, module remains `sports`, and safety judgments are unchanged. `clinical_review_not_covered` remains explicit: missing EAA research is a Phase3 task, not a completed negative review. This fix does not finish calibration or authorize release.

Clean source `3ee91eae9285b1a0fda492de2d0acdc6edae9fc6`, baseline `b39328b9`, full Clean→Enrich→Score captures:

- Six-label manifest SHA `048ffd9669499ab9f94625f7ee1b2a237a163c9310e945a6dadadc488516be67`; candidate SHA `eb126dbff734db2d1665eac3a6621629eda0dd22e86b77d18d5117274058f205`. Controls `1179`, `2219`, `243271`, `221108`, `49630` retain identical complete payloads.
- Extended 1,259-label manifest SHA `cbe041440eb1eb565edf2564298e106adfc35175f413d1aab26782447a1e8286`; candidate SHA `a20cea182bc18ecb6eeff4dc7dc54232c6452a2631c22a53b5b11e2560c5ea72`. All 1,259 complete payloads remain identical to baseline. Both captures report unchanged source and matching frozen input hashes.
- RED regressions cover original purpose, abbreviation, genuine protein/stimulant Formulation and actual Dose driver. Final focused suite: 74 passed; prior 62 consumer files: 2,150 passed, two artifact skips; final eight Dose consumer files: 117 passed.
- Fresh independent review accepted source and measured causality after catching and fixing both the Formulation subtype regression and Dose's separate best-credit protein path. Full fast checkpoint passed at source `3ee91eae`: **17,915 passed, 167 skipped, zero expected failures** (551.27 seconds). Q39(b) is closed for source/sample validation; source pushed to main with Sean's approval. Fresh review accepted source, causality and controls; no catalog release.

Receipts: integration worktree `.claude/state/trace_protein/final_receipt.json`, `final_candidate.jsonl`, `final_extended_candidate.jsonl`, focused logs and `final_fast.log`. Source push and catalog release are separate states.
