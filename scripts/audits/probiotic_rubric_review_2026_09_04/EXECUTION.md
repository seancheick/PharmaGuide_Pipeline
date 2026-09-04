# Probiotic correctness and rubric execution

Authorized 2026-09-04 after the report-only clinical review. This ledger tracks
implementation separately from clinical approval and the eventual release.

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

## Verified implementation details

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

## Final corpus verification

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

## Remaining source and clinical decisions

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
