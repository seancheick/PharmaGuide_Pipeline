#!/usr/bin/env python3
"""Build, sign, verify and roll back the signed release manifest (ADR-012).

The manifest is the exact text the app verifies, so its bytes are the contract:
``json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)``,
signed as UTF-8 with Ed25519. ``release_signature`` is
``<key_id>:<standard base64 of the 64-byte signature>``.

Signing needs no Supabase credential and runs apart from publishing. The steps
and the key custody rules are in docs/RELEASE_SIGNING_RUNBOOK.md.

    python scripts/release_manifest.py build --catalog-dir DIR [--rules-dir DIR] \\
        --sequence N --min-rules-version X.Y.Z --key-id ID --output release.json
    python scripts/release_manifest.py sign --manifest release.json \\
        --key-file /outside/the/repo/key.pem --output release.sig
    python scripts/release_manifest.py verify --manifest release.json \\
        --signature release.sig --public-key key.pub.pem
    python scripts/release_manifest.py prepare-rollback --source-dir GOOD --output-dir NEW
    python scripts/release_manifest.py sign-alert-feed --statement safety_alerts_release.json \\
        --key-file /outside/the/repo/key.pem --output safety_alerts_release.sig

The safety-alert feed uses the same canonical text, signature format and key file
rules. Its statement is a different document, and its keys are pinned apart.
"""

import argparse
import base64
import getpass
import json
import os
import re
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from release_interaction_artifact import compute_sha256, strip_sha256_prefix
from supabase_client import core_db_remote_path, rules_db_remote_path

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE_PATH = REPO_ROOT / "scripts" / "config" / "remote_rules_gate.json"
TRUST_PATH = REPO_ROOT / "scripts" / "config" / "release_trust.json"

RELEASE_FORMAT = 1
CATALOG_DB = "pharmaguide_core.db"
CATALOG_MANIFEST = "export_manifest.json"
RULES_DB = "interaction_db.sqlite"
RULES_MANIFEST = "interaction_db_manifest.json"

MAX_SEQUENCE = 2**63 - 1  # export_manifest.release_sequence is a bigint
SIGNATURE_BYTES = 64
KEY_ID_PATTERN = re.compile(r"[A-Za-z0-9._-]+")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
SEMVER_PATTERN = re.compile(r"(\d+)\.(\d+)\.(\d+)")
# The shape the app's CatalogVersion parser accepts; anything else never activates.
CATALOG_VERSION_PATTERN = re.compile(r"(\d{4})\.(\d{2})\.(\d{2})\.(\d{6})")

_TOP_LEVEL_KEYS = {
    "format", "key_id", "release_sequence", "catalog", "rules",
    "min_rules_version", "blocked_versions",
}
_ENTRY_KEYS = {"version", "path", "sha256", "schema_version", "min_app_version"}

ALERT_FEED_PURPOSE = "safety_alert_feed"
ALERT_FEED_PATH_PATTERN = re.compile(r"safety-alerts/sha256/([0-9a-f]{64})\.json")
_ALERT_FEED_KEYS = {
    "format", "purpose", "key_id", "release_sequence", "base_feed", "extended_feed",
}


class ReleaseManifestError(ValueError):
    """The release manifest, its signature or its inputs cannot be trusted."""


def _refuse_unless(condition, message):
    if not condition:
        raise ReleaseManifestError(message)


def _version_key(value, pattern, label):
    match = pattern.fullmatch(value) if isinstance(value, str) else None
    _refuse_unless(match, f"{label} has an unparseable version: {value!r}")
    return tuple(int(part) for part in match.groups())


def _semver(value, label):
    return _version_key(value, SEMVER_PATTERN, label)


def _catalog_version(value, label):
    return _version_key(value, CATALOG_VERSION_PATTERN, label)


