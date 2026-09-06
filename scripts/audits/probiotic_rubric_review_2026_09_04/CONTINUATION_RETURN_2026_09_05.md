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

---

# Round 2 — Codex audit follow-up (2026-09-05, same worktree)

Codex accepted the source-ownership fix and listed five corrections. Each was
reproduced first, fixed at its root with a RED-first test, and measured.

## Commits

- `7c8b5fa0` fix(applicability): source-required terms ignore enrichment-derived forms (cherry-pick of cloud `19ebfbbf`)
- `58a5aa6c` fix(evidence): registry trial counts no longer feed the depth bonus
- `fd2215e8` fix(dose): unreferenced mass-primary active caps the window proxy at partial credit
- `f5054f86` fix(cleaner): blend rows and disagreeing form UNIIs never identify a row
- `bc5f06a3` feat(taxonomy): urinary tract health outcome and goal; PS record reclassified (registry 5.3.13)
- `07715980` refactor(dose): the mass-primary label-active decision lives in the scoring contract
- plus the docs commit that adds this section

## 1. Applicability bypass (cloud `19ebfbbf`)

Its regression was RED on the local branch (`1 failed, 15 passed` with the
cloud test file). Cherry-picked as `7c8b5fa0` with `-x`; the cloud branch's
alternative ownership implementation was not adopted.

## 2. Cranberry contract failures — truthful urinary taxonomy

Neither the locked 15-label outcome vocabulary nor the 18 user goals had a
urinary entry, so the checkpoint's free-text outcome and empty goal list
could not be mapped honestly. Added, with every contract and app pin updated:

- `primary_outcome_vocab.json`: `urinary_tract_health` / "Urinary Tract
  Health" (16 entries; related goal below). Notes state prevention of
  recurrent UTIs, not treatment.
- `user_goals_vocab.json`: `GOAL_URINARY_TRACT_HEALTH` (19 goals, priority
  low); `user_goals_to_clusters.json` maps it to the existing
  `urinary_tract_health` synergy cluster (required, 1.0) with
  `probiotic_and_gut_health` 0.4, the same blocked workout clusters as other
  goals and min_match_score 0.6.
- `db_integrity_sanity_check.py` canonical goal list, and the three pipeline
  contract tests (outcome 16, goals 19, mapping integrity) updated.
- INGR_CRANBERRY: `primary_outcome` "Urinary Tract Health",
  `health_goals_supported` ["Urinary Tract Health"].
- App repo `/Users/seancheick/PharmaGuide ai` (NOT committed — main is your
  branch with one unpushed commit): both vocab assets synced from the
  pipeline (the goal asset also picks up two pre-existing
  `related_drug_class_ids` differences), `schema_ids.dart` goals/labels/
  priorities, the loader comment, and both drift tests (`flutter test`: 10
  passed). Profile and wizard screens enumerate `SchemaIds.goals` dynamically,
  so no other app list exists.

## 3. Identity corrections proven end to end

- `enhanced_normalizer._try_unii_match`: a DSLD blend-group row never takes a
  form UNII as its identity, and disagreeing form UNIIs identify nothing.
  Tests: `test_unii_form_identity_ambiguity.py` (3) plus the existing ledger
  and cleaner suites.
- Cleaner replayed on the raw records (`clean_dsld_data.py` on
  17186.json and 328831.json), then enriched and scored with the candidate:
  17186's header is now an unmapped `blend_header_total` (no vitamin C
  identity; evidence 10.5 → 5.8, transparency 15.0 → 0.9 under the existing
  opaque-blend policy, score 66.2 → 48.6); 328831 "Botalys" maps to ginseng
  and matches INGR_GINSENG (score 65.7, versus 56.9 old and 71.6 with the wrong
  astragalus identity). The read-only corpus audit still replays the stored
  cleaned rows, so both products keep their old identities in the reports
  below until the operational re-clean; the harness cannot show the fix.
- Follow-up, not changed: `_anchor_identity` mints a slug identity from an
  unmapped header's standard name (`glucosamine_chondroitin_complex`); a
  product-level projection with a non-registry identity is a pre-existing
  seam for the identity review.

## 4. Evidence-credit semantics

- `_published_study_count` no longer falls back to
  `registry_completed_trials_count` (DATABASE_SCHEMA.md contract). The test
  that pinned the old fallback was inverted to the contract. 155 entries lose
  that exposure; the effect is a depth-bonus change only.
