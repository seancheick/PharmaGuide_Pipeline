# PharmaGuide Pipeline Dashboard

Internal read-only Streamlit dashboard for inspecting the PharmaGuide export, pipeline health, data quality, release diffs, observability, and intelligence views.

The refreshed UI is organized as an executive analytics workspace with:

- a `Command Center` landing page
- grouped navigation by workflow
- human-readable timestamps
- clear page-level source and freshness context

## Run

Run commands from the repository root:

`/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie`

Do not `cd` into `.venv`. Use the virtualenv binary from the repo root, or activate the virtualenv first.

Use the project virtualenv:

```bash
cd /Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie
.venv/bin/streamlit run scripts/dashboard/app.py
```

Alternative with an activated shell:

```bash
cd /Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie
source .venv/bin/activate
streamlit run scripts/dashboard/app.py
```

Optional explicit paths:

```bash
.venv/bin/streamlit run scripts/dashboard/app.py -- \
  --scan-dir scripts/products \
  --build-root scripts/final_db_output
```

Open a specific view directly after launch with `?view=`:

- `command-center`
- `product-inspector`
- `pipeline-health`
- `data-quality`
- `observability`
- `release-diff`
- `batch-diff`
- `intelligence`

## Inputs

The dashboard reads existing pipeline artifacts only.

- Release artifacts from `scripts/final_db_output/`
  - `pharmaguide_core.db`
  - `export_manifest.json`
  - `export_audit_report.json`
  - `detail_index.json`
  - `detail_blobs/*.json`
- Dataset and batch artifacts from `scripts/products/`
  - `output_*/`
  - `logs/processing_state.json`
  - `logs/batch_*_log.txt`

Important: the dashboard intentionally blends different data planes.

- `Release Snapshot` comes from `scripts/final_db_output/`
- `Pipeline Logs` come from `scripts/products/logs/`
- `Dataset Outputs` come from `scripts/products/output_*`

Those timelines may not match. The UI now labels that explicitly per page.

## Verification

Primary dashboard verification:

```bash
.venv/bin/python -m pytest -q \
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

## Notes

- The dashboard is read-only. It does not mutate the export DB or pipeline outputs.
- Current build-history and drift features are strongest when multiple build roots are available.
- Current dataset discovery supports both idealized report layouts and the workspace's real `output_*` / batch-log structure.
- Manual screenshot instructions live in `scripts/dashboard/INSTRUCTIONS.md`.
- Existing deep links still work through `?view=` and Product Inspector still supports `?dsld_id=`.
