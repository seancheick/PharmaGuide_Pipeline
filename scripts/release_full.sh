#!/usr/bin/env bash
#
# release_full.sh — One-command catalog + interaction DB release pipeline.
#
# AUTO-SMART by design: every step decides for itself whether it has work to
# do, by comparing input freshness against output freshness. No flags
# required for the common case. The pipeline always produces the most
# up-to-date and accurate output without shortcuts.
#
# Steps (in order):
#   1. Gate, assemble, and promote (rebuild_dashboard_snapshot.sh)
#                                  AUTO-SKIPS when dist/ catalog is already
#                                  fresh relative to per-brand outputs.
#                                  The snapshot path validates candidates before
#                                  atomically promoting dist/final_db_output.
#   2. Confirm catalog parity      No direct staging; the same safe snapshot
#                                  path handles any final/dist mismatch.
#   3. Extract DSLD product images (extract_product_images.py)
#                                  AUTO-SKIPS when dist/ image backfill is
#                                  already complete and current.
#   4. Rebuild interaction DB      (rebuild_interaction_db.sh)
#                                  AUTO-SKIPS when no rule-data file is
#                                  newer than the bundled interaction_db.
#   5. Sync to Supabase            (sync_to_supabase.py — UPLOAD ONLY)
#                                  Trusts sync_to_supabase's built-in
#                                  "up_to_date" detection (manifest checksum).
#                                  Storage cleanup is NO LONGER here — see 8.
#   6. Atomic Flutter bundle       (Flutter import_catalog_artifact.sh)
#                                  AUTO-SKIPS when Flutter assets/db/
#                                  manifests already match dist/ checksums.
#   7. Prune .previous backups     (assets/db/*.previous)
#                                  No-ops cleanly when none exist.
#   8. Commit bundle + cleanup     (git commit assets/db/ then
#                                  cleanup_old_versions.py --execute ...)
#                                  Commits the Flutter bundle LOCALLY so the
#                                  orphan-cleanup bundle_alignment gate passes,
#                                  then sweeps old version dirs + orphan blobs.
#                                  Push stays manual.
#
# Usage:
#     # Standard: detect what needs running, do it, no flags needed.
#     bash scripts/release_full.sh
#
#     # Force every step to run (override auto-detect — emergency rebuild):
#     bash scripts/release_full.sh --force
#
#     # Skip cloud/device steps (local-only iteration):
#     bash scripts/release_full.sh --skip-supabase
#     bash scripts/release_full.sh --skip-flutter
#     bash scripts/release_full.sh --skip-product-images
#
#     # Preview Supabase sync without uploading:
#     bash scripts/release_full.sh --supabase-dry-run
#
#     # Custom Flutter repo location:
#     bash scripts/release_full.sh --flutter-repo /path/to/PharmaGuide_ai
#
# Legacy flags (still accepted for backward compat; redundant now):
#     --skip-assemble    same effect as auto-detection when dist/ is fresh
#
# Prerequisites:
#     - Per-brand pipeline outputs under scripts/products/output_*/ (only
#       needed if step 1 actually runs; auto-detect handles missing case
#       only if dist/ already has a catalog from another path).
#     - .env at repo root: UMLS_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY
#     - Flutter repo exists at $FLUTTER_REPO
#
# Exit codes:
#     0  full pipeline completed (incl. when every step auto-skipped)
#     2  bad CLI args
#     N  the failing step's exit code

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"
source "$REPO_ROOT/scripts/python_env.sh"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

FLUTTER_REPO="/Users/seancheick/PharmaGuide ai"
FORCE=0
SKIP_SUPABASE=0
SKIP_FLUTTER=0
SKIP_PRODUCT_IMAGES=0
SUPABASE_DRY_RUN=0
KEEP_VERSIONS=2
SCORING_SNAPSHOT_GATE_RAN=0

# ---------------------------------------------------------------------------
# CLI parsing
# ---------------------------------------------------------------------------

