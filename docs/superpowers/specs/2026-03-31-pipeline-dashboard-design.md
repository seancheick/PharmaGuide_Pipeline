# PharmaGuide Pipeline Operator Dashboard — Design Spec

> Version: 1.2.0 | Date: 2026-03-31
> Status: Verified against actual files — pending final review
> Stack: Python 3.13 + Streamlit + Pandas + Plotly
> Scope: Read-only internal operator dashboard, local-only, no auth

---

## 1. Purpose

An internal Streamlit dashboard for the PharmaGuide pipeline operator to:

1. **Inspect any product** from the final export, with best-effort links to enriched/scored source files when resolvable
2. **Check pipeline health**: did the last run succeed, what's the current release, are release artifacts ready, which stage failed
3. **Triage data quality**: unmapped ingredients, fallbacks, not-scored products, coverage gaps
4. **Explain scores**: show pillar totals plus a trace-lite of how the exported score was assembled from section breakdown, bonuses, and penalties
5. **Compare releases** (phase 2): score shifts, verdict changes, added/removed products

This is a read-only tool. It never writes to the database, pipeline outputs, or Supabase. It reads existing JSON reports and SQLite files that the pipeline already produces.

---

## 2. Architecture

### 2.1 File Structure

```
scripts/dashboard/
  app.py                    # Streamlit entry point, sidebar nav, global layout
  config.py                 # CLI arg parsing, defaults, root resolution
  data_loader.py            # Auto-discovery, JSON/SQLite readers, path normalization
  views/
    inspector.py            # View 1: Product Inspector (landing page)
    health.py               # View 2: Pipeline Health
    quality.py              # View 3: Data Quality
    diff.py                 # View 4: Release Diff (phase 2 — designed, not built in v1)
  components/
    metric_cards.py         # KPI card row (count + label + color)
    score_breakdown.py      # 4-pillar horizontal bar display
    score_trace.py          # Trace-lite view of exported score components
    product_header.py       # Name/brand/verdict/grade/score header block
    status_badge.py         # Pass/fail/warning status badges
    data_table.py           # Styled dataframe wrapper with sorting/filtering
    data_dictionary.py      # Field/tool-tip dictionary used across metrics and tables
```

### 2.2 Run Command

```bash
streamlit run scripts/dashboard/app.py -- \
  --scan-dir scripts/ \
  --build-root scripts/final_db_output/ \
  --dataset-root /Users/seancheick/Documents/DataSetDsld/
```

All args have sensible defaults so `streamlit run scripts/dashboard/app.py` works after installing dashboard dependencies (`pip install streamlit pandas plotly`). These are dev-only dependencies, not added to the pipeline's core `requirements.txt`.

### 2.3 CLI Arguments

| Arg | Default | Purpose |
|-----|---------|---------|
| `--scan-dir` | `scripts/` | Where to find `output_*` directories, `batch_run_summary_*.txt`, `logs/`, `config/` |
| `--build-root` | `scripts/final_db_output/` | Where the release artifacts live (SQLite DB, detail blobs, export manifest, audit report) |
| `--dataset-root` | None (optional) | External dataset location (e.g. `Documents/DataSetDsld/`) for newer flow builds |

Resolution order for release artifacts:
1. `--build-root` (explicit)
2. If `--dataset-root` is provided, also scan `{dataset-root}/builds/` for release artifacts
3. If multiple release DBs are found, use the one with the latest `export_manifest.generated_at`

### 2.4 Data Source Separation

The loader cleanly separates two categories:

**Release artifacts** (from `--build-root` or `--dataset-root`):
- `pharmaguide_core.db` — SQLite, the product inspector's primary data source
- `detail_blobs/*.json` — per-product detail drill-down
- `detail_index.json` — dsld_id → blob hash mapping
- `export_manifest.json` — release version metadata
- `export_audit_report.json` — safety/verdict aggregate counts

**Dataset reports** (from `--scan-dir`):
- `output_*/reports/enrichment_summary_*.json` — per-brand enrichment quality
- `output_*/reports/scoring_summary_*.json` — per-brand score distributions
- `output_*/reports/coverage_report_*.json` — per-brand coverage gate results
- `output_*/reports/form_fallback_audit_report.json` — form fallback triage
- `output_*/reports/parent_fallback_report.json` — parent fallback triage
- `batch_run_summary_*.txt` — batch run history
- `logs/processing_state.json` — latest run state
- `config/scoring_config.json` — current scoring parameters

