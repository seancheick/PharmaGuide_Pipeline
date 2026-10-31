# PharmaGuide Pipeline Operations

> Canonical operator runbook | Batch/release flow checked against entry points: 2026-10-31

## 1. Which command should I run?

Run from `/Users/seancheick/Downloads/dsld_clean`. For a full Clean → Enrich → Score → snapshot → publication attempt, the command is:

```bash
bash batch_run_all_datasets.sh --pre-check
```

The batch script loads `scripts/python_env.sh` itself. The pre-check is optional;
plain `bash batch_run_all_datasets.sh` follows the same full compute and release
path with essential startup checks. Neither command builds or uploads a phone app.
Both commands can publish to Supabase and update the Flutter bundle after gates
pass, so use `--pipeline-only` or `--skip-release` when publication is not intended.
Both full commands run `scripts/release_full.sh --preflight-only` before corpus
work. A run that may publish needs a pipeline checkout with no tracked changes
and `HEAD` at the freshly fetched `origin/main`; release checks the Flutter
checkout the same way. `--pipeline-only` and `--skip-release` skip this release
preflight.
For the direct Python maintenance commands later in this guide, first run
`source scripts/python_env.sh` in that terminal; the batch and test wrappers
load it for themselves.

`--pipeline-only` chooses where the run stops. `--pre-check` independently chooses
whether aggregate preparation runs before processing. Both combinations are
available on current main.

| Intent                                                    | Command                                                                          | Result                                                                     |
| --------------------------------------------------------- | -------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| Compute only, essential startup checks                    | `bash batch_run_all_datasets.sh --pipeline-only`                                 | Clean → Enrich → Score; no snapshot, upload or Flutter import              |
| Compute only, with full preparation                       | `bash batch_run_all_datasets.sh --pipeline-only --pre-check`                     | Aggregate preparation → Clean → Enrich → Score; then stop                  |
| Compute and release, essential startup checks             | `bash batch_run_all_datasets.sh`                                                 | Clean → Enrich → Score → Snapshot → Release → Supabase → Flutter bundle    |
| Compute and release, with full preparation                | `bash batch_run_all_datasets.sh --pre-check`                                     | Aggregate preparation first, then the full compute/release path            |
| Re-score the corpus from current Enrich outputs           | `bash batch_run_all_datasets.sh --stages score --pipeline-only`                  | Score only for brands; refuses stale upstream inputs                       |
| Build a snapshot after processing, without publishing     | `bash batch_run_all_datasets.sh --skip-release`                                  | Clean → Enrich → Score → local snapshot; no cloud upload or Flutter import |
| Reprocess selected brands                                 | `bash batch_run_all_datasets.sh --targets Brand_A,Brand_B --stages enrich,score` | Selected pipeline only; upstream stages must be current                    |
| Selected brands, then release whole catalog               | Add `--release` to the targeted command                                          | Target pipeline → Snapshot → Release; all catalog inputs must be current   |
| Build catalog without publishing                          | `bash scripts/rebuild_dashboard_snapshot.sh`                                     | Candidate build, gates and local promotion                                 |
| Finish/retry release after a successful pipeline-only run | `bash scripts/release_full.sh`                                                   | Reuse current outputs; build snapshot if needed, then release              |
| Collect weekly regulatory signals                         | `bash scripts/run_fda_sync.sh`                                                   | Report only; exits 3 when clinical review is required                      |

Flutter bundle import updates the app repository's data assets; it does **not**
build, install or distribute a new phone/TestFlight binary. The release makes a
local bundle commit; pushing it and distributing an app build are separate steps.

### Phone package and Transporter handoff

Run app commands from `/Users/seancheick/PharmaGuide ai`, after the reviewed
source and desired catalog bundle are on app `main`:

```bash
cd "/Users/seancheick/PharmaGuide ai"
make verify-bundle
PHARMAGUIDE_IOS_DISTRIBUTION=testflight make build-ios
```

