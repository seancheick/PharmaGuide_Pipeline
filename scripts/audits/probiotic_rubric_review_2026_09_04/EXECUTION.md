# Probiotic correctness and rubric execution

Authorized 2026-09-04 after the report-only clinical review. This ledger tracks
implementation separately from clinical approval and the eventual release.

## Paused for Claude handoff — 2026-09-04

The user requested a laptop-close handoff before completion. Continue from
[CLAUDE_HANDOFF_2026_09_04.md](CLAUDE_HANDOFF_2026_09_04.md), which records the
actual feature-worktree paths, frozen hashes, test results and remaining gates.
The continuation is uncommitted. The new primary-evidence source-ownership test
is intentionally RED (**1 failed, 3 passed**); no runtime fix has been applied.
Latest botanical data corrections have **158 focused tests passing**, but still
need an independent feature-worktree review and a new corpus comparison. The
older report named `corpus_preparation_continuation_accepted.json` predates those
corrections and is not current acceptance. No operational rebuild or release is
authorized or running. Historical completion statements below describe only
their named earlier checkpoints.

## Fixed boundaries

- One production scorer, router and applicability decision; no competing shadow engine in production.
- No global weight changes, target-score tuning, invented study dose or clinical sign-off.
- No operational full rebuild, catalog publication, Supabase mutation or phone import in this work.
- Preserve source labels, explicit uncertainty, safety suppression and exact source ownership.
- Each behavior change starts with a failing test; targeted tests during iteration,
  a broad fast backstop and read-only corpus impact before handoff.
- Independent human benchmark ratings and clinical/statistical ratification cannot be supplied by agents.

## Tasks

1. **IMPLEMENTED; CORPUS VERIFIED — identity/routing correctness.** Reproduced Jarrow 264610 at the
   source-row boundary; prevent yeast extracts/components or contradictory taxonomy
   from becoming live probiotic identity. Preserve true live-organism products.
   Validate source ownership, label copy, dose/evidence and full-corpus route impact.
2. **IMPLEMENTED; INDEPENDENTLY REVIEWED — benchmark ingestion/provenance.** One response contract shared by
   parser and analysis; real round-trip tests; expose AI/engine-review history in
   machine-readable gates; preserve old responses and the sealed historical freeze.
3. **IMPLEMENTED; REVIEWED — outcome-specific assessment.** Extend the existing assessment,
   not a second matcher, to multiple source-backed dose/population/outcome/regimen
   contexts and combination restrictions. Unknown is not negative. Test malformed,
   wrong-indication, wrong-population, mixture and discrete-dose boundaries.
4. **SOURCE REVIEW COMPLETE; CLINICAL APPROVAL PENDING — prioritized curation.** Verify primary sources individually
   for LGG, BB-12, Bi-07, HN019 and S. boulardii; then high-reach additional strains.
   Record eligible, null and unresolved contexts with review limits. Do not claim
   a completed systematic review or add human approval stamps.
5. **MEASURED PROPOSAL; RATIFICATION PENDING — category rubric and semantics.** Audited CFU/count rewards and
   repeated disclosure credit; measured five sensitivity alternatives. They are
   not complete replacement rubrics and were not installed. Keep unfinished
   research review explicit; preserve global weights and no target-score goal.
6. **ENGINEERING VERIFIED — integration and handoff.** Targeted real labels, read-only corpus
   route/score/status diffs, cross-module canaries, fast backstop and independent
   review; small commits with source/version provenance and exact remaining gates.

## External completion gates

- Qualified independent reviewer panel and locked ratings; clinical/statistical
  approval of the benchmark brief and any calibration candidate.
- Clinical policy sign-off where source interpretation is materially ambiguous.
- Full operational rebuild and release verification after the above decisions.

The audit's five ablations are diagnostics, not pre-approved replacement scores.

## Prior checkpoint implementation details

- Native registry version 2.2.11 adds 14 study contexts across LGG, BB-12,
  Bi-07, HN019, S. boulardii, NCFM and Bl-04. All 13 unique PMIDs retrieved
  from NCBI; individual primary-source methods/outcomes were reviewed and
  independently spot-checked. This is a bounded review, not all-literature coverage.
- No new clinician approval or numerical evidence credit. Historical anchor
  sources are kept separate from the expanded research inventory. Null/negative
  results and pending review are independent; pending review does not imply
  absence of human evidence or poor product quality.
- Removed the unused universal native min/max applicability consumer, rather
  than keeping a competing path beside the source-context model. Exact reviewed
  finished-formula assessment remains intact.
- New benchmark response contract 2.0 binds documents, responses and stages to
  one frozen packet and validator. Historical freezes/answers are untouched;
  assisted/exposed responses cannot become an independent three-rater result.