**Resilience rule**: if any file is missing, that section shows "No data available" with the expected path. The dashboard never crashes on missing data.

### 2.5 Implementation Rules

- **SQLite is the compute layer.** Use SQL for counts, distributions, grouping, and filters whenever the data originates in `products_core`.
- **Pandas is the rendering layer.** Use DataFrames only after query results have already been narrowed.
- **Manual refresh is the default.** Auto-refresh is optional and opt-in.
- **Deep-link state is first-class.** Product Inspector must support URL query params such as `?dsld_id=12345`.
- **Trace-lite, not synthetic exactness.** The score trace should explain exported score structure from actual artifacts (`section_breakdown`, `score_bonuses`, `score_penalties`), but should not claim to be a line-by-line replay of scorer internals unless the scorer exports a canonical trace in the future.

---

## 3. Navigation

### 3.1 Sidebar

**Top block — Latest Release Summary** (always visible):
- DB version
- Scoring version
- Product count
- Generated timestamp
- Release artifact status: green "Artifacts ready" (DB + manifest + blobs exist) / yellow "Incomplete" (some artifacts missing) / red "No release found"
- Source: `export_manifest.json`
- Note: this is local file status only. Actual Supabase sync state is not checked in v1.

**Data Freshness block** (always visible, below release summary):
- Latest enriched timestamp (newest `enrichment_summary_*.json`)
- Latest scored timestamp (newest `scoring_summary_*.json`)
- Latest final DB timestamp (`export_manifest.generated_at`)
- Latest batch run timestamp (newest `batch_run_summary_*.txt`)
- Each line: relative time ("2 hours ago", "3 days ago") + absolute timestamp on hover

**Dataset filter** (dropdown):
- "All Datasets" (default)
- Auto-populated from discovered `output_*` directory names (e.g. "Thorne", "NOW", "Garden_of_Life")
- When selected: Health and Quality views scope to that dataset's reports only

**Warnings / Assumptions panel** (collapsed by default):
- "Showing latest discovered reports from `{scan_dir}`"
- "Release data from `{build_root}`"
- "Some sections may mix release-wide and dataset-scoped data"
- Lists any missing expected files

**Refresh controls**:
- Manual refresh button always visible in the sidebar
- Optional "Live mode" toggle enables timed auto-refresh for active monitoring sessions
- Refresh action clears Streamlit caches and reloads discovery metadata

**View navigation:**
1. Product Inspector (default)
2. Pipeline Health
3. Data Quality
4. Release Diff (phase 2 — greyed out in v1, shows "Coming soon")

---

## 4. View 1 — Product Inspector (Landing Page)

The primary view. Search for any product and see its full pipeline lineage.

### 4.1 Search

**Search input**: single text field at top, full width.
- Placeholder: "Search by DSLD ID, UPC, product name, or brand..."

**Progressive fallback search logic**:
1. If input is numeric-only or matches dsld_id pattern: exact `WHERE dsld_id = ?`
2. If input matches UPC pattern (10-14 digits): exact `WHERE upc_sku = ?`
3. If `products_fts` table exists: `WHERE products_fts MATCH ? LIMIT 50`
4. Fallback: `WHERE product_name LIKE '%?%' OR brand_name LIKE '%?%'`

This ensures the search works across different release DBs, even if FTS wasn't built.
Search input should be debounced by ~300ms to avoid query-per-keystroke load.

### 4.2 Results Table

Columns: dsld_id, product_name, brand_name, score_100_equivalent, grade, verdict, form_factor, supplement_type, product_status.

- Verdict column: color-coded text (green SAFE, yellow CAUTION, orange POOR, red UNSAFE/BLOCKED, grey NOT_SCORED)
- Sortable by any column
- Max 100 results displayed. If more: show "Showing 100 of X results. Refine your search."

Click a row to expand the drill-down below the table.

**Deep linking**:
- When a product is selected, update URL state with `?dsld_id=<id>`
- On app load, if `dsld_id` is present in query params, load that product directly
- Shared URLs should reproduce the exact product-inspector state without additional clicks

### 4.3 Product Drill-Down

**Header block**:
- Product name (bold, large)
- Brand name (muted)
- Verdict badge (colored pill)
- Grade label
- Score: large number with "/100" suffix, colored by threshold (green >=70, yellow 40-69, red <40)
- Percentile chip (if percentile_top_pct is not null): "Top X% in [category]"
- Form factor pill + supplement type pill
- Product status badge (if not active)

