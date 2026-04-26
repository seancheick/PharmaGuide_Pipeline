#!/bin/bash

###############################################################################
# Batch Pipeline Runner for All DSLD Datasets
###############################################################################
# Processes child dataset folders through the pipeline → dashboard snapshot →
# full release (catalog + interaction DB → Supabase → Flutter bundle).
#
# Stop-on-fail: if any brand fails during clean/enrich/score, the post-pipeline
# release stages are skipped so partial data never reaches Supabase or Flutter.
# If a release stage fails, earlier stages remain successful and dist/ keeps
# the previous good copy.
#
# Usage:
#   bash batch_run_all_datasets.sh                          # Full pipeline → snapshot → full release
#   bash batch_run_all_datasets.sh score                    # Score-only on all brands
#   bash batch_run_all_datasets.sh --stages enrich,score    # Enrich + score only
#   bash batch_run_all_datasets.sh --targets Thorne,Olly    # Specific brands only
#   bash batch_run_all_datasets.sh --stages score --targets Nature_Made
#   bash batch_run_all_datasets.sh --root "$HOME/Documents/DataSetDsld/staging/forms"
#   bash batch_run_all_datasets.sh --root "$HOME/Documents/DataSetDsld/delta/olly"
#bash batch_run_all_datasets.sh --root "/Users/seancheick/Documents/DataSetDsld/staging/brands" --targets Olly,Thorne,Pure,CVS,Nature,Goli,Hum,Legion,Ora,Ritual,Transparent,Vitafusion
#
# Release-stage flags (apply after pipeline + snapshot succeed):
#   --skip-release            Skip the full release (snapshot only — old behavior)
#   --skip-supabase           Run snapshot + interaction DB + Flutter, but no Supabase sync
#   --skip-flutter            Run snapshot + interaction DB + Supabase, but no Flutter import
#   --supabase-dry-run        Preview Supabase sync without uploading
#   --flutter-repo <path>     Override Flutter repo location for the import step
#
# Environment:
#   PYTHON=python3.13 bash batch_run_all_datasets.sh        # Use specific python
#   SKIP_SNAPSHOT=1 bash batch_run_all_datasets.sh          # Skip snapshot+release (legacy)
#   SKIP_RELEASE=1  bash batch_run_all_datasets.sh          # Snapshot only, skip full release
#
# After every successful run:
#   1. Dashboard snapshot is rebuilt (scripts/dist/ refreshed for streamlit).
#   2. Interaction DB is rebuilt (verifies CUI/RXCUI live, stages to dist/).
#   3. dist/ is synced to Supabase with full cleanup (storage + manifest rows).
#   4. Both DBs are atomically bundled into Flutter assets/db/ (17 gates).
#   5. .previous backups in Flutter assets/db/ are pruned.
#
# Set SKIP_SNAPSHOT=1 (legacy) or SKIP_RELEASE=1 to skip the post-pipeline work.
###############################################################################

set -e -o pipefail  # Exit on error and fail pipelines when any segment fails

# Configuration
DATASET_ROOT="$HOME/Documents/DataSetDsld/staging/brands"
SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/scripts" && pwd)"
STAGES="clean,enrich,score"  # Default: full pipeline
TARGET_DATASETS=""  # Empty = all datasets
PYTHON="${PYTHON:-python3}"  # Use python3 by default

# Release-stage flags (passed through to release_full.sh)
SKIP_RELEASE_FLAG=0          # 1 = skip full release entirely (snapshot still runs)
RELEASE_SKIP_SUPABASE=0
RELEASE_SKIP_FLUTTER=0
RELEASE_SUPABASE_DRY_RUN=0
RELEASE_FLUTTER_REPO=""      # empty = use release_full.sh default

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --targets)
            TARGET_DATASETS="$2"
            shift 2
            ;;
        --stages)
            STAGES="$2"
            shift 2
            ;;
        --root)
            DATASET_ROOT="$2"
            shift 2
            ;;
        --skip-release)
            SKIP_RELEASE_FLAG=1
            shift
            ;;
        --skip-supabase)
            RELEASE_SKIP_SUPABASE=1
            shift
            ;;
        --skip-flutter)
            RELEASE_SKIP_FLUTTER=1
            shift
            ;;
        --supabase-dry-run)
            RELEASE_SUPABASE_DRY_RUN=1
            shift
            ;;
        --flutter-repo)
            RELEASE_FLUTTER_REPO="$2"
            shift 2
            ;;
        *)
            STAGES="$1"
            shift
            ;;
    esac
done

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'  # No Color

# Validate paths
if [ ! -d "$DATASET_ROOT" ]; then
    echo -e "${RED}ERROR: Dataset root not found: $DATASET_ROOT${NC}"
    exit 1
fi

if [ ! -d "$SCRIPTS_DIR" ]; then
    echo -e "${RED}ERROR: Scripts directory not found: $SCRIPTS_DIR${NC}"
    echo -e "${RED}Run this script from the dsld_clean project root.${NC}"
    exit 1
