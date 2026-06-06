"""Phase 0 — config-usage audit.

Guards the config-driven migration: a module that has been moved onto the shared
config registry must NOT regress to loading/hardcoding its own rubric. As each
module is migrated in later phases, add it to MIGRATED_MODULES so this audit
keeps it honest.

(The broader "flag every new hardcoded scoring constant" AST audit belongs to the
module-extraction phases — running it now, mid-calibration with most modules
intentionally still hardcoded, would just be noise.)
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULES_DIR = REPO_ROOT / "scripts" / "scoring_v4" / "modules"

# Modules whose rubric is now sourced from scripts/scoring_v4/config_registry.py.
# Append as extraction proceeds (probiotic_*, generic_*, ...).
MIGRATED_OMEGA_MODULES = [
    "omega_dose.py",
    "omega_evidence.py",
    "omega_formulation.py",
    "omega_transparency.py",
    "omega_trust.py",
]

# The old direct-load pattern that must no longer appear in a migrated module.
_DIRECT_RUBRIC_LOAD = re.compile(r"json\.loads\(\s*RUBRIC_PATH\.read_text\(\)\s*\)")


def test_migrated_omega_modules_use_registry_not_direct_load():
    for name in MIGRATED_OMEGA_MODULES:
        src = (MODULES_DIR / name).read_text()
        assert not _DIRECT_RUBRIC_LOAD.search(src), (
            f"{name} still loads the rubric directly; it must use "
            f"config_registry.load_rubric('omega')"
        )
        assert 'load_rubric("omega")' in src or "load_rubric('omega')" in src, (
            f"{name} no longer routes through the shared config registry"
        )


def test_registry_validates_on_load():
    """The registry must fail-fast on an invalid rubric (the safety net that
    replaces a constant's review/test coverage)."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "scoring_v4"))
    from scoring_v4.config_schema import validate_rubric, RubricValidationError
    import json

    rubric = json.loads((REPO_ROOT / "scripts" / "data" / "omega_rubric.json").read_text())
    rubric["dimension_caps"]["dose"] = 9999  # out of range
    try:
        validate_rubric("omega", rubric)
        assert False, "expected RubricValidationError on out-of-range cap"
    except RubricValidationError:
        pass
