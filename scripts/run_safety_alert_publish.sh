#!/usr/bin/env bash
# Publish an already human-approved safety-alert release without rebuilding the
# catalog. Resolution is deliberately absent: it is a draft-authoring step and
# may never mutate a published record.
#
# The publish step refuses until the staged feed is signed, so a first run stops
# there with the feed ready. docs/RELEASE_SIGNING_RUNBOOK.md has the steps.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"
source "$REPO_ROOT/scripts/python_env.sh"

"$PG_PYTHON" scripts/build_safety_alerts.py --check
"$PG_PYTHON" scripts/build_safety_alerts.py --stage
"$PG_PYTHON" scripts/sync_safety_alerts.py
