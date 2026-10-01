# Phase 2 — generic Evidence prominence ownership

Status: **PINNED CODEX AUDIT IMPLEMENTED AND MEASURED; FINAL FAST PASSED; NOT INTEGRATED.**
Codex fixes through `9f7837e8` extend Claude production `b43a048f` on the isolated
`codex/quality-completion` branch. Claude subsequently advanced production to `68cae99a`
(fetched feature tip `002d2683`); those later changes require reconciliation and a new candidate
checkpoint. Main remains outside this audit. No push or catalog release authorized/performed by this Codex audit; Claude has pushed its feature branch for review.
Historical Claude progress below is preserved as history, superseded by the dated audit receipt
for Codex validation status. Older numbers do not validate a later candidate.

## Owner Check

- Owner: `scripts/scoring_input_contract.py::classify_ingredient_roles` (roles) read through
  `scripts/evidence_resolver.py::evidence_owner_canonicals` (Evidence owner tiers) — evidence: matrix
  concept `scoring_input_contract`; glossary "Material active"; `rg` of every caller of the four
  generic helpers (`generic.py`, `sports.py`, `fiber_digestive.py` call
  `score_evidence(apply_primary_floor=True, owner_scoped=True)`; `resolved_clinical_matches` also feeds
  `assessment_readiness`, `confidence` and `probiotic_evidence`).
- Extension, not a second owner: `_evidence_owner_selection` returns both views of the one decision —
  owner identities (unchanged contract of `evidence_owner_canonicals`) and the prominent subject rows
  (`evidence_prominent_row_keys`, keyed by `evidence_row_key`, the subject key that already existed).
- Probiotic organism identity: `scripts/probiotic_measurements.py::is_probiotic_source_identity`
  (matrix concept `probiotic_row_identity`).
- Will NOT create: classifier, subject list, scorer, Dose engine, registry, public field/status,
  config key or app calculation. No config, clinical data or export change.

## Classification of every mass/amount check touched

| Check | Before | Class | Now |
|---|---|---|---|
| Floor anchor "mass >= 0.5 x heaviest competing active" as *which row is primary* | `_primary_mass_floor` | 1 private prominence | row must be prominent (`evidence_prominent_row_keys`) |
| Same comparison as the only amount judgment for records without `min_clinical_dose` | `_primary_mass_floor` | 3 uncovered amount | **retained unchanged** as the exposure stand-in; removal is decision D26 |
| `min_clinical_dose` sub-clinical / unconvertible gates | `score_evidence`, `_primary_mass_floor` | 3 | retained |
| Anchor linkage (single non-structural ref, refs, identity token) and own positive amount; never lent blend mass, NF declaration | `_active_mass_index`/`_match_active_mass` | 2 source/structural | retained (`_evidence_anchor_rows`), now row-level |
| Authority floor "heaviest owner is DRI-essential" | `_mass_dominant_essential_canonical` | 3 (first classed 1; corrected after both fresh reviews) | **baseline helper restored unchanged** (`7ea61daa`): it was already scoped to the role owner's purpose identities, so no private prominence remained; the mass dominance is the authority's exposure stand-in (D26) because only generic Dose reads DRI adequacy and route-specific exceptions are forbidden. Only addition: a heaviest row that is a blend total lent to a member never qualifies |
| Recovery "mass >= 0.5 x max" + single-scorable/owner/title-regex primary | `_recover_verified_primary_ingredient_matches`, `_is_clear_primary_recovery_row` | 1 (selection) + 3 (exposure; first classed 1 only, corrected after round-2 review) | selection: prominent row with its own, non-lent mass (`_is_clear_primary_recovery_row` deleted); the half-heaviest comparison is **retained unchanged** as recovery's exposure stand-in (D26), since 199 of 210 records carry no studied minimum |
| Recovery identity exclusions (collagen, DRI, module-owned), blend-anchor rule, protein every-source rule | same | 2 | retained; probiotic organisms added via the identity owner |
| Collagen peptide "mass >= 0.5 x max" | `_has_primary_collagen_peptide_identity` | 1 | prominent peptide row with own (non-lent) mass; exposure stays judged by the recovered record's own 2,500 mg minimum, which the sub-clinical gate applies to its points |
| Blend heading total as an anchor | `_primary_mass_floor` (baseline anchored any heading total) | 2 | a `blend_anchor_mass` heading carries only a verified product-level record that the heading's own text names (never a member's record, never via the product title) |
| Competitor structural filter (`_competing_active_rows`) | shared | 2 | retained |
| Role owner L5/L3 mass ratio over all strict rows | `classify_ingredient_roles` | owner defect | ratio read over `primary_mass_competitor_rows` (lineage-owned totals excluded) |
| Role owner unit parsing (`mg NE`, `mcg DFE`, `mcg RAE`, vitamin D IU) | `_role_mass_mg` | owner defect, **not fixed here** | measured fix flipped 4 products to `not_scored` (Dose readiness cannot assess DFE/RAE rows once material); reverted, open item |
| Owner abstains (retain-everything fallback, no prominent row) | — | — | floor and authority keep the legacy rule unchanged; recovery/collagen recover nothing (no identified purpose to borrow for) |

