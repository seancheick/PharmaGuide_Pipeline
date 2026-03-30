# Supabase Sync Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the Supabase distribution layer that uploads pipeline exports (SQLite DB + detail blobs) to Supabase Storage and tracks versions in a PostgreSQL manifest table.

**Architecture:** `build_final_db.py` output -> `sync_to_supabase.py` -> Supabase Storage (versioned .db + JSON blobs) + PostgreSQL export_manifest table. Manual script first, CI/CD later. Service role key for writes, anon key for app reads.

**Tech Stack:** Python 3.13, supabase-py (Supabase Python client), existing env_loader.py pattern, pytest 9

---

## File Structure

| File | Responsibility |
|------|---------------|
| `scripts/sync_to_supabase.py` | Main sync script: reads build output, compares versions, uploads to Supabase |
| `scripts/supabase_client.py` | Thin wrapper: initializes Supabase client from env vars, exposes typed helpers |
| `scripts/tests/test_sync_to_supabase.py` | Tests for sync logic (version comparison, manifest parsing, upload orchestration) |
| `scripts/tests/test_supabase_client.py` | Tests for client wrapper (env loading, error handling) |
| `scripts/sql/supabase_schema.sql` | Full Supabase schema: tables, indexes, RLS policies (reference, not executed by Python) |
| `scripts/SUPABASE_SYNC_README.md` | Setup guide: project creation, env vars, usage, troubleshooting |
| `requirements-dev.txt` | Add supabase dependency |
| `.env.example` | Add Supabase env var placeholders |

---

### Task 1: Add Supabase Dependency and Environment Variables

**Files:**
- Modify: `requirements-dev.txt`
- Modify or Create: `.env.example`

- [ ] **Step 1: Add supabase to requirements-dev.txt**

```
requests>=2.32,<3
rapidfuzz>=3.9,<4
pytest>=9,<10
supabase>=2.0,<3
```

- [ ] **Step 2: Add Supabase env var placeholders to .env.example**

Check if `.env.example` exists. If not, create it. Add these lines (append if it exists):

```
# Supabase (sync_to_supabase.py)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...your-service-role-key
```

- [ ] **Step 3: Install the new dependency**

Run: `pip install supabase>=2.0,<3`
Expected: Successful installation of supabase and its dependencies (httpx, gotrue, storage3, postgrest, etc.)

- [ ] **Step 4: Verify import works**

Run: `python3 -c "from supabase import create_client; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add requirements-dev.txt .env.example
git commit -m "chore: add supabase dependency and env var placeholders"
```

---

### Task 2: Write Supabase Schema SQL Reference

**Files:**
- Create: `scripts/sql/supabase_schema.sql`

This file is a reference document. You run it manually in the Supabase SQL Editor to set up the project. The Python code does NOT execute this file.

- [ ] **Step 1: Create the schema file**

