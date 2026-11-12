# Batch 7 timing — source and implementation receipt (2026-11-12)

Owner: `scripts/data/timing_rules.json` and `timing_rules_rejected.json`; runtime projection:
`scripts/sync_flutter_reference_data.py::publishable_timing_rules`. Evidence: `rg timing` in the source-of-truth
matrix/glossary; `rg 'ingredient.*Rxcui|rxcui'` in Flutter's `timing_evaluation_service.dart`.
Will NOT create: a relation type, registry, severity, scoring algorithm or standalone hydration scheduler.

Authority: `DR_PHAM_REVIEW_20261111.md`, sections C, F10 and G3. Clinical decisions belong to Dr. Pham;
source rechecks, identity verification and wording below are Codex agent work, not a new clinician review.
Changes are behavioral data (publication and medication scope). No corpus or release was run.

## Per-entry results

- `timing_thyroid_med_magnesium_separate`: publish the existing four-hour D27 precaution. The
  [ThyroMag full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC12605969/) and live API abstract for PMID 41221788
  describe 15 healthy adults, simultaneous dosing, 12% lower thyroxine exposure with aspartate and a
  nonsignificant 7% reduction with citrate. No separated-dose interval was tested. The
  [SYNTHROID label](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=1e11ad30-1041-4520-10b0-8f9d30d30fcc)
  names magnesium hydroxide antacids in 7.1; section 17 supplies antacid spacing. The mechanism now identifies
  four hours as extrapolated precaution; the nonsignificant result is explicit. Live PMID 10193669 matches
  antacid/laxative case reports and in-vitro work, not a timed magnesium trial. Old label URL replaced by the
  content-read current SYNTHROID label. Status verified reflects D27 plus the recorded G3 decision.