**Score Pillar Bars** (4 horizontal bars, side by side):
- Ingredient Quality: score/25
- Safety & Purity: score/30
- Evidence & Research: score/20
- Brand Trust: score/5
- Each bar colored by % of max: green >=80%, yellow 50-79%, red <50%

**Pros & Cons** (two columns):
- Left: "What Helped" — from `score_bonuses[]`. Each row: green dot + label + "+X pts" (from `score` field).
  Bonus fields: `{id, label, score, detail?}`. All bonuses have a `score` value.
- Right: "What Hurt" — from `score_penalties[]`. Each row: red dot + label + severity badge + reason text.
  Penalty fields vary by `id`:
    B0 (banned/recalled): `{id, label, reason, status}` — no numeric score
    B1 (harmful additive): `{id, label, severity, reason}` — no numeric score
    B2 (allergen): `{id, label, severity, presence}` — no numeric score
    B5 (proprietary blend): `{id, label, score, blend_count}` — HAS numeric score
    B6 (disease claims): `{id, label, score}` — HAS numeric score
    B7 (dose safety): `{id, label, severity, reason}` — no numeric score
    violation: `{id, label, score}` — HAS numeric score
  Display: show "-X pts" when `score` field exists, otherwise show severity badge + reason.
- Source: detail blob. If detail blob not available: "Detail blob not cached — bonuses/penalties unavailable"

**Active Ingredients Table**:
- Columns: name, standard_name, bio_score, form, dosage, dosage_unit, category, is_mapped, is_harmful, is_banned, is_allergen
- Bio score cell colored: green >=14, blue 10-13, grey <10
- Harmful/banned/allergen flags shown as red/orange/yellow dots

**Inactive Ingredients Table**:
- Columns: name, category, is_additive, is_harmful, mechanism_of_harm (if harmful), common_uses
- Harmful rows highlighted with light red background

**Warnings Table**:
- Columns: type, severity, title, detail
- Severity colored: red (critical/avoid/contraindicated), orange (high/caution), yellow (moderate/monitor), grey (info/low)
- Expandable detail text per row

**Interaction Summary** (if interaction_summary present in detail blob):
- Conditions flagged: table with condition_id, label, highest_severity, ingredients list, actions
- Drug classes flagged: same structure

**Source Paths** (collapsed expander, best-effort):
- Absolute paths displayed as copyable text (not clickable OS links).
- **Detail blob**: `{build_root}/detail_blobs/{dsld_id}.json` — always resolvable if build root exists.
- **Enriched/Scored files**: best-effort resolution. The loader searches `{scan_dir}/output_*/enriched/{dsld_id}.json` and `{scan_dir}/output_*/scored/{dsld_id}.json` by globbing. If found: show path. If not found: show "Source file not found — may be from a different run or naming convention."
- This approach handles brand-based dirs (`output_Thorne_enriched`), form-based dirs, dated delta runs, and manual import runs without brittle path assumptions.
- Copy button next to each resolved path.

**Raw JSON** (collapsed expander):
- Full detail blob JSON rendered in a code block
- Full products_core row as JSON

### 4.4 Score Trace Lite

Add a collapsed section below the pillar bars:

- **Ingredient Quality trace**
- **Safety & Purity trace**
- **Evidence & Research trace**
- **Brand Trust trace**

Each trace block should show:
- exported section total
- key subsection values when present in `section_breakdown`
- bonuses from `score_bonuses`
- penalties from `score_penalties`

Example:

```text
Ingredient Quality
  Bioavailability / forms / delivery: 12.4
  Category bonuses: +2.0
  Final exported total: 14.4 / 25
```

Important:
- this is an **explainability layer built from exported artifacts**
- it must not imply a mathematically exact replay of every scorer branch unless the scorer later emits a formal trace payload

---

## 5. View 2 — Pipeline Health

### 5.1 Latest Release Card

KPI card row (4 cards):
- **DB Version**: `export_manifest.db_version`
- **Scoring Version**: `export_manifest.scoring_version`
- **Product Count**: `export_manifest.product_count`
- **Generated**: `export_manifest.generated_at` (relative + absolute)

Below: checksum (monospace, truncated with copy button), min_app_version.

### 5.2 Release Artifact Status

Local file presence check only — does not query Supabase.

