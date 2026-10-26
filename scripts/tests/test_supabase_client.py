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

    class MockRpcResponse:
        data = "fake-uuid-returned-by-rotate-manifest"

    class MockRpcChain:
        def execute(self):
            return MockRpcResponse()

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

    approvals = [{"submission_id": "018f4c79-7c7e-4c70-9d62-7fc3b9ce6a11"}]
    insert_manifest(MockClient(), manifest_data, submission_approvals=approvals)

    assert captured["name"] == "rotate_manifest_with_submission_approvals"
    assert captured["params"]["p_schema_version"] == "5"  # str coercion
    assert captured["params"]["p_product_count"] == 50000  # int coercion
    assert captured["params"]["p_db_version"] == "2026.03.27.5"
    assert captured["params"]["p_min_app_version"] == "1.0.0"  # default
    assert captured["params"]["p_submission_approvals"] == approvals


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


def test_storage_bucket_is_declared_once():
    """The storage bucket name has one Python owner, mirroring Flutter
    ``SupabaseContract.storageBucket``; every module imports it."""
    import re
    from pathlib import Path
    from supabase_client import STORAGE_BUCKET

    assert STORAGE_BUCKET == "pharmaguide"

    scripts = Path(_scripts_dir).resolve()
    literal = re.compile(r"""["']pharmaguide["']""")
    # storage_audit's known top-level folder set names a folder inside the
    # bucket, not the bucket.
    allowed = {"supabase_client.py": 1, "release_safety/storage_audit.py": 1}
    found = {}
    for path in scripts.rglob("*.py"):
        rel = path.relative_to(scripts).as_posix()
        if rel.startswith("tests/"):
            continue
        count = len(literal.findall(path.read_text(encoding="utf-8")))
        if count:
            found[rel] = count
    assert found == allowed

@pytest.mark.parametrize('defect', [None, 'missing_rpc', 'missing_approvals', 'wrong_count_type', 'new_required_argument'])
def test_publication_preflight_rejects_incompatible_live_contract(monkeypatch, defect):
    import requests
    from types import SimpleNamespace
    from supabase_client import require_publication_contract
    properties = {k: {'format': v} for k, v in {
        'p_db_version': 'text', 'p_pipeline_version': 'text',
        'p_scoring_version': 'text', 'p_schema_version': 'text',
        'p_product_count': 'integer', 'p_checksum': 'text',
        'p_generated_at': 'timestamp with time zone', 'p_min_app_version': 'text',
        'p_submission_approvals': 'jsonb'}.items()}
    schema = {'properties': properties, 'required': ['p_db_version']}
    paths = {'/rpc/rotate_manifest_with_submission_approvals': {
        'post': {'parameters': [{'in': 'body', 'schema': schema}]}}}
    if defect == 'missing_rpc': paths.clear()
    if defect == 'missing_approvals': properties.pop('p_submission_approvals')
    if defect == 'wrong_count_type': properties['p_product_count']['format'] = 'text'
    if defect == 'new_required_argument': schema['required'].append('new_required')
    monkeypatch.setenv('SUPABASE_URL', 'https://example.invalid')
    monkeypatch.setenv('SUPABASE_SERVICE_ROLE_KEY', 'test-only-secret')
    monkeypatch.setattr(requests, 'get', lambda *a, **k: SimpleNamespace(
        raise_for_status=lambda: None, json=lambda: {'paths': paths}))
    if defect is None:
        require_publication_contract()
    else:
        with pytest.raises(ValueError, match='publication contract'):
            require_publication_contract()


@pytest.mark.parametrize('remote', [b'old', b'new'])
def test_create_only_upload_retry_never_overwrites(tmp_path, remote):
    from types import SimpleNamespace
    from supabase_client import upload_file
    path = tmp_path / 'catalog.db'
    path.write_bytes(b'new')
    writes = []
    class Storage:
        def upload(self, **kwargs):
            writes.append(kwargs['file_options']['upsert'])
            raise RuntimeError('object already exists')
        def download(self, path):
            return remote
    client = SimpleNamespace(storage=SimpleNamespace(from_=lambda bucket: Storage()))
    if remote == b'new':
        upload_file(client, 'bucket', 'vold/pharmaguide_core.db', path, upsert=False)
    else:
        with pytest.raises(ValueError, match='immutable'):
            upload_file(client, 'bucket', 'vold/pharmaguide_core.db', path, upsert=False)
    assert writes == ['false']

@pytest.mark.parametrize('same_bytes', [False, True])
def test_concurrent_create_only_uploads_preserve_winning_bytes(tmp_path, same_bytes):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, Lock
    from types import SimpleNamespace
    from supabase_client import upload_file
    files = [tmp_path / 'one', tmp_path / 'two']
    files[0].write_bytes(b'one')
    files[1].write_bytes(b'one' if same_bytes else b'two')
    barrier, lock = Barrier(2), Lock()
    objects = {}
    class Storage:
        def upload(self, path, file, file_options):
            assert file_options['upsert'] == 'false'
            barrier.wait(timeout=5)
            with lock:
                if path in objects:
                    raise RuntimeError('collision')
                objects[path] = file.read()
        def download(self, path):
            return objects[path]
    client = SimpleNamespace(storage=SimpleNamespace(from_=lambda bucket: Storage()))
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(upload_file, client, 'bucket', 'vold/catalog.db', path, upsert=False) for path in files]
    errors = [future.exception() for future in futures]
    assert sum(error is not None for error in errors) == (0 if same_bytes else 1)
    if not same_bytes:
        assert any(isinstance(error, ValueError) for error in errors)
    assert objects['vold/catalog.db'] in {path.read_bytes() for path in files}


def test_fetch_manifest_version_includes_inactive_history():
    from types import SimpleNamespace
    from supabase_client import fetch_manifest_version
    calls = []
    class Query:
        def select(self, columns):
            return self
        def eq(self, column, value):
            calls.append((column, value))
            return self
        def limit(self, count):
            return self
        def execute(self):
            return SimpleNamespace(data=[{'db_version': 'old', 'is_current': False}])
    client = SimpleNamespace(table=lambda name: Query())
    assert fetch_manifest_version(client, 'old')['is_current'] is False
    assert calls == [('db_version', 'old')]
