"""Shared reader for the v4 public-score config (config/quality_score.json).

Leaf module: holds NO scoring logic and imports NO scoring module, so every
scoring module can read its calibration magnitudes from here without an import
cycle (§13 lock stays satisfied — values come from config, logic stays in the
modules). Mirrors the cached-load pattern in quality_score.py._config, but is
importable by the low-level dimension modules.

Used by the config-hoist refactor (2026-07-04) that moves hardcoded point
values / caps / thresholds out of the modules into named `*_magnitudes` blocks.
Each hoist is validated by an empty score diff on real products + a drift-guard
test pinning the config to the pre-hoist values.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

_PATH = Path(__file__).resolve().parent / "config" / "quality_score.json"


@lru_cache(maxsize=1)
def config() -> Dict[str, Any]:
    """Parsed quality_score.json, cached (fresh parse once per process)."""
    return json.loads(_PATH.read_text())


def block(name: str, sentinel: str) -> Dict[str, Any]:
    """Return config block ``name``, failing fast if it or ``sentinel`` is
    absent — a silent wrong score is worse than a loud error at import."""
    cfg = config()
    blk = cfg.get(name) if isinstance(cfg, dict) else None
    if not isinstance(blk, dict) or sentinel not in blk:
        raise RuntimeError(
            f"quality_score.json missing {name}.{sentinel} — v4 config not found"
        )
    return blk


if __name__ == "__main__":  # tiny self-check
    assert config()["pillars"]["formulation"]["weight"] == 20
    assert block("formulation_magnitudes", "dimension_cap")["dimension_cap"] == 30.0
    print("quality_score_config OK")
