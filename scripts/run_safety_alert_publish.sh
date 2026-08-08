#!/usr/bin/env bash
# Publish an already human-approved safety-alert release without rebuilding the
# catalog. Resolution is deliberately absent: it is a draft-authoring step and
# may never mutate a published record.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"
source "$REPO_ROOT/scripts/python_env.sh"

"$PG_PYTHON" scripts/build_safety_alerts.py --check
"$PG_PYTHON" scripts/build_safety_alerts.py --stage
"$PG_PYTHON" scripts/sync_safety_alerts.py
