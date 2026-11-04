"""Safety-alert feed publication must remain independent from catalog sync."""

import hashlib
import json
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import build_safety_alerts as publisher
import release_manifest
import sync_safety_alerts
from sync_safety_alerts import load_staged_release


SCRIPT = Path(__file__).resolve().parents[1] / "sync_safety_alerts.py"
RUNNER = Path(__file__).resolve().parents[1] / "run_safety_alert_publish.sh"
# Pinned in scripts/tests/test_safety_alerts_publisher.py and the app's tests.
FAKE_BASE_FEED_SHA256 = "sha256:7564e689beaa6fe47a794d3121ac715c211a487476098e3c80c6b0bde2a940c5"
FAKE_EXTENDED_FEED_SHA256 = "sha256:e0f20b54bcdf8aa77eef02c2c8420644adb390510546f8121e8e3359f3c1eb8f"
FAKE_SIGNED_STATEMENT = (
    '{"base_feed":{"checksum":"sha256:7564e689beaa6fe47a794d3121ac715c211a487476098e3c80c6b0bde2a940c5",'
    '"path":"safety-alerts/sha256/7564e689beaa6fe47a794d3121ac715c211a487476098e3c80c6b0bde2a940c5.json"},'
    '"extended_feed":{"checksum":"sha256:e0f20b54bcdf8aa77eef02c2c8420644adb390510546f8121e8e3359f3c1eb8f",'
    '"path":"safety-alerts/sha256/e0f20b54bcdf8aa77eef02c2c8420644adb390510546f8121e8e3359f3c1eb8f.json"},'
    '"format":1,"key_id":"alert-feed-test","purpose":"safety_alert_feed","release_sequence":7}'
)
FAKE_SIGNED_SIGNATURE = (
    "alert-feed-test:NvakCzcQUs9jnDjhng2OJzMIgnBOoNzTu/zGCJ410aHW8G6b1d6FHbOXMSQPxgEN3bZdzjR6+9mHIOy9tSe+AQ=="
)


@pytest.fixture(autouse=True)
def alert_trust(tmp_path_factory, monkeypatch):
    """A trust file pinning only the published test key. Call it to change a group."""
    path = tmp_path_factory.mktemp("trust") / "release_trust.json"

    def write(**groups):
        path.write_text(json.dumps({
            "production_project_ref": "omayamxacvacrnvdvzhr",
            "test_hosts": ["127.0.0.1", "localhost"],
            "production_keys": {},
            "test_keys": {},
            "alert_feed_keys": {TEST_KEY_ID: TEST_PUBLIC_HEX},
            **groups,
        }), encoding="utf-8")

    write()
    monkeypatch.setattr(release_manifest, "TRUST_PATH", path)
    return write


def test_independent_safety_alert_publisher_is_shipped():
    assert SCRIPT.is_file(), "safety alerts need an independently invocable publisher"
    assert RUNNER.is_file(), "human-approved alerts need one safe fast-lane command"
    assert "build_safety_alerts.py --stage" in RUNNER.read_text(encoding="utf-8")
    assert "sync_safety_alerts.py" in RUNNER.read_text(encoding="utf-8")