## Defect -> owner fix -> regression

Every regression is in `scripts/tests/test_evidence_prominence_ownership.py` unless named. RED on
`e8687b39`: 11 failed / 7 protections passed (`~/pg_quality/prominence_20261001/red_baseline.log`).

| # | Defect (reproduced) | Owner fixed | Regression |
|---|---|---|---|
| 1 | Generic Evidence chose its primary by mass; another ingredient's amount decided the declared purpose | `generic_evidence` consumes `evidence_prominent_row_keys` (floor, authority, recovery, collagen) | `test_an_unrelated_ingredients_mass_never_changes_the_declared_purpose`, `test_a_heavier_undeclared_adjunct_never_anchors_the_floor`, recovery/collagen/authority tests |
| 2 | Floor read a blend total as an undisclosed member's dose (Sleep Tonight 328062, Fiber Fusion 219048) | anchor must be a prominent row with its own amount; lent blend mass never anchors | `test_real_blend_total_never_becomes_an_undisclosed_members_floor` |
| 3 | Role owner counted a lineage-owned supplying complex in its mass ratio (Solgar 218600) | `scoring_input_contract._role_context` reads `primary_mass_competitor_rows` | `test_real_218600_...` |
| 4 | Role owner cannot size `mg NE`/`mcg DFE`/`mcg RAE`/vitamin D IU, so such products have no purpose row (Niacinamide 306366) | not fixed (cross-owner, see open items); the abstention rule keeps their legacy floors | existing folate DFE / vitamin D IU tests stay green unchanged |
| 5 | Disclosed members of a title-named blend lost purpose at row level (Test 1700 210555) | `evidence_resolver._evidence_owner_selection` reads blend tier per row | `test_real_210555_...`, `test_disclosed_members_...` |
| 6 | Generic recovery lent species records to live probiotic rows (232059 pre-existing; 236913 would follow) | recovery identity exclusions + `probiotic_measurements.is_probiotic_source_identity` | `test_real_probiotic_organisms_never_borrow_generic_ingredient_recovery` |
| 7 | Recovery re-stamped a record enrichment already linked to the same row, narrowing its refs (Garlic Powder 217818, Multi-Oil 1838) | recovery skips an existing record already linked to that row | `test_real_recovery_never_restamps_a_record_onto_a_row_it_already_links` |
| 8 | Found by the frozen raw replay: the floor's prominence check also dropped a blend heading that IS the branded intervention ("Relora 175 mg", 293928: baseline floor 17 → 0), while correctly dropping member records under a heading total | `_is_prominent_anchor`: a `blend_anchor_mass` heading carries only a verified product-level record the heading names (the product-level recovery predicate), on a row the role owner marks prominent | `test_real_heading_that_names_its_brand_anchors_that_brands_floor`; Ravage creatine module added to `test_real_blend_total_never_becomes_an_undisclosed_members_floor` |
| 9 | Product-level predicate built brand keys from the record id only: `BRAND_UCII` → "ucii", label "UC-II" → "uc ii" (also BCM-95, EGb 761), so UC-II's heading (321604, baseline floor 18) could not name its record | `_verified_product_entry_matches_text` also accepts an alias that is the identifier itself once separators are removed; descriptive aliases stay excluded; floor gate reads the registry record | `test_a_brand_identifier_matches_as_labels_spell_it`, 321604 case of the heading test |
| 10 | Fresh review B1: the heading gate's identity text included the product title, so retitling 328062 "Sensoril Sleep Tonight" let its 250 mg two-member blend total anchor Sensoril's floor (0 → 18) | heading gate reads `_row_identity_text(..., with_product=False)`; product-level recovery keeps its title-inclusive text | `test_a_title_naming_a_brand_never_lends_a_blend_total_to_that_member` |
| 11 | Fresh review S1/S3/S4: the authority floor had dropped its heaviest-owner amount check (lent "Epsom Salt" blend total 273823/40604; fiber-route Fiber+Calcium 177088 with no Dose DRI reader; counter-ion calcium in "Calcium BHB" 311247–311250) | heaviest-owner check retained as exposure stand-in (D26), anchor must be prominent and non-lent | `test_authority_floor_keeps_the_heaviest_declared_owner_exposure_stand_in`, `test_real_authority_floor_needs_the_heaviest_owner_with_its_own_amount` |
| 12 | Fresh review S2: recovery's own-amount check (`_mass_mg > 0`) admitted a blend total lent to a member (fucoPROTEIN 40581 "Milk Protein" ← 15 g four-member blend); collagen recovery had the same hole | recovery and collagen refuse `is_lent_blend_mass` rows | `test_recovery_never_reads_a_blend_total_lent_to_a_member` |
| 13 | Found in the final-source preview replay: the row-level prominence check added to the authority floor (`32765afe`) lost vitamin C's authority on Calcium Ascorbate 1 g (306193): the title names the "Calcium Ascorbate" row, the heaviest vitamin C row is the "Vitamin C 900 mg" line | baseline helper restored unchanged + lent-mass rule (`7ea61daa`) | `test_real_authority_floor_reads_purpose_by_identity_not_by_row` |
| 14 | Fresh review round 2 S1: the floor required any linked row to be prominent but took the stand-in amount over all linked rows, so a melatonin 1 mg match also referencing L-theanine 400 mg floored at 14 (baseline did the same) | `46ca2145` excluded unrelated linked amounts; `b43a048f` then retained linked same-identity/source-equivalent rows for a prominent anchor | `test_the_retained_stand_in_reads_the_prominent_rows_own_amount` |
| 15 | Fresh review round 2 S3: recovery's half-heaviest comparison was deleted as prominence while the identical floor comparison was retained as uncovered exposure | retained unchanged in recovery (`46ca2145`); collagen's stays removed (record minimum) | `test_ingredient_recovery_keeps_the_retained_exposure_stand_in` |
| 16 | Found by the final replay of `9ea4af85`: the defect-14 fix also dropped the anchor's own same-identity rows, so Sambucus (204048, 242865: 250 mg elderberry extract with a nested "Elderberries 16 g" source row) lost its baseline floor 6.6 | stand-in reads every linked row of the prominent anchor's identity, never another identity's (`b43a048f`) | `test_real_the_stand_in_keeps_reading_the_purposes_own_identity_rows` |