- No global weights or numeric rubric replacements have been installed. The
  frozen full-corpus alternatives and cross-pillar ledger remain the proposal
  to ratify, not a second production scorer.
- Required identity conflicts remain in one source-owned coverage denominator,
  including skipped IQD rows and legacy callers. Readiness diagnostics use the
  same ownership helper; a stale canonical or old positive match reason cannot
  turn a conflicted active into a mapped one.
- Exact preparation identity and whole-organism identity are distinct. Literal
  source forms prevent extract/fermentate/heat-treated products from inheriting
  live-organism research; source-organism words inside fermented rice do not
  make the rice an organism. No preparation-to-organism equivalence was added.
- Exact `EpiCor dried yeast fermentate` now belongs to the existing branded
  preparation; generic names cannot inherit it. Source doses and ownership are
  preserved. [Primary-source note and isolated replay](epicor_alias_research.md).
- Missing IQM form ratings now say **not rated**, not **basic or low-cost**.
  One producer supplies the unchanged numeric average and its rating count;
  botanical, collagen, finished-formula and omega explanations retain precedence.
- The benchmark owner protocol is explicitly private. Historical staging notes
  link to the current draft workflow; none supplies clinical ratification or
  authorizes distributing the private sample design.

## Prior checkpoint corpus verification

Implementation `619b5409` completed the read-only audit in 374.0 s:
**15,415 products, 786 complete cleaned-to-enriched replays, zero errors**.
All 174 input files, 267 production/reference files and two runner files retained
their hashes. The clean replays include all 551 baseline probiotics and all 74
labels selected by the production derivative guard. Other rows recomputed
affected enrichment lanes and the production scorer; this is not a full
operational clean-to-export rebuild.

Full report: `/Users/seancheick/Downloads/dsld_clean/reports/probiotic_rubric_review_2026_09_04/corpus_engineering_final.json`.
SHA-256: `22d493b37e5ede3ad0da4f3b1c10ac0791045bab589391dcece18656e9ec4b4e`.
Its authenticated baseline is the completed dose audit
`corpus_impact_final.json`, SHA-256
`07c4a5e1592855d17f9351b396a5c7327b15bf595e4dea115c1c1f62041d2214`.

| Check | Final measurement |
| --- | ---: |
| Retained scored products | 15,271 |
| Retained products with numerical score/pillar corrections | 14 |
| Newly held for unresolved identity | 13 |
| Already not scored, unchanged | 77 |
| Safety-suppressed, unchanged | 54 |
| Route changes | 3 |
| Numerical Evidence/confidence changes among retained scored products | 0 / 0 |
| Newly accurate unrated-form explanations | 151 |

The final alias and explanation fixes introduce **zero** numerical, status,
verdict, tier, route or confidence differences from the reviewed `3ecf73d4`
checkpoint; 151 explanations change. Compared with the dose baseline, 27 score
fields change: 14 numerical corrections plus 13 newly null held scores. The
4,546 changed report records include research/metadata differences and must not
be described as 4,546 changed scores.

All seven controls retain their scores, pillars, status, route and confidence:
Seed 81.2; Culturelle 72.7; Garden of Life 57.4; Fortify 63.6; Ritual 55.9;
Jarrow S. boulardii + MOS 62.4; Solgar 75.8. These bind the exact product IDs
in [verified_execution_summary.json](verified_execution_summary.json), not all
similarly named labels or the currently served catalog.

Final `scripts/test.sh fast`, run after the corpus audit: **13,174 passed,
167 skipped, zero failures**, 213.90 s. Skips are chiefly unavailable generated
or historical canary artifacts and existing schema-test exceptions; they are
not counted as passing release gates. Independent reviews cleared identity
boundaries, evidence provenance, benchmark ingestion/blinding, the final
explanation correction, corpus metrics and operator instructions.

## Prior checkpoint remaining decisions

- **13 identity holds, not missing-study penalties:** ten Airborne labels have
  ambiguous bare dried-yeast-fermentate identity; Jarrow 264610/307558 need the
  whole yeast-extract preparation resolved; Garden of Life 241325 needs its
  heat-treated Immuno-LP20 preparation resolved. Do not borrow live-organism
  identity or infer branded preparation from a generic name. Obtain exact-label
  identity evidence, correct one owner at a time, then replay these IDs.
- **EpiCor quality/evidence curation:** the exact alias now matches. Product
  25492 still has no authored IQM form rating or loaded clinical evidence
  record; current brand credit is offset by the existing additive penalty.
  Its Formulation 0 and composite 44 are not a clinical finding of poor-quality
  EpiCor. The form explanation is corrected; broader composite/provisional and
  generic Evidence wording policy remains part of the unratified semantics
  proposal, not solved by giving unreviewed points.
