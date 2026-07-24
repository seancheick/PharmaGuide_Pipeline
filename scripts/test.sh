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

has_xdist() {
  "$PG_PYTHON" - <<'PY' >/dev/null 2>&1
import xdist  # noqa: F401
PY
}

has_timeout() {
  "$PG_PYTHON" - <<'PY' >/dev/null 2>&1
import pytest_timeout  # noqa: F401
PY
}

# Emit `--timeout=<seconds>` iff pytest-timeout is installed, so a hung test
# fails with a named traceback instead of becoming a multi-hour zombie (see
# the test_unii_backfill live-DSLD-scan incident). No-op on minimal installs.
# A user-supplied --timeout in USER_OPTIONS is appended after and wins.
timeout_args() {
  if has_timeout; then
    printf '%s\n' "--timeout=$1"
  fi
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

# RAM-aware xdist worker cap. Each pytest worker loads the heavy enricher
# (~13k lines) + the large data JSONs and holds ~4-5 GB resident. `-n auto`
# (one worker PER CORE) therefore demanded ~60 GB on a 16 GB / high-core box and
# swap-thrashed the machine into a freeze. Cap workers by whichever is smaller:
# CPU cores or how many ~5 GB workers physical RAM can hold after reserving
# headroom for the OS + editor + browser. Override with PG_TEST_WORKERS=N.
safe_worker_count() {
  if [[ -n "${PG_TEST_WORKERS:-}" ]]; then
    printf '%s\n' "$PG_TEST_WORKERS"
    return
  fi
  "$PG_PYTHON" - <<'PY'
import os, sys
mem_gb = 8.0
try:
    if sys.platform == "darwin":
        import subprocess
        mem_gb = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"])) / 1e9
    else:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    mem_gb = int(line.split()[1]) / 1e6  # kB -> GB
                    break
except Exception:
    pass
cores = os.cpu_count() or 2
PER_WORKER_GB = 5.0   # conservative resident footprint per worker
RESERVE_GB = 6.0      # OS + editor/Claude + browser headroom
by_mem = int((mem_gb - RESERVE_GB) // PER_WORKER_GB)
print(max(1, min(cores - 1, by_mem)))
PY
}

pytest_args_for_parallel() {
  local profile="${1:-suite}"
  if has_xdist; then
    local n
    n="$(safe_worker_count)"
    echo "test.sh: running $profile with $n parallel worker(s) (RAM-capped; set PG_TEST_WORKERS to override)" >&2
    printf '%s\n' -n "$n"
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
  # Live identifier gates (RxNorm / PubMed) — the stated pre-ship gate must
  # RESOLVE every shipped clinical id, not just check non-empty strings (a batch
  # of retired/swapped rxcuis shipped undetected in the 2026-07-24 audit for
  # exactly this reason). Fail-closed; need network + an NCBI key in .env. Set
  # SKIP_LIVE_IDENTITY_GATES=1 for an intentionally-offline run (you then own the
  # identifier risk). Mirrors release_full.sh Step 4b.
  if [[ "${SKIP_LIVE_IDENTITY_GATES:-0}" == "1" ]]; then
    echo "[test.sh] SKIP live identifier gates (SKIP_LIVE_IDENTITY_GATES=1) — identifier risk UNVERIFIED" >&2
  else
    "$PG_PYTHON" scripts/api_audit/verify_drug_class_rxcuis.py
    "$PG_PYTHON" scripts/api_audit/verify_medication_depletion_identifiers.py
    "$PG_PYTHON" scripts/api_audit/verify_depletion_timing_pmids.py --live
  fi
}

fast_test_files() {
  "$PG_PYTHON" "$REPO_ROOT/scripts/test_profiles.py" fast
}

profile_test_files() {
  "$PG_PYTHON" "$REPO_ROOT/scripts/test_profiles.py" "$1"
}

# Per-profile hang guards. fast = dev loop (no test should exceed 2 min);
# heavy profiles run real-catalog tests that legitimately take ~8 min, so use a
# 10-min ceiling there to catch true hangs without false-killing slow tests.
TIMEOUT_FAST=(); while IFS= read -r _a; do TIMEOUT_FAST+=("$_a"); done < <(timeout_args 120)
TIMEOUT_HEAVY=(); while IFS= read -r _a; do TIMEOUT_HEAVY+=("$_a"); done < <(timeout_args 600)

# Low-priority prefix for the heavy (full/slow) profiles so a long parallel run
# can't starve the UI / freeze the machine. No-op if `nice` is unavailable.
NICE=(); command -v nice >/dev/null 2>&1 && NICE=(nice -n 15)

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
    parallel_args=()
    # xdist startup costs more than it saves for a single targeted file.
    # Keep focused checks (including the release snapshot contract) serial;
    # parallelize the broad fast profile and explicit multi-file runs.
    if ((${#USER_TARGETS[@]} != 1)); then
      while IFS= read -r _a; do
        parallel_args+=("$_a")
      done < <(pytest_args_for_parallel fast)
    fi
    "$PG_PYTHON" -m pytest "${files[@]}" -q --tb=line "${parallel_args[@]+"${parallel_args[@]}"}" "${TIMEOUT_FAST[@]+"${TIMEOUT_FAST[@]}"}" "${USER_OPTIONS[@]+"${USER_OPTIONS[@]}"}"
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
      files=()
      while IFS= read -r file; do
        files+=("$file")
      done < <(profile_test_files release)
    fi
    "$PG_PYTHON" -m pytest "${files[@]}" -q --tb=line "${TIMEOUT_HEAVY[@]+"${TIMEOUT_HEAVY[@]}"}" "${USER_OPTIONS[@]+"${USER_OPTIONS[@]}"}"
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
    done < <(pytest_args_for_parallel full)
    "${NICE[@]+"${NICE[@]}"}" "$PG_PYTHON" -m pytest "${files[@]}" -q --tb=line "${parallel_args[@]+"${parallel_args[@]}"}" "${TIMEOUT_HEAVY[@]+"${TIMEOUT_HEAVY[@]}"}" "${USER_OPTIONS[@]+"${USER_OPTIONS[@]}"}"
    ;;
  slow)
    split_user_pytest_args "$@"
    if ((${#USER_TARGETS[@]} > 0)); then
      files=("${USER_TARGETS[@]}")
    else
      files=()
      while IFS= read -r file; do
        files+=("$file")
      done < <(profile_test_files slow)
    fi
    "${NICE[@]+"${NICE[@]}"}" "$PG_PYTHON" -m pytest "${files[@]}" -q --tb=line "${TIMEOUT_HEAVY[@]+"${TIMEOUT_HEAVY[@]}"}" "${USER_OPTIONS[@]+"${USER_OPTIONS[@]}"}"
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
