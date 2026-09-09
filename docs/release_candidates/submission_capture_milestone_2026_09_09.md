# Submission milestone: Batches 0–1 integrated, Batch 2 durable capture

Date: 2026-09-09. Source integration and app capture work only. No migration
was applied, no edge function deployed, no catalog published, no provider
called, and no clinical or scoring artifact changed.

## What now works for the user

A contribution stops being all-or-nothing.

Photos are written to app-private storage as each one is taken, so a crash,
the OS reclaiming the app behind the camera, or a dead connection in a shop
aisle no longer throws the work away. Reopening the same barcode offers
"Finish your photos?" and resumes at the first panel still missing rather than
at the beginning or falsely at review. Contributions gained a "Not sent yet"
section listing what this device is still holding, because rescanning the same
barcode was previously the only route back to an interrupted capture.

Three rules the flow now keeps that it did not before:

- Only the server's own receipt retires a local capture. Nothing on this
  screen can read as "submitted and waiting for review" when it is not.
- A recovered capture submits under the id it was saved with, so finishing it
  replays the server's idempotent sequence instead of opening a duplicate.
- Deleting a photo deletes it from disk, and a capture whose bytes no longer
  match their manifest is refused with an explanation rather than sent.

## Commits

Pipeline (`3bf7ec17` merge; published):

| Commit | Content |
|---|---|
| `3bf7ec17` | Merge of Batches 0 and 1: identity hardening plus foundations and their review corrections |

App (published):

| Commit | Content |
|---|---|
| `c242d50` | Merge of Batches 0 and 1 |
| `a73943c` | Durable capture store, recovery offer, save before the network call |
| `bb10349` | "Not sent yet" section on Contributions |
| `2fa854b` | Do not resume another attempt's photos under this retry |
| `708fc76` | One owner for identity, hashing and category reading, with guards |
| `2b51b06` | Keep a capture from the first photo rather than from submit |
| (head) | Submit a recovered capture under the id it was saved with |

## Verification

| Check | Result |
|---|---|
| Pipeline affected slice on the merged tree | 742 passed |
| SQL harness, disposable Postgres, real migration chain | 39 cases pass |
| Deno edge tests; both entrypoints type-check | 76 passed |
| Flutter scanner, contributions, services, safety invariants | 1,271 passed |
| Capture sheet including recovery | 26 passed |
| Single-owner invariants | 5 passed |
| `flutter analyze lib` | clean |
| iOS simulator build and launch | succeeds, app renders |

Two guards were verified by breaking them on purpose: reintroducing GTIN
zero-padding turns the single-owner suite red, and removing the recovered-id
fix turns the resume test red. A guard that cannot fail is not a guard.

## Implemented, merged, deployed, device-tested

- **Implemented and merged:** Batches 0 and 1 in both repositories, and the
  Batch 2 capture persistence and recovery work. Both mains are pushed.
- **Deployed:** nothing. The migration is not applied and neither edge
  function is deployed. Old clients fail closed on consent and the cleanup
  claim shape changed, so migration, functions and app must roll out together
  in a verified window.
- **Device-tested:** no. The app builds, launches and renders on the
  simulator. Physical-camera behaviour cannot be proven there, but that is the
  only part that needs a phone: the draft list, a restored capture and the
  error states can be exercised from saved-photo fixtures under a controlled
  signed-in setup, and that visual pass is still owed. The new screens
  currently have widget coverage, not a rendered inspection.

## Remaining defects and decisions

1. **The release gate does not pass, and that stands unresolved.** Enrichment
   records a content hash of every data file, and the artifacts on disk match
   no recent commit: `origin/main` before any of this work hashes to
   `34f64057…` while the manifests record `bced5f9d…`. No build was running.
   Two things are true at once and neither cancels the other: the mismatch
   predates this work, *and* the axis hoist changed a data file, so a rebuild
   is genuinely owed before any catalog ship. Documented, not bypassed. This is
   also not a claim that all 37 brands must rerun to verify capture work, which
   touches no data file at all; sequencing the rebuild is a separate decision.
2. **On-device OCR (B2.6, B2.7) is deliberately not built.** Its own benchmark
   gates it, and that benchmark does not exist yet.
3. **No revision UI.** The server accepts evidence revisions; the app does not
   yet open one. Intake deliberately answers `open_existing` for a pending
   retake so current clients stay correct.
4. **Two questions belong to the evidence-axis track, not to capture.**
   `liposomal probiotics` and `liquid probiotics` have no assessment axis yet.
   Neither "enhanced" nor "good (rapid uptake)" establishes the right
   scientific standard, so they stay open on the clinical track and block
   nothing here.

## Next milestone

Batch 3: the extraction queue, the worker principal and the development
evaluation harness, built and tested against the frozen contracts without
touching held-out answers. Choosing a production provider stays blocked on the
real 20/40 photo and gold set, which is physical work no agent can do, but the
queue, worker and reviewer tooling do not wait on it.

Running separately: the assessment-axis classification, continuing in
reviewable batches with exact form fingerprints and sources rather than
keyword matching, and coverage enforcement staying off until the population is
actually classified.
