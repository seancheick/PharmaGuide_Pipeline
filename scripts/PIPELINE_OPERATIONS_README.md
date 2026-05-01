# Pipeline Operations README

Updated: 2026-04-22
Owner: Sean Cheick Baradji

This file is a practical command guide for running and releasing the PharmaGuide pipeline.

It covers:

- full pipeline run (Clean → Enrich → Score)
- dashboard snapshot rebuild (final DB build + release staging in one step)
- final DB build (per-pair + assembled release, alternative incremental path)
- pair change-journal generation
- assembled release creation
- Supabase sync and `--cleanup`
- Flutter artifact import and release gate
- DSLD API tooling status and commands

---

## 🟢 Canonical Operations — START HERE

> **If you have N brand folders under `$HOME/Documents/DataSetDsld/staging/brands/` and want a fresh `scripts/dist/` ready to sync — run this one command.**
>
> Works the same for 10 brands, 20 brands, or 30+ brands.

```bash
# From repo root
cd /Users/seancheick/Downloads/dsld_clean

# ONE command — does everything below in order
bash batch_run_all_datasets.sh
```

### What actually runs (and in what order)

The batch driver `batch_run_all_datasets.sh` is the canonical entry point. It orchestrates two phases:

**Phase 1 — Per-brand pipeline (repeats × N brands, sequentially, smallest first):**

| Step | Script | Reads | Writes |
|---:|---|---|---|
| 1.1 | `clean_dsld_data.py` | `staging/brands/<brand>/` raw DSLD JSON | `scripts/products/output_<brand>_cleaned/` |
| 1.2 | `enrich_supplements_v3.py` | cleaned | `scripts/products/output_<brand>_enriched/enriched/` |
| 1.3 | `score_supplements.py` | enriched | `scripts/products/output_<brand>_scored/scored/` |

Each brand runs through all three stages before the next brand starts. Brand outputs are independent — a failure in one brand doesn't stop the others (tracked, reported in summary).

**Phase 2 — Catalog-wide build + dashboard snapshot (runs once, after all brands complete):**

Triggered automatically at end of Phase 1 **only if every brand succeeded** (see "Guards" below). Calls `rebuild_dashboard_snapshot.sh`, which executes:

| Step | Script | Reads | Writes |
|---:|---|---|---|
| 2.1 | `build_final_db.py` | **every** `*_enriched/enriched` + `*_scored/scored` pair across all brands | `/tmp/pg_dashboard_snapshot_<pid>/` — staging dir with `pharmaguide_core.db`, `detail_blobs/`, `detail_index.json`, `export_manifest.json`, `export_audit_report.json` |
| 2.2 | `release_catalog_artifact.py` | `/tmp/pg_dashboard_snapshot_<pid>/` | `scripts/dist/pharmaguide_core.db`, `scripts/dist/export_manifest.json`, `scripts/dist/RELEASE_NOTES.md` — validates + stages atomically |
| 2.3 | bash copy | `/tmp/…/detail_blobs/` + `/tmp/…/detail_index.json` + `/tmp/…/export_audit_report.json` | `scripts/dist/detail_blobs/`, `scripts/dist/detail_index.json`, `scripts/dist/export_audit_report.json` — these are dashboard-only (Flutter bundle doesn't need them, but the Streamlit dashboard does) |

**Phase 2 answers the "dashboard before or after final build DB?" question directly:**

> The dashboard snapshot **IS** the final build-db step. Step 2.1 (`build_final_db.py`) produces the catalog DB; step 2.2 stages the Flutter bundle; step 2.3 adds the dashboard-only artifacts on top. All three are part of the same automated `rebuild_dashboard_snapshot.sh` run. There is no separate "dashboard update" that happens later.

### End-state after a clean run

```
scripts/dist/
├── RELEASE_NOTES.md               ← auto-generated
├── pharmaguide_core.db            ← Flutter catalog (ships with app)
├── export_manifest.json           ← schema + version + integrity + errors
├── export_audit_report.json       ← warnings + counts (dashboard-only)
├── detail_index.json              ← id → sha256 lookup (dashboard-only)
└── detail_blobs/<id>.json         ← per-product full detail JSON (dashboard-only)
```

The Flutter import script (`PharmaGuide ai/scripts/import_catalog_artifact.sh`) pulls only the 3 artifacts it needs (`pharmaguide_core.db`, `export_manifest.json`, `RELEASE_NOTES.md`). The dashboard and Supabase sync read everything in `scripts/dist/`.

### Running with fewer brands / specific brands

```bash
# Process one brand only (e.g., while iterating on enricher)
bash batch_run_all_datasets.sh --targets Olly

# Process a subset
bash batch_run_all_datasets.sh --targets Olly,Thorne,Pure

# Use a different brands root
bash batch_run_all_datasets.sh --root "$HOME/Documents/DataSetDsld/delta/olly"

# Score-only on all brands (skip clean + enrich — requires prior cleaned+enriched)
bash batch_run_all_datasets.sh score

# Specific stages + specific brands
bash batch_run_all_datasets.sh --stages enrich,score --targets Nature_Made
```

### Skipping the automated snapshot rebuild

```bash
# Skip the Phase 2 snapshot rebuild (useful for single-brand iteration loops)
SKIP_SNAPSHOT=1 bash batch_run_all_datasets.sh --targets Olly

# Later, rebuild the snapshot manually when you're ready
bash scripts/rebuild_dashboard_snapshot.sh
```

### Guards (when Phase 2 is skipped automatically)

Phase 2 does **not** run if:

1. **Any brand failed in Phase 1** — a partial catalog snapshot would be misleading. You'll see: `Dashboard snapshot NOT rebuilt because some brands failed.`
2. **`SKIP_SNAPSHOT=1`** — caller opted out.
3. **`rebuild_dashboard_snapshot.sh` is not executable** — fix with `chmod +x scripts/rebuild_dashboard_snapshot.sh`.

If Phase 2 is skipped and you later want the snapshot, run `bash scripts/rebuild_dashboard_snapshot.sh` manually. It is idempotent and safe to rerun.

### What gets written to `scripts/products/reports/`

Every batch run writes a summary file: `scripts/products/reports/batch_run_summary_YYYYMMDD_HHMMSS.txt`

Contains the full per-brand pipeline log + the Phase 2 snapshot log. Useful for release ledgers and post-run diagnostics.

### After a successful batch run

1. **Verify** — check `scripts/dist/export_audit_report.json` for `contract_failures: 0` and review the `counts.total_errors` value
2. **Scope-report** (optional, E1+) — see the command below
3. **Canary shadow-diff** (optional, E1+) — see the command below
4. **Dry-run sync** — `python3 scripts/sync_to_supabase.py scripts/dist --dry-run`
5. **Real sync** — `python3 scripts/sync_to_supabase.py scripts/dist`
6. **Flutter bundle** — see `§ Release playbook` below for the Flutter side

### Useful post-run commands

```bash
# Label-fidelity + safety-copy scope report (Sprint E1+)
python3 scripts/reports/label_fidelity_scope_report.py \
    --blobs scripts/dist/detail_blobs/ \
    --out reports/ \
    --prefix release_$(date +%Y%m%d)

# 9-canary shadow-diff (requires reports/canary_rebuild/<id>.json baselines)
for id in 35491 306237 246324 1002 19067 1036 176872 266975 19055; do
  diff <(python3 -c "import json; print(json.dumps(json.load(open('reports/canary_rebuild/$id.json')), sort_keys=True, indent=2))") \
       <(python3 -c "import json; print(json.dumps(json.load(open('scripts/dist/detail_blobs/$id.json')), sort_keys=True, indent=2))") \
    | head -5
done

# Streamlit dashboard (requires scripts/dist/ populated)
streamlit run scripts/dashboard/app.py
```

### Runtime expectations

- **All-local, no external API calls in the main pipeline** — runs as fast as your SSD + CPU allow
- **20 brands / ~8–13K products** — ~15 min per brand end-to-end (clean+enrich+score), plus ~1 min for Phase 2 snapshot
- **No network required** — everything reads local data and local reference JSON

### Mental model

```
staging/brands/<brand>/  ──clean──▶  *_cleaned/  ──enrich──▶  *_enriched/  ──score──▶  *_scored/
      (× N brands)                                                              │
                                                                                ▼
                                                         rebuild_dashboard_snapshot.sh
                                                                                │
                                                          build_final_db.py (all brands merged)
                                                                                │
                                                                                ▼
                                                                /tmp/staging/
                                                                      │
                                                       release_catalog_artifact.py
                                                                      │
                                                                      ▼
                                                               scripts/dist/  ← consumed by Supabase sync + Flutter + dashboard
```

---

## Schema version history

| Version | Date       | Columns | Summary                                                                                                                                                                                                      |
| ------- | ---------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| v1.3.0  | 2026-04-07 | 87      | Stack interaction, social sharing, search/filter, goal matching, dosing/allergen summary                                                                                                                     |
| v1.3.1  | 2026-04-10 | 89      | `serving_info` phantom key bugfix (`dosing_summary` + `servings_per_container` now populate) + `net_contents_*`                                                                                              |
| v1.3.2  | 2026-04-10 | 90      | Nutrition hybrid (`calories_per_serving` column + `nutrition_detail` blob) + `unmapped_actives` blob transparency                                                                                            |
| v1.3.3  | 2026-04-14 | 90      | Interaction safety expansion: 127 rules (was 98), 4 new drug classes, context-aware harmful scoring, 25 PMID fixes, IQM 588 entries (was 571)                                                                |
| v1.3.4  | 2026-04-14 | 90      | CAERS B8 scoring (159 adverse event signals), UNII offline cache (172K substances), IQM UNII standardization (66%), drug label interaction mining (40 supplements, 90% coverage), CAERS dashboard audit view |
| v1.4.0  | 2026-04-15 | 91      | `image_thumbnail_url` column added; IQM expanded to 589 entries; branded ingredient bio-score prioritization fix (KSM-66, Sensoril, Bergavit); 31 new IQM aliases; normalize_upc pipeline step               |

Runtime source of truth: `CORE_COLUMN_COUNT` in `build_final_db.py` plus `EXPORT_SCHEMA_VERSION`. See `FINAL_EXPORT_SCHEMA_V1.md` for the per-column contract.

### What landed in v1.3.1 and v1.3.2 (field-level audit cycle, 2026-04-10)

The 2026-04 audit traced every field across Clean → Enrich → Score → Final DB → Flutter, looking for silent drops where one stage computed data that a downstream stage ignored (Bug C pattern — named after the original probiotic `clinical_strain_count` bug from 2026-04-09). Ten tracks landed across the cycle:

- **Track 1 (v1.3.1)**: Fixed `serving_info` phantom key in `generate_dosing_summary`. The function was reading a nonexistent `enriched["serving_info"]` path, so `dosing_summary` always fell through to "See product label" and `servings_per_container` was always NULL. Rewrote it to read the real cleaner-emitted `servingSizes[0]` + `servingsPerContainer`. Also added `net_contents_quantity` + `net_contents_unit` columns for the refill-reminder feature. Flutter computes `days_until_empty = net_contents_quantity / (servingSizes[0].maxQuantity * maxDailyServings)`.
- **Track 2**: The enricher now strips 14 dead passthrough fields (`src`, `nhanesId`, `brandIpSymbol`, `productVersionCode`, `pdf`, `thumbnail`, `percentDvFootnote`, `hasOuterCarton`, `upcValid`, `productType`, `events`, `labelRelationships`, `metadata`, `images`). They were riding through from cleaner → enricher → final DB with zero downstream consumers, inflating record size. `display_ingredients` is kept because the enricher overwrites it.
- **Track 3**: Deleted three orphaned top-level reads (`qualityFeatures`, `certifications`, `otherIngredients`) in `_extract_text_sources`. The cleaner nests these under `labelText.parsed.*`, and the parsed iteration already captures them.
- **Track 4**: Amount-based sugar penalty in B1. Reads `dietary_sensitivity_data.sugar.level` from the enricher and docks `-0.5` for `moderate` (3–5 g) and `-1.5` for `high` (>5 g). Config-driven via `section_B_safety_purity.B1_dietary_sugar_penalty` in `scoring_config.json` (enables future per-user personalization — e.g. stronger penalty for diabetic profiles). Emits `SUGAR_LEVEL_MODERATE` or `SUGAR_LEVEL_HIGH` flags and B1 evidence entries. Stacks with the existing named-sweetener B1 penalty but the combined total is clamped to the existing B1 cap.
- **Track 5 (blob)**: `unmapped_actives` packed into `detail_blob.unmapped_actives` with `{names, total, excluding_banned_exact_alias}` shape. Always present (empty shape when nothing unmapped) so the Flutter app can render a transparency panel without null checks. The coverage gate stays at 99.5% for the batch-level BLOCK — we accept exotic long-tail ingredients, but users can now see which specific names failed to map.
- **Track 6 (nutrition hybrid, v1.3.2)**: Enricher emits `nutrition_summary` with all five macros (`calories_per_serving`, `total_carbohydrates_g`, `total_fat_g`, `protein_g`, `dietary_fiber_g`). Final DB adds one column (`calories_per_serving`, highest-value filter) and packs the remaining four plus calories into `detail_blob.nutrition_detail`. Promote more macros to columns later if usage justifies it.
- **Track 7 (Flutter sync)**: `lib/data/database/tables/products_core_table.dart` updated to match the 90-column pipeline schema. Added `netContentsQuantity`, `netContentsUnit`, `caloriesPerServing` Drift columns with refill-reminder and nutrition-hybrid docstrings. **One manual step still required**: run `dart run build_runner build --delete-conflicting-outputs` from the Flutter repo to regenerate `core_database.g.dart`.

## Supabase deployment checklist

The pipeline targets an **offline-first architecture**: the products table lives inside the SQLite file (`pharmaguide_core.db`) that ships as a Supabase Storage blob, NOT in the Supabase Postgres layer. Schema bumps to the SQLite columns require no Postgres migration — the Postgres tables (`export_manifest`, `user_stacks`, `user_usage`, `pending_products`) are unchanged.

What actually moves:

- `pharmaguide_core.db` → uploaded to `pharmaguide/v{db_version}/pharmaguide_core.db` in Storage. Contains the full 91-column `products_core` table (as of v1.4.0).
- `detail_blobs/*.json` → uploaded to `pharmaguide/shared/details/sha256/{prefix}/{hash}.json` in Storage.
- `export_manifest.json` → insert-new-row via `rotate_manifest(p_schema_version='1.4.0', ...)` RPC.

**Rollout checks** (run before a production sync):

1. Local build produces `export_manifest.json` with `schema_version: "1.4.0"`, `pipeline_version: "3.4.0"`, `scoring_version: "3.4.0"`
2. Full test suite green: `python3 -m pytest scripts/tests/ -q`
3. Dry-run sync: `python3 scripts/sync_to_supabase.py ~/Documents/DataSetDsld/builds/release_output --dry-run`
4. Flutter release gate passes: `flutter test test/release_gate/bundled_catalog_test.dart`
5. If schema version changed, regen Drift: `dart run build_runner build --delete-conflicting-outputs`

## Release playbook — bundling the catalog into the Flutter app

The offline-first contract the mobile app depends on is: every fresh install, even with no network, lands on a fully populated catalog. That means the Flutter repo (`seancheick/Pharmaguide.ai`) must bundle the exact SQLite file this pipeline produces, not a sample and not an OTA-only download. The bridge between the two repos is two scripts plus Git LFS. The flow below is the canonical release path.

### One-time setup (first release only)

In the Flutter repo:

```bash
# 1. Install Git LFS (macOS)
brew install git-lfs
git lfs install

# 2. Enable LFS tracking for the bundled SQLite
git lfs track "assets/db/*.db"
git add .gitattributes
```

`assets/db/*.db filter=lfs` should appear in `.gitattributes`. Verify with `git lfs track`.

### Every release

> **Critical:** `--assemble-release-output` MUST be on the same command line as
> `build_all_final_dbs.py`. If you paste it as a second shell line, zsh treats it
> as a separate command (error: `command not found: --assemble-release-output`) and
> the release_output directory is never updated — you silently release stale data.

```bash
# ── Pipeline side (dsld_clean repo) ──────────────────────────────────────────

# 1. Build all brand DBs AND assemble the release in one command.
#    Both flags MUST be on the same line.
python3 scripts/build_all_final_dbs.py \
  --scan-dir scripts/products \
  --per-pair-output-root ~/Documents/DataSetDsld/builds/pair_outputs \
  --assemble-release-output ~/Documents/DataSetDsld/builds/release_output

# 2. Run full test suite (3894+ tests).
python3 -m pytest scripts/tests/ -q

# 3. Package the catalog artifact (validates DB + manifest + checksum,
#    writes scripts/dist/ atomically). Requires --input-dir.
python3 scripts/release_catalog_artifact.py \
  --input-dir ~/Documents/DataSetDsld/builds/release_output

# 4. Package the interaction artifact.
python3 scripts/release_interaction_artifact.py

# Exit 0 on both means scripts/dist/ is ready.
# Any validation failure aborts with a clear error; dist/ is left untouched.

# 5. Dry-run Supabase sync to confirm what would upload.
python3 scripts/sync_to_supabase.py \
  ~/Documents/DataSetDsld/builds/release_output \
  --dry-run

# 6. Real sync. Add --cleanup to prune old Supabase versions (see §7B).
python3 scripts/sync_to_supabase.py \
  ~/Documents/DataSetDsld/builds/release_output

# ── Flutter side (PharmaGuide-ai repo) ───────────────────────────────────────

# 7. Import artifacts. Re-validates every gate (SHA-256, integrity, row count,
#    version alignment) before copying into assets/db/.
cd "/Users/seancheick/PharmaGuide ai"
./scripts/import_catalog_artifact.sh \
  /Users/seancheick/Downloads/dsld_clean/scripts/dist

# 8. Run the Flutter release gate test.
flutter test test/release_gate/bundled_catalog_test.dart

# 9. Regenerate Drift code only if the schema version changed.
dart run build_runner build --delete-conflicting-outputs

# 10. Commit and push.
git add assets/db/
git commit -m "chore(catalog): bundle v<db_version> (schema <schema_version>, <product_count> products)"
git push origin main
```

### Validation gates enforced at each step

| Step                 | Gate                                                               | Where                                                     |
| -------------------- | ------------------------------------------------------------------ | --------------------------------------------------------- |
| Clinical-copy gate   | Path C authored-field contract across 6 reference files            | `scripts/validate_safety_copy.py --strict`                |
| Pipeline validation  | SQLite integrity + row count + embedded manifest + checksum        | `release_catalog_artifact.py::validate_release_candidate` |
| Flutter bridge       | SHA-256 match, schema allowlist, split-brain check                 | `scripts/import_catalog_artifact.sh`                      |
| Flutter release gate | Bundle-load via rootBundle, CoreDatabase open, version cross-check | `test/release_gate/bundled_catalog_test.dart`             |

Any failure at any step aborts the release with a clear error. The Flutter bridge script intentionally leaves `assets/db/` untouched on failure so a broken build never replaces a good bundled DB.

### Clinical-copy validator (`validate_safety_copy.py`)

Release gate for Dr. Pham's authored clinical copy across six data files. Enforces length bounds, tone rules (no SCREAM words, no encyclopedic openers, no catastrophizing), conditional-framing requirements, and per-file structural contracts (e.g., `adequacy_threshold_mcg` XOR `adequacy_threshold_mg`).

**Run all files:**

```bash
python3 scripts/validate_safety_copy.py --strict
```

**Run a single file (faster during authoring):**

```bash
python3 scripts/validate_safety_copy.py --banned-recalled-only --strict
python3 scripts/validate_safety_copy.py --interaction-rules-only --strict
python3 scripts/validate_safety_copy.py --depletions-only --strict
python3 scripts/validate_safety_copy.py --harmful-additives-only --strict
python3 scripts/validate_safety_copy.py --synergy-only --strict
python3 scripts/validate_safety_copy.py --violations-only --strict
```

**Modes:**

- **Authoring (default)** — missing authored fields are warnings. Use while Dr. Pham is still working.
- **`--strict`** — missing authored fields are errors. Use as the release gate.
- **`--quiet`** — suppress warnings; only errors print. Use in CI output.

**What it checks (summary by file):**

| Reference file                      | Required authored fields                                                                                      | Extra contract                                                                                                                      |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `banned_recalled_ingredients.json`  | `ban_context` (enum), `safety_warning` (50-200), `safety_warning_one_liner` (20-80)                           | Adulterant entries must contain "in supplement" guardrail; contamination_recall must use regulatory verb                            |
| `ingredient_interaction_rules.json` | `alert_headline` (20-60), `alert_body` (60-200), `informational_note` (40-120)                                | Avoid/contraindicated severity requires conditional framing ("if you take", "talk to")                                              |
| `medication_depletions.json`        | `alert_headline`, `alert_body`, `acknowledgement_note`, `monitoring_tip_short`, optional `food_sources_short` | No acute-tense framing; no numeric stats in body; exactly one of `adequacy_threshold_mcg`/`_mg`                                     |
| `harmful_additives.json`            | `safety_summary` (50-200), `safety_summary_one_liner` (20-80)                                                 | No SCREAM words; terminal punctuation on one-liner                                                                                  |
| `synergy_cluster.json`              | `synergy_benefit_short` (40-160)                                                                              | No alarm/nocebo words (synergy is positive framing)                                                                                 |
| `manufacturer_violations.json`      | `brand_trust_summary` (40-120)                                                                                | No semicolons; terminal punctuation; SCREAM words blocked (but alarming adjectives allowed — serious recalls deserve serious voice) |

**Failure output:** each violation prints the exact entry ID + field + reason. Fix the offender and re-run; no explicit "fix this" tooling yet — the messages point at the file and field directly.

### Reference-data schema versions

The `EXPORT_SCHEMA_VERSION` above tracks the product-core DB. Each reference data file has its own `_metadata.schema_version` that advances independently:

| File                                | Current | Notes                                                                             |
| ----------------------------------- | ------- | --------------------------------------------------------------------------------- |
| `banned_recalled_ingredients.json`  | 5.3.0   | Added `contamination_recall` as 5th `ban_context` enum value (2026-04-18)         |
| `ingredient_interaction_rules.json` | 5.2.0   | All severe sub-rules + pregnancy_lactation blocks + non-severe sub-rules authored |
| `medication_depletions.json`        | 5.2.1   | `food_sources_short` optional field added; 68 entries authored                    |
| `harmful_additives.json`            | 5.1.0   | `safety_summary` + `safety_summary_one_liner` fields added; 115 authored          |
| `synergy_cluster.json`              | 5.0.0   | `synergy_benefit_short` field added (Dr. Pham, 2026-04-18); 58 authored           |
| `manufacturer_violations.json`      | 5.0.0   | `brand_trust_summary` field added; 79 authored                                    |

Schema bumps cascade into Flutter's reference-data asset sync — see "Flutter asset sync status" in the Clinical Copy dashboard to spot drift the moment it happens.

### Git LFS quota notes

The SQLite file currently ships at ~5.9 MiB (4240 products, schema v1.4.0, 91 columns). Free GitHub LFS quota is 1 GB storage + 1 GB/month bandwidth, which easily accommodates thousands of releases. If the DB grows past ~50 MiB, plan for an LFS quota bump on the Flutter repo before the release that ships it.

### Rollback

The bridge script automatically moves the previous bundled DB aside as `assets/db/pharmaguide_core.db.previous` before replacing it. If a post-release issue surfaces, roll back with:

```bash
cd "/path/to/PharmaGuide ai"
mv assets/db/pharmaguide_core.db.previous assets/db/pharmaguide_core.db
mv assets/db/export_manifest.json.previous assets/db/export_manifest.json
git commit -am "rollback: revert catalog to previous bundled version"
```

The `.previous` files are overwritten on every successful import, so the rollback window is exactly one release back.

## 1. Build a final DB from enriched + scored outputs

Build one final release artifact directly:

```bash
python3 scripts/build_final_db.py \
  --enriched-dir /Users/seancheick/Documents/DataSetDsld/output_olly_2026-03-30T01-49-58_enriched/enriched \
  --scored-dir /Users/seancheick/Documents/DataSetDsld/output_olly_2026-03-30T01-49-58_scored/scored \
  --output-dir /Users/seancheick/Documents/DataSetDsld/final_db_output_olly_2026-03-30T01-49-58
```

Output includes:

- `pharmaguide_core.db`
- `detail_blobs/`
- `detail_index.json`
- `export_manifest.json`

## 2. Auto-discover and build all final DBs

Build from all discovered enriched/scored pairs:

```bash
python3 scripts/build_all_final_dbs.py --scan-dir scripts
```

Plan without building:

```bash
python3 scripts/build_all_final_dbs.py --scan-dir scripts --plan-only
```

Build only selected brands:

```bash
python3 scripts/build_all_final_dbs.py \
  --scan-dir scripts \
  --include-prefix Nordic \
  --include-prefix Olly
```

Exclude brands:

```bash
python3 scripts/build_all_final_dbs.py \
  --scan-dir scripts \
  --exclude-prefix Emerald
```

## 3. Incremental pair builds

Use fingerprint state:

```bash
python3 scripts/build_all_final_dbs.py \
  --scan-dir scripts \
  --state-file /Users/seancheick/Documents/DataSetDsld/builds/pair_state.json \
  --changed-only \
  --per-pair-output-root /Users/seancheick/Documents/DataSetDsld/builds/pair_outputs
```

Use upstream change journal:

```bash
python3 scripts/build_all_final_dbs.py \
  --scan-dir scripts \
  --change-journal /Users/seancheick/Documents/DataSetDsld/builds/pair_change_journal.json \
  --per-pair-output-root /Users/seancheick/Documents/DataSetDsld/builds/pair_outputs
```

Important:

- `--changed-only` is for per-pair builds, not partial combined releases
- use `--assemble-release-output` if you want a full release artifact after per-pair builds

## 4. Generate a pair change journal

Create a journal from discovered enriched/scored outputs:

```bash
python3 scripts/generate_pair_change_journal.py \
  --scan-dir scripts \
  --journal-path /Users/seancheick/Documents/DataSetDsld/builds/pair_change_journal.json \
  --state-file /Users/seancheick/Documents/DataSetDsld/builds/pair_source_state.json
```

This writes:

- a journal of `new`, `changed`, and `removed` pairs
- a persisted source-state file for the next run

## 5. Assemble a full release from per-pair outputs

Assemble from a root of per-pair build outputs:

```bash
python3 scripts/assemble_final_db_release.py \
  --input-root /Users/seancheick/Documents/DataSetDsld/builds/pair_outputs \
  --output-dir /Users/seancheick/Documents/DataSetDsld/builds/release_output
```

Assemble from one or more explicit per-pair dirs:

```bash
python3 scripts/assemble_final_db_release.py \
  --input-dir /Users/seancheick/Documents/DataSetDsld/builds/pair_outputs/Nordic-Naturals-2-17-26-L511 \
  --input-dir /Users/seancheick/Documents/DataSetDsld/builds/pair_outputs/Olly-2-17-26-L187 \
  --output-dir /Users/seancheick/Documents/DataSetDsld/builds/release_output
```

## 6. Integrated per-pair build + release assembly

Run per-pair builds and assemble a release in one workflow:

```bash
python3 scripts/build_all_final_dbs.py \
  --scan-dir scripts \
  --change-journal /Users/seancheick/Documents/DataSetDsld/builds/pair_change_journal.json \
  --per-pair-output-root /Users/seancheick/Documents/DataSetDsld/builds/pair_outputs \
  --assemble-release-output /Users/seancheick/Documents/DataSetDsld/builds/release_output
```

## 6A. Product image extraction (DSLD label PDFs → WebP)

Generates the fallback product images served when OpenFoodFacts has nothing
for a UPC. Reads `products_core.image_url` from `pharmaguide_core.db`,
downloads each DSLD label PDF, renders page 1, and saves as WebP into
`<output-dir>/`. Writes `product_image_index.json` with filename + size +
sha256 for every successful render.

These WebPs are picked up automatically by `sync_to_supabase.py` (Section 7)
and uploaded to the `product-images` bucket. Flutter then references them
via `products_core.image_thumbnail_url`.

**Source script:** `scripts/extract_product_images.py`
**Inputs:** `pharmaguide_core.db` (rows where `image_url LIKE '%.pdf'`)
**Outputs:** `<output-dir>/<dsld_id>.webp` + `<output-dir>/product_image_index.json`
**PDF cache:** `/tmp/dsld_pdf_cache/` (reused across runs to avoid re-downloads)

### Standard run

```bash
python3 scripts/extract_product_images.py \
  --db-path scripts/dist/pharmaguide_core.db \
  --output-dir scripts/dist/product_images
```

This is **idempotent** — already-rendered `<dsld_id>.webp` files are
skipped via a pre-scan, so reruns only process new/missing products.

### Force a full re-render (e.g., after changing render settings)

Use `--force-rerender` to ignore the skip-on-disk check. Existing files
are overwritten. The PDF cache is still reused, so no re-downloads.

```bash
python3 scripts/extract_product_images.py \
  --db-path scripts/dist/pharmaguide_core.db \
  --output-dir scripts/dist/product_images \
  --force-rerender
```

Use this when you've changed `RENDER_ZOOM`, `MAX_WIDTH_PX`, or
`WEBP_QUALITY` and want every image regenerated at the new settings.

### Tuning runtime concurrency (rarely needed)

Defaults are conservative to avoid NIH 429 rate limits. Bump only if you
have a clean slate and want to risk getting blocked:

```bash
python3 scripts/extract_product_images.py \
  --db-path scripts/dist/pharmaguide_core.db \
  --output-dir scripts/dist/product_images \
  --max-workers 4 \
  --batch-delay 1.0
```

### Image quality settings — what to tweak and what each does

The three knobs live as module-level constants near the top of
`scripts/extract_product_images.py`. There is no CLI flag for them
because changing quality is a deliberate, infrequent decision that
implies a full `--force-rerender`.

```python
# scripts/extract_product_images.py:38-43
PDF_CACHE_DIR = "/tmp/dsld_pdf_cache"
MAX_CONCURRENT_DOWNLOADS = 2          # NIH-friendly concurrency
BATCH_DELAY_SECONDS = 1.5              # Pause between batches (rate-limit cushion)
WEBP_QUALITY = 88                      # ← image-quality knob #1
MAX_WIDTH_PX = 900                     # ← image-quality knob #2
RENDER_ZOOM = 8.0                      # ← image-quality knob #3
```

**`RENDER_ZOOM` (currently 8.0)** — multiplier applied to PDF source
resolution before LANCZOS downscale. Higher = sharper edges and text.
- 2.0 = 144 DPI source render (visibly blurry)
- 4.0 = 288 DPI (readable)
- **8.0 = 576 DPI (current, sharp)**
- 10+ = diminishing returns; bottlenecks on raster content baked into
  the PDF (scanned label panels) regardless of render DPI
- **File-size impact: NEAR ZERO.** Output dimensions are fixed at
  `MAX_WIDTH_PX`, so encoded WebP size depends on content complexity,
  not source render DPI. Bump this freely.
- **Speed impact: noticeable.** Zoom 8 renders are ~4× slower than
  zoom 4 per image. NIH download is still the bottleneck though.

**`MAX_WIDTH_PX` (currently 900)** — output width in pixels. Aspect
ratio is preserved. This is the dominant file-size driver.
- 600 = ~25 KB/img, ~200 MB total (was the v1 default — too small,
  visibly soft on retina screens)
- **900 = ~80 KB/img, ~640 MB total (current)**
- 1200 = ~140 KB/img, ~1.1 GB total
- **File-size impact: scales linearly with pixel count**, so width 1200
  is ~75% larger than width 900.
- **Speed impact: small** — encoding is fast.

**`WEBP_QUALITY` (currently 88)** — WebP encoder quality, 0-100.
- 80 = small files, soft text edges (was the v1 default)
- 85 = balanced (≈ -10% size vs 88, slightly softer text)
- **88 = sharp text edges, modest file size (current)**
- 92+ = barely-perceptible improvement, ~25% bigger files
- **File-size impact: ~+10% per +3 quality points**
- **Speed impact: trivial.**

**Recommended approach to tweak quality:**

1. Edit the constants in `scripts/extract_product_images.py:38-43`
2. Sample-render a handful of products to a test directory:

```bash
python3 -c "
import sys, os, glob
sys.path.insert(0, 'scripts')
from extract_product_images import pdf_page1_to_webp
os.makedirs('/tmp/quality_test', exist_ok=True)
# Render the first 8 cached PDFs with current settings
for pdf in sorted(glob.glob('/tmp/dsld_pdf_cache/*.pdf'))[:8]:
    dsld = os.path.basename(pdf).replace('.pdf', '')
    out = f'/tmp/quality_test/{dsld}.webp'
    size = pdf_page1_to_webp(pdf, out)
    print(f'  {dsld}: {size/1024:.1f} KB')
"
open /tmp/quality_test/    # visual inspect
```

3. If satisfied, full re-render with `--force-rerender` (see above).
4. Resync to Supabase (Section 7) — `sync_to_supabase.py` detects size
   changes and re-uploads everything.

### Settings history

| Date | RENDER_ZOOM | MAX_WIDTH_PX | WEBP_QUALITY | Avg KB | Notes |
|---|---|---|---|---|---|
| original | 2.0 | 600 | 80 | ~25 | Visibly blurry, text unreadable on retina |
| 2026-04-29 | 4.0 | 900 | 85 | ~60 | First sharpening pass — readable |
| 2026-04-30 | 8.0 | 900 | 88 | ~80 | Current — sharp text, modest file growth |

### Troubleshooting

- **NIH 429 Client Error: Too Many Requests** — the script auto-retries
  with exponential backoff (5s → 15s → 45s → 135s, max 4 attempts) and
  honors `Retry-After` headers. If 429s persist, lower `--max-workers`
  to 1 and bump `--batch-delay` to 3.0.
- **Some products fail with 404** — those PDFs no longer exist on NIH's
  CDN (discontinued products). Expected for a small fraction; they stay
  on the placeholder fallback in Flutter.
- **Images look fine locally but blurry in the app** — check that
  Supabase has the latest WebPs (run `sync_to_supabase.py`) and that
  the Flutter side isn't holding onto a stale `cached_network_image`
  cache. Force-clear app cache or bump the URL with a version query
  string.
- **PDF cache eats too much disk** — `/tmp/dsld_pdf_cache/` is ~7,000
  PDFs at ~500 KB each (~3.5 GB). Safe to delete (`rm -rf
  /tmp/dsld_pdf_cache`); next run will re-download from NIH. Keep it
  if you plan to re-render soon.

---

## 7. Sync build output to Supabase

Always point at the assembled `release_output` directory, not a single-brand output.

Dry run (confirm what would upload before touching Supabase):

```bash
python3 scripts/sync_to_supabase.py \
  ~/Documents/DataSetDsld/builds/release_output \
  --dry-run
```

Real sync:

```bash
python3 scripts/sync_to_supabase.py \
  ~/Documents/DataSetDsld/builds/release_output
```

Tune upload concurrency and retries:

```bash
python3 scripts/sync_to_supabase.py \
  ~/Documents/DataSetDsld/builds/release_output \
  --max-workers 8 \
  --retry-count 3 \
  --retry-base-delay 1.0
```

What the sync does:

- uploads `pharmaguide_core.db` to `pharmaguide/v{db_version}/`
- uploads `detail_index.json`
- uploads hashed detail blobs to `pharmaguide/shared/details/sha256/{prefix}/{hash}.json`
- skips unchanged hashed blobs already present remotely
- inserts a new `export_manifest` row; if the version already exists, exits "Already up to date"

## 7A. Recommended release pattern

Always sync the assembled release, never a single-brand output. The app reads one coherent product universe; a single-brand sync would replace the entire catalog with just that brand.

Standard flow (all-brands full release):

```bash
# Build + assemble (one command)
python3 scripts/build_all_final_dbs.py \
  --scan-dir scripts/products \
  --per-pair-output-root ~/Documents/DataSetDsld/builds/pair_outputs \
  --assemble-release-output ~/Documents/DataSetDsld/builds/release_output

# Package artifacts
python3 scripts/release_catalog_artifact.py \
  --input-dir ~/Documents/DataSetDsld/builds/release_output
python3 scripts/release_interaction_artifact.py

# Sync
python3 scripts/sync_to_supabase.py \
  ~/Documents/DataSetDsld/builds/release_output --dry-run
python3 scripts/sync_to_supabase.py \
  ~/Documents/DataSetDsld/builds/release_output
```

Partial release (one or two brands only, then re-assemble everything):

```bash
# Rebuild just the changed brands
python3 scripts/build_all_final_dbs.py \
  --scan-dir scripts/products \
  --include-prefix Thorne \
  --include-prefix Nutricost \
  --per-pair-output-root ~/Documents/DataSetDsld/builds/pair_outputs \
  --assemble-release-output ~/Documents/DataSetDsld/builds/release_output
# Assembly reads ALL pair_outputs (not just the two rebuilt), so the release
# still contains all 15 brands.
```

## 7B. When to use `--cleanup`

`--cleanup` runs immediately after a successful sync and prunes old Supabase Storage versions.

```bash
python3 scripts/sync_to_supabase.py \
  ~/Documents/DataSetDsld/builds/release_output \
  --cleanup
```

What it does:

1. Lists all versions in the `export_manifest` table (newest first)
2. Keeps the last **2** versions by default (current + one rollback)
3. Deletes Storage objects under `pharmaguide/v{old_version}/` for anything older
4. Detects and deletes **orphaned detail blobs** — hashed blobs in `shared/details/` that are no longer referenced by the current `detail_index.json`
5. Optionally prunes the manifest table rows (`--cleanup-db` flag)

Keep more versions (e.g. 3) if you want a wider rollback window:

```bash
python3 scripts/sync_to_supabase.py \
  ~/Documents/DataSetDsld/builds/release_output \
  --cleanup --cleanup-keep 3
```

**When to use it:**

| Situation                               | Use `--cleanup`?                                                    |
| --------------------------------------- | ------------------------------------------------------------------- |
| Regular release (every pipeline run)    | Yes — keeps Storage tidy                                            |
| After a schema bump (many new blobs)    | Yes — orphan blobs from old schema get removed                      |
| Debugging / uncertain about the release | No — run without first, verify app works, then run with `--cleanup` |
| Rollback scenario                       | No — you want the old version still in Storage                      |

Run `cleanup_old_versions.py` standalone for a dry-run preview without syncing:

```bash
python3 scripts/cleanup_old_versions.py          # dry-run, keep 2
python3 scripts/cleanup_old_versions.py --execute # actually delete
python3 scripts/cleanup_old_versions.py --execute --cleanup-db  # also prune manifest rows
```

## 8. DSLD API tooling

### What it does

Fetches supplement labels from the NIH DSLD API and writes them into the same raw-label contract used by manual downloads. The goal is for the existing pipeline (clean -> enrich -> score) to process API-fetched labels without a separate downstream path.

### Status: Live and verified

- API base URL: `https://api.ods.od.nih.gov/dsld/v9`
- Live structured version check passed from your machine
- Live probe passed: **100% parity** between API output and one known manual download (`13418`)
- `sync-brand --brand "Olly"` fetched and wrote `186/186` labels successfully
- API test coverage currently passing:
- `18` tests in `scripts/tests/test_dsld_api_client.py`
- `20` tests in `scripts/tests/test_dsld_api_sync.py`

## 9. Valyu evidence watchtower

### What it is

A separate, review-only evidence discovery tool for curator workflows.

It helps scan:

- `backed_clinical_studies.json`
- `ingredient_quality_map.json` gaps
- `harmful_additives.json`
- `banned_recalled_ingredients.json`

It writes report files only. It does **not** change production source files and does **not** affect scoring directly.

### What it is not

- not part of `clean -> enrich -> score`
- not a canonical evidence writer
- not allowed to auto-apply updates

### Commands

Run one domain:

```bash
.venv/bin/python scripts/api_audit/valyu_evidence_discovery.py clinical-refresh
.venv/bin/python scripts/api_audit/valyu_evidence_discovery.py iqm-gap-scan
.venv/bin/python scripts/api_audit/valyu_evidence_discovery.py harmful-refresh
.venv/bin/python scripts/api_audit/valyu_evidence_discovery.py recall-refresh
```

Run all domains:

```bash
.venv/bin/python scripts/api_audit/valyu_evidence_discovery.py all
```

Optional target cap:

```bash
.venv/bin/python scripts/api_audit/valyu_evidence_discovery.py clinical-refresh --limit 10
```

Optional output dir override:

```bash
.venv/bin/python scripts/api_audit/valyu_evidence_discovery.py clinical-refresh \
  --output-dir /tmp/valyu-watchtower
```

### Outputs

Default report location:

- `scripts/api_audit/reports/valyu/`

Each run writes:

- `*-raw-search-report.json`
- `*-review-queue.json`
- `*-summary.md`

Use this tool to find review candidates, then manually promote approved findings into canonical source files through the normal audited workflow.

### Files

- `scripts/dsld_api_client.py` — Low-level API client (retry, rate limit, circuit breaker, disk cache)
- `scripts/dsld_api_sync.py` — CLI with 6 subcommands
- `scripts/tests/test_dsld_api_client.py` — client and normalization tests
- `scripts/tests/test_dsld_api_sync.py` — sync CLI and parity helper tests

### Quick start

Check structured API version metadata:

```bash
python3 scripts/dsld_api_sync.py check-version
```

This calls the real deployed DSLD version endpoint:

- `https://api.ods.od.nih.gov/dsld/version`

### Canonical form corpus

The long-term recommended DSLD raw corpus is now canonical-by-form:

```text
/Users/seancheick/Documents/DataSetDsld/forms/gummies/*.json
/Users/seancheick/Documents/DataSetDsld/forms/softgels/*.json
/Users/seancheick/Documents/DataSetDsld/forms/capsules/*.json
/Users/seancheick/Documents/DataSetDsld/forms/bars/*.json
/Users/seancheick/Documents/DataSetDsld/forms/powders/*.json
/Users/seancheick/Documents/DataSetDsld/forms/lozenges/*.json
/Users/seancheick/Documents/DataSetDsld/forms/tablets-pills/*.json
/Users/seancheick/Documents/DataSetDsld/forms/liquids/*.json
/Users/seancheick/Documents/DataSetDsld/forms/other/*.json
```

Identity rule:

- `dsld_id` is the only product identity key
- if a label is discovered through both a brand pull and a form pull, it is still one product
- overlap is deduped by `dsld_id`

Recommended permanent layout if you want this outside the repo and under your existing dataset root:

```text
/Users/seancheick/Documents/DataSetDsld/
/Users/seancheick/Documents/DataSetDsld/forms/
/Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json
/Users/seancheick/Documents/DataSetDsld/delta/<brand>/<timestamp>/
/Users/seancheick/Documents/DataSetDsld/reports/<brand>/<timestamp>.json
/Users/seancheick/Documents/DataSetDsld/staging/
```

Example:

```text
/Users/seancheick/Documents/DataSetDsld/
/Users/seancheick/Documents/DataSetDsld/forms/gummies/*.json
/Users/seancheick/Documents/DataSetDsld/forms/softgels/*.json
/Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json
/Users/seancheick/Documents/DataSetDsld/delta/olly/2026-03-30T15-04-05/*.json
/Users/seancheick/Documents/DataSetDsld/reports/olly/2026-03-30T15-04-05.json
/Users/seancheick/Documents/DataSetDsld/staging/
```

Meaning:

- `forms/` = canonical raw source of truth
- `state/` = shared sync memory
- `delta/` = dated new/changed raw sets for each run
- `reports/` = dated sync audit reports
- `staging/` = optional temporary seed/review folders

Migration note:

- your existing manually downloaded flat brand folders still work as raw input for the cleaner
- they already match the raw DSLD contract closely enough for the downstream pipeline
- but they are not the best long-term home for the new `sync-delta` workflow
- for long-term maintenance, use canonical-by-form storage plus one shared state file
- use brand folders only as legacy inputs, snapshots, or temporary review sets
- `staging/` is optional and should not be treated as long-term truth

Recommended market status values:

- `--status 0` = off market only
- `--status 1` = on market only
- `--status 2` = all

Recommended default:

- use `--status 2` for canonical corpus syncs so discontinued products remain available for scans

### Form code table

- `e0176` = gummies
- `e0161` = softgels
- `e0159` = capsules
- `e0164` = bars
- `e0162` = powders
- `e0174` = lozenges
- `e0155` = tablets-pills
- `e0165` = liquids
- `e0172` = other
- `e0177` = other

### Commands

**probe** — Fetch one label and optionally compare against a manual download:

```bash
# Just fetch and display
python3 scripts/dsld_api_sync.py probe --id 13418

# Compare against a reference file (parity check)
python3 scripts/dsld_api_sync.py probe \
  --id 13418 \
  --reference /Users/seancheick/Documents/DataSetDsld/Nordic-Naturals-2-17-26-L511/13418.json
```

**sync-brand** — Fetch all labels for a brand into a flat directory:

```bash
python3 scripts/dsld_api_sync.py sync-brand \
  --brand "Nordic Naturals" \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json
```

If you also want a flat staging copy for review:

```bash
python3 scripts/dsld_api_sync.py sync-brand \
  --brand "Nordic Naturals" \
  --status 2 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json \
  --output-dir /Users/seancheick/Documents/DataSetDsld/staging/brands/nordic-naturals
```

The canonical form corpus or any staging directory can then be fed directly to the pipeline:

```bash
cd scripts
python3 clean_dsld_data.py \
  --input-dir /Users/seancheick/Documents/DataSetDsld/staging/brands/nordic-naturals \
  --output-dir /Users/seancheick/Documents/DataSetDsld/output_nordic_seed_cleaned \
  --config config/cleaning_config.json
```

Note:

- `clean_dsld_data.py` currently expects to be run from the `scripts/` directory because of relative-path assumptions in its config/reference-data handling
- `sync-brand`, `sync-filter`, and `sync-delta` now paginate through all matching results by default
- use `--limit N` only when you want to intentionally cap discovery for a test or partial run

**refresh-ids** — Re-fetch specific label IDs (e.g., after an audit fix):

```bash
python3 scripts/dsld_api_sync.py refresh-ids \
  --ids 13418 241695 182215 \
  --output-dir /Users/seancheick/Documents/DataSetDsld/staging/refresh-ids
```

**sync-query** — Fetch labels matching a search query:

```bash
python3 scripts/dsld_api_sync.py sync-query \
  --query "vitamin d" \
  --output-dir /Users/seancheick/Documents/DataSetDsld/staging/query-vitamin-d \
  --limit 50
```

**sync-filter** — Fetch labels through DSLD filter fields and route them into the canonical form corpus:

Pull all gummies into the canonical form corpus:

```bash
python3 scripts/dsld_api_sync.py sync-filter \
  --supplement-form e0176 \
  --status 2 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json
```

Pull only on-market softgels and keep a staging copy:

```bash
python3 scripts/dsld_api_sync.py sync-filter \
  --supplement-form e0161 \
  --status 1 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json \
  --staging-dir /Users/seancheick/Documents/DataSetDsld/staging/forms/softgels
```

Pull products containing melatonin:

```bash
python3 scripts/dsld_api_sync.py sync-filter \
  --ingredient-name melatonin \
  --status 2 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json
```

Pull a recent date window:

```bash
python3 scripts/dsld_api_sync.py sync-filter \
  --date-start 2026-01-01 \
  --date-end 2026-03-30 \
  --status 2 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json
```

Important:

- `sync-filter` updates canonical form folders when `--canonical-root` is provided
- `--staging-dir` is optional and creates a flat review/work folder
- no `--limit` means fetch all matching labels across paginated API results
- `--limit N` means stop discovery after `N` labels
- date windows are good for newly added labels, not all label changes

**sync-delta** — Fetch only new or changed labels based on the shared state file:

Delta-sync a brand and write a cleaner-ready delta set:

```bash
python3 scripts/dsld_api_sync.py sync-delta \
  --brand "Olly" \
  --status 2 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json \
  --delta-output-dir /Users/seancheick/Documents/DataSetDsld/delta/olly \
  --dated-delta \
  --report-dir /Users/seancheick/Documents/DataSetDsld/reports/olly
```

Delta-sync gummies without producing a pipeline-ready delta folder:

```bash
python3 scripts/dsld_api_sync.py sync-delta \
  --supplement-form e0176 \
  --status 2 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json
```

Important:

- with `--delta-output-dir`, changed/new labels are written there as a flat cleaner-ready set
- without `--delta-output-dir`, canonical form folders and state are updated only
- no `--limit` means fetch all matching labels across paginated API results
- `--limit N` means stop discovery after `N` labels
- off-market products are retained in canonical storage and continue through scoring/build
- if the state file does not exist yet, the first `sync-delta` run behaves like an initial full seed for that discovery lane
- after that first seed, later runs only write newly changed/new labels into the delta directory
- if you already have an old flat folder like `/Users/seancheick/Documents/DataSetDsld/Olly`, that does not break anything, but it does not replace the shared sync state
- `--dated-delta` is the recommended mode: it writes each run into a fresh timestamped subdirectory under `--delta-output-dir`
- example resolved path:
  - `/Users/seancheick/Documents/DataSetDsld/delta/olly/2026-03-30T15-04-05/`
- this avoids stale files from previous runs making a no-change delta look non-empty
- `--report-dir` writes a JSON run report for auditing and review
- example report path:
  - `/Users/seancheick/Documents/DataSetDsld/reports/olly/2026-03-30T15-04-05.json`
- the report includes:
  - candidate count
  - new / changed / unchanged counts
  - skipped and failed IDs
  - off-market IDs seen in the run
  - resolved delta directory for that run

**import-local** — Import local/manual DSLD raw JSON into the same canonical form/state/delta system:

Use this when the API is unavailable or when you downloaded raw JSON manually from DSLD and still want to update:

- `forms/`
- `state/dsld_sync_state.json`
- optional dated `delta/`
- optional JSON `reports/`

Example:

```bash
python3 scripts/dsld_api_sync.py import-local \
  --input-dir /Users/seancheick/Documents/DataSetDsld/manual/softgels_batch_01 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json \
  --delta-output-dir /Users/seancheick/Documents/DataSetDsld/delta/manual-softgels \
  --dated-delta \
  --report-dir /Users/seancheick/Documents/DataSetDsld/reports/manual-softgels
```

Important:

- `import-local` does not use the DSLD API
- it reads local JSON recursively, so both flat and nested folders work
- it routes labels into canonical form buckets using the same form logic as API sync
- it updates the same shared state file used by API sync
- it can produce a delta folder and report just like `sync-delta`
- API sync and local import stay independent operationally, but share the same canonical corpus/state model
- payload change detection ignores provenance-only fields like `_source` and `src`, so importing the same label from API vs manual raw files does not create false diffs by itself

### Recommended operator workflows

Use these as the default day-to-day commands.

Standard workflow:

- keep `forms/`, `state/`, `delta/`, and `reports/`
- use `staging/` only when you explicitly want a temporary flat seed/review folder
- after initial seeding, most ongoing maintenance should be `sync-delta`

### Operator cheat sheet

Use this section when you just want the exact commands.

#### Brand, first time

Seed the canonical corpus and create a flat working folder:

```bash
python3 scripts/dsld_api_sync.py sync-brand \
  --brand "Olly" \
  --status 2 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json \
  --output-dir /Users/seancheick/Documents/DataSetDsld/staging/brands/olly
```

Run pipeline on that first-time brand folder:

```bash
python3 scripts/run_pipeline.py \
  --raw-dir /Users/seancheick/Documents/DataSetDsld/staging/brands/Olly \
  --output-prefix /Users/seancheick/Documents/DataSetDsld/output_olly_seed
```

#### Brand, second time or later

Fetch only new/changed products:

```bash
python3 scripts/dsld_api_sync.py sync-delta \
  --brand "Olly" \
  --status 2 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json \
  --delta-output-dir /Users/seancheick/Documents/DataSetDsld/delta/olly \
  --dated-delta \
  --report-dir /Users/seancheick/Documents/DataSetDsld/reports/olly
```

Then run pipeline on the printed dated delta folder:

```bash
python3 scripts/run_pipeline.py \
  --raw-dir /Users/seancheick/Documents/DataSetDsld/delta/olly/2026-03-30T01-49-58 \
  --output-prefix /Users/seancheick/Documents/DataSetDsld/output_olly_2026-03-30T01-49-58
```

#### 2. First-time category/form seed without staging

This is the simpler default for form/category pulls.

Example: first-time gummies seed directly into the canonical form bucket:

```bash
python3 scripts/dsld_api_sync.py sync-filter \
  --supplement-form e0176 \
  --status 2 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json
```

Then run the pipeline directly on that canonical form bucket:

```bash
python3 scripts/run_pipeline.py \
  --raw-dir /Users/seancheick/Documents/DataSetDsld/forms/gummies \
  --output-prefix /Users/seancheick/Documents/DataSetDsld/output_gummies_seed
```

#### 2A. First-time category/form seed with staging

If you want a flat first-time working set:

```bash
python3 scripts/dsld_api_sync.py sync-filter \
  --supplement-form e0176 \
  --status 2 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json \
  --staging-dir /Users/seancheick/Documents/DataSetDsld/staging/forms/gummies
```

Run pipeline on that first-time form folder:

```bash
python3 scripts/run_pipeline.py \
  --raw-dir /Users/seancheick/Documents/DataSetDsld/staging/forms/gummies \
  --output-prefix /Users/seancheick/Documents/DataSetDsld/output_gummies_seed
```

#### 2B. Form/category, second time or later

Fetch only new/changed products:

```bash
python3 scripts/dsld_api_sync.py sync-delta \
  --supplement-form e0176 \
  --status 2 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json \
  --delta-output-dir /Users/seancheick/Documents/DataSetDsld/delta/gummies \
  --dated-delta \
  --report-dir /Users/seancheick/Documents/DataSetDsld/reports/gummies
```

Then run pipeline on the printed dated delta folder:

```bash
python3 scripts/run_pipeline.py \
  --raw-dir /Users/seancheick/Documents/DataSetDsld/delta/gummies/2026-03-30T01-49-58 \
  --output-prefix /Users/seancheick/Documents/DataSetDsld/output_gummies_2026-03-30T01-49-58
```

#### 3. Manual/local import fallback

Use this when the DSLD API is unavailable but you already downloaded raw DSLD JSON manually.

```bash
python3 scripts/dsld_api_sync.py import-local \
  --input-dir /Users/seancheick/Documents/DataSetDsld/manual/softgels_batch_01 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json \
  --delta-output-dir /Users/seancheick/Documents/DataSetDsld/delta/manual-softgels \
  --dated-delta \
  --report-dir /Users/seancheick/Documents/DataSetDsld/reports/manual-softgels
```

Then run pipeline on the printed dated delta folder:

```bash
python3 scripts/run_pipeline.py \
  --raw-dir /Users/seancheick/Documents/DataSetDsld/delta/manual-softgels/2026-03-30T01-49-58 \
  --output-prefix /Users/seancheick/Documents/DataSetDsld/output_manual_softgels_2026-03-30T01-49-58
```

#### 5. What to process after each kind of sync

- `sync-brand` with `--output-dir`:
  - process the `--output-dir` folder
- `sync-filter` with `--staging-dir`:
  - process the `--staging-dir` folder
- `sync-filter` with only `--canonical-root` and no staging folder:
  - process the specific canonical form bucket you just seeded, such as `/Users/seancheick/Documents/DataSetDsld/forms/gummies`
- `import-local` with `--delta-output-dir --dated-delta`:
  - process the printed `Delta directory:` dated folder
- `sync-delta` with `--delta-output-dir --dated-delta`:
  - process the printed `Delta directory:` dated folder
- `sync-brand` with only `--canonical-root` and no staging folder:
  - this updates the canonical corpus only
  - it does not create a clean brand-only pipeline input folder by itself

#### 6. How to read the result

- if a later `sync-delta` run prints `delta=0`, there were no new/changed labels for that run
- the dated delta folder for that run may still exist as an empty or near-empty audit artifact
- the JSON report in `--report-dir` is the clean place to check:
  - `new_count`
  - `changed_count`
  - `unchanged_count`
  - `failed_ids`
  - `off_market_ids`

### Batch runner with the new structure

`batch_run_all_datasets.sh` can still be useful, but it works best when you point it at a subtree that contains only flat dataset folders you actually want to process.

Recommended usage:

- top-level legacy folders only:
  - `bash batch_run_all_datasets.sh --targets Thorne,Olly`
- first-time brand seeds in staging:
  - `bash batch_run_all_datasets.sh --root "$HOME/Documents/DataSetDsld/staging/brands"`
- first-time form seeds in staging:
  - `bash batch_run_all_datasets.sh --root "$HOME/Documents/DataSetDsld/staging/forms"`
- one brand's dated delta runs:
  - `bash batch_run_all_datasets.sh --root "$HOME/Documents/DataSetDsld/delta/olly"`
- all brand delta roots is not recommended directly because `delta/` contains brand folders, not dated run folders

Important:

- when run at top-level `DataSetDsld/`, the script now skips:
  - `forms/`
  - `state/`
  - `delta/`
  - `reports/`
  - `staging/`
- that makes top-level usage safer for your old legacy flat dataset folders
- for the new workflow, `--root` is the clearer option

Examples:

Run all staged brand seeds:

```bash
bash batch_run_all_datasets.sh \
  --root "$HOME/Documents/DataSetDsld/staging/brands"
```

Run all dated Olly delta folders:

```bash
bash batch_run_all_datasets.sh \
  --root "$HOME/Documents/DataSetDsld/delta/olly"
```

Run only score for dated Olly deltas:

```bash
bash batch_run_all_datasets.sh \
  --root "$HOME/Documents/DataSetDsld/delta/olly" \
  --stages score
```

**verify-db** — Sample-verify existing raw files against the API (non-destructive, never overwrites):

```bash
python3 scripts/dsld_api_sync.py verify-db \
  --input-dir /Users/seancheick/Documents/DataSetDsld/Nordic-Naturals-2-17-26-L511 \
  --sample-size 10
```

**--snapshot mode** — Write to a timestamped subdirectory instead of overwriting:

```bash
python3 scripts/dsld_api_sync.py sync-brand \
  --brand "Olly" \
  --output-dir /Users/seancheick/Documents/DataSetDsld/staging/brands/olly \
  --snapshot
# Writes to: /Users/seancheick/Documents/DataSetDsld/staging/brands/olly/_snapshots/20260329_143000/
```

### End-to-end workflow: recommended delta path

```bash
# 1. Update a brand and create a dated delta folder + report
python3 scripts/dsld_api_sync.py sync-delta \
  --brand "Thorne" \
  --status 2 \
  --canonical-root /Users/seancheick/Documents/DataSetDsld/forms \
  --state-file /Users/seancheick/Documents/DataSetDsld/state/dsld_sync_state.json \
  --delta-output-dir /Users/seancheick/Documents/DataSetDsld/delta/thorne \
  --dated-delta \
  --report-dir /Users/seancheick/Documents/DataSetDsld/reports/thorne

# 2. Run the pipeline on the printed dated delta folder
python3 scripts/run_pipeline.py \
  --raw-dir /Users/seancheick/Documents/DataSetDsld/delta/thorne/2026-03-30T01-49-58 \
  --output-prefix /Users/seancheick/Documents/DataSetDsld/output_thorne_2026-03-30T01-49-58

# 3. Build final DB
python3 scripts/build_final_db.py \
  --enriched-dir /Users/seancheick/Documents/DataSetDsld/output_thorne_2026-03-30T01-49-58_enriched/enriched \
  --scored-dir /Users/seancheick/Documents/DataSetDsld/output_thorne_2026-03-30T01-49-58_scored/scored \
  --output-dir /Users/seancheick/Documents/DataSetDsld/final_db_output_thorne_2026-03-30T01-49-58

# 4. Sync to Supabase
python3 scripts/sync_to_supabase.py /Users/seancheick/Documents/DataSetDsld/final_db_output_thorne_2026-03-30T01-49-58
```

### How it works

- `dsld_api_sync.py` now supports two ingestion paths:
  - API-driven sync via `sync-brand`, `sync-filter`, and `sync-delta`
  - local/manual raw import via `import-local`
- both paths normalize labels into the same raw-label contract and route them into the same canonical `forms/` corpus
- both paths update the same shared `state/dsld_sync_state.json`
- optional dated delta folders and JSON reports work for both `sync-delta` and `import-local`
- payload change detection ignores provenance-only fields like `_source` and `src`, so API vs manual copies of the same label do not create false diffs by themselves
- the pipeline processes the raw JSON the same way regardless of whether the files came from API sync or local import
- Rate limited to ~6.6 requests/second (0.15s delay) to respect NIH API limits
- Retries failed requests up to 4 times with exponential backoff
- Circuit breaker trips after 3 consecutive failures

## 9. Verification commands

Core pipeline verification:

```bash
pytest \
  scripts/tests/test_build_final_db.py \
  scripts/tests/test_build_all_final_dbs.py \
  scripts/tests/test_sync_to_supabase.py \
  scripts/tests/test_supabase_client.py \
  scripts/tests/test_assemble_final_db_release.py \
  scripts/tests/test_generate_pair_change_journal.py \
  scripts/tests/test_dsld_api_client.py \
  scripts/tests/test_dsld_api_sync.py -q
```

Syntax verification:

```bash
python3 -m py_compile \
  scripts/build_final_db.py \
  scripts/build_all_final_dbs.py \
  scripts/sync_to_supabase.py \
  scripts/supabase_client.py \
  scripts/assemble_final_db_release.py \
  scripts/generate_pair_change_journal.py \
  scripts/dsld_api_client.py \
  scripts/dsld_api_sync.py
```

## 10. Important operating notes

- The pipeline architecture is now more scalable on the build/sync side than before:
  - incremental pair selection
  - per-pair cached builds
  - assembled full releases
  - hashed shared detail-blob sync
  - concurrent/retrying uploads
- The Flutter-related docs and Supabase schema were updated to match the corrected export/sync model.
- The DSLD API path is additive, not a replacement:
  - manual raw JSON still works
  - API-fetched raw JSON now has:
    - live connectivity verification
    - one successful parity probe against a real manual label
    - one successful live brand sync for `Olly`
  - broader parity confidence should come from more real-label probes over time, not one label
  - use `probe --reference` any time the API response shape might have changed

---

## 11. Core Pipeline Scripts — Quick Reference

These are the main scripts that make up the 3-stage pipeline (Clean → Enrich → Score) plus supporting utilities. The ops doc sections above (§1–§8) cover the build, sync, and DSLD API workflows. This section covers everything else.

### 11.1 Pipeline Stages

| Script                     | Stage        | What it does                                                                                            |
| -------------------------- | ------------ | ------------------------------------------------------------------------------------------------------- |
| `run_pipeline.py`          | Orchestrator | Runs Clean → Enrich → Score in sequence. Use `--raw-dir` and `--output-prefix`.                         |
| `clean_dsld_data.py`       | Stage 1      | Normalizes raw DSLD JSON labels. Strips dead fields, normalizes units, extracts ingredients.            |
| `enrich_supplements_v3.py` | Stage 2      | Matches ingredients against IQM, classifies forms, resolves aliases, adds clinical data. ~12K lines.    |
| `score_supplements.py`     | Stage 3      | 80-point arithmetic scoring engine. Reads enriched JSON, writes scored output with verdicts. ~3K lines. |

### 11.2 Build & Release

| Script                            | What it does                                                                                                                                           |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `build_final_db.py`               | Converts scored JSON → SQLite `pharmaguide_core.db` + detail blobs + manifest.                                                                         |
| `build_all_final_dbs.py`          | Auto-discovers enriched/scored pairs, builds all or selected brands. Supports `--changed-only`, `--per-pair-output-root`, `--assemble-release-output`. |
| `assemble_final_db_release.py`    | Merges per-pair build outputs into one combined release artifact.                                                                                      |
| `release_catalog_artifact.py`     | Validates final DB + manifest, stages to `scripts/dist/` atomically.                                                                                   |
| `release_interaction_artifact.py` | Same as above but for the interaction DB. Stages `scripts/interaction_db_output/` → `scripts/dist/`.                                                   |
| `cleanup_old_versions.py`         | Removes old PharmaGuide versions from Supabase Storage. Use `--dry-run` first.                                                                         |

### 11.3 Interaction DB Pipeline — End to End

The interaction DB is a separate SQLite artifact (`interaction_db.sqlite`) that ships alongside the catalog DB. It powers the app's drug-supplement safety warnings, "Because you're taking X" personalization, and research evidence display.

#### The full picture: pipeline → app → user

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         PIPELINE REPO (dsld_clean)                       │
│                                                                          │
│  DATA SOURCES (you edit these)                                           │
│  ├── scripts/data/curated_interactions/                                  │
│  │   ├── curated_interactions_v1.json     99 drug↔sup + sup↔sup pairs   │
│  │   └── med_med_pairs_v1.json            29 drug↔drug pairs            │
│  ├── scripts/data/drug_classes.json        24 classes, 693 RxCUIs        │
│  └── ~/Downloads/Supp ai DB/              supp.ai raw dump (245 MB)      │
│                                                                          │
│  VERIFICATION (live API calls — nothing passes without this)             │
│  ┌─────────────────────────────────────────────────────────┐             │
│  │ verify_interactions.py                                   │             │
│  │                                                          │             │
│  │  Check 1: JSON schema — required fields, valid enums    │             │
│  │  Check 2: Duplicate ID detection                        │             │
│  │  Check 3: RXCUI → RxNorm API (is this a real drug?)     │             │
│  │  Check 4: CUI → UMLS API (is this a real substance?)    │             │
│  │  Check 5: CUI → canonical_id mapping (IQM + botanicals  │             │
│  │           + banned_recalled + harmful_additives)         │             │
│  │  Check 6: Drug class expansion (class:statins → 8 drugs)│             │
│  │  Check 7: Direction normalization (drug always agent1)   │             │
│  │  Check 8: Severity normalization (Major → avoid)         │             │
│  │  Check 9: Evidence gate (Major+ MUST have source URL)    │             │
│  │  Check 10: PMID extraction from source URLs              │             │
│  │                                                          │             │
│  │  EXIT CODE 0 = all clear    EXIT CODE 1 = build blocked │             │
│  └─────────────────────┬───────────────────────────────────┘             │
│                        │                                                 │
│  CONTENT VERIFICATION (proves citations match claims)                    │
│  ┌─────────────────────────────────────────────────────────┐             │
│  │ verify_all_citations_content.py                          │             │
│  │                                                          │             │
│  │  For every PubMed PMID:                                 │             │
│  │  1. Fetch actual article title + abstract via E-utils   │             │
│  │  2. Check topic words from our entry appear in paper    │             │
│  │  3. Flag mismatches (paper about wrong topic)           │             │
│  │                                                          │             │
│  │  RULE: A paper about "renal impairment of biologics"    │             │
│  │  CANNOT be cited for "magnesium helps sleep"            │             │
│  └─────────────────────┬───────────────────────────────────┘             │
│                        │                                                 │
│  BUILD                 ▼                                                 │
│  ┌─────────────────────────────────────────────────────────┐             │
│  │ build_interaction_db.py                                  │             │
│  │                                                          │             │
│  │  Inputs:                                                │             │
│  │  • interactions_verified.json (128 curated rows)        │             │
│  │  • research_pairs.json (28,038 supp.ai evidence pairs)  │             │
│  │  • drug_classes.json (24 classes)                        │             │
│  │                                                          │             │
│  │  Creates SQLite with:                                    │             │
│  │  ┌─────────────────────────────────────────────────┐     │             │
│  │  │ interactions          128 rows (safety warnings) │     │             │
│  │  │ research_pairs     28,038 rows (evidence only)   │     │             │
│  │  │ drug_class_map        24 rows (class → RxCUIs)   │     │             │
│  │  │ interaction_db_meta   10 rows (version, counts)  │     │             │
│  │  │ interactions_fts    FTS5 (name search index)     │     │             │
│  │  └─────────────────────────────────────────────────┘     │             │
│  │                                                          │             │
│  │  PRAGMA integrity_check = ok                            │             │
│  │  PRAGMA user_version = 1                                │             │
│  └─────────────────────┬───────────────────────────────────┘             │
│                        │                                                 │
│  RELEASE               ▼                                                 │
│  release_interaction_artifact.py → scripts/dist/                         │
│  (SHA-256 checksum, manifest, validation gates)                          │
└────────────────────────┬─────────────────────────────────────────────────┘
                         │
    ONE COMMAND: bash scripts/rebuild_interaction_db.sh --import
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                      FLUTTER REPO (PharmaGuide ai)                       │
│                                                                          │
│  IMPORT (import_catalog_artifact.sh — 17 validation gates)               │
│  ├── Gate I1: manifest JSON valid + required keys present                │
│  ├── Gate I2: schema_version in supported list                           │
│  ├── Gate I3: SHA-256 matches manifest                                   │
│  ├── Gate I4: PRAGMA integrity_check = ok                                │
│  ├── Gate I5: PRAGMA user_version = 1                                    │
│  ├── Gate I6: live interaction rows ≥ 1                                  │
│  ├── Gate I7: embedded metadata agrees with JSON manifest                │
│  └── Gate I8: no self-referencing checksum bug (T7)                      │
│  (catalog DB also validated through 8 gates — both or nothing)           │
│                                                                          │
│  BUNDLED ASSETS                                                          │
│  ├── assets/db/interaction_db.sqlite          (20 MB)                    │
│  ├── assets/db/interaction_db_manifest.json                              │
│  ├── assets/db/pharmaguide_core.db            (12 MB, 5231 products)     │
│  └── assets/reference_data/timing_rules.json  (39 timing rules)          │
│                                                                          │
│  ON FIRST LAUNCH / UPDATE                                                │
│  ensureInteractionDatabaseAvailable():                                   │
│  1. Compare bundled byte length vs on-disk copy                          │
│  2. If different → re-materialize to documents directory                 │
│  3. Open read-only Drift database wrapper                                │
│                                                                          │
│  DATABASE LAYER (lib/data/database/)                                     │
│  ┌─────────────────────────────────────────────────────────┐             │
│  │ InteractionDatabase (Drift — read-only)                  │             │
│  │                                                          │             │
│  │  lookupByCanonicalId(id) → interactions for a supplement│             │
│  │  lookupByRxcui(rxcui)    → interactions for a drug      │             │
│  │  lookupByDrugClass(cls)  → interactions for a drug class│             │
│  │  lookupPair(a1, a2)      → specific pair interaction    │             │
│  │  rxcuisForDrugClass(cls) → expand class to member drugs │             │
│  │  getMetadata()           → DB version, counts           │             │
│  └─────────────────────┬───────────────────────────────────┘             │
│                        │                                                 │
│  SERVICE LAYER (lib/services/stack/)                                     │
│  ┌─────────────────────────────────────────────────────────┐             │
│  │ StackInteractionChecker                                  │             │
│  │                                                          │             │
│  │  When user SCANS a supplement:                          │             │
│  │  1. Get product's ingredient canonical_ids              │             │
│  │  2. lookupByCanonicalId() for each ingredient           │             │
│  │  3. Cross-check against user's stack medications        │             │
│  │  4. Cross-check against user's stack supplements        │             │
│  │  5. Return List<InteractionResult>                      │             │
│  │                                                          │             │
│  │  When user ADDS a medication:                           │             │
│  │  1. Get medication's RXCUI + drug_classes               │             │
│  │  2. lookupByRxcui() + lookupByDrugClass()               │             │
│  │  3. Cross-check against user's supplement stack         │             │
│  │  4. Return List<InteractionResult>                      │             │
│  └─────────────────────┬───────────────────────────────────┘             │
│                        │                                                 │
│  SEVERITY & PENALTIES                                                    │
│  ┌─────────────────────────────────────────────────────────┐             │
│  │ Severity Enum (lib/core/constants/severity.dart)         │             │
│  │                                                          │             │
│  │  ┌─────────────────┬────────┬─────────┬───────────────┐ │             │
│  │  │ Severity         │ Weight │ Penalty │ User sees     │ │             │
│  │  ├─────────────────┼────────┼─────────┼───────────────┤ │             │
│  │  │ contraindicated  │   5    │   -8    │ BLOCK — Do    │ │             │
│  │  │                  │        │         │ Not Use (RED) │ │             │
│  │  ├─────────────────┼────────┼─────────┼───────────────┤ │             │
│  │  │ avoid            │   4    │   -5    │ AVOID (RED)   │ │             │
│  │  ├─────────────────┼────────┼─────────┼───────────────┤ │             │
│  │  │ caution          │   3    │   -3    │ CAUTION       │ │             │
│  │  │                  │        │         │ (ORANGE)      │ │             │
│  │  ├─────────────────┼────────┼─────────┼───────────────┤ │             │
│  │  │ monitor          │   2    │   -1    │ MONITOR       │ │             │
│  │  │                  │        │         │ (YELLOW)      │ │             │
│  │  ├─────────────────┼────────┼─────────┼───────────────┤ │             │
│  │  │ safe             │   0    │    0    │ SAFE (GREEN)  │ │             │
│  │  └─────────────────┴────────┴─────────┴───────────────┘ │             │
│  │                                                          │             │
│  │  Draft → Flutter mapping (verify_interactions.py):       │             │
│  │  Contraindicated → contraindicated                       │             │
│  │  Major           → avoid                                 │             │
│  │  Moderate         → caution                              │             │
│  │  Minor            → monitor                              │             │
│  └─────────────────────┬───────────────────────────────────┘             │
│                        │                                                 │
│  STACK SAFETY SCORE                                                      │
│  ┌─────────────────────────────────────────────────────────┐             │
│  │ StackSafetyScorer (lib/services/stack/)                  │             │
│  │                                                          │             │
│  │  score = 100 - interaction_penalties + synergy_bonuses   │             │
│  │                                                          │             │
│  │  Hard caps:                                             │             │
│  │  • contraindicated found → score capped at 25           │             │
│  │  • avoid found           → score capped at 50           │             │
│  │  • Floor: 25 (max deduction 75)                         │             │
│  │  • Ceiling: 100 (max bonus 15 from synergies)           │             │
│  │                                                          │             │
│  │  Example:                                                │             │
│  │  User takes Warfarin + Fish Oil supplement               │             │
│  │  → lookupPair finds "Moderate" interaction              │             │
│  │  → penalty = -3                                          │             │
│  │  → score = 100 - 3 = 97 (SAFE tier)                    │             │
│  │                                                          │             │
│  │  User takes MAOI + St. John's Wort supplement            │             │
│  │  → lookupPair finds "Contraindicated"                   │             │
│  │  → penalty = -8, hard cap kicks in                      │             │
│  │  → score = 25 (CRITICAL tier, red alert)                │             │
│  └─────────────────────┬───────────────────────────────────┘             │
│                        │                                                 │
│  WHAT THE USER SEES                                                      │
│  ┌─────────────────────────────────────────────────────────┐             │
│  │                                                          │             │
│  │  Product Detail Screen:                                 │             │
│  │  ┌──────────────────────────────────────────────────┐   │             │
│  │  │ ⚠️ INTERACTION WARNING                           │   │             │
│  │  │                                                   │   │             │
│  │  │ "Because you're taking Warfarin, this Fish Oil   │   │             │
│  │  │  supplement has a MODERATE bleeding risk."        │   │             │
│  │  │                                                   │   │             │
│  │  │  Mechanism: Omega-3 fatty acids have mild        │   │             │
│  │  │  antiplatelet activity...                         │   │             │
│  │  │                                                   │   │             │
│  │  │  Management: Doses under 3g/day generally safe   │   │             │
│  │  │  on warfarin. Higher doses require oversight.     │   │             │
│  │  │                                                   │   │             │
│  │  │  Source: NIH ODS ↗  PubMed ↗                     │   │             │
│  │  └──────────────────────────────────────────────────┘   │             │
│  │                                                          │             │
│  │  Stack Safety Banner:                                   │             │
│  │  ┌──────────────────────────────────────────────────┐   │             │
│  │  │ Stack Safety Score: 72 / 100  [CAUTION]          │   │             │
│  │  │ 2 interactions • 1 synergy                        │   │             │
│  │  └──────────────────────────────────────────────────┘   │             │
│  │                                                          │             │
│  │  Research Evidence (from supp.ai — informational only): │             │
│  │  ┌──────────────────────────────────────────────────┐   │             │
│  │  │ 📄 12 published studies mention this pair         │   │             │
│  │  │ "EPA supplementation was associated with..."     │   │             │
│  │  └──────────────────────────────────────────────────┘   │             │
│  │                                                          │             │
│  └─────────────────────────────────────────────────────────┘             │
└──────────────────────────────────────────────────────────────────────────┘
```

#### Current data counts (as of 2026-04-13)

| Table                     | Rows   | What it contains                                                  |
| ------------------------- | ------ | ----------------------------------------------------------------- |
| `interactions`            | 128    | 99 drug↔supplement + 29 drug↔drug curated safety pairs            |
| `research_pairs`          | 28,038 | supp.ai NLP-extracted co-occurrence evidence (informational only) |
| `drug_class_map`          | 24     | Drug classes with 693 member RxCUIs                               |
| `interactions_fts`        | —      | FTS5 full-text search index on agent names                        |
| `interaction_db_metadata` | 10     | Version, build time, counts                                       |

#### Severity distribution (128 curated interactions)

| Draft severity      | Flutter severity  | Penalty        | Count | Evidence requirement                   | Current distribution                      |
| ------------------- | ----------------- | -------------- | ----- | -------------------------------------- | ----------------------------------------- |
| **Contraindicated** | `contraindicated` | -8 (cap at 25) | 11    | FDA label or clinical consensus        | ALL high confidence, ALL label/regulatory |
| **Major**           | `avoid`           | -5 (cap at 50) | 33    | Published clinical literature or label | 27 high + 6 medium confidence             |
| **Moderate**        | `caution`         | -3             | 60    | Clinical data or authoritative review  | ALL medium confidence                     |
| **Minor**           | `monitor`         | -1             | 24    | Theoretical or limited case reports    | ALL low confidence                        |

Every severity is justified by its evidence basis. High severity = high evidence. Low severity = theoretical.

#### Interaction types

| Type            | Meaning                      | Example                 | Count |
| --------------- | ---------------------------- | ----------------------- | ----- |
| `Med-Sup`       | Drug ↔ supplement            | Warfarin + Ginkgo       | 86    |
| `Sup-Sup`       | Supplement ↔ supplement      | Iron + Calcium          | 8     |
| `Med-Med`       | Drug ↔ drug                  | MAOI + SSRI             | 24    |
| `Med-Food`      | Drug ↔ food                  | CCB + Grapefruit        | 5     |
| `Med-Lifestyle` | Drug ↔ lifestyle factor      | Metformin + Alcohol     | 2     |
| `Med-Procedure` | Drug ↔ medical procedure     | Metformin + IV Contrast | 1     |
| `Sup-Med`       | Supplement ↔ drug (reversed) | Kava + Acetaminophen    | 2     |

#### Per-row verification fields

Every curated interaction entry carries proof of verification:

```json
{
  "verification": {
    "status": "verified",
    "verified_at": "2026-04-13T16:37:00Z",
    "verified_with": {
      "rxnorm": true,
      "umls": true,
      "pubmed": true
    },
    "method": "live_api_batch_2026_04_13"
  },
  "evidence_basis": "label_regulatory",
  "clinical_confidence": "high",
  "evidence_notes": "optional — explains mixed evidence or nuance",
  "applies_to": "whole_class"
}
```

#### The main command: `rebuild_interaction_db.sh`

This is the **only command you need**. It automates the entire pipeline — verify, build, stage, and optionally import into Flutter — in one shot. No manual steps. No forgetting to copy files.

```bash
# Build + stage only (pipeline side)
bash scripts/rebuild_interaction_db.sh

# Build + stage + auto-import into Flutter (the default workflow)
bash scripts/rebuild_interaction_db.sh --import

# Bump version when you add new interactions
bash scripts/rebuild_interaction_db.sh --import --version 1.1.0

# Offline mode (schema checks only, skip live API calls)
bash scripts/rebuild_interaction_db.sh --offline
```

What this single command does:

| Step          | What happens                                                                                                                                           | Stops on failure?                              |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------- |
| 1. **Verify** | `verify_interactions.py` — checks every RXCUI against RxNorm, every CUI against UMLS, normalizes severity, expands drug classes, gates Major+ evidence | YES — bad data never reaches the build         |
| 2. **Build**  | `build_interaction_db.py` — creates `interaction_db.sqlite` with all tables, FTS5 index, integrity checks                                              | YES — corrupt DB never ships                   |
| 3. **Stage**  | `release_interaction_artifact.py` — validates output, writes SHA-256 manifest, copies to `scripts/dist/` atomically                                    | YES — failed validation leaves dist/ untouched |
| 4. **Import** | (with `--import`) Flutter's `import_catalog_artifact.sh` — validates BOTH catalog + interaction DB through 17 gates, copies atomically to `assets/db/` | YES — if either DB fails, neither ships        |

If `research_pairs.json` doesn't exist yet, the script auto-runs `ingest_suppai.py` first.
If the catalog DB isn't in `dist/`, the script auto-stages it from `final_db_output/`, or tells you exactly what to do.

**Important:** The Flutter import requires both `pharmaguide_core.db` AND `interaction_db.sqlite` in `dist/`. This is by design — atomic: both or nothing.

#### Content verification (run before every release)

After `rebuild_interaction_db.sh`, run the content verifier to ensure every PubMed citation actually supports its claimed topic:

```bash
python3 scripts/api_audit/verify_all_citations_content.py
```

This fetches actual article titles and abstracts from PubMed and checks that the cited paper mentions the ingredients/drugs/nutrients claimed in each entry. A paper about "renal impairment" cannot be cited for "magnesium helps sleep." Zero tolerance for wrong-topic citations.

#### What to do when you add new interactions

1. Edit `scripts/data/curated_interactions/curated_interactions_v1.json` or `med_med_pairs_v1.json`
2. Update `_metadata.total_entries` to match actual count
3. Run: `bash scripts/rebuild_interaction_db.sh --import --version 1.1.0`
4. Run: `python3 scripts/api_audit/verify_all_citations_content.py`
5. Update `_expectedLiveInteractionCount` in Flutter's `test/data/database/interaction_database_test.dart`
6. Commit + push both repos

#### Running individual steps (advanced / debugging)

```bash
# Step 1: Verify curated data (live API checks)
python3 scripts/api_audit/verify_interactions.py \
    --drafts scripts/data/curated_interactions \
    --report scripts/interaction_db_output/interaction_audit_report.json \
    --normalized-out scripts/interaction_db_output/interactions_verified.json \
    --corrections-out scripts/interaction_db_output/corrections.json

# Step 2: Build SQLite from verified data
python3 scripts/build_interaction_db.py \
    --normalized-drafts scripts/interaction_db_output/interactions_verified.json \
    --research-pairs scripts/interaction_db_output/research_pairs.json \
    --drug-classes scripts/data/drug_classes.json \
    --output scripts/interaction_db_output/interaction_db.sqlite \
    --manifest scripts/interaction_db_output/interaction_db_manifest.json \
    --report scripts/interaction_db_output/build_audit_report.json \
    --interaction-db-version "1.0.0"

# Step 3: Stage to dist/
python3 scripts/release_interaction_artifact.py

# Step 4: Import into Flutter
cd "/Users/seancheick/PharmaGuide ai"
./scripts/import_catalog_artifact.sh /Users/seancheick/Downloads/dsld_clean/scripts/dist

# Content verification (always run before release)
python3 scripts/api_audit/verify_all_citations_content.py
```

#### Re-ingest supp.ai (rare — only if the raw dump changes)

```bash
python3 scripts/ingest_suppai.py \
    --suppai-dir "/Users/seancheick/Downloads/Supp ai DB/" \
    --output scripts/interaction_db_output/research_pairs.json \
    --report scripts/interaction_db_output/ingest_suppai_report.json
```

The supp.ai dump is a static dataset from 2021 (5 files, 245 MB). After re-ingesting, run `rebuild_interaction_db.sh` to rebuild the SQLite.

#### What NOT to do

- **NEVER edit `interaction_db.sqlite` directly** — always rebuild from JSON sources via the script
- **NEVER manually `cp` files to Flutter `assets/db/`** — use `rebuild_interaction_db.sh --import`
- **NEVER ship `paper_metadata.json`** from supp.ai — it's 84MB, not needed in the app
- **NEVER skip verification** — `rebuild_interaction_db.sh` runs it automatically
- **NEVER manually edit `interactions_verified.json`** — it's generated output, not a source file
- **NEVER trust AI-generated PMIDs without content verification** — existence alone proves nothing
- **NEVER assign Contraindicated/Major severity without label/regulatory or clinical literature source**

### 11.4 Enrichment Support Libraries

These are imported by `enrich_supplements_v3.py` — you don't run them directly, but they contain core logic:

| Script                           | What it does                                                                                                 |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `enhanced_normalizer.py`         | Core text normalization engine (~6K lines). Ingredient name cleanup, alias resolution, form detection.       |
| `constants.py`                   | Shared constants, mappings, category lists, regex patterns (~1.5K lines). Defines `DATA_DIR`, `SCRIPTS_DIR`. |
| `dosage_normalizer.py`           | Parses dosage strings ("500mg", "1,000 IU") into structured `(amount, unit)` tuples.                         |
| `unit_converter.py`              | Converts between units (mg↔g, mcg↔mg, IU↔mcg for fat-solubles).                                              |
| `fuzzy_matcher.py`               | RapidFuzz-based fuzzy string matching for ingredient resolution.                                             |
| `match_ledger.py`                | Records how each ingredient was matched (exact, alias, fuzzy, unmatched) for audit trail.                    |
| `normalization.py`               | Lower-level text normalization helpers.                                                                      |
| `proprietary_blend_detector.py`  | Identifies and flags proprietary/branded blends in ingredient lists.                                         |
| `functional_grouping_handler.py` | Groups ingredients into functional categories (vitamins, minerals, amino acids, etc.).                       |
| `supplement_type_utils.py`       | Classifies supplement type from label data (multi, single-ingredient, probiotic, etc.).                      |
| `rda_ul_calculator.py`           | RDA/UL lookups from `rda_optimal_uls.json` for dosing adequacy scoring.                                      |
| `unmapped_ingredient_tracker.py` | Tracks ingredients that couldn't be mapped to any known database entry.                                      |
| `env_loader.py`                  | Loads `.env` file for API keys (UMLS, openFDA, PubMed, Supabase).                                            |
| `dsld_validator.py`              | Validates raw DSLD JSON structure before pipeline ingestion.                                                 |
| `batch_processor.py`             | Batch processing with resume capability for large dataset runs.                                              |

### 11.5 Quality & Validation

| Script                             | What it does                                                                                                | When to use                  |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------- | ---------------------------- |
| `db_integrity_sanity_check.py`     | Validates schema, metadata, IDs, cross-references across all 36 data files in `scripts/data/`. ~1.5K lines. | After any data file change   |
| `enrichment_contract_validator.py` | Validates enriched output has all required sections and correct structure.                                  | After enrichment changes     |
| `coverage_gate.py`                 | Enforces quality thresholds (ingredient match rate ≥99.5%, scoring coverage, etc.).                         | Before release               |
| `preflight.py`                     | Pre-run checks (dependencies, config files, data files present).                                            | Before pipeline run          |
| `regression_snapshot.py`           | Captures scoring snapshots for before/after comparison.                                                     | Before scoring changes       |
| `shadow_score_comparison.py`       | Phase 0 validation — compares old vs new scoring side-by-side.                                              | During scoring recalibration |

```bash
# Run all data file integrity checks
python3 scripts/db_integrity_sanity_check.py

# Validate enriched output
python3 scripts/enrichment_contract_validator.py <enriched_file>

# Check coverage thresholds
python3 scripts/coverage_gate.py <scored_file>

# Pre-flight check
python3 scripts/preflight.py

# Capture regression snapshot before changes
python3 scripts/regression_snapshot.py --output snapshots/before_change.json

# Compare scoring before/after
python3 scripts/shadow_score_comparison.py --before snapshots/before.json --after snapshots/after.json
```

---

## 12. API Audit Scripts (`scripts/api_audit/`)

External API verification tools that validate data accuracy. These call real APIs — use `PHARMAGUIDE_LIVE_TESTS=1` for live test mode. All results are reports only; they never modify production data files.

### 12.1 Verification Scripts

| Script                             | API                   | What it verifies                                                                                                |
| ---------------------------------- | --------------------- | --------------------------------------------------------------------------------------------------------------- |
| `verify_cui.py`                    | UMLS                  | CUI identifiers for supplement ingredients. The 1087-line reference implementation for API patterns.            |
| `verify_pubchem.py`                | PubChem               | CID + CAS numbers for chemical compounds.                                                                       |
| `verify_unii.py`                   | FDA UNII              | UNII codes and CFR regulatory references.                                                                       |
| `verify_rda_uls.py`                | USDA FoodData Central | RDA/AI/UL values against National Academies DRI tables.                                                         |
| `verify_efsa.py`                   | EFSA                  | EU regulatory ADI/opinion validation.                                                                           |
| `verify_clinical_trials.py`        | ClinicalTrials.gov    | NCT ID verification for clinical study references.                                                              |
| `verify_pubmed_references.py`      | PubMed                | DOI/PMID references across all pipeline data files.                                                             |
| `verify_interactions.py`           | RxNorm + UMLS         | Interaction DB entries — RXCUI/CUI verification, severity normalization. Runs before `build_interaction_db.py`. |
| `verify_depletion_timing_pmids.py` | PubMed                | PMIDs in `timing_rules.json` and `medication_depletions.json`.                                                  |
| `verify_comptox.py`                | CompTox               | Chemical toxicity data verification.                                                                            |

```bash
# Verify PMIDs in timing/depletion files (dry-run — extracts only)
python3 scripts/api_audit/verify_depletion_timing_pmids.py

# Verify PMIDs live against PubMed API
python3 scripts/api_audit/verify_depletion_timing_pmids.py --live

# Verify interaction DB entries
python3 scripts/api_audit/verify_interactions.py

# Verify CUI identifiers against UMLS
python3 scripts/api_audit/verify_cui.py
```

### 12.2 Enrichment & Audit Scripts

| Script                                | What it does                                                                               |
| ------------------------------------- | ------------------------------------------------------------------------------------------ |
| `pubmed_client.py`                    | Shared PubMed E-utilities client. Used by all scripts that validate PMIDs.                 |
| `normalize_clinical_pubmed.py`        | Normalizes clinical study references to structured PMID format.                            |
| `enrich_chembl_bioactivity.py`        | ChEMBL mechanism of action enrichment for bioactive compounds.                             |
| `enrich_botanicals.py`                | Enriches botanical ingredient data from external sources.                                  |
| `discover_clinical_evidence.py`       | Discovers new clinical evidence for ingredients not yet in `backed_clinical_studies.json`. |
| `audit_banned_recalled_accuracy.py`   | Release gate — validates banned/recalled data accuracy.                                    |
| `audit_clinical_evidence_strength.py` | Classifies evidence strength (RCT, meta-analysis, observational).                          |
| `audit_clinical_sources.py`           | Audits source quality across clinical study references.                                    |
| `audit_alias_accuracy.py`             | Verifies ingredient alias mappings are correct.                                            |
| `audit_notes_alignment.py`            | Checks that notes/explanations align with scoring logic.                                   |
| `seed_drug_classes.py`                | Seeds `drug_classes.json` from NLM RxClass API (ATC hierarchy).                            |

```bash
# Regenerate drug classes from RxNorm (dry-run)
python3 scripts/api_audit/seed_drug_classes.py --dry-run

# Regenerate drug classes (live — writes to scripts/data/drug_classes.json)
python3 scripts/api_audit/seed_drug_classes.py --live

# Audit banned/recalled data accuracy
python3 scripts/api_audit/audit_banned_recalled_accuracy.py
```

### 12.3 FDA Regulatory Sync

| Script                                | What it does                                                                                                       |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `fda_weekly_sync.py` (api_audit/)     | Fetches FDA recalls, safety alerts, DEA scheduling from openFDA + RSS. Updates `banned_recalled_ingredients.json`. |
| `fda_manufacturer_violations_sync.py` | Syncs manufacturer warning letters and violations from FDA.                                                        |

```bash
# Run FDA weekly sync
python3 scripts/api_audit/fda_weekly_sync.py

# Or use the wrapper script
bash scripts/run_fda_sync.sh
```

---

## 13. Reference Data Files (`scripts/data/`)

36 JSON files that power the pipeline. All follow the `_metadata` contract with `schema_version`, `last_updated`, `total_entries`.

### 13.1 Scoring Data (used by `score_supplements.py`)

| File                               | Entries     | Role                                                                          |
| ---------------------------------- | ----------- | ----------------------------------------------------------------------------- |
| `ingredient_quality_map.json`      | 563 parents | Quality scoring — bioavailability, premium forms, delivery. **Largest file.** |
| `banned_recalled_ingredients.json` | 143         | Safety disqualifications — BLOCKED/UNSAFE verdicts.                           |
| `harmful_additives.json`           | 115         | Penalty scoring for harmful additives (colors, sweeteners).                   |
| `backed_clinical_studies.json`     | 197         | Evidence bonus points — all PMID-backed.                                      |
| `allergens.json`                   | Big 8       | Allergen classification and penalties.                                        |
| `rda_optimal_uls.json`             | 47          | Dosing adequacy benchmarks (RDA, optimal, UL per age/sex).                    |
| `manufacturer_violations.json`     | —           | Brand trust penalties from FDA warning letters.                               |
| `synergy_cluster.json`             | 54          | Ingredient synergy bonuses when complementary pairs found.                    |
| `top_manufacturers_data.json`      | —           | Manufacturer reputation data.                                                 |
| `cert_claim_rules.json`            | —           | Certification and label claim validation rules.                               |

### 13.2 Enrichment Data (used by `enrich_supplements_v3.py`)

| File                                   | Role                                                                 |
| -------------------------------------- | -------------------------------------------------------------------- |
| `ingredient_classification.json`       | Maps ingredients to categories (vitamin, mineral, amino acid, etc.). |
| `botanical_ingredients.json`           | Botanical-specific enrichment data (standardization, part used).     |
| `standardized_botanicals.json`         | Standardized extract forms and marker compounds.                     |
| `clinically_relevant_strains.json`     | Probiotic strain data (CFU, clinical evidence).                      |
| `other_ingredients.json`               | Non-active "other ingredient" classification (excipients, fillers).  |
| `absorption_enhancers.json`            | Absorption-enhancing delivery technologies (BioPerine, liposomal).   |
| `enhanced_delivery.json`               | Premium delivery systems (phytosome, nano, micelle).                 |
| `proprietary_blends.json`              | Known proprietary blend detection patterns.                          |
| `functional_ingredient_groupings.json` | Functional groupings for category-level analysis.                    |
| `ingredient_weights.json`              | Ingredient importance weights for scoring.                           |
| `color_indicators.json`                | Artificial color identification.                                     |

### 13.3 Interaction Data (used by interaction DB pipeline)

| File                                | Entries                 | Role                                                   |
| ----------------------------------- | ----------------------- | ------------------------------------------------------ |
| `ingredient_interaction_rules.json` | 98                      | Deterministic interaction rules keyed by canonical ID. |
| `drug_classes.json`                 | 24 classes, 693 members | RxNorm drug class expansion map (ATC hierarchy).       |
| `clinical_risk_taxonomy.json`       | —                       | Risk category classification for interaction severity. |

### 13.4 Flutter Feature Data (new — built 2026-04-12)

| File                          | Entries  | Role                                                                              | Flutter consumer                                                         |
| ----------------------------- | -------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| `timing_rules.json`           | 39       | Supplement timing/absorption rules (separate iron+calcium, take D with fat, etc.) | `ReferenceDataRepository.loadTimingRules()` → `TimingOptimization` model |
| `medication_depletions.json`  | 68       | Drug-induced nutrient depletions (statins→CoQ10, metformin→B12, PPIs→magnesium)   | Future Depletion Checker feature                                         |
| `user_goals_to_clusters.json` | 18 goals | Maps user health goals to synergy clusters (e.g. "sleep" → sleep_stack cluster).  | `ReferenceDataRepository.loadGoalMappings()`                             |

### 13.5 Utility Data

| File                              | Role                                                                                      |
| --------------------------------- | ----------------------------------------------------------------------------------------- |
| `unit_conversions.json`           | Unit conversion factors (mg→g, IU→mcg).                                                   |
| `unit_mappings.json`              | Unit name normalization ("milligrams" → "mg").                                            |
| `percentile_categories.json`      | Score percentile tier boundaries.                                                         |
| `id_redirects.json`               | DSLD ID redirects for merged/superseded products.                                         |
| `cross_db_overlap_allowlist.json` | Allowed overlaps between data files (e.g., ingredient in both IQM and harmful_additives). |
| `banned_match_allowlist.json`     | False-positive allowlist for banned ingredient matching.                                  |
| `efsa_openfoodtox_reference.json` | EU regulatory reference data.                                                             |
| `migration_report.json`           | Schema migration tracking.                                                                |
| `rda_therapeutic_dosing.json`     | Extended dosing data beyond standard RDA.                                                 |
| `manufacture_deduction_expl.json` | Manufacturer deduction explanations for scoring.                                          |

---

## 14. How to Grow the Data Files

### 14.1 Adding Timing Rules

Edit `scripts/data/timing_rules.json`. Each rule needs:

```json
{
  "id": "timing_<ingredient1>_<ingredient2>_<type>",
  "ingredient1": "<lowercase name>",
  "ingredient2": "<lowercase name>",
  "rule_type": "separate|take_together|take_with_food|take_on_empty_stomach|time_of_day",
  "advice": "<one sentence, consumer-friendly>",
  "mechanism": "<brief pharmacological explanation>",
  "separation_hours": 2,
  "score_impact": -2,
  "evidence_level": "established|probable|possible",
  "sources": [
    {
      "source_type": "pubmed",
      "label": "...",
      "url": "https://pubmed.ncbi.nlm.nih.gov/<PMID>/"
    }
  ]
}
```

After adding:

```bash
# 1. Update _metadata.total_entries to match actual count
# 2. Run contract tests
python3 -m pytest scripts/tests/test_timing_rules.py -v

# 3. Verify PMIDs
python3 scripts/api_audit/verify_depletion_timing_pmids.py --live

# 4. Copy to Flutter assets
cp scripts/data/timing_rules.json "/path/to/PharmaGuide ai/assets/reference_data/timing_rules.json"
```

### 14.2 Adding Medication Depletions

Edit `scripts/data/medication_depletions.json`. Each entry needs:

```json
{
  "id": "DEP_<DRUG_OR_CLASS>_<NUTRIENT>",
  "drug_ref": {
    "type": "class|drug",
    "id": "class:<class_id>",
    "display_name": "Human-readable name"
  },
  "depleted_nutrient": {
    "standard_name": "Vitamin B12",
    "canonical_id": "vitamin_b12"
  },
  "severity": "significant|moderate|mild",
  "mechanism": "<how the drug depletes this nutrient>",
  "clinical_impact": "<what happens if unchecked>",
  "recommendation": "<consumer-friendly suggestion>",
  "onset_timeline": "weeks|months|years",
  "evidence_level": "established|probable|possible",
  "monitoring_note": "<optional: when to check levels>",
  "sources": [{ "source_type": "pubmed", "label": "...", "url": "..." }]
}
```

For class-type drug refs, the `id` must match a key in `drug_classes.json`. To add a new drug class:

```bash
# Regenerate drug classes from RxNorm API
python3 scripts/api_audit/seed_drug_classes.py --live
```

After adding depletions:

```bash
# 1. Update _metadata.total_entries
# 2. Run contract tests (includes cross-reference check against drug_classes.json)
python3 -m pytest scripts/tests/test_medication_depletions.py -v

# 3. Verify PMIDs
python3 scripts/api_audit/verify_depletion_timing_pmids.py --live
```

### 14.3 Adding Interaction Rules

Edit `scripts/data/ingredient_interaction_rules.json`. Follow the existing entry structure (see first entry for template). Each rule has `condition_rules`, `drug_class_rules`, `dose_thresholds`, and `pregnancy_lactation` sections.

After adding:

```bash
# Verify interactions (RXCUI/CUI validation)
python3 scripts/api_audit/verify_interactions.py

# Run interaction tests
python3 -m pytest scripts/tests/test_verify_interactions.py -v

# Rebuild interaction DB
python3 scripts/build_interaction_db.py
```

### 14.4 Adding Synergy Clusters

Edit `scripts/data/synergy_cluster.json`. Each cluster needs `id`, `standard_name`, `ingredients[]`, `min_effective_doses{}`, `evidence_tier`, `sources[]`.

After adding:

```bash
python3 -m pytest scripts/tests/test_synergy_schema_contract.py -v
```

### 14.5 General Rules for Any Data File Change

1. **Update `_metadata.total_entries`** to match the actual count
2. **Update `_metadata.last_updated`** to today's date
3. **Run integrity check**: `python3 scripts/db_integrity_sanity_check.py`
4. **Run pipeline tests**: `python3 -m pytest scripts/tests/test_pipeline_integrity.py -v`
5. **Never batch-edit** — add one entry, verify, test. Batch ops skip entries silently.

---

## 15. Test Suite

3,100+ tests across 83 files. Run from the repo root.

```bash
# Run ALL tests
python3 -m pytest scripts/tests/ -q

# Run a specific test file
python3 -m pytest scripts/tests/test_score_supplements.py -v

# Run tests matching a keyword
python3 -m pytest scripts/tests/ -k "banned"

# Run only data file contract tests
python3 -m pytest scripts/tests/test_pipeline_integrity.py scripts/tests/test_timing_rules.py scripts/tests/test_medication_depletions.py scripts/tests/test_synergy_schema_contract.py -v

# Run interaction DB tests
python3 -m pytest scripts/tests/test_build_interaction_db.py scripts/tests/test_verify_interactions.py scripts/tests/test_ingest_suppai.py -v

# Run live API tests (requires PHARMAGUIDE_LIVE_TESTS=1 and API keys in .env)
PHARMAGUIDE_LIVE_TESTS=1 python3 -m pytest scripts/tests/test_verify_interactions_live.py -v
```

---

## 16. Environment Setup

### 16.1 Dependencies

```bash
pip install -r requirements-dev.txt
# Core: requests>=2.32, rapidfuzz>=3.9, pytest>=9
```

### 16.2 API Keys (`.env` file at repo root)

```
UMLS_API_KEY=...          # UMLS/RxNorm CUI verification
NCBI_API_KEY=...          # PubMed PMID verification (optional but raises rate limit)
PUBMED_EMAIL=...          # Required by NCBI for identification
SUPABASE_URL=...          # Supabase project URL
SUPABASE_SERVICE_KEY=...  # Supabase service role key
OPENFDA_API_KEY=...       # openFDA recall data (optional)
```

Keys are loaded by `scripts/env_loader.py`. Never commit `.env` to git.

### 16.3 Project Structure

```
scripts/
  *.py                        # Core pipeline scripts (~45 files)
  api_audit/                  # External API verification tools (28 scripts)
  config/                     # cleaning_config.json, enrichment_config.json, scoring_config.json
  data/                       # 36 reference JSON databases (schema v5.0/5.1)
  data/curated_interactions/  # Curated interaction drafts (for interaction DB)
  data/curated_overrides/     # Manual CUI/PubChem/GSRS policy overrides
  data/suppai_import/         # supp.ai raw export (user drops here)
  tests/                      # 83 test files, 3100+ tests
  logs/                       # Runtime logs
  reports/                    # Generated audit reports
  dist/                       # Release artifacts (catalog + interaction DB)
  final_db_output/            # Build output before staging to dist/
  interaction_db_output/      # Interaction DB build output
docs/                         # Technical deep-dives, specs, infographics
```
