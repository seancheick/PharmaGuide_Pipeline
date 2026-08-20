# On-Market Catalog Wave 1 Implementation Plan

> **For agentic workers:** REQUIRED: execute this plan through one owning implementation path. Do not run parallel edits across the pipeline and Flutter identity surfaces. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a verified 1,220-product on-market expansion wave, normalize brand display across the existing catalog and the new cohort, replace score-based UPC selection with bottle/version-aware resolution, and prove the expanded offline/online catalog on a dry build before publication.

**Architecture:** Preserve every DSLD label exactly as received. Apply brand display normalization only in the final catalog projection, keep full product details in Supabase blobs, and keep the offline database focused on identity, barcode resolution, the quick verdict, actionable warnings, search, and stack safety. UPC collisions remain identity questions: resolve by market state, version/date, formulation, package, and explicit label relationships; never resolve by product score.

**Tech Stack:** Python 3.13, SQLite/FTS5, existing DSLD API client and Clean → Enrich → Score pipeline, Supabase detail blobs, Flutter/Dart, Drift, Riverpod, and the existing release gates.

---

## Execution Status — 2026-08-19

- [x] Use the existing `scripts/dsld_api_sync.py sync-brand --status 1` operation. It remains the only download path and stages one JSON label per DSLD ID directly under `staging/brands/<folder>`.
- [x] Harden that operation with bounded retry, `Retry-After`, nonzero partial-failure exit, and `--resume`; no replacement ingestion system was created.
- [x] Stage all nine Wave 1 brands: **1,220 on-market labels**, with exact per-brand counts, unique IDs, filename/ID parity, and `offMarket=0` throughout.
- [x] Add one central brand registry while preserving every raw brand string.
- [x] Remove score-based shared-UPC selection. Retain all candidates and ask the user which bottle matches when identity is genuinely ambiguous.
- [x] Run clean-only mapping audits while remediating aliases. MegaFood finishes **278/278 clean**, with zero active gaps, zero inactive gaps, zero unresolved no-dose children, and zero products requiring review.
- [ ] User runs the single final Clean → Enrich → Score pipeline after this branch is integrated. Do not start that long run from this plan executor.
- [ ] After that run passes, assemble/measure the full offline/online candidate and proceed through the existing release gates.

Raw labels remain outside Git in `/Users/seancheick/Documents/DataSetDsld/staging/brands`. Git owns the downloader, identity registry, mappings, corrections, tests, and release contracts—not a duplicate copy of downloaded staging data.

---

## Decisions Locked for This Wave

- Wave 1 contains the eight mass-market brands plus **MegaFood**.
- Wave 1 is **on-market only**. Historical labels are a later, explicitly separate surface.
- The current 28-brand catalog and Wave 1 use one brand-identity contract. There will not be an old normalization regime and a new one.
- Raw `brandName`, raw product name, label ID, UPC, entry date, version code, label relationships, package data, and source payload are immutable.
- Consumer brand display is normalized centrally at export time. Scoring, certification matching, and manufacturer matching continue to receive the source identity unless a separately tested contract says otherwise.
- MegaFood is intentionally included despite its more complex whole-food/herbal label archetype. Its results are reported as a separate subgroup so it cannot hide mass-market regressions.
- The existing offline-core/online-detail architecture stays. This project refines and measures it; it does not create a second catalog system.
- `ingredient_fingerprint` stays in the offline core because Quick Check and stack safety consume it.
- Build-constant columns and duplicate blob structures are optimization candidates only after a usage/parity audit. Nothing is removed based on size estimates alone.
- Product scores never select a UPC winner. An unresolved collision produces a bottle-confirmation choice, not a guessed product.
- Missing-product submission continues through the existing DTC submission flow.

## Verified Wave 1 Scope

Observed from the DSLD `search-filter` endpoint with `status=1` on 2026-08-19:

