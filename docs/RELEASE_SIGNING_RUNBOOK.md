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

## The safety-alert feed

The alert feed uses the same signing: the same text form, the same signature format, the same
`sign` key file rules and the same app check. What differs is what gets signed and where its key
is pinned.

**What is signed.** A short statement that names the base feed, the extended feed if there is one,
and a sequence. It is detached, and it travels inside the release row's `manifest` as `signed_feed`.
The feed bytes, `feed_path` and `checksum` don't change, so builds already on phones read exactly
what they read before.

**Why it has its own key.** A key in `production_keys` makes every catalog publish signed-only, and a
key in the app's release list starts keyed catalog behaviour, which is held until A9 finishes. The
feed can't wait for that and must not cause it. So its keys go in `alert_feed_keys` and
`_kProductionAlertFeedKeys`. It also keeps recalls moving if the catalog key is ever lost.

Sean alone holds this key, under the same custody rules as above.

### What happens with no key

| Situation | Result |
|---|---|
| Publisher, nothing in `alert_feed_keys` | Refuses every feed, before any remote step |
| Publisher, unsigned feed, or signed by any key not pinned there | Refuses, before any remote step |
| New build, no key in `_kProductionAlertFeedKeys` | Verifies nothing: no alert from the feed and no all-clear, even for a correct feed |
| New build, missing or bad signature, with a good saved copy | Keeps the copy, not a complete check |
| New build, missing or bad signature, never verified a feed | No alerts and no all-clear |
| New build, a saved copy nothing vouches for (from an older build, or its key was removed) | Keeps its alerts, gives no all-clear, and the first verified fetch replaces it |
| Builds already on phones | Unchanged. They don't read the signature, so they also get no protection from it |

**This differs from the catalog on purpose.** A catalog publish may stay unsigned until the first
key is pinned, because phones were already taking unsigned catalogs and need them to keep working.
No alert release has ever been published, so there is nothing to keep working, and Sean decided the
feed is signed from its first publish. A keyless new build also fails closed where a keyless catalog
build ignores signed fields, because trusting an unverified feed would let it give an all-clear.

`make build-ios` and `make build-android` refuse a store build with no key, because that build could
never verify a feed and could only be fixed by an app update. `PHARMAGUIDE_IOS_DISTRIBUTION=testflight`
is allowed, for testing before the key exists.

### Generate the keys

Run this on the custody machine. It makes the working key and a standby, and asks for a passphrase for
each. Only the public hex it prints may leave the machine. Keep one offline backup of both private keys.

```bash
source scripts/python_env.sh   # run from the repo
mkdir -p ~/alert-feed-custody && cd ~/alert-feed-custody
umask 077
for KEY_NAME in alert-feed-2026-11 alert-feed-standby; do
KEY_NAME="$KEY_NAME" "$PG_PYTHON" - <<'PY'
import getpass, os
from pathlib import Path
from cryptography.hazmat.primitives import serialization as s
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
name = os.environ["KEY_NAME"]
key = Ed25519PrivateKey.generate()
passphrase = getpass.getpass(f"New passphrase for {name}: ").encode()
Path(f"{name}.pem").write_bytes(key.private_bytes(
    s.Encoding.PEM, s.PrivateFormat.PKCS8, s.BestAvailableEncryption(passphrase)))
public = key.public_key().public_bytes(s.Encoding.Raw, s.PublicFormat.Raw).hex()
print(f"{name} public key (hex): {public}")
PY
done
```

The custody directory must stay outside every repo. `sign-alert-feed` refuses a key inside this one, and
a key file anyone but its owner can read.

### Pin the public keys

1. **Pipeline.** In `scripts/config/release_trust.json`, set the working key only, and merge it:

   ```json
   "alert_feed_keys": {"alert-feed-2026-11": "<public hex>"}
   ```

   This changes nothing for the catalog.
2. **App.** In `lib/services/release_manifest.dart`, set both keys, and merge it:

   ```dart
   const Map<String, String> _kProductionAlertFeedKeys = {
     'alert-feed-2026-11': '<public hex>',
     'alert-feed-standby': '<public hex>',
   };
   ```

3. Ship that app build. The first signed publish can come before or after it: older builds read the
   feed either way, and a keyed build with no release yet behaves as it does today.

