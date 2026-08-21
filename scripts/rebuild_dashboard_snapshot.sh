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
#     bash scripts/rebuild_dashboard_snapshot.sh \
#       --candidate-only --candidate-root /absolute/path/to/candidate
#
# Runtime: ~1 minute on current 20-brand catalog.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

usage() {
  cat <<'USAGE'
Usage:
  bash scripts/rebuild_dashboard_snapshot.sh
  bash scripts/rebuild_dashboard_snapshot.sh \
    --candidate-only --candidate-root /absolute/path/to/candidate

Options:
  --candidate-only       Run every gate and preserve the candidate without
                         replacing scripts/dist or scripts/final_db_output.
  --candidate-root PATH  New, absolute output directory for candidate-only mode.
                         The script refuses to overwrite an existing path.
  -h, --help             Show this help.
USAGE
}

CANDIDATE_ONLY=false
CANDIDATE_ROOT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --candidate-only)
      CANDIDATE_ONLY=true
      shift
      ;;
    --candidate-root)
      if [[ $# -lt 2 ]]; then
        echo "✗ --candidate-root requires a path." >&2
        exit 2
      fi
      CANDIDATE_ROOT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "✗ Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$CANDIDATE_ONLY" == "true" ]]; then
  if [[ -z "$CANDIDATE_ROOT" ]]; then
    echo "✗ --candidate-only requires --candidate-root." >&2
    exit 2
  fi
  if ! [[ "$CANDIDATE_ROOT" = /* ]]; then
    echo "✗ --candidate-root must be an absolute path." >&2
    exit 2
  fi
  [[ ! -e "$CANDIDATE_ROOT" ]] || {
    echo "✗ Candidate output already exists; refusing to overwrite: $CANDIDATE_ROOT" >&2
    exit 2
  }

  CANDIDATE_PARENT="$(dirname -- "$CANDIDATE_ROOT")"
  if [[ ! -d "$CANDIDATE_PARENT" ]]; then
    echo "✗ Candidate parent directory does not exist: $CANDIDATE_PARENT" >&2
    exit 2
  fi
  CANDIDATE_ROOT="$(cd "$CANDIDATE_PARENT" && pwd -P)/$(basename -- "$CANDIDATE_ROOT")"
  case "$CANDIDATE_ROOT" in
    /|"$REPO_ROOT"|"$REPO_ROOT/scripts"|"$REPO_ROOT/scripts/"*)
      echo "✗ Candidate output may not target the repository or live scripts tree." >&2
      exit 2
      ;;
  esac
elif [[ -n "$CANDIDATE_ROOT" ]]; then
  echo "✗ --candidate-root is only valid with --candidate-only." >&2
  exit 2
fi

cd "$REPO_ROOT"
source "$REPO_ROOT/scripts/python_env.sh"

if [[ "$CANDIDATE_ONLY" == "true" ]]; then
  CANDIDATE_STAGE="${CANDIDATE_ROOT}.staging.$$"
  [[ ! -e "$CANDIDATE_STAGE" ]] || {
    echo "✗ Candidate staging path already exists: $CANDIDATE_STAGE" >&2
    exit 2
  }
  mkdir "$CANDIDATE_STAGE"
  FINAL_CANDIDATE="$CANDIDATE_STAGE/final_db_output"
  DIST_CANDIDATE="$CANDIDATE_STAGE/dist"
  CLEANUP_TARGETS=("$CANDIDATE_STAGE")
else
  FINAL_CANDIDATE="$REPO_ROOT/scripts/.final_db_output.candidate.$$"
  DIST_CANDIDATE="$REPO_ROOT/scripts/.dist.candidate.$$"
  CLEANUP_TARGETS=("$FINAL_CANDIDATE" "$DIST_CANDIDATE" "${DIST_CANDIDATE}.staging")
fi
SOURCE_OF_TRUTH_AUDIT="$REPO_ROOT/scripts/audit_source_of_truth_contract.py"

cleanup_candidates() {
  local target
  for target in "${CLEANUP_TARGETS[@]}"; do
    if [[ -n "$target" && -e "$target" ]]; then
      rm -rf -- "$target"
    fi
  done
}
trap cleanup_candidates EXIT

run_strict_gate() {
  local label="$1"; shift
  echo "◦ Strict gate: $label"
  "$@"
}

run_strict_gate "source-of-truth matrix" \
  "$PG_PYTHON" "$SOURCE_OF_TRUTH_AUDIT" matrix --strict-release
run_strict_gate "IQM form-evidence contract" \
  "$PG_PYTHON" scripts/iqm_form_evidence.py audit
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
run_strict_gate "scoring assessment readiness" \
  "$PG_PYTHON" "$SOURCE_OF_TRUTH_AUDIT" scoring --products-dir scripts/products --strict-release
run_strict_gate "scoring snapshot contract" \
  bash scripts/test.sh fast scripts/tests/test_scoring_snapshot_v1.py

# 1. Collect enriched + scored dirs.
shopt -s nullglob
ENR=(scripts/products/*_enriched/enriched)
SCR=(scripts/products/*_scored/scored)
shopt -u nullglob

# A reviewed label correction intentionally keeps the original DSLD identity.
# The staging tables resolve duplicate identities by last write, so the single
# approved-submission source must be last on both sides of the join. Keep this
# precedence here at the catalog assembly boundary instead of teaching every
# upstream stage a second override model.
SUBMISSION_ENRICHED_DIR="scripts/products/output_Product_Submissions_enriched/enriched"
SUBMISSION_SCORED_DIR="scripts/products/output_Product_Submissions_scored/scored"
BASE_ENR=()
for directory in "${ENR[@]}"; do
  [[ "$directory" == "$SUBMISSION_ENRICHED_DIR" ]] || BASE_ENR+=("$directory")
done
BASE_SCR=()
for directory in "${SCR[@]}"; do
  [[ "$directory" == "$SUBMISSION_SCORED_DIR" ]] || BASE_SCR+=("$directory")
done
ENR=("${BASE_ENR[@]}")
SCR=("${BASE_SCR[@]}")
[[ -d "$SUBMISSION_ENRICHED_DIR" ]] && ENR+=("$SUBMISSION_ENRICHED_DIR")
[[ -d "$SUBMISSION_SCORED_DIR" ]] && SCR+=("$SUBMISSION_SCORED_DIR")

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
  --strict \
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
run_strict_gate "form-note export artifact" \
  "$PG_PYTHON" scripts/validate_form_notes_export.py --blobs-dir "$DIST_CANDIDATE/detail_blobs"
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

# 5a. Candidate-only mode stops after all gates and atomically preserves the
# verified pair at the caller's explicit destination. It never reaches the live
# promotion helper below.
if [[ "$CANDIDATE_ONLY" == "true" ]]; then
  PRODUCT_COUNT=$("$PG_PYTHON" -c "import sqlite3; print(sqlite3.connect('$DIST_CANDIDATE/pharmaguide_core.db').execute('SELECT COUNT(*) FROM products_core').fetchone()[0])")
  BLOB_COUNT=$(find "$DIST_CANDIDATE/detail_blobs" -maxdepth 1 -type f | wc -l | tr -d ' ')
  mv "$CANDIDATE_STAGE" "$CANDIDATE_ROOT"
  DIST_OUTPUT="$CANDIDATE_ROOT/dist"
  FINAL_OUTPUT="$CANDIDATE_ROOT/final_db_output"

  echo ""
  echo "✓ Gated candidate ready (no live artifacts replaced):"
  echo "  $DIST_OUTPUT/pharmaguide_core.db              $PRODUCT_COUNT products"
  echo "  $DIST_OUTPUT/detail_blobs/                    $BLOB_COUNT blobs"
  echo "  $FINAL_OUTPUT/ (working-build mirror, also $PRODUCT_COUNT products)"
  exit 0
fi

# 5b. This is the only live mutation. The helper restores both previous live
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
