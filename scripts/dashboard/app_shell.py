from __future__ import annotations

from typing import Mapping, MutableMapping, Any

from scripts.dashboard.navigation import DEFAULT_VIEW, SECTION_BY_VIEW, parse_dashboard_query_params


def build_initial_shell_state(
    query_params: Mapping[str, str],
    session_state: MutableMapping[str, Any],
) -> dict[str, Any]:
    route_state = parse_dashboard_query_params(query_params)

    # Shareable links should win over previously cached UI state.
    current_view = route_state.current_view or session_state.get("current_view") or DEFAULT_VIEW
    selected_dsld_id = route_state.selected_dsld_id or session_state.get("selected_dsld_id")
    current_section = SECTION_BY_VIEW.get(current_view, SECTION_BY_VIEW[DEFAULT_VIEW])

    return {
        "current_view": current_view,
        "current_section": current_section,
        "selected_dsld_id": selected_dsld_id,
    }
