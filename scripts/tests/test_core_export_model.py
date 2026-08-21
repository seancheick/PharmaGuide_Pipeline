"""One-model projection contract for the products_core export."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from build_final_db import CORE_COLUMN_COUNT, SCHEMA_SQL  # noqa: E402
from core_export_model import (  # noqa: E402
    APP_CORE_COLUMNS,
    PRODUCTS_CORE_COLUMNS,
    SERVER_CORE_COLUMNS,
    build_projection_manifest,
    products_core_columns_for_schema,
)
from generate_flutter_core_projection import render_dart_projection  # noqa: E402


def _schema_columns() -> tuple[str, ...]:
    connection = sqlite3.connect(":memory:")
    try:
        connection.executescript(SCHEMA_SQL)
        rows = connection.execute("PRAGMA table_info(products_core)").fetchall()
    finally:
        connection.close()
    return tuple(row[1] for row in sorted(rows, key=lambda row: row[0]))


def test_export_model_is_the_exact_physical_schema_in_insert_order() -> None:
    assert PRODUCTS_CORE_COLUMNS == _schema_columns()
    assert CORE_COLUMN_COUNT == len(PRODUCTS_CORE_COLUMNS)


def test_app_and_server_projections_partition_the_export_model() -> None:
    assert not set(APP_CORE_COLUMNS) & set(SERVER_CORE_COLUMNS)
    assert set(APP_CORE_COLUMNS) | set(SERVER_CORE_COLUMNS) == set(
        PRODUCTS_CORE_COLUMNS
    )
    assert "quality_score_confidence" in APP_CORE_COLUMNS
    assert "score_unavailable_reason" in APP_CORE_COLUMNS
    assert "route_confidence" in APP_CORE_COLUMNS
    assert "v4_confidence" in SERVER_CORE_COLUMNS


def test_projection_manifest_is_deterministic_and_schema_typed() -> None:
    first = build_projection_manifest(export_schema_version="2.4.0")
    second = build_projection_manifest(export_schema_version="2.4.0")

    assert first == second
    assert first["export_schema_version"] == "2.4.0"
    assert first["app_core"]["columns"] == list(APP_CORE_COLUMNS)
    assert first["server_core"]["columns"] == list(SERVER_CORE_COLUMNS)
    assert first["model_sha256"].startswith("sha256:")


def test_schema_3_removes_deprecated_and_retired_core_columns() -> None:
    schema2 = products_core_columns_for_schema("2.4.0")
    schema3 = products_core_columns_for_schema("3.0.0")

    assert schema2 == PRODUCTS_CORE_COLUMNS
    assert set(schema2) - set(schema3) == {
        "score_display_100_equivalent",
        "score_100_equivalent",
        "v4_confidence",
        "score_ingredient_quality",
        "score_ingredient_quality_max",
        "score_safety_purity",
        "score_safety_purity_max",
        "score_evidence_research",
        "score_evidence_research_max",
        "score_brand_trust",
        "score_brand_trust_max",
    }
    assert "quality_score_v4_100" in schema3
    assert "quality_score_confidence" in schema3


def test_app_projection_does_not_read_retired_compat_columns() -> None:
    retired = {
        "score_display_100_equivalent",
        "score_100_equivalent",
        "v4_confidence",
        "score_ingredient_quality",
        "score_ingredient_quality_max",
        "score_safety_purity",
        "score_safety_purity_max",
        "score_evidence_research",
        "score_evidence_research_max",
        "score_brand_trust",
        "score_brand_trust_max",
    }
    assert not retired & set(APP_CORE_COLUMNS)


def test_flutter_projection_generator_contains_only_the_app_read_set() -> None:
    rendered = render_dart_projection(export_schema_version="2.4.0")

    for column in APP_CORE_COLUMNS:
        assert f"'{column}'" in rendered
    for column in SERVER_CORE_COLUMNS:
        assert f"'{column}'" not in rendered
    assert "export schema 2.4.0" in rendered
