# Pipeline Dashboard UX Refresh Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the PharmaGuide Pipeline Dashboard into a modern executive analytics UI with grouped navigation, a new Command Center landing page, human-readable timestamps, and consistent per-page source/freshness context.

**Architecture:** Introduce shared UI primitives first: a page metadata contract, timestamp formatting helpers, a consistent page chrome/header/context pattern, and a new grouped navigation shell. Then migrate existing views onto that shell incrementally so deep links, data loading, and tests remain stable while the experience improves page by page.

**Tech Stack:** Python 3.13, Streamlit, Pandas, Plotly, existing dashboard components and tests

---

## File Structure

### Create

- `scripts/dashboard/components/page_frame.py`
  - Shared page scaffold for title, summary, source chips, freshness block, warnings, and right-side context panel with fallback layout.
- `scripts/dashboard/components/source_chips.py`
  - Small reusable visual tokens for `Release Snapshot`, `Pipeline Logs`, and `Dataset Outputs`.
- `scripts/dashboard/components/command_center.py`
  - New landing page summarizing release health, freshness, key alerts, and navigation shortcuts.
- `scripts/dashboard/app_shell.py`
  - Side-effect-light shell bootstrap that converts query params plus session state into dashboard shell state for `app.py`.
- `scripts/dashboard/page_meta.py`
  - Canonical metadata contract for each page, including source paths, data planes, freshness fields, related views, and usage notes.
- `scripts/dashboard/navigation.py`
  - Side-effect-light route definitions, query-param parsing, and grouped navigation metadata used by `app.py` and tests.
- `scripts/dashboard/time_format.py`
  - Human-readable datetime formatting helpers for full and compact display.
- `scripts/tests/test_dashboard_time_format.py`
  - Unit coverage for normal date formatting and timezone-aware output.
- `scripts/tests/test_dashboard_page_meta.py`
  - Coverage for metadata contract shape and mixed-plane warnings.
- `scripts/tests/test_dashboard_navigation.py`
  - Coverage for grouped route config and deep-link compatibility without importing `app.py`.
- `scripts/tests/test_dashboard_app_shell.py`
  - Coverage that app-shell bootstrap consumes query params into initial selected page and inspector state.
- `scripts/tests/test_dashboard_command_center.py`
  - Smoke test for the new Command Center rendering.

### Modify

- `scripts/dashboard/app.py`
  - Replace flat navigation with grouped sections and add the `Command Center` landing route while preserving `?view=` deep links.
- `scripts/dashboard/data_loader.py`
  - Expose any missing shared freshness/source metadata needed by page headers and the Command Center.
- `scripts/dashboard/views/inspector.py`
  - Move page title/context into the shared page frame and add source/freshness context.
- `scripts/dashboard/views/health.py`
  - Adopt shared header/context panel and human-readable dates.
- `scripts/dashboard/views/quality.py`
  - Adopt shared header/context panel and clearer source labeling.
- `scripts/dashboard/views/observability.py`
  - Adopt shared header/context panel and explicit mixed-plane warning.
- `scripts/dashboard/views/diff.py`
  - Adopt shared header/context panel and release-source emphasis.
- `scripts/dashboard/views/batch_diff.py`
  - Adopt shared header/context panel and pipeline-log source emphasis.
- `scripts/dashboard/views/intelligence.py`
  - Adopt shared header/context panel and release/detail-blob source emphasis.
- `scripts/dashboard/README.md`
  - Update with the new navigation model and Command Center description.
- `scripts/dashboard/INSTRUCTIONS.md`
  - Update walkthrough and screenshot instructions for the new UI.
- `docs/plans/pipeline-dashboard-sprint-tracker.md`
  - Record the UX refresh sprint with accurate verification evidence.
- `docs/plans/LESSONS_LEARNED.md`
  - Add the redesign sprint retrospective after implementation.

### Test

- `scripts/tests/test_dashboard_smoke.py`
  - Update to render the new shell and Command Center route.
- `scripts/tests/test_dashboard_empty_db.py`
  - Ensure the new page frame and Command Center handle empty/minimal data.
- `scripts/tests/test_dashboard_architecture.py`
  - Extend architecture assertions for metadata/freshness primitives if needed.

## Task 1: Shared Metadata And Date Formatting Primitives

**Files:**
- Create: `scripts/dashboard/page_meta.py`
- Create: `scripts/dashboard/time_format.py`
- Test: `scripts/tests/test_dashboard_time_format.py`
- Test: `scripts/tests/test_dashboard_page_meta.py`

