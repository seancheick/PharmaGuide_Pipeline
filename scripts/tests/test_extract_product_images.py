import os
import json
import sqlite3
import pytest

from extract_product_images import (
    backfill_image_thumbnail_urls,
    default_output_dir_for_db,
    parse_args,
    refresh_export_manifest_checksum,
    load_products_from_db,
)


def test_dsld_pdf_extraction_excludes_submission_and_non_dsld_ids(tmp_path):
    db_path = tmp_path / "catalog.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE products_core (dsld_id TEXT, image_url TEXT)")
        conn.executemany("INSERT INTO products_core VALUES (?, ?)", [
            ("12345", "https://api.ods.od.nih.gov/dsld/s3/pdf/12345.pdf"),
            ("PG_SUB_12345", "https://api.ods.od.nih.gov/dsld/s3/pdf/PG_SUB_12345.pdf"),
            ("MANUAL_12345", "https://api.ods.od.nih.gov/dsld/s3/pdf/MANUAL_12345.pdf"),
        ])
    assert load_products_from_db(str(db_path)) == [
        ("12345", "https://api.ods.od.nih.gov/dsld/s3/pdf/12345.pdf"),
    ]


def test_cleaner_does_not_invent_dsld_pdf_for_submission():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalizer = EnhancedDSLDNormalizer.__new__(EnhancedDSLDNormalizer)
    assert normalizer._generate_image_url("", "PG_SUB_12345") == ""
    assert normalizer._generate_image_url("", "12345").endswith("/12345.pdf")


@pytest.mark.parametrize("missing", [False, True])
def test_release_image_probe_uses_exact_dsld_targets_not_file_count(tmp_path, missing):
    from extract_product_images import needs_image_extraction

    db_path = tmp_path / "catalog.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE products_core (dsld_id TEXT, image_url TEXT, image_thumbnail_url TEXT)")
        conn.executemany("INSERT INTO products_core VALUES (?, ?, ?)", [
            ("12345", "https://api.ods.od.nih.gov/dsld/s3/pdf/12345.pdf", "product-images/12345.webp"),
            ("PG_SUB_1", "https://api.ods.od.nih.gov/dsld/s3/pdf/PG_SUB_1.pdf", None),
        ])
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    (image_dir / "unrelated.webp").write_bytes(b"webp")
    if not missing:
        (image_dir / "12345.webp").write_bytes(b"webp")
    assert needs_image_extraction(str(db_path), str(image_dir)) is missing
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE products_core SET image_thumbnail_url = NULL WHERE dsld_id = '12345'")
    assert needs_image_extraction(str(db_path), str(image_dir))


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


def test_backfill_compacts_db_before_manifest_checksum(tmp_path):
    db_path = tmp_path / "pharmaguide_core.db"
    image_dir = tmp_path / "product_images"
    image_dir.mkdir()

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE products_core "
            "(dsld_id TEXT PRIMARY KEY, image_thumbnail_url TEXT)"
        )
        conn.execute("CREATE TABLE build_padding (payload TEXT)")
        conn.executemany(
            "INSERT INTO build_padding VALUES (?)",
            [("x" * 4000,) for _ in range(200)],
        )
        conn.execute("DELETE FROM build_padding")
        conn.commit()

    size_before = db_path.stat().st_size
    backfill_image_thumbnail_urls(str(db_path), str(image_dir), {})

    assert db_path.stat().st_size < size_before
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("PRAGMA freelist_count").fetchone()[0] == 0


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
