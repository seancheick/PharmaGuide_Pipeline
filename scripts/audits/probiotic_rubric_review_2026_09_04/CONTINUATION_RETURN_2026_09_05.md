# Continuation return package — 2026-09-05 (local, feature worktree)

For Codex's independent audit. Everything below was produced in
`/Users/seancheick/Downloads/dsld_clean/worktrees/probiotic-evidence-coverage`
on branch `codex/probiotic-evidence-coverage` from checkpoint `dcd38005`.
Nothing was merged to main, published, uploaded, imported into Flutter, or
calibrated; `quality_score.json` is unchanged
(`18b7ff59dc1c4baa4e89562492ffa9338491bb618da42e4044900f805beae9e1`).

## Commit range

`048e65fb` fix(scoring): structural totals no longer compete with their own active — batch 1
`be974efb` fix(evidence): review lost botanical joins and the 5.3.11 patch on real labels — batch 2
plus the docs commit that adds this package (batch 3), all on `codex/probiotic-evidence-coverage` descending from `dcd38005`. Main is untouched.

## What changed (three reviewed batches)

1. **Source-owned structural totals no longer compete with their own active**
   (handoff §5). One lineage decision,
   `scoring_input_contract.primary_mass_competitor_rows`, consumed by the three
   primary-mass helpers in `generic_evidence.py`. Synthetic
   `activeIngredients[i]` provenance resolves through the product's actual
   tree; undisclosed members and activity/CFU/IU-only children keep a total
   competing. Details, boundaries and the matched A/B comparison:
   `source_ownership_lineage_research.md`.
2. **Individually reviewed lost botanical joins** (handoff §6). Registry
   5.3.12: exact preparation aliases for Echinacea purpurea aerial/herb/root
   extract and Astragalus root after reading the cited reviews live; an
   explicit, machine-visible Ceylon exclusion on the Cassia/Cinnulin cinnamon
   family; black garlic, whole red-grape extract and DPP-IV enzyme products
   reviewed and left unjoined. Independent real-label review of the 5.3.11
   patch: Boswellia required terms gain the printed extract spellings, its
   outcome uses the locked vocabulary label, scoring-contract recoveries now
   carry their row reference (Pacran cranberry powders), and the wrong
   "Botalys" astragalus alias is removed. No enrollment, effect, multiplier,
   dose threshold or approval changed. Details: `botanical_lost_match_dispositions.md`.
3. Audit notes, ledger and this package.

## Tests

- RED reproduced at checkpoint: `1 failed, 175 passed` (floor 0.0 vs 18.0).
- Ownership file after fix: 11 passed. Disposition file: 25 passed (joins on
  the enricher path, Ceylon denials on the real label path, a Cassia control,
  unreviewed-preparation locks, no-threshold guards, the five Boswellia
  printed-spelling labels, the bare-row denial, the cinnamon typo, the Pacran
  recovery reference and its seed-oil exclusion, the Boswellia vocabulary label).
- Seven-file focused set plus every test touching the changed seams:
  489 passed.
- Citation content gate (`verify_backed_studies_citations.py`, live):
  ok=461, TITLE-MISMATCH=0, TITLE-DRIFT=0, not-found=0, GHOST-SUSPECT=2
  (PMID 21747893 PRECLIN_DGL, PMID 33516238 BRAND_LIFE_EXTENSION_SUPER_BIOCURCUMIN),
  both pre-existing and already recorded in `backed_studies_ghost_review.json`.
- Broad `scripts/test.sh fast` after the corpus run: 2 failed, 13,505 passed, 167 skipped (206 s). Both failures are the checkpoint's 5.3.11 cranberry entry (`primary_outcome` outside the locked vocabulary; `health_goals_supported` empty) and need the taxonomy decision below; no failure is caused by this continuation's code or data.

## Corpus comparisons (read-only harness, matched inputs)

Input root `/Users/seancheick/Downloads/dsld_clean` (174 manifest-owned input
files, hashes verified before/after by the harness). Reports live in
`/Users/seancheick/Downloads/dsld_clean/reports/probiotic_rubric_review_2026_09_04/`
and are Git-ignored.

