# Six-pillar scoring diagnosis — 22 September 2026

## Conclusion

High scores are possible, but they do not currently mean the same achievement across product types. The concern is justified. The strongest findings are inconsistent daily-dose handling, ingredient-count dependence, universal form-quality denominators that some nutrient families cannot reach, and overlapping pillar rewards/penalties. Raising scores across the board would conceal these problems.

This is a diagnosis, not a scoring change or release. No clinical records, policy values, production code, or existing tests were changed. The repository already contained unrelated edits to canary tests and an audit document; those were preserved.

## What was examined

- The local distributed SQLite catalog: 15,310 products, including 15,240 scored and 70 safety-suppressed. Its scoring engine is 4.4.0; quality configuration is 1.12.0.
- Current source and configuration 1.13.0, including the shared classifier, seven route modules, profile adapters, six public-pillar assemblers, safety/completeness gates, evidence disposition, and underlying omega rubric.
- Current-scorer replay of stored enriched products, with per-file input hashes and per-product breakdowns. This does not regenerate enrichment or prove the running app/cloud release is current.
- Controlled arithmetic probes at production module boundaries. Synthetic probes establish behavior of the formula; they are not invented clinical evidence or proof that a commercial product qualifies for a score.
- Seven existing targeted test files: 319 tests passed. Tests validate current contracts; they do not establish that those contracts are scientifically calibrated.

Machine-readable summaries and provenance accompany this report. Large per-product debug output is retained under `/tmp/pg_scoring_diagnosis_20260922/`.

## Findings in priority order

### 1. Daily-dose equivalence breaks in sports and fiber

**Confirmed implementation inconsistency.** `sports_dose.py:49` uses row quantities through `sports_helpers.dose_g`; `fiber_digestive_dose.py:25` uses fiber grams per serving. Neither applies the label-directed daily serving range on these category-specific paths.

Production-helper probes, with the shared serving resolver independently confirming the label's serving count:

| Same daily exposure | Label representation | Public Dose |
|---|---|---:|
| Creatine, 3 g/day | 1.5 g × 2 servings/day | 6.4/20 |
| Creatine, 3 g/day | 3 g × 1 serving/day | 20/20 |
| Psyllium, 6 g/day | 3 g × 2 servings/day | 12.8/20 |
| Psyllium, 6 g/day | 6 g × 1 serving/day | 16.8/20 |

The creatine gap also triggers the focused-single completion bonus, amplifying the quantity-basis error. Correct each benchmark's exposure basis explicitly: daily intake for daily benchmarks, per-use exposure where the reviewed benchmark actually concerns a session. Do not blindly multiply all sports doses, especially caffeine, by a daily count.

There is a second exposure-policy inconsistency: omega uses midpoint daily servings, generic clinical evidence delegates to the maximum daily-serving helper, and probiotic measured potency uses minimum daily servings. These are materially different for variable directions. A shared resolver alone does not guarantee a shared adequacy policy.

### 2. Single-strain probiotics cannot earn the same Dose/Evidence ceiling as blends

**Confirmed structural disadvantage on the ordinary native-strain path.** Probiotic Dose gives 10 raw points for complete per-strain disclosure, then sums potency-tier points across strains. One “excellent” strain supplies at most 3 × 3 = 9 adequacy points. Thus its raw maximum is 19, normalized against 22: **17.3/20**, even with an expiration guarantee. Two excellent strains can fill the adequacy budget. A reviewed complete-formula route is a separate exception.

Native Evidence similarly assigns at most 8 research points to one strongly supported strain, plus 8 applicability points: **16/20**. Multiple applicable strains can fill the 12-point research lane. An independent generic-evidence or complete-formula contribution can alter this; 16 is not a universal cap on the entire probiotic route.

Formulation also reserves 1/16 raw points for a prebiotic complement and 3/16 for delivery/survivability signals. A plain single-strain product must add qualifying features to fill those budgets, regardless of whether those features are necessary for its reviewed use.

The rubric needs a purpose-fit test: can one appropriately delivered strain with strong applicable evidence earn full marks without adding organisms or a prebiotic solely to collect points? NIH ODS cautions that higher CFU counts are not necessarily more effective and emphasizes strain/product-specific evidence: https://ods.od.nih.gov/factsheets/Probiotics-HealthProfessional/ . This supports reviewing the count-based design; it does not itself prescribe numerical replacements.