- Check for: `pharmaguide_core.db`, `export_manifest.json`, `detail_index.json`, `detail_blobs/` directory
- All present: green "Artifacts ready"
- Some missing: yellow "Incomplete" + list of missing files
- None found: red "No release found at `{build_root}`"
- If `sync_failures_*.json` exists: orange warning card with error count and failed blob list

### 5.3 Latest Batch Run

Source: newest `batch_run_summary_*.txt` file.

Note: this file is a raw log (~10K lines), not structured JSON. The loader must parse it to extract:
- Header block (lines 1-8): dataset root, scripts dir, stages list, target dataset names (comma-separated)
- Timestamp: parsed from filename (`batch_run_summary_YYYYMMDD_HHMMSS.txt`)
- Per-dataset status: scan log lines for `Pipeline stopped: Coverage gate failed` or `ENRICHMENT COMPLETE` / `SCORING COMPLETE` patterns per dataset
- Error lines: grep for `ERROR` log level entries

Display:
- Batch timestamp + target datasets list
- Per-dataset row: dataset name, status (green pass / red fail badge), last stage reached
- Error summary: count of ERROR-level lines, expandable to show them
- Overall: "X/Y datasets completed all stages"

### 5.3A Pipeline Stage Visualization

For each dataset in the latest batch, render a simple stage rail:

```text
CLEAN -> ENRICH -> SCORE -> EXPORT
  ✓        ✓        ✗        -
```

Status inference comes from parsed batch summary and processing-state artifacts:
- completed stage markers
- first failure point
- "not reached" stages after failure

This is an operator aid, not a source of truth beyond the logs being parsed.

### 5.4 Processing State

Source: `logs/processing_state.json`

- Started / last updated timestamps
- Progress: "Batch X/Y completed"
- Can resume: yes/no badge
- Error list (if any)

### 5.5 Missing Artifact Detector

For each discovered `output_*` directory, check for expected files:
- `reports/enrichment_summary_*.json` — present/missing
- `reports/scoring_summary_*.json` — present/missing
- `reports/coverage_report_*.json` — present/missing
- Scored output directory — present/missing

Table with dataset name, and red/green status per artifact type. Red rows sorted to top.

### 5.6 Batch History

Table of all discovered `batch_run_summary_*.txt` files:
- Filename, date (parsed from filename), file size
- Sorted newest first
- Click to show file contents in an expander

---

## 6. View 3 — Data Quality

### 6.1 Not-Scored Queue

Source: `products_core` SQLite table, `WHERE verdict = 'NOT_SCORED'`.

- KPI card: total count of NOT_SCORED products
- Table: dsld_id, product_name, brand_name, mapped_coverage
- Sorted by brand (group similar products)
- This is the highest-value QA list in the dashboard

### 6.2 Unmapped Hotspot Table

Source: aggregated from all `enrichment_summary_*.json` files, `unmapped_ingredients` field.

- Table: ingredient name, total occurrence count, brands affected (comma-separated list), first seen in
- Sorted by occurrence count descending
- Top 50 shown by default, expandable
- Scoped to selected dataset if filter is active

### 6.3 Fallback Hotspot Tables

**Form Fallbacks** (source: `form_fallback_audit_report.json`):

The raw report splits entries into `action_needed_differs` and `likely_ok_same` arrays with fields like `ingredient_label`, `unmapped_form_text`, `fallback_form`, `occurrence_count`. The loader normalizes both arrays into one flat table with a `forms_differ` boolean column.

- Normalized table columns: ingredient_label, unmapped_form_text, fallback_form, forms_differ (yes/no), occurrence_count, source_array (action_needed / likely_ok)
- Default filter: "Show only mismatches" toggle (forms_differ = true)
- Sorted by occurrence_count descending

**Parent Fallbacks** (source: `parent_fallback_report.json`):
- Table: ingredient_raw, ingredient_normalized, canonical_id, fallback_form_name, match_type, tier, occurrence_count
- Sorted by count descending

### 6.4 Verdict Distribution

Source: `products_core` SQLite or `export_audit_report.json`.

- Bar chart (Plotly): SAFE, CAUTION, POOR, UNSAFE, BLOCKED, NOT_SCORED
- Colors match app palette (green, yellow, orange, red, dark red, grey)

### 6.5 Score Distribution

Source: `products_core` SQLite.

