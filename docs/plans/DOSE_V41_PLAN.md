# Dose V4.1: finish the shared rules before one pipeline run

Status: **candidate on `claude/dose-v41`; reference research and factual bug fixes completed October18, revised 37/2/4 calibration decisions and explicit prenatal choline membership await Sean; final implementation/validation still required. Not merge/run/release-ready. See [the reference decision table](DOSE_V41_REFERENCE_DECISIONS.md) and [review packet](DOSE_V41_REVIEW_PACKET.md).** Revised October 17, 2026 after Sean's
design review (grill). Baseline: `main` at `b043fc513`, engine 4.6.0, config
`1.27.0-declared-serving-dose`. This plan supersedes the serving-only Dose decision recorded in
`reports/declared_serving_20261017/README.md` (PR #154).

Sean decided the four questions in "Decisions from the design review". Every other statement
names its owner or the command that verified it. Validation class: **behavioral** (AGENTS.md
table). Sean runs the pipeline; no agent runs the corpus, a release or an IPA build.

---

## 0. Decisions from the design review (October 17, 2026)

| # | Question | Decision (Sean) |
|---|---|---|
| D1 | Minimum directed use already above a UL | No automatic Dose 0. The minimum is graded like the maximum. One product-level ceiling, applied once after aggregation: ≤100% none; >100% and <150% → cap 10; ≥150% → 0. Minimum vs maximum changes the explanation only. |
| D2 | Which UL for a general-adult product | Safety screening uses the **lowest established UL across ordinary adult groups** (calcium 2,000 mg; phosphorus 3,000 mg). A population printed on the label narrows it. Adequacy references unchanged. |
| D3 | Sports above-range reductions | Remove the protein, creatine, beta-alanine and HMB cuts. Caffeine's in-band cut is removed; total daily caffeine feeds the same final ceiling against 400 mg/day. |
| D4 | Sequencing | **Both** the pipeline Dose candidate **and** the app batch (receipt rendering/parity + personal UL checker fix) must be complete and validated before Sean runs the pipeline. |

The 10/0 ceilings and the caffeine 600 mg boundary are **PharmaGuide scoring policy**, not
medically established toxicity grades. Explanations must say so where they cite a limit.

---

## 1. Goal and ownership

Complete the Dose correction across every scoring route, including omega, magnesium, calcium and
potassium. Deliver one measured, documented candidate (pipeline and app) before asking Sean to run
the pipeline.

**Exposure rule:** minimum directed daily use determines adequacy; maximum directed daily use
determines safety.

### Owner Check

| Concern | Owner (extend, do not duplicate) | Evidence |
|---|---|---|
| Canonical ingredients, quantities, scoring inputs | `scripts/scoring_input_contract.py` (incl. `declared_serving_dose_input`) | source read; matrix `scoring_input_contract` (ADR-0002) |
| Daily-use range | `scripts/serving_frequency.py::resolve_daily_serving_range`, via `generic_helpers::daily_serving_range` / `daily_serving_multiplier` | the helpers still exist; the 2026-09-28 policy "benefit at the minimum, risk at the maximum" is in their docstring |
| Route Dose wrapper to replace | `generic_helpers::score_declared_serving_dose` (1.27 serving-only wrapper all routes call) | `rg score_declared_serving_dose scripts/scoring_v4` |
| Source-owned dose assessments | `scripts/dose_assessment.py` | source read |
| Public Dose normalization, receipts | `scripts/scoring_v4/quality_score.py` (`_receipt_entry`, Dose pillar assembly) | source read |
| Excess evaluation (typed states) | `scripts/scoring_v4/dose_safety.py` (`evaluate_dose_safety`, `confirmed_over_threshold`, `material_but_unresolved`) | source read |
| UL selection | `scripts/rda_ul_calculator.py::_get_age_sex_values` with `enrich_supplements_v3::_RDA_REFERENCE_PROFILE` (19–30, max RDA / min UL across sexes) | source read |
| Magnitudes | `scripts/scoring_v4/config/quality_score.json` (`dose_subscale`, `dose_magnitudes`, `dose_safety_policy`) | config read |
| Neutral value | `dose_subscale.unbenchmarked_neutral_public` via `generic_helpers::unbenchmarked_dose_credit` | source read |
| Omega purpose | `scripts/evidence_resolver.py::resolve_omega_evidence_standard` (ordinary / prenatal / triglyceride) | `docs/scoring/OMEGA_DOSE_REVIEW_2026-10-17.md` §Owner |
| Reference records | `scripts/data/rda_optimal_uls.json` (DRI rows, clinical anchors), config band tables, `studied_formulas` | data/config read |
| App assessment state | Flutter `lib/core/scoring/catalog_product_semantics.dart::catalogAssessmentStatus`, `lib/services/recommendations/better_alternatives_ranker.dart::isCatalogScoreSuppressed` | source read |
| App personal UL | Flutter `lib/services/stack/stack_ul_checker.dart`; catalog UL reader `lib/services/health/dose_safety.dart` | source read |

**Will NOT create:** a second scorer, a parallel clinical registry, a new purpose resolver, a
brand-specific adjustment, a new top-level score/status, or any independent Flutter calculation of
catalog quality. Extend the owners above.

Keep the current approved scorer as the comparison baseline. Reconsidering a policy does not make
an otherwise completed assessment Preliminary.

---

## 2. Shared Dose contract

### 2.1 Exposure
- Adequacy: **minimum** explicit daily directions. Safety: **maximum** explicit daily directions.
  Replace `score_declared_serving_dose` with this; do not add a parallel wrapper.
- No daily directions: one Facts-panel serving, explicitly identified as the default
  (`resolve_daily_serving_range` already returns `was_defaulted`).
- Preserve elemental amounts, preparation identity, units, population and source qualifications.
  Ambiguous directions or unread amounts never become invented exposures.
- Retain per-administration information for context (e.g. divided calcium dosing). Never infer an
  unprinted schedule.

### 2.2 Reference meaning
Extend each **existing** reference record (in its current owner file/config, with one shared
schema and one CI check) with: reference type, scope, preparation, purpose, population, exposure
basis, units, applicable curve, source identifiers, rationale, owner, review date, approval status.
Do not create a central registry beside them.

Reference types to distinguish: nutritional reference; supplement-contribution policy; supported
minimum; genuine bounded window; discrete studied regimen; null regimen; safety-only reference;
completed absence of a benchmark; unfinished review.

- Approved proportional curve: `20 × min(amount / target, 1)`.
- An isolated trial dose establishes no minimum, continuous range or upper limit.
- Source-supported thresholds/windows need an explicitly reviewed curve.
- Above-target amounts earn no extra credit. A reduction needs a justified appropriateness boundary
  or a safety reference, and is then applied only through §2.4.
- Evidence strength never multiplies or caps Dose points (known instance: sports ATP capped at 12
  "weak-equivocal evidence", `sports_dose.py` ATP branch).
- CI rejects any active numerical anchor lacking complete semantics and approval metadata.

### 2.3 Neutral and incomplete states
- 11.4/20 neutral/unassessable (`unbenchmarked_neutral_public`) for completed no-reference
  conclusions and genuinely hidden amounts. Transparency keeps the missing-disclosure consequence.
- "80% of the reference" never becomes "80% effective" or "proven inadequate".
- Unfinished research uses the existing partial/Preliminary mechanism. The app already maps
  `quality_assessment_status = partial` and excludes it from ranking.
- Material identity failures or pipeline-lost amounts follow the existing strict holds; no neutral
  fallback.

### 2.4 One final safety ceiling (D1)
Order: adequacy per ingredient → route aggregation → normalize to public 0–20 → apply the
**strongest** applicable ceiling **once**:

| Confirmed exposure vs applicable upper reference | Final Dose |
|---|---:|
| ≤100% (exactly 100% is not an exceedance) | no ceiling |
| >100% and <150% | at most 10 |
| ≥150% | 0 |

- Evaluated on maximum directed daily use. The minimum is graded the same way. Because the
  maximum is at least the minimum, the maximum sets the band; the minimum only changes the
  explanation: "even the lowest directed use exceeds the limit" vs "the higher directed amounts
  exceed it".
- The automatic `minimum > UL → 0` rule from the earlier draft is **removed**.
- The ceiling is product-level on every route, panels included. Other nutrients cannot dilute an
  excessive one, and a nutrient excluded from adequacy aggregation (incidental) still counts.
- The ceiling never raises a lower score.
- Remove both current excess paths: the per-nutrient UL bands in
  `generic_dose::_band_credit` (`window_overdose_credit` 11/22; ≥150% → 0) and the B7 subtraction
  (`dose_safety_policy` −2/flag, cap 3). Keep `B7_safety_evaluation` metadata, which Safety/Hygiene
  already shows without deducting (`quality_score.py::_pillar_safety_hygiene`). The same exposure
  reduces no other pillar.
- `material_but_unresolved` keeps its review state with no numerical ceiling.
- Non-UL upper references (caffeine, §3.3) use the same bands only where explicitly approved;
  any other non-UL threshold keeps its own source-supported meaning and applicability.
- Niacin: the FNB UL applies to nicotinic acid and niacinamide alike
  (https://ods.od.nih.gov/factsheets/Niacin-HealthProfessional/). Explanations must not attribute
  nicotinic-acid flushing to niacinamide.

### 2.5 UL selection for catalog screening (D2)
- No stated adult population: lowest established UL across ordinary adult male/female groups.
- Stated population: lowest applicable UL across that whole population (calcium "19–50" → 2,500;
  "50+" → 2,000).
- Pregnancy, lactation, pediatric: their own references, never the general-adult fallback. Do not
  assume every nutrient has a different pregnancy UL.
- Change **safety** selection only. Adequacy (`adequacy_basis` = higher sourced adult RDA/AI) is
  unchanged; do not simply change `_RDA_REFERENCE_PROFILE.age_range`.
- The one selection feeds both the shared warning/status owner and the Dose ceiling.
- Wording names scope, e.g. "Maximum labeled use exceeds the calcium limit for adults 51+." Calcium and phosphorus
  have total-intake limits; other nutrients may have source-restricted limits. Use each reference
  scope. A product below a total-intake limit does not establish that food plus supplements stays below it.

| Nutrient | General-adult screening UL | Source rows |
|---|---:|---|
| Calcium | 2,000 mg/day | 2,500 (19–50); 2,000 (51+). https://ods.od.nih.gov/factsheets/Calcium-HealthProfessional/ |
| Phosphorus | 3,000 mg/day | 4,000 (19–70); 3,000 (71+). https://ods.od.nih.gov/factsheets/Phosphorus-HealthProfessional/ |

---

## 3. Calibrations and route behavior

### 3.1 Ordinary-adult references
| Nutrient | Treatment |
|---|---|
| Magnesium | proportional to 84 mg elemental/day, then plateau |
| Calcium | proportional to 260 mg elemental/day, then plateau |
| Potassium | 11.4 neutral, completed assessment, unless an applicable purpose-specific reference exists (it is already excluded from the generic proxy: `_DIETARY_INTAKE_DOMINANT_CANONICALS`) |
| Omega EPA+DHA | proportional to 250 mg/day, then plateau |
| Omega, explicit applicable triglyceride purpose | 2,000 mg/day purpose-specific reference, read from `resolve_omega_evidence_standard` |
| Prenatal omega | keep the explicit DHA reference (`prenatal_dha_full_mg` 200); combined EPA+DHA cannot substitute for undisclosed DHA |

- Magnesium/calcium targets are PharmaGuide contribution-policy targets = 20% of FDA Daily Value
  (420 mg, 1,300 mg). The current engine uses the "legacy" macro band (full at 25% of the 400 mg
  19–30 RDA = 100 mg). FDA's 20% threshold applies per RACC; applying it per minimum directed day is
  PharmaGuide's adaptation, not a label-claim certification.
  Sources: https://www.ecfr.gov/current/title-21/chapter-I/subchapter-B/part-101/subpart-D/section-101.54 ,
  https://www.fda.gov/food/nutrition-facts-label/daily-value-nutrition-and-supplement-facts-labels
- Magnesium safety: adult 350 mg supplemental/medication UL, excluding food
  (https://ods.od.nih.gov/factsheets/Magnesium-HealthProfessional/). The data row already carries
  350 with that note.
- Calcium safety: §2.5. Above 500 mg per confirmed administration → absorption context only, no
  numerical penalty. Distinguish divided from single administration; never infer a schedule
  (https://ods.od.nih.gov/factsheets/Calcium-HealthProfessional/).
- Omega ordinary target: the selected EFSA reference (https://www.efsa.europa.eu/en/efsajournal/pub/1461),
  without implying everyone needs it from supplements. 4 g/day prescription context: no extra points,
  no prescription-equivalence claim. Rationale: `docs/scoring/OMEGA_DOSE_REVIEW_2026-10-17.md`.
- Contribution targets apply only to ordinary adult single-nutrient products and ordinary generic
  formulas with a declared nutrient purpose. Prenatal, pediatric, panel and clinical-purpose
  standards keep their own references.
- Guard: no ordinary target may require an amount above its applicable supplemental UL (84 < 350).

### 3.2 Aggregation by route
| Route | Rule |
|---|---|
| Generic | Equal average over declared purpose ingredients (already one vote each, `_score_declared_purpose_window`); exclude incidental rows and duplicate projections; unbenchmarked purpose = neutral |
| Multi / prenatal | Keep required-panel, critical-nutrient and prenatal-complement structure |
| B-complex | Keep the fixed expected panel |
| Sports | One primary → its benchmark; multiple co-primaries → their average (replaces strongest-anchor-only) |
| Probiotic | Applicable exact studied formula → its formula assessment; otherwise average of co-primary strain assessments including neutral states (replaces current strongest-strain `max`) |
| Fiber | Keep the source-owned aggregate fiber assessment; separately purpose-owning non-fiber actives keep their own |

Every route uses the shared exposure, reference, neutral and §2.4 ceiling rules.

### 3.3 Sports above-range behavior (D3)
- **Remove** reductions caused solely by exceeding a studied range: protein >40 g (16), creatine
  >10 g without loading (16), beta-alanine >6 g (16), HMB >6 g (16). Adequacy plateaus. Keep
  independently supported warnings and regimen distinctions.
- **Caffeine:** remove the in-band `caffeine_above_400_mg` → 14. The per-use performance benchmark
  (`basis="per_use"`) stays a separate adequacy assessment; it does not become a daily benchmark.
- Total declared **daily** caffeine, including quantified caffeine from other ingredients, without
  counting a declared total and its components twice. Unknown stays unknown. It feeds §2.4 as an
  approved non-UL upper reference:

| Maximum directed caffeine/day | Final Dose |
|---|---:|
| ≤400 mg | no caffeine ceiling |
| >400 and <600 mg | at most 10 |
| ≥600 mg | 0 |

  400 mg/day is FDA's "generally not associated with negative effects for most adults", all sources
  (https://www.fda.gov/consumers/consumer-updates/spilling-beans-how-much-caffeine-too-much); the
  600 mg boundary and points are PharmaGuide policy. Keep EFSA acute context: single doses up to
  200 mg (https://www.efsa.europa.eu/en/topics/topic/caffeine); under 400 mg/day is not reassurance
  about taking it all at once.
- Calibrations to review in the packet: caffeine 200–400 mg tops at 18, not 20; ATP's evidence cap
  of 12 (§2.2).

### 3.4 Cleanup
Remove obsolete active legacy/interim calibration wording (e.g. the `generic_dose.py` module
docstring describing the RDA/UL proxy and B7) after validation. Keep historical records as history.

---

## 4. App, connector and explanation contract

Extend the existing nested pillar explanation; no new top-level score or status. Declare any new
blob key in `scripts/audit_contract_sync.py::BLOB_TOP_LEVEL` only if one is truly top-level (none is
expected) and name the Flutter consumer.

Every Dose receipt shows:
- the serving amount, and minimum/maximum directed daily exposure (and which was defaulted);
- the reference, its scope, and whether it is clinical guidance or PharmaGuide policy;
- ingredient/panel contributions and the aggregation rule;
- adequacy score before safety;
- the applicable upper reference, its population scope, exposure %, and the ceiling applied;
- the final Dose, with arithmetic that reconciles exactly.

Flutter and the public connector render the same recorded result. Preserve warning deduplication.
Distinguish a per-capsule amount from maximum daily exposure.

**Worked example (Pure Magnesium Glycinate, DSLD 205309).** Probe on `b043fc513`
(`build_scored_artifact` on `scripts/products/output_Pure_Encapsulations_enriched`): today it scores
86.6, Dose 20, serving basis, with an adequacy row of 120 mg, 30% RDA, 137% UL at 480 mg max. Under
this plan, minimum 120 mg ≥ 84 mg gives 20 adequacy. Maximum 480 mg = 137% of 350 caps Dose at 10.
Predicted total 76.6, the pre-1.27 value. Confirm through the real scorer; do not preserve 87.
Control 299065 (one capsule daily, 34% UL) stays Dose 20.

Preliminary assessments stay distinguishable from completed neutral ones and cannot enter
completed-quality rankings (already enforced by the app predicates in §1).

### 4.1 App batch (D4: required before the pipeline run)
**A. Receipt rendering and parity:** render §4 receipts from the recorded result; no recomputation.

**B. Personal UL checker root-cause fix** (`lib/services/stack/stack_ul_checker.dart`). These
defects were reproduced by reading the source at the line numbers below:
1. Boundary: `pctOfUl >= 100.0` classifies exactly 100% as exceeding (≈l.424). It must be `> 100`,
   matching `dose_safety.dart` and §2.4.
2. Anonymous fallback takes the lowest UL across **all** demographic rows, including children
   (≈l.398–404). It must use the adult screening rule in §2.5, and a missing profile is
   "not assessed", never "no concerns".
3. Mixed references: when the pipeline verdict is over UL, the percentage comes from the catalog
   `verdict.pctUl` while the UL is the person's (≈l.199–203). Percentage, tier and warning must use
   one applicable reference.

Fix by preserving the pipeline's verified identity, amount and exposure scope, then comparing that
exposure against the correct reference for each assessment.

Three layers stay separate:

| Layer | Purpose | Changes with profile |
|---|---|---|
| Product quality | catalog score, six pillars, general warnings | no |
| Personal assessment | age, sex, pregnancy/lactation, conditions, medications | yes, on device |
| Stack assessment | combined exposure vs applicable references | yes, on device |

App acceptance:
- The same product shows identical quality/pillars across profiles.
- Personal % and warning use the same reference.
- Editing or clearing the profile refreshes the assessment.
- A missing profile shows "not assessed".
- Label-directed exposure is distinguished from actual intake.
- Demographics stay on the phone.
- Pregnancy selects its applicable references.

---

## 5. Measurement, acceptance and handoff

### 5.1 Review packet (before activation): ten outputs
1. inventory of active reference types;
2. every benchmark missing declared semantics;
3. every highest-studied-dose upper-bound misuse (includes the four §3.3 sports cuts);
4. every Evidence→Dose numerical dependency (includes ATP's evidence cap of 12);
5. every disclosure→Dose dependency;
6. every duplicate excess deduction (includes the `_band_credit` UL bands and B7);
7. minimum-daily vs serving-only impact;
8. final omega-policy impact;
9. the complete calibration-record diff, including the three minerals and the D2 UL selection;
10. permanent golden-case tests and results.

### 5.2 Sizing already known (stored inputs; not scored)
Read-only screen of 15,426 manifest-owned enriched inputs, using the pipeline's unit-converted
`pct_ul` (raw `per_day` vs `ul` mixes units: e.g. boron 500 mcg vs 20 mg):

| Class | Products |
|---|---:|
| Minimum use already above a UL | 937 (561 of 2,624 multi-panel; 376 other) |
| Only maximum ≥150% | 71 |
| Only maximum >100% and <150% | 74 |

Leading nutrients: niacin in multis (513), magnesium (194), vitamin D (100), B6 (47), zinc (40).
Under D1, a minimum between 100% and 150% now caps at 10 rather than 0. Re-measure on the scored
seam; this screen is not a scored claim.

### 5.3 Measurement method
Use `scripts/audits/quality_redesign/replay.py` (freeze-raw, snapshot, compare) on identical frozen
inputs. Separate the effects (exposure, calibration, neutral, aggregation, safety ceiling, D2 UL
selection, sports/caffeine), then measure the combined candidate. Report pillar/total/tier changes
separately from safety-state, assessment-status, identity and routing changes, with unaffected
controls on every route. The D2 measurement must include calcium max use >2,000–2,500 mg (newly
capped at 10) and 3,000–<3,750 mg (10 → 0), plus any warning/status change.

### 5.4 Required regressions (fail-first)
- Target coverage, plateau, exact UL boundaries (100% exactly; just above; just below 150%; 150%).
- Ranged use exceeding the UL vs fixed use already above it: both graded by magnitude (D1). Expected
  explanation differs.
- Neutral plus ceiling; a ceiling never raises a low score.
- Product-level ceiling on a panel: one nutrient over cannot be diluted; incidental nutrient counts.
- Discrete/null regimens, wrong preparations, unsupported upper bounds.
- Hidden amounts vs pipeline-lost amounts.
- Magnesium 84 mg, calcium 260 mg, potassium neutral, ordinary omega 250 mg, triglyceride-purpose
  2,000 mg, prenatal DHA.
- Calcium once-daily vs divided administration (context only).
- D2: general adult calcium 2,000; labeled 19–50 → 2,500; labeled 50+ → 2,000; pregnancy/pediatric
  use their own; adequacy unchanged.
- Caffeine: 400, just above 400, just below 600, 600; repeated servings; multiple sources; declared
  total plus components (no double count); unknown amount; caffeine not primary.
- Sports: protein/creatine/beta-alanine/HMB above former cuts plateau; one primary vs co-primary
  average.
- Probiotic exact studied formula vs averaged strains with neutral states.
- Required panels (multi/prenatal, B-complex).
- No ordinary target requires an amount above its supplemental UL.
- Niacinamide explanation does not claim flushing risk.
- Pure 205309 → Dose 10 through the real scorer; 299065 control unchanged.
- App: receipt parity with pipeline, warning deduplication, completed-ranking eligibility, and the
  three §4.1B defects plus the acceptance list.

### 5.5 Gates and handoff
1. Focused regressions and affected owner/consumer tests (pipeline and app).
2. One independent fresh-context review (requirement + owners + diff only).
3. Required local checks (`scripts/test.sh local`) and one completed-candidate CI checkpoint per
   repo. Resolve all known failure classes before requesting another broad checkpoint.
4. Bump config version/engine identifier; update `scripts/SCORING_ENGINE_SPEC.md`,
   `docs/plans/DOSE_V41_REFERENCE_DECISIONS.md` and the existing handoff/LEDGER.
5. Integrate validated source changes in both repos (main pushes are Sean's).
6. Inspect actual stage fingerprints, then give Sean the exact earliest-stage command. Today's
   form, to be re-confirmed against the fingerprints:
   ```bash
   cd /Users/seancheick/Downloads/dsld_clean
   source scripts/python_env.sh
   PYTHON="$PG_PYTHON" bash batch_run_all_datasets.sh --pipeline-only
   ```
7. Sean runs the pipeline. After that: verify new artifacts, catalog, export and app against them;
   release and IPA only under Sean's authorization.

### Sean-only decisions remaining
Approval of the calibration-record diff (packet item 9) and activation; pushes to `main`; the
pipeline run; catalog release; IPA build.
