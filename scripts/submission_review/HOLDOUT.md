# Submission extraction holdout — frozen protocol

Status: **protocol amended 2026-09-08 after independent Batch 1 review. The
real 20-development / 40-holdout product photo/gold set is NOT assembled or
frozen. No model has qualified.** The validator and synthetic tests are an
engineering scaffold. The owner must arrange actual captures and two
independent human gold checks; engineering must not invent their attestations.
The product set lives outside git. Nothing in
this document may change after the first provider run on the development
split except through a dated amendment appended at the bottom; the held-out
split may be evaluated exactly once per candidate configuration.

## What this measures

A label-draft extractor (`scripts/submission_review/extraction/`) turns a
submission's photos into a `label_draft_v1` envelope or a typed failure. The
benchmark decides whether one configuration (provider + model digest +
prompt version + preparation config) is good enough to *draft* for a human
reviewer. It never decides what is true about a product; the reviewer does.

Passing this benchmark is a pilot gate, not a clinical standard and not an
accuracy guarantee for any single label.

## The set

| Split | Products | Use |
|---|---|---|
| development | 20 | prompt and preparation tuning; may be run repeatedly |
| held-out | 40 | one evaluation per candidate configuration |

- Products are grouped by **brand/family** so that no family appears in both
  splits (a family is the brand plus product line; both splits should still
  span the families below).
- Every product has its own photos (front, Supplement Facts, other
  ingredients, barcode; optional directions) captured with a phone the way
  a user would, plus a **gold label** checked independently by two people
  who did not use any model output. The model under test can never write or
  edit a gold answer.
- Required case families across the two splits (each must appear at least
  twice in held-out): glare, curved bottle, tiny print, split facts panel,
  combined facts + other-ingredients panel, wrong-slot photo (Directions
  uploaded as Facts), mismatched bottle (front from a different product),
  ambiguous serving basis, nested proprietary blends, multiple forms in one
  row, units `mg / mcg / g / IU / CFU / AFU`, %DV-only rows, serving ranges
  ("1–2 capsules"), foreign-language panel, handwritten text, expired date,
  and **intentionally unreadable** images where the correct output is an
  abstention.
- A separate **OCR / retake** set (≥ 60 photos, majority *acceptable*)
  measures false retake suggestions. It is evaluated with the same
  one-shot rule for its held-out half.

## Where it lives

`reports/submission_holdout/` (git-ignored by the top-level `reports/` rule).
Photos, gold labels and provider outputs never enter git, app assets, a
public branch, a release asset, or a free provider tier.

```
reports/submission_holdout/
  manifest.json            # submission_holdout_v1 (see below)
  freeze.json              # verified, exclusive freeze receipt (no overwriting)
  gold/<product_key>.json  # gold_label_v1
  photos/<product_key>/    # original bytes; sha256 recorded in the manifest
  runs/<run_id>/           # drafts and meta written by a candidate config
  holdout_runs.jsonl       # append-only ledger written by benchmark.py
```

`manifest.json`:

```json
{"schema_version": "submission_holdout_v1", "frozen_at": "<UTC timestamp>",
 "candidates": [{"id": "local-candidate", "configuration": {
   "provider": "<provider>", "model": "<immutable model identifier>",
   "model_digest": "<64 lowercase hex>", "prompt_version": "<version>",
   "prompt_sha256": "<64 lowercase hex>", "preparation": {"version": "<version>"}}}],
 "products": [{"product_key": "h-001", "brand": "Example Brand", "family": "Example Brand/probiotic",
               "split": "holdout", "cases": ["glare", "nested_blend"],
               "gold": "gold/h-001.json",
               "gold_sha256": "<64 lowercase hex>",
               "photos": [{"photo_id": "<UUID>", "path": "photos/h-001/front.jpg", "sha256": "<64 lowercase hex>"}]}]}
```

`gold/<key>.json` (`gold_label_v1`):

