# Submission extraction holdout — frozen protocol

Status: **protocol frozen 2026-09-08 (Batch 1).** The product set itself is
assembled by the owner under this protocol and lives outside git. Nothing in
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
  gold/<product_key>.json  # gold_label_v1
  photos/<product_key>/    # original bytes; sha256 recorded in the manifest
  runs/<run_id>/           # drafts and meta written by a candidate config
  holdout_runs.jsonl       # append-only ledger written by benchmark.py
```

`manifest.json`:

```json
{"schema_version": "submission_holdout_v1", "frozen_at": "2026-09-..",
 "products": [{"product_key": "h-001", "family": "brand-x/probiotic",
               "split": "holdout", "cases": ["glare", "nested_blend"],
               "gold": "gold/h-001.json",
               "photos": [{"path": "photos/h-001/front.jpg", "sha256": "..."}]}]}
```

`gold/<key>.json` (`gold_label_v1`):

```json
{"schema_version": "gold_label_v1", "product_key": "h-001",
 "checked_by": [{"checker": "initials-A", "checked_at": "2026-09-..T..Z"},
                {"checker": "initials-B", "checked_at": "2026-09-..T..Z"}],
 "expected": "draft",
 "identity": {"brand": "Example Brand", "product_name": "Magnesium Glycinate"},
 "rows": [{"display_name": "Magnesium (as magnesium glycinate)",
           "amount": {"value": 200, "unit_text": "mg"}, "owner": null,
           "readable": true}]}
```

`expected` is `draft` or `abstain` (intentionally unreadable). `owner` is
the blend header the row belongs to, verbatim, or `null`. `readable: false`
marks rows the checkers agree a careful human cannot read from the photos;
such rows are excluded from recall but still count for "invented" checks.

A candidate configuration writes one file per product into
`runs/<run_id>/<product_key>.json`: a `label_draft_v1` envelope or a typed
failure `{"schema_version": "extraction_failure_v1", "code": "...",
"detail": "..."}`, plus optional `<product_key>.meta.json` with
`{"latency_seconds": 12.4, "cost_microcents": 160, "cold_start": false}`.

## Gates (frozen before any result)

All gates apply to the held-out split. Denominators are reported per
product and per family with 95% Wilson intervals. Abstentions and typed
failures are reported as **missing coverage**; the quality gates below are
measured on products the configuration actually drafted, and the coverage
figure is published beside the verdict rather than hidden inside it.

| Gate | Threshold |
|---|---|
| Schema-safe output (valid draft or typed failure) | 100% of products |
| Readable ingredient-row recall | ≥ 99% |
| Exact amount / unit / serving-owner tuples on recalled rows | ≥ 99% |
| Invented actives (draft rows absent from the label) | 0 |
| Wrong-product substitutions (brand or name from another product) | 0 |
| Order-of-magnitude amount errors (×10 or ÷10 with the same unit) | 0 |
| Expected abstentions honoured (unreadable set) | 100% |
| Critical errors remaining after human review of the drafts | 0 |
| p95 draft latency on the bounded set (cold start reported separately) | ≤ 60 s |
| Median reviewer time per accepted label vs manual transcription | ≥ 30% lower, p95 not worse |

OCR / retake set (must pass before any automatic user-facing retake
request leaves observation mode): unnecessary-retake rate ≤ 2% on acceptable
photos; per-reason precision ≥ 95%; wrong-slot detection recall ≥ 90%.

"No provider qualifies" is a valid, complete outcome. Manual transcription
in the console remains the path in that case.

## Rules

1. Freeze this file, the manifest and every gold label **before** the first
   provider run. The manifest's `frozen_at` and the gold files' checksums
   are recorded in the first run receipt.
2. Tune only on the development split. Adapters and prompts are frozen
   (digest, prompt version, prep config) before the held-out run.
3. The held-out split is evaluated **once** per candidate configuration.
   `benchmark.py --split holdout` appends to `holdout_runs.jsonl`; a second
   evaluation of the same configuration is reported as *consumed*. Tuning
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

## Amendments

(none)