- `timing_psyllium_water_med_spacing`: retain ID, narrow to digoxin RxCUI 3407 and binary three-hour separation.
  [MedlinePlus](https://medlineplus.gov/druginfo/meds/a601104.html) names digoxin, salicylates and nitrofurantoin,
  not all medicines. Live API PMID 3038494 describes 30 geriatric inpatients, with 14 in the ispaghula group;
  four weeks of ispaghula did not change steady-state digoxin levels. Retain that negative result explicitly;
  do not use it as proof of reduced absorption or of the interval.
- `timing_psyllium_salicylates_separate`: same named MedlinePlus precaution, exact RxCUIs for aspirin 1191,
  salsalate 36108, choline magnesium trisalicylate 215799, magnesium salicylate 52364, sodium salicylate 9907.
  This applies the named class instruction to those identities; it is not a study of each medicine.
- `timing_psyllium_nitrofurantoin_separate`: same precaution, exact RxCUI 7454. No broad antibiotic class.
- `timing_calcium_vitamin_d_together`: removed from runtime source to existing rejection ledger. Live
  [PMID 21118827](https://pubmed.ncbi.nlm.nih.gov/21118827/) is dietary reference intake guidance, not evidence
  for obligatory simultaneous swallowing. Preserve original claim/fingerprint; no timing bonus.
- `timing_quercetin_vitamin_c_together`: removed to rejection ledger. The live
  [LPI flavonoid reference](https://lpi.oregonstate.edu/mic/dietary-factors/phytochemicals/flavonoids) discusses
  bioavailability, metabolites and in-vitro antioxidant context; it supplies no supported simultaneous-vitamin-C
  quercetin absorption instruction. Preserve original claim/fingerprint; no timing bonus.

All eight RxCUIs (including levothyroxine 10582) resolved by exact-name lookup and `/properties.json`
on `https://rxnav.nlm.nih.gov/REST/` on 2026-11-12; names matched. Sodium salicylate is PIN; others are IN.
PMIDs 3038494, 41221788, 10193669 were independently content-read via the Europe PMC API; the repository's
PubMed content verifier also fetched them live: 3 match, 0 mismatch, 0 unresolved.

## Consumer limits and retained holds

Psyllium water guidance stays in each scoped card: at least 8 oz liquid, powder/granules mixed just before use.
Other medicines follow their own product label; no universal three-hour or generic two-hour interval is shipped.
A standalone liquid card has no honest current timing relation, so no new type or placeholder was introduced.

A fail-first app probe confirmed that a selected injected digoxin product plus its generic ingredient incorrectly
received the oral timing card. Sean explicitly authorized the optional exclusion field and app correction on
2026-11-12 ("Add the exclusion field and fix the app"). Schema 6.1.0 now carries optional
`excluded_member_rxcuis`, reusing the class-map name for exact medication product exclusions. The existing
publishable projection preserves it verbatim; the app parses RxCUI strings and excludes that rule for that
medication before matching its ingredient aliases. Missing field preserves prior matching, malformed lists
throw, and one excluded medication does not suppress another oral/unknown-route medication.

Current RxNorm `related.json?tty=SCD+SBD+SCDF+SBDF+SCDG+SBDG` content read on 2026-11-12:
- levothyroxine: 219 product/form concepts; nonoral names identify injections 1115267, 1115269, 2166148,
  2166193, 2166196, 2621123, 966219, 1868004 and 1602750;
- digoxin: 32 concepts; injections 208135, 208137, 1743560, 1175613, 104208, 204504, 1743558 and 1151519;
- aspirin: 374 concepts; rectal products 103863, 198461, 198463, 198464, 198473, 370609 and 1154071.
The other authored salicylates and nitrofurantoin returned no nonoral concepts in those term types. This is a
verified current census, not an exhaustive promise for retired or future RxNorm IDs. Unknown route retains
oral-qualified guidance. The existing levothyroxine/iron, calcium and held-soy rows get the same exclusions;
this is one timing contract, not a separate medication route engine.

The bundled timing asset is synced in the isolated app consumer checkout. Actual new asset tests confirm that
known nonoral magnesium/levothyroxine, psyllium/digoxin and psyllium/aspirin pairs emit no medication timing
card, the same ingredients without an excluded product still do, and unrelated metformin never matches.
No salicylic-acid topical identity was included. New timing asset and compatible reader must ship together;
older apps would ignore the new field. No app has been published or device-qualified.

Melatonin, bromelain, probiotics, soy, EGCG, calcium carbonate and the iron/calcium, iron/zinc and
theanine/caffeine relation questions remain held unchanged. No new interval or relation was invented.

## Checks

- Fail-first: the three named regressions failed on the baseline for missing scoped psyllium rules,
  runtime presence of rejected claims, and unpublished approved magnesium precaution.
- After apply: `scripts/test.sh fast scripts/tests/test_timing_rules.py
  scripts/tests/test_levothyroxine_grapefruit_reconciliation.py scripts/tests/test_sync_flutter_reference_data.py`
  — **78 passed** after the exclusion contract test. Includes schema, exact medication scope, publication projection, rejected-fingerprint guards,
  retained holds and owner/consumer interval consistency.
- Exact `data_batch.py check --since HEAD --expect` manifest: nine timing entries (two removed, two added,
  five changed); two rejection entries added. Both report zero problems.
- `verify_all_citations_content.py --file timing_rules.json --changed-since HEAD`: 3 matches, no mismatches or
  unresolved entries, live retrieval. Safety-copy and Python-correctness checks run with the combined tree.
- Real catalog identity canaries inspected read-only in the app's existing `pharmaguide_core.db`:
  17778 “Psyllium Seed Husk 500 mg” has only `psyllium`; 1055 has `magnesium`; negative 17550 has only `coq10`.
  These establish ingredient reach, not new medication-route behavior or a rebuilt candidate.

- App route fail-first: three regressions failed before consumer correction; omission control passed.
  `flutter test test/services/stack/timing_evaluation_service_test.dart
  test/services/stack/timing_guidance_invariants_test.dart`: **58 passed**, including the new bundled-asset test.
  Focused analyzer on consumer and test: no issues (final repeat passed).
- Pipeline timing plus source-of-truth owner tests: **90 passed, 1 skipped** because the worktree has no built
  interaction DB. This focused skip is not a broad local checkpoint pass.

Broad local and exact-candidate CI belong to the integrator checkpoint. The candidate timing asset is synced;
paired artifact publication and real app/device verification remain release work. Product scorer and identity code are unchanged; timing findings intentionally
change only for the published medication pairs.

Apply-script rerun verification: a cloned digoxin exclusion on nitrofurantoin was reproduced and fixed;
the assertion now guards it. Final rerun leaves both timing files byte-identical, and synced app asset parity passes.

Independent double-check: the held-research agent reviewed the pipeline projection, app provider/parse/exclusion
paths, tests and apply-script idempotence fix; content-verified all 24 excluded RxCUIs live and re-read
MedlinePlus, ThyroMag and SYNTHROID on 2026-11-12. No blocking findings. This was agent source/applicability
review, not clinician review; existing clinical sign-offs and paired-release limitation remain as stated.
