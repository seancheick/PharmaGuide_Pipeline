"""
Loads .env file from project root into os.environ.

Usage in any script:
    import env_loader  # noqa: F401 — side-effect import, loads .env

All keys become available via os.environ.get("KEY_NAME").
Does NOT override existing env vars (system/shell takes precedence).
"""

import os
from pathlib import Path

_ENV_FILE = Path(__file__).parent.parent / ".env"


def _load_env():
    if not _ENV_FILE.exists():
        return
    with open(_ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # Don't override existing env vars
            if key and key not in os.environ:
                os.environ[key] = value


_load_env()
