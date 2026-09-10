# Submission extraction — plan v3

Supersedes the v2 plan for everything below. Written 2026-09-10 on pipeline
`9d820573`. It merges two independent reviews and records, in one place, what
changed and what I would not do.

Standing constraints, unchanged: extraction stays disabled; no `auto_approved`
disposition and no approval-RPC change before the benchmark qualifies; one
server-side `LabelDraftExtractor`; a human clicks Approve; AI never mints
identities, scores, or clinical claims.

## Status correction

Both reviews open with "the working tree is not clean, Claude has uncommitted
holdout tooling." That was true while they were being written and is not true
now. `catalog_gold.py`, `prepare_holdout_set.py` and their tests were audited,
tested, committed and pushed as `9d820573`; `git status` is clean and local
matches `origin/main`. Codex separately found a path-traversal hole in
`read_candidate` — a `--dsld-id` of `../secret` escaped the blobs directory —
and fixed it. That is the second time it has caught this bug class in a tool of
mine, which is a pattern in my work, not an accident.

## Adopted without change

Field-level metrics rather than one accuracy number. Critical/major/minor error
separation. Product identity kept separate from label-edition identity, reusing
the existing `formula_fingerprint` and `label_record` rather than a second
edition-ID system. Evidence requirements based on field coverage rather than
rigid photo categories. Adaptive capture guidance. Field-level provenance and
reviewer attestations. Risk-based review routing after qualification. A
permanent shadow bank after launch. Certificate expiry and re-verification,
contributing to the verification pillar only and never overriding safety, dose,
clinical evidence or personal fit. `label verified` as a state independent of
enrichment and scoring. Incremental promotion only through the existing
clean → enrich → score path, with periodic full-rebuild parity checks.
Manufacturer, distributor, net quantity and market status as metadata. No
auto-approval on model confidence, ever.

## Three things I would not do as written

**1. Thresholds may not be chosen from the benchmark results.** One review says
accuracy thresholds "must be chosen from the frozen benchmark results." Read
literally that destroys the holdout: a gate picked after seeing the score is
not a gate, it is a description. `HOLDOUT.md` freezes gates before any result
and consumes each candidate once, deliberately. The defensible reading — that
these are engineering targets and not a regulatory guarantee, and that a
threshold may be revised for the *next* frozen round through a dated
amendment — is already how the protocol works. I have not changed any
threshold.

**2. Dropping the GTIN requirement is an owner decision, not an engineering
one.** "Barcode stays required" was decision 3 of 2026-09-08. The
`identity_pending` design in review two is good and I would build it — stronger
human review, front label plus Facts plus manufacturer plus net quantity, no
auto-approval, no publication until identity is confirmed, and the immutable
label-edition identity generated only after human verification. But it reverses
a written decision and touches consent, dedupe and the approval gate, so it
needs your explicit sign-off before any code moves. Until then, barcode stays
required.

**3. The ten-state lifecycle is a migration, not a vocabulary.** Draft →
Submitted → Extraction complete → Label review → Retake required / Label
verified → Enrichment pending → Scored → Release validation → Catalog ready →
Released is the right shape, and "one canonical contract shared by app,
Supabase, worker, console, importer and catalog builder" is exactly right. But
states already exist across all six of those. This is a reconciliation of live
state machines with data in them — an audit of every current state and every
consumer first, one migration, no parallel vocabulary. Scheduled as its own
batch, not folded into another.

## One decision I am putting back to you

**Should warnings be gated?** Both reviews list warnings among the hard safety
gates. I built them as reported-but-not-gated, reasoning that a missed
direction is a copy defect a reviewer sees in the editor while a missed dose is
a claim about a product. Two reviewers disagreeing with me is enough to
reopen it, and on reflection they have the better of it for a health app: "do
not use if pregnant" or "consult a physician if taking anticoagulants" is not
copy.

