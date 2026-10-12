"""catalog_search publish step: products_core row -> upsert payload, batching,
version pruning, and the schema's access boundary. No network: a fake client
records the PostgREST calls."""

import os
import re
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))

import sync_to_supabase as sync  # noqa: E402

SCHEMA_SQL = Path(__file__).parent.parent / "sql" / "supabase_schema.sql"


def _create_products_core(conn):
    conn.execute(
        """
        CREATE TABLE products_core (
          dsld_id TEXT PRIMARY KEY, product_name TEXT, brand_name TEXT,
          brand_family TEXT, product_line TEXT, upc_sku TEXT, form_factor TEXT,
          supplement_type TEXT, product_status TEXT, quality_tier TEXT,
          quality_score_status TEXT, product_safety_status TEXT,
          mapped_coverage REAL, quality_score_confidence TEXT, quality_assessment_status TEXT,
          verdict TEXT, top_warnings TEXT
        )
        """
    )


def _insert(conn, **values):
    defaults = {
        "dsld_id": "1",
        "product_name": "Magnesium Bisglycinate",
        "brand_name": "Thorne",
        "brand_family": "Thorne",
        "product_line": None,
        "upc_sku": None,
        "form_factor": "capsule",
        "supplement_type": "single_nutrient",
        "product_status": "active",
        "quality_tier": "Good",
        "quality_score_status": "scored",
        "product_safety_status": "no_known_catalog_concern",
        "mapped_coverage": 1.0,
        "quality_score_confidence": "high",
        "quality_assessment_status": "complete",
        "verdict": "SAFE",
        "top_warnings": "[]",
    }
    defaults.update(values)
    columns = ", ".join(defaults)
    marks = ", ".join("?" for _ in defaults)
    conn.execute(f"INSERT INTO products_core ({columns}) VALUES ({marks})", list(defaults.values()))


def test_row_mapping_from_in_memory_products_core():
    conn = sqlite3.connect(":memory:")
    _create_products_core(conn)
    _insert(
        conn,
        dsld_id="241695",
        product_name="Sport Milk Chocolate",
        brand_name="GNC",
        brand_family="  ",
        product_line="Mega Men",
        upc_sku="0 50428-38139.7",
        quality_tier="Needs improvement",
        product_safety_status="caution",
        mapped_coverage=0.25,
        quality_score_confidence="low",
        quality_assessment_status="partial",
    )

    rows = sync.catalog_search_rows_from_connection(conn, "2026.10.12.142202")

    assert rows == [
        {
            "catalog_version": "2026.10.12.142202",
            "dsld_id": "241695",
            "product_name": "Sport Milk Chocolate",
            "brand_name": "GNC",
            "brand_family": None,
            "product_line": "Mega Men",
            "upc_sku": "050428381397",
            "form_factor": "capsule",
            "supplement_type": "single_nutrient",
            "product_status": "active",
            "quality_tier": "Needs improvement",
            "quality_score_status": "scored",
            "product_safety_status": "caution",
            "mapped_coverage": 0.25,
            "quality_score_confidence": "low",
            "quality_assessment_status": "partial",
        }
    ]
    # Never copied: the legacy verdict and warning payloads stay out of search.
    assert "verdict" not in rows[0] and "top_warnings" not in rows[0]


def test_row_mapping_keeps_null_coverage_and_empty_upc_as_null():
    conn = sqlite3.connect(":memory:")
    _create_products_core(conn)
    _insert(conn, upc_sku="", mapped_coverage=None, quality_tier=None)

    (row,) = sync.catalog_search_rows_from_connection(conn, "v1")

    assert row["upc_sku"] is None
    assert row["mapped_coverage"] is None
    assert row["quality_tier"] is None


# (SQLite stores NaN as NULL, so the NaN guard is not reachable from a fixture.)
@pytest.mark.parametrize("coverage", [1.5, -0.1])
def test_row_mapping_rejects_out_of_range_coverage(coverage):
    conn = sqlite3.connect(":memory:")
    _create_products_core(conn)
    _insert(conn, mapped_coverage=coverage)

    with pytest.raises(ValueError, match="mapped_coverage"):
        sync.catalog_search_rows_from_connection(conn, "v1")


def test_row_mapping_rejects_missing_product_name():
    conn = sqlite3.connect(":memory:")
    _create_products_core(conn)
    _insert(conn, product_name="")

    with pytest.raises(ValueError, match="product_name"):
        sync.catalog_search_rows_from_connection(conn, "v1")