def canonical_text(obj):
    """Return the exact text that is signed and stored in ``signed_release``."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
    )


def _validate_entry(entry, label, remote_path):
    _refuse_unless(
        isinstance(entry, dict) and set(entry) == _ENTRY_KEYS,
        f"{label} must have exactly {sorted(_ENTRY_KEYS)}",
    )
    _refuse_unless(
        entry["path"] == remote_path,
        f"{label}.path must be {remote_path}, got {entry['path']!r}",
    )
    _refuse_unless(
        isinstance(entry["sha256"], str) and SHA256_PATTERN.fullmatch(entry["sha256"]),
        f"{label}.sha256 must be 64 lowercase hex characters",
    )
    for field in ("schema_version", "min_app_version"):
        _refuse_unless(
            isinstance(entry[field], str) and entry[field],
            f"{label}.{field} must be a non-empty string",
        )


def validate_release(release):
    """Refuse anything that is not exactly the published contract."""
    _refuse_unless(
        isinstance(release, dict) and set(release) == _TOP_LEVEL_KEYS,
        f"release manifest must have exactly {sorted(_TOP_LEVEL_KEYS)}",
    )
    _refuse_unless(
        type(release["format"]) is int and release["format"] == RELEASE_FORMAT,
        f"unsupported release format: {release['format']!r}",
    )
    _refuse_unless(
        isinstance(release["key_id"], str) and KEY_ID_PATTERN.fullmatch(release["key_id"]),
        f"invalid key_id: {release['key_id']!r}",
    )
    sequence = release["release_sequence"]
    _refuse_unless(
        type(sequence) is int and 0 < sequence <= MAX_SEQUENCE,
        f"release_sequence must be a positive integer, got {sequence!r}",
    )

    catalog = release["catalog"]
    _refuse_unless(isinstance(catalog, dict), "catalog must be an object")
    _catalog_version(catalog.get("version"), "catalog")
    _validate_entry(catalog, "catalog", core_db_remote_path(catalog["version"]))

    minimum = _semver(release["min_rules_version"], "min_rules_version")
    rules = release["rules"]
    if rules is not None:
        _refuse_unless(isinstance(rules, dict), "rules must be an object or null")
        rules_version = _semver(rules.get("version"), "rules")
        _validate_entry(rules, "rules", rules_db_remote_path(rules["version"]))
        _refuse_unless(
            rules_version >= minimum,
            f"rules {rules['version']} is below min_rules_version "
            f"{release['min_rules_version']}, so this release could never activate",
        )

    blocked = release["blocked_versions"]
    _refuse_unless(
        isinstance(blocked, dict) and set(blocked) == {"catalog", "rules"}
        and isinstance(blocked["catalog"], list) and isinstance(blocked["rules"], list),
        "blocked_versions must have exactly catalog and rules lists",
    )
    # A typo here would silently leave a bad version unblocked.
    for version in blocked["catalog"]:
        _catalog_version(version, "blocked_versions.catalog")
    for version in blocked["rules"]:
        _semver(version, "blocked_versions.rules")
    _refuse_unless(
        catalog["version"] not in blocked["catalog"],
        f"release names catalog {catalog['version']} and also blocks it",
    )
    _refuse_unless(
        rules is None or rules["version"] not in blocked["rules"],
        f"release names rules {(rules or {}).get('version')} and also blocks them",
    )


def parse_release(text):
    """Parse signed text, refusing anything other than its canonical form."""
    try:
        release = json.loads(text)
    except json.JSONDecodeError:
        raise ReleaseManifestError("release manifest is not valid JSON") from None
    _refuse_unless(
        canonical_text(release) == text,
        "release manifest is not canonical JSON; rebuild it instead of editing it",
    )
    validate_release(release)
    return release


def _read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _hash_against_manifest(path, manifest, label):
    """Hash the real file and refuse if its manifest claims anything else."""
    actual = compute_sha256(path)
    claimed = [
        strip_sha256_prefix(manifest[key])
        for key in ("checksum", "checksum_sha256") if manifest.get(key)
    ]
    _refuse_unless(claimed, f"{label} manifest names no checksum")
    for value in claimed:
        _refuse_unless(
            value == actual,
            f"{label} file does not match its manifest: manifest={value}, actual={actual}",
        )
    return actual


def _text(value):
    return "" if value is None else str(value)


def _embedded_db_version(db_path):
    # Older builds refuse a download whose embedded version differs from the manifest.
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        row = conn.execute(
            "SELECT value FROM export_manifest WHERE key = 'db_version'"
        ).fetchone()
    finally:
        conn.close()
    return row[0] if row else None


def _catalog_entry(catalog_dir):
    catalog_dir = Path(catalog_dir)
    manifest = _read_json(catalog_dir / CATALOG_MANIFEST)
    db_path = catalog_dir / CATALOG_DB
    sha256 = _hash_against_manifest(db_path, manifest, "catalog")
    version = _text(manifest.get("db_version"))
    embedded = _embedded_db_version(db_path)
    _refuse_unless(
        embedded == version,
        f"catalog manifest names {version} but the database embeds {embedded}",
    )
    return {
        "version": version,
        "path": core_db_remote_path(version),
        "sha256": sha256,
        "schema_version": _text(manifest.get("schema_version")),
        "min_app_version": _text(manifest.get("min_app_version", "1.0.0")),
    }


def _rules_entry(rules_dir):
    rules_dir = Path(rules_dir)
    manifest = _read_json(rules_dir / RULES_MANIFEST)
    sha256 = _hash_against_manifest(rules_dir / RULES_DB, manifest, "rules")
    version = _text(manifest.get("interaction_db_version"))
    return {
        "version": version,
        "path": rules_db_remote_path(version),
        "sha256": sha256,
        "schema_version": _text(manifest.get("schema_version")),
        "min_app_version": _text(manifest.get("min_app_version")),
    }


def build_release(*, catalog_dir, sequence, min_rules_version, key_id,
                  rules_dir=None, block_catalog=(), block_rules=()):
    """Return canonical manifest text for real files on disk."""
    release = {
        "format": RELEASE_FORMAT,
        "key_id": key_id,
        "release_sequence": sequence,
        "catalog": _catalog_entry(catalog_dir),
        "rules": _rules_entry(rules_dir) if rules_dir else None,
        "min_rules_version": min_rules_version,
        "blocked_versions": {
            "catalog": sorted(set(block_catalog)),
            "rules": sorted(set(block_rules)),
        },
    }
    validate_release(release)
    return canonical_text(release)


def load_private_key(key_file):
    """Load a PEM Ed25519 key kept outside the repo. Never prints or logs it."""
    path = Path(key_file).expanduser().resolve()
    _refuse_unless(
        not path.is_relative_to(REPO_ROOT),
        "the signing key must not live inside the repository",
    )
    _refuse_unless(
        not path.stat().st_mode & 0o077,
        "the signing key file must be readable only by its owner (chmod 600)",
    )
    data = path.read_bytes()
    try:
        try:
            key = serialization.load_pem_private_key(data, password=None)
        except TypeError:  # The PEM is encrypted.
            passphrase = getpass.getpass("Signing key passphrase: ")
            key = serialization.load_pem_private_key(data, password=passphrase.encode())
    except ValueError:
        # Cryptography's own error is dropped so no key detail can reach a log.
        raise ReleaseManifestError("could not read the signing key") from None
    _refuse_unless(isinstance(key, Ed25519PrivateKey), "the signing key must be Ed25519")
    return key


def _signature_over(text, key_id, private_key):
    signature = base64.b64encode(private_key.sign(text.encode("utf-8"))).decode("ascii")
    return f"{key_id}:{signature}"


def sign_release(text, private_key):
    """Return ``release_signature`` for canonical manifest text."""
    release = parse_release(text)
    release_signature = _signature_over(text, release["key_id"], private_key)
    verify_release(text, release_signature, private_key.public_key())
    return release_signature


def parse_signature(release_signature, key_id):
    """Return signature bytes, refusing a wrong key ID or malformed value."""
    found_key_id, separator, encoded = release_signature.partition(":")
    _refuse_unless(separator, "release_signature must be <key_id>:<base64>")
    _refuse_unless(
        found_key_id == key_id,
        f"signature key ID {found_key_id!r} does not match manifest key ID {key_id!r}",
    )
    try:
        signature = base64.b64decode(encoded, validate=True)
    except ValueError:
        raise ReleaseManifestError("release_signature is not standard base64") from None
    _refuse_unless(
        len(signature) == SIGNATURE_BYTES
        and base64.b64encode(signature).decode("ascii") == encoded,
        "release_signature must encode exactly 64 bytes in standard base64",
    )
    return signature


def _require_signature_covers(text, release_signature, key_id, public_key):
    signature = parse_signature(release_signature, key_id)
    _refuse_unless(isinstance(public_key, Ed25519PublicKey), "public key must be Ed25519")
    try:
        public_key.verify(signature, text.encode("utf-8"))
    except InvalidSignature:
        raise ReleaseManifestError(
            "signature does not verify against this manifest and key"
        ) from None


def verify_release(text, release_signature, public_key):
    """Raise unless the signature covers exactly these bytes."""
    release = parse_release(text)
    _require_signature_covers(text, release_signature, release["key_id"], public_key)
    return release


def _read_trust():
    """The repo's own record of where releases go and whose signatures count.

    Anything wrong with it refuses, because a publish can't be judged without it.
    """
    try:
        trust = _read_json(TRUST_PATH)
    except (OSError, ValueError):
        trust = None
    _refuse_unless(
        isinstance(trust, dict)
        and isinstance(trust.get("production_project_ref"), str)
        and trust["production_project_ref"]
        and isinstance(trust.get("test_hosts"), list)
        and isinstance(trust.get("production_keys"), dict)
        and isinstance(trust.get("test_keys"), dict),
        f"{TRUST_PATH.name} can't be read, so nothing can be published",
    )
    return trust


def require_test_destination():
    """Refuse unless SUPABASE_URL is a host this repo lists as a test project.

    The environment says where the client will write, so it can't also vouch for
    that destination. Production is refused first, even if the list ever names it.
    """
    trust = _read_trust()
    try:
        host = (urlsplit(os.environ.get("SUPABASE_URL", "").strip()).hostname or "").lower()
    except ValueError:
        host = ""
    _refuse_unless(
        host != f"{trust['production_project_ref']}.supabase.co",
        "--test-project refused: SUPABASE_URL is the production project",
    )
    _refuse_unless(
        host and host in trust["test_hosts"],
        f"--test-project refused: SUPABASE_URL host {host or '(none)'} is not listed in "
        f"{TRUST_PATH.name}",
    )


def unsigned_publish_allowed():
    """Unsigned stays possible only while no keyed build can exist.

    Pinning the first production key, which comes before the first keyed build,
    ends unsigned publishing for good. A keyed build refuses an unsigned row.
    """
    return not _read_trust()["production_keys"]


def require_signed_when_keys_are_pinned():
    _refuse_unless(
        unsigned_publish_allowed(),
        f"this release must be signed: {TRUST_PATH.name} pins a production key",
    )


def _pinned_public_key(key_id, group):
    keys = _read_trust().get(group)
    public = keys.get(key_id) if isinstance(keys, dict) else None
    _refuse_unless(
        isinstance(public, str),
        f"signing key {key_id} is not pinned in {TRUST_PATH.name} {group}",
    )
    try:
        return Ed25519PublicKey.from_public_bytes(bytes.fromhex(public))
    except ValueError:
        raise ReleaseManifestError(
            f"signing key {key_id} in {TRUST_PATH.name} is not a valid Ed25519 key"
        ) from None


def _verify_against_pinned_key(text, release_signature, release, test_project):
    """Check the signature here, in the publish path, against a key in the repo."""
    group = "test_keys" if test_project else "production_keys"
    verify_release(text, release_signature, _pinned_public_key(release["key_id"], group))


def _validate_alert_feed_entry(entry, label):
    _refuse_unless(
        isinstance(entry, dict) and set(entry) == {"path", "checksum"},
        f"{label} must have exactly path and checksum",
    )
    match = isinstance(entry["path"], str) and ALERT_FEED_PATH_PATTERN.fullmatch(entry["path"])
    _refuse_unless(
        match and entry["checksum"] == f"sha256:{match.group(1)}",
        f"{label} must name a content-addressed feed",
    )


def validate_alert_feed_statement(statement):
    """Refuse anything but this document, so a signature can't be reused across documents."""
    _refuse_unless(
        isinstance(statement, dict)
        and set(statement) == _ALERT_FEED_KEYS
        and statement["purpose"] == ALERT_FEED_PURPOSE,
        f"this is not a safety-alert statement: it must have exactly {sorted(_ALERT_FEED_KEYS)}",
    )
    _refuse_unless(
        type(statement["format"]) is int and statement["format"] == RELEASE_FORMAT,
        f"unsupported statement format: {statement['format']!r}",
    )
    _refuse_unless(
        isinstance(statement["key_id"], str) and KEY_ID_PATTERN.fullmatch(statement["key_id"]),
        f"invalid key_id: {statement['key_id']!r}",
    )
    sequence = statement["release_sequence"]
    _refuse_unless(
        type(sequence) is int and 0 < sequence <= MAX_SEQUENCE,
        f"release_sequence must be a positive integer, got {sequence!r}",
    )
    _validate_alert_feed_entry(statement["base_feed"], "base_feed")
    if statement["extended_feed"] is not None:
        _validate_alert_feed_entry(statement["extended_feed"], "extended_feed")


