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
#   0. Validate prepared intake    Preserves the prepared submission set.
#                                  --refresh-submissions explicitly fetches and
#                                  processes new approved labels; prefer doing
#                                  that before the final corpus.
#   1. Gate, assemble, and promote (rebuild_dashboard_snapshot.sh)
#                                  AUTO-SKIPS when dist/ catalog is already
#                                  fresh relative to per-brand outputs.
#                                  The snapshot path validates candidates before
#                                  atomically promoting dist/final_db_output.
#   2. Catalog already staged      Step 1 builds or validates both mirrors;
#                                  no second assembly/staging decision.
#   3. Extract DSLD product images (extract_product_images.py)
#                                  AUTO-SKIPS when dist/ image backfill is
#                                  already complete and current.
#   4. Rebuild interaction DB      (rebuild_interaction_db.sh)
#                                  AUTO-SKIPS when no rule-data file is
#                                  newer than the bundled interaction_db.
#      Publish interaction asset   (release_interaction_artifact.py
#                                  --publish-flutter-pin) after the preflight
#                                  gates: GitHub Release asset + the app's
#                                  hydration pin, committed with the bundle.
#                                  NO-OP when the pin already names dist/.
#   5. Sync to Supabase            (sync_to_supabase.py — UPLOAD ONLY)
#                                  Trusts sync_to_supabase's built-in
#                                  "up_to_date" detection (manifest checksum).
#                                  Storage cleanup is NO LONGER here — see 8.
#   6. Atomic Flutter bundle       (Flutter import_catalog_artifact.sh)
#                                  AUTO-SKIPS when Flutter assets/db/
#                                  manifests already match dist/ checksums.
#   7. Prune .previous backups     (assets/db/*.previous)
#                                  No-ops cleanly when none exist.
#   8. Commit bundle locally      (git commit assets/db/)
#                                  Reports separate version-directory and
#                                  orphan maintenance commands; neither runs
#                                  during publication.
#                                  Orphan-blob reconciliation is a SEPARATE
#                                  maintenance step (reconcile_orphan_blobs.py):
#                                  it needs a ~6 min full-bucket inventory and
#                                  must not sit on the release critical path.
#                                  Push stays manual.
#
# Usage:
#     # Standard: detect what needs running, do it, no flags needed.
#     bash scripts/release_full.sh
#
#     # Force assembly, preserving the prepared intake set:
#     bash scripts/release_full.sh --force
#
#     # Check publishing prerequisites without processing or publishing:
#     bash scripts/release_full.sh --preflight-only
#     # Read-only producer/consumer schema check; no clean main or catalog needed:
#     bash scripts/release_full.sh --compatibility-only
#
#     # Publish the already-prepared submission set without fetching new inbox labels:
#     bash scripts/release_full.sh --prepared-inputs
#     # Stale prepared submission manifests still fail; all release gates run.
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
# Input policy: release preserves the prepared submission set by default.
# --refresh-submissions explicitly opts into fetching and processing new intake.
# Prefer preparing intake before the final corpus, never during publication.
#
# Prerequisites:
#     - Per-brand pipeline outputs under scripts/products/output_*/ (only
#       needed if step 1 actually runs; auto-detect handles missing case
#       only if dist/ already has a catalog from another path).
#     - .env at repo root: UMLS_API_KEY, SUPABASE_URL,
#       SUPABASE_SERVICE_ROLE_KEY
#     - Flutter repo exists at $FLUTTER_REPO
#     - Publishing runs (Supabase upload or Flutter bundle) start from a clean
#       checkout at the fetched origin/main; the release-base check refuses
#       anything else before the first step.
#     - Publishing runs also refuse manufacturer penalties that a recalculation as
#       of today would change (fda_manufacturer_violations_sync.py --check).
#
# Exit codes:
#     0  full pipeline completed (incl. when every step auto-skipped)
#     2  bad CLI args
#     N  the failing step's exit code

set -Eeuo pipefail

# Progress must remain visible when a release is piped or redirected to a log.
export PYTHONUNBUFFERED=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"
source "$REPO_ROOT/scripts/python_env.sh"

# HR-12: a release and storage maintenance may never interleave. The Python
# wrapper owns the lock for this entire shell run and passes a secret borrow
# token to child commands that legitimately re-enter the same lock.
if [[ "${PG_RELEASE_LOCK_WRAPPED:-0}" != "1" ]]; then
  exec "$PG_PYTHON" scripts/run_with_release_lock.py \
    --lock-path "$REPO_ROOT/scripts/.release.lock" \
    -- bash "$REPO_ROOT/scripts/release_full.sh" "$@"
fi

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

FLUTTER_REPO="/Users/seancheick/PharmaGuide ai"
FORCE=0
PREFLIGHT_ONLY=0
COMPATIBILITY_ONLY=0
PREPARED_INPUTS=1
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
    --preflight-only)    PREFLIGHT_ONLY=1; shift ;;
    --compatibility-only) COMPATIBILITY_ONLY=1; shift ;;
    --prepared-inputs)   PREPARED_INPUTS=1; shift ;;
    --refresh-submissions) PREPARED_INPUTS=0; shift ;;
    --force)             FORCE=1; shift ;;
    --skip-assemble)     shift ;;  # accepted for backward compat; no-op now
    --skip-supabase)     SKIP_SUPABASE=1; shift ;;
    --skip-flutter)      SKIP_FLUTTER=1; shift ;;
    --skip-product-images) SKIP_PRODUCT_IMAGES=1; shift ;;
    --supabase-dry-run)  SUPABASE_DRY_RUN=1; shift ;;
    --keep-versions)     KEEP_VERSIONS="${2:?--keep-versions requires N}"; shift 2 ;;
    --flutter-repo)      FLUTTER_REPO="${2:?--flutter-repo requires path}"; shift 2 ;;
    -h|--help)
      sed -n '2,102p' "$0" | sed 's/^# \{0,1\}//'
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

