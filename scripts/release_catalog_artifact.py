#!/usr/bin/env python3
"""release_catalog_artifact.py — stage a pipeline release for the Flutter app.

Reads the current pipeline output at `scripts/final_db_output/` (produced by
`build_final_db.py`), validates it, and stages a clean `dist/` directory
containing exactly the artifacts the Flutter release bridge consumes:

    dist/
      pharmaguide_core.db        # SQLite, 90-col products_core @ schema v1.3.2+
      export_manifest.json       # release-contract fields (see below)
      RELEASE_NOTES.md           # human-readable summary of this build

The staging step is deliberate: `scripts/final_db_output/` is a working
directory that `build_final_db.py` can overwrite at any time. `dist/` is the
frozen artifact the bridge script in the Flutter repo copies from.

## Release manifest contract

The staged `export_manifest.json` preserves every field the pipeline already
emits and guarantees the following keys exist (the Flutter bridge and OTA
flow read these by name):

- db_version            — build timestamp (e.g. "2026.04.10.222555"), stable per build
- schema_version        — export schema semver (e.g. "1.3.2")
- pipeline_version      — pipeline semver
- scoring_version       — scoring engine semver
- generated_at          — ISO-8601 UTC of this build
- product_count         — row count in products_core
- checksum              — "sha256:<hex>" of pharmaguide_core.db (pipeline format)
- checksum_sha256       — raw hex sha256, no prefix (Flutter bridge format)
- min_app_version       — minimum mobile app version required to consume this DB

The script writes both `checksum` (prefixed) and `checksum_sha256` (raw hex)
so producers and consumers can use whichever convention they prefer without a
string-munging step.

## Validation gates

Before writing anything to `dist/`, the script enforces:

1. `pharmaguide_core.db` exists in input, SQLite opens cleanly, `PRAGMA
   integrity_check` returns `"ok"`
2. `products_core` has at least `--min-products` rows (default 500)
3. At least one row has a non-empty `export_version` column
4. The in-SQLite `export_manifest` key-value table has `db_version`,
   `schema_version`, `pipeline_version`, `scoring_version`, `product_count`,
   `min_app_version`
5. `export_manifest.json` exists alongside the DB
6. The manifest's `schema_version` matches the DB's `export_manifest.schema_version`
7. The manifest's `db_version` matches the DB's `export_manifest.db_version`
8. The manifest's `product_count` matches `SELECT COUNT(*) FROM products_core`
9. The DB's actual SHA-256 on disk matches the manifest's `checksum`

Any failure aborts with a non-zero exit code and a clear error. `dist/` is
left untouched so a broken build never replaces a good one.

## Usage

From the repo root:

    # default input (scripts/final_db_output/) and output (scripts/dist/)
    python3 scripts/release_catalog_artifact.py

    # explicit paths
    python3 scripts/release_catalog_artifact.py \
        --input-dir scripts/final_db_output \
        --output-dir scripts/dist

    # raise the minimum product count bar
    python3 scripts/release_catalog_artifact.py --min-products 2000

    # JSON summary for CI machine-reads
    python3 scripts/release_catalog_artifact.py --print-json

Exit codes:

    0   release staged successfully
    1   validation failed (input DB missing, integrity bad, version mismatch, …)
    2   unexpected runtime error (permissions, filesystem, …)

The bridge script in the PharmaGuide-ai Flutter repo consumes `dist/`:

    ./scripts/import_catalog_artifact.sh ../dsld_clean/scripts/dist

See `PIPELINE_OPERATIONS_README.md` → "Release playbook" for the end-to-end
flow.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ReleaseValidationError(RuntimeError):
    """Raised when a release candidate fails a validation gate."""


# ---------------------------------------------------------------------------
# Pure helpers (testable, no filesystem side effects beyond reads)
# ---------------------------------------------------------------------------


def compute_sha256(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Stream-hash a file to avoid loading large DBs into memory."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def strip_sha256_prefix(value: Optional[str]) -> Optional[str]:
    """Normalize either "sha256:<hex>" or "<hex>" to the raw hex form."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"checksum must be a string, got {type(value).__name__}")
    value = value.strip()
    if value.lower().startswith("sha256:"):
        return value.split(":", 1)[1].strip()
    return value


