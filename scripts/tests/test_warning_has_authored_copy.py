"""
Sprint E1.1.3 — regression tests for warning authored-copy completeness.

Every warning must carry at least one non-empty authored-copy field from
the required set: ``alert_headline``, ``alert_body``, ``safety_warning``,
``safety_warning_one_liner``, ``detail``. A warning lacking all five
would render as raw enum text in Flutter (e.g. the user sees
"ban_ingredient" instead of Dr Pham's authored copy).

The build-time validator fails on any such leak, emitting
``dsld_id + warning_type`` so Dr Pham's authoring queue can be populated
from triage output.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_final_db import (  # noqa: E402
    _validate_warning_has_authored_copy,
    _WARNING_REQUIRED_COPY_FIELDS,
)


# ---------------------------------------------------------------------------
# Passes — at least one field populated
# ---------------------------------------------------------------------------

def test_validator_passes_on_empty_warnings_list() -> None:
    _validate_warning_has_authored_copy([], "CLEAN-0001")


@pytest.mark.parametrize("field", list(_WARNING_REQUIRED_COPY_FIELDS))
def test_validator_passes_when_any_single_field_populated(field: str) -> None:
    """Each of the 5 required fields should independently satisfy the
    validator when populated alone."""
    warnings = [{
        "type": "interaction",
        "display_mode_default": "suppress",
        field: "Non-empty authored copy.",
    }]
    _validate_warning_has_authored_copy(warnings, "OK-SINGLE-FIELD")


def test_validator_passes_when_multiple_fields_populated() -> None:
    warnings = [{
        "type": "banned_substance",
        "display_mode_default": "critical",
        "safety_warning": "FDA-banned.",
        "safety_warning_one_liner": "Avoid.",
        "detail": "Regulatory status detail.",
    }]
    _validate_warning_has_authored_copy(warnings, "OK-MULTI")


# ---------------------------------------------------------------------------
# Fails — all 5 fields empty or missing
# ---------------------------------------------------------------------------

def test_validator_raises_when_all_fields_missing() -> None:
    warnings = [{
        "type": "ban_ingredient",
        "display_mode_default": "critical",
    }]
    with pytest.raises(ValueError, match="E1.1.3"):
        _validate_warning_has_authored_copy(warnings, "BAD-0001")


def test_validator_raises_when_all_fields_empty_string() -> None:
    warnings = [{
        "type": "interaction",
        "display_mode_default": "suppress",
        "alert_headline": "",
        "alert_body": "",
        "safety_warning": "",
        "safety_warning_one_liner": "",
        "detail": "",
    }]
    with pytest.raises(ValueError, match="E1.1.3"):
        _validate_warning_has_authored_copy(warnings, "BAD-EMPTY")


def test_validator_raises_when_all_fields_whitespace_only() -> None:
    """Whitespace-only is not populated copy."""
    warnings = [{
        "type": "interaction",
        "display_mode_default": "suppress",
        "alert_headline": "   ",
        "alert_body": "\n\t ",
        "detail": "",
    }]
    with pytest.raises(ValueError, match="E1.1.3"):
        _validate_warning_has_authored_copy(warnings, "BAD-WS")


def test_validator_raises_when_fields_are_non_string_types() -> None:
    """None / numbers in authored-copy slots do not satisfy the invariant."""
    warnings = [{
        "type": "safety",
        "display_mode_default": "critical",
        "alert_headline": None,
        "alert_body": 0,
        "safety_warning": None,
        "safety_warning_one_liner": [],
        "detail": {},
    }]
    with pytest.raises(ValueError, match="E1.1.3"):
        _validate_warning_has_authored_copy(warnings, "BAD-NON-STRINGS")


# ---------------------------------------------------------------------------
# Error message — usable as Dr Pham authoring-queue triage input
# ---------------------------------------------------------------------------

def test_error_message_carries_dsld_id_and_type() -> None:
    warnings = [{"type": "ban_ingredient", "display_mode_default": "critical"}]
    with pytest.raises(ValueError) as excinfo:
        _validate_warning_has_authored_copy(warnings, "DSLD-12345")
    msg = str(excinfo.value)
    assert "DSLD-12345" in msg
    assert "ban_ingredient" in msg
    assert "Dr Pham authoring queue" in msg


# ---------------------------------------------------------------------------
# Robustness — non-dict entries and mixed lists don't blow up
# ---------------------------------------------------------------------------

def test_validator_skips_non_dict_entries() -> None:
    """A warning list contaminated with non-dict entries (defensive) must
    skip them gracefully, still validating the dict entries."""
    warnings = [
        "bogus string",
        None,
        42,
        {"type": "interaction", "display_mode_default": "suppress", "detail": "Ok."},
    ]
    _validate_warning_has_authored_copy(warnings, "MIXED-OK")


def test_validator_validates_all_entries_not_just_first() -> None:
    """A list with one valid and one invalid entry must still raise on
    the invalid one (not stop at the first)."""
    warnings = [
        {"type": "interaction", "display_mode_default": "suppress", "detail": "Ok."},
        {"type": "ban_ingredient", "display_mode_default": "critical"},
    ]
    with pytest.raises(ValueError, match="ban_ingredient"):
        _validate_warning_has_authored_copy(warnings, "MIXED-BAD")


# ---------------------------------------------------------------------------
# End-to-end: current pipeline emission paths all satisfy the invariant
# ---------------------------------------------------------------------------

def test_current_emission_paths_all_populate_detail_fallback() -> None:
    """Smoke test — build a detail blob via the real build_detail_blob
    and assert every warning has at least one required-copy field. This
    guards the invariant against any regression in the warnings-building
    loops in build_final_db."""
    sys.path.insert(0, str(Path(__file__).parent))
    from test_build_final_db import make_enriched, make_scored  # noqa: E402
    from scripts.build_final_db import build_detail_blob  # noqa: E402

    blob = build_detail_blob(make_enriched(), make_scored())
    for w in blob["warnings"]:
        assert any(
            isinstance(w.get(f), str) and w.get(f).strip()
            for f in _WARNING_REQUIRED_COPY_FIELDS
        ), f"warning has no authored copy: {w}"
    for w in blob["warnings_profile_gated"]:
        assert any(
            isinstance(w.get(f), str) and w.get(f).strip()
            for f in _WARNING_REQUIRED_COPY_FIELDS
        ), f"gated warning has no authored copy: {w}"
