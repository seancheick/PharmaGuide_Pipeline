# PharmaGuide Quality Control Dashboard

An internal, read-only Streamlit app for tracing every v4 score point by point,
filtering the catalog by any pillar, state or receipt line, catching anomalies, and
reviewing a candidate run against the release. The dashboard **never computes a
score**. It projects what the scorer already recorded:
- the per-pillar receipts in `quality_pillars_v4.<pillar>.receipt`;
- the gates;
- the dose-safety evaluation.

## Run

From the repository root (the theme lives in `.streamlit/config.toml`):

```bash
python -m scripts.dashboard.score_index refresh
streamlit run scripts/dashboard/app.py
```

Optional explicit paths (the same flags work for both commands):

```bash
streamlit run scripts/dashboard/app.py -- --scan-dir scripts/products --build-root scripts/dist
```

The Clinical Copy tab (Safety & Regulatory) compares pipeline data files with the
Flutter app's `assets/reference_data`. Pass `FLUTTER_REPO=/path/to/app` or
`-- --flutter-repo /path/to/app`.

## The index (`score_index.py`)

Pages read a small Parquet index under the gitignored `scripts/.cache/dashboard/`, never
the source JSON. Nothing in the pipeline or the release runs it.

| Command | What it does |
|---|---|
| `refresh` | Re-reads only what changed: scored batches whose stage-manifest hashes moved, and release blobs whose `detail_blob_sha256` moved. Cold build ~1–2 min, incremental seconds. |
| `backfill DB…` | Adds older `pharmaguide_core.db` catalogs as pillar-totals-only history. |
| `status` | Prints the current build, freshness and runs. |
| `gc` | Removes old builds; the current build and its predecessor are kept. |

How refresh behaves:
- Each refresh writes a new immutable build, validates it, then atomically swaps
  `current.json`. A failed refresh keeps the last good build and records the error in
  `status.json`.
- Pages show a stale banner and a **Refresh index** button when sources change.

Planes:

| Plane | Source | Notes |
|---|---|---|
| **candidate** | Scored JSON in `scripts/products/output_*_scored/scored/` | Readable right after scoring; not yet published. |
| **release** | `scripts/dist/pharmaguide_core.db` plus blobs | What ships. The total is whole-number by contract. |
| **backfill** | Older catalogs | Pillar totals only; movements show deltas, never invented causes. |

Each run records its plane, fidelity, config versions and the artifacts' stage-code and
reference-data fingerprints. The dashboard's own git SHA is labelled as the indexer's,
never the scorer's.

## Pages

| Group | Page | Answers |
|---|---|---|
| Monitor | Overview | Run health, KPIs, candidate vs release, top findings, drift |
| Monitor | Audit Queue | Versioned findings grouped by root cause, with local triage |
| Monitor | Run Compare & Trends | Baseline vs candidate movers and causes (`replay.reason_codes`), history |
| Audit | Product Explorer | Every product, six pillar bars, any filter, saved audit views |
| Audit | Product Trace | 100-point composition, per-pillar ledgers (nominal / realized / absorbed), gates, dose references, timeline, explain JSON |
| Audit | Score Lab | Distributions, rule impact, neutral usage, deductions and floors, caps, threshold cliffs, peer percentile (context only) |
| Audit | Coverage & Calibration | The config's calibration records, assessment coverage, golden set |
| Intelligence | Market Intelligence | Brand leaderboard (complete products, minimum counts), categories, verification, additives |
| Intelligence | Safety & Regulatory | Blocked/suppressed with reasons, caution signals, upper-limit findings, CAERS, safety copy |
| Operations | Data Quality, Release & Ops | Pipeline health, data quality, batch diff, index status |

Old `?view=` links redirect to the page that replaced them (`navigation.py`).

## Findings vs audit states

- **Audit states** are Product Explorer saved views (`saved_views.py`) and are not
  findings. Examples: Evidence 0, a neutral Dose, Verification neutral 6, Formula
  checks below 10, unrated forms.
- **Findings** are rules in `findings_rules.py`. Each has an id, a version, a severity
  and a policy citation. They cover:
  - receipt or pillar reconciliation;
  - penalties outside their registered pillar;
  - repeated Dose ceilings;
  - evidence gaps shown as assessed;
  - structured copy contradictions;
  - calibration records that are incomplete or stale;
  - unexplained score or safety changes.
- **Triage** (`triage.py`) lives in `scripts/.cache/dashboard_review/triage.sqlite`.
  - An accepted exception is scoped to the rule version and config version, so it
    reopens when either changes.

## Tests

```bash
scripts/test.sh fast scripts/tests/test_dashboard_score_index.py scripts/tests/test_dashboard_findings.py scripts/tests/test_dashboard_pages.py
```

`test_dashboard_smoke.py` and parts of `test_graceful_degradation.py` read real local
artifacts (local rung). The guard tests in `test_dashboard_pages.py` fail if the dashboard:
- imports a scorer executor;
- writes outside its cache;
- reintroduces retired v3 concepts.