### 3. Omega Evidence has an indication ceiling, an ingredient-count ceiling, and a surviving dose floor

**Confirmed arithmetic; policy requires review.** `omega_evidence.py:100` takes generic clinical Evidence capped at 15 and adds 5 only for prenatal-DHA labeling meeting its DHA target. Non-prenatal omega therefore has a hard **15/20 upper bound**, even with unlimited qualifying clinical support elsewhere in that pipeline.

For ordinary focused products the bound is tighter: generic Evidence contributes at most 7 per canonical evidence identity with weights 1/.7/.5/.3 and at most .5 depth. One identity yields at most 7.5; two yield 12.4. The omega class floor raises sufficiently disclosed EPA/DHA to 10, but does not solve the breadth-dependent formula.

The prenatal example's clinical 10 is therefore not evidence that its clinical data earned 10. The surviving `disclosed_epa_dha_clinical_floor` awards 10 at 250 mg/day. This is still a dose-derived Evidence floor, despite configuration prose saying ingredient-presence floors and duplicate Dose credit were removed. The prenatal bonus also remains a label-context-plus-dose condition, rather than a requirement for a matched reviewed indication record.

Changing only the normalization reference from 20 to 15 would turn that class floor from 10/20 into 13.3/20; it would not repair the evidence model. The appropriate correction is a reviewed omega-specific evidence standard with consistent indication ownership, then its matching denominator.

Omega Dose additionally gives general products 5/20 at 250 mg, 10 at 500 mg, 16 at 1 g, and 20 at 2 g/day. That rewards a higher-dose use case, not universally optimal nutritional adequacy. NIH distinguishes indication-specific evidence and does not establish a universal EPA/DHA RDA: https://ods.od.nih.gov/factsheets/Omega3FattyAcids-HealthProfessional/ . The scoring purpose must be explicit before changing these anchors.

### 4. Multi and B-complex Formulation normalize against unattainable family ideals

**Confirmed denominator/data mismatch for ordinary broad panels; not an absolute module cap.** Multi Formulation is `12 × max(weighted_mean_bio_score, 9)/15 + disclosure_credit`, divided by 14 and scaled to 20. Full credit requires every positively weighted form to score 15, complete disclosure, and no penalties.

The current IQM's listed B2 forms top out at 10, B3 at 11, B6 at 10, B12 at 11, iodine at 12, and iron at 13. These are observations about local ratings, not new assertions about clinical superiority. A panel containing these nutrients cannot average 15 merely by choosing its best listed forms. Some names/forms have separate parent entries, so these maxima must not be used as a universal nutrient lookup without identity reconciliation.

B-complex uses the same universal 15 denominator for its eight-point form-quality component. Its other components reward the core B panel, focus, and dose disclosure. The observed 17.5/20 maximum does not prove 17.5 is a mathematical cap; a synthetic all-15 panel can fill the formula. But such a synthetic panel is not a defensible benchmark when the curated family ratings cannot supply those values.

The low end is compressed too: explicit multi form ratings averaging 0, 5, or 9 all produce **13.1/20 before penalties**, when doses are disclosed. The neutral rule is applied to the panel average, not just missing ratings. This erases differences among known lower-rated forms.

Use reviewed nutrient/form-family attainable standards and distinguish an unknown rating from a known low rating. Do not lower the denominator to today's best commercial product or raise IQM ratings to force the total upward.

### 5. Verification is coarse, but Claude's description and proposed fix are not established

The catalog has **eight** values, not four: 6 (5,673), 8 (4,682), 10 (3,842), 15 (808), 5.5 (214), 3.5 (12), 4.5 (8), and 6.5 (1). The four main values account for 15,005 of 15,240 scored products. Violation deductions explain additional values.

There is intentional scope ordering: unknown baseline 6, claim/brand ceiling 8, manufacturing ceiling 10, and product-level certification floor 11 with saturation at 15. But these are **ceilings, not fixed rungs**. A direct audited-GMP-only probe scores 8; adding the existing COA/batch and own-testing signals scores 10. Thus the claim that GMP alone necessarily equals GMP plus all those signals is false.

There is a real limitation: once a tier saturates, additional qualifying signals have no effect, and common product certifications saturate 15 quickly. Whether to use finer bands is a policy decision. QR/COA mentions and own testing must not be promoted into independent batch verification. The current source records often establish the former, not the latter.