def parse_alert_feed_statement(text):
    try:
        statement = json.loads(text)
    except json.JSONDecodeError:
        raise ReleaseManifestError("safety-alert statement is not valid JSON") from None
    _refuse_unless(
        canonical_text(statement) == text,
        "safety-alert statement is not canonical JSON; rebuild it instead of editing it",
    )
    validate_alert_feed_statement(statement)
    return statement


def sign_alert_feed(text, private_key):
    """Return the signature for a canonical safety-alert statement."""
    statement = parse_alert_feed_statement(text)
    signature = _signature_over(text, statement["key_id"], private_key)
    _require_signature_covers(text, signature, statement["key_id"], private_key.public_key())
    return signature


def verify_alert_feed_against_pin(text, signature, *, test_project=False):
    """There is no unsigned phase: with nothing pinned, every feed is refused."""
    if test_project:
        require_test_destination()
    statement = parse_alert_feed_statement(text)
    group = "test_keys" if test_project else "alert_feed_keys"
    _require_signature_covers(
        text, signature, statement["key_id"], _pinned_public_key(statement["key_id"], group),
    )
    return statement


def check_remote_rules_gate(release, *, test_project=False):
    """Hold remote rules off production until the A9 sign-off is recorded.

    Returns a one-line reason.
    """
    if test_project:
        require_test_destination()
    if release["rules"] is None:
        return "catalog-only release; the remote rules gate does not apply"
    try:
        gate = _read_json(GATE_PATH)
    except (OSError, ValueError):
        gate = {}  # A missing or broken gate file stays closed.
    if (isinstance(gate, dict) and gate.get("a9_review_complete") is True
            and gate.get("signed_off_by") and gate.get("signed_off_at")):
        return "remote rules gate is open: A9 sign-off recorded"
    _refuse_unless(
        test_project,
        "refusing to publish rules: remote_rules_gate.json records no A9 sign-off",
    )
    return "remote rules gate is closed; allowed for this named test project only"


