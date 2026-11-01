#!/bin/bash

###############################################################################
# Batch Pipeline Runner for All DSLD Datasets
###############################################################################
# Processes child dataset folders through the pipeline → strict dashboard snapshot →
# strict full release (catalog + DSLD images + interaction DB → Supabase → Flutter bundle).
#
# Stop-on-fail: if any brand fails during clean/enrich/score, the post-pipeline
# release stages are skipped so partial data never reaches Supabase or Flutter.
# If a release stage fails, earlier stages remain successful and dist/ keeps
# the previous good copy.
#
# Usage:
#   bash batch_run_all_datasets.sh                          # Full pipeline → snapshot → full release
#   bash batch_run_all_datasets.sh score                    # Score-only on all brands
#   bash batch_run_all_datasets.sh --stages enrich,score    # Enrich + score, then snapshot + full release
#   bash batch_run_all_datasets.sh --targets Thorne,Olly    # Specific brands, pipeline only (safe default)
#   bash batch_run_all_datasets.sh --targets Thorne,Olly --release  # Explicit catalog + release
#   bash batch_run_all_datasets.sh --pipeline-only          # Quick startup, no snapshot/release
#   bash batch_run_all_datasets.sh --pipeline-only --pre-check  # Also run aggregate preparation
#   bash batch_run_all_datasets.sh --stages score --targets Nature_Made
#   bash batch_run_all_datasets.sh --root "$HOME/Downloads/PharmaGuide_Datasets/staging/forms"
#   bash batch_run_all_datasets.sh --root "$HOME/Downloads/PharmaGuide_Datasets/delta/olly"
#   bash batch_run_all_datasets.sh --root "$HOME/Downloads/PharmaGuide_Datasets/staging/brands" --targets Olly,Thorne,Pure,CVS,Nature,Goli,Hum,Legion,Ora,Ritual,Transparent,Vitafusion
#
# Release-stage flags (apply after pipeline + strict snapshot gates succeed):
#   --release                 Explicitly release after a targeted run
#   --pipeline-only           Stop after Clean/Enrich/Score
#   --skip-release            Skip the full release (snapshot only — old behavior)
#   --skip-product-images     Run release without DSLD image extract/backfill
#   --skip-supabase           Run snapshot + images + interaction DB + Flutter, but no Supabase sync
#   --skip-flutter            Run snapshot + images + interaction DB + Supabase, but no Flutter import
#   --supabase-dry-run        Preview Supabase sync without uploading
#   --flutter-repo <path>     Override Flutter repo location for the import step
#
# Environment:
#   PYTHON=python3.13 bash batch_run_all_datasets.sh        # Use specific python
#   PHARMAGUIDE_DATASET_ROOT=/local/path bash batch_run_all_datasets.sh
#   SKIP_SNAPSHOT=1 bash batch_run_all_datasets.sh          # Skip snapshot+release (legacy)
#   SKIP_RELEASE=1  bash batch_run_all_datasets.sh          # Snapshot only, skip full release
#
# After every successful run:
#   1. Dashboard snapshot is rebuilt and strict cleaner/source-of-truth gates pass.
#   2. DSLD product images are extracted/backfilled into scripts/dist/ when needed.
#   3. Interaction DB is rebuilt and strict interaction parity gates pass.
#   4. dist/ is synced to Supabase with full cleanup (storage + manifest rows).
#   5. Both DBs are atomically bundled into Flutter assets/db/ (17 gates).
#   6. .previous backups in Flutter assets/db/ are pruned.
#
# Set SKIP_SNAPSHOT=1 (legacy) or SKIP_RELEASE=1 to skip the post-pipeline work.
###############################################################################

set -e -o pipefail  # Exit on error and fail pipelines when any segment fails

