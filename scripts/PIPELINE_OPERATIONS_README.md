# Pipeline Operations README

Updated: 2026-03-30
Owner: Sean Cheick Baradji

This file is a practical command guide for the pipeline work added and updated today.

It covers:

- final DB build
- incremental pair builds
- pair change-journal generation
- assembled release creation
- Supabase sync
- DSLD API tooling status and commands

## 1. Build a final DB from enriched + scored outputs

Build one final release artifact directly:

```bash
python3 scripts/build_final_db.py \
  --enriched-dir /Users/seancheick/Documents/DataSetDsld/output_olly_2026-03-30T01-49-58_enriched/enriched \
  --scored-dir /Users/seancheick/Documents/DataSetDsld/output_olly_2026-03-30T01-49-58_scored/scored \
  --output-dir /Users/seancheick/Documents/DataSetDsld/final_db_output_olly_2026-03-30T01-49-58
```

Output includes:

- `pharmaguide_core.db`
- `detail_blobs/`
- `detail_index.json`
- `export_manifest.json`

## 2. Auto-discover and build all final DBs

Build from all discovered enriched/scored pairs:

```bash
python3 scripts/build_all_final_dbs.py --scan-dir scripts
```

Plan without building:

```bash
python3 scripts/build_all_final_dbs.py --scan-dir scripts --plan-only
```

Build only selected brands:

```bash
python3 scripts/build_all_final_dbs.py \
  --scan-dir scripts \
  --include-prefix Nordic \
  --include-prefix Olly
```

Exclude brands:

```bash
python3 scripts/build_all_final_dbs.py \
  --scan-dir scripts \
  --exclude-prefix Emerald
```

## 3. Incremental pair builds

Use fingerprint state:

```bash
python3 scripts/build_all_final_dbs.py \
  --scan-dir scripts \
  --state-file /Users/seancheick/Documents/DataSetDsld/builds/pair_state.json \
  --changed-only \
  --per-pair-output-root /Users/seancheick/Documents/DataSetDsld/builds/pair_outputs
```

Use upstream change journal:

```bash
python3 scripts/build_all_final_dbs.py \
  --scan-dir scripts \
  --change-journal /Users/seancheick/Documents/DataSetDsld/builds/pair_change_journal.json \
  --per-pair-output-root /Users/seancheick/Documents/DataSetDsld/builds/pair_outputs
```

Important:

- `--changed-only` is for per-pair builds, not partial combined releases
- use `--assemble-release-output` if you want a full release artifact after per-pair builds

## 4. Generate a pair change journal

Create a journal from discovered enriched/scored outputs:

```bash
python3 scripts/generate_pair_change_journal.py \
  --scan-dir scripts \
  --journal-path /Users/seancheick/Documents/DataSetDsld/builds/pair_change_journal.json \
  --state-file /Users/seancheick/Documents/DataSetDsld/builds/pair_source_state.json
```

This writes:

- a journal of `new`, `changed`, and `removed` pairs
- a persisted source-state file for the next run

## 5. Assemble a full release from per-pair outputs

Assemble from a root of per-pair build outputs:

```bash
python3 scripts/assemble_final_db_release.py \
  --input-root /Users/seancheick/Documents/DataSetDsld/builds/pair_outputs \
  --output-dir /Users/seancheick/Documents/DataSetDsld/builds/release_output
```

Assemble from one or more explicit per-pair dirs:

```bash
python3 scripts/assemble_final_db_release.py \
  --input-dir /Users/seancheick/Documents/DataSetDsld/builds/pair_outputs/Nordic-Naturals-2-17-26-L511 \
  --input-dir /Users/seancheick/Documents/DataSetDsld/builds/pair_outputs/Olly-2-17-26-L187 \
  --output-dir /Users/seancheick/Documents/DataSetDsld/builds/release_output
```

## 6. Integrated per-pair build + release assembly

Run per-pair builds and assemble a release in one workflow:

```bash
python3 scripts/build_all_final_dbs.py \
  --scan-dir scripts \
  --change-journal /Users/seancheick/Documents/DataSetDsld/builds/pair_change_journal.json \
  --per-pair-output-root /Users/seancheick/Documents/DataSetDsld/builds/pair_outputs \
  --assemble-release-output /Users/seancheick/Documents/DataSetDsld/builds/release_output
```

