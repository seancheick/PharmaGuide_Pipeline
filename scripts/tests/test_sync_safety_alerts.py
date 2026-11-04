"""Safety-alert feed publication must remain independent from catalog sync."""

import hashlib
import json
from pathlib import Path

import pytest

import build_safety_alerts as publisher
import sync_safety_alerts
from sync_safety_alerts import load_staged_release


SCRIPT = Path(__file__).resolve().parents[1] / "sync_safety_alerts.py"
RUNNER = Path(__file__).resolve().parents[1] / "run_safety_alert_publish.sh"


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
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SAFETY_ALERT_DISPATCH_SECRET", raising=False)

    def unexpected_client():
        raise AssertionError("dry run contacted the remote client")

    monkeypatch.setattr(sync_safety_alerts, "get_supabase_client", unexpected_client)
    assert sync_safety_alerts.sync(tmp_path, dry_run=True)["status"] == "dry_run"


def test_staged_release_verifies_the_extended_feed(tmp_path):
    staged = _stage_all(tmp_path)
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
