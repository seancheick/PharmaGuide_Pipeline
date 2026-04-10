# Pipeline Operations README

Updated: 2026-04-10
Owner: Sean Cheick Baradji

This file is a practical command guide for the pipeline work added and updated today.

It covers:

- final DB build
- incremental pair builds
- pair change-journal generation
- assembled release creation
- Supabase sync
- DSLD API tooling status and commands

## Schema version history

| Version  | Date       | Columns | Summary                                                                                                              |
|----------|------------|---------|----------------------------------------------------------------------------------------------------------------------|
| v1.3.0   | 2026-04-07 | 87      | Stack interaction, social sharing, search/filter, goal matching, dosing/allergen summary                             |
| v1.3.1   | 2026-04-10 | 89      | `serving_info` phantom key bugfix (`dosing_summary` + `servings_per_container` now populate) + `net_contents_*`      |
| v1.3.2   | 2026-04-10 | 90      | Nutrition hybrid (`calories_per_serving` column + `nutrition_detail` blob) + `unmapped_actives` blob transparency    |

Runtime source of truth: `CORE_COLUMN_COUNT` in `build_final_db.py` plus `EXPORT_SCHEMA_VERSION`. See `FINAL_EXPORT_SCHEMA_V1.md` for the per-column contract.

### What landed in v1.3.1 and v1.3.2 (field-level audit cycle, 2026-04-10)

The 2026-04 audit traced every field across Clean → Enrich → Score → Final DB → Flutter, looking for silent drops where one stage computed data that a downstream stage ignored (Bug C pattern — named after the original probiotic `clinical_strain_count` bug from 2026-04-09). Ten tracks landed across the cycle:

- **Track 1 (v1.3.1)**: Fixed `serving_info` phantom key in `generate_dosing_summary`. The function was reading a nonexistent `enriched["serving_info"]` path, so `dosing_summary` always fell through to "See product label" and `servings_per_container` was always NULL. Rewrote it to read the real cleaner-emitted `servingSizes[0]` + `servingsPerContainer`. Also added `net_contents_quantity` + `net_contents_unit` columns for the refill-reminder feature. Flutter computes `days_until_empty = net_contents_quantity / (servingSizes[0].maxQuantity * maxDailyServings)`.
- **Track 2**: The enricher now strips 14 dead passthrough fields (`src`, `nhanesId`, `brandIpSymbol`, `productVersionCode`, `pdf`, `thumbnail`, `percentDvFootnote`, `hasOuterCarton`, `upcValid`, `productType`, `events`, `labelRelationships`, `metadata`, `images`). They were riding through from cleaner → enricher → final DB with zero downstream consumers, inflating record size. `display_ingredients` is kept because the enricher overwrites it.
- **Track 3**: Deleted three orphaned top-level reads (`qualityFeatures`, `certifications`, `otherIngredients`) in `_extract_text_sources`. The cleaner nests these under `labelText.parsed.*`, and the parsed iteration already captures them.
- **Track 4**: Amount-based sugar penalty in B1. Reads `dietary_sensitivity_data.sugar.level` from the enricher and docks `-0.5` for `moderate` (3–5 g) and `-1.5` for `high` (>5 g). Config-driven via `section_B_safety_purity.B1_dietary_sugar_penalty` in `scoring_config.json` (enables future per-user personalization — e.g. stronger penalty for diabetic profiles). Emits `SUGAR_LEVEL_MODERATE` or `SUGAR_LEVEL_HIGH` flags and B1 evidence entries. Stacks with the existing named-sweetener B1 penalty but the combined total is clamped to the existing B1 cap.
- **Track 5 (blob)**: `unmapped_actives` packed into `detail_blob.unmapped_actives` with `{names, total, excluding_banned_exact_alias}` shape. Always present (empty shape when nothing unmapped) so the Flutter app can render a transparency panel without null checks. The coverage gate stays at 99.5% for the batch-level BLOCK — we accept exotic long-tail ingredients, but users can now see which specific names failed to map.
- **Track 6 (nutrition hybrid, v1.3.2)**: Enricher emits `nutrition_summary` with all five macros (`calories_per_serving`, `total_carbohydrates_g`, `total_fat_g`, `protein_g`, `dietary_fiber_g`). Final DB adds one column (`calories_per_serving`, highest-value filter) and packs the remaining four plus calories into `detail_blob.nutrition_detail`. Promote more macros to columns later if usage justifies it.
- **Track 7 (Flutter sync)**: `lib/data/database/tables/products_core_table.dart` updated to match the 90-column pipeline schema. Added `netContentsQuantity`, `netContentsUnit`, `caloriesPerServing` Drift columns with refill-reminder and nutrition-hybrid docstrings. **One manual step still required**: run `dart run build_runner build --delete-conflicting-outputs` from the Flutter repo to regenerate `core_database.g.dart`.

