# Release hygiene validation - 2026-05-25

Scope: read-only validation. No Supabase cleanup, quarantine, delete, or
manifest mutation was executed.

## Artifact parity

Local catalog artifacts all match:

| Location | Version | Product count | SHA-256 |
|---|---|---:|---|
| `scripts/dist/pharmaguide_core.db` | `2026.05.25.184400` | 8,951 | `02331e72a47117c0d9ac4d2f3c80b7870af307876f6568d5787bd99558a8195e` |
| `scripts/final_db_output/pharmaguide_core.db` | `2026.05.25.184400` | 8,951 | `02331e72a47117c0d9ac4d2f3c80b7870af307876f6568d5787bd99558a8195e` |
| `/Users/seancheick/PharmaGuide ai/assets/db/pharmaguide_core.db` | `2026.05.25.184400` | 8,951 | `02331e72a47117c0d9ac4d2f3c80b7870af307876f6568d5787bd99558a8195e` |

Manifest parity also matches across the same three locations:

| Manifest | db_version | product_count | checksum_sha256 |
|---|---|---:|---|
| `scripts/dist/export_manifest.json` | `2026.05.25.184400` | 8,951 | `02331e72a47117c0d9ac4d2f3c80b7870af307876f6568d5787bd99558a8195e` |
| `scripts/final_db_output/export_manifest.json` | `2026.05.25.184400` | 8,951 | `02331e72a47117c0d9ac4d2f3c80b7870af307876f6568d5787bd99558a8195e` |
| `/Users/seancheick/PharmaGuide ai/assets/db/export_manifest.json` | `2026.05.25.184400` | 8,951 | `02331e72a47117c0d9ac4d2f3c80b7870af307876f6568d5787bd99558a8195e` |

Flutter git state:

- `main` local HEAD equals `origin/main`.
- Current Flutter commit: `e25f87229d7ba5077b28bdd962c31d97f842614b`
  (`chore(catalog): bundle catalog v2026.05.25.184400 + interaction v1.0.0`).

## Supabase manifest state

Read-only `export_manifest` query:

| Version | Current | Created at | Product count | Checksum |
|---|---|---|---:|---|
| `2026.05.25.184400` | true | `2026-05-25T18:51:37.21117+00:00` | 8,951 | `sha256:02331e72a47117c0d9ac4d2f3c80b7870af307876f6568d5787bd99558a8195e` |
| `2026.05.25.163900` | false | `2026-05-25T16:47:31.184767+00:00` | 8,949 | `sha256:6eb9c8fcb2b1ccce23110da31c89eeb4413f7853ca60bf54967e122d700ed71c` |

Read-only `catalog_releases` ACTIVE/VALIDATING query:

| Version | State | detail_index_url | Activated at |
|---|---|---|---|
| `2026.05.25.184400` | ACTIVE | `v2026.05.25.184400/detail_index.json` | `2026-05-25T18:51:37.368011+00:00` |

## Release-safety protected-set prerequisites

Read-only protected-set computation:

| Check | Result |
|---|---|
| Bundle alignment | PASS |
| Bundled version | `2026.05.25.184400` |
| Dist version | `2026.05.25.184400` |
| Registry protected versions | `2026.05.25.184400` |
| Protected set degenerate | `False` |
| Bundled detail blob count | 8,951 |
| Dist detail blob count | 8,951 |
| Bundled/detail intersection | 8,951 |
| Bundled/detail union | 8,951 |
| Protected blob count | 8,951 |

This means the prior orphan-cleanup rejection caused by an uncommitted Flutter
bundle is resolved.

## Cleanup dry run

Dry-run version cleanup:

```bash
python3 scripts/cleanup_old_versions.py --keep 2 --cleanup-db
```

Result:

- 2 `export_manifest` versions exist.
- Both are inside the keep window.
- Nothing would be deleted.

## Orphan-blob cleanup status

No destructive orphan cleanup was run.

The protected-set prerequisites are now healthy enough for the built-in
release cleanup gate to evaluate on a future release. This validation does
not quarantine or delete orphan blobs, and it does not compute a fresh orphan
count by walking all Supabase storage objects.

Before any future destructive orphan cleanup, run one of:

- `bash scripts/release_full.sh` and let the built-in cleanup gate decide.
- Or a dedicated read-only storage audit with progress enabled:

```bash
PYTHONPATH=scripts python3 -m release_safety.storage_audit \
  --flutter-repo "/Users/seancheick/PharmaGuide ai" \
  --dist-dir scripts/dist \
  --progress \
  --json
```

## Important caveat

The shipped catalog `2026.05.25.184400` is internally consistent across
Supabase, `scripts/dist`, `scripts/final_db_output`, and Flutter. It does not
include dsld_clean commits made after that release, including:

- `61c4d8ce` omega parent-total source-oil handling
- `a1426de7`, `437a468a`, `e0a78fb7` UNII audit reports/specs
- `5e9ed28a`, `3895c2de`, `23d7e56a` P0 UNII model fixes

A future corpus rerun/release is needed before those code/data changes affect
the shipped catalog.
