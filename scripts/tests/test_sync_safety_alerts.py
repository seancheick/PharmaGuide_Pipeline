"""Safety-alert feed publication must remain independent from catalog sync."""

import hashlib
import json
from pathlib import Path

import pytest

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
