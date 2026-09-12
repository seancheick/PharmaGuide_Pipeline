#!/usr/bin/env bash
# Open the reviewer console, starting it only if it is not already running.
#
# Starting a second copy fails on the port, which reads like the console is
# broken when in fact it is already up. So: ask the running one first, start
# it only when nobody answers, and say plainly what to do when the port is
# held by something that is listening but not responding.
#
#   bash scripts/submission_review/start.sh            # port 8765, opens a browser
#   bash scripts/submission_review/start.sh 8899       # another port
#   bash scripts/submission_review/start.sh --no-open  # print the URL only

set -euo pipefail

PORT=8765
OPEN_BROWSER=1
for arg in "$@"; do
  case "$arg" in
    --no-open) OPEN_BROWSER=0 ;;
    [0-9]*) PORT="$arg" ;;
    *) echo "usage: start.sh [PORT] [--no-open]" >&2; exit 2 ;;
  esac
done

URL="http://127.0.0.1:${PORT}/"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG="${TMPDIR:-/tmp}/submission_review_${PORT}.log"

answers() { curl -fsS -o /dev/null -m 3 "$URL"; }
listening() { lsof -tiTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; }

if answers; then
  echo "Reviewer console already running: $URL"
else
  if listening; then
    echo "Port ${PORT} is held by a process that is not answering." >&2
    echo "Stop it, then run this again:" >&2
    echo "  lsof -tiTCP:${PORT} -sTCP:LISTEN | xargs kill" >&2
    exit 1
  fi

  # shellcheck source=/dev/null
  source "${REPO_ROOT}/scripts/python_env.sh"
  cd "$REPO_ROOT"
  nohup "$PG_PYTHON" scripts/submission_review/serve.py --port "$PORT" \
    >>"$LOG" 2>&1 &
  console_pid=$!

  # It builds its identity index before it answers, which takes about half a
  # minute on a cold start.
  echo "Starting the reviewer console (pid ${console_pid}, log ${LOG})…"
  for _ in $(seq 1 120); do
    if answers; then break; fi
    if ! kill -0 "$console_pid" 2>/dev/null; then
      echo "The console exited while starting. Last lines of ${LOG}:" >&2
      tail -20 "$LOG" >&2
      exit 1
    fi
    sleep 1
  done

  if ! answers; then
    echo "The console did not answer within 120s. Last lines of ${LOG}:" >&2
    tail -20 "$LOG" >&2
    exit 1
  fi
  echo "Reviewer console ready: $URL"
fi

if [ "$OPEN_BROWSER" = 1 ] && command -v open >/dev/null 2>&1; then
  open "$URL"
fi
