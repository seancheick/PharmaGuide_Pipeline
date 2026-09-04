# Scoring applicability and Seed verification — 2026-09-03

## Boundary

This implements the approved correctness and evidence-applicability work. It does not calibrate weights, approve unreviewed clinical strains, publish a catalog, or modify the Flutter bundle. Scoring version is 4.3.2; the six-pillar configuration is unchanged.

Baseline source: `3f7fc754573ba8640833da98e4b4d731ce694dec`. Staged catalog: `2026.09.03.205958`, schema 2.4.0 / scoring 4.3.1, core SHA-256 `b3134964b70ad5b30043ac4fd786b2c77103e13322e8e4c01a167e2babc77e57`.

## Root-cause corrections

- Certification identity guards run before normalized equality/fuzzy ranking. Population, life stage, dosage form, strength, flavor-only overlap and missing named additions cannot borrow another SKU's certificate. Explicit reviewed line overrides remain supported.
- A cleaner-confirmed Supplement Facts parent nutrient with an explicit `(as/from source)` declaration can establish nutrient exposure without a Daily Value. Standalone compound masses remain unresolved; no guessed salt conversion was added.
- Clinical matches retain source-row references. Shared applicability checks prevent zinc cold-lozenge evidence from supporting an ordinary zinc capsule and AREDS combination evidence from becoming isolated vitamin-A credit. Dose lookup cannot borrow a higher amount from a differently formulated sibling.
- KSM-66's two cited trials enrolled 124 randomized participants, not 200. The record now describes the verified root extract, daily doses and stress/sleep outcomes, without unsupported strength/libido/cognition claims. Known low doses are graded, not silently dropped.
- Native probiotic research requires the current reviewed registry ID **and** the matching strain identity. One exact identity predicate guards enrichment output and scoring, so a rejected identity cannot keep an affirmative app badge. Species-only or other-strain rows cannot inherit a strain-specific assessment. Formula-level/pending records cannot provide independent-strain clinical credit. Punctuation variants and individually verified aliases are preserved; fuzzy scientific identity expansion is not allowed.
- Structured strain forms belong to their own label row. Nature's Way 327965's three HOWARU rows require their distinct scientific forms to resolve; their shared marketing name cannot identify the owner. Source references are rechecked by consumers, legacy name fallback must have one exact owner, and clinical identity cannot double-count label CFU disclosure. This was a pre-existing omitted-form path, not a demonstrated new regression.
- Readiness is linked to the actual ingredient row, not any researched strain elsewhere in the product. Confidence and score consume the same accepted evidence. Incomplete curation is still distinct from evidence of poor quality.
- Disclosure copy uses the actual label disclosure facts. Primary-ingredient evidence is not described as a trial of the finished multi-ingredient formula.
- The evidence-reachability audit replays both ingredient evidence and the later formula-evidence stage. It re-proves Seed's formula rather than trusting a stamp, recognizes source-row provenance, and detects a changed formula dose as stale evidence.

## Seed: grow the assessment, not the score target

The reviewed formula contract requires the complete 24-strain composition, exact membership and AFU amount in each of four blends, 400 mg MAPP pomegranate extract with >40% polyphenols, the capsule formulation and two-capsule maintenance serving. It is shared by enrichment, readiness, dose, formulation, transparency, evidence, confidence and export.

No AFU-to-CFU conversion or individual strain quantity is invented. The formula trial does not approve any pending individual-strain badge. Existing component budgets recognize native potency and exact studied composition; weights and tier boundaries are unchanged. Missing individual strain amounts remain visible. Confidence stays moderate given study limitations.

Primary-source review and exact citations are in [research.md](research.md). The six-week symptom trial and smaller mechanistic trial do not establish broad skin, cardiovascular, pregnancy, pediatric or disease-treatment benefits.

## Verification method

Certification inventory: all registry programs discovered across 15,415 products, not just previously emitted pairs. Of 1,554 formerly point-eligible resolutions, 36 no longer qualify: seven population conflicts, 16 fruit powders matched to flavored creatine, and 13 missing named additions such as `+ DHA`. One newly found exact listing qualifies: Thorne Zinc Picolinate 30 mg (291803), independently checked in the official NSF listing on September 3, 2026. Net: 1,519 point-eligible resolutions. There are no record remaps or changes to the 367 reviewed line overrides. All 15 Apple powders and both tested plain CBD 10 mg products remain uncredited by the unrelated listings. The named-addition cases are reviewable identity gaps, not proof that the products lack certification.

Nutrient exposure inventory: 113,498 top-level label rows. Seven rows change exposure authority, all on the submitted Ritual label. D, magnesium and zinc are no longer falsely missing; iron remains absent and boron gains no invented RDA.