- BRAND_PHOSPHATIDYLSERINE → INGR_PHOSPHATIDYLSERINE, `ingredient-human`,
  standard name Phosphatidylserine (registry 5.3.13). Both cited trials are
  ingredient-level (PMID 20523044 PS-DHA; PMID 21103034 soybean PS). The
  `serinaid` alias stays as a name for the ingredient. Tests referencing the
  id updated. Primary floor for PS labels moves from the branded tier to the
  generic strong tier (26 labels 73.2 → 70.6, including the two SerinAid
  labels), and four PS labels that the branded guard had excluded now earn
  the ingredient-level evidence (e.g. 243046 56.3 → 72.6). One product, 82935
  GNC "Stress Hormone Balancing Blend", drops 61.7 → 37.2: its only PS row is
  an undisclosed 0 mg child inside a 400 mg PS + phosphatidic-acid blend, so
  ingredient-level evidence cannot attach once the record is no longer treated
  as a product-level branded study; the formulation change follows from the
  lost brand credit. Reviewed as a consequence of the honest classification,
  not corrected.

## 5. Dose coverage

`generic_dose.score_dose`: when the heaviest competing active (same
source-ownership helper as evidence) has no RDA/UL adequacy row, the
supplemental-window proxy is capped at the existing partial credit for a
disclosed dose without a reference (`NO_REFERENCE_INDIVIDUAL_DOSE_CREDIT`),
and metadata records `window_proxy_status = partial_credit_primary_active_unassessed`
and `primary_active_unassessed`. A trace unreferenced co-active does not cap.
No new magnitude was introduced. Cognigrape 304628 moves from 20/20 to the
partial band. The first full pass showed the cap also firing on 172 products
whose heaviest row is an opaque greens/fruit blend total or an unmapped
projection (Raw D3, Daily C-Protect, Methyl B12, Vitamin C sprays); those are
not the product's primary active, so the cap is limited to identified label
actives (not `product_level_evidence`, not `unmapped`). Tests: three cases at
the scorer and helper level; the synthetic clamp fixture (rows named Magnesium
with placeholder ids) is honoured by matching adequacy rows on nutrient name
as well as canonical id.

## Verification

- Seam suites across everything changed this round: 1,075 passed, 18 skipped.
- Contract/integrity suites: 43 passed (integrity errors and warnings 0).
- Targeted 831-product comparison (checkpoint `dcd38005` vs candidate, same
  inputs and baseline, before the cap narrowing): 356 score changes, 61 up and
  295 down, 0 status/module changes. Downs by cause: 223 evidence-only
  changes of at most 0.5 (registry-count depth bonus removed), 46 PS-family
  tier changes above 1.0, 8 dose-cap cases, remaining small mixed changes.
  Reports `corpus_round2_control_dcd38005_targets.json` and
  `corpus_round2_candidate_targets.json`.
- Consolidated full audit before the cap narrowing
  (`corpus_continuation_2026_09_05_full_v3.json`, SHA-256 `a952b513…e970`,
  838.0 s, zero errors): transitions identical; controls unchanged; 2,451
  score changes versus the round-1 final report (2,440 down, mostly the tiny
  depth-bonus change; 172 dose-cap products, reviewed above and narrowed).
- FINAL consolidated audit (`corpus_continuation_2026_09_05_full_v4.json`,
  SHA-256 `64286ff51bb9dd4d15fcb94c6b9e8df51103639d457fcd7400c75d8cd66d73da`,
  845.3 s, zero errors, 8,078 fully re-enriched, baseline
  `corpus_preparation_control_cea87d01_source_owners.json`): transitions
  identical to the checkpoint; seven controls unchanged (Seed 81.2, Culturelle
  72.7, Garden 57.4, Fortify 63.6, Ritual 55.9, Jarrow 62.4, Solgar 75.8).
  Versus the old-code control: 2,545 retained numerical changes (evidence
  2,485, formulation 123, dose 61), 163 tier, 28 verdict, 0 confidence.
  Versus the round-1 final report (round-2 effect alone): 2,397 score changes,
  7 up and 2,390 down, 0 status or module changes. 2,394 of the downs are the
  small depth-bonus change from removing the registry-count fallback; 19 are
  the narrowed dose cap (iron builders with a heavier botanical, cranberry and
  cinnamon formulas, the Cognigrape gummy, all 20 → 14.5-band); the PS family
  moves 18.9 → 14.7 evidence with four previously excluded PS labels gaining
  14.7 and 82935 losing its undisclosed-dose evidence as described above.
- Broad `scripts/test.sh fast` on the final tree: 13,517 passed, 165 skipped,
  0 failed (219.7 s). The two round-1 cranberry failures are resolved.
