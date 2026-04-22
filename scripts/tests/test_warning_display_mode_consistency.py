"""
Sprint E1.1.2 — regression tests for warning display_mode vs copy consistency.

A warning with ``display_mode_default == "critical"`` is rendered to every
user regardless of profile. Its copy must therefore be profile-agnostic —
no "during pregnancy", "for liver disease", etc. The condition-specific
variants belong under ``display_mode_default == "suppress"`` (profile-
gated) and are surfaced only when Flutter's on-device filter matches the
rule's ``condition_id`` / ``drug_class_id`` against the user's profile.

Covers two flavors of the invariant:

  1. Build-time validator: critical-mode warnings with condition-specific
     copy in any authored-copy field → ValueError.
  2. Emission-time policy: interaction-rule severities inside
     ``condition_rules[]`` / ``drug_class_rules[]`` map to
     ``display_mode_default == "suppress"`` — even when severity is
     ``contraindicated``. Flutter promotes on profile match.
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
    _validate_warning_display_mode_consistency,
    _WARNING_CONDITION_SPECIFIC_RE,
)


# ---------------------------------------------------------------------------
# Validator — passes on clean inputs
# ---------------------------------------------------------------------------

def test_validator_passes_on_empty_warnings_list() -> None:
    _validate_warning_display_mode_consistency([], "CLEAN-0001")


def test_validator_passes_on_profile_agnostic_critical() -> None:
    warnings = [{
        "type": "banned_substance",
        "display_mode_default": "critical",
        "safety_warning_one_liner": "FDA-banned. Avoid.",
        "safety_warning": "Banned for cardiovascular risk. Avoid.",
    }]
    _validate_validator_passes(warnings)


def test_validator_passes_on_suppress_with_condition_specific_copy() -> None:
    """Profile-gated warnings (suppress) are ALLOWED to carry condition-
    specific copy — that's why they are gated."""
    warnings = [{
        "type": "interaction",
        "display_mode_default": "suppress",
        "condition_id": "pregnancy",
        "alert_headline": "Do not use during pregnancy",
        "alert_body": "May affect fetal development.",
    }]
    _validate_validator_passes(warnings)


def _validate_validator_passes(warnings) -> None:
    """Helper — asserts validator does not raise."""
    _validate_warning_display_mode_consistency(warnings, "TEST-001")


# ---------------------------------------------------------------------------
# Validator — raises on critical + condition-specific copy across fields
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("field,phrase", [
    ("alert_headline", "Do not use during pregnancy"),
    ("alert_body", "Avoid while nursing."),
    ("safety_warning", "Contraindicated for liver disease patients."),
    ("safety_warning_one_liner", "Not safe during pregnancy."),
    ("safety_summary", "Avoid during breastfeeding."),
    ("safety_summary_one_liner", "Risky for kidney disease."),
    ("detail", "Caution during pregnancy."),
    ("title", "Warning during pregnancy"),
    ("informational_note", "Note: breastfeeding concerns."),
])
def test_validator_raises_on_critical_with_condition_specific_copy(
    field: str, phrase: str
) -> None:
    warnings = [{
        "type": "interaction",
        "display_mode_default": "critical",
        field: phrase,
    }]
    with pytest.raises(ValueError, match="Sprint E1.1.2"):
        _validate_warning_display_mode_consistency(warnings, "BAD-0001")


def test_validator_reports_condition_token_in_error_message() -> None:
    warnings = [{
        "type": "interaction",
        "display_mode_default": "critical",
        "alert_headline": "Do not use during pregnancy",
    }]
    with pytest.raises(ValueError) as excinfo:
        _validate_warning_display_mode_consistency(warnings, "BAD-0002")
    assert "during pregnancy" in str(excinfo.value)
    assert "BAD-0002" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Validator — not confused by non-string fields or missing keys
# ---------------------------------------------------------------------------

def test_validator_ignores_non_string_fields() -> None:
    warnings = [{
        "type": "interaction",
        "display_mode_default": "critical",
        "alert_headline": None,  # None, not a string
        "alert_body": "",  # empty string
        "detail": 42,  # non-string value in authored-copy field
    }]
    _validate_warning_display_mode_consistency(warnings, "CLEAN-0002")


def test_validator_skips_non_dict_entries() -> None:
    warnings = ["not a dict", None, 42, {
        "type": "interaction",
        "display_mode_default": "suppress",
        "alert_headline": "Do not use during pregnancy",
    }]
    _validate_warning_display_mode_consistency(warnings, "SKIP-0001")


# ---------------------------------------------------------------------------
# Emission policy — profile-scoped interaction rules default to suppress
# ---------------------------------------------------------------------------

