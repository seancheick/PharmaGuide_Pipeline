# Dose V4.1 review packet (plan §5.1)

October 18, 2026. The clinical-reference decision blocker is closed: Sean directly approved the revised 43 decisions and six-member prenatal critical group. The three baseline failures are resolved and latest main `2a9ee189e` is integrated. Final runtime is `5b34112b9`; exact-source CI passes all four groups and final local qualification remains pending. **Do not run the pipeline until the final handoff confirms readiness.**

## What is approved and implemented

- 37 policy rows retained; magnesium/calcium routing amended; phosphorus/ALA use the shared nutritional curve; ordinary generic sodium/chloride conclude completed-neutral 11.4/20.
- Choline is the sixth fixed prenatal critical member inside the existing 5-point budget. Missing choline stays in the denominator. Actual source-qualified choline is assessed against the pregnancy 450 mg total-dietary AI using the shared contribution curve; the supplement is not required to supply the whole AI. Broad-panel and critical credit remain separately auditable. No inferred credit from lecithin, phosphatidylcholine or blend mass without the canonical supported conversion.
- Minimum directed exposure supplies contribution; maximum supplies safety. One final product-level safety ceiling is applied after aggregation/normalization and never raises a lower Dose. No second excess penalty or chelation bonus is introduced.
- Study regimens remain descriptive unless a qualified approved benchmark applies. Completed no-general-benchmark conclusions use the existing neutral; unresolved identities, preparations and lost amounts remain explicitly incomplete. No unknown active numerical curve is deferred to a later release.
- No change to Verification policy, pillar budgets, neutral value, separate prenatal DHA complement, public top-level blob keys or status vocabulary.

## Tested source and comparison scope

Final pipeline runtime: `5b34112b945f3d2a0b1b49fed07bd844490162e6`, including main `2a9ee189e` (PR163 architecture and PR164 omega safeguards). Engine 4.8.1, quality config `1.29.1-dose-v41-omega-integration`, omega 2.3.1. App PR128 is merged as `6fcd9e678c8f3678e4d0fb4967f5769b7d7e1040`, containing reviewed source `51567dae`; primary app checkout is synchronized. No app build or deployment occurred.

The earlier approved-policy comparison on `2339ec8f` scores **all 15,426 unique frozen enriched inputs** from 58 checksum-verified files, with zero replay errors and matching source hashes. Baseline `832c1bd7f756fd9b9d5f1e1b1204400e899a6481` is the pre-approval Dose candidate, **not production/main**. Candidate capture took 710.44 seconds. This is a scorer replay, not a full pipeline, regenerated catalog, app bundle, deployment or phone acceptance. Separate bounded raw-label replays validate affected producer paths.

## Full frozen-input movement

| Result | Count |
|---|---:|
| Numeric total changes | 5,048 |
| Increases / decreases | 1,696 / 3,352 |
| Numeric movement range / median | −20.0 to +15.2 / −1.1 |
| Identical numeric totals | 10,050 |
| Numeric tier crossings | 1,935 |
| Numeric → not_scored / tier unavailable | 23 |
| Assessment complete → partial | 28 |
| Product-safety / Dose-safety / flag / route changes | 0 / 0 / 0 / 0 |
| Completed-score Dose receipt reconciliation failures | 0 |

Equal numeric totals do not by themselves prove all fields equal. The controls below compare the full core result. The frozen safety equality does not substitute for raw-source safety checks or regenerated-catalog acceptance.

| Route | Inputs | Numeric movers | Full core results unchanged |
|---|---:|---:|---:|
| multi_or_prenatal | 2,073 | 1,499 | 539 |
| probiotic | 541 | 97 | 432 |
| generic | 10,680 | 2,542 | 7,833 |
| sports | 923 | 622 | 274 |
| omega | 715 | 34 | 536 |
| fiber_digestive | 348 | 198 | 146 |
| b_complex | 146 | 56 | 90 |

Representative unchanged controls compare total, all six pillars, tier, assessment/quality status, safety, Dose-safety, flags and route. Receipt wording is outside that core-equality claim.

| DSLD ID | Product | Route | Total |
|---|---|---|---:|
| 180213 | Airborne Citrus | multi_or_prenatal | 46.2 |
| 180214 | Airborne Berry | multi_or_prenatal | 45.7 |
| 242946 | BetaBoost + Vitamin C Citrus | generic | 70.9 |
| 242284 | Vitamin B3 | generic | 56.8 |
| 252500 | Fish Oil Softgel 1000 mg | omega | 75.6 |
| 252585 | Creatine Monohydrate | sports | 100.0 |
| 253729 | Betaine HCL | fiber_digestive | 68.4 |
| 253730 | Betaine HCL | fiber_digestive | 68.4 |
| 253731 | Creatine Monohydrate | sports | 100.0 |
| 12078 | Natural Cod Liver Oil | omega | 41.5 |
| 18174 | Adult 50+ Probiotic | probiotic | 49.4 |
| 18178 | Adult Probiotic | probiotic | 49.4 |
| 19173 | Balanced B-100 | b_complex | 65.1 |
| 19176 | Balanced B-150 | b_complex | 66.6 |