# Configuration
# Keep operational inputs outside iCloud-synced Desktop/Documents. macOS may
# replace those files with `dataless` placeholders, which cannot support a
# deterministic multi-hour pipeline run.
DATASET_ROOT="${PHARMAGUIDE_DATASET_ROOT:-$HOME/Downloads/PharmaGuide_Datasets/staging/brands}"
SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/scripts" && pwd)"
REPO_ROOT="$(cd "$SCRIPTS_DIR/.." && pwd)"
STAGES="clean,enrich,score"  # Default: full pipeline
TARGET_DATASETS=""  # Empty = all datasets
# Every other pipeline entry point (rebuild_dashboard_snapshot.sh,
# release_full.sh, test.sh, rebuild_interaction_db.sh, run_fda_sync.sh) selects
# its interpreter through this one shared helper, which prefers PG_PYTHON / the
# repo .venv / pyenv and HARD-FAILS below Python 3.13. This script was the only
# one defaulting to a bare `python3` and checking nothing but `command -v`, so
# on a host where `python3` is the macOS 3.9 it would run the entire
# Clean/Enrich/Score on 3.9 while every downstream script correctly used 3.13.
# One selector, one runtime. An explicit PYTHON=... still wins, as documented
# in the usage header above.
source "$REPO_ROOT/scripts/python_env.sh"
PYTHON="${PYTHON:-$PG_PYTHON}"

# Release-stage flags (passed through to release_full.sh)
SKIP_RELEASE_FLAG=0          # 1 = skip full release entirely (snapshot still runs)
RELEASE_SKIP_PRODUCT_IMAGES=0
RELEASE_SKIP_SUPABASE=0
RELEASE_SKIP_FLUTTER=0
RELEASE_SUPABASE_DRY_RUN=0
RELEASE_FLUTTER_REPO=""      # empty = use release_full.sh default
SUBMISSION_OUTPUT_DIR="$REPO_ROOT/manual_labels/product_submissions"
SUBMISSION_PIPELINE_PREFIX="products/output_Product_Submissions"
SUBMISSION_CLEAN_MANIFEST="$SCRIPTS_DIR/${SUBMISSION_PIPELINE_PREFIX}/cleaned/.stage_manifest.json"
SUBMISSION_ENRICH_MANIFEST="$SCRIPTS_DIR/${SUBMISSION_PIPELINE_PREFIX}_enriched/enriched/.stage_manifest.json"
SUBMISSION_SCORE_MANIFEST="$SCRIPTS_DIR/${SUBMISSION_PIPELINE_PREFIX}_scored/scored/.stage_manifest.json"
PIPELINE_ONLY=0
RELEASE_EXPLICIT=0
PRE_CHECK=0                 # Aggregate preparation is explicit opt-in
RESUME_ARGS=()

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --resume)
            RESUME_ARGS=(--resume)
            shift
            ;;
        --pre-check)
            PRE_CHECK=1
            shift
            ;;
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
        --pipeline-only)
            PIPELINE_ONLY=1
            shift
            ;;
        --release)
            RELEASE_EXPLICIT=1
            shift
            ;;
        --skip-product-images)
            RELEASE_SKIP_PRODUCT_IMAGES=1
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

if [ "$PIPELINE_ONLY" = "1" ] && [ "$RELEASE_EXPLICIT" = "1" ]; then
    echo "ERROR: --pipeline-only and --release cannot be used together." >&2
    exit 2
fi

# An empty --targets entry is a substring of every folder name and would
# silently select every brand. Read the raw string: `read -a` drops a trailing one.
if [ -n "$TARGET_DATASETS" ]; then
    case ",$(printf '%s' "$TARGET_DATASETS" | tr -d '[:space:]')," in
        *,,*)
            echo "ERROR: --targets '$TARGET_DATASETS' contains an empty entry; name each dataset." >&2
            exit 2
            ;;
    esac
fi

# A targeted rerun is normally an iteration step, not authorization to rebuild
# and ship the entire catalog. Require --release to opt into downstream work.
if [ -n "$TARGET_DATASETS" ] && [ "$RELEASE_EXPLICIT" != "1" ]; then
    PIPELINE_ONLY=1
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'  # No Color