## 7. Sync build output to Supabase

Dry run:

```bash
python3 scripts/sync_to_supabase.py /Users/seancheick/Documents/DataSetDsld/final_db_output_olly_2026-03-30T01-49-58 --dry-run
```

Real sync:

```bash
python3 scripts/sync_to_supabase.py /Users/seancheick/Documents/DataSetDsld/final_db_output_olly_2026-03-30T01-49-58
```

Tune upload concurrency and retries:

```bash
python3 scripts/sync_to_supabase.py /Users/seancheick/Documents/DataSetDsld/final_db_output_olly_2026-03-30T01-49-58 \
  --max-workers 8 \
  --retry-count 3 \
  --retry-base-delay 1.0
```

Current sync behavior:

- uploads `pharmaguide_core.db`
- uploads `detail_index.json`
- uploads hashed detail blobs under shared storage paths
- skips unchanged hashed blobs when already present remotely
- uses retry/backoff for uploads

## 8. DSLD API tooling

### What it does

Fetches supplement labels from the NIH DSLD API and writes them into the same raw-label contract used by manual downloads. The goal is for the existing pipeline (clean -> enrich -> score) to process API-fetched labels without a separate downstream path.

### Status: Live and verified

- API base URL: `https://api.ods.od.nih.gov/dsld/v9`
- Live structured version check passed from your machine
- Live probe passed: **100% parity** between API output and one known manual download (`13418`)
- `sync-brand --brand "Olly"` fetched and wrote `186/186` labels successfully
- API test coverage currently passing:
  - `18` tests in `scripts/tests/test_dsld_api_client.py`
  - `20` tests in `scripts/tests/test_dsld_api_sync.py`

### Files

- `scripts/dsld_api_client.py` — Low-level API client (retry, rate limit, circuit breaker, disk cache)
- `scripts/dsld_api_sync.py` — CLI with 6 subcommands
- `scripts/tests/test_dsld_api_client.py` — client and normalization tests
- `scripts/tests/test_dsld_api_sync.py` — sync CLI and parity helper tests

### Quick start

Check structured API version metadata:

```bash
python3 scripts/dsld_api_sync.py check-version
```

This calls the real deployed DSLD version endpoint:

- `https://api.ods.od.nih.gov/dsld/version`

### Canonical form corpus

The long-term recommended DSLD raw corpus is now canonical-by-form:

```text
/Users/seancheick/Documents/DataSetDsld/forms/gummies/*.json
/Users/seancheick/Documents/DataSetDsld/forms/softgels/*.json
/Users/seancheick/Documents/DataSetDsld/forms/capsules/*.json
/Users/seancheick/Documents/DataSetDsld/forms/bars/*.json
/Users/seancheick/Documents/DataSetDsld/forms/powders/*.json
/Users/seancheick/Documents/DataSetDsld/forms/lozenges/*.json
/Users/seancheick/Documents/DataSetDsld/forms/tablets-pills/*.json
/Users/seancheick/Documents/DataSetDsld/forms/liquids/*.json
/Users/seancheick/Documents/DataSetDsld/forms/other/*.json
```

Identity rule:

- `dsld_id` is the only product identity key
- if a label is discovered through both a brand pull and a form pull, it is still one product
- overlap is deduped by `dsld_id`

Recommended permanent layout if you want this outside the repo and under your existing dataset root:

```text
/Users/seancheick/Documents/DataSetDsld/
/Users/seancheick/Documents/DataSetDsld/forms/
/Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json
/Users/seancheick/Documents/DataSetDsld/delta/<brand>/<timestamp>/
/Users/seancheick/Documents/DataSetDsld/reports/<brand>/<timestamp>.json
/Users/seancheick/Documents/DataSetDsld/staging/
```

Example:

```text
/Users/seancheick/Documents/DataSetDsld/
/Users/seancheick/Documents/DataSetDsld/forms/gummies/*.json
/Users/seancheick/Documents/DataSetDsld/forms/softgels/*.json
/Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json
/Users/seancheick/Documents/DataSetDsld/delta/olly/2026-03-30T15-04-05/*.json
/Users/seancheick/Documents/DataSetDsld/reports/olly/2026-03-30T15-04-05.json
/Users/seancheick/Documents/DataSetDsld/staging/
```

Meaning:

