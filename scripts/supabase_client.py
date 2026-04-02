"""Thin Supabase client wrapper for PharmaGuide sync operations.

Initializes from environment variables (loaded via env_loader.py).
Provides typed helpers for manifest queries and storage uploads.
"""

import os


def _load_env():
    """Load .env the same way all pipeline scripts do."""
    import sys
    scripts_dir = os.path.dirname(__file__)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import env_loader  # noqa: F401


def get_supabase_client():
    """Create and return a Supabase client using service role credentials.

    Raises ValueError if required environment variables are missing.
    Uses a 5-minute storage timeout for large .db file uploads.
    """
    _load_env()
    from supabase import create_client, ClientOptions

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

    return create_client(url, key, options=ClientOptions(
        storage_client_timeout=300,  # 5 minutes for large DB uploads
    ))


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

    Uses the rotate_manifest RPC function so manifest rotation stays inside a
    single database transaction. The SQL function owns the exact update/insert
    order; callers should treat it as atomic.
    """
    response = client.rpc("rotate_manifest", {
        "p_db_version": manifest_data["db_version"],
        "p_pipeline_version": manifest_data["pipeline_version"],
        "p_scoring_version": manifest_data["scoring_version"],
        "p_schema_version": str(manifest_data["schema_version"]),
        "p_product_count": int(manifest_data["product_count"]),
        "p_checksum": manifest_data["checksum"],
        "p_generated_at": manifest_data["generated_at"],
        "p_min_app_version": manifest_data.get("min_app_version", "1.0.0"),
    }).execute()
    return response


def upload_file(client, bucket, remote_path, local_path,
                content_type="application/octet-stream",
                upsert=True):
    """Upload a file to Supabase Storage.

    Streams the file to avoid loading large .db files into memory.
    Returns the storage response.
    """
    with open(local_path, "rb") as f:
        return client.storage.from_(bucket).upload(
            path=remote_path,
            file=f,
            file_options={"content-type": content_type, "upsert": "true" if upsert else "false"},
        )


def storage_object_exists(client, bucket, remote_path):
    """Return True when a storage object already exists at the given path."""
    return client.storage.from_(bucket).exists(remote_path)


def list_storage_paths(client, bucket, prefix, limit=1000, offset=0):
    """List storage objects under a prefix using paged bucket.list()."""
    return client.storage.from_(bucket).list(
        path=prefix,
        options={"limit": limit, "offset": offset},
    )
