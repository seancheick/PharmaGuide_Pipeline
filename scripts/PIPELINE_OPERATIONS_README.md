# PharmaGuide Pipeline Operations

> Canonical operator runbook | Last verified: 2026-07-15

## 1. Which command should I run?

| Intent | Command | What follows automatically |
|---|---|---|
| Reprocess and release the complete catalog | `bash batch_run_all_datasets.sh` | All brands Clean → Enrich → Score → Snapshot → Release |
| Reprocess every brand but stop before catalog build | `bash batch_run_all_datasets.sh --pipeline-only` | Pipeline only |
| Reprocess selected brands safely | `bash batch_run_all_datasets.sh --targets Brand_A,Brand_B --stages enrich,score` | Pipeline only by default |
| Reprocess selected brands and intentionally release the full catalog | Add `--release` to the targeted command | Target pipeline → Snapshot → Release |
| Rebuild the catalog from existing brand outputs | `bash scripts/rebuild_dashboard_snapshot.sh` | Candidate build/gates/promotion only |
| Finish/retry downstream release work | `bash scripts/release_full.sh` | Auto-detect snapshot need, images, interactions, gates, Supabase, Flutter |
| Collect weekly FDA/DEA regulatory signals | `bash scripts/run_fda_sync.sh` | Report only; exits 3 when clinical review is required |

`release_full.sh` does include `rebuild_dashboard_snapshot.sh`. It calls it only
when the current catalog is missing, stale, or inconsistent. When you already
ran a successful snapshot immediately before release, release sees matching
fresh artifacts and skips those catalog steps.

## 2. What plain `batch_run_all_datasets.sh` does

With no options:

```bash
bash batch_run_all_datasets.sh
```

the script performs this exact sequence.

### 2.1 Dataset discovery

- Root defaults to `$HOME/Documents/DataSetDsld/staging/brands`.
- Each eligible child directory is treated as one dataset/brand.
- Hidden/infrastructure directories are excluded.
- Brand directories run sequentially in filesystem lexical order.

### 2.2 Per-brand strict pipeline

For each brand, the batch wrapper invokes the equivalent of:

```text
run_pipeline.py
  --raw-dir <brand directory>
  --output-prefix scripts/products/output_<brand>
  --stages clean,enrich,score
  --strict-release-gates
```

That means:

1. Clean raw product files.
2. Quarantine stale Enrich outputs and enrich the current cleaned files.
3. Write/validate the Enrich stage ownership manifest.
4. Load the enriched batch once.
5. Run the enrichment contract validator.
6. Run the strict coverage gate.
7. Quarantine stale Score outputs and generate legacy score scaffolding.
8. Write the Score stage ownership manifest.

The batch attempts every discovered brand even if one fails. It records each
result in:

```text
scripts/products/reports/batch_run_summary_YYYYMMDD_HHMMSS.txt
```

### 2.3 Stop-on-partial-catalog rule

If any brand failed:

- snapshot is not started
- release is not started
- the batch exits non-zero

Fresh outputs from successful brands remain available for diagnosis, but a
partial catalog cannot move downstream.

### 2.4 Snapshot

If every brand passed, the batch invokes:

```bash
bash scripts/rebuild_dashboard_snapshot.sh
```

The snapshot script:

1. runs source-of-truth, row-contract, clinical, identity, RDA/UL, and scoring
   snapshot gates
2. discovers all current enriched/scored brand outputs
3. builds `final_db_output` and `dist` candidates
4. validates/stamps both candidates
5. checks export contract and freshness
6. atomically promotes both candidates together

No candidate touches the live snapshot before every required gate passes,
including the per-product scoring snapshot contract. If the snapshot fails,
the batch exits non-zero and full release is not started; the last good live
snapshot remains in place.

### 2.5 Full release

After a successful snapshot, the batch invokes:

```bash
bash scripts/release_full.sh
```

Because the snapshot is now fresh, release normally skips its own catalog
rebuild checks and continues with images, interaction DB, strict gates,
Supabase, and Flutter.

## 3. Targeted runs

Targeted work is intentionally non-publishing by default:

```bash
bash batch_run_all_datasets.sh \
  --targets CVS,Garden_of_life,Goli,Nutricost,Pure_Encapsulations,Ritual,Thorne \
  --stages enrich,score \
  --pipeline-only
```

For a targeted run:

- only matching brand directories are processed
- omitted stages are reused from their existing owned outputs
- strict pre-score gates still run
- snapshot and release do not start
- the rest of the catalog is not recalculated

`--pipeline-only` is explicit in the example but redundant with `--targets`;
targeted runs already default to pipeline-only unless `--release` is supplied.

When the target output has been reviewed and you intend to publish the whole
catalog, run the two downstream owners:

```bash
bash scripts/rebuild_dashboard_snapshot.sh
bash scripts/release_full.sh
```

The first command builds and promotes the catalog. The second auto-skips
duplicate catalog work and finishes release.

To authorize that automatically in one targeted batch invocation:

```bash
bash batch_run_all_datasets.sh \
  --targets Brand_A,Brand_B \
  --stages enrich,score \
  --release
```

Do not combine `--pipeline-only` and `--release`; the wrapper rejects that
conflict.

## 4. Stage selection

```bash
bash batch_run_all_datasets.sh --stages clean
bash batch_run_all_datasets.sh --stages enrich,score --pipeline-only
bash batch_run_all_datasets.sh --stages score --pipeline-only
```

Use a later-stage-only run only when its upstream owned output is current and
valid. Strict mode validates manifests and checksums rather than trusting every
JSON present in a directory.

