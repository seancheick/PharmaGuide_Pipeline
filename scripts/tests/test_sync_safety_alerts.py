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