| Query brand | Live labels | Known raw brand variants | Consumer family |
|---|---:|---|---|
| Centrum | 197 | `Centrum`, `Centrum Specialist`, `Pfizer Centrum ProNutrients`, whitespace/case variants | Centrum |
| Up & Up | 197 | `up&up` | up&up |
| Emergen-C | 134 | `Emergen-C` | Emergen-C |
| One A Day | 116 | `Bayer One A Day`, adult/kids/for-her/for-him variants | One A Day |
| Member's Mark | 102 | `Member's Mark` | Member's Mark |
| Airborne | 91 | base, Advanced, Original, Kids, Plus, Everyday variants | Airborne |
| Culturelle | 61 | base, Kids, Baby, Pro-Well, Digestive Health, whitespace variant | Culturelle |
| Kirkland Signature | 44 | `Kirkland Signature` | Kirkland Signature |
| MegaFood | 278 | `MegaFood`, `Women's Ensemble by MegaFood` | MegaFood |
| **Total** | **1,220** | | |

The live IDs generated during execution are authoritative. These counts are an audit expectation, not a reason to discard a newly added legitimate label or accept an unexplained disappearance.

## Current Baseline

- Current raw corpus: 14,194 labels; all observed as on-market.
- Current shipped core: 13,271 products after quarantine/release gates.
- Current SQLite size: approximately 50 MB installed and 6.4 MB gzip-compressed.
- Current indexed lookup latency on the development Mac: approximately 0.02–0.03 ms median for ID, UPC, and FTS queries.
- Wave 1 adds about 9.2% to the current shipped product count before quarantine.
- A linear 121,959-product extrapolation is not a release decision. The expanded candidate must be built and measured.

## Critical Existing Defect to Fix First

`scripts/build_final_db.py::dedup_by_upc` currently ranks active duplicates by score and deletes the lower-scoring label. Flutter `CoreDatabase.findByUpc` also uses safety/score ordering when more than one row shares a UPC.

Both behaviors confuse **identity** with **evaluation**. A different score may indicate a different formula or an unsafe historical record; neither tells us which bottle the user is holding. Wave 1 must not expand until this is replaced with version-aware resolution.

## File Map

### Pipeline repository

Created:

- `scripts/data/catalog_brand_registry.json` — reviewed query/display/family/line mappings and raw aliases.
- `scripts/brand_identity.py` — exact registry lookup and immutable source/display projection.
- `scripts/tests/test_brand_identity.py` — registry coverage, typo/case normalization, and no-fuzzy-match tests.
- `scripts/reports/catalog_expansion_wave_1/` — generated manifests and dry-build measurements; reports are not source-of-truth.

Modify:

- Keep the existing `scripts/dsld_api_sync.py sync-brand` operational path unchanged. It already supports `--status 0/1/2` and writes directly into the chosen `staging/brands/<brand>` folder.
- `scripts/build_final_db.py` — apply display-brand projection, retain source brand/version lineage, and replace destructive score-based UPC deduplication.
- `scripts/tests/test_dedup_by_upc.py` — remove score-winner expectations; retain only provably equivalent consolidation cases.
- `scripts/tests/test_build_final_db.py` — lock core/detail identity lineage and manifest counts.
- `scripts/tests/test_core_schema_drift.py` — update the schema contract only for fields proven necessary.
- `scripts/audit_raw_to_final.py` — trace raw brand/version/UPC through cleaned, enriched, scored, core, and detail outputs.
- `scripts/release_catalog_artifact.py` — reject unexplained identity loss or unresolved destructive deduplication.
- `scripts/sync_to_supabase.py` — publish the online candidate only after the same manifest passes release gates.

### Flutter repository

Create:

- `lib/features/scanner/product_version_picker_sheet.dart` — concise bottle-confirmation UI for genuinely ambiguous UPCs.
- `test/features/scanner/product_version_picker_sheet_test.dart` — clear/ambiguous/accessibility states.

Modify:

- `lib/data/database/core_database.dart` — return all valid UPC candidates and a typed unique/ambiguous resolution instead of selecting by score.
- `lib/app.dart` — handle UPC deep links with the same resolver as scanning.
- `lib/features/scanner/scanner_screen.dart` — navigate directly for a unique identity; show the bottle chooser for ambiguity; keep the existing missing-product submission path for zero matches.
- `test/data/database/find_by_upc_safety_tiebreak_test.dart` — replace score/safety tie-break tests with identity-resolution tests.
- `test/data/database/database_performance_test.dart` — prove candidate lookup still uses the normalized UPC index.
- `test/features/scanner/scanner_screen_test.dart` — unique, ambiguous, and not-found routes.
- `lib/data/database/tables/products_core_table.dart` — document any new pipeline-only identity columns; avoid Drift regeneration if the app reads them through a typed projection/raw query.

## Task 0: Reconcile the Independent CoQ10 Evidence Commit

