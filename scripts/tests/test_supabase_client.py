"""Tests for supabase_client.py."""

import os
import pytest


def test_missing_url_raises():
    """Client raises ValueError if SUPABASE_URL is not set."""
    env_backup = {}
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"):
        if key in os.environ:
            env_backup[key] = os.environ.pop(key)

    try:
        from scripts.supabase_client import get_supabase_client
        with pytest.raises(ValueError, match="SUPABASE_URL"):
            get_supabase_client()
    finally:
        os.environ.update(env_backup)


def test_missing_key_raises():
    """Client raises ValueError if SUPABASE_SERVICE_ROLE_KEY is not set."""
    env_backup = {}
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"):
        if key in os.environ:
            env_backup[key] = os.environ.pop(key)

    os.environ["SUPABASE_URL"] = "https://test.supabase.co"
    try:
        from scripts.supabase_client import get_supabase_client
        with pytest.raises(ValueError, match="SUPABASE_SERVICE_ROLE_KEY"):
            get_supabase_client()
    finally:
        os.environ.pop("SUPABASE_URL", None)
        os.environ.update(env_backup)


def test_get_current_manifest_returns_none_when_empty(monkeypatch):
    """get_current_manifest returns None when no rows exist."""
    from scripts.supabase_client import parse_manifest_response

    result = parse_manifest_response({"data": [], "count": None})
    assert result is None


def test_get_current_manifest_returns_dict(monkeypatch):
    """get_current_manifest returns manifest dict from Supabase response."""
    from scripts.supabase_client import parse_manifest_response

    fake_row = {
        "id": "abc-123",
        "db_version": "2026.03.17.5",
        "pipeline_version": "3.2.0",
        "scoring_version": "3.1.0",
        "schema_version": "5",
        "product_count": 50000,
        "checksum": "sha256:abc123",
        "generated_at": "2026-03-17T12:00:00Z",
        "is_current": True,
    }
    result = parse_manifest_response({"data": [fake_row], "count": None})
    assert result is not None
    assert result["db_version"] == "2026.03.17.5"
    assert result["product_count"] == 50000
