# Flutter v4 Migration — Handoff for the Flutter Agent

**Date:** 2026-06-09
**Owner repo for this doc:** `seancheick/PharmaGuide_Pipeline` (the data pipeline).
**Target repo for the work:** the Flutter app (`/Users/seancheick/PharmaGuide ai`, memory `reference_flutter_repo`).
**Status:** the pipeline-side v4 cutover is **merged to `main`** (export schema **v2.0.0**, default `--score-model v4`). The app is the **last** consumer still on the v3 field contract. This handoff is the turnkey spec to migrate it.

---

## 0. TL;DR

- The downloaded **SQLite catalog bundle now ships v4 fields** and **dropped the legacy `/80` columns**. A v3-reading app will query `score_quality_80` (gone) → break.
- **Supabase needs NO schema migration.** The catalog (with all score columns) lives inside the SQLite bundle in Storage. The Postgres side is only a release registry + user data — no product/score tables. The only Postgres value that changes is `export_manifest.schema_version` → `"2.0.0"`, written automatically on sync.
- **The only real work is in the Flutter app:** read `quality_score_v4_100` / `quality_score_status` / the six `quality_pillars_v4` instead of `score_quality_80` / A-B-C-D sections.
- **Hard ordering:** ship the Flutter v4 reader **first**, gate the bundle by `min_app_version`, **then** sync the v4 bundle. The pipeline already refuses to sync a v4 build unless `--allow-v4-cutover` is passed (a deliberate tripwire — `scripts/sync_to_supabase.py`, `scripts/tests/test_sync_v4_cutover_tripwire.py`).

**Source of truth for field names (do not guess):**
`scripts/build_final_db.py` `SCHEMA_SQL` (products_core DDL) + `build_detail_blob` (blob keys);
`scripts/FINAL_EXPORT_SCHEMA_V1.md`; tier bands in `scripts/scoring_v4/config/quality_score.json`.

---

## 1. The new `products_core` contract (export schema v2.0.0)

### DROPPED (remove from Drift + all queries)
- `score_quality_80` (REAL) — the old `/80` headline.
- `score_display_80` (TEXT).

### ADDED — the v4 `/100` contract
| Column | Type | Meaning |
|---|---|---|
| `quality_score_v4_100` | REAL | **Canonical shipped score, 0–100.** `NULL` when `quality_score_status != 'scored'`. **Rank/search on this.** |
| `quality_score_status` | TEXT | `scored` \| `suppressed_safety` \| `not_scored`. Drives display + filtering. |
| `quality_tier` | TEXT | `Elite` / `Excellent` / `Strong` / `Acceptable` / `Weak` / `Poor`. `NULL` when not scored. |
| `quality_score_suppressed_reason` | TEXT | Why the score is suppressed (e.g. `banned_ingredient`); `NULL` when scored. |
| `raw_score_v4_100` | REAL | **Audit/debug only — NEVER display or rank on this.** |
| `v4_module` | TEXT | routed archetype (`generic`/`probiotic`/`omega`/`multi_or_prenatal`/`sports`). |
| `v4_confidence` | TEXT | top-level confidence band. |
| `score_model_version` | TEXT | loud stamp = `"v4"`. Use to assert you're reading v4 math. |
| `quality_score_version`, `scoring_engine_version`, `classification_schema_version`, `v4_config_fingerprint` | TEXT | provenance ("why did this score change?"). Optional to surface. |

### KEPT (compat / unchanged source)
- `score_100_equivalent` (REAL) — honest `/100` mirror of `quality_score_v4_100` (same value when scored, `NULL` otherwise). Safe fallback if you want one column.
- `score_display_100_equivalent` (TEXT) — e.g. `"88/100"` or `"N/A"`.
- `grade` (TEXT) — now carries the **v4 tier** string (legacy column, reused). Prefer `quality_tier`.
- `verdict` (TEXT: `SAFE`/`CAUTION`/`POOR`/`BLOCKED`/`UNSAFE`/`NOT_SCORED`), `safety_verdict`, `mapped_coverage` (label completeness — **not** score confidence).
- `score_ingredient_quality*` / `score_safety_purity*` / `score_evidence_research*` / `score_brand_trust*` — **vestigial v3 section columns. Do NOT rank or render from these.** They remain only as v3 scaffolding and will be dropped in a later phase.