- Histogram (Plotly) of `score_100_equivalent` values, 10-point bins
- Vertical lines at grade thresholds (90, 80, 70, 60, 50, 32)
- Exclude NULL scores (NOT_SCORED products)
- Mean and median displayed as annotations

### 6.6 Coverage Gate

Source: latest `coverage_report_*.json` per dataset.

- Per-dataset row (or single dataset if filter active):
  - 6 horizontal bars: ingredients, additives, allergens, manufacturer, delivery, claims
  - Threshold line overlay (99.5%, 98%, 95%, 90% depending on domain)
  - Bar color: green if above threshold, red if below
- Products blocked count
- Average coverage %

### 6.7 Safety Summary

Source: `export_audit_report.json`.

KPI card row:
- Banned substances: count (red if >0)
- Recalled ingredients: count (red if >0)
- Harmful additives: count
- Allergen risks: count
- Watchlist hits: count
- High-risk hits: count

### 6.8 Config Snapshot

Source: `scoring_config.json`.

- Scoring version
- Section maxima: A=25, B=30, C=20, D=5
- Verdict thresholds: POOR cutoff, grade scale
- Key tunable parameters: bio_score_weight, harmful_additive_penalties, omega-3 dose bands
- Displayed as a clean key-value table, not raw JSON

### 6.9 Data Dictionary Tooltips

The dashboard should centralize operator-facing field definitions in one helper:

```python
DATA_DICT = {
    "bio_score": "Ingredient bioavailability score from the quality map/exported ingredient detail.",
    "mapped_coverage": "Fraction of active ingredients mapped to supported reference data.",
    "blocking_reason": "Primary reason the product was marked BLOCKED/UNSAFE/NOT_SCORED.",
}
```

Use these definitions as `help=` tooltips on:
- KPI cards
- table headers where supported
- section labels
- config snapshot fields

---

## 7. View 4 — Release Diff (Phase 2)

Designed now, built after views 1-3 are stable.

### 7.1 Comparison Setup

Two dropdowns:
- **Release A** (baseline): select from discovered scored output directories or release DBs
- **Release B** (candidate): same list, default to latest

"Compare" button triggers the diff.

### 7.2 Diff Output

**Summary cards**:
- Products in A / Products in B
- Products added / removed
- Products with score change
- Products with verdict change

**Score Shifts Table**:
- Columns: dsld_id, product_name, brand, score_A, score_B, delta, verdict_A, verdict_B
- Filter: "Show only delta > 3 pts" toggle
- Sorted by absolute delta descending
- Verdict changes highlighted with red background

**Verdict Changes Table** (filtered subset):
- Only products where verdict_A != verdict_B
- Columns: dsld_id, product_name, verdict_A → verdict_B, score_A → score_B

**New Warnings Summary**:
- Warnings present in B but not A, grouped by type
- Count per warning type

---

## 8. Components

Reusable Streamlit components shared across views.

### 8.1 Metric Card

```python
def metric_card(label: str, value: str | int, color: str = "default", delta: str = None):
    """Single KPI card. Use in st.columns() for card rows."""
```

Colors: green (good), yellow (warning), red (critical), grey (neutral), default (brand teal).

### 8.2 Score Breakdown

```python
def score_breakdown(ingredient: float, safety: float, evidence: float, brand: float):
    """4 horizontal bars showing pillar scores with max labels."""
```

### 8.3 Status Badge

```python
def status_badge(label: str, status: str):
    """Colored badge. status: 'pass' | 'fail' | 'warning' | 'info'."""
```

### 8.4 Data Table

```python
def data_table(df: pd.DataFrame, color_columns: dict = None, max_rows: int = 100):
    """Styled dataframe with optional column coloring and row limit."""
```

### 8.5 Data Dictionary Helper

```python
DATA_DICT: dict[str, str]

def field_help(key: str) -> str | None:
    """Return operator-facing help text for a field when defined."""
```

---

## 9. Data Loader Contract

`data_loader.py` exposes a single `DashboardData` object that all views read from.

