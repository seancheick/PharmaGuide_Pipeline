# Supabase Sync Pipeline

Uploads pipeline build output to Supabase for distribution to the Flutter app.

## Prerequisites

1. **Supabase Project:** Create at [supabase.com](https://supabase.com)
2. **Run Schema:** Copy `scripts/sql/supabase_schema.sql` into the Supabase SQL Editor and execute
3. **Create Storage Bucket:** In Supabase Dashboard > Storage, create bucket `pharmaguide` with public read access
4. **Environment Variables:** Add to your `.env` file:

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

### Version checking

The script compares the local `export_manifest.json` to the current Supabase manifest:
- If versions differ or no remote manifest exists: uploads everything
- If versions and checksums match: skips (already synced)

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

See `scripts/sql/supabase_schema.sql` for the complete schema including:
- `export_manifest` (pipeline version tracking)
- `user_stacks` (user supplement stacks)
- `user_usage` (freemium scan/AI limits)
- `pending_products` (user-submitted product requests)

Current remote user-data contract notes:
- `user_stacks` uses last-write-wins with tombstones for MVP (`deleted_at`, `client_updated_at`, `source_device_id`)
- `user_usage` resets on UTC day boundaries via `reset_day_utc`
- `pending_products` includes normalized UPC dedupe and review metadata

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

### Crash during sync (DB uploaded, blobs partially done, manifest not rotated)
This is safe. Supabase Storage has the new DB file but the manifest still points to the old version — the app won't see it. Re-run `sync_to_supabase.py` and it will re-upload the DB (upsert), retry all blobs, and then call `rotate_manifest`. No data is lost or corrupted.

### Version conflict
If the Supabase manifest shows a newer version than your local build, re-run the pipeline to generate a fresh build before syncing.