- `forms/` = canonical raw source of truth
- `state/` = shared sync memory
- `delta/` = dated new/changed raw sets for each run
- `reports/` = dated sync audit reports
- `staging/` = optional temporary seed/review folders

Migration note:

- your existing manually downloaded flat brand folders still work as raw input for the cleaner
- they already match the raw DSLD contract closely enough for the downstream pipeline
- but they are not the best long-term home for the new `sync-delta` workflow
- for long-term maintenance, use canonical-by-form storage plus one shared state file
- use brand folders only as legacy inputs, snapshots, or temporary review sets
- `staging/` is optional and should not be treated as long-term truth

Recommended market status values:

- `--status 0` = off market only
- `--status 1` = on market only
- `--status 2` = all

Recommended default:

- use `--status 2` for canonical corpus syncs so discontinued products remain available for scans

### Form code table

- `e0176` = gummies
- `e0161` = softgels
- `e0159` = capsules
- `e0164` = bars
- `e0162` = powders
- `e0174` = lozenges
- `e0155` = tablets-pills
- `e0165` = liquids
- `e0172` = other
- `e0177` = other

### Commands

**probe** — Fetch one label and optionally compare against a manual download:

```bash
# Just fetch and display
python3 scripts/dsld_api_sync.py probe --id 13418

# Compare against a reference file (parity check)
python3 scripts/dsld_api_sync.py probe \
  --id 13418 \
  --reference /Users/seancheick/Documents/DataSetDsld/Nordic-Naturals-2-17-26-L511/13418.json
```

**sync-brand** — Fetch all labels for a brand into a flat directory:

```bash
python3 scripts/dsld_api_sync.py sync-brand \
  --brand "Nordic Naturals" \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json
```

If you also want a flat staging copy for review:

```bash
python3 scripts/dsld_api_sync.py sync-brand \
  --brand "Nordic Naturals" \
  --status 2 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json \
  --output-dir /Users/seancheick/Documents/DataSetDsld/staging/brands/nordic-naturals
```

The canonical form corpus or any staging directory can then be fed directly to the pipeline:

```bash
cd scripts
python3 clean_dsld_data.py \
  --input-dir /Users/seancheick/Documents/DataSetDsld/staging/brands/nordic-naturals \
  --output-dir /Users/seancheick/Documents/DataSetDsld/output_nordic_seed_cleaned \
  --config config/cleaning_config.json
```

Note:

- `clean_dsld_data.py` currently expects to be run from the `scripts/` directory because of relative-path assumptions in its config/reference-data handling

**refresh-ids** — Re-fetch specific label IDs (e.g., after an audit fix):

```bash
python3 scripts/dsld_api_sync.py refresh-ids \
  --ids 13418 241695 182215 \
  --output-dir /Users/seancheick/Documents/DataSetDsld/staging/refresh-ids
```

**sync-query** — Fetch labels matching a search query:

```bash
python3 scripts/dsld_api_sync.py sync-query \
  --query "vitamin d" \
  --output-dir /Users/seancheick/Documents/DataSetDsld/staging/query-vitamin-d \
  --limit 50
```

**sync-filter** — Fetch labels through DSLD filter fields and route them into the canonical form corpus:

Pull all gummies into the canonical form corpus:

```bash
python3 scripts/dsld_api_sync.py sync-filter \
  --supplement-form e0176 \
  --status 2 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json
```

Pull only on-market softgels and keep a staging copy:

```bash
python3 scripts/dsld_api_sync.py sync-filter \
  --supplement-form e0161 \
  --status 1 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json \
  --staging-dir /Users/seancheick/Documents/DataSetDsld/staging/forms/softgels
```

Pull products containing melatonin:

```bash
python3 scripts/dsld_api_sync.py sync-filter \
  --ingredient-name melatonin \
  --status 2 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json
```

Pull a recent date window:

```bash
python3 scripts/dsld_api_sync.py sync-filter \
  --date-start 2026-01-01 \
  --date-end 2026-03-30 \
  --status 2 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json
```

Important:

- `sync-filter` updates canonical form folders when `--canonical-root` is provided
- `--staging-dir` is optional and creates a flat review/work folder
- date windows are good for newly added labels, not all label changes

**sync-delta** — Fetch only new or changed labels based on the shared state file:

Delta-sync a brand and write a cleaner-ready delta set:

