#!/usr/bin/env bash
#
# Pinned-runtime test profiles for the PharmaGuide pipeline.
#
# Usage:
#   scripts/test.sh fast       # local iteration, excludes heavy/generated-artifact tests
#   scripts/test.sh release    # release-critical pytest slice + strict artifact gates
#   scripts/test.sh full       # full pytest suite; parallel when pytest-xdist is installed
#   scripts/test.sh slow       # heavy integration tests only

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"
source "$REPO_ROOT/scripts/python_env.sh"

# Signals scripts/tests/conftest.py that pytest was launched through this runner
# (pinned interpreter + profile selection), so it stays quiet. Direct raw
# pytest invocation lacks it and gets nudged toward this script.
export PG_TEST_RUNNER=1

PROFILE="${1:-fast}"
shift || true

FLUTTER_REPO="${FLUTTER_REPO:-/Users/seancheick/PharmaGuide ai}"
PYTEST_BASE=(scripts/tests -q --tb=line)
USER_TARGETS=()
USER_OPTIONS=()
SLOW_FILES=(
  # Heavy real-catalog / V4-canary integration tests. Excluded from `fast`;
  # run via `slow`/`full`. Expanded 2026-06-24 from a full --durations=40 pass
  # — worst offenders ran 25s to 485s each and were not previously listed.
  scripts/tests/test_canonical_id_e2e_continuity.py
  scripts/tests/test_clean_unmapped_alias_regressions.py
  scripts/tests/test_dsld_317006_piperine_demotion_2026_05_25.py
  scripts/tests/test_enrichment_regressions.py
  scripts/tests/test_pipeline_regressions.py
  scripts/tests/test_scorable_classification.py
  scripts/tests/test_score_supplements.py
  scripts/tests/test_scoring_evidence_contract_v1.py
  scripts/tests/test_unii_match_method_in_ledger.py
  scripts/tests/test_v4_banned_form_evidence_gate.py
  scripts/tests/test_v4_cross_module_canary_diversity.py
  scripts/tests/test_v4_gate_canary_diversity.py
  scripts/tests/test_v4_multi_prenatal_canary_diversity_p3.py
  scripts/tests/test_v4_omega_canary_diversity_p161.py
  scripts/tests/test_v4_omega_dose_p162.py
  scripts/tests/test_v4_omega_evidence_p163.py
  scripts/tests/test_v4_omega_final_assembly_p166.py
  scripts/tests/test_v4_omega_transparency_p165.py
  scripts/tests/test_v4_omega_trust_p164.py
  scripts/tests/test_v4_opaque_stimulant_blend.py
  scripts/tests/test_v4_probiotic_final_assembly_p26.py
)
RELEASE_FILES=(
  scripts/tests/test_active_banned_recalled_parity.py
  scripts/tests/test_cert_audit_canary.py
  scripts/tests/test_final_db_integrity_gate.py
  scripts/tests/test_manifest_contract.py
  scripts/tests/test_python_runtime_contract.py
  scripts/tests/test_release_export_parity.py
  scripts/tests/test_release_gate_banned_safe_contradictions.py
  scripts/tests/test_source_of_truth_contract.py
  scripts/tests/test_v4_canary_coverage.py
  scripts/tests/test_v4_safety_parity_release.py
)
ARTIFACT_FILES=(
  scripts/tests/test_active_banned_recalled_parity.py
  scripts/tests/test_cert_audit_canary.py
  scripts/tests/test_dashboard_smoke.py
  scripts/tests/test_d53_detail_blob_top_level_contract.py
  scripts/tests/test_d54_dr_pham_fields_propagate.py
  scripts/tests/test_form_sensitive_nutrient_gate.py
  scripts/tests/test_graceful_degradation.py
  scripts/tests/test_label_fidelity_contract.py
  scripts/tests/test_release_export_parity.py
  scripts/tests/test_release_gate_banned_safe_contradictions.py
  scripts/tests/test_safety_audit_gates.py
  scripts/tests/test_safety_copy_contract.py
  scripts/tests/test_v4_canary_coverage.py
)

has_xdist() {
  "$PG_PYTHON" - <<'PY' >/dev/null 2>&1
import xdist  # noqa: F401
PY
}