def ensure_sha256_prefix(value: Optional[str]) -> Optional[str]:
    """Normalize raw hex to the pipeline's "sha256:<hex>" convention."""
    stripped = strip_sha256_prefix(value)
    if stripped is None:
        return None
    return f"sha256:{stripped}"


def read_sqlite_manifest(db_path: Path) -> Dict[str, str]:
    """Read the `export_manifest` key-value table embedded in the SQLite file.

    Returns a {key: value} dict. Raises ReleaseValidationError if the table
    is missing (the pipeline always writes it; a missing table means the DB
    did not come from build_final_db.py).
    """
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='export_manifest'"
        )
        if cursor.fetchone() is None:
            raise ReleaseValidationError(
                f"{db_path.name} is missing the embedded export_manifest table. "
                "Re-run build_final_db.py to regenerate."
            )
        rows = conn.execute("SELECT key, value FROM export_manifest").fetchall()
    finally:
        conn.close()
    return {str(k): str(v) for k, v in rows}


def count_products(db_path: Path) -> int:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        row = conn.execute("SELECT COUNT(*) FROM products_core").fetchone()
    finally:
        conn.close()
    return int(row[0]) if row else 0


def count_products_with_export_version(db_path: Path) -> int:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM products_core "
            "WHERE export_version IS NOT NULL AND export_version != ''"
        ).fetchone()
    finally:
        conn.close()
    return int(row[0]) if row else 0


def run_integrity_check(db_path: Path) -> str:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
    finally:
        conn.close()
    return str(row[0]) if row else "unknown"


# ---------------------------------------------------------------------------
# Validation orchestration
# ---------------------------------------------------------------------------


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ReleaseValidationError(message)


def validate_release_candidate(
    *,
    input_dir: Path,
    min_products: int,
) -> Dict[str, Any]:
    """Validate a pipeline final_db_output/ directory and return a summary dict.

    On success, the returned dict carries everything the staging step needs:
    the verified DB path, the parsed manifest JSON, the computed checksum,
    and the embedded SQLite manifest.

    Raises ReleaseValidationError with a clear message on any failure.
    """
    db_path = input_dir / "pharmaguide_core.db"
    manifest_path = input_dir / "export_manifest.json"

    _require(
        db_path.is_file(),
        f"Release candidate missing pharmaguide_core.db at {db_path}. "
        "Run build_final_db.py first.",
    )
    _require(
        manifest_path.is_file(),
        f"Release candidate missing export_manifest.json at {manifest_path}. "
        "Run build_final_db.py first.",
    )

    integrity = run_integrity_check(db_path)
    _require(
        integrity == "ok",
        f"SQLite PRAGMA integrity_check returned {integrity!r} for {db_path}. "
        "Re-run build_final_db.py to regenerate.",
    )

    product_count = count_products(db_path)
    _require(
        product_count >= min_products,
        f"Release candidate has only {product_count} products in products_core, "
        f"minimum is {min_products}. Refusing to stage a partial release.",
    )

    versioned_count = count_products_with_export_version(db_path)
    _require(
        versioned_count > 0,
        "Release candidate has zero rows with a non-empty export_version. "
        "Flutter validateCatalogSnapshot will reject this DB.",
    )

    embedded = read_sqlite_manifest(db_path)
    required_embedded_keys = (
        "db_version",
        "schema_version",
        "pipeline_version",
        "scoring_version",
        "product_count",
        "min_app_version",
    )
    missing_embedded = [k for k in required_embedded_keys if k not in embedded]
    _require(
        not missing_embedded,
        f"Embedded export_manifest table is missing required keys: "
        f"{', '.join(missing_embedded)}. Re-run build_final_db.py.",
    )

    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as exc:
        raise ReleaseValidationError(
            f"export_manifest.json is not valid JSON: {exc}"
        ) from exc

    required_manifest_keys = (
        "db_version",
        "schema_version",
        "pipeline_version",
        "scoring_version",
        "product_count",
        "min_app_version",
        "generated_at",
        "checksum",
    )
    missing_manifest = [k for k in required_manifest_keys if k not in manifest]
    _require(
        not missing_manifest,
        f"export_manifest.json is missing required keys: "
        f"{', '.join(missing_manifest)}. Re-run build_final_db.py.",
    )

    _require(
        manifest["db_version"] == embedded["db_version"],
        f"db_version mismatch between manifest ({manifest['db_version']!r}) "
        f"and embedded SQLite table ({embedded['db_version']!r}). "
        "Release integrity broken.",
    )
    _require(
        str(manifest["schema_version"]) == str(embedded["schema_version"]),
        f"schema_version mismatch: manifest={manifest['schema_version']!r}, "
        f"embedded={embedded['schema_version']!r}. Release integrity broken.",
    )
    _require(
        int(manifest["product_count"]) == product_count,
        f"product_count mismatch: manifest={manifest['product_count']}, "
        f"actual_rows={product_count}. Release integrity broken.",
    )

    actual_checksum = compute_sha256(db_path)
    manifest_checksum = strip_sha256_prefix(manifest["checksum"])
    _require(
        manifest_checksum == actual_checksum,
        f"SHA-256 mismatch: manifest says {manifest_checksum}, "
        f"actual is {actual_checksum}. Re-run build_final_db.py — the DB "
        "was modified after the manifest was written.",
    )

    return {
        "db_path": db_path,
        "manifest_path": manifest_path,
        "manifest": manifest,
        "embedded_manifest": embedded,
        "checksum_sha256": actual_checksum,
        "product_count": product_count,
        "integrity": integrity,
    }


