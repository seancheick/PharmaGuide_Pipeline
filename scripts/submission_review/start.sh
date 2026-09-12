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

if [[ ! "$PORT" =~ ^[0-9]{1,5}$ ]] || ((10#$PORT < 1 || 10#$PORT > 65535)); then
  echo "usage: start.sh [PORT 1-65535] [--no-open]" >&2
  exit 2
fi
PORT=$((10#$PORT))

URL="http://127.0.0.1:${PORT}/"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=/dev/null
source "${REPO_ROOT}/scripts/python_env.sh"

answers() {
  curl --noproxy '*' -fsS -m "${1:-3}" "${URL}api/health" 2>/dev/null |
    "$PG_PYTHON" -c 'import hashlib,json,pathlib,sys
try:
    value=json.load(sys.stdin)
    expected={"service":"pharmaguide-submission-review","version":1,
              "server_sha256":hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest()}
    sys.exit(0 if value == expected else 1)
except (ValueError,OSError):
    sys.exit(1)' "${REPO_ROOT}/scripts/submission_review/serve.py"
}
listening() { lsof -tiTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; }

if answers; then
  echo "Reviewer console already running: $URL"
else
  if listening; then
    echo "Port ${PORT} is not answering as the current reviewer console." >&2
    echo "It may be an older console or an unrelated service. Inspect it first:" >&2
    echo "  lsof -nP -iTCP:${PORT} -sTCP:LISTEN" >&2
    echo "Stop only the identified console process, then run this again." >&2
    exit 1
  fi

  cd "$REPO_ROOT"
  umask 077
  LOG_DIR="$(mktemp -d "${TMPDIR:-/tmp}/pharmaguide-review.XXXXXX")"
  LOG="${LOG_DIR}/console.log"
  nohup "$PG_PYTHON" scripts/submission_review/serve.py --port "$PORT" \
    </dev/null >>"$LOG" 2>&1 &
  console_pid=$!
  ready=0
  # Clean up only the child we started if initialization fails or is interrupted.
  cleanup_start() {
    if [ "$ready" = 0 ]; then
      kill "$console_pid" 2>/dev/null || true
      wait "$console_pid" 2>/dev/null || true
    fi
  }
  trap cleanup_start EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM

  # It builds its identity index before it answers, which takes about half a
  # minute on a cold start.
  echo "Starting the reviewer console (pid ${console_pid}, log ${LOG})…"
  deadline=$((SECONDS + 120))
  while ((SECONDS < deadline)); do
    remaining=$((deadline - SECONDS))
    probe_timeout=3
    if ((remaining < probe_timeout)); then probe_timeout=$remaining; fi
    if answers "$probe_timeout"; then ready=1; break; fi
    if ! kill -0 "$console_pid" 2>/dev/null; then
      echo "The console exited while starting. Last lines of ${LOG}:" >&2
      tail -20 "$LOG" >&2
      exit 1
    fi
    sleep 1
  done

  if [ "$ready" = 0 ]; then
    echo "The console did not answer within 120s. Last lines of ${LOG}:" >&2
    tail -20 "$LOG" >&2
    exit 1
  fi
  echo "Reviewer console ready: $URL"
fi

if [ "$OPEN_BROWSER" = 1 ] && command -v open >/dev/null 2>&1; then
  open "$URL"
fi
