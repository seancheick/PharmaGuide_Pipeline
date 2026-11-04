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
| `pharmaguide_core.db.gz`, `pharmaguide_core.db.gz.json` | Storage: the same folder. The gzip of that catalog and its descriptor; see **Compressed catalog** below |
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

### Signed release manifest (ADR-012)

Optional. With `--release-manifest` and `--release-signature`, the sync also publishes a signed
release. Without them, the sync and its RPC payload are unchanged. The procedure, key custody
and rollback are in [`docs/RELEASE_SIGNING_RUNBOOK.md`](../docs/RELEASE_SIGNING_RUNBOOK.md).
`scripts/release_manifest.py` owns this contract, and the Flutter app parses it exactly.

`signed_release` is this text, signed as UTF-8 bytes with Ed25519:
`json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`.
`release_signature` is `<key_id>:<standard base64 of the 64-byte signature>`.

```
{
 "format": 1,
 "key_id": "<same key id>",
 "release_sequence": <positive int>,
 "catalog": {"version": "<db_version>", "path": "v<db_version>/pharmaguide_core.db", "sha256": "<hex no prefix>", "schema_version": "...", "min_app_version": "..."},
 "rules": {"version": "...", "path": "rules/<version>/interaction_db.sqlite", "sha256": "<hex no prefix>", "schema_version": "...", "min_app_version": "..."} or null for a catalog-only release,
 "min_rules_version": "<semver>",
 "blocked_versions": {"catalog": [<db_version>...], "rules": [<rules version>...]}
}
```

| Storage or table | Added by a signed release |
|---|---|
| Storage: `pharmaguide/rules/{version}/interaction_db.sqlite` | Create-only, before the manifest flip. Existing bytes must match. `--rules-dir` names the local directory (default: the build dir) |
| `export_manifest.release_sequence` (bigint) | Monotonic, separate from content versions, enforced by the RPC |
| `export_manifest.signed_release` (text) | The exact signed text. Rules fields live only here |
| `export_manifest.release_signature` (text) | The signature |

The RPC `rotate_manifest_with_submission_approvals` takes `p_release_sequence`,
`p_signed_release` and `p_release_signature`, all defaulting to NULL. The app repo's migration
owns the RPC; `scripts/sql/supabase_schema.sql` only mirrors the columns. `--preflight-only`
checks the unsigned contract. A signed sync checks the three new arguments before its first
Storage write, so the publisher keeps working before that migration deploys.

An unsigned sync is refused once `release_trust.json` pins a production key. Before any Storage write, a signed sync refuses:

- a manifest that isn't canonical or doesn't match the contract;
- a catalog version, hash, schema or minimum app version that differs from the build;
- a rules file whose hash differs from the manifest;
- a signature that doesn't verify against the key pinned for this destination in
  `scripts/config/release_trust.json`, or a key that isn't pinned there;
- rules while `scripts/config/remote_rules_gate.json` records no A9 sign-off, unless
  `--test-project` is passed and the `SUPABASE_URL` host is listed in `test_hosts` there;
- a sequence below the current row's, or equal to it with different content;
- a deployed RPC without the new arguments.

A signed release on the current catalog still rotates, because its sequence is new. Re-running
the same signed release does not. The RPC currently refuses any repeated `db_version`, so this
path needs a migration that allows it.

### Compressed catalog

Every sync publishes the catalog twice in `v{version}/`: the plain file and its gzip, about one eighth the size. There is no second update path. The manifest row, the version and the checksum all stay as they were, and what activates on a phone must hash to that checksum either way.

- **Keep publishing the plain file.** Every build before compression fetches only `pharmaguide_core.db`, and it has no other route to a catalog. Removing it strands those builds, so it stays until no supported build lacks the gzip reader.
- **`pharmaguide_core.db.gz`** is `application/gzip` with no `Content-Encoding`, so no client unpacks it in transit and Range requests count compressed bytes. Its bytes don't depend on the time or the folder it was built in.
- **`pharmaguide_core.db.gz.json`** is for builds with no release keys, which can't read signed fields. It holds `format`, `version`, `path`, `sha256`, `size`, `decompressed_sha256` and `decompressed_size`. It vouches for nothing: the app uses it only if `version` and `decompressed_sha256` match its manifest row. It is uploaded after the gzip, so a phone that can see it finds the file it names.
- **Signed releases** carry the same facts as `catalog.compressed`, with `path`, `sha256`, `size` and `decompressed_size`. `format` stays 1, and older keyed builds ignore the key. A release signed before compression stays valid.
- **On the phone:** if the gzip can't deliver (its hash is wrong, it won't unpack to the catalog, or it's missing), the app falls back to the plain file. A network or disk failure does neither: the partial is kept and the next check resumes it.

### Product images

`products_core.image_thumbnail_url` holds `product-images/<object path>`, and every app build reads that path the same way. New catalogs use `sha256/<first two hex>/<sha256 of the image>.webp`, written by `extract_product_images.py` and the submission image import.

- **Only hash-named objects get the one-year cache.** The name can't come to mean anything else, and a corrected picture gets a new name. They're create-only, and products with identical pictures share one object.
- **Older paths keep resolving, so they are never deleted.** The bundled catalog points at root names such as `1024.webp`, and earlier catalogs may point at `v<version>/`. Those keep the storage default (`no-cache`), and no code removes anything from this bucket.
- **Sync refuses a catalog that would show the wrong picture.** Before any write, each row with an index entry must name that entry's object, and a row naming a hash must have an entry. Each image's bytes must then hash to its own path. A rollback keeps hash-named paths, and moves only version-folder paths.
- **An image already uploaded** is recognized by its name and size, so a run doesn't download thousands of images to re-check them.

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
