# Supabase Sync Pipeline

Uploads pipeline build output to Supabase for distribution to the Flutter app.

## Prerequisites

1. **Supabase Project:** Create at [supabase.com](https://supabase.com)
2. **Run Pipeline Schema:** Copy `scripts/sql/supabase_schema.sql` into the Supabase SQL Editor and execute. It creates only pipeline distribution and release objects.
3. **Apply App Migrations:** Apply the versioned migrations in the Flutter repository's `supabase/migrations/` directory. Those migrations are the sole authority for user data, stack sync, usage storage, and pending-product requests.
4. **Create Storage Bucket:** In Supabase Dashboard > Storage, create bucket `pharmaguide` with public read access
5. **Environment Variables:** Add to your `.env` file:

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...your-service-role-key
```

Get these from Supabase Dashboard > Settings > API.

**IMPORTANT:** Use the **service role key** (not the anon key). The service role key bypasses RLS and is required for writing to the manifest table and storage bucket. Never commit this key to Git.

## Usage

### Run the full pipeline then sync

```bash
# 1. Run pipeline
python scripts/run_pipeline.py <dataset_dir>

# 2. Build Flutter export
python scripts/build_final_db.py \
  --enriched-dir output_Brand_enriched/enriched \
  --scored-dir output_Brand_scored/scored \
  --output-dir final_db_output

# 3. Sync to Supabase
python scripts/sync_to_supabase.py final_db_output
```

### Dry run (preview without uploading)

```bash
python scripts/sync_to_supabase.py <output_dir> --dry-run
```

### What gets uploaded

| Local File | Supabase Location |
|-----------|-------------------|
| `pharmaguide_core.db` | Storage: `pharmaguide/v{version}/pharmaguide_core.db` |
| `detail_index.json` | Storage: `pharmaguide/v{version}/detail_index.json` (compatibility/audit map; app can now prefer `products_core.detail_blob_sha256`) |
| `detail_blobs/*.json` | Storage: `pharmaguide/shared/details/sha256/{blob_sha256[0:2]}/{blob_sha256}.json` |
| `export_manifest.json` | PostgreSQL: `export_manifest` table (is_current=true) |
| `pharmaguide_core.db` → `products_core` | PostgreSQL: `catalog_search` rows (one per product per version) |

### Public catalog search table (`catalog_search`)

Before the manifest rotates (and on an already-current re-run), the sync reads the
release's `pharmaguide_core.db` with stdlib `sqlite3` and upserts one slim row per
product into `catalog_search` in batches of 500 (`on_conflict=catalog_version,dsld_id`),
then reads existing IDs with pagination and deletes products absent from this release
in bounded batches. Deletion starts only after every upsert succeeds; retries reconcile
an interrupted run. It retains this release and the actual current manifest version,
filling the two-version retention target with recent history when those are the same.
Readers use the `catalog_search_current` view (joined on `export_manifest.is_current`)
or the `search_catalog()` RPC. A **new version** becomes searchable when the manifest
flips. A same-version correction changes the current rows batch by batch, so readers
can temporarily see mixed old/new data. The public MCP reloads its index on the next
lookup once the local cache reaches 60 seconds; facts follow the refreshed index hash
and current catalog row. Mutable version-stamped DB, detail-index and share-index uploads
use a 60-second cache-control max-age, while SHA-addressed detail blobs retain their
one-year immutable policy. These are separate cache layers, not a 60-second end-to-end
freshness guarantee: CDN propagation can add delay, and historical long-lived cached
responses are not retroactively expired by changing the upload policy. Supabase's
[Smart CDN documentation](https://supabase.com/docs/guides/storage/cdn/smart-cdn)
states that update invalidation may take up to 60 seconds. Use a new release version
when an atomic catalog switch and fresh version-keyed caches are required. Keep one
publisher active: concurrent same-version writers are not transactionally isolated.
Only the service role can read the table; the app repo's public MCP edge function
(`supabase/functions/mcp-public`) is the consumer. Columns: `CATALOG_SEARCH_COLUMNS` in
`sync_to_supabase.py`; `upc_sku` is stored normalized like the app's barcode lookup.
`--dry-run` prints the row count without touching Supabase. **Apply section 9 of
`scripts/sql/supabase_schema.sql` (idempotent) before the first sync that includes this
step**: a missing table fails the step, and the manifest then does not rotate.

### Version checking

The script compares the local `export_manifest.json` to the current Supabase manifest:
- If versions differ or no remote manifest exists: uploads everything
- If versions and checksums match: refreshes share-index shards and search rows without rotating the manifest

## Client-side safety expectations

The Flutter client should not promote a downloaded DB artifact just because it exists remotely.
Required client behavior:
- download the new DB to a staging path
- use a native/background downloader for large DB artifacts so the OS can complete the transfer if the app is backgrounded
- verify it against the remote `export_manifest.json` checksum
- respect `min_app_version` as a hard compatibility gate
- atomically swap in only after checksum + open/readability validation pass
- never overwrite `user_data.db` or any app-local user tables during the swap
- keep using the previous known-good DB if any step fails

## Supabase Schema

See `scripts/sql/supabase_schema.sql` for pipeline-owned schema including:
- `export_manifest` (pipeline version tracking)
- `catalog_releases` (release state and artifact provenance)

The Flutter repository's `supabase/migrations/` directory owns the app-data contract:
- `user_stacks` uses last-write-wins with tombstones (`deleted_at`, `client_updated_at`, `source_device_id`)
- `user_usage` resets on UTC day boundaries via `reset_day_utc`
- `pending_products` includes normalized UPC dedupe and review metadata

For an existing production project, apply named incremental migrations from
each owner rather than treating this bootstrap file as an upgrade mechanism:
- pipeline distribution migrations: `scripts/sql/migrations/`
- Flutter app-data migrations: `supabase/migrations/`

Each migration must be recorded through the Supabase migration mechanism after
the preflight checks pass. Do not use a blind `supabase db push` against this
project until its legacy migration history has been reconciled.

Sync decision logic:
- push when `db_version` changes
- push when checksum changes even if `db_version` did not
- use `--force` for controlled repushes
- RLS policies and indexes

## Troubleshooting

### "SUPABASE_URL environment variable is not set"
Add `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` to your `.env` file.

### "export_manifest.json not found"
Run `build_final_db.py` before `sync_to_supabase.py`.

### Partial upload (some blobs failed)
Re-run `sync_to_supabase.py`. It uses upsert mode -- re-uploading is safe and idempotent. Failed blobs will be retried.

### Crash during a new-version sync (DB uploaded, blobs partially done, manifest not rotated)
This is safe. Supabase Storage has the new DB file but the manifest still points to the old version — the app won't see it. Re-run `sync_to_supabase.py` and it will re-upload the DB (upsert), retry all blobs, and then call `rotate_manifest`. No data is lost or corrupted.

### Version conflict
If the Supabase manifest shows a newer version than your local build, re-run the pipeline to generate a fresh build before syncing.
