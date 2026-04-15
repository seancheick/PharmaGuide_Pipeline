#!/bin/bash

###############################################################################
# Batch Pipeline Runner for All DSLD Datasets
###############################################################################
# Processes child dataset folders through the pipeline
# Creates separate output directories for each dataset
#
# Usage:
#   bash batch_run_all_datasets.sh                          # Full pipeline on all brands
#   bash batch_run_all_datasets.sh score                    # Score-only on all brands
#   bash batch_run_all_datasets.sh --stages enrich,score    # Enrich + score only
#   bash batch_run_all_datasets.sh --targets Thorne,Olly    # Specific brands only
#   bash batch_run_all_datasets.sh --stages score --targets Nature_Made
#   bash batch_run_all_datasets.sh --root "$HOME/Documents/DataSetDsld/staging/forms"
#   bash batch_run_all_datasets.sh --root "$HOME/Documents/DataSetDsld/delta/olly"
#bash batch_run_all_datasets.sh --root "/Users/seancheick/Documents/DataSetDsld/staging/brands" --targets Olly,Thorne,Pure,CVS,Nature,Goli,Hum,Legion,Ora,Ritual,Transparent,Vitafusion
# Environment:
#   PYTHON=python3.13 bash batch_run_all_datasets.sh        # Use specific python
###############################################################################

set -e -o pipefail  # Exit on error and fail pipelines when any segment fails

# Configuration
DATASET_ROOT="$HOME/Documents/DataSetDsld/staging/brands"
SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/scripts" && pwd)"
STAGES="clean,enrich,score"  # Default: full pipeline
TARGET_DATASETS=""  # Empty = all datasets
PYTHON="${PYTHON:-python3}"  # Use python3 by default

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

# Exit with appropriate code
if [ ${#FAILED[@]} -eq 0 ]; then
    echo -e "${GREEN}All datasets processed successfully!${NC}"
    exit 0
else
    echo -e "${RED}Some datasets failed processing.${NC}"
    exit 1
fi
