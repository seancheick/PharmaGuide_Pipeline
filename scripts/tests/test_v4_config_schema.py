"""Phase 0 — fail-fast rubric schema validation.

Proves the safety net: a config typo (out-of-range score, wrong type, missing
required section) RAISES before any product is scored. This is what makes
externalized config at least as safe as the module constants it replaces.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "scoring_v4"))

OMEGA_RUBRIC = REPO_ROOT / "scripts" / "data" / "omega_rubric.json"


def _rubric():
    return json.loads(OMEGA_RUBRIC.read_text())


def test_real_omega_rubric_passes():
    from scoring_v4.config_schema import validate_rubric

    validate_rubric("omega", _rubric())  # must not raise


def test_out_of_range_band_score_raises():
    from scoring_v4.config_schema import validate_rubric, RubricValidationError

    bad = _rubric()
    bad["dose"]["epa_dha_bands"][1]["score"] = 200  # the classic typo (18 -> 200)
    with pytest.raises(RubricValidationError):
        validate_rubric("omega", bad)


def test_wrong_type_cap_raises():
    from scoring_v4.config_schema import validate_rubric, RubricValidationError

    bad = _rubric()
    bad["dimension_caps"]["dose"] = "twenty-five"  # string where number expected
    with pytest.raises(RubricValidationError):
        validate_rubric("omega", bad)


def test_missing_required_section_raises():
    from scoring_v4.config_schema import validate_rubric, RubricValidationError

    bad = _rubric()
    del bad["dose"]
    with pytest.raises(RubricValidationError):
        validate_rubric("omega", bad)


def test_missing_schema_version_raises():
    from scoring_v4.config_schema import validate_rubric, RubricValidationError

    bad = _rubric()
    bad["_metadata"].pop("schema_version", None)
    with pytest.raises(RubricValidationError):
        validate_rubric("omega", bad)


def test_unregistered_rubric_raises():
    from scoring_v4.config_schema import validate_rubric, RubricValidationError

    with pytest.raises(RubricValidationError):
        validate_rubric("no_such_rubric", {})
