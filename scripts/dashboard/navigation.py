from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


PAGE_DEFINITIONS = [
    ("Command Center", "Command Center", "command-center"),
    ("Release", "Product Inspector", "product-inspector"),
    ("Release", "Release Diff", "release-diff"),
    ("Pipeline", "Pipeline Health", "pipeline-health"),
    ("Pipeline", "Observability", "observability"),
    ("Pipeline", "Batch Diff", "batch-diff"),
    ("Quality", "Data Quality", "data-quality"),
    ("Quality", "Section A Audit", "section-a-audit"),
    ("Quality", "Section B Audit", "section-b-audit"),
    ("Quality", "Section C Audit", "section-c-audit"),
    ("Quality", "Section D Audit", "section-d-audit"),
    ("Intelligence", "Intelligence", "intelligence"),
]

DEFAULT_VIEW = "Command Center"
SUPPORTED_QUERY_PARAMS = ("view", "dsld_id")

VIEW_SLUGS = {label: slug for _, label, slug in PAGE_DEFINITIONS}
VIEW_BY_SLUG = {slug: label for _, label, slug in PAGE_DEFINITIONS}
SECTION_BY_VIEW = {label: section for section, label, _ in PAGE_DEFINITIONS}
VIEWS_BY_SECTION: dict[str, list[str]] = {}
for section, label, _ in PAGE_DEFINITIONS:
    VIEWS_BY_SECTION.setdefault(section, []).append(label)


@dataclass(frozen=True)
class DashboardRouteState:
    current_view: str
    selected_dsld_id: str | None = None


def parse_dashboard_query_params(params: Mapping[str, str]) -> DashboardRouteState:
    raw_view = str(params.get("view", "")).strip().lower()
    dsld_id = str(params.get("dsld_id", "")).strip() or None

    if raw_view in VIEW_BY_SLUG:
        current_view = VIEW_BY_SLUG[raw_view]
    elif dsld_id:
        current_view = "Product Inspector"
    else:
        current_view = DEFAULT_VIEW

    return DashboardRouteState(current_view=current_view, selected_dsld_id=dsld_id)
