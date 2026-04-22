#!/usr/bin/env bash
# Sprint E1 — full-pipeline rerun across every brand, then dashboard snapshot.
#
# The existing scripts/products/output_*_enriched / output_*_scored dirs were
# populated on 2026-04-21 (pre-Sprint E1) and do NOT carry the E1 changes in:
#   - enhanced_normalizer (E1.2.1 parentBlendMass, E1.2.4 / 5 raw counts)
#   - enrich_supplements_v3 (E1.3.1 additive override, E1.3.2.a/b probiotic,
#     E1.3.3 parent_blend_mass_mg)
#   - score_supplements (E1.3.2.c probiotic uplift, E1.3.3 omega3 fallback,
#     E1.3.4 enzyme credit)
#
# `rebuild_dashboard_snapshot.sh` alone only re-runs the BUILD stage against
# the stale enriched/scored files, so E1.3 scoring changes do not land in the
# release bundle.
#
# This driver re-runs CLEAN → ENRICH → SCORE for every brand, then triggers
# the snapshot rebuild. Runtime is long because of external API calls in the
# enrich stage (UMLS / openFDA / PubMed lookups). Expect tens of minutes.
#
# Usage:
#   bash scripts/rerun_all_brands_e1.sh                    # all brands
#   bash scripts/rerun_all_brands_e1.sh output_Thorne      # one brand only
#
# Env knobs:
#   STAGES=enrich,score  (default clean,enrich,score — pass enrich,score to skip clean)
#   SKIP_SNAPSHOT=1      (skip the final rebuild_dashboard_snapshot.sh step)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

STAGES="${STAGES:-clean,enrich,score}"
SKIP_SNAPSHOT="${SKIP_SNAPSHOT:-0}"

# Select brands: explicit arg wins, else everything under scripts/products/output_*
# that has a cleaned/ dir (excludes *_enriched and *_scored sibling dirs).
if [[ $# -gt 0 ]]; then
  BRANDS=("$@")
else
  BRANDS=()
  for d in scripts/products/output_*; do
    base="$(basename "$d")"
    [[ "$base" == *"_enriched"* || "$base" == *"_scored"* ]] && continue
    [[ -d "$d" ]] || continue
    BRANDS+=("$base")
  done
fi

if [[ ${#BRANDS[@]} -eq 0 ]]; then
  echo "✗ No brand dirs found under scripts/products/output_*" >&2
  exit 1
fi

echo "=== Sprint E1 multi-brand rerun ==="
echo "  stages:    $STAGES"
echo "  brands:    ${#BRANDS[@]} (${BRANDS[*]})"
echo "  snapshot:  $([ "$SKIP_SNAPSHOT" = 1 ] && echo 'skipped' || echo 'yes')"
echo

start_epoch=$(date +%s)
failed=()

for brand in "${BRANDS[@]}"; do
  echo "---- [$brand] $(date +%H:%M:%S) ----"
  if python3 scripts/run_pipeline.py \
        --stages "$STAGES" \
        --output-prefix "scripts/products/$brand"; then
    echo "✓ $brand"
  else
    echo "✗ $brand FAILED"
    failed+=("$brand")
  fi
  echo
done

elapsed=$(( $(date +%s) - start_epoch ))
echo "=== Pipeline complete in ${elapsed}s ==="
if [[ ${#failed[@]} -gt 0 ]]; then
  echo "✗ ${#failed[@]} brand(s) failed: ${failed[*]}"
  echo "  Investigate logs under scripts/logs/ before proceeding to snapshot."
  exit 1
fi

if [[ "$SKIP_SNAPSHOT" != "1" ]]; then
  echo
  echo "=== Rebuilding dashboard snapshot ==="
  bash scripts/rebuild_dashboard_snapshot.sh
fi

echo
echo "✓ All brands re-ran + snapshot rebuilt. Now re-run the scope report:"
echo "    python3 scripts/reports/label_fidelity_scope_report.py \\"
echo "        --blobs scripts/dist/detail_blobs/ --out reports/ \\"
echo "        --prefix e1_release_\$(date +%Y%m%d)_v2"
