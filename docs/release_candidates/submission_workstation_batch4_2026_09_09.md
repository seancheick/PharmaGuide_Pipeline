# Batch 4 part one: persistent reviewer corrections and server-owned attestation

Built 2026-09-09 on pipeline `79a4d416` and app `bce3624`, both verified as
ancestors before any change. Source and disposable-local verification only. No
production migration, no extraction enablement, no catalog rebuild, no real
user photo processing, no model download, no paid inference, no scoring change.
Extraction remains disabled.

## Codex's audit findings: verified, not assumed

Three claimed fixes were spot-checked against source before building on them,
and all three are real: the v4 candidate now derives `prompt_sha256` from one
immutable request template (`ollama_adapter.py:40,72,76`), `help.json` carries
zero `user_sees` keys, and `handleShortcut` refuses on `event.repeat`,
`event.isComposing` and any open dialog (`app.js:728`).

**The artifact-accounting finding is correct and was mine.** Commit `161bce29`
deleted `docs/release_candidates/receipts/flutter_suite.log` and both
`device_product_detail_{dark,light}.png` while its own message claimed all five
pre-existing deletions were untouched. All three are restored from `541b456c`
in this batch. The two report CSV deletions remain uncommitted and untouched.

## What is now true

**Corrections and ticks survive a reload.** They live in
`product_submission_reviewer_drafts` and
`product_submission_field_verifications`, owned by one reviewer, bound to the
exact payload digest, evidence revision and manifest they were made against.
Both tables are RLS-forced and revoked from `PUBLIC`, `anon`, `authenticated`
and `service_role`; they are reachable only through definer functions that
derive the reviewer from `auth.uid()` and the allowlist. A naked service key
cannot author a human's attestation, and one reviewer cannot read another's
unfinished corrections.

**Staleness is compared and reported, never silently repaired.** A draft
written against replaced photographs is returned with `superseded: true` and is
never adopted into the editor; its attestations are returned `live: false`
rather than deleted, so the console can say what was withdrawn instead of
letting a reviewer believe work survived that did not. Both states now block
approval and render a banner.

**The database owns what "fully read" means.**
`product_submission_required_verification_paths()` holds the five critical
paths and `assert_product_submission_fully_verified()` enforces them against
this reviewer, this payload digest and current evidence. The console checklist
is a hint; this is the rule.

**A batch reuses the single decision, it does not re-implement it.** The
single-item transition was extracted into `applyTransition`, and both
`transition` and the new `batch_transition` call it. Every item is fenced to
its own evidence, payload, reviewer and identity check exactly as a lone
approval is; each runs in its own transaction, so one refusal neither rolls
back nor skips the rest, and per-item results are returned. Item shapes are all
validated before any item is applied, so a malformed entry cannot abort a run
that has already approved its predecessors.

## Two defects found in my own diff, before review

1. `scheduleReviewSave()` sat inside the `try` in `updateShaPreview` that
   decides whether the payload is valid. Any throw from saving would have been
   caught there, nulled `state.payloadSha` and reported the reviewer's label as
   invalid. Moved outside the block. The existing out-of-order hash test
   caught this, which is why it was worth having.
2. Verification replies could arrive out of order. An earlier reply lists fewer
   ticks, so repainting from it would silently drop a check the database had
   already accepted. Guarded with a request counter and a regression test.

## Evidence

- SQL harness against the real migration chain in a disposable Docker Postgres:
  **79 passed** (74 before; 15 new cases). Reviewer isolation, attestation
  binding, supersession, the photo-membership rule, the five-path gate, and
  `service_role` refusal.
- Deno: **76 passed**, before and after the edge refactor.
- Console behaviour, executed against the shipped `app.js` in a sandbox:
  **7 new cases** in `test_submission_review_persistence.py`, plus the existing
  31 readiness/draft cases still green.
- Broad pipeline fast backstop: **14,049 passed, 54 skipped, zero failures**,
  387.45s. The opt-in local HTTP cases are deliberately skipped in this tier.
- Flutter safety invariants (they read the migrations and the edge function
  directly): **96 passed**.
- `deno fmt --check` and `deno check` clean on the edge function.
- `deno check` clean on `review-product-submissions/index.ts`.

## Not done, and precisely what remains of Batch 4

Reporting these separately rather than as one number:

1. **Photo-linked review — partial.** An attestation now carries the source
   `photo_id` and the database refuses one that is not part of the current
   evidence revision. The side-by-side UI that shows each field beside its
   actual source region is **not built**, and the console does not yet ask the
   existing Python validator for authoritative diagnostics.
2. **Batch console UI — not built.** The server half is complete and is the
   authority. The queue cannot yet mark items green, because `list` does not
   return per-item live-verified counts for the calling reviewer. That needs
   one RPC over `product_submission_reviewer_state_internal` and a batch bar.
3. **Real reviewer HTTP boundary — not extended.** The disposable integration
   setup still stops at the worker; it does not yet exercise the reviewer Edge
   Function, the saved-review path, concurrent edit, wrong reviewer, partial
   batch or lost acknowledgement.
4. **Browser inspection — not run** for the new banner and persistence states.

## A third defect, caught by the existing suite

`select()` cleared the pending save timer *before* resetting identity and
product-image state. In any context without timers the ReferenceError aborted
the reset half-way and left `identityRecorded` standing, which is precisely the
stale-review rebinding `test_submission_review_revision_refresh.py` exists to
prevent. Cleanup now runs last and only when a save is actually pending: a
cleanup step must never be able to abort a reset part-way through.

One pre-existing failure is unrelated and untouched:
`test/release_gate/quick_check_catalog_interaction_test.dart` still expects at
least one live catalog product and finds none. It is the vinpocetine
catalog-content gate already recorded as present on unchanged main; this batch
touches no catalog asset.

## One decision that is not mine to make

Batch approval is gated by `assert_product_submission_fully_verified`. Single
approval is still gated only by the console checklist. Unifying them — making
`review_product_submission` refuse any approval without live attestations — is
the right end state and closes the hole for every path, but it changes the
approval contract and breaks every fixture that approves without ticking
(`fixture.approve` among them). That is a substantive product decision, so it
is flagged rather than taken.

The migration is written but **not deployed**. It has run only in the
disposable Docker harness. `supabase db reset` remains unproven while the
duplicate `20260614` migration prefixes exist; production migration history was
not touched. The existing `data_vs_enriched` release blocker is unrelated and
untouched.
