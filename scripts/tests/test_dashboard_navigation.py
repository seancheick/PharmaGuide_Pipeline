from scripts.dashboard.navigation import (
    DEFAULT_VIEW,
    VIEW_BY_SLUG,
    parse_dashboard_query_params,
)


def test_navigation_keeps_existing_view_slugs():
    assert VIEW_BY_SLUG["product-inspector"] == "Product Inspector"
    assert VIEW_BY_SLUG["pipeline-health"] == "Pipeline Health"


def test_navigation_default_is_command_center():
    assert DEFAULT_VIEW == "Command Center"


def test_query_params_select_existing_view():
    state = parse_dashboard_query_params({"view": "product-inspector"})
    assert state.current_view == "Product Inspector"


def test_query_params_preserve_product_inspector_dsld_id():
    state = parse_dashboard_query_params({"view": "product-inspector", "dsld_id": "12345"})
    assert state.current_view == "Product Inspector"
    assert state.selected_dsld_id == "12345"


def test_product_inspector_deep_link_without_view_defaults_to_inspector():
    state = parse_dashboard_query_params({"dsld_id": "67890"})
    assert state.current_view == "Product Inspector"
    assert state.selected_dsld_id == "67890"