- Committed tree verified against the hashes the final audit ran on
  (12 implementation/data files, all match).

## Still open after round 2

- Operational re-clean is required before 17186 and 328831 change in a
  shipped catalog; the corpus audit cannot replay the cleaner.
- Unmapped-header identity minting (`_anchor_identity` standard-name slug).
- Enrollment convention, remaining branded-with-generic-alias entries, and
  the semantics decisions listed in round 1.
- App-side taxonomy edits are in the working tree of the app repo, uncommitted.

---

# Round 3 — Codex's second audit (2026-09-06)

Codex kept the ownership fix and found three reproducible boundaries after
round 2. Each was reproduced before any change, closed with regression tests,
measured on the corpus, and left as one system: the contract decides
identities and primaries, the builder decides the goal, the modules consume.

## Commits

Pipeline `db5325d2..3e2f5343` plus the docs commit that adds this section, on `codex/probiotic-evidence-coverage`;
app `73ee825..4c1685c` on `main` of `/Users/seancheick/PharmaGuide ai`
(the six taxonomy files Codex asked to preserve, plus the loader comment
that still said 18 goals). Nothing merged, published, uploaded, imported,
calibrated or rebuilt.

## 1. Dose guard — usable assessments, deterministic ties

Reproduced at module level with the round-2 fixtures: an adequacy row for the
primary with both percentages empty restored 22/22 (expected 16); with an
assessed and an unassessed active at equal mass, reversing the label order
flipped 22 ↔ 16.

- `scoring_input_contract.mass_primary_label_actives` replaces the single-row
  helper: every identified label active tied at the top competing mass is a
  primary, returned in identity order; an opaque total or unmapped row is
  never returned and, when it alone holds the top mass, there is no
  identified primary (unchanged policy).
- `generic_dose._mass_primary_without_reference` counts an adequacy row as an
  assessment only when the window proxy itself could band it
  (`_band_credit(pct_rda, pct_ul) is not None`): pct_rda-only rows are
  usable, pct_ul-only and empty rows are not. A potassium row (the proxy's
  dietary-intake exclusion) with numeric percentages still counts as assessed
  because a reference exists; the guard's copy would otherwise claim a
  benchmark is unavailable when it is merely excluded.
- Assessments are source-linked. Closing the empty-row hole first exposed
  344 products whose mass primary has no bandable adequacy row; 65 of them
  are assessed through their own source — the constituent a parent declares
  (ALA under flaxseed oil in 36, GLA under borage oil in 10) or the label row
  a projected child was cut from (the enricher's "Vitamin K2" child under the
  assessed "Vitamin K" row, tied at 45 mcg). `scoring_input_contract.
  source_linked_rows` applies the contract's existing lineage (same resolved
  path, nested under, or ancestor; never shared identity) and the guard
  reads identities across that set. A constituent the label prints as a
  sibling row (6 flaxseed labels) stays unlinked; a parent whose constituents
  carry no percentage (fish oil with EPA/DHA rows, 11) stays capped.
  Families still capped (`reports/…/dose_guard_families_2026_09_06.json`):
  protein powders 40, caffeine 13, BHB 12, CLA 12, L-tyrosine 12, fish oil 11,
  keratin 9, phytosterols 9, chlorophyll 9, fiber 7, saw palmetto 7, …
- Consumer copy: `quality_score._unassessed_primary_dose_reason` — "The main
  ingredient's dose benchmark is unavailable, so dose credit is partial." —
  sits after the over-limit and undisclosed-component copy and before the
  band copy, so Cognigrape no longer reads "reasonable but not fully in the
  studied range".
- Tests: `test_v4_generic_dose_p132a.py` (+10: empty row, UL-only row,
  RDA-only row, tie in both orders, helper order, nested constituent, same-path
  projection, nested projection under an assessed parent, sibling constituent,
  parent with unassessed constituents) and `test_v4_quality_score.py` (+1).

## 2. Urinary goal — reviewed applicability, owned by the goal rule

Reproduced through `build_final_db.compute_goal_matches` over the 15,415
enriched products (probe only; the builder was not run). 129 products carry
the enricher's `urinary_tract_health` synergy cluster; 44 of them have no
cranberry row and 42 of those were "supported" — lactobacillus + vitamin C
(15, Culturelle immune packets, Garden of Life collagen beauty), uva ursi +
vitamin C, D-mannose + vitamin C. 98 products with a cranberry row and no
cluster (BulkSupplements 500 mg extract, 5 g powders) never matched.

