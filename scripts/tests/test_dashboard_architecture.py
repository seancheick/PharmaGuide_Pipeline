import sys
from pathlib import Path
from unittest.mock import MagicMock


mock_st = MagicMock()


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


def test_loader_build_history_and_shared_metrics():
    config = DashboardConfig(
        scan_dir=Path("scripts/products").resolve(),
        build_root=Path("scripts/final_db_output").resolve(),
    )

    data = load_dashboard_data(config)

    assert getattr(data, "build_history", []), "expected at least the current build in history"
    assert getattr(data, "shared_metrics", None) is not None, "expected normalized shared metrics"
    assert data.shared_metrics["product_count"] == 783
    assert data.shared_metrics["verdict_counts"]["SAFE"] == 700
    assert data.shared_metrics["safety_counts"]["has_banned_substance"] == 5
    assert getattr(data, "alert_thresholds", None) is not None
    assert data.alert_thresholds["coverage_min_pct"] == 95


def test_loader_discovers_dataset_outputs_and_batch_history():
    config = DashboardConfig(
        scan_dir=Path("scripts/products").resolve(),
        build_root=Path("scripts/final_db_output").resolve(),
    )

    data = load_dashboard_data(config)

    assert "Olly" in data.discovered_datasets
    assert "Thorne" in data.discovered_datasets
    assert getattr(data, "dataset_reports", {}).get("Thorne") is not None
    assert getattr(data, "batch_history", []), "expected parsed batch log history"
    assert data.batch_history[0]["summary"]["processed"] >= 0


def test_loader_blob_analytics_are_available():
    config = DashboardConfig(
        scan_dir=Path("scripts/products").resolve(),
        build_root=Path("scripts/final_db_output").resolve(),
    )

    data = load_dashboard_data(config)

    analytics = getattr(data, "blob_analytics", None)
    assert analytics is not None
    assert analytics["ingredient_forms"], "expected ingredient form analytics from detail blobs"
    assert analytics["bonus_frequency"], "expected bonus aggregation from detail blobs"
    assert "high_risk_ingredients" in analytics
    assert "product_explainers" in analytics
