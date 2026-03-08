#!/bin/bash
# FDA Weekly Sync Runner
# Invoked by cron or launchd. Generates FDA report, then passes to Claude for enrichment.
#
# Usage: ./scripts/run_fda_sync.sh [--days N] [--no-commit] [--no-claude]
#   --days N       Look back N days (default: 7)
#   --no-commit    Skip git commit after sync
#   --no-claude    Skip Claude review (report only mode — manual review required)

set -euo pipefail

# ─── Config ────────────────────────────────────────────────────────────────────

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="${PROJECT_DIR}/scripts/fda_sync.log"
DAYS=7
DO_COMMIT=true
DO_CLAUDE=true

# Auto-detect python
if command -v python3 &>/dev/null; then
  PYTHON="python3"
elif command -v python &>/dev/null; then
  PYTHON="python"
else
  echo "[ERROR] Python not found" >&2
  exit 1
fi

# Use venv if it exists
if [ -f "${PROJECT_DIR}/.venv/bin/python" ]; then
  PYTHON="${PROJECT_DIR}/.venv/bin/python"
fi

# Parse args
while [[ $# -gt 0 ]]; do
  case $1 in
    --days)      DAYS="$2"; shift 2 ;;
    --no-commit) DO_COMMIT=false; shift ;;
    --no-claude) DO_CLAUDE=false; shift ;;
    *) echo "[WARN] Unknown arg: $1"; shift ;;
  esac
done

# ─── Logging ───────────────────────────────────────────────────────────────────

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

log "==================================================================="
log "FDA Weekly Sync START — looking back ${DAYS} days"
log "Project: $PROJECT_DIR"
log "Python:  $PYTHON"

# ─── Step 1: Generate FDA Report ──────────────────────────────────────────────

log "Step 1: Fetching FDA recall data..."
"$PYTHON" "${PROJECT_DIR}/scripts/fda_weekly_sync.py" --days "$DAYS" 2>&1 | tee -a "$LOG_FILE"

# Find the report file just created
REPORT_FILE=$(ls -t "${PROJECT_DIR}/scripts/fda_sync_report_"*.json 2>/dev/null | head -1)
if [ -z "$REPORT_FILE" ]; then
  log "[ERROR] No sync report found after script run"
  exit 1
fi
log "Report: $REPORT_FILE"

# Check if there's anything to review
NEW_COUNT=$(python3 -c "
import json
with open('${REPORT_FILE}') as f:
    d = json.load(f)
print(d['summary']['new_substances_requiring_review'])
" 2>/dev/null || echo "?")

STALE_COUNT=$(python3 -c "
import json
with open('${REPORT_FILE}') as f:
    d = json.load(f)
print(d['summary']['stale_recalled_entries_to_verify'])
" 2>/dev/null || echo "?")

log "New substances to review: ${NEW_COUNT}"
log "Stale recalls to verify:  ${STALE_COUNT}"

if [ "$NEW_COUNT" = "0" ] && [ "$STALE_COUNT" = "0" ]; then
  log "Nothing to do this week — no new relevant recalls and no stale entries."
  log "==================================================================="
  exit 0
fi

# ─── Step 2: Claude Review ─────────────────────────────────────────────────────

if [ "$DO_CLAUDE" = true ]; then
  if ! command -v claude &>/dev/null; then
    log "[ERROR] 'claude' CLI not found. Install with: npm install -g @anthropic-ai/claude-code"
    log "        Run manually: cd $PROJECT_DIR && claude /fda-weekly-sync"
    exit 1
  fi

  log "Step 2: Invoking Claude Code (/fda-weekly-sync)..."
  cd "$PROJECT_DIR"
  claude --dangerously-skip-permissions -p "/fda-weekly-sync" 2>&1 | tee -a "$LOG_FILE"
  log "Claude review complete."
else
  log "Step 2: SKIPPED (--no-claude). Run manually: cd $PROJECT_DIR && claude /fda-weekly-sync"
fi

# ─── Step 3: Git Commit ────────────────────────────────────────────────────────

if [ "$DO_COMMIT" = true ]; then
  log "Step 3: Committing changes..."
  cd "$PROJECT_DIR"

  git add scripts/data/banned_recalled_ingredients.json

  # Only commit if there are changes
  if git diff --cached --quiet; then
    log "No changes to commit (JSON unchanged)."
  else
    COMMIT_MSG="chore(fda-sync): weekly regulatory update $(date +%Y-%m-%d)

- Reviewed FDA food/enforcement + drug/enforcement recalls (past ${DAYS} days)
- New substances added: ${NEW_COUNT}
- Stale recalls verified: ${STALE_COUNT}
- Source: openFDA API, report: $(basename $REPORT_FILE)"

    git commit -m "$COMMIT_MSG"
    log "Committed: $COMMIT_MSG"
  fi
else
  log "Step 3: SKIPPED (--no-commit)."
fi

log "FDA Weekly Sync DONE"
log "==================================================================="
