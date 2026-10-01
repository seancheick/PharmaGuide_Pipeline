# Phase 2 — generic Evidence prominence ownership

Status: **IN PROGRESS — implementation committed, Claude validation underway (frozen replay, fresh
review and full fast checkpoint pending); Codex audit/integration pending.** Branch
`claude/generic-prominence-ownership` from main/origin `e8687b39`, pushed as a feature branch for
tracking only. Not merged to main, no catalog release. Measured numbers are added below only from
receipts.

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
- Approved probiotic model input: `scripts/scoring_v4/modules/probiotic_evidence.py` reads
  `resolved_clinical_matches` without owner scoping; this batch leaves that path unchanged (defect 19).
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
| Recovery identity exclusions (collagen, DRI, module-owned), blend-anchor rule, protein every-source rule | same | 2 | retained unchanged |
| Recovery for callers that are not owner-scoped (approved probiotic model, omega, multi, readiness, confidence) | same, `_is_clear_primary_recovery_row` | 1, but feeding approved models | **kept unchanged** (`68cae99a`, defect 19): only owner-scoped generic/sports/fiber Evidence moves to the role owner here; moving the others changes the approved probiotic model's inputs and needs its own measured decision |
| Collagen peptide "mass >= 0.5 x max" | `_has_primary_collagen_peptide_identity` | 1 (selection) + 3 (exposure; first classed 1 only, corrected after round-3 review) | selection: prominent peptide row with own non-lent mass; the baseline comparison is **retained unchanged** as collagen's stand-in (D26): the record's 2,500 mg minimum is read from the heaviest "collagen" row, not the peptide row |
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
| 6 | **Withdrawn.** First classed as "generic recovery lends species records to live probiotic rows (232059)". The full fast checkpoint's locked fixture `probiotic__failure` showed it is the approved probiotic model's designed input (same species record on the organism row); the guard (`5c549d1a`) is superseded by defect 19 | — | — |
| 7 | Recovery re-stamped a record enrichment already linked to the same row, narrowing its refs (Garlic Powder 217818, Multi-Oil 1838) | recovery skips an existing record already linked to that row | `test_real_recovery_never_restamps_a_record_onto_a_row_it_already_links` |
| 8 | Found by the frozen raw replay: the floor's prominence check also dropped a blend heading that IS the branded intervention ("Relora 175 mg", 293928: baseline floor 17 → 0), while correctly dropping member records under a heading total | `_is_prominent_anchor`: a `blend_anchor_mass` heading carries only a verified product-level record the heading names (the product-level recovery predicate), on a row the role owner marks prominent | `test_real_heading_that_names_its_brand_anchors_that_brands_floor`; Ravage creatine module added to `test_real_blend_total_never_becomes_an_undisclosed_members_floor` |
| 9 | Product-level predicate built brand keys from the record id only: `BRAND_UCII` → "ucii", label "UC-II" → "uc ii" (also BCM-95, EGb 761), so UC-II's heading (321604, baseline floor 18) could not name its record | `_verified_product_entry_matches_text` also accepts an alias that is the identifier itself once separators are removed; descriptive aliases stay excluded; floor gate reads the registry record | `test_a_brand_identifier_matches_as_labels_spell_it`, 321604 case of the heading test |
| 10 | Fresh review B1: the heading gate's identity text included the product title, so retitling 328062 "Sensoril Sleep Tonight" let its 250 mg two-member blend total anchor Sensoril's floor (0 → 18) | heading gate reads `_row_identity_text(..., with_product=False)`; product-level recovery keeps its title-inclusive text | `test_a_title_naming_a_brand_never_lends_a_blend_total_to_that_member` |
| 11 | Fresh review S1/S3/S4: the authority floor had dropped its heaviest-owner amount check (lent "Epsom Salt" blend total 273823/40604; fiber-route Fiber+Calcium 177088 with no Dose DRI reader; counter-ion calcium in "Calcium BHB" 311247–311250) | heaviest-owner check retained as exposure stand-in (D26), anchor must be prominent and non-lent | `test_authority_floor_keeps_the_heaviest_declared_owner_exposure_stand_in`, `test_real_authority_floor_needs_the_heaviest_owner_with_its_own_amount` |
| 12 | Fresh review S2: recovery's own-amount check (`_mass_mg > 0`) admitted a blend total lent to a member (fucoPROTEIN 40581 "Milk Protein" ← 15 g four-member blend); collagen recovery had the same hole | recovery and collagen refuse `is_lent_blend_mass` rows | `test_recovery_never_reads_a_blend_total_lent_to_a_member` |
| 13 | Found in the final-source preview replay: the row-level prominence check added to the authority floor (`32765afe`) lost vitamin C's authority on Calcium Ascorbate 1 g (306193): the title names the "Calcium Ascorbate" row, the heaviest vitamin C row is the "Vitamin C 900 mg" line | baseline helper restored unchanged + lent-mass rule (`7ea61daa`) | `test_real_authority_floor_reads_purpose_by_identity_not_by_row` |
| 14 | Fresh review round 2 S1: the floor required any linked row to be prominent but took the stand-in amount over all linked rows, so a melatonin 1 mg match also referencing L-theanine 400 mg floored at 14 (baseline did the same) | stand-in amount comes only from rows that pass the prominence gate (`46ca2145`) | `test_the_retained_stand_in_reads_the_prominent_rows_own_amount` |
| 15 | Fresh review round 2 S3: recovery's half-heaviest comparison was deleted as prominence while the identical floor comparison was retained as uncovered exposure | retained unchanged in recovery (`46ca2145`); collagen's stays removed (record minimum) | `test_ingredient_recovery_keeps_the_retained_exposure_stand_in` |
| 16 | Found by the final replay of `9ea4af85`: the defect-14 fix also dropped the anchor's own same-identity rows, so Sambucus (204048, 242865: 250 mg elderberry extract with a nested "Elderberries 16 g" source row) lost its baseline floor 6.6 | stand-in reads every linked row of the prominent anchor's identity, never another identity's (`b43a048f`) | `test_real_the_stand_in_keeps_reading_the_purposes_own_identity_rows` |
| 17 | Fresh review round 3 B1: with collagen's comparison removed, a 300 mg peptide row beside a 10 g non-peptide "Bovine Hide Collagen" row recovered the collagen record (baseline: nothing); the 2,500 mg minimum reads the heaviest "collagen" row | comparison restored as collagen's retained stand-in (`9a6eb7c9`) | `test_collagen_recovery_keeps_the_retained_exposure_stand_in` |
| 18 | Found by the raw-coverage replay of `b43a048f`: four Essential Amino Complete labels (220827, 220956, 221014, 259615) lost their BCAA floor 9.35. "Branched-Chain Amino Acids 5 g" discloses leucine 2.5 g, isoleucine 1.25 g, valine 1.25 g; the no-re-stamp rule (defect 7) blocked recovery's designed re-binding of the BCAA mixture record to that aggregate | the rule leaves the admitted aggregates (disclosed BCAA or protein totals) alone (`5b8cc834`) | `test_real_bcaa_record_still_binds_to_its_disclosed_aggregate` |
| 19 | Found by the full fast checkpoint at `90d0d741`: the locked archetype fixture `probiotic__failure` (Evidence 10 → 0) and 232059 (13 → 0) lost the species record the approved probiotic model reads through `resolved_clinical_matches` without owner scoping; removing the guard alone would instead add one the baseline never gave (236913, La-14 at 0.5 mg: Evidence 0 → 10) | callers that are not owner-scoped keep the previous ingredient and collagen recovery rules unchanged (`_is_clear_primary_recovery_row` restored for them); guard removed (`68cae99a`) | `test_real_probiotic_model_inputs_stay_as_approved` (236913, 232059); `test_v4_archetype_fixtures` passes again |

