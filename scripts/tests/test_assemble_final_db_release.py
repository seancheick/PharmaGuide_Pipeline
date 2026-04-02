"""Tests for assembling a full release artifact from per-pair outputs."""

import json
import os
import sqlite3
import sys
from pathlib import Path

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))


def _write_pair_output(root: Path, name: str, dsld_id: str, product_name: str):
    from build_final_db import CORE_COLUMN_COUNT, SCHEMA_SQL

    pair_dir = root / name
    pair_dir.mkdir(parents=True, exist_ok=True)
    detail_dir = pair_dir / "detail_blobs"
    detail_dir.mkdir()

    db_path = pair_dir / "pharmaguide_core.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.execute(
            "INSERT INTO products_core VALUES ({})".format(",".join(["?"] * CORE_COLUMN_COUNT)),
            (
                dsld_id, product_name, "Brand", None, None, 0, None, None, '{"has_any": false, "highest_severity": "", "condition_ids": [], "drug_class_ids": []}', '{"positive": "", "caution": "", "trust": ""}',
                "active", None, "capsule", "targeted",
                70.0, "70/80", "88/100", 88.0, "Good", "SAFE", "SAFE", 1.0,
                20.0, 25.0, 20.0, 30.0, 15.0, 20.0, 4.0, 5.0,
                90.0, 10.0, "targeted_capsule", "Top 10%", 100,
                1, 0, 0, 0, 1, 0, 0,
                0, 0, 0, 0, None,
                0, 0, 0, 0, 0,
                1, 1, 1,
                "[]", "[]", "[]", "[]",
                "3.1.0", "5.0.0", "3.1.0", "2026-03-29T00:00:00Z", "1", "2026-03-29T00:00:00Z",
            ),
        )
        conn.execute(
            "INSERT INTO reference_data VALUES (?,?,?,?)",
            ("interaction_rules", "1", '{"ok":true}', "2026-03-29T00:00:00Z"),
        )
        conn.execute(
            "INSERT INTO export_manifest VALUES (?,?)",
            ("db_version", "2026.03.29.000000"),
        )
        conn.commit()
    finally:
        conn.close()

    blob = {"dsld_id": dsld_id, "blob_version": 1, "product_name": product_name}
    blob_path = detail_dir / f"{dsld_id}.json"
    blob_path.write_text(json.dumps(blob), encoding="utf-8")
    blob_sha = __import__("hashlib").sha256(json.dumps(blob, separators=(",", ":")).encode("utf-8")).hexdigest()

    detail_index = {
        dsld_id: {
            "blob_sha256": blob_sha,
            "storage_path": f"shared/details/sha256/{blob_sha[:2]}/{blob_sha}.json",
            "blob_version": 1,
        }
    }
    (pair_dir / "detail_index.json").write_text(json.dumps(detail_index), encoding="utf-8")
    (pair_dir / "export_manifest.json").write_text(json.dumps({
        "db_version": "2026.03.29.000000",
        "pipeline_version": "3.1.0",
        "scoring_version": "3.1.0",
        "generated_at": "2026-03-29T00:00:00Z",
        "product_count": 1,
        "checksum": "sha256:test",
        "detail_blob_count": 1,
        "detail_blob_unique_count": 1,
        "detail_index_checksum": "sha256:test",
        "min_app_version": "1.0.0",
        "schema_version": 1,
        "errors": [],
    }), encoding="utf-8")
    return pair_dir


def test_merge_pair_outputs_combines_products_and_detail_index(tmp_path):
    from assemble_final_db_release import merge_pair_outputs

    inputs_root = tmp_path / "pairs"
    output_dir = tmp_path / "release"
    _write_pair_output(inputs_root, "Nordic", "1001", "Nordic Product")
    _write_pair_output(inputs_root, "Pure", "2002", "Pure Product")

    result = merge_pair_outputs(
        [str(inputs_root / "Nordic"), str(inputs_root / "Pure")],
        str(output_dir),
    )

    assert result["product_count"] == 2
    assert result["detail_blob_count"] == 2

    conn = sqlite3.connect(output_dir / "pharmaguide_core.db")
    try:
        rows = conn.execute("SELECT dsld_id, product_name FROM products_core ORDER BY dsld_id").fetchall()
    finally:
        conn.close()

    assert rows == [("1001", "Nordic Product"), ("2002", "Pure Product")]

    detail_index = json.loads((output_dir / "detail_index.json").read_text(encoding="utf-8"))
    assert sorted(detail_index.keys()) == ["1001", "2002"]


def test_merge_pair_outputs_rejects_conflicting_duplicate_dsld_id(tmp_path):
    from assemble_final_db_release import merge_pair_outputs

    inputs_root = tmp_path / "pairs"
    output_dir = tmp_path / "release"
    _write_pair_output(inputs_root, "Nordic", "1001", "Nordic Product")
    _write_pair_output(inputs_root, "Pure", "1001", "Different Product")

    try:
        merge_pair_outputs(
            [str(inputs_root / "Nordic"), str(inputs_root / "Pure")],
            str(output_dir),
        )
    except ValueError as exc:
        assert "Conflicting detail index entry" in str(exc)
    else:
        raise AssertionError("Expected conflicting duplicate dsld_id to raise ValueError")