# A local failure cannot roll back an already activated remote catalog. Track
# only what this invocation established; a failed sync has an unknown outcome.
REMOTE_CATALOG_STATE=not_attempted
RELEASE_PHASE="release prerequisites and artifact validation"
report_incomplete_release() {
  local status="$1"
  (( status == 0 )) && return 0
  err "Release incomplete during $RELEASE_PHASE (exit $status)."
  case "$REMOTE_CATALOG_STATE" in
    confirmed_current)
      err "Supabase catalog sync completed successfully (published or already current) before this failure."
      err "The remaining local/reconciliation work is incomplete; this failure does not undo cloud publication."
      ;;
    unknown)
      err "Supabase sync was attempted; activation outcome is unknown. Verify the remote manifest before retrying."
      ;;
    not_attempted)
      err "Supabase catalog publication was not attempted by this run."
      ;;
  esac
}
trap 'report_incomplete_release "$?"' EXIT

DIST_DIR="$REPO_ROOT/scripts/dist"
FINAL_DB_DIR="$REPO_ROOT/scripts/final_db_output"
ASSETS_DIR="$FLUTTER_REPO/assets/db"
DIST_PRODUCT_IMAGES_DIR="$DIST_DIR/product_images"
DIST_PRODUCT_IMAGE_INDEX="$DIST_PRODUCT_IMAGES_DIR/product_image_index.json"
PRODUCTS_DIR="$REPO_ROOT/scripts/products"
SOURCE_OF_TRUTH_AUDIT="$REPO_ROOT/scripts/audit_source_of_truth_contract.py"
IDENTITY_AUDIT_SCRIPT="$REPO_ROOT/scripts/audit_identity_integrity.py"
SUBMISSION_OUTPUT_DIR="$REPO_ROOT/manual_labels/product_submissions"
SUBMISSION_RECEIPTS="$SUBMISSION_OUTPUT_DIR/.product_submission_import_receipts"
SUBMISSION_PIPELINE_PREFIX="$PRODUCTS_DIR/output_Product_Submissions"
SUBMISSION_SCORE_MANIFEST="$SUBMISSION_PIPELINE_PREFIX"_scored/scored/.stage_manifest.json
SUBMISSION_ENRICH_MANIFEST="$SUBMISSION_PIPELINE_PREFIX"_enriched/enriched/.stage_manifest.json
SUBMISSION_CLEAN_MANIFEST="$SUBMISSION_PIPELINE_PREFIX"/cleaned/.stage_manifest.json

# A release publishes what this checkout builds, so a publishing run must start
# from a clean checkout at the freshly fetched origin/main. On 2026-09-29 a
# checkout still at 827f6b90 built a catalog after four newer fixes had landed;
# every gate passed because its outputs were current for that checkout.
# Local-only runs (no Supabase upload, no Flutter bundle) may use any checkout.
require_release_base() {
  local repo="$1" require_branch="${2:-0}" head origin
  if ! git -C "$repo" fetch --quiet origin main; then
    err "Cannot fetch origin/main to confirm this checkout is the release base."
    return 1
  fi
  if [[ -n "$(git -C "$repo" status --porcelain --untracked-files=no)" ]]; then
    err "Tracked files have uncommitted changes; a release builds only committed code and data."
    return 1
  fi
  head="$(git -C "$repo" rev-parse HEAD)"
  origin="$(git -C "$repo" rev-parse origin/main)"
  if [[ "$head" != "$origin" ]]; then
    err "This checkout is at ${head:0:8}; origin/main is ${origin:0:8}."
    err "Fast-forward (git merge --ff-only origin/main), rebuild from the earliest stale stage, then release."
    return 1
  fi
  if (( require_branch == 1 )) && [[ -z "$(git -C "$repo" branch --show-current)" ]]; then
    err "Flutter repository is in detached HEAD state; switch to its main branch before release."
    return 1
  fi
}

# Manufacturer penalties age with the calendar: a recall drops a recency band, or
# a repeat-offender window closes, on a day nobody edits the file. Publishing
# stored deductions computed on an earlier day ships stale scores, so a
# publishing run refuses them. The check is offline and compares against today,
# so it only ever blocks when a deduction would actually change: a same-day
# rerun, or a new day with no penalty crossing a band, passes untouched. It never
# re-ages by itself: that edits scripts/data, needs review and a corpus rebuild.
require_manufacturer_penalties_current() {
  local out
  if ! out="$("$PG_PYTHON" "$REPO_ROOT/scripts/api_audit/fda_manufacturer_violations_sync.py" --check 2>&1)"; then
    printf '%s\n' "$out" | tail -n 15 >&2
    err "Stored manufacturer penalties differ from a recalculation as of today."
    err "Re-age them in their own commit, push, rebuild from the earliest stale stage, then release:"
    err "  \"\$PG_PYTHON\" scripts/api_audit/fda_manufacturer_violations_sync.py --recalculate-only --output scripts/data/manufacturer_violations.json"
    return 1
  fi
  ok "Manufacturer penalties current: $(printf '%s\n' "$out" | tail -n 1)"
}

