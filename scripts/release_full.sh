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
#   1. Assemble final DB           (build_all_final_dbs.py)
#                                  AUTO-SKIPS when dist/ catalog is already
#                                  fresh relative to per-brand outputs.
#   2. Stage catalog to dist/      (release_catalog_artifact.py)
#                                  AUTO-SKIPS when dist/ catalog is already
#                                  in sync with final_db_output/ (or when
#                                  another upstream — e.g. snapshot — staged
#                                  it directly).
#   3. Extract DSLD product images (extract_product_images.py)
#                                  AUTO-SKIPS when dist/ image backfill is
#                                  already complete and current.
#   4. Rebuild interaction DB      (rebuild_interaction_db.sh)
#                                  AUTO-SKIPS when no rule-data file is
#                                  newer than the bundled interaction_db.
#   5. Sync to Supabase            (sync_to_supabase.py --cleanup)
#                                  Trusts sync_to_supabase's built-in
#                                  "up_to_date" detection (manifest checksum).
#   6. Atomic Flutter bundle       (Flutter import_catalog_artifact.sh)
#                                  AUTO-SKIPS when Flutter assets/db/
#                                  manifests already match dist/ checksums.
#   7. Prune .previous backups     (assets/db/*.previous)
#                                  No-ops cleanly when none exist.
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
  python3 -c "
import json, sys
try:
    with open('$path') as f: d = json.load(f)
    print(d.get('$key', ''))
except Exception:
    pass
" 2>/dev/null
}

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

PRODUCTS_DIR="$REPO_ROOT/scripts/products"
DIST_CATALOG="$DIST_DIR/pharmaguide_core.db"
FINAL_CATALOG="$FINAL_DB_DIR/pharmaguide_core.db"

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
  return 1  # safe to skip
}

if step1_needs_run; then
  info "Step 1/7: Per-brand outputs newer than catalog (or catalog missing) — assembling..."
  # build_all_final_dbs.py defaults its scan dir to scripts/ but per-brand
  # pipeline outputs live in scripts/products/output_*/. Always pass an
  # explicit --scan-dir so the auto-discovery actually finds them.
  python3 scripts/build_all_final_dbs.py --scan-dir scripts/products --output-dir scripts/final_db_output
  ok "Final DB assembled (scripts/final_db_output/)"
else
  skip "Step 1/7: Catalog up to date with per-brand outputs — skipping assembly"
fi

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
    err "Step 2/7: No catalog anywhere — step 1 should have caught this."
    err "         Run 'bash scripts/build_all_final_dbs.py' or rebuild_dashboard_snapshot.sh."
    exit 1
  fi
  return 1  # dist is current; skip
}

if step2_needs_run; then
  info "Step 2/7: final_db_output newer than dist/ — staging catalog..."
  python3 scripts/release_catalog_artifact.py
  ok "Catalog staged"
else
  skip "Step 2/7: dist/ catalog already current — skipping stage"
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
    python3 - "$DIST_CATALOG" "$DIST_PRODUCT_IMAGES_DIR" <<'PY'
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
    info "Step 3/7: Catalog/images out of sync — extracting DSLD product images..."
    python3 scripts/extract_product_images.py --db-path "$DIST_CATALOG"
    ok "DSLD product images extracted + DB backfilled"
  else
    skip "Step 3/7: DSLD product images already current — skipping extraction"
  fi
else
  skip "Step 3/7: DSLD product image extraction skipped (--skip-product-images)"
fi

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
  info "Step 4/7: Interaction-rule inputs newer than bundled DB — rebuilding..."
  bash scripts/rebuild_interaction_db.sh
  ok "Interaction DB rebuilt + staged"
else
  skip "Step 4/7: Interaction DB up to date with rule sources — skipping rebuild"
fi

# ---------------------------------------------------------------------------
# Step 5: Sync to Supabase (with full cleanup)
#
# We do NOT pre-skip this step — sync_to_supabase.py has built-in
# checksum-based "up_to_date" detection that is more reliable than mtime
# (catches edits that touched files without changing content). It exits
# 0 with status="up_to_date" when nothing changed.
# ---------------------------------------------------------------------------

