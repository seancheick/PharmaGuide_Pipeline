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
- ``all_config_provenance`` stamps versions and sha256 fingerprints from the
  same source read for each config.
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


def _rubric_path(name: str) -> Path:
    try:
        return DATA_DIR / _RUBRICS[name]
    except KeyError:
        raise KeyError(
            f"unknown rubric config {name!r}; registered: {sorted(_RUBRICS)}"
        )


def _read_provenance_source(name: str) -> Tuple[bytes, Dict[str, Any]]:
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
def _load_provenance_source(name: str) -> Tuple[bytes, Dict[str, Any]]:
    return _read_provenance_source(name)


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


def _config_version(data: Dict[str, Any]) -> str:
    meta = data.get("_metadata") if isinstance(data, dict) else None
    if isinstance(meta, dict):
        value = meta.get("version") or meta.get("schema_version")
        if value:
            return str(value)
    return "unknown"


def all_config_provenance(*, fresh: bool = False) -> Dict[str, Dict[str, str]]:
    """Version + fingerprint for every production config.

    Scoring keeps process-stable caches. Dashboard reloads request fresh reads
    without invalidating those caches; each stamp describes one exact read.
    """
    read = _read_provenance_source if fresh else _load_provenance_source
    provenance = {}
    for name in _PROVENANCE_CONFIGS:
        raw, data = read(name)
        provenance[name] = {
            "version": _config_version(data),
            "fingerprint": hashlib.sha256(raw).hexdigest()[:16],
        }
    return provenance


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