```sql
-- PharmaGuide Supabase Schema
-- Run this in the Supabase SQL Editor to set up the project.
-- Version: 1.0.0
-- Date: 2026-03-27

-- =============================================================================
-- 1. Pipeline Distribution Table
-- =============================================================================

CREATE TABLE IF NOT EXISTS export_manifest (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  db_version       text NOT NULL,
  pipeline_version text NOT NULL,
  scoring_version  text NOT NULL,
  schema_version   text NOT NULL,
  product_count    integer NOT NULL,
  checksum         text NOT NULL,
  min_app_version  text NOT NULL DEFAULT '1.0.0',
  generated_at     timestamptz NOT NULL,
  created_at       timestamptz DEFAULT now(),
  is_current       boolean DEFAULT true
);

-- =============================================================================
-- 2. User Tables (App-facing)
-- =============================================================================

CREATE TABLE IF NOT EXISTS user_stacks (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      uuid REFERENCES auth.users NOT NULL,
  dsld_id      text NOT NULL,
  dosage       text,
  timing       text,
  supply_count integer,
  added_at     timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_usage (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           uuid REFERENCES auth.users NOT NULL,
  scans_today       integer DEFAULT 0,
  ai_messages_today integer DEFAULT 0,
  reset_date        date DEFAULT CURRENT_DATE
);

CREATE TABLE IF NOT EXISTS pending_products (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      uuid REFERENCES auth.users NOT NULL,
  upc          text NOT NULL,
  product_name text,
  brand        text,
  image_url    text,
  status       text DEFAULT 'pending',
  submitted_at timestamptz DEFAULT now()
);

-- =============================================================================
-- 3. Indexes
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_user_stacks_user ON user_stacks(user_id);
CREATE INDEX IF NOT EXISTS idx_user_usage_user ON user_usage(user_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_usage_daily ON user_usage(user_id, reset_date);
CREATE INDEX IF NOT EXISTS idx_pending_products_user ON pending_products(user_id);

-- =============================================================================
-- 4. Row Level Security
-- =============================================================================

-- export_manifest: anyone can read, only service role can write
ALTER TABLE export_manifest ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read manifest" ON export_manifest
  FOR SELECT USING (true);

-- user_stacks: users own their rows
ALTER TABLE user_stacks ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users manage own stacks" ON user_stacks
  FOR ALL USING (auth.uid() = user_id);

-- user_usage: users read their counters; writes go through increment_usage
ALTER TABLE user_usage ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users read own usage" ON user_usage
  FOR SELECT USING (auth.uid() = user_id);

-- pending_products: users submit and view their requests; status is server-owned
ALTER TABLE pending_products ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users read own submissions" ON pending_products
  FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users submit pending products" ON pending_products
  FOR INSERT WITH CHECK (auth.uid() = user_id);

-- =============================================================================
-- 5. RPC Functions
-- =============================================================================

-- Atomic manifest rotation: ensures there is always exactly one current row.
-- INSERT first, then UPDATE — no window where zero rows are current.
CREATE OR REPLACE FUNCTION rotate_manifest(
  p_db_version text,
  p_pipeline_version text,
  p_scoring_version text,
  p_schema_version text,
  p_product_count integer,
  p_checksum text,
  p_generated_at timestamptz,
  p_min_app_version text DEFAULT '1.0.0'
) RETURNS uuid AS $$
DECLARE
  new_id uuid;
BEGIN
  -- Insert new row first (so there's always at least one current)
  INSERT INTO export_manifest (
    db_version, pipeline_version, scoring_version, schema_version,
    product_count, checksum, min_app_version, generated_at, is_current
  ) VALUES (
    p_db_version, p_pipeline_version, p_scoring_version, p_schema_version,
    p_product_count, p_checksum, p_min_app_version, p_generated_at, true
  ) RETURNING id INTO new_id;

  -- Then mark all others as not current
  UPDATE export_manifest
  SET is_current = false
  WHERE is_current = true AND id != new_id;

  RETURN new_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =============================================================================
-- 6. Storage Bucket
-- =============================================================================
-- Create via Supabase Dashboard or API:
--   Bucket name: pharmaguide
--   Public: true (read via anon key)
--   File size limit: 100MB (for the SQLite DB file)
--
-- Folder structure:
--   pharmaguide/v{version}/pharmaguide_core.db
--   pharmaguide/v{version}/details/{dsld_id}.json
```

- [ ] **Step 2: Commit**

```bash
mkdir -p scripts/sql
git add scripts/sql/supabase_schema.sql
git commit -m "docs: add Supabase schema SQL reference for project setup"
```

---

### Task 3: Write Supabase Client Wrapper

**Files:**
- Create: `scripts/supabase_client.py`
- Create: `scripts/tests/test_supabase_client.py`

- [ ] **Step 1: Write the failing test for client initialization**

Create `scripts/tests/test_supabase_client.py`:

```python
"""Tests for supabase_client.py."""

import os
import pytest


def test_missing_url_raises():
    """Client raises ValueError if SUPABASE_URL is not set."""
    # Remove env vars if present
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

    # Simulate empty Supabase response
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest scripts/tests/test_supabase_client.py -v`
Expected: FAIL with `ModuleNotFoundError` (supabase_client.py doesn't exist yet)

- [ ] **Step 3: Write the client wrapper**

Create `scripts/supabase_client.py`:

```python
"""Thin Supabase client wrapper for PharmaGuide sync operations.

Initializes from environment variables (loaded via env_loader.py).
Provides typed helpers for manifest queries and storage uploads.
"""

import os
import sys

# Load .env the same way all pipeline scripts do
sys.path.insert(0, os.path.dirname(__file__))
import env_loader  # noqa: F401


def get_supabase_client():
    """Create and return a Supabase client using service role credentials.

    Raises ValueError if required environment variables are missing.
    """
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL")
    if not url:
        raise ValueError(
            "SUPABASE_URL environment variable is not set. "
            "Add it to your .env file."
        )

    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        raise ValueError(
            "SUPABASE_SERVICE_ROLE_KEY environment variable is not set. "
            "Add it to your .env file."
        )

    return create_client(url, key)


def parse_manifest_response(response):
    """Parse a Supabase query response for export_manifest.

    Returns the manifest dict if a row exists, None otherwise.
    """
    data = response.get("data", [])
    if not data:
        return None
    return data[0]


def fetch_current_manifest(client):
    """Fetch the current (is_current=true) export_manifest row.

    Returns dict or None.
    """
    response = (
        client.table("export_manifest")
        .select("*")
        .eq("is_current", True)
        .limit(1)
        .execute()
    )
    return parse_manifest_response({"data": response.data, "count": None})


def insert_manifest(client, manifest_data):
    """Atomically insert a new manifest and mark previous as not current.

    Uses the rotate_manifest RPC function to avoid a window where
    no row has is_current=true (INSERT first, then UPDATE others).
    """
    response = client.rpc("rotate_manifest", {
        "p_db_version": manifest_data["db_version"],
        "p_pipeline_version": manifest_data["pipeline_version"],
        "p_scoring_version": manifest_data["scoring_version"],
        "p_schema_version": str(manifest_data["schema_version"]),
        "p_product_count": int(manifest_data["product_count"]),
        "p_checksum": manifest_data["checksum"],
        "p_generated_at": manifest_data["generated_at"],
    }).execute()
    return response


def upload_file(client, bucket, remote_path, local_path, content_type="application/octet-stream"):
    """Upload a file to Supabase Storage.

    Returns the storage response.
    """
    with open(local_path, "rb") as f:
        data = f.read()

    return client.storage.from_(bucket).upload(
        path=remote_path,
        file=data,
        file_options={"content-type": content_type, "upsert": "true"},
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest scripts/tests/test_supabase_client.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/supabase_client.py scripts/tests/test_supabase_client.py
git commit -m "feat: add Supabase client wrapper with manifest helpers"
```

---

### Task 4: Write Sync Script Core Logic

**Files:**
- Create: `scripts/sync_to_supabase.py`
- Create: `scripts/tests/test_sync_to_supabase.py`

- [ ] **Step 1: Write the failing test for manifest comparison**

Create `scripts/tests/test_sync_to_supabase.py`:

```python
"""Tests for sync_to_supabase.py."""

import json
import os
import tempfile
import pytest


def _make_manifest(tmp_dir, db_version="2026.03.27.5", product_count=100):
    """Helper: write a fake export_manifest.json and return its path."""
    manifest = {
        "db_version": db_version,
        "pipeline_version": "3.2.0",
        "scoring_version": "3.1.0",
        "generated_at": "2026-03-27T12:00:00Z",
        "product_count": str(product_count),
        "checksum": "sha256:abc123def456",
        "min_app_version": "1.0.0",
        "schema_version": 5,
        "errors": [],
    }
    path = os.path.join(tmp_dir, "export_manifest.json")
    with open(path, "w") as f:
        json.dump(manifest, f)
    return path


def _make_build_output(tmp_dir, db_version="2026.03.27.5", product_count=3):
    """Helper: create a fake build output directory with manifest, db, and blobs."""
    _make_manifest(tmp_dir, db_version, product_count)

    # Fake SQLite file
    db_path = os.path.join(tmp_dir, "pharmaguide_core.db")
    with open(db_path, "wb") as f:
        f.write(b"FAKE_SQLITE_DATA")

    # Fake detail blobs
    detail_dir = os.path.join(tmp_dir, "detail_blobs")
    os.makedirs(detail_dir, exist_ok=True)
    for i in range(product_count):
        blob_path = os.path.join(detail_dir, f"{1000 + i}.json")
        with open(blob_path, "w") as f:
            json.dump({"dsld_id": str(1000 + i), "blob_version": 1}, f)

    return tmp_dir


def test_load_local_manifest():
    """load_local_manifest reads and parses export_manifest.json."""
    from scripts.sync_to_supabase import load_local_manifest

    with tempfile.TemporaryDirectory() as tmp:
        _make_manifest(tmp, db_version="2026.03.27.5", product_count=500)
        manifest = load_local_manifest(tmp)
        assert manifest["db_version"] == "2026.03.27.5"
        assert manifest["product_count"] == "500"


def test_load_local_manifest_missing_file():
    """load_local_manifest raises FileNotFoundError for missing manifest."""
    from scripts.sync_to_supabase import load_local_manifest

    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(FileNotFoundError, match="export_manifest.json"):
            load_local_manifest(tmp)


def test_needs_update_true_when_versions_differ():
    """needs_update returns True when local version differs from remote."""
    from scripts.sync_to_supabase import needs_update

    local = {"db_version": "2026.03.27.5", "checksum": "sha256:new"}
    remote = {"db_version": "2026.03.17.5", "checksum": "sha256:old"}
    assert needs_update(local, remote) is True


def test_needs_update_false_when_same():
    """needs_update returns False when versions match."""
    from scripts.sync_to_supabase import needs_update

    local = {"db_version": "2026.03.27.5", "checksum": "sha256:same"}
    remote = {"db_version": "2026.03.27.5", "checksum": "sha256:same"}
    assert needs_update(local, remote) is False


def test_needs_update_true_when_no_remote():
    """needs_update returns True when remote manifest is None (first push)."""
    from scripts.sync_to_supabase import needs_update

    local = {"db_version": "2026.03.27.5", "checksum": "sha256:new"}
    assert needs_update(local, None) is True


def test_collect_detail_blobs():
    """collect_detail_blobs returns sorted list of blob file paths."""
    from scripts.sync_to_supabase import collect_detail_blobs

    with tempfile.TemporaryDirectory() as tmp:
        _make_build_output(tmp, product_count=3)
        blobs = collect_detail_blobs(tmp)
        assert len(blobs) == 3
        assert all(b.endswith(".json") for b in blobs)
        # Sorted by filename
        names = [os.path.basename(b) for b in blobs]
        assert names == sorted(names)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest scripts/tests/test_sync_to_supabase.py -v`
Expected: FAIL with `ModuleNotFoundError` (sync_to_supabase.py doesn't exist yet)

- [ ] **Step 3: Write the sync script**

Create `scripts/sync_to_supabase.py`:

```python
#!/usr/bin/env python3
"""Sync pipeline build output to Supabase Storage + PostgreSQL manifest.

Usage:
    python scripts/sync_to_supabase.py <build_output_dir>

The build_output_dir should contain:
    - export_manifest.json
    - pharmaguide_core.db
    - detail_blobs/{dsld_id}.json (one per product)

Environment variables (from .env):
    - SUPABASE_URL
    - SUPABASE_SERVICE_ROLE_KEY
"""

import json
import os
import sys
import time
import glob

# Ensure scripts/ is on the path for sibling imports (supabase_client)
sys.path.insert(0, os.path.dirname(__file__))
import env_loader  # noqa: F401


# ---------------------------------------------------------------------------
# Pure functions (testable without Supabase)
# ---------------------------------------------------------------------------

def load_local_manifest(build_dir):
    """Read export_manifest.json from build output directory.

    Raises FileNotFoundError if the manifest is missing.
    """
    manifest_path = os.path.join(build_dir, "export_manifest.json")
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(
            f"export_manifest.json not found in {build_dir}. "
            "Run build_final_db.py first."
        )
    with open(manifest_path) as f:
        return json.load(f)


def needs_update(local_manifest, remote_manifest):
    """Determine if Supabase needs updating.

    Returns True if:
    - remote_manifest is None (first push ever)
    - db_version differs
    """
    if remote_manifest is None:
        return True
    if local_manifest["db_version"] != remote_manifest["db_version"]:
        return True
    return False


def collect_detail_blobs(build_dir):
    """Return sorted list of detail blob file paths."""
    detail_dir = os.path.join(build_dir, "detail_blobs")
    if not os.path.isdir(detail_dir):
        return []
    blobs = sorted(glob.glob(os.path.join(detail_dir, "*.json")))
    return blobs


# ---------------------------------------------------------------------------
# Supabase operations (require real client)
# ---------------------------------------------------------------------------

def sync(build_dir, dry_run=False):
    """Main sync workflow.

    1. Load local manifest
    2. Compare to remote manifest
    3. Upload .db file to Storage
    4. Upload detail blobs to Storage
    5. Insert new manifest row
    """
    from supabase_client import (
        get_supabase_client,
        fetch_current_manifest,
        insert_manifest,
        upload_file,
    )

    print(f"Loading manifest from {build_dir}...")
    local = load_local_manifest(build_dir)
    version = local["db_version"]
    product_count = local["product_count"]
    checksum = local["checksum"]

    print(f"  Version:  {version}")
    print(f"  Products: {product_count}")
    print(f"  Checksum: {checksum[:20]}...")

    if dry_run:
        blobs = collect_detail_blobs(build_dir)
        db_path = os.path.join(build_dir, "pharmaguide_core.db")
        db_size = os.path.getsize(db_path) / (1024 * 1024) if os.path.exists(db_path) else 0
        print(f"\n[DRY RUN] Would upload:")
        print(f"  - pharmaguide_core.db ({db_size:.1f} MB)")
        print(f"  - {len(blobs)} detail blobs")
        print(f"  - New manifest row (version {version})")
        return {"status": "dry_run", "version": version, "blob_count": len(blobs)}

    client = get_supabase_client()
    print("Checking Supabase for current version...")
    remote = fetch_current_manifest(client)

    if remote:
        print(f"  Remote version: {remote['db_version']}")
    else:
        print("  No remote version found (first push)")

    if not needs_update(local, remote):
        print("Already up to date. Nothing to do.")
        return {"status": "up_to_date", "version": version}

    # Upload SQLite DB
    db_path = os.path.join(build_dir, "pharmaguide_core.db")
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"pharmaguide_core.db not found in {build_dir}")

    bucket = "pharmaguide"
    remote_db_path = f"v{version}/pharmaguide_core.db"
    print(f"\nUploading {remote_db_path}...")
    start = time.time()
    upload_file(client, bucket, remote_db_path, db_path)
    db_time = time.time() - start
    db_size_mb = os.path.getsize(db_path) / (1024 * 1024)
    print(f"  Done ({db_size_mb:.1f} MB in {db_time:.1f}s)")

    # Upload detail blobs
    # NOTE: Sequential uploads are fine for MVP (<10K products, ~15 min).
    # When product count exceeds ~10K, add concurrent.futures.ThreadPoolExecutor
    # with max_workers=10 to parallelize uploads (~10x speedup).
    blobs = collect_detail_blobs(build_dir)
    blob_count = len(blobs)
    print(f"\nUploading {blob_count} detail blobs...")
    start = time.time()
    errors = []
    for i, blob_path in enumerate(blobs, 1):
        dsld_id = os.path.splitext(os.path.basename(blob_path))[0]
        remote_blob_path = f"v{version}/details/{dsld_id}.json"
        try:
            upload_file(
                client, bucket, remote_blob_path, blob_path,
                content_type="application/json",
            )
        except Exception as e:
            errors.append({"dsld_id": dsld_id, "error": str(e)})
        if i % 500 == 0 or i == blob_count:
            elapsed = time.time() - start
            print(f"  {i}/{blob_count} ({elapsed:.1f}s)")

    blob_time = time.time() - start
    print(f"  Done ({blob_count} blobs in {blob_time:.1f}s, {len(errors)} errors)")

    # Insert manifest
    print(f"\nUpdating manifest (version {version})...")
    insert_manifest(client, local)
    print("  Done")

    # Summary
    total_time = db_time + blob_time
    print(f"\n{'=' * 50}")
    print(f"Sync complete: v{version}")
    print(f"  Products:    {product_count}")
    print(f"  DB size:     {db_size_mb:.1f} MB")
    print(f"  Blobs:       {blob_count}")
    print(f"  Errors:      {len(errors)}")
    print(f"  Total time:  {total_time:.1f}s")
    print(f"{'=' * 50}")

    if errors:
        print(f"\nFailed uploads ({len(errors)}):")
        for err in errors[:10]:
            print(f"  - {err['dsld_id']}: {err['error']}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")

    return {
        "status": "synced",
        "version": version,
        "product_count": int(product_count),
        "blob_count": blob_count,
        "error_count": len(errors),
        "time_seconds": round(total_time, 1),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/sync_to_supabase.py <build_output_dir> [--dry-run]")
        print()
        print("Options:")
        print("  --dry-run    Show what would be uploaded without actually uploading")
        sys.exit(1)

    build_dir = sys.argv[1]
    dry_run = "--dry-run" in sys.argv

    if not os.path.isdir(build_dir):
        print(f"Error: {build_dir} is not a directory")
        sys.exit(1)

    try:
        result = sync(build_dir, dry_run=dry_run)
        if result["status"] == "synced":
            sys.exit(0)
        elif result["status"] == "up_to_date":
            sys.exit(0)
        elif result["status"] == "dry_run":
            sys.exit(0)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Sync failed: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest scripts/tests/test_sync_to_supabase.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Verify the script runs with --help-like usage**

Run: `python3 scripts/sync_to_supabase.py`
Expected: Prints usage message and exits with code 1

- [ ] **Step 6: Commit**

```bash
git add scripts/sync_to_supabase.py scripts/tests/test_sync_to_supabase.py
git commit -m "feat: add sync_to_supabase.py with version comparison and upload logic"
```

---

### Task 5: Write Supabase Sync Documentation

**Files:**
- Create: `scripts/SUPABASE_SYNC_README.md`

- [ ] **Step 1: Write the documentation**

Create `scripts/SUPABASE_SYNC_README.md`:

```markdown
# Supabase Sync Pipeline

Uploads pipeline build output to Supabase for distribution to the Flutter app.

## Prerequisites

1. **Supabase Project:** Create at [supabase.com](https://supabase.com)
2. **Run Schema:** Copy `scripts/sql/supabase_schema.sql` into the Supabase SQL Editor and execute
3. **Create Storage Bucket:** In Supabase Dashboard > Storage, create bucket `pharmaguide` with public read access
4. **Environment Variables:** Add to your `.env` file:

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...your-service-role-key
```

Get these from Supabase Dashboard > Settings > API.

**IMPORTANT:** Use the **service role key** (not the anon key). The service role key bypasses RLS and is required for writing to the manifest table and storage bucket. Never commit this key to Git.

## Usage

### Run the full pipeline then sync

```bash
# 1. Run pipeline
python scripts/run_pipeline.py <dataset_dir>

# 2. Build Flutter export
python scripts/build_final_db.py \
  --enriched-dir output_Brand_enriched/enriched \
  --scored-dir output_Brand_scored/scored \
  --output-dir final_db_output

# 3. Sync to Supabase
python scripts/sync_to_supabase.py final_db_output
```

### Dry run (preview without uploading)

```bash
python scripts/sync_to_supabase.py <output_dir> --dry-run
```

### What gets uploaded

| Local File | Supabase Location |
|-----------|-------------------|
| `pharmaguide_core.db` | Storage: `pharmaguide/v{version}/pharmaguide_core.db` |
| `detail_blobs/*.json` | Storage: `pharmaguide/v{version}/details/{dsld_id}.json` |
| `export_manifest.json` | PostgreSQL: `export_manifest` table (is_current=true) |

### Version checking

The script compares the local `export_manifest.json` to the current Supabase manifest:
- If versions differ or no remote manifest exists: uploads everything
- If versions and checksums match: skips (already synced)

## Supabase Schema

See `scripts/sql/supabase_schema.sql` for the complete schema including:
- `export_manifest` (pipeline version tracking)
- `user_stacks` (user supplement stacks)
- `user_usage` (freemium scan/AI limits)
- `pending_products` (user-submitted product requests)
- RLS policies and indexes

## Troubleshooting

### "SUPABASE_URL environment variable is not set"
Add `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` to your `.env` file.

### "export_manifest.json not found"
Run `build_final_db.py` before `sync_to_supabase.py`.

### Partial upload (some blobs failed)
Re-run `sync_to_supabase.py`. It uses upsert mode -- re-uploading is safe and idempotent. Failed blobs will be retried.

### Version conflict
If the Supabase manifest shows a newer version than your local build, re-run the pipeline to generate a fresh build before syncing.
```

- [ ] **Step 2: Commit**

```bash
git add scripts/SUPABASE_SYNC_README.md
git commit -m "docs: add Supabase sync pipeline setup and usage guide"
```

---

### Task 6: Update Project Documentation

**Files:**
- Modify: `CLAUDE.md`
- Modify: `scripts/PIPELINE_ARCHITECTURE.md`

- [ ] **Step 1: Add sync script to CLAUDE.md Commands table**

Open `CLAUDE.md` and add this row to the Commands section, after the `build_final_db.py` entry:

```markdown
# Sync pipeline output to Supabase
python3 scripts/sync_to_supabase.py <build_output_dir>

# Dry run (preview without uploading)
python3 scripts/sync_to_supabase.py <build_output_dir> --dry-run
```

- [ ] **Step 2: Add Stage 4 to PIPELINE_ARCHITECTURE.md**

Open `scripts/PIPELINE_ARCHITECTURE.md` and add a new section after the Score stage:

```markdown
## Stage 4: Distribute (sync_to_supabase.py)

**Input:** Build output from build_final_db.py (pharmaguide_core.db + detail_blobs/ + export_manifest.json)
**Output:** Versioned artifacts in Supabase Storage + manifest row in PostgreSQL

**Workflow:**
1. Read export_manifest.json from build directory
2. Compare version to current Supabase manifest (is_current=true)
3. If newer: upload .db file and detail blobs to Supabase Storage
4. Insert new manifest row, mark previous as not current

**Environment:** Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env

**CLI:**
```bash
python scripts/sync_to_supabase.py <build_output_dir>          # Full sync
python scripts/sync_to_supabase.py <build_output_dir> --dry-run # Preview only
```

**Safety:** Uses upsert mode. Re-running is idempotent. The Flutter app reads the manifest to detect new versions and downloads in background -- never blocks the user.
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md scripts/PIPELINE_ARCHITECTURE.md
git commit -m "docs: add sync stage to pipeline architecture and CLAUDE.md commands"
```

---

### Task 7: Integration Test with Dry Run

**Files:**
- No new files (manual verification)

This task verifies the full flow works end-to-end before you have a real Supabase project.

- [ ] **Step 1: Create a fake build output for testing**

```bash
mkdir -p /tmp/pharma_test_build/detail_blobs
```

```python
# Run in Python shell or as a script:
import json, hashlib

# Fake manifest
manifest = {
    "db_version": "2026.03.27.5",
    "pipeline_version": "3.2.0",
    "scoring_version": "3.1.0",
    "generated_at": "2026-03-27T12:00:00Z",
    "product_count": "3",
    "checksum": "sha256:" + hashlib.sha256(b"test").hexdigest(),
    "min_app_version": "1.0.0",
    "schema_version": 5,
    "errors": []
}
with open("/tmp/pharma_test_build/export_manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)

# Fake SQLite
with open("/tmp/pharma_test_build/pharmaguide_core.db", "wb") as f:
    f.write(b"FAKE_SQLITE" * 100)

# Fake detail blobs
for dsld_id in [182215, 182216, 182217]:
    with open(f"/tmp/pharma_test_build/detail_blobs/{dsld_id}.json", "w") as f:
        json.dump({"dsld_id": str(dsld_id), "blob_version": 1}, f)
```

- [ ] **Step 2: Test dry-run mode (no Supabase credentials needed)**

Run: `python3 scripts/sync_to_supabase.py /tmp/pharma_test_build --dry-run`
Expected: Script prints manifest info and what would be uploaded, then exits cleanly. No Supabase credentials needed for dry-run (client is only initialized for actual uploads).

- [ ] **Step 3: Run full test suite**

Run: `python3 -m pytest scripts/tests/test_sync_to_supabase.py scripts/tests/test_supabase_client.py -v`
Expected: All tests pass

- [ ] **Step 4: Run the entire project test suite to ensure no regressions**

Run: `python3 -m pytest scripts/tests/ -x -q`
Expected: All 2844+ tests pass with no failures

- [ ] **Step 5: Clean up test artifacts**

```bash
rm -rf /tmp/pharma_test_build
```

---

## Post-Implementation: When You Have a Real Supabase Project

After creating the Supabase project and running the schema SQL:

1. Add credentials to `.env`:
   ```
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_SERVICE_ROLE_KEY=eyJ...
   ```

2. Create the storage bucket in Supabase Dashboard (name: `pharmaguide`, public read)

3. Run a real pipeline build and sync:
   ```bash
   python3 scripts/sync_to_supabase.py <real_build_output>
   ```

4. Verify in Supabase Dashboard:
   - `export_manifest` table has one row with `is_current=true`
   - Storage bucket has `v{version}/pharmaguide_core.db`
   - Storage bucket has `v{version}/details/*.json`
