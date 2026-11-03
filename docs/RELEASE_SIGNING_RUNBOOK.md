# Release signing runbook

This is the procedure ADR-012 requires before the first signed release. The tool is
`scripts/release_manifest.py`. The contract is in `scripts/SUPABASE_SYNC_README.md`.

A signature proves who published a release. It does not prove the content is clinically
correct. The A9 review stays separate.

## Who holds the key

- **Sean is the accountable custodian.** He decides who may sign, and he answers for every
  signature.
- The private key lives in a protected runner or in hardware-backed custody. It never lives
  in a repo, a `.env` file, Supabase, chat, a log or a CI variable that other jobs can read.
- `sign` reads a PEM file only. For hardware custody, keep the key's passphrase in the
  hardware-backed store and enter it when `sign` asks. Signing directly on a hardware device
  needs a new signing path, which does not exist yet.
- Signing needs no Supabase credential. Publishing needs no private key. Keep the two apart,
  ideally on different machines.
- `sign` refuses a key inside the repo, and a key file that anyone but its owner can read.

## Generate a key

Run this outside any repo, on the machine that will hold the key. It asks for a passphrase.

```bash
source scripts/python_env.sh   # run from the repo, then cd to the custody directory
umask 077
"$PG_PYTHON" - <<'PY'
import getpass
from pathlib import Path
from cryptography.hazmat.primitives import serialization as s
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
key = Ed25519PrivateKey.generate()
passphrase = getpass.getpass("New key passphrase: ").encode()
Path("release-key.pem").write_bytes(key.private_bytes(
    s.Encoding.PEM, s.PrivateFormat.PKCS8, s.BestAvailableEncryption(passphrase)))
public = key.public_key()
Path("release-key.pub.pem").write_bytes(public.public_bytes(
    s.Encoding.PEM, s.PublicFormat.SubjectPublicKeyInfo))
print("App public key (hex):", public.public_bytes(s.Encoding.Raw, s.PublicFormat.Raw).hex())
PY
```

Pick a key ID such as `release-2026-11`. It may use letters, digits, `.`, `_` and `-`. The
public key and its ID go in the app and in `scripts/config/release_trust.json`. Only the public key may leave the custody machine.
Make one offline backup of the private key, held under the same protections.

## Publish a signed release

1. Pick the next sequence. It must be higher than the current row's `release_sequence`, and
   it never goes back. Re-publishing good data still takes a new sequence.
2. Build the manifest:

   ```bash
   python scripts/release_manifest.py build --catalog-dir scripts/dist \
     --sequence 12 --min-rules-version 1.0.15 --key-id release-2026-11 \
     --output release.json
   ```

   Add `--rules-dir DIR` only to publish rules. Leave it out for a catalog-only release, which
   keeps the phone's current rules if they meet `--min-rules-version`.
3. Move `release.json` to the custody machine and sign it:

   ```bash
   python scripts/release_manifest.py sign --manifest release.json \
     --key-file /custody/release-key.pem --output release.sig
   ```

4. Move `release.json` and `release.sig` back. Don't edit them. Any edit breaks the signature.
5. Dry-run. `sync` verifies the signature against the key pinned for this destination in
   `scripts/config/release_trust.json`, before anything else:

   ```bash
   python scripts/sync_to_supabase.py scripts/dist --dry-run \
     --release-manifest release.json --release-signature release.sig
   ```

6. Publish. The usual way is the same release command, which stops before its sync step
   once a production key is pinned, with the build ready to sign:

   ```bash
   bash scripts/release_full.sh                    # stops: "This release must be signed"
   # steps 2-4 above, on the build it left in scripts/dist
   bash scripts/release_full.sh --release-manifest release.json --release-signature release.sig
   ```

   Add `--release-rules-dir DIR` when the manifest names rules. The rerun finds every earlier
   step up to date. If the build changed, `sync` refuses, because the manifest no longer
   matches it. Before its first Storage write `sync` also checks the catalog version and hash
   against the build, the rules file's hash, the rules gate, the deployed RPC arguments and
   the sequence.

An unsigned publish is refused as soon as `production_keys` names any key, by `sync` itself,
so no caller can skip it. Until then no keyed build can exist, so unsigned catalog-only
releases still work.

## Order of first use

1. Deploy the app repo's migration that adds the columns and RPC arguments.
2. Pin the public key in `scripts/config/release_trust.json` `production_keys`, and merge it.
   From this commit every publish must be signed. Builds with no keys ignore the signed
   fields, so nothing changes for them.
3. Ship the first keyed app build, with the same key.

Don't reverse this. A keyed build refuses any unsigned row, so a keyed build shipped before
signing starts gets no catalog updates. After step 3, **every** publish must be signed.

The current RPC refuses a `db_version` it has already seen. Unless the deployed migration
allows that for a signed release, the first signed release needs a fresh catalog build, and a
rules-only release can't be published.

## Remote rules gate

`scripts/config/remote_rules_gate.json` holds rules off production. `sync` refuses a manifest
that names rules until `a9_review_complete` is `true` and `signed_off_by` and `signed_off_at`
are filled in. Only Sean records that sign-off, after A9 finishes. Public builds also carry no
key until then, so two separate locks hold.