```python
@dataclass
class DashboardData:
    # Release artifacts
    db_path: Path | None                    # pharmaguide_core.db
    db_conn: sqlite3.Connection | None      # open connection (read-only)
    export_manifest: dict | None            # export_manifest.json
    export_audit: dict | None               # export_audit_report.json
    detail_blobs_dir: Path | None           # detail_blobs/ directory

    # Dataset reports (keyed by dataset name)
    enrichment_summaries: dict[str, dict]   # latest per dataset
    scoring_summaries: dict[str, dict]      # latest per dataset
    coverage_reports: dict[str, dict]       # latest per dataset
    form_fallback_reports: dict[str, dict]  # per dataset
    parent_fallback_reports: dict[str, dict]# per dataset

    # Pipeline state
    processing_state: dict | None           # logs/processing_state.json
    scoring_config: dict | None             # config/scoring_config.json
    batch_run_files: list[Path]             # sorted newest first

    # Freshness timestamps
    latest_enriched_at: datetime | None
    latest_scored_at: datetime | None
    latest_export_at: datetime | None
    latest_batch_at: datetime | None

    # Discovery metadata
    scan_dir: Path
    build_root: Path
    dataset_root: Path | None
    discovered_datasets: list[str]          # ["Thorne", "NOW", ...]
    missing_artifacts: dict[str, list[str]] # {"Thorne": ["coverage_report"], ...}
    warnings: list[str]                     # loader warnings for sidebar display
    latest_batch_summary: dict | None       # parsed latest batch run summary
    release_artifact_status: dict[str, Any] # presence/health of DB, manifest, index, blob dir
```

**Caching**: `@st.cache_data` on JSON file reads, `@st.cache_resource` on SQLite connection. TTL: 5 minutes by default. Manual refresh clears caches immediately. Auto-refresh, when enabled, should reuse the same TTL rules instead of bypassing them.

**SQLite access**: opened with `sqlite3.connect(db_path, uri=True)` in read-only mode (`?mode=ro`). Never writes.

---

## 10. Dependencies

Dashboard-only dependencies. Install separately — NOT added to the pipeline's core `requirements.txt` or `requirements-dev.txt` to avoid bloating the pipeline environment:

```bash
pip install streamlit pandas plotly
```

Pinned versions for reproducibility (add to a `scripts/dashboard/requirements.txt`):
```
streamlit>=1.30,<2
pandas>=2.0,<3
plotly>=5.0,<6
```

No other dependencies. Uses stdlib `sqlite3`, `json`, `pathlib`, `datetime`, `glob`.

---

## 11. What Is NOT in v1

- No editing/writing to any data source
- No ingredient-wide search (needs enriched output index — phase 2)
- No Supabase remote status check (local artifact status only)
- No auth, hosting, or deployment
- No Release Diff view (designed above, built in phase 2)
- No open-in-editor/finder links (display copyable paths only)
- No visualization of every scoring sub-field (pillar totals + bonuses/penalties only)
- No mobile/responsive layout (desktop browser only)
- No synthetic confidence score in v1. A confidence layer is deferred until backed by formal pipeline/export signals instead of invented heuristics.
- No anomaly detection engine in v1. Defer until Release Diff and trace-lite are stable enough to reduce false positives.
- No separate Operator Mode / Analyst Mode in v1. Sidebar views already provide sufficient separation at this stage.

---

## 12. Build Phases

### Phase 1: Foundation + Inspector
- `config.py`: CLI args, defaults, path resolution
- `data_loader.py`: auto-discovery, JSON readers, SQLite connection, `DashboardData` dataclass
- `app.py`: sidebar layout (release summary, freshness, dataset filter, warnings, nav)
- `views/inspector.py`: search, results table, product drill-down
- Deep linking via query params
- Manual refresh button + optional live mode
- SQL-backed aggregations and capped FTS queries
- Components: `metric_cards.py`, `score_breakdown.py`, `product_header.py`, `data_table.py`, `data_dictionary.py`

### Phase 2: Health + Quality
- `views/health.py`: release card, batch run, stage visualization, processing state, missing artifacts, batch history
- `views/quality.py`: not-scored queue, unmapped hotspots, fallback hotspots, verdict/score distributions, coverage gate, safety summary, config snapshot
- Score trace-lite in Product Inspector
- Component: `status_badge.py`, `score_trace.py`

### Phase 3: Release Diff
- `views/diff.py`: comparison setup, score shifts, verdict changes, new warnings
- Requires loading two scored output directories and computing deltas

---

## 13. Success Criteria

The dashboard is useful when:
1. You can type a dsld_id and see why it got its score in under 5 seconds
2. You can see at a glance whether the last pipeline run succeeded
3. You can find the top unmapped ingredients across all brands in one table
4. You can spot NOT_SCORED products without running a SQL query