# ---------------------------------------------------------------------------
# Staging (filesystem side effects)
# ---------------------------------------------------------------------------


def build_release_manifest(
    *,
    source_manifest: Dict[str, Any],
    checksum_sha256: str,
) -> Dict[str, Any]:
    """Build the frozen `dist/export_manifest.json` payload.

    Pass-through every field the source manifest already has, and guarantee
    the two checksum formats (`checksum` prefixed + `checksum_sha256` raw hex)
    are both present for producer/consumer flexibility.
    """
    release = dict(source_manifest)
    release["checksum"] = ensure_sha256_prefix(checksum_sha256)
    release["checksum_sha256"] = strip_sha256_prefix(checksum_sha256)
    release["release_staged_at"] = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    return release


def build_release_notes(
    *,
    manifest: Dict[str, Any],
    checksum_sha256: str,
) -> str:
    """Render a short human-readable summary of the staged release."""
    generated_at = manifest.get("generated_at", "unknown")
    return (
        "# PharmaGuide Catalog Release Notes\n"
        "\n"
        f"- db_version:       `{manifest.get('db_version')}`\n"
        f"- schema_version:   `{manifest.get('schema_version')}`\n"
        f"- pipeline_version: `{manifest.get('pipeline_version')}`\n"
        f"- scoring_version:  `{manifest.get('scoring_version')}`\n"
        f"- product_count:    {manifest.get('product_count')}\n"
        f"- min_app_version:  `{manifest.get('min_app_version')}`\n"
        f"- generated_at:     `{generated_at}`\n"
        f"- checksum_sha256:  `{checksum_sha256}`\n"
        "\n"
        "Consumed by the Flutter release bridge at:\n"
        "    PharmaGuide-ai/scripts/import_catalog_artifact.sh\n"
        "\n"
        "The bridge script re-verifies every field above before copying the\n"
        "artifacts into `assets/db/` in the mobile app repo.\n"
    )