- `_urinary_goal_cluster_applies` in `build_final_db.py` (constants block
  documents the review): a label row whose identity is cranberry — canonical
  `cranberry`, `cranberry_fruit`, or the standardized brands `pacran`,
  `cran_max`, `cranrx`, `flowens`, or the label text — with a disclosed mass.
  Supported when the mass reaches the synergy cluster's own minimum for
  "cranberry extract" (500 mg, read from `synergy_cluster.json` through
  `_synergy_cluster_min_dose_mg`; no second copy of the number); present
  below it → `goal_matches_underdosed`. Seed oil / seed extract rows and
  undisclosed listings inside fruit blends are excluded; a cranberry blend
  header counts for presence only. The synergy cluster itself never earns the
  goal on either the primary or the legacy path.
- Not credited on their own, by review and recorded in the code: vitamin C,
  unspecified probiotics/lactobacillus, uva ursi, hibiscus, and D-mannose —
  Hayward et al., JAMA Intern Med 2024 (PMID 38587819, title verified live
  via esummary) found no prevention benefit. Both vocabulary notes now say so
  (`user_goals_vocab.json`, `primary_outcome_vocab.json`, ≤ 200 chars);
  `user_goals_to_clusters.json` is unchanged.
- Corpus effect (probe, `reports/…/urinary_goal_transitions_2026_09_06.json`):
  supported→partial 83 (cranberry 60–400 mg: CVS 168 mg concentrate,
  BulkSupplements 60 mg softgels, GNC multis at 2.5–10 mg), none→supported 45,
  none→partial 46, supported→none 18 (the vitamin C + probiotic / uva ursi
  families), partial→supported 2 (CranRx gummies at 500 mg), unchanged 33.
  Products with any urinary status: 127 → 200.
- Tests: `test_compute_goal_matches.py` (+13: extract 500 mg, powder in
  grams, branded CranRx, trace cranberry in a multi → partial, disclosed
  nested row → partial, blend header → partial; negatives for lactobacillus +
  vitamin C, D-mannose + vitamin C, uva ursi + vitamin C, D-mannose alone,
  seed extract, undisclosed listing; dedup with the cluster).
- App: assets re-synced after the wording change; `flutter test` on both
  drift tests: 10 passed; committed as `4c1685c`.

## 3. Identity — agreement, not first-hit; structural ≠ verified

**Form UNIIs.** `_try_unii_match` now returns None when any UNII-bearing form
carries a UNII the identity index does not know; the row falls through to
name matching. Scan of all 15,414 raw labels: 266 non-blend rows mix a
resolvable and an unresolvable form UNII, 263 of them currently identified
through the resolvable one. The cleaner was replayed on those 217 labels
(`reports/…/cleaner_replay_unii_strict_2026_09_06.json`, 8,915 rows
compared): 27 identity changes in 27 products, each read individually —
plain "Lactobacillus" listings no longer become `lactobacillus_plantarum`
(12), "Protease(s)" no longer `bacillus_subtilis` (8), "Vitamin K" with mixed
K1/K2 forms → `vitamin_k` (2), "Vitamin K2" and "Vitamin D2" no longer
`brewers_yeast` (3), "Medium Chain Triglycerides" no longer `lauric_acid`,
bergamot "Polyphenolic Flavones" → its marker row; 236 rows change match
method only (same identity by name). One regression was found and fixed with
one entry: "Pomegranate Fruit, Peel Extract" (forms POMEGRANATE `56687D1Z4D`
and POMEGRANATE FRUIT RIND `RS999V57DU`, both verified on GSRS) fell to the
other-ingredients "pomegranate juice" entry; the IQM `pomegranate` entry has a
single `external_ids.unii` slot, so two printed-name aliases were added and
the row maps to `pomegranate` again (statistic and date reconciled). Test:
`test_unii_form_identity_ambiguity.py` (+1).

