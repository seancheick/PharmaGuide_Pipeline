# Phase-3 source reconciliation — every tagged item, final data disposition

Generated 2026-09-20. Companion to `SOURCE_RESOLUTION_RECEIPTS_20260920.json`
(per-product evidence) and `labels/label_ocr_manifest_20260920.json` (label-image
provenance: source URL, PDF sha256, DPI, OCR char count).

Column meanings:

* **Frozen source** — what the PharmaGuide ingest record holds today.
* **Live DSLD** — `GET https://api.ods.od.nih.gov/dsld/v9/label/{id}`, 2026-09-20.
* **Printed/manufacturer label** — the archived DSLD label image (the scan that
  matches this product/version), or the manufacturer panel where the scan is not
  readable. `—` means the archived scan for that record does not contain the row
  legibly; no glyph read is claimed in that case.
* **Still needs pharmacist?** — a *source* question, not a policy question.

## Table

| DSLD ID | Issue | Frozen source | Live DSLD | Printed/manufacturer label | Final data disposition | Still needs pharmacist? |
|---|---|---|---|---|---|---|
| 328644 | E2 vitamin-A unit | Vit A `1300 mg RAE` (100 %DV) | identical (`unchanged_since_snapshot`) | scan row unreadable; **both sibling versions of the same panel read `1300 mcg RAE`** | `source_verified_correction` — mg RAE → mcg RAE | No |
| 223563 | E2 vitamin-A unit | Vit A `900 mg RAE` (60 %DV) | identical | quantity `900`, 3-glyph mcg-class unit box, row %DV 60 % | `source_verified_correction` — mg RAE → mcg RAE | No |
| 223572 | E2 vitamin-A unit | Vit A `900 mg RAE` (60 %DV) | identical | same panel as 223563 | `source_verified_correction` — mg RAE → mcg RAE | No |
| 223563 / 223572 | E2 vitamin-D3 row | `100 mg` / `50 mg` | identical | row not resolvable at audit grade in the archived scan | no correction authored; row keeps its conservative handling | No — value flagged as unresolvable, not as a question |
| 231334 | E2 vitamin-A unit | `6000 mcg DFE` (667 %DV) | identical | scan reads `6,000 <3-glyph mcg-class> DFE … 667 %` | `source_insufficient_keep_withheld` — record reproduces the printed panel; denomination glyph not separable to audit grade; no UL claim depends on it | No |
| 231335 | E2 vitamin-A unit | `6000 mcg DFE` (667 %DV) | identical | identical panel to 231334 | `source_insufficient_keep_withheld` | No |
| 263865 | E2 vitamin-A unit | `6000 mcg DFE` (667 %DV) | identical | same panel design | `source_insufficient_keep_withheld` | No |
| 231334 / 231335 / 263865 | E2 vitamin-E row | `134 mcg` / `134 mcg` / `134 mg` (893 %DV) | identical | scan prints a 3-glyph `mcg`-class box; the 893 %DV and the pre-2016 siblings (`200 IU` = 134 mg) establish a milligram quantity | `source_record_correct_no_change` — records reproduce the label; 263865 already holds mg; no plausibility rewrite | No |
| 12300 | needs_info | `Proprietary Blend 860 mg`, zero component doses | identical | scan shows the blend line only, no component doses | `intentional_non_scoreable` (was already ledgered; re-verified on the label) | No |
| 254396 | needs_info | `Vitamin B12` 0 NP, serving `1 Not Present` | identical | bulk powder tub, **no Supplement Facts panel**, professionals-only statement | `intentional_non_scoreable` | No |
| 254413 | needs_info | `Vitamin B12` 0 NP, serving `1 Not Present` | identical | bulk powder tub, no panel | `intentional_non_scoreable` | No |
| 75291 | needs_info (ratified) | Total Omega-3 300 mg parent, DHA/EPA as forms | identical | scan row `Total Omega-3 Fatty Acids (including EPA/DHA) 300 mg` | `source_record_correct_no_change` — ratification re-verified on its own record and own label | No |
| 228823, 243799, 243808, 243812, 243815 | Vitamin-A form/completeness gap | Vit A row with **no form** → `unknown_vitamin_form`, `unresolved_form`, one incomplete source row, product gated | identical (no form upstream either) | label's OTHER INGREDIENTS vitamin/mineral blend names **`Natural beta-Carotene`** as the vitamin A source; row %DV 334 %/380 % resolves on the ~900 mcg RAE basis | `source_verified_correction` — record the form as natural beta-carotene (provitamin A) with the label citation; never default to retinol | No for the data question; the **UL/applicability policy** for provitamin A goes in the pharmacist packet |
| 228823, 243799, 243812, 243815 | Bulk 1340 folate | Folate parent + folic-acid child, values paired by serving basis | identical | two printed columns (`360 g in Water` / `360 g in 2% Milk`): `667 mcg DFE (400 mcg Folic Acid)` ‖ `725 mcg DFE (435 mcg Folic Acid)` | `source_record_correct_no_change` — representation already pairs by basis | No |
| 243808 | Bulk 1340 folate (duplication) | Folate `[(725),(667)]` **plus two separate sibling child rows** `Folic Acid 435` and `Folic Acid 400` | identical | two printed columns, one folic-acid child each | `source_verified_correction` — collapse the two sibling child rows into one form row carrying both basis values (435 milk / 400 water); **14 sibling label records of the same panel already represent it that way** | No |
| 201420 | folate residual (name) | declared-total row **named `Folic Acid`** 1333 mcg DFE + nested `Folic Acid` 800 mcg | identical | scan not legible for this row | `source_verified_correction` — rename the declared-total row to `Folate`, keep 800 mcg as its nested breakdown (**sibling 201405 of the same panel transcribes it exactly so**) | No |
| 246430 | folate residual (subset) | `Folate 1667 mcg DFE` + nested `Folic Acid 400 mcg` | identical | scan partial/unreadable | `source_record_correct_no_change` — 1667 = 1000 mcg L-5-MTHF + 400×1.7 (680) DFE, so the child is inside the parent total; siblings appear both with and without the child | No |
| 269360 | Serrapeptase quarantine | `Serrapeptase Enzyme` **0 NP** (form Serratia sp.) | identical | **archived scan reads `Serrapeptase Enzyme 40,000 SPU**` with the label's own footnote `**SPU - serratiopeptidase activity units`**; manufacturer panel states the same | `source_verified_correction` — record the declared 40,000 SPU activity from the panel (the DSLD record already carries the SPU footnote as a statement, and sibling label 25222 is transcribed with `40000 Unit(s)`) | No |
| EDTA ×16 | Safety/representation | identity + evidence representation complete; products are standalone orally marketed EDTA | identical | manufacturer (BulkSupplements) label states oral daily directions (500 mg EDTA disodium / 500 mg calcium disodium EDTA) | `representation_correct_no_change` — calcium disodium and disodium must stay distinct identities | **Policy only** (hidden/BLOCKED vs scored) |
| GHOST-SUSPECT PMIDs ×2 | citation review | recorded in `scripts/data/backed_studies_ghost_review.json` with a written rationale per PMID | n/a | n/a (PubMed records) | closed by design — the reviewed ledger *is* the mechanism that permits them past the gate; `total_entries: 2` | No source question; covered by release sign-off |
| 49 suppressed depletion records | identity enforcement | suppressed (`needs_revision`/`rejected`) entries | n/a | n/a | **closed by design** — `scripts/api_audit/verify_medication_depletion_identifiers.py` documents that suppressed entries are *tracked but identity not enforced* because they cannot cause a live missed-warning; displayed entries are enforced | No |
| `omission_reason` enum debt | omega child rows reuse `duplicate_source_line` | n/a | n/a | n/a | accepted technical debt, explicitly out of Phase-3 scope | No |
| `V4_IQD_INGREDIENTS_FALLBACK` | static source-of-truth audit | resolved at the closure tip | n/a | n/a | **closed** — 0 static-audit findings at the closure tip | No |

## Counts

| Final data disposition | Rows |
|---|---:|
| `source_verified_correction` | **11** |
| `source_record_correct_no_change` | **9** |
| `source_insufficient_keep_withheld` | **3** |
| `intentional_non_scoreable` | **3** |
| **Source/data items remaining unresolved** | **0** |

## Non-source items that remain (and are *not* source questions)

1. **One reviewed dose-safety reconciliation change** (folate parent/child basis), owner: dose-safety/folate. Fully specified from source; fixtures `201420`, `243808`, `246430`, guard `228823`. This is an engine change, not a data question.
2. **EDTA ×16** — Safety policy disposition.
3. **Standardization-marker clinical policy** — the five-product rule (216948, 232718, 216776, 44423, 77254).
4. **Discrete-enzyme formulation policy** — neutral/unrated Formulation state after removal of unsupported multi-enzyme evidence transfer.
5. **Provitamin-A UL applicability** — whether a beta-carotene RAE amount is evaluated against the retinol upper limit.
6. **Licensed-pharmacist release sign-off.**
