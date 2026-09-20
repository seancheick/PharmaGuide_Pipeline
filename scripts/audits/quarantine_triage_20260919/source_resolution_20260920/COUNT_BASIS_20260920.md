# Phase-3 source resolution — canonical count basis (2026-09-20)

Three documents summarised this phase with three different totals. None of them was
wrong about the underlying work; each counted a different unit, and none of them
said which. This file fixes the denominators so the summaries can be compared, and
`count_reconciliation_20260920.py --check` asserts every number below against
`SOURCE_RESOLUTION_RECEIPTS_20260920.json` and the two frozen-replay artifacts.

Reproduce with:

```bash
source scripts/python_env.sh
"$PG_PYTHON" scripts/audits/quarantine_triage_20260919/source_resolution_20260920/count_reconciliation_20260920.py --check
```

## Basis 1 — receipt items (the ledger's own unit of record)

One item per product-and-issue, exactly as recorded in the receipts ledger.

| Section | Items | Corrections | Confirmed correct | Withheld | Non-scoreable |
|---|---:|---:|---:|---:|---:|
| A — E2 vitamin-unit defects | 6 | 3 | — | 3 | — |
| B — `needs_info` | 4 | — | 1 | — | 3 |
| C — vitamin-A form gap | 5 | 5 | — | — | — |
| D — folate residuals | 7 | 2 | 5 | — | — |
| E — serrapeptase 269360 | 1 | 1 | — | — | — |
| **Total** | **23** | **11** | **6** | **3** | **3** |

The section-level `vitamin_e_note` under A is a finding *about* three already-counted
rows (231334 / 231335 / 263865), not an additional item, and is not counted.

## Basis 2 — distinct products

| | Count | Ids |
|---|---:|---|
| Products carrying a correction receipt | **10** | 201420, 223563, 223572, 228823, 243799, 243808, 243812, 243815, 269360, 328644 |
| Of those, **applied** | **9** | all of the above except 201420 |
| Of those, **reported but not applied** | **1** | 201420 |
| Products explicitly withheld | 3 | 231334, 231335, 263865 |
| Products intentional non-scoreable | 3 | 12300, 254396, 254413 |
| Products confirmed correct | 6 items / 2 products | 75291, 246430, plus the folate rows of 228823 / 243799 / 243812 / 243815 |
| **Distinct products carrying any receipt** | **18** | — |

**`201420` is the only receipt that is not applied.** Its declared-total row is named
`Folic Acid` and is byte-identical to its own child row, so the per-row correction
mechanism cannot scope a rename to the total without renaming the child too. It is a
pre-existing folate double-count (`pct_ul` 161.55) with the dose-safety/folate owner —
reported, never silently dropped, and not a source question.

## Basis 3 — measured on the frozen corpus

| Measurement | Value |
|---|---:|
| Row-level records compared / changed | 15,414 / **9** |
| Scored records compared | 15,412 |
| Score changes | **0** |
| Conclusion changes | **9** |
| Quarantine exits / new entries | **8** / **0** |
| Safety changes | **2** (243808, 246430) |
| Changes outside the intended family | **0** |

The 9 row-level changes are exactly the 9 applied corrections. `269360` changes row-level
(0 NP → 40,000 SPU) but not its scored conclusion: its residual quarantine is an
identity-scoring condition, not a missing dose. `246430` appears in the scored changes
because the folate parent-total contract altered its dose-safety outcome even though its
source record needed no correction.

## Reconciliation of the previously published totals

| Where | It said | Basis it was actually using |
|---|---|---|
| Pharmacist packet (before this correction) | 10 corrections / 10 products, "1 not authorable" | distinct products (correct), applied/not-applied conflated |
| Reconciliation table | 11 / **9** / 3 / 3 | receipt items for corrections, but its "9" also counted non-receipt rows in the same table (EDTA ×16, the two GHOST-SUSPECT PMIDs, the 49 suppressed depletion rows, the `omission_reason` enum debt and the static-audit row) |
| Review summary | 11 / **7** / 3 / 3 | receipt items for corrections; the extra "confirmed correct" row is the `vitamin_e_note`, which is a finding about three counted rows, not an item |
| **This file (derived from the ledger)** | **11 / 6 / 3 / 3 = 23 items** | receipt items, with the note excluded |

The authoritative totals are **11 corrections, 6 confirmed correct, 3 withheld,
3 intentional non-scoreable (23 receipt items)**, **10 products with a correction
receipt**, **9 applied**, **1 reported not applied**, and **0 unresolved source/data
questions**.