- **Bounded evidence review:** seven identities have 14 source contexts,
  not a completed systematic review of all 49 entries. Next source work includes
  Lpc-37, BB536, HN001, DE111 and exact commercial formula editions. New contexts
  still need clinical approval; neither old approval nor a real PMID supplies it.
- **Benchmark/calibration:** ratify the reviewer brief and statistical plan,
  recruit three independent raters including two licensed clinicians, and freeze
  the approved candidate immediately before distribution. Prior AI-assisted
  ratings remain exploratory. Then evaluate category rules; no target-score
  tuning or global-weight changes have been authorized here.

The `3ecf73d4` checkpoint and earlier intermediate reports are retained for
audit, superseded by the final report above. Final export, Flutter compatibility,
release/full suites and publication remain subsequent gates; none ran here.

## Continuation: preparation identity and next native context

Baseline: `cea87d01` and `corpus_engineering_final.json` above. The earlier
measurements remain the frozen pre-continuation state, not completion claims
for this follow-up.

- [x] Verify all three held identity families against exact labels and primary
  preparation sources. Preserve whole-preparation amounts; no inferred CFU or
  generic-to-branded identity.
- [x] Generic dried fermentate: three RED assertions reproduced the duplicate
  alias / ghost citation defects; four focused tests and 113 adjacent tests
  pass after removing two conflicting IQM aliases and the unrelated citation.
- [x] Register Jarrow's exact yeast-extract preparation, preserving the separate
  glucan constituent rather than replacing the parent amount.
- [x] Register Immuno-LP20 separately from live L. plantarum and from its
  concentrated HK L-137 constituent. Keep the printed 50 mg mixture amount.
- [x] Repair the newly exposed identity-projection seam: a resolved canonical
  must retain its owning registry/name across IQD, active rows and scoring
  projections, without inheriting a stale quality score.
- [x] Curate the next bounded native context, Lpc-37: verify both Sisu and
  ChillEx, distinguish null primary results from exploratory findings, and
  retain pending clinical approval.
- [ ] Targeted real-label replay, whole-corpus diff, independent reviews and
  fast backstop; commit/push reviewed changes and report remaining gates.

No operational rebuild, release/export, Supabase mutation, Flutter import,
global weight change, new clinician approval or independent reviewer rating is
authorized by this continuation.

### Independent review corrections

- Exact labels and primary sources independently confirm all three preparation
  families. No inferred constituent dose, CFU, clinical approval or new form
  rating is introduced.
- An adversarial older-artifact test exposed a denominator hole in the first
  projection guard: dropping an incomplete repaired row hid it beside a valid
  peer. One shared tuple validator now keeps the required exposure unresolved
  in both scoring coverage and readiness, with an explicit contract-rejection
  reason. The independent re-review reproduced coverage 0.5 and `not_scored`
  for the damaged parent plus valid child, in place of false coverage 1.0.
- Old probiotic indication copy could disagree with corrected source research.
  The existing evidence assessment now owns current registry indications and
  supplies them to descriptive alignment. Strength is not parsed as a benefit
  claim. Accepted-row identity, approval and dose ownership remain unchanged.
- The first report-only whole-corpus attempt was deliberately interrupted for
  the denominator correction. `corpus_preparation_continuation.json` remains
  incomplete and is not an acceptance artifact or baseline. Its explicit
  selection list is reused by the final run; source and implementation hashes
  are freshly verified there.

### Expanded replay investigation (not a release acceptance)

The complete `corpus_preparation_continuation_v2.json` expanded full clean
re-enrichment from 786 to 6,522 labels while scoring all 15,415. It exposed
181 additional holds and 75 retained numerical changes. Those numbers were
investigated, not accepted as unexplained consequences of a green test suite.

A detached, unchanged `cea87d01` checkout then replayed the identical 6,522
labels through the same harness and hashed input corpus. The complete
`corpus_preparation_control_cea87d01.json` took 770.4 seconds and preserves
the previous status totals. That controlled comparison distinguishes:

- 48 apparent verification changes caused by comparing old enriched inputs
  with fresh enrichment; they are not caused by this continuation's code.
- 27 retained numerical changes attributable to this continuation, requiring
  per-family review before acceptance.
- 156 holds exposed by rejecting safety-only IDs as primary active identity;
  221 required source rows had no mapped cleaner primary. The safety matches
  remain valid separate metadata, not sufficient identity/quality evidence.
- 24 EDTA/mannitol labels with no eligible source-active rows, previously
  admitted through stale/fallback quality metadata.