while (($# > 0)); do
  case "$1" in
    --force)             FORCE=1; shift ;;
    --skip-assemble)     shift ;;  # accepted for backward compat; no-op now
    --skip-supabase)     SKIP_SUPABASE=1; shift ;;
    --skip-flutter)      SKIP_FLUTTER=1; shift ;;
    --skip-product-images) SKIP_PRODUCT_IMAGES=1; shift ;;
    --supabase-dry-run)  SUPABASE_DRY_RUN=1; shift ;;
    --keep-versions)     KEEP_VERSIONS="${2:?--keep-versions requires N}"; shift 2 ;;
    --flutter-repo)      FLUTTER_REPO="${2:?--flutter-repo requires path}"; shift 2 ;;
    -h|--help)
      sed -n '2,55p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "Unknown flag: $1" >&2; exit 2 ;;
  esac
done

info()  { printf '\033[36m[release]\033[0m %s\n' "$*"; }
ok()    { printf '\033[32m[release] OK:\033[0m %s\n' "$*"; }
warn()  { printf '\033[33m[release] WARN:\033[0m %s\n' "$*"; }
err()   { printf '\033[31m[release] ERROR:\033[0m %s\n' "$*" >&2; }
skip()  { printf '\033[2m[release] —\033[0m %s\n' "$*"; }

DIST_DIR="$REPO_ROOT/scripts/dist"
FINAL_DB_DIR="$REPO_ROOT/scripts/final_db_output"
ASSETS_DIR="$FLUTTER_REPO/assets/db"
DIST_PRODUCT_IMAGES_DIR="$DIST_DIR/product_images"
DIST_PRODUCT_IMAGE_INDEX="$DIST_PRODUCT_IMAGES_DIR/product_image_index.json"
PRODUCTS_DIR="$REPO_ROOT/scripts/products"
SOURCE_OF_TRUTH_AUDIT="$REPO_ROOT/scripts/audit_source_of_truth_contract.py"
RDA_REFERENCE_SOURCE="$REPO_ROOT/scripts/data/rda_optimal_uls.json"
IDENTITY_AUDIT_SCRIPT="$REPO_ROOT/scripts/audit_identity_integrity.py"

# Code that changes emitted catalog identity, scoring, or explanation fields is
# a catalog-build input, just like the source product outputs. Without this,
# a release after an exporter change can incorrectly reuse an older catalog.
CATALOG_BUILD_SOURCES=(
  "$REPO_ROOT/scripts/build_all_final_dbs.py"
  "$REPO_ROOT/scripts/build_final_db.py"
  "$REPO_ROOT/scripts/enhanced_normalizer.py"
  "$REPO_ROOT/scripts/enrich_supplements_v3.py"
  "$REPO_ROOT/scripts/identity_integrity.py"
  "$REPO_ROOT/scripts/score_products_v4.py"
  "$REPO_ROOT/scripts/scoring_input_contract.py"
  "$REPO_ROOT/scripts/scoring_v4/scored_artifact.py"
  "$REPO_ROOT/scripts/scoring_v4/quality_score.py"
  "$REPO_ROOT/scripts/scoring_v4/pillar_explanations.py"
  "$REPO_ROOT/scripts/release_catalog_artifact.py"
)

START_TS=$(date +%s)

info "================================================================"
info "PharmaGuide — Full Release Pipeline (auto-smart)"
info "================================================================"
if (( FORCE == 1 )); then
  info "MODE: --force (every step will run regardless of freshness)"
else
  info "MODE: auto-detect (each step decides if it has work to do)"
fi
info "skip-product-images: $SKIP_PRODUCT_IMAGES"
info "skip-supabase:    $SKIP_SUPABASE  (supabase-dry-run: $SUPABASE_DRY_RUN)"
info "skip-flutter:     $SKIP_FLUTTER"
info "keep-versions:    $KEEP_VERSIONS"
info "flutter-repo:     $FLUTTER_REPO"
info "================================================================"

# ---------------------------------------------------------------------------
# Helpers — freshness primitives. All return 0 (true) or 1 (false) for use
# in `if` blocks. We use mtime comparisons because they're cheap, accurate
# enough at this scale, and don't require parsing JSON manifests.
# ---------------------------------------------------------------------------

