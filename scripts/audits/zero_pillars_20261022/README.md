# Zero Dose / Evidence audit — October 22, 2026

All **5,512 products with a saved Dose0 or Evidence0** were audited against current owners.
The saved population is15,427 unique products (Dose0:523; Evidence0:5,094). This is a development
source audit, not a new clinical systematic review or a regenerated production catalog.
[Every product and its disposition](products.csv), [counts](summary.json),
[source checks](research.md), [capture receipts](receipts.json).

## Findings and fixes

**82 formerly zero Dose results now earn credit:74 were stale saved output;8 reflect this batch's
verified source/quantity corrections.** No original Evidence0 was converted into positive credit.
Lost ingredient identities and false source amounts were fixed without inventing efficacy points.

Existing owners were extended for printed botanical volumes, exact product-row corrections,
preparation-specific aliases, three reviewed blend-header names, and honest zero/incomplete-review
explanations. Broad forms expansion was rejected after carrier/source regressions; generic
carriers and plant sources remain protected. Blend totals never become individual amounts.

The eight source-fixed Dose0→positive cases are213826/251975/328014 (printed liquid amounts),
273629/33660/46729/64433/64821 (verified label units/values).78327 retains its verified iodine correction but now has the separate
acetylated-cystine identity hold. The13 product-correction keys
also include corroborated existing conversion, DV corrections, and explicit conflict holds.
Existing B6/niacin corrections on46729/66380 were preserved. Full per-entry receipts are in research.md.

Cystine was independently found while reviewing the zero-Evidence subjects:213846's structured
source falsely said alpha-glucan, and IQM falsely aliased cystine to cysteine. The label text/500mg
and chemical distinction are restored; unrelated UNII/alias removed. No unreviewed form rating is
invented.213846/328818/337851/297638 now correctly remain unscored.213846 also fails the existing
strict unresolved-active blob-export guard; that release block is deliberately retained and tested.

## Which remaining zeros are real, and which are unresolved?

The audited original set now contains5,427 products with at least one numerical zero,76 with
both pillars nonzero, and9 explicit unscored holds. One additional affected control297638 becomes
unscored; the CSV includes it, for5,513 rows. No new numerical zero occurs outside the original set.
There are ten unscored holds in the CSV overall.
Twenty other raw controls were already held on baseline main; they are not counted as new defects.

| Remaining Dose0 reason | Products |
| --- | ---: |
| Existing upper-reference policy withholds credit |327|
| No established EPA/DHA amount; oil/total-omega mass cannot substitute |58|
| Individual blend amounts undisclosed |14|
| Actual protein grams unknown; ingredient/powder mass cannot substitute |5|
| Applicable benchmark review unfinished |32|
| **Total Dose0** |**436**|

| Remaining Evidence0 state | Products |
| --- | ---: |
| Completed review: no qualifying applicable human benefit evidence |402|
| Completed review: no clear benefit established |300|
| Nutritional authority reviewed; no earned Evidence credit |41|
| Preparation/purpose/population match unestablished |3,317|
| Research recorded; applicability unestablished |293|
| No eligible individual efficacy subject under current owners |349|
| Clinical review unfinished |246|
| Identity/material clarification required |141|
| **Total Evidence0** |**5,089**|

Only the first743 completed-review cases support a finished zero-credit conclusion from existing
reviews. The other4,346 are withheld credit for eligibility/applicability/unfinished identity or
review work. **Do not describe them as proof that no research exists.** Likewise the32 unfinished
Dose benchmarks are not completed scientific conclusions. These limits are explicit in the CSV;
this batch does not declare those scientific reviews complete.

## Verification and measured impact

- Full current-main scorer census:15,427; frozen original zero-union raw replay:5,512; no missing
  raw labels or scorer errors. Latest source fixes overlaid only on exhaustively selected affected
  names/forms/quantity/zero-explanation classes plus controls. No production score was recomputed
  inside the reporting script; CSV columns project owner outputs and recorded reasons.
- Immutable1039-label mainb06f38597→candidate92fbaa33 full Clean/Enrich/Score/detail-blob pair:
  both exit0/source_unchanged/count1039.135 full-record movers;64 total-score changes including5
  scored→held statuses;14Dose/7Evidence/52Formulation changes (null pillars included),0route changes.
