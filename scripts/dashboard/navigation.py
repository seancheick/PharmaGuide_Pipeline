"""Page registry: grouped navigation, URL slugs, and redirects for retired ``?view=`` links."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PageSpec:
    section: str
    title: str
    slug: str
    icon: str
    module: str  # scripts.dashboard.views.<module>.render(ctx)


PAGES: list[PageSpec] = [
    PageSpec("Monitor", "Overview", "overview", ":material/space_dashboard:", "overview"),
    PageSpec("Monitor", "Audit Queue", "audit-queue", ":material/flag:", "audit_queue"),
    PageSpec("Monitor", "Run Compare & Trends", "run-compare", ":material/compare_arrows:", "run_compare_view"),
    PageSpec("Audit", "Product Explorer", "product-explorer", ":material/table_view:", "explorer"),
    PageSpec("Audit", "Product Trace", "product-trace", ":material/receipt_long:", "trace"),
    PageSpec("Audit", "Score Lab", "score-lab", ":material/science:", "score_lab"),
    PageSpec("Audit", "Coverage & Calibration", "coverage-calibration", ":material/tune:", "coverage"),
    PageSpec("Intelligence", "Market Intelligence", "market-intelligence", ":material/storefront:", "market"),
    PageSpec("Intelligence", "Safety & Regulatory", "safety-regulatory", ":material/health_and_safety:", "safety"),
    PageSpec("Operations", "Data Quality, Release & Ops", "data-quality", ":material/monitor_heart:", "ops"),
]
DEFAULT_SLUG = "overview"
PAGE_BY_SLUG = {page.slug: page for page in PAGES}

# Links shared before the v4 revamp keep working.
LEGACY_VIEW_SLUGS = {
    "command-center": "overview",
    "product-inspector": "product-trace",
    "pipeline-health": "data-quality",
    "observability": "audit-queue",
    "release-diff": "run-compare",
    "batch-diff": "data-quality",
    "scoring-integrity": "audit-queue",
    "pillar-audit": "score-lab",
    "module-health": "score-lab",
    "suppression-audit": "safety-regulatory",
    "caers-audit": "safety-regulatory",
    "clinical-copy": "safety-regulatory",
    "intelligence": "market-intelligence",
}


def resolve_legacy_view(view: str | None) -> str | None:
    """Slug of the page that replaced a retired ``?view=`` value (or a current slug)."""
    if not view:
        return None
    view = str(view).strip().lower()
    if view in PAGE_BY_SLUG:
        return view
    return LEGACY_VIEW_SLUGS.get(view)
