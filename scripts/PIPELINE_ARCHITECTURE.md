# PharmaGuide Pipeline Architecture

> Last verified: 2026-07-16
> Export schema: 2.0.0 | Core columns: 110 | Pipeline manifest: 3.4.0

## 1. System boundary

PharmaGuide converts raw NIH DSLD product labels into a gated, offline-first
catalog and a separate interaction database used by the Flutter app.

```text
DSLD brand folders
  → Clean
  → Enrich
  → pre-score contract + coverage gates
  → v4 Stage-3 scored artifacts
  → candidate Build (no rescoring)
  → candidate gates
  → atomic Snapshot promotion
  → images + interaction DB + release gates
  → Supabase + Flutter bundle
```

There is one supported operator chain:

```text
batch_run_all_datasets.sh
  ├─ run_pipeline.py per brand
  ├─ rebuild_dashboard_snapshot.sh
  └─ release_full.sh
```

Lower-level Python scripts are implementation/debugging boundaries, not an
alternative release process.

## 2. Authority map

| Concern | Single authority |
|---|---|
| Raw row role and score eligibility | Cleaner (`enhanced_normalizer.py`) |
| Stage output ownership | `stage_manifest.py` |
| Canonical enriched ingredient contract | `scoring_input_contract.py` |
| Supplement taxonomy | `supplement_taxonomy.py` |
| V4 module dispatch | `scoring_v4/router.py` |
| Safety identity normalization | `identity/safety.py` |
| V4 safety verdict policy | `scoring_v4/gate_safety.py` |
| Production score | `score_supplements_v4.py` + `scoring_v4/` |
| Complete scored artifact | `scoring_v4/scored_artifact.py` |
| Stage-3 batch I/O | `score_products_v4.py` |
| Export schema/quarantine | `build_final_db.py` |
| Snapshot promotion | `rebuild_dashboard_snapshot.sh` + `promote_release_artifacts.py` |
| Release sequencing | `release_full.sh` |
| Source-of-truth rules | `contracts/source_of_truth_matrix.json` |

No later stage should rediscover an upstream decision from product-name text.
It may validate, explain, or fail the contract; it must not create a competing
classifier.

## 3. Compute stages

### 3.1 Clean

Authority:

- `clean_dsld_data.py`
- `enhanced_normalizer.py`
- `config/cleaning_config.json`

Responsibilities:

- normalize raw DSLD shapes and text
- preserve printed ingredient identity
- bind nutrients by canonical identity
- classify source section and row role
- emit score eligibility, exclusion reason, dose class, and raw taxonomy
- scope allergen negation and positive evidence by clause
- write cleaned product JSON and ownership manifest

The cleaner does not assign the final product score or verdict.

### 3.2 Enrich

Authority:

- `enrich_supplements_v3.py` (version 3.1.0)
- deterministic reference matchers in `scripts/data/` and helper modules
- `config/enrichment_config.json`

Responsibilities:

- canonical ingredient/form identity
- branded-token metadata without replacing the printed name
- product taxonomy and category features
- safety matches with US applicability and regional advisories
- RDA/AI/UL exposure by group and reference profile
- evidence, certification, manufacturer, allergen, delivery, synergy, and blend
  structures
- shared scorer inputs and match ledgers
- write enriched JSON and ownership manifest

Matching is exact/canonical/bounded-alias and deterministic. Dormant fuzzy
identity fallback is not part of the production contract.

### 3.3 Pre-score gates

`run_pipeline.py` loads the enriched batch once and runs:

1. stage-manifest ownership/checksum validation in strict mode
2. `enrichment_contract_validator.py`
3. `coverage_gate.py`

`batch_run_all_datasets.sh` always invokes the runner with
`--strict-release-gates`; required gates cannot be skipped or reduced to
warn-only in that mode.

### 3.4 V4 Stage-3 score

Authority:

- `score_products_v4.py`
- `scoring_v4/scored_artifact.py`
- `score_supplements_v4.py` (engine 4.1.0)
- `scoring_v4/`
- `scoring_v4/config/quality_score.json`

`build_scored_artifact()` is the single production seam. It runs the v4 scorer
once, consumes shared coverage/strict diagnostics, applies verdict and safety
precedence, and emits the complete score/status/pillar/provenance contract.
The CLI owns only input validation, atomic batch writes, failure reporting,
and the stage manifest. Failed or partial batches cannot produce a promotable
manifest.

### 3.5 Final build

Authority:

- `build_final_db.py`

Final build pairs enriched rows with v4-native Stage-3 artifacts. It never
invokes a scorer. It validates the six-pillar contract, coverage bounds,
status/verdict consistency, hard-block suppression, and export schema before
producing:

- `quality_score_v4_100`
- `quality_score_status`
- `quality_pillars_v4`
- `/100` compatibility mirrors
- v4 safety, confidence, module, and provenance data

Ranking/dedup use only v4-scored products. Deprecated `/80` export columns are
absent.

## 4. Stage ownership and stale-output containment

Each stage directory contains product JSON plus `.stage_manifest.json`.

The manifest records:

- schema and stage name
- completion state
- current run ID
- exact owned filenames
- SHA-256 for every owned file