def test_staged_release_rejects_a_feed_that_no_longer_matches_its_manifest(tmp_path):
    feed = b'{"alerts": []}\n'
    (tmp_path / "safety_alerts.json").write_bytes(feed)
    (tmp_path / "safety_alerts_manifest.json").write_text(
        json.dumps(
            {
                "checksum": "sha256:" + "0" * 64,
                "feed_version": "sha256:" + "0" * 64,
                "latest_revisions": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="checksum mismatch"):
        load_staged_release(tmp_path)


def test_staged_release_uses_a_content_addressed_remote_path(tmp_path):
    feed = b'{"alerts": []}\n'
    checksum = "sha256:" + hashlib.sha256(feed).hexdigest()
    (tmp_path / "safety_alerts.json").write_bytes(feed)
    (tmp_path / "safety_alerts_manifest.json").write_text(
        json.dumps(
            {
                "checksum": checksum,
                "feed_version": checksum,
                "latest_revisions": {},
            }
        ),
        encoding="utf-8",
    )

    _sign_staged(tmp_path)
    staged = load_staged_release(tmp_path)

    assert staged["remote_path"] == f"safety-alerts/sha256/{checksum.removeprefix('sha256:')}.json"


class _FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body
        self.text = body if isinstance(body, str) else json.dumps(body)

    def json(self):
        if isinstance(self._body, str):
            raise ValueError("not json")
        return self._body


def _dispatch_with(monkeypatch, response):
    import requests

    from sync_safety_alerts import _dispatch_release

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SAFETY_ALERT_DISPATCH_SECRET", "test-secret")
    monkeypatch.setattr(requests, "post", lambda *a, **k: response)
    _dispatch_release("00000000-0000-4000-8000-000000000000")


def test_dispatch_accepts_only_an_explicit_ok_body(monkeypatch):
    _dispatch_with(
        monkeypatch,
        _FakeResponse(200, {"ok": True, "sent": 2, "failed": 0, "removed": 0}),
    )


def test_dispatch_http_success_with_failed_sends_still_raises(monkeypatch):
    # A 200 with ok=false (or a 502 body) means deliveries stayed queued;
    # the release pipeline must halt so the operator re-runs dispatch.
    with pytest.raises(RuntimeError, match="undelivered"):
        _dispatch_with(
            monkeypatch,
            _FakeResponse(200, {"ok": False, "sent": 1, "failed": 3, "removed": 0}),
        )


def test_dispatch_transport_error_raises(monkeypatch):
    with pytest.raises(RuntimeError, match="HTTP 502"):
        _dispatch_with(
            monkeypatch,
            _FakeResponse(502, {"ok": False, "sent": 0, "failed": 4, "removed": 0}),
        )


def test_dispatch_unreadable_body_raises(monkeypatch):
    with pytest.raises(RuntimeError, match="unreadable"):
        _dispatch_with(monkeypatch, _FakeResponse(200, "<html>gateway</html>"))


# --- the extended feed --------------------------------------------------------

FIXTURES = Path(__file__).parent / "fixtures" / "safety_alerts"


def _stage_all(dist_dir):
    records = [
        json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        for name in ("SA_9999_0001.json", "SA_9999_0002.json", "SA_9999_0003.json", "SA_9999_0004.json")
    ]
    return publisher.stage(records, "2026-11-03", dist_dir)


@pytest.mark.parametrize("missing", ["SUPABASE_URL", "SAFETY_ALERT_DISPATCH_SECRET"])
def test_missing_dispatch_config_stops_before_any_remote_operation(tmp_path, monkeypatch, missing):
    import env_loader  # noqa: F401 — load before clearing the test environment

    _stage_all(tmp_path)
    _sign_staged(tmp_path)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SAFETY_ALERT_DISPATCH_SECRET", "test-secret")
    monkeypatch.delenv(missing, raising=False)
    events = []

    def unexpected_client():
        events.append("client")
        raise AssertionError("publication reached the remote client without dispatch configuration")

    monkeypatch.setattr(sync_safety_alerts, "get_supabase_client", unexpected_client)
    with pytest.raises(RuntimeError, match="required to dispatch"):
        sync_safety_alerts.sync(tmp_path)
    assert events == []


def test_dry_run_needs_no_dispatch_credentials_or_remote_client(tmp_path, monkeypatch):
    _stage_all(tmp_path)
    _sign_staged(tmp_path)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SAFETY_ALERT_DISPATCH_SECRET", raising=False)

    def unexpected_client():
        raise AssertionError("dry run contacted the remote client")

    monkeypatch.setattr(sync_safety_alerts, "get_supabase_client", unexpected_client)
    assert sync_safety_alerts.sync(tmp_path, dry_run=True)["status"] == "dry_run"


def test_staged_release_verifies_the_extended_feed(tmp_path):
    staged = _stage_all(tmp_path)
    _sign_staged(tmp_path)
    loaded = load_staged_release(tmp_path)
    digest = staged["extended_feed"]["checksum"].removeprefix("sha256:")
    assert loaded["extended_remote_path"] == f"safety-alerts/sha256/{digest}.json"
    assert loaded["extended_feed_path"] == tmp_path / publisher.EXTENDED_FEED_FILENAME

    (tmp_path / publisher.EXTENDED_FEED_FILENAME).write_text("{}")
    with pytest.raises(ValueError, match="extended"):
        load_staged_release(tmp_path)


def test_staged_release_needs_its_extended_feed(tmp_path):
    _stage_all(tmp_path)
    (tmp_path / publisher.EXTENDED_FEED_FILENAME).unlink()
    with pytest.raises(FileNotFoundError):
        load_staged_release(tmp_path)


def test_staged_release_refuses_a_rule_in_the_feed_old_builds_read(tmp_path):
    """Old builds reject the whole feed on this event, and the old dispatcher reads it."""
    feed = json.dumps({"alerts": [{"event_type": "interaction_rule"}]}).encode()
    checksum = "sha256:" + hashlib.sha256(feed).hexdigest()
    (tmp_path / "safety_alerts.json").write_bytes(feed)
    (tmp_path / "safety_alerts_manifest.json").write_text(
        json.dumps({"checksum": checksum, "feed_version": checksum, "latest_revisions": {}}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="interaction_rule"):
        load_staged_release(tmp_path)


def test_sync_uploads_the_extended_feed_before_promoting(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SAFETY_ALERT_DISPATCH_SECRET", "test-secret")
    staged = _stage_all(tmp_path)
    _sign_staged(tmp_path)
    events = []

    class _Query:
        def __init__(self, table):
            self.table_name = table
            self.inserted = None

        def select(self, *_):
            return self

        def eq(self, *_):
            return self

        def limit(self, *_):
            return self

        def insert(self, row):
            self.inserted = row
            events.append(("insert", row))
            return self

        def execute(self):
            class _Response:
                data = [{"id": "fake-release"}] if self.inserted else []

            return _Response()

    class _Client:
        def table(self, name):
            return _Query(name)

        def rpc(self, name, _params):
            events.append(("rpc", name))
            return _Query(name)

    monkeypatch.setattr(sync_safety_alerts, "get_supabase_client", _Client)
    monkeypatch.setattr(
        sync_safety_alerts, "upload_file",
        lambda _client, _bucket, remote, _local, **_kw: events.append(("upload", remote)),
    )
    monkeypatch.setattr(
        sync_safety_alerts, "_dispatch_release", lambda _id: events.append(("dispatch", None))
    )

    sync_safety_alerts.sync(tmp_path)

    names = [event[0] for event in events]
    assert names == ["upload", "upload", "insert", "rpc", "dispatch"]
    assert events[0][1] == staged["extended_feed"]["path"]
    assert events[2][1]["feed_path"] == f"safety-alerts/sha256/{staged['checksum'].removeprefix('sha256:')}.json"
    assert events[2][1]["manifest"]["extended_feed"]["path"] == staged["extended_feed"]["path"]


# --- the signature ------------------------------------------------------------

# RFC 8032 test vector 1: a published key, so it can never be anyone's real one.
TEST_KEY_ID = "alert-feed-test"
TEST_KEY = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(
    "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"
))
TEST_PUBLIC_HEX = "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
OTHER_KEY = Ed25519PrivateKey.generate()


def _sign_staged(dist_dir, *, sequence=1, key=TEST_KEY, key_id=TEST_KEY_ID):
    text = sync_safety_alerts.build_statement(dist_dir, sequence=sequence, key_id=key_id)
    (dist_dir / sync_safety_alerts.STATEMENT_FILENAME).write_text(text, encoding="utf-8")
    (dist_dir / sync_safety_alerts.SIGNATURE_FILENAME).write_text(
        release_manifest.sign_alert_feed(text, key), encoding="utf-8"
    )
    return text


def _no_remote(monkeypatch):
    """Fail the test on any step that could reach Supabase."""
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SAFETY_ALERT_DISPATCH_SECRET", "test-secret")
    events = []

    def unexpected(*_args, **_kwargs):
        events.append("remote")
        raise AssertionError("publication reached the remote before refusing")

    monkeypatch.setattr(sync_safety_alerts, "get_supabase_client", unexpected)
    monkeypatch.setattr(sync_safety_alerts, "upload_file", unexpected)
    monkeypatch.setattr(sync_safety_alerts, "_dispatch_release", unexpected)
    return events


def _refuses_before_any_remote_write(dist_dir, monkeypatch, match):
    events = _no_remote(monkeypatch)
    for dry_run in (True, False):
        with pytest.raises(release_manifest.ReleaseManifestError, match=match):
            sync_safety_alerts.sync(dist_dir, dry_run=dry_run)
    assert events == []


def test_an_unsigned_feed_is_refused_before_any_remote_write(tmp_path, monkeypatch):
    _stage_all(tmp_path)
    _refuses_before_any_remote_write(tmp_path, monkeypatch, "must be signed")


def test_a_statement_with_no_signature_is_refused(tmp_path, monkeypatch):
    _stage_all(tmp_path)
    _sign_staged(tmp_path)
    (tmp_path / sync_safety_alerts.SIGNATURE_FILENAME).unlink()
    _refuses_before_any_remote_write(tmp_path, monkeypatch, "must be signed")


def test_no_pinned_key_refuses_even_a_signed_feed(tmp_path, monkeypatch, alert_trust):
    """Unlike the catalog, there is no unsigned phase before the first key."""
    _stage_all(tmp_path)
    _sign_staged(tmp_path)
    alert_trust(alert_feed_keys={})
    _refuses_before_any_remote_write(tmp_path, monkeypatch, "not pinned")


def test_a_feed_signed_by_an_unpinned_key_id_is_refused(tmp_path, monkeypatch):
    _stage_all(tmp_path)
    _sign_staged(tmp_path, key=OTHER_KEY, key_id="someone-else")
    _refuses_before_any_remote_write(tmp_path, monkeypatch, "not pinned")


def test_another_key_claiming_the_pinned_key_id_is_refused(tmp_path, monkeypatch):
    _stage_all(tmp_path)
    _sign_staged(tmp_path, key=OTHER_KEY)
    _refuses_before_any_remote_write(tmp_path, monkeypatch, "does not verify")


def test_a_catalog_release_key_does_not_vouch_for_a_feed(tmp_path, monkeypatch, alert_trust):
    other_public = OTHER_KEY.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    ).hex()
    _stage_all(tmp_path)
    _sign_staged(tmp_path, key=OTHER_KEY, key_id="release-key")
    alert_trust(production_keys={"release-key": other_public})
    _refuses_before_any_remote_write(tmp_path, monkeypatch, "not pinned")


def test_a_signature_over_an_earlier_feed_is_refused(tmp_path, monkeypatch):
    _stage_all(tmp_path)
    _sign_staged(tmp_path)
    # A later --stage replaces the feed and leaves the old signature beside it.
    feed = b'{"alerts": []}\n'
    checksum = "sha256:" + hashlib.sha256(feed).hexdigest()
    (tmp_path / publisher.FEED_FILENAME).write_bytes(feed)
    (tmp_path / publisher.EXTENDED_FEED_FILENAME).unlink()
    (tmp_path / publisher.MANIFEST_FILENAME).write_text(
        json.dumps({"checksum": checksum, "feed_version": checksum, "latest_revisions": {}}),
        encoding="utf-8",
    )
    _refuses_before_any_remote_write(tmp_path, monkeypatch, "does not name this feed")


def test_a_signature_that_drops_the_extended_feed_is_refused(tmp_path, monkeypatch):
    """Otherwise a signer's mistake would hide every rule from new builds."""
    _stage_all(tmp_path)
    text = sync_safety_alerts.build_statement(tmp_path, sequence=1, key_id=TEST_KEY_ID)
    statement = json.loads(text)
    statement["extended_feed"] = None
    text = release_manifest.canonical_text(statement)
    (tmp_path / sync_safety_alerts.STATEMENT_FILENAME).write_text(text, encoding="utf-8")
    (tmp_path / sync_safety_alerts.SIGNATURE_FILENAME).write_text(
        release_manifest.sign_alert_feed(text, TEST_KEY), encoding="utf-8"
    )
    _refuses_before_any_remote_write(tmp_path, monkeypatch, "does not name this feed")


def test_an_edited_statement_is_refused(tmp_path, monkeypatch):
    _stage_all(tmp_path)
    text = _sign_staged(tmp_path)
    statement = json.loads(text)
    statement["release_sequence"] = 99
    (tmp_path / sync_safety_alerts.STATEMENT_FILENAME).write_text(
        release_manifest.canonical_text(statement), encoding="utf-8"
    )
    _refuses_before_any_remote_write(tmp_path, monkeypatch, "does not verify")


def test_a_signed_catalog_manifest_cannot_stand_in_for_a_feed_statement(tmp_path, monkeypatch):
    _stage_all(tmp_path)
    (tmp_path / sync_safety_alerts.STATEMENT_FILENAME).write_text(
        release_manifest.canonical_text({
            "format": 1, "key_id": TEST_KEY_ID, "release_sequence": 1,
            "catalog": {}, "rules": None, "min_rules_version": "1.0.0",
            "blocked_versions": {"catalog": [], "rules": []},
        }),
        encoding="utf-8",
    )
    (tmp_path / sync_safety_alerts.SIGNATURE_FILENAME).write_text(
        f"{TEST_KEY_ID}:AAAA", encoding="utf-8"
    )
    _refuses_before_any_remote_write(tmp_path, monkeypatch, "safety-alert statement")


def test_a_feed_statement_cannot_be_signed_or_verified_as_a_catalog_manifest(tmp_path):
    _stage_all(tmp_path)
    text = _sign_staged(tmp_path)
    with pytest.raises(release_manifest.ReleaseManifestError):
        release_manifest.sign_release(text, TEST_KEY)
    with pytest.raises(release_manifest.ReleaseManifestError):
        release_manifest.verify_release(
            text, release_manifest.sign_alert_feed(text, TEST_KEY), TEST_KEY.public_key()
        )


@pytest.mark.parametrize("sequence", [0, -1, True, "1", 1.5])
def test_a_bad_sequence_cannot_be_built(tmp_path, sequence):
    _stage_all(tmp_path)
    with pytest.raises(release_manifest.ReleaseManifestError, match="release_sequence"):
        sync_safety_alerts.build_statement(tmp_path, sequence=sequence, key_id=TEST_KEY_ID)


def test_the_test_project_lane_takes_only_a_test_key_and_a_test_host(
    tmp_path, monkeypatch, alert_trust
):
    _stage_all(tmp_path)
    _sign_staged(tmp_path)
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    with pytest.raises(release_manifest.ReleaseManifestError, match="not pinned"):
        load_staged_release(tmp_path, test_project=True)

    alert_trust(alert_feed_keys={}, test_keys={TEST_KEY_ID: TEST_PUBLIC_HEX})
    assert load_staged_release(tmp_path, test_project=True)["statement"]["release_sequence"] == 1
    with pytest.raises(release_manifest.ReleaseManifestError, match="not pinned"):
        load_staged_release(tmp_path)

    monkeypatch.setenv("SUPABASE_URL", "https://omayamxacvacrnvdvzhr.supabase.co")
    with pytest.raises(release_manifest.ReleaseManifestError, match="production project"):
        load_staged_release(tmp_path, test_project=True)


def test_signing_changes_nothing_old_builds_read(tmp_path, monkeypatch):
    """Detached on purpose: `feed_path`, `checksum` and the bytes stay as they were."""
    staged = _stage_all(tmp_path)
    before = {
        name: (tmp_path / name).read_bytes()
        for name in (publisher.FEED_FILENAME, publisher.EXTENDED_FEED_FILENAME, publisher.MANIFEST_FILENAME)
    }
    text = _sign_staged(tmp_path)
    events = _publish_with_fakes(tmp_path, monkeypatch)

    for name, data in before.items():
        assert (tmp_path / name).read_bytes() == data
    inserted = next(event[1] for event in events if event[0] == "insert")
    assert inserted["checksum"] == staged["checksum"] == FAKE_BASE_FEED_SHA256
    digest = FAKE_BASE_FEED_SHA256.removeprefix("sha256:")
    assert inserted["feed_path"] == f"safety-alerts/sha256/{digest}.json"
    written = dict(inserted["manifest"])
    signed = written.pop("signed_feed")
    assert written == json.loads(before[publisher.MANIFEST_FILENAME])
    assert signed["statement"] == text
    assert signed["signature"] == (tmp_path / sync_safety_alerts.SIGNATURE_FILENAME).read_text()


def test_the_signature_vector_the_app_verifies(tmp_path):
    """Two pins, one vector: test/services/safety_alerts/signed_feed_test.dart reads these."""
    _stage_all(tmp_path)
    text = sync_safety_alerts.build_statement(tmp_path, sequence=7, key_id=TEST_KEY_ID)
    assert text == FAKE_SIGNED_STATEMENT
    assert release_manifest.sign_alert_feed(text, TEST_KEY) == FAKE_SIGNED_SIGNATURE


def test_the_commands_build_sign_and_refuse_as_the_runbook_says(tmp_path, monkeypatch, capsys):
    _stage_all(tmp_path)
    key_file = tmp_path / "key.pem"
    key_file.write_bytes(TEST_KEY.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption(),
    ))
    key_file.chmod(0o600)
    statement = tmp_path / sync_safety_alerts.STATEMENT_FILENAME
    signature = tmp_path / sync_safety_alerts.SIGNATURE_FILENAME
    events = _no_remote(monkeypatch)

    def publisher_command(*flags):
        monkeypatch.setattr(sys, "argv", ["sync_safety_alerts.py", "--dist-dir", str(tmp_path), *flags])
        return sync_safety_alerts.main()

    assert publisher_command() == 1
    assert "must be signed" in capsys.readouterr().err
    assert publisher_command(
        "--build-statement", "--sequence", "7", "--key-id", TEST_KEY_ID
    ) == 0
    assert statement.read_text(encoding="utf-8") == FAKE_SIGNED_STATEMENT
    assert publisher_command("--dry-run") == 1
    assert release_manifest.main([
        "sign-alert-feed", "--statement", str(statement),
        "--key-file", str(key_file), "--output", str(signature),
    ]) == 0
    assert signature.read_text(encoding="utf-8") == FAKE_SIGNED_SIGNATURE
    assert publisher_command("--dry-run") == 0
    assert str(TEST_KEY.private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption(),
    ).hex()) not in capsys.readouterr().out
    assert events == []