The consumer reason “unknown, not penalized” is also imprecise: 6/15 still leaves nine points unavailable in a fixed /100 total. It means no explicit negative deduction, not no effect on the score.

### 6. Pillars overlap and different routes apply different extra charges

**Confirmed design overlap; not every overlap is automatically a bug.**

- Generic Formulation normalizes by its profile; multi adds dose disclosure; B-complex adds panel size/focus/disclosure; protein adds dose amount, amino disclosure, focus and cleanliness; fiber adds disclosure/focus/cleanliness; probiotic adds identity/potency disclosure. The same pillar therefore measures substantially different mixtures of quality and disclosure.
- Protein Formulation's “dose transparency” gives more credit at 10 and 20 g. A completely disclosed smaller dose earns less, although disclosure itself is complete.
- Generic Transparency's complete-label base plus disclosure bonus is 9/10 raw, or 13.5/15. Validated free-from/vegan claims supply the last points. Multi has 11/15 from identity plus individual-dose disclosure; free-from/vegan claims fill the remaining four. A fully transparent product can lack those attributes legitimately.
- Sugar/additives can lower Formulation and Safety/Hygiene. Protein also has reduced cleanliness credit and an extra artificial-sweetener penalty; fiber reduces cleanliness credit as well as applying shared penalties. Some identical facts therefore have different effective weights by route.
- The multi average is also exposed to accumulating small excipient penalties. Low-severity deductions are excluded from the shared Safety/Hygiene additive penalty, so it would be wrong to claim every filler is double-charged there.

Make every positive/negative fact's owner explicit and review any intentional secondary effect as part of the total weight. The six printed pillar maxima do not currently describe six independent budgets.

### 7. Generic is several scoring routes hidden under one name

Generic dispatch contains IQM, botanical, collagen, immune, joint, and sleep logic. Aggregate generic statistics conceal those differences.

- Generic Evidence often uses decisive primary-ingredient floors (11/14/17/18 raw), conditioned on source lineage, mass relevance, evidence class/direction and dose applicability. These are computed rubric rules, not evidence that the scorer is broken merely because values cluster. They also make high-quality singles competitive while omega/multi do not inherit the same floor.
- The primary mass threshold is half the largest active mass, not necessarily half of total formula mass. “Mass-dominant” should not be interpreted as majority ownership of the product without checking the calculation.
- Joint-support Evidence is capped at 14 raw and usually normalized against 18: **15.6/20**. An immune profile's cap of 17 instead gets a matching 17 denominator. These are unequal category policies that the generic route maximum of 100 conceals.
- B-complex Evidence caps generic contribution at 15 but normalizes against 14, so 14 already earns full public Evidence. Its current authority formula tops out at 12, contrary to stale configuration commentary describing an authority floor of 15.
- Multis and B-complex give full per-nutrient dose coverage at 50% RDA/AI, while generic DRI dose uses a 100% full-adequacy anchor. Their coverage credit also jumps from about .85 just below 50% to 1 at 50%. Category differences may be justified, but the rationale and public meaning need alignment.

### 8. Fiber routing and its adapter disagree about what counts as fiber

**Confirmed on a real product.** G.I. Integrity (184924) has zero canonical fiber rows in the classifier's feature vector. Its “G.I.” title nevertheless selects the fiber/digestive route through `_FIBER_TITLE_RE` in `scoring_v4/route_features.py:180`. A digestive route is not itself proof of a routing error, since enzymes also use this route. The downstream error is that `fiber_digestive_helpers.is_fiber_row` accepts any row with `category == "fiber"`, while the stricter classifier did not count that row as canonical fiber.

The stored N-Acetyl-D-Glucosamine row is canonicalized as `glucosamine` and tagged `fiber`. The adapter counts its 500 mg as 0.5 g of fiber, calls `fiber_effective_dose_v1`, and emits **2.4/20 Dose**. The other label actives include L-glutamine, gamma-oryzanol and aloe. The broad category tag is overriding the identity boundary; this should be corrected at the shared identity/category contract and verified at the adapter, not fixed by changing this product's score manually.

A second route-review case is Ipriflavone 200 mg (214586). A 1 g dietary-fiber declaration accounts for 83.3% of comparable mass, so `material_fiber_panel` selects the digestive route despite no fiber title or fiber taxonomy and one non-digestive claim-prominent active. The fiber-mass branch does not apply the claim-prominence guard used by the enzyme branch. It then scores Dose against 1 g of fiber (7.2/20). This is an intent-versus-mass routing concern requiring label review, not a confirmed clinical assessment of ipriflavone.