To test rules on a test project, pass `--test-project`. `sync` refuses unless the host in
`SUPABASE_URL` is listed under `test_hosts` in `scripts/config/release_trust.json`, and it
refuses the project named by `production_project_ref` even if that list ever names it. The
environment can't prove where it points, so adding a test project takes a reviewed commit. A
test release is signed with a key under `test_keys`, and that key can't publish to production.

## Rotate the key

1. Generate the next key with a new key ID.
2. Ship its public key in an app release, alongside the current one.
3. Wait until every supported build carries it. Builds without it can't verify the new key.
4. Switch signing to the new key.
5. Remove the old public key in a later app release.

## If the key is lost

Nothing already published is affected. No new signed release can be made until a new key
reaches phones.

1. Restore from the offline backup if there is one.
2. If not, generate a new key and ship it in an app release. If the app's bundled next key has
   a private copy, switch to that one instead.
3. Builds holding only the lost key stay on their last release until they update the app.
   The alert feed still reaches them, because it doesn't use this key.

## If the key is exposed

Treat this as an incident. Whoever holds the key can sign a release that phones will accept,
provided they can also write to Supabase. Sean decides and acts the same day.

1. Stop publishing and rotate the Supabase service role key, since an attack needs both.
2. Check `export_manifest` and Storage for releases you didn't publish. Compare each sequence
   and hash with your own records.
3. Generate a new key and switch signing to the app's next key if it is still safe.
   Otherwise ship a new key in an expedited app release, and remove the exposed public key.
4. If a bad release was published, roll back as below, with a sequence above the attacker's.
   The app refuses anything lower than the highest it has verified. If the forged sequence
   is too high to beat, phones that took it can only recover through an app release.
5. Record what happened in the ADR log.

The current design has no way to revoke a key remotely. Removing it takes an app release.

## Roll back a bad catalog

You need the known-good build directory on disk, with its `detail_blobs`. Without it, rebuild
from source instead. Say `2026.11.02.090000` is the bad catalog and the current sequence is 12.

1. Make a new build dir from the known-good one:

   ```bash
   python scripts/release_manifest.py prepare-rollback \
     --source-dir /builds/known-good --output-dir /builds/rollback \
     --newer-than 2026.11.02.090000
   ```

   This copies the catalog and stamps a fresher `db_version` into its `export_manifest` table.
   It writes a matching `export_manifest.json` with new checksums. Product rows don't change,
   except that an image path naming the source version moves to the new one. Detail blobs and
   image files are linked to the source, so keep the source in place until the sync finishes.
2. Build with a newer sequence and block the bad version:

   ```bash
   python scripts/release_manifest.py build --catalog-dir /builds/rollback \
     --sequence 13 --min-rules-version 1.0.15 --key-id release-2026-11 \
     --block-catalog 2026.11.02.090000 --output release.json
   ```

3. Sign, verify and dry-run as in "Publish a signed release".
4. Sync. Don't pass `--submission-output-dir` or `--cleanup`:

   ```bash
   python scripts/sync_to_supabase.py /builds/rollback \
     --release-manifest release.json --release-signature release.sig
   ```

To replace bad rules, add `--rules-dir` with the known-good rules, `--block-rules` with the bad
version, and a `--min-rules-version` at or below the known-good version. The rules gate applies.
`prepare-rollback` does not re-stamp a rules file. It stays at its own version.

Sync runs `scripts/rule_change_gate.py` on any signed release that names rules, comparing with the
rules the newest signed release that named any names, so a catalog-only release in between
doesn't reset the comparison. Before any are published, pass
`--rule-pin <app repo>/tool/interaction_db.release.json`; `release_full.sh` does this for you.

**What a rules-only release can't change.** On a schema 2 catalog the product page's pregnancy and
condition wording is inline in each detail blob, and the app reads `profile_warning_rules` only for
schema 3 blobs. A correction to that wording, published as rules only, looks published and changes
nothing. Ship it in a signed catalog release, which needs no app update either. Proved on a simulator
on 2026-11-03; see ADR-012.

### What each build does

| Build | Catalog | Rules | `blocked_versions` |
|---|---|---|---|
| Keyed (ADR-012 design, not shipped yet) | Compares sequence, verifies the signature, installs the rollback | Uses the named rules, or keeps its own if they meet the pair rule | Applied: a blocked version isn't kept or selected again |
| No keys (today's public builds) | Compares `db_version`, sees a newer one, installs the rollback | Unchanged; rules ship only with the app | Ignored |

### Limits

- Older builds need the fresher `db_version`, and a stamped file has a new hash. So every phone
  downloads the whole catalog again, even one that never took the bad release.
- A phone that stays offline keeps what it has until it next connects.
- Bad rules on a build with no keys can only be fixed by an app release. Use the alert feed for
  an individual clinical risk in the meantime.
- Detail blobs named by the old catalog must exist in Storage. `sync` uploads any that are
  missing from the linked `detail_blobs`, which is why the source directory is required.
- Products added by the bad catalog disappear, including approved submissions promoted in it.
  Check those by hand, because their submissions still point at the bad version.
- The app's bundled catalog is untouched. Re-run the normal bundle step before the next app
  release, so that build doesn't carry the bad catalog.