# Ask the real consumer before a multi-hour corpus, without importing producer
# modules or requiring a candidate. The importer owns accepted schema versions.
require_producer_compatibility() {
  local catalog_schema interaction_schema
  if [[ ! -x "$FLUTTER_REPO/scripts/import_catalog_artifact.sh" ]]; then
    err "Flutter import script is missing or not executable: $FLUTTER_REPO/scripts/import_catalog_artifact.sh"
    return 1
  fi
  if ! read -r catalog_schema interaction_schema < <(
    "$PG_PYTHON" - "$REPO_ROOT" <<'PY'
import ast
import pathlib
import sys
root = pathlib.Path(sys.argv[1]) / 'scripts'
values = []
for filename, key in [('build_final_db.py', 'EXPORT_SCHEMA_VERSION'),
                      ('build_interaction_db.py', 'SCHEMA_VERSION')]:
    tree = ast.parse((root / filename).read_text())
    assignments = [node for node in tree.body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == key
                           for target in node.targets)]
    if len(assignments) != 1:
        raise SystemExit(f'Cannot resolve producer schema: {filename}::{key}')
    values.append(str(ast.literal_eval(assignments[0].value)))
print(*values)
PY
  ); then
    err "Cannot read canonical producer schemas"
    return 1
  fi
  "$FLUTTER_REPO/scripts/import_catalog_artifact.sh" \
    --check-compatibility "$catalog_schema" "$interaction_schema"
}

if (( COMPATIBILITY_ONLY == 1 )); then
  require_producer_compatibility || exit 1
  ok "Producer/consumer compatibility passed; no artifacts rebuilt or published"
  exit 0
fi

if (( SKIP_FLUTTER == 0 || (SKIP_SUPABASE == 0 && SUPABASE_DRY_RUN == 0) )); then
  require_release_base "$REPO_ROOT" || exit 1
  ok "Release base: clean checkout at origin/main $(git -C "$REPO_ROOT" rev-parse --short HEAD)"
  require_manufacturer_penalties_current || exit 1
  if (( SKIP_FLUTTER == 0 )); then
    require_release_base "$FLUTTER_REPO" "$(( SKIP_SUPABASE == 0 && SUPABASE_DRY_RUN == 0 ))" || exit 1
    ok "Flutter release base: clean checkout at origin/main"
  fi
else
  skip "Release base check skipped (local-only run: no Supabase upload, no Flutter bundle)"
fi

# Read-only prerequisite mode is shared with the corpus runner. Final artifact,
# clinical, change-approval and publication gates still run in a normal release.
if (( SKIP_FLUTTER == 0 )); then
  require_producer_compatibility || exit 1
  for tool in sqlite3 shasum python3; do
    command -v "$tool" >/dev/null 2>&1 || { err "Required importer tool is missing: $tool"; exit 1; }
  done
fi
if (( SKIP_SUPABASE == 0 && SUPABASE_DRY_RUN == 0 )); then
  "$PG_PYTHON" "$REPO_ROOT/scripts/sync_to_supabase.py" --preflight-only || exit 1
fi
"$PG_PYTHON" "$REPO_ROOT/scripts/promote_release_artifacts.py" --check-disk "$REPO_ROOT/scripts"
# Submission receipts drive the image copy and promotion steps hours into a
# release. Prove offline, before anything is built, that every receipt can
# carry its label through those steps (2026-10-31 failed there after 3 h).
if [[ -f "$SUBMISSION_RECEIPTS" ]]; then
  "$PG_PYTHON" scripts/product_submission_import.py --check-receipts \
    --output-dir "$SUBMISSION_OUTPUT_DIR" || exit 1
  ok "Product submissions: import receipts verified against their labels"
fi
# Say up front whether Step 1 will rebuild the catalog (~60 min) or reuse the
# sealed receipt, so a surprise assembly is visible before the run starts.
if "$PG_PYTHON" "$REPO_ROOT/scripts/promote_release_artifacts.py" --catalog-current; then
  ok "Catalog receipt is current for these inputs: Step 1 will skip assembly"
else
  info "Catalog receipt is stale or absent: Step 1 will assemble the catalog"
fi
if (( PREFLIGHT_ONLY == 1 )); then
  if (( SKIP_FLUTTER == 0 )) && [[ ! -x "$FLUTTER_REPO/scripts/import_catalog_artifact.sh" ]]; then
    err "Flutter import script is missing or not executable: $FLUTTER_REPO/scripts/import_catalog_artifact.sh"
    exit 1
  fi
  ok "Release prerequisites passed; no artifacts rebuilt or published"
  exit 0
fi

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
info "prepared-inputs:  $PREPARED_INPUTS"
info "keep-versions:    $KEEP_VERSIONS"
info "flutter-repo:     $FLUTTER_REPO"
info "================================================================"

# ---------------------------------------------------------------------------
# Helpers — content-bound release checks and artifact fields.
# Catalog and interaction assembly both use sealed content receipts.
# ---------------------------------------------------------------------------

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
    with open(sys.argv[1]) as f: d = json.load(f)
    print(d.get(sys.argv[2], ''))
except Exception:
    pass
" "$path" "$key" 2>/dev/null
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
  "$PG_PYTHON" "$REPO_ROOT/scripts/audits/run_verification_gate.py" \
    --name "$label" --receipt-dir "$REPO_ROOT/scripts/reports/release-gates" \
    --cwd "$REPO_ROOT" --release-check -- "$@"
  ok "Strict gate passed: $label"
}

run_strict_gate "source-of-truth matrix" \
  "$PG_PYTHON" "$SOURCE_OF_TRUTH_AUDIT" matrix --strict-release