Custom dataset root:

```bash
bash batch_run_all_datasets.sh \
  --root "$HOME/Documents/DataSetDsld/staging/brands" \
  --pipeline-only
```

## 5. Snapshot-only operation

Use snapshot-only when brand pipeline outputs are already current and you want
to rebuild the dashboard/catalog artifacts without publishing:

```bash
bash scripts/rebuild_dashboard_snapshot.sh
```

Expected result:

- both `scripts/final_db_output/` and `scripts/dist/` are current
- export manifests are stamped
- the previous live pair is replaced only after gates pass
- candidate directories are removed

Do not manually copy databases or detail blobs into `dist/`. The release
artifact builder owns the complete distributable shape.

## 6. Full release operation

Standard command:

```bash
bash scripts/release_full.sh
```

The eight auto-smart steps are:

1. refresh the catalog through the snapshot path if upstream/build inputs are
   newer
2. repair final/dist mismatch through the same snapshot path
3. extract/backfill product images when needed
4. rebuild/stage interaction DB when rule inputs changed
5. sync `dist/` to Supabase after all publication gates pass
6. atomically import and verify Flutter bundle
7. prune `.previous` Flutter DB backups
8. locally commit the Flutter bundle and perform aligned recoverable storage
   cleanup; push remains manual

Before Supabase, release runs the cleaner/enrichment/clinical/interaction/
freshness/export/RDA/scoring-snapshot contracts. A failure there stops cloud
and app publication.

Useful release options:

```bash
bash scripts/release_full.sh --skip-product-images
bash scripts/release_full.sh --skip-supabase
bash scripts/release_full.sh --supabase-dry-run
bash scripts/release_full.sh --skip-flutter
bash scripts/release_full.sh --flutter-repo "/path/to/PharmaGuide ai"
bash scripts/release_full.sh --force
```

`--force` overrides freshness decisions. It does not bypass gates.

## 7. Batch release options

Options passed from the batch wrapper to `release_full.sh` after a successful
snapshot:

- `--skip-product-images`
- `--skip-supabase`
- `--supabase-dry-run`
- `--skip-flutter`
- `--flutter-repo <path>`

Other batch controls:

- `--skip-release`: build/promote snapshot but do not run full release
- `--pipeline-only`: stop after requested compute stages
- `SKIP_SNAPSHOT=1`: legacy environment switch; skips snapshot and release
- `SKIP_RELEASE=1`: snapshot only

Prefer the explicit CLI flags for new operational instructions.

## 8. Failure and recovery

### A brand fails

1. Read the brand failure and the timestamped batch summary.
2. Fix the owning Clean/Enrich/Score/gate issue.
3. Rerun only the failed brand/stages with a targeted pipeline-only command.
4. Review the output.
5. Run snapshot and release when all intended brands are current.

### Stage-manifest failure

Do not delete the manifest to make the gate fall back. The manifest is proving
that files belong to the successful run. Rerun the owning stage so stale files
are quarantined and a new manifest is written.

### Snapshot gate fails

- Live `dist/` and `final_db_output/` remain the previous good pair.
- A full batch exits non-zero and does not start release.
- Read the first failing source/candidate gate.
- Fix upstream product data or the contract; do not copy candidate artifacts
  into place manually.
- Rerun the snapshot command.

### Release fails at scoring snapshot

This occurs before Supabase and Flutter publication.

1. Review every changed product's score, status, verdict, route, pillars, and
   clinical/safety reason.
2. Fix unintended changes at the owning layer.
3. Re-freeze only reviewed, intentional per-product deltas.
4. Rerun `release_full.sh`; completed/current earlier steps auto-skip.

### Supabase or Flutter step fails

Fix credentials/path/import/parity issue and rerun `release_full.sh`. Its
freshness/checksum checks reuse already-gated artifacts.

## 9. Tests and audits

Use only the supported test runner:

```bash
scripts/test.sh fast
scripts/test.sh fast -k folate
scripts/test.sh release
scripts/test.sh full
```

For a fresh artifact audit, first build through the snapshot owner. Then use
the pinned runtime:

```bash
source scripts/python_env.sh
"$PG_PYTHON" scripts/audit_contract_sync.py --help
"$PG_PYTHON" scripts/audit_raw_to_final.py --help
"$PG_PYTHON" scripts/db_integrity_sanity_check.py
```

Use each audit's current `--help` for required artifact paths. Do not paste
historical commands from archived handoffs into the release path.

## 10. FDA regulatory operation

Weekly signal collection:

```bash
bash scripts/run_fda_sync.sh
```

The wrapper is report-only. It:

- fetches openFDA/FDA RSS/DEA signals
- writes a timestamped `scripts/fda_sync_report_*.json`
- validates the report summary contract
- exits 0 when nothing requires review
- exits 3 when new/stale records require clinical/regulatory review
- never edits or commits `banned_recalled_ingredients.json`

Every proposed change must be verified against its linked primary source,
matched to the correct substance/product and US applicability, tested through
`scripts/test.sh`, and reviewed before it enters curated data.

## 11. Definition of release complete

A release is complete only when:

- all intended brand stages passed strict gates
- snapshot candidates passed and both live artifacts were promoted
- scoring snapshot deltas are reviewed
- export, freshness, interaction, RDA/UL, and Flutter parity gates pass
- Supabase action is successful or explicitly skipped/dry-run by operator intent
- Flutter action is successful or explicitly skipped by operator intent
- the final release process exits zero

A pipeline-only run—even a fully successful one—is not a release.