```bash
python3 scripts/dsld_api_sync.py sync-delta \
  --brand "Olly" \
  --status 2 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json \
  --delta-output-dir /Users/seancheick/Documents/DataSetDsld/delta/olly \
  --dated-delta \
  --report-dir /Users/seancheick/Documents/DataSetDsld/reports/olly
```

Delta-sync gummies without producing a pipeline-ready delta folder:

```bash
python3 scripts/dsld_api_sync.py sync-delta \
  --supplement-form e0176 \
  --status 2 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json
```

Important:

- with `--delta-output-dir`, changed/new labels are written there as a flat cleaner-ready set
- without `--delta-output-dir`, canonical form folders and state are updated only
- off-market products are retained in canonical storage and continue through scoring/build
- if the state file does not exist yet, the first `sync-delta` run behaves like an initial full seed for that discovery lane
- after that first seed, later runs only write newly changed/new labels into the delta directory
- if you already have an old flat folder like `/Users/seancheick/Documents/DataSetDsld/Olly`, that does not break anything, but it does not replace the shared sync state
- `--dated-delta` is the recommended mode: it writes each run into a fresh timestamped subdirectory under `--delta-output-dir`
- example resolved path:
  - `/Users/seancheick/Documents/DataSetDsld/delta/olly/2026-03-30T15-04-05/`
- this avoids stale files from previous runs making a no-change delta look non-empty
- `--report-dir` writes a JSON run report for auditing and review
- example report path:
  - `/Users/seancheick/Documents/DataSetDsld/reports/olly/2026-03-30T15-04-05.json`
- the report includes:
  - candidate count
  - new / changed / unchanged counts
  - skipped and failed IDs
  - off-market IDs seen in the run
  - resolved delta directory for that run

### Recommended operator workflows

Use these as the default day-to-day commands.

Standard workflow:

- keep `forms/`, `state/`, `delta/`, and `reports/`
- use `staging/` only when you explicitly want a temporary flat seed/review folder
- after initial seeding, most ongoing maintenance should be `sync-delta`

### Operator cheat sheet

Use this section when you just want the exact commands.

#### Brand, first time

Seed the canonical corpus and create a flat working folder:

```bash
python3 scripts/dsld_api_sync.py sync-brand \
  --brand "Olly" \
  --status 2 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json \
  --output-dir /Users/seancheick/Documents/DataSetDsld/staging/brands/olly
```

Run pipeline on that first-time brand folder:

```bash
python3 scripts/run_pipeline.py \
  --raw-dir /Users/seancheick/Documents/DataSetDsld/staging/brands/olly \
  --output-prefix /Users/seancheick/Documents/DataSetDsld/output_olly_seed
```

#### Brand, second time or later

Fetch only new/changed products:

```bash
python3 scripts/dsld_api_sync.py sync-delta \
  --brand "Olly" \
  --status 2 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json \
  --delta-output-dir /Users/seancheick/Documents/DataSetDsld/delta/olly \
  --dated-delta \
  --report-dir /Users/seancheick/Documents/DataSetDsld/reports/olly
```

Then run pipeline on the printed dated delta folder:

```bash
python3 scripts/run_pipeline.py \
  --raw-dir /Users/seancheick/Documents/DataSetDsld/delta/olly/2026-03-30T01-49-58 \
  --output-prefix /Users/seancheick/Documents/DataSetDsld/output_olly_2026-03-30T01-49-58
```

#### Form/category, first time

If you want a flat first-time working set:

```bash
python3 scripts/dsld_api_sync.py sync-filter \
  --supplement-form e0176 \
  --status 2 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json \
  --staging-dir /Users/seancheick/Documents/DataSetDsld/staging/forms/gummies
```

Run pipeline on that first-time form folder:

```bash
python3 scripts/run_pipeline.py \
  --raw-dir /Users/seancheick/Documents/DataSetDsld/staging/forms/gummies \
  --output-prefix /Users/seancheick/Documents/DataSetDsld/output_gummies_seed
```

#### Form/category, second time or later

Fetch only new/changed products:

```bash
python3 scripts/dsld_api_sync.py sync-delta \
  --supplement-form e0176 \
  --status 2 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json \
  --delta-output-dir /Users/seancheick/Documents/DataSetDsld/delta/gummies \
  --dated-delta \
  --report-dir /Users/seancheick/Documents/DataSetDsld/reports/gummies
```