| Report | Purpose | SHA-256 |
| --- | --- | --- |
| `corpus_source_ownership_control_dcd38005_targets.json` | 774 targets, checkpoint code | `0887cbcd766e7535c8cd6f7529207d52a1b6dd7f9cbbc7fbc9a3c0d73205a38f` |
| `corpus_source_ownership_candidate_targets.json` | 774 targets, candidate before activity-unit refinement | `507c547d1f1ebc2830693314e161f1756dd9097fe28dff5f6255f5c513a827ea` |
| `corpus_source_ownership_candidate_targets_v2.json` | 774 targets, final candidate | `48ea3765cf7a8ae2d9c9cafae6223766e1eabb011fcf6572f095ebb8f3dc71ca` |
| `corpus_dose_attribution_control_cea87d01_6.json` | 6 targets, old code, dose-method attribution | `1836683178e886dc` (prefix; 6-product attribution run) |
| `corpus_source_ownership_cloud_1xp12h_targets.json` | 774 targets, concurrent cloud branch | `095e57ebe1af3b5779baf43401a65cf91d8b1584bfbadbeab3d9a3ca2361b11a` |
| `corpus_continuation_2026_09_05_full.json` | first full pass (before the patch-review fixes; superseded) | `69c5c7e6fcae6e34bf42a28148cb159ba8f8a7d2a50fcf2955eee92d1235c560` |
| `corpus_continuation_2026_09_05_full_v2.json` | FINAL: all 15,415 products, 8,078 fully re-enriched, baseline `corpus_preparation_control_cea87d01_source_owners.json` (`7f77ae2b…`), 840.3 s, zero errors | `1ff7d57909c65564be19bc7c7ac0e5f28a3f2e74833c4ee1aeba9a6bbe8a462b` |

Targeted A → final candidate (774): 40 score changes, all upward (+0.7 to
+15.1), evidence pillar only; 0 status/module/route/confidence/evidence-set
changes; 11 tier, 3 verdict; generic 35, sports 5. Every changed product was
inspected by cause (see the research note).

Full corpus (final) versus the old-code control: status transitions identical to the accepted checkpoint (13 not_scored→scored, 15,091 scored→scored, 180 scored→not_scored, 77 unchanged not_scored, 54 unchanged suppressed); 3 module changes (the same two generic→omega and one generic→fiber_digestive); 461 score changes, of which 268 retained scored→scored numerical changes (evidence 195, formulation 79, dose 43), 82 tier and 23 verdict changes, 0 confidence changes, 169 up / 99 down, range −15.1 to +14.7.

Versus the accepted checkpoint report (same control, so this isolates the 5.3.11 patch plus this continuation): 196 records differ, 180 score changes, 177 up and 3 down, 0 status changes. The three decreases are reviewed decisions (330604 Ceylon explicit denial; 243132 grape-seed blend losing mismatched cranberry evidence; 243146 bare "Boswellia serrata" row, recorded as ambiguous). Every family among the increases was traced: Boswellia (patch restoration plus the five printed extract spellings), cranberry (patch restoration plus recovered Pacran powders), echinacea/astragalus joins, and the source-ownership floor cases. One known wrong-identity artifact remains inside the increases (328831 "Botalys" carries a cleaner-stage astragalus identity; alias fixed for future cleaning).

Named controls (Seed, Culturelle, Garden, Fortify, Ritual, Jarrow, Solgar):
all unchanged — Seed 81.2, Culturelle 72.7, Garden 57.4, Fortify 63.6, Ritual 55.9, Jarrow S. boulardii + MOS 62.4, Solgar 79324 75.8 -> 75.8.

## Concurrent cloud branch

`origin/claude/probiotic-evidence-audit-1xp12h` (two commits from the same
checkpoint) appeared during this work. Its ownership fix leaves the real
213475 label at floor 0 (synthetic projection still competes); its nine test
cases pass against this branch. Its applicability tightening (`19ebfbbf`) is
compatible and recommended for verification and adoption. Neither branch
touched the other. Side-by-side numbers: the cloud run above.

## Human decisions required (nothing below was changed)

1. Branded-vs-generic evidence tier: BRAND_PHOSPHATIDYLSERINE and 14 other
   branded entries carry generic aliases; the branded floor tier reaches
   generic labels.
