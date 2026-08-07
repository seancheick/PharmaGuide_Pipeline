# Reviewer provenance — must appear in the final validation report

Recording this because the report has to state how each panel member's ratings
were produced. It is not a blocker; the owner has decided. It is here so the
decision is visible rather than inferred from a blank field.

## Slot 1 — PHAM · returned 2026-08-06 · 120/120 complete

Mechanically clean: 120 unique IDs, exact coverage of the frozen set, zero
duplicates, zero range/increment/enum errors, every `caution`/`blocked` carrying
a driver, every row carrying sources. Arithmetic computed by
`parse_review_doc.py`, not by hand — 0 failures.

Followed the protocol additions: 99 rows carry the required
"Verification 7.5 = neutral, nothing establishable" justification, 5 apply the
broken-frequency one-serving rule, and one row (PG-3B4535CCF789) correctly
*overrode* a data note, arguing the eight-times-daily direction is a genuine
five-day labeled regimen rather than our extraction defect.

**Disclosure.** A draft returned alongside this file carried the header
"AI CLINICAL ADJUDICATION / SHADOW REVIEW — NOT AN INDEPENDENT BLINDED HUMAN
REVIEW" and `prior_ai_review_seen` on every row. The submitted CSV carried
neither, and the owner confirmed the reviewer and the assisting agent work
together and green-lit proceeding. `protocol_deviation` is therefore recorded
as `none`.

**What the report must say:** these ratings were produced with AI assistance and
with a prior AI pass over the same 120 products visible. That does not make them
wrong — the file is the most internally consistent review received — but it
means slot 1 is not evidence of *independence from the engine's reasoning*, only
of agreement with a clinically-argued assessment. State it plainly and let the
reader weigh it. Do not describe slot 1 as "blinded" without this caveat.

If slots 2 and 3 are produced without prior-AI exposure, report the
three-reviewer ICC both with and without slot 1. The protocol already provides
the mechanism: primary analysis plus an all-locked-responses sensitivity arm.

## Slot 2 — KEVIN · issued 2026-08-06 · outstanding
## Slot 3 — unassigned · issued 2026-08-06 · outstanding

Each received an independently randomized product order (verified distinct).
For these two, prior-AI exposure should be avoided if at all possible — with
slot 1 already assisted, they are what carries the independence claim.

## Two zero-variance signals to watch when the panel closes

- **QUALITY = 10 on all 120 (slot 1).** Contributes nothing to engine-vs-human
  comparison. Possibly caused by the 2026-08-06 narrowing of that pillar's scope
  to catalog-level signals only, done to stop dose risk being counted three
  times. If slots 2 and 3 do the same, the pillar needs rethinking before any
  calibration decision rests on it.
- **VERIFICATION = 7.5 on 106 of 120.** Expected — that is the defined neutral
  doing its job where nothing was establishable — but it means the pillar will
  carry almost no discriminating signal, independently corroborating the earlier
  finding that verification is near-inert across most of the catalog.