def stage_release(
    *,
    validation: Dict[str, Any],
    output_dir: Path,
) -> Dict[str, Any]:
    """Write the validated release into output_dir atomically.

    Strategy: write into a sibling `.staging` directory, then rename-swap with
    the real output_dir. This guarantees an in-progress stage can never leave
    output_dir in a partial state, even on crash.
    """
    output_dir = output_dir.resolve()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = output_dir.with_name(output_dir.name + ".staging")
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True)

    try:
        dest_db = staging_dir / "pharmaguide_core.db"
        dest_manifest = staging_dir / "export_manifest.json"
        dest_notes = staging_dir / "RELEASE_NOTES.md"

        shutil.copy2(validation["db_path"], dest_db)

        release_manifest = build_release_manifest(
            source_manifest=validation["manifest"],
            checksum_sha256=validation["checksum_sha256"],
        )
        dest_manifest.write_text(
            json.dumps(release_manifest, indent=2, sort_keys=True) + "\n"
        )

        dest_notes.write_text(
            build_release_notes(
                manifest=release_manifest,
                checksum_sha256=validation["checksum_sha256"],
            )
        )

        # Self-verify the staged copy: the checksum of the copied DB must
        # match the one we already validated in the source. This catches
        # copy corruption.
        staged_checksum = compute_sha256(dest_db)
        if staged_checksum != validation["checksum_sha256"]:
            raise ReleaseValidationError(
                f"Staged DB checksum {staged_checksum} does not match source "
                f"{validation['checksum_sha256']}. Copy corrupted."
            )

        # Preserve the rendered product image cache across the rename-swap.
        # `product_images/` is expensive to regenerate (PDF→WebP for ~8 K
        # products, hours on first run) but is a pure derivative of
        # `image_url` rows in the catalog DB — `extract_product_images.py`
        # idempotently re-uses any existing `<dsld_id>.webp` file. Carrying
        # it forward into the new staging dir means step 3 of the release
        # runner can skip already-rendered files instead of re-rendering
        # 100 % of the catalog every time the catalog DB changes.
        #
        # Intentionally narrow: ONLY `product_images/` is preserved.
        # Everything else in `dist/` (interaction_db.sqlite, detail_blobs/,
        # detail_index.json, export_audit_report.json) is correctly wiped
        # so downstream steps regenerate fresh artifacts from the new
        # catalog DB.
        preserved_image_dir = output_dir / "product_images"
        if preserved_image_dir.is_dir():
            shutil.move(str(preserved_image_dir), str(staging_dir / "product_images"))

        if output_dir.exists():
            shutil.rmtree(output_dir)
        staging_dir.rename(output_dir)
    except Exception:
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
        raise

    return {
        "output_dir": output_dir,
        "db_path": output_dir / "pharmaguide_core.db",
        "manifest_path": output_dir / "export_manifest.json",
        "release_notes_path": output_dir / "RELEASE_NOTES.md",
        "checksum_sha256": validation["checksum_sha256"],
        "product_count": validation["product_count"],
        "db_version": validation["manifest"].get("db_version"),
        "schema_version": validation["manifest"].get("schema_version"),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Stage a pipeline release artifact for the Flutter bridge.",
    )
    p.add_argument(
        "--input-dir",
        default="scripts/final_db_output",
        help="Pipeline build output directory (default: scripts/final_db_output).",
    )
    p.add_argument(
        "--output-dir",
        default="scripts/dist",
        help="Release staging directory (default: scripts/dist).",
    )
    p.add_argument(
        "--min-products",
        type=int,
        default=500,
        help="Minimum product count required in products_core (default: 500).",
    )
    p.add_argument(
        "--print-json",
        action="store_true",
        help="Print the staging result as JSON on stdout (for CI consumption).",
    )
    return p.parse_args(argv)


def main(argv: Optional[list] = None) -> int:
    args = _parse_args(argv)
    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve()

    try:
        validation = validate_release_candidate(
            input_dir=input_dir,
            min_products=args.min_products,
        )
    except ReleaseValidationError as exc:
        print(f"[release] VALIDATION FAILED: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 — surface unexpected errors loud
        print(f"[release] UNEXPECTED ERROR during validation: {exc}", file=sys.stderr)
        return 2

    try:
        result = stage_release(validation=validation, output_dir=output_dir)
    except ReleaseValidationError as exc:
        print(f"[release] STAGING FAILED: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"[release] UNEXPECTED ERROR during staging: {exc}", file=sys.stderr)
        return 2

    if args.print_json:
        printable = {k: (str(v) if isinstance(v, Path) else v) for k, v in result.items()}
        print(json.dumps(printable, indent=2, sort_keys=True))
    else:
        print(f"[release] staged → {result['output_dir']}")
        print(f"[release]   db_version       = {result['db_version']}")
        print(f"[release]   schema_version   = {result['schema_version']}")
        print(f"[release]   product_count    = {result['product_count']}")
        print(f"[release]   checksum_sha256  = {result['checksum_sha256']}")
        print()
        print("Next step: from the PharmaGuide-ai Flutter repo run:")
        print(f"    ./scripts/import_catalog_artifact.sh {result['output_dir']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