## Historical D26 packet — superseded by the dated audit below

At pinned `b43a048f`, three comparisons were retained. This paragraph describes that historical candidate; later Claude source restores a fourth collagen comparison, as recorded in the dated audit below. The three were unchanged from `e8687b39`: the primary floor's half-heaviest
anchor mass, recovery's identical half-heaviest row mass, and the authority floor's "the heaviest
owner is the essential". The fresh reviews showed each is an exposure judgment no Dose owner makes
for every route: 199 of 210 records carry no studied minimum, and only generic Dose reads DRI
adequacy (`generic_dose.py` 29 references, `sports_dose.py` and `fiber_digestive_dose.py` 0).

**Question for Sean.** The primary-evidence floor now chooses its anchor from the shared role owner,
but still requires the anchor to carry half the heaviest competing active's mass. That comparison is
not prominence; it is the only thing that stops a strong floor from rewarding a trace amount when the
record has no studied minimum (`min_clinical_dose`: 11 of 210 records at `e8687b39`) and no Dose owner judges that
ingredient's exposure. Removing it now would move amount judgment out of Evidence with no owner taking
it, which the transfer invariant forbids; keeping it keeps a mass demotion of declared purposes, the
pattern D24 rejected for Dose.

- **R (implemented, status quo for these gates):** keep all three stand-ins until Dose owns per-ingredient
  exposure for every anchor (or the record carries a reviewed studied minimum) and every route that
  uses the authority floor reads DRI adequacy.