## Prenatal and choline results

**119 inputs:** 117 numeric and 2 already unassessed. 114 numeric movers: 112 decreases, 2 increases, 3 unchanged; range **−1.9 to +0.6**, with 7 numeric tier crossings. This is the combined policy batch; the earlier membership-only −0.8..+0.3 simulation is not its final result.

Choline classification: 80 missing/zero, 36 partial-credit, 1 full-credit, 2 unassessed products. A missing label contribution does not mean the person gets no dietary choline. No prenatal safety/status/other-pillar changes occurred.

| Example | Before → after | Change |
|---|---:|---:|
| 233218 Garden of Life MyKind Organics — Prenatal | 81.0 → 79.1 | -1.9 |
| 267605 MegaFood — Baby & Me 2 Prenatal Multi Red Raspberry | 81.7 → 79.9 | -1.8 |
| 246194 vitafusion — Organic Prenatal Multi Ripe Raspberry Flavor | 76.2 → 74.6 | -1.6 |
| 71579 Nature's Bounty — Prenatal | 81.2 → 79.7 | -1.5 |
| 322428 Bayer One A Day — Pregnancy Planning | 78.7 → 77.2 | -1.5 |
| 328830 Thorne — Basic Prenatal | 94.8 → 95.4 | +0.6 |
| 271093 Doctor's Best — Prenatal Essentials | 71.8 → 72.1 | +0.3 |

The complete 119-row `prenatal_choline.csv` records minimum/maximum daily amount, unit, total-dietary AI, %AI, and separate broad-panel/critical **unit credits**. Those 0..1 credits are not raw points: the critical raw share is 5/6 × unit credit before route normalization.

## All assessment and other-pillar movements

All 28 complete→partial changes are classified. **22 not_scored cases are stale stored protein Facts contracts** (old units, missing typed assessments or old producer projections); six additional fresh-source probes restore all six tested protein products to complete scores, and earlier representative proofs cover the other source classes. These need regeneration through the corrected producer, not a scorer compatibility patch. **One further not_scored case, EAA330806, is an honest persistent identity hold:** its10g EAA header does not own the separate nine-amino-acid list. A rerun must not force it complete.

The remaining **five retain numeric 63.9 scores with assessment_status=partial** (294273,311852,312355,312356,312357): their labels declare 30 g whey ingredient, without actual protein grams. The old 20 Dose points assumed powder mass was actual protein. The current owner leaves actual-protein assessment unresolved, exposes partial status, and gives no completed Dose credit; all five other pillars/safety are unchanged. A fresh raw 294273 probe reproduces it. This is the existing partial-publication contract, not invented protein purity. All 28 changes have source explanations; no unclassified case remains.

The 233 non-Dose pillar field changes comprise 115 fields cleared when 23 scores become not_scored, plus **118 completed→completed changes**, all classified:

- **111 Transparency gains:** 110 × +6 and one+5.9 rounding effect (275464). Every case has an independently confirmed original printed zero, qualified unit/operator/serving and an exact zero-only Transparency-owner counterfactual. A disclosed zero stops looking like missing label data; it does not earn efficacy credit.
- **Four frozen Transparency losses:**252510,253633,253638,253654 still carry stale lactose source roles; current bounded raw-source proofs restore12/15.
- **One genuine Transparency loss:**176044 contains genuinely NP amounts for independent arginine/glutamine and papain/bromelain; retiring false duplicate protein previously filling its census reveals the real gap (8.9→2.9).
- **One stale frozen enzyme-origin loss:**82893 (7.6→1.6). Current Clean correctly retains enzyme origins as descriptors and yields Transparency15; its bounded fresh before/after score70.9→84.3 preserves the other five pillars and removes the false probiotic warning. This raw-source safety correction is separate from the frozen zero-safety-change result.
- **One Formulation correction:**2715 Soy Peptide 100 mg is not an actual-protein Facts total. Retiring its false protein projection selects the existing generic identity/form owner (8→20), without changing Formulation policy.

All 58 source hashes and 118 completed movements are classified; unsupported/unexplained cases: 0. The six stored-role decreases demonstrate why the frozen scorer replay cannot stand in for the eventual full producer rerun.

## Bugs corrected through existing owners

- Current source identity, path and preparation membership now govern Dose. Stale mirrors cannot lend quantities, borrow children from another blend header or hide unresolved operators/units.
- BCAA/EAA identity completeness is separate from amount completeness. Missing captured members remain incomplete; genuinely label-hidden amounts use the approved neutral. Typed whole preparations are not counted again through their components, and partial sums are not described as whole-mixture quantities.
- Explicit printed zero is disclosure when its source quantity/unit/operator is qualified. It is not a positive efficacy amount; NP, ambiguous quantities and lost data do not receive this exception.
- Protein-source mass and Nutrition Facts actual protein remain distinct. A Nutrition Facts macro cannot manufacture protein-product intent, and 30 g whey ingredient mass is not assumed to be30 g actual protein.
- Explicit enzyme-origin organisms/plants remain source descriptors rather than independent live probiotic/botanical purposes. Source labels and quantities are preserved.
- Prenatal DHA follows minimum daily directions. Sports and fiber do not silently drop independently named co-primaries. Adult sports targets qualify the full stated label population. Incomplete receipts do not claim completed arithmetic.

