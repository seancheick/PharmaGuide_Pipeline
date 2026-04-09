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
from scripts.dashboard.data_loader import load_dashboard_data

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