run_strict_gate "IQM form-evidence contract" \
  "$PG_PYTHON" scripts/iqm_form_evidence.py audit

# ---------------------------------------------------------------------------
# Step 0: Approved product submissions
#
# The service export is not a second publication path. It materializes the
# already-human-approved label into manual_labels/, then invokes run_pipeline.py
# exactly as a normal brand source. The existing scorer, gates, snapshot
# builder, cloud sync, and Flutter bundle remain the only release authority.
#
# Local-only and cloud dry-run releases do not mutate the approval inbox.
# Existing imported labels are still processed when their scored output is
# absent or stale.
# The release host should prefer SUPABASE_SECRET_KEY (sb_secret_...) and may
# temporarily fall back to the legacy SUPABASE_SERVICE_ROLE_KEY.
# ---------------------------------------------------------------------------

submission_labels_exist() {
  [[ -d "$SUBMISSION_OUTPUT_DIR" ]] || return 1
  find "$SUBMISSION_OUTPUT_DIR" -maxdepth 1 -type f -name '*.json' \
    -print -quit 2>/dev/null | grep -q .
}

submission_pipeline_needs_run() {
  [[ ! -f "$SUBMISSION_SCORE_MANIFEST" ]] && return 0
  if ! "$PG_PYTHON" "$REPO_ROOT/scripts/pipeline_freshness.py" \
      check-stage-manifests \
      --repo-root "$REPO_ROOT" \
      --clean "$SUBMISSION_CLEAN_MANIFEST" \
      --enrich "$SUBMISSION_ENRICH_MANIFEST" \
      --score "$SUBMISSION_SCORE_MANIFEST" \
      --raw-inputs "$SUBMISSION_OUTPUT_DIR" >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

if (( PREPARED_INPUTS == 1 )); then
  if submission_labels_exist && submission_pipeline_needs_run; then
    err "Prepared submission inputs are stale; prepare and validate them before publishing."
    exit 1
  fi
  skip "Product submissions: prepared input set preserved; inbox fetch deferred"
elif (( SKIP_SUPABASE == 0 && SUPABASE_DRY_RUN == 0 )); then
  info "Product submissions: fetching human-approved records..."
  "$PG_PYTHON" scripts/product_submission_import.py --fetch \
    --output-dir "$SUBMISSION_OUTPUT_DIR"
  ok "Product submissions: approval inbox reconciled"
else
  skip "Product submissions: approval fetch skipped (cloud disabled or dry-run)"
fi

if submission_labels_exist; then
  if (( PREPARED_INPUTS == 0 && FORCE == 1 )) || submission_pipeline_needs_run; then
    info "Product submissions: running fresh labels through Clean → Enrich → Score..."
    "$PG_PYTHON" scripts/run_pipeline.py --raw-dir "$SUBMISSION_OUTPUT_DIR" \
      --output-prefix "$SUBMISSION_PIPELINE_PREFIX" \
      --strict-release-gates
    ok "Product submissions: canonical pipeline outputs refreshed"
  else
    skip "Product submissions: scored outputs are current"
  fi
else
  skip "Product submissions: no approved labels to process"
fi

# ---------------------------------------------------------------------------
# Step 1: Assemble final DB from per-brand outputs
#
# Reuse only with a sealed receipt for current input/output content. Old
# catalogs without such evidence rebuild once. Assembly also stages both mirrors.
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

CATALOG_STATE_SCRIPT="$REPO_ROOT/scripts/promote_release_artifacts.py"
CATALOG_INPUT_BINDING=$("$PG_PYTHON" "$CATALOG_STATE_SCRIPT" --catalog-input-binding)

step1_needs_run() {
  (( FORCE == 1 )) && return 0
  # A sealed content receipt binds both complete catalog mirrors. Every final
  # artifact/live gate still runs; timestamps cannot qualify a catalog.
  if "$PG_PYTHON" "$CATALOG_STATE_SCRIPT" --catalog-current; then
    return 1
  fi
  return 0
}

if step1_needs_run; then
  info "Step 1/8: Catalog refresh required — gating and building candidates..."
  run_strict_gate "catalog assembly" bash scripts/rebuild_dashboard_snapshot.sh
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
# Assembly already stages both mirrors atomically, and content reuse above
# validates both. There is no second assembly or mtime-based staging decision.
# ---------------------------------------------------------------------------
skip "Step 2/8: Both catalog mirrors already staged and content-bound"

# Run even when assembly/staging was skipped. Unresolved identities must have
# a verified quarantine receipt and be absent from the actual outgoing catalog.
run_strict_gate "active identity integrity" \
  "$PG_PYTHON" "$IDENTITY_AUDIT_SCRIPT" \
    --products-dir "$PRODUCTS_DIR" --export-dir "$DIST_DIR"

# Gate B inspects the emitted blob contract after the candidate has been
# promoted to dist and before any publication step can run.
run_strict_gate "form-note export artifact" \
  "$PG_PYTHON" scripts/validate_form_notes_export.py --blobs-dir "$DIST_DIR/detail_blobs"

# ---------------------------------------------------------------------------
# Step 3: Extract/backfill DSLD product images into dist/
#
# Skip when: dist/product_images/product_image_index.json exists, the dist/
# catalog DB is not newer than that index, the DB already has
# product-images-backed thumbnail paths and nonempty files for every eligible
# DSLD PDF. Reviewer-approved submission photos are handled by the import lane.
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
import sys

sys.path.insert(0, "scripts")
from extract_product_images import needs_image_extraction

print("run" if needs_image_extraction(sys.argv[1], sys.argv[2]) else "skip")
PY
  )" || return 0
  [[ "$status" == "run" ]]
}