- [ ] **Step 1: Write the failing tests**

```python
from datetime import datetime, timezone

from scripts.dashboard.page_meta import PAGE_META
from scripts.dashboard.time_format import format_dashboard_datetime


def test_format_dashboard_datetime_humanizes_iso_timestamp():
    value = datetime(2026, 4, 9, 13, 1, 20, tzinfo=timezone.utc)
    rendered = format_dashboard_datetime(value, style="full")
    assert "Thursday, April 9, 2026" in rendered


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest -q \
  scripts/tests/test_dashboard_time_format.py \
  scripts/tests/test_dashboard_page_meta.py
```

Expected: FAIL because the new modules do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/dashboard/time_format.py
def format_dashboard_datetime(value, style="full", fallback="N/A"):
    ...

# scripts/dashboard/page_meta.py
PAGE_META = {
    "command-center": {
        "page_title": "Command Center",
        "page_summary": "...",
        "data_planes": ["Release Snapshot", "Pipeline Logs", "Dataset Outputs"],
        "source_paths": [...],
        "freshness_fields": [...],
        "mixed_plane_warning": "...",
        "related_views": [...],
        "usage_notes": [...],
    },
    ...
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest -q \
  scripts/tests/test_dashboard_time_format.py \
  scripts/tests/test_dashboard_page_meta.py
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add \
  scripts/dashboard/page_meta.py \
  scripts/dashboard/time_format.py \
  scripts/tests/test_dashboard_time_format.py \
  scripts/tests/test_dashboard_page_meta.py
git commit -m "feat: add dashboard metadata and time formatting primitives"
```

## Task 2: Shared Page Frame And Source Context UI

**Files:**
- Create: `scripts/dashboard/components/page_frame.py`
- Create: `scripts/dashboard/components/source_chips.py`
- Modify: `scripts/dashboard/components/__init__.py`
- Test: `scripts/tests/test_dashboard_smoke.py`
- Test: `scripts/tests/test_dashboard_empty_db.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_page_frame_renders_header_and_context_panel():
    from scripts.dashboard.components.page_frame import render_page_frame
    assert render_page_frame is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest -q \
  scripts/tests/test_dashboard_smoke.py \
  scripts/tests/test_dashboard_empty_db.py
```

Expected: FAIL because the new frame component is not wired.

- [ ] **Step 3: Write minimal implementation**

```python
def render_page_frame(meta, data, body_renderer):
    header_col, side_col = st.columns([3.2, 1.2])
    with header_col:
        ...
        body_renderer()
    with side_col:
        ...
```

Implementation requirements:
- Desktop-first right context column
- Fallback to expander or below-the-fold block when width constraints are hit
- Source chips rendered consistently
- Human-readable timestamps only in header/context surfaces

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest -q \
  scripts/tests/test_dashboard_smoke.py \
  scripts/tests/test_dashboard_empty_db.py
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add \
  scripts/dashboard/components/page_frame.py \
  scripts/dashboard/components/source_chips.py \
  scripts/dashboard/components/__init__.py \
  scripts/tests/test_dashboard_smoke.py \
  scripts/tests/test_dashboard_empty_db.py
git commit -m "feat: add dashboard page frame and source context UI"
```

## Task 3: App Shell, Grouped Navigation, And Deep-Link Compatibility

**Files:**
- Create: `scripts/dashboard/components/command_center.py`
- Create: `scripts/dashboard/app_shell.py`
- Create: `scripts/dashboard/navigation.py`
- Modify: `scripts/dashboard/app.py`
- Modify: `scripts/dashboard/page_meta.py`
- Test: `scripts/tests/test_dashboard_navigation.py`
- Test: `scripts/tests/test_dashboard_app_shell.py`
- Test: `scripts/tests/test_dashboard_command_center.py`
- Test: `scripts/tests/test_dashboard_smoke.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_command_center_route_exists():
    from scripts.dashboard.components.command_center import render_command_center
    assert render_command_center is not None


def test_navigation_keeps_existing_view_slugs():
    from scripts.dashboard.navigation import VIEW_BY_SLUG
    assert VIEW_BY_SLUG["product-inspector"] == "Product Inspector"
    assert VIEW_BY_SLUG["pipeline-health"] == "Pipeline Health"


def test_navigation_default_is_command_center():
    from scripts.dashboard.navigation import DEFAULT_VIEW
    assert DEFAULT_VIEW == "Command Center"


def test_query_params_select_existing_view():
    from scripts.dashboard.navigation import parse_dashboard_query_params
    state = parse_dashboard_query_params({"view": "product-inspector"})
    assert state.current_view == "Product Inspector"


def test_query_params_preserve_product_inspector_dsld_id():
    from scripts.dashboard.navigation import parse_dashboard_query_params
    state = parse_dashboard_query_params({"view": "product-inspector", "dsld_id": "12345"})
    assert state.current_view == "Product Inspector"
    assert state.selected_dsld_id == "12345"


def test_app_shell_bootstrap_consumes_query_params():
    from scripts.dashboard.app_shell import build_initial_shell_state
    state = build_initial_shell_state(
        query_params={"view": "product-inspector", "dsld_id": "12345"},
        session_state={},
    )
    assert state["current_view"] == "Product Inspector"
    assert state["selected_dsld_id"] == "12345"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest -q \
  scripts/tests/test_dashboard_navigation.py \
  scripts/tests/test_dashboard_app_shell.py \
  scripts/tests/test_dashboard_command_center.py \
  scripts/tests/test_dashboard_smoke.py
```

Expected: FAIL because `Command Center` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
VIEW_GROUPS = {
    "Command Center": ["Command Center"],
    "Release": ["Product Inspector", "Release Diff"],
    "Pipeline": ["Pipeline Health", "Observability", "Batch Diff"],
    "Quality": ["Data Quality"],
    "Intelligence": ["Intelligence"],
}


@dataclass
class DashboardRouteState:
    current_view: str
    selected_dsld_id: str | None


def parse_dashboard_query_params(params):
    ...
```

```python
# scripts/dashboard/app_shell.py
def build_initial_shell_state(query_params, session_state):
    route_state = parse_dashboard_query_params(query_params)
    return {
        "current_view": route_state.current_view,
        "selected_dsld_id": route_state.selected_dsld_id or session_state.get("selected_dsld_id"),
    }
```

Implementation requirements:
- Keep top title `PharmaGuide Pipeline Dashboard`
- Preserve `?view=` behavior for all existing pages
- Preserve `?dsld_id=` for inspector
- Make `Command Center` the default landing page
- Add global freshness/status strip in the shell
- Keep route parsing in `scripts/dashboard/navigation.py` so tests do not import `app.py`
- Keep `app.py` thin and delegate query-param/session bootstrap into `scripts/dashboard/app_shell.py`

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest -q \
  scripts/tests/test_dashboard_navigation.py \
  scripts/tests/test_dashboard_app_shell.py \
  scripts/tests/test_dashboard_command_center.py \
  scripts/tests/test_dashboard_smoke.py
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add \
  scripts/dashboard/components/command_center.py \
  scripts/dashboard/app_shell.py \
  scripts/dashboard/navigation.py \
  scripts/dashboard/app.py \
  scripts/dashboard/page_meta.py \
  scripts/tests/test_dashboard_navigation.py \
  scripts/tests/test_dashboard_app_shell.py \
  scripts/tests/test_dashboard_command_center.py \
  scripts/tests/test_dashboard_smoke.py
git commit -m "feat: add command center and grouped dashboard navigation"
```

## Task 4: Migrate Operational Pages To The New Shell

**Files:**
- Modify: `scripts/dashboard/views/health.py`
- Modify: `scripts/dashboard/views/observability.py`
- Modify: `scripts/dashboard/views/batch_diff.py`
- Modify: `scripts/dashboard/data_loader.py`
- Test: `scripts/tests/test_dashboard_smoke.py`
- Test: `scripts/tests/test_dashboard_empty_db.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_operational_pages_define_mixed_plane_metadata_when_needed():
    from scripts.dashboard.page_meta import PAGE_META
    assert PAGE_META["observability"]["mixed_plane_warning"]
    assert "Pipeline Logs" in PAGE_META["batch-diff"]["data_planes"]


def test_health_page_uses_human_readable_datetime_strings():
    from scripts.dashboard.time_format import format_dashboard_datetime
    rendered = format_dashboard_datetime(...)
    assert " at " in rendered
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest -q \
  scripts/tests/test_dashboard_page_meta.py \
  scripts/tests/test_dashboard_time_format.py \
  scripts/tests/test_dashboard_smoke.py \
  scripts/tests/test_dashboard_empty_db.py
```

Expected: FAIL until the operational pages are wired to shared metadata/freshness behavior.

- [ ] **Step 3: Write minimal implementation**

Implementation requirements:
- `Pipeline Health` uses the shared frame and readable dates for release/build/batch timestamps
- `Observability` shows explicit mixed-plane warning when it combines release and log data
- `Batch Diff` labels itself as `Pipeline Logs`
- `data_loader.py` exposes any missing header freshness data in one normalized place

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest -q \
  scripts/tests/test_dashboard_page_meta.py \
  scripts/tests/test_dashboard_time_format.py \
  scripts/tests/test_dashboard_smoke.py \
  scripts/tests/test_dashboard_empty_db.py \
  scripts/tests/test_dashboard_loader.py
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add \
  scripts/dashboard/views/health.py \
  scripts/dashboard/views/observability.py \
  scripts/dashboard/views/batch_diff.py \
  scripts/dashboard/data_loader.py \
  scripts/tests/test_dashboard_page_meta.py \
  scripts/tests/test_dashboard_time_format.py \
  scripts/tests/test_dashboard_smoke.py \
  scripts/tests/test_dashboard_empty_db.py \
  scripts/tests/test_dashboard_loader.py
git commit -m "feat: migrate operational dashboard pages to new shell"
```

## Task 5: Migrate Analytical And Release Pages To The New Shell

**Files:**
- Modify: `scripts/dashboard/views/quality.py`
- Modify: `scripts/dashboard/views/intelligence.py`
- Modify: `scripts/dashboard/views/inspector.py`
- Modify: `scripts/dashboard/views/diff.py`
- Test: `scripts/tests/test_dashboard_smoke.py`
- Test: `scripts/tests/test_graceful_degradation.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_release_pages_keep_deep_link_compatibility():
    from scripts.dashboard.navigation import parse_dashboard_query_params
    state = parse_dashboard_query_params({"view": "release-diff"})
    assert state.current_view == "Release Diff"


def test_product_inspector_deep_link_still_accepts_dsld_id():
    from scripts.dashboard.navigation import parse_dashboard_query_params
    state = parse_dashboard_query_params({"dsld_id": "67890"})
    assert state.current_view == "Product Inspector"
    assert state.selected_dsld_id == "67890"


def test_analytical_pages_declare_expected_data_planes():
    from scripts.dashboard.page_meta import PAGE_META
    assert PAGE_META["quality"]["data_planes"] == ["Release Snapshot", "Dataset Outputs"]
    assert PAGE_META["intelligence"]["data_planes"] == ["Release Snapshot"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest -q \
  scripts/tests/test_dashboard_navigation.py \
  scripts/tests/test_dashboard_page_meta.py \
  scripts/tests/test_dashboard_smoke.py \
  scripts/tests/test_graceful_degradation.py
```

Expected: FAIL until the release and analytical pages are fully migrated to the new frame and metadata contract.

- [ ] **Step 3: Write minimal implementation**

Implementation requirements:
- `Data Quality` clearly labels dataset-output sources
- `Intelligence` clearly labels release DB plus detail-blob sources
- `Product Inspector` keeps deep-link behavior and adds clearer source/freshness context
- `Release Diff` frames itself as release-comparison data, not live pipeline data

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest -q \
  scripts/tests/test_dashboard_navigation.py \
  scripts/tests/test_dashboard_page_meta.py \
  scripts/tests/test_dashboard_smoke.py \
  scripts/tests/test_graceful_degradation.py \
  scripts/tests/test_dashboard_loader.py
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add \
  scripts/dashboard/views/quality.py \
  scripts/dashboard/views/intelligence.py \
  scripts/dashboard/views/inspector.py \
  scripts/dashboard/views/diff.py \
  scripts/tests/test_dashboard_navigation.py \
  scripts/tests/test_dashboard_page_meta.py \
  scripts/tests/test_dashboard_smoke.py \
  scripts/tests/test_graceful_degradation.py \
  scripts/tests/test_dashboard_loader.py
git commit -m "feat: migrate analytical and release pages to new shell"
```

## Task 6: Visual Polish, Documentation, And Final Verification

**Files:**
- Modify: `scripts/dashboard/README.md`
- Modify: `scripts/dashboard/INSTRUCTIONS.md`
- Modify: `docs/plans/pipeline-dashboard-sprint-tracker.md`
- Modify: `docs/plans/LESSONS_LEARNED.md`
- Test: `scripts/tests/test_dashboard_empty_db.py`
- Test: `scripts/tests/test_dashboard_architecture.py`
- Test: `scripts/tests/test_dashboard_smoke.py`
- Test: `scripts/tests/test_dashboard_loader.py`
- Test: `scripts/tests/test_graceful_degradation.py`
- Test: `scripts/tests/test_batch_run_all_datasets.py`

- [ ] **Step 1: Write the failing test or verification checklist**

```python
def test_command_center_and_existing_deep_links_render_in_smoke_suite():
    from scripts.dashboard.navigation import parse_dashboard_query_params
    assert parse_dashboard_query_params({"view": "command-center"}).current_view == "Command Center"
    assert parse_dashboard_query_params({"view": "product-inspector", "dsld_id": "42"}).selected_dsld_id == "42"
```

This task is verification-heavy rather than unit-heavy. The acceptance test is the full suite plus a live app launch.

- [ ] **Step 2: Run verification to identify remaining gaps**

Run:

```bash
.venv/bin/python -m pytest -q \
  scripts/tests/test_dashboard_empty_db.py \
  scripts/tests/test_dashboard_architecture.py \
  scripts/tests/test_dashboard_navigation.py \
  scripts/tests/test_dashboard_app_shell.py \
  scripts/tests/test_dashboard_page_meta.py \
  scripts/tests/test_dashboard_time_format.py \
  scripts/tests/test_dashboard_command_center.py \
  scripts/tests/test_dashboard_smoke.py \
  scripts/tests/test_dashboard_loader.py \
  scripts/tests/test_graceful_degradation.py \
  scripts/tests/test_batch_run_all_datasets.py
```

Expected: PASS after implementation completes.

- [ ] **Step 3: Write minimal implementation**

Implementation requirements:
- Update docs to describe the new `Command Center` and grouped navigation
- Update manual screenshot instructions for the refreshed pages
- Record the UX refresh sprint honestly in tracker and lessons
- Confirm the live app launches from repo root with Streamlit

- [ ] **Step 4: Run final verification**

Run:

```bash
PYTHONPYCACHEPREFIX=/tmp/pycache .venv/bin/python -m py_compile \
  scripts/dashboard/app.py \
  scripts/dashboard/app_shell.py \
  scripts/dashboard/data_loader.py \
  scripts/dashboard/navigation.py \
  scripts/dashboard/page_meta.py \
  scripts/dashboard/time_format.py \
  scripts/dashboard/components/page_frame.py \
  scripts/dashboard/components/source_chips.py \
  scripts/dashboard/components/command_center.py \
  scripts/dashboard/views/health.py \
  scripts/dashboard/views/quality.py \
  scripts/dashboard/views/observability.py \
  scripts/dashboard/views/intelligence.py \
  scripts/dashboard/views/inspector.py \
  scripts/dashboard/views/diff.py \
  scripts/dashboard/views/batch_diff.py
```

Then:

```bash
.venv/bin/streamlit run scripts/dashboard/app.py --server.headless true --server.port 8599
```

And verify:

```bash
curl -I http://127.0.0.1:8599
```

Expected:
- py_compile PASS
- pytest PASS
- Streamlit launches without traceback
- curl returns `HTTP/1.1 200 OK`

- [ ] **Step 5: Commit**

```bash
git add \
  scripts/dashboard/README.md \
  scripts/dashboard/INSTRUCTIONS.md \
  docs/plans/pipeline-dashboard-sprint-tracker.md \
  docs/plans/LESSONS_LEARNED.md \
  scripts/tests/test_dashboard_navigation.py \
  scripts/tests/test_dashboard_app_shell.py \
  scripts/tests/test_dashboard_page_meta.py \
  scripts/tests/test_dashboard_time_format.py \
  scripts/tests/test_dashboard_command_center.py
git commit -m "docs: complete dashboard ux refresh handoff"
```

## Notes For Execution

- Preserve `?view=` and `?dsld_id=` deep links throughout the migration.
- Do not rewrite data logic into the UI if the loader can expose it once.
- Keep the redesign honest about mixed timelines. A polished UI that hides stale-release vs fresh-pipeline differences is a regression.
- Prefer shared primitives over per-page ad hoc styling.
- If the right-side context panel is too constrained in Streamlit for a given page, use the spec-approved fallback order rather than dropping the context.
