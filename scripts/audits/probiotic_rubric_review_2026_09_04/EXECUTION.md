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

1. **IN PROGRESS — identity/routing correctness.** Reproduce Jarrow 264610 at the
   source-row boundary; prevent yeast extracts/components or contradictory taxonomy
   from becoming live probiotic identity. Preserve true live-organism products.
   Validate source ownership, label copy, dose/evidence and full-corpus route impact.
2. **PENDING — benchmark ingestion/provenance.** One response contract shared by
   parser and analysis; real round-trip tests; expose AI/engine-review history in
   machine-readable gates; preserve old responses and the sealed historical freeze.
3. **PENDING — outcome-specific applicability.** Extend the existing assessment,
   not a second matcher, to multiple source-backed dose/population/outcome/regimen
   contexts and combination restrictions. Unknown is not negative. Test malformed,
   wrong-indication, wrong-population, mixture and discrete-dose boundaries.
4. **PENDING — prioritized curation.** Verify primary full-text sources individually
   for LGG, BB-12, Bi-07, HN019 and S. boulardii; then high-reach additional strains.
   Record eligible, null and unresolved contexts with review limits. Do not claim
   a completed systematic review or add human approval stamps.
5. **PENDING — category rubric and semantics.** Remove unsupported generic quantity/
   count and duplicate-disclosure assumptions through an auditable category design.
   Keep unfinished research review explicit. Measure proposed deltas before choosing
   numeric policy; preserve global weights and no target-score goal.
6. **PENDING — integration and handoff.** Targeted real labels, read-only corpus
   route/score/status diffs, cross-module canaries, fast backstop and independent
   review; small commits with source/version provenance and exact remaining gates.

## External completion gates

- Qualified independent reviewer panel and locked ratings; clinical/statistical
  approval of the benchmark brief and any calibration candidate.
- Clinical policy sign-off where source interpretation is materially ambiguous.
- Full operational rebuild and release verification after the above decisions.

The audit's five ablations are diagnostics, not pre-approved replacement scores.
