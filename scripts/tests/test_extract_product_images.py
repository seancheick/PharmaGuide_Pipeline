import os
import json
import sqlite3

from extract_product_images import (
    backfill_image_thumbnail_urls,
    default_output_dir_for_db,
    parse_args,
    refresh_export_manifest_checksum,
)


def test_default_output_dir_lives_next_to_db():
    assert default_output_dir_for_db("/tmp/build/pharmaguide_core.db") == (
        "/tmp/build/product_images"
    )


def test_parse_args_allows_default_output_dir():
    args = parse_args(["--db-path", "scripts/dist/pharmaguide_core.db"])
    assert args.db_path == "scripts/dist/pharmaguide_core.db"
    assert args.output_dir is None


def test_backfill_image_thumbnail_urls_updates_existing_images(tmp_path):
    db_path = tmp_path / "pharmaguide_core.db"
    image_dir = tmp_path / "product_images"
    image_dir.mkdir()
    (image_dir / "1000.webp").write_bytes(b"webp")

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "CREATE TABLE products_core "
            "(dsld_id TEXT PRIMARY KEY, image_thumbnail_url TEXT)"
        )
        conn.execute("INSERT INTO products_core (dsld_id) VALUES ('1000')")
        conn.commit()
    finally:
        conn.close()

    result = backfill_image_thumbnail_urls(
        str(db_path),
        str(image_dir),
        {"1000": {"filename": "1000.webp"}},
    )

    assert result == {"updated": 1, "missing": 0}
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT image_thumbnail_url FROM products_core WHERE dsld_id = '1000'"
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == "product-images/1000.webp"


def test_backfill_image_thumbnail_urls_skips_missing_files(tmp_path):
    db_path = tmp_path / "pharmaguide_core.db"
    image_dir = tmp_path / "product_images"
    image_dir.mkdir()

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "CREATE TABLE products_core "
            "(dsld_id TEXT PRIMARY KEY, image_thumbnail_url TEXT)"
        )
        conn.execute("INSERT INTO products_core (dsld_id) VALUES ('1000')")
        conn.commit()
    finally:
        conn.close()

    result = backfill_image_thumbnail_urls(
        str(db_path),
        str(image_dir),
        {"1000": {"filename": "1000.webp"}},
    )

    assert result == {"updated": 0, "missing": 1}
    assert not os.path.exists(image_dir / "1000.webp")


def test_refresh_export_manifest_checksum_updates_manifest_next_to_db(tmp_path):
    db_path = tmp_path / "pharmaguide_core.db"
    db_path.write_bytes(b"new-db-bytes")
    manifest_path = tmp_path / "export_manifest.json"
    manifest_path.write_text(
        json.dumps({"checksum": "sha256:old", "checksum_sha256": "old"}),
        encoding="utf-8",
    )

    result = refresh_export_manifest_checksum(str(db_path))

    assert result["updated"] is True
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["checksum"].startswith("sha256:")
    assert manifest["checksum"] != "sha256:old"
    assert manifest["checksum_sha256"] == manifest["checksum"].removeprefix("sha256:")