**Structural anchors.** Every derived evidence item now carries
`identity_kind`: `verified_ingredient` when the identity it carries is the
cleaner's (its `clean_identity_id` — for a header total, the mapped nested
child it is keyed to — else the source row's canonical), otherwise
`label_taxonomy_anchor` when `_anchor_identity` minted one from the label's
group or standard name. A structural anchor is `mapped: False`,
`mapped_identity: False`, keeps its `product_level_evidence` role and its
anchor as the join key, and never becomes a dose primary. The one rule is
public, `has_scoring_identity` (a verified row by its mapped identity, a
structural anchor by its anchor alone); `assessment_readiness` consumes it
instead of re-reading `mapped`, which is what made the 24-strain seed
probiotic `not_scored` during development (its header totals are keyed to
mapped nested children — classifying by the header's source db was wrong,
and the seed-pipeline test caught it). Recovery of skipped rows can no longer
upgrade a minted anchor to a mapped identity (no corpus instances). Census:
2,673 product-level rows and 74 label projections carried an unmapped
identity as `mapped: True` before.
- Fixture `replay_identity_fixtures_2026_09_06.json` (17186 and 328831,
  replayed through the candidate cleaner and enricher, trimmed to the fields
  the contract and modules read) and `test_structural_anchor_identity_flags.py`
  (5): the 3,500 mg header stays a structural total with `mapped: False`, the
  vitamin C row keeps its cleaner identity, the header is never a dose
  primary, and Ginseng Plus matches INGR_GINSENG, not astragalus.

## Verification

- Targeted comparison, 1,826 products carrying unmapped structural
  projections, control `db5325d2` (detached worktree) vs candidate, same
  targets and baseline: 1,826 products (control 361.6 s, candidate 363.4 s, zero errors), status transitions identical (1,592 scored, 187 not scored, 47 suppressed); 337 products differ, all decreases — 289 formulation changes of at most 0.8 points (the panel-form neutral floor is no longer granted to a structural anchor that was stamped mapped) and 48 dose caps to 14.5 where the primary's own source carries no bandable reference (25 protein powders, saw palmetto, nicotinamide riboside, resveratrol…; Life Extension NAD+ Cell Regenerator 182477: the 250 mg NR row has pct_rda and pct_ul None and its 22/22 came from quercetin's 30% RDA alone). Reports: `corpus_round3_control_db5325d2_structural_targets.json`, `corpus_round3_candidate_structural_targets_v2.json`, `corpus_round3_structural_ab_diffs.json`.
- Final consolidated audit `corpus_continuation_2026_09_06_full_v6.json`
  (SHA-256 `7e1ae7e6340749608f74be497ce40de4b74ced88ab9519621392bed099096094`, 861.9 s, zero errors): transitions identical to round 2 (15,104 scored, 257 not scored, 54 suppressed); 832 products differ from the round-2 report — 691 score changes, all decreases, no status change: 281 dose (212 at −5.5, the 20 → 14.5 cap for a primary whose source lineage has no bandable reference: protein powders, CLA, caffeine, BHB, L-tyrosine, fish oil with unreferenced EPA/DHA rows, keratin over biotin; 69 smaller) and 410 formulation (≤ 0.8); 92 tier labels and 4 verdict labels follow those decreases; 141 copy-only changes (414 dose reasons now name the missing benchmark, Cognigrape 304628 included at 56.4). The round-1 controls, 213475 and 218600 are unchanged; the committed tree matches all 267 audited file hashes.
  The earlier `…_full_v5.json` (SHA-256 `f7b26146…c2fa49`) is the same tree
  before the source-linked rule and is kept as the record that exposed it.
- Broad `scripts/test.sh fast` on the final tree: 13,547 passed, 165 skipped, 0 failed (216.4 s).
- Contract leak audit (in the suite) passes: `generic_dose` reads no identity
  field; the goal rule lives in the builder, not a scoring selector.

## Human decisions after round 3

- 83 cranberry products between 60 and 400 mg are now "partially supported"
  under the cluster's 500 mg extract dose; a PAC-based (36 mg/day) or
  concentrate-ratio gate would need clinical review before it is added.
- Mass dominance names 25 mg keratin, not 10 mg biotin, the primary of nine
  "Biotin 10,000 mcg" products, so they now read "main ingredient's benchmark
  unavailable" and drop 5.5 points; whether label prominence should override
  mass for microgram nutrients is a scoring-policy decision, not made here.
- Primaries whose reference exists in principle but has no percentage in
  `rda_ul_data` (protein, EPA/DHA, chlorophyll) now read as unassessed; a
  reference-table coverage item.
- Probiotic strains with urinary evidence (L. rhamnosus GR-1 / L. reuteri
  RC-14, L. crispatus) are not credited; adding strain rules is a review item.
- The IQM schema holds one UNII per entry; a second registered UNII for the
  same substance (pomegranate fruit rind) cannot be indexed without a schema
  change.
- `synergy_cluster.json` `urinary_tract_health` note reads "Tier 1 (strong)"
  while its `evidence_tier` is 4 (display text only; untouched).
- The identity corrections (17186, 328831, the 27 UNII rows) reach shipped
  artifacts only through an operational re-clean.