`make build-ios` is the one iOS packaging target. The explicit TestFlight
setting tags beta builds correctly; plain `make build-ios` is the App Store
production configuration. Both export `build/ios/ipa/pharmaguide.ipa` locally
and do not upload it. The builder reserves the build number automatically.
Commit and push that reservation after verifying the exported IPA, then upload
the new file through Transporter yourself. Catalog publication and a Git push
do not update an already exported IPA.

All app commands live in the [Flutter command guide](../../../PharmaGuide%20ai/README.md#supported-commands).
Its online source is the [app README](https://github.com/seancheick/Pharmaguide.ai/blob/main/README.md#supported-commands).
Old per-screen UI-toggle targets are retired. Use `make help` for supported
app targets, not historical design checklists. No pipeline run is needed
merely to package already qualified app/catalog assets.

### Startup checks versus release checks

Every batch checks the runtime, raw-root path and critical reference JSON files.
The existing phone schema compatibility check also applies to a full pipeline-only
run unless `--skip-flutter` is explicit. Publishing runs additionally validate
publishing prerequisites and prepare approved submission inputs before processing.
Those steps can involve disk/network work, so total startup is not guaranteed to
finish within five or ten seconds. The isolated critical-data check measured 0.07
seconds locally on October 15.

`--pre-check` adds aggregate raw/reference/ownership/freshness, canary, and source/live
verification. It can take minutes and stops processing if it fails. For targeted
runs it checks the supplied raw root, not only the selected brands. It does not
include the broad developer test suite. That suite belongs to development/CI;
explicitly repeating it is a separate audit:

```bash
"$PG_PYTHON" scripts/preflight.py --prepare \
  --raw-root "$HOME/Downloads/PharmaGuide_Datasets/staging/brands" \
  --include-source-tests
```

Omitting `--pre-check` skips aggregate preparation only. Strict per-stage validation
and mandatory snapshot/publication gates remain enabled. They can still reject
invalid generated data: no advance check guarantees that future outputs will pass.
Source/clinical changes still require their development validation before merge.

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

### 2.1 Essential startup and dataset discovery

First run the essential checks described above. Aggregate preparation runs only
when `--pre-check` is present. Publishing prerequisites precede optional preparation.

- Root defaults to `$HOME/Downloads/PharmaGuide_Datasets/staging/brands`
  so iCloud cannot evict inputs during a long run.
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
7. Quarantine stale Score outputs and generate complete v4 scored artifacts
   through `score_products_v4.py`.
8. Atomically write the Score outputs and ownership manifest. A partial or
   failed batch cannot leave a promotable manifest.

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

If every brand passed, the batch refreshes any stale locally prepared Product
Submissions through Clean → Enrich → Score as well, then invokes:

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

Finish the source batch before starting snapshot assembly, then keep that
checkout fixed until assembly exits. Its input-stability guard covers catalog
producer Python and shell source, raw labels, scored products and reference
data. Test-runner and test-fixture edits require their own CI/release checks,
but do not make the catalog bytes stale. A dashboard-only change can leave
Clean/Enrich/Score fingerprints
unchanged while still invalidating an assembly already in progress. Do not
merge, fast-forward, or edit that checkout during the build; a PR merge can
also update the local checkout. A rejected candidate is discarded, not
restamped. Check the actual stage fingerprints before deciding whether only
export assembly, rather than any pipeline stage, needs repeating.

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
catalog, use the release owner:

```bash
bash scripts/release_full.sh
```

It builds the snapshot if needed, then finishes release. A separate snapshot
command is useful for inspection, but is not a prerequisite to this command.

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
bash batch_run_all_datasets.sh --stages clean --pipeline-only
bash batch_run_all_datasets.sh --stages enrich,score --pipeline-only
bash batch_run_all_datasets.sh --stages score --pipeline-only
```

The auxiliary Product Submissions source is independently refreshed through
Clean/Enrich/Score if stale; selecting Score does not bypass its input checks.

Use a later-stage-only run only when its upstream owned output is current and
valid. Strict mode validates manifests and checksums rather than trusting every
JSON present in a directory.

Custom dataset root:

```bash
bash batch_run_all_datasets.sh \
  --root "$HOME/Downloads/PharmaGuide_Datasets/staging/brands" \
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

Release preserves the already-prepared submission set by default. It refuses stale
submission stage manifests. `--refresh-submissions` explicitly fetches/processes
new approved intake; prepare new intake before the final corpus run rather than
introducing it during publication.

The downstream steps are:

1. refresh the catalog through the snapshot path if upstream/build inputs are
   newer
2. repair final/dist mismatch through the same snapshot path
3. extract/backfill product images when needed
4. rebuild/stage interaction DB when rule inputs changed
5. sync `dist/` to Supabase after all publication gates pass
6. atomically import and verify Flutter bundle
7. prune `.previous` Flutter DB backups
8. locally commit the Flutter bundle and print separate storage-maintenance
   commands; integration remains manual through a temporary branch, required CI and PR merge.
   Do not push a new local bundle commit directly to protected main. Version and orphan cleanup do not run during
   release. Run the printed gated commands separately when convenient.

Release progress is unbuffered when saved to a log. Sync elapsed time includes
images, search-index updates, registry work and activation, not just blob upload.

Interaction rebuild reuse is content-bound to its build dependencies and staged outputs;
missing or invalid receipts rebuild rather than relying on timestamps. Existing
clinical live checks still run. `--skip-flutter` suppresses reference-data writes
but retains the read-only parity gate. A failed local bundle commit exits nonzero
and reports that cloud publication may already be live; review and commit the
staged app changes before pushing. It does not close submission receipts or
report full completion. No cleanup is attempted on that path.

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

`--force` requests catalog assembly even when it would otherwise be reused. It
does not bypass gates or turn stale prepared submission manifests into current ones.

### Diagnostic high-resolution DSLD images

The shipped catalog keeps the 900px WebP thumbnails. For OCR experiments,
select a bounded sample of numeric DSLD IDs and render larger copies into a
separate directory; this mode never updates `products_core`, the export
manifest, or Flutter assets:

```bash
"$PG_PYTHON" scripts/extract_product_images.py \
  --db-path scripts/dist/pharmaguide_core.db \
  --diagnostic-ids-file /path/to/ids.txt \
  --diagnostic-output-dir /tmp/pharmaguide-dsld-diagnostic \
  --diagnostic-max-width 2400 \
  --diagnostic-quality 95
```

The file accepts one DSLD ID per line (blank lines and `#` comments are
ignored) and is capped at 200 unique IDs. The output contains a
`diagnostic_manifest.json` with source-PDF and rendered-image hashes. These
bytes are for measurement only; benchmark qualification must use the exact
preparation configuration intended for production.

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
- `--pre-check`: opt into aggregate preparation before processing; does not change
  whether the command publishes
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

1. Group score/tier changes by shared cause and compare representative affected
   products plus unaffected controls. Inspect changed safety, status, identity,
   amounts, routing, unsupported credit and unexplained differences.
2. Fix unintended changes at the canonical owner. Do not preserve an obsolete
   score or require per-product approval for expected development movement.
3. Refresh only source-grounded, reviewed expectations through the existing owner;
   never overwrite a baseline to hide an unresolved difference. Clinical holds and
   new scoring policy still require Sean.
4. Check fingerprints and regenerate from the earliest stale stage if needed.
   Otherwise rerun `release_full.sh`; current earlier outputs are reused.

### Supabase or Flutter step fails

Fix credentials/path/import/parity issue and rerun `release_full.sh`. Its
freshness/checksum checks reuse already-gated artifacts.

## 9. Tests and audits

Use only the supported test runner:

```bash
scripts/test.sh fast scripts/tests/test_release_full_catalog_path.py
scripts/test.sh local     # Required corpus checks for a completed behavioral batch
scripts/test.sh release   # Prepublication validation of the current catalog
scripts/test.sh full      # Post-pipeline backstop, never alongside a corpus run
```

Use named files/nodes while fixing a defect. Whole-fast validation normally runs
in CI; run it locally only when CI is unavailable. Do not run broad local/release/
full suites alongside an active corpus job.

The default release test runs before `release_full.sh` imports the catalog into
Flutter. An older app bundle is expected then and does not make the pipeline
stale. `release_full.sh` imports the bundle and verifies catalog/interaction
checksum parity afterward. To repeat the release suite after import, use
`PG_RELEASE_PHASE=postimport scripts/test.sh release`; that phase adds Flutter
parity and fails on content differences, regardless of file timestamps.

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

## 11. Brand coverage and freshness audit

Answers two different questions that are easy to confuse:

1. **Completeness** — did we download every on-market DSLD label for the brands
   we track, or did something get silently skipped?
2. **Freshness** — does the brand appear in recent DSLD batches? A brand can be
   100% complete and still fail in a store. `entryDate` is DSLD's monthly
   **batch-load** date, not the manufacturer's filing date.

```bash
source scripts/python_env.sh

# Full check, all brands (one API call per brand, ~30s)
"$PG_PYTHON" scripts/audit_brand_coverage.py

# Limit to specific brands
"$PG_PYTHON" scripts/audit_brand_coverage.py --targets CVS,GNC

# Prove SET membership instead of counts (slower, pages every label id)
"$PG_PYTHON" scripts/audit_brand_coverage.py --ids --targets GNC,BulkSupplements
```

Output:

```text
brand                       on disk   LIVE on-mkt   delta       newest  %fresh
------------------------------------------------------------------------------
CVS                             240           240      +0   2023-06-22      0%
GNC                            2214          2214      +0   2025-09-25     16%
Thorne                          196           196      +0   2025-09-25     60%
------------------------------------------------------------------------------
TOTALS  on disk=2,796  live on-mkt=2,796  delta=+0
brands with any delta: 0

STALE — complete, but no label filed since 2024-01-01. ...
  - CVS: newest label 2023-06-22
```

Exit codes: `0` every brand matches, `1` at least one delta, `2` bad usage.
Freshness is advisory and never changes the exit code.

### Reading the result

- **delta `+N`** — DSLD has labels we do not. Either new products were published
  since the last download, or the derived brand query is wrong. Check the query
  before assuming missing data.
- **delta `-N`** — we hold labels DSLD no longer lists on-market. Usually a
  product left the market; not an error.
- **Matching counts are not proof.** One product leaving the market while
  another appears nets to zero. Use `--ids` on any brand that matters.
- **STALE** — the brand has not appeared in a recent DSLD batch, so its newer
  SKUs are not obtainable from DSLD at any price. Coverage is partial, not
  useless: older SKUs still on shelf keep scanning. Do NOT infer that the
  manufacturer stopped filing — only that DSLD has not published those labels.
- **DSLD-wide lag.** Compare the latest live results before drawing conclusions
  about a single brand. The dates in the sample above are historical examples,
  not a current statement of DSLD coverage. A brand's newest published label does
  not establish the manufacturer's filing behavior.

  ```bash
  "$PG_PYTHON" scripts/audit_brand_coverage.py --targets Thorne,Nature_Made
  ```

### Brand query derivation

DSLD's `brand` filter matches by prefix, and one folder usually holds several
sub-brand strings. The query is the longest common **word** prefix of every
`brandName` in the folder, case-insensitively — so a `CVS` folder holding
"CVS Health" and "CVS Pharmacy" queries as `CVS` and finds both. Override a
bad derivation with `--brand-map`.

### When to run it

- Before any catalog publish.
- Before adding a new brand wave — check the candidates' freshness first, so a
  brand that stopped filing is not selected for a scan-probability wave.
- Monthly, as a cheap drift check.

Refreshing is a delta, not a re-download: `scripts/dsld_api_sync.py` brand mode
defaults to `--status 1` and takes `--state-file`, which classifies every label
as new / changed / unchanged against the prior run.

## 12. Definition of release complete

A release is complete only when:

- all intended brand stages passed strict gates
- snapshot candidates passed and both live artifacts were promoted
- scoring snapshot deltas are reviewed
- export, freshness, interaction, RDA/UL, and Flutter parity gates pass
- Supabase action is successful or explicitly skipped/dry-run by operator intent
- Flutter action is successful or explicitly skipped by operator intent
- the final release process exits zero

A pipeline-only run—even a fully successful one—is not a release.
