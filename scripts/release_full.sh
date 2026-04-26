#!/usr/bin/env bash
#
# release_full.sh — One-command catalog + interaction DB release pipeline.
#
# Picks up where the per-brand pipeline (run_pipeline.py) leaves off and
# delivers fresh data all the way from build_final_db → Supabase → Flutter
# bundled assets in one atomic flow. Each step gates the next: failure at
# any stage stops the rest, leaving the previous good release in place.
#
# Steps (in order):
#   1. Assemble final DB           (build_all_final_dbs.py)
#   2. Stage catalog to dist/      (release_catalog_artifact.py)
#   3. Rebuild interaction DB      (rebuild_interaction_db.sh) — picks up
#                                  any IQM / curated_interactions changes
#   4. Sync to Supabase --cleanup  (sync_to_supabase.py)
#   5. Atomic Flutter bundle       (Flutter's import_catalog_artifact.sh)
#   6. Prune .previous backups     (assets/db/*.previous)
#
# Usage:
#     # Standard release (interactive Supabase confirmation):
#     bash scripts/release_full.sh
#
#     # Skip Supabase (e.g. dev iteration before push):
#     bash scripts/release_full.sh --skip-supabase
#
#     # Skip Flutter import (release pipeline-side only):
#     bash scripts/release_full.sh --skip-flutter
#
#     # Dry-run Supabase (preview what would upload):
#     bash scripts/release_full.sh --supabase-dry-run
#
#     # Skip the assembly step (already-built dist/ ready for re-release):
#     bash scripts/release_full.sh --skip-assemble
#
#     # Custom Flutter repo location:
#     bash scripts/release_full.sh --flutter-repo /path/to/PharmaGuide_ai
#
# Prerequisites:
#     - Per-brand pipeline already ran: output_<brand>_{enriched,scored}/ exist
#     - .env at repo root has UMLS_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY
#     - Flutter repo exists at $FLUTTER_REPO (or pass --flutter-repo)
#
# Exit codes:
#     0  full release pipeline completed
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
SKIP_ASSEMBLE=0
SKIP_SUPABASE=0
SKIP_FLUTTER=0
SUPABASE_DRY_RUN=0
KEEP_VERSIONS=2

# ---------------------------------------------------------------------------
# CLI parsing
# ---------------------------------------------------------------------------

while (($# > 0)); do
  case "$1" in
    --skip-assemble)     SKIP_ASSEMBLE=1; shift ;;
    --skip-supabase)     SKIP_SUPABASE=1; shift ;;
    --skip-flutter)      SKIP_FLUTTER=1; shift ;;
    --supabase-dry-run)  SUPABASE_DRY_RUN=1; shift ;;
    --keep-versions)     KEEP_VERSIONS="${2:?--keep-versions requires N}"; shift 2 ;;
    --flutter-repo)      FLUTTER_REPO="${2:?--flutter-repo requires path}"; shift 2 ;;
    -h|--help)
      sed -n '2,46p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "Unknown flag: $1" >&2; exit 2 ;;
  esac
done

info()  { printf '\033[36m[release]\033[0m %s\n' "$*"; }
ok()    { printf '\033[32m[release] OK:\033[0m %s\n' "$*"; }
warn()  { printf '\033[33m[release] WARN:\033[0m %s\n' "$*"; }
err()   { printf '\033[31m[release] ERROR:\033[0m %s\n' "$*" >&2; }

DIST_DIR="$REPO_ROOT/scripts/dist"
ASSETS_DIR="$FLUTTER_REPO/assets/db"

START_TS=$(date +%s)

info "================================================================"
info "PharmaGuide — Full Release Pipeline"
info "================================================================"
info "skip-assemble:    $SKIP_ASSEMBLE"
info "skip-supabase:    $SKIP_SUPABASE  (supabase-dry-run: $SUPABASE_DRY_RUN)"
info "skip-flutter:     $SKIP_FLUTTER"
info "keep-versions:    $KEEP_VERSIONS"
info "flutter-repo:     $FLUTTER_REPO"
info "================================================================"