if (( SKIP_PRODUCT_IMAGES == 0 )); then
  if step3_needs_run; then
    info "Step 3/8: Catalog/images out of sync — extracting DSLD product images..."
    run_strict_gate "product image extraction" \
      "$PG_PYTHON" scripts/extract_product_images.py --db-path "$DIST_CATALOG"
    ok "DSLD product images extracted + DB backfilled"
  else
    skip "Step 3/8: DSLD product images already current — skipping extraction"
  fi
else
  skip "Step 3/8: DSLD product image extraction skipped (--skip-product-images)"
fi

# Approved missing-product labels use the same image bundle and index as DSLD
# products. The importer re-downloads the singular human-approved private
# source, verifies its hash, renders the bounded WebP, updates the index, and
# binds the catalog row before any cloud upload can observe the candidate.
if (( SKIP_PRODUCT_IMAGES == 0 )) && [[ -f "$SUBMISSION_RECEIPTS" ]]; then
  info "Product submissions: copying approved catalog images..."
  run_strict_gate "approved submission image preparation" \
    "$PG_PYTHON" scripts/product_submission_import.py --copy-images \
    --output-dir "$SUBMISSION_OUTPUT_DIR" \
    --catalog-db "$DIST_CATALOG" \
    --product-images-dir "$DIST_PRODUCT_IMAGES_DIR"
  ok "Product submissions: approved catalog images reconciled"
else
  skip "Product submissions: approved image copy skipped"
fi

# Step 3 mutates the staged dist catalog in place when it backfills
# image_thumbnail_url and refreshes export_manifest.json. Mirror that canonical
# catalog back to final_db_output before freshness compares the two manifests.
sync_final_db_output_catalog_from_dist
# Image owners legitimately mutate catalog checksums; bind their resulting
# mirrors only while the exact validated source remains unchanged.
"$PG_PYTHON" "$CATALOG_STATE_SCRIPT" --record-catalog "$CATALOG_INPUT_BINDING"

# ---------------------------------------------------------------------------
# Step 4: Rebuild interaction DB (delegates verify → build → stage)
#
# Reuse only a successful build bound to current source/code/research bytes
# and intact staged outputs. Clinical verification still runs on every rebuild.
# ---------------------------------------------------------------------------

SUPPAI_DIR="${PHARMAGUIDE_SUPPAI_DIR:-/Users/seancheick/Downloads/Supp ai DB}"

step4_needs_run() {
  (( FORCE == 1 )) && return 0
  ! "$PG_PYTHON" "$REPO_ROOT/scripts/release_interaction_artifact.py" \
    --restage-build-current --repo-root "$REPO_ROOT" \
    --suppai-dir "$SUPPAI_DIR" --output-dir "$DIST_DIR"
}

if step4_needs_run; then
  info "Step 4/8: Interaction build receipt missing or stale — rebuilding..."
  run_strict_gate "interaction database assembly" bash scripts/rebuild_interaction_db.sh
  ok "Interaction DB rebuilt + staged"
else
  skip "Step 4/8: Interaction build inputs and outputs match — skipping rebuild"
fi

# ---------------------------------------------------------------------------
# Step 4b: LIVE identifier gates (RxNorm / PubMed) — added 2026-07-24
#
# The contract gates below validate identifier STRINGS structurally; they do NOT
# resolve them. A batch of retired/swapped rxcuis shipped undetected in the
# 2026-07-24 audit precisely because "non-empty string" != "correct drug". These
# three gates hit the live APIs and FAIL CLOSED (a transient failure keeps them
# red, never green). They need network + an NCBI key in .env. For an
# intentionally-offline build set SKIP_LIVE_IDENTITY_GATES=1 — you then own the
# identifier risk for that build.
# ---------------------------------------------------------------------------
if [[ "${SKIP_LIVE_IDENTITY_GATES:-0}" == "1" ]]; then
  skip "Live identifier gates (SKIP_LIVE_IDENTITY_GATES=1) — identifier risk UNVERIFIED for this build"
else
  run_strict_gate "drug-class rxcui live identity (RxNorm)" \
    "$PG_PYTHON" scripts/api_audit/verify_drug_class_rxcuis.py
  run_strict_gate "medication-depletion drug identity (RxNorm)" \
    "$PG_PYTHON" scripts/api_audit/verify_medication_depletion_identifiers.py
  run_strict_gate "depletion/timing PMID existence (PubMed)" \
    "$PG_PYTHON" scripts/api_audit/verify_depletion_timing_pmids.py --live
  run_strict_gate "reviewed depletion/timing PMID content (PubMed)" \
    "$PG_PYTHON" scripts/api_audit/verify_depletion_timing_citation_content.py \
      --live \
      --require-coverage
  run_strict_gate "IQM form-evidence PMID content (PubMed)" \
    "$PG_PYTHON" scripts/iqm_form_evidence.py verify-live
  run_strict_gate "backed clinical studies PMID content (PubMed)" \
    "$PG_PYTHON" scripts/api_audit/verify_backed_studies_citations.py --strict
  # Interaction-rule citations are safety claims (Sean, D6 2026-09-26): an
  # unresolved, unrelated or unreviewed citation, including one in a dose
  # floor or threshold note, fails the release.
  run_strict_gate "interaction-rule citation content (PubMed)" \
    "$PG_PYTHON" scripts/api_audit/verify_interaction_rules_citations.py --strict
  # Every other citation in scripts/data. The triaged backlog (register Q22) is
  # reported, not blocking; an unresolved PMID or a mismatch outside it fails,
  # so a new bad citation cannot hide in the backlog.
  run_strict_gate "data-file citation content vs triaged backlog (PubMed)" \
    "$PG_PYTHON" scripts/api_audit/verify_all_citations_content.py \
      --baseline "$REPO_ROOT/scripts/data/citation_content_backlog.json" \
      --report "$REPO_ROOT/scripts/reports/citation_content_audit.json"
  # AGENTS.md and api_audit/README.md called this "the release gate for
  # banned/recalled data" since it was written, but it was never actually
  # invoked here — the docs wrote a check the release train never cashed.
  # --release fails closed on integrity errors, curation gaps (missing
  # source_category / reference_urls / cui annotations), any CUI mismatch, and
  # on a missing or unparsable FDA sync report.
  run_strict_gate "banned/recalled curation accuracy (UMLS + FDA sync)" \
    "$PG_PYTHON" scripts/api_audit/audit_banned_recalled_accuracy.py \
      --release \
      --fda-report-in "$REPO_ROOT/scripts/fda_sync_report_latest.json"
