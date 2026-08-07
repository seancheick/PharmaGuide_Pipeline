# Reviewer workflow — one file out, one file back

Replaces the earlier 4-file packet (brief + HTML + answer CSV + brand list).
That packet asked a clinician to hand-sum six columns 120 times; the first
return failed arithmetic on 38% of rows with a uniform +10 offset (the
quality-checks column silently dropped from the sum) and carried an invalid
`reviewer_slot`, breaking the join it existed to guarantee.

Now the reviewer writes six numbers and a few words. The machine does the
arithmetic and restores the frozen column contract.

## Send

```bash
python3 scripts/audits/v4_reviewer_benchmark/build_review_doc.py \
    --slot 2 --reviewer-id KEVIN --out /tmp/out
```

Writes `REVIEW_<id>.md` (everything the reviewer needs — instructions, 120
products in their own randomized order, a fill-in block under each) and
`.slotmap_<id>.json`. Fill in the return address and deadline at the top before
sending. Keep the slotmap: it is the only path from a returned file back to the
frozen template, and without it ICC(A,1)/ICC(A,3) cannot be fit.

## Receive

```bash
python3 scripts/audits/v4_reviewer_benchmark/parse_review_doc.py \
    --doc REVIEW_KEVIN.md --slotmap responses/slotmap_KEVIN.json --out responses/
```

Computes `overall_0_100`, restores slot/order/round, and validates ranges,
half-point increments, enum values, duplicate and unknown IDs, missing scores,
and `caution`/`blocked` without a driver. **A file with any error writes no
CSV** — broken data cannot quietly enter the study. A blank template correctly
produces 720 errors (120 x 6 empty pillars).

## What is blinded out

Only the two artifacts a reviewer may receive are read. Neither baseline key is
ever opened. No engine score, threshold, denominator, penalty, or
development/holdout split appears in the generated file. `review_sequence` — the
hidden master join key — is withheld.

`third_party_programs` renders **name only**. It holds dicts carrying our own
`{"verified": true}` verdict, and `str(dict)` once leaked that into 20 blinded
blocks, pre-answering the exact pillar the reviewer is meant to judge.

## Data-defect flags

Products carry inline `⚠ DATA NOTE` blocks for our own extraction gaps, so a
reviewer never has to guess whether we already know: zero quantities, missing
units, implausible serving frequencies, parent-total-then-component-forms rows
(do not add them), and `%DV` values internally inconsistent with the amount.
The `%DV` reference in `dv_reference.json` is derived from all 13,271 shipped
blobs (median amount implying 100% DV per ingredient|unit, >=8 observations),
so it encodes no scoring policy and cannot drift from a hand-typed table.

Counts quoted in the instructions are computed at generation time and written to
`COUNTS.json` — never retyped. An earlier draft hand-copied them and got two
wrong.

## Contents

- `sent/` — the exact document each reviewer received (audit trail)
- `responses/` — returned answers in the frozen column contract, plus the
  slotmaps needed to parse them
- `pending_v7/` — prerequisites for the next freeze (amendment, registry,
  reviewer provenance)