- **P (measured counterfactual, not implemented):** remove all three. Declared trace purposes then
  earn full floors and recovered records regardless of amount, and any declared essential earns the
  authority floor beside a heavier co-purpose — see the measured classes below.
- **C (rejected by the transfer packet):** keep it only for anchors without DRI/Dose coverage. The
  transfer README forbids record allowlists and route-specific exceptions for this transfer.

Unblocking work, already queued elsewhere: Phase 3 studied-minimum curation per record (Q39(g)) and
Phase 4 Dose policy packets (D24). Either retires the stand-in without a magnitude decision here.

## Progress

| Step | State | Receipt |
|---|---|---|
| Failing-first regressions | done | RED `~/pg_quality/prominence_20261001/red_baseline.log` (11 failed / 7 protections passed), `c3_probiotic_red.log`, `c4_rerecovery_red.log` |
| Source commits | done | `eb70f424`, `2ce48b21`, `5c549d1a`, `2d9ede38`; after the first replay `c4119d30`, `916d0c62`; after review round 1 `32765afe`, `db939b57`, `41eb22d7`, `452a618e`; after the preview replay and review round 2 `7ea61daa`, `46ca2145`, `9ea4af85`; after the final replay of `9ea4af85` `b43a048f` (final source). RED logs: `c6_heading_red.log` 2 failed, `c7_brand_identifier_red.log` 4, `c8_review_red.log` 6, `c9_authority_red.log` 1, `c10_review2_red.log` 2, `c11_identity_red.log` 1; GREEN focused `c11_identity_green.log` 147 passed |
| Focused + consumer tests | done (exploratory) | focused 308 passed; 90 consumer files 2,698 passed / 38 skipped; one artifact test fails identically on `e8687b39` |
| Frozen targeted replay (2,781 raw labels) | first pass at `2d9ede38` (170 moved) superseded; preview at `452a618e` (34 moved, every mover classified) superseded by defect 13–15 fixes; run on `9ea4af85` (17 moved, all down) found defect 16 and is archived in `superseded_9ea4af85/`; final run on `b43a048f` running from the isolated checkout `prominence-final` | manifest `2b314063…`; baseline `9ba85f1a…` (head `e8687b39`). Two runs were aborted: one by my own docs commit changing HEAD in the measured worktree (the harness checks HEAD), one stopped for a source change |
| 1,259-label control replay | done at `2d9ede38` (1,251 identical; 232059 Evidence 13→0; 7 readiness-only); final run on `9ea4af85` queued | Codex manifest `cbe04144…`; baseline = Codex capture `a20cea18…` (head `3ee91eae`, all 434 source hashes equal to `e8687b39`) |
| Brand-identifier cohort (every raw label naming UC-II, BCM-95 or EGb 761: 48) | done at `916d0c62` | manifest `4f62f9a2…`; baseline `66a228a2…`, candidate `b7dea4de…`: 47 identical, 219249 TamaFlex readiness lists `BRAND_UCII` for its "UC-II Type II Collagen Complex 20 mg" adjunct row (score unchanged) |
| D26 counterfactual (P arm) | queued on the targeted and second cohorts | scratch worktree `prominence-parm` at `9ea4af85` with all three stand-ins removed (`scratchpad/patch_parm.py`), never committed |
| Fresh-context review | round 1 (`e8687b39..916d0c62`): 1 blocker + 4 should-fix, all reproduced and fixed (defects 10–12). Round 2 (`e8687b39..452a618e`, fresh agent): no blocker; S1 and S3 reproduced and fixed (defects 14–15); S2 recorded below; its 400-label raw sample found 0 authority-subset violations and 1 intended down (79192 caffeine floor on a lent 243 mg blend total). Review of `7ea61daa` onward pending | probes `scratchpad/probe4.py`, `probe9.py`, `scratchpad/review2/` |
| Full fast checkpoint | pending | |

| Second cohort (raw-only coverage) | running | The targeted cohort came from stored-corpus movers and missed raw-only movers (273823/40604 were absent). Added every label not yet frozen whose raw label prints a blend total over an undisclosed member (1,464) plus a seeded random 1,500 of the remaining 9,902; manifest `6a4b4807…`. 8,402 labels stay unreplayed; the random sample estimates their mover rate |

## Historical review notes and disposition (superseded where noted)