# is_path_newer_than <input_path> <output_path>
# Returns 0 if input mtime > output mtime (i.e. input is newer, output is stale).
# Returns 0 when output doesn't exist (must be built).
# Returns 1 when output is at least as fresh as input (skip is safe).
is_path_newer_than() {
  local input="$1"
  local output="$2"
  [[ ! -e "$output" ]] && return 0  # output missing → must build
  [[ ! -e "$input"  ]] && return 1  # input missing → can't be stale; skip
  # -nt = "newer than"; bash mtime check
  [[ "$input" -nt "$output" ]]
}

# any_newer_input <output_path> <input_path...>
# Returns 0 if any input is newer than output (or output is missing).
any_newer_input() {
  local output="$1"; shift
  [[ ! -e "$output" ]] && return 0
  local i
  for i in "$@"; do
    [[ -e "$i" && "$i" -nt "$output" ]] && return 0
  done
  return 1
}

# any_pipeline_output_newer_than <output_path> <products_dir>
# Returns 0 if any per-brand pipeline-output file (i.e. JSON inside
# `output_*_enriched/enriched/` or `output_*_scored/scored/`) has mtime
# newer than <output>. Deliberately scoped — does NOT match `reports/`,
# `logs/`, or other side-effect directories under products/, which get
# touched by the release run itself and would cause false positives.
any_pipeline_output_newer_than() {
  local output="$1"
  local products_dir="$2"
  [[ ! -e "$output"      ]] && return 0
  [[ ! -d "$products_dir" ]] && return 1
  # Scope: only the canonical per-brand output folders. -path filters
  # match the `*_enriched/enriched/` and `*_scored/scored/` segments.
  if find "$products_dir" \
       -type d \( -name 'reports' -o -name 'logs' -o -name '__pycache__' \) -prune -o \
       -type f -name '*.json' \
       \( -path '*_enriched/enriched/*' -o -path '*_scored/scored/*' \) \
       -newer "$output" -print -quit 2>/dev/null | grep -q .; then
    return 0
  fi
  return 1
}

# json_field <path> <key>
# Cheap JSON-string extractor for top-level checksum_sha256-style fields.
# Avoids depending on jq. Returns empty string on miss.
json_field() {
  local path="$1"
  local key="$2"
  [[ ! -f "$path" ]] && return 0
  "$PG_PYTHON" -c "
import json, sys
try:
    with open('$path') as f: d = json.load(f)
    print(d.get('$key', ''))
except Exception:
    pass
" 2>/dev/null
}

file_sha256() {
  local path="$1"
  [[ ! -f "$path" ]] && return 0
  "$PG_PYTHON" -c "
import hashlib, sys
h = hashlib.sha256()
with open(sys.argv[1], 'rb') as f:
    for chunk in iter(lambda: f.read(1024 * 1024), b''):
        h.update(chunk)
print(h.hexdigest())
" "$path" 2>/dev/null
}

run_strict_gate() {
  local label="$1"; shift
  info "Strict gate: $label"
  "$@"
  ok "Strict gate passed: $label"
}

run_strict_gate "source-of-truth matrix" \
  "$PG_PYTHON" "$SOURCE_OF_TRUTH_AUDIT" matrix --strict-release

# This verifies the already-produced enrichment output before any freshness
# shortcut can reuse it. A catalog rebuild cannot repair stale enrichment, so
# fail with the actionable upstream requirement instead of restaging old data.
run_strict_gate "active identity integrity" \
  "$PG_PYTHON" "$IDENTITY_AUDIT_SCRIPT" --products-dir "$PRODUCTS_DIR"

# ---------------------------------------------------------------------------
# Step 1: Assemble final DB from per-brand outputs
#
# Skip when: dist/pharmaguide_core.db already exists AND no per-brand
#            output is newer than it AND final_db_output/ also has a copy
#            that's at least as fresh (or doesn't need refreshing).
#
# Net effect:
#   • Cold start (no dist, no final_db_output): assemble.
#   • Pipeline ran (per-brand outputs newer than dist): assemble.
#   • Chained from snapshot (dist fresh, final_db_output absent): SKIP.
#   • Re-running release_full with no upstream changes: SKIP.
# ---------------------------------------------------------------------------

DIST_CATALOG="$DIST_DIR/pharmaguide_core.db"
FINAL_CATALOG="$FINAL_DB_DIR/pharmaguide_core.db"

