# Live integration and reviewer workstation — milestone handoff

> Historical milestone report. The subsequent
> [workstation audit](submission_workstation_audit_2026_09_09.md) corrects its
> integration scope, readiness races, candidate fingerprint and artifact-state
> claims. Use that audit for the next handoff; this is not a deployment sign-off.

2026-09-09. Continued from pipeline `541b456c` and app `bce3624`; both verified
as ancestors. Source and local verification only. Extraction remains disabled,
nothing was deployed, no catalog was rebuilt, and no paid or remote model was
contacted.

## 1. The integration gap is closed

The audit listed "real authenticated HTTP through PostgREST + Storage + worker"
as unproven. It is now proven, and it is not a regex over migration text.

A disposable local Supabase stack, a submission created through the production
RPCs by its owner's own session, a real JPEG uploaded to Storage, and the actual
queue client driving PostgREST with a real worker JWT. Claim, private download
under the lease-scoped policy, shared preparation, shared extractor, completion.
The draft comes back attributed to the machine, in model origin, naming the
input it was sent, job at `review_ready`, budget row settled.

The authorization surface is exercised rather than described:

| Case | Result |
|---|---|
| Worker with no live lease reads the photo | refused |
| Worker after its job completes | refused |
| Owner reads their own photo | allowed |
| Signed-in non-worker claims | 403, worker error |
| Anonymous claims | 401, before the function |
| Extraction disabled | 55000, extraction is disabled |
| AI consent retired | nothing leased, so nothing read |
| Finished job claimed again | not handed out, no second draft |

Committed as a skipped-by-default test: it runs only against a local stack at a
literal loopback address, so it can never reach a linked project.

## 2. The local model failure is diagnosed

The audit's 60-second `provider_unavailable` was left open. Measured rather
than guessed.

qwen3.5 answers a trivial text prompt in 50 seconds and never finishes a vision
request inside 200, with or without thinking. gemma4 completes the same
synthetic label in about 12. Measured while the Supabase stack was also running
on a 16 GiB machine, so this is a practical observation on this hardware, not a
verdict on the model.

gemma4's own failure was the interesting one: a valid JSON prefix, then a
whitespace loop until the budget ran out. Deterministic, 1,248 identical
characters over four runs, triggered by the image and the prompt suffix
together rather than either alone. Two settings changed under a new candidate
identity, `label-draft-local-v3`, because the request body is part of what a
result is attributable to:

- thinking off: 19.8s to 12.0s on identical input, same answer
- a small repeat penalty: breaks the loop and the reading completes

The penalty is not a cure. Prepared bytes, which differ from the raw file, can
still loop, so the guard stays and its message got sharper: an incomplete
answer and a non-local answer are now different sentences. An incomplete
reading is refused rather than parsed. Whether these settings are good enough
is a question for the held-out benchmark.

## 3. The approval page

Two problems, fixed where the reviewer is already looking. It could refuse to
approve without saying why, and it could approve fields nobody had read.

A readiness panel lists what stands between the reviewer and Approve, in
sentences that name the next action: "Read and tick 3 more fields", "Run the
barcode check to confirm this product is not already in the catalog", "Choose
the one photo that becomes the catalog picture". Approve is disabled until the
list is clear and carries the first blocker as its title, because a disabled
button with no reason is a dead end.

Each critical field gets a tick, bound to the exact payload digest and evidence
revision, so one edit or one new photo withdraws them. Corrections are not
asked for a catalog picture or a barcode check. A help drawer carries plain
definitions in one shared JSON, including the sentence the submitter reads for
each rejection reason, and describes model confidence as a hint that can be
confidently wrong. Keyboard: j, k, s, a, and ? for help, never while typing.

This sits on top of the server's gates, not in place of them.

## 4. Verification

| Run | Result |
|---|---|
| Pipeline fast backstop | 14,038 passed, 42 skipped |
| SQL harness, real chain, with concurrency and advisors | 70 cases pass |
| Flutter safety invariants and services | 1,203 passed |
| Deno edge tests | 76 passed |
| Live stack integration | 6 passed |
| Approval readiness, executed against the shipped console | 11 passed |
| Real browser render of the approval page | 2 of 5 done, 3 blockers, Approve refused with its reason |

## 5. Four states

- **Implemented:** live integration proof, model diagnosis and settings, the
  reviewer readiness workstation.
- **Integrated and tested:** locally, including real authenticated HTTP through
  PostgREST and Storage with a real worker JWT.
- **Deployed:** nothing. Extraction ships disabled.
- **Qualified:** nothing. No accuracy claim exists, and none can until the
  photo benchmark exists.

## 6. What remains

- **Batch actions** for individually checked items are not built. The readiness
  gate they must reuse now exists, so each item can enforce its own revision,
  identity and evidence rather than inheriting a neighbour's.
- **The photo benchmark**: 20 development and 40 held-out real products with
  independent two-person gold checks. It blocks qualification, nothing else.
- **`scripts/test.sh release`** stays blocked by the pre-existing
  `data_vs_enriched` fingerprint mismatch. Not bypassed, not rerun.
- **Five deleted pipeline artifacts** remain deleted in the working tree,
  untouched as instructed: two device screenshots, a Flutter suite log and two
  report CSVs.