def _publish_with_fakes(dist_dir, monkeypatch, *, current=None, existing=None):
    """Run the real publish path against a fake client, recording every step."""
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SAFETY_ALERT_DISPATCH_SECRET", "test-secret")
    events = []

    class _Query:
        def __init__(self):
            self.rows = []
            self.written = False

        def select(self, *_):
            return self

        def eq(self, column, _value):
            if column == "is_current":
                self.rows = [current] if current else []
            elif column == "checksum":
                self.rows = [existing] if existing else []
            return self

        def limit(self, *_):
            return self

        def insert(self, row):
            events.append(("insert", row))
            self.rows = [{"id": "fake-release"}]
            return self

        def update(self, row):
            events.append(("update", row))
            return self

        def execute(self):
            class _Response:
                data = self.rows

            return _Response()

    class _Client:
        def table(self, _name):
            return _Query()

        def rpc(self, name, params):
            events.append(("rpc", name, params))
            return _Query()

    monkeypatch.setattr(sync_safety_alerts, "get_supabase_client", _Client)
    monkeypatch.setattr(
        sync_safety_alerts, "upload_file",
        lambda _client, _bucket, remote, _local, **_kw: events.append(("upload", remote)),
    )
    monkeypatch.setattr(
        sync_safety_alerts, "_dispatch_release", lambda _id: events.append(("dispatch", None))
    )
    sync_safety_alerts.sync(dist_dir)
    return events