## Supabase deployment checklist

The pipeline targets an **offline-first architecture**: the products table lives inside the SQLite file (`pharmaguide_core.db`) that ships as a Supabase Storage blob, NOT in the Supabase Postgres layer. This means **v1.3.2 needs no SQL migration on Supabase** — the Postgres tables (`export_manifest`, `user_stacks`, `user_usage`, `pending_products`) are unchanged.

What actually moves:

- `pharmaguide_core.db` → uploaded verbatim to `pharmaguide/v{db_version}/pharmaguide_core.db` in Storage. Contains the full 90-column `products_core` table.
- `detail_blobs/*.json` → uploaded to `pharmaguide/shared/details/sha256/{prefix}/{hash}.json` in Storage. Each blob now has `nutrition_detail` and `unmapped_actives` subkeys added by v1.3.2.
- `export_manifest.json` → insert-new-row via `rotate_manifest(p_schema_version='1.3.2', ...)` RPC. The `schema_version` column on the Postgres manifest table is already present; the RPC just receives `'1.3.2'` as the string value.

**Rollout checks** (run before a production sync):

1. Local build produces `export_manifest.json` with `schema_version: "1.3.2"`, `pipeline_version: "3.4.0"`, `scoring_version: "3.4.0"`
2. Parity tests green: `python3 -m pytest scripts/tests/test_release_export_parity.py -q`
3. Dry-run sync: `python3 scripts/sync_to_supabase.py <build_dir> --dry-run`
4. Verify no Flutter consumer is pinned to `schema_version < 1.3.2` in the app — bumping the minor version is non-breaking for older apps (new columns are `.nullable()`) but the Flutter Drift regen is still needed for the app to READ the new columns.

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

## 7A. Recommended release pattern

For local QA, it is fine to build dataset-specific final DB outputs such as:

- `final_db_output_hum_...`
- `final_db_output_gummies_...`

These are useful for:

- reviewing one brand or one form/category in isolation
- validating one new batch before release
- debugging export issues without rebuilding everything

For the actual app-facing Supabase release, the recommended default is:

1. Build per-pair outputs for the brand(s) or form/category set you want to review
2. QA those per-pair outputs
3. Assemble one combined release artifact
4. Sync that one combined release artifact to Supabase

Reason:

- `sync_to_supabase.py` pushes one build directory and one active manifest/version at a time
- the app should usually read one coherent product universe, not a rotating slice like only one brand or only one form
- hashed detail blobs are still deduped remotely, so merged releases do not lose the blob-sync efficiency improvements

Example production flow:

```bash
# 1. Build per-pair outputs for selected datasets
python3 scripts/build_all_final_dbs.py \
  --scan-dir scripts \
  --include-prefix Transparent_Labs \
  --include-prefix gummies \
  --per-pair-output-root /Users/seancheick/Documents/DataSetDsld/builds/pair_outputs

# 2. Assemble one combined release artifact
python3 scripts/assemble_final_db_release.py \
  --input-root /Users/seancheick/Documents/DataSetDsld/builds/pair_outputs \
  --output-dir /Users/seancheick/Documents/DataSetDsld/builds/release_output_2026-03-30T18-30-00

# 3. Dry-run the Supabase sync
python3 scripts/sync_to_supabase.py \
  /Users/seancheick/Documents/DataSetDsld/builds/release_output_2026-03-30T18-30-00 \
  --dry-run

# 4. Real sync
python3 scripts/sync_to_supabase.py \
  /Users/seancheick/Documents/DataSetDsld/builds/release_output_2026-03-30T18-30-00
```

So the flow is:

python3 scripts/build_all_final_dbs.py ...
python3 scripts/assemble_final_db_release.py ...
python3 scripts/sync_to_supabase.py ...
Or in one integrated step for build + assemble:

python3 scripts/build_all_final_dbs.py \
 --scan-dir scripts/products \
 --per-pair-output-root /path/to/pair_outputs \
 --assemble-release-output /path/to/release_output
