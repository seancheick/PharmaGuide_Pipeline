# Probiotic rubric clinical review — 2026-09-04

## Decision

**Keep the operational rebuild paused. The correctness work is substantially stronger, but the probiotic rubric is not clinically calibrated.** This review found both rubric choices and one further identity/routing defect; they need different fixes.

Audit baseline: `2544beac`, configuration `1.1.1-probiotic-label-dose`, fingerprint `18b7ff59dc1c4baa`. No production rule, reference entry, global weight, catalog, Flutter code or remote state changed. New code is confined to this report's diagnostic tools and their tests. No clinician approval was created.

| Requested conclusion | Finding |
|---|---|
| A. Defensible as-is | Exact label ownership; no invented individual doses; no AFU/CFU conversion; whole-formula evidence confined to the matched formula; null/nonhuman findings distinguished from supportive human evidence; safety independent of quality. These are defensible principles, **not validation of every point amount**. |
| B. Modify | Universal CFU escalation, count-based identity/diversity credit, disclosure credit repeated in Dose, and outcome-insensitive evidence accumulation. Native registry membership must not masquerade as complete label identification. |
| C. Curate | Native strain/dose/population/outcome contexts, negative/null results, exact formula editions, and trial-family relationships. All 49 native registry entries currently lack the structured applicability block; this does **not** mean 49 strains lack studies. |
| D. Before rebuild | Fix the beta-glucan identity conflict; harden outcome/mixture applicability before populating it; repair benchmark ingestion/provenance; curate the high-value contexts; select and test a category-level rubric. Do not restore old scores or change global weights to compensate. |
| E. Ready for calibration? | **No.** Shadow sensitivity is measured; neither the replacement rubric nor the independent reviewer benchmark is ready for calibration claims. |

## 1. Exact budgets and clinical interpretation

Truth sources: `scoring_v4/modules/probiotic_{formulation,dose,evidence,transparency}.py`, `studied_formulas.py`, `probiotic_measurements.py`, and the public adapters/config in `scoring_v4/quality_score.py`.

Formulation and Dose each have a **25-point internal cap**, but their public reference is **22**, normalized to **20**. Thus one uncapped raw point contributes approximately 0.909 public points. Evidence and Transparency are already on their public /20 and /15 scales. Component maxima cannot simply be added beyond pillar caps.

### Formulation

| Signal | Raw points | Assessment |
|---|---:|---|
| Positive total CFU disclosed | 4 | A label-completeness fact, repeated elsewhere. |
| Total CFU magnitude | 1.5 at >0–1B; 3 at >1–<10B; 4 at ≥10B; 5 at ≥50B | No trial-relative applicability test. Up to 4.55 public points for size alone. |
| Named species/strain count | 3 for 1–2; 4 for 3–8; 3 for 9–15; 2 for ≥16 | **Not monotonically increasing**, contrary to a blanket “more strains always wins” diagnosis. The preferred 3–8 band still lacks a demonstrated universal clinical basis. |
| Identified native registry identities | 3/5/7/8 for 1/2/3–4/≥5 | Rewards how many recognized identities exist, not the fraction of the label identified. Registry coverage remains a confounder. |
| Delivery / prebiotic complement | Up to 3 / 1 | Plausible distinct attributes, but a coating or added fiber alone does not prove better clinical outcomes. Exact point amounts remain unvalidated. |

The reviewed AFU formula uses corresponding budgets: 4 native-potency disclosure, 5 studied-formula potency, 8 formula identity, 3 delivery, 1 prebiotic, plus the count curve. It is not exempt from this review.

### Dose

- Individual amount disclosure earns **10 × disclosed fraction** raw points (up to 9.09 public).
- Measured native CFU earns 0/1/2/3 per identity for low/adequate/good/excellent, summed to 5 and multiplied by 3: up to **15 raw** potency points. Two identities at 10B each earn twice the potency credit of one at 10B, even without outcome applicability.
- **48/49** strain records use the same 1B/10B/50B convention; M63 uses the different 5B boundary. Registry notes explicitly call the common bands industry convention, not verified clinical efficacy thresholds.
- Aggregate-only labels receive a 2-point floor, or 4 for qualifying named native identities and total ≥1B. Direct individually owned mass can receive a 5-point floor; neither establishes viable-count adequacy.
- Expiration/manufacture/unknown guarantee factors are 1/.9/.85 on potency, not disclosure. Shelf-life viability is relevant, but the exact discounts require validation.
- The exact reviewed AFU formula receives 25 raw Dose points without invented per-strain allocations. The unit of assessment is appropriate; automatic maximum credit is still a rubric choice.