- After the final cystine data correction, independent six-label full-stage pair atb6aaa5f8:
  four legitimate held results; true cysteine201101/NAC329943 controls remain scored. A final seven-label
  follow-up at19755342c adds78327's distinct acetylated-cystine ambiguity: only that product changes,
  into a held result. Its source15mg and corrected iodine150mcg remain; exported quality stays
  withheld with the literal unresolved ingredient retained. The other six labels are unchanged. One input
  overlaps the1039 set, giving1,044 unique paired products. Combined68total/10status/18Dose/
  12Evidence/57Formulation changes including withheld pillars; no route changes. Original1039
  blob evidence is pre-cystine; the later213846 export refusal is explicit, not a successful blob.
- Independent recursive review: two Evidence increases are printed HMB in Ravage under its
  existing clinical owner. Four printed yohimbe restorations (1179/12800/19471 Ravage,14168 Rampant)
  activate existing high-risk findings. Prior stimulant signals remain. Profile-warning removals
  follow verified corrected exposures below existing thresholds; full warning records remain.
  Grape skin/safflower/Neumentix identity and form changes have source receipts. No unexplained
  clinical credit, source amount, status or lost-warning movement was accepted. Independent final
  six-label review also confirms unchanged enriched warning/safety/interaction payloads; the four
  cystine products lose borrowed identity credit while retaining their printed500/340/150/150mg.
  The final acetylated-cystine fix removes only its borrowed NAC alert group; all32 other ingredient
  alert groups and the safety gate are unchanged. No NAC clinical match existed before or after.
- Final failure-class/owner slice110passed; final NAC/source-group slice30passed; earlier
  completed owner slice621passed with one
  obsolete Ravage-header expectation, corrected against its original source and retested. New
  actual cystine/export guard plus consumer checks4passed. Independent47 targeted checks passed.
- Final33 raw scoring canaries pass.293924 fixture reanchor was separately reproduced on unchanged
  main before this batch: existing optional-use Dose policy, not a production change in this batch.
- Final local rung:546passed,24 declared optional-service skips; skip guard green.
- Prior runtimeb6aaa5f8: [39892624194 passed23,321 tests/192 declared skips, all four groups and skip guards](https://github.com/seancheick/PharmaGuide_Pipeline/actions/runs/39892624194).
  Final NAC follow-up19755342c: **[39894910595 passed23,323 tests/192 declared skips, all four groups and skip guards](https://github.com/seancheick/PharmaGuide_Pipeline/actions/runs/39894910595)**. Earlier39888610678/39891352694 failed,
  exposed the rejected broad approach and stale consumer assumptions, and are not passes.
  Source-equivalent report-only duplicate runs were cancelled, not counted as passes.


## Provenance and limits

The private immutable captures, raw PDFs, source inventory, full path deltas and test logs live in
`~/pg_quality/zero_pillars_20261022/`. Published receipts retain their input/output hashes and source
SHAs. The all-corpus form and literal-name scans bound the changed source classes; unchanged
subjects reuse the complete5,512 raw audit. Existing evidence triage's1,035 identity/linkage flags
are screening candidates, not1,035 proven bugs; contextual nutrients cannot borrow primary credit.

All114 saved stage fingerprints are stale:38Clean/38Enrich/38Score. Regeneration must begin atClean.
No manifests were restamped; no stored catalog, app bundle, Supabase data or release was changed.
Sean's existing final producer/catalog/app acceptance task remains open. The retained cystine
identity/export hold remains open; no complete releasable-catalog claim is made. No ledger exception or false ingredient rating was added to force it.

Owner: existing scoring modules, enhanced_normalizer::_expand_header_forms_for_processing,
constants::BLEND_HEADER_EXACT_NAMES, product_label_corrections and ingredient_quality_map.
Evidence: ownership matrix/glossary/caller search, frozen raw replay and original source panels.
Will NOT create: parallel scoring/normalization, clinical policy, numerical floors, evidence
registry, public status, guessed exposure, or an export bypass.
