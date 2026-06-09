"""Tripwire: ``sync_to_supabase`` must REFUSE to upload a v4-schema build to
Supabase unless ``--allow-v4-cutover`` is passed.

The v4 export schema (2.0.0) drops ``score_quality_80`` /
``score_display_80`` in favour of ``quality_score_v4_100`` + the six pillars.
Pushing a v4 build to Supabase before Flutter proves v4-reader support can
break older app builds. This guard makes that footgun impossible to fire by
accident. Dry-run is a safe preview and never blocks.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from sync_to_supabase import assert_cutover_sync_allowed  # noqa: E402


def _v4_manifest():
    return {"schema_version": "2.0.0", "score_model": "v4", "db_version": "x", "product_count": 1}


def _v3_manifest():
    return {"schema_version": "1.6.0", "score_model": "v3", "db_version": "x", "product_count": 1}


def test_v4_build_blocked_without_flag():
    with pytest.raises(RuntimeError, match="v4"):
        assert_cutover_sync_allowed(_v4_manifest(), allow_v4_cutover=False, dry_run=False)


def test_v4_build_allowed_with_explicit_flag():
    # The explicit acknowledgement lets it through (returns is_v4=True, no raise).
    assert assert_cutover_sync_allowed(_v4_manifest(), allow_v4_cutover=True, dry_run=False) is True


def test_v3_build_never_blocked():
    assert assert_cutover_sync_allowed(_v3_manifest(), allow_v4_cutover=False, dry_run=False) is False


def test_v4_dry_run_is_a_safe_preview_never_blocks():
    # dry-run uploads nothing, so it must not raise even without the flag.
    assert assert_cutover_sync_allowed(_v4_manifest(), allow_v4_cutover=False, dry_run=True) is True


def test_v4_detected_by_schema_major_even_if_score_model_missing():
    # A 2.x schema with no score_model field is still a v4 build → blocked.
    manifest = {"schema_version": "2.1.0", "product_count": 1}
    with pytest.raises(RuntimeError):
        assert_cutover_sync_allowed(manifest, allow_v4_cutover=False, dry_run=False)


def test_v3_schema_without_score_model_not_blocked():
    # A legacy 1.x schema with no score_model is v3 → allowed.
    manifest = {"schema_version": "1.6.0", "product_count": 1}
    assert assert_cutover_sync_allowed(manifest, allow_v4_cutover=False, dry_run=False) is False


def test_error_message_names_flutter_and_the_flag():
    with pytest.raises(RuntimeError) as exc:
        assert_cutover_sync_allowed(_v4_manifest(), allow_v4_cutover=False, dry_run=False)
    msg = str(exc.value)
    assert "Flutter" in msg
    assert "--allow-v4-cutover" in msg
    assert "still reads" not in msg