These cases demonstrate why one router is insufficient if the downstream profile adapters reconstruct ingredient roles with looser rules. Preserve a shared owner all the way through the rubric.

### 9. Incomplete review and inapplicable evidence must stay distinct

The code now distinguishes reviewed zero, applicability not established, no assessable active, and unfinished review. The artifact layer marks unfinished Evidence as a partial assessment. The inspected distributed database has 118 scored/partial records, not thousands of unidentified review gaps.

Do not infer “we have not reviewed it” from an Evidence score of zero. Conversely, a partial assessment is not a finished judgment of poor product quality. Keep assessment state separate from its numeric lower bound and verify actual app presentation before claiming that the UI misrepresents these cases. This audit did not inspect the running app.

## Every route: disposition

| Route | Diagnosis |
|---|---|
| Generic | High scores exist. Audit profile-specific caps, floor ownership, authority versus efficacy, and form-family standards; generic-wide max is insufficient. |
| Sports | High scores exist. Daily benchmark/per-serving inconsistency is a direct defect for daily-use actives; protein has extra disclosure/cleanliness/penalty paths. |
| Fiber/digestive | High scores exist. Fiber uses per-serving dose and step thresholds; enzymes fall back to generic dose/formulation and need separate subroute reporting. |
| B-complex | No demonstrated 97.4 hard ceiling. Family form ratings suppress Formulation; Evidence saturates easily; nutrient-count/focus/disclosure and dose policy differ from generic. |
| Multi/prenatal | No demonstrated 95.9 hard ceiling. Form-family denominator, low-end smoothing, excipient accumulation and claim-dependent Transparency explain substantial compression. |
| Omega | Confirmed non-prenatal Evidence ceiling and narrower focused-identity ceiling; class dose floor survives. Formulation's 12 raw reference is already aligned with its component maximum. |
| Probiotic | Observed 80 is not a universal maximum. Single-strain Dose/Evidence disadvantage, allocation disclosure and reviewed applicability are separate drivers. |

The classifier lives in `scoring_input_contract.py:4168`; `router.py` delegates to it. Priority includes probiotic identity with a declared-multi exception, prenatal panel handling, sports, validated omega, B-complex, multi, fiber/digestive, and taxonomy/fallback checks. Persisted native routes are checked against a freshly derived route before reuse. Keep this as the single classifier; correct the observed downstream fiber-identity disagreement and review the material-fiber intent guard. Fix destination rubrics without creating another classifier.

## Corrections to Claude's proposals

1. Summing the best observed pillar values from different products does not establish a jointly attainable ceiling or a mathematical upper bound on future products.
2. A best observed probiotic score of 80 does not mean no probiotic can exceed 80.
3. `WITHIN_TESTED_RANGE` and `NEAR_TESTED_RANGE` are not emitted by the current native dose classifier. It emits exact, outside, or unknown for reviewed discrete daily arms. Changing only those unused credit entries will not recover the proposed points. Tested arms at 1 and 10 billion do not, in the current contract, establish efficacy at 5 billion. A genuine reviewed continuous range would need a typed representation and supporting review before it could score.
4. Verification has additional post-violation values and real within-tier variation. A projected mean of 10 after changing bands was not demonstrated.
5. Omega normalization alone cannot fix its surviving dose floor and identity-count dependence.

## Recommended correction order

1. Repair the shared fiber identity/profile mismatch and review mass-versus-intent routing. Lock an invariant that equivalent daily exposures score equally where benchmarks are daily; repair sports/fiber exposure ownership and review minimum/midpoint/maximum policy.
2. Define a realistic, reviewable full-credit reference for each route **and subroute**, including one-strain probiotics, ordinary non-prenatal omega, a broad multi, B-complex, protein and digestive enzymes. All pillars must be achievable together with compatible facts; fabricated evidence or added ingredients do not count.
3. Correct probiotic single-strain arithmetic and multi/B form-family normalization. Preserve clinical identity/applicability gates and separate missing ratings from known poor forms.
4. Redesign omega Evidence around reviewed purpose and applicable support, then remove/justify the remaining dose-derived floor and set its denominator.
5. Reconcile duplicated rewards/penalties and claim-dependent Transparency. Refine Verification only with evidence of additional independent assurance.
6. Run frozen-input full-corpus before/after comparisons by route, subroute, score/assessment status, each pillar and real product. Review large upward **and downward** changes. Run required release gates before publication.

