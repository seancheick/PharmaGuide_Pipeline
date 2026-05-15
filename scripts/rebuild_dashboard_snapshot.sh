#!/usr/bin/env bash
#
# rebuild_dashboard_snapshot.sh — rebuild scripts/dist/ for the Streamlit dashboard.
#
# The Streamlit dashboard at scripts/dashboard/ loads a release snapshot from
# scripts/dist/. That directory is gitignored (build artifact), so after a
# fresh clone, a `git clean`, or adding new brands to scripts/products/, the
# dashboard sees no data and every view renders blank.
#
# This script rebuilds it in one step:
#   1. Discovers every scripts/products/*_enriched/enriched and *_scored/scored pair.
#   2. Runs build_final_db.py across all of them into a /tmp staging dir.
#   3. Stages the release bundle into scripts/dist/ via release_catalog_artifact.py.
#   4. Copies detail_index.json + detail_blobs/ into scripts/dist/ (the dashboard
#      needs these for the Product Inspector; the release-stage script only ships
#      the catalog DB and manifest because those are what Flutter consumes).
#
# Usage:
#     bash scripts/rebuild_dashboard_snapshot.sh
#
# Runtime: ~1 minute on current 20-brand catalog.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

STAGING="/tmp/pg_dashboard_snapshot_$$"
trap 'rm -rf "$STAGING"' EXIT

# 1. Collect enriched + scored dirs.
ENR=(scripts/products/*_enriched/enriched)
SCR=(scripts/products/*_scored/scored)

if [[ ${#ENR[@]} -eq 0 || ${#SCR[@]} -eq 0 ]]; then
  echo "✗ No enriched/scored outputs found under scripts/products/."
  echo "  Run the pipeline first (scripts/run_pipeline.py <dataset_dir>) before rebuilding the dashboard snapshot."
  exit 1
fi

echo "◦ Building from ${#ENR[@]} enriched dirs + ${#SCR[@]} scored dirs..."

# 2. Build into /tmp.
PYTHON="${PYTHON:-/Users/seancheick/.pyenv/versions/3.13.3/bin/python3}"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="python3"
fi

"$PYTHON" scripts/build_final_db.py \
  --enriched-dir "${ENR[@]}" \
  --scored-dir "${SCR[@]}" \
  --output-dir "$STAGING" \
  2>&1 | tail -5

# 3. Stage the complete release bundle into scripts/dist/.
#
# release_catalog_artifact.py is the SINGLE owner of populating dist/:
# pharmaguide_core.db, export_manifest.json, RELEASE_NOTES.md,
# detail_index.json, detail_blobs/, and (if present) export_audit_report.json.
# Previously this script had a manual `cp` workaround at this position to
# patch around release_catalog_artifact.py wiping the detail artifacts.
# That workaround moved INTO release_catalog_artifact.py (commit a81c6e3),
# so the manual copies here are now redundant and would silently drift if
# the staging script's behavior changes. Removed 2026-05-15.
"$PYTHON" scripts/release_catalog_artifact.py \
  --input-dir "$STAGING" \
  --output-dir scripts/dist \
  2>&1 | tail -5

# 4. Mirror the working build into scripts/final_db_output/ so dev tools
#    that default to that path (build_final_db.py legacy default,
#    release_catalog_artifact.py --input-dir default, audit_raw_to_final.py
#    --build-dir default) always see today's data — never a stale leftover.
#    This is the "no mixed builds" guarantee: both scripts/dist/ and
#    scripts/final_db_output/ are refreshed atomically on every pipeline run.
#    Added 2026-05-14 — see freshness guard in release_catalog_artifact.py.
rm -rf scripts/final_db_output
mkdir -p scripts/final_db_output
cp -r "$STAGING/." scripts/final_db_output/

PRODUCT_COUNT=$("$PYTHON" -c "import sqlite3; print(sqlite3.connect('scripts/dist/pharmaguide_core.db').execute('SELECT COUNT(*) FROM products_core').fetchone()[0])")
BLOB_COUNT=$(ls scripts/dist/detail_blobs | wc -l | tr -d ' ')

echo ""
echo "✓ Dashboard snapshot ready:"
echo "  scripts/dist/pharmaguide_core.db              $PRODUCT_COUNT products"
echo "  scripts/dist/detail_blobs/                    $BLOB_COUNT blobs"
echo "  scripts/final_db_output/ (working-build mirror, also $PRODUCT_COUNT products)"
echo ""
echo "Launch the dashboard:"
echo "  streamlit run scripts/dashboard/app.py"
