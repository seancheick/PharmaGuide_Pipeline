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
| Of those, **applied** | **10** | 9 source corrections + 201420, closed structurally |
| Of those, **reported but not applied** | **0** | — |
| Products explicitly withheld | 3 | 231334, 231335, 263865 |
| Products intentional non-scoreable | 3 | 12300, 254396, 254413 |
| Products confirmed correct | 6 items / 2 products | 75291, 246430, plus the folate rows of 228823 / 243799 / 243812 / 243815 |
| **Distinct products carrying any receipt** | **18** | — |

**`201420` is applied, but deliberately not as a row rewrite.** Its declared-total row is
named `Folic Acid` and is byte-identical to its own child row, so the per-row correction
mechanism cannot scope a rename to the total without renaming the child too. The source
conclusion was instead implemented structurally in the single folate dose-safety contract
(`scoring_v4/dose_safety.py::is_folate_parent_total_duplicate_flag`), which now identifies
the declared total from structure — the row anchored to a Daily Value, else the
declared-total (DFE) basis — rather than from a parent-name vocabulary that cannot contain
`Folic Acid`. **Zero data rows were modified.** Full evidence:
`FOLATE_201420_CLOSURE_20260920.md`.

## Basis 3 — measured on the frozen corpus

Two replays cover the phase. The source-correction A/B is the accepted record for the
nine rewrites; the closure A/B is this phase's last item (`201420`), whose fix is
structural and therefore cannot appear in a row-correction replay.

**Source-correction A/B** (base `c9e9d6ba`):

| Measurement | Value |
|---|---:|
| Row-level records compared / changed | 15,414 / **9** |
| Scored records compared | 15,412 |
| Score changes | **0** |
| Conclusion changes | **9** |
| Quarantine exits / new entries | **8** / **0** |
| Safety changes | **2** (243808, 246430) |
| Changes outside the intended family | **0** |

**Closure A/B** (base `5fb0d0f1`, `FOLATE_201420_*`):

| Measurement | Value |
|---|---:|
| Row-level (cleaner) records compared / crashes / **representation changes** | 15,414 / 0 / **0** |
| Scored records compared / crashes | 15,412 / 0 |
| Changed ids | **`201420`** only |
| Score changes | **1** (201420, 66.3 → 68.1) |
| Conclusion changes | **1** (201420) |
| Quarantine exits / new entries | **0** / **0** |
| Safety changes | **1** (201420's folate flag re-classified; verdict unchanged) |
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
receipt**, **10 applied**, **0 reported not applied**, and **0 unresolved source/data
questions**.

The ledger itself carries both a `count_items` block (this canonical basis) and a
`count_rows_including_section_verdicts` block. They differ by exactly the three
section-level verdicts (`vitamin_e_note`, the vitamin-A form verdict, the folate
structural verdict), never by a product's state; the canonical basis excludes them
because each is a finding *about* rows counted elsewhere.
