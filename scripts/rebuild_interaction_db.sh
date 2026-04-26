#!/usr/bin/env bash
#
# rebuild_interaction_db.sh — Full interaction DB pipeline in one command.
#
# Runs: verify → build → stage → (optionally) import into Flutter
#
# Usage:
#     # Build and stage only (pipeline side)
#     bash scripts/rebuild_interaction_db.sh
#
#     # Build, stage, AND import into Flutter app
#     bash scripts/rebuild_interaction_db.sh --import
#
#     # Offline mode (skip live API checks — schema validation only)
#     bash scripts/rebuild_interaction_db.sh --offline
#
#     # Bump version
#     bash scripts/rebuild_interaction_db.sh --version 1.1.0
#
# Prerequisites:
#     - .env file at repo root with UMLS_API_KEY (for live CUI verification)
#     - research_pairs.json already built (run ingest_suppai.py separately)
#     - For --import: catalog DB must be in dist/ (run release_catalog_artifact.py first,
#       or the script will attempt to stage it from final_db_output/ automatically)
#
# The script stops on first error. No partial output is promoted to dist/.
#

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

INTERACTION_VERSION="1.0.0"
OFFLINE_FLAG=""
DO_IMPORT=0
FLUTTER_REPO="/Users/seancheick/PharmaGuide ai"

# Single source of truth: pull pipeline version from build_final_db.py
# (catalog and interaction artifacts must agree on pipeline_version).
PIPELINE_VERSION="$(grep -E '^PIPELINE_VERSION[[:space:]]*=' scripts/build_final_db.py | head -1 | awk -F'"' '{print $2}')"
if [[ -z "$PIPELINE_VERSION" ]]; then
  echo "ERROR: could not read PIPELINE_VERSION from scripts/build_final_db.py" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# CLI parsing
# ---------------------------------------------------------------------------

while (($# > 0)); do
  case "$1" in
    --version)   INTERACTION_VERSION="${2:?--version requires a value}"; shift 2 ;;
    --offline)   OFFLINE_FLAG="--offline"; shift ;;
    --import)    DO_IMPORT=1; shift ;;
    --flutter-repo) FLUTTER_REPO="${2:?--flutter-repo requires a path}"; shift 2 ;;
    -h|--help)
      sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "Unknown flag: $1" >&2; exit 2 ;;
  esac
done

info()  { printf '\033[36m[rebuild]\033[0m %s\n' "$*"; }
ok()    { printf '\033[32m[rebuild] OK:\033[0m %s\n' "$*"; }
err()   { printf '\033[31m[rebuild] ERROR:\033[0m %s\n' "$*" >&2; }

OUTPUT_DIR="scripts/interaction_db_output"
DIST_DIR="scripts/dist"
mkdir -p "$OUTPUT_DIR" "$DIST_DIR"

# ---------------------------------------------------------------------------
# Check prerequisites
# ---------------------------------------------------------------------------

if [[ ! -f "$OUTPUT_DIR/research_pairs.json" ]]; then
  info "research_pairs.json not found — running ingest_suppai.py first..."
  python3 scripts/ingest_suppai.py \
    --output "$OUTPUT_DIR/research_pairs.json" \
    --report "$OUTPUT_DIR/ingest_suppai_report.json"
  ok "supp.ai ingest complete"
fi

# ---------------------------------------------------------------------------
# Step 1: Verify curated interactions
# ---------------------------------------------------------------------------

info "Step 1/4: Verifying curated interactions..."
python3 scripts/api_audit/verify_interactions.py \
  --drafts scripts/data/curated_interactions \
  --report "$OUTPUT_DIR/interaction_audit_report.json" \
  --normalized-out "$OUTPUT_DIR/interactions_verified.json" \
  --corrections-out "$OUTPUT_DIR/corrections.json" \
  $OFFLINE_FLAG

ok "Verification passed"

# ---------------------------------------------------------------------------
# Step 2: Build SQLite
# ---------------------------------------------------------------------------

info "Step 2/4: Building interaction_db.sqlite..."
python3 scripts/build_interaction_db.py \
  --normalized-drafts "$OUTPUT_DIR/interactions_verified.json" \
  --research-pairs "$OUTPUT_DIR/research_pairs.json" \
  --drug-classes scripts/data/drug_classes.json \
  --output "$OUTPUT_DIR/interaction_db.sqlite" \
  --manifest "$OUTPUT_DIR/interaction_db_manifest.json" \
  --report "$OUTPUT_DIR/build_audit_report.json" \
  --interaction-db-version "$INTERACTION_VERSION" \
  --pipeline-version "$PIPELINE_VERSION"

ok "SQLite built"

# ---------------------------------------------------------------------------
# Step 3: Stage release
# ---------------------------------------------------------------------------

info "Step 3/4: Staging release to dist/..."
python3 scripts/release_interaction_artifact.py

ok "Interaction DB staged to $DIST_DIR/"

# ---------------------------------------------------------------------------
# Step 4 (optional): Import into Flutter
# ---------------------------------------------------------------------------

if (( DO_IMPORT == 1 )); then
  info "Step 4/4: Importing into Flutter..."

  # Ensure catalog DB is also in dist/ (required by import script)
  if [[ ! -f "$DIST_DIR/pharmaguide_core.db" ]]; then
    info "Catalog DB not in dist/ — attempting to stage from final_db_output/..."
    if [[ -f "scripts/final_db_output/pharmaguide_core.db" ]]; then
      python3 scripts/release_catalog_artifact.py
      ok "Catalog staged"
    else
      err "No catalog DB available. Run the catalog pipeline first, or"
      err "copy the existing bundled catalog:"
      err "  cp \"$FLUTTER_REPO/assets/db/pharmaguide_core.db\" $DIST_DIR/"
      err "  cp \"$FLUTTER_REPO/assets/db/export_manifest.json\" $DIST_DIR/"
      exit 1
    fi
  fi

  # Run the atomic import
  "$FLUTTER_REPO/scripts/import_catalog_artifact.sh" "$REPO_ROOT/$DIST_DIR"
  ok "Imported into Flutter"
else
  info "Step 4/4: Skipped (use --import to auto-import into Flutter)"
  info ""
  info "To import manually:"
  info "  cd \"$FLUTTER_REPO\""
  info "  ./scripts/import_catalog_artifact.sh $REPO_ROOT/$DIST_DIR"
fi

echo ""
ok "Done! Interaction DB v$INTERACTION_VERSION ready."