This is a separate evidence correction, not part of catalog identity. Keep it isolated so Wave 1 cannot accidentally carry a score change.

- [ ] Inspect commit `8bf71302` on `evidence/coq10-ubiquinol-source`.
- [ ] Confirm it adds PMID `32188111` only to plain `coq10::ubiquinol`, records the reconciliation-ledger change, and does not attach it to `ubiquinol crystal-free`.
- [ ] Confirm the DOI is `10.3390/nu12030784`.
- [ ] Confirm the study supports parity with crystal-dispersed ubiquinone and does not claim a statistically significant ubiquinol premium.
- [ ] Run the focused IQM evidence audit and live PMID verification.
- [ ] Cherry-pick only that commit onto `main` if the diff and gates match this contract.
- [ ] Keep this commit separate from all Wave 1 commits.

Expected result: one verified source is added, no form score changes, and the remaining-form backlog decreases by one.

## Task 1: Confirm the Existing Brand-Staging Operation

**Files:** existing `scripts/dsld_api_sync.py`; generated report under `scripts/reports/catalog_expansion_wave_1/`.

- [x] Confirm `sync-brand` accepts `--status 0/1/2`, defaults to `1`, and writes flat raw labels to the selected staging folder.
- [x] Confirm this wave will use `--status 1` and preserve the full API label unchanged.
- [ ] Download each reviewed brand once through `sync-brand`; do not introduce a second bulk downloader.
- [ ] After download, derive the identity/hash manifest from the staged raw files so no label is fetched twice.
- [ ] Reconcile counts, raw brand variants, duplicate IDs, malformed UPCs, and source identity from that derived manifest.

## Task 2: Add One Brand-Identity Contract for Existing + New Catalog

**Files:** `scripts/data/catalog_brand_registry.json`, `scripts/brand_identity.py`, `scripts/tests/test_brand_identity.py`, `scripts/build_final_db.py`.

- [ ] Inventory distinct raw brand strings from the current 14,194 raw labels and Wave 1 manifest.
- [ ] Include the known current typo `Garden of Life Dr. Fomulated` and all case/whitespace duplicates in the review queue.
- [ ] Write failing tests for exact alias mapping, canonical display, family, product line, and unknown-brand pass-through.
- [ ] Implement exact normalized-key matching only. No substring or fuzzy brand matching.
- [ ] Preserve raw `brandName` in raw/clean/enriched artifacts.
- [ ] Apply canonical `brand_name` only while building the consumer catalog.
- [ ] Carry `brand_name_raw` and label-version lineage in the core/detail identity contract so audits and UPC resolution never lose the submitted identity.
- [ ] Keep scoring, manufacturer trust, and certification matching on their existing source identity paths; compare score outputs before/after and require zero score drift from display normalization.
- [ ] Build FTS from canonical brand plus source alias so users can search either `Bayer One A Day` or `One A Day`.
- [ ] Require 100% registry coverage for the existing targeted brands and Wave 1; unknown future brands pass through visibly and enter a report rather than disappearing.
- [ ] Run `scripts/test.sh fast scripts/tests/test_brand_identity.py scripts/tests/test_build_final_db.py scripts/tests/test_core_schema_drift.py`.

Commit: `feat(identity): centralize catalog brand display`

## Task 3: Replace Score-Based UPC Deduplication

**Files:** `scripts/upc_version_resolver.py`, `scripts/build_final_db.py`, `scripts/tests/test_upc_version_resolver.py`, `scripts/tests/test_dedup_by_upc.py`.

- [ ] Write failing tests proving score cannot select a UPC winner.
- [ ] Write cases for:
  - same UPC + explicit `Image difference, same product` relationship + identical formula/package → one canonical identity with retained aliases;
  - same UPC + later `entryDate` + identical formula/package → current canonical label;
  - same UPC + different ingredient/formula fingerprint → ambiguous, retain both;
  - same UPC + different net contents/package → ambiguous unless the scanned packaging distinguishes it;
  - active versus off-market → active candidate for the on-market catalog, historical record retained online;
  - missing or `Not Present` version code → do not pretend version ordering is known;
  - blocked and scored rows with different formulas → ambiguous, never choose either by severity or score.
