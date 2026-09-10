# Batch 4: the reviewer workstation, end to end

Built 2026-09-10 on pipeline `4391edfb` and app `dba9edb`, both verified as
ancestors before any change. Source and disposable-local verification only. No
production migration, no extraction enablement, no provider connected, no
catalog pipeline run, no published data. Extraction remains disabled.

## Codex's slice: verified before building on it

The race is real and the fix is right. My guard compared only `submission.id`,
and a submission id survives a retake — so a slow reply from revision 1 could
land after revision 2 opened and restore corrections made against photographs
that were no longer the evidence. Binding to revision and manifest as well as
id is the correct fence. Verified independently: reviewer persistence **8
passed**, SQL harness **85 passed** (79 cases plus 6 concurrency).

## What is now true

**The console has no label rules of its own.** `collect_label_diagnostics`
exposes the importer's own validator — the same code that gates catalog entry —
through `/api/validate_label`, and the console renders the answer. A second
validator in JavaScript would eventually disagree with that one, and the
disagreement would surface as a reviewer being told a label is fine and the
catalog gate refusing it later with nobody able to say which was right. The
whole-payload run stays authoritative; per-row detail is collected by re-running
the same row and serving helpers, so a twenty-row label does not have to be
fixed one error per save.

**Not yet checked is not clean.** An unanswered or failed validator blocks
approval rather than reading as permission, and a previous clean answer does not
survive an outage.

**Fields point at their source.** A tick carries the photograph it was read off;
the database refuses a photograph that is not part of the current evidence
revision, and the checklist offers a one-click jump to it.

**Batch actions are per item, and the server owns the payload.** Readiness comes
from `product_submission_reviewer_batch_state`, which reads the same required
paths the single approval gate uses. Each item carries its own revision and
manifest; the approved label is read server-side from that reviewer's saved
draft rather than accepted from the page, so a batch cannot approve text the
attestations were never made against. A malformed entry is rejected before any
item is applied, so it cannot abort a run that has already approved its
predecessors.

**A lost answer is never replayed.** The console refreshes and stops rather than
retrying work that may already be done, and the transition matrix makes a
replayed approval a refusal rather than a second approval — proven over HTTP.

## The real reviewer Edge Function, over HTTP

`scripts/provision_live_review_stack.sh` brings up a disposable local stack,
applies the submission chain, creates a reviewer, and serves the real Edge
Functions with that reviewer in the allowlist. The chain is **not** duplicated:
it moved to `supabase/tests/submission_identity/chain.sh`, which both the SQL
harness and the provisioner read. `supabase db reset` still cannot own it while
duplicate `20260614` prefixes exist.

Proven end to end, tearing the stack down and rebuilding it from the script to
confirm the setup is repeatable rather than a one-off: **8 passed**. A real
owner creates a real submission with a real photo; a real reviewer signs in
through the function and saves corrections, attests to fields, reads batch
readiness, and approves. Also proven: a non-reviewer is refused 403, an
attestation naming other text is refused, a stale revision cannot save, a batch
refuses an item nobody finished reading, and a replayed batch approval applies
zero.

Applying the chain to a real Supabase stack rather than the harness's stubs is
itself new evidence: it had only ever been loaded into a stubbed database.

## Two defects found in my own work

1. `scheduleReviewSave()` sat inside the `try` that decides whether the payload
   is valid, so a save failure would have nulled the digest and reported the
   reviewer's label as invalid. Moved out.
2. `select()` cleared the pending save timer before resetting identity and image
   state; without timers the reset aborted half-way and left a stale identity
   standing — the exact rebinding `test_submission_review_revision_refresh.py`
   exists to prevent. Cleanup now runs last and only when pending.

## A limit that is stated, not hidden

Batch selection is offered for corrections only. A new product also needs its
barcode check and its catalog picture, and neither is knowable from the queue —
`list` does not return `product_image_photo_id`. Offering it would produce a
refusal the reviewer cannot act on from that screen, so new products are
approved from their own page. **The server supports either kind**: the live test
approves a `missing_product` through `batch_transition` with the picture
supplied. Returning the picture and identity state in `list` would extend
selection to new products and is the obvious next step.

## Evidence

- Pipeline fast backstop: **14,066 passed, 62 skipped, zero failures**, 395.31s.
- Reviewer Edge Function over HTTP: **8 passed** (opt-in; they skip cleanly in
  the ordinary tier, verified by running them with the environment unset).
- SQL harness on the real chain: **89 passed** (83 cases plus 6 concurrency).
- Deno **76 passed**; `deno check` and `deno fmt --check` clean.
- Flutter safety invariants **96 passed** — they read the migrations and the
  edge function directly.
- Focused console + importer suite after the last change: **142 passed**.

Unrelated and untouched: `test/release_gate/quick_check_catalog_interaction_test.dart`
still expects at least one live catalog product and finds none — the vinpocetine
content gate already recorded as present on unchanged main. This batch touches
no catalog asset. The `data_vs_enriched` release blocker is likewise untouched.

## Still open

- **Single approval is gated by the console checklist; batch is gated by the
  database.** Unifying them — making `review_product_submission` refuse any
  approval without live attestations — closes the hole for every path but
  changes the approval contract and breaks every fixture that approves without
  ticking, `fixture.approve` included. Still a decision, not a refactor.
- `list` does not return the product picture or identity state, which is what
  keeps batch selection to corrections.
- No browser inspection was run for the diagnostics panel, the batch bar or the
  source-photo jump; they are covered by sandbox execution of the shipped asset
  and by the HTTP tests, which is not the same thing.
- The migrations are written and applied only to disposable local stacks. They
  are **not deployed**.