def load_signed_release(manifest_path, signature_path, *, local_manifest, rules_dir,
                        test_project=False):
    """Prove a signed release is genuine and describes this build.

    Called before any Storage write. Publishing needs no private key: the public
    keys it checks against are pinned in the repo.
    """
    if test_project:
        require_test_destination()
    text = Path(manifest_path).read_bytes().decode("utf-8")
    release = parse_release(text)
    release_signature = Path(signature_path).read_text(encoding="utf-8").strip()
    _verify_against_pinned_key(text, release_signature, release, test_project)

    catalog = release["catalog"]
    expected = {
        "version": _text(local_manifest["db_version"]),
        "sha256": strip_sha256_prefix(local_manifest["checksum"]),
        "schema_version": _text(local_manifest["schema_version"]),
        "min_app_version": _text(local_manifest.get("min_app_version", "1.0.0")),
    }
    for field, value in expected.items():
        _refuse_unless(
            catalog[field] == value,
            f"release manifest catalog.{field} is {catalog[field]} but this build has {value}",
        )

    rules_local_path = None
    if release["rules"] is not None:
        rules_local_path = os.path.join(rules_dir, RULES_DB)
        actual = compute_sha256(Path(rules_local_path))
        _refuse_unless(
            actual == release["rules"]["sha256"],
            f"release manifest rules.sha256 is {release['rules']['sha256']} but "
            f"{RULES_DB} is {actual}",
        )
    return {
        "release": release,
        "rules_local_path": rules_local_path,
        "rpc_params": {
            "release_sequence": release["release_sequence"],
            "signed_release": text,
            "release_signature": release_signature,
        },
    }