- [ ] Define formula fingerprint from label identity fields and the ordered label ledger—not the numeric product score.
- [ ] Stop deleting ambiguous UPC rows and their detail blobs.
- [ ] Emit a compact UPC-resolution map containing canonical IDs, aliases, and ambiguity reason codes.
- [ ] Add a release gate: no UPC group may be destructively collapsed because of score, grade, verdict, or quality status.
- [ ] Run `scripts/test.sh fast scripts/tests/test_upc_version_resolver.py scripts/tests/test_dedup_by_upc.py scripts/tests/test_build_final_db.py`.

Commit: `fix(identity): resolve UPCs by bottle version`

## Task 4: Make Flutter Handle Unique and Ambiguous UPCs Honestly

**Files:** `lib/data/database/core_database.dart`, `lib/app.dart`, `lib/features/scanner/scanner_screen.dart`, `lib/features/scanner/product_version_picker_sheet.dart`, related tests.

- [ ] Write failing database tests showing `findByUpc` cannot return a highest-score or most-severe winner for an ambiguous formula group.
- [ ] Add a typed result with three states: `notFound`, `unique(product)`, `ambiguous(candidates)`.
- [ ] Keep UPC normalization and the expression index unchanged.
- [ ] Return only the compact fields needed for confirmation: image, canonical brand, product name, package/form, version/date when meaningful, and DSLD ID internally.
- [ ] Show the confirmation sheet only when identity remains genuinely ambiguous.
- [ ] Use consumer copy such as “Which bottle matches yours?”; do not expose catalog/debug terminology.
- [ ] Never use the score as a visual discriminator in the chooser.
- [ ] Route the selected identity to the existing product-detail screen.
- [ ] Preserve the existing DTC submission sheet for zero matches.
- [ ] Apply the same behavior to scan, manual barcode entry, and UPC deep links.
- [ ] Run focused Flutter database/scanner tests, `flutter analyze lib/`, then `make check` before integration.

Commit: `fix(scan): confirm ambiguous product versions`

## Task 5: Download Wave 1 Raw Labels Once Through `sync-brand` — Complete

**Destination folders:**

- `Centrum`
- `Up_and_Up`
- `Emergen_C`
- `One_A_Day`
- `Members_Mark`
- `Airborne`
- `Culturelle`
- `Kirkland_Signature`
- `MegaFood`

- [x] Run the existing command once per brand with `--status 1 --output-dir <staging/brands/folder>`.
- [x] Preserve the full normalized API label in the existing staging layout.
- [x] Derive source identity directly from the completed staging folders; do not maintain a second downloaded-label manifest as source-of-truth.
- [x] Verify file count per brand against the expected live count.
- [x] Verify every filename matches its DSLD ID and `offMarket=0`.
- [x] Verify there are no duplicate IDs in any Wave 1 folder.
- [x] Verify raw brand variants still match DSLD; do not rewrite them in staging.
- [x] Run clean-only identity audits before the final pipeline.

No raw-label commit: staging data stays in the existing external staging tree.

## Task 6: Run the Final Wave 1 Pipeline — User-Owned Final Run

During mapping, use clean-only targeted audits. Do not run Enrich/Score repeatedly. After this branch is integrated, the user runs the existing final pipeline once across the complete staged corpus.

```bash
bash batch_run_all_datasets.sh \
  --targets Centrum,Up_and_Up,Emergen_C,One_A_Day,Members_Mark,Airborne,Culturelle,Kirkland_Signature,MegaFood \
  --stages clean,enrich,score \
  --pipeline-only
```

- [x] Confirm all nine brand folders pass the clean identity audit with no true mapping gaps.
- [ ] Confirm all nine brand folders pass Enrich and Score in the user's final run.
- [ ] Produce separate audit slices for the 942 mass-market labels and 278 MegaFood labels.
- [ ] Review quarantine reasons, unmapped identities, label-ledger repairs, blend hierarchy, nutrition rows, form ratings, dose bands, warning counts, and certification claims.
- [ ] Compare existing-product scores before/after identity changes; brand normalization alone must produce zero scoring drift.
- [ ] Sample at least five products per brand and all high-severity/blocked products.
- [ ] Stop if a new archetype causes silent ingredient loss, duplicate display rows, or generic warnings.

## Task 7: Assemble and Measure the Full Candidate

The candidate includes the existing 28 brands plus all nine Wave 1 folders. Rebuild locally without publishing.