# Validate paths
if [ ! -d "$DATASET_ROOT" ]; then
    HYDRATING_ROOT="$HOME/Downloads/PharmaGuide_Datasets/.hydrating/brands"
    if [ -z "${PHARMAGUIDE_DATASET_ROOT:-}" ] && [ -d "$HYDRATING_ROOT" ]; then
        HYDRATED_COUNT=$(find "$HYDRATING_ROOT" -type f -name '*.json' | wc -l | tr -d ' ')
        echo -e "${YELLOW}Local dataset hydration is still in progress.${NC}"
        echo "  $HYDRATED_COUNT JSON file(s) copied so far."
        echo "  Wait for the verified copy to be promoted to:"
        echo "  $DATASET_ROOT"
        echo "  Then rerun this same command."
        exit 1
    fi
    echo -e "${RED}ERROR: Dataset root not found: $DATASET_ROOT${NC}"
    exit 1
fi

# The snapshot's raw-to-final line gate reads the same raw labels this run cleans.
export PHARMAGUIDE_DATASET_ROOT="$DATASET_ROOT"

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

BATCH_SOURCE_BASELINE=$("$PYTHON" pipeline_freshness.py batch-source-fingerprint --repo-root "$REPO_ROOT") || exit 1
check_batch_source() {
    local current_source
    current_source=$("$PYTHON" pipeline_freshness.py batch-source-fingerprint --repo-root "$REPO_ROOT") || exit 1
    if [ "$current_source" != "$BATCH_SOURCE_BASELINE" ]; then
        echo "STOP: runtime source changed during this batch. Completed outputs are retained; freeze source and retry with --resume."
        exit 1
    fi
}

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

# Refuse predictable publishing prerequisites before preparation or any brand.
# release_full owns these checks; it repeats them at publication because state
# can change while the corpus runs. Output-dependent accuracy gates stay final.
RELEASE_ARGS=()
[ "$RELEASE_SKIP_PRODUCT_IMAGES" = "1" ] && RELEASE_ARGS+=(--skip-product-images)
[ "$RELEASE_SKIP_SUPABASE" = "1" ]    && RELEASE_ARGS+=(--skip-supabase)
[ "$RELEASE_SKIP_FLUTTER" = "1" ]     && RELEASE_ARGS+=(--skip-flutter)
[ "$RELEASE_SUPABASE_DRY_RUN" = "1" ] && RELEASE_ARGS+=(--supabase-dry-run)
[ -n "$RELEASE_FLUTTER_REPO" ]        && RELEASE_ARGS+=(--flutter-repo "$RELEASE_FLUTTER_REPO")

if [ "$PIPELINE_ONLY" != "1" ] && [ "${SKIP_SNAPSHOT:-0}" != "1" ] \
    && [ "${SKIP_RELEASE:-0}" != "1" ] && [ "$SKIP_RELEASE_FLAG" != "1" ]; then
    if ! bash "$SCRIPTS_DIR/release_full.sh" --preflight-only "${RELEASE_ARGS[@]}" 2>&1 | tee -a "$SUMMARY_FILE"; then
        echo "STOP: release prerequisites failed before corpus work. Fix the reported prerequisite and rerun this command."
        exit 1
    fi
    # Materialize approved inputs through the existing importer before the
    # preparation fingerprint and any brand work. The final release keeps
    # this verified set instead of fetching another batch after the long run.
    if [ "$RELEASE_SKIP_SUPABASE" = "0" ] && [ "$RELEASE_SUPABASE_DRY_RUN" = "0" ]; then
        if ! "$PYTHON" "$SCRIPTS_DIR/product_submission_import.py" --fetch \
            --output-dir "$SUBMISSION_OUTPUT_DIR" 2>&1 | tee -a "$SUMMARY_FILE"; then
            echo "STOP: approved submission intake failed before preparation or corpus work."
            exit 1
        fi
    fi
    RELEASE_ARGS+=(--prepared-inputs)
