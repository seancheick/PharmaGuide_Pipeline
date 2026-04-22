# PharmaGuide Dashboard Instructions

This file explains what the dashboard is, where its data comes from, how to run it, how to test it, and what to check before you tell anyone it is ready.

## What This Dashboard Does

The dashboard is an internal, read-only operator tool for the PharmaGuide data pipeline. It is not part of the consumer app. It helps an engineer or operator:

- start from a `Command Center` summary page
- inspect products in the final export
- review release health and gate status
- triage quality issues and missing data
- audit Section A (ingredient quality) scoring
- compare builds and batch runs
- monitor observability and alert conditions
- review market / ingredient / brand intelligence derived from the export

The dashboard reads files that already exist on disk. It does not write to the release database or pipeline outputs.

The refreshed UI distinguishes three data planes:

- `Release Snapshot`
- `Pipeline Logs`
- `Dataset Outputs`

That matters because those timelines can differ. The dashboard now shows source chips and freshness context on every page so you can tell whether a number came from the released export, a current batch log, or a dataset output directory.

## Main Files

Core app files:

- `scripts/dashboard/app.py`
- `scripts/dashboard/config.py`
- `scripts/dashboard/data_loader.py`

View files:

- `scripts/dashboard/components/command_center.py`
- `scripts/dashboard/views/inspector.py`
- `scripts/dashboard/views/health.py`
- `scripts/dashboard/views/quality.py`
- `scripts/dashboard/views/audit_section_a.py`
- `scripts/dashboard/views/observability.py`
- `scripts/dashboard/views/diff.py`
- `scripts/dashboard/views/batch_diff.py`
- `scripts/dashboard/views/intelligence.py`

Support files:

- `scripts/dashboard/app_shell.py`
- `scripts/dashboard/navigation.py`
- `scripts/dashboard/page_meta.py`
- `scripts/dashboard/time_format.py`
- `scripts/dashboard/dashboard_alerts.json`
- `scripts/dashboard/README.md`
- `scripts/dashboard/requirements.txt`

Tests:

- `scripts/tests/test_dashboard_loader.py`
- `scripts/tests/test_graceful_degradation.py`
- `scripts/tests/test_dashboard_architecture.py`
- `scripts/tests/test_dashboard_smoke.py`
- `scripts/tests/test_dashboard_empty_db.py`

## Data Sources

The dashboard reads two main groups of artifacts.

Release artifacts from `scripts/dist/`:

- `pharmaguide_core.db`
- `export_manifest.json`
- `export_audit_report.json` (optional)
- `detail_index.json` (optional)
- `detail_blobs/*.json` (optional)

Dataset and pipeline artifacts from `scripts/products/` (if present):

- `output_*/`
- `logs/processing_state.json`
- `logs/batch_*_log.txt`

The loader also supports the idealized report layout if those files exist later:

- `output_*/reports/enrichment_summary_*.json`
- `output_*/reports/scoring_summary_*.json`
- `output_*/reports/coverage_report_*.json`

## Important Design Rules

- The dashboard is read-only.
- SQLite is the main compute layer for product/export facts.
- Views should prefer normalized loader data instead of recomputing their own release metrics.
- Build history should come from the loader abstraction, not ad hoc scanning inside views.
- If files are missing, the dashboard should degrade gracefully instead of crashing.
- The UI should clearly distinguish release snapshot data from newer pipeline and dataset activity.
- Raw ISO timestamps should not be the primary display format in the UI.

## Run Commands

Run all dashboard commands from the repository root:

```
/Users/seancheick/Downloads/dsld_clean
```

The dashboard defaults to reading release data from `scripts/dist/` and pipeline data from `scripts/products/`.

Recommended start flow:

```bash
cd /Users/seancheick/Downloads/dsld_clean
streamlit run scripts/dashboard/app.py
```

bash scripts/rebuild_dashboard_snapshot.sh
streamlit run scripts/dashboard/app.py

Run with explicit scan/build roots:

```bash
streamlit run scripts/dashboard/app.py -- \
  --scan-dir scripts/products \
  --build-root scripts/dist
```

Open a specific main view directly with the `view` query param after the app starts:

- `http://127.0.0.1:8501/?view=command-center`
- `http://127.0.0.1:8501/?view=product-inspector`
- `http://127.0.0.1:8501/?view=pipeline-health`
- `http://127.0.0.1:8501/?view=data-quality`
- `http://127.0.0.1:8501/?view=section-a-audit`
- `http://127.0.0.1:8501/?view=observability`
- `http://127.0.0.1:8501/?view=release-diff`
- `http://127.0.0.1:8501/?view=batch-diff`
- `http://127.0.0.1:8501/?view=intelligence`

If you need to test a different dataset/build root:

```bash
streamlit run scripts/dashboard/app.py -- \
  --scan-dir /path/to/products \
  --build-root /path/to/dist \
  --dataset-root /optional/path/to/dataset/root
```

## Expected Startup Behavior

Normal behavior:

- Streamlit starts
- a local URL is printed
- the dashboard loads in the browser with `Command Center` as the default page
- the top header reads `PharmaGuide Pipeline Dashboard`
- each page shows source/freshness context

Not normal:

- `ModuleNotFoundError: No module named 'scripts'`