sync_final_db_output_catalog_from_dist() {
  [[ -f "$DIST_CATALOG" ]] || return 0
  [[ -f "$DIST_DIR/export_manifest.json" ]] || return 0

  mkdir -p "$FINAL_DB_DIR"
  cp -p "$DIST_CATALOG" "$FINAL_CATALOG"
  cp -p "$DIST_DIR/export_manifest.json" "$FINAL_DB_DIR/export_manifest.json"
  if [[ -f "$DIST_DIR/detail_index.json" ]]; then
    cp -p "$DIST_DIR/detail_index.json" "$FINAL_DB_DIR/detail_index.json"
  fi
  ok "final_db_output catalog mirror synced from dist/"
}

step1_needs_run() {
  (( FORCE == 1 )) && return 0
  # If we have NO catalog anywhere → must assemble
  if [[ ! -f "$DIST_CATALOG" && ! -f "$FINAL_CATALOG" ]]; then
    return 0
  fi
  # If per-brand outputs are newer than the freshest assembled output → must reassemble
  local newest_output="$DIST_CATALOG"
  [[ -f "$FINAL_CATALOG" && "$FINAL_CATALOG" -nt "$DIST_CATALOG" ]] && newest_output="$FINAL_CATALOG"
  [[ ! -f "$newest_output" ]] && return 0
  if [[ -d "$PRODUCTS_DIR" ]]; then
    if any_pipeline_output_newer_than "$newest_output" "$PRODUCTS_DIR"; then
      return 0
    fi
  fi
  # A reference-table change alters every emitted rda_ul_data stamp and can
  # change product UL outcomes, so it requires a catalog rebuild even when no
  # source label changed.
  if is_path_newer_than "$RDA_REFERENCE_SOURCE" "$newest_output"; then
    return 0
  fi
  if any_newer_input "$newest_output" "${CATALOG_BUILD_SOURCES[@]}"; then
    return 0
  fi
  return 1  # safe to skip
}

if step1_needs_run; then
  info "Step 1/8: Catalog refresh required — gating and building candidates..."
  bash scripts/rebuild_dashboard_snapshot.sh
  SCORING_SNAPSHOT_GATE_RAN=1
  ok "Catalog candidates gated and promoted"
else
  skip "Step 1/8: Catalog up to date with per-brand outputs — skipping assembly"
fi

# Every emitted product UL block must carry the canonical reference stamp.
# This blocks a mixed refresh from publishing stale product-detail UL data.
run_strict_gate "RDA/UL emitted-reference stamp parity" \
  "$PG_PYTHON" scripts/audit_rda_ul_reference_stamps.py --products-dir "$PRODUCTS_DIR"

# ---------------------------------------------------------------------------
# Step 2: Stage catalog to dist/
#
# Skip when: dist/ catalog is at least as fresh as final_db_output/ catalog.
# This handles all three valid input paths:
#   • Standalone after step 1 ran (final_db_output newer) → stage.
#   • Chained-from-snapshot (final_db_output absent, dist already populated) → skip.
#   • Re-running with no changes (final_db_output equal to dist) → skip.
# ---------------------------------------------------------------------------

step2_needs_run() {
  (( FORCE == 1 )) && return 0
  # If final_db_output exists and is newer than dist → must re-stage
  if [[ -f "$FINAL_CATALOG" ]]; then
    if [[ ! -f "$DIST_CATALOG" ]] || [[ "$FINAL_CATALOG" -nt "$DIST_CATALOG" ]]; then
      return 0
    fi
  fi
  # If neither catalog exists, this is a hard fail (caller bug)
  if [[ ! -f "$DIST_CATALOG" && ! -f "$FINAL_CATALOG" ]]; then
    err "Step 2/8: No catalog anywhere — step 1 should have caught this."
    err "         Run 'bash scripts/build_all_final_dbs.py' or rebuild_dashboard_snapshot.sh."
    exit 1
  fi
  return 1  # dist is current; skip
}

if step2_needs_run; then
  info "Step 2/8: final/dist mismatch — rebuilding through the gated candidate path..."
  bash scripts/rebuild_dashboard_snapshot.sh
  SCORING_SNAPSHOT_GATE_RAN=1
  ok "Catalog candidates gated and promoted"
