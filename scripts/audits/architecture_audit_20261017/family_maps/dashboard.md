# Family map — scripts/dashboard/ (Level 1)

Source: listing agent (sonnet, read-only, 30 tool calls) at `5fb2be1ca`. Facts here are Level-1
evidence; any line AUDIT.md relies on is re-verified against source by the main audit and cited
with its command in EVIDENCE_LEDGER.md.

Conventions: paths relative to `scripts/`; LOC is `wc -l`; 35 `.py` files, 8,308 LOC. "Outside" means importers outside `scripts/dashboard` in `scripts/*.py`, `scripts/**/*.py` (excl. tests/audits), `*.sh`, `.claude/skills/**`, `.github/**` — none found for every file. No dashboard file imports any top-level `scripts/` production module (stdlib, streamlit, pandas, plotly, `scripts.dashboard.*` only). No Supabase reads: `DashboardData.remote_manifest` is declared (`data_loader.py:78`) and read in `observability.py:460-470` but never assigned. `DB` = `scripts/dist/pharmaguide_core.db`; "via loader" = data from `data_loader.load_dashboard_data`.

| file | LOC | kind | purpose | imported by (in dashboard; outside) | reads | core imports |
|---|---|---|---|---|---|---|
| dashboard/app.py | 188 | entry point (streamlit) | `_render_current_view` dispatches 13 views | 0; none (launched via `streamlit run`) | via loader | none |
| dashboard/app_shell.py | 23 | module | `build_initial_shell_state` | 1: app.py | none | none |
| dashboard/capture_screenshots.py | 113 | CLI | headless screenshots of each main view | 0 | running dashboard at 127.0.0.1:8599; writes docs/plans/dashboard-screenshots | none |
| dashboard/components/__init__.py | 27 | module | `_safe_columns`, `_safe_tabs`; re-exports 3 components | 6 | none | none |
| dashboard/components/command_center.py | 118 | module | `render_command_center` | 1 (+app.py via package) | via loader | none (lazy import of views.scoring_integrity :76) |
| dashboard/components/data_dictionary.py | 23 | module | `field_help` tooltip dict | 1: views/quality | none | none |
| dashboard/components/data_table.py | 87 | module | `arrow_safe`, `data_table` | 8 | none | none |
| dashboard/components/metric_cards.py | 51 | module | `metric_card`, `metric_row` | 9 | none | none |
| dashboard/components/page_frame.py | 333 | module | `inject_dashboard_theme`, `render_page_frame` | 1 (+app.py) | none (CSS @import fonts.googleapis.com) | none |
| dashboard/components/product_header.py | 70 | module | `product_header` | 1: views/inspector | none | none |
| dashboard/components/score_breakdown.py | 93 | module | `V4_PILLARS`, `score_breakdown_v4`; hard-coded pillar maxima | 4 | none (comment cites quality_score.json; does not read it) | none |
| dashboard/components/source_chips.py | 35 | module | `render_source_chips`, `PLANE_STYLES` | 2 | none | none |
| dashboard/components/status_badge.py | 33 | module | `status_badge` | 2 | none | none |
| dashboard/config.py | 33 | module | `DashboardConfig`, `get_config` | 1: app.py | none | none |
| dashboard/data_loader.py | 1524 | module | `DashboardData`, `load_dashboard_data`, `filter_product_catalog` | 9 | scripts/dist/{core DB ro, export_manifest, export_audit_report, detail_index, detail_blobs/*, label_mismatch_summary}; sibling build dirs; scripts/products/{output_*, logs/processing_state.json, logs/batch_*_log.txt, batch_run_summary_*.txt}; scripts/config/scoring_config.json; scripts/data/caers_adverse_event_signals.json; dashboard_alerts.json | none |
| dashboard/navigation.py | 52 | module | `PAGE_DEFINITIONS` (14 views), `parse_dashboard_query_params` | 2 | none | none |
| dashboard/page_meta.py | 327 | module | `PAGE_META` (16 slugs), `get_page_meta` | 1: app.py | none | none |
| dashboard/time_format.py | 45 | module | `format_dashboard_datetime` | 5 | none | none |
| dashboard/views/__init__.py | 16 | module | re-exports 17 `render_*` functions | 1: app.py (imports 13) | none | none |
| dashboard/views/audit_caers.py | 366 | module | CAERS adverse-events audit | 1 (+app.py) | via loader; direct open of scripts/data/banned_recalled_ingredients.json (cwd-relative) | none |
| dashboard/views/audit_pillars.py | 125 | module | V4 six-pillar audit | 1 (+app.py) | via loader (`pillar_*_v4`) | none |
| dashboard/views/audit_section_a.py | 422 | module | Section A (Ingredient Quality) audit | 1: views/__init__; **not imported by app.py** | via loader; direct detail_blobs/{id}.json | none |
| dashboard/views/audit_section_b.py | 440 | module | Section B (Safety & Purity) audit | 1; not imported by app.py | via loader | none |
| dashboard/views/audit_section_c.py | 257 | module | Section C (Evidence) audit | 1; not imported by app.py | via loader | none |
| dashboard/views/audit_section_d.py | 298 | module | Section D (Brand Trust) audit | 1; not imported by app.py | via loader | none |
| dashboard/views/batch_diff.py | 44 | module | `render_batch_diff` | 1 (+app.py) | via loader: batch_history | none |
| dashboard/views/diff.py | 132 | module | `render_diff`, `render_release_comparison` | 1 (+app.py) | direct sqlite3 ro connect to two builds' core DB | none |
| dashboard/views/health.py | 319 | module | `render_health` | 1 (+app.py) | via loader | none |
| dashboard/views/inspector.py | 376 | module | `render_inspector`, `render_drill_down`, `perform_search` | 1 (+app.py) | DB `SELECT * FROM products_core`; detail_blobs/{dsld_id}.json | none |
| dashboard/views/intelligence.py | 179 | module | `render_intelligence` | 1 (+app.py) | via loader | none |
| dashboard/views/module_health.py | 86 | module | per-module V4 pillar comparison | 1 (+app.py) | via loader | none |
| dashboard/views/observability.py | 572 | module | `render_observability` | 1 (+app.py) | via loader; direct stat/glob of scripts/dist; `remote_manifest` (never assigned) | none |
| dashboard/views/quality.py | 803 | module | `render_quality`, `build_form_curation_rows`, `build_safety_finding_rows` | 1 (+app.py) | via loader; direct detail_blobs/*.json glob | none |
| dashboard/views/safety_copy.py | 464 | module | Safety-copy coverage | 1 (+app.py) | direct: six scripts/data/*.json; **hard-coded absolute path `/Users/seancheick/PharmaGuide ai/assets/reference_data`** | none |
| dashboard/views/scoring_integrity.py | 234 | module | automated V4 scoring-anomaly detection | 2 (+app.py); `scripts/audits/v4_scoring_health_report.py:28` imports `classify_zero_pillar` | via loader | none |

## How it is launched

No Makefile; `.claude/launch.json` has only `website-prod`; no skill launches it. Launch lines: `scripts/dashboard/README.md:18`, `:24` (`streamlit run scripts/dashboard/app.py` with `--scan-dir scripts/products --build-root scripts/dist`), `scripts/dashboard/INSTRUCTIONS.md:114`, `:118`, `:123`, `:143`, `:241` (headless on port 8599), `docs/superpowers/plans/2026-04-09-…md:631`. `scripts/rebuild_dashboard_snapshot.sh` does **not** run Streamlit — it builds and promotes `scripts/dist` / `scripts/final_db_output`; `streamlit` appears only in an echo at line 298. It is called from `release_full.sh:488` and `rebuild_interaction_db.sh:180`. CI caches `scripts/dashboard/requirements.txt` as a pip key only.

## Level-2 candidates (agent's list; promotion decided by census criteria)

- `dashboard/data_loader.py`: 1,524 LOC, 9 in-dashboard importers; the only loader of release and pipeline artifacts; `@st.cache_resource` entry points.
- `dashboard/views/quality.py`: 803 LOC; reads `detail_blobs/*.json` directly and the DB through `db_conn`.
- Coupling to production is by artifact schema only (`pillar_*_v4` columns, manifest/audit JSON field names); `components/score_breakdown.py` hard-codes the V4 pillar maxima.
- Other facts: `views/safety_copy.py` reads six `scripts/data/*.json` directly plus a hard-coded absolute Flutter-repo path; `views/scoring_integrity.py` is the one module imported from outside (an audit script); `views/audit_section_a/b/c/d.py` (1,417 LOC together) are re-exported by `views/__init__.py` but not imported by `app.py`, and `navigation.PAGE_DEFINITIONS` has no entry for them while `page_meta.PAGE_META` still has `section-a/b/c/d-audit` keys and `INSTRUCTIONS.md` lists `view=section-a-audit`.

## How tests reach it

`dashboard_app` fixture in `scripts/tests/conftest.py` (~line 182): snapshots `sys.modules`, deletes `scripts.dashboard*`, installs `_DashboardStreamlitMock` (MagicMock subclass, line 108) as `sys.modules["streamlit"]`, re-imports the dashboard, yields a SimpleNamespace; restores on teardown; never imports `app.py`. Users: `test_dashboard_smoke.py` (9 tests; renders 12 slugs, not caers-audit, clinical-copy or section-a/b/c/d), `test_graceful_degradation.py`, `test_candidate_release_test_runner.py`. Direct imports with real streamlit: `test_dashboard_arrow_safe.py`, `test_dashboard_form_curation.py`, `test_scoring_integrity.py`.