Then run pipeline on the printed dated delta folder:

```bash
python3 scripts/run_pipeline.py \
  --raw-dir /Users/seancheick/Documents/DataSetDsld/delta/gummies/2026-03-30T01-49-58 \
  --output-prefix /Users/seancheick/Documents/DataSetDsld/output_gummies_2026-03-30T01-49-58
```

#### 1. First-time brand seed

Use this when you want to add a brand into the canonical corpus for the first time and also get a flat brand-only folder to run through the pipeline immediately.

This is one of the few cases where `staging/` is useful.

```bash
python3 scripts/dsld_api_sync.py sync-brand \
  --brand "Olly" \
  --status 2 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json \
  --output-dir /Users/seancheick/Documents/DataSetDsld/staging/brands/olly
```

Run the pipeline on that first-time brand seed:

```bash
python3 scripts/run_pipeline.py \
  --raw-dir /Users/seancheick/Documents/DataSetDsld/staging/brands/olly \
  --output-prefix /Users/seancheick/Documents/DataSetDsld/output_olly_seed
```

#### 2. First-time category/form seed

Use this when you want to seed a full category such as gummies, softgels, or capsules into the canonical corpus and also get a flat category folder to run through the pipeline.

This is also an optional `staging/` workflow.

Example: first-time gummies seed

```bash
python3 scripts/dsld_api_sync.py sync-filter \
  --supplement-form e0176 \
  --status 2 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json \
  --staging-dir /Users/seancheick/Documents/DataSetDsld/staging/forms/gummies
```

Run the pipeline on that first-time category seed:

```bash
python3 scripts/run_pipeline.py \
  --raw-dir /Users/seancheick/Documents/DataSetDsld/staging/forms/gummies \
  --output-prefix /Users/seancheick/Documents/DataSetDsld/output_gummies_seed
```

#### 3. Update a brand later with only new/changed products

Use this after the first seed when you want only the brand delta.

```bash
python3 scripts/dsld_api_sync.py sync-delta \
  --brand "Olly" \
  --status 2 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json \
  --delta-output-dir /Users/seancheick/Documents/DataSetDsld/delta/olly \
  --dated-delta \
  --report-dir /Users/seancheick/Documents/DataSetDsld/reports/olly
```

What to run next:

- read the printed `Delta directory:` path
- run the pipeline on that exact dated folder

Example:

```bash
python3 scripts/run_pipeline.py \
  --raw-dir /Users/seancheick/Documents/DataSetDsld/delta/olly/2026-03-30T01-49-58 \
  --output-prefix /Users/seancheick/Documents/DataSetDsld/output_olly_2026-03-30T01-49-58
```

#### 4. Update a category/form later with only new/changed products

Example: update capsules and process only the capsules delta

```bash
python3 scripts/dsld_api_sync.py sync-delta \
  --supplement-form e0159 \
  --status 2 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json \
  --delta-output-dir /Users/seancheick/Documents/DataSetDsld/delta/capsules \
  --dated-delta \
  --report-dir /Users/seancheick/Documents/DataSetDsld/reports/capsules
```

Then run the pipeline on the printed dated delta folder:

```bash
python3 scripts/run_pipeline.py \
  --raw-dir /Users/seancheick/Documents/DataSetDsld/delta/capsules/2026-03-30T01-49-58 \
  --output-prefix /Users/seancheick/Documents/DataSetDsld/output_capsules_2026-03-30T01-49-58
```

#### 5. What to process after each kind of sync

- `sync-brand` with `--output-dir`:
  - process the `--output-dir` folder
- `sync-filter` with `--staging-dir`:
  - process the `--staging-dir` folder
- `sync-delta` with `--delta-output-dir --dated-delta`:
  - process the printed `Delta directory:` dated folder
- `sync-brand` or `sync-filter` with only `--canonical-root` and no staging folder:
  - this updates the canonical corpus only
  - it does not create a clean brand-only or category-only pipeline input folder by itself

#### 6. How to read the result

- if a later `sync-delta` run prints `delta=0`, there were no new/changed labels for that run
- the dated delta folder for that run may still exist as an empty or near-empty audit artifact
- the JSON report in `--report-dir` is the clean place to check:
  - `new_count`
  - `changed_count`
  - `unchanged_count`
  - `failed_ids`
  - `off_market_ids`