else
  skip "Step 2/8: dist/ catalog already current — skipping stage"
fi

# ---------------------------------------------------------------------------
# Step 3: Extract/backfill DSLD product images into dist/
#
# Skip when: dist/product_images/product_image_index.json exists, the dist/
# catalog DB is not newer than that index, the DB already has
# product-images-backed thumbnail paths for every PDF-label product, and the
# corresponding .webp count is not short.
# ---------------------------------------------------------------------------

step3_needs_run() {
  (( FORCE == 1 )) && return 0
  [[ ! -f "$DIST_CATALOG" ]] && return 0
  [[ ! -d "$DIST_PRODUCT_IMAGES_DIR" ]] && return 0
  [[ ! -f "$DIST_PRODUCT_IMAGE_INDEX" ]] && return 0
  [[ "$DIST_CATALOG" -nt "$DIST_PRODUCT_IMAGE_INDEX" ]] && return 0

  local status
  status="$(
    "$PG_PYTHON" - "$DIST_CATALOG" "$DIST_PRODUCT_IMAGES_DIR" <<'PY'
import os
import sqlite3
import sys

db_path, image_dir = sys.argv[1], sys.argv[2]
conn = sqlite3.connect(db_path)
try:
    eligible = conn.execute(
        "SELECT COUNT(*) FROM products_core "
        "WHERE image_url IS NOT NULL AND image_url != '' "
        "AND LOWER(image_url) LIKE '%.pdf'"
    ).fetchone()[0]
    backfilled = conn.execute(
        "SELECT COUNT(*) FROM products_core "
        "WHERE image_url IS NOT NULL AND image_url != '' "
        "AND LOWER(image_url) LIKE '%.pdf' "
        "AND image_thumbnail_url LIKE 'product-images/%'"
    ).fetchone()[0]
finally:
    conn.close()

webp_count = 0
if os.path.isdir(image_dir):
    for name in os.listdir(image_dir):
        if name.endswith(".webp"):
            path = os.path.join(image_dir, name)
            if os.path.isfile(path) and os.path.getsize(path) > 0:
                webp_count += 1

needs_run = backfilled < eligible or webp_count < eligible
print("run" if needs_run else "skip")
PY
  )"
  [[ "$status" == "run" ]]
}

if (( SKIP_PRODUCT_IMAGES == 0 )); then
  if step3_needs_run; then
    info "Step 3/8: Catalog/images out of sync — extracting DSLD product images..."
    "$PG_PYTHON" scripts/extract_product_images.py --db-path "$DIST_CATALOG"
    ok "DSLD product images extracted + DB backfilled"
  else
    skip "Step 3/8: DSLD product images already current — skipping extraction"
  fi
else
  skip "Step 3/8: DSLD product image extraction skipped (--skip-product-images)"
fi

# Step 3 mutates the staged dist catalog in place when it backfills
# image_thumbnail_url and refreshes export_manifest.json. Mirror that canonical
# catalog back to final_db_output before freshness compares the two manifests.
sync_final_db_output_catalog_from_dist

# ---------------------------------------------------------------------------
# Step 4: Rebuild interaction DB (delegates verify → build → stage)
#
# Skip when: dist/interaction_db.sqlite is newer than every interaction-rule
# input file. The inputs are the curated drafts, the System A rules JSON,
# the drug-classes file, and the suppai research_pairs feed.
# ---------------------------------------------------------------------------

DIST_INTERACTION="$DIST_DIR/interaction_db.sqlite"
INTERACTION_INPUTS=(
  "$REPO_ROOT/scripts/data/curated_interactions/curated_interactions_v1.json"
  "$REPO_ROOT/scripts/data/curated_interactions/med_med_pairs_v1.json"
  "$REPO_ROOT/scripts/data/ingredient_interaction_rules.json"
  "$REPO_ROOT/scripts/data/drug_classes.json"
  "$REPO_ROOT/scripts/interaction_db_output/research_pairs.json"
)

step4_needs_run() {
  (( FORCE == 1 )) && return 0
  any_newer_input "$DIST_INTERACTION" "${INTERACTION_INPUTS[@]}"
}