# Read by sync but unchanged by a new db_version. Detail blobs are linked, because sync
# only reads them and they are addressed by hash; files are copied. share_index is left
# out because sync regenerates it with the new version inside. Image files are linked one
# by one, because their index names the version and has to be rewritten.
_ROLLBACK_COPIED_FILES = (
    "detail_index.json", "core_projection_manifest.json", RULES_DB, RULES_MANIFEST,
)
_IMAGES_DIR = "product_images"
_IMAGE_INDEX = "product_image_index.json"
_IMAGE_URL_PREFIX = "product-images/"


def _write_rollback_image_index(source_index, destination, db_version):
    index = _read_json(source_index)
    for entry in index.values():
        if entry.get("remote_path") is not None:
            entry["remote_path"] = f"v{db_version}/{entry['filename']}"
    with open(destination, "w", encoding="utf-8") as handle:
        json.dump(index, handle, indent=2, sort_keys=True)


def prepare_rollback(source_dir, output_dir, *, db_version=None, newer_than=None):
    """Make a publishable build dir from a known-good one, with a fresher db_version.

    Keyed builds roll back by sequence alone. Builds without keys only ever move to
    a newer db_version, and they refuse a file whose embedded version differs from
    the manifest, so the version is stamped inside the catalog and its hash changes.
    Sync uploads images under the new version and old versions get pruned, so an image
    path that names the source version moves with it. Everything else in the product
    rows, and the detail blobs, stay exactly as they were.
    """
    source = Path(source_dir).resolve()
    output = Path(output_dir).resolve()
    _refuse_unless(not output.exists(), f"output directory already exists: {output}")
    manifest = _read_json(source / CATALOG_MANIFEST)
    _hash_against_manifest(source / CATALOG_DB, manifest, "known-good catalog")

    generated_at = datetime.now(timezone.utc)
    if db_version is None:
        from build_final_db import build_db_version
        db_version = build_db_version(generated_at)
    new_key = _catalog_version(db_version, "rollback")
    for floor in (manifest.get("db_version"), newer_than):
        if floor is not None:
            _refuse_unless(
                new_key > _catalog_version(floor, "existing catalog"),
                f"rollback version {db_version} is not newer than {floor}",
            )

    staging = output.with_name(output.name + ".staging")
    _refuse_unless(not staging.exists(), f"staging directory already exists: {staging}")
    staging.mkdir(parents=True)
    try:
        db_path = staging / CATALOG_DB
        shutil.copy2(source / CATALOG_DB, db_path)
        conn = sqlite3.connect(db_path)
        try:
            with conn:
                changed = conn.execute(
                    "UPDATE export_manifest SET value = ? WHERE key = 'db_version'",
                    (db_version,),
                ).rowcount
                _refuse_unless(changed == 1, "catalog has no embedded db_version row")
                conn.execute(
                    "UPDATE export_manifest SET value = ? WHERE key = 'generated_at'",
                    (generated_at.isoformat(),),
                )
                columns = {row[1] for row in conn.execute("PRAGMA table_info(products_core)")}
                if "image_thumbnail_url" in columns:
                    old_prefix = f"{_IMAGE_URL_PREFIX}v{manifest.get('db_version')}/"
                    conn.execute(
                        "UPDATE products_core SET image_thumbnail_url = "
                        "? || substr(image_thumbnail_url, ?) "
                        "WHERE substr(image_thumbnail_url, 1, ?) = ?",
                        (f"{_IMAGE_URL_PREFIX}v{db_version}/", len(old_prefix) + 1,
                         len(old_prefix), old_prefix),
                    )
        finally:
            conn.close()

        sha256 = compute_sha256(db_path)
        stamped = {
            **manifest,
            "db_version": db_version,
            "generated_at": generated_at.isoformat(),
            "checksum": f"sha256:{sha256}",
        }
        if "checksum_sha256" in stamped:
            stamped["checksum_sha256"] = sha256
        with open(staging / CATALOG_MANIFEST, "w", encoding="utf-8") as handle:
            json.dump(stamped, handle, indent=2)

        for name in _ROLLBACK_COPIED_FILES:
            if (source / name).is_file():
                shutil.copy2(source / name, staging / name)
        if (source / "detail_blobs").is_dir():
            os.symlink(source / "detail_blobs", staging / "detail_blobs")
        if (source / _IMAGE_INDEX).is_file():
            _write_rollback_image_index(source / _IMAGE_INDEX, staging / _IMAGE_INDEX, db_version)
        if (source / _IMAGES_DIR).is_dir():
            (staging / _IMAGES_DIR).mkdir()
            for item in (source / _IMAGES_DIR).iterdir():
                if item.name == _IMAGE_INDEX:
                    _write_rollback_image_index(
                        item, staging / _IMAGES_DIR / _IMAGE_INDEX, db_version,
                    )
                else:
                    os.symlink(item, staging / _IMAGES_DIR / item.name)
        os.replace(staging, output)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {"db_version": db_version, "sha256": sha256, "output_dir": str(output)}