if (( SKIP_SUPABASE == 0 )); then
  if (( SUPABASE_DRY_RUN == 1 )); then
    info "Step 5/7: Syncing dist/ to Supabase (DRY-RUN)..."
    python3 scripts/sync_to_supabase.py "$DIST_DIR" --dry-run
    warn "Supabase sync was DRY-RUN — nothing actually uploaded"
  else
    info "Step 5/7: Syncing dist/ to Supabase (with --cleanup, content-checksum-aware)..."
    python3 scripts/sync_to_supabase.py "$DIST_DIR" --cleanup --cleanup-keep "$KEEP_VERSIONS"
  fi
  ok "Supabase step done (uploaded if changed; up-to-date otherwise)"
else
  skip "Step 5/7: Supabase sync skipped (--skip-supabase)"
fi

# ---------------------------------------------------------------------------
# Step 6: Atomic Flutter bundle import
#
# Skip when: Flutter assets/db/ checksums already match dist/ — both
# catalog AND interaction manifests. This avoids a 22 MB LFS upload on
# every release when nothing actually changed.
# ---------------------------------------------------------------------------

step5_needs_run() {
  (( FORCE == 1 )) && return 0
  # Compare both manifest checksums dist/ vs Flutter assets/
  local dist_cat dist_int flu_cat flu_int
  dist_cat=$(json_field "$DIST_DIR/export_manifest.json" "checksum_sha256")
  dist_int=$(json_field "$DIST_DIR/interaction_db_manifest.json" "checksum_sha256")
  flu_cat=$(json_field "$ASSETS_DIR/export_manifest.json" "checksum_sha256")
  flu_int=$(json_field "$ASSETS_DIR/interaction_db_manifest.json" "checksum_sha256")
  # If any manifest missing on either side → run
  [[ -z "$dist_cat" || -z "$flu_cat" || -z "$dist_int" || -z "$flu_int" ]] && return 0
  # If either checksum differs → run
  [[ "$dist_cat" != "$flu_cat" || "$dist_int" != "$flu_int" ]] && return 0
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
  if step5_needs_run; then
    info "Step 6/7: Checksums differ between dist/ and Flutter assets/ — importing..."
    "$FLUTTER_REPO/scripts/import_catalog_artifact.sh" "$DIST_DIR"
    ok "Flutter bundle updated"
  else
    skip "Step 6/7: Flutter bundle checksums already match dist/ — skipping import"
  fi
else
  skip "Step 6/7: Flutter import skipped (--skip-flutter)"
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
    info "Step 7/7: Pruning ${#PREVS[@]} .previous backup(s) in $ASSETS_DIR..."
    for p in "${PREVS[@]}"; do
      info "  removing $(basename "$p")"
      rm -f "$p"
    done
    ok "Pruned"
  else
    skip "Step 7/7: No .previous backups to prune"
  fi
else
  skip "Step 7/7: Skipped (Flutter step disabled)"
fi

ELAPSED=$(($(date +%s) - START_TS))
echo ""
ok "Full release pipeline completed in ${ELAPSED}s"
info ""

# Resolve the freshly-bundled versions from the Flutter assets/db/ manifests
# so the next-steps message prints a copy-pasteable commit command instead of
# a literal "<version>" placeholder. Falls back to "unknown" if the manifest
# is unreadable (skipped Flutter step, missing jq, etc.) — the user will see
# the placeholder and know something needs investigating before committing.
CATALOG_VERSION="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('db_version','unknown'))" "$ASSETS_DIR/export_manifest.json" 2>/dev/null || echo unknown)"
INTERACTION_VERSION="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('interaction_db_version','unknown'))" "$ASSETS_DIR/interaction_db_manifest.json" 2>/dev/null || echo unknown)"

info "Next steps (manual git-side):"
info "  cd \"$FLUTTER_REPO\""
info "  git status                 # review assets/db/ changes (LFS-tracked)"
info "  git add assets/db/"
info "  git commit -m 'chore(catalog): bundle catalog v${CATALOG_VERSION} + interaction v${INTERACTION_VERSION}'"
info "  git push origin main"
info ""
info "  cd $REPO_ROOT"
info "  git push origin main       # if any pipeline-side commits are unpushed"
