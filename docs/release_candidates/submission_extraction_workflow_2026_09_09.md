# Local extraction-to-review workflow — milestone handoff

> Superseded for readiness claims by
> [the independent audit and continuation](submission_extraction_audit_2026_09_09.md).
> The original model smoke test bypassed the shared extractor, and the
> development-output test did not invoke the benchmark. Those claims did not
> establish an end-to-end working workflow. Preserve this document as history;
> use the audit for the current rollout boundary and next milestone.

Date: 2026-09-09. Continued from pipeline `b33615ee` and app `8825941`.
Source implementation and local verification. Nothing was deployed, extraction
remains disabled, no paid or third-party service was contacted, no model was
downloaded, and no catalog was rebuilt.

## What now exists, end to end

A submission can be read by a local model and land in front of a reviewer
without anyone holding a service key or a browser session.

1. A worker signs in as **its own account** and claims work through the RPCs
   the migration grants it. It refuses to start if a service key is merely
   present in its environment.
2. The claim hands it the evidence manifest, the object paths for exactly that
   revision, and the configuration frozen at enqueue. A **storage policy**
   admits the worker to those objects while its lease is live and to nothing
   else.
3. Photos are fetched into an owner-only private directory, verified against
   the manifest hash, bounded, re-encoded, and deleted when the job ends.
4. A **digest-pinned local model** reads them over loopback. Vision is read
   from declared capabilities; the digest is checked before every run.
5. The draft is recorded through the same writer the human path uses, and the
   console shows it beside the photographs with per-field provenance.
6. The same extractor can be driven over the development split to produce
   scorable output.

## The two defects only integration could find

Both were found by exercising the authorization surface, and both would have
failed on the first real run while every mock-based test passed.

- **A leased worker could not read the photos it was leased.** Claim returned
  content hashes only, and no storage policy admitted the machine account.
  Fixed by returning the object paths and adding a lease-scoped policy, rather
  than putting a service key in the runner to mint signed URLs.
- **The client called a function no role may execute.** It asked for the
  internal allowance function, which is revoked from everyone and only
  reachable inside a definer. The contract test now reads the shipped SQL and
  asserts every called function is granted to `authenticated`.

## Commits

Pipeline: `81189dde` queue client, `8b073894` local adapter, `29e2a7da` runner,
`5ee81918` reconcile, `75c2e0c7` console draft panel, `79f1d684` development
evaluation, `83220879` granted-function fix and contract test.

App: `943b3a2` leased evidence access, `de2600e` attempt outcome, `f6c58a5`
current-revision drafts in list, `171c4cc` contention/revocation/disabled cases.

## Verification

| Run | Result |
|---|---|
| SQL harness, real migration chain, with concurrency | 68 cases pass |
| Pipeline fast backstop | 13,995 passed, 42 skipped |
| Flutter safety invariants, services, scanner, contributions | 1,292 passed |
| Deno edge tests, entrypoints type-check | 76 passed |
| Local adapter against the installed model | valid envelope in 15.8s |

The local adapter run used a label this session drew. It proves the wiring
reaches the model and back. It establishes nothing about accuracy on
photographed labels.

## Four states, kept separate

- **Implemented:** items 1–7 of the continuation milestone.
- **Integrated and tested:** locally, against the real migration chain in a
  disposable Postgres and the real local model daemon. Not against a running
  Supabase stack: the HTTP path to PostgREST and storage is covered by a
  contract test against the shipped SQL, not by a live round trip.
- **Deployed:** nothing. Extraction ships disabled.
- **Qualified:** nothing. No model has been measured on real labels.

## Rollout, with extraction still disabled

1. Review and integrate the identity, foundations, queue and worker-evidence
   migrations together. Do not apply the queue migration without the
   worker-evidence one: claim would return no object paths.
2. Apply the chain to staging. Confirm `enabled` is false in
   `product_submission_extraction_settings`; the constraint refuses to enable
   it without a named provider, model digest, prompt version and a non-zero
   cap.
3. Deploy `review-product-submissions` and `cleanup-product-submissions`
   together with the migrations, and install the paired app build.
4. Create the worker account, add it to `product_submission_extraction_workers`,
   and confirm it is **not** in `product_submission_reviewers`; both triggers
   refuse the overlap.
5. Run `prepare_product_submissions.py preflight --mode local` with the worker
   credentials. It writes nothing. It must report the account configured and
   the pinned model installed, vision-capable and at the expected digest.
6. Only then enable extraction with a small pilot cap, and run one submission
   with `--max-jobs 1`. Check the draft appears in the console under the
   current revision, and that the reviewer still has to read every field.

If a completion's answer is lost, `reconcile --job-id --fencing-token` states
what that attempt recorded and what remains reserved. It settles nothing:
elapsed time is not evidence that a call cost nothing.

## What is still missing, precisely

The benchmark cannot start until these exist. No agent can produce them.

- 20 development and 40 held-out **real products**, grouped by brand and
  family so no family spans both splits.
- Photographs of each, taken the way a user would: front, Supplement Facts,
  other ingredients, barcode.
- A **gold label per product, checked by two people independently**, neither
  of whom has seen a model's answer. `gold_template()` emits the blank form;
  it is deliberately not a valid record until filled.

Until then the development split can be run and the wiring measured, and no
statement about provider accuracy is available or should be made.
