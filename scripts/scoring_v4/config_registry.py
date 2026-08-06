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
SCORING_CONFIG_DIR = Path(__file__).resolve().parent / "config"

# Logical config name -> filename under scripts/data/. Extend per module as the
# extraction milestone proceeds (probiotic_rubric.json, generic_rubric.json, ...).
_RUBRICS: Dict[str, str] = {
    "omega": "omega_rubric.json",
}

# Every file whose values can change a production v4 score. This registry is
# deliberately broader than ``_RUBRICS``: quality_score.json is consumed by
# the shared public assembler and most category modules, even though it is not
# loaded through ``load_rubric``.
_PROVENANCE_CONFIGS: Dict[str, Path] = {
    "omega": DATA_DIR / "omega_rubric.json",
    "quality_score": SCORING_CONFIG_DIR / "quality_score.json",
}

_FINGERPRINT_HISTORY_PATH = SCORING_CONFIG_DIR / "config_fingerprint_history.json"


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
def _load_provenance_source(name: str) -> Tuple[bytes, Dict[str, Any]]:
    """Read a registered score-affecting config for provenance."""
    try:
        path = _PROVENANCE_CONFIGS[name]
    except KeyError:
        raise KeyError(
            f"unknown scoring config {name!r}; registered: "
            f"{sorted(_PROVENANCE_CONFIGS)}"
        )
    raw = path.read_bytes()
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError(f"scoring config {name!r} must be a JSON object")
    return raw, parsed


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
    raw, _ = _load_provenance_source(name)
    return hashlib.sha256(raw).hexdigest()[:16]


def config_version(name: str) -> str:
    """The config's policy version, falling back to its schema version."""
    _, data = _load_provenance_source(name)
    meta = data.get("_metadata") if isinstance(data, dict) else None
    if isinstance(meta, dict):
        value = meta.get("version") or meta.get("schema_version")
        if value:
            return str(value)
    return "unknown"


def all_config_provenance() -> Dict[str, Dict[str, str]]:
    """Version + fingerprint for every score-affecting production config."""
    return {
        name: {
            "version": config_version(name),
            "fingerprint": config_fingerprint(name),
        }
        for name in _PROVENANCE_CONFIGS
    }


@lru_cache(maxsize=1)
def _load_fingerprint_history() -> Dict[str, Dict[str, str]]:
    data = json.loads(_FINGERPRINT_HISTORY_PATH.read_text())
    configs = data.get("configs") if isinstance(data, dict) else None
    if not isinstance(configs, dict):
        raise ValueError("config fingerprint history must contain a configs object")
    return configs


def config_fingerprint_history() -> Dict[str, Dict[str, str]]:
    """Return the review ledger that pins each config version to exact bytes."""
    return copy.deepcopy(_load_fingerprint_history())
