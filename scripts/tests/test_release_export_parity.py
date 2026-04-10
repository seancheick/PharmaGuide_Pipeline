import json
import sqlite3
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))

from build_final_db import build_detail_blob, resolve_export_supplement_type


BUILD_ROOT = Path("scripts/final_db_output")
PRODUCTS_ROOT = Path("scripts/products")


def _discover_pair_dirs() -> tuple[list[Path], list[Path]]:
    enriched_dirs = {
        path.parent.name[: -len("_enriched")]: path
        for path in sorted(PRODUCTS_ROOT.glob("output_*_enriched/enriched"))
    }
    scored_dirs = {
        path.parent.name[: -len("_scored")]: path
        for path in sorted(PRODUCTS_ROOT.glob("output_*_scored/scored"))
    }
    paired = sorted(set(enriched_dirs) & set(scored_dirs))
    return [enriched_dirs[prefix] for prefix in paired], [scored_dirs[prefix] for prefix in paired]


ENRICHED_DIRS, SCORED_DIRS = _discover_pair_dirs()


def _load_products(directories: list[Path]) -> dict[str, dict]:
    products: dict[str, dict] = {}
    for directory in directories:
        for path in sorted(directory.glob("*.json")):
            data = json.loads(path.read_text())
            rows = data if isinstance(data, list) else data.get("products", [])
            for row in rows:
                products[str(row["dsld_id"])] = row
    return products


def test_release_export_counts_and_index_parity():
    enriched_lookup = _load_products(ENRICHED_DIRS)
    scored_lookup = _load_products(SCORED_DIRS)
    manifest = json.loads((BUILD_ROOT / "export_manifest.json").read_text())
    audit = json.loads((BUILD_ROOT / "export_audit_report.json").read_text())
    index = json.loads((BUILD_ROOT / "detail_index.json").read_text())
    blob_count = len(list((BUILD_ROOT / "detail_blobs").glob("*.json")))

    conn = sqlite3.connect(BUILD_ROOT / "pharmaguide_core.db")
    try:
        row_count = conn.execute("SELECT COUNT(*) FROM products_core").fetchone()[0]
    finally:
        conn.close()

    assert row_count == len(enriched_lookup) == len(scored_lookup)
    assert row_count == blob_count == len(index)
    assert manifest["product_count"] == row_count
    assert manifest["detail_blob_count"] == row_count
    assert manifest["detail_blob_unique_count"] == row_count
    assert audit["counts"]["total_errors"] == 0
    assert not audit["contract_failures"]


def test_release_export_matches_source_scored_and_resolved_type():
    enriched_lookup = _load_products(ENRICHED_DIRS)
    scored_lookup = _load_products(SCORED_DIRS)

    conn = sqlite3.connect(BUILD_ROOT / "pharmaguide_core.db")
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT dsld_id, supplement_type, score_100_equivalent, verdict, mapped_coverage,
                   output_schema_version
            FROM products_core
            """
        ).fetchall()
    finally:
        conn.close()

    assert rows, "expected exported products in release DB"

    for row in rows:
        dsld_id = str(row["dsld_id"])
        enriched = enriched_lookup[dsld_id]
        scored = scored_lookup[dsld_id]
        expected_type = resolve_export_supplement_type(enriched, scored)

        assert row["supplement_type"] == expected_type
        assert row["verdict"] == scored["verdict"]
        assert row["output_schema_version"] == scored["output_schema_version"]

        expected_score = scored["score_100_equivalent"]
        if expected_score is None:
            assert row["score_100_equivalent"] is None
        else:
            assert row["score_100_equivalent"] == expected_score

        expected_coverage = round(float(scored["mapped_coverage"]), 4)
        assert row["mapped_coverage"] == expected_coverage


def test_release_detail_blobs_match_recomputed_export_contract():
    enriched_lookup = _load_products(ENRICHED_DIRS)
    scored_lookup = _load_products(SCORED_DIRS)
    blob_dir = BUILD_ROOT / "detail_blobs"

    blob_paths = sorted(blob_dir.glob("*.json"))
    assert blob_paths, "expected exported detail blobs"

    for path in blob_paths:
        actual = json.loads(path.read_text())
        dsld_id = str(actual["dsld_id"])
        expected = build_detail_blob(enriched_lookup[dsld_id], scored_lookup[dsld_id])

        assert actual == expected, dsld_id
