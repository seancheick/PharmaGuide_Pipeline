# Reviewer workstation audit and next substantial milestone

Audited 2026-09-09: pipeline `541b456c..161bce29`; paired app `bce3624`
unchanged. Source and disposable-local verification only. No production
migration, extraction enablement, catalog rebuild, real-user photo processing,
model download, paid inference or scoring change.

## Findings closed

1. **Checks could outlive an edit.** Hashing yielded before revoking checks;
   late promises could replace the current payload hash with an older one.
   Checks now require the current canonical payload, digest, revision and
   manifest. Edits revoke synchronously; stale completions are ignored.
   The original test named “editing clears ticks” never edited a checked
   payload. New tests perform the transitions, including out-of-order hashes.
2. **Approve only consulted ticks through its button.** The action now applies
   the same readiness function before and after the asynchronous identity
   check. No second approval ruleset. It no longer re-normalizes the payload
   after attestation (which could collapse a printed serving range).
3. **Readiness did not refresh after identity/image choices.** Those actions
   now immediately update availability. Adding an ingredient also invalidates
   the digest. “Under review” no longer claims exclusive reviewer assignment.
4. **Single-key actions leaked through dialogs.** Shortcuts are ignored in
   open dialogs, during composition and on key repeat. The real browser also
   exposed a loading interval before Help became modal: it now opens before
   fetching content, with retryable failure copy. This has a separate failing-
   then-passing regression.
5. **Generation settings were outside the fingerprint.** One immutable request
   template now owns both transmitted settings and `prompt_sha256`, including
   thinking, repeat penalty, seed and token limit. Candidate version is
   `label-draft-local-v4`; existing configurations are not silently relabelled.
   Comments no longer claim the repeat penalty cures the loop. No successful
   model extraction or model qualification is claimed by this audit.
6. **Help invented a second set of consumer rejection sentences.** They differed
   from Flutter's `productSubmissionResolutionGuidance`. Removed the purported
   quotations; help owns operator guidance only. Unfamiliar language is not
   equated with an unreadable photograph.
7. **The live test repaired intake with privileged SQL.** It wrote Storage
   metadata directly and toggled the submission to re-enqueue it. The fixture
   now supplies metadata through the real multipart upload, enables the fake
   provider before finalization and lets the production trigger enqueue.
   Test accounts/photos/submissions are cleaned even on failure; original
   settings are restored. The test refuses a nonempty job queue and needs
   explicit opt-in on a dedicated disposable local stack. No ambient proxy or
   redirects. The ordinary fast tier cannot silently run these mutations.

## Evidence and limits

- Real local HTTP: **12 passed** in 17.51 seconds. Owner create/upload/finalize;
  worker JWT claim/private download/preparation/shared extractor/completion;
  non-worker/anonymous denial; duplicate claim prevention; disabled switch,
  retired consent, expired lease and retake revoke an existing lease's Storage
  access; another allowlisted worker cannot read its receipt; loss of the
  completion response after COMMIT reconciles without a second write; a fresh
  client independently reads that receipt.
- These use the canonical **abstaining fake adapter**, not a successful vision
  model, and do not yet traverse the reviewer Edge Function. Do not call that
  the entire worker → real model → human workstation → approval proof.
- Cleanup query returned **0 auth users / 0 submissions / 0 photo objects /
  extraction disabled / 0 jobs**. Only this audit's disposable stack was
  removed afterwards. No user's local or remote database was cleaned.
- Browser inspection uses real static assets and synthetic state/network
  fixtures, not a signed-in physical operator. This complements, not replaces,
  the authenticated HTTP tests. Checked the final-image action, help-loading
  shortcut suppression and editing a fully checked payload. The final
  [screenshot](screenshots/workstation_audit_2026_09_09.png) shows all checks
  withdrawn after the edit and approval disabled with its reason. Initial
  auth/config 404s are expected on the fixture's static server.
- Test logs: `/tmp/pg-workstation-audit.slFjPD/live-expanded.log`,
  `/tmp/pg_workstation_full_fast.log`, `/tmp/pg_workstation_last_ui.log`.
  Final suite results are recorded in the completion addendum below.
- Catalog release readiness remains separate. Existing enrichment/reference
  fingerprint staleness was not repaired or bypassed in this submission audit.
