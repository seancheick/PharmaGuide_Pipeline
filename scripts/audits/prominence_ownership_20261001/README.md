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
| Authority floor "heaviest owner is DRI-essential" | `_mass_dominant_essential_canonical` | 1 + 3 (first classed 1 only; corrected after fresh review) | **heaviest-owner comparison retained unchanged** as the authority's exposure stand-in (D26): only generic Dose reads DRI adequacy, sports/fiber Dose do not, and the transfer packet forbids route-specific exceptions. Prominence only narrows it: that heaviest owner must also be a prominent row with its own (non-lent) amount (`_prominent_essential_canonical`) |
| Recovery "mass >= 0.5 x max" + single-scorable/owner/title-regex primary | `_recover_verified_primary_ingredient_matches`, `_is_clear_primary_recovery_row` | 1 | prominent row with its own mass, never a blend total lent to it; helper deleted. Recovered records still pass the unchanged sub-clinical gates and, to anchor a floor, the floor's stand-in |
| Recovery identity exclusions (collagen, DRI, module-owned), blend-anchor rule, protein every-source rule | same | 2 | retained; probiotic organisms added via the identity owner |
| Collagen peptide "mass >= 0.5 x max" | `_has_primary_collagen_peptide_identity` | 1 | prominent peptide row with own (non-lent) mass; the recovered collagen record keeps its 2,500 mg minimum |
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

## Decision packet D26 — the retained exposure stand-ins

Two comparisons are retained, both unchanged from `e8687b39`: the primary floor's half-heaviest
anchor mass, and the authority floor's "the heaviest owner is the essential". Fresh review showed the
second is also an exposure judgment on sports and fiber routes, whose Dose modules read no DRI
adequacy (`generic_dose.py` 29 references, `sports_dose.py` and `fiber_digestive_dose.py` 0).

**Question for Sean.** The primary-evidence floor now chooses its anchor from the shared role owner,
but still requires the anchor to carry half the heaviest competing active's mass. That comparison is
not prominence; it is the only thing that stops a strong floor from rewarding a trace amount when the
record has no studied minimum (`min_clinical_dose`: 11 of 210 records at `e8687b39`) and no Dose owner judges that
ingredient's exposure. Removing it now would move amount judgment out of Evidence with no owner taking
it, which the transfer invariant forbids; keeping it keeps a mass demotion of declared purposes, the
pattern D24 rejected for Dose.

- **R (implemented, status quo for these gates):** keep both stand-ins until Dose owns per-ingredient
  exposure for every anchor (or the record carries a reviewed studied minimum) and every route that
  uses the authority floor reads DRI adequacy.
- **P (measured counterfactual, not implemented):** remove both. Declared trace purposes then earn
  full floors regardless of amount, and any prominent essential earns the authority floor beside a
  heavier co-purpose — see the measured classes below.
- **C (rejected by the transfer packet):** keep it only for anchors without DRI/Dose coverage. The
  transfer README forbids record allowlists and route-specific exceptions for this transfer.

Unblocking work, already queued elsewhere: Phase 3 studied-minimum curation per record (Q39(g)) and
Phase 4 Dose policy packets (D24). Either retires the stand-in without a magnitude decision here.

## Progress

| Step | State | Receipt |
|---|---|---|
| Failing-first regressions | done | RED `~/pg_quality/prominence_20261001/red_baseline.log` (11 failed / 7 protections passed), `c3_probiotic_red.log`, `c4_rerecovery_red.log` |
| Source commits | done | `eb70f424`, `2ce48b21`, `5c549d1a`, `2d9ede38`; after the first replay `c4119d30`, `916d0c62` (RED `c6_heading_red.log` 2 failed, `c7_brand_identifier_red.log` 4 failed); after fresh review `32765afe`, `db939b57`, `41eb22d7`, `452a618e` (RED `c8_review_red.log` 6 failed / 27 passed; GREEN focused 123 passed) |
| Focused + consumer tests | done (exploratory) | focused 308 passed; 90 consumer files 2,698 passed / 38 skipped; one artifact test fails identically on `e8687b39` |
| Frozen targeted replay (2,781 raw labels) | first pass done at `2d9ede38`; final re-run on `452a618e` running | manifest `2b314063…`; baseline output `9ba85f1a…` (head `e8687b39`), first candidate `0edd8dd2…`: 170 totals moved (153 up / 17 down), 0 status/route, Evidence pillar only. The stored-corpus exploratory A/B missed most of the 17 downs because stored enrichment predates the identity-bearing heading rows: raw replay is authoritative. Classification of the downs found defect 8 |
| 1,259-label control replay | done at `2d9ede38`; re-run on final HEAD pending | Codex manifest `cbe04144…`; baseline = Codex capture `a20cea18…` (head `3ee91eae`, all 434 source hashes equal to `e8687b39`); candidate `42de5e4a…`: 1,251 identical, 232059 Evidence 13→0 (defect 6), 7 omega/probiotic labels readiness metadata only (role materiality excludes the supplying-oil total, defect 3) |
| Brand-identifier cohort (every raw label naming UC-II, BCM-95 or EGb 761: 48) | done at `916d0c62` | manifest `4f62f9a2…`; baseline `66a228a2…`, candidate `b7dea4de…`: 47 identical, 219249 TamaFlex readiness lists `BRAND_UCII` for its "UC-II Type II Collagen Complex 20 mg" adjunct row (score unchanged) |
| D26 counterfactual (P arm) | running (scratch worktree `prominence-parm` at `452a618e`, both stand-ins removed, never committed) | |
| Fresh-context review | round 1 done on `e8687b39..916d0c62`: 1 blocker + 4 should-fix, all reproduced and fixed (defects 10–12; S4 resolved by the retained authority check) in `32765afe`, `db939b57`, `41eb22d7`, `452a618e`; notes dispositioned below; round 2 pending | reviewer probes `scratchpad/probe4.py`, `probe7.out`, `probe9.py` |
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
| N8 232059 probiotic total moves through a generic-module edit | for Sean: removing the leak leaves the approved probiotic model's own result (`applicability_unestablished`, Evidence 0) |
| N9 alias rule | no false-positive path found; title leak closed by defect 10 |

Measured results and reproduction commands are added when each receipt exists.
