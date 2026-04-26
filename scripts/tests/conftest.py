"""Pytest configuration shared across the scripts/tests/ suite.

Centralizes sys.path setup so individual test files don't each need their
own copy-paste `sys.path.insert(...)` hack. Without this, tests that
import scripts/* modules directly (e.g. `from enhanced_normalizer import …`)
work in the full-suite run only because *other* tests happen to run first
and set the path. Standalone runs (`pytest scripts/tests/test_X.py`) would
otherwise fail with ModuleNotFoundError.

This file is auto-discovered by pytest. No imports needed in test files.
"""
from __future__ import annotations

import sys
from pathlib import Path

# scripts/ directory — where enhanced_normalizer, score_supplements, etc. live.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
