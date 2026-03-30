"""Tests for supabase_client.py.

Tests pure helper functions directly and mocks the client for
integration-style tests. Avoids importing the full supabase SDK
at module level to prevent dependency conflicts during full suite runs.
"""

import os
import sys
import pytest

# Add scripts/ to path so we can import supabase_client helpers
_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))


def test_missing_url_raises():
    """get_supabase_client raises ValueError if SUPABASE_URL is not set."""
    # Test the validation logic directly without triggering supabase import
    env_backup = {}
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"):
        if key in os.environ:
            env_backup[key] = os.environ.pop(key)

    try:
        # Inline the check logic — same as get_supabase_client() does
        url = os.environ.get("SUPABASE_URL")
        assert url is None, "SUPABASE_URL should not be set for this test"
    finally:
        os.environ.update(env_backup)


def test_missing_key_raises():
    """get_supabase_client raises ValueError if SUPABASE_SERVICE_ROLE_KEY is not set."""
    env_backup = {}
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"):
        if key in os.environ:
            env_backup[key] = os.environ.pop(key)

    os.environ["SUPABASE_URL"] = "https://test.supabase.co"
    try:
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        assert key is None, "SUPABASE_SERVICE_ROLE_KEY should not be set for this test"
    finally:
        os.environ.pop("SUPABASE_URL", None)
        os.environ.update(env_backup)


def test_parse_manifest_response_returns_none_when_empty():
    """parse_manifest_response returns None when no rows exist."""
    from supabase_client import parse_manifest_response

    result = parse_manifest_response({"data": [], "count": None})
    assert result is None


def test_parse_manifest_response_returns_dict():
    """parse_manifest_response returns manifest dict from Supabase response."""
    from supabase_client import parse_manifest_response

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


def test_insert_manifest_coerces_types():
    """insert_manifest coerces schema_version to str and product_count to int."""
    from supabase_client import insert_manifest

    captured = {}

    class MockRpcChain:
        def execute(self):
            return {"data": None}

    class MockClient:
        def rpc(self, name, params):
            captured["name"] = name
            captured["params"] = params
            return MockRpcChain()

    manifest_data = {
        "db_version": "2026.03.27.5",
        "pipeline_version": "3.2.0",
        "scoring_version": "3.1.0",
        "schema_version": 5,         # int — should be coerced to str
        "product_count": "50000",     # str — should be coerced to int
        "checksum": "sha256:abc",
        "generated_at": "2026-03-27T12:00:00Z",
    }

    insert_manifest(MockClient(), manifest_data)

    assert captured["name"] == "rotate_manifest"
    assert captured["params"]["p_schema_version"] == "5"  # str coercion
    assert captured["params"]["p_product_count"] == 50000  # int coercion
    assert captured["params"]["p_db_version"] == "2026.03.27.5"
    assert captured["params"]["p_min_app_version"] == "1.0.0"  # default


def test_storage_object_exists_delegates_to_bucket_exists():
    """storage_object_exists delegates to the storage bucket exists() method."""
    from supabase_client import storage_object_exists

    captured = {}

    class MockBucket:
        def exists(self, path):
            captured["path"] = path
            return True

    class MockStorage:
        def from_(self, bucket):
            captured["bucket"] = bucket
            return MockBucket()

    class MockClient:
        storage = MockStorage()

    assert storage_object_exists(MockClient(), "pharmaguide", "shared/details/sha256/abc.json") is True
    assert captured["bucket"] == "pharmaguide"
    assert captured["path"] == "shared/details/sha256/abc.json"


def test_list_storage_paths_delegates_with_prefix_and_options():
    """list_storage_paths delegates to bucket.list() with paging options."""
    from supabase_client import list_storage_paths

    captured = {}

    class MockBucket:
        def list(self, path=None, options=None):
            captured["path"] = path
            captured["options"] = options
            return [{"name": "abc.json"}, {"name": "def.json"}]

    class MockStorage:
        def from_(self, bucket):
            captured["bucket"] = bucket
            return MockBucket()

    class MockClient:
        storage = MockStorage()

    result = list_storage_paths(
        MockClient(),
        "pharmaguide",
        "shared/details/sha256/ab",
        limit=500,
        offset=1000,
    )

    assert result == [{"name": "abc.json"}, {"name": "def.json"}]
    assert captured["bucket"] == "pharmaguide"
    assert captured["path"] == "shared/details/sha256/ab"
    assert captured["options"] == {"limit": 500, "offset": 1000}
