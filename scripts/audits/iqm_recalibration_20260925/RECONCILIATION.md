# IQM reconciliation and calibration — 2026-09-25

Status: read-only first deliverable. No curated values changed at this checkpoint.

Owner: `scripts/data/ingredient_quality_map.json` (authored values), `scripts/scoring_reference_resolver.py::iqm_reference_entry` (main lookup), v41 `unknown_form_quality` / `effective_form_bio` (shared form interpretation), `scripts/iqm_form_evidence.py::validate_iqm_form_evidence` (promotion governance). Evidence: `rg -n 'ingredient_quality|IQM' scripts/contracts/source_of_truth_matrix.json scripts/GLOSSARY.md`; source inspection and committed diff.
Will NOT create: another form table, scoring policy copy, new status, product whitelist, or omega tier implementation.

## Snapshot and reproducibility

The exact fetched main and v41 commits, reference resolver SHA256, 96 enriched file hashes, every parent/category distribution, all parents lacking an eligible 15, form-by-form differences, floor deviations/overrides, fixture findings, and ranked product exposure are in `census.json`. `census.py` is read-only and records its assumptions. `resolver.diff` is the exact committed main→v41 resolver diff. The v41 working copy differs additionally in one explanatory comment about non-delivering forms; no uncommitted code was copied.

Corpus: 15,422 unique product IDs, 96 existing enriched files, zero parse errors. These are exposure counts, **not** fresh re-enrichment or measured score deltas; product identities may reflect old aliases. Counts overlap by family. The audit did not run a pipeline, export, or release.

Main has IQM schema 5.5.6; v41 has 5.6.0. Main retains form `score` and `natural`, natural-bonus metadata, duplicate form selection in enrichment/scoring, and a fallback that can assign a named form when none was disclosed. v41 removes those fields, adds `scoring_system.unknown_form`, centralizes interpretation, and distinguishes unmapped disclosure using existing `form_match_status` plus curation reasons. Typed `parent_relationship` excludes nonfunctional/non-delivering and wrong-identity records from the floor. Source preparations are excluded by the existing alias scope.

## Reconciliation ledger

| Commit | Reviewed scope | Integration disposition |
|---|---|---|
| `aba89280`, `47d17d4b` | Creatine anhydrous/monohydrate and generic aliases; cleaner precedence | Review chemical receipts and cleaner tests together; not a JSON-only copy. |
| `a455c655`, `e16c782e`, `0e55886b`, `ddcb353e`, `81139b24`, `9acff28e`, `13c47521`, `52c233a5`, `4e24ba05`, `097a65f0` | Generic B12, D, C, biotin, B1, B6, niacin, mixture/trace aliases | Small identity commits are candidates for individual replay after live identity verification; do not claim automatically safe from commit titles. |
| `9224cd21`, `e00bcdc9`, `c20a80b5` | Remaining A1/A7 identity aliases, vitamin A fish-liver source, black-seed oil | Review exact source/preparation ownership; mixed enrichment commit requires selective integration. |
| `a9801685` | bio-only fallback selection and unresolved shares | Runtime prerequisite for field retirement; compare caller behavior on main. |
| `c3afa98b` | Removes all form `score`/`natural`; runtime, export contract and tests | Mechanically score-neutral on its original predecessor according to its receipt, not yet independently established on main. Minimum integration crosses enrichment/export field projections, but no other pillar is needed. |
| `56314f5c` | `scoring_system.unknown_form`, shared resolver; identity-neutral derived default | Dependent runtime migration. Do not cherry-pick alone after copying only JSON. |
| `83f75fe9` | Disclosed-unmapped hold; 152 unspecified score changes; 15 overrides; exclusions and aliases | **Not safe wholesale:** mixes calibration, matcher, gates and export. Review family values and override provenance individually. |
| `a7065751` | Typed `parent_relationship`, curation queue, identity cases, integrity loop repair | Superseded in part by `099f4b5b`; its temporary statuses must not be reintroduced. |
| `099f4b5b` | Restores existing statuses, IQM component relationships, eleuthero/CurcuWIN/ALCAR identity, nutrient-delivery boundary | Contains Dose/Evidence changes owned by Claude. Coordinate this boundary; do not port those pillars here. |

No whole mixed commit is certified safe to cherry-pick onto current main yet. Safe strategy: preserve current main; integrate retirement and shared form interpretation as a reviewed dependency slice, then one evidence-reviewed family at a time. Keep consumer projections paired with producer removal. Compare main and v41 again before integration because Claude is active. Never copy the entire v41 IQM JSON. Final delivery should be new atomic commits suitable for main; avoid replaying duplicate v41 commits if the integrator has already adopted them.

## Calibration census

Under v41's typed eligibility interpretation, 638/652 main parents and 639/653 v41 parents have no eligible ordinary form at 15 (includes parents with no eligible named form). This is a review queue, not authorization to promote every maximum. Parent-relative ranking cannot manufacture evidence for pending entries. `census.json` lists **every** parent and the score histogram and maximum, rather than hiding the long tail in a summary.