if step4_needs_run; then
  info "Step 4/8: Interaction-rule inputs newer than bundled DB — rebuilding..."
  bash scripts/rebuild_interaction_db.sh
  ok "Interaction DB rebuilt + staged"
else
  skip "Step 4/8: Interaction DB up to date with rule sources — skipping rebuild"
fi

run_strict_gate "cleaner/IQD row contract" \
  "$PG_PYTHON" "$SOURCE_OF_TRUTH_AUDIT" cleaner --products-dir "$PRODUCTS_DIR" --strict-release
run_strict_gate "enrichment/IQD source-of-truth contract" \
  "$PG_PYTHON" "$SOURCE_OF_TRUTH_AUDIT" enrichment --products-dir "$PRODUCTS_DIR" --strict-release
run_strict_gate "clinical drift contract" \
  "$PG_PYTHON" "$SOURCE_OF_TRUTH_AUDIT" clinical --products-dir "$PRODUCTS_DIR" --strict-release
run_strict_gate "interaction DB parity" \
  "$PG_PYTHON" "$SOURCE_OF_TRUTH_AUDIT" interaction --dist-dir "$DIST_DIR" --strict-release
run_strict_gate "artifact freshness" \
  "$PG_PYTHON" "$SOURCE_OF_TRUTH_AUDIT" freshness \
    --dist-dir "$DIST_DIR" \
    --final-db-dir "$FINAL_DB_DIR" \
    --products-dir "$PRODUCTS_DIR" \
    --strict-release
run_strict_gate "stamp export manifest contract metadata" \
  "$PG_PYTHON" "$SOURCE_OF_TRUTH_AUDIT" stamp-manifest --dist-dir "$DIST_DIR" --strict-release
if [[ -f "$FINAL_DB_DIR/export_manifest.json" ]]; then
  run_strict_gate "stamp final_db_output manifest contract metadata" \
    "$PG_PYTHON" "$SOURCE_OF_TRUTH_AUDIT" stamp-manifest --dist-dir "$FINAL_DB_DIR" --strict-release
fi
run_strict_gate "export contract" \
  "$PG_PYTHON" "$SOURCE_OF_TRUTH_AUDIT" export --dist-dir "$DIST_DIR" --require-stamped-manifest --strict-release

# Pipeline reference files are canonical. Regenerate and validate both Flutter
# copies before any bundle commit can occur.
run_strict_gate "Flutter reference-data parity" \
  "$PG_PYTHON" scripts/sync_flutter_reference_data.py --flutter-repo "$FLUTTER_REPO"

# A fresh per-brand rebuild can materialize score changes from reviewed source
# data that earlier scored artifacts had not incorporated. Block publication
# until the snapshot baseline records any such reviewed change.
if (( SCORING_SNAPSHOT_GATE_RAN == 0 )); then
  run_strict_gate "scoring snapshot contract" \
    bash scripts/test.sh fast scripts/tests/test_scoring_snapshot_v1.py
else
  skip "Strict gate: scoring snapshot contract already passed before candidate promotion"
fi

# ---------------------------------------------------------------------------
# Step 5: Sync to Supabase (upload only; cleanup is post-bundle)
#
# We do NOT pre-skip this step — sync_to_supabase.py has built-in
# checksum-based "up_to_date" detection that is more reliable than mtime
# (catches edits that touched files without changing content). It exits
# 0 with status="up_to_date" when nothing changed.
# ---------------------------------------------------------------------------

if (( SKIP_SUPABASE == 0 )); then
  if (( SUPABASE_DRY_RUN == 1 )); then
    info "Step 5/8: Syncing dist/ to Supabase (DRY-RUN)..."
    "$PG_PYTHON" scripts/sync_to_supabase.py "$DIST_DIR" --dry-run
    warn "Supabase sync was DRY-RUN — nothing actually uploaded"
  else
    info "Step 5/8: Syncing dist/ to Supabase (upload only; cleanup deferred)..."
    # Storage cleanup (version dirs + orphan blobs) is NO LONGER run here.
    # It moved to the aligned-cleanup step below, AFTER the Flutter bundle is
    # committed. Reason: the orphan-cleanup bundle_alignment gate compares
    # Flutter main HEAD to the just-built dist version, but at THIS point the
    # new bundle has not been imported or committed yet — so the gate rejected
    # the sweep on every release and orphan blobs accumulated to ~84% of
    # storage (cleanup quarantined 0 across 80 runs). Deferring cleanup until
    # after the bundle commit lets the gate pass.
    "$PG_PYTHON" scripts/sync_to_supabase.py "$DIST_DIR"
  fi
  ok "Supabase step done (uploaded if changed; up-to-date otherwise)"