### Status semantics (the single most important rule)
- `scored` → `quality_score_v4_100` is finite. Show the score + tier.
- `suppressed_safety` → score is `NULL` (product is BLOCKED/UNSAFE). **Show NO number**; show the safety reason. Exclude from ranking/alternatives.
- `not_scored` → score is `NULL` (insufficient label data). Show "Not scored / insufficient label data". The pipeline already **excludes** these from the catalog, but guard for `NULL` anyway.

---

## 2. The detail blob now carries the v4 explainability payload

`build_detail_blob` emits these keys (only on v4 builds):

| Blob key | Use |
|---|---|
| `quality_pillars_v4` | The **six pillars**, each `{score, max, reason, components}`: `formulation`/20, `dose`/20, `evidence`/20, `transparency`/15, `verification`/15, `safety_hygiene`/10. **Render these instead of the old A/B/C/D `section_breakdown`.** |
| `clean_label_flags_v4` | Clean-label additive flags (e.g. titanium dioxide / E171) with `consumer_note`, `tier`, `regulation_citation`, `regulation_url`. New clean-label UI. |
| `v4_safety_gate` | `{verdict, blocking_reason, matched_substance, safety_signals, clean_label_hits}`. |
| `v4_completeness_gate` | `{module, missing_fields, mapped_coverage, ...}`. |
| `v4_score_provenance` | `{score_model_version, quality_score_status, quality_tier, quality_score_version, scoring_engine_version, module, confidence, config_fingerprint, suppressed_reason}`. |
| `v4_score_explanation` | Top positive/negative pillar reasons — the "how it scored X" summary. |
| `raw_score_v4_100` | audit only. |

Note: the old `section_breakdown` (A/B/C/D) is still present in the blob for now (v3 scaffolding) — **ignore it**; render `quality_pillars_v4`.

---

## 3. Field mapping (v3 → v4)

| v3 (current Flutter) | v4 (new) |
|---|---|
| `score_quality_80` / `scoreQuality80` | `quality_score_v4_100` (and gate on `quality_score_status == 'scored'`) |
| `score_100_equivalent` (hero) | `quality_score_v4_100` (mirror still in `score_100_equivalent`) |
| `grade` (letter) | `quality_tier` (Elite…Poor) |
| `section_breakdown` A/B/C/D | `quality_pillars_v4` (six pillars + reasons) |
| `score_brand_trust` (5-pt, drives alternatives) | the **verification** pillar inside `quality_pillars_v4` (do not rank on the old field) |
| n/a | `quality_score_status`, `quality_tier`, `clean_label_flags_v4`, `score_model_version` |

---

## 4. Per-file changes (from the cutover audit; verify line numbers against current Flutter HEAD)

1. **`data/database/products_core_table.dart`** (Drift table, ~line 51)
   - Remove `scoreQuality80`, `scoreDisplay80`.
   - Add `qualityScoreV4100` (real, nullable), `qualityScoreStatus` (text), `qualityTier` (text, nullable), `qualityScoreSuppressedReason`, `rawScoreV4100`, `v4Module`, `v4Confidence`, `scoreModelVersion`, and the provenance columns you choose to surface.
   - Keep `score100Equivalent`, `scoreDisplay100Equivalent`, `grade`, `verdict`, `safetyVerdict`, `mappedCoverage`.
   - **Bump the Drift `schemaVersion`** and update the table mapping so the downloaded bundle's columns resolve. (The app opens a freshly-downloaded bundle; the Drift table definition must match the new column set or reads fail.)