Native-strain old-artifact inventory: 1,214 emitted clinical rows, including 1,043 formerly signed-independent rows. The initial exact-name gate accepted 638. Individual primary-source review added 26 aliases to 16 existing registry entries, restoring 119 valid rows (757 accepted) without changing thresholds, efficacy classifications or clinician sign-off. Ignoring punctuation also preserves 52 matches. The remaining 286 consist of 284 generic/different-code rows and two unresolved `L. reuteri 1E1` rows (332922 and 333915), for which equivalence to DSM 17938 was not established. Major erroneous classes include species-only acidophilus→NCFM, CUL60/21→NCFM, species-only coagulans→MTCC5856, and cerevisiae/yeast/extract→boulardii. These are comparisons of old emitted rows, not the final producer output counts; the final corpus replay recollects probiotic data and checks the shared producer predicate too. [Exact alias source ledger](../probiotic_identity_aliases_2026_09_03/research.md).

Structured-form inventory: all 58 manifest-owned enriched files / 15,415 products; all 11 exact direct strain owners with forms remain accepted. The single generic species descriptors on Jarrow 307727/307728 and Thorne 337852 do not erase their explicit strain names. No observed direct owner has multiple form records; synthetic tests require conflicting strain forms to fail, while redundant names and same-species descriptors retain one identity and one dose. Nature's Way 327965's three separate HOWARU owners resolve from their own full scientific forms without assigning them the undisclosed share of the 100-billion-CFU blend.

Structured group-code compatibility is preserved as well: an explicit same-row `ingredientGroup` code must complete a compatible species into an exact current registry identity and carry source ownership. Notes, a genus alone, generic taxonomy and conflicting codes cannot substitute. The full inventory found 35 already-resolved typed candidates, zero missed/newly eligible candidates and two correctly rejected owners (264610 and 337873); the current corpus impact is unchanged by this compatibility correction. Seed's pending records remain formula-only, not independently approved strains.

The reproducible `audit_corpus.py` reads only stage-manifest-owned cleaned, enriched and scored products. It compares the production scorer across the entire corpus, recollects the changed evidence/certification/probiotic producer surfaces using the same ingredient-quality input as operational enrichment, and fully re-enriches a deterministic brand/module-stratified sample plus every submitted product and known certification/native-strain canary. It hashes inputs, code and reference data before/after. It never reconstructs from consumer blobs or overwrites pipeline outputs.

The complete machine report is local at `reports/scoring_applicability_2026_09_03/corpus_impact.json`. It is intentionally not committed as a large generated fixture. The original exploratory replay omitted the ingredient-quality argument on the audit-only evidence recollection call; that caused artificial Pycnogenol/Testofen/collagen declines. That exploratory result is superseded. The final report must be `complete: true`; interrupted/partial reports are not evidence of completion.

## Final frozen corpus result

The final replay completed in 294.5 seconds: **15,415 products, 215 full re-enrichment canaries, zero input/code/reference hash drift**. Report SHA-256: `5bd6df71f464f9e6bc4514f9a9ba90eb4518ef589a6f957fbf9553675ea30134`. All prior exploratory/interrupted reports are superseded.

- **1,677 numeric-score changes:** 1,636 decreases, 40 increases among previously scored products, plus Seed newly scored. The 9,496 changed report records also include explanations, provenance and age/recency metadata; they are not 9,496 changed scores.
- **Zero route changes.** 341 tier changes and 102 verdict changes: 98 SAFE→POOR, three POOR→SAFE from recovered HOWARU identities, and Seed NOT_SCORED→SAFE. No BLOCKED/UNSAFE verdict changes.
- **Eligibility:** 15,283 remain scored, Seed becomes scored, 54 remain safety-suppressed, and 77 remain not scored. These are candidate scorer results, not a published catalog count.
- **Confidence:** only two existing products change moderate→low (270966 and 335195, lost SKU certification support); Seed gains moderate confidence. Registry absence is not reclassified as evidence of ineffectiveness.
- **4,292 inapplicable ingredient-evidence matches rejected:** 1,976 combination-only references, 2,294 delivery mismatches, 15 below applicable dose, seven wrong forms. Nutritional DRI authority remains separate from therapeutic study credit.

