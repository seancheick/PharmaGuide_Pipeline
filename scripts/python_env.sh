#!/usr/bin/env bash
#
# Shared Python runtime selector for PharmaGuide pipeline shell scripts.
#
# The pipeline targets Python 3.13. Do not rely on macOS/Xcode Python: it can
# drift by host machine and has already broken tests by running Python 3.9.

if [[ -z "${REPO_ROOT:-}" ]]; then
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

PG_REQUIRED_PYTHON_MAJOR="${PG_REQUIRED_PYTHON_MAJOR:-3}"
PG_REQUIRED_PYTHON_MINOR="${PG_REQUIRED_PYTHON_MINOR:-13}"

pg_python_candidate() {
  if [[ -n "${PG_PYTHON:-}" && -x "${PG_PYTHON:-}" ]]; then
    printf '%s\n' "$PG_PYTHON"
    return 0
  fi

  if [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
    printf '%s\n' "$REPO_ROOT/.venv/bin/python"
    return 0
  fi

  if command -v pyenv >/dev/null 2>&1; then
    local pyenv_python
    pyenv_python="$(cd "$REPO_ROOT" && pyenv which python 2>/dev/null || true)"
    if [[ -n "$pyenv_python" && -x "$pyenv_python" ]]; then
      printf '%s\n' "$pyenv_python"
      return 0
    fi
  fi

  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi

  if command -v python >/dev/null 2>&1; then
    command -v python
    return 0
  fi

  return 1
}

PG_PYTHON="$(pg_python_candidate || true)"

if [[ -z "$PG_PYTHON" ]]; then
  cat >&2 <<'EOF'
ERROR: Python not found.

Install and activate the project runtime:
  pyenv install 3.13.3
  pyenv local 3.13.3
  python -m venv .venv
  source .venv/bin/activate
  python -m pip install -r requirements-dev.txt
EOF
  exit 1
fi

if ! "$PG_PYTHON" - "$PG_REQUIRED_PYTHON_MAJOR" "$PG_REQUIRED_PYTHON_MINOR" <<'PY'
import pathlib
import sys

major = int(sys.argv[1])
minor = int(sys.argv[2])

if sys.version_info < (major, minor):
    print(
        f"ERROR: PharmaGuide requires Python {major}.{minor}+; "
        f"got {sys.version.split()[0]} at {pathlib.Path(sys.executable)}",
        file=sys.stderr,
    )
    sys.exit(1)
PY
then
  cat >&2 <<'EOF'

Run from the repo with the pinned runtime:
  pyenv install 3.13.3
  pyenv local 3.13.3
  python -m venv .venv
  source .venv/bin/activate
  python -m pip install -r requirements-dev.txt

If a script is being launched by Xcode/launchd/cron, pass PG_PYTHON=/absolute/path/to/.venv/bin/python.
EOF
  exit 1
fi

export PG_PYTHON
