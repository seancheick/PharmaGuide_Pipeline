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
#   2. Runs every source gate before catalog assembly.
#   3. Builds and stages sibling candidate directories without touching live data.
#   4. Runs every artifact gate against those candidates.
#   5. Promotes both candidates together with rollback on any rename failure.
#
# Usage:
#     bash scripts/rebuild_dashboard_snapshot.sh
#
# Runtime: ~1 minute on current 20-brand catalog.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
source "$REPO_ROOT/scripts/python_env.sh"

FINAL_CANDIDATE="$REPO_ROOT/scripts/.final_db_output.candidate.$$"
DIST_CANDIDATE="$REPO_ROOT/scripts/.dist.candidate.$$"
SOURCE_OF_TRUTH_AUDIT="$REPO_ROOT/scripts/audit_source_of_truth_contract.py"
trap 'rm -rf "$FINAL_CANDIDATE" "$DIST_CANDIDATE" "${DIST_CANDIDATE}.staging"' EXIT

run_strict_gate() {
  local label="$1"; shift
  echo "◦ Strict gate: $label"
  "$@"
}

run_strict_gate "source-of-truth matrix" \
  "$PG_PYTHON" "$SOURCE_OF_TRUTH_AUDIT" matrix --strict-release
run_strict_gate "cleaner/IQD row contract" \
  "$PG_PYTHON" "$SOURCE_OF_TRUTH_AUDIT" cleaner --products-dir scripts/products --strict-release
run_strict_gate "enrichment/IQD source-of-truth contract" \
  "$PG_PYTHON" "$SOURCE_OF_TRUTH_AUDIT" enrichment --products-dir scripts/products --strict-release
run_strict_gate "clinical drift contract" \
  "$PG_PYTHON" "$SOURCE_OF_TRUTH_AUDIT" clinical --products-dir scripts/products --strict-release
run_strict_gate "active identity integrity" \
  "$PG_PYTHON" scripts/audit_identity_integrity.py --products-dir scripts/products
run_strict_gate "RDA/UL emitted-reference stamp parity" \
  "$PG_PYTHON" scripts/audit_rda_ul_reference_stamps.py --products-dir scripts/products
run_strict_gate "scoring snapshot contract" \
  bash scripts/test.sh fast scripts/tests/test_scoring_snapshot_v1.py

# 1. Collect enriched + scored dirs.
shopt -s nullglob
ENR=(scripts/products/*_enriched/enriched)
SCR=(scripts/products/*_scored/scored)
shopt -u nullglob

if [[ ${#ENR[@]} -eq 0 || ${#SCR[@]} -eq 0 ]]; then
  echo "✗ No enriched/scored outputs found under scripts/products/."
  echo "  Run the pipeline first (scripts/run_pipeline.py <dataset_dir>) before rebuilding the dashboard snapshot."
  exit 1
fi

echo "◦ Building from ${#ENR[@]} enriched dirs + ${#SCR[@]} scored dirs..."

# 2. Build into a same-filesystem candidate. Live final_db_output is untouched.
"$PG_PYTHON" scripts/build_final_db.py \
  --enriched-dir "${ENR[@]}" \
  --scored-dir "${SCR[@]}" \
  --output-dir "$FINAL_CANDIDATE" \
  2>&1 | tail -5

run_strict_gate "detail-blob field completeness" \
  "$PG_PYTHON" scripts/audit_contract_sync.py \
    --build-dir "$FINAL_CANDIDATE" \
    --out "$FINAL_CANDIDATE/contract_sync_report.json"

# 3. Stage the complete release bundle into a candidate, not scripts/dist/.
#
# release_catalog_artifact.py is the SINGLE owner of populating dist/:
# pharmaguide_core.db, export_manifest.json, RELEASE_NOTES.md,
# detail_index.json, detail_blobs/, and the required export_audit_report.json.
# Previously this script had a manual `cp` workaround at this position to
# patch around release_catalog_artifact.py wiping the detail artifacts.
# That workaround moved INTO release_catalog_artifact.py (commit a81c6e3),
# so the manual copies here are now redundant and would silently drift if
# the staging script's behavior changes. Removed 2026-05-15.
"$PG_PYTHON" scripts/release_catalog_artifact.py \
  --input-dir "$FINAL_CANDIDATE" \
  --output-dir "$DIST_CANDIDATE" \
  --preserve-assets-from scripts/dist \
  2>&1 | tail -5

# 4. Gate both candidates completely before the promotion step below.
run_strict_gate "stamp dist candidate export manifest contract metadata" \
  "$PG_PYTHON" "$SOURCE_OF_TRUTH_AUDIT" stamp-manifest --dist-dir "$DIST_CANDIDATE" --strict-release
run_strict_gate "stamp final candidate export manifest contract metadata" \
  "$PG_PYTHON" "$SOURCE_OF_TRUTH_AUDIT" stamp-manifest --dist-dir "$FINAL_CANDIDATE" --strict-release
run_strict_gate "dist candidate export contract" \
  "$PG_PYTHON" "$SOURCE_OF_TRUTH_AUDIT" export --dist-dir "$DIST_CANDIDATE" --require-stamped-manifest --strict-release
run_strict_gate "final candidate export contract" \
  "$PG_PYTHON" "$SOURCE_OF_TRUTH_AUDIT" export --dist-dir "$FINAL_CANDIDATE" --require-stamped-manifest --strict-release
run_strict_gate "catalog artifact freshness" \
  "$PG_PYTHON" "$SOURCE_OF_TRUTH_AUDIT" freshness \
    --dist-dir "$DIST_CANDIDATE" \
    --final-db-dir "$FINAL_CANDIDATE" \
    --products-dir scripts/products \
    --skip-interaction-inputs \
    --strict-release

# 5. This is the only live mutation. The helper restores both previous live
# directories if either rename fails.
"$PG_PYTHON" scripts/promote_release_artifacts.py \
  --dist-candidate "$DIST_CANDIDATE" \
  --final-candidate "$FINAL_CANDIDATE" \
  --dist-dir scripts/dist \
  --final-dir scripts/final_db_output

PRODUCT_COUNT=$("$PG_PYTHON" -c "import sqlite3; print(sqlite3.connect('scripts/dist/pharmaguide_core.db').execute('SELECT COUNT(*) FROM products_core').fetchone()[0])")
BLOB_COUNT=$(ls scripts/dist/detail_blobs | wc -l | tr -d ' ')

echo ""
echo "✓ Dashboard snapshot ready:"
echo "  scripts/dist/pharmaguide_core.db              $PRODUCT_COUNT products"
echo "  scripts/dist/detail_blobs/                    $BLOB_COUNT blobs"
echo "  scripts/final_db_output/ (working-build mirror, also $PRODUCT_COUNT products)"
echo ""
echo "Launch the dashboard:"
echo "  streamlit run scripts/dashboard/app.py"