fi

run_strict_gate "cleaner/IQD row contract" \
  "$PG_PYTHON" "$SOURCE_OF_TRUTH_AUDIT" cleaner --products-dir "$PRODUCTS_DIR" --strict-release
run_strict_gate "enrichment/IQD source-of-truth contract" \
  "$PG_PYTHON" "$SOURCE_OF_TRUTH_AUDIT" enrichment --products-dir "$PRODUCTS_DIR" --strict-release
run_strict_gate "scoring assessment completion contract" \
  "$PG_PYTHON" "$SOURCE_OF_TRUTH_AUDIT" scoring --products-dir "$PRODUCTS_DIR" --dist-dir "$DIST_DIR" --strict-release
run_strict_gate "clinical drift contract" \
  "$PG_PYTHON" "$SOURCE_OF_TRUTH_AUDIT" clinical --products-dir "$PRODUCTS_DIR" --strict-release
run_strict_gate "clinical evidence match reachability" \
  "$PG_PYTHON" scripts/audits/evidence_match_reachability.py \
    --products-dir "$PRODUCTS_DIR" \
    --output "$REPO_ROOT/scripts/reports/evidence_match_reachability_latest.json" \
    --strict
run_strict_gate "interaction DB parity" \
  "$PG_PYTHON" "$SOURCE_OF_TRUTH_AUDIT" interaction --dist-dir "$DIST_DIR" --strict-release
run_strict_gate "artifact freshness" \
  "$PG_PYTHON" "$SOURCE_OF_TRUTH_AUDIT" freshness \
    --dist-dir "$DIST_DIR" \
    --final-db-dir "$FINAL_DB_DIR" \
    --products-dir "$PRODUCTS_DIR" \
    --strict-release
run_strict_gate "stamp export manifest contract metadata" \
  "$PG_PYTHON" "$SOURCE_OF_TRUTH_AUDIT" stamp-manifest \
    --dist-dir "$DIST_DIR" \
    --interaction-parity-verified \
    --strict-release
if [[ -f "$FINAL_DB_DIR/export_manifest.json" ]]; then
  run_strict_gate "stamp final_db_output manifest contract metadata" \
    "$PG_PYTHON" "$SOURCE_OF_TRUTH_AUDIT" stamp-manifest \
      --dist-dir "$FINAL_DB_DIR" \
      --interaction-parity-verified \
      --strict-release
fi
run_strict_gate "export contract" \
  "$PG_PYTHON" "$SOURCE_OF_TRUTH_AUDIT" export --dist-dir "$DIST_DIR" --require-stamped-manifest --strict-release

# Pipeline reference files are canonical. Regenerate and validate both Flutter
# copies before any bundle commit can occur.
if (( SKIP_FLUTTER == 0 )); then
  run_strict_gate "Flutter reference-data parity" \
    "$PG_PYTHON" scripts/sync_flutter_reference_data.py --flutter-repo "$FLUTTER_REPO"
else
  skip "Flutter reference-data writes skipped (--skip-flutter); parity still checked"
fi

# The sync above WRITES the Flutter copies, so on its own it can only ever
# agree with itself. Re-run in check mode so the committed state is verified
# independently and a failed sync cannot pass silently.
run_strict_gate "Flutter reference-data verified" \
  "$PG_PYTHON" scripts/sync_flutter_reference_data.py --check --flutter-repo "$FLUTTER_REPO"

# A fresh per-brand rebuild can materialize score changes from reviewed source
# data that earlier scored artifacts had not incorporated. Block publication
# until the snapshot baseline records any such reviewed change.
if (( SCORING_SNAPSHOT_GATE_RAN == 0 )); then
  run_strict_gate "scoring snapshot contract" \
    bash scripts/test.sh fast scripts/tests/test_scoring_snapshot_v1.py
else
  skip "Strict gate: scoring snapshot contract already passed before candidate promotion"
fi

# Seal metadata written by the validated gates before a review hold can exit.
# The retry may reuse assembly; every publication gate still runs again.
"$PG_PYTHON" "$CATALOG_STATE_SCRIPT" --record-catalog "$CATALOG_INPUT_BINDING"