- One additional correctable Immuno-LP20 case, Doctor's Best 82408: the source
  group is TBD but its literal preparation and own heat-killed form resolve.
  The regression and shared-resolver correction pass the focused tests.

The 156 safety-primary cases cannot be fixed by deleting their IDs and thereby
making the required exposure disappear. The producer correction retains
safety recognition, explicitly reports the missing primary identity, and keeps
those rows in the existing readiness denominator. Exact primary-identity
curation is separate work; no chemical identity, quality rating or clinical
approval is invented to restore a score. This expanded finding means that the
older 90/77 quarantine totals are not a forecast for the eventual rebuild.

### Final acceptance follow-through

The first complete 6,650-label continuation replay is a diagnostic checkpoint,
not the final accepted candidate. Reviewing its individual score deltas exposed
additional source-ownership seams:

- [x] Keep botanical primary ID, registry and preferred name coherent through
  the single final projection; invalid source records retain required coverage
  and cannot borrow an IQM marker's quality rating.
- [x] Retain `OI_GUAR_GUM` as the existing guar identity; only its own verified
  PHGG/Sunfiber preparation wording can make it hydrolyzed guar. Plain guar
  keeps its existing soluble-fiber credit.
- [x] Preserve whole-seaweed interventions separately from isolated
  astaxanthin, fucoidan and fucoxanthin; no constituent mass is invented.
- [x] Bind green-tea research to the exact source preparation. Whole-leaf,
  black-tea, caffeine-primary and theanine-primary records cannot borrow it.
- [x] Replace the separate primary-active selector with the existing strict
  source-owner join. Quantified nested actives own their evidence and amount;
  ancestor totals remain RDA/UL lineage only. Verify full EGCG spellings through
  primary chemical-identity sources before repairing their exact aliases.
- [x] Close independent-review follow-ups for nested synergy/other collectors,
  failed synergy unit conversions, and title-head parsing after separators.
- [ ] Compare old and candidate implementations over the same expanded clean
  selection (initially 7,791, plus any newly demonstrated affected rows), then
  run the broad fast backstop and review the final numerical/hold ledger.

Do not describe a lower score as automatically more accurate. The Astaxanthin
domain correction is supported by its isolated ingredient identity; the
MacuGuard decrease instead exposed an existing title-head parser defect and
must be corrected before acceptance. Research notes retain the per-product
causal analysis. The later complete comparison owns the final numbers.

The final clean-replay selection contains **8,078 labels**. An unchanged-code
control at `cea87d01` scored all 15,415 products and fully re-enriched 7,791;
it completed with zero errors in 869.5 seconds. Expanding source-owner coverage
introduced three control-only numerical differences from the prior control,
which must not be attributed to this continuation.

The synergy conversion inventory then found 287 further affected labels outside
that selection. A separate unchanged-code replay of all 287 completed in 64.5
seconds with **zero summary differences** from the 7,791-label control. Thus
the final candidate can use that control as its numerical baseline while fully
re-enriching the 8,078-label union. Metadata differences in the supplemental
report do not mean numerical changes. The corpus harness preserves exact
input/implementation hashes; this remains a read-only impact audit, not an
operational rebuild or export.

## Cloud handoff checkpoint — 2026-09-04

The operator authorized committing and pushing the unfinished continuation for
Claude Code cloud. This is a WIP transfer, not engineering/release acceptance.
See `CLOUD_START_HERE.md` for portable paths, runtime, access and stop boundaries;
`CLAUDE_HANDOFF_2026_09_04.md` retains the full technical continuation roadmap.

Fresh focused verification: **1 failed / 175 passed in 5.60 seconds** across
source ownership, botanical reachability/projection, clinical source projection,
green tea, native study contexts and synergy units. The sole failure is the
documented phosphatidylserine owned-total floor defect (0 versus 18); it remains
unmodified and intentionally RED. No broad-fast, release or full completion is
claimed by this checkpoint.

Added three selected public DSLD label projections (213475/218600/218838), with
source-batch and projection hashes, for cloud source-shape debugging. They do
not replace full products or corpus gates. The original JSON numeric types were
preserved after fingerprint verification caught serialization drift during
packaging. No clinical/code behavior was changed by packaging.

The full manifest-owned inputs total **8,956,945,899 bytes across 174 files**;
they and the large comparison reports remain local/Git-ignored. The repository
is public, so no bulk corpus/private submission export or credentials were
uploaded. Cloud engineering may proceed; full-corpus acceptance requires secure
input provisioning or the operator's later local comparison. Global weights
remain unchanged. No main merge, catalog publication or app bundle push belongs
to this handoff checkpoint.