fi

# Sean runs the full corpus with --pipeline-only and publishes later. Catch
# the paired app's schema mismatch before that expensive run as well, without
# demanding a publishing checkout, cloud credentials or a built catalog.
# Targeted/offline work can omit the app explicitly with --skip-flutter.
if [ "$PIPELINE_ONLY" = "1" ] && [ -z "$TARGET_DATASETS" ] && [ "$RELEASE_SKIP_FLUTTER" != "1" ]; then
    if ! bash "$SCRIPTS_DIR/release_full.sh" --compatibility-only "${RELEASE_ARGS[@]}" 2>&1 | tee -a "$SUMMARY_FILE"; then
        echo "STOP: phone consumer compatibility failed before corpus work."
        exit 1
    fi
fi

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
    # A requested brand that is absent would otherwise be skipped silently.
    for target in "${targets_array[@]}"; do
        target=$(echo "$target" | xargs)
        matched=0
        for folder in "${filtered_folders[@]}"; do
            [[ "$(basename "$folder")" == *"$target"* ]] && matched=1 && break
        done
        if [ "$matched" = "0" ]; then
            echo -e "${RED}ERROR: no dataset folder under $DATASET_ROOT matches target '$target'${NC}" | tee -a "$SUMMARY_FILE"
            exit 1
        fi
    done
    sorted_folders=("${filtered_folders[@]}")
fi

# Reuse the critical-file/JSON owner for inexpensive offline startup checks,
# including the raw DSLD labels Clean reads and the snapshot's raw-to-final
# gate compares (ADR-0005). This does not claim the future generated catalog
# is ready to publish.
RAW_LABEL_ARGS=(--raw-root "$DATASET_ROOT")
for folder in "${sorted_folders[@]}"; do
    RAW_LABEL_ARGS+=(--dataset "$(basename "$folder")")
done
# A snapshot after this run audits every assembled brand against this root.
if [ "$PIPELINE_ONLY" != "1" ] && [ "${SKIP_SNAPSHOT:-0}" != "1" ]; then
    RAW_LABEL_ARGS+=(--products-dir products)
fi
echo "Checking essential pipeline inputs..."
if ! "$PYTHON" preflight.py --quick "${RAW_LABEL_ARGS[@]}" 2>&1 | tee -a "$SUMMARY_FILE"; then
    echo "STOP: essential pipeline input checks failed before corpus work."
    exit 1
fi

# Reuse current completion facts only when content provenance proves they still
# apply. Stale or missing facts allow the corrective rebuild, not publication.
if [ "$PIPELINE_ONLY" != "1" ] && [ "${SKIP_SNAPSHOT:-0}" != "1" ]; then
    if ! "$PYTHON" preflight.py --release-readiness --raw-root "$DATASET_ROOT" 2>&1 | tee -a "$SUMMARY_FILE"; then
        echo "STOP: current assessments block publication before corpus work."
        exit 1
    fi
fi

# Aggregate source/live/canary preparation is optional. Publication still runs
# its own mandatory output-dependent gates, regardless of this flag.
if [ "$PRE_CHECK" = "1" ]; then
    echo "Collecting aggregate pipeline preparation (--pre-check)..."
    if ! "$PYTHON" preflight.py --prepare --raw-root "$DATASET_ROOT" 2>&1 | tee -a "$SUMMARY_FILE"; then
        echo "STOP: aggregate preparation failed. Review scripts/reports/pipeline_preparation.json before any corpus or publication work."
        exit 1
    fi
else
    echo "Aggregate preparation skipped; add --pre-check to request it. Release gates remain required."
fi

# Track results
PROCESS_SUBMISSIONS=0
if { [ "$PIPELINE_ONLY" != "1" ] && [ "${SKIP_SNAPSHOT:-0}" != "1" ]; } \
    || { [ "$PIPELINE_ONLY" = "1" ] && [ -z "$TARGET_DATASETS" ]; }; then
    PROCESS_SUBMISSIONS=1