Higher CFU is not automatically more effective; clinical interpretation depends on the studied organism, condition and population. Shelf-life viable count is a more meaningful label fact than manufacture count. These distinctions are supported by [NIH ODS](https://ods.od.nih.gov/factsheets/Probiotics-HealthProfessional/), not a universal numerical ladder.

### Evidence and Transparency

Evidence has research credit capped at 12 plus dose applicability capped at 8. Without established applicability, contextual research cannot exceed 8. Multiple **applicable** native rows can accumulate research using weights 1/.7/.5/.3. That is not yet proof that combining individually studied organisms improves the finished product.

Transparency gives 8 for named identities, 7 proportionally for individual CFU, with a non-stacking aggregate floor of **2 below 1B, 3 from 1B, 4 from 10B**. This is a third quantity-sensitive pillar: a small and large honestly disclosed count should not differ in disclosure completeness merely because of amount. Exact-formula native AFU already uses a flat 4 floor. Claim bonuses can add up to 4 but clamp at 15. The naming check measures named containers/rows, not universal validation of every exact strain code.

## 2. Cross-pillar fact ledger

| Underlying fact | Formulation | Dose | Evidence | Transparency | Disposition |
|---|---|---|---|---|---|
| Total amount disclosed | 4; plus size tier | Aggregate floor 2/4 | Not clinical applicability by itself | Floor 2/3/4 | Repeated label completeness; remove the quantity dependence in Transparency and avoid calling disclosure clinical dose adequacy. |
| Individual amounts disclosed | Contributes to total summary | Up to 10 before potency | Needed to establish a native studied dose | Up to 7 | Disclosure belongs in Transparency; assess actual dose compatibility separately. Missing allocation should not create another arbitrary deduction. |
| Exact identity | Native count ladder to 8 | Unlocks native measurement | Joins relevant studies | Naming to 8 | Different concepts can legitimately use identity, but identity must be a prerequisite for clinical transfer, not three bonuses for the same string. |
| Amount matches a study | Formula potency 5 on exact path | Formula maximum / native potency convention | Up to 8 applicability | No study-match points | Dose fit and strength of supporting research are distinct. Avoid repeatedly rewarding the match itself without independent meaning. |
| More studied strains | Count rewards | Summed potency rewards | Weighted applicable research | No count bonus beyond naming completeness | Do not infer combination efficacy from a larger evidence list. |
| Exact finished formula | Identity/delivery/potency | Formula-level dose | Formula-specific findings | Native aggregate disclosure | Preserve exact matching and unknown individual allocations. Audit budgets against a modest-strain formula too. |

Pure, source-owned probiotic allocation opacity is already consolidated in the current B5 path; do not reintroduce that fixed duplicate penalty. Shared additive deductions outside these four concepts also need distinct rationales in a later cross-category review, not blanket removal here.

## 3. Adversarial observations

`probes.py` executes the real modules with existing label fixtures. All rows below are **synthetic labels and raw module scores**, not recommended products or public /100 totals. The two “reviewed-scope” rows temporarily supply synthetic applicability fields in memory; no actual clinical approval is implied.

| Case | Formulation /25 | Dose /25 | Evidence /20 | Transparency /15 |
|---|---:|---:|---:|---:|
| LGG 0.1B | 11.5 | 10 | 8 | 15 |
| LGG 1B | 11.5 | 13 | 8 | 15 |
| LGG 10B | 14 | 16 | 8 | 15 |
| LGG 50B | 15 | 19 | 8 | 15 |
| DSM 17938 0.1B, current registry | 11.5 | 10 | 8 | 15 |
| One 10B native identity, simulated applicable context | 14 | 16 | 16 | 15 |
| Two 10B native identities, simulated applicable contexts | 16 | 22 | 20 | 15 |
| 15 unreviewed identities, 100B aggregate | 12 | 2 | 0 | 12 |
| 20 unreviewed identities, 100B aggregate | 11 | 2 | 0 | 12 |
| Two-strain exact-formula counterfactual | 24 | 25 | 10.2 | 12 |

The 100B blends do **not** automatically win the whole score. The concern is specific: size still earns Formulation credit, and multiple individually assessed strains can compound Dose/Evidence without combination evidence.

The DSM case is clinically important: a randomized infant-colic trial studied **0.1B/day for 21 days** and reported reduced crying in its specific breastfed-infant population. Our generic potency contribution is zero at that amount. This is not an adult dose recommendation, but it disproves a universal ≥1B minimum for clinical relevance. [Savino et al., 2010](https://pubmed.ncbi.nlm.nih.gov/20713478/)

The modest-strain formula is a **counterfactual branch test**, not a second real RCT-backed product. The only current assessed commercial formula in this population is Seed. The existing exact-formula implementation is AFU/capsule/pomegranate-shaped; additional formula types need explicit contract coverage before their studies can be represented fairly.

## 4. Measured shadow alternatives

The final report replays **all 551 current candidate probiotic products**: 546 scored and 5 safety-suppressed. Forty use full re-enrichment; the other 511 recompute affected enrichment lanes and scoring from manifest-owned enriched inputs. This is not a 551-product full clean-to-export rebuild. Baseline adapters and authenticated candidate summaries matched exactly; input/code/reference hashes remained unchanged. No blob reconstruction was used.

These are **sensitivity ablations**, not complete clinically approved alternatives. They retain current denominators and global weights, redistribute no points, and do not recompute verdicts or tiers. Removing credit mechanically lowers scores; those lower values are not proposed “fair scores.” Safety-suppressed rows remain scoreless in every arm.

| Shadow | Diagnostic change | Changed /546 | Up / down | Mean delta | Strict ranking reversals* |
|---|---|---:|---:|---:|---:|
| F−size | Remove Formulation size/diversity, including formula potency | 546 | 0 / 546 | −5.960 | 5,587 |
| Identity fraction | Replace count ladder with 8 × recognized fraction | 339 | 160 / 179 | +0.317 | 8,409 |
| T flat | Flat valid aggregate disclosure floor of 4, non-stacking | 153 | 153 / 0 | +0.285 | 1,574 |
| D−disclosure | Remove Dose disclosure/aggregate/mass floors; retain measured potency | 535 | 0 / 535 | −4.264 | 12,373 |
| Combined | First three together; no Dose change | 545 | 21 / 524 | −5.356 | 13,588 |

*Out of 148,785 scored pairs; strict reversals exclude ties. Five suppressed rows are excluded from numerical comparisons, not silently dropped from the report.*

The identity-fraction arm is **not safe to install verbatim**: its numerator still depends on the clinical registry, and denominator provenance needs review. The combined arm still contains generic Dose magnitude/count rewards. Neither is the final rubric.

### Seven mandatory controls

All scores are candidate /100, not necessarily the currently served catalog. IDs bind exact label editions; results must not be generalized to every similarly named product.

| Product / ID | Current | F−size | Identity fraction | T flat | D−disclosure | Combined |
|---|---:|---:|---:|---:|---:|---:|
| Seed DS-01 / `PG_SUB_35E0BD3374BF494B80FEABE87FC559E7` | 81.2 | 75.7 | 81.2 | 81.2 | 81.2 | 75.7 |
| Culturelle Digestive Daily / `250851` | 72.7 | 66.3 | 77.2 | 72.7 | 63.6 | 70.9 |
| Garden of Life 100B / `326762` | 57.4 | 51.0 | 52.6 | 57.4 | 53.8 | 46.2 |
| Fortify 100B / `327965` | 63.6 | 56.6 | 60.5 | 63.6 | 60.5 | 53.2 |
| Ritual Synbiotic+ / `299239` | 55.9 | 49.6 | 58.6 | 55.9 | 52.3 | 52.3 |
| Jarrow S. boulardii + MOS / `307727` | 62.4 | 56.9 | 66.9 | 62.4 | 53.3 | 61.5 |
| Solgar Advanced Multi-Billion / `79324` | 75.8 | 69.4 | 76.7 | 75.8 | 66.7 | 70.3 |

Unexpected movements show why target tuning is unsafe: identity-fraction raises Advanced Acidophilus `81368` from 48.0 to 52.6 but lowers Probiotics 30B `297668` from 54.8 to 49.7. Combined lowers Critical Care 80B `233091` from 54.5 to 42.3 and raises Probiotic + Prebiotic Peach `291259` from 41.2 to 43.7. These are ranking changes, not merely clearer explanations.

## 5. Curation queue and outcome contract

The report contains 36 matched native registry IDs, deduplicated by product. Highest counts: LGG 113, Bl-04 84, NCFM 68, Lpc-37 52, BB536 41, HN001 38, Bi-07 34, HN019 33, DE111 31. S. boulardii has 16 and BB-12 15. These are **catalog reach**, not sales or market share; products may contain several IDs.

Priority is reach plus risk of misleading evidence transfer:

1. **LGG; BB-12; Bi-07; HN019; S. boulardii.** Bounded primary-source review and missing full-text fields are recorded in [research.md](research.md). Preserve positive, null and uncertain endpoints separately. Do not equate species-general S. boulardii evidence with a specific commercial strain.
2. **Bl-04, NCFM, Lpc-37, BB536, HN001, DE111.** High-impact next full-text review batch. Existing literature may concern respiratory illness, stress, pregnancy or other outcomes rather than digestive efficacy. No new clinical scope was authored here.
3. **Exact commercial formulations.** Seed retains its real formula match; do not count companion mechanistic papers as independent symptom replications. The bounded previous Garden/Fortify search did not establish exact-formula evidence; this is not proof no study exists. Ritual and other comparators need exact edition, dose and combination review rather than borrowed ingredient evidence.

Observed Evidence states among the 546 scored products: 359 research-present/applicability-unestablished; 147 applicability-unestablished; 32 human clinical evidence unestablished; 5 native review incomplete; 2 evaluated null; 1 evaluated applicable. No native row currently satisfies the missing structured applicability contract. **184 scored products have Evidence=0; that is not 184 demonstrations of ineffectiveness.**

### Fix the scope consumer before populating its fields

`studied_formulas.py:_assess_strain_scope` verifies dose, exact identity/owner, dosage form and broad target population. It requires a nonempty `supported_outcomes` list but does not match an indication, duration, co-therapy or combination context. Adding broad CFU ranges would unlock credit without fixing those omissions.

Use multiple source-backed assessment contexts, not one universal min/max per strain: exact organism or finished formula; patient population; prevention versus treatment; condition/outcome; studied discrete dose/regimen and duration; co-therapy; endpoint hierarchy; effect direction; trial quality; independent trial-family ID; applicability limits and review completeness. Do not convert tested 1B and 10B arms into proof for every intervening dose, or treat end-of-shelf-life measurements as randomized dose arms.

Patient-important outcomes (diarrhea incidence, pain, bowel movements, quality of life) must remain distinguishable from biomarkers/microbiome changes. Current broad marketing categories are insufficient. Use controlled outcome concepts for AAD, IBS, constipation, infectious diarrhea, bloating, respiratory illness and vaginal health; unsupported contexts remain unassessed, not silently positive or negative. [AGA guidance](https://gastro.org/clinical-guidance/role-of-probiotics-in-the-management-of-gastrointestinal-disorders/) also illustrates indication-specific recommendations: IBS use is recommended only in a clinical-trial context, not blanket endorsement.

## 6. Consumer meaning and the additional correctness defect

The app already has separate `product_safety_status`, `quality_assessment_status`, and score-confidence semantics. `catalog_product_semantics.dart` does not equate legacy POOR with an unsafe product. `confidence.py` treats incomplete native evidence review as moderate rather than automatically low. Preserve that work; no second semantic system is needed.

However, an unqualified quality tier still summarizes a composite where unfinished Evidence review can reduce available points. Adding “not a quality finding” to the explanation does not remove that mathematical effect. Proposed policy: keep measured label/manufacturing facts, explicit safety findings, evidence strength, applicability, and review completeness separate; mark incomplete composites **provisional** and do not present their rankings as equally assessed. Do not invent evidence points, silently rescale weights, or treat our unfinished search as proven poor quality.

**New pre-rebuild correctness finding — Jarrow Beta Glucan `264610`:** the source ingredient is `Saccharomyces cerevisiae extract`, 250 mg, with a form stating at least 75% beta-1,3/1,6 glucans. DSLD's ingredientGroup instead says S. boulardii. The identity repair replaces `brewers_yeast` with `saccharomyces_boulardii`; broad yeast text then admits a probiotic payload/route. Current scoring returns 28.3, Dose=0 and probiotic-strain/CFU copy. A separate full re-enrichment from the manifest-owned cleaned row reproduced this exactly. Native strain evidence is now correctly rejected, but the conflicting identity still routes incorrectly. Resolve literal/form versus taxonomy conflict at the identity boundary; do not impose CFU requirements on a cell-wall extract or “fix” it by boosting the probiotic score. No replacement identity or route was guessed or installed in this audit.

## 7. Blinded benchmark readiness

Confirmed executable and provenance issues:

- `parse_review_doc.py` omits required `review_sequence`; analysis requires it. Parser emits free-text citations into `source_citations_json`; analysis requires a JSON list. Existing green tests do not cover the actual document → parser → analysis round trip.
- The fixed design expects 3 independent reviewers × 120 products, including at least 2 licensed clinicians. Only one completed set is recorded; remaining slots are unfinished. Its provenance explicitly discloses AI assistance and exposure to a prior AI review; `protocol_deviation=none` does not erase that fact.
- The reviewer-facing protocol reveals the 96/24 design and challenge criteria. This does not reveal every hidden ID, but conflicts with the proposed independent-review brief. The revised protocol/brief remains unratified.
- Historical v6 **does exist** in the original checkout (`scripts/reports/v4_reviewer_benchmark_2026_08_06_v6`); it froze schema 2.3, 13,271 products and 120 cases, including 10 probiotics. Do not claim the freeze is missing because it is absent from this worktree. It is a historical baseline, not validation of today's changed candidate.

Minimum repair: one versioned parser/analysis contract plus round-trip tests; machine-readable reviewer exposure/deviations; preserve assisted results as an explicitly exploratory arm; finalize an independent panel and ratify its brief/statistical plan **before** exposing new results; freeze current inputs and hidden engine scores with hashes; prespecify any probiotic challenge extension without tuning against its holdout. Removing one reviewer is not the original 3-rater primary analysis. No sealed development/holdout key was opened during this audit.

## 8. Execution handoff and verification

Do next, in small tested batches: identity/routing conflict → outcome/combination applicability contract and benchmark ingestion → prioritized source curation → category-level replacement proposal with matched denominators, adversarial cases and corpus ranking diffs → locked independent benchmark. Global weights stay unchanged unless independent validation justifies a separate calibrated release. Then run the operational rebuild once and apply normal artifact/Flutter/release gates.

Do not install these ablations as the replacement rubric. A clinical dose-relative alternative cannot honestly receive a full-corpus efficacy score until its source contexts exist; its current eligibility is 0 native contexts and 1 exact formula, not a license to award the rest zero efficacy.

Artifacts:

- [verified_shadow_summary.json](verified_shadow_summary.json): compact, reproducible counts, seven controls, baseline and full-report SHA-256.
- Full report: `/Users/seancheick/Downloads/dsld_clean/reports/probiotic_rubric_review_2026_09_04/shadow_full_final.json`; SHA-256 `eb6497d415c36492b1c957cc00e42d126a45929680c39109706299188145378f`.
- [shadow.py](shadow.py): manifest-owned read-only replay, authenticated baseline, unchanged production/input hashes, public-adapter parity, all five arms.
- [probes.py](probes.py): ten explicitly synthetic boundary cases, temporary test-only scopes, no registry writes.

Independent review identified three reporting gaps (formula AFU ablation coverage, numerical denominators, per-arm non-scored state). Each received failing tests and a correction; final replay remained 551/551 with zero baseline disagreements and zero errors. AFU disclosure already used the flat floor, so its explicit coverage correction did not change Seed's shadow scores. The earlier `shadow_full.json` is superseded by `shadow_full_final.json`. A second independent pass reviewed the final narrative, synthetic probes, harness, compact results and tests and found no further actionable report issues. This is engineering review, not clinician validation.

Verification: **194 passed, 3 skipped** via `scripts/test.sh fast`, covering the new shadow/probe tests, existing label-dose independence, applicability/formula tests, benchmark freeze/analysis and reviewer-document tests. The three skips require built detail blobs unavailable in this worktree; they are not represented as passing artifact checks. The diagnostic test file alone contains 19 passing cases. No full suite, operational rebuild, migration, upload or release was run for this report-only batch. Clinical curation, benchmark repair, rubric selection and the newly identified production defect remain explicit work—not silently claimed complete.
