"""Tests for scripts/release_catalog_artifact.py.

These tests build synthetic pipeline-output directories (a real SQLite
file plus a matching export_manifest.json) and exercise every validation
gate and the atomic staging path. No real pipeline artifacts are touched.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# Make scripts/ importable when running from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import release_catalog_artifact as rca  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


DEFAULT_DB_VERSION = "2026.04.10.222555"
DEFAULT_SCHEMA_VERSION = "1.3.2"
DEFAULT_PIPELINE_VERSION = "3.4.0"
DEFAULT_SCORING_VERSION = "3.4.0"
DEFAULT_MIN_APP_VERSION = "1.0.0"


def _build_products_core_sql() -> str:
    """A minimal products_core schema with the single column our validation
    needs (`export_version`) plus enough columns to stand in for a real
    90-col row. We don't need the full 90 cols here — the release script
    only cares about row count, integrity, and export_version presence.
    """
    return (
        "CREATE TABLE products_core ("
        " dsld_id TEXT PRIMARY KEY,"
        " product_name TEXT,"
        " export_version TEXT NOT NULL"
        ")"
    )


def _make_fake_db(
    db_path: Path,
    *,
    row_count: int,
    schema_version: str = DEFAULT_SCHEMA_VERSION,
    db_version: str = DEFAULT_DB_VERSION,
    include_export_manifest_table: bool = True,
    drop_required_embedded_key: str | None = None,
    export_version_override: str | None = None,
) -> None:
    """Create a synthetic pipeline-output SQLite file.

    The file has `products_core` with `row_count` rows (all with a
    non-empty `export_version`) and the in-SQLite `export_manifest`
    key-value table that `build_final_db.py` writes. Tests can mutate
    the shape to exercise failure paths.
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(_build_products_core_sql())
        ev = export_version_override if export_version_override is not None else schema_version
        for i in range(row_count):
            conn.execute(
                "INSERT INTO products_core (dsld_id, product_name, export_version) "
                "VALUES (?, ?, ?)",
                (f"ID{i:05d}", f"Product {i}", ev),
            )
        if include_export_manifest_table:
            conn.execute(
                "CREATE TABLE export_manifest (key TEXT PRIMARY KEY, value TEXT)"
            )
            rows = [
                ("db_version", db_version),
                ("schema_version", schema_version),
                ("pipeline_version", DEFAULT_PIPELINE_VERSION),
                ("scoring_version", DEFAULT_SCORING_VERSION),
                ("product_count", str(row_count)),
                ("min_app_version", DEFAULT_MIN_APP_VERSION),
                ("generated_at", "2026-04-10T22:25:55Z"),
            ]
            if drop_required_embedded_key:
                rows = [(k, v) for k, v in rows if k != drop_required_embedded_key]
            conn.executemany(
                "INSERT INTO export_manifest VALUES (?, ?)", rows
            )
        conn.commit()
    finally:
        conn.close()


def _write_manifest_json(
    manifest_path: Path,
    db_path: Path,
    *,
    row_count: int,
    schema_version: str = DEFAULT_SCHEMA_VERSION,
    db_version: str = DEFAULT_DB_VERSION,
    override_checksum: str | None = None,
    override_product_count: int | None = None,
    drop_key: str | None = None,
) -> dict:
    """Write a JSON manifest alongside the DB and return the written dict."""
    checksum = override_checksum or ("sha256:" + rca.compute_sha256(db_path))
    manifest = {
        "db_version": db_version,
        "schema_version": schema_version,
        "pipeline_version": DEFAULT_PIPELINE_VERSION,
        "scoring_version": DEFAULT_SCORING_VERSION,
        "product_count": (
            override_product_count if override_product_count is not None else row_count
        ),
        "min_app_version": DEFAULT_MIN_APP_VERSION,
        # 2026-05-14 — generate fresh per-call so tests using main() pass
        # the freshness guard. Tests that need a stale timestamp overwrite
        # this field after the fixture writes it (see freshness-guard tests).
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checksum": checksum,
    }
    if drop_key:
        manifest.pop(drop_key, None)
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return manifest


@pytest.fixture
def good_release_dir(tmp_path: Path) -> Path:
    """A fully valid pipeline output dir with 1000 products."""
    input_dir = tmp_path / "final_db_output"
    input_dir.mkdir()
    db_path = input_dir / "pharmaguide_core.db"
    _make_fake_db(db_path, row_count=1000)
    _write_manifest_json(input_dir / "export_manifest.json", db_path, row_count=1000)
    return input_dir


