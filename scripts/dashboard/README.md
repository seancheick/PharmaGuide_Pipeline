# PharmaGuide Pipeline Dashboard

Internal read-only Streamlit dashboard for inspecting the PharmaGuide export, pipeline health, data quality, release diffs, observability, and intelligence views.

The refreshed UI is organized as an executive analytics workspace with:

- a `Command Center` landing page
- grouped navigation by workflow
- human-readable timestamps
- clear page-level source and freshness context

## Run

Run commands from the repository root:

```bash
cd /Users/seancheick/Downloads/dsld_clean
streamlit run scripts/dashboard/app.py
```

Optional explicit paths:

```bash
streamlit run scripts/dashboard/app.py -- \
  --scan-dir scripts/products \
  --build-root scripts/dist
```

The `Clinical Copy` view compares pipeline data files with the app's
`assets/reference_data` copies. Point it at the Flutter checkout the same way the
release scripts are pointed: `FLUTTER_REPO=/path/to/app` in the environment, or
`-- --flutter-repo /path/to/app`. Without either, the view reports the Flutter asset
sync as not configured instead of comparing.

Open a specific view directly after launch with `?view=`:

- `command-center`
- `product-inspector`
- `pipeline-health`
- `data-quality`
- `pillar-audit`
- `observability`
- `release-diff`
- `batch-diff`
- `intelligence`

## Inputs

The dashboard reads existing pipeline artifacts only.

- Release artifacts from `scripts/dist/`
  - `pharmaguide_core.db`
  - `export_manifest.json`
  - `export_audit_report.json` (optional)
  - `detail_index.json` (optional)
  - `detail_blobs/*.json` (optional)
- Dataset and batch artifacts from `scripts/products/` (if present)
  - `output_*/`
  - `logs/processing_state.json`
  - `logs/batch_*_log.txt`

Important: the dashboard intentionally blends different data planes.

- `Release Snapshot` comes from `scripts/dist/`
- `Pipeline Logs` come from `scripts/products/logs/`
- `Dataset Outputs` come from `scripts/products/output_*`

Those timelines may not match. The UI now labels that explicitly per page.

## Scoring config and CAERS

- The `Config Snapshot` tab of `Data Quality` shows the production v4 config: the
  version and fingerprint of `scripts/scoring_v4/config/quality_score.json` and
  `scripts/data/omega_rubric.json` from `scoring_v4/config_registry.py`, the
  pillar maxima, and whether the released catalog was scored with the same
  config (`products_core.v4_config_fingerprint`).
- `CAERS Audit` is analytics only. The v4 score applies no CAERS penalty; the
  v3 B8 penalty was disabled on 2026-04-30 and removed on 2026-06-24, and the
  `Scoring Status` tab records why.
- No view reads the retired v3 file `scripts/config/scoring_config.json`.

## Verification

Primary dashboard verification:

```bash
scripts/test.sh fast -k "dashboard or graceful_degradation or batch_run_all_datasets"
```

## Notes

- The dashboard is read-only. It does not mutate the export DB or pipeline outputs.
- Current build-history and drift features are strongest when multiple build roots are available.
- Current dataset discovery supports both idealized report layouts and the workspace's real `output_*` / batch-log structure.
- Manual screenshot instructions live in `scripts/dashboard/INSTRUCTIONS.md`.
- Existing deep links still work through `?view=` and Product Inspector still supports `?dsld_id=`.
