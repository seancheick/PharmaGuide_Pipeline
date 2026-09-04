# Probiotic evidence coverage audit — 2026-09-03

Baseline: `2a5b99d7` (scoring applicability candidate, not the released catalog).
This work does not run a catalog release or change global pillar weights.

## Accepted scope and completion ledger

- [x] Audit six exact comparator labels against primary clinical sources.
- [x] Fix verified identity/scope/assessment defects with failing tests first.
- [x] Record research strength, applicability and search coverage separately;
      incomplete searches never become negative efficacy findings.
- [x] Inspect certification losses and document actual match limitations.
- [x] Review CFU/diversity/double-credit rules as proposals, not silent calibration.
- [x] Replay representative native/formula products and measure corpus impact.
- [x] Independent spec review, then code-quality review; focused and fast tests.
- [x] Publish findings, remaining clinical decisions and exact rebuild readiness.

## Boundaries

No invented clinical ranges, no total-to-per-strain dose allocation, no automatic
species-to-strain transfer, no autonomous clinician-signoff stamp. Clinical study
discovery is separate from the label-photo extraction pilot. Search completion
means a dated, bounded review, never proof that no other evidence exists. The
existing blinded benchmark requires its documented protocol/reviewer prerequisites;
this audit cannot substitute for independent clinical review.

## Research files

Primary-source extraction and query logs are retained alongside this document.
Each production data change must identify the source and exact scope it supports.

## Implemented corrections

- Missing specificity is now `scope_unresolved`, not automatically species-level.
  LGG's existing primary guideline explicitly identifies LGG; it is no longer
  mislabeled as species-general. This does not establish an adult dose window.
- Native clinical credit requires a human source. Animal/laboratory or unresolved
  sources remain visible but cannot masquerade as human clinical support.
- Native effect direction uses the existing multiplier once. HN019's cited null
  trials no longer silently receive positive-result credit.
- BB-12's unverified source and Bi-07's different-species laboratory source are
  held. Identities and aliases remain; no replacement PMID or clinician approval
  was invented. `unreviewed` support is null, not a weak-evidence assertion.
- The audit runner authenticates the complete baseline-report chain. The first
  broad replay's 56 off-category score differences were comparison artifacts:
  an intermediate report omitted unchanged candidates preserved in its parent.
  Regression tests now cover inherited deltas, source/count/hash drift, cycles,
  ancestor mutation, separate code/input roots, and immutable output paths.

## Important interpretation limits

This is a completed **bounded search and engineering review**, not completed
clinical curation of all probiotics. `coverage_review.json` records internal
search coverage separately from score and confidence. All 49 native registry
entries still lack reviewed dose-applicability records. See `rubric_decisions.md`
for the next work: clinical-context contract, source replacement approval,
Formulation/Dose/Evidence ownership, then blinded validation before calibration.

The 42-label sample is stratified by brand, CFU, native identity count and dose
ownership. It is not a prevalence estimate or a substitute for independent
reviewers. Five of the six main scores are unchanged; Ritual's decline exposes
existing cross-pillar approval coupling, not changed physical product quality.

No operational corpus rebuild, catalog export, app import or production publish
is performed by this audit. Phase 3 remains the label-photo extraction pilot and
can proceed separately; it is not automated literature curation.

## Verified impact and test result

`verified_impact.json` retains every material numeric transition, all six
comparators, and hashes of the full reports and their authenticated baseline
chain. `coverage_review.json` is the separate internal research-coverage view.

- Full fast profile: **12,880 passed, 167 skipped, zero failures** (204.62s).
  Skips include unavailable generated-artifact canaries in the isolated worktree
  and existing conditional checks; they are not counted as verified behaviors.
- Final targeted replay: **42 labels fully re-enriched**, 41 scored and one
  safety-suppressed, no status changes (35.7s).
- Final corpus replay: **15,415 products**, 217 fully re-enriched with changed
  lanes recomputed for the rest, zero processing errors (330.7s).
- **57 numeric changes, all probiotic-only**; nine SAFE→POOR legacy verdict
  transitions and eleven tier transitions. No route/status/confidence changes.
  The nine verdict transitions reflect the existing quality-score floor, not
  new safety hazards; review their knowledge-gap treatment before shipping.
- **43 unique live PMIDs / 55 citation occurrences** pass the topic screen.
  The screen is not an outcome-level clinical validator. Individual identity
  and interpretation corrections are documented in `source_corrections.md`.
- Independent code and report review completed. The ancestor-overwrite finding
  is fixed by exclusive report creation; final report-ledger checks are closed.
- Release-profile diagnostic against the existing root artifacts: **117 passed,
  3 failed, 3 skipped** (78.30s). The isolated candidate has no local enriched/
  scored stage outputs to join, so stamped-score, stamped-route and historical
  BLOCKED canary presence checks fail. The old final export is also a canary
  subset, causing three export-parity skips. This is **not** a passed release
  gate or validation of a newly built candidate. No missing-artifact check was
  relaxed or skipped by adding a bypass.

**Release approval remains false.** No final export built with this candidate
exists. A green fast suite and read-only replay do not replace the operational
rebuild, fresh export, Flutter checks or clinical/rubric decisions. Do not rerun
the full pipeline just to ship an intermediate numeric model that is still
awaiting the pillar-ownership review.