split_user_pytest_args() {
  USER_TARGETS=()
  USER_OPTIONS=()
  local arg base
  for arg in "$@"; do
    base="${arg%%::*}"
    if [[ -e "$base" ]]; then
      USER_TARGETS+=("$arg")
    else
      USER_OPTIONS+=("$arg")
    fi
  done
}

pytest_args_for_full() {
  if has_xdist; then
    printf '%s\n' -n auto
  fi
}

release_preflight_staleness_check() {
  # Wave 6.Z release hardening: emit BIG actionable messages when the
  # pipeline chain is stale. The downstream audits (FRESHNESS_PRODUCTS_NEWER_
  # THAN_DIST etc.) DO catch these, but their messages are technical and
  # easy to miss. This preflight surfaces the exact next command BEFORE
  # any pytest runs — so a stale-Flutter-bundle ship never surprises you.
  #
  # Skip with: SKIP_STALENESS_CHECK=1 bash scripts/test.sh release
  if [[ "${SKIP_STALENESS_CHECK:-0}" == "1" ]]; then
    return 0
  fi

  "$PG_PYTHON" - <<'PY' || {
import sys, os, glob
from pathlib import Path

REPO = Path(os.environ.get("REPO_ROOT", "."))
FLUTTER = Path(os.environ.get("FLUTTER_REPO", "/Users/seancheick/PharmaGuide ai"))


def newest(paths):
    mtimes = [Path(p).stat().st_mtime for p in paths if Path(p).exists()]
    return max(mtimes) if mtimes else 0


def warn(layer, action, command):
    bar = "=" * 78
    print(f"\n{bar}", file=sys.stderr)
    print(f"STALE ARTIFACT DETECTED: {layer}", file=sys.stderr)
    print(f"{bar}", file=sys.stderr)
    print(f"  what:   {action}", file=sys.stderr)
    print(f"  fix:    {command}", file=sys.stderr)
    print(f"  bypass: SKIP_STALENESS_CHECK=1 bash scripts/test.sh release", file=sys.stderr)
    print(f"{bar}\n", file=sys.stderr)


stale = []

# Layer 1: scripts/data/*.json vs per-brand enriched
data_files = glob.glob(str(REPO / "scripts/data/*.json")) + glob.glob(str(REPO / "scripts/data/curated_overrides/*.json"))
enriched = glob.glob(str(REPO / "scripts/products/output_*_enriched/enriched/*.json"))
if data_files and enriched:
    newest_data = newest(data_files)
    newest_enriched = newest(enriched)
    if newest_data > newest_enriched:
        warn(
            "data files newer than per-brand enriched outputs",
            "scripts/data/ JSON changes have not propagated through the pipeline",
            "bash batch_run_all_datasets.sh   # full clean+enrich+score across 27 brands",
        )
        stale.append("data_vs_enriched")

# Layer 2: enriched vs scored
scored = glob.glob(str(REPO / "scripts/products/output_*_scored/scored/*.json"))
if enriched and scored:
    newest_enriched = newest(enriched)
    newest_scored = newest(scored)
    if newest_enriched > newest_scored:
        warn(
            "enriched outputs newer than scored outputs",
            "enrichment ran but scoring did not — partial pipeline state",
            "bash batch_run_all_datasets.sh --stages score   # score-only across all brands",
        )
        stale.append("enriched_vs_scored")

# Layer 3: scored vs dist/ catalog DB
catalog_db = REPO / "scripts/dist/pharmaguide_core.db"
if scored and catalog_db.exists():
    newest_scored = newest(scored)
    catalog_mtime = catalog_db.stat().st_mtime
    if newest_scored > catalog_mtime:
        warn(
            "per-brand scored outputs newer than dist/ catalog DB",
            "build_final_db has NOT picked up the latest scored outputs — release artifacts are stale",
            "bash scripts/release_full.sh   # rebuild catalog + dist + Supabase + Flutter",
        )
        stale.append("scored_vs_dist")

# Layer 4: dist/ vs Flutter bundle (only when Flutter repo mounted)
flutter_db = FLUTTER / "assets/db/pharmaguide_core.db"
if catalog_db.exists() and flutter_db.exists():
    if catalog_db.stat().st_mtime > flutter_db.stat().st_mtime:
        warn(
            "dist/ catalog newer than Flutter bundle",
            "Flutter app is shipping an older catalog than dist/",
            "bash scripts/release_full.sh   # re-runs Flutter import step",
        )
        stale.append("dist_vs_flutter")

if stale:
    print(f"\nPREFLIGHT FAILED: {len(stale)} stale layer(s): {stale}", file=sys.stderr)
    sys.exit(1)
print("Preflight staleness check: OK (all artifacts in sync)", file=sys.stderr)
PY
    echo ""
    echo "scripts/test.sh release: STALE ARTIFACT(S) DETECTED — see actionable fix(es) above." >&2
    echo "After running the recommended command, re-run: bash scripts/test.sh release" >&2
    echo "To bypass (NOT recommended): SKIP_STALENESS_CHECK=1 bash scripts/test.sh release" >&2
    exit 1
  }
}

