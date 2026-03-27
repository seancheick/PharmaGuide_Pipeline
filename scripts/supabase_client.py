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
    """
    _load_env()
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


def upload_file(client, bucket, remote_path, local_path,
                content_type="application/octet-stream"):
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