```json
{"schema_version": "gold_label_v1", "product_key": "h-001",
 "checked_by": [{"checker": "<first human>", "checked_at": "<UTC timestamp>",
                 "human": true, "independent": true, "model_output_seen": false},
                {"checker": "<second human>", "checked_at": "<UTC timestamp>",
                 "human": true, "independent": true, "model_output_seen": false}],
 "expected": "draft",
 "identity": {"brand": "Example Brand", "product_name": "Magnesium Glycinate", "barcode_digits_seen": null},
 "serving": {"size": "2 capsules", "amount": {"value": 2, "unit_text": "capsules"},
             "servings_per_container": "60", "basis_text": "Amount Per Serving"},
 "other_ingredients": {"text": "Vegetable cellulose", "disclosure_hint": "present"},
 "rows": [{"display_name": "Magnesium (as magnesium glycinate)",
           "amount": {"value": 200, "unit_text": "mg"}, "parent_index": null,
           "is_blend_header": false, "form_text": "magnesium glycinate",
           "percent_dv": 48, "readable": true}]}
```

`expected` is `draft` or `abstain` (intentionally unreadable). `parent_index`
is the zero-based index of the earlier blend header, or `null`. Repeated
printed names, including headers, remain distinct occurrences. `readable: false`
marks rows the checkers agree a careful human cannot read from the photos;
such rows are excluded from recall but still count for "invented" checks.
All identity, serving, disclosure and row fields shown above are required
in gold; use explicit null for unknown/inapplicable values. Preserve raw
barcode leading zeroes and label text. Serving `amount` is optional in a
draft: if gold knows it and the draft omits it, it earns no exact tuple.
The printed `size` and `basis_text` are always evaluated when known.

A candidate configuration writes one file per product into
`runs/<run_id>/<product_key>.json`: a `label_draft_v1` envelope or a typed
failure `{"schema_version": "extraction_failure_v1", "code": "...",
"detail": "..."}`. Each run also includes `configuration.json` with
`{"candidate_id":"local-candidate","configuration":{...}}`; the complete
configuration must equal a candidate predeclared in the frozen manifest.

Each `<product_key>.meta.json` records `latency_seconds`, optional
`cost_microcents` and `cold_start`, plus `sent_inputs`, an array of
`{"input_id":"input-1","path":"inputs/h-001-input-1.jpg"}`. Those paths
resolve inside the run directory to the exact bytes transmitted. The
evaluator verifies their hashes against the draft and verifies the draft's
snapshot against this product's original frozen photos.

For final qualification, every readable product needs a completed human
review measurement in its metadata:

```json
{"review":{"reviewer":"<actual reviewer>","checked_at":"<UTC timestamp>",
 "completed":true,"reviewed_output_sha256":"<SHA256 of exact draft JSON bytes>",
 "critical_errors":0,"manual_seconds":100,"assisted_seconds":60}}
```

The times are measured manual-transcription and assisted-review times for
that same label under the predeclared comparison procedure. They must be
finite and positive. Measurements do not constitute clinical ground truth;
the operator retains the independent review evidence behind them.

## Gates (frozen before any result)

All gates apply to the held-out split. Denominators are reported per
product and per family with 95% Wilson intervals. Abstentions and typed
failures on readable products are reported as **missing coverage** and
remain in both row-recall and exact-tuple denominators. Missing mandatory
latency or human measurements produce `not_evaluated` gates, never passes.
The final verdict is `does_not_qualify` if any evaluated gate fails,
`not_evaluated` if no gate fails but mandatory evidence is missing, and
`qualifies` only when every gate passes on an unused, frozen holdout candidate.
Development and explicitly synthetic miniature sets can never qualify.