Fail-first cases, controls, source receipts and independent review cover these classes. Source fixes are shared; no product/brand score override is used.

## Validation evidence and limits

- Pipeline whole-fast CI [39157311609](https://github.com/seancheick/PharmaGuide_Pipeline/actions/runs/39157311609): all 4 groups and skip guards passed on exact runtime 2339ec8f.
- Earlier `2339ec8f` named owner/consumer slice: 499 passed. Final `5b34112b` raw canaries: 33 pass. Raw 63 comparison on 2339 retains the prior source-qualified results with zero further total/other-pillar/status/route movements.
- App analysis clean and full Flutter suite 3,964 passed on runtime bb352dde; app CI [39148045039](https://github.com/seancheick/Pharmaguide.ai/actions/runs/39148045039) passes on 51567dae. The app renders pipeline scores; it does not recalculate them.
- Independent final boundary review is clear after the current-source facts correction. Source verifiers confirm references, separately from Sean’s policy approval; two old strain alerts are an explicitly excluded wrong PMID and a correction/limitations reference, not active Dose anchors.
- The earlier three-failure local result is superseded: integrated `6197a1be` passes **546 tests / 24 declared opt-in service skips**, with the skip guard passing. Its whole-fast CI [39160872917](https://github.com/seancheick/PharmaGuide_Pipeline/actions/runs/39160872917) passes all four groups. Final `5b34112b` CI [39162345603](https://github.com/seancheick/PharmaGuide_Pipeline/actions/runs/39162345603) passes all four groups and skip guards; final local qualification is pending.

## Pure magnesium: what to expect

**Pure label 205309 / barcode 766298001753 stays 76.6 (display 77)** under the newer approved D1 policy: 120 mg minimum daily magnesium earns 20/20 contribution against the 84 mg target; maximum 480 mg/day is 137% of the 350 mg supplemental UL, so the single final ceiling caps Dose at 10. This is a maximum-directed-use policy consequence, not a claim that 120 mg is a high dose. A different one-capsule/day label 299065 has 120 mg minimum and maximum, no ceiling, and scores 86.6. Personal chosen use does not recalculate the catalog score. The newer D1 policy supersedes the historical serving-only77→87 expectation.

## Integration closeout and remaining gates

The three strict baseline failures are closed without weakening comparisons. Original raw labels and accepted source history establish: 306237 must not receive a duplicate BioPerine delivery bonus; 246324 and 176872 use canonical sugar spacing. All nine baseline pairs were regenerated through the actual owners, including the source-supported 250 mg ordinary-adult omega reference for 1002. Historical baselines are retained. The preflight now asks the same dated-baseline path owner as its strict consumer, so obsolete root files cannot falsely establish readiness.

The architecture integration preserves approved Dose and shared quantity/module owners. A 71-label Clean → Enrich → Score → detail-blob replay found only 50 deterministic enriched-name sorting changes against the pre-integration candidate, with no scored/blob changes. The latest omega integration retains main's marketing Evidence, molecular-form and child-population safeguards while preserving Sean's approved directed-daily Dose semantics. A source-verified printed zero DHA is distinct from a hidden amount; source identity and units are checked by the existing EPA/DHA qualifier, including MCT/flax and unknown-sibling controls.

A separate 715-product frozen omega comparison (`6197a1be` → final `5b34112b`) found 19 score changes (4 up / 15 down, −19.0 to +7.3), all recognized child labels receiving approved neutral Dose. Eleven also lose inapplicable adult Evidence credit. There are 15 tier crossings and four assessment completions, with zero safety/route/gate/flag/readiness or other-pillar changes and zero receipt errors. The remaining 696 score outcomes are unchanged: 695 equal numeric totals and 260262 still unscored. The final 71-label replay adds provenance and three Dose explanation changes, with no numeric movement; its final source-identity guard changes no artifacts. Full captures, clocks and source hashes are retained; this does not regenerate the catalog.

Pending: the applicable final local checkpoint. Exact final whole-fast CI passes all four groups and skip guards; a separately authorized corpus job is already using primary main `2a9ee189e`, so this session will not change that checkout or start a broad local job until it finishes. App PR128 is already integrated. Sean authorized merging the pipeline candidate after green qualification. Older failed/pending candidate records below are historical, not current blockers.

After the final merge and source-fingerprint check, Sean's compute-only command is:

```bash
cd /Users/seancheick/Downloads/dsld_clean
source scripts/python_env.sh
PYTHON="$PG_PYTHON" bash batch_run_all_datasets.sh --pipeline-only
```

**Do not start a second corpus run while the existing job is active.** That older-source job does not include Dose V4.1. Default startup uses essential checks; `--pre-check` is optional full preparation. No full pipeline was launched by this session. New artifacts still need catalog/export parity, release checks, app bundle validation and separately authorized publication. Existing phone build22 has not been replaced.

## Local evidence files

Final integration receipts are in `reports/dose_v41_integration_20261018/`, including the 71-label four-layer captures, nine source-verified baseline pairs, final 715-product classification, fail-first tests and review. Earlier full-policy evidence remains under `reports/dose_v41_approved_candidate_20261018/`: baseline/candidate JSONL captures and manifests; `final_comparison.json`; every numeric/status transition in `score_changes.csv`; all 119 prenatal rows in `prenatal_choline.csv`; source-classification and raw-proof receipts; exact CI/local logs; current stage fingerprints. Preserve final captures, baselines, checksum manifests and compact source proofs. Superseded partial captures are not accepted evidence.

## Historical candidate records


Branch `claude/dose-v41` (pipeline) and `claude/dose-v41` (app), October 17, 2026. Spec:
[`DOSE_V41_PLAN.md`](DOSE_V41_PLAN.md) with Sean's decisions D1–D4. Baseline `main` 5fb2be1ca,
engine 4.6.0, config 1.27.0. Candidate engine 4.7.0, config `1.28.0-dose-v41`, omega rubric
`2.3.0-dose-v41-references`. Nothing here is activated: activation, the calibration diff (item 9),
pushes to `main`, the pipeline run, release and IPA are Sean's.

Measurement inputs: the 15,426 manifest-owned stored enriched inputs, scored by clean detached
checkouts of each batch commit (`~/pg_quality/dose_v41_20261017/capture.py`, deltas by
`compare.py`, ledger `LEDGER.md`). Stored inputs predate D2, so the D2 effect is measured
separately by a raw Clean → Enrich → Score replay (`replay.py`).

## Results by batch (stored inputs unless stated)

| Batch | Commit | Score changes | Up / down | Tier crossings | Non-Dose pillar changes | Status/safety/route changes |
|---|---|---:|---:|---:|---|---|
| B1 exposure: min adequacy, max safety | 38f804fbd | 622 | 297 / 325 | 302 | 0 | 0 |
| B2 one product-level ceiling | 7b8ae4501 (+14e2b1013) | 737 | 18 / 719 | 466 | 2 Formulation (sports subtype fix) | 0 |
| B3 D2 UL screening selection (enrich) | e96320a28 | 0 on stored inputs; raw replay of 26 labels: 1 | 0 / 1 | 1 | 0 | 1 new CAUTION, 1 critical signal |
| B4 Mg/Ca/K/omega references | c9ef82128 (+f3614ec7c) | 728 | 665 / 63 | 350 | 0 | 0 |
| B5 sports, caffeine, probiotic, co-primaries | 6be63e98e | 578 | 491 / 87 | 199 | 0 | 0 |
| B6 hidden-amount neutral, semantics gate | 30f1d0124 | 35 | 20 / 15 | 6 | 0 | 0 |
| B6b no highest-studied-dose cut, one excess path; B7 receipt | 66830a6ed, e8833f0dc | 85 | 85 / 0 | 56 | 0 | 0 |
| **Combined base → candidate** | 8db71366d | **2,595** | **1,516 / 1,079** | **1,347** | 2 Formulation | **0** |

By route (combined): generic 794 of 10,430 moved, omega 582 of 714, multi/prenatal 504 of 2,040,
probiotic 450 of 530, sports 158 of 919, B-complex 89 of 146, fiber 18 of 344. Every route keeps
unmoved controls. The 2 Formulation changes are a latent defect fixed in 14e2b1013 (generic
reassembly dropped the sports subtype; protein products were normalized against 24 instead of 15).

Worked example (plan §4): Pure 205309 (120 mg magnesium, 1–4 capsules) scores 76.6, Dose 10:
adequacy 20 (120 mg ≥ 84 mg target), 480 mg/day = 137% of 350 mg caps Dose at 10. Control
299065 (one capsule) stays 86.6, Dose 20. Both are pinned in pipeline and app tests.

Raw canaries: the complete 33-label raw check had 8 drifts, all score/derived tier only (no
safety, identity or status field); a raw replay shows Dose is the only pillar that moved for
each. Causes are recorded per label in `contract_snapshots/_manifest.json`; 33/33 now pass.

## 1. Inventory of active reference types

| Reference type (§2.2) | Where (owner) | Count |
|---|---|---:|
| nutritional_reference | DRI window curve `generic.reference_semantics.dri` over `rda_optimal_uls.json` rows; omega ordinary 250 mg; prenatal DHA 200 mg; child omega bands | 77 DRI rows |
| supplement_contribution_policy | `generic.contribution_policy_targets` magnesium 84, calcium 260 | 2 |
| supported_minimum | clinical anchors `_clinical_anchor_reference_by_canonical`; omega triglyceride 2,000 mg | 14 + 1 |
| bounded_window / studied ranges | botanical `rda_therapeutic_dosing.json`; collagen, sleep, joint, immune ranges (module literals) | 43 + module bands |
| discrete_studied_regimen | positive clinical/formula benchmarks in `backed_clinical_studies.json` | 11 with a minimum dose |
| safety_only_reference | UL ceiling (`dose_safety_ceiling`), caffeine 400/600 mg | 2 |
| no_benchmark / hidden amount | shared neutral 11.4 (`dose_subscale.unbenchmarked_neutral_public`) | 1 |
| probiotic potency tiers | `clinically_relevant_strains.json` CFU tiers | 49 of 132 strains |
| sports bands | `sports_dose._score_primary` literals | 12 identities |

## 2. Benchmarks missing declared semantics

The eleven enumerated records carry the shared schema; other config anchors, including joint/immune magnitudes, are not covered (`schemas/dose_reference_semantics.schema.json`,
CI `test_dose_reference_semantics.py`, 11 records). Still pending, listed exactly in
`PENDING_ANCHOR_FAMILIES`: sports band literals; multi/prenatal and B-complex coverage curves;
collagen, sleep, joint and immune ranges; botanical therapeutic ranges (43); per-row DRI and
clinical-anchor rows (curve records exist); probiotic strain tiers (49); positive clinical and
formula benchmarks. Moving these into semantic records is the follow-up (needs curation, not
code); the current CI only checks that the listed files/functions exist. It neither proves completeness nor enforces a shrinking exception list. This is an activation blocker, not a completed acceptance gate.

## 3. Highest-studied-dose upper-bound misuse

Removed (adequacy now plateaus): sports protein >40 g, creatine >10 g without loading,
beta-alanine >6 g, HMB >6 g (each 16); caffeine >400 mg per use (14); generic clinical and
aggregate-formula benchmarks above `max_studied_clinical_dose` (11 of 22).
**Kept, for Sean** (their high end may be a reviewed window, §2.4 last bullet): botanical/collagen
near (16) and above (12) a studied range's high end; immune above-band half credit; melatonin
>1/3/5/10/20 mg and 5-HTP >300/400 mg steps; multi/prenatal coverage above 200%/500% RDA and
B-complex above 300%/1,000% RDA.

## 4. Evidence → Dose numerical dependencies

Removed (§2.2 "evidence strength never caps Dose"): ATP ≥400 mg 12 → 20, betaine ≥2.5 g 16 →
20, taurine ≥1 g 10 → 20 (below them, proportional to the same minimum). **Kept, for Sean:**
caffeine 200–400 mg tops at 18 (plan lists it for review), BCAA aggregate tops at 14 ("recovery
not performance": purpose applicability rather than certainty).

## 5. Disclosure → Dose dependencies

Changed (§2.3): an amount the label hides now takes the 11.4 neutral on generic purposes,
sports co-primaries, botanical/collagen profiles and probiotic strains (previously 0 or skipped);
Transparency keeps its B5/disclosure deductions. "Hidden" is a positive label fact
(`dose_disclosure_status` = `not_disclosed_blend`, a lent blend mass, an opaque sports blend, or a
per-strain CFU under a total); a row missing its amount without one keeps main's 0 or no vote,
and a pipeline-lost amount keeps its strict hold (review fix e8ab8f439; 0 stored-input changes).
Risk for Sean: a hidden underdose now scores 11.4 in Dose where a disclosed low dose may score
less; Transparency carries the counterweight. **Kept:** probiotic CFU guarantee multiplier
(0.9 at manufacture, 0.85 unstated) on measured strains only.

## 6. Duplicate excess deductions

Removed: per-nutrient UL bands in generic, multi/prenatal and B-complex coverage; B7 −2/flag cap
3; immune zinc/vitamin D zeroing at 40 mg/100 µg (the adult ULs) and its withheld daily-use
points. One ceiling remains (§2.4), applied once in `quality_score._pillar_dose`; Safety/Hygiene
still explains without deducting.

## 7. Minimum-daily vs serving-only impact

B1 alone: 622 changes, 297 up / 325 down, the exact inverse of PR #154's 325 up / 297 down;
Dose only.

## 8. Final omega policy impact

Omega route 714 inputs: 581 Dose up, 132 unchanged, 1 down (326301, a vitamin D exceedance
ceiling). Ordinary adults plateau at 250 mg/day (1,000 mg products 16 → 20; 74 mg 0 → 5.9);
an explicit triglyceride purpose uses 2,000 mg; prenatal products use DHA 200 mg only, including
a prenatal title that mentions a baby (f3614ec7c fixed a 20 → 5 regression found in measurement).

## 9. Calibration-record diff (for Sean's approval)

`git diff 5fb2be1ca -- scripts/scoring_v4/config/quality_score.json scripts/data/omega_rubric.json`:
- `dose_safety_policy` (150/−2/cap 3) → `dose_safety_ceiling` {100, 150, 10} + `caffeine` {400, 600}.
- `dose_magnitudes.generic`: `window_ul_partial_band` and `window_overdose_credit` retired;
  `contribution_policy_targets` (magnesium 84, calcium 260 with 500 mg per-administration context);
  `reference_semantics` for the DRI / clinical-anchor / legacy curves.
- `dose_magnitudes.multi_prenatal.reference_semantics` (prenatal DHA).
- Omega `dose.adequacy_references` (ordinary 250, triglyceride 2,000) and `epa_dha_band_semantics`.
- D2 (code, `rda_ul_calculator.UL_SCREENING_POPULATIONS`): general adult = lowest UL across
  Male/Female 19+ (calcium 2,000, phosphorus 3,000); seniors tag 51+; pregnancy/lactation tag
  19–50 rows; a label stating several populations screens the lowest UL across all of them, and
  a negated tag ("Women (not pregnant or lactating)", 959 labels) is an ordinary adult (review
  fix b69d8acdf: pregnancy-only screens 1,146 → 46, plus 142 unions; the ≥90%-of-UL cohort is
  unchanged at 12); DSLD's 18–50 adult tag (on 12,102 of 15,426 labels) does not narrow; adolescent 14–18 rows already exist and must be used when applicable. Younger pediatric gaps cannot borrow adult limits; see the October 18 correction below.

## 10. Permanent golden-case tests and results

Pipeline (137 tests, all pass): `test_directed_daily_dose` 5, `test_dose_final_safety_ceiling`
16, `test_ul_screening_population` 27, `test_dose_v41_calibrations` 24, `test_dose_v41_sports_caffeine`
18, `test_dose_v41_neutral_states` 4, `test_dose_v41_above_range` 4, `test_dose_reference_semantics`
14, `test_dose_v41_receipt` 25 (every archetype fixture's receipt reconciles). App (25 tests across these four files, all pass):
`stack_ul_checker_dose_v41_test` 8, `dose_v41_receipt_parity_test` 4 (real pipeline output for
205309/299065), nutrient panel "not assessed" notice, parity pin (100%).

## App batch (D4)

- `stack_ul_checker.dart`: exactly 100% is not an exceedance; no-profile screen = lowest
  ordinary-adult UL (not children or pregnancy rows), unknown-age and group-only fallbacks use adult
  rows; known adolescent age keeps its applicable adolescent reference. All incomplete profiles are flagged not personal; a catalog verdict's percentage is re-expressed against the
  person's limit when the row carries the catalog limit, otherwise shown with no personal limit.
- `PipelineUlVerdict` percentage fallback `> 100` (was `>= 150`, the retired B7 band), pinned to
  the pipeline's `exceeds_above_pct`.
- Nutrient panel marks general-adult limits with * and says they are not assessed for the person.
- Receipts render from the recorded result (facts verbatim, receipt kinds summed); no app math.
- Unchanged and already true: quality is profile-independent; the stack provider watches the
  profile; demographics stay on device; catalog warnings name maximum labeled daily use.

## Independent review (fresh context, requirement + owners + diff)

Verdict: request changes, one Critical. Each finding was reproduced before acting.

| Finding | Disposition |
|---|---|
| CRITICAL: "Women (not pregnant or lactating)" screened as pregnancy (D2) | Fixed b69d8acdf, fail-first tests |
| Pregnancy + adult tags screened only pregnancy rows (§2.5 "whole stated population") | Fixed b69d8acdf (union of populations) |
| Hidden-amount neutral defined by exclusion | Fixed e8ab8f439 via the existing `dose_disclosure_status` owner |
| Two unrelated copy tests deleted | Restored a316ccfe1 |
| 100% threshold had two owners | Guard a316ccfe1: config start must equal the confirmed exceedance |
| Receipt counts the ceiling as unawarded | Kept: caps (verification tier ceilings too) land in `unawarded`, not deductions; entries reconcile |
| Multi/B-complex high-RDA reductions kept | Kept for Sean: §2.4 names the two UL excess paths removed; these are non-UL coverage bands (§3.2 keeps the panel structure) |
| Caffeine inside guarana/green tea stays unknown | Kept: §3.3 counts quantified caffeine only; unknown stays unknown |
| Pediatric adult fallback; app no-profile shows % with * | Kept for Sean (data gap; the notice says "not assessed for you", no tier reads as safe) |

After the fixes: stored-input scores unchanged (0 of 15,426 vs 810af3cf0), raw canaries 33/33.
Locally rebuilt canaries (6 of 9; three raw labels are not in the dataset) show e1_2_2
score-array drift on 306237/246324/176872 that reproduces identically on main 5fb2be1ca: a stale
October 12 baseline, not this branch (follow-up).

## October 18 independent audit correction status

The preceding batch counts and CI runs describe the original candidate, not the fixes below.
The independent audit was rechecked before implementation; source fixes are committed on the same
feature branches. No pipeline, main push, release or IPA was performed.

- Caffeine totals retain their authoritative source and independent sources; qualified amounts
  preserve their bounds. Only confirmed excess sets the one final ceiling.
- Stated 19–50 labels reach their population owner. Pediatric labels use available adolescent
  references when applicable; missing established younger references keep the existing incomplete
  assessment/strict hold. Nutrients with no established UL are not falsely held for absent rows.
- BCAA/EAA vote once per preparation, on their existing normalized scales. The audit's expected
  12 for creatine 5g + BCAA 1g was imprecise: 20 and 4/22×20 average to **11.8**. Genuine hidden
  co-primaries take neutral; betaine uses its daily target. ATP retains its acute per-use basis.
- Invalid/conflicting CFU producer measurements remain unresolved, including alias spellings of
  the same source identity. Legitimately hidden strain allocations remain neutral. Missing
  botanical quantities do not become completed no-benchmark assessments.
- Receipts carry the actual selected assessment, quantified exposure/default/qualifier, panel
  components and assessed references. Prenatal reference rows reflect the pregnancy rebase.
  Receipt reconciliation checks contribution arithmetic, and magnesium copy no longer expands a
  supplemental-only UL to food intake. The triglyceride reference is a purpose-specific authorized-claim condition; the decision table corrects its earlier supported-minimum interpretation.
- App percentages keep their matching reference and non-personal marker; stronger verified
  personal excess is retained. Clearing age/sex actually clears the watched state. The original
  audit's request to replace a known adolescent's limit with an adult limit is **retracted**;
  the fallback explanation was corrected instead.
- Engine 4.7.1; numerical config/rubric calibrations unchanged. Glossary now describes directed daily Dose.

**Unclosed requirement:** §2.2 needs source/preparation/population/purpose/curve review for the
pending active anchors and a complete executable acceptance gate. Eleven schema-valid records
are not complete clinical approval. No review/approval fields were fabricated; do not activate
or run the full pipeline until this requirement and Sean's remaining policy decisions are closed.

Current verification (October 18):

- Combined named 16-file pipeline owner/consumer checkpoint: **486 passed**. Final receipt
  follow-up: **42 passed**; final UL-population file including the real abbreviated DSLD tag:
  **46 passed**. Counts overlap. Native strain/formula provenance and assessment-readiness slice: **193 passed**.
- App: `flutter analyze` clean; implementer 15-file slice **205 passed**, independent review
  **39 passed**, refreshed-fixture/checker/profile/widget slice **43 passed** (overlapping).
- Clean-source frozen raw replay, **63 labels**, baseline `4b1ea450f` versus final runtime
  `4148a7abb`: sports249741 total **84.3→82.1**, Dose **18→15.8**, restored normalized BCAA vote;
  pediatric218441/256961/327416/82319 become incomplete/not_scored for unavailable established
  younger UL references. All completed products retain other five numeric pillars. Fifty-six
  completed controls preserve total score. No unexpected completed route/status change; every
  available final Dose receipt reconciles. The raw cohort covers five routes; archetype fixtures
  and named tests cover the other routes. This is a bounded development comparison, not a full catalog.
- Raw canaries: initial **32/33**, the one drift327416 was independently traced to its label's
  `Children more than 1 but less than 4` target and missing applicable younger ULs. Only that
  snapshot was regenerated through the canonical raw freezer, with source-based reason in its
  manifest. Final **33/33 passed**.
- Current fingerprints: **114 stale stage manifests**, including Clean. Do not restamp
  existing artifacts. Once activation blockers and merge gates close, regeneration must begin
  at Clean; no corpus command is authorized or recommended by this handoff.

Evidence: `reports/dose_v41_audit_fixes_20261018/` (local, ignored), checksum-bound raw and score
captures, final_impact_summary.json, safety_changes.json, canary logs and fingerprints.json.
No new whole-fast CI or local/release rung is claimed; historical CI does not cover these fixes.
Those candidate merge gates remain pending. Local commits were requested; no remote push occurred.

## Earlier decision inventory (superseded by the complete reference table below)

The earlier inventory was: approve item 9 and the "kept, for Sean" lines in items 3–5 and the pediatric gap; activation;
merging both branches to `main`; the pipeline run; release; IPA.

## October18 reference review completion and factual corrections

The [one reference decision table](DOSE_V41_REFERENCE_DECISIONS.md) supersedes generic pending-reference lists in earlier review notes. It contains237 concrete reference/consumer rows:43 ask for policy approval; the external review recommends37 as written,2 magnesium/calcium routing amendments,4 replacements (phosphorus/ALA shared nutritional curve; ordinary generic sodium/chloride completed neutral),194 retain accepted direction, retire unsupported inference to approved neutral, correct facts, or identify descriptive/inactive records. A completed no-general-benchmark conclusion is complete, not Preliminary. These are proposed implementation dispositions; table preparation does not mean all retirements have landed or policy is approved.

Unambiguous committed corrections: immune duplicate zinc/D zeroing and microgram units; Bi07 combination-total basis; five source-fact corrections; literature-regimen-to-minimum fallback retirement with seven existing source records completed-neutral; actual Facts protein quantity ownership; established soluble-nickel UL with form/elemental guards; FDA Daily Value versus RDA policy wording. Engine4.7.3/config1.28.2 identify this technical candidate. No new proposed numerical calibration has been applied.

Measurements use frozen stored inputs only, not regenerated catalog evidence. Immune142: one total67.8→69.0, no safety/status changes. Literature10 against832c1bd7: three lysine Dose10/15→11.4,three MCT6→11.4; four controls unchanged, all safety/status/non-Dose pillars unchanged. Protein252510 Facts27g remains Dose20/total83.6;294273 ingredient-only whey30g becomes incomplete Dose/partial assessment, preserving ingredient mass, other pillars and safety. The latter is a real quantity qualification correction; no purity is inferred. Nickel synthetic regressions pin1mg exactly,1.2mg soluble elemental nickel, unknown salt scope and compound mass. Low unknown-form exposure is bounded using the existing maximum-possible-moiety owner without a salt-identity assertion or false warning; higher unresolved exposure remains review-only. A personal stack containing unknown scoped contributions can remain indeterminate: individually bounded products cannot be blindly excluded when summed. The app guard is paired before qualification.

Current validation:503 combined named pipeline checks pass;124 nickel owner checks and259 protein owner checks pass (overlapping sets, not additive). Config/semantics24 pass; earlier CI679330f1 failed9 checks in four classes, all reproduced and corrected against existing owners. It is not acceptance. Appdd8e0529 analyze/full3951 tests andCI39136864282 passed before the additional form-scope safeguard; that new app candidate requires its own checks. The local rung reported502passed/3known out-of-scope e1_2_2 failures/65skips (41generated-artifact gaps,24declared opt-ins); it is not green/current final acceptance. Missing rebuilt canary/build-dependent cases and declared live opt-ins remain explicit.

Before merge: Sean approves the table; implement approved calibrations and remaining unsupported-curve retirements together in existing owners; make §2.2 exhaustive semantics acceptance executable (the current eleven-record inventory is insufficient); measure the combined candidate and unaffected controls; independent fresh-context review; one green exact completed-candidate CI per repo plus applicable local checks. Keep the separate e1_2_2 owner informed; do not weaken its assertions. Then inspect stage fingerprints and give Sean the required run command. No full pipeline before policy approval, no main push/release/IPA under this task.

Final paired technical check: app sourcebb352dde passes clean full analysis and all3964Flutter tests (2m36s); first full run3963pass/one stale warning-copy fixture is preserved as failed, isolated fixture correction keeps its warning assertion and uses qualified exposure. Independent fresh-context review found no outstanding actionable defect in this technical batch. Feature commits remain local after the earlier remote checkpoints; no completed policy-batch CI or merge is claimed.


## October 18 — external reviewer amendments verified

The six concerns reproduce in the actual owners: generic `_adequacy_reference_kind` falls back to legacy for phosphorus/ALA/sodium/chloride; `_band_credit` then awards full credit at25%RDA/AI. Magnesium/calcium use the same fallback outside ordinary-adult contribution eligibility. The reference table is revised to37 proposals retained,2 routing amendments,4 replacements. These are reviewer recommendations awaiting Sean adoption, not43 approvals already granted. No runtime/source/config/reference data changed in this documentation batch.

Prenatal choline membership is now a concrete proposed decision, not an incidental absence: add it as sixth member within the existing5-point critical budget, using the shared nutritional curve and applicable pregnancyAI; keep DHA separate. The explicit alternative is five-member priority weighting with choline only in broad disclosed coverage. The current source comment claiming choline already participates in the critical group is false and must be corrected with the chosen implementation.

Membership-only isolated scorer what-if:119 frozen stored prenatal labels,5 non-prenatal controls;117 numeric scores/2 retained unscored.38 have choline broad-coverage data.113 scores decrease,1 increases,3 numeric scores unchanged; range−0.8..+0.3;5tier crossings. No safety/Dose-safety/status/assessment or other-pillar change; all controls identical. Source5bf2b0b1; receipt reports/dose_v41_reference_amendments_20261018/choline_membership_whatif.json, SHA25615583cdda7014066259632dd7c9175ee7ee3cce929bb6d88af3e6bdb4d56d036. This is an aggregation-choice measurement under the proposed shared panel curve, with other proposed changes not simulated; not final combined-policy impact or catalog regeneration. No pipeline stage ran.

Before merge: Sean adopts the revised policy/membership; implement the complete bounded batch through existing owners, including exhaustive active-reference semantic coverage and residual fallback removal; measure the combined candidate against all15426 frozen inputs with controls; independent review; exact-source CI and applicable local/app checks. The three known e1_2_2 baseline failures remain unwaived and require source-based resolution with their existing owner; this external review does not justify weakening assertions or silently repinning. The missing simulator screenshot remains the declared host limitation. Sean still runs the eventual pipeline after candidate acceptance; no main push, release or IPA is authorized here.
