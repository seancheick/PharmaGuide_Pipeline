# Submission extraction — the plan

One document. It replaces plan v3 and the two review threads it merges, so
there is one place to read and one place to change. Written 2026-09-10 on
pipeline `ecaa9a4e`.

Standing constraints: extraction stays disabled; no `auto_approved` and no
approval-RPC change before the frozen holdout qualifies; one server-side
`LabelDraftExtractor`; a human clicks Approve; AI never mints identities,
scores or clinical claims; barcode stays required until that decision is
reversed in writing.

## Where things actually stand

Done and pushed: the draft envelope, worker and queue; deterministic checks;
the grounding verifier wired at the boundary; per-dimension benchmark
reporting with gates on dose, unit, blend nesting and warning presence; the
shared-preprocessing measurement; the barcode coverage tool; and the protocol
amendment that lets a pre-existing independent transcription serve as gold
when a person confirms the edition.

Not done: `import-reference`, the 20+40 set itself, the benchmark run, and
everything downstream of it.

## What is actually blocking

Real bottles, real photographs, and one person deciding that a record
describes the package in their hand. Tools can select candidates, match
barcodes, compare records, generate templates, compute coverage, list
disagreements and score runs. None can make that judgement, and no amount of
model agreement substitutes for it.

## Phase 1 — `import-reference`, then assemble and freeze

`prepare_holdout_set.py import-reference` writes a proposed gold record from a
confirmed catalog candidate. It must: load the candidate through the existing
identity index; verify the record fingerprint; compare record against the
photographed label; refuse unresolved disagreements; require explicit
physical-label confirmation; write atomically; update the manifest hash; and
leave an immutable audit record of source and reviewer. It imports an
independent transcription and never a draft.

Then: choose a risk-stratified set, photograph every panel, confirm each
edition against the package, settle disagreements, freeze hashes and
attestations. Two human checks for discrepancies, high-risk products and a
random sample regardless of route. Products with no reliable catalog match
take the two-person transcription route.

Measured sourcing notes: `dv_only` is invisible in all 15,103 catalog records
because DSLD carries a quantity for essentially every row, so it must be found
by eye. CFU and AFU exist but are rare and are printed as compound units
("Billion AFU"); the coverage tool now reads those correctly.

**Capture UX runs in parallel here, not at the end.** The preprocessing
measurement says a Facts panel spanning under about a third of the frame loses
dose rows before any model sees them, so framing guidance protects the
benchmark's own inputs. With it: adaptive panel coverage rather than a fixed
checklist, camera/library choice, reusing one photo for several roles, retake
and resume, OCR UPC suggestion with manual entry, and Sentry events.

## Phase 2 — benchmark

RapidOCR and `qwen3-vl:4b` through one `LabelDraftExtractor`. Reported
separately: identity, product name, serving, row presence, dose, unit, blend
parentage, warning presence, warning wording, printed detail, other
ingredients, provenance, abstention. Two denominators each, because fields
within one label are not independent observations. Gates at 100% on dose,
unit, blend nesting and warning presence. A critical numeric or unit error
blocks automation regardless of confidence or agreement between extractors.

Shared preprocessing is tested separately, and independent-extractor agreement
counts as evidence only alongside that test — two readers of one prepared
photograph share its losses.

## Phase 3 — observation mode

Extraction runs in production and approves nothing. Every submission still
gets human review. Grounding and deterministic checks report. Agreement is
measured by field and severity against gold. Shadow samples are compared with
human decisions.

## Phase 4 — selective automation

Only after qualification. Low-risk, independently agreeing fields become
auto-candidates; dose, units, warnings, identity and complex blends stay in
human review. Automated decisions carry a distinct disposition and remain
reversible. Permanent random human sampling continues.

## Phase 5 — promotion and operations

Promotion through the existing clean → enrich → score path, never a second
one, with periodic full-rebuild parity checks proving incremental equals full.
Then the points ledger, scheduled monitoring, certificate re-checks, and
shadow-bank expansion.

## Identity and lifecycle (own batches)

**Canonical identity**, reusing `formula_fingerprint` and `label_record`
rather than a second edition-ID system: optional GTIN, brand, product name,
package/net quantity, manufacturer/distributor, formula fingerprint, immutable
label-edition evidence digest, market status. Product family is separate from
label edition.

**No-GTIN submissions** would use that same record with `identity_pending`:
stronger human review, front label plus Facts plus manufacturer plus net
quantity, no auto-approval, no publication until identity is confirmed, and
the label-edition identity generated only after human verification. **This
reverses the written decision of 2026-09-08 that barcode stays required, so it
needs explicit sign-off before any code moves.** It is one identity system
with an optional GTIN, never a second submission architecture.

**The lifecycle** — draft, submitted, extraction complete, label review,
retake required or label verified, enrichment pending, scored, release
validation, catalog ready, released — is the right shape, and one contract
shared by app, Supabase, worker, console, importer and catalog builder is the
right rule. But states already exist across all six with live data, so this is
an audit of every current state and consumer, then one migration, never a
parallel vocabulary. A verified label must not disappear because enrichment or
scoring fails.

**Certificates** are label claims. Distinguish printed claim, exact product or
SKU verification, brand-only, expired, and unresolved. Evidence contributes to
the verification pillar only and never overrides ingredient safety, dose
warnings, clinical evidence or personal fit.

## Two things this plan will not do

**Thresholds are not chosen from the results.** A gate picked after seeing the
score is not a gate, it is a description. `HOLDOUT.md` freezes gates before
any result and consumes each candidate once. That they are engineering targets
rather than regulatory guarantees is true and already how the protocol reads;
a threshold may be revised for the *next* frozen round through a dated
amendment.

**No second brain.** Every concern keeps one owner: GTIN identity in
`gtin.py`, catalog lookup in the console's identity index, mass-unit spelling
in `normalization.canonicalize_mass_unit`, row reading and text normalization
in `benchmark.py`, label validation in `envelope.py`, approval in the database.
This rule has been broken three times in this work — a second draft-to-label
mapper, a second validator, and a local unit table that missed 820 rows and
hid AFU entirely. Each was deleted rather than kept in sync. A near-duplicate
still stands: `_strip_parenthetical_groups` is nested inside a function in
`enrich_supplements_v3.py` and cannot be imported, so `catalog_gold` has its
own. Lifting it is a change to the enricher and belongs in its own batch.