run_release_artifact_gates() {
  "$PG_PYTHON" scripts/coverage_gate_functional_roles.py
  "$PG_PYTHON" scripts/audit_source_of_truth_contract.py freshness \
    --dist-dir scripts/dist \
    --final-db-dir scripts/final_db_output \
    --products-dir scripts/products \
    --strict-release
  if [[ -d "$FLUTTER_REPO" ]]; then
    "$PG_PYTHON" scripts/audit_source_of_truth_contract.py flutter \
      --dist-dir scripts/dist \
      --flutter-repo "$FLUTTER_REPO" \
      --strict-release
  fi
}

fast_test_files() {
  "$PG_PYTHON" - "${SLOW_FILES[@]}" "${RELEASE_FILES[@]}" "${ARTIFACT_FILES[@]}" <<'PY'
from pathlib import Path
import sys

excluded = {Path(p).name for p in sys.argv[1:]}
for path in sorted(Path("scripts/tests").glob("test_*.py")):
    name = path.name
    if name in excluded or name.endswith("_live.py"):
        continue
    print(path)
PY
}

case "$PROFILE" in
  fast)
    split_user_pytest_args "$@"
    if ((${#USER_TARGETS[@]} > 0)); then
      files=("${USER_TARGETS[@]}")
    else
      files=()
      while IFS= read -r file; do
        files+=("$file")
      done < <(fast_test_files)
    fi
    "$PG_PYTHON" -m pytest "${files[@]}" -q --tb=line "${USER_OPTIONS[@]+"${USER_OPTIONS[@]}"}"
    ;;
  release)
    # Wave 6.Z release hardening: actionable staleness preflight runs
    # BEFORE pytest so a stale Flutter bundle never sneaks through with
    # only a technical-finding-code warning. Skip via SKIP_STALENESS_CHECK=1.
    REPO_ROOT="$REPO_ROOT" FLUTTER_REPO="$FLUTTER_REPO" \
      release_preflight_staleness_check
    split_user_pytest_args "$@"
    if ((${#USER_TARGETS[@]} > 0)); then
      files=("${USER_TARGETS[@]}")
    else
      files=("${RELEASE_FILES[@]}")
    fi
    "$PG_PYTHON" -m pytest "${files[@]}" -q --tb=line "${USER_OPTIONS[@]+"${USER_OPTIONS[@]}"}"
    run_release_artifact_gates
    ;;
  full)
    split_user_pytest_args "$@"
    if ((${#USER_TARGETS[@]} > 0)); then
      files=("${USER_TARGETS[@]}")
    else
      files=("${PYTEST_BASE[0]}")
    fi
    parallel_args=()
    while IFS= read -r arg; do
      parallel_args+=("$arg")
    done < <(pytest_args_for_full)
    "$PG_PYTHON" -m pytest "${files[@]}" -q --tb=line "${parallel_args[@]+"${parallel_args[@]}"}" "${USER_OPTIONS[@]+"${USER_OPTIONS[@]}"}"
    ;;
  slow)
    split_user_pytest_args "$@"
    if ((${#USER_TARGETS[@]} > 0)); then
      files=("${USER_TARGETS[@]}")
    else
      files=("${SLOW_FILES[@]}")
    fi
    "$PG_PYTHON" -m pytest "${files[@]}" -q --tb=line "${USER_OPTIONS[@]+"${USER_OPTIONS[@]}"}"
    ;;
  *)
    cat >&2 <<'EOF'
Unknown test profile.

Valid profiles:
  fast
  release
  full
  slow
EOF
    exit 2
    ;;
esac