- Fresh local setup still needs the selected submission migration chain and
  its retired empty `pending_products` fixture. `supabase db reset` is not
  proven: the repository still contains duplicate `20260614` migration prefixes.
  Do not change production migration history to make a local test pass.

## Corrected artifact accounting

Claude's `161bce29` committed deletion of `receipts/flutter_suite.log` and both
`device_product_detail_{dark,light}.png` audit screenshots despite saying all
five pre-existing deletions were untouched. They remain recoverable from
`541b456c`; this audit does not restore or further remove unrelated artifacts.
The two report CSV deletions remain uncommitted and outside this work. The app
repository needed no change in this audit.

## Claude: continue Batch 4 as one substantial source milestone

Do not stop after every helper. Fetch both repositories, verify these fixes
are ancestors, then carry the following through tests, browser inspection,
coherent commits and a single handoff:

1. **Persistent human corrections and verification.** Use the current owning
   draft/revision contract. Bind saved corrections and attestations to reviewer,
   exact payload and evidence manifest. Restore the same review after reload;
   never silently discard edits on navigation or overwrite them on refresh.
   A new revision invalidates old attestations, with an explicit comparison.
   Do not add a parallel draft database or permit the model to attest.
2. **Photo-linked review.** Show each field beside its actual source, preserve
   unknown rows/nesting/forms/printed units, and make unresolved conflicts
   explicit. Label confidence as unverified model confidence. Ask the existing
   server validator for authoritative diagnostics rather than copying its
   validation into JavaScript. Keep serving ranges intact in ordinary editing.
3. **Per-item verified batch actions.** Reuse the existing human decision
   transition and validators. Bind every selected item to its own reviewer,
   revision, manifest, verified payload and identity check. Enforce idempotency
   and per-item results for partial failure/lost responses. A checked neighbour,
   model confidence or stale screen must never authorize another item.
4. **Close the real reviewer HTTP boundary.** Extend the disposable integration
   setup to include the actual reviewer Edge Function and saved-review path.
   Exercise concurrent edit, changed revision, wrong reviewer, partial batch,
   lost acknowledgement, restart and unchanged read-only refresh. The queue
   tests remain on their shared worker implementation. Do not duplicate the
   migration list in another permanent runner: choose a canonical chain owner
   shared with the existing SQL harness when making setup repeatable.
5. **One backstop at milestone end.** Focused tests during development, one
   broad backstop, real rendered UI checks and one return package. Audit every
   consumer when a contract changes. Include untracked/deleted files in status.

Model tuning on synthetic/development fixtures may proceed separately if useful,
under immutable v4-or-later candidate configurations. Do not change acceptance
thresholds to make a model pass. The 20-development/40-held-out photo set with
independent human gold checks still gates qualification, not workstation work.

**Stop only at genuine boundaries:** new deployment/credentials, paid or external
photo processing, irreversible operations or a substantive clinical/product
policy decision. Keep extraction disabled; no production rollout, autonomous
approval or catalog rebuild. Report implemented, integrated, deployed and
qualified separately. Batch 5 onward is not closed by a Batch 4 demo.

## Completion addendum

- Broad fast backstop: **14,039 passed, 54 skipped, zero failures**, 575.39s.
  The 12 local HTTP cases are deliberately skipped in that ordinary tier;
  they passed in the separately opted-in run above. Existing unrelated skips
  remain skips, not proof of unavailable corpus fixtures.
- Last isolated UI regressions: **20 passed**. Final affected-suite rerun after
  the last UI correction: **322 passed, 12 opt-in cases skipped**, 52.46s.
  `/tmp/pg_workstation_final_affected.log` records it; the only warning is the
  intentional decompression-bomb fixture. No failure was waived.
- Release command was rerun and stops on the existing `data_vs_enriched`
  reference mismatch. `/tmp/pg_workstation_release.log` is the fresh receipt.
  This gates catalog publication, not a claim that a source-only commit has
  deployed anything.
- No deployment approval is implied by these results.

Receipt SHA-256:

- broad fast: `6290860fdaada8fe1e417b11f4765c0b37ae2e31dfbec433d92dde9364ee8928`
- final affected: `2eb6df493310e326fded62d57a87129347727a394959c481dab5f2bf7634c2f5`
- local HTTP: `15b0437b8faa321784c0cef7de5d755037a8844957b1f4f8aeb6112a1fb02f13`
