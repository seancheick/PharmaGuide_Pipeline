from pathlib import Path

from scripts.dashboard.config import DashboardConfig
from scripts.dashboard.data_loader import load_dashboard_data
from scripts.dashboard.page_meta import PAGE_META, get_page_meta


def test_all_page_meta_entries_define_required_fields():
    required = {
        "page_title",
        "page_summary",
        "data_planes",
        "source_paths",
        "freshness_fields",
        "mixed_plane_warning",
        "related_views",
        "usage_notes",
    }
    for meta in PAGE_META.values():
        assert required.issubset(meta.keys())


def test_page_meta_resolves_real_paths_and_planes():
    config = DashboardConfig(
        scan_dir=Path("scripts/products").resolve(),
        build_root=Path("scripts/final_db_output").resolve(),
    )
    data = load_dashboard_data(config)

    quality_meta = get_page_meta("data-quality", data)
    intelligence_meta = get_page_meta("intelligence", data)
    inspector_meta = get_page_meta("product-inspector", data)

    assert quality_meta["data_planes"] == ["Release Snapshot", "Dataset Outputs"]
    assert intelligence_meta["data_planes"] == ["Release Snapshot"]
    assert inspector_meta["data_planes"] == ["Release Snapshot", "Dataset Outputs"]
    assert inspector_meta["show_mixed_plane_warning"] is True
    assert any("scripts/final_db_output" in path for path in intelligence_meta["source_paths"])