Then:

python3 scripts/sync_to_supabase.py /path/to/release_output --dry-run
python3 scripts/sync_to_supabase.py /path/to/release_output --cleanup
Why:

the app should read one coherent release
Supabase sync rotates one active manifest/version at a time
unchanged pair outputs are reused during assembly
unchanged hashed detail blobs are skipped during upload when already present remotely

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

## 9. Valyu evidence watchtower

### What it is

A separate, review-only evidence discovery tool for curator workflows.

It helps scan:

- `backed_clinical_studies.json`
- `ingredient_quality_map.json` gaps
- `harmful_additives.json`
- `banned_recalled_ingredients.json`

It writes report files only. It does **not** change production source files and does **not** affect scoring directly.

### What it is not

- not part of `clean -> enrich -> score`
- not a canonical evidence writer
- not allowed to auto-apply updates

### Commands

Run one domain:

```bash
.venv/bin/python scripts/api_audit/valyu_evidence_discovery.py clinical-refresh
.venv/bin/python scripts/api_audit/valyu_evidence_discovery.py iqm-gap-scan
.venv/bin/python scripts/api_audit/valyu_evidence_discovery.py harmful-refresh
.venv/bin/python scripts/api_audit/valyu_evidence_discovery.py recall-refresh
```

Run all domains:

```bash
.venv/bin/python scripts/api_audit/valyu_evidence_discovery.py all
```

Optional target cap:

```bash
.venv/bin/python scripts/api_audit/valyu_evidence_discovery.py clinical-refresh --limit 10
```

Optional output dir override:

```bash
.venv/bin/python scripts/api_audit/valyu_evidence_discovery.py clinical-refresh \
  --output-dir /tmp/valyu-watchtower
```

### Outputs

Default report location:

- `scripts/api_audit/reports/valyu/`

Each run writes:

- `*-raw-search-report.json`
- `*-review-queue.json`
- `*-summary.md`

Use this tool to find review candidates, then manually promote approved findings into canonical source files through the normal audited workflow.

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
- `sync-brand`, `sync-filter`, and `sync-delta` now paginate through all matching results by default
- use `--limit N` only when you want to intentionally cap discovery for a test or partial run

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
- no `--limit` means fetch all matching labels across paginated API results
- `--limit N` means stop discovery after `N` labels
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
- no `--limit` means fetch all matching labels across paginated API results
- `--limit N` means stop discovery after `N` labels
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

**import-local** — Import local/manual DSLD raw JSON into the same canonical form/state/delta system:

Use this when the API is unavailable or when you downloaded raw JSON manually from DSLD and still want to update:

- `forms/`
- `state/dsld_sync_state.json`
- optional dated `delta/`
- optional JSON `reports/`

Example:

```bash
python3 scripts/dsld_api_sync.py import-local \
  --input-dir /Users/seancheick/Documents/DataSetDsld/manual/softgels_batch_01 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json \
  --delta-output-dir /Users/seancheick/Documents/DataSetDsld/delta/manual-softgels \
  --dated-delta \
  --report-dir /Users/seancheick/Documents/DataSetDsld/reports/manual-softgels
```

Important:

- `import-local` does not use the DSLD API
- it reads local JSON recursively, so both flat and nested folders work
- it routes labels into canonical form buckets using the same form logic as API sync
- it updates the same shared state file used by API sync
- it can produce a delta folder and report just like `sync-delta`
- API sync and local import stay independent operationally, but share the same canonical corpus/state model
- payload change detection ignores provenance-only fields like `_source` and `src`, so importing the same label from API vs manual raw files does not create false diffs by itself

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
  --raw-dir /Users/seancheick/Documents/DataSetDsld/staging/brands/Olly \
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

#### 2. First-time category/form seed without staging

This is the simpler default for form/category pulls.

Example: first-time gummies seed directly into the canonical form bucket:

```bash
python3 scripts/dsld_api_sync.py sync-filter \
  --supplement-form e0176 \
  --status 2 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json
```

Then run the pipeline directly on that canonical form bucket:

```bash
python3 scripts/run_pipeline.py \
  --raw-dir /Users/seancheick/Documents/DataSetDsld/forms/gummies \
  --output-prefix /Users/seancheick/Documents/DataSetDsld/output_gummies_seed
```

#### 2A. First-time category/form seed with staging

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

