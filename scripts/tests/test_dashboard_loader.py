import pytest
from pathlib import Path
from unittest.mock import MagicMock
import sys

# Mock streamlit before importing data_loader
mock_st = MagicMock()

# Decorators that just return the original function
def passthrough(func=None, **kwargs):
    if func is not None:
        return func
    def wrapper(f):
        return f
    return wrapper

mock_st.cache_data = passthrough
mock_st.cache_resource = passthrough
sys.modules["streamlit"] = mock_st

from scripts.dashboard.config import DashboardConfig
from scripts.dashboard.data_loader import DashboardData, filter_product_catalog, load_dashboard_data
import pandas as pd

def test_load_dashboard_data_real_files():
    # Use real project paths
    config = DashboardConfig(
        scan_dir=Path("scripts/products").resolve(),
        build_root=Path("scripts/final_db_output").resolve()
    )
    
    data = load_dashboard_data(config)
    
    assert data.scan_dir == Path("scripts/products").resolve()
    assert data.build_root == Path("scripts/final_db_output").resolve()
    
    # Check if DB connection was attempted (if DB exists)
    if data.db_path and data.db_path.exists():
        assert data.db_conn is not None
        # Try a simple query
        cursor = data.db_conn.execute("SELECT count(*) as count FROM products_core")
        row = cursor.fetchone()
        assert row["count"] > 0
    else:
        assert data.db_conn is None

    # Check manifest if it exists
    manifest_path = config.build_root / "export_manifest.json"
    if manifest_path.exists():
        assert data.export_manifest is not None
        assert "db_version" in data.export_manifest
    else:
        assert data.export_manifest is None

def test_load_dashboard_data_missing_files():
    # Use non-existent paths
    config = DashboardConfig(
        scan_dir=Path("non_existent_scan").resolve(),
        build_root=Path("non_existent_build").resolve()
    )
    
    data = load_dashboard_data(config)
    
    assert data.db_conn is None
    assert data.export_manifest is None
    assert len(data.warnings) > 0
    assert any("Database not found" in w for w in data.warnings)


def test_filter_product_catalog_applies_global_sidebar_filters():
    data = DashboardData(
        product_catalog=pd.DataFrame(
            [
                {
                    "dsld_id": "1",
                    "brand_name": "Thorne",
                    "supplement_type": "probiotic",
                    "primary_category": "probiotic",
                    "verdict": "SAFE",
                    "score": 92.0,
                    "section_a_score": 25.0,
                    "section_a_max": 25.0,
                    "is_non_gmo": 1,
                    "contains_omega3": 0,
                    "has_harmful_additives": 0,
                },
                {
                    "dsld_id": "2",
                    "brand_name": "Hum",
                    "supplement_type": "targeted",
                    "primary_category": "omega-3",
                    "verdict": "CAUTION",
                    "score": 70.0,
                    "section_a_score": 15.0,
                    "section_a_max": 25.0,
                    "is_non_gmo": 0,
                    "contains_omega3": 1,
                    "has_harmful_additives": 1,
                },
            ]
        )
    )
    mock_st.session_state = {
        "dataset_filter": "All Datasets",
        "brand_filter": ["Thorne"],
        "supplement_type_filter": ["probiotic"],
        "primary_category_filter": ["probiotic"],
        "verdict_filter": ["SAFE"],
        "min_score_filter": 80.0,
        "min_section_a_filter": 20.0,
        "only_section_a_ceiling": True,
        "only_harmful_flags": False,
        "only_omega_bonus_candidates": False,
        "only_non_gmo_verified": True,
    }

    filtered = filter_product_catalog(data)

    assert filtered["dsld_id"].tolist() == ["1"]