def _parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build", help="Write canonical manifest JSON")
    build.add_argument("--catalog-dir", required=True)
    build.add_argument("--rules-dir", help="Omit for a catalog-only release")
    build.add_argument("--sequence", type=int, required=True)
    build.add_argument("--min-rules-version", required=True)
    build.add_argument("--block-catalog", action="append", default=[])
    build.add_argument("--block-rules", action="append", default=[])
    build.add_argument("--key-id", required=True)
    build.add_argument("--output", required=True)

    sign = commands.add_parser("sign", help="Sign a manifest with a private key file")
    sign.add_argument("--manifest", required=True)
    sign.add_argument("--key-file", required=True)
    sign.add_argument("--output", required=True)

    alert_feed = commands.add_parser(
        "sign-alert-feed", help="Sign a safety-alert statement with a private key file",
    )
    alert_feed.add_argument("--statement", required=True)
    alert_feed.add_argument("--key-file", required=True)
    alert_feed.add_argument("--output", required=True)

    commands.add_parser(
        "unsigned-allowed", help="Exit 0 only while an unsigned publish is still allowed",
    )

    verify = commands.add_parser("verify", help="Verify a signature with a public key file")
    verify.add_argument("--manifest", required=True)
    verify.add_argument("--signature", required=True)
    verify.add_argument("--public-key", required=True)

    rollback = commands.add_parser("prepare-rollback", help="Stamp a known-good build as new")
    rollback.add_argument("--source-dir", required=True)
    rollback.add_argument("--output-dir", required=True)
    rollback.add_argument("--db-version", help="Default: the current UTC build version")
    rollback.add_argument("--newer-than", help="The bad catalog version being replaced")
    return parser.parse_args(argv)