Before a new Enrich or Score run, prior materialized outputs are moved into a
timestamped quarantine. In strict mode, missing, corrupt, incomplete, wrong-
stage, checksum-mismatched, missing, or unowned files stop consumption.

Control files beginning with `.` are never product payloads. Audits must select
products through `stage_manifest.py`, not a blind `*.json` directory scan.

## 5. Batch orchestration

`batch_run_all_datasets.sh` discovers eligible child directories under the
dataset root and runs them sequentially in filesystem lexical order. It skips
infrastructure/hidden directories and invokes:

```text
run_pipeline.py
  --raw-dir <brand>
  --output-prefix scripts/products/output_<brand>
  --stages <requested>
  --strict-release-gates
```

Every brand is attempted. Success/failure is recorded in a timestamped summary.
If any brand fails, snapshot and release are skipped and the batch exits
non-zero.

Targeted runs default to pipeline-only. Full-corpus runs continue to Snapshot
and Release unless explicitly stopped.

## 6. Snapshot architecture

`rebuild_dashboard_snapshot.sh` is the only normal catalog build/promotion
path.

### 6.1 Source gates

Before assembly it runs:

- source-of-truth matrix
- cleaner/IQD row contract
- enrichment/IQD contract
- clinical drift contract
- active identity integrity
- RDA/UL emitted-reference stamp parity

### 6.2 Candidate build

It discovers current enriched/scored brand directories and builds into
same-filesystem sibling candidates:

- `scripts/.final_db_output.candidate.<pid>`
- `scripts/.dist.candidate.<pid>`

`build_final_db.py` creates the internal candidate. Then
`release_catalog_artifact.py` becomes the single owner of the distributable
candidate, while preserving valid static assets from the previous `dist/`.

### 6.3 Candidate gates and promotion

Both candidates are stamped and checked for export contract and freshness.
Only after all gates pass does `promote_release_artifacts.py` atomically replace
both live directories. If either replacement fails, rollback preserves the
last good pair. Shell cleanup removes abandoned candidates.

Live `dist/` is never populated before candidate gates pass.

## 7. Release architecture

`release_full.sh` is auto-smart and fail-fast. It does include the snapshot
rebuild, but only when freshness/parity checks require it.

1. Run source matrix and active identity gates.
2. If product/build inputs are newer than the catalog, invoke
   `rebuild_dashboard_snapshot.sh`.
3. If `final_db_output/` and `dist/` disagree, invoke the same safe snapshot
   path again rather than copying an unvalidated artifact.
4. Refresh product images when catalog/image evidence is stale.
5. Mirror image-mutated catalog/manifest back to `final_db_output/`.
6. Rebuild the interaction DB when its rule inputs changed.
7. Run cleaner, enrichment, clinical, interaction, freshness, manifest, export,
   RDA/UL Flutter parity, and scoring snapshot gates.
8. Sync Supabase unless skipped/dry-run.
9. Import and verify the Flutter bundle unless skipped.
10. Prune local `.previous` backups.
11. Commit the Flutter bundle locally, then perform aligned recoverable storage
    cleanup; push remains manual.

If a preceding snapshot just produced a fresh matched pair, release steps 2–3
auto-skip. This is why running snapshot and then release is not a duplicate
catalog build.

## 8. Release artifacts

Canonical live catalog artifacts:

```text
scripts/final_db_output/
scripts/dist/
  pharmaguide_core.db
  export_manifest.json
  export_audit_report.json
  detail_index.json
  detail_blobs/
  product_images/
  interaction_db.sqlite
  interaction_db_manifest.json
```

The Flutter app bundles the catalog and interaction database under its
`assets/db/` directory and reads the SQLite catalog locally first. Supabase is
the remote distribution/hydration path, not the phone's only source of data.

## 9. Failure semantics

| Failure | Result |
|---|---|
| Brand Clean/Enrich/Score/gate fails | Other brands may finish; no snapshot/release; batch exits non-zero |
| Snapshot source/candidate gate fails | No live promotion; last good snapshot remains |
| Snapshot fails inside the batch | Release is skipped; current batch script reports pipeline success and exits zero—operator must treat the printed snapshot failure as unresolved |
| Release gate fails before Supabase | No Supabase or Flutter publication from later steps |
| Flutter parity/import fails | Release exits non-zero; no successful completion claim |
| Storage cleanup fails | Warning only; cleanup is recoverable and does not invalidate already-gated artifacts |

The snapshot-exit behavior above is current executable behavior, not the
preferred long-term contract. Do not infer publication success from a brand
pipeline summary alone.

## 10. Verification ownership

Tests always run through `scripts/test.sh`:

- `fast`: normal development loop
- `release`: release gates and heavier contract checks
- `full`: complete suite, parallelized
- `slow`: heavy integration subset

Artifact audits operate on a fresh candidate/live build and include:

- `audit_contract_sync.py`
- `audit_raw_to_final.py`
- `audit_inactive_safety.py`
- `audit_source_of_truth_contract.py`
- `db_integrity_sanity_check.py`
- `coverage_gate.py`

Generated reports and archived planning documents are evidence/history, not
runtime specifications.