2. **`data/database/core_database.dart`** (ranking/search, ~lines 284, 303, 484)
   - Replace `ORDER BY score_quality_80` with `ORDER BY quality_score_v4_100 DESC` and add `WHERE quality_score_status = 'scored'` (exclude null-score rows from ranked lists).
   - Any index on `score_quality_80` → `quality_score_v4_100` (the bundle's index is already `idx_core_score(quality_score_v4_100)`).

3. **`services/recommendations/better_alternatives_ranker.dart`** (~136–148)
   - Rank alternatives by `quality_score_v4_100`; **exclude** `quality_score_status != 'scored'` and any BLOCKED/UNSAFE. Stop using `score_brand_trust` as the driver.

4. **`features/product_detail/v2/product_detail_v2_connected.dart`** (~228, ~490) + **`score_breakdown_section.dart`**
   - Hero score: `quality_score_status == 'scored'` → show `quality_score_v4_100` + `quality_tier`; `suppressed_safety` → no number, show safety reason; `not_scored` → "Not scored / insufficient label data".
   - Breakdown: render the six `quality_pillars_v4` (score/max + one-line `reason` each), not the old A/B/C/D section UI.
   - Verification/trust UI: use the v4 `verification` pillar, not the old 5-pt `score_brand_trust`.

5. **Share cards / descriptions** — use `quality_tier` + `quality_score_status`, not `grade`/`score_100_equivalent` semantics.

6. **Clean-label UI (new)** — render `clean_label_flags_v4` (consumer note + `regulation_url` click-through).

7. **Keep label confidence separate** — `mapped_coverage` is **label completeness**, not score confidence. Don't conflate with `v4_confidence`.

---

## 5. Behavior rules (medical-grade — don't violate)

- **Never show `raw_score_v4_100`** — it's audit-only.
- **Never show a number for `suppressed_safety`** — that's a BLOCKED/UNSAFE product; show the safety reason.
- A **CAUTION** product is `quality_score_status == 'scored'` and **keeps its score** — show score + a caution flag.
- Ranked surfaces (search, alternatives, "best in category") must filter to `quality_score_status == 'scored'`.

---

## 6. Release ordering (do NOT skip — this is how you avoid breaking live users)

The moment a v4 bundle is **ACTIVE**, every app downloads it. A v3-reading build then crashes on the missing `score_quality_80`. So:

1. **Land + ship the Flutter v4 reader** (this handoff). Bump the app version.
2. **Gate the bundle:** set `export_manifest.min_app_version` for the v4 release to the new app version so older apps won't pull it. Record the supporting commit in `catalog_releases.flutter_repo_commit`.
3. **Validate, then sync (pipeline side):**
   - Full-corpus v4 build: `python3 scripts/build_final_db.py --enriched-dir … --scored-dir … --output-dir <out>` (default v4).
   - Audits green: `db_integrity_sanity_check.py`, `audit_contract_sync.py`, `audit_inactive_safety.py`, `audit_raw_to_final.py --canary`.
   - Dry run: `python3 scripts/sync_to_supabase.py <out> --dry-run`.
   - Real sync requires the explicit tripwire: `python3 scripts/sync_to_supabase.py <out> --allow-v4-cutover` (it **refuses** a v4 build otherwise — see `test_sync_v4_cutover_tripwire.py`).
4. Only after the v4 app is in users' hands do you flip the v4 bundle ACTIVE.

---

## 7. Verification for the Flutter agent

- Unit/widget tests: hero score renders per status; ranked lists exclude non-scored; breakdown shows six pillars; clean-label chips render.
- Integration: open the app against a **v4 sample bundle** (ask the pipeline owner for one, or build with `--score-model v4`) and confirm: scores show, ranking works, no crash on `NULL` score, breakdown is the six pillars.
- Regression: a BLOCKED product shows the safety reason and **no** number.

---

## 8. What is explicitly NOT in scope here

- **Supabase Postgres migration** — none needed (see §0).
- **Pipeline changes** — done and merged (schema v2.0.0, default v4).
- **Phase C teardown** (pipeline) — removing `display_calibration`, renaming `shadow_*`→prod, retiring the v3 scorer — stays gated on this Flutter migration + Supabase proven green across a canary cycle.
