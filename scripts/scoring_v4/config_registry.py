"""Shared v4 scoring config registry — Phase 0 of config-driven calibration.

Replaces each scoring module's private ``json.loads(path.read_text())`` with one
cached, fingerprinted, schema-validated loader. This supplies *values* and the
provenance needed to stamp every scored artifact with the exact config that
produced it. Algorithms stay in code; this never holds control flow.

Design notes:
- ``load_rubric`` returns a fresh ``deepcopy`` per call (real dicts/lists, so
  module ``isinstance(x, dict)`` guards keep working) — byte-identical to the
  old per-call ``json.loads`` semantics, minus the file I/O.
- The parse + schema validation run once and are cached; only the cheap deepcopy
  is per-call.
- ``config_fingerprint`` is the sha256 of the on-disk bytes — the exact config
  hash for provenance.
"""
from __future__ import annotations

import copy
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "scripts" / "data"

# Logical config name -> filename under scripts/data/. Extend per module as the
# extraction milestone proceeds (probiotic_rubric.json, generic_rubric.json, ...).
_RUBRICS: Dict[str, str] = {
    "omega": "omega_rubric.json",
}


def registered_rubrics() -> Tuple[str, ...]:
    return tuple(sorted(_RUBRICS))


def _rubric_path(name: str) -> Path:
    try:
        return DATA_DIR / _RUBRICS[name]
    except KeyError:
        raise KeyError(
            f"unknown rubric config {name!r}; registered: {sorted(_RUBRICS)}"
        )


@lru_cache(maxsize=None)
def _load_raw(name: str) -> Tuple[bytes, Dict[str, Any]]:
    """Read + parse + validate once; cached. Returns (raw_bytes, parsed_dict)."""
    path = _rubric_path(name)
    raw = path.read_bytes()
    data = json.loads(raw)
    # Fail-fast schema validation. Imported lazily so the registry has no hard
    # dependency cycle and so a missing schema degrades to a clear error.
    from scoring_v4.config_schema import validate_rubric

    validate_rubric(name, data)
    return raw, data


def load_rubric(name: str) -> Dict[str, Any]:
    """Return the validated rubric config as a fresh, independent dict."""
    _, data = _load_raw(name)
    return copy.deepcopy(data)


def config_fingerprint(name: str) -> str:
    """sha256 (first 16 hex) of the rubric file bytes — the exact config hash."""
    raw, _ = _load_raw(name)
    return hashlib.sha256(raw).hexdigest()[:16]


def config_version(name: str) -> str:
    """The rubric's ``_metadata.schema_version`` (or 'unknown')."""
    _, data = _load_raw(name)
    meta = data.get("_metadata") if isinstance(data, dict) else None
    if isinstance(meta, dict) and meta.get("schema_version"):
        return str(meta["schema_version"])
    return "unknown"


def all_config_provenance() -> Dict[str, Dict[str, str]]:
    """{name: {schema_version, fingerprint}} for every registered rubric."""
    return {
        name: {
            "schema_version": config_version(name),
            "fingerprint": config_fingerprint(name),
        }
        for name in _RUBRICS
    }
