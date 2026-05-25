# Release hygiene validation — 2026-05-25

Scope: read-only validation. No Supabase cleanup, quarantine, delete, or
manifest mutation was executed.

## Artifact parity

Local catalog artifacts all match:

| Location | Version | Product count | SHA-256 |
|---|---|---:|---|
| `scripts/dist/pharmaguide_core.db` | `2026.05.25.184400` | 8,951 | `02331e72a47117c0d9ac4d2f3c80b7870af307876f6568d5787bd99558a8195e` |
| `scripts/final_db_output/pharmaguide_core.db` | `2026.05.25.184400` | 8,951 | `02331e72a47117c0d9ac4d2f3c80b7870af307876f6568d5787bd99558a8195e` |
| `/Users/seancheick/PharmaGuide ai/assets/db/pharmaguide_core.db` | `2026.05.25.184400` | 8,951 | `02331e72a47117c0d9ac4d2f3c80b7870af307876f6568d5787bd99558a8195e` |

Flutter git state:

- `main` local HEAD equals `origin/main`.
- Current Flutter commit: `e25f87229d7ba5077b28bdd962c31d97f842614b`
  (`chore(catalog): bundle catalog v2026.05.25.184400 + interaction v1.0.0`).

## Release-safety protected-set prerequisites

Read-only protected-set computation:

| Check | Result |
|---|---|
| Bundle alignment | PASS |
| Bundled version | `2026.05.25.184400` |
| Dist version | `2026.05.25.184400` |
| Protected set degenerate | `False` |
| Bundled detail blob count | 8,951 |
| Dist detail blob count | 8,951 |
| Bundled∩dist intersection | 8,951 |
| Bundled∪dist union | 8,951 |

This means the prior orphan-cleanup rejection caused by an uncommitted Flutter
bundle is resolved.

## Supabase manifest state

Read-only `export_manifest` query:

| Version | Current | Created at |
|---|---|---|
| `2026.05.25.184400` | true | `2026-05-25T18:51:37.21117+00:00` |
| `2026.05.25.163900` | false | `2026-05-25T16:47:31.184767+00:00` |

Dry-run version cleanup with `--keep 2 --cleanup-db` reports nothing to
delete because only two manifest versions exist.

## Orphan-blob cleanup status

No destructive orphan cleanup was run.

Attempted the read-only storage audit:

```bash
PYTHONPATH=scripts python3 -m release_safety.storage_audit \
  --flutter-repo "/Users/seancheick/PharmaGuide ai" \
  --dist-dir scripts/dist \
  --json
```

The audit was intentionally stopped after a long remote walk with no completed
result. The cheaper release-safety prerequisites above still prove that the
bundle-alignment/protected-set gate inputs are now healthy; they do not prove
the current orphan count.

Before any future destructive orphan cleanup, run one of:

- `bash scripts/release_full.sh` and let the built-in cleanup gate decide.
- Or a dedicated storage audit with `--progress` in a long-running terminal to
  obtain the exact orphan count first.

## Important caveat

The dsld_clean repo now has a post-release commit:

- `61c4d8ce fix(enrichment): mark omega source oil rows as parent totals`

So `2026.05.25.184400` is internally consistent and shipped correctly, but it
does **not** include the omega parent-total slice. A future corpus rerun/release
is needed before that code affects shipped catalog rows.