# ---------------------------------------------------------------------------
# Pure helper unit tests
# ---------------------------------------------------------------------------


def test_compute_sha256_matches_hashlib(tmp_path: Path) -> None:
    f = tmp_path / "blob.bin"
    content = b"hello world " * 1024
    f.write_bytes(content)
    assert rca.compute_sha256(f) == hashlib.sha256(content).hexdigest()


def test_strip_sha256_prefix_handles_both_forms() -> None:
    assert rca.strip_sha256_prefix("abc123") == "abc123"
    assert rca.strip_sha256_prefix("sha256:abc123") == "abc123"
    assert rca.strip_sha256_prefix("SHA256:abc123") == "abc123"
    assert rca.strip_sha256_prefix("  sha256:abc123  ") == "abc123"
    assert rca.strip_sha256_prefix(None) is None


def test_strip_sha256_prefix_rejects_non_string() -> None:
    with pytest.raises(TypeError):
        rca.strip_sha256_prefix(12345)  # type: ignore[arg-type]


def test_ensure_sha256_prefix_adds_prefix() -> None:
    assert rca.ensure_sha256_prefix("abc") == "sha256:abc"
    assert rca.ensure_sha256_prefix("sha256:abc") == "sha256:abc"
    assert rca.ensure_sha256_prefix(None) is None


