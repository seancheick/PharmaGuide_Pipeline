# PharmaGuide Pipeline Operator Dashboard — Design Spec

> Version: 3.1.0 | Date: 2026-04-09
> Status: Updated after correction sprint implementation
> Stack: Python 3.13 + Streamlit + Pandas + Plotly
> Scope: Read-only internal operator dashboard, local-only, no auth

---

## 1. Purpose

An internal Streamlit dashboard that serves as PharmaGuide's **data observability + QA + release validation system**. Not just analytics — an operator control plane for the entire data engine.

Core capabilities:

1. **Inspect any product** from the final export, with best-effort links to enriched/scored source files when resolvable
2. **Check pipeline health**: did the last run succeed, what's the current release, are release artifacts ready, which stage failed
3. **Triage data quality**: unmapped ingredients, fallbacks, not-scored products, coverage gaps
4. **Explain scores**: show pillar totals plus a trace-lite of how the exported score was assembled from section breakdown, bonuses, and penalties
5. **Gate releases**: GO/NO-GO decision engine that blocks bad releases before they reach users
6. **Compare releases** (phase 2): score shifts, verdict changes, added/removed products
7. **Surface intelligence**: market insights, brand rankings, ingredient analytics, and scoring sensitivity that feed the app, AI layer, and content engine
8. **Detect drift**: automatic alerts when scores, safety signals, or coverage regress between builds

This is a read-only tool (except for the storage cleanup action, which requires operator confirmation). It never writes to the database, pipeline outputs, or Supabase. It reads existing JSON reports and SQLite files that the pipeline already produces.

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
  --scan-dir scripts/products/ \
  --build-root scripts/final_db_output/ \
  --dataset-root /Users/seancheick/Documents/DataSetDsld/
