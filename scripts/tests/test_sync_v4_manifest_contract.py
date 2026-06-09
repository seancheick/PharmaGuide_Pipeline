"""v4 Supabase sync contract.

v4 schema 2.0.0 is now the production catalog contract. The sync layer should
identify v4 builds for logging/observability, but must not require a cutover
flag or block a normal release run.
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from sync_to_supabase import is_v4_manifest, parse_args  # noqa: E402


def test_v4_manifest_detected_by_score_model() -> None:
    manifest = {
        "schema_version": "2.0.0",
        "score_model": "v4",
        "db_version": "x",
        "product_count": 1,
    }
    assert is_v4_manifest(manifest) is True


def test_v4_manifest_detected_by_schema_major() -> None:
    manifest = {"schema_version": "2.1.0", "product_count": 1}
    assert is_v4_manifest(manifest) is True


def test_legacy_schema_not_detected_as_v4() -> None:
    manifest = {"schema_version": "1.6.0", "score_model": "legacy"}
    assert is_v4_manifest(manifest) is False


def test_sync_cli_has_no_cutover_flag() -> None:
    args = parse_args(["/tmp/build", "--dry-run"])
    assert not any("cutover" in key for key in vars(args))