#### 2B. Form/category, second time or later

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

#### 3. Manual/local import fallback

Use this when the DSLD API is unavailable but you already downloaded raw DSLD JSON manually.

```bash
python3 scripts/dsld_api_sync.py import-local \
  --input-dir /Users/seancheick/Documents/DataSetDsld/manual/softgels_batch_01 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json \
  --delta-output-dir /Users/seancheick/Documents/DataSetDsld/delta/manual-softgels \
  --dated-delta \
  --report-dir /Users/seancheick/Documents/DataSetDsld/reports/manual-softgels
```

Then run pipeline on the printed dated delta folder:

```bash
python3 scripts/run_pipeline.py \
  --raw-dir /Users/seancheick/Documents/DataSetDsld/delta/manual-softgels/2026-03-30T01-49-58 \
  --output-prefix /Users/seancheick/Documents/DataSetDsld/output_manual_softgels_2026-03-30T01-49-58
```

#### 5. What to process after each kind of sync

- `sync-brand` with `--output-dir`:
  - process the `--output-dir` folder
- `sync-filter` with `--staging-dir`:
  - process the `--staging-dir` folder
- `sync-filter` with only `--canonical-root` and no staging folder:
  - process the specific canonical form bucket you just seeded, such as `/Users/seancheick/Documents/DataSetDsld/forms/gummies`
- `import-local` with `--delta-output-dir --dated-delta`:
  - process the printed `Delta directory:` dated folder
- `sync-delta` with `--delta-output-dir --dated-delta`:
  - process the printed `Delta directory:` dated folder
- `sync-brand` with only `--canonical-root` and no staging folder:
  - this updates the canonical corpus only
  - it does not create a clean brand-only pipeline input folder by itself

#### 6. How to read the result

- if a later `sync-delta` run prints `delta=0`, there were no new/changed labels for that run
- the dated delta folder for that run may still exist as an empty or near-empty audit artifact
- the JSON report in `--report-dir` is the clean place to check:
  - `new_count`
  - `changed_count`
  - `unchanged_count`
  - `failed_ids`
  - `off_market_ids`

### Batch runner with the new structure

`batch_run_all_datasets.sh` can still be useful, but it works best when you point it at a subtree that contains only flat dataset folders you actually want to process.

Recommended usage:

- top-level legacy folders only:
  - `bash batch_run_all_datasets.sh --targets Thorne,Olly`
- first-time brand seeds in staging:
  - `bash batch_run_all_datasets.sh --root "$HOME/Documents/DataSetDsld/staging/brands"`
- first-time form seeds in staging:
  - `bash batch_run_all_datasets.sh --root "$HOME/Documents/DataSetDsld/staging/forms"`
- one brand's dated delta runs:
  - `bash batch_run_all_datasets.sh --root "$HOME/Documents/DataSetDsld/delta/olly"`
- all brand delta roots is not recommended directly because `delta/` contains brand folders, not dated run folders

Important:

- when run at top-level `DataSetDsld/`, the script now skips:
  - `forms/`
  - `state/`
  - `delta/`
  - `reports/`
  - `staging/`
- that makes top-level usage safer for your old legacy flat dataset folders
- for the new workflow, `--root` is the clearer option

Examples:

Run all staged brand seeds:

```bash
bash batch_run_all_datasets.sh \
  --root "$HOME/Documents/DataSetDsld/staging/brands"
```

Run all dated Olly delta folders:

```bash
bash batch_run_all_datasets.sh \
  --root "$HOME/Documents/DataSetDsld/delta/olly"
```

Run only score for dated Olly deltas:

```bash
bash batch_run_all_datasets.sh \
  --root "$HOME/Documents/DataSetDsld/delta/olly" \
  --stages score
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

- `dsld_api_sync.py` now supports two ingestion paths:
  - API-driven sync via `sync-brand`, `sync-filter`, and `sync-delta`
  - local/manual raw import via `import-local`
- both paths normalize labels into the same raw-label contract and route them into the same canonical `forms/` corpus
- both paths update the same shared `state/dsld_sync_state.json`
- optional dated delta folders and JSON reports work for both `sync-delta` and `import-local`
- payload change detection ignores provenance-only fields like `_source` and `src`, so API vs manual copies of the same label do not create false diffs by themselves
- the pipeline processes the raw JSON the same way regardless of whether the files came from API sync or local import
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