# Compare every product with each catalog users can have: the app bundle
# committed on the app's main, and the live Supabase catalog the in-app updater
# downloads when that differs. Milder safety and warned-product removal require
# exact reviewed safety exceptions. Ordinary score/tier changes are report-only,
# grouped for source-based review; they do not require per-product signatures.
# This comparison does not replace clinical/contract gates or authorize publication.
# Runs with every --skip-* flag so local candidates retain safety review.
run_strict_gate "catalog changes vs what users have" \
  "$PG_PYTHON" scripts/release_safety/catalog_diff.py \
    --flutter-repo "$FLUTTER_REPO" \
    --candidate-db "$DIST_DIR/pharmaguide_core.db" \
    --report "$REPO_ROOT/scripts/reports/release_catalog_diff.md" \
    --draft-approvals "$REPO_ROOT/scripts/reports/release_catalog_diff_draft_approvals.json"

# Validate the complete Flutter import contract before any remote publication.
# The same script performs the real atomic copy in Step 6; --dry-run exercises
# schema compatibility, checksums, SQLite integrity, counts, and both embedded
# manifests without mutating the Flutter bundle. This prevents a catalog from
# reaching Supabase only to fail at the local import boundary afterward.
if (( SKIP_FLUTTER == 0 )); then
  if [[ ! -x "$FLUTTER_REPO/scripts/import_catalog_artifact.sh" ]]; then
    err "Flutter import script not found or not executable:"
    err "  $FLUTTER_REPO/scripts/import_catalog_artifact.sh"
    err "Pass --flutter-repo <path> if your Flutter checkout lives elsewhere"
    err "or --skip-flutter to bypass this step."
    exit 1
  fi
  run_strict_gate "Flutter import preflight" \
    "$FLUTTER_REPO/scripts/import_catalog_artifact.sh" "$DIST_DIR" --dry-run
else
  skip "Strict gate: Flutter import preflight skipped (--skip-flutter)"
fi

# The app hydrates interaction_db.sqlite from the GitHub Release asset named by
# its pin (tool/interaction_db.release.json); the import only stages the
# manifest. Publish the staged asset and move the pin with the bundle, so the
# bundle commit never names an interaction DB the app cannot hydrate. Only when
# this run commits the bundle; a no-op without network when the pin is current.
# The completed catalog was sealed before review; verify the source freeze
# regardless of which publication flags are set.
"$PG_PYTHON" "$CATALOG_STATE_SCRIPT" --check-input-binding "$CATALOG_INPUT_BINDING"
if (( SKIP_FLUTTER == 0 && SKIP_SUPABASE == 0 && SUPABASE_DRY_RUN == 0 )); then
  run_strict_gate "interaction DB release asset + app hydration pin" \
    "$PG_PYTHON" scripts/release_interaction_artifact.py \
      --output-dir "$DIST_DIR" --publish-flutter-pin "$FLUTTER_REPO"
else
  skip "Interaction DB publication skipped (this run does not commit the bundle)"
fi

# ---------------------------------------------------------------------------
# Step 5: Sync to Supabase (upload only; cleanup is post-bundle)
#
# We do NOT pre-skip this step — sync_to_supabase.py has built-in
# checksum-based "up_to_date" detection that is more reliable than mtime
# (catches edits that touched files without changing content). It exits
# 0 with status="up_to_date" when nothing changed.
# ---------------------------------------------------------------------------

# Fail early before expensive uploads if a reviewer reopened an approval while
# the pipeline ran. The authoritative fence still occurs inside the atomic
# manifest-activation transaction below; this precheck is only an early exit.
if (( SKIP_SUPABASE == 0 && SUPABASE_DRY_RUN == 0 )) \
    && [[ -f "$SUBMISSION_RECEIPTS" ]]; then
  info "Product submissions: verifying exact approval revisions before publication..."
  "$PG_PYTHON" scripts/product_submission_import.py --verify-current-approvals \
    --output-dir "$SUBMISSION_OUTPUT_DIR"
  ok "Product submissions: exact approval revisions confirmed"
fi

if (( SKIP_SUPABASE == 0 )); then
  if (( SUPABASE_DRY_RUN == 1 )); then
    info "Step 5/8: Syncing dist/ to Supabase (DRY-RUN)..."
    "$PG_PYTHON" scripts/sync_to_supabase.py "$DIST_DIR" --dry-run
    warn "Supabase sync was DRY-RUN — nothing actually uploaded"
  else
    "$PG_PYTHON" "$CATALOG_STATE_SCRIPT" --check-input-binding "$CATALOG_INPUT_BINDING"
    info "Step 5/8: Syncing dist/ to Supabase (upload only; cleanup deferred)..."
    # Storage inventory/deletion runs separately after publication.
    RELEASE_PHASE="Supabase catalog sync"
    REMOTE_CATALOG_STATE=unknown
    run_strict_gate "Supabase catalog sync" \
      "$PG_PYTHON" scripts/sync_to_supabase.py "$DIST_DIR" \
      --submission-output-dir "$SUBMISSION_OUTPUT_DIR"
    REMOTE_CATALOG_STATE=confirmed_current
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

RELEASE_PHASE="Flutter bundle import and validation"

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
    run_strict_gate "Flutter bundle import" \
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
  # The app's own verifier: pin, staged manifest and bundled DB are one
  # artifact, and the DB carries the clinical drug-class taxonomy.
  if (( SKIP_SUPABASE == 0 && SUPABASE_DRY_RUN == 0 )); then
    run_strict_gate "Flutter interaction hydration" \
      bash "$FLUTTER_REPO/tool/fetch_interaction_db.sh"
  fi
else
  skip "Step 6/8: Flutter import skipped (--skip-flutter)"
fi

# ---------------------------------------------------------------------------
# Step 7: Prune .previous backups in Flutter assets/db/
# (No-op when none exist — always safe to attempt.)
# ---------------------------------------------------------------------------

