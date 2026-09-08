# Submission identity hardening — 2026-09-08

Scope: the operator approved starting with submission identity and duplicate handling.
This is not the AI-extraction, clinical-validation, scoring, or catalog-release batch.

## Implemented

- Equivalent validated GTIN widths compare as one identity across retry lineage,
  database approval contention, pipeline receipt ownership, and contribution-history
  filtering. Original barcode digits and photo manifests remain unchanged.
- Ambiguous eight-digit lookup candidates are not interchangeable ownership identities.
  Known UPC-E input follows the existing symbology-driven expansion before submission.
- Missing-product capture asks an owner-scoped, read-only intake RPC before taking photos:
  open an existing receipt, explicitly link an eligible rejected retry, explain an
  interrupted upload, or start a new submission. Unknown/offline/timed-out responses
  keep capture closed; late responses after an account switch are discarded.
- A previous product-identity-mismatch rejection is not automatically linked by a fresh
  intake. The explicit resubmit path retains its existing server validation.
- Create/finalize remain authoritative after preflight. Concurrent first creates with the
  same UUID cannot rewrite original retry lineage; equivalent-width competing approvals
  cannot bypass the approval lock. No other submitter's private receipt is returned.
- Reviewer identity lookup refreshes when local catalog or corpus files change. Recording
  a match and approving recheck source freshness, clear stale decisions, and require review
  of changed candidates. A later DSLD arrival no longer leaves the running console on a
  cached no-match result.
- Import rejects conflicting canonical receipt ownership before writing output, including
  equivalent-width repeats across separate import runs. Existing replay/recovery behavior
  and label-edition ambiguity protections are retained.
- Public rejection guidance has one Flutter producer. New dialogs are scrollable for
  narrow screens and large text.

## Verification and review

- Pipeline `scripts/test.sh fast`: 13,626 passed, 167 skipped, one warning, zero
  failures (330.45 seconds). The isolated worktree does not contain the generated
  brand corpus; corpus-dependent skips are not evidence of a new full-corpus run.
- Reproduced barcode-width, stale-source, concurrent-lineage, and dialog-overflow defects
  before fixing them.
- 128 affected pipeline tests passed in the implementation pass; independent reviewer
  reran 81 related pipeline tests after the ambiguous-eight-digit correction.
- The executable local SQL harness applies the actual affected migration chain in a
  disposable Postgres container: 24 behavior/permission/concurrency groups pass.
  Independent reviewer also reran all 24. Local Supabase security advisors found no
  error-level issues. These are local results, not a production security audit.
- 17 capture-flow widget tests pass, including navigation, timeout, explicit lineage,
  interrupted upload, and a 320-pixel-wide screen at 2x text scaling.
- Flutter analysis: no issues. Full Flutter suite: 3,401 passed, one failure. The
  failure is the unchanged `test/release_gate/quick_check_catalog_interaction_test.dart:190`
  requirement for at least one live vinpocetine product. It also fails on unchanged main;
  both checkouts contain the same catalog SHA-256
  `5be7c7fca48d642660aa549d6bc1c4008b8bfd85f5ccedf41024e34169e157c7`
  and zero products tagged vinpocetine. This is an OPEN release-gate reconciliation,
  not a submission regression and not permission to weaken the test or restore scores.
- Simulator: actual capture widget with the V2 app theme, test-only backend, no live
  records. Inspected existing-submission, rejected-retry, and interrupted-upload states;
  selecting retry opens fresh capture. Navigation and 2x text scaling are also pinned by
  widget tests. This is not the deployment/physical-phone end-to-end proof.

## Deployment sequence — not executed

1. Review/merge the paired `codex/submission-identity-hardening` branches. Preserve the
   historical migrations and any unrelated working-tree changes.
2. Inspect linked migration history and pending migrations. Apply the new app-owned
   `20260908230736_harden_submission_identity_and_intake.sql` migration through the
   normal reviewed migration process; do not run a blind push of unrelated migrations.
3. Verify owner-scoped intake and role permissions in the target environment. The new
   Flutter client requires this RPC; do not ship the client first.
4. Update/restart the local reviewer console from the paired pipeline changes, then build
   the phone from the new app commit. No Edge Function change is required in this batch.
5. Physically test same actual GTIN while pending, rejected-as-new, explicit width-variant
   retry, interrupted upload, and known/ambiguous catalog lookup. Use separately authorized
   test receipts for review transitions. No real submission was approved/rejected here.
6. Check notification, points, and operator-alert behavior in the separate A3 matrix.
   A code-complete identity batch is not an external-beta approval.

No 37-brand enrichment/scoring rebuild is needed for these changes. A later normal release
must still pass its usual final-artifact and release gates.

## Commit handoff

Both repositories use the local branch `codex/submission-identity-hardening`.
App commits: `0c02f9d` (migration/local SQL harness) and `01b01a5` (Flutter intake).
Pipeline code commits: `d8513897`, `13314173`, `a0d3a6aa`.
No branch merge, remote push, migration deployment, live submission mutation, or
catalog publication was performed. The paired changes must be integrated and deployed
in the order above, with the unrelated open catalog gate resolved before a beta claim.

## Explicit boundaries still open

- Interrupted photos are not durably resumed on another device. The existing immutable
  in-memory attempt may continue on its original device; this change offers an explicit
  fresh capture instead of pretending stored photos can be resumed or overwriting them.
  Two incomplete drafts may exist; ready/open uniqueness is still enforced transactionally.
- A same-GTIN match is a review candidate, not proof of the same formulation. Automatically
  aliasing a historical PG_SUB ID to a later DSLD ID, or approving distinct editions with
  the same GTIN, needs an explicit source/edition contract. This batch neither silently
  merges labels nor adds a bypass for unresolved collisions.
- Historical competing approvals/incorrect barcode assignments are not rewritten. They
  require evidence-based, separately authorized review dispositions.
- A1 engineering is implemented for the bounded intake behavior above. A2's current-source
  and receipt guards are strengthened, but future alias/edition handling is not closed.
  A3 device/notification/points assurance, A4 capture simplification, Batch 3 extraction,
  clinical review, and independent scoring calibration remain separate work.
