# Dose V4.1 review packet (plan §5.1)

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

## Sean-only decisions remaining

Approve item 9 and the "kept, for Sean" lines in items 3–5 and the pediatric gap; activation;
merging both branches to `main`; the pipeline run; release; IPA.

## October18 reference review completion and factual corrections

The [one reference decision table](DOSE_V41_REFERENCE_DECISIONS.md) supersedes generic pending-reference lists in earlier review notes. It contains237 concrete reference/consumer rows:43 ask for policy approval (29 retain existing nutritional curves;14 propose module calibration),194 retain accepted direction, retire unsupported inference to approved neutral, correct facts, or identify descriptive/inactive records. A completed no-general-benchmark conclusion is complete, not Preliminary. These are proposed implementation dispositions; table preparation does not mean all retirements have landed or policy is approved.

Unambiguous committed corrections: immune duplicate zinc/D zeroing and microgram units; Bi07 combination-total basis; five source-fact corrections; literature-regimen-to-minimum fallback retirement with seven existing source records completed-neutral; actual Facts protein quantity ownership; established soluble-nickel UL with form/elemental guards; FDA Daily Value versus RDA policy wording. Engine4.7.3/config1.28.2 identify this technical candidate. No new proposed numerical calibration has been applied.

Measurements use frozen stored inputs only, not regenerated catalog evidence. Immune142: one total67.8→69.0, no safety/status changes. Literature10 against832c1bd7: three lysine Dose10/15→11.4,three MCT6→11.4; four controls unchanged, all safety/status/non-Dose pillars unchanged. Protein252510 Facts27g remains Dose20/total83.6;294273 ingredient-only whey30g becomes incomplete Dose/partial assessment, preserving ingredient mass, other pillars and safety. The latter is a real quantity qualification correction; no purity is inferred. Nickel synthetic regressions pin1mg exactly,1.2mg soluble elemental nickel, unknown salt scope and compound mass. Low unknown-form exposure is bounded using the existing maximum-possible-moiety owner without a salt-identity assertion or false warning; higher unresolved exposure remains review-only. A personal stack containing unknown scoped contributions can remain indeterminate: individually bounded products cannot be blindly excluded when summed. The app guard is paired before qualification.

Current validation:503 combined named pipeline checks pass;124 nickel owner checks and259 protein owner checks pass (overlapping sets, not additive). Config/semantics24 pass; earlier CI679330f1 failed9 checks in four classes, all reproduced and corrected against existing owners. It is not acceptance. Appdd8e0529 analyze/full3951 tests andCI39136864282 passed before the additional form-scope safeguard; that new app candidate requires its own checks. The local rung reported502passed/3known out-of-scope e1_2_2 failures/65skips (41generated-artifact gaps,24declared opt-ins); it is not green/current final acceptance. Missing rebuilt canary/build-dependent cases and declared live opt-ins remain explicit.

Before merge: Sean approves the table; implement approved calibrations and remaining unsupported-curve retirements together in existing owners; make §2.2 exhaustive semantics acceptance executable (the current eleven-record inventory is insufficient); measure the combined candidate and unaffected controls; independent fresh-context review; one green exact completed-candidate CI per repo plus applicable local checks. Keep the separate e1_2_2 owner informed; do not weaken its assertions. Then inspect stage fingerprints and give Sean the required run command. No full pipeline before policy approval, no main push/release/IPA under this task.