## Decision packet D26 — the retained exposure stand-ins

Four comparisons are retained, all unchanged from `e8687b39`: the primary floor's half-heaviest
anchor mass, recovery's and collagen recovery's identical half-heaviest row mass, and the authority
floor's "the heaviest owner is the essential". The fresh reviews showed each is an exposure judgment
no Dose owner makes for every route: 199 of 210 records carry no studied minimum, and only generic Dose reads DRI
adequacy (`generic_dose.py` 29 references, `sports_dose.py` and `fiber_digestive_dose.py` 0).

**Question for Sean.** The primary-evidence floor now chooses its anchor from the shared role owner,
but still requires the anchor to carry half the heaviest competing active's mass. That comparison is
not prominence; it is the only thing that stops a strong floor from rewarding a trace amount when the
record has no studied minimum (`min_clinical_dose`: 11 of 210 records at `e8687b39`) and no Dose owner judges that
ingredient's exposure. Removing it now would move amount judgment out of Evidence with no owner taking
it, which the transfer invariant forbids; keeping it keeps a mass demotion of declared purposes, the
pattern D24 rejected for Dose.

- **R (implemented, status quo for these gates):** keep all four stand-ins until Dose owns per-ingredient
  exposure for every anchor (or the record carries a reviewed studied minimum) and every route that
  uses the authority floor reads DRI adequacy.