That import error was a real app bug, not expected behavior. The dashboard now adds the repo root to `sys.path` in `scripts/dashboard/app.py`, so starting it from the repo root should work.

If you still see that old error:

1. Confirm you are in `/Users/seancheick/Downloads/dsld_clean`
2. Confirm you restarted Streamlit after the fix
3. Confirm the updated file exists at `scripts/dashboard/app.py`

## Test Commands

Run the dashboard verification suite:

```bash
python3 -m pytest -q \
  scripts/tests/test_dashboard_navigation.py \
  scripts/tests/test_dashboard_app_shell.py \
  scripts/tests/test_dashboard_page_meta.py \
  scripts/tests/test_dashboard_time_format.py \
  scripts/tests/test_dashboard_command_center.py \
  scripts/tests/test_dashboard_architecture.py \
  scripts/tests/test_dashboard_smoke.py \
  scripts/tests/test_dashboard_loader.py \
  scripts/tests/test_graceful_degradation.py \
  scripts/tests/test_dashboard_empty_db.py \
  scripts/tests/test_batch_run_all_datasets.py
```

Run only smoke coverage for all views:

```bash
python3 -m pytest -q scripts/tests/test_dashboard_smoke.py
```

Run only loader checks:

```bash
python3 -m pytest -q \
  scripts/tests/test_dashboard_loader.py \
  scripts/tests/test_dashboard_architecture.py
```

Run only empty-state checks:

```bash
python3 -m pytest -q \
  scripts/tests/test_graceful_degradation.py \
  scripts/tests/test_dashboard_empty_db.py
```

## What To Verify Before Calling It Ready

Minimum:

1. The full dashboard pytest suite passes.
2. The app launches locally with Streamlit.
3. The `Command Center` loads as the default page.
4. The grouped navigation works.
5. The dashboard handles missing files and an empty export without throwing exceptions.
6. Page headers show source and freshness context.

Better:

1. Confirm the `Command Center` clearly shows release snapshot freshness versus pipeline freshness.
2. Open Product Inspector and search a known product.
3. Open Health and confirm release gate / batch sections render.
4. Open Quality and confirm distributions plus queue tabs render.
5. Open Section A Audit and confirm ingredient quality scoring and probiotic CFU sections render.
6. Open Observability and confirm integrity / analytics tabs render.
7. Open Diff and Batch Diff and confirm selectors and tables render.
8. Open Intelligence and confirm category, ingredient, brand, and driver sections render.

## Manual Screenshot Handoff

If browser automation is flaky on your machine, take the screenshots manually.

1. Start the app:

```bash
streamlit run scripts/dashboard/app.py --server.headless true --server.port 8599
```

2. Open each of these URLs in your browser:

- `http://127.0.0.1:8599/?view=command-center`
- `http://127.0.0.1:8599/?view=product-inspector`
- `http://127.0.0.1:8599/?view=pipeline-health`
- `http://127.0.0.1:8599/?view=data-quality`
- `http://127.0.0.1:8599/?view=section-a-audit`
- `http://127.0.0.1:8599/?view=observability`
- `http://127.0.0.1:8599/?view=release-diff`
- `http://127.0.0.1:8599/?view=batch-diff`
- `http://127.0.0.1:8599/?view=intelligence`

3. Wait for the page to finish rendering before capturing.
4. Save each PNG into `docs/plans/dashboard-screenshots/` using these filenames:

- `command-center.png`
- `product-inspector.png`
- `pipeline-health.png`
- `data-quality.png`
- `section-a-audit.png`
- `observability.png`
- `release-diff.png`
- `batch-diff.png`
- `intelligence.png`

5. If you need an automated starting point, this script exists:

```bash
python3 scripts/dashboard/capture_screenshots.py --base-url http://127.0.0.1:8599
```

Use that only if headless Chrome behaves correctly on your machine. Manual browser capture is acceptable for handoff evidence.

## Known Practical Constraints

- Some advanced features are stronger when multiple builds exist on disk.
- Some dataset-level sections depend on actual `output_*` content, which may vary by workspace.
- In restricted environments, launching Streamlit may require permission to bind a local port.
- The `scripts/products/` directory may not exist until you run the pipeline at least once.

## If A Junior Engineer Needs To Modify This

Recommended order:

1. Read `scripts/dashboard/data_loader.py` first.
2. Then read `scripts/dashboard/page_meta.py` and `scripts/dashboard/navigation.py`.
3. Identify whether the change belongs in the loader, shared shell, or a specific view.
4. If multiple views need the same data, add it to the loader once instead of recomputing it in each view.
5. Add or update tests before changing behavior.
6. Re-run the dashboard test suite.
7. If behavior changed materially, update this file.

## Quick Troubleshooting

If the dashboard does not load:

- check that `streamlit`, `pandas`, and `plotly` are installed (`pip install -r scripts/dashboard/requirements.txt`)
- check that `scripts/dist/pharmaguide_core.db` exists
- run the loader tests first
- check whether the environment blocks local port binding

If a view shows less data than expected:

- inspect `scripts/dashboard/data_loader.py`
- verify the required files actually exist in `scripts/dist/` or `scripts/products/`
- confirm the section is using shared loader data instead of stale view-local logic