2. `total_enrollment` convention: schema doc vs 5.3.11 practice vs stored
   values (astragalus 112/1,094; echinacea 719/4,631; cinnamon 229/543;
   garlic 3,411/553). Enrollment bands change points.
3. `registry_completed_trials_count` feeding the depth bonus (removed for two
   entries in 5.3.11, present elsewhere).
4. Dose-method semantics when the primary active has no reference (Cognigrape
   304628 20/20 from B6/B12; shiitake 223536 partial credit 16 with formulation
   0.8); pre-existing fail-open floor without a dose gate (Bio-Quercetin 325831).
5. Identity defect: multi-constituent DSLD form headers projecting as one
   constituent (17186 "Glucosamine Chondroitin Complex 3,500 mg" → vitamin C).
6. `sports.py` / `fiber_digestive.py` opt into the primary floor against the
   `score_evidence` docstring.
7. 218838 sibling lineage (needs producer/label evidence).
8. Two lineage policies (`profile_owner_candidate_rows` reconciliation vs
   `primary_mass_competitor_rows`) and two mass parsers (`_mass_mg` vs
   `_role_mass_mg`) are candidates for unification.
9. Taxonomy: the 5.3.11 cranberry entry's `primary_outcome` ("Prevention of
   recurrent symptomatic urinary tract infections") is outside the LOCKED,
   app-facing 15-label `primary_outcome_vocab.json`, and its
   `health_goals_supported` is empty; neither vocabulary has a urinary entry.
   These are the two remaining broad-suite failures. Decide: add a urinary
   outcome/goal to the vocabularies, or map to an existing label.
10. Two cleaner-stage identity items surfaced by the replay: 328831 "Botalys"
    (ginseng brand stored as `astragalus_root`; alias fixed, re-clean needed)
    and 243146 (source row "Boswellia serrata" with a boswellic-acid form while
    the title says extract; left unmatched).
11. Unchanged from the handoff: 180 identity/non-scoreable holds, clinical
    rubric ratification, native-context approval, blinded benchmark.

## Commands and state mutations actually performed

- Read-only: fixture hash verification; enrichment probes of 213475/218600/
  218838/17186 and the 17 open labels; inventory scan of 15,415 enriched
  products; four targeted harness runs and one full harness run (new output
  paths only); live PubMed esummary/efetch for PMIDs 20523044, 21103034,
  37952511, 24554461, 24019277, 32010325; the citation gate.
- Worktrees added (detached, read-only use): `worktrees/checkpoint-dcd38005`
  at `dcd38005`, `worktrees/cloud-1xp12h` at `19ebfbbf`. The existing
  `continuation-baseline.1ZPh87` was used as `--implementation-root` only.
- Edited: `scripts/scoring_input_contract.py`,
  `scripts/scoring_v4/modules/generic_evidence.py`,
  `scripts/data/backed_clinical_studies.json`,
  `scripts/tests/test_evidence_primary_source_ownership.py`; added
  `scripts/tests/test_botanical_lost_match_dispositions.py` and three audit
  notes. No pipeline output, catalog, Supabase, Flutter or `.env` touched.
- Git: fetch, commits on the feature branch, push of the feature branch only.

## Frozen fingerprints (final tree)

```
9b738b513a4553db72447ca9c2c020a556f12fa9b7047082ba2c7e394f3b16b9  scripts/scoring_input_contract.py
945f953f9fc5c3febec0d4d946a2238af929172b5179accfc4e40cf927416c27  scripts/scoring_v4/modules/generic_evidence.py
e4d581c69d35abd05488433a7f68d9da5ae8bcd8e187dd9550c8a15680164dac  scripts/data/backed_clinical_studies.json
2017232ac825fd2f0264eb8c1e44b240d2a02970ec6e6a3f5836c2b98e9add7d  scripts/data/botanical_ingredients.json
7921e875959bbe34bbd97ceead7e2502eeec601aa7b36eb2fec2843b3bd7fda0  scripts/tests/test_evidence_primary_source_ownership.py
a5099dc5290552af97556436cf4ea8937d9f311c006eb7d457baa179dc4651b4  scripts/tests/test_botanical_lost_match_dispositions.py
18b7ff59dc1c4baa4e89562492ffa9338491bb618da42e4044900f805beae9e1  scripts/scoring_v4/config/quality_score.json
```