fi
BATCH_INPUT_BASELINE=$("$PYTHON" pipeline_freshness.py batch-source-fingerprint \
    --repo-root "$REPO_ROOT" --raw-inputs "$DATASET_ROOT" \
    --raw-inputs "$SUBMISSION_OUTPUT_DIR") || exit 1
check_batch_inputs() {
    local current_inputs
    current_inputs=$("$PYTHON" pipeline_freshness.py batch-source-fingerprint \
        --repo-root "$REPO_ROOT" --raw-inputs "$DATASET_ROOT" \
        --raw-inputs "$SUBMISSION_OUTPUT_DIR") || exit 1
    if [ "$current_inputs" != "$BATCH_INPUT_BASELINE" ]; then
        echo "STOP: source or raw labels changed during this batch. Freeze inputs and retry with --resume."
        exit 1
    fi
}
if [ "${#RESUME_ARGS[@]}" -gt 0 ]; then
    if [ "$STAGES" != "clean,enrich,score" ]; then
        echo "ERROR: --resume requires the default clean,enrich,score stages."
        exit 1
    fi
    echo "Verified resume plan (no computation yet):" | tee -a "$SUMMARY_FILE"
    for folder in "${sorted_folders[@]}"; do
        "$PYTHON" run_pipeline.py --raw-dir "$folder" \
            --output-prefix "products/output_$(basename "$folder")" \
            --resume-plan 2>&1 | tee -a "$SUMMARY_FILE" || exit 1
    done
    if [ "$PROCESS_SUBMISSIONS" = "1" ] && [ -d "$SUBMISSION_OUTPUT_DIR" ] && find "$SUBMISSION_OUTPUT_DIR" \
        -maxdepth 1 -type f -name '*.json' -print -quit | grep -q .; then
        "$PYTHON" run_pipeline.py --raw-dir "$SUBMISSION_OUTPUT_DIR" \
            --output-prefix "$SUBMISSION_PIPELINE_PREFIX" \
            --resume-plan 2>&1 | tee -a "$SUMMARY_FILE" || exit 1
    fi
fi
PASSED=()
FAILED=()

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
    check_batch_source
    if $PYTHON run_pipeline.py --raw-dir "$folder" --output-prefix "products/output_${folder_name}" --stages "$STAGES" "${RESUME_ARGS[@]}" --strict-release-gates 2>&1 | tee -a "$SUMMARY_FILE"; then
        echo -e "${GREEN}${PROGRESS} ✓ SUCCESS: ${folder_name}${NC}"
        PASSED+=("$folder_name")
    else
        echo -e "${RED}${PROGRESS} ✗ FAILED: ${folder_name}${NC}"
        FAILED+=("$folder_name")
        check_batch_source
    fi
    
    echo ""
    echo "=========================================="
    echo ""
done

# Print final summary
check_batch_source
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
if [ "$PIPELINE_ONLY" = "1" ]; then
    SKIP_SNAPSHOT=1
fi
SNAPSHOT_SCRIPT="$SCRIPTS_DIR/rebuild_dashboard_snapshot.sh"
RELEASE_SCRIPT="$SCRIPTS_DIR/release_full.sh"
SNAPSHOT_OK=0

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