- **P (measured counterfactual, not implemented):** remove all four. Declared trace purposes then
  earn full floors and recovered records (collagen included) regardless of amount, and any declared essential earns the
  authority floor beside a heavier co-purpose — see the measured classes below.
- **C (rejected by the transfer packet):** keep it only for anchors without DRI/Dose coverage. The
  transfer README forbids record allowlists and route-specific exceptions for this transfer.

Unblocking work, already queued elsewhere: Phase 3 studied-minimum curation per record (Q39(g)) and
Phase 4 Dose policy packets (D24). Either retires the stand-in without a magnitude decision here.

**Measured counterfactual P** (all four stand-ins removed in a scratch worktree at `9d65403f` by
`counterfactual_patch.py`; compared with the final candidate on the same frozen inputs):

| Cohort | Totals that move | Direction | Tier crossings | Size |
|---|---|---|---|---|
| Targeted 2,781 (output `cbb9489d…5c20`) | 793 | all up | 347 (Needs improvement→Good 166, Good→Very good 113, Poor→Needs improvement 38, Very good→Excellent 17, NI→Very good 10, others 3) | median +4.4; 341 ≥ +5; 64 ≥ +10; max +16 |
| Raw coverage 2,964 (output `333c5336…a87c`) | 22 | all up | 12 | median +5.9 |

New floors under P are led by vitamin D3 (211 targeted labels), creatine monohydrate (91),
vitamin C (65), biotin (39), calcium (28), melatonin (22) and magnesium (20); new authority floors
by vitamin C (65), zinc (9), choline (7) and chromium (6). The vitamin D3 class is mostly
"Calcium 500–600 mg with Vitamin D" labels (e.g. 4226, 8836, 8955), where P moves the floor from
calcium 14 to the vitamin D3 consensus 18 (+4.4 total). It cuts both ways: raw mass ranks any
microgram-scale vitamin D3 as trace beside grams of calcium, yet the same class includes 12054
"Calcium + Vitamin D 600 mg/125 IU" (3.1 mcg, about a fifth of the RDA), which P would also float
to 18. Generic Dose judges D3 against its RDA, but the Evidence floor would not see that judgment.
Removing the stand-ins therefore needs per-ingredient exposure from Dose (or reviewed studied
minima) feeding the floor, not a different fraction. Sports (96 movers) and fiber (11) have no DRI
reader at all.

## Progress

