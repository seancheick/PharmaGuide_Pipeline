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
          quality_score_v4_100 REAL, mapped_coverage REAL, quality_score_confidence TEXT, quality_assessment_status TEXT,
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
        "quality_score_v4_100": 82,
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
            "quality_score_v4_100": 82,
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
        self.operation = "read"
        self.filters = {}
        self.after = None
        self.count = None
        self.negated = False

    def upsert(self, rows, on_conflict):
        self.client.calls.append(("upsert", self.table, len(rows), on_conflict))
        self.operation = "upsert"
        self.rows = rows
        return self

    def delete(self):
        self.operation = "delete"
        return self

    @property
    def not_(self):
        self.negated = True
        return self

    def in_(self, column, values):
        self.column, self.values = column, list(values)
        label = "delete_not_in" if self.negated else "delete_in"
        self.client.calls.append((label, self.table, column, self.values))
        return self

    def eq(self, column, value):
        self.filters[column] = value
        return self

    def gt(self, column, value):
        assert column == "dsld_id"
        self.after = value
        return self

    def select(self, _columns):
        return self

    def order(self, column, desc=False):
        assert desc is (column == "created_at")
        return self

    def limit(self, count):
        self.count = count
        return self

    def execute(self):
        if self.table == "export_manifest":
            rows = self.client.manifest_rows
        elif self.operation == "upsert":
            upserts = sum(call[0] == "upsert" for call in self.client.calls)
            if self.client.fail_upsert and upserts >= self.client.fail_upsert:
                raise RuntimeError("injected upsert failure")
            for row in self.rows:
                self.client.rows[(row["catalog_version"], row["dsld_id"])] = dict(row)
            return SimpleNamespace(data=[])
        else:
            rows = list(self.client.rows.values())
        rows = [r for r in rows if all(r.get(k) == v for k, v in self.filters.items())]
        if self.operation == "delete":
            if self.client.fail_delete:
                self.client.fail_delete = False
                raise RuntimeError("injected delete failure")
            for row in rows:
                if (row[self.column] in self.values) != self.negated:
                    del self.client.rows[(row["catalog_version"], row["dsld_id"])]
            return SimpleNamespace(data=[])
        if self.table == "catalog_search":
            rows = sorted(rows, key=lambda r: r["dsld_id"])
            if self.after is not None:
                rows = [r for r in rows if r["dsld_id"] > self.after]
            self.client.read_pages += 1
        count = self.count
        if self.table == "catalog_search" and self.client.page_cap is not None:
            count = min(count or self.client.page_cap, self.client.page_cap)
        return SimpleNamespace(data=rows[:count])


class _FakeClient:
    def __init__(self, manifest_rows, rows=(), page_cap=None):
        self.manifest_rows = manifest_rows
        self.calls = []
        self.rows = {(r["catalog_version"], r["dsld_id"]): dict(r) for r in rows}
        self.page_cap = page_cap
        self.read_pages = 0
        self.fail_upsert = False
        self.fail_delete = False

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


def test_republish_reconciles_removed_ids_across_capped_pages_and_retries(tmp_path):
    db_path = tmp_path / "core.db"
    _write_db(db_path, 2)
    client = _FakeClient(
        [{"db_version": "v1", "is_current": True}],
        rows=[{"catalog_version": version, "dsld_id": str(100000 + i)}
              for version in ("v1", "v0") for i in range(1203)],
        page_cap=137,
    )
    client.manifest_rows.append({"db_version": "v0", "is_current": False})
    client.fail_delete = True
    sync.publish_catalog_search(client, db_path=str(db_path), catalog_version="v1",
                                sleep_fn=lambda _s: None)
    assert {key[1] for key in client.rows if key[0] == "v1"} == {"100000", "100001"}
    assert len([key for key in client.rows if key[0] == "v0"]) == 1203
    assert client.read_pages > 2
    deletes = [call for call in client.calls if call[0] == "delete_in"]
    assert deletes and all(len(call[3]) <= 500 for call in deletes)
    before = dict(client.rows)
    sync.publish_catalog_search(client, db_path=str(db_path), catalog_version="v1")
    assert client.rows == before


def test_failed_upsert_does_not_delete_existing_catalog_rows(tmp_path):
    db_path = tmp_path / "core.db"
    _write_db(db_path, 2)
    client = _FakeClient([], rows=[{"catalog_version": "v1", "dsld_id": "removed"}])
    client.fail_upsert = 2
    with pytest.raises(RuntimeError, match="upsert failure"):
        sync.publish_catalog_search(client, db_path=str(db_path), catalog_version="v1",
                                    batch_size=1, retries=0)
    assert ("v1", "100000") in client.rows  # First batch succeeded.
    assert ("v1", "removed") in client.rows
    assert not any(call[0].startswith("delete") for call in client.calls)


def test_pruning_keeps_current_even_outside_recent_manifest_window():
    manifests = [{"db_version": f"recent{i}", "is_current": False} for i in range(12)]
    manifests.append({"db_version": "live", "is_current": True})
    client = _FakeClient(manifests)
    assert sync.catalog_search_keep_versions(client, "candidate") == ["candidate", "live"]


def _catalog_search_sql():
    sql = SCHEMA_SQL.read_text(encoding="utf-8")
    start = sql.index("CREATE TABLE IF NOT EXISTS public.catalog_search")
    return sql, sql[start:]


def test_schema_declares_every_published_column():
    _, section = _catalog_search_sql()
    table = section[: section.index(");\n")]
    declared = set(re.findall(r"^\s+([a-z_][a-z_0-9]*)\s+(?:text|double precision|tsvector|timestamptz)", table, re.M))
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
    assert "REVOKE ALL ON FUNCTION public.search_catalog(text, text, text, integer, text, integer, text, text)\n  FROM PUBLIC, anon, authenticated;" in section
    # No policy may open these rows to client roles.
    assert "CREATE POLICY" not in section
    for index in (
        "idx_catalog_search_product_name_trgm",
        "idx_catalog_search_brand_name_trgm",
        "idx_catalog_search_tsv",
        "idx_catalog_search_upc_sku",
    ):
        assert f"CREATE INDEX IF NOT EXISTS {index}" in section

@pytest.mark.parametrize("score", [None, 0, 82, 100])
def test_search_preserves_canonical_numeric_quality_score(score):
    conn = sqlite3.connect(":memory:")
    _create_products_core(conn)
    _insert(conn, quality_score_v4_100=score)
    assert sync.catalog_search_rows_from_connection(conn, "v1")[0]["quality_score_v4_100"] == score

@pytest.mark.parametrize("score", [-1, 101, float("inf")])
def test_search_rejects_invalid_quality_score(score):
    conn = sqlite3.connect(":memory:")
    _create_products_core(conn)
    _insert(conn, quality_score_v4_100=score)
    with pytest.raises(ValueError, match="quality_score_v4_100"):
        sync.catalog_search_rows_from_connection(conn, "v1")


def test_comparison_migration_matches_bootstrap_search_owner():
    schema = SCHEMA_SQL.read_text()
    migration = (SCHEMA_SQL.parent / "migrations/20261013213803_public_catalog_comparison.sql").read_text()
    start = "CREATE OR REPLACE FUNCTION public.search_catalog("
    assert schema[schema.index(start):] == migration[migration.index(start):]
    assert "count(*) OVER () AS total_matches" in migration
    assert "c.quality_score_status = 'scored'" in migration
    assert "c.quality_assessment_status = 'complete'" in migration
    assert "THEN c.quality_score_v4_100 END DESC NULLS LAST" in migration