Success is not a higher mean. It is that an excellent product can earn an excellent score for its intended purpose, a poor product remains distinguishable, and the difference is explainable without changing labels, adding unnecessary ingredients, or overstating evidence.

## Replay measurements

All 15,421 input IDs were unique. Current scoring returned 15,244 scored, 70 safety-suppressed, and 107 not scored, with zero exceptions. These are current-scorer values on stored enriched inputs, not a newly published catalog.

| Route | Scored products | Highest observed total | Formulation max | Dose max | Evidence max | Transparency max | Verification max | Safety/Hygiene max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| b_complex | 146 | 97.1 | 17.5 | 19.9 | 20.0 | 15.0 | 15.0 | 10.0 |
| fiber_digestive | 411 | 97.8 | 20.0 | 20.0 | 20.0 | 15.0 | 15.0 | 10.0 |
| generic | 10466 | 100.0 | 20.0 | 20.0 | 20.0 | 15.0 | 15.0 | 10.0 |
| multi_or_prenatal | 2063 | 91.0 | 16.8 | 20.0 | 19.1 | 15.0 | 15.0 | 10.0 |
| omega | 713 | 90.4 | 20.0 | 20.0 | 15.0 | 15.0 | 15.0 | 10.0 |
| probiotic | 537 | 80.2 | 20.0 | 20.0 | 11.9 | 15.0 | 15.0 | 10.0 |
| sports | 908 | 98.7 | 20.0 | 20.0 | 20.0 | 15.0 | 15.0 | 10.0 |

These column maxima belong to different products and must not be added and labeled a reachable ceiling. The current result precedes final whole-number export rounding.

There are 402 matched scored products with at least one pillar or route difference versus the distributed database. Eleven change from probiotic to multi/prenatal. The stored enrichment and scorer are newer than the distributed output, so this is a freshness comparison, not a controlled attribution to configuration 1.13.0 alone. For example, Omega-3 Extra Strength EPA 1500 mg (259484) is 36 in the distributed database and 72.5 in this replay; One Daily Multivitamin plus Probiotics (315333) is 52 versus 75.6 and changes route. Those differences require release-state reconciliation before using a screenshot as evidence about today's code.

Measured causes:

- Multi/prenatal: 1,082 of 2,063 scored products have a form average below 9 raised to the neutral floor. Mean raw Formulation deductions are 3.83 points (about 5.47 public points before floor/clamp interactions). This is a substantial second reason for the low Formulation mean, alongside the denominator.
- Generic: primary-evidence floors determine 5,194 of 10,466 scored products. The joint Evidence cap binds on 93. There are 3,901 zero-Evidence products, dominated by applicability states rather than uncompleted review.
- Omega: 559 of 713 earn the disclosed-dose Evidence floor; 24 earn the prenatal bonus. That floor is a common production path, not dead configuration.
- Probiotic: 383 of 537 use the aggregate-CFU-only dose allowance; 85 use per-strain CFU disclosure. There are 132 single-strain products. Only four products receive positive dose-applicability Evidence credit. Counts of individual strain-assessment reasons are in drivers.json and must not be mistaken for product counts.
- Sports: mean raw Formulation deductions are 4.897; average Safety/Hygiene loss is 2.134. These totals describe the current rules, not a clinical endorsement of every deduction.

Seven targeted existing test files passed: 285 scoring/classification/applicability tests plus 34 sports/fiber tests, 319 total. The controlled probes expose rubric behavior that the existing suite currently accepts or does not cover. No full test suite or release gates were run because this investigation changes no scoring behavior.

Input ownership verification passed: all 58 replayed batch files are owned by their enrichment stage manifests, every manifest content hash matches, and no input changed between scoring and re-reading. The source fingerprints captured during the investigation were unchanged at the final check.

The exposure audit identifies 340 sports and 151 fiber/digestive products whose resolved daily serving range differs from exactly one serving. These 491 are an inspection queue, not a claimed number of wrong scores: some are already capped, have per-use benchmarks, or take generic fallback paths. Examples include BCAA 2:1:1 (252414), three servings daily, and Psyllium Husk 500 mg (252907), two servings daily. See exposure_audit.json for actual ingredient quantities and dose methods.