class _FakeQuery:
    def __init__(self, client, table):
        self.client = client
        self.table = table

    def upsert(self, rows, on_conflict):
        self.client.calls.append(("upsert", self.table, len(rows), on_conflict))
        return self

    def delete(self):
        return self

    @property
    def not_(self):
        return self

    def in_(self, column, values):
        self.client.calls.append(("delete_not_in", self.table, column, list(values)))
        return self

    def select(self, _columns):
        return self

    def order(self, _column, desc=False):
        assert desc is True
        return self

    def limit(self, _count):
        return self

    def execute(self):
        if self.table == "export_manifest":
            return SimpleNamespace(data=self.client.manifest_rows)
        return SimpleNamespace(data=[])


class _FakeClient:
    def __init__(self, manifest_rows):
        self.manifest_rows = manifest_rows
        self.calls = []

    def table(self, name):
        return _FakeQuery(self, name)


def _write_db(path, count):
    conn = sqlite3.connect(path)
    _create_products_core(conn)
    for index in range(count):
        _insert(conn, dsld_id=str(100000 + index))
    conn.commit()
    conn.close()


def test_publish_batches_upserts_and_prunes_to_two_versions(tmp_path):
    db_path = tmp_path / "pharmaguide_core.db"
    _write_db(db_path, 1201)
    client = _FakeClient(
        manifest_rows=[{"db_version": "2026.10.01"}, {"db_version": "2026.09.20"}]
    )

    result = sync.publish_catalog_search(
        client, db_path=str(db_path), catalog_version="2026.10.12", sleep_fn=lambda _s: None
    )

    assert result == {"row_count": 1201, "kept_versions": ["2026.10.12", "2026.10.01"]}
    assert client.calls == [
        ("upsert", "catalog_search", 500, "catalog_version,dsld_id"),
        ("upsert", "catalog_search", 500, "catalog_version,dsld_id"),
        ("upsert", "catalog_search", 201, "catalog_version,dsld_id"),
        ("delete_not_in", "catalog_search", "catalog_version", ["2026.10.12", "2026.10.01"]),
    ]


def test_keep_versions_when_release_is_already_current_and_rows_repeat():
    client = _FakeClient(
        manifest_rows=[
            {"db_version": "2026.10.12"},
            {"db_version": "2026.10.12"},
            {"db_version": "2026.10.01"},
            {"db_version": "2026.09.20"},
        ]
    )

    assert sync.catalog_search_keep_versions(client, "2026.10.12") == ["2026.10.12", "2026.10.01"]


def test_first_release_keeps_only_itself():
    assert sync.catalog_search_keep_versions(_FakeClient([]), "2026.10.12") == ["2026.10.12"]


def _catalog_search_sql():
    sql = SCHEMA_SQL.read_text(encoding="utf-8")
    start = sql.index("CREATE TABLE IF NOT EXISTS public.catalog_search")
    return sql, sql[start:]


def test_schema_declares_every_published_column():
    _, section = _catalog_search_sql()
    table = section[: section.index(");\n")]
    declared = set(re.findall(r"^\s+([a-z_]+)\s+(?:text|double precision|tsvector|timestamptz)", table, re.M))
    assert set(sync.CATALOG_SEARCH_COLUMNS) | {"catalog_version"} <= declared
    assert "PRIMARY KEY (catalog_version, dsld_id)" in table


def test_schema_keeps_catalog_search_service_role_only():
    sql, section = _catalog_search_sql()
    assert "CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA extensions;" in sql
    assert "ALTER TABLE public.catalog_search ENABLE ROW LEVEL SECURITY;" in section
    assert "REVOKE ALL ON TABLE public.catalog_search FROM PUBLIC, anon, authenticated;" in section
    assert "REVOKE ALL ON TABLE public.catalog_search_current FROM PUBLIC, anon, authenticated;" in section
    assert "WITH (security_invoker = true)" in section
    assert "AND m.is_current = true" in section
    assert "REVOKE ALL ON FUNCTION public.search_catalog(text, text, text, integer)\n  FROM PUBLIC, anon, authenticated;" in section
    # No policy may open these rows to client roles.
    assert "CREATE POLICY" not in section
    for index in (
        "idx_catalog_search_product_name_trgm",
        "idx_catalog_search_brand_name_trgm",
        "idx_catalog_search_tsv",
        "idx_catalog_search_upc_sku",
    ):
        assert f"CREATE INDEX IF NOT EXISTS {index}" in section