| Gate | Threshold |
|---|---|
| Schema-safe output (valid draft or typed failure) | 100% of products |
| Readable ingredient-row recall | ≥ 99% |
| Exact amount / unit / serving-owner tuples on all readable gold rows | ≥ 99% |
| Known identity, serving, form, %DV and other-ingredients field fidelity | ≥ 99% |
| Invented actives (draft rows absent from the label) | 0 |
| Wrong-product substitutions (brand or name from another product) | 0 |
| Order-of-magnitude amount errors (×10 or ÷10 with the same unit) | 0 |
| Printed-unit mismatches after explicit spelling equivalence | 0 |
| Dose accuracy (printed number **and** unit) on matched readable rows | 100% |
| Unit accuracy alone on matched readable rows | 100% |
| Blend nesting (parent header and header flag) on matched readable rows | 100% |
| Printed statements present (directions and warnings reaching the draft) | 100% |
| Expected abstentions honoured (unreadable set) | 100% |
| Critical errors remaining after human review of the drafts | 0 |
| p95 draft latency on all products (cold starts also reported separately) | ≤ 60 s |
| Median reviewer time per accepted label vs manual transcription | ≥ 30% lower, p95 not worse |

Every gate above is also reported **per dimension** — identity, serving, row
presence, dose, unit, blend nesting, printed detail (form and %DV), other
ingredients, and printed statements — under `metrics.per_field`, with two
denominators. `observations` counts fields; `products_without_error` counts
labels. Only the second has independent samples: fields within one label fail
together, because one bad photograph or one misread panel takes several of
them at once, so an interval computed over observations is narrower than the
evidence supports. Qualification decisions read the product interval.

Printed statements are measured twice. **Presence is gated at 100%**: a
warning that never reaches the draft is a warning the reader never gets, and
"do not use if pregnant" is not copy. **Exact wording is reported and not
gated**, because a gate a misplaced comma can fail is a gate that gets worked
around rather than met. A statement counts as present when it is reproduced,
or when a returned statement carries at least 90% of its words; a fragment
does not count.

OCR / retake set (must pass before any automatic user-facing retake
request leaves observation mode): unnecessary-retake rate ≤ 2% on acceptable
photos; per-reason precision ≥ 95%; wrong-slot detection recall ≥ 90%.

"No provider qualifies" is a valid, complete outcome. Manual transcription
in the console remains the path in that case.

## Rules

1. Freeze this file, the manifest and every gold label **before** the first
   provider run. `benchmark.py --holdout <set> --freeze` validates all gold
   attestations, product and photo uniqueness, exact 20/40 counts, disjoint
   brands and families, and at least two held-out examples per required
   case. A known gold brand must agree with its manifest brand; duplicate
   known barcode or brand/product-name identities are rejected. Barcode
   comparison reuses the existing audited GTIN helper; fidelity still
   evaluates the raw printed digits. Photos cannot be copied across products.
   It verifies manifest-declared gold/source-photo SHA256 values and
   writes `freeze.json` exclusively. The receipt hashes the manifest,
   protocol, gold and all original-photo bytes, including predeclared configs.
   `--freeze --synthetic` relaxes population/case-count requirements only and
   marks the receipt permanently nonqualifying. It still verifies provenance.
2. Tune only on the development split. Adapters and prompts are frozen
   (digest, prompt version, prep config) before the held-out run.
3. The held-out split is evaluated **once** per candidate configuration.
   `benchmark.py --split holdout` appends to `holdout_runs.jsonl`; a second
   evaluation of the same complete configuration digest is reported as *consumed* and cannot
   qualify. The Python `evaluate` API also enforces this, not just the CLI.
   Two candidate IDs may not predeclare the same configuration under aliases.
   The ledger is locked while checking and appending to prevent concurrent
   qualifications. A changed configuration, added candidate, modified gold,
   source photo or receipt cannot earn a new qualification on an exposed set. Tuning
   after a held-out failure requires a fresh, untouched evaluation set.
4. The model never sees gold answers; gold checkers never see model output
   before checking. Any gold file that names a provider or model as a
   checker is rejected.
5. Free provider tiers never receive holdout photos. Every adapter records
   the retention precondition it ran under.
6. Reports state n/N for every rate. A rate without its denominator is not
   a result.