fi

# Verify python3 works
if ! command -v "$PYTHON" &> /dev/null; then
    echo -e "${RED}ERROR: $PYTHON not found. Set PYTHON=path/to/python3${NC}"
    exit 1
fi

# Change to scripts directory
cd "$SCRIPTS_DIR"

# Create summary file in products/reports/
mkdir -p products/reports
SUMMARY_FILE="products/reports/batch_run_summary_$(date +%Y%m%d_%H%M%S).txt"
{
    echo "=========================================="
    echo "BATCH PIPELINE RUN - $(date)"
    echo "=========================================="
    echo "Dataset root: $DATASET_ROOT"
    echo "Scripts directory: $SCRIPTS_DIR"
    echo "Stages: $STAGES"
    if [ -n "$TARGET_DATASETS" ]; then
        echo "Target datasets: $TARGET_DATASETS"
    else
        echo "Target datasets: ALL"
    fi
    echo "=========================================="
    echo ""
} > "$SUMMARY_FILE"

# Track results
PASSED=()
FAILED=()

# Process each dataset folder, sorted by size (smallest first)
# build list sorted by directory size
# macOS ships with bash 3.2 which lacks mapfile/readarray, so use a loop
sorted_folders=()
while IFS= read -r dirpath; do
    sorted_folders+=("$dirpath")