| Product | Baseline → candidate | Interpretation |
|---|---|---|
| Seed DS-01 | not scored → **69.1**, SAFE, moderate confidence | Exact complete formula and native AFU assessment; limited independent symptom-trial confirmation. |
| Ritual Essential for Men 18+ | 81.6 → **73.5**, SAFE | Correct nutrient exposure, removal of a mismatched certification and inapplicable research credit. |
| Youtheory Ashwagandha + GABA | 77.4 → **77.4**, SAFE | Existing primary-ingredient credit retained; explanation no longer implies a trial of the whole formula. |
| Nature's Way Fortify 100 Billion (327965) | 76.0 → **76.7**, SAFE | Three source-owned HOWARU forms recovered; disclosed total CFU and individual-dose uncertainty unchanged. |
| Jarrow 307727 / 307728 | 66.4 → **66.4**, SAFE | Exact strain identity survives its generic species descriptor. |
| Thorne Bacillus Coagulans (337852) | 68.8 → **68.8**, SAFE | Exact strain identity survives its generic species descriptor. |
| Garden of Life 5-Day Max Care (174659) | 73.6 → **40.9**, POOR | Removes borrowed strain/formula research, not a new toxicity finding or proof of ineffectiveness. |

Reviewed change classes include certification conflicts; written-out gram/milligram units and source-owned dose lookup; zinc/AREDS/KSM-66 applicability; false native-strain transfers; exact structured-form recoveries; and explanation-only changes. All 40 increases were inspected by pillar and evidence/strain provenance. The largest increase is the three Nature's Way Women's Probiotic Pearls records (41.5→56.9), now resolving their own HOWARU/NCFM form. Existing primary-ingredient rules and component budgets are unchanged; this is not a weight-calibration endorsement.

Seed's six pillars are formulation 20, dose 13.6, evidence 6.8, transparency 9.7, verification 9, safety/hygiene 10. No individual strain dose, clinical approval or AFU/CFU equivalence was manufactured to obtain that total.

## Test and release status

- Focused certification and adjacent tests: 177 passed.
- Final structured-form/native/AFU/group-code compatibility slice: 290 passed; independent final group-code/structured-form review: 71 passed, no concrete blocker found. The prior descriptor-only independent review passed 31 tests.
- Parent reachability/AFU/structured-form slice: 47 passed before the last descriptor-only extension. Readiness: 41 passed, including real-owner support and IQD-only/no-owner non-support.
- Clinical reference audit earlier in this pass: 202 entries, 447 distinct PMIDs, 462 claims; strict gate passed with zero identifier-not-found, topic-mismatch or drift failures. Two previously reviewed suspicion flags remain recorded by that audit; this is not a claim that all outstanding clinical curation is complete. No citation IDs changed afterward.
- The earlier integrated fast run exposed three compatibility failures: two existing structured group-code fixtures needed the exact source-owned producer path preserved, and a readiness fixture lacked its actual label owner. The production compatibility path and realistic fixtures are corrected; the 290-test slice and separate 23-test formula/readiness file pass.
- **Final `scripts/test.sh fast`: 12,773 passed, 42 skipped, zero failures in 330.25 seconds**, run after the final corpus replay. Skips include missing historical build/canary paths and intentional metadata exceptions; they are not counted as verified behavior. All corpus input/code/reference hashes were checked again afterward and still match. The sole scoring configuration remains byte-identical to baseline. `git diff --check` passed.
- The old staged catalog **correctly fails** `audit_source_of_truth_contract.py freshness` with `FRESHNESS_ENRICHMENT_REFERENCE_MISMATCH` across all 38 dataset manifests. Release/full artifact gates are intentionally pending the operator's fresh operational rebuild. Neither a stale-artifact gate nor this impact replay substitutes for release verification.

## Local implementation commits

- `50651e5b` — certification identity and regression coverage.
- `4fa4ece8` — nutrient exposure, shared clinical applicability, source-owned probiotic identities, exact Seed formula assessment, source ledgers and regression coverage.
- The final audit/checklist commit packages the reproducible corpus replay and this verification record. Work remains on `codex/scoring-applicability-and-seed`; no merge, push, catalog publication or app import was performed in this pass.

## Release handoff

After code verification, run one operational enrichment/scoring refresh and snapshot, without publication:

```bash
bash batch_run_all_datasets.sh --stages enrich,score --skip-release
```

This runner refreshes the auxiliary Product Submissions dataset before building the snapshot. Do not substitute score-only: ingredient-dose assessment and reference-data changes need enrichment. No raw DSLD redownload or cleaner rerun is required for this change.

Then run the release gates against the fresh output before publishing. A release gate against the old 4.3.1 artifacts must fail freshness; do not bypass it. The read-only impact replay is not a release artifact or a substitute for that gate.

Next work remains the Phase 3 label-extraction benchmark. Weight calibration follows it and a blinded reviewer benchmark, not a desired score distribution. Unreviewed evidence entries, marketing-name aliases and pending strain reviews are not declared clinically complete by this change.