**verify-db** — Sample-verify existing raw files against the API (non-destructive, never overwrites):

```bash
python3 scripts/dsld_api_sync.py verify-db \
  --input-dir /Users/seancheick/Documents/DataSetDsld/Nordic-Naturals-2-17-26-L511 \
  --sample-size 10
```

**--snapshot mode** — Write to a timestamped subdirectory instead of overwriting:

```bash
python3 scripts/dsld_api_sync.py sync-brand \
  --brand "Olly" \
  --output-dir /Users/seancheick/Documents/DataSetDsld/staging/brands/olly \
  --snapshot
# Writes to: /Users/seancheick/Documents/DataSetDsld/staging/brands/olly/_snapshots/20260329_143000/
```

### End-to-end workflow: recommended delta path

```bash
# 1. Update a brand and create a dated delta folder + report
python3 scripts/dsld_api_sync.py sync-delta \
  --brand "Thorne" \
  --status 2 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json \
  --delta-output-dir /Users/seancheick/Documents/DataSetDsld/delta/thorne \
  --dated-delta \
  --report-dir /Users/seancheick/Documents/DataSetDsld/reports/thorne

# 2. Run the pipeline on the printed dated delta folder
python3 scripts/run_pipeline.py \
  --raw-dir /Users/seancheick/Documents/DataSetDsld/delta/thorne/2026-03-30T01-49-58 \
  --output-prefix /Users/seancheick/Documents/DataSetDsld/output_thorne_2026-03-30T01-49-58

# 3. Build final DB
python3 scripts/build_final_db.py \
  --enriched-dir /Users/seancheick/Documents/DataSetDsld/output_thorne_2026-03-30T01-49-58_enriched/enriched \
  --scored-dir /Users/seancheick/Documents/DataSetDsld/output_thorne_2026-03-30T01-49-58_scored/scored \
  --output-dir /Users/seancheick/Documents/DataSetDsld/final_db_output_thorne_2026-03-30T01-49-58

# 4. Sync to Supabase
python3 scripts/sync_to_supabase.py /Users/seancheick/Documents/DataSetDsld/final_db_output_thorne_2026-03-30T01-49-58
```

### How it works

- `dsld_api_client.py` fetches labels from the API and runs `normalize_api_label()` to force the expected raw-label key contract
- Each label is written as `{dsld_id}.json` in a flat directory (same as manual downloads)
- The only difference: API-fetched files have `"_source": "api"` added as a provenance field
- The pipeline ignores `_source` — it processes API and manual files identically
- Rate limited to ~6.6 requests/second (0.15s delay) to respect NIH API limits
- Retries failed requests up to 4 times with exponential backoff
- Circuit breaker trips after 3 consecutive failures

## 9. Verification commands

Core pipeline verification:

```bash
pytest \
  scripts/tests/test_build_final_db.py \
  scripts/tests/test_build_all_final_dbs.py \
  scripts/tests/test_sync_to_supabase.py \
  scripts/tests/test_supabase_client.py \
  scripts/tests/test_assemble_final_db_release.py \
  scripts/tests/test_generate_pair_change_journal.py \
  scripts/tests/test_dsld_api_client.py \
  scripts/tests/test_dsld_api_sync.py -q
```

Syntax verification:

```bash
python3 -m py_compile \
  scripts/build_final_db.py \
  scripts/build_all_final_dbs.py \
  scripts/sync_to_supabase.py \
  scripts/supabase_client.py \
  scripts/assemble_final_db_release.py \
  scripts/generate_pair_change_journal.py \
  scripts/dsld_api_client.py \
  scripts/dsld_api_sync.py
```

## 10. Important operating notes

- The pipeline architecture is now more scalable on the build/sync side than before:
  - incremental pair selection
  - per-pair cached builds
  - assembled full releases
  - hashed shared detail-blob sync
  - concurrent/retrying uploads
- The Flutter-related docs and Supabase schema were updated to match the corrected export/sync model.
- The DSLD API path is additive, not a replacement:
  - manual raw JSON still works
  - API-fetched raw JSON now has:
    - live connectivity verification
    - one successful parity probe against a real manual label
    - one successful live brand sync for `Olly`
  - broader parity confidence should come from more real-label probes over time, not one label
  - use `probe --reference` any time the API response shape might have changed
