"""Thin Supabase client wrapper for PharmaGuide sync operations.

Initializes from environment variables (loaded via env_loader.py).
Provides typed helpers for manifest queries and storage uploads.
"""

import json
import os

#: Storage bucket for pipeline artifacts (core DB, detail blobs, indexes,
#: quarantine); the app reads the same bucket (Flutter
#: ``SupabaseContract.storageBucket``). Product images live in a separate
#: bucket (``sync_to_supabase.PRODUCT_IMAGE_BUCKET``).
STORAGE_BUCKET = "pharmaguide"


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


def core_db_remote_path(db_version):
    """Storage path of a catalog's core DB; the app reads the same path
    (Flutter ``SupabaseContract.coreDbPath``)."""
    return f"v{db_version}/pharmaguide_core.db"


def core_db_compressed_remote_path(db_version):
    """Storage path of the gzip of that core DB. Beside it, ``.json`` describes it
    for builds with no release keys (Flutter ``SupabaseContract.compressedCoreDbPath``)."""
    return f"{core_db_remote_path(db_version)}.gz"


def rules_db_remote_path(rules_version):
    """Immutable Storage path of an interaction rules file named by a signed release."""
    return f"rules/{rules_version}/interaction_db.sqlite"


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


PUBLICATION_RPC = "rotate_manifest_with_submission_approvals"


def require_publication_contract(signed_release=False):
    """Verify the service-role-visible RPC contract without activating anything.

    PostgREST's role-filtered OpenAPI schema checks the deployed operation and
    its arguments. This proves availability, not successful future activation.
    The signed-release arguments are required only when publishing a signed
    release, so the unsigned path keeps working before that migration deploys.
    """
    import requests
    _load_env()
    url = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    response = requests.get(url + "/rest/v1/", headers={
        "apikey": key, "Authorization": "Bearer " + key,
        "Accept": "application/openapi+json",
    }, timeout=20)
    response.raise_for_status()
    operation = response.json().get("paths", {}).get("/rpc/" + PUBLICATION_RPC, {}).get("post", {})
    bodies = [p.get("schema", {}) for p in operation.get("parameters", []) if p.get("in") == "body"]
    expected = {
        "p_db_version": "text", "p_pipeline_version": "text",
        "p_scoring_version": "text", "p_schema_version": "text",
        "p_product_count": "integer", "p_checksum": "text",
        "p_generated_at": "timestamp with time zone", "p_min_app_version": "text",
        "p_submission_approvals": "jsonb",
    }
    if signed_release:
        expected.update({
            "p_release_sequence": "bigint", "p_signed_release": "text",
            "p_release_signature": "text",
        })
    if len(bodies) != 1:
        raise ValueError("Deployed publication contract is unavailable to the publishing role")
    schema = bodies[0]
    # PostgREST 14 reports the Postgres type name; 16 reports int32 and int64.
    spellings = {"integer": {"integer", "int32"}, "bigint": {"bigint", "int64"}}
    if (any(schema.get("properties", {}).get(k, {}).get("format") not in spellings.get(v, {v})
            for k, v in expected.items())
            or not set(schema.get("required", [])).issubset(expected)):
        raise ValueError("Deployed publication contract arguments do not match this publisher")


def fetch_manifest_version(client, db_version):
    """Look up any published version, including inactive release history."""
    response = (client.table("export_manifest").select("*")
                .eq("db_version", db_version).limit(1).execute())
    return parse_manifest_response({"data": response.data})


def fetch_latest_signed_rules(client, page_size=1000):
    """The rules entry of the newest signed release that named usable rules, or None.

    A catalog-only release names none, and phones keep what they hold. Rules the
    newest release blocks don't count: phones have stopped using them, and comparing
    with them would hide a rule carried over from the blocked file. Only the newest
    list applies, because phones replace theirs with it.
    """
    blocked = None
    start = 0
    while True:
        rows = (client.table("export_manifest").select("signed_release")
                .not_.is_("signed_release", "null")
                .order("release_sequence", desc=True)
                .range(start, start + page_size - 1).execute()).data or []
        if not rows:
            return None
        for row in rows:
            release = json.loads(row["signed_release"])
            if blocked is None:
                blocked = set(release.get("blocked_versions", {}).get("rules", []))
            rules = release.get("rules")
            if rules and rules.get("version") not in blocked:
                return rules
        start += len(rows)