def _read_text(path):
    return Path(path).read_bytes().decode("utf-8")


def _write_text(path, text):
    Path(path).write_bytes(text.encode("utf-8"))


def _run(args):
    if args.command == "build":
        text = build_release(
            catalog_dir=args.catalog_dir, rules_dir=args.rules_dir, sequence=args.sequence,
            min_rules_version=args.min_rules_version, key_id=args.key_id,
            block_catalog=args.block_catalog, block_rules=args.block_rules,
        )
        _write_text(args.output, text)
        print(f"Wrote {args.output}")
    elif args.command == "sign":
        signature = sign_release(_read_text(args.manifest), load_private_key(args.key_file))
        _write_text(args.output, signature)
        print(f"Wrote {args.output} (key ID {signature.partition(':')[0]})")
    elif args.command == "sign-alert-feed":
        signature = sign_alert_feed(_read_text(args.statement), load_private_key(args.key_file))
        _write_text(args.output, signature)
        print(f"Wrote {args.output} (key ID {signature.partition(':')[0]})")
    elif args.command == "unsigned-allowed":
        require_signed_when_keys_are_pinned()
        print("Unsigned publishing is allowed: no production key is pinned")
    elif args.command == "verify":
        public_key = serialization.load_pem_public_key(Path(args.public_key).read_bytes())
        release = verify_release(
            _read_text(args.manifest),
            _read_text(args.signature).strip(),
            public_key,
        )
        print(f"Signature OK: sequence {release['release_sequence']}, "
              f"catalog {release['catalog']['version']}")
    else:
        result = prepare_rollback(
            args.source_dir, args.output_dir,
            db_version=args.db_version, newer_than=args.newer_than,
        )
        print(f"Wrote {result['output_dir']}: db_version {result['db_version']}, "
              f"sha256 {result['sha256']}")


def main(argv=None):
    args = _parse_args(argv)
    try:
        _run(args)
    except (ValueError, OSError, sqlite3.Error) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
