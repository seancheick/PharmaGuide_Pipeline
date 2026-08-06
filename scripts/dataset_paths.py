"""Canonical local paths for operational DSLD datasets."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping, Optional


DATASET_ROOT_ENV = "PHARMAGUIDE_DATASET_ROOT"


def brand_dataset_root(
    *,
    environ: Optional[Mapping[str, str]] = None,
    home: Optional[Path] = None,
) -> Path:
    """Return the brand corpus root, defaulting outside iCloud Documents."""
    values = os.environ if environ is None else environ
    override = values.get(DATASET_ROOT_ENV)
    if override:
        return Path(override).expanduser()
    base = Path.home() if home is None else home
    return base / "Downloads" / "PharmaGuide_Datasets" / "staging" / "brands"