What blocks a straight 100% gate is the metric, not the principle. Statements
are scored today by exact normalized text match, so a comma would fail a gate
set at 100% and the gate would be worked around rather than met. My
recommendation: gate the **presence** of every printed warning at 100%, and
keep exact wording as a reported metric. That is a scoring change plus a
`HOLDOUT.md` amendment, cheap now because no result exists, and it is the
next thing I would do on your word.

## Phase 0 — gold tooling (complete)

`scan` matches scanned barcodes through the reviewer console's own identity
index and reports the candidate record, what a person compares against the
package, and which required cases the record accounts for. `diff` reports only
the rows a record and a draft disagree about. Coverage counts once per barcode
and counts nothing for a barcode with two candidate editions.

Three detectors earned their design by being measured rather than assumed:
matching units by prefix read the enzyme units GALU and GaIU as grams; matching
rows by exact name reported 12 of a real 21-row prenatal record as
disagreements on wording alone; pairing leftover rows by dose is refused when
the dose is not unique on both sides, because a guess there hides a
contradiction.

Tests now cover ambiguous barcodes, duplicate records, unreadable barcodes,
path traversal, malformed drafts, missing records, reformulated editions, and
the guarantee both reviews asked for by name: after `diff` reads a model's
draft, the gold file is byte-identical and still counts as unfilled.

**The protocol is amended.** A gold record may be two independent human
transcriptions, or one independently sourced transcription plus one human
confirmation of the physical label edition with every disagreement settled.
`sourced_from` records the source, record id, formula fingerprint, import time
and the number of disagreements resolved; one checker must carry
`confirmed_physical_label: true`; and naming a model as a gold source is
refused. The two-person route is unchanged and remains the only route for any
product the catalog does not hold.

## Phase 1 — assemble and freeze 20 + 40

Build `prepare_holdout_set.py import-reference`, which writes a proposed gold
record from a confirmed DSLD candidate and fills `sourced_from`. It imports an
independent transcription; it never imports a draft. Then: choose a
risk-stratified set, photograph every panel, confirm each edition against the
package, settle disagreements, freeze hashes and attestations. Two human checks
for discrepancies, high-risk products and a random sample regardless of route.

Known sourcing gaps, measured: CFU appears in 2 rows per 4,000 products and AFU
in none, so those two cases need a probiotic and an enzyme product confirmed by
eye; `dv_only` is invisible in all 15,103 records, because DSLD carries a
quantity for essentially every row.

## Phase 2 — benchmark

RapidOCR and `qwen3-vl:4b` through one `LabelDraftExtractor`. Reported
separately: identity, product name, serving, row presence, dose, unit, blend
parentage, warnings, printed detail, other ingredients, provenance, abstention.
Each with two denominators, because fields within one label are not independent
observations. Dose, unit and blend nesting gate at 100%. A critical numeric or
unit error blocks automation regardless of confidence or agreement.

Shared preprocessing is tested separately and already has a first result: above
about 25 pixels per em preparation is transparent; between 18 and 23 one dose
row is a coin flip; the app's 2400px sanitise, not the server, is the binding
constraint. Any holdout photograph whose Facts panel spans under about a third
of the frame measures the capture, not the reader.

## Phases 3–8

Unchanged from the reviews and adopted as written: observation mode with every
submission still human-reviewed; selective automation only after qualification,
with dose, units, warnings, identity and complex blends staying in human review
and every automated decision reversible under a distinct disposition; promotion
through the existing pipeline with parity checks; then points ledger,
monitoring, shadow-bank expansion, capture UX and certificates.

Capture UX is not last in value. The preprocessing measurement says framing
guidance protects dose rows before any model sees them, so the adaptive
coverage prompt, camera/library choice, photo reuse and resume-after-interrupt
work should run in parallel with Phase 1 rather than wait for Phase 6.

## What actually blocks this

Real bottles, real photographs, and one person deciding that a record describes
the package in their hand. Tools can select candidates, match barcodes, compare
records, generate templates, compute coverage, list disagreements and score
runs. None of them can make that judgement, and no amount of model agreement
substitutes for it.
