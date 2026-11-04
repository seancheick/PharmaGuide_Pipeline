"""Signed release manifest: build, sign, verify, gate, sync seam and rollback (ADR-012).

Keys are generated at runtime. No private key is ever committed.
"""

import base64
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

_scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

import release_manifest as rm  # noqa: E402
import supabase_client  # noqa: E402
import sync_to_supabase as sync  # noqa: E402

_REAL_SIGNED_RULE_GATE = sync._enforce_signed_rule_gate
CATALOG_VERSION = "2026.10.01.120000"
RULES_VERSION = "1.0.15"
KEY_ID = "test-key-1"


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _make_catalog(directory, version=CATALOG_VERSION, product_count=2):
    """A real build dir: catalog DB with embedded version, blobs, index, manifest."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    db_path = directory / "pharmaguide_core.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE products_core ("
        "dsld_id TEXT, product_name TEXT, brand_name TEXT, "
        "product_safety_status TEXT, quality_assessment_status TEXT, "
        "quality_score_status TEXT, quality_score_v4_100 REAL, quality_tier TEXT, "
        "v4_confidence TEXT, has_third_party_testing INTEGER, "
        "is_trusted_manufacturer INTEGER, is_vegan INTEGER, "
        "is_gluten_free INTEGER, is_dairy_free INTEGER, is_soy_free INTEGER, "
        "is_organic INTEGER, is_non_gmo INTEGER, "
        "pillar_formulation_v4 REAL, pillar_dose_v4 REAL, pillar_evidence_v4 REAL, "
        "pillar_transparency_v4 REAL, pillar_verification_v4 REAL, pillar_safety_hygiene_v4 REAL)"
    )
    conn.executemany(
        "INSERT INTO products_core VALUES "
        "(?, ?, 'Example', 'no_known_catalog_concern', 'complete', "
        "'scored', 81, 'Very good', 'high', 1, 1, 0, 1, 0, 0, 0, 0, "
        "11.2, 20.0, 18.9, 15.0, 6.0, 10.0)",
        [(str(i), f"Product {i}") for i in range(1, product_count + 1)],
    )
    conn.execute("CREATE TABLE export_manifest (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.executemany(
        "INSERT INTO export_manifest VALUES (?, ?)",
        [("db_version", version), ("generated_at", "2026-10-01T12:00:00+00:00"),
         ("schema_version", "2.5.0"), ("min_app_version", "1.0.0")],
    )
    conn.commit()
    conn.close()

    blobs = directory / "detail_blobs"
    blobs.mkdir()
    detail_index = {}
    for i in range(1, product_count + 1):
        payload = json.dumps({"dsld_id": str(i)}).encode()
        (blobs / f"{i}.json").write_bytes(payload)
        blob_sha = hashlib.sha256(payload).hexdigest()
        detail_index[str(i)] = {
            "blob_sha256": blob_sha,
            "storage_path": f"shared/details/sha256/{blob_sha[:2]}/{blob_sha}.json",
        }
    index_path = directory / "detail_index.json"
    index_path.write_text(json.dumps(detail_index))
    (directory / "export_manifest.json").write_text(json.dumps({
        "db_version": version,
        "pipeline_version": "3.4.0",
        "scoring_version": "4.5.0",
        "schema_version": "2.5.0",
        "generated_at": "2026-10-01T12:00:00+00:00",
        "product_count": product_count,
        "min_app_version": "1.0.0",
        "checksum": f"sha256:{_sha(db_path)}",
        "detail_blob_count": product_count,
        "detail_blob_unique_count": product_count,
        "detail_index_checksum": f"sha256:{_sha(index_path)}",
        "errors": [],
    }))
    return directory


def _make_rules(directory, version=RULES_VERSION, content=b"rules-file-bytes"):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    db_path = directory / "interaction_db.sqlite"
    db_path.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    (directory / "interaction_db_manifest.json").write_text(json.dumps({
        "checksum": f"sha256:{digest}",
        "checksum_sha256": digest,
        "db_version": version,
        "interaction_db_version": version,
        "schema_version": "4.0.0",
        "min_app_version": "1.0.0",
    }))
    return directory


def _build(catalog_dir, rules_dir=None, sequence=5, **overrides):
    return rm.build_release(**{
        "catalog_dir": catalog_dir, "rules_dir": rules_dir, "sequence": sequence,
        "min_rules_version": "1.0.0", "key_id": KEY_ID, **overrides,
    })


@pytest.fixture()
def key():
    return Ed25519PrivateKey.generate()


PRODUCTION_REF = "prodref000000000000"
PRODUCTION_URL = f"https://{PRODUCTION_REF}.supabase.co"


@pytest.fixture(autouse=True)
def trust_file(tmp_path, monkeypatch):
    path = tmp_path / "release_trust.json"
    path.write_text(json.dumps({
        "production_project_ref": PRODUCTION_REF,
        "test_hosts": ["project-under-test.example", "127.0.0.1"],
        "production_keys": {},
        "test_keys": {},
    }))
    monkeypatch.setattr(rm, "TRUST_PATH", path)
    return path


def _public_hex(key):
    return key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    ).hex()


def _pin(key, *groups):
    trust = json.loads(rm.TRUST_PATH.read_text())
    for group in groups:
        trust[group][KEY_ID] = _public_hex(key)
    rm.TRUST_PATH.write_text(json.dumps(trust))


def _write_signed(tmp_path, text, key, *, pin=("production_keys", "test_keys")):
    manifest_path = tmp_path / "release.json"
    signature_path = tmp_path / "release.sig"
    manifest_path.write_bytes(text.encode("utf-8"))
    signature_path.write_text(rm.sign_release(text, key))
    _pin(key, *pin)
    return str(manifest_path), str(signature_path)


# --- canonical bytes and signature ---------------------------------------------------


def test_canonical_text_is_the_exact_published_form():
    assert rm.canonical_text({"b": [1, {"z": None, "a": "é"}], "a": True}) == (
        '{"a":true,"b":[1,{"a":"é","z":null}]}'
    )


def test_manifest_has_exactly_the_contract_shape(tmp_path):
    catalog = _make_catalog(tmp_path / "catalog")
    rules = _make_rules(tmp_path / "rules")
    release = json.loads(_build(
        catalog, rules, block_catalog=["2026.09.01.000000"], block_rules=["1.0.14"],
    ))
    assert release == {
        "format": 1,
        "key_id": KEY_ID,
        "release_sequence": 5,
        "catalog": {
            "version": CATALOG_VERSION,
            "path": f"v{CATALOG_VERSION}/pharmaguide_core.db",
            "sha256": _sha(catalog / "pharmaguide_core.db"),
            "schema_version": "2.5.0",
            "min_app_version": "1.0.0",
        },
        "rules": {
            "version": RULES_VERSION,
            "path": f"rules/{RULES_VERSION}/interaction_db.sqlite",
            "sha256": _sha(rules / "interaction_db.sqlite"),
            "schema_version": "4.0.0",
            "min_app_version": "1.0.0",
        },
        "min_rules_version": "1.0.0",
        "blocked_versions": {"catalog": ["2026.09.01.000000"], "rules": ["1.0.14"]},
    }


def test_catalog_only_release_names_null_rules(tmp_path):
    release = json.loads(_build(_make_catalog(tmp_path / "catalog")))
    assert release["rules"] is None
    assert release["blocked_versions"] == {"catalog": [], "rules": []}


def test_round_trip_verifies_the_canonical_utf8_bytes(tmp_path, key):
    text = _build(_make_catalog(tmp_path / "catalog"), _make_rules(tmp_path / "rules"))
    signature = rm.sign_release(text, key)
    key_id, _, encoded = signature.partition(":")
    assert key_id == KEY_ID
    raw = base64.b64decode(encoded, validate=True)
    assert len(raw) == 64
    # Independent of the module's verifier: this is what the Dart side does.
    key.public_key().verify(raw, text.encode("utf-8"))
    assert rm.verify_release(text, signature, key.public_key())["release_sequence"] == 5


def test_cli_round_trip_never_prints_the_key(tmp_path, key, capsys):
    catalog = _make_catalog(tmp_path / "catalog")
    key_dir = tmp_path / "custody"
    key_dir.mkdir()
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    key_file = key_dir / "key.pem"
    key_file.write_bytes(pem)
    key_file.chmod(0o600)
    public_file = key_dir / "key.pub.pem"
    public_file.write_bytes(key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    manifest, signature = tmp_path / "release.json", tmp_path / "release.sig"

    assert rm.main([
        "build", "--catalog-dir", str(catalog), "--sequence", "7",
        "--min-rules-version", "1.0.0", "--key-id", KEY_ID, "--output", str(manifest),
    ]) == 0
    assert not manifest.read_bytes().endswith(b"\n")
    assert rm.main([
        "sign", "--manifest", str(manifest), "--key-file", str(key_file),
        "--output", str(signature),
    ]) == 0
    assert rm.main([
        "verify", "--manifest", str(manifest), "--signature", str(signature),
        "--public-key", str(public_file),
    ]) == 0
    out = capsys.readouterr()
    assert "PRIVATE KEY" not in out.out + out.err

    manifest.write_bytes(manifest.read_bytes().replace(b'"release_sequence":7', b'"release_sequence":8'))
    assert rm.main([
        "verify", "--manifest", str(manifest), "--signature", str(signature),
        "--public-key", str(public_file),
    ]) == 1


def test_sign_refuses_a_key_others_can_read_or_one_inside_the_repo(tmp_path, key, monkeypatch):
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    key_file = tmp_path / "key.pem"
    key_file.write_bytes(pem)
    key_file.chmod(0o644)
    with pytest.raises(rm.ReleaseManifestError, match="only by its owner"):
        rm.load_private_key(key_file)
    key_file.chmod(0o600)
    assert isinstance(rm.load_private_key(key_file), Ed25519PrivateKey)
    monkeypatch.setattr(rm, "REPO_ROOT", tmp_path.resolve())
    with pytest.raises(rm.ReleaseManifestError, match="inside the repository"):
        rm.load_private_key(key_file)


def test_sign_reads_a_passphrase_protected_key(tmp_path, key, monkeypatch):
    key_file = tmp_path / "key.pem"
    key_file.write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(b"right-passphrase"),
    ))
    key_file.chmod(0o600)
    monkeypatch.setattr(rm.getpass, "getpass", lambda _prompt: "right-passphrase")
    assert isinstance(rm.load_private_key(key_file), Ed25519PrivateKey)
    monkeypatch.setattr(rm.getpass, "getpass", lambda _prompt: "wrong-passphrase")
    with pytest.raises(rm.ReleaseManifestError, match="could not read"):
        rm.load_private_key(key_file)


def test_tampered_bytes_are_refused(tmp_path, key):
    text = _build(_make_catalog(tmp_path / "catalog"))
    signature = rm.sign_release(text, key)
    release = json.loads(text)

    changed = rm.canonical_text({**release, "release_sequence": 6})
    with pytest.raises(rm.ReleaseManifestError, match="does not verify"):
        rm.verify_release(changed, signature, key.public_key())
    # Same meaning, different bytes: refused rather than parsed and accepted.
    with pytest.raises(rm.ReleaseManifestError, match="not canonical"):
        rm.verify_release(text + "\n", signature, key.public_key())
    with pytest.raises(rm.ReleaseManifestError, match="does not verify"):
        rm.verify_release(text, signature, Ed25519PrivateKey.generate().public_key())


@pytest.mark.parametrize("mangle, match", [
    (lambda s: s.replace(KEY_ID, "other-key"), "does not match manifest key ID"),
    (lambda s: s.partition(":")[2], "must be <key_id>"),
    (lambda s: s[:-8], "standard base64|exactly 64 bytes"),
    (lambda s: s[:-2] + "!!", "standard base64"),
])
def test_malformed_signature_is_refused(tmp_path, key, mangle, match):
    text = _build(_make_catalog(tmp_path / "catalog"))
    with pytest.raises(rm.ReleaseManifestError, match=match):
        rm.verify_release(text, mangle(rm.sign_release(text, key)), key.public_key())


# --- build refusals ------------------------------------------------------------------


@pytest.mark.parametrize("sequence", [0, -1, True, 2**63])
def test_bad_sequence_is_refused(tmp_path, sequence):
    with pytest.raises(rm.ReleaseManifestError, match="release_sequence"):
        _build(_make_catalog(tmp_path / "catalog"), sequence=sequence)


def test_catalog_hash_mismatch_is_refused(tmp_path):
    catalog = _make_catalog(tmp_path / "catalog")
    with open(catalog / "pharmaguide_core.db", "ab") as handle:
        handle.write(b"x")
    with pytest.raises(rm.ReleaseManifestError, match="catalog file does not match"):
        _build(catalog)


def test_rules_hash_mismatch_is_refused(tmp_path):
    catalog = _make_catalog(tmp_path / "catalog")
    rules = _make_rules(tmp_path / "rules")
    (rules / "interaction_db.sqlite").write_bytes(b"other bytes")
    with pytest.raises(rm.ReleaseManifestError, match="rules file does not match"):
        _build(catalog, rules)


def test_embedded_catalog_version_mismatch_is_refused(tmp_path):
    catalog = _make_catalog(tmp_path / "catalog")
    manifest_path = catalog / "export_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["db_version"] = "2026.10.02.120000"
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(rm.ReleaseManifestError, match="embeds"):
        _build(catalog)


@pytest.mark.parametrize("overrides, match", [
    ({"block_catalog": [CATALOG_VERSION]}, "also blocks"),
    ({"block_rules": [RULES_VERSION]}, "also blocks"),
    ({"block_catalog": ["2026.9.1"]}, "unparseable"),
    ({"block_rules": ["latest"]}, "unparseable"),
    ({"min_rules_version": "1.0"}, "unparseable"),
    ({"min_rules_version": "1.0.16"}, "could never activate"),
    ({"key_id": "has:colon"}, "invalid key_id"),
])
def test_release_that_could_mislead_or_never_activate_is_refused(tmp_path, overrides, match):
    catalog = _make_catalog(tmp_path / "catalog")
    rules = _make_rules(tmp_path / "rules")
    with pytest.raises(rm.ReleaseManifestError, match=match):
        _build(catalog, rules, **overrides)


def test_unparseable_catalog_version_is_refused(tmp_path):
    # The app's CatalogVersion parser fails closed on this shape.
    with pytest.raises(rm.ReleaseManifestError, match="unparseable"):
        _build(_make_catalog(tmp_path / "catalog", version="2026.03.27.5"))


# --- remote rules gate ---------------------------------------------------------------


@pytest.fixture()
def gate_file(tmp_path, monkeypatch):
    path = tmp_path / "remote_rules_gate.json"
    monkeypatch.setattr(rm, "GATE_PATH", path)
    monkeypatch.setenv("SUPABASE_URL", "https://project-under-test.example/")
    return path


def _gate(path, complete, by, at):
    path.write_text(json.dumps(
        {"a9_review_complete": complete, "signed_off_by": by, "signed_off_at": at}
    ))


RULES_RELEASE = {"rules": {"version": RULES_VERSION}}


def test_committed_gate_has_the_declared_shape():
    gate = json.loads((Path(_scripts_dir) / "config" / "remote_rules_gate.json").read_text())
    assert set(gate) == {"a9_review_complete", "signed_off_by", "signed_off_at"}


@pytest.mark.parametrize("gate", [
    (False, None, None),
    (True, None, None),            # complete with nobody accountable is not a sign-off
    (True, "Sean", None),
    ("true", "Sean", "2026-12-01"),
])
def test_gate_refuses_rules_without_a_recorded_sign_off(gate_file, gate):
    _gate(gate_file, *gate)
    with pytest.raises(rm.ReleaseManifestError, match="no A9 sign-off"):
        rm.check_remote_rules_gate(RULES_RELEASE)


@pytest.mark.parametrize("content", [None, "{not json", "[]"])
def test_gate_stays_closed_when_its_file_is_missing_or_broken(gate_file, content):
    if content is not None:
        gate_file.write_text(content)
    with pytest.raises(rm.ReleaseManifestError, match="no A9 sign-off"):
        rm.check_remote_rules_gate(RULES_RELEASE)


def test_gate_allows_rules_after_a_recorded_sign_off(gate_file):
    _gate(gate_file, True, "Sean", "2026-12-01")
    assert "open" in rm.check_remote_rules_gate(RULES_RELEASE)


def test_gate_does_not_apply_to_a_catalog_only_release(gate_file):
    _gate(gate_file, False, None, None)
    assert "catalog-only" in rm.check_remote_rules_gate({"rules": None})


def test_test_project_needs_a_host_the_repo_allows(gate_file):
    _gate(gate_file, False, None, None)
    assert "test project" in rm.check_remote_rules_gate(RULES_RELEASE, test_project=True)
    # Without the flag, nothing about the host opens the gate.
    with pytest.raises(rm.ReleaseManifestError, match="no A9 sign-off"):
        rm.check_remote_rules_gate(RULES_RELEASE)


@pytest.mark.parametrize("url", [
    PRODUCTION_URL,
    PRODUCTION_URL.upper().replace("HTTPS", "https"),
    f"{PRODUCTION_URL}/",
    # The name before the @ is not the host.
    f"https://127.0.0.1@{PRODUCTION_REF}.supabase.co",
])
def test_test_project_refuses_production_however_it_is_spelled(gate_file, monkeypatch, url):
    _gate(gate_file, False, None, None)
    monkeypatch.setenv("SUPABASE_URL", url)
    # The env var that used to prove this is no longer read, even when it agrees.
    monkeypatch.setenv("PHARMAGUIDE_TEST_SUPABASE_URL", url)
    with pytest.raises(rm.ReleaseManifestError, match="production"):
        rm.check_remote_rules_gate(RULES_RELEASE, test_project=True)


def test_production_stays_refused_if_the_allowlist_ever_names_it(gate_file, monkeypatch, trust_file):
    trust = json.loads(trust_file.read_text())
    trust["test_hosts"].append(f"{PRODUCTION_REF}.supabase.co")
    trust_file.write_text(json.dumps(trust))
    monkeypatch.setenv("SUPABASE_URL", PRODUCTION_URL)
    with pytest.raises(rm.ReleaseManifestError, match="production"):
        rm.check_remote_rules_gate({"rules": None}, test_project=True)


@pytest.mark.parametrize("url", ["https://unlisted-project.supabase.co", "", "not a url"])
def test_test_project_refuses_any_host_the_repo_does_not_list(gate_file, monkeypatch, url):
    monkeypatch.setenv("SUPABASE_URL", url)
    with pytest.raises(rm.ReleaseManifestError, match="release_trust.json"):
        rm.check_remote_rules_gate({"rules": None}, test_project=True)


@pytest.mark.parametrize("content", [None, "not json", "[]", "{}", '{"production_keys": 1}'])
def test_unreadable_trust_refuses_the_test_project(gate_file, trust_file, content):
    if content is None:
        trust_file.unlink()
    else:
        trust_file.write_text(content)
    with pytest.raises(rm.ReleaseManifestError, match="release_trust.json"):
        rm.check_remote_rules_gate({"rules": None}, test_project=True)


def test_committed_trust_file_is_well_formed_and_keeps_production_apart():
    trust = json.loads((Path(rm.__file__).parent / "config" / "release_trust.json").read_text())
    assert set(trust) == {
        "production_project_ref", "test_hosts", "production_keys", "test_keys", "alert_feed_keys",
    }
    assert re.fullmatch(r"[a-z0-9]{20}", trust["production_project_ref"])
    assert not any(trust["production_project_ref"] in host for host in trust["test_hosts"])
    for group in ("production_keys", "test_keys", "alert_feed_keys"):
        for key_id, public in trust[group].items():
            assert rm.KEY_ID_PATTERN.fullmatch(key_id)
            assert len(bytes.fromhex(public)) == 32


# --- RPC client seam -----------------------------------------------------------------


class _RpcClient:
    def __init__(self):
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, params))
        return SimpleNamespace(execute=lambda: SimpleNamespace(data="new-id"))


LOCAL_MANIFEST = {
    "db_version": CATALOG_VERSION, "pipeline_version": "3.4.0", "scoring_version": "4.5.0",
    "schema_version": "2.5.0", "product_count": 2, "checksum": "sha256:abc",
    "generated_at": "2026-10-01T12:00:00+00:00", "min_app_version": "1.0.0",
}
UNSIGNED_PARAMS = {
    "p_db_version": CATALOG_VERSION, "p_pipeline_version": "3.4.0",
    "p_scoring_version": "4.5.0", "p_schema_version": "2.5.0", "p_product_count": 2,
    "p_checksum": "sha256:abc", "p_generated_at": "2026-10-01T12:00:00+00:00",
    "p_min_app_version": "1.0.0", "p_submission_approvals": [],
}


def test_unsigned_rpc_payload_is_unchanged():
    client = _RpcClient()
    supabase_client.insert_manifest(client, LOCAL_MANIFEST)
    assert client.calls == [("rotate_manifest_with_submission_approvals", UNSIGNED_PARAMS)]
    # Exact order too: this is the JSON body sent today.
    assert list(client.calls[0][1]) == list(UNSIGNED_PARAMS)


def test_signed_rpc_payload_adds_exactly_the_three_params():
    client = _RpcClient()
    supabase_client.insert_manifest(
        client, LOCAL_MANIFEST,
        release_sequence=5, signed_release="{}", release_signature="k:s",
    )
    assert client.calls[0][1] == {
        **UNSIGNED_PARAMS, "p_release_sequence": 5,
        "p_signed_release": "{}", "p_release_signature": "k:s",
    }


def test_partial_signed_params_are_refused():
    with pytest.raises(ValueError, match="together"):
        supabase_client.insert_manifest(_RpcClient(), LOCAL_MANIFEST, release_sequence=5)


@pytest.mark.parametrize("integer, bigint, ok", [
    ("integer", "bigint", True),   # PostgREST 14.5, production today
    ("int32", "int64", True),      # PostgREST 16.4, what the Supabase CLI now pins
    ("int64", "int64", False),     # a real change of argument type still refuses
    ("int32", "int32", False),
])
def test_publication_contract_reads_either_postgrest_spelling(monkeypatch, integer, bigint, ok):
    import requests
    formats = {
        "p_db_version": "text", "p_pipeline_version": "text", "p_scoring_version": "text",
        "p_schema_version": "text", "p_product_count": integer, "p_checksum": "text",
        "p_generated_at": "timestamp with time zone", "p_min_app_version": "text",
        "p_submission_approvals": "jsonb", "p_release_sequence": bigint,
        "p_signed_release": "text", "p_release_signature": "text",
    }
    schema = {"properties": {k: {"format": v} for k, v in formats.items()},
              "required": ["p_db_version"]}
    paths = {"/rpc/rotate_manifest_with_submission_approvals": {
        "post": {"parameters": [{"in": "body", "schema": schema}]}}}
    monkeypatch.setenv("SUPABASE_URL", "https://example.invalid")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-only-secret")
    monkeypatch.setattr(requests, "get", lambda *a, **k: SimpleNamespace(
        raise_for_status=lambda: None, json=lambda: {"paths": paths}))
    if ok:
        supabase_client.require_publication_contract(signed_release=True)
    else:
        with pytest.raises(ValueError, match="publication contract"):
            supabase_client.require_publication_contract(signed_release=True)


@pytest.mark.parametrize("deployed, signed, ok", [
    (False, False, True),   # the publisher keeps working before the migration deploys
    (True, False, True),
    (False, True, False),   # a signed release needs the migration
    (True, True, True),
])
def test_publication_contract_requires_new_params_only_when_signing(
    monkeypatch, deployed, signed, ok,
):
    import requests
    formats = {
        "p_db_version": "text", "p_pipeline_version": "text", "p_scoring_version": "text",
        "p_schema_version": "text", "p_product_count": "integer", "p_checksum": "text",
        "p_generated_at": "timestamp with time zone", "p_min_app_version": "text",
        "p_submission_approvals": "jsonb",
    }
    if deployed:
        formats.update({
            "p_release_sequence": "bigint", "p_signed_release": "text",
            "p_release_signature": "text",
        })
    schema = {"properties": {k: {"format": v} for k, v in formats.items()},
              "required": ["p_db_version"]}
    paths = {"/rpc/rotate_manifest_with_submission_approvals": {
        "post": {"parameters": [{"in": "body", "schema": schema}]}}}
    monkeypatch.setenv("SUPABASE_URL", "https://example.invalid")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-only-secret")
    monkeypatch.setattr(requests, "get", lambda *a, **k: SimpleNamespace(
        raise_for_status=lambda: None, json=lambda: {"paths": paths}))
    if ok:
        supabase_client.require_publication_contract(signed_release=signed)
    else:
        with pytest.raises(ValueError, match="publication contract"):
            supabase_client.require_publication_contract(signed_release=signed)


# --- sync seam -----------------------------------------------------------------------


@pytest.fixture()
def harness(monkeypatch, gate_file):
    """A sync with every remote call recorded, in order. No network."""
    events = []
    remote = SimpleNamespace(current=None, objects={}, older_releases=[])
    client = _RpcClient()

    def upload(_client, _bucket, path, local_path, **kwargs):
        events.append(("upload", path, kwargs.get("upsert")))
        remote.objects[path] = Path(local_path).read_bytes()

    def download(_client, _bucket, path):
        if path not in remote.objects:
            raise FileNotFoundError(path)
        return remote.objects[path]

    def list_paths(_client, _bucket, prefix, limit=1000, offset=0):
        if offset:
            return []
        return [{"name": path.rsplit("/", 1)[1]} for path in remote.objects
                if path.rsplit("/", 1)[0] == prefix]

    def contract(signed_release=False):
        events.append(("contract", signed_release))

    real_insert = supabase_client.insert_manifest

    def insert(*args, **kwargs):
        events.append(("insert", dict(kwargs)))
        return real_insert(*args, **kwargs)

    monkeypatch.setattr(supabase_client, "get_supabase_client", lambda: client)
    monkeypatch.setattr(supabase_client, "fetch_current_manifest", lambda _c: remote.current)
    monkeypatch.setattr(supabase_client, "fetch_manifest_version", lambda *_a: None)

    def latest_signed_rules(_client):
        for row in [remote.current or {}, *remote.older_releases]:
            text = row.get("signed_release")
            if text and json.loads(text).get("rules"):
                return json.loads(text)["rules"]
        return None

    monkeypatch.setattr(supabase_client, "fetch_latest_signed_rules", latest_signed_rules, raising=False)
    monkeypatch.setattr(supabase_client, "upload_file", upload)
    monkeypatch.setattr(supabase_client, "download_file", download)
    monkeypatch.setattr(supabase_client, "list_storage_paths", list_paths)
    monkeypatch.setattr(supabase_client, "require_publication_contract", contract)
    monkeypatch.setattr(supabase_client, "insert_manifest", insert)
    monkeypatch.setattr(sync, "validate_bucket_upload_capacity", lambda *_a, **_k: None)
    monkeypatch.setattr(sync, "discover_existing_remote_blob_paths", lambda *_a, **_k: set())
    monkeypatch.setattr(sync, "_publish_catalog_search_step", lambda *_a, **_k: None)
    monkeypatch.setattr(sync, "catalog_search_rows", lambda *_a, **_k: [])
    monkeypatch.setattr(sync, "_ensure_registry_validating", lambda *_a, **_k: None)
    monkeypatch.setattr(sync, "_promote_registry_release", lambda *_a, **_k: None)
    monkeypatch.setattr(sync, "_enforce_signed_rule_gate", lambda *_a, **_k: None)
    return SimpleNamespace(events=events, remote=remote, client=client)


def _uploads(harness):
    return [event for event in harness.events if event[0] == "upload"]


def _storage_writes_and_flips(harness):
    return [event for event in harness.events if event[0] in ("upload", "insert")]


def test_unsigned_sync_is_unchanged(tmp_path, harness):
    catalog = _make_catalog(tmp_path / "catalog")
    result = sync.sync(str(catalog), max_workers=1)
    assert result["status"] == "synced"
    assert "release_sequence" not in result
    # No signed contract check, no rules object, and the same insert call as today.
    assert ("contract", True) not in harness.events
    assert not any(event[1].startswith("rules/") for event in _uploads(harness))
    assert [e for e in harness.events if e[0] == "insert"] == [
        ("insert", {"submission_approvals": []})
    ]
    assert list(harness.client.calls[0][1]) == list(UNSIGNED_PARAMS)


def test_signed_sync_stages_rules_before_the_flip_and_sends_the_params(tmp_path, harness, key):
    _gate(rm.GATE_PATH, True, "Sean", "2026-12-01")
    catalog = _make_catalog(tmp_path / "catalog")
    rules = _make_rules(tmp_path / "rules")
    text = _build(catalog, rules)
    manifest, signature = _write_signed(tmp_path, text, key)

    result = sync.sync(
        str(catalog), max_workers=1, release_manifest=manifest,
        release_signature=signature, rules_dir=str(rules),
    )

    assert result["status"] == "synced"
    assert result["release_sequence"] == 5
    rules_path = f"rules/{RULES_VERSION}/interaction_db.sqlite"
    names = [event[1] if event[0] == "upload" else event[0] for event in harness.events]
    assert names.index("contract") == 0
    assert names.index(rules_path) < names.index("insert")
    # Create-only, the immutability rule every versioned object uses.
    assert ("upload", rules_path, False) in harness.events
    assert harness.client.calls[0][1] == {
        **UNSIGNED_PARAMS,
        "p_checksum": f"sha256:{_sha(catalog / 'pharmaguide_core.db')}",
        "p_release_sequence": 5,
        "p_signed_release": text,
        "p_release_signature": Path(signature).read_text(),
    }


def test_catalog_only_signed_sync_uploads_no_rules_even_with_the_gate_closed(
    tmp_path, harness, key,
):
    _gate(rm.GATE_PATH, False, None, None)
    catalog = _make_catalog(tmp_path / "catalog")
    manifest, signature = _write_signed(tmp_path, _build(catalog), key)
    result = sync.sync(
        str(catalog), max_workers=1, release_manifest=manifest, release_signature=signature,
    )
    assert result["status"] == "synced"
    assert not any(event[1].startswith("rules/") for event in _uploads(harness))
    assert harness.client.calls[0][1]["p_release_sequence"] == 5


@pytest.mark.parametrize("dry_run", [True, False])
def test_sync_refuses_rules_while_the_gate_is_closed(tmp_path, harness, key, dry_run):
    _gate(rm.GATE_PATH, False, None, None)
    catalog = _make_catalog(tmp_path / "catalog")
    rules = _make_rules(tmp_path / "rules")
    manifest, signature = _write_signed(tmp_path, _build(catalog, rules), key)
    with pytest.raises(rm.ReleaseManifestError, match="no A9 sign-off"):
        sync.sync(
            str(catalog), dry_run=dry_run, max_workers=1, release_manifest=manifest,
            release_signature=signature, rules_dir=str(rules),
        )
    assert harness.events == []


def test_sync_allows_rules_on_a_listed_test_project(tmp_path, harness, key):
    _gate(rm.GATE_PATH, False, None, None)
    catalog = _make_catalog(tmp_path / "catalog")
    rules = _make_rules(tmp_path / "rules")
    manifest, signature = _write_signed(tmp_path, _build(catalog, rules), key)
    result = sync.sync(
        str(catalog), max_workers=1, release_manifest=manifest, release_signature=signature,
        rules_dir=str(rules), test_project=True,
    )
    assert result["status"] == "synced"


@pytest.mark.parametrize("dry_run", [True, False])
def test_sync_refuses_a_signature_from_any_other_key_before_any_write(
    tmp_path, harness, key, dry_run,
):
    catalog = _make_catalog(tmp_path / "catalog")
    manifest, signature = _write_signed(tmp_path, _build(catalog), key, pin=())
    _pin(Ed25519PrivateKey.generate(), "production_keys")
    with pytest.raises(rm.ReleaseManifestError, match="does not verify"):
        sync.sync(
            str(catalog), dry_run=dry_run, max_workers=1,
            release_manifest=manifest, release_signature=signature,
        )
    assert harness.events == []


def test_sync_refuses_a_manifest_changed_after_signing(tmp_path, harness, key):
    catalog = _make_catalog(tmp_path / "catalog")
    manifest, signature = _write_signed(tmp_path, _build(catalog), key)
    # Still canonical and still this build; only the signature can catch it.
    Path(manifest).write_bytes(_build(catalog, sequence=6).encode("utf-8"))
    with pytest.raises(rm.ReleaseManifestError, match="does not verify"):
        sync.sync(
            str(catalog), max_workers=1, release_manifest=manifest, release_signature=signature,
        )
    assert harness.events == []


def test_sync_refuses_a_key_the_repo_does_not_pin(tmp_path, harness, key):
    catalog = _make_catalog(tmp_path / "catalog")
    manifest, signature = _write_signed(tmp_path, _build(catalog), key, pin=())
    with pytest.raises(rm.ReleaseManifestError, match="not pinned"):
        sync.sync(
            str(catalog), max_workers=1, release_manifest=manifest, release_signature=signature,
        )
    assert harness.events == []


def test_a_test_key_can_not_publish_to_production(tmp_path, harness, key):
    catalog = _make_catalog(tmp_path / "catalog")
    manifest, signature = _write_signed(tmp_path, _build(catalog), key, pin=("test_keys",))
    with pytest.raises(rm.ReleaseManifestError, match="not pinned"):
        sync.sync(
            str(catalog), max_workers=1, release_manifest=manifest, release_signature=signature,
        )
    assert harness.events == []


def test_a_production_key_is_not_a_test_key(tmp_path, harness, key):
    catalog = _make_catalog(tmp_path / "catalog")
    manifest, signature = _write_signed(tmp_path, _build(catalog), key, pin=("production_keys",))
    with pytest.raises(rm.ReleaseManifestError, match="not pinned"):
        sync.sync(
            str(catalog), max_workers=1, release_manifest=manifest,
            release_signature=signature, test_project=True,
        )
    assert harness.events == []


@pytest.mark.parametrize("dry_run", [True, False])
def test_once_a_production_key_is_pinned_unsigned_can_not_publish(tmp_path, harness, key, dry_run):
    _pin(key, "production_keys")
    catalog = _make_catalog(tmp_path / "catalog")
    with pytest.raises(rm.ReleaseManifestError, match="must be signed"):
        sync.sync(str(catalog), dry_run=dry_run, max_workers=1)
    assert harness.events == []


def test_an_unreadable_trust_file_stops_unsigned_publishing(tmp_path, harness, trust_file):
    trust_file.unlink()
    catalog = _make_catalog(tmp_path / "catalog")
    with pytest.raises(rm.ReleaseManifestError, match="release_trust.json"):
        sync.sync(str(catalog), max_workers=1)
    assert harness.events == []


@pytest.mark.parametrize("pinned,expected", [(False, 0), (True, 1)])
def test_unsigned_allowed_command_reports_the_rule(key, pinned, expected, capsys):
    if pinned:
        _pin(key, "production_keys")
    assert rm.main(["unsigned-allowed"]) == expected


def test_unsigned_allowed_command_fails_closed(trust_file):
    trust_file.unlink()
    assert rm.main(["unsigned-allowed"]) == 1


# --- release_full wiring -------------------------------------------------------------


RELEASE_FULL = Path(rm.__file__).parent / "release_full.sh"


def _signed_publish_gate(*, allowed, signed_args=""):
    source = RELEASE_FULL.read_text()
    start = source.index("require_signed_release_or_stop() {")
    end = source.index("\n}\n", start) + 3
    python = "true" if allowed else "false"
    return subprocess.run(
        ["bash", "-uc", f"""
