"""Fail-fast JSON-schema validation for v4 scoring config rubrics — Phase 0.

A rubric typo (a cap of 180 instead of 18, a string where a number is expected,
a missing required section) must raise BEFORE any product is scored. This is the
safety net that makes externalized config at least as safe as the module
constants it replaces — config without validation is *more* dangerous than
constants, because a typo silently corrupts scores.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import jsonschema

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO_ROOT / "scripts" / "scoring_v4" / "schemas"

# Logical config name -> schema filename under scripts/scoring_v4/schemas/.
_SCHEMAS: Dict[str, str] = {
    "omega": "omega_rubric.schema.json",
}


class RubricValidationError(ValueError):
    """Raised when a rubric config fails its JSON schema (fail-fast at load)."""


def _schema_path(name: str) -> Path:
    filename = _SCHEMAS.get(name)
    path = SCHEMA_DIR / filename if filename else None
    if not filename or path is None or not path.exists():
        raise RubricValidationError(
            f"no JSON schema registered for rubric {name!r} "
            f"(expected scripts/data/schemas/{_SCHEMAS.get(name, name + '.schema.json')})"
        )
    return path


def validate_rubric(name: str, data: Any) -> None:
    """Validate ``data`` against the registered schema for ``name``. Raises
    RubricValidationError on any structural/type/range violation."""
    schema = json.loads(_schema_path(name).read_text())
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as exc:
        loc = "/".join(str(p) for p in exc.absolute_path) or "<root>"
        raise RubricValidationError(
            f"{name} rubric failed schema validation at {loc!r}: {exc.message}"
        ) from exc