# ---------------------------------------------------------------------------
# Step 1: Assemble final DB from per-brand outputs
# ---------------------------------------------------------------------------

if (( SKIP_ASSEMBLE == 0 )); then
  info "Step 1/6: Assembling final DB from per-brand outputs..."
  python3 scripts/build_all_final_dbs.py
  ok "Final DB assembled (scripts/final_db_output/)"
else
  info "Step 1/6: Skipped (--skip-assemble)"
fi

# ---------------------------------------------------------------------------
# Step 2: Stage catalog to dist/
# ---------------------------------------------------------------------------

info "Step 2/6: Staging catalog artifact to dist/..."
python3 scripts/release_catalog_artifact.py
ok "Catalog staged"

# ---------------------------------------------------------------------------
# Step 3: Rebuild interaction DB (delegates verify → build → stage)
# ---------------------------------------------------------------------------

info "Step 3/6: Rebuilding interaction DB..."
bash scripts/rebuild_interaction_db.sh
ok "Interaction DB rebuilt + staged"

# ---------------------------------------------------------------------------
# Step 4: Sync to Supabase (with full cleanup)
# ---------------------------------------------------------------------------

if (( SKIP_SUPABASE == 0 )); then
  info "Step 4/6: Syncing dist/ to Supabase (with --cleanup)..."
  if (( SUPABASE_DRY_RUN == 1 )); then
    python3 scripts/sync_to_supabase.py "$DIST_DIR" --dry-run
    warn "Supabase sync was DRY-RUN — nothing actually uploaded"
  else
    python3 scripts/sync_to_supabase.py "$DIST_DIR" --cleanup --cleanup-keep "$KEEP_VERSIONS"
  fi
  ok "Supabase synced"
else
  info "Step 4/6: Skipped (--skip-supabase)"
fi

# ---------------------------------------------------------------------------
# Step 5: Atomic Flutter bundle import
# ---------------------------------------------------------------------------

if (( SKIP_FLUTTER == 0 )); then
  info "Step 5/6: Importing dist/ artifacts into Flutter assets/..."
  if [[ ! -x "$FLUTTER_REPO/scripts/import_catalog_artifact.sh" ]]; then
    err "Flutter import script not found or not executable:"
    err "  $FLUTTER_REPO/scripts/import_catalog_artifact.sh"
    err "Pass --flutter-repo <path> if your Flutter checkout lives elsewhere"
    err "or --skip-flutter to bypass this step."
    exit 1
  fi
  "$FLUTTER_REPO/scripts/import_catalog_artifact.sh" "$DIST_DIR"
  ok "Flutter bundle updated"
else
  info "Step 5/6: Skipped (--skip-flutter)"
fi

# ---------------------------------------------------------------------------
# Step 6: Prune .previous backups in Flutter assets/db/
# ---------------------------------------------------------------------------

if (( SKIP_FLUTTER == 0 )); then
  info "Step 6/6: Pruning .previous backups in $ASSETS_DIR..."
  shopt -s nullglob
  PREVS=("$ASSETS_DIR"/*.previous)
  shopt -u nullglob
  if (( ${#PREVS[@]} > 0 )); then
    for p in "${PREVS[@]}"; do
      info "  removing $(basename "$p")"
      rm -f "$p"
    done
    ok "Pruned ${#PREVS[@]} backup file(s)"
  else
    info "  (no .previous backups to prune)"
  fi
else
  info "Step 6/6: Skipped (--skip-flutter)"
fi

ELAPSED=$(($(date +%s) - START_TS))
echo ""
ok "Full release pipeline completed in ${ELAPSED}s"
info ""
info "Next steps (manual):"
info "  cd \"$FLUTTER_REPO\""
info "  git status                 # review assets/db/ changes (LFS-tracked)"
info "  git add assets/db/"
info "  git commit -m 'chore(catalog): bundle catalog + interaction <version>'"
info "  git push origin main"
info ""
info "  cd $REPO_ROOT"
info "  git push origin main       # if any pipeline-side commits are unpushed"