- [ ] Build the dashboard/catalog snapshot from all current successful outputs.
- [ ] Record raw and compressed core DB size, per-table/index size, row count, detail-blob count/bytes, share-index shard bytes, and image bytes.
- [ ] Measure ID, UPC, FTS, category, and alternatives queries using median, p95, and max latency.
- [ ] Measure a physical-device cold launch, first scan, repeat scan, offline product opening, and online detail hydration.
- [ ] Measure the actual archive/TestFlight contribution instead of using SQLite linear extrapolation.
- [ ] Verify the offline quick verdict remains complete when detail blobs are unavailable.
- [ ] Verify online detail loads from the matching catalog version and hash.
- [ ] Store the measurement report under `scripts/reports/catalog_expansion_wave_1/`.

### Optimization decision after measurement

- [ ] Audit all eight build-constant columns against Flutter and release consumers.
- [ ] Move only proven constants into `export_manifest`/metadata, with a backward-compatible migration.
- [ ] Audit duplicate ingredient and `rda_ul_data` blob representations by JSON path and consumer.
- [ ] Remove duplication only when parity tests prove no UI, scoring, safety, evidence, or debugging capability is lost.
- [ ] Rebuild and report measured bytes saved. Do not claim projected savings as achieved savings.

Commit, if justified: `perf(catalog): slim verified duplicate metadata`

## Task 8: Release Gates and Canary Publication

- [ ] Run `scripts/test.sh release` once after all Wave 1 code/data review is complete.
- [ ] Run the source-of-truth, IQM evidence, active identity, RDA/UL conversion, snapshot, and export gates.
- [ ] Confirm the catalog product count equals previous shipped products plus accepted Wave 1 rows minus documented quarantine—not silent UPC deletion.
- [ ] Confirm detail-index/blob parity and version hashes.
- [ ] Run `make check` and `make verify-bundle` in Flutter.
- [ ] Publish the candidate only through the existing catalog-release path.
- [ ] TestFlight canaries:
  - one simple multivitamin from each mass-market family;
  - one Culturelle probiotic;
  - one MegaFood multivitamin with food-cultured forms;
  - one MegaFood botanical/blend product;
  - one shared-UPC unique case;
  - one intentionally ambiguous UPC case;
  - offline quick verdict;
  - online complete label/evidence hydration;
  - missing UPC → existing DTC submission.
- [ ] Monitor Sentry for the new release and keep hash/decode/server failures reportable while expected offline detail unavailability stays quiet.

Commit: `release(catalog): publish on-market Wave 1`

## Task 9: Expansion After Wave 1

Only begin after Wave 1 metrics and TestFlight canaries are accepted.

1. Rank the next on-market brands by scan probability, DSLD live-maintenance ratio, label archetype value, and mapping readiness.
2. Use the same registry, identity manifest, version resolver, dry-build metrics, and release gates.
3. Expand the Supabase/website catalog beyond the bundled seed without claiming historical labels are current products.
4. Add historical products as an explicit on-demand state after the current on-market catalog is strong.
5. Continue the existing reviewed DTC submission workflow for missing products.

## Stop Conditions

Do not publish if any of the following occurs:

- an on-market API count changes without an explained manifest diff;
- raw source identity is rewritten or lost;
- a UPC winner is selected using score, grade, verdict, or warning severity;
- an ambiguous formulation is silently collapsed;
- brand display normalization changes scoring, certification, or manufacturer-trust results;
- MegaFood or another complex label archetype drops label rows or flattens blend children;
- offline quick verdicts require a detail-blob network request;
- detail blobs do not match the bundled catalog version/hash;
- release gates, Flutter checks, or physical-device canaries fail.

## Definition of Done

- Wave 1 contains all reviewed on-market IDs for the nine brands, currently expected to total 1,220 before quarantine.
- Existing and new brands render through one reviewed display identity while raw source brands remain recoverable.
- No identity path chooses a product because it scores higher or looks more severe.
- Unique UPC scans open immediately; genuine ambiguity asks the user which bottle matches.
- The pipeline, core DB, online blobs, Flutter app, and website resolve the same product/version identity.
- The offline experience provides a fast quality verdict and actionable warnings without network access.
- The online experience provides the complete label, evidence, citations, images, and detailed scoring.
- Actual size, speed, cache, and TestFlight measurements are recorded and accepted.
- The full release suite passes and the catalog is published through the existing gated release path.
