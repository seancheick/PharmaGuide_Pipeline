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

PROFILE="${1:-fast}"
shift || true

FLUTTER_REPO="${FLUTTER_REPO:-/Users/seancheick/PharmaGuide ai}"
PYTEST_BASE=(scripts/tests -q --tb=line)
USER_TARGETS=()
USER_OPTIONS=()
SLOW_FILES=(
  scripts/tests/test_clean_unmapped_alias_regressions.py
  scripts/tests/test_enrichment_regressions.py
  scripts/tests/test_pipeline_regressions.py
  scripts/tests/test_scorable_classification.py
  scripts/tests/test_score_supplements.py
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