else
  skip "Step 5/8: Supabase sync skipped (--skip-supabase)"
fi

# ---------------------------------------------------------------------------
# Step 6: Atomic Flutter bundle import
#
# Skip when: Flutter assets/db/ checksums already match dist/ — both
# catalog AND interaction manifests. This avoids a 22 MB LFS upload on
# every release when nothing actually changed.
# ---------------------------------------------------------------------------

step6_needs_run() {
  (( FORCE == 1 )) && return 0
  # Compare both manifest checksums dist/ vs Flutter assets/
  local dist_cat dist_int flu_cat flu_int dist_cat_manifest dist_int_manifest flu_cat_manifest flu_int_manifest
  dist_cat=$(json_field "$DIST_DIR/export_manifest.json" "checksum_sha256")
  dist_int=$(json_field "$DIST_DIR/interaction_db_manifest.json" "checksum_sha256")
  flu_cat=$(json_field "$ASSETS_DIR/export_manifest.json" "checksum_sha256")
  flu_int=$(json_field "$ASSETS_DIR/interaction_db_manifest.json" "checksum_sha256")
  dist_cat_manifest=$(file_sha256 "$DIST_DIR/export_manifest.json")
  dist_int_manifest=$(file_sha256 "$DIST_DIR/interaction_db_manifest.json")
  flu_cat_manifest=$(file_sha256 "$ASSETS_DIR/export_manifest.json")
  flu_int_manifest=$(file_sha256 "$ASSETS_DIR/interaction_db_manifest.json")
  # If any manifest missing on either side → run
  [[ -z "$dist_cat" || -z "$flu_cat" || -z "$dist_int" || -z "$flu_int" ]] && return 0
  # If either checksum differs → run
  [[ "$dist_cat" != "$flu_cat" || "$dist_int" != "$flu_int" ]] && return 0
  # If manifest metadata differs → run so Flutter receives contract stamps too.
  [[ "$dist_cat_manifest" != "$flu_cat_manifest" || "$dist_int_manifest" != "$flu_int_manifest" ]] && return 0
  return 1
}

if (( SKIP_FLUTTER == 0 )); then
  if [[ ! -x "$FLUTTER_REPO/scripts/import_catalog_artifact.sh" ]]; then
    err "Flutter import script not found or not executable:"
    err "  $FLUTTER_REPO/scripts/import_catalog_artifact.sh"
    err "Pass --flutter-repo <path> if your Flutter checkout lives elsewhere"
    err "or --skip-flutter to bypass this step."
    exit 1
  fi
  if step6_needs_run; then
    info "Step 6/8: Checksums differ between dist/ and Flutter assets/ — importing..."
    "$FLUTTER_REPO/scripts/import_catalog_artifact.sh" "$DIST_DIR"
    ok "Flutter bundle updated"
  else
    skip "Step 6/8: Flutter bundle checksums already match dist/ — skipping import"
  fi
  run_strict_gate "Flutter bundle parity" \
    "$PG_PYTHON" "$SOURCE_OF_TRUTH_AUDIT" flutter \
      --dist-dir "$DIST_DIR" \
      --flutter-repo "$FLUTTER_REPO" \
      --strict-release
else
  skip "Step 6/8: Flutter import skipped (--skip-flutter)"
fi

# ---------------------------------------------------------------------------
# Step 7: Prune .previous backups in Flutter assets/db/
# (No-op when none exist — always safe to attempt.)
# ---------------------------------------------------------------------------