7. Confidence values in drafts are cues calibrated against held-out errors;
   they are never a gate, a score pillar, or an approval authority.
8. Run identity includes the exact freeze receipt, selected config, every
   output and metadata file, and actual retained sent-input bytes. Protect
   freeze receipts and the ledger with operator access controls/backups;
   local hashes cannot prevent a privileged operator from deleting all
   evidence and forging a different history.

Required case tokens are `glare`, `curved_bottle`, `tiny_print`, `split_facts`,
`combined_facts_other`, `wrong_slot`, `mismatched_bottle`, `ambiguous_serving`,
`nested_blend`, `multiple_forms`, `unit_mg`, `unit_mcg`, `unit_g`, `unit_IU`,
`unit_CFU`, `unit_AFU`, `dv_only`, `serving_range`, `foreign_language`,
`handwritten`, `expired_date`, and `unreadable`. The two human gold checkers
must confirm the actual case coverage; a tag alone does not establish it.

Printed unit equivalence is deliberately small: `µg`, `μg` and `mcg` are the
same spelling of micrograms. Whitespace/case are ignored. Grams, milligrams,
micrograms, IU, CFU and AFU remain distinct. No clinical unit conversion is
performed. Unit mismatches are a separate critical gate from same-unit
`magnitude_errors`, so a gram/microgram error cannot hide inside the 1%
tuple allowance. Replacing a positive amount with zero, or zero with a
positive amount, is also a critical magnitude error. Explicit conflicting
identity text remains a wrong-product error even if marked `partial`.
Form and %DV fidelity also constrain exact-row credit.

The partial-draft envelope requires `draft_origin: "model"` or
`"human_transcription"`. Model drafts have real `sent_inputs`, each with
`input_id`, `photo_id`, `original_sha256`, `sent_sha256` and optional original
photo `crop` coordinates. Each sourced field cites its exact `input_id`
and matching `photo_id`. `original_sha256` equals the evidence snapshot;
`sent_sha256` hashes the actual transmitted crop/reencoded bytes. Human
transcription uses `provider: "human"`, `model: "human"`, empty sent inputs
and photo sources without model input IDs. A human recorder's identity is
enforced separately by the authorized database writer. Partial amounts may
have a null number or unit; no fake value or fake request is required.

## Amendments

2026-09-08 — Independent-review correction R4–R8: restored missing-inclusive
quality denominators; implemented mandatory reviewer/latency gates; added
field-fidelity measurement and one-to-one parent/row matching; distinguished
unit spellings and original/sent image provenance; added a real freeze
verification scaffold and enforced predeclared one-use candidate evaluation.
This amendment corrects the Batch 1 protocol/implementation; it does not
assert that the real data set or independent human checks exist.

2026-09-10 — Per-dimension reporting. An aggregate accuracy hides which field
failed, and the fields do not carry equal risk: a run can read ninety per
cent of a label correctly and still have put every dose in the wrong unit.
`metrics.per_field` now reports each dimension separately, with a
product-level denominator alongside the field-level one because fields within
a label are not independent observations. Three gates are added at 100% —
dose, unit and blend nesting — because those are the three errors a reviewer
is least likely to catch by eye and the three that change what a person
swallows. `gold_label_v1` gains a required `statements` array (explicit `[]`
when the label prints none) so directions and warnings can be measured at
all; they are reported, not gated. This tightens the protocol before any
result exists and before the set is assembled; no threshold was loosened.

2026-09-10 — Shared preparation measured, not gated. The step every candidate
shares was measured against genuine 6pt print
(`docs/release_candidates/shared_preprocessing_fine_print_2026_09_10.md`).
Preparation is transparent above roughly 25 pixels per em and can drop a dose
row between 18 and 23. Because both candidates read the same prepared bytes,
that loss appears in a benchmark as agreement. Any holdout photograph whose
Facts panel spans less than about a third of the frame width therefore
measures the capture, not the reader, and must be recorded as such.