def insert_manifest(client, manifest_data, submission_approvals=None,
                    release_sequence=None, signed_release=None, release_signature=None):
    """Atomically insert a new manifest and mark previous as not current.

    Uses the approval-aware publication RPC so manifest rotation stays inside a
    single database transaction. The SQL function owns the exact update/insert
    order; callers should treat it as atomic. The signed-release params are sent
    only when present, and only all together.

    Raises RuntimeError if the RPC returns an error or unexpected response.
    """
    signed_params = {
        "p_release_sequence": release_sequence,
        "p_signed_release": signed_release,
        "p_release_signature": release_signature,
    }
    present = [value is not None for value in signed_params.values()]
    if any(present) and not all(present):
        raise ValueError("a signed release needs its sequence, text and signature together")
    params = {
        "p_db_version": manifest_data["db_version"],
        "p_pipeline_version": manifest_data["pipeline_version"],
        "p_scoring_version": manifest_data["scoring_version"],
        "p_schema_version": str(manifest_data["schema_version"]),
        "p_product_count": int(manifest_data["product_count"]),
        "p_checksum": manifest_data["checksum"],
        "p_generated_at": manifest_data["generated_at"],
        "p_min_app_version": manifest_data.get("min_app_version", "1.0.0"),
        "p_submission_approvals": submission_approvals or [],
    }
    if all(present):
        params.update(signed_params)
    response = client.rpc(PUBLICATION_RPC, params).execute()

    # The RPC returns the new manifest UUID on success.
    # Validate that we got a non-empty result back.
    if response.data is None:
        raise RuntimeError(
            "catalog activation RPC returned None — manifest rotation may have failed. "
            "Check Supabase logs for constraint violations or permission errors."
        )

    return response


def upload_file(client, bucket, remote_path, local_path,
                content_type="application/octet-stream",
                upsert=True,
                cache_control=None):
    """Upload a file to Supabase Storage.

    Streams the file to avoid loading large .db files into memory.
    Returns the storage response.

    `cache_control` is the max-age in seconds (as int or str). Pass
    CACHE_CONTROL_IMMUTABLE for content-addressed / versioned paths so the
    Supabase CDN serves them from edge instead of origin.
    """
    file_options = {
        "content-type": content_type,
        "upsert": "true" if upsert else "false",
    }
    if cache_control is not None:
        file_options["cache-control"] = str(cache_control)
    with open(local_path, "rb") as f:
        try:
            return client.storage.from_(bucket).upload(
                path=remote_path,
                file=f,
                file_options=file_options,
            )
        except Exception:
            if upsert:
                raise
            # Create-only is atomic at Storage. A collision or a lost success
            # response is retryable only when the stored bytes are identical.
            remote_bytes = download_file(client, bucket, remote_path)
            f.seek(0)
            if remote_bytes != f.read():
                raise ValueError(f"immutable Storage object differs: {remote_path}")
            return None


def download_file(client, bucket, remote_path):
    """Download a file from Supabase Storage and return its bytes."""
    return client.storage.from_(bucket).download(remote_path)


# One year — for immutable artifacts only: sha256-addressed detail blobs and
# version-stamped catalog paths (v{db_version}/...). Never use for "current"
# pointers like the manifest.
CACHE_CONTROL_IMMUTABLE = 31536000


def list_storage_paths(client, bucket, prefix, limit=1000, offset=0):
    """List storage objects under a prefix using paged bucket.list()."""
    return client.storage.from_(bucket).list(
        path=prefix,
        options={"limit": limit, "offset": offset},
    )