done < <(ls -d "$DATASET_ROOT"/*/ 2>/dev/null)

# Skip infra/hidden folders regardless of root
filtered_top_level=()
for folder in "${sorted_folders[@]}"; do
    folder_name=$(basename "$folder")
    case "$folder_name" in
        forms|state|delta|reports|staging|.qodo|xOld*|__pycache__)
            continue
            ;;
    esac
    filtered_top_level+=("$folder")
done
sorted_folders=("${filtered_top_level[@]}")

# Filter by target datasets if specified
if [ -n "$TARGET_DATASETS" ]; then
    IFS=',' read -ra targets_array <<< "$TARGET_DATASETS"
    filtered_folders=()
    for folder in "${sorted_folders[@]}"; do
        folder_name=$(basename "$folder")
        for target in "${targets_array[@]}"; do
            target=$(echo "$target" | xargs)  # trim whitespace
            if [[ "$folder_name" == *"$target"* ]]; then
                filtered_folders+=("$folder")
                break
            fi
        done
    done
    sorted_folders=("${filtered_folders[@]}")
fi

CURRENT=0

echo -e "${BLUE}Processing ${#sorted_folders[@]} dataset(s) with stages: $STAGES${NC}"
echo ""

for folder in "${sorted_folders[@]}"; do
    folder_name=$(basename "$folder")
    # Skip hidden folders
    if [[ "$folder_name" == .* ]]; then
        continue
    fi
    
    CURRENT=$((CURRENT + 1))
    PROGRESS="[$CURRENT/${#sorted_folders[@]}]"
    
    echo -e "${YELLOW}${PROGRESS} Processing: ${folder_name}${NC}"
    echo "  Path: $folder"
    echo "  Output prefix: products/output_${folder_name}"
    echo ""

    # Run pipeline
    if $PYTHON run_pipeline.py --raw-dir "$folder" --output-prefix "products/output_${folder_name}" --stages "$STAGES" 2>&1 | tee -a "$SUMMARY_FILE"; then
        echo -e "${GREEN}${PROGRESS} ✓ SUCCESS: ${folder_name}${NC}"
        PASSED+=("$folder_name")
    else
        echo -e "${RED}${PROGRESS} ✗ FAILED: ${folder_name}${NC}"
        FAILED+=("$folder_name")
    fi
    
    echo ""
    echo "=========================================="
    echo ""
done

# Print final summary
echo -e "${BLUE}=========================================="
echo "BATCH RUN COMPLETE"
echo "==========================================${NC}"
echo ""
echo -e "${GREEN}Passed: ${#PASSED[@]}${NC}"
if [ ${#PASSED[@]} -gt 0 ]; then
    for item in "${PASSED[@]}"; do
        echo "  ✓ $item"
    done
fi
echo ""

if [ ${#FAILED[@]} -gt 0 ]; then
    echo -e "${RED}Failed: ${#FAILED[@]}${NC}"
    for item in "${FAILED[@]}"; do
        echo "  ✗ $item"
    done
    echo ""
fi

echo "Summary written to: $SUMMARY_FILE"
echo ""

# ─────────────────────────────────────────────────────────────────────────
# POST-PIPELINE: dashboard snapshot → full release
# ─────────────────────────────────────────────────────────────────────────
# Skip everything when any brand failed (post-pipeline work from a partial
# catalog would push misleading data downstream).
#
# SKIP_SNAPSHOT=1 (legacy) / SKIP_RELEASE=1 / --skip-release flag → skip
# the full release stage. The dashboard snapshot still runs unless
# SKIP_SNAPSHOT=1 (which now skips both).

SKIP_SNAPSHOT="${SKIP_SNAPSHOT:-0}"
SKIP_RELEASE="${SKIP_RELEASE:-0}"
SNAPSHOT_SCRIPT="$SCRIPTS_DIR/rebuild_dashboard_snapshot.sh"
RELEASE_SCRIPT="$SCRIPTS_DIR/release_full.sh"

# CLI flag overrides env var for the full release.
if [ "$SKIP_RELEASE_FLAG" = "1" ]; then
    SKIP_RELEASE=1
fi

if [ ${#FAILED[@]} -ne 0 ]; then
    echo -e "${RED}Some datasets failed processing.${NC}"
    echo -e "${YELLOW}Dashboard snapshot + full release NOT run because some brands failed.${NC}"
    echo -e "${YELLOW}  Fix failures + rerun, or:${NC}"
    echo -e "${YELLOW}    SKIP_SNAPSHOT=0 bash scripts/rebuild_dashboard_snapshot.sh${NC}"
    echo -e "${YELLOW}    bash scripts/release_full.sh${NC}"
    exit 1
fi

# Step A: dashboard snapshot
if [ "$SKIP_SNAPSHOT" = "1" ]; then
    echo -e "${YELLOW}Snapshot rebuild skipped (SKIP_SNAPSHOT=1)${NC}"
    echo -e "${YELLOW}  Run manually when ready: bash scripts/rebuild_dashboard_snapshot.sh${NC}"
    echo -e "${YELLOW}Full release also skipped (snapshot is its prerequisite).${NC}"
    echo ""
    echo -e "${GREEN}All datasets processed successfully!${NC}"
    exit 0
fi

if [ ! -x "$SNAPSHOT_SCRIPT" ]; then
    echo -e "${RED}✗ Snapshot script not executable: $SNAPSHOT_SCRIPT${NC}"
    exit 1
fi

echo -e "${BLUE}=========================================="
echo "REBUILDING DASHBOARD SNAPSHOT"
echo "==========================================${NC}"
echo ""
if bash "$SNAPSHOT_SCRIPT" 2>&1 | tee -a "$SUMMARY_FILE"; then
    echo -e "${GREEN}✓ Snapshot rebuilt: scripts/dist/ is up to date${NC}"
else
    echo -e "${RED}✗ Snapshot rebuild failed — pipeline outputs are fresh but scripts/dist/ may be stale${NC}"
    echo -e "${RED}  Rerun manually: bash scripts/rebuild_dashboard_snapshot.sh${NC}"
    # Don't fail the whole batch for snapshot issues; pipeline stages succeeded.
    # But skip the full release since dist/ is suspect.
    SKIP_RELEASE=1
fi
echo ""

# Step B: full release (interaction DB → Supabase → Flutter)
if [ "$SKIP_RELEASE" = "1" ]; then
    echo -e "${YELLOW}Full release skipped (SKIP_RELEASE=1 or --skip-release).${NC}"
    echo -e "${YELLOW}  Run manually when ready: bash scripts/release_full.sh${NC}"
    echo ""
    echo -e "${GREEN}All datasets + dashboard snapshot ready.${NC}"
    exit 0
fi

if [ ! -x "$RELEASE_SCRIPT" ]; then
    echo -e "${RED}✗ Release script not found or not executable: $RELEASE_SCRIPT${NC}"
    echo -e "${YELLOW}  Snapshot succeeded; pipeline can be released manually.${NC}"
    exit 1
fi

echo -e "${BLUE}=========================================="
echo "FULL RELEASE: interaction DB → Supabase → Flutter"
echo "==========================================${NC}"
echo ""

# Build release_full.sh arguments. Snapshot already assembled the catalog,
# so --skip-assemble avoids a redundant build_all_final_dbs.py run.
RELEASE_ARGS=(--skip-assemble)
[ "$RELEASE_SKIP_SUPABASE" = "1" ]    && RELEASE_ARGS+=(--skip-supabase)
[ "$RELEASE_SKIP_FLUTTER" = "1" ]     && RELEASE_ARGS+=(--skip-flutter)
[ "$RELEASE_SUPABASE_DRY_RUN" = "1" ] && RELEASE_ARGS+=(--supabase-dry-run)
[ -n "$RELEASE_FLUTTER_REPO" ]        && RELEASE_ARGS+=(--flutter-repo "$RELEASE_FLUTTER_REPO")

if bash "$RELEASE_SCRIPT" "${RELEASE_ARGS[@]}" 2>&1 | tee -a "$SUMMARY_FILE"; then
    echo -e "${GREEN}✓ Full release pipeline completed${NC}"
else
    echo -e "${RED}✗ Full release pipeline failed${NC}"
    echo -e "${RED}  Pipeline outputs + dashboard snapshot are fine; rerun release manually:${NC}"
    echo -e "${RED}    bash scripts/release_full.sh${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}All datasets processed + released successfully!${NC}"
exit 0
