#!/usr/bin/env python3
"""Assemble a full release artifact from existing per-pair build outputs."""

import argparse
import json
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from build_final_db import (
    SCHEMA_SQL,
    CORE_INDEX_SQL,
    FTS_SQL,
    PIPELINE_VERSION,
    EXPORT_SCHEMA_VERSION,
    MIN_APP_VERSION,
    apply_sqlite_build_pragmas,
    build_db_version,
    compute_file_sha256,
)


def validate_pair_output_dir(path: str) -> None:
    required = [
        "pharmaguide_core.db",
        "detail_index.json",
        "export_manifest.json",
        "detail_blobs",
    ]
    for name in required:
        full = os.path.join(path, name)
        if not os.path.exists(full):
            raise FileNotFoundError(f"Missing required pair output artifact: {full}")


def discover_pair_output_dirs(root: str):
    root_path = Path(root)
    if not root_path.is_dir():
        raise FileNotFoundError(f"Pair output root does not exist: {root}")
    dirs = []
    for child in sorted(root_path.iterdir()):
        if child.is_dir() and (child / "pharmaguide_core.db").exists():
            dirs.append(str(child))
    return dirs


def _copy_or_replace(src: str, dst: str) -> None:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)


def merge_pair_outputs(input_dirs, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    detail_dir = os.path.join(output_dir, "detail_blobs")
    os.makedirs(detail_dir, exist_ok=True)

    for entry in os.scandir(detail_dir):
        if entry.is_file():
            os.remove(entry.path)

    db_path = os.path.join(output_dir, "pharmaguide_core.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    apply_sqlite_build_pragmas(conn)
    conn.executescript(SCHEMA_SQL)

    detail_index = {}
    unique_hashes = set()
    inserted = 0

    try:
        for input_dir in sorted(input_dirs):
            validate_pair_output_dir(input_dir)
            pair_db = os.path.join(input_dir, "pharmaguide_core.db")
            pair_detail_index_path = os.path.join(input_dir, "detail_index.json")
            pair_detail_dir = os.path.join(input_dir, "detail_blobs")

            with sqlite3.connect(pair_db) as pair_conn:
                cursor = pair_conn.execute("SELECT * FROM products_core ORDER BY dsld_id")
                rows = cursor.fetchall()
                if rows:
                    placeholders = ",".join(["?"] * len(rows[0]))
                    conn.executemany(
                        f"INSERT OR REPLACE INTO products_core VALUES ({placeholders})",
                        rows,
                    )
                    inserted += len(rows)

                for key, version, data, updated_at in pair_conn.execute(
                    "SELECT key, version, data, updated_at FROM reference_data"
                ):
                    existing = conn.execute(
                        "SELECT version, data FROM reference_data WHERE key = ?",
                        (key,),
                    ).fetchone()
                    if existing and existing != (version, data):
                        raise ValueError(f"Conflicting reference_data for key={key}")
                    conn.execute(
                        "INSERT OR REPLACE INTO reference_data VALUES (?,?,?,?)",
                        (key, version, data, updated_at),
                    )

            with open(pair_detail_index_path, "r", encoding="utf-8") as f:
                pair_detail_index = json.load(f)

            for dsld_id, entry in pair_detail_index.items():
                existing = detail_index.get(dsld_id)
                if existing and existing != entry:
                    raise ValueError(f"Conflicting detail index entry for dsld_id={dsld_id}")
                detail_index[dsld_id] = entry
                unique_hashes.add(entry["blob_sha256"])
                _copy_or_replace(
                    os.path.join(pair_detail_dir, f"{dsld_id}.json"),
                    os.path.join(detail_dir, f"{dsld_id}.json"),
                )

        conn.executescript(CORE_INDEX_SQL)
        conn.executescript(FTS_SQL)
        conn.execute("INSERT INTO products_fts(products_fts) VALUES ('rebuild')")

        manifest_now = datetime.now(timezone.utc)
        db_version = build_db_version(manifest_now)
        local_manifest_rows = [
            ("db_version", db_version),
            ("pipeline_version", PIPELINE_VERSION),
            ("scoring_version", PIPELINE_VERSION),
            ("generated_at", manifest_now.isoformat()),
            ("product_count", str(len(detail_index))),
            ("min_app_version", MIN_APP_VERSION),
            ("schema_version", str(EXPORT_SCHEMA_VERSION)),
        ]
        for key, value in local_manifest_rows:
            conn.execute("INSERT OR REPLACE INTO export_manifest VALUES (?,?)", (key, value))
        conn.commit()
    finally:
        conn.close()

    detail_index_path = os.path.join(output_dir, "detail_index.json")
    with open(detail_index_path, "w", encoding="utf-8") as f:
        json.dump(detail_index, f, indent=2, sort_keys=True)

    db_checksum = compute_file_sha256(db_path)
    detail_index_checksum = compute_file_sha256(detail_index_path)
    manifest_path = os.path.join(output_dir, "export_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "db_version": db_version,
                "pipeline_version": PIPELINE_VERSION,
                "scoring_version": PIPELINE_VERSION,
                "generated_at": manifest_now.isoformat(),
                "product_count": len(detail_index),
                "checksum": f"sha256:{db_checksum}",
                "detail_blob_count": len(detail_index),
                "detail_blob_unique_count": len(unique_hashes),
                "detail_index_checksum": f"sha256:{detail_index_checksum}",
                "min_app_version": MIN_APP_VERSION,
                "schema_version": EXPORT_SCHEMA_VERSION,
                "errors": [],
            },
            f,
            indent=2,
            sort_keys=True,
        )

    return {
        "db_path": db_path,
        "detail_dir": detail_dir,
        "detail_index_path": detail_index_path,
        "manifest_path": manifest_path,
        "product_count": len(detail_index),
        "detail_blob_count": len(detail_index),
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Assemble a full release artifact from per-pair build outputs.")
    parser.add_argument("--input-root", help="Root directory containing per-pair build outputs")
    parser.add_argument("--input-dir", action="append", default=[], help="Specific per-pair build output directory (repeatable)")
    parser.add_argument("--output-dir", required=True, help="Output directory for the assembled release")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    input_dirs = list(args.input_dir)
    if args.input_root:
        input_dirs.extend(discover_pair_output_dirs(args.input_root))
    if not input_dirs:
        raise SystemExit("No input pair outputs provided.")

    result = merge_pair_outputs(input_dirs, args.output_dir)
    print(f"Release assembled: {result['product_count']} products -> {result['db_path']}")


if __name__ == "__main__":
    main()