err() {{ echo "$*" >&2; }}
PG_PYTHON={python}
DIST_DIR=/fake/dist
RELEASE_SIGN_ARGS=({signed_args})
{source[start:end]}
require_signed_release_or_stop || exit 1
echo reached-sync
"""],
        capture_output=True, text=True,
    )


def test_release_full_stops_before_sync_when_a_signature_is_owed():
    result = _signed_publish_gate(allowed=False)
    assert result.returncode == 1
    assert "reached-sync" not in result.stdout
    assert "--release-manifest" in result.stderr and "sign" in result.stderr


def test_release_full_goes_on_when_unsigned_is_still_allowed():
    result = _signed_publish_gate(allowed=True)
    assert result.returncode == 0 and "reached-sync" in result.stdout


def test_release_full_goes_on_with_a_signed_release_and_leaves_checking_to_sync():
    result = _signed_publish_gate(allowed=False, signed_args="--release-manifest a --release-signature b")
    assert result.returncode == 0 and "reached-sync" in result.stdout


def test_every_release_full_sync_carries_the_signed_arguments():
    source = RELEASE_FULL.read_text()
    calls = re.findall(r'scripts/sync_to_supabase\.py "\$DIST_DIR"(?:[^\n]*\\\n)*[^\n]*', source)
    assert len(calls) == 2
    for call in calls:
        assert '${RELEASE_SIGN_ARGS[@]+"${RELEASE_SIGN_ARGS[@]}"}' in call
    gate = source.index("require_signed_release_or_stop || exit 1")
    assert gate < source.index('scripts/sync_to_supabase.py "$DIST_DIR"')


def test_release_full_gives_a_signed_sync_the_app_pin_to_compare_rules_with():
    source = RELEASE_FULL.read_text()
    forward = source.index('RELEASE_SIGN_ARGS+=(--rule-pin "$FLUTTER_REPO/tool/interaction_db.release.json")')
    assert forward < source.index('scripts/sync_to_supabase.py "$DIST_DIR"')


def test_sync_refuses_a_manifest_for_another_build_before_any_write(tmp_path, harness, key):
    other = _make_catalog(tmp_path / "other", version="2026.10.02.120000")
    catalog = _make_catalog(tmp_path / "catalog")
    manifest, signature = _write_signed(tmp_path, _build(other), key)
    with pytest.raises(rm.ReleaseManifestError, match="catalog.version"):
        sync.sync(
            str(catalog), max_workers=1, release_manifest=manifest, release_signature=signature,
        )
    assert harness.events == []


def test_sync_refuses_a_changed_rules_file_before_any_write(tmp_path, harness, key):
    _gate(rm.GATE_PATH, True, "Sean", "2026-12-01")
    catalog = _make_catalog(tmp_path / "catalog")
    rules = _make_rules(tmp_path / "rules")
    manifest, signature = _write_signed(tmp_path, _build(catalog, rules), key)
    (rules / "interaction_db.sqlite").write_bytes(b"swapped after signing")
    with pytest.raises(rm.ReleaseManifestError, match="rules.sha256"):
        sync.sync(
            str(catalog), max_workers=1, release_manifest=manifest,
            release_signature=signature, rules_dir=str(rules),
        )
    assert harness.events == []


def test_sync_refuses_to_replace_an_existing_rules_object(tmp_path, harness, key):
    _gate(rm.GATE_PATH, True, "Sean", "2026-12-01")
    catalog = _make_catalog(tmp_path / "catalog")
    rules = _make_rules(tmp_path / "rules")
    harness.remote.objects[f"rules/{RULES_VERSION}/interaction_db.sqlite"] = b"different"
    manifest, signature = _write_signed(tmp_path, _build(catalog, rules), key)
    with pytest.raises(ValueError, match="immutable"):
        sync.sync(
            str(catalog), max_workers=1, release_manifest=manifest,
            release_signature=signature, rules_dir=str(rules),
        )
    assert _storage_writes_and_flips(harness) == []


def test_sync_reuses_an_identical_rules_object_on_retry(tmp_path, harness, key):
    _gate(rm.GATE_PATH, True, "Sean", "2026-12-01")
    catalog = _make_catalog(tmp_path / "catalog")
    rules = _make_rules(tmp_path / "rules")
    rules_path = f"rules/{RULES_VERSION}/interaction_db.sqlite"
    harness.remote.objects[rules_path] = (rules / "interaction_db.sqlite").read_bytes()
    manifest, signature = _write_signed(tmp_path, _build(catalog, rules), key)
    result = sync.sync(
        str(catalog), max_workers=1, release_manifest=manifest,
        release_signature=signature, rules_dir=str(rules),
    )
    assert result["status"] == "synced"
    assert not any(event[1] == rules_path for event in _uploads(harness))


@pytest.mark.parametrize("remote_sequence, match", [
    (6, "older than the current"),
    (5, "already published with different content"),
])
def test_sync_refuses_a_stale_sequence_before_any_write(
    tmp_path, harness, key, remote_sequence, match,
):
    catalog = _make_catalog(tmp_path / "catalog")
    manifest, signature = _write_signed(tmp_path, _build(catalog), key)
    harness.remote.current = {
        "db_version": "2026.09.01.000000", "checksum": "sha256:old",
        "release_sequence": remote_sequence, "signed_release": "{}",
    }
    with pytest.raises(ValueError, match=match):
        sync.sync(
            str(catalog), max_workers=1, release_manifest=manifest, release_signature=signature,
        )
    assert _storage_writes_and_flips(harness) == []


def test_signed_release_on_the_current_catalog_still_publishes_its_new_sequence(
    tmp_path, harness, key,
):
    catalog = _make_catalog(tmp_path / "catalog")
    local = json.loads((catalog / "export_manifest.json").read_text())
    harness.remote.current = {
        "db_version": local["db_version"], "checksum": local["checksum"],
        "release_sequence": 4, "signed_release": "{}",
    }
    manifest, signature = _write_signed(tmp_path, _build(catalog), key)
    result = sync.sync(
        str(catalog), max_workers=1, release_manifest=manifest, release_signature=signature,
    )
    assert result["status"] == "synced"
    assert harness.client.calls[0][1]["p_release_sequence"] == 5


def test_rerun_of_the_same_signed_release_does_not_rotate(tmp_path, harness, key):
    catalog = _make_catalog(tmp_path / "catalog")
    local = json.loads((catalog / "export_manifest.json").read_text())
    text = _build(catalog)
    manifest, signature = _write_signed(tmp_path, text, key)
    harness.remote.current = {
        "db_version": local["db_version"], "checksum": local["checksum"],
        "release_sequence": 5, "signed_release": text,
    }
    result = sync.sync(
        str(catalog), max_workers=1, release_manifest=manifest, release_signature=signature,
    )
    assert result == {"status": "up_to_date", "version": local["db_version"]}
    assert harness.client.calls == []


def test_dry_run_reports_the_signed_release_without_touching_supabase(
    tmp_path, harness, key, capsys,
):
    _gate(rm.GATE_PATH, True, "Sean", "2026-12-01")
    catalog = _make_catalog(tmp_path / "catalog")
    rules = _make_rules(tmp_path / "rules")
    manifest, signature = _write_signed(tmp_path, _build(catalog, rules), key)
    result = sync.sync(
        str(catalog), dry_run=True, release_manifest=manifest,
        release_signature=signature, rules_dir=str(rules),
    )
    assert result["release_sequence"] == 5
    out = capsys.readouterr().out
    assert "sequence 5" in out
    assert f"rules/{RULES_VERSION}/interaction_db.sqlite (create-only" in out
    assert "A9 sign-off recorded" in out
    assert "p_release_sequence" in out
    assert harness.events == []


def test_unsigned_dry_run_result_has_no_signed_fields(tmp_path, harness, capsys):
    result = sync.sync(str(_make_catalog(tmp_path / "catalog")), dry_run=True)
    assert result["status"] == "dry_run"
    assert "release_sequence" not in result
    assert "Signed release" not in capsys.readouterr().out


@pytest.mark.parametrize("argv", [
    ["build", "--release-manifest", "m"],
    ["build", "--release-signature", "s"],
    ["build", "--rules-dir", "r"],
    ["build", "--test-project"],
    ["--preflight-only", "--release-manifest", "m", "--release-signature", "s"],
])
def test_cli_refuses_incomplete_signed_flags(argv):
    with pytest.raises(SystemExit):
        sync.parse_args(argv)


def test_main_reports_a_malformed_manifest_as_a_configuration_error(tmp_path, harness, capsys):
    catalog = _make_catalog(tmp_path / "catalog")
    manifest = tmp_path / "bad.json"
    manifest.write_text("{not json")
    signature = tmp_path / "bad.sig"
    signature.write_text(f"{KEY_ID}:x")
    with pytest.raises(SystemExit) as exit_info:
        sync.main([
            str(catalog), "--release-manifest", str(manifest),
            "--release-signature", str(signature),
        ])
    assert exit_info.value.code == 1
    assert "Configuration error" in capsys.readouterr().err
    assert harness.events == []


# --- rollback ------------------------------------------------------------------------


def _rows(db_path, table):
    conn = sqlite3.connect(db_path)
    try:
        return sorted(conn.execute(f"SELECT * FROM {table}").fetchall(), key=str)  # noqa: S608
    finally:
        conn.close()


def test_rollback_stamps_a_newer_version_and_keeps_the_rows(tmp_path):
    source = _make_catalog(tmp_path / "good")
    before = (source / "pharmaguide_core.db").read_bytes()
    output = tmp_path / "rollback"
    result = rm.prepare_rollback(
        source, output, db_version="2026.11.02.120000", newer_than="2026.11.01.000000",
    )

    new_db = output / "pharmaguide_core.db"
    manifest = json.loads((output / "export_manifest.json").read_text())
    assert result["db_version"] == manifest["db_version"] == "2026.11.02.120000"
    assert manifest["checksum"] == f"sha256:{_sha(new_db)}"
    embedded = dict(_rows(new_db, "export_manifest"))
    assert embedded["db_version"] == "2026.11.02.120000"
    assert embedded["generated_at"] == manifest["generated_at"]
    assert embedded["schema_version"] == "2.5.0"
    assert _rows(new_db, "products_core") == _rows(source / "pharmaguide_core.db", "products_core")
    # The known-good build is untouched.
    assert (source / "pharmaguide_core.db").read_bytes() == before
    assert not (tmp_path / "rollback.staging").exists()


def test_rollback_build_passes_sync_validation_and_can_be_signed(tmp_path, key, harness):
    source = _make_catalog(tmp_path / "good")
    output = tmp_path / "rollback"
    rm.prepare_rollback(source, output, db_version="2026.11.02.120000")

    local = sync.load_local_manifest(str(output))
    stats = sync.validate_build_output(str(output), local)
    assert stats["blob_count"] == 2
    assert (output / "detail_index.json").read_bytes() == (source / "detail_index.json").read_bytes()
    assert (output / "detail_blobs").is_symlink()

    text = _build(output, sequence=9, block_catalog=["2026.11.01.000000"])
    manifest, signature = _write_signed(tmp_path, text, key)
    result = sync.sync(
        str(output), dry_run=True, release_manifest=manifest, release_signature=signature,
    )
    assert result["version"] == "2026.11.02.120000"
    # Sync regenerates the share index with the new version inside.
    shard = json.loads((output / "share_index" / "00.json").read_text())
    assert shard["catalogVersion"] == "2026.11.02.120000"
    assert not (source / "share_index").exists()


def _add_version_bound_images(build, version=CATALOG_VERSION):
    """Images as the extractor leaves them: paths in the index and the DB name the version."""
    images = build / "product_images"
    images.mkdir()
    index = {}
    for dsld_id in ("1", "2"):
        (images / f"{dsld_id}.webp").write_bytes(b"webp-" + dsld_id.encode())
        index[dsld_id] = {"filename": f"{dsld_id}.webp", "remote_path": f"v{version}/{dsld_id}.webp"}
    (images / "product_image_index.json").write_text(json.dumps(index))
    conn = sqlite3.connect(build / "pharmaguide_core.db")
    with conn:
        conn.execute("ALTER TABLE products_core ADD COLUMN image_thumbnail_url TEXT")
        conn.execute(
            "UPDATE products_core SET image_thumbnail_url = 'product-images/v' || ? || '/' || dsld_id || '.webp'",
            (version,),
        )
    conn.close()
    manifest = json.loads((build / "export_manifest.json").read_text())
    manifest["checksum"] = f"sha256:{_sha(build / 'pharmaguide_core.db')}"
    (build / "export_manifest.json").write_text(json.dumps(manifest))


def test_rollback_moves_version_bound_images_to_the_new_version(tmp_path, key, harness):
    source = _make_catalog(tmp_path / "good")
    _add_version_bound_images(source)
    source_index = (source / "product_images" / "product_image_index.json").read_bytes()
    new_version = "2026.11.02.120000"
    output = tmp_path / "rollback"
    rm.prepare_rollback(source, output, db_version=new_version)

    index = json.loads((output / "product_images" / "product_image_index.json").read_text())
    assert {entry["remote_path"] for entry in index.values()} == {
        f"v{new_version}/1.webp", f"v{new_version}/2.webp",
    }
    assert (output / "product_images" / "1.webp").read_bytes() == b"webp-1"
    assert (source / "product_images" / "product_image_index.json").read_bytes() == source_index
    conn = sqlite3.connect(output / "pharmaguide_core.db")
    urls = {row[0] for row in conn.execute("SELECT image_thumbnail_url FROM products_core")}
    conn.close()
    assert urls == {
        f"product-images/v{new_version}/1.webp", f"product-images/v{new_version}/2.webp",
    }

    manifest, signature = _write_signed(tmp_path, _build(output, sequence=9), key)
    result = sync.sync(
        str(output), max_workers=1, release_manifest=manifest, release_signature=signature,
    )
    assert result["status"] == "synced"
    assert ("upload", f"v{new_version}/1.webp", False) in harness.events


def test_rollback_leaves_unversioned_image_urls_alone(tmp_path):
    source = _make_catalog(tmp_path / "good")
    conn = sqlite3.connect(source / "pharmaguide_core.db")
    with conn:
        conn.execute("ALTER TABLE products_core ADD COLUMN image_thumbnail_url TEXT")
        conn.execute("UPDATE products_core SET image_thumbnail_url = 'product-images/1.webp'")
    conn.close()
    manifest = json.loads((source / "export_manifest.json").read_text())
    manifest["checksum"] = f"sha256:{_sha(source / 'pharmaguide_core.db')}"
    (source / "export_manifest.json").write_text(json.dumps(manifest))
    output = tmp_path / "rollback"
    rm.prepare_rollback(source, output, db_version="2026.11.02.120000")
    conn = sqlite3.connect(output / "pharmaguide_core.db")
    assert {r[0] for r in conn.execute("SELECT image_thumbnail_url FROM products_core")} == {
        "product-images/1.webp",
    }
    conn.close()


def _rule_gate_setup(tmp_path, key):
    _gate(rm.GATE_PATH, True, "Sean", "2026-12-01")
    catalog = _make_catalog(tmp_path / "catalog")
    rules = _make_rules(tmp_path / "rules")
    manifest, signature = _write_signed(tmp_path, _build(catalog, rules), key)
    return catalog, rules, manifest, signature


@pytest.fixture()
def rule_gate(monkeypatch):
    """Records what the real gate is asked to compare, and answers as told."""
    import rule_change_gate

    seen = SimpleNamespace(baseline=None, candidate=None, errors=[])

    def check(candidate, baseline, **_kwargs):
        seen.candidate = Path(candidate).read_bytes()
        seen.baseline = Path(baseline).read_bytes()
        return rule_change_gate.GateResult(errors=list(seen.errors))

    monkeypatch.setattr(sync, "_enforce_signed_rule_gate", _REAL_SIGNED_RULE_GATE)
    monkeypatch.setattr(rule_change_gate, "check_rule_changes", check)
    return seen


def test_a_held_rule_change_stops_a_signed_rules_release_before_any_write(
    tmp_path, harness, key, rule_gate,
):
    catalog, rules, manifest, signature = _rule_gate_setup(tmp_path, key)
    previous = b"rules-the-phones-hold"
    harness.remote.objects["rules/1.0.14/interaction_db.sqlite"] = previous
    harness.remote.current = {
        "db_version": "2026.09.01.000000", "checksum": "sha256:other", "release_sequence": 4,
        "signed_release": json.dumps({
            "rules": {"path": "rules/1.0.14/interaction_db.sqlite",
                      "sha256": hashlib.sha256(previous).hexdigest()},
        }),
    }
    rule_gate.errors = ["RULE: raised to avoid with no alert"]
    with pytest.raises(ValueError, match="raised to avoid"):
        sync.sync(str(catalog), max_workers=1, release_manifest=manifest,
                  release_signature=signature, rules_dir=str(rules))
    assert rule_gate.baseline == previous
    assert rule_gate.candidate == (rules / "interaction_db.sqlite").read_bytes()
    assert _uploads(harness) == []
    assert harness.client.calls == []


def test_the_first_signed_rules_release_compares_with_the_app_pin(
    tmp_path, harness, key, rule_gate, monkeypatch,
):
    import rule_change_gate

    catalog, rules, manifest, signature = _rule_gate_setup(tmp_path, key)
    pin = tmp_path / "interaction_db.release.json"
    pin.write_text(json.dumps({"url": "https://example.test/rules", "sha256": "abc"}))

    def fetch(named, destination):
        assert named["sha256"] == "abc"
        Path(destination).write_bytes(b"bundled-rules")

    monkeypatch.setattr(rule_change_gate, "fetch_pinned_db", fetch)
    result = sync.sync(str(catalog), max_workers=1, release_manifest=manifest,
                       release_signature=signature, rules_dir=str(rules),
                       rule_pin=str(pin))
    assert result["status"] == "synced"
    assert rule_gate.baseline == b"bundled-rules"


def test_a_catalog_only_release_does_not_reset_the_rules_phones_hold(
    tmp_path, harness, key, rule_gate, monkeypatch,
):
    """Withdrawing a rule after a catalog-only release must still need its alert."""
    import rule_change_gate

    catalog, rules, manifest, signature = _rule_gate_setup(tmp_path, key)
    held = b"rules-from-the-last-release-that-named-rules"
    harness.remote.objects["rules/1.0.14/interaction_db.sqlite"] = held
    harness.remote.current = {
        "db_version": "2026.09.02.000000", "checksum": "sha256:other", "release_sequence": 4,
        "signed_release": json.dumps({"rules": None}),
    }
    harness.remote.older_releases = [{
        "signed_release": json.dumps({
            "rules": {"path": "rules/1.0.14/interaction_db.sqlite",
                      "sha256": hashlib.sha256(held).hexdigest()},
        }),
    }]
    pin = tmp_path / "interaction_db.release.json"
    pin.write_text(json.dumps({"url": "https://example.test/rules", "sha256": "abc"}))
    monkeypatch.setattr(
        rule_change_gate, "fetch_pinned_db",
        lambda _named, destination: Path(destination).write_bytes(b"older-app-pin"),
    )
    sync.sync(str(catalog), max_workers=1, release_manifest=manifest,
              release_signature=signature, rules_dir=str(rules), rule_pin=str(pin))
    assert rule_gate.baseline == held


class _SignedManifestRows:
    """export_manifest as PostgREST serves it: newest first, one range at a time."""

    def __init__(self, releases):
        self.rows = [{"signed_release": json.dumps(release)} for release in releases]
        self.sent = []
        self.not_ = self
        self.window = (0, 999)

    def __getattr__(self, name):
        def step(*args, **kwargs):
            self.sent.append((name, args, kwargs))
            return self
        return step

    def range(self, start, end):
        self.window = (start, end)
        return self

    def execute(self):
        start, end = self.window
        return SimpleNamespace(data=self.rows[start:min(end + 1, start + 1000)])

    def client(self):
        return SimpleNamespace(table=lambda name: self if name == "export_manifest" else None)


def _named_rules(version, blocked=()):
    return {
        "rules": {"version": version, "path": f"rules/{version}"},
        "blocked_versions": {"catalog": [], "rules": list(blocked)},
    }


def _catalog_only(blocked=()):
    return {"rules": None, "blocked_versions": {"catalog": [], "rules": list(blocked)}}


def test_latest_signed_rules_skips_catalog_only_releases_newest_first():
    rows = _SignedManifestRows([
        _catalog_only(), _named_rules("1.0.20"), _named_rules("1.0.19"),
    ])
    assert supabase_client.fetch_latest_signed_rules(rows.client())["version"] == "1.0.20"
    assert ("order", ("release_sequence",), {"desc": True}) in rows.sent


def test_latest_signed_rules_reads_past_one_page_of_catalog_only_releases():
    rows = _SignedManifestRows([_catalog_only()] * 1000 + [_named_rules("1.0.20")])
    assert supabase_client.fetch_latest_signed_rules(rows.client())["version"] == "1.0.20"


def test_latest_signed_rules_skips_rules_the_newest_release_blocks():
    """A rule kept from a blocked file must count as new, so its gate still runs."""
    rows = _SignedManifestRows([
        _catalog_only(blocked=["1.0.20"]), _named_rules("1.0.20"), _named_rules("1.0.19"),
    ])
    assert supabase_client.fetch_latest_signed_rules(rows.client())["version"] == "1.0.19"


def test_latest_signed_rules_counts_a_lifted_block_as_lifted():
    """Phones replace their list with the newest release's, so older lists don't count."""
    rows = _SignedManifestRows([
        _catalog_only(), _catalog_only(blocked=["1.0.20"]), _named_rules("1.0.20"),
    ])
    assert supabase_client.fetch_latest_signed_rules(rows.client())["version"] == "1.0.20"


def test_latest_signed_rules_is_none_when_every_named_rules_file_is_blocked():
    rows = _SignedManifestRows([_catalog_only(blocked=["1.0.20"]), _named_rules("1.0.20")])
    assert supabase_client.fetch_latest_signed_rules(rows.client()) is None


def test_a_signed_rules_release_with_no_baseline_is_refused(tmp_path, harness, key, rule_gate):
    catalog, rules, manifest, signature = _rule_gate_setup(tmp_path, key)
    with pytest.raises(ValueError, match="--rule-pin"):
        sync.sync(str(catalog), max_workers=1, release_manifest=manifest,
                  release_signature=signature, rules_dir=str(rules))
    assert _uploads(harness) == []


def test_a_baseline_that_does_not_match_its_release_is_refused(tmp_path, harness, key, rule_gate):
    catalog, rules, manifest, signature = _rule_gate_setup(tmp_path, key)
    harness.remote.objects["rules/1.0.14/interaction_db.sqlite"] = b"altered"
    harness.remote.current = {
        "db_version": "2026.09.01.000000", "checksum": "sha256:other", "release_sequence": 4,
        "signed_release": json.dumps({
            "rules": {"path": "rules/1.0.14/interaction_db.sqlite", "sha256": "0" * 64},
        }),
    }
    with pytest.raises(ValueError, match="does not match"):
        sync.sync(str(catalog), max_workers=1, release_manifest=manifest,
                  release_signature=signature, rules_dir=str(rules))
    assert _uploads(harness) == []


def test_rollback_default_version_comes_from_the_build_owner(tmp_path):
    result = rm.prepare_rollback(_make_catalog(tmp_path / "good"), tmp_path / "rollback")
    assert rm.CATALOG_VERSION_PATTERN.fullmatch(result["db_version"])
    assert result["db_version"] > CATALOG_VERSION


@pytest.mark.parametrize("kwargs", [
    {"db_version": CATALOG_VERSION},
    {"db_version": "2026.09.01.000000"},
    {"db_version": "2026.11.02.120000", "newer_than": "2026.11.02.120000"},
])
def test_rollback_refuses_a_version_that_older_builds_would_ignore(tmp_path, kwargs):
    output = tmp_path / "rollback"
    with pytest.raises(rm.ReleaseManifestError, match="not newer"):
        rm.prepare_rollback(_make_catalog(tmp_path / "good"), output, **kwargs)
    assert not output.exists()


def test_rollback_refuses_a_source_that_does_not_match_its_manifest(tmp_path):
    source = _make_catalog(tmp_path / "good")
    with open(source / "pharmaguide_core.db", "ab") as handle:
        handle.write(b"x")
    with pytest.raises(rm.ReleaseManifestError, match="does not match"):
        rm.prepare_rollback(source, tmp_path / "rollback", db_version="2026.11.02.120000")


def test_rollback_refuses_an_existing_output_dir(tmp_path):
    source = _make_catalog(tmp_path / "good")
    output = tmp_path / "rollback"
    output.mkdir()
    with pytest.raises(rm.ReleaseManifestError, match="already exists"):
        rm.prepare_rollback(source, output, db_version="2026.11.02.120000")


# The app's test/services/release/release_manifest_test.dart pins these same
# values, so a change to the canonical text fails in one repo or the other.
_APP_PINNED_PUBLIC_KEY = "8ec0368289f32dbbada878000f19fb5f2f08e9c4c9630489fd9d011138d31014"
_APP_PINNED_RELEASES = [
    (
        "{\"blocked_versions\":{\"catalog\":[\"2026.11.02.000000\"],\"rules\":[\"1.0.14\"]},\"catalog\":{\"min_app_version\":\"1.0.0\",\"path\":\"v2026.11.03.120000/pharmaguide_core.db\",\"schema_version\":\"5.3.0\",\"sha256\":\"652f55016243bf1b9f1bbea46d5749ef892dbe394e46de9d66ab1aacf0b4af57\",\"version\":\"2026.11.03.120000\"},\"format\":1,\"key_id\":\"vector-key-1\",\"min_rules_version\":\"1.0.15\",\"release_sequence\":42,\"rules\":{\"min_app_version\":\"1.0.0\",\"path\":\"rules/1.0.16/interaction_db.sqlite\",\"schema_version\":\"4.0.0\",\"sha256\":\"6c621d1a05138a7888d37d9269a9da8e2e11e4aced2f6cfd24b05ab1b9e61bb0\",\"version\":\"1.0.16\"}}",
        "vector-key-1:Hjk2pCMD50dxcq72BBmWEjeZ/idZxuwHUVC8rRVQDzwcWDt3aCmPb1Jgz3PGalvBALHb7g1hbvKJBixo74lCAw==",
    ),
    (
        "{\"blocked_versions\":{\"catalog\":[\"2026.11.02.000000\"],\"rules\":[\"1.0.14\"]},\"catalog\":{\"min_app_version\":\"1.0.0\",\"path\":\"v2026.11.03.120000/pharmaguide_core.db\",\"schema_version\":\"5.3.0\",\"sha256\":\"652f55016243bf1b9f1bbea46d5749ef892dbe394e46de9d66ab1aacf0b4af57\",\"version\":\"2026.11.03.120000\"},\"format\":1,\"key_id\":\"vector-key-1\",\"min_rules_version\":\"1.0.15\",\"release_sequence\":42,\"rules\":null}",
        "vector-key-1:mIgDvhdypUq6lBFzUi46OROmrleTgGkX/sg9rk4g8ydsdtt+zqhQMjqeQ300NYfsloqo3ZAf+2ivOTnfU9iLDQ==",
    ),
]


@pytest.mark.parametrize("text,signature", _APP_PINNED_RELEASES)
def test_output_matches_what_the_app_pins(text, signature):
    public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(_APP_PINNED_PUBLIC_KEY))
    assert rm.canonical_text(json.loads(text)) == text
    rm.verify_release(text, signature, public_key)