| Note | Disposition |
|---|---|
| N1 floor tests prominence and mass over linked rows separately | Superseded by `b43a048f`: a prominent anchor is required; its linked same-identity/source-equivalent rows can supply the numerator. Unrelated identities cannot supply it. |
| N2 a prominent heading row is not structurally checked | kept: a heading the role owner itself names as a subject (e.g. a fiber-route "Fiber Blend" whose identity is fiber) is that row's own amount; recorded for Codex |
| N3 stand-in denominator can be a heading total | pre-existing baseline denominator, retained unchanged (D26) |
| N4 `eb70f424` changes roles for every consumer, including the enricher | measured by the raw replays (Clean→Enrich→Score), not the stored-corpus A/B |
| N5 one synthetic test passed on the baseline | it is a protection, counted among the 7 baseline-passing protections |
| N6 stale comments | fixed in `452a618e` |
| N7 repeated owner selection per score | about +20% scoring time on a 349-product sample; no behavior effect |
| N8 232059 probiotic total moves through a generic-module edit | for Sean: removing the leak leaves the approved probiotic model's own result (`applicability_unestablished`, Evidence 0) |
| N9 alias rule | no false-positive path found; title leak closed by defect 10 |
| R2-S2 an identity-bearing heading (the input contract resolves the heading itself to an identity) passes the prominence gate for any record | kept, recorded for Codex: the input contract's `identity_bearing_blend_header_mass` decides that the heading total is that identity's amount; real anchors through this branch in the reviewer's sample were all single-identity rows (Lion's Mane 1 g, Red Yeast Rice, Honey 7 g, a BCAA aggregate, Probiotics). Superseded by the Codex audit: edited Sensoril headings reproduce the source defect and actual 321351 borrows its UC-II member floor from the larger total; see accepted corrections below |
| R2-N1 owner-abstain floor can still anchor a heading total | same as baseline; recovery/collagen recover nothing when the owner abstains |
| R2-N2 brand-named multi-member headings (48 in the raw corpus: BioCell, Relora, Nitrosigine, TamaFlex, Tesnor, Sytrinol, Lutemax, Curcumin C3) | historical behavior protection for whole-formula headings; no blanket clinical-applicability approval. Named intervention/preparation applicability still requires Phase 3 per-entry review |
| R2-N3 product-level recovery still matches title-inclusive text, now with three new brand-identifier keys (bcm-95, uc-ii, egb 761; the reviewer's fourth, ester-c, was already reachable through the record id) | adds points only; the floor's heading gate reads the heading's own text |
| R2-N4 prominence read with `module=None` on sports/fiber | consistent with the existing `evidence_owner_canonicals` call |
| R2-N5 `nutrition_authority_canonical` metadata can appear where the baseline's higher floor pre-empted it | superseded: the authority helper is now the baseline's plus the lent rule |
| R2 stale docs (owner_eligibility, p8, p133 docstrings; generic.py opt-in comment) | fixed in `9ea4af85`; `numerical_ownership_20260930/README.md` names `_mass_dominant_essential_canonical`, which exists again |

Measured results and reproduction commands are added when each receipt exists.

## Codex independent audit — October 1

### Owner Check and scope

- Owner: `scripts/scoring_input_contract.py::derive_product_scoring_evidence` — evidence: raw source-path tracing, existing `identity_bearing_blend_header_mass_from_nested_child` reason and `is_lent_blend_mass` consumers. A heading literally named after one immediate member cannot disclose that member's amount when the same heading totals multiple physical members. Canonical identity alone does not establish preparation equivalence.
- Owner: `scripts/scoring_v4/modules/generic_evidence.py::_is_prominent_anchor` — evidence: verified branded record predicates and production `_primary_mass_floor` callers. A multi-member total naming a branded intervention among its immediate children is not that intervention's dose. Whole branded formulas remain eligible through the same owner.
- Owner: `scripts/tests/test_canonical_id_e2e_continuity.py::test_label_active_projection_retains_its_source_provenance` — evidence: old protein fixture no longer produced a projection on main; fresh Jarrow extraction exercises the same production provenance assertions.
- **Will NOT create:** a scorer, classifier, field, clinical registry, benchmark, config magnitude or export contract. No curated data changed. Six maxima and public contracts unchanged.

### Reproduced defects and accepted fixes

1. Renaming the 250 mg Stress-Reducing blend in raw `328062` to Sensoril allowed undosed Sensoril plus L-theanine to use the entire total for an Evidence floor. Four edited variants include a second preparation sharing the same canonical identity. The source owner tags literal member-named totals with its existing lent-mass reason; the branded-floor consumer also rejects immediate-member borrowing before the prominent-row shortcut.
2. Physical child rows, not distinct canonical IDs, establish multiple members. Immediate children are distinguished from deeper constituents; repeated source links are deduplicated. Single interventions remain unchanged.
3. The initial wider canonical-based prototype incorrectly demoted named whole preparations (Mirtogenol and Boswellia phytosome). The 186-label raw replay exposed this despite green unit tests. **That prototype (`d17257ca`) and its 28 score movers were rejected.** Final `9f7837e8` narrows source tagging to literal declared member names; explicit whole-preparation regressions preserve baseline floors. This is behavior preservation, not clinical research approval.
4. The stale canonical-provenance test now uses fresh Clean→Enrich extraction and retains its original provenance assertions; explicit test passed (1 passed, 18 deselected). Default fast skips this slow module, so it was run separately.
5. The full checkpoint exposed a stale archetype expectation: `probiotic__failure` lists live L. acidophilus without a specific strain, CFU or clinical matches, but expected generic species Evidence 10. Main reproduced that old award; the corrected species-recovery owner gives Evidence 0 and total 20 rather than 30, with every other projected value identical. `086a8938` updates only those three expected values; it changes no scorer. Failed-test rerun: 1 passed; complete archetype suite: 41 passed. This is a justified expectation migration, not an Evidence policy change.

### Accepted measurements and provenance

Durable receipts: `/Users/seancheick/pg_quality/prominence_20261001/codex_audit/`.
Both baselines use `b43a048f`; both candidates use clean source `9f7837e8`.
Every capture exited zero, preserved source hashes during capture and processed its expected count.

| Frozen input | Baseline output SHA256 | Candidate output SHA256 | Result |
|---|---|---|---|
| 186 affected actual raw labels | `29b25bb16be178c12c77ce07e6b6fe650f57c53922af5f0afd309b62067036ea` | `07366237f8e129bc50c186ac3a5b9f2240ab12bbf3924da89eac139f9df8ca10` | 185 complete captured payloads identical; one explained Evidence-only mover |
| 15 controls/adversarial cases | `1de1f1192f613498f6cd661d955e43045e4a6957e50443b913b6c2c235792094` | `bb79ea578b9a53a4a6a63252382bbc6e42b89aa966024a173b385ab5db91361c` | eleven identical; four edited member headings lose invalid floors |

The sole real mover is **321351 Multi-Sourced Collagen Turmeric Apple Cinnamon Flavor**:
raw 10 g Collagen Type I, II, & III Blend contains undosed Bovine Hide Collagen Peptides and UC-II.
Total **70.4→54.8**, Evidence **20→4.4**, primary floor **18→0**; clinical points **4.0 unchanged**,
Dose **6.7 unchanged** and other pillars unchanged. Standalone UC-II preparation control `321604`
retains its floor of 18. Four synthetic variants (IDs 990001–990004, explicitly edited from 328062)
move 72.8→60.6 or 56.8; only invalid Evidence floors leave. Synthetic IDs are not catalog products.
Captured status, routes and safety gates are unchanged. The replay format does **not** include final
`v4_verdict`; this is not a full final-verdict/export audit. Release acceptance still requires that check.

Claude's four frozen cohorts contain **7,015 distinct IDs: 7,012 raw DSLD labels and three submission
fixtures**, not 7,052 distinct products (that is summed assignments). Input manifests were independently
hash-checked with zero mismatches. Of 15,414 current raw labels, 8,402 are outside these cohorts.
Sampling coverage is not a completed corpus run or clinical review.

### Verification and remaining work

- Narrowed production-boundary protections: **53 passed**, `narrow_focused.log`.
- Fresh independent reviewer accepted the narrowed scope; broader ambiguity is not declared solved.
- First completed full fast: **1 failed, 17,961 passed, 167 skipped**, `fast_narrow_final.log`; the sole failure was the obsolete probiotic archetype expectation above.
- Rerun at `086a8938` was deliberately interrupted (6,466 passed, 110 skipped) after reproducing the cross-unit defect below; it is not a completed checkpoint. Final checkpoint completed at `b0c51483` (production code unchanged from `c6ea928d`): **17,823 passed, 307 skipped, zero failures and zero expected failures**, exit zero, `fast_audit_final.log`. Skips include missing stored artifacts and Node-dependent console checks; this is not release validation. Earlier interrupted runs and missing stored-corpus fixture failures do not count as passing checkpoints.
- Main integration, latest Claude reconciliation, full corpus, calibration, Flutter and release remain pending.

**Observed baseline issue, separate from this correction:** a single Sensoril intervention with a
Withanolides grandchild links its evidence only to the marker path. Probe: edit raw 328062 to a single
Sensoril child, then add Withanolides 1.25 mg below it; baseline and corrected floor remain zero, while
without the marker the floor is 18. Owner trace: `enrich_supplements_v3.py::_collect_evidence_data` /
`generic_evidence.py::_unambiguous_non_structural_source_ref`. High confidence in the source-ref behavior;
clinical preparation applicability needs review. Do not silently borrow the parent amount to repair it.

**Latest Claude findings awaiting reconciliation:** `9a6eb7c9` restores collagen's relative-mass gate
because a reviewed peptide minimum could read another heavier collagen preparation's amount;
`5b8cc834` restores declared BCAA aggregate recovery. These are beyond the pinned Codex candidate.
D26 now has four retained legacy comparisons on that latest source. Relative mass is not a reviewed
clinical benchmark; the next transfer packet must bind an actual studied minimum to the matched
preparation and use the existing Dose owners. Removing Evidence gates without an amount owner or
implicitly approving new numerical policy remains prohibited.

### Additional reproduced unit-selection defect

Owner: `scripts/scoring_v4/modules/generic_evidence.py::_dose_map` / existing `_convert_unit` — evidence: `test_evidence_source_dose.py` failed with 300 mg selected over 10 g. Alias fallback compared raw numbers across compatible mass units. `c6ea928d` converts the previous amount into the incoming unit before comparing, preserving original selected tuples and exact source keys. It invents no benchmark or activity-to-mass equivalence. Unrecognized/incompatible dimensions retain prior behavior; preparation binding remains unresolved separately.

Failing-first unit regression: 1 failed / 1 passed; focused amount, serving, prominence, blend and archetype checks: **143 passed**. Fresh reviewer independently accepted both orders, g/mg, mcg/mg, plural DSLD spellings, exact-source selection and missing-source refusal. Stored-source discovery found twelve potentially affected labels. Frozen Clean→Enrich→Score replay at baseline `086a8938` and candidate `c6ea928d`: all twelve complete captured payloads identical, output SHA256 `8e666321a8aeb6be7c66b410bbb250a92f82064066800f24e76b32d6dc298830`. New 186-label capture at `c6ea928d` is identical to `9f7837e8`, output SHA256 `07366237f8e129bc50c186ac3a5b9f2240ab12bbf3924da89eac139f9df8ca10`. All metadata records complete coverage, exit zero and unchanged source. This discovery is not clinical coverage or release validation. Final full fast ran after Claude's broad suite finished and passed as recorded above.

### Latest Claude checkpoint failures classified independently

Claude's recorded final fast: **5 failed, 17,991 passed, 126 skipped**. One is the probiotic expectation fixed above. Three direct-name canaries fail only because their symlink paths differ from the physical paths returned by the manifest owner: Codex reproduced all three with temporary links to the real main artifacts, then `b0c51483` applies `path.resolve()` before comparing. All three clinical identity assertions pass unchanged; temporary links were removed, with no source-artifact edits. Owner: `stage_manifest.py::select_stage_input_files` (physical artifact ownership); consumer: `test_probiotic_structured_form_identity.py::test_real_direct_name_generic_form_controls`. The final failure is a 120-second citation-parser timeout, not a failed subject assertion; its focused rerun passes (1 passed, 14 deselected), without changing clinical data or timeout policy. The isolated final complete checkpoint passed as recorded above; this does not validate later Claude source.

Final fetch before closing this pinned audit: main remains `e8687b3983903443d46951d26ab6067ef828c12b`; Claude feature is now `002d2683`, with new production change `68cae99a` preserving recovery rules for non-owner-scoped callers. That source is outside the pinned audit and requires reconciliation and fresh validation before integration.