Main has 187 authored unspecified values different from the proposed floor: 153 above and 34 below. Main has no structured overrides. v41 has 50 deviations: 15 documented above-floor overrides and 35 below-floor values. The resolver deliberately retains below-floor values, so v41 does **not** implement the newly specified exact floor in those 35 cases. Some are specific clinical locks (mushrooms/botanicals); these must be reconciled with their evidence, not silently raised by a generic floor test. All deviation records and override author/date/rationale are in the census.

The current evidence validator permits historical Excellent entries on a frozen backlog; it does not license new/increased 12–15 values merely because the parent lacks 15. New promoted forms require reviewed axis, moderate/strong applicable evidence, explicit score support, structured references and source-verification attribution. The backlog must never be expanded to absorb this recalibration.

## Pareto-first exposure

| Parent | Existing products |
|---|---:|
| Vitamin C | 2,903 |
| Calcium | 2,608 |
| Vitamin D | 2,552 |
| B12 | 2,324 |
| Zinc | 2,311 |
| B6 | 2,235 |
| Vitamin E | 2,094 |
| Folate | 2,077 |
| Niacin | 2,011 |
| Biotin | 1,959 |
| Magnesium | 1,935 |
| Pantothenate | 1,921 |

These vitamin/mineral families dominate multi/prenatal/B-complex exposure. Full parent/form counts (including fish oil, EPA/DHA, algae/krill sources) are in the ranked census. Review B12, B6, E and folate first because the evidence contradictions are independently reproducible; then assess the remaining high-exposure parents individually.

## Independently checked contradictions

Primary guidance was read live on 2026-09-25:

- **B12:** scores 8 (methyl/adenosyl/hydroxo), 10 (cyano), 11/9 (sublingual methyl/cyano). Sublingual absorption fields claim intrinsic-factor bypass and 10–40% absorption, while the same methyl-sublingual notes reject that advantage. [NIH ODS B12](https://ods.od.nih.gov/factsheets/VitaminB12-HealthProfessional/) reports no evidence of supplement-form absorption differences and no demonstrated oral/sublingual efficacy difference. Dose-dependent fractional absorption is not a parent-relative quality ranking. Existing Dr Pham C2 exact-score locks need explicit reconciliation; do not mislabel revised numerical policy as new clinical superiority. Stored exposure: cyano 1,765, methyl 555, adenosyl 20, hydroxo 9 products (overlap possible).
- **Folate:** folic acid 6 despite ~85% absorption with food, food folate 9, yeast folate 10. [NIH ODS Folate](https://ods.od.nih.gov/factsheets/Folate-HealthProfessional/) supports high folic-acid bioavailability and equal-or-greater 5-MTHF bioavailability. The record conflates unmodified portal folate/UMFA with poor absorption. UMFA observation alone does not justify a bioavailability penalty. Exact 5-MTHF salt evidence and existing safety/DFE handling must remain distinct.
- **Vitamin E:** free d-alpha 12, acetate/succinate 10, despite notes acknowledging hydrolysis. [NIH ODS Vitamin E](https://ods.od.nih.gov/factsheets/VitaminE-HealthProfessional/) supports comparable ester absorption. Natural/all-rac activity conversion already belongs to dose normalization; a second activity penalty requires a separate justified quality rationale. Do not assume tocotrienols or mixed tocopherols are equivalent alpha-tocopherol nutrition.
- **B6:** P5P/pyridoxamine 10, pyridoxine HCl 9 and glutamate 8, while records describe class-equivalent absorption. [NIH ODS B6](https://ods.od.nih.gov/factsheets/VitaminB6-HealthProfessional/) finds no substantial supplement-form absorption difference. Clinical indications and toxicity are separate from a form absorption premium.
- Other internal review candidates: B1 mononitrate 10 versus HCl 9 with the same dose-dependent absorption description; B5 calcium salt 12 versus sodium 10 with notes asserting comparable absorption; yeast biotin 9 versus d-biotin 12 with a same-molecule/class-equivalence statement. These are flags, not completed primary-source adjudications.

## Pending/stub guard

46 parents carry stub/pending/needs-review/draft/provisional review states in the census. Main's named-form match builder caps stub/pending/needs_review at 10; v41 centralizes that cap. This prevents premium 12–15 credit through that path, **not all production credit**. Stub parents still carry positive values (for example acai 5, cat's claw 8, keratin 7), and at least these appear in stored products. Draft/provisional are accepted integrity vocabulary but are not in the cap set. Therefore the stronger assertion “unreviewed parents cannot receive unjustified production credit” is **not established**. A cap is not evidence validation. Do not promote these parents while calibrating the reviewed families; audit all entry paths before asserting a complete guard.

## Archetype fixtures and omega boundary

The ideal-fixture audit reports 50 rows needing IQM/form or dosage-importance review. Missing exact keys are distinguished from numeric contradictions; an alias may be valid and needs the real resolver, not string-only adjudication. The prenatal fixture assigns 13 to all 18 rows and omits dosage_importance on all 18. Definitive contradictions include riboflavin-5-phosphate 13 vs IQM 10, niacinamide 13 vs 11, methylcobalamin 13 vs 8. Vitamin E, K1, B5, B6, biotin, iodine and choline rows also exceed their parent's current maximum. These synthetic totals cannot establish attainable IQM-based production performance. Fix fixtures through the production enrichment owner after IQM calibration, then re-freeze measured outputs; never raise IQM to preserve fixture totals.

Omega's independent form regex/tier owner is `scripts/scoring_v4/modules/omega_formulation.py` (`form_tier_table`, textual form detection). That broader scorer boundary belongs to Claude. IQM calibration alone cannot prove omega Formulation parity; no omega refactor is included here.

## Verification / remaining work

Census completed without parse errors and includes hashed inputs; primary guidance checked live. Clinical identifier verification and regression/impact work follow this first report. No pytest needed for this report-only checkpoint. No assertion of release readiness, fresh-corpus effect, or completed calibration is made.

## Field-retirement checkpoint

Reconciled the mechanical scope of `c3afa98b`, plus retirement-only test cleanup from `56314f5c`, against main. No v41 JSON was copied. A structural equality check proved all 1,444 forms unchanged except removal of exactly 2,888 `score`/`natural` keys. The 652 main parents and all bio_scores/aliases/identifiers/evidence remain unchanged. Main's fallback now reads bio_score where it previously consulted retired score; the broader unknown/disclosed-unmapped migration remains separate.

- Red regression: 2 intended failures (2,888 retired keys; `bio_score_of({'score':12})` incorrectly returns 12).
- Fast checkpoint: **15,983 passed, 172 skipped**, 2 pre-existing invalid-escape warnings, 340.85 seconds. Skips include absent local corpora/services/release blobs; this does not establish release readiness.
- Follow-up focused retirement/schema/evidence suite after cleanup: **100 passed**.
- Form-evidence audit: passed. Database integrity: **zero findings**.
- Four real raw-label comparisons through cleaner → `enrich_product` → production scorer: identical form readings, pillars, totals, statuses and safety verdicts. `retirement_probe.py` loads main's changed modules through an in-process source overlay and main's IQM, without creating another worktree. Before/after outputs are committed.
- One stored-input corpus comparison is in progress. Its completion will be recorded separately; no claim of full re-enrichment neutrality is made from the four-label cohort.

Numerical calibration is waiting on the explicit conflict between the new relative scale/floor and existing Dr Pham C2 / other audit locks. The user was asked whether reviewed recalibration may replace those numerical locks while retaining clinical/safety findings. The exact constraints are in AGENTS.md (specific clinical lock beats generic floor) and the `/data-fix` workflow (preserve explicit clinician-review holds).

## B12 absorption-only correction

Owner: IQM `vitamin_b12_cobalamin.forms` — evidence: direct record inspection, NIH ODS live guidance, and repository PubMed/GSRS/PubChem clients recorded in `research.md`, `b12_pubmed.json`, `b12_live_identity.json`. Will NOT create a new form or inferred absorption estimate.

Both sublingual records had unsupported fractions: methyl 0.20 (0.10–0.40), cyano 0.15 (0.10–0.30). They now carry the existing null/unknown representation, with matching absorption prose and notes. The cited 30-person trial measured serum response and found no significant route difference; it did not measure those fractions. Scores, aliases, identifiers and reviewed consumer identity descriptions are unchanged. No claim of clinician approval is added.

Regression first: 2 intended failures on the fabricated point estimates. After correction: **171 passed** (B12 integrity, schema, vitamin/mineral, existing Dr Pham locks, and structured evidence). Stored corpus exposure to these exact two matched form IDs: **0 products**; this does not prove no raw labels mention sublingual delivery. The wider B12 parent has 2,324 products and remains a calibration priority. This correction changes clinical metadata, not bio_score; fresh enrichment is needed for any newly matched sublingual row to receive the corrected copy. Oral sibling numerical/copy issues are recorded in the evidence receipt and remain pending the score-lock decision.

## IQM numeric guard correction

Owner: `scripts/db_integrity_sanity_check.py::check_iqm` — evidence: injected -1, 16, True, NaN and infinity into a real parent copy; all five incorrectly passed the bio_score check. Will NOT create another validator or score clamp. The existing integrity owner now rejects boolean/non-finite/out-of-range values and accepts both 0 and 15. The schema regression's obsolete lower bound of 1 is aligned to the authorized 0–15 contract. This changes no data or runtime score. Red: **5 failed, 2 passed**; green schema/retirement suite: **63 passed**; real database integrity: **zero findings**.