def _current_row(sequence, *, statement=None):
    return {
        "id": "current-release",
        "manifest": {"signed_feed": {
            "statement": statement or json.dumps({"release_sequence": sequence}),
            "signature": "x",
        }},
    }


def test_a_lower_sequence_than_the_current_release_is_refused(tmp_path, monkeypatch):
    _stage_all(tmp_path)
    _sign_staged(tmp_path, sequence=4)
    with pytest.raises(release_manifest.ReleaseManifestError, match="higher than"):
        _publish_with_fakes(tmp_path, monkeypatch, current=_current_row(5))


def test_the_same_sequence_on_a_different_feed_is_refused(tmp_path, monkeypatch):
    _stage_all(tmp_path)
    _sign_staged(tmp_path, sequence=5)
    with pytest.raises(release_manifest.ReleaseManifestError, match="higher than"):
        _publish_with_fakes(tmp_path, monkeypatch, current=_current_row(5))


def test_a_retry_of_the_current_release_stays_safe(tmp_path, monkeypatch):
    _stage_all(tmp_path)
    text = _sign_staged(tmp_path, sequence=5)
    row = _current_row(5, statement=text)
    row["manifest"]["signed_feed"]["signature"] = (
        tmp_path / sync_safety_alerts.SIGNATURE_FILENAME
    ).read_text()
    events = _publish_with_fakes(tmp_path, monkeypatch, current=row, existing=row)
    assert [event[0] for event in events] == ["upload", "upload", "rpc", "dispatch"]


