# Pipeline Operations README

Updated: 2026-03-29
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
  --enriched-dir output_Emerald-Labs-2-17-26-L88_enriched/enriched \
  --scored-dir output_Emerald-Labs-2-17-26-L88_scored/scored \
  --output-dir scripts/final_db_output_review_final
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
  --state-file /tmp/pg_pair_state.json \
  --changed-only \
  --per-pair-output-root /tmp/pg_pair_outputs
```

Use upstream change journal:

```bash
python3 scripts/build_all_final_dbs.py \
  --scan-dir scripts \
  --change-journal /tmp/pair_change_journal.json \
  --per-pair-output-root /tmp/pg_pair_outputs
```

Important:

- `--changed-only` is for per-pair builds, not partial combined releases
- use `--assemble-release-output` if you want a full release artifact after per-pair builds

## 4. Generate a pair change journal

Create a journal from discovered enriched/scored outputs:

```bash
python3 scripts/generate_pair_change_journal.py \
  --scan-dir scripts \
  --journal-path /tmp/pair_change_journal.json \
  --state-file /tmp/pair_source_state.json
```

This writes:

- a journal of `new`, `changed`, and `removed` pairs
- a persisted source-state file for the next run

## 5. Assemble a full release from per-pair outputs

Assemble from a root of per-pair build outputs:

```bash
python3 scripts/assemble_final_db_release.py \
  --input-root /tmp/pg_pair_outputs \
  --output-dir /tmp/pg_release_output
```

Assemble from one or more explicit per-pair dirs:

```bash
python3 scripts/assemble_final_db_release.py \
  --input-dir /tmp/pg_pair_outputs/Nordic-Naturals-2-17-26-L511 \
  --input-dir /tmp/pg_pair_outputs/Olly-2-17-26-L187 \
  --output-dir /tmp/pg_release_output
```

## 6. Integrated per-pair build + release assembly

Run per-pair builds and assemble a release in one workflow:

```bash
python3 scripts/build_all_final_dbs.py \
  --scan-dir scripts \
  --change-journal /tmp/pair_change_journal.json \
  --per-pair-output-root /tmp/pg_pair_outputs \
  --assemble-release-output /tmp/pg_release_output
```

## 7. Sync build output to Supabase

Dry run:

```bash
python3 scripts/sync_to_supabase.py scripts/final_db_output_review_final --dry-run
```

Real sync:

```bash
python3 scripts/sync_to_supabase.py scripts/final_db_output_review_final
```

Tune upload concurrency and retries:

```bash
python3 scripts/sync_to_supabase.py scripts/final_db_output_review_final \
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

Fetches supplement labels from the NIH DSLD API and writes them as raw JSON files in the **exact same format** as manual downloads. The existing pipeline (clean -> enrich -> score) works identically on both sources.

### Status: Live and verified

- API base URL: `https://api.ods.od.nih.gov/dsld/v9`
- API version: 9.4.0 (January 2026)
- No authentication required for label fetches
- Live probe passed: **100% parity** between API and manual download (label 13418)
- 15 unit tests passing
- Brand sync tested: 186 Olly labels fetched successfully

### Files

- `scripts/dsld_api_client.py` — Low-level API client (retry, rate limit, circuit breaker, disk cache)
- `scripts/dsld_api_sync.py` — CLI with 6 subcommands
- `scripts/tests/test_dsld_api_client.py` — 15 tests

### Quick start

Check API connectivity:

```bash
python3 scripts/dsld_api_sync.py check-version
```

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
  --output-dir raw_data/Nordic-Naturals-2026-03-29
```

The output directory can then be fed directly to the pipeline:

```bash
python3 scripts/clean_dsld_data.py raw_data/Nordic-Naturals-2026-03-29 output_Nordic-cleaned
```

**refresh-ids** — Re-fetch specific label IDs (e.g., after an audit fix):

```bash
python3 scripts/dsld_api_sync.py refresh-ids \
  --ids 13418 241695 182215 \
  --output-dir raw_data/refresh-2026-03-29
```

**sync-query** — Fetch labels matching a search query:

```bash
python3 scripts/dsld_api_sync.py sync-query \
  --query "vitamin d" \
  --output-dir raw_data/query-vitamin-d \
  --limit 50
```

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
  --output-dir raw_data/Olly \
  --snapshot
# Writes to: raw_data/Olly/_snapshots/20260329_143000/
```

### End-to-end workflow: API fetch -> pipeline -> Supabase

```bash
# 1. Fetch a brand via API
python3 scripts/dsld_api_sync.py sync-brand \
  --brand "Thorne" \
  --output-dir raw_data/Thorne-2026-03-29

# 2. Run the pipeline on fetched data
python3 scripts/run_pipeline.py raw_data/Thorne-2026-03-29

# 3. Build final DB
python3 scripts/build_final_db.py \
  --enriched-dir output_Thorne-2026-03-29_enriched/enriched \
  --scored-dir output_Thorne-2026-03-29_scored/scored \
  --output-dir final_db_output

# 4. Sync to Supabase
python3 scripts/sync_to_supabase.py final_db_output
```

### How it works

- `dsld_api_client.py` fetches labels from the API and runs `normalize_api_label()` to ensure the output matches manual downloads exactly
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
  scripts/tests/test_dsld_api_client.py -q
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
  - API-fetched raw JSON feeds the same downstream pipeline (100% parity verified)
  - use `probe --reference` to verify parity any time the API might have changed
