# Dead-code batch — unreachable dashboard section views (2026-10-18)

Branch `claude/dashboard-unreachable-views`; architecture audit §H item 5
(`scripts/audits/architecture_audit_20261017/AUDIT.md`). Proof tags are those of
`scripts/audits/closure_20260921/REMOVALS_AND_RETENTIONS_20260921.md` (ZERO, TRACE, FIELD,
SUPERSEDED, RETARGETED). Dashboard only: no pipeline module, data file, scoring config or rule
changed, so no corpus rebuild and no score-neutrality run.

## Removed

| File | Removed | Proof |
|---|---|---|
| `scripts/dashboard/views/audit_section_a.py` (422 lines) | `render_audit_section_a` | ZERO + SUPERSEDED |
| `scripts/dashboard/views/audit_section_b.py` (440 lines) | `render_audit_section_b` | ZERO + SUPERSEDED |
| `scripts/dashboard/views/audit_section_c.py` (257 lines) | `render_audit_section_c` | ZERO + SUPERSEDED |
| `scripts/dashboard/views/audit_section_d.py` (298 lines) | `render_audit_section_d` | ZERO + SUPERSEDED |
| `scripts/dashboard/views/__init__.py` | the four re-exports | the only production reference |
| `scripts/dashboard/page_meta.py` | keys `section-a-audit` … `section-d-audit`; `caers-audit.related_views` label "Section B Audit" → "Suppression Audit" | metadata for routes that do not exist (`get_page_meta` is only called with a routed slug) |
| `scripts/dashboard/INSTRUCTIONS.md`, `README.md` | `section-a-audit` URL/screenshot/file mentions → `pillar-audit` / `audit_pillars.py` | docs leave with the code |

**ZERO.** The only route table is `scripts/dashboard/navigation.py::PAGE_DEFINITIONS` (14 slugs) and the
only dispatcher is `scripts/dashboard/app.py::_render_current_view`; neither names a section view or slug.
Probe: `rg -n "render_audit_section_[abcd]|audit_section_[abcd]\b|section-[abcd]-audit|Section [ABCD] Audit"`
over `scripts/`, `.claude/` (skills, rules), `docs/` and the Flutter repo
(`/Users/seancheick/PharmaGuide ai`, whole tree) found: the four re-exports in `views/__init__.py`, the four
`page_meta.py` keys (plus one dangling `related_views` label), prose in `INSTRUCTIONS.md`/`README.md`, and
history only — `scripts/audits/quality_redesign/baseline_provenance.json` (a hash manifest of the
September baseline, left as recorded), gitignored replay `*.meta.json` hash manifests under `.claude/state/`,
old `sed` permission strings in `.claude/settings.local.json`, and the app's `SPRINT_TRACKER.md` describing a
2026 sprint. `python -c` comparing `PAGE_META` keys with `PAGE_DEFINITIONS` slugs: exactly these four keys had no
route; every route has its metadata. The helpers the views imported (`filter_product_catalog`, `metric_row`,
`data_table`) each have live consumers in other views, so no helper became dead with them (fixpoint).

**SUPERSEDED.** Commit 39057b0a0 (2026-06-14, "V4 six-pillar rebuild — pillars, suppression, cohorts")
removed the four routes; `page_meta.py` says so in the Pillar Audit summary ("Replaces the legacy V3 Section
A/B/C/D audits"). The section views sorted and plotted the loader's V3 aliases (`section_a_score` …
`section_d_max`), which `scripts/dashboard/data_loader.py:525-540` fills from the core columns
`score_ingredient_quality` … `score_brand_trust_max`. `build_final_db.py` (comment above the insert tuple)
emits those eight columns as NULL ("retired v3 section columns kept only because the published 2.5.0
SQLite schema declares them … nothing reads them") and `core_export_model.py` lists them in
`_SCHEMA3_REMOVED_COLUMNS`. The live owners are `views/audit_pillars.py` (Pillar Audit, Suppression Audit),
`views/scoring_integrity.py` and `views/module_health.py`.

Not a KEEP candidate: nothing reaches the functions, so `audit_dead_code.KEEP` gains no entry; the ratchet
saw them as live only through the `__init__` re-export.

## Kept

Nothing from this batch. `test_dashboard_smoke.py` still renders the 12 routed slugs it knows;
`caers-audit` and `clinical-copy` remain outside its `view_renderers` (audit F.4, a test gap, not this batch).

## Validation (dashboard-only class)

`scripts/test.sh fast scripts/tests/test_dashboard_smoke.py scripts/tests/test_graceful_degradation.py
scripts/tests/test_candidate_release_test_runner.py scripts/tests/test_dashboard_form_curation.py
scripts/tests/test_scoring_integrity.py scripts/tests/test_dashboard_arrow_safe.py
scripts/tests/test_no_unreferenced_production_code.py` → 51 passed; the smoke and degradation files rerun by
name with `-v` → 11 passed. `git diff --check` clean.