if (( SKIP_FLUTTER == 0 )); then
  shopt -s nullglob
  PREVS=("$ASSETS_DIR"/*.previous)
  shopt -u nullglob
  if (( ${#PREVS[@]} > 0 )); then
    info "Step 7/8: Pruning ${#PREVS[@]} .previous backup(s) in $ASSETS_DIR..."
    for p in "${PREVS[@]}"; do
      info "  removing $(basename "$p")"
      rm -f "$p"
    done
    ok "Pruned"
  else
    skip "Step 7/8: No .previous backups to prune"
  fi
else
  skip "Step 7/8: Skipped (Flutter step disabled)"
fi

# Resolve the freshly-bundled versions from the Flutter assets/db/ manifests
# (used for the auto-commit message and the next-steps summary). Falls back to
# "unknown" if a manifest is unreadable (skipped Flutter step, etc.).
CATALOG_VERSION="$("$PG_PYTHON" -c "import json,sys; print(json.load(open(sys.argv[1])).get('db_version','unknown'))" "$ASSETS_DIR/export_manifest.json" 2>/dev/null || echo unknown)"
INTERACTION_VERSION="$("$PG_PYTHON" -c "import json,sys; print(json.load(open(sys.argv[1])).get('interaction_db_version','unknown'))" "$ASSETS_DIR/interaction_db_manifest.json" 2>/dev/null || echo unknown)"

# ---------------------------------------------------------------------------
# Commit the Flutter bundle + run ALIGNED storage cleanup.
#
# The orphan-blob cleanup was moved out of Step 5 to here: its bundle_alignment
# gate needs Flutter main HEAD to equal the just-built dist version. We commit
# the bundle LOCALLY first (push stays manual), then run the cleanup so the
# gate passes — fixing the deadlock that let orphan blobs grow to ~84% of
# storage (0 blobs quarantined across 80 prior release runs).
# ---------------------------------------------------------------------------
if (( SKIP_FLUTTER == 0 && SKIP_SUPABASE == 0 && SUPABASE_DRY_RUN == 0 )); then
  if git -C "$FLUTTER_REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    if git -C "$FLUTTER_REPO" status --porcelain -- assets/db assets/reference_data/rda_optimal_uls.json assets/data/product_type_vocab.json | grep -q .; then
      info "Committing Flutter bundle and canonical reference data (local) so storage cleanup runs aligned..."
      git -C "$FLUTTER_REPO" add assets/db/ assets/reference_data/rda_optimal_uls.json assets/data/product_type_vocab.json
      if git -C "$FLUTTER_REPO" commit -q -m "chore(catalog): bundle catalog v${CATALOG_VERSION} + interaction v${INTERACTION_VERSION}"; then
        ok "Flutter bundle committed locally (push remains manual)"
      else
        warn "Flutter bundle commit failed — cleanup may reject on bundle_alignment"
      fi
    else
      skip "Flutter bundle already committed — nothing to commit"
    fi

    info "Step 8/8: Aligned storage cleanup (version dirs + orphan blobs)..."
    # No --expected-count: blast-radius stays a backstop. A big-churn release
    # that would delete >5% is logged and left for a manual authorized sweep
    # (cleanup_old_versions.py --execute --cleanup-orphan-blobs ... --expected-count N).
    # Quarantine is a recoverable MOVE (30-day TTL), not a hard delete.
    if "$PG_PYTHON" scripts/cleanup_old_versions.py \
        --execute --cleanup-db --cleanup-orphan-blobs \
        --keep "$KEEP_VERSIONS" \
        --flutter-repo "$FLUTTER_REPO" \
        --dist-dir "$DIST_DIR"; then
      ok "Storage cleanup step done"
    else
      warn "Storage cleanup returned non-zero — non-fatal; see reports/release_audit/"
    fi
  else
    warn "$FLUTTER_REPO is not a git work tree — skipping bundle commit + cleanup"
  fi
else
  skip "Bundle commit + aligned cleanup skipped (flutter/supabase disabled or dry-run)"
fi

ELAPSED=$(($(date +%s) - START_TS))
echo ""
ok "Full release pipeline completed in ${ELAPSED}s"
info ""

info "Next steps (push the auto-committed bundle):"
info "  cd \"$FLUTTER_REPO\""
info "  git log --oneline -1       # the pipeline committed the bundle locally"
info "  git push origin main"
info ""
info "  cd $REPO_ROOT"
info "  git push origin main       # if any pipeline-side commits are unpushed"
