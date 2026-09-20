# Phase-3 source resolution (2026-09-20)

Closes the last data/source questions left open by the Phase-3 engineering closure, so the
pharmacist receives only clinical/policy decisions.

## Read this first

| File | What it is |
|---|---|
| `SOURCE_RESOLUTION_RECEIPTS_20260920.json` | The authoritative per-product receipts: frozen vs live vs printed for every flagged row, with the correction, the confidence and the final state. |
| `SOURCE_RECONCILIATION_20260920.md` | The reconciliation table — every item previously tagged `needs_info` / `source` / `stale` / `corrupt` / `unknown` / `incomplete` / `label` / `upstream` / `correction` / `form`, and its final data disposition. |
| `PHARMACIST_PACKET_PHASE3_FINAL_20260920.md` | **The packet to send.** Three policy decisions plus release signature, no source research. Supersedes the source-resolution draft. |
| `PHARMACIST_PACKET_PHASE3_SOURCE_RESOLVED_20260920.md` | The source-resolution draft packet, retained as history. Its §4 (provitamin-A UL) is no longer a pharmacist decision. |
| `LANE_PROOF_20260920.json` | `receipt -> correction layer -> cleaned lane row` for every product, produced by `../prove_source_corrections_20260920.py`. |
| `COUNT_BASIS_20260920.md` | **How this phase is counted.** Three published summaries used three different denominators; this fixes the definitions (receipt items / distinct products / measured replay) and the authoritative totals. |
| `count_reconciliation_20260920.py` | Derives every count from the receipts ledger and cross-checks the applied set against **both** frozen replays (the source-correction A/B and the `201420` closure A/B). `--check` asserts the published totals. Pinned by `scripts/tests/test_phase3_source_count_basis_20260920.py`. |
| `../FOLATE_201420_CLOSURE_20260920.md` | **The last Phase-3 engineering item, closed.** Root cause, the structural fix, before/after for the record, the test matrix, and the full-corpus blast radius. |
| `../FOLATE_201420_SCORED_REPLAY_5fb0d0f1_to_closure_20260920.json` | Scored A/B evidence for the closure: 15,412 records, exactly one changed id. |
| `../FOLATE_201420_ROWLEVEL_REPLAY_5fb0d0f1_to_closure_20260920.json` | Cleaner-side A/B evidence: 15,414 records, **0 representation changes**, input fingerprint verified. |

## Applied corrections (2026-09-20)

The receipts in this directory are no longer research only: the accepted
corrections are applied in the pipeline. See the `fix(data): materialize the
Phase-3 source-verified corrections` commit.

| Product(s) | Correction | Where it lives |
|---|---|---|
| 223563, 223572, 328644 | Vitamin A `mg RAE` -> `mcg RAE` | `scripts/data/curated_overrides/product_label_corrections.json` (RC-5) |
| 228823, 243799, 243808, 243812, 243815 | Vitamin A form -> printed `Natural Beta-Carotene` | RC-5 |
| 269360 | Serrapeptase `0 NP` -> printed `40,000 SPU` | RC-5 |
| 243808, 246430 | Declared DFE total not charged again for its own form breakdown; sibling rows of one printed form collapse instead of summing | `scripts/scoring_v4/dose_safety.py` folate parent-total contract |
| 201420 | **Closed without a row rewrite.** The declared-total row and its nested form row share the identical raw text `Folic Acid`, so the per-row mechanism cannot scope a rename to the total alone; the contract now identifies the declared total from structure (Daily-Value-anchored row, else the declared-total DFE basis). 0 data rows changed; folate charged once (1333 mcg DFE = 79.96 %UL), niacin exceedance and `CAUTION` verdict preserved. See `../FOLATE_201420_CLOSURE_20260920.md`. | `scripts/scoring_v4/dose_safety.py` folate parent-total contract |
| 231334, 231335, 263865 | **Deliberately withheld.** Printed denomination not separable at audit grade. | — |
| 254396, 254413 | `intentional_non_scoreable` (`professional_formulation_material`) | already produced by `assessment_readiness.evaluate_catalog_disposition` — no change needed |
| 12300 | Deterministically withheld (`no_score_eligible_active_rows`); the label discloses no component dose | already produced — no change needed |

## Supporting evidence (all machine-readable)

| Path | Contents |
|---|---|
| `live/*.json` | The raw live NIH DSLD v9 record for each id, exactly as retrieved. |
| `live_source_index_20260920.json` | Retrieval index: `src`, `entryDate`, `offMarket`, `productVersionCode`, serving sizes, net contents, PDF name, retrieval timestamp. |
| `labels/*.ocr.txt` | OCR text of the **archived DSLD label image** (the scan matching this product/version). |
| `dump_frozen_targets.py` | Read-only dumper of the exact frozen-corpus source rows, so every correction is keyed on real source text rather than a reconstruction from memory. |
| `labels/label_ocr_manifest_20260920.json` | Per-label provenance: source URL, PDF sha256, DPI, page count, OCR char count, OCR engine, retrieval timestamp. |
| `e2_label_receipts_20260920.json` | Machine-read printed quantity + unit-glyph measurement per E2 row. |
| `e2_sibling_crosscheck_20260920.json` | DSLD sibling-label `(field, quantity, unit)` frequency index per E2 product. |

Label PDFs themselves are **not** committed (multi-MB); the sha256 plus the source URL make
each reading reproducible from the URL.

## Reproducing

```bash
cd <repo> && source scripts/python_env.sh
A=scripts/audits/quarantine_triage_20260919

# 1. live DSLD + frozen/live row dump (writes live/ and live_source_index_20260920.json)
"$PG_PYTHON" $A/fetch_live_source_20260920.py --ids all --out $A/source_resolution_20260920/live

# 2. archived label images -> OCR text + provenance manifest
"$PG_PYTHON" $A/read_label_pdf_20260920.py --ids all

# 3. row-level Supplement Facts band OCR (unit glyphs); needs the label PDFs locally
"$PG_PYTHON" $A/label_row_ocr_20260920.py --pdf /path/to/231334.pdf --rows "Vitamin A,Vitamin E" --dpi 400

# 4. DSLD sibling-label cross-check (the decisive in-DSLD evidence)
"$PG_PYTHON" $A/compare_label_siblings_20260920.py

# 5. printed quantity + unit glyph receipts for the E2 set
"$PG_PYTHON" $A/build_e2_label_receipts_20260920.py --pdf-dir /path/to/label-pdfs
```

Requirements: `tesseract` (homebrew), PyMuPDF (`fitz`), Pillow, numpy — all present in the
project's pyenv. Tesseract is always fed images **on stdin**, because its file reader is
intermittently blocked for scratch paths on macOS.

## Evidence rules applied

1. A correction is authored only when the printed source establishes the value/unit —
   never from physiological plausibility.
2. Where the archived scan cannot be read to audit grade, the row gets an explicit
   `source_insufficient_keep_withheld`, not a TODO and not a guess.
3. The **most decisive** check is the DSLD sibling-label index: independent transcriptions
   of the same printed panel, with no OCR involved.
4. No pipeline file, product lane, or frozen corpus record was modified by this phase.