### Sign and publish a feed

1. Stage it. This stops at the signature, with the feed ready in `scripts/dist`:

   ```bash
   bash scripts/run_safety_alert_publish.sh   # stops: "this feed must be signed"
   ```

2. Pick the next sequence. The first is 1, and it never goes back:

   ```sql
   select manifest->'signed_feed'->>'statement' from safety_alert_releases where is_current;
   ```

3. Write the text to sign. This needs no key and no Supabase credential:

   ```bash
   "$PG_PYTHON" scripts/sync_safety_alerts.py --build-statement --sequence 1 --key-id alert-feed-2026-11
   ```

4. Move `scripts/dist/safety_alerts_release.json` to the custody machine and sign it. Don't edit it:

   ```bash
   "$PG_PYTHON" scripts/release_manifest.py sign-alert-feed \
     --statement safety_alerts_release.json \
     --key-file ~/alert-feed-custody/alert-feed-2026-11.pem \
     --output safety_alerts_release.sig
   ```

5. Move `safety_alerts_release.sig` back to `scripts/dist` and dry-run. This checks the signature against
   the pinned key, and that it names these exact bytes:

   ```bash
   "$PG_PYTHON" scripts/sync_safety_alerts.py --dry-run
   ```

6. Publish:

   ```bash
   bash scripts/run_safety_alert_publish.sh
   ```

The feed carries the date it was staged, so the runner makes different bytes on a later day, and the
publisher refuses the old signature ("does not name this feed"). Go back to step 3 with a new sequence.

To publish a feed already staged elsewhere, such as a reviewed candidate, skip the runner, which would
stage again, and pass `--dist-dir DIR` to each `sync_safety_alerts.py` command.

Re-running the same signed feed is safe. Publishing earlier bytes again, to undo a release, also works:
it takes a new sequence and a new signature, and the publisher writes them onto the earlier row. Publishing
takes the same dispatch secret as before.

To rehearse on a test project, add `--test-project` to the publish command. It takes a key under `test_keys`
and a host under `test_hosts`, and can't reach production. A debug build trusts that key through
`PHARMAGUIDE_RELEASE_TEST_KEY_ID` and `PHARMAGUIDE_RELEASE_TEST_KEY`; release mode ignores both.

### Rotate the alert key

1. Generate the next key, or use the standby.
2. Ship its public key in an app release, alongside the current one.
3. Wait until every supported build carries it. A build without it treats the new signature as bad: it
   keeps its saved copy and gives no all-clear.
4. Add it to `alert_feed_keys`, and sign with it. Keep sequences rising across the switch.
5. Remove the old key from `alert_feed_keys`, then from the app in a later release. A saved copy signed
   only by a removed key keeps its alerts, and gives no all-clear until the next verified fetch.

Pin the next key in the app before you need it. There's no remote way to add or revoke a key.

### If the alert key is lost or exposed

**Lost.** Switch to the standby: add its public key to `alert_feed_keys` and sign with it. It works at
once on every build that shipped with it. Without a standby, generate a new key and ship it in an app
release. **Until phones have it, keyed builds get no new alert**: they keep their saved copy and give no
all-clear. Older builds keep receiving the feed. This is the real cost of signing a recall channel, and
it's why the standby is in the first step.

**Exposed.** Treat this as an incident, as for the release key. An attack also needs write access to
Supabase, so rotate the service role key first. Switch to the standby if it is still safe and remove the
exposed key in an expedited app release. If a forged release went out, publish a correct one with a
sequence above it. A forged sequence too high to beat can only be recovered with an app release.

### What this does not prove

- A signature says Sean approved this feed. It doesn't say the content is clinically correct.
- It can't prove a release is the latest. Someone who can write to Supabase can hold phones on the last
  genuine release, or remove it. Phones then see an older copy, not a false one.
- A phone remembers the highest sequence only in its saved copy, so reinstalling resets it.
- Builds from before this change don't check. They are protected only by Supabase access control.

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
   The alert feed still reaches them, because it has its own key.

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
doesn't reset the comparison. Rules the newest release blocks don't count, so a rule carried
over from a blocked file still needs its review. Before any are published, pass
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