```

All args have sensible defaults so `streamlit run scripts/dashboard/app.py` works after installing dashboard dependencies (`pip install streamlit pandas plotly`). These are dev-only dependencies, not added to the pipeline's core `requirements.txt`.

### 2.3 CLI Arguments

| Arg | Default | Purpose |
|-----|---------|---------|
| `--scan-dir` | `scripts/products/` | Where to find `output_*` directories, `reports/`, `logs/`, and pipeline outputs |
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

**Implemented fallback discovery**:
- `output_*/cleaned/*.json`
- `output_*/errors/*_error.json`
- `output_*/unmapped/*.json`
- `logs/batch_*_log.txt`

The current workspace uses the fallback discovery paths heavily, so the loader supports both the ideal report layout and the real `output_*` / log structure present on disk.

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
2. Pipeline Health (includes Release Gate)
3. Data Quality
4. Pipeline Observability
5. Release Diff
6. Batch Run Comparison
7. Intelligence

All seven views are now wired in the app shell. Advanced sections are strongest when multiple builds and richer dataset artifacts are available, but they are no longer navigation stubs.

### 3.2 Implementation Notes (2026-04-09)

- The loader now provides a normalized `build_history` abstraction that powers release comparison, drift checks, and monitoring.
- Health, Quality, and Observability now consume shared loader metrics rather than recomputing release counts independently.
- The dashboard test suite now includes view smoke coverage and empty-export verification in addition to loader and graceful-degradation tests.

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

### 5.3 Release Gate (GO / NO-GO Decision Engine)

A prominent card at the top of Pipeline Health that turns the dashboard from visibility into a **decision engine**. This prevents bad releases from reaching users.

**Release Status Card**:

```text
Release Status: GO / NO-GO / BLOCKED

Reasons (when blocked):
- 142 enriched but not scored
- Coverage dropped to 93%
- 3 banned substances detected
- 12 export errors
```

**Blocking rules** (any triggers NO-GO):

| Condition | Threshold | Severity |
|-----------|-----------|----------|
| `enriched_only > 0` | 0 (in strict mode) | BLOCK |
| Coverage < threshold | configurable, default 95% | BLOCK |
| Error count > 0 | 0 | BLOCK |
| Banned substances detected | any new vs prior build | BLOCK |
| BLOCKED verdict count increased | any increase vs prior build | WARN |
| Build age > N days | configurable, default 7 | WARN |

**Display**:
- Large colored badge: green "GO" / red "BLOCKED" / yellow "REVIEW"
- Below: bullet list of all triggered conditions with severity
- "Override" button (requires typing "CONFIRM" — logged to audit trail)
- Source: `export_manifest.integrity`, `export_audit_report.json`, prior build manifest for delta checks

**Gate thresholds** are configurable via `dashboard_alerts.json` (same file as 7B.10 alerting rules).

### 5.4 Latest Batch Run

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

### 5.4A Pipeline Stage Visualization

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

### 5.5 Processing State

Source: `logs/processing_state.json`

- Started / last updated timestamps
- Progress: "Batch X/Y completed"
- Can resume: yes/no badge
- Error list (if any)

### 5.6 Missing Artifact Detector

For each discovered `output_*` directory, check for expected files:
- `reports/enrichment_summary_*.json` — present/missing
- `reports/scoring_summary_*.json` — present/missing
- `reports/coverage_report_*.json` — present/missing
- Scored output directory — present/missing

Table with dataset name, and red/green status per artifact type. Red rows sorted to top.

### 5.7 Batch History

Table of all discovered `batch_run_summary_*.txt` files:
- Filename, date (parsed from filename), file size
- Sorted newest first
- Click to show file contents in an expander

---

## 6. View 3 — Data Quality

### 6.1 Not-Scored Queue

Source: `products_core` SQLite table, `WHERE verdict = 'NOT_SCORED'`.

- KPI card: total count of NOT_SCORED products
- Table: dsld_id, product_name, brand_name, mapped_coverage, **not_scored_reason**
- Sorted by brand (group similar products)
- This is the highest-value QA list in the dashboard

**Root cause explanation per product** (saves hours of debugging):

Each NOT_SCORED product should display a reason derived from available data:

```text
NOT SCORED — Reason:
- Missing ingredient mapping (2 of 8 ingredients unmapped)
- Coverage below threshold (92% < 95% gate)
```

Reason inference logic (check in order):
1. If `mapped_coverage < coverage_threshold` → "Coverage below threshold (X% < Y%)"
2. If product has unmapped ingredients → "Missing ingredient mapping (N ingredients)"
3. If product failed enrichment → "Enrichment failure" (from enrichment summary errors)
4. If product has no scored output file → "Scoring stage not reached"
5. Fallback: "Reason unknown — check pipeline logs"

Source: cross-reference `coverage_report`, `enrichment_summary`, and `products_core` fields.

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

## 7B. View 5 — Pipeline Observability (Quality Control Panel)

This is the comprehensive data health dashboard. It surfaces pipeline integrity, product flow, safety signals, sync state, and build history in one place.

### 7B.1 Pipeline Integrity Summary

KPI cards sourced from `export_manifest.json`'s `integrity` block:

| Card | Value | Color Rule |
|------|-------|------------|
| Enriched Input Count | `integrity.enriched_input_count` | neutral |
| Scored Input Count | `integrity.scored_input_count` | neutral |
| Exported Count | `integrity.exported_count` | neutral |
| Skipped Count | `integrity.enriched_only + integrity.scored_only + integrity.errors` | yellow if >0 |
| Coverage % | `exported_count / enriched_input_count * 100` | green >=99%, yellow 95-99%, red <95% |
| Error Count | `integrity.errors` | red if >0, green if 0 |
| Strict Mode | `integrity.strict_mode` | green "ON" / yellow "OFF" |

### 7B.2 Product Flow Sankey

Plotly Sankey diagram showing how products flow through the pipeline:

- **Left node**: Total enriched products
- **Middle nodes**: Matched (present in both enriched + scored), Enriched-only, Scored-only
- **Right nodes**: Exported, Contract failures, Errors
- Color coding: green for the happy path (Enriched → Matched → Exported), red for any drop-off path
- **% loss labels on every edge** — operators need percentages more than raw counts:
  ```text
  Enriched → Matched: 98.2% (4,820 / 4,908)
  Matched → Exported: 95.6% (4,608 / 4,820)
  Total pipeline yield: 93.9%
  Total loss: 6.1% (300 products)
  ```
- Source: `integrity` block values + `export_audit_report.json`

If Plotly Sankey is unavailable, degrade gracefully to a text-based flow summary table with the same percentage labels.

### 7B.3 Enriched vs Scored Mismatch Tracker

Two tables and a trend chart:

**Enriched-only products** (products enriched but never scored — source: audit report):
- Columns: dsld_id, product_name, brand_name, reason_not_scored
- Sorted by brand

**Scored-only products** (products scored but no matching enriched file):
- Columns: dsld_id, reason_not_enriched
- These are anomalies — flag in orange

**Historical mismatch trend** (line chart):
- X-axis: batch run date (from `batch_run_summary_*.txt` filenames)
- Y-axis: enriched-only count, scored-only count, error count
- Shows whether mismatch rate is improving or degrading over time

### 7B.4 Export Error Drill-Down

The `integrity.errors` list contains `{dsld_id, error}` pairs, but the dashboard needs a dedicated view to browse them — not just a count.

- Table: dsld_id, product_name, brand_name, error_message, stage (inferred from error text)
- Sortable and filterable by error type
- Click any row to jump to Product Inspector for that dsld_id
- Error classification: group errors by pattern (e.g., "missing field", "contract violation", "scoring exception")
- KPI card: "X errors out of Y products (Z%)"

Source: `export_manifest.integrity.errors` array + cross-reference `products_core` for product names.

### 7B.5 Top Failure Reasons Aggregation

Aggregates WHY products fail at scale — drives pipeline improvements.

**Failure Breakdown Table**:

| Reason | Count | % of Total Failures |
|--------|-------|---------------------|
| Missing ingredient mapping | 120 | 42% |
| Coverage gate fail | 45 | 16% |
| Scoring exception | 12 | 4% |
| Unknown ingredient | 8 | 3% |
| Enrichment timeout | 5 | 2% |

- Source: cross-reference NOT_SCORED reasons (6.1), `integrity.errors`, enrichment summary `unmapped_ingredients`, coverage report failures
- Bar chart visualization (horizontal bars, sorted by count)
- Trend: if prior build data is available, show count delta ("+12 vs last build" / "-5 vs last build")
- This table directly informs which pipeline improvements to prioritize

### 7B.6 Safety & Regulatory Dashboard

Real-time safety signal counts from the `integrity` block and `products_core`:

| Signal | Source | Drill-down |
|--------|--------|-----------|
| Banned substances count | `integrity` / `export_audit` | Link to product inspector filtered by `has_banned_substance = true` |
| Recalled ingredients count | `integrity` / `export_audit` | Link to product inspector filtered by `has_recalled_ingredient = true` |
| BLOCKED verdict count | `products_core` | List of affected products |
| UNSAFE verdict count | `products_core` | List of affected products |
| Harmful additives flagged | `export_audit` | Count + drill-down |
| Allergen risks flagged | `export_audit` | Count + drill-down |
| Watchlist hits count | `export_audit` | Count + drill-down |

All counts are clickable — clicking a count opens the Product Inspector pre-filtered to that cohort.

### 7B.7 Supabase Sync Status

Checks remote Supabase state. Requires credentials from `.env` to be present; if not available, shows a graceful "Credentials not configured — showing local status only" message.

| Field | Source | Status Color |
|-------|--------|-------------|
| Remote manifest version | Fetched from Supabase storage | green if matches local, yellow if outdated, red if never synced |
| Local manifest version | `export_manifest.db_version` | — |
| Last sync timestamp | `export_manifest.generated_at` vs remote | — |
| Storage bucket usage | Supabase Storage API (total size, file count) | yellow if >80% quota |
| Old version count | Versions in bucket minus current | yellow if >3 |
| Sync failure history | `sync_failures_*.json` files | red if any failures in last 7 days |

Status summary badge: **Synced** (green) / **Outdated** (yellow) / **Never synced** (red).

Graceful degradation: if Supabase credentials are absent or the request times out (>5s), show last-known local state with a "Remote check unavailable" warning.

**Client adoption tracking** (phase 3 — requires app telemetry):
- "% users on latest DB version" — sync success does not mean users updated
- Requires the Flutter app to report its local DB version to Supabase (via an analytics event or metadata table)
- Until app telemetry is wired: show placeholder "Client adoption: awaiting app telemetry" with a link to the implementation ticket

### 7B.8 Storage Health Monitor

Summarizes versioned storage on disk for the build root:

- Total versioned directories in `--build-root` (or `--dataset-root/builds/`)
- Size per version directory (sorted newest first)
- Orphaned blob estimate: blobs in `detail_blobs/` not referenced by current `detail_index.json`
- Cleanup recommendation: "X versions can be cleaned up, saving ~Y MB" (any version that is not the current release and older than 30 days)

**Safe cleanup flow** (no accidental deletion):
1. Click "Preview Cleanup" → runs dry-run first
2. Shows: files to delete, size to be freed, versions affected
3. Operator reviews the list
4. Click "Confirm Cleanup" to execute (`python3 scripts/cleanup_old_versions.py --execute`)
5. Never a single "one-click delete" — always preview → confirm

Note: cleanup trigger is the only write action in the dashboard. It only deletes old build artifacts, never pipeline inputs or Supabase data.

### 7B.9 Score Distribution Analytics

Enhanced version of the existing 6.5 histogram. Adds:

- Score histogram (10-point bins) with grade threshold overlay (90, 80, 70, 60, 50, 32)
- **Per-brand score distribution**: box plots for the top 10 brands by product count
- **Score shift heatmap**: if two or more builds are available, show a grid of score-range transitions (from build N-1 to build N)
- **Percentile distribution by category**: bar chart showing median score per supplement type
- **Top improvers / top decliners**: table of products with the largest score delta vs previous build (if prior build manifest is discoverable)

Source: `products_core` SQLite + cross-build comparison when prior `export_manifest.json` history is available.

**Score vs Coverage correlation** (reveals scoring bias and data gaps):
- Scatter plot: X = `mapped_coverage`, Y = `score_100_equivalent`
- Reveals whether low coverage systematically produces low scores
- Helps identify if the scoring system unfairly penalizes products with missing data vs genuinely poor products
- Color dots by verdict for additional insight

### 7B.10 Ingredient Coverage Health

- Total unique ingredients across all products (from `products_core` ingredient arrays or enrichment summaries)
- Mapped vs unmapped ratio (pie chart)
- Coverage trend over time (line chart, X = batch run date, Y = mapped %)
- Top 20 unmapped ingredients by frequency (table: name, occurrence count, affected brands)
- Ingredients with the lowest `bio_score` across all products — quality improvement candidates
- IQM coverage gaps: ingredients present in products that have no entry in `scripts/data/ingredient_quality_map.json`

Source: enrichment summaries + `ingredient_quality_map.json` key set.

### 7B.11 Build History Timeline

- Timeline visualization of all discovered builds (from `export_manifest.json` history files or versioned build dirs)
- Each build node shows: version label, product count, coverage %, error count, generated_at timestamp
- Click any node to open a comparison between that build and the current release (links to Release Diff view, View 4)
- Trend lines overlay: product count growth, coverage % improvement, error count reduction
- If only one build exists: show a single node with a "No prior builds to compare" note

### 7B.12 Alerting Rules (Configurable)

Operator-defined thresholds stored in `scripts/dashboard/dashboard_alerts.json`. Alerts render as colored banners at the top of the observability view.

| Condition | Default Threshold | Banner Color |
|-----------|-------------------|-------------|
| Coverage drops below X% | 95% | Red |
| Error count exceeds N | 0 | Red |
| Banned substance count increases vs prior build | any increase | Red |
| Unmapped ingredients exceed N | 100 | Yellow |
| Build age exceeds N days | 7 days | Yellow |
| Supabase out of sync for N+ hours | 24 hours | Yellow |

All thresholds are configurable. The `dashboard_alerts.json` schema:

```json
{
  "coverage_min_pct": 95,
  "max_errors": 0,
  "ban_increase_alert": true,
  "max_unmapped": 100,
  "max_build_age_days": 7,
  "max_sync_lag_hours": 24
}
```

If `dashboard_alerts.json` does not exist, defaults are used and a one-time notice is shown: "Using default alert thresholds. Create `scripts/dashboard/dashboard_alerts.json` to customize."

### 7B.13 Drift Detection (Automatic Regression Alerts)

Automatic alerts when key metrics regress between builds. This is how you catch regressions instantly without manually comparing builds.

**Drift alerts** (rendered as colored banners at top of observability view):

```text
⚠️ ALERT: Average score dropped by 6.2 pts vs last build (68.4 → 62.2)
⚠️ ALERT: SAFE products decreased by 18% (2,400 → 1,968)
⚠️ ALERT: Banned substance count increased by 3 (was 12, now 15)
⚠️ ALERT: Coverage dropped from 98.1% to 94.3%
```

**Drift metrics tracked** (all require prior build manifest for comparison):

| Metric | Alert Condition | Severity |
|--------|----------------|----------|
| Average score | Drops > 3 pts | Red |
| SAFE verdict count | Decreases > 5% | Red |
| Banned/recalled count | Any increase | Red |
| Coverage % | Drops > 1% | Red |
| Error count | Any increase | Yellow |
| Unmapped ingredient count | Increases > 10% | Yellow |
| NOT_SCORED count | Increases > 10% | Yellow |

- If no prior build exists: show "Drift detection requires 2+ builds — no prior build found"
- Source: current `export_manifest.json` vs most recent prior `export_manifest.json` (discovered from versioned build dirs or build history)
- Drift thresholds are configurable in `dashboard_alerts.json`

### 7B.14 Pipeline Bottleneck Analyzer

Shows where time is spent in each pipeline stage — helps optimize and scale.

```text
CLEAN:   2 min   ██░░░░░░░░░░░░░░
ENRICH: 18 min   ████████████████  ⚠️ bottleneck
SCORE:   4 min   ████░░░░░░░░░░░░
EXPORT:  1 min   █░░░░░░░░░░░░░░░
```

- Source: parse timestamps from batch run summary log (stage start/end markers)
- Horizontal bar chart with time labels
- Highlight the longest stage with a "bottleneck" badge
- If timestamps aren't parseable from logs: show "Timing data unavailable — add stage timestamps to batch runner for bottleneck analysis"
- History: if multiple batch runs are available, show stage duration trends over time

### 7B.15 Data Completeness Score

Not a confidence score (that's deferred) — this is honest **data completeness** per product.

```text
Product Data Completeness: 92%

Breakdown:
- Ingredients mapped: 100% ✓
- Manufacturer data: missing ✗
- Clinical evidence: partial (2 of 5 ingredients)
- Allergen screening: complete ✓
- Dosage info: complete ✓
```

**Aggregate completeness** (KPI card row on observability view):
- Average data completeness across all products
- Distribution histogram (how many products at 100%, 90-99%, 80-89%, etc.)
- Products with <80% completeness: table with dsld_id, product_name, missing fields

**Per-product completeness** (shown in Product Inspector drill-down):
- Completeness % based on: ingredients mapped, manufacturer present, clinical evidence count, allergen screening done, dosage extracted, form factor identified
- Missing fields highlighted in red

Source: `products_core` fields + detail blob field presence checks.

### 7B.16 Edge Case / Outlier Detector

Automatically catches weird scoring outcomes that could be bugs, scoring inconsistencies, or trust breakers.

**Outlier rules**:

| Pattern | What It Catches | Severity |
|---------|----------------|----------|
| Score ≥ 80 AND has harmful additive | High score despite safety flag | Red |
| Score ≤ 40 AND zero penalties | Low score with no clear reason | Orange |
| SAFE verdict AND has high-risk ingredient | Verdict may not match content | Red |
| Score delta > 20 pts vs prior build | Suspicious large swing | Yellow |
| BLOCKED verdict but score > 60 | Blocking reason may be wrong | Orange |
| Bio_score = 0 for mapped ingredient | Quality map data may be incomplete | Yellow |

- Table: dsld_id, product_name, outlier_type, details, severity
- Click any row to jump to Product Inspector
- KPI card: "X outliers detected across Y products"
- Source: `products_core` SQL queries + detail blob field checks

### 7B.17 Trend Over Time (Long-Term Health)

Shows system improvement, data quality growth, and regression detection across all builds.

**A. Average Score Trend**:
- Line chart: X = build date, Y = average `score_100_equivalent`
- Shows whether the pipeline is producing better scores over time

**B. Coverage Trend**:
- Line chart: X = build date, Y = coverage %
- Shows whether data completeness is improving

**C. Safety Issues Trend**:
- Line chart: X = build date, Y = banned count, recalled count, harmful additive count
- Shows whether safety detection is catching more or fewer issues

**D. Verdict Distribution Trend**:
- Stacked area chart: X = build date, Y = count per verdict (SAFE, CAUTION, POOR, UNSAFE, BLOCKED, NOT_SCORED)
- Shows how the product health landscape evolves

Source: requires `export_manifest.json` + `export_audit_report.json` from multiple builds. Stored in versioned build directories or a lightweight `build_history.json` cache.

---

## 7C. View 6 — Intelligence Dashboard (Phase 3)

Strategic analytics that transform internal data into competitive advantage. These feed the app, AI layer, and content engine.

### 7C.1 Market Intelligence — Top Products

**A. Top Products by Category**:

```text
Omega-3
1. Brand X — Score: 92 — SAFE
2. Brand Y — Score: 88 — SAFE

Multivitamins
1. Brand A — Score: 85 — SAFE
2. Brand B — Score: 82 — SAFE
```

- Source: `products_core` grouped by `supplement_type`, sorted by `score_100_equivalent` DESC
- Top 10 per category, expandable

**B. Top Products by Ingredient**:

```text
Magnesium (all forms)
1. Magnesium Glycinate — Brand A — 90
2. Magnesium Threonate — Brand B — 87
```

- Source: `products_core` ingredient arrays, grouped by primary active ingredient
- Top 10 per ingredient

**C. Best Form per Ingredient** (high value):

```text
Magnesium:
- Glycinate → avg score: 84 (120 products)
- Threonate → avg score: 78 (45 products)
- Citrate → avg score: 62 (200 products)
- Oxide → avg score: 42 (310 products)
```

- Source: cross-reference ingredient form data with product scores
- Validates the scoring system (better forms should score higher)
- Becomes future user-facing content

**D. Why Top Products Rank High** (per-product explainer):

```text
Top Omega-3 Product: Brand X Ultra Omega
Why it ranks high:
  + High EPA/DHA dose (1200mg combined)
  + Triglyceride form (+bioavailability)
  + Third-party tested (NSF certified)
  - Minor additive penalty (-2 pts)
```

- Source: detail blob `score_bonuses` and `score_penalties` for top-ranked products
- This is the bridge from internal scoring to user-facing explanations

### 7C.2 Ingredient Intelligence Dashboard

Ingredient-level analytics across the entire product catalog.

**A. Most Used Ingredients**:
- Table: ingredient name, product count, average bio_score
- Sorted by product count descending
- Top 50, expandable

**B. Lowest Quality Ingredients** (improvement candidates):
- Table: ingredient name, form, average bio_score, product count
- Sorted by bio_score ascending
- Highlights ingredients where form upgrades would improve scores

**C. High-Risk Ingredients**:
- Table: ingredient name, risk_flags (banned/recalled/watchlist/harmful), product count, severity
- Sorted by product count descending
- Flags ingredients that appear in many products despite safety concerns

**D. Ingredient-Level Search** (phase 2 prerequisite — #1 operator request):

Search across ALL products by ingredient name:
- "Does any product contain Yohimbine?" → list of products with that ingredient
- "Which products have Magnesium Glycinate?" → filtered product list with scores
- Requires building an ingredient index from enriched output or `products_core` ingredient arrays
- Search: `WHERE ingredient_name LIKE '%?%'` across the ingredient arrays (may need a denormalized ingredient table)

Source: `products_core` ingredient arrays, enrichment summaries, `ingredient_quality_map.json`.

### 7C.3 Brand Intelligence

**A. Brand Leaderboard**:

```text
Top Brands (avg score across all products)
1. Thorne — avg: 87 — 45 products — SAFE: 93%
2. Pure Encapsulations — avg: 85 — 62 products — SAFE: 89%
3. NOW Foods — avg: 72 — 180 products — SAFE: 71%
```

- Source: `products_core` grouped by `brand_name`, aggregated
- Sortable by avg score, product count, or SAFE %

**B. Worst Brands**:
- Same table, sorted ascending by avg score
- Highlights brands with high additive penalties or violation flags

**C. Brand Consistency Score**:

```text
Thorne:
  Avg score: 87 | Std dev: 4.2 | Variance: LOW (consistent quality)

Garden of Life:
  Avg score: 70 | Std dev: 18.5 | Variance: HIGH (inconsistent)
```

- Low variance = brand is consistently good (or bad)
- High variance = brand quality depends heavily on the specific product
- Source: standard deviation of `score_100_equivalent` per brand

### 7C.4 Scoring Sensitivity — What Moves Scores

Impact analysis: which scoring factors have the biggest effect?

**Top positive score drivers** (across all products):

| Factor | Avg Impact | Products Affected |
|--------|-----------|-------------------|
| High bioavailability forms | +8 avg | 2,400 |
| Third-party testing | +6 avg | 1,800 |
| Clinical evidence backing | +5 avg | 1,200 |
| Synergy cluster bonus | +3 avg | 800 |

**Top negative score drivers**:

| Factor | Avg Impact | Products Affected |
|--------|-----------|-------------------|
| Harmful additives | -10 avg | 3,100 |
| Proprietary blends | -6 avg | 1,500 |
| Manufacturer violations | -4 avg | 600 |
| Disease claims | -3 avg | 400 |

- Source: aggregate `score_bonuses` and `score_penalties` across all detail blobs
- Reveals if the scoring system is balanced or if something is overweighted
- Bar chart visualization with positive (green, right) and negative (red, left) bars

### 7C.5 User Impact Simulation (Phase 3 — Requires Personalization Logic)

Internal simulation of how personalization filters affect the product catalog.

```text
If user has diabetes:
  → 12% of products become CAUTION/UNSAFE (148 products)
  → 3 currently SAFE products would be flagged

If user avoids allergens (gluten-free):
  → 18% filtered out (220 products)
  → Top remaining: Brand X, Brand Y

If user takes blood thinners:
  → 8% get interaction warnings (98 products)
```

- Source: `products_core` warnings + interaction_summary data in detail blobs
- Prepares the AI personalization layer
- Validates that personalization logic doesn't over-filter or under-filter
- Deferred until interaction/condition data is stable in the export

---

## 7D. View 7 — Batch Run Comparison (Phase 2)

Compares batch runs **within the same release** to catch regressions during iterative pipeline improvements. This is distinct from Release Diff (View 4) which compares different releases.

### 7D.1 Comparison Setup

Two dropdowns:
- **Run A** (baseline): select from discovered `batch_run_summary_*.txt` files
- **Run B** (candidate): same list, default to latest

"Compare Runs" button triggers the diff.

### 7D.2 Run Comparison Output

**Summary cards**:
- Datasets processed in A / in B
- Datasets that changed status (pass → fail or fail → pass)
- Error count delta
- Stage completion delta

**Per-dataset comparison table**:
- Columns: dataset_name, status_A, status_B, last_stage_A, last_stage_B, error_count_A, error_count_B
- Highlight rows where status changed
- Sorted with regressions (pass → fail) at top

**Error diff**:
- New errors in B not present in A
- Errors resolved in B that were present in A

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

    # Pipeline integrity (from manifest)
    integrity_data: dict | None             # export_manifest.integrity block

    # Supabase sync state (optional, requires credentials)
    remote_manifest: dict | None            # fetched from Supabase if credentials available
    sync_failures: list[dict]               # from sync_failures_*.json files
    storage_health: dict | None             # bucket stats if available
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

- No editing/writing to any data source (except storage cleanup with confirmation)
- No ingredient-wide search (needs enriched output index — phase 2, highest priority)
- No auth, hosting, or deployment
- No Release Diff view (designed above, built in phase 2)
- No Batch Run Comparison (designed above, built in phase 2)
- No open-in-editor/finder links (display copyable paths only)
- No visualization of every scoring sub-field (pillar totals + bonuses/penalties only)
- No mobile/responsive layout (desktop browser only)
- No synthetic confidence score in v1. Data completeness (7B.15) replaces this with honest field-presence checks instead of invented heuristics.
- No outlier detection engine in v1. Designed in 7B.16 — defer until Release Diff and trace-lite are stable enough to reduce false positives.
- No Intelligence Dashboard (View 6) in v1. Designed in 7C — deferred to phase 5 after observability is stable.
- No User Impact Simulation in v1. Requires personalization logic to be stable in the export.
- No client adoption tracking in v1. Requires Flutter app telemetry (DB version reporting).
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
- `views/health.py`: release card, **release gate (GO/NO-GO)**, batch run, stage visualization, processing state, missing artifacts, batch history
- `views/quality.py`: not-scored queue **(with root cause reasons)**, unmapped hotspots, fallback hotspots, verdict/score distributions, coverage gate, safety summary, config snapshot
- Score trace-lite in Product Inspector
- Data completeness score in Product Inspector drill-down
- Component: `status_badge.py`, `score_trace.py`

### Phase 3: Release Diff + Batch Run Comparison
- `views/diff.py`: release comparison setup, score shifts, verdict changes, new warnings
- `views/batch_diff.py`: batch run comparison within same release (7D)
- Ingredient-level search (cross-product ingredient index)
- Requires loading two scored output directories and computing deltas

### Phase 4: Pipeline Observability
- `views/observability.py`: integrity summary, product flow sankey **(with % loss labels)**, mismatch tracker, **export error drill-down**, **top failure reasons**, safety dashboard, sync status, storage health **(with safe cleanup flow)**, score distribution analytics **(with score vs coverage correlation)**, ingredient coverage health, build history timeline, alerting rules, **drift detection**, **pipeline bottleneck analyzer**, **outlier detector**, **trend over time**
- Components: `sankey_chart.py`, `alert_banner.py`, `timeline.py`, `outlier_table.py`
- Requires: `export_manifest.json` integrity block for most panels; Supabase client access for sync status (optional — graceful degradation if credentials absent)

### Phase 5: Intelligence Dashboard
- `views/intelligence.py`: market intelligence (top products, best forms, why-top explainer), ingredient intelligence (most used, lowest quality, high-risk, ingredient search), brand intelligence (leaderboard, consistency scores), scoring sensitivity (impact analysis)
- Components: `leaderboard.py`, `form_comparison.py`
- Source: aggregations from `products_core` + detail blobs
- This view bridges internal data → user-facing content, AI answers, and competitive intelligence

### Phase 6: User Impact Simulation + Client Adoption
- User impact simulation (requires stable personalization/interaction data in export)
- Client adoption tracking (requires Flutter app DB version telemetry)
- These are deferred until app-side telemetry is wired

---

## 13. Success Criteria

The dashboard is useful when:
1. You can type a dsld_id and see why it got its score in under 5 seconds
2. You can see at a glance whether the last pipeline run succeeded
3. You can find the top unmapped ingredients across all brands in one table
4. You can spot NOT_SCORED products **and why they weren't scored** without running a SQL query
5. You can see at a glance how many products were lost between enrichment and export **with exact % at each stage**
6. You can track Supabase sync freshness without logging into the Supabase dashboard
7. You get visual alerts when data quality drops below thresholds
8. You can compare any two builds and see exactly what changed
9. **A bad release is automatically blocked** — the Release Gate shows GO/NO-GO before any sync
10. **You see drift alerts instantly** when scores, safety signals, or coverage regress between builds
11. You can browse individual export errors (not just a count) and see which products failed and why
12. You can see the top failure reasons driving pipeline losses and prioritize fixes
13. You can identify scoring outliers (high score + safety flag, low score + no penalties)
14. You can answer "what's the best magnesium supplement?" from internal data
15. You can see which brands are consistently high-quality vs inconsistent
16. You can search for any ingredient across all products (phase 2)
17. You can compare batch runs within the same release to catch iterative regressions (phase 2)