| Step | State | Receipt |
|---|---|---|
| Failing-first regressions | done | RED `~/pg_quality/prominence_20261001/red_baseline.log` (11 failed / 7 protections passed), `c3_probiotic_red.log`, `c4_rerecovery_red.log` |
| Source commits | done | `eb70f424`, `2ce48b21`, `5c549d1a`, `2d9ede38`; after the first replay `c4119d30`, `916d0c62`; after review round 1 `32765afe`, `db939b57`, `41eb22d7`, `452a618e`; after the preview replay and review round 2 `7ea61daa`, `46ca2145`, `9ea4af85`; after the final replay of `9ea4af85` `b43a048f`; after review round 3 and the raw-coverage replay `9a6eb7c9`, `5b8cc834`, `9d65403f` (**final source**). RED logs (`~/pg_quality/prominence_20261001/`): `red_baseline.log` 11 failed, `c3_probiotic_red.log`, `c4_rerecovery_red.log`, `c6_heading_red.log` 2, `c7_brand_identifier_red.log` 4, `c8_review_red.log` 6, `c9_authority_red.log` 1, `c10_review2_red.log` 2, `c11_identity_red.log` 1, `c12_collagen_red.log` 1, `c13_bcaa_red.log` 1; GREEN focused `c13_bcaa_green.log` 149 passed |
| Focused + consumer tests | done (exploratory) | focused 308 passed; 90 consumer files 2,698 passed / 38 skipped; one artifact test fails identically on `e8687b39` |
| Frozen targeted replay (2,781 raw labels) | first pass at `2d9ede38` (170 moved) superseded; preview at `452a618e` (34 moved, every mover classified) superseded by defect 13–15 fixes; run on `9ea4af85` (17 moved, all down) found defect 16 and is archived in `superseded_9ea4af85/`; final run on `b43a048f` running from the isolated checkout `prominence-final` | manifest `2b314063…`; baseline `9ba85f1a…` (head `e8687b39`). Two runs were aborted: one by my own docs commit changing HEAD in the measured worktree (the harness checks HEAD), one stopped for a source change |
| 1,259-label control replay | done at `2d9ede38` (1,251 identical; 232059 Evidence 13→0; 7 readiness-only); final run on `9ea4af85` queued | Codex manifest `cbe04144…`; baseline = Codex capture `a20cea18…` (head `3ee91eae`, all 434 source hashes equal to `e8687b39`) |
| Brand-identifier cohort (every raw label naming UC-II, BCM-95 or EGb 761: 48) | done at `916d0c62` | manifest `4f62f9a2…`; baseline `66a228a2…`, candidate `b7dea4de…`: 47 identical, 219249 TamaFlex readiness lists `BRAND_UCII` for its "UC-II Type II Collagen Complex 20 mg" adjunct row (score unchanged) |
| D26 counterfactual (P arm) | done | scratch worktree `prominence-parm` at `9d65403f` with all four stand-ins removed (`counterfactual_patch.py`), never committed; results in the D26 packet |
| Fresh-context review | round 1 (`e8687b39..916d0c62`): 1 blocker + 4 should-fix, all reproduced and fixed (defects 10–12). Round 2 (`e8687b39..452a618e`, fresh agent): no blocker; S1 and S3 reproduced and fixed (defects 14–15); S2 recorded below; its 400-label raw sample found 0 authority-subset violations and 1 intended down (79192 caffeine floor on a lent 243 mg blend total). Review of `7ea61daa` onward pending; round 3 (`e8687b39..b43a048f`, fresh agent): 1 blocker (collagen borrow, defect 17) and 1 should-fix (non-owner-scoped recovery, measured: no effect), both resolved | probes `scratchpad/probe4.py`, `probe9.py`, `scratchpad/review2/`, `scratchpad/review3/` |
| Full fast checkpoint | pending | |

| Second cohort (raw-only coverage) | running | The targeted cohort came from stored-corpus movers and missed raw-only movers (273823/40604 were absent). Added every label not yet frozen whose raw label prints a blend total over an undisclosed member (1,464) plus a seeded random 1,500 of the remaining 9,902; manifest `6a4b4807…`. 8,402 labels stay unreplayed; the random sample estimates their mover rate |

## Fresh review notes and disposition