def test_contraindicated_interaction_defaults_to_suppress() -> None:
    """End-to-end: a profile-scoped contraindicated interaction rule
    emits ``display_mode_default="suppress"`` in the detail blob.
    Pre-E1.1.2 this defaulted to ``critical``, forcing the condition-
    specific copy onto every user.
    """
    # Import fixtures from the existing test module; keeps the fixture
    # definition in one place (test_build_final_db) without duplicating.
    sys.path.insert(0, str(Path(__file__).parent))
    from test_build_final_db import make_enriched, make_scored  # noqa: E402

    from scripts.build_final_db import build_detail_blob  # noqa: E402

    enriched = make_enriched()
    enriched.setdefault("interaction_profile", {})["ingredient_alerts"] = [{
        "ingredient_name": "DHEA",
        "condition_hits": [{
            "severity": "contraindicated",
            "condition_id": "pregnancy",
            "mechanism": "Hormonal risk",
            "action": "Avoid",
            "alert_headline": "Do not use during pregnancy",
            "alert_body": "Hormonal activity concerns.",
            "evidence_level": "moderate",
        }],
        "drug_class_hits": [],
    }]

    blob = build_detail_blob(enriched, make_scored())

    contra = [
        w for w in blob["warnings"]
        if w.get("source") == "interaction_rules"
        and w.get("severity") == "contraindicated"
    ]
    assert contra, "fixture did not produce a contraindicated interaction"
    for w in contra:
        assert w["display_mode_default"] == "suppress", (
            f"Sprint E1.1.2: expected 'suppress' on profile-scoped "
            f"contraindicated rule; got {w.get('display_mode_default')!r}"
        )
        assert w["severity_contextual"] == "contraindicated"


# ---------------------------------------------------------------------------
# 10 known condition-specific examples from current enricher output
# (sprint DoD requires this coverage)
# ---------------------------------------------------------------------------

KNOWN_CONDITION_SPECIFIC_EXAMPLES = [
    ("Do not use during pregnancy", "during pregnancy"),
    ("Not recommended during pregnancy", "during pregnancy"),
    ("Avoid while nursing", "while nursing"),
    ("Breastfeeding safety not established", "breastfeeding"),
    ("Contraindicated for liver disease", "for liver disease"),
    ("Caution: kidney disease", "kidney disease"),
    ("Contraindicated for heart disease", "heart disease"),
    ("May affect pregnancy — consult physician", None),   # NOT condition-specific: profile-agnostic phrasing
    ("Pregnant users: consult your doctor.", None),        # NOT condition-specific per the sprint regex
    ("FDA-banned. Avoid.", None),                          # Clean
]


@pytest.mark.parametrize("text,expected_match", KNOWN_CONDITION_SPECIFIC_EXAMPLES)
def test_regex_detects_condition_specific_phrasing(text: str, expected_match: str | None) -> None:
    m = _WARNING_CONDITION_SPECIFIC_RE.search(text)
    if expected_match is None:
        assert m is None, f"Regex falsely matched profile-agnostic copy: {text!r}"
    else:
        assert m is not None and m.group(0).lower() == expected_match.lower(), (
            f"Regex missed condition-specific phrase {expected_match!r} in {text!r}"
        )


# ---------------------------------------------------------------------------
# End-to-end: drug-class-scoped contraindicated rules also default to
# suppress (same invariant, different emission loop).
# ---------------------------------------------------------------------------

def test_drug_class_contraindicated_defaults_to_suppress() -> None:
    """Drug-class-scoped interaction rules — e.g. 5-HTP + MAOI serotonin
    syndrome — are profile-scoped (match user's declared medications).
    Default display_mode_default=suppress; Flutter promotes to critical
    on profile match.
    """
    sys.path.insert(0, str(Path(__file__).parent))
    from test_build_final_db import make_enriched, make_scored  # noqa: E402
    from scripts.build_final_db import build_detail_blob  # noqa: E402

    enriched = make_enriched()
    enriched.setdefault("interaction_profile", {})["ingredient_alerts"] = [{
        "ingredient_name": "5-HTP",
        "condition_hits": [],
        "drug_class_hits": [{
            "severity": "contraindicated",
            "drug_class_id": "maoi",
            "mechanism": "Serotonin syndrome risk",
            "action": "Avoid combination",
            "alert_headline": "Do not combine with MAOIs",
            "alert_body": "Serotonin syndrome risk.",
            "evidence_level": "strong",
        }],
    }]

    blob = build_detail_blob(enriched, make_scored())

    contra = [
        w for w in blob["warnings"]
        if w.get("source") == "interaction_rules"
        and w.get("type") == "drug_interaction"
        and w.get("severity") == "contraindicated"
    ]
    assert contra
    for w in contra:
        assert w["display_mode_default"] == "suppress"
        assert w["severity_contextual"] == "contraindicated"
