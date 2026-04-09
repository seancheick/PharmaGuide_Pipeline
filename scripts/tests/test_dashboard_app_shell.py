from scripts.dashboard.app_shell import build_initial_shell_state


def test_app_shell_bootstrap_consumes_query_params():
    state = build_initial_shell_state(
        query_params={"view": "product-inspector", "dsld_id": "12345"},
        session_state={},
    )
    assert state["current_view"] == "Product Inspector"
    assert state["selected_dsld_id"] == "12345"


def test_app_shell_defaults_to_command_center():
    state = build_initial_shell_state(query_params={}, session_state={})
    assert state["current_view"] == "Command Center"
    assert state["current_section"] == "Command Center"


def test_app_shell_query_params_override_existing_session_state():
    state = build_initial_shell_state(
        query_params={"view": "batch-diff", "dsld_id": "999"},
        session_state={"current_view": "Pipeline Health", "selected_dsld_id": "123"},
    )
    assert state["current_view"] == "Batch Diff"
    assert state["current_section"] == "Pipeline"
    assert state["selected_dsld_id"] == "999"