RELEASE_PHASE="Flutter bundle backup cleanup"
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
# Commit the Flutter bundle + report deferred storage maintenance.
#
# Commit locally (push stays manual). Report the exact branch for separately
# gated orphan maintenance, whose alignment check needs the committed bundle.
# ---------------------------------------------------------------------------
RELEASE_PHASE="Flutter bundle commit"
if (( SKIP_FLUTTER == 0 && SKIP_SUPABASE == 0 && SUPABASE_DRY_RUN == 0 )); then
  if git -C "$FLUTTER_REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    FLUTTER_RELEASE_BRANCH="$(git -C "$FLUTTER_REPO" branch --show-current)"
    if [[ -z "$FLUTTER_RELEASE_BRANCH" ]]; then
      err "Flutter repository is in detached HEAD state; refusing to commit a release bundle without a branch"
      exit 1
    fi

    if git -C "$FLUTTER_REPO" status --porcelain -- assets/db tool/interaction_db.release.json assets/reference_data/rda_optimal_uls.json assets/reference_data/medication_depletions.json assets/reference_data/clinical_risk_taxonomy.json assets/reference_data/timing_rules.json assets/reference_data/reference_data_manifest.json assets/data/product_type_vocab.json 'assets/data/*_vocab.json' | grep -q .; then
      info "Committing Flutter bundle and canonical reference data (local)..."
      git -C "$FLUTTER_REPO" add assets/db/ tool/interaction_db.release.json assets/reference_data/rda_optimal_uls.json assets/reference_data/medication_depletions.json assets/reference_data/clinical_risk_taxonomy.json assets/reference_data/timing_rules.json assets/reference_data/reference_data_manifest.json assets/data/product_type_vocab.json 'assets/data/*_vocab.json'
      if git -C "$FLUTTER_REPO" commit -q -m "chore(catalog): bundle catalog v${CATALOG_VERSION} + interaction v${INTERACTION_VERSION}"; then
        ok "Flutter bundle committed locally (push remains manual)"
      else
        err "Flutter bundle commit failed — release is incomplete."
        err "Review and commit the staged app bundle locally before pushing. No submission receipts were closed."
        exit 1
      fi
    else
      skip "Flutter bundle already committed — nothing to commit"
    fi

    info "Step 8/8: Bundle step finished; storage maintenance deferred"
    # Publication and bundle verification are complete. Storage inventories
    # and deletion are gated maintenance, not prerequisites for using this release.
    warn "Version cleanup: DEFERRED (not attempted by the release)"
    info "  Run version-directory maintenance when convenient:"
    info "    \"$PG_PYTHON\" scripts/cleanup_old_versions.py --execute --cleanup-db --keep $KEEP_VERSIONS"

    # Reported separately, and never as a success this step did not achieve.
    warn "Orphan cleanup: DEFERRED (not attempted by the release)"
    info "  Run the maintenance step when convenient — it is resumable:"
    info "    scripts/reconcile_orphan_blobs.py \\"
    info "        --flutter-repo \"$FLUTTER_REPO\" --dist-dir \"$DIST_DIR\" \\"
    info "        --branch \"$FLUTTER_RELEASE_BRANCH\" \\"
    info "        --checkpoint reports/orphan_inventory.checkpoint.json \\"
    info "        --json-report reports/orphan_report.json"
    info "  Review the exact orphan count and digests in that report, then re-run with"
    info "  --execute --approval-report reports/orphan_report.json --expected-count N"
    info "  to quarantine the frozen set (recoverable, 30d TTL)."
  else
    warn "$FLUTTER_REPO is not a git work tree — skipping bundle commit and maintenance instructions"
  fi
else
  skip "Bundle commit and maintenance instructions skipped (flutter/supabase disabled or dry-run)"
fi

# A submission becomes user-visible only after the exact product identity is
# present in the released catalog database. The adapter verifies that fact
# before calling the immutable promotion RPC; unprocessed or failed products
# remain approved-but-unpromoted for the next release.
RELEASE_PHASE="submission promotion receipt reconciliation"
if (( SKIP_FLUTTER == 0 && SKIP_SUPABASE == 0 && SUPABASE_DRY_RUN == 0 )) \
    && [[ -f "$SUBMISSION_RECEIPTS" ]]; then
  info "Closing approved product-submission receipts against the released catalog..."
  "$PG_PYTHON" scripts/product_submission_import.py --mark-promoted \
    --output-dir "$SUBMISSION_OUTPUT_DIR" \
    --catalog-db "$DIST_DIR/pharmaguide_core.db" \
    --detail-blobs-dir "$DIST_DIR/detail_blobs"
  ok "Product-submission promotion receipts reconciled"
else
  skip "Product-submission promotion skipped (no receipts or release disabled)"
fi

ELAPSED=$(($(date +%s) - START_TS))
echo ""
ok "Full release pipeline completed in ${ELAPSED}s"
info ""

info "Next steps (integrate any new local bundle commit):"
info "  cd \"$FLUTTER_REPO\""
info "  git log --oneline origin/main..HEAD"
info "  # If a new bundle commit is listed, create a temporary branch:"
info "  git switch -c codex/catalog-bundle-$(date +%Y%m%d-%H%M%S)"
info "  git push -u origin HEAD"
info "  gh pr create --base main --fill"
info "  # Wait for Merge readiness, review the bundle, then merge the PR."
info "  # Return to main, fetch origin and fast-forward; delete only the merged branch."
info ""
info "Any unpushed pipeline commits use the same branch/CI/PR path; main requires checks."
