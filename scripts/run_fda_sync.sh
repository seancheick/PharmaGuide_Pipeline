#!/usr/bin/env bash
# FDA regulatory signal collector.
#
# This wrapper is intentionally REPORT-ONLY. It fetches current FDA/DEA signals
# and creates an auditable review queue. It never edits or commits curated
# clinical reference data; those changes require explicit source verification,
# regression tests, and operator review.
#
# Usage:
#   bash scripts/run_fda_sync.sh
#   bash scripts/run_fda_sync.sh --days 30
#
# Exit codes:
#   0  report complete; no new or stale records require review
#   1  fetch, report, or report-contract failure
#   2  invalid command-line arguments
#   3  report complete; clinical/regulatory review is required

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="${PROJECT_DIR}/scripts/fda_sync.log"
DAYS=7

usage() {
  sed -n '2,17p' "${BASH_SOURCE[0]}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --days)
      if [[ $# -lt 2 ]]; then
        echo "[ERROR] --days requires a positive integer." >&2
        exit 2
      fi
      DAYS="$2"
      shift 2
      ;;
    --no-claude|--no-commit)
      echo "[WARN] $1 is deprecated; the FDA sync is always report-only." >&2
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[ERROR] Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ! "$DAYS" =~ ^[1-9][0-9]*$ ]]; then
  echo "[ERROR] --days requires a positive integer; received: $DAYS" >&2
  exit 2
fi

source "${PROJECT_DIR}/scripts/python_env.sh"
PYTHON="$PG_PYTHON"
REPORT_FILE="${PROJECT_DIR}/scripts/fda_sync_report_$(date +%Y%m%d_%H%M%S).json"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "==================================================================="
log "FDA regulatory sync START — REPORT-ONLY — looking back ${DAYS} days"
log "Project: $PROJECT_DIR"
log "Python:  $PYTHON"
log "Fetching FDA/DEA regulatory signals..."

"$PYTHON" "${PROJECT_DIR}/scripts/api_audit/fda_weekly_sync.py" \
  --days "$DAYS" \
  --output "$REPORT_FILE" \
  2>&1 | tee -a "$LOG_FILE"

if [[ ! -s "$REPORT_FILE" ]]; then
  log "[ERROR] FDA sync did not produce a non-empty report: $REPORT_FILE"
  exit 1
fi

SUMMARY="$("$PYTHON" - "$REPORT_FILE" <<'PY'
import json
import sys

path = sys.argv[1]
try:
    with open(path, encoding="utf-8") as handle:
        report = json.load(handle)
    summary = report["summary"]
    if "requiring_review" in summary:
        review_count = int(summary["requiring_review"])
    else:
        review_count = int(summary["requiring_claude_review"])
    stale_count = int(summary["stale_recalled_entries_to_verify"])
except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
    print(f"ERROR\t{exc}")
    raise SystemExit(1)
print(f"{review_count}\t{stale_count}")
PY
)" || {
  log "[ERROR] FDA report failed its summary contract: $REPORT_FILE"
  exit 1
}

IFS=$'\t' read -r NEW_COUNT STALE_COUNT <<< "$SUMMARY"
log "Report: $REPORT_FILE"
log "New records requiring review: ${NEW_COUNT}"
log "Stale recalls to verify:      ${STALE_COUNT}"

if [[ "$NEW_COUNT" == "0" && "$STALE_COUNT" == "0" ]]; then
  log "FDA regulatory sync complete; no curated-data review is required."
  log "==================================================================="
  exit 0
fi

log "[REVIEW REQUIRED] The report contains unresolved regulatory signals."
log "No clinical reference data was edited and no source-control action was taken."
log "Review every candidate against its linked primary source, update curated data"
log "only after identity/applicability verification, then run the focused audit and"
log "project test runner before approving the change."
log "==================================================================="
exit 3