def test_a_higher_sequence_is_published(tmp_path, monkeypatch):
    _stage_all(tmp_path)
    text = _sign_staged(tmp_path, sequence=6)
    events = _publish_with_fakes(tmp_path, monkeypatch, current=_current_row(5))
    assert [event[0] for event in events] == ["upload", "upload", "insert", "rpc", "dispatch"]
    assert events[2][1]["manifest"]["signed_feed"]["statement"] == text


def test_republishing_earlier_bytes_carries_the_new_signature(tmp_path, monkeypatch):
    """A return to earlier content finds the old row, whose old sequence phones would refuse."""
    _stage_all(tmp_path)
    text = _sign_staged(tmp_path, sequence=6)
    events = _publish_with_fakes(
        tmp_path, monkeypatch, current=_current_row(5), existing=_current_row(2)
    )
    assert [event[0] for event in events] == ["upload", "upload", "update", "rpc", "dispatch"]
    assert events[2][1]["manifest"]["signed_feed"]["statement"] == text
    assert events[3][2] == {"p_release_id": "current-release"}


def test_the_runbook_names_the_real_commands_and_pins():
    runbook = (
        Path(release_manifest.__file__).parents[1] / "docs" / "RELEASE_SIGNING_RUNBOOK.md"
    ).read_text(encoding="utf-8")
    for needle in (
        "sign-alert-feed", "--build-statement", "--test-project", "alert_feed_keys",
        "_kProductionAlertFeedKeys", sync_safety_alerts.STATEMENT_FILENAME,
        sync_safety_alerts.SIGNATURE_FILENAME, "this feed must be signed", "does not name this feed",
    ):
        assert needle in runbook, needle


def test_the_real_trust_file_pins_nothing_yet():
    committed = Path(release_manifest.__file__).parent / "config" / "release_trust.json"
    trust = json.loads(committed.read_text(encoding="utf-8"))
    assert trust["alert_feed_keys"] == {}
    assert TEST_PUBLIC_HEX not in trust["production_keys"].values()