def test_read_sqlite_manifest_returns_keys(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    _make_fake_db(db_path, row_count=5)
    embedded = rca.read_sqlite_manifest(db_path)
    assert embedded["db_version"] == DEFAULT_DB_VERSION
    assert embedded["schema_version"] == DEFAULT_SCHEMA_VERSION
    assert embedded["product_count"] == "5"


def test_read_sqlite_manifest_raises_when_table_missing(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    _make_fake_db(db_path, row_count=1, include_export_manifest_table=False)
    with pytest.raises(rca.ReleaseValidationError, match="embedded export_manifest table"):
        rca.read_sqlite_manifest(db_path)


def test_count_products_and_versioned_count(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    _make_fake_db(db_path, row_count=42)
    assert rca.count_products(db_path) == 42
    assert rca.count_products_with_export_version(db_path) == 42


def test_count_versioned_is_zero_when_all_blank(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    _make_fake_db(db_path, row_count=3, export_version_override="")
    assert rca.count_products(db_path) == 3
    assert rca.count_products_with_export_version(db_path) == 0


# ---------------------------------------------------------------------------
# Validation gate tests
# ---------------------------------------------------------------------------


def test_validate_release_candidate_happy_path(good_release_dir: Path) -> None:
    result = rca.validate_release_candidate(
        input_dir=good_release_dir, min_products=500
    )
    assert result["product_count"] == 1000
    assert result["integrity"] == "ok"
    assert isinstance(result["checksum_sha256"], str)
    assert len(result["checksum_sha256"]) == 64


def test_validate_fails_when_db_missing(tmp_path: Path) -> None:
    input_dir = tmp_path / "empty"
    input_dir.mkdir()
    (input_dir / "export_manifest.json").write_text("{}")
    with pytest.raises(rca.ReleaseValidationError, match="missing pharmaguide_core.db"):
        rca.validate_release_candidate(input_dir=input_dir, min_products=1)


def test_validate_fails_when_manifest_missing(tmp_path: Path) -> None:
    input_dir = tmp_path / "db_only"
    input_dir.mkdir()
    db_path = input_dir / "pharmaguide_core.db"
    _make_fake_db(db_path, row_count=10)
    with pytest.raises(rca.ReleaseValidationError, match="missing export_manifest.json"):
        rca.validate_release_candidate(input_dir=input_dir, min_products=1)


def test_validate_fails_below_min_products(tmp_path: Path) -> None:
    input_dir = tmp_path / "tiny"
    input_dir.mkdir()
    db_path = input_dir / "pharmaguide_core.db"
    _make_fake_db(db_path, row_count=10)
    _write_manifest_json(input_dir / "export_manifest.json", db_path, row_count=10)
    with pytest.raises(rca.ReleaseValidationError, match="only 10 products"):
        rca.validate_release_candidate(input_dir=input_dir, min_products=500)


def test_validate_fails_when_export_version_missing_for_all_rows(tmp_path: Path) -> None:
    input_dir = tmp_path / "blank_versions"
    input_dir.mkdir()
    db_path = input_dir / "pharmaguide_core.db"
    _make_fake_db(db_path, row_count=600, export_version_override="")
    _write_manifest_json(
        input_dir / "export_manifest.json", db_path, row_count=600
    )
    with pytest.raises(rca.ReleaseValidationError, match="zero rows with a non-empty export_version"):
        rca.validate_release_candidate(input_dir=input_dir, min_products=500)


def test_validate_fails_when_embedded_manifest_missing_key(tmp_path: Path) -> None:
    input_dir = tmp_path / "bad_embedded"
    input_dir.mkdir()
    db_path = input_dir / "pharmaguide_core.db"
    _make_fake_db(db_path, row_count=600, drop_required_embedded_key="db_version")
    _write_manifest_json(input_dir / "export_manifest.json", db_path, row_count=600)
    with pytest.raises(rca.ReleaseValidationError, match="missing required keys"):
        rca.validate_release_candidate(input_dir=input_dir, min_products=500)


def test_validate_fails_when_manifest_json_missing_checksum(tmp_path: Path) -> None:
    input_dir = tmp_path / "no_checksum"
    input_dir.mkdir()
    db_path = input_dir / "pharmaguide_core.db"
    _make_fake_db(db_path, row_count=600)
    _write_manifest_json(
        input_dir / "export_manifest.json",
        db_path,
        row_count=600,
        drop_key="checksum",
    )
    with pytest.raises(rca.ReleaseValidationError, match="missing required keys.*checksum"):
        rca.validate_release_candidate(input_dir=input_dir, min_products=500)


def test_validate_fails_on_schema_version_mismatch(tmp_path: Path) -> None:
    input_dir = tmp_path / "schema_mismatch"
    input_dir.mkdir()
    db_path = input_dir / "pharmaguide_core.db"
    _make_fake_db(db_path, row_count=600, schema_version="1.3.2")
    _write_manifest_json(
        input_dir / "export_manifest.json",
        db_path,
        row_count=600,
        schema_version="1.4.0",  # intentional drift
    )
    with pytest.raises(rca.ReleaseValidationError, match="schema_version mismatch"):
        rca.validate_release_candidate(input_dir=input_dir, min_products=500)


def test_validate_fails_on_db_version_mismatch(tmp_path: Path) -> None:
    input_dir = tmp_path / "dbver_mismatch"
    input_dir.mkdir()
    db_path = input_dir / "pharmaguide_core.db"
    _make_fake_db(db_path, row_count=600, db_version="2026.04.10.000000")
    _write_manifest_json(
        input_dir / "export_manifest.json",
        db_path,
        row_count=600,
        db_version="2026.04.11.999999",  # intentional drift
    )
    with pytest.raises(rca.ReleaseValidationError, match="db_version mismatch"):
        rca.validate_release_candidate(input_dir=input_dir, min_products=500)


def test_validate_fails_on_product_count_mismatch(tmp_path: Path) -> None:
    input_dir = tmp_path / "count_mismatch"
    input_dir.mkdir()
    db_path = input_dir / "pharmaguide_core.db"
    _make_fake_db(db_path, row_count=600)
    _write_manifest_json(
        input_dir / "export_manifest.json",
        db_path,
        row_count=600,
        override_product_count=999,
    )
    with pytest.raises(rca.ReleaseValidationError, match="product_count mismatch"):
        rca.validate_release_candidate(input_dir=input_dir, min_products=500)


def test_validate_fails_on_checksum_mismatch(tmp_path: Path) -> None:
    input_dir = tmp_path / "checksum_mismatch"
    input_dir.mkdir()
    db_path = input_dir / "pharmaguide_core.db"
    _make_fake_db(db_path, row_count=600)
    _write_manifest_json(
        input_dir / "export_manifest.json",
        db_path,
        row_count=600,
        override_checksum="sha256:" + "0" * 64,  # definitely wrong
    )
    with pytest.raises(rca.ReleaseValidationError, match="SHA-256 mismatch"):
        rca.validate_release_candidate(input_dir=input_dir, min_products=500)


# ---------------------------------------------------------------------------
# Staging tests
# ---------------------------------------------------------------------------


def test_stage_release_creates_all_three_files(good_release_dir: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "dist"
    validation = rca.validate_release_candidate(
        input_dir=good_release_dir, min_products=500
    )
    result = rca.stage_release(validation=validation, output_dir=output_dir)

    assert result["output_dir"] == output_dir.resolve()
    assert (output_dir / "pharmaguide_core.db").is_file()
    assert (output_dir / "export_manifest.json").is_file()
    assert (output_dir / "RELEASE_NOTES.md").is_file()
    assert result["db_version"] == DEFAULT_DB_VERSION
    assert result["schema_version"] == DEFAULT_SCHEMA_VERSION
    assert result["product_count"] == 1000


def test_stage_release_manifest_has_both_checksum_formats(
    good_release_dir: Path, tmp_path: Path
) -> None:
    output_dir = tmp_path / "dist"
    validation = rca.validate_release_candidate(
        input_dir=good_release_dir, min_products=500
    )
    rca.stage_release(validation=validation, output_dir=output_dir)
    data = json.loads((output_dir / "export_manifest.json").read_text())
    assert data["checksum"].startswith("sha256:")
    assert data["checksum_sha256"] == data["checksum"].split(":", 1)[1]
    assert len(data["checksum_sha256"]) == 64
    assert "release_staged_at" in data


def test_stage_release_is_atomic_on_failure(
    good_release_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_dir = tmp_path / "dist"
    output_dir.mkdir()
    sentinel = output_dir / "pre_existing_artifact.txt"
    sentinel.write_text("must not be destroyed by a failed stage")

    validation = rca.validate_release_candidate(
        input_dir=good_release_dir, min_products=500
    )

    # Force the staged copy self-verification to fail by returning a wrong
    # hash for every call after validation completes. This simulates a copy
    # corruption between the source read and the staged read.
    monkeypatch.setattr(rca, "compute_sha256", lambda _path: "0" * 64)

    with pytest.raises(rca.ReleaseValidationError, match="Copy corrupted"):
        rca.stage_release(validation=validation, output_dir=output_dir)

    # The sentinel file must still be present — the failed stage must not
    # have touched output_dir.
    assert sentinel.exists()
    assert sentinel.read_text() == "must not be destroyed by a failed stage"


def test_stage_release_replaces_existing_output_dir(
    good_release_dir: Path, tmp_path: Path
) -> None:
    output_dir = tmp_path / "dist"
    output_dir.mkdir()
    stale = output_dir / "stale_file_from_previous_run.txt"
    stale.write_text("old release")

    validation = rca.validate_release_candidate(
        input_dir=good_release_dir, min_products=500
    )
    rca.stage_release(validation=validation, output_dir=output_dir)

    # Previous contents are replaced, not merged.
    assert not stale.exists()
    assert (output_dir / "pharmaguide_core.db").is_file()


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


def test_main_exits_0_on_success(
    good_release_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    output_dir = tmp_path / "dist"
    exit_code = rca.main(
        [
            "--input-dir",
            str(good_release_dir),
            "--output-dir",
            str(output_dir),
            "--min-products",
            "500",
        ]
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "staged" in captured.out
    assert (output_dir / "pharmaguide_core.db").is_file()


def test_main_exits_1_on_validation_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    exit_code = rca.main(
        [
            "--input-dir",
            str(empty),
            "--output-dir",
            str(tmp_path / "dist"),
            "--min-products",
            "1",
        ]
    )
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "VALIDATION FAILED" in captured.err


def test_main_print_json_emits_parseable_output(
    good_release_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    output_dir = tmp_path / "dist"
    exit_code = rca.main(
        [
            "--input-dir",
            str(good_release_dir),
            "--output-dir",
            str(output_dir),
            "--min-products",
            "500",
            "--print-json",
        ]
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["db_version"] == DEFAULT_DB_VERSION
    assert payload["schema_version"] == DEFAULT_SCHEMA_VERSION
    assert payload["product_count"] == 1000


# ---------------------------------------------------------------------------
# Freshness guard — added 2026-05-14 to prevent re-staging stale builds
# (e.g., from a leftover scripts/final_db_output/ that wasn't refreshed).
# ---------------------------------------------------------------------------


def _iso_utc(offset_hours: float) -> str:
    """Helper: return a now+offset ISO-8601 UTC string."""
    return (datetime.now(timezone.utc) + timedelta(hours=offset_hours)).isoformat()


def test_freshness_passes_when_manifest_is_recent() -> None:
    """Fresh manifest (1h old) — guard stays silent at default 24h max."""
    manifest = {"generated_at": _iso_utc(-1)}
    rca.check_release_freshness(
        manifest=manifest, max_age_hours=24.0, allow_stale=False
    )  # no raise


def test_freshness_raises_when_manifest_is_stale() -> None:
    """Stale manifest (48h old) — guard raises at default 24h max."""
    manifest = {"generated_at": _iso_utc(-48)}
    with pytest.raises(rca.ReleaseValidationError) as exc:
        rca.check_release_freshness(
            manifest=manifest, max_age_hours=24.0, allow_stale=False
        )
    msg = str(exc.value)
    assert "stale" in msg.lower()
    assert "48" in msg  # age reported
    assert "--allow-stale" in msg  # escape hatch documented
    assert "batch_run_all_datasets.sh" in msg  # remediation hint


def test_freshness_allow_stale_bypasses_with_warning(
    capsys: pytest.CaptureFixture,
) -> None:
    """--allow-stale lets the build through but emits a warning to stderr."""
    manifest = {"generated_at": _iso_utc(-48)}
    rca.check_release_freshness(
        manifest=manifest, max_age_hours=24.0, allow_stale=True
    )  # no raise
    captured = capsys.readouterr()
    assert "WARNING" in captured.err
    assert "--allow-stale" in captured.err


def test_freshness_accepts_z_suffix_timestamps() -> None:
    """build_final_db.py writes "...Z"; Python <3.11 doesn't parse that
    natively. Verify the normalization works."""
    # 1h ago, formatted with 'Z'
    recent = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(microsecond=0)
    manifest = {"generated_at": recent.strftime("%Y-%m-%dT%H:%M:%SZ")}
    rca.check_release_freshness(
        manifest=manifest, max_age_hours=24.0, allow_stale=False
    )  # no raise


def test_freshness_naive_timestamp_assumed_utc() -> None:
    """Defensive: timestamps without tz are treated as UTC rather than
    crashing. A 1h-ago naive timestamp is still within a 24h window."""
    naive_recent = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(
        tzinfo=None
    )
    manifest = {"generated_at": naive_recent.isoformat()}
    rca.check_release_freshness(
        manifest=manifest, max_age_hours=24.0, allow_stale=False
    )  # no raise


def test_freshness_raises_on_unparseable_timestamp() -> None:
    """Garbage generated_at fails loudly rather than silently allowing
    a potentially-stale build through."""
    manifest = {"generated_at": "not-a-timestamp"}
    with pytest.raises(rca.ReleaseValidationError) as exc:
        rca.check_release_freshness(
            manifest=manifest, max_age_hours=24.0, allow_stale=False
        )
    assert "ISO-8601" in str(exc.value)


def test_freshness_missing_generated_at_is_silent_defensive() -> None:
    """If generated_at is missing, the guard returns silently —
    validate_release_candidate already enforces presence; this is a
    defensive no-op for unit-test isolation."""
    rca.check_release_freshness(
        manifest={}, max_age_hours=24.0, allow_stale=False
    )  # no raise


def test_main_exits_1_when_input_dir_is_stale(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """End-to-end: main() returns 1 with a clear FRESHNESS GATE message
    when the input dir's manifest is older than --max-age-hours."""
    input_dir = tmp_path / "stale_build"
    input_dir.mkdir()
    db_path = input_dir / "pharmaguide_core.db"
    _make_fake_db(db_path, row_count=1000)
    # Overwrite manifest with a 48h-old generated_at
    manifest_dict = _write_manifest_json(
        input_dir / "export_manifest.json", db_path, row_count=1000
    )
    manifest_dict["generated_at"] = _iso_utc(-48)
    (input_dir / "export_manifest.json").write_text(json.dumps(manifest_dict, indent=2))

    exit_code = rca.main(
        [
            "--input-dir",
            str(input_dir),
            "--output-dir",
            str(tmp_path / "dist"),
            "--min-products",
            "500",
        ]
    )
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "FRESHNESS GATE FAILED" in err


def test_main_succeeds_when_stale_input_with_allow_stale(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """--allow-stale lets a deliberately-stale restage proceed."""
    input_dir = tmp_path / "stale_build"
    input_dir.mkdir()
    db_path = input_dir / "pharmaguide_core.db"
    _make_fake_db(db_path, row_count=1000)
    manifest_dict = _write_manifest_json(
        input_dir / "export_manifest.json", db_path, row_count=1000
    )
    manifest_dict["generated_at"] = _iso_utc(-48)
    (input_dir / "export_manifest.json").write_text(json.dumps(manifest_dict, indent=2))

    exit_code = rca.main(
        [
            "--input-dir",
            str(input_dir),
            "--output-dir",
            str(tmp_path / "dist"),
            "--min-products",
            "500",
            "--allow-stale",
        ]
    )
    assert exit_code == 0
    err = capsys.readouterr().err
    assert "WARNING" in err and "--allow-stale" in err