2026-09-10 — A second route to gold, for products the catalog already knows.

Typing sixty labels by hand is why this set does not exist. The route that
removes most of that typing without weakening the measurement is a
transcription that already existed and was not derived from our photograph:
the NIH DSLD records in the released catalog were written from the physical
label by someone else, before any of this. A gold record may therefore be
either:

* **two independent human transcriptions** — unchanged, and still the only
  route for any product the catalog does not hold; or
* **one independently sourced transcription plus one human confirmation of
  the physical label edition**, with every disagreement between the record
  and the photographed label settled by a person.

Both give gold two sources of error with no cause in common. Two models
reading one photograph do not, however accurate each is: they share the
photograph and the preparation step, so a row preparation deleted is missing
from both and their agreement reads as confirmation. A model may never be
named as a gold source, and `load_gold` refuses one that is.

A reference-sourced record carries `sourced_from` with the source name,
record id, formula fingerprint, import timestamp, and the number of
disagreements a person settled. It needs one checker with
`confirmed_physical_label: true`. That confirmation is the one judgement no
record and no tool can make: whether a record written years ago describes the
package in a person's hand. The record's own version and date identify the
record, not the package, and cannot stand in for it.

The physical label always wins. Where the record is stale, reformulated, or
its edition ambiguous, the product goes to the two-person route or leaves the
set. `scripts/prepare_holdout_set.py scan` proposes candidates and `diff`
lists the rows to settle; neither writes a value into a gold record, and a
test asserts a gold file is byte-identical after a comparison runs.

2026-09-10 — Warnings gated on presence. Two independent reviews put warnings
among the hard safety gates and were right to: on a health product a dropped
"consult a physician if taking anticoagulants" is not a copy defect. The gate
is presence rather than exact text, so it measures whether the warning
arrived, and the verbatim comparison stays beside it as a reported metric.
Frozen before any result exists; no existing threshold was loosened.

2026-09-10 — Unit-family detection moved to the pipeline's own vocabulary.
`catalog_gold.unit_case` kept a local spelling table, which missed
"Milligram(s)" across 820 rows of the corpus and reported AFU as absent from
the catalogue entirely — probiotics print "Billion AFU", never a bare token,
so a person would have gone hunting for a product they already had. Mass
spelling now comes from `normalization.canonicalize_mass_unit`, the one owner
of those aliases; activity units match on a whole word, which keeps the
enzyme units GALU and GaIU out of the gram and IU families.

2026-09-10 — Identity and serving-size qualification gates. These fields were
already measured in `metrics.per_field`, but measurement without enforcement
could let a candidate qualify with the right ingredient rows attached to the
wrong product or serving basis. `identity_accuracy` and `serving_accuracy` now
use the same independent product-level denominator as the existing dose, unit,
blend-nesting and statement-presence gates, each at 100%. This is a tightening
before any real provider run; no result or threshold was loosened.

2026-09-11 — The reference route's comparison, tightened after an adversarial
review. `import-reference` now refuses a draft that is not a reading of the
product's own photographs (checked by content hash); refuses to replace
anything but a pristine template, so a half-finished human transcription is
never discarded; treats a row the photograph shows but the reader could not
name as a disagreement, since that is what a reformulation looks like; keeps
Other Ingredients rows out of the Facts rows, where they had been scored twice;
compares %DV, which gold takes from the record; and compares typed statements
against the photographed ones in both directions. A refusal names the rows and
the record's value but never the model's reading.

Follow-up counterexamples require rehashing the actual files, not merely
trusting manifest hash strings; resolving the gold path within the set before
any write; treating partial/unreadable statements as unresolved rather than
absent; and naming rows from the independent record, never echoing a
model-invented name in a blinded refusal.

One condition this code cannot enforce, and the route depends on it: the
person who confirms a product must not have seen a model's reading of that
product first — including through `diff`, which prints both sides for a
reviewer's triage. Where they have, the product takes the two-person route.
