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
| Authority floor "heaviest owner is DRI-essential" | `_mass_dominant_essential_canonical` | 1 | any prominent essential with own amount (`_prominent_essential_canonical`); Dose owns DRI adequacy |
| Recovery "mass >= 0.5 x max" + single-scorable/owner/title-regex primary | `_recover_verified_primary_ingredient_matches`, `_is_clear_primary_recovery_row` | 1 | prominent row with own mass; helper deleted |
| Recovery identity exclusions (collagen, DRI, module-owned), blend-anchor rule, protein every-source rule | same | 2 | retained; probiotic organisms added via the identity owner |
| Collagen peptide "mass >= 0.5 x max" | `_has_primary_collagen_peptide_identity` | 1 | prominent peptide row with own mass |
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
| 7 | Recovery re-stamped a record enrichment already linked to the same row, narrowing its refs (Garlic Powder 217818, Multi-Oil 1838) | recovery skips an existing record already linked to that row `test_real_recovery_never_restamps_a_record_onto_a_row_it_already_links` |

## Decision packet D26 — the primary floor's retained exposure stand-in

**Question for Sean.** The primary-evidence floor now chooses its anchor from the shared role owner,
but still requires the anchor to carry half the heaviest competing active's mass. That comparison is
not prominence; it is the only thing that stops a strong floor from rewarding a trace amount when the
record has no studied minimum (`min_clinical_dose`: 11 of 210 records at `e8687b39`) and no Dose owner judges that
ingredient's exposure. Removing it now would move amount judgment out of Evidence with no owner taking
it, which the transfer invariant forbids; keeping it keeps a mass demotion of declared purposes, the
pattern D24 rejected for Dose.

- **R (implemented, status quo for this gate):** keep the stand-in until Dose owns per-ingredient
  exposure for every anchor (or the record carries a reviewed studied minimum).
- **P (measured counterfactual, not implemented):** remove it. Declared trace purposes then earn full
  floors regardless of amount — see the measured classes below.
- **C (rejected by the transfer packet):** keep it only for anchors without DRI/Dose coverage. The
  transfer README forbids record allowlists and route-specific exceptions for this transfer.

Unblocking work, already queued elsewhere: Phase 3 studied-minimum curation per record (Q39(g)) and
Phase 4 Dose policy packets (D24). Either retires the stand-in without a magnitude decision here.

## Progress

| Step | State | Receipt |
|---|---|---|
| Failing-first regressions | done | RED `~/pg_quality/prominence_20261001/red_baseline.log` (11 failed / 7 protections passed), `c3_probiotic_red.log`, `c4_rerecovery_red.log` |
| Source commits | done | `eb70f424`, `2ce48b21`, `5c549d1a`, `2d9ede38` |
| Focused + consumer tests | done (exploratory) | focused 308 passed; 90 consumer files 2,698 passed / 38 skipped; one artifact test fails identically on `e8687b39` |
| Frozen targeted replay (2,781 raw labels) | running | frozen manifest SHA-256 `2b3140639883423bb75d2f0db750aeedad9ed2ceee052590caf259b20ee5c41c` |
| 1,259-label control replay | pending | Codex frozen manifest and `a20cea18` capture |
| D26 counterfactual (P arm) | pending | |
| Fresh-context review | pending | |
| Full fast checkpoint | pending | |

Measured results and reproduction commands are added when each receipt exists.
