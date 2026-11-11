# Interaction audit, Stage 1 baseline (2026-11-11)

Plan: interaction audit rev 2, approved by Sean on 2026-11-11. This stage changes no behaviour.

## Pins

`baseline.json` holds pipeline a01269d6b, app a094763d, interaction DB 1.0.15 (154 profile rules) and
blob build 2026.11.02.191010 (15,447 blobs). The sample is 4,000 blobs (seed 1, sorted paths) and its
ids are in `sample_ids.json`. Rerun with `baseline.py`; its warning shares estimate the app's gates and
are used only to rank rules for review.

## Evidence ledger

| # | Finding | Kind | Proof |
|---|---|---|---|
| 1 | 79 drug-class sub-rules gate on ids that no medication class reaches: hypoglycemics_* 54, thyroid_medications 11, cardiac_glycosides 4, cyp3a4 3, cyp2d6 3, antiarrhythmics 2, anticholinergics 2. The audit's earlier 81 missed two SSRI sub-rules rescued by an authored `ssris` alias in `drug_classes_any`, which the app matches on | source data | `test_interaction_baseline_reproductions.py::test_every_rule_drug_class_is_reachable…` (xfail), count pinned by `test_unreachable_rule_count_is_the_audited_baseline` |
| 2 | Digoxin (RxCUI 3407) is in no medication class. Live RxNav gives ATC "Digitalis glycosides", so the app stores `digitalis_glycosides`, and the senna, cascara, aloe ferox and ginseng rules never fire | source data | `test_digoxin_reaches_the_cardiac_glycoside_rules` (xfail); app `digoxin resolves to the cardiac_glycosides rule class` (RED) |
| 3 | The CBD rule targets anticonvulsants and sedatives; clobazam (21241) is only in benzodiazepines and valproic acid (11118) only in valproate | source data | `test_cbd_antiseizure_rule_reaches_clobazam_and_valproate` (xfail ×2) |
| 4 | New finding: venlafaxine (39786) and duloxetine (72625) are in no class. The St. John's wort contraindication for SSRI/SNRI therefore never reaches an SNRI user, and no curated pair covers SNRIs | source data | `test_st_johns_wort_antidepressant_rule_reaches_snris` (xfail ×2); `grep -il venlafaxine curated_interactions/*` finds none |
| 5 | Held timing intervals are still published: the iron–calcium 2 h and levothyroxine–magnesium 4 h intervals, held for `interval_not_supported_by_cited_source`, ship in the management text of curated pairs | source data | `test_held_timing_interval_is_not_published_elsewhere` (xfail ×2) |
| 6 | A drug-class-only rule warning that the product page shows never reaches the Stack (`hasConditionScope` skip) | runtime | app `a drug-class-only rule warning … also reaches the Stack` (RED) |
| 7 | Digoxin + senna: no warning on the product page and none in the saved Stack (in both add orders), and the Stack reports its checks as complete. The result is a silent all-clear | runtime | app `digoxin + senna` group (RED ×3); `identityIncomplete` is set only when the class list is empty |

The app tests were run with their skip removed and seen to fail (5 failures, controls passing), then
marked `skip` so CI stays green. The pipeline tests are `xfail(strict=True)`.

## Not covered in this stage

- The app reproduction of a severity conflict (ginkgo + warfarin) moves to Stage 3, where conflicts are
  reconciled. The conflict list from the audit (18 pairs) is not yet regenerated here.
- No simulator run; the four flows are exercised through the providers that the screens use.