# Product Submissions is an auxiliary, human-approved label source outside the
# 37-brand dataset root, but the catalog snapshot includes it. Rebuild it (clean,
# enrich, score) whenever reference data or stage code changed, so a successful
# brand run cannot reach snapshot assembly with one stale auxiliary manifest.
# A pipeline-only run over every brand refreshes them too: the snapshot that
# follows it by hand reads them.
if [ "$PROCESS_SUBMISSIONS" = "1" ] \
    && [ -d "$SUBMISSION_OUTPUT_DIR" ] \
    && find "$SUBMISSION_OUTPUT_DIR" -maxdepth 1 -type f -name '*.json' \
        -print -quit 2>/dev/null | grep -q .; then
    if [ "${#RESUME_ARGS[@]}" -gt 0 ] || ! "$PYTHON" pipeline_freshness.py check-stage-manifests \
        --repo-root "$REPO_ROOT" \
        --clean "$SUBMISSION_CLEAN_MANIFEST" \
        --enrich "$SUBMISSION_ENRICH_MANIFEST" \
        --score "$SUBMISSION_SCORE_MANIFEST" \
        --raw-inputs "$SUBMISSION_OUTPUT_DIR" >/dev/null 2>&1; then
        echo -e "${BLUE}Refreshing Product Submissions against current reference data and pipeline code...${NC}"
        if "$PYTHON" run_pipeline.py \
            --raw-dir "$SUBMISSION_OUTPUT_DIR" \
            --output-prefix "$SUBMISSION_PIPELINE_PREFIX" \
            --stages clean,enrich,score "${RESUME_ARGS[@]}" \
            --strict-release-gates 2>&1 | tee -a "$SUMMARY_FILE"; then
            echo -e "${GREEN}✓ Product Submissions cleaning, enrichment and scoring refreshed${NC}"
        else
            echo -e "${RED}✗ Product Submissions refresh failed; snapshot and release were not started${NC}"
            exit 1
        fi
        echo ""
    fi
fi

# Step A: dashboard snapshot
check_batch_source
check_batch_inputs
if [ "$SKIP_SNAPSHOT" = "1" ]; then
    if [ "$PIPELINE_ONLY" = "1" ]; then
        echo -e "${YELLOW}Pipeline-only run complete; snapshot and release were not started.${NC}"
        if [ -n "$TARGET_DATASETS" ] && [ "$RELEASE_EXPLICIT" != "1" ]; then
            echo -e "${YELLOW}Targeted runs use this safe default. Add --release only when you intend to rebuild and ship the full catalog.${NC}"
        fi
    else
        echo -e "${YELLOW}Snapshot rebuild skipped (SKIP_SNAPSHOT=1)${NC}"
    fi
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
    SNAPSHOT_OK=1
else
    echo -e "${RED}✗ Snapshot rebuild failed — pipeline outputs are fresh but scripts/dist/ may be stale${NC}"
    echo -e "${RED}  Rerun manually: bash scripts/rebuild_dashboard_snapshot.sh${NC}"
    echo -e "${RED}  Full release was not started.${NC}"
    exit 1
fi
echo ""

# Step B: full release (interaction DB → Supabase → Flutter)
check_batch_source
check_batch_inputs
if [ "$SKIP_RELEASE" = "1" ]; then
    echo -e "${YELLOW}Full release skipped (SKIP_RELEASE=1 or --skip-release).${NC}"
    echo -e "${YELLOW}  Run manually when ready: bash scripts/release_full.sh${NC}"
    echo ""
    if [ "$SNAPSHOT_OK" = "1" ]; then
        echo -e "${GREEN}All datasets + dashboard snapshot ready.${NC}"
    else
        echo -e "${YELLOW}All datasets processed, but dashboard snapshot is NOT ready.${NC}"
    fi
    exit 0
fi

if [ ! -x "$RELEASE_SCRIPT" ]; then
    echo -e "${RED}✗ Release script not found or not executable: $RELEASE_SCRIPT${NC}"
    echo -e "${YELLOW}  Snapshot succeeded; pipeline can be released manually.${NC}"
    exit 1
fi

echo -e "${BLUE}=========================================="
echo "FULL RELEASE: DSLD images → interaction DB → Supabase → Flutter"
echo "==========================================${NC}"
echo ""

# Build release_full.sh arguments. release_full.sh is auto-smart now —
# every step decides for itself whether it has work. After
# rebuild_dashboard_snapshot.sh runs, the catalog is fresh in dist/, and
# release_full's step 1+2 detection skips both. No --skip-assemble needed.

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