| Note | Disposition |
|---|---|
| N1 floor tests prominence and mass over linked rows separately | kept: linked rows are one record's identity rows; the stand-in is the baseline's max over them, unchanged by design (restoring it fixed the Sambucus 204048 regression) |
| N2 a prominent heading row is not structurally checked | kept: a heading the role owner itself names as a subject (e.g. a fiber-route "Fiber Blend" whose identity is fiber) is that row's own amount; recorded for Codex |
| N3 stand-in denominator can be a heading total | pre-existing baseline denominator, retained unchanged (D26) |
| N4 `eb70f424` changes roles for every consumer, including the enricher | measured by the raw replays (Clean→Enrich→Score), not the stored-corpus A/B |
| N5 one synthetic test passed on the baseline | it is a protection, counted among the 7 baseline-passing protections |
| N6 stale comments | fixed in `452a618e` |
| N7 repeated owner selection per score | about +20% scoring time on a 349-product sample; no behavior effect |
| N8 232059 probiotic total moves through a generic-module edit | resolved: it no longer moves (defect 19); the approved probiotic model's inputs are unchanged |
| N9 alias rule | no false-positive path found; title leak closed by defect 10 |
| R2-S2 an identity-bearing heading (the input contract resolves the heading itself to an identity) passes the prominence gate for any record | kept, recorded for Codex: the input contract's `identity_bearing_blend_header_mass` decides that the heading total is that identity's amount; real anchors through this branch in the reviewer's sample were all single-identity rows (Lion's Mane 1 g, Red Yeast Rice, Honey 7 g, a BCAA aggregate, Probiotics). A heading named for one member of a multi-member blend would be a contract defect (synthetic only) |
| R2-N1 owner-abstain floor can still anchor a heading total | same as baseline; recovery/collagen recover nothing when the owner abstains |
| R2-N2 brand-named multi-member headings (48 in the raw corpus: BioCell, Relora, Nitrosigine, TamaFlex, Tesnor, Sytrinol, Lutemax, Curcumin C3) | acceptable: the heading total is the studied composite formula; the docstring now says the contract decides |
| R2-N3 product-level recovery still matches title-inclusive text, now with three new brand-identifier keys (bcm-95, uc-ii, egb 761; the reviewer's fourth, ester-c, was already reachable through the record id) | adds points only; the floor's heading gate reads the heading's own text |
| R2-N4 prominence read with `module=None` on sports/fiber | consistent with the existing `evidence_owner_canonicals` call |
| R2-N5 `nutrition_authority_canonical` metadata can appear where the baseline's higher floor pre-empted it | superseded: the authority helper is now the baseline's plus the lent rule |
| R2 stale docs (owner_eligibility, p8, p133 docstrings; generic.py opt-in comment) | fixed in `9ea4af85`; `numerical_ownership_20260930/README.md` names `_mass_dominant_essential_canonical`, which exists again |
| R3-B1 collagen borrow | fixed, defect 17 |
| R3-S1 recovery for callers that are not owner-scoped (omega, multi, probiotic, readiness, confidence) used role-owner prominence instead of "single scorable or title regex" | resolved by keeping the previous rule for those callers (defect 19): its first measurement showed no effect only because the organism guard blocked probiotic rows |
| R3-N1 authority ⊆ baseline holds for a fixed owner set; `eb70f424` can change the owner set | every authority change in every arm is listed; the targeted arm has none, the owner-set additions moved no authority |
| R3-N2 identity-scoped numerator still counts same-canonical structural rows (compound duplicate) | same as baseline (pre-existing); recorded for Codex |
| R3-N3 `_dose_map` compares raw quantities across units (300 mg beats 10 g for one identity key) | pre-existing defect in the clinical-dose gates, outside this batch: separate measured task offered ("Fix cross-unit comparison in generic Evidence dose map") |
| R3-N4 tests identical on baseline | `test_collagen_recovery_follows_prominence` is a protection; defect 17's test is the RED pin |
| R3-N5 stale docstrings | fixed in `9d65403f`; D26 count updated |
| Raw-coverage single-member blend (241676 Collagen Love: "Collagen Peptide Hydro-Matrix Blend 600 mg" with one undisclosed member) | the input contract marks the total as lent and Dose readers follow it, so Evidence does too; whether a single-member heading's total is its member's amount is a contract question for Codex |

## Measured results (final source `9d65403f`; `0cf9262e` is comments only, AST identical)

> **Being re-measured.** The full fast checkpoint at `90d0d741` found defect 19; source `68cae99a`
> keeps the approved probiotic model's inputs unchanged. Every arm is replaying on `68cae99a` now.
> The figures below are from `9d65403f`, where 232059 still moved (13 → 0); it is expected to
> drop out. This note is replaced when the new receipts exist.

All arms are complete Clean→Enrich→Score captures of frozen raw DSLD labels with
`scripts/audits/quality_redesign/replay.py`; every capture reports `exit_code 0`,
`source_unchanged true`, full product coverage and the same input manifest as its baseline.
Baselines ran on `e8687b39` (clean detached worktree `prominence-base`); candidates on the
isolated detached worktree `prominence-final` at `9d65403f`. Outputs live in
`~/pg_quality/prominence_20261001/`; every changed product of every arm is listed with its
cause columns in `replay_*_changed.md` in this folder (produced by `classify_movers.py`).

| Arm | Inputs (manifest SHA-256) | Baseline output | Candidate output | Result |
|---|---|---|---|---|
| Targeted, 2,781 labels | `2b314063…5c41c` | `9ba85f1a…2b5` | `86e0e44d…0437` | 2,653 identical; 15 totals move, **all down**; tiers Good→Needs improvement 2, Needs improvement→Poor 2; 113 metadata-only |
| Controls, 1,259 labels (Codex set) | `cbe04144…8286` | Codex `a20cea18…ea72` (head `3ee91eae`; all 434 source hashes equal to `e8687b39`) | `42de5e4a…3553` | 1,251 identical; 232059 Evidence 13→0; 7 readiness-metadata-only (omega/probiotic) |
| Brand identifiers, 48 labels | `4f62f9a2…55ea` | `66a228a2…b5a` | `b7dea4de…7d7` | 47 identical; 219249 readiness lists `BRAND_UCII` on its "UC-II Type II Collagen Complex 20 mg" adjunct row |
| Raw coverage, 2,964 labels | `6a4b4807…086a` | `cohort2_baseline` | `3df7e371…54b9` | 2,908 identical; 52 totals move, **all down**; tiers Good→Needs improvement 6, Needs improvement→Poor 7; 4 metadata/no-score |
| D26 counterfactual (four stand-ins removed) | targeted + raw coverage | final candidate | `cbb9489d…5c20`, `333c5336…a87c` | 793 and 22 totals up, none down (D26 packet) |

Every arm: Evidence is the only pillar that moves; status, route, Safety/Hygiene, Dose,
Formulation, Transparency and Verification are unchanged for every product. In total 67
distinct products move (15 targeted, 52 raw coverage; 232059 appears in both the targeted and
control arms), all down, 17 crossing a quality tier.

**Coverage.** The raw-coverage cohort holds every raw label (of 15,414) not already frozen whose
label prints a blend total over at least one undisclosed member (1,464 → 52 movers) plus a seeded
random 1,500 of the other 9,902 labels (→ **0 movers**). The 8,402 labels never replayed all lack
that structure; 0 of 1,500 bounds their mover rate below about 0.2% (rule of three).

### Every product whose score moves

| ids | products | total | Evidence | cause |
|---|---|---|---|---|
| 219048, 219049, 270532, 317119, 333746 | Fiber Fusion Daily | e.g. 75.8 → 61.8 (Good → NI) | 20 → 6 | psyllium floor 18 rested on the 3.1 g four-fiber blend total (defect 2) |
| 79233, 227922, 230979, 76540 | Thisilyn Daily Cleanse / Cleanse Part II / Part II Digestive Health / Fiber Formula | e.g. 71.8 → 57.8 | 20 → 6–10 | psyllium floor 18 on 1.3–3.4 g five- or six-fiber blend totals (defect 2) |
| 328062 | Sleep Tonight | 72.8 → 59.7 (Good → NI) | 20 → 6.9 | Sensoril floor 18 on the 250 mg two-member blend total (defect 2) |
| 2219, 28981 | Ravage Grape / Fruit Punch | 30.7 → 22.0 | 20 → 11.3 | creatine floor 18 on the 3.1 g ten-member creatine module total (defect 2) |
| 2221, 36992, 42235, 42236, 42237, 63923 | Re-Built Mass (six flavors) | −6.1 to −7.8 | 20 → 12.2–13.9 | creatine floor 18 on the 10 g ten-member "Advanced Creatine Complex" total (defect 2) |
| 28973 | ReBuilt Mass Chocolate | 67.6 → 63.2 | floor 18 creatine → 14 protein | same creatine complex total; the protein floor (its own disclosed amount) remains (defect 2) |
| 74753, 176055 | Amplified Creatine XXX | 38.7 → 29.8 | 18 → 0 floor | creatine floor on the 10 g six-member "Micronized Creatine Matrix Blend" total (defect 2) |
| 40581, 40595 | fucoPROTEIN | 62.0 → 53.6, 62.4 → 54.0 (NI → Poor) | 15.6 → 7.2 | protein floor 14 on the 15 g four-member protein blend total (defect 2) |
| 37217, 37224 | Rare Vanilla / Chocolate Fudge | 48.3 → 43.3 | 12.2 → 7.2 | glycine floor 11 on the 6.2 g three-member "Creatine Precursors" total (defect 2) |
| 5773, 5820, 5883, 25594, 27420, 45104, 70327, 79192, 315848 | Thermo Igniter 12X / X12 / Ultra Energy Generator | −8.4 each (three NI → Poor) | floor 14 → 0 | caffeine floor on the ~240 mg three-member thermogenic blend total (defect 2) |
| 5817, 5863, 18473, 297644, 333753 | Amplified Muscle Igniter 4X / FYI / Kidney Bladder | −3.4 to −9.6 | floor 14 → 0 | ginger root floor on four- to seven-member herbal blend totals (defect 2) |
| 5816, 5873, 25593, 30565 | Amplified Maxertion N.O. / Muscle Fatigue Buffer | −3.7 | floor 6.6 → 0 | L-arginine floor on the two-member "PEG-Arginine System" total (defect 2) |
| 62116, 178632, 327953, 332914 | Echinacea & Goldenseal | −4.8 to −5.1 (two NI → Poor) | floor 9.35 → 0 | echinacea floor on two- to seven-member herbal blend totals (defect 2) |
| 40598, 273822 | Purify / Perfect Cleanse Purify | 65.1 → 61.4 | floor 14 → 0 | milk thistle floor on the 1 g six-member blend total (defect 2) |
| 184497, 199530 | Change-O-Life | 49.8 → 45.5 | floor 6.6 → 0 | black cohosh floor on the six-member blend total (defect 2) |
| 251338, 254958 | Centrum Immune & Digestive Support | 54.3 → 44.7 | floor 14 → 0 | inulin floor on the 400 mg three-member botanical blend total (defect 2) |
| 273825, 321361 | Raw Cleanse Organ Detox / Organ Detox | 52.9 → 48.9 | floor 11 → 0 | chlorella floor on the 2 g four-member greens blend total (defect 2) |
| 327398, 327399 | Grass Fed Collagen Protein | 48.7 → 39.1 | floor 14 → 0 | collagen-peptide floor on the 22 g four-member protein blend total (defect 2) |
| 82935 | Stress Hormone Balancing Blend | 55.4 → 43.8 (NI → Poor) | floor 14 → 0 | phosphatidylserine floor on the 400 mg two-member total (defect 2) |
| 251578, 251594, 308198, 323062 | Ex-Stress / Garlic Parsley / Glucosamine Chondroitin / Calming Day | −0.6 to −7.0 | floor → 0 | lemon balm, garlic, MSM and taurine floors on two- to six-member blend totals (defect 2) |
| 241676, 268562, 268575, 326268 | Collagen Love / Multi-Collagen Complex / Multi Collagen 1600 mg | −6.3 each (one NI → Poor) | 6.3 → 0 | collagen record recovered from a blend total lent to its first member (three four-member blends; 241676 has one member, see notes) (defect 12) |
| 232059 | Bifido GI Balance | 53.5 → 40.5 | 13 → 0 | generic recovery had lent a species record to a live organism row; the approved probiotic model's own result stands (defect 6) |

Each member keeps its Evidence ownership and research points; only the floor or recovered record
that read a blend total as the member's dose is gone. Exact per-product values:
`replay_targeted_changed.md`, `replay_raw_coverage_changed.md`, `replay_controls_changed.md`.

### Changes without a score movement

- Targeted 113: 102 readiness/confidence metadata from role materiality (defect 3; more disclosed
  rows are `material`) including the 20 BCAA labels, whose recovery now matches baseline;
  3 turmeric labels lose a narrowing re-stamp (defect 7); 3 valerian recoveries (315311, 333901,
  333903: a 200 mg major row with its own amount that passes the retained stand-in; points
  already covered); 6 owner-set additions (63330, 63475, 210738, 229547, 297666, 328292; defect 3).
- Raw coverage 4: 273823 and 40604 lose a magnesium authority floor that rested on the lent
  "Epsom Salt" blend total (their pipeline already exceeds 10); two floor-only changes with no
  total movement (classified in `replay_raw_coverage_changed.md`).
- Controls 7 and brand 1: readiness metadata as above.

### Reproduction

```
P=/Users/seancheick/.pyenv/versions/3.13.3/bin/python
R=scripts/audits/quality_redesign/replay.py
$P $R freeze-raw --raw-root ~/Downloads/PharmaGuide_Datasets/staging/brands --ids <ids.json> --frozen-root <F> --manifest <F>/manifest.json
$P $R snapshot --checkout <worktree at e8687b39> --products-root <F> --manifest <F>/manifest.json --out base.jsonl --workers 4
$P $R snapshot --checkout <worktree at b43a048f> --products-root <F> --manifest <F>/manifest.json --out cand.jsonl --workers 4
```

Id lists: `targeted_ids.json` (stored-corpus movers of every draft plus canaries),
`brand_identifier_ids.json`, `cohort2_ids.json` (`select_cohort.py` in this folder, seed 20261001).
The counterfactual arm is a scratch detached worktree at `b43a048f` patched by
`counterfactual_patch.py` (never committed). Classify with
`classify_movers.py <checkout> base.jsonl cand.jsonl out.json out.md`. Run snapshots only from a checkout nothing commits to: the harness also checks HEAD.
