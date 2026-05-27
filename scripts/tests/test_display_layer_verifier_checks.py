"""Hermetic unit tests for Wave 9.B.3 Phase 1 display_layer verifier checks.

Tests the pure `check_display_layer_policy(entry)` function in
scripts/api_audit/verify_interactions.py — no network, no real entries,
no curated_interactions data touched. Each test passes a minimal entry
dict and asserts the expected issue shape.

Per Wave 9.B.2 schema design
(reports/wave_9b_minor_review/9B2_SCHEMA_DESIGN_DISPLAY_LAYER.md) and
Wave 9.B.3 Phase 1 directive (2026-05-27):

  - Check 12: display_layer enum — only {"alert", "background"} when present
  - Check 13: severity ↔ lane invariant
      alert + Minor       → warning (migration; → error post-Phase-3)
      background + Major+ → error (hard policy conflict)
      absent + Minor      → warning (migration; missing declaration)
      absent + Major+     → no finding (backward-compat default = alert)
  - Check 14: background_rationale required when display_layer="background"

Phase 1 is verifier-only — no data, no SQLite, no Supabase, no Flutter
changes. Migration warnings are intentional; they will be promoted to
errors only after Phase 3 backfills explicit display_layer on every
non-retired entry.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from api_audit.verify_interactions import (
    check_display_layer_policy,
    DISPLAY_LAYER_VALUES,
    ALERT_LANE_DRAFT_SEVERITIES,
    BACKGROUND_LANE_DRAFT_SEVERITIES,
)


# --------------------------------------------------------------------------- #
# Sanity: the module-level enums are what we expect
# --------------------------------------------------------------------------- #


def test_display_layer_values_enum_is_exactly_two():
    """Per the 9.B.2 design: only `alert` and `background`. Deprecation
    reuses the existing `retired_at` column — there is no `deprecated`
    display_layer value to avoid duplicating the deprecation primitive."""
    assert DISPLAY_LAYER_VALUES == frozenset({"alert", "background"})


def test_severity_lane_sets_are_disjoint_and_cover_the_severity_map():
    """No severity may appear in both lanes; together they cover the four
    draft severities defined in SEVERITY_MAP (contraindicated, major,
    moderate, minor)."""
    assert ALERT_LANE_DRAFT_SEVERITIES.isdisjoint(BACKGROUND_LANE_DRAFT_SEVERITIES)
    union = ALERT_LANE_DRAFT_SEVERITIES | BACKGROUND_LANE_DRAFT_SEVERITIES
    # Each of the 4 SEVERITY_MAP keys must land in exactly one lane
    for sev_key in ("contraindicated", "major", "moderate", "minor"):
        assert sev_key in union, f"severity {sev_key!r} must be classified into a lane"


# --------------------------------------------------------------------------- #
# Check 12 — display_layer enum
# --------------------------------------------------------------------------- #


def test_absent_display_layer_with_alert_severity_emits_no_finding():
    """Backward-compat: absent display_layer + Major severity is the
    current state of ~123 alert entries. They must validate clean during
    the migration window (Phase 3 will explicitly backfill them)."""
    entry = {"severity": "Major"}
    issues = check_display_layer_policy(entry)
    assert issues == []


def test_invalid_display_layer_value_is_error():
    """Anything outside the enum is rejected. Common author mistakes
    (capitalized 'Alert', the string 'deprecated') must not slip in."""
    for bad in ("Alert", "BACKGROUND", "deprecated", "retired", "hidden", "foo"):
        entry = {"severity": "Major", "display_layer": bad}
        issues = check_display_layer_policy(entry)
        assert any(i["check"] == "display_layer_enum" for i in issues), (
            f"display_layer={bad!r} must trigger Check 12 enum error"
        )
        # Severity should be 'error' (hard reject)
        enum_issues = [i for i in issues if i["check"] == "display_layer_enum"]
        assert all(i["severity"] == "error" for i in enum_issues)
        # When enum is broken, lane/rationale checks are skipped to avoid
        # cascading nonsense findings.
        assert all(i["check"] == "display_layer_enum" for i in issues), (
            f"only enum issue should fire when display_layer={bad!r} is invalid"
        )


def test_valid_alert_with_explicit_display_layer_emits_no_finding():
    entry = {"severity": "Major", "display_layer": "alert"}
    assert check_display_layer_policy(entry) == []


def test_valid_background_with_rationale_emits_no_finding():
    entry = {
        "severity": "Minor",
        "display_layer": "background",
        "background_rationale": "CoQ10 is studied as mitigation for SAMS, not an adverse interaction.",
    }
    assert check_display_layer_policy(entry) == []


# --------------------------------------------------------------------------- #
# Check 13 — severity ↔ lane invariant
# --------------------------------------------------------------------------- #


def test_alert_lane_with_minor_severity_emits_warning_during_migration():
    """The 25 legacy Minor entries scenario: alert + Minor is a policy
    contradiction, but during the Phase 1→Phase 3 migration window the
    verifier flags it as a WARNING so the build still succeeds while
    authors process the backlog. The 'migration_warning' detail flag is
    the signal that this will become an error post-Phase-3."""
    entry = {"severity": "Minor", "display_layer": "alert"}
    issues = check_display_layer_policy(entry)
    lane_issues = [i for i in issues if i["check"] == "display_layer_lane"]
    assert lane_issues, "alert + Minor must trigger Check 13"
    assert lane_issues[0]["severity"] == "warning", (
        "alert + Minor must be WARNING during migration, not error"
    )
    assert lane_issues[0]["details"].get("migration_warning") is True, (
        "the migration_warning flag is required so a follow-up batch can "
        "promote these specific issues to errors after Phase 3 backfill"
    )


def test_background_lane_with_major_severity_is_hard_error():
    """background + Major is NOT a migration artifact — it's a real policy
    conflict (background lane is for Minor/Monitor only). Must be hard error,
    not a migration warning, because no legacy entry has this combo by
    accident (you'd have to explicitly set display_layer='background' on
    a Major entry)."""
    entry = {
        "severity": "Major",
        "display_layer": "background",
        "background_rationale": "this rationale exists but the combo is still wrong",
    }
    issues = check_display_layer_policy(entry)
    lane_issues = [i for i in issues if i["check"] == "display_layer_lane"]
    assert lane_issues
    assert lane_issues[0]["severity"] == "error", (
        "background + Major must be hard ERROR, not a migration warning"
    )
    assert "migration_warning" not in (lane_issues[0].get("details") or {}), (
        "hard policy conflicts must not carry the migration_warning flag"
    )


def test_absent_display_layer_with_minor_severity_emits_migration_warning():
    """Currently the 25 legacy Minor entries are in this state: severity
    declared but display_layer absent. Check 13's 'missing' branch fires
    a migration warning so the backlog is visible without blocking the
    build."""
    entry = {"severity": "Minor"}
    issues = check_display_layer_policy(entry)
    missing_issues = [i for i in issues if i["check"] == "display_layer_missing"]
    assert missing_issues
    assert missing_issues[0]["severity"] == "warning"
    assert missing_issues[0]["details"].get("migration_warning") is True


def test_absent_display_layer_with_contraindicated_or_moderate_is_clean():
    """The ~123 current Major/Moderate/Contraindicated entries without an
    explicit display_layer must validate clean during migration — they
    fall back to the implicit 'alert' default which is correct for them.
    Phase 3 will backfill explicit declarations; Phase 1 must not noise
    the build for these legacy-but-correct entries."""
    for sev in ("Major", "Moderate", "Contraindicated"):
        entry = {"severity": sev}
        issues = check_display_layer_policy(entry)
        assert issues == [], (
            f"absent display_layer + {sev} must emit no finding during migration; "
            f"got: {issues}"
        )


def test_retired_entry_skips_lane_checks_even_with_bad_combo():
    """Retired entries are not user-facing. The lane invariant doesn't
    apply — the entry is preserved as audit history regardless of what
    its severity / display_layer look like. Check 13 must skip retired
    entries entirely so old retracted alerts don't generate phantom
    warnings forever."""
    entry = {
        "severity": "Minor",
        "display_layer": "alert",       # would normally warn (Check 13)
        "retired_at": "2024-01-15T00:00:00Z",
        "retired_reason": "Evidence retracted; superseded by ...",
    }
    issues = check_display_layer_policy(entry)
    lane_issues = [i for i in issues if i["check"] in {
        "display_layer_lane",
        "display_layer_missing",
    }]
    assert lane_issues == [], (
        "retired entries must not trigger lane invariants; got: "
        f"{lane_issues}"
    )


# --------------------------------------------------------------------------- #
# Check 14 — background_rationale required
# --------------------------------------------------------------------------- #


def test_background_without_rationale_is_hard_error():
    """Authors who promote an entry to display_layer='background' MUST
    record WHY in background_rationale. This is the load-bearing
    documentation for the next reviewer; missing it is a hard error,
    not a warning."""
    entry = {"severity": "Minor", "display_layer": "background"}
    issues = check_display_layer_policy(entry)
    rationale_issues = [i for i in issues if i["check"] == "display_layer_rationale"]
    assert rationale_issues, "missing background_rationale must trigger Check 14"
    assert rationale_issues[0]["severity"] == "error"


def test_background_with_empty_string_rationale_is_hard_error():
    """An empty string / whitespace-only rationale is the same as missing."""
    for empty in ("", "   ", "\n\t "):
        entry = {
            "severity": "Minor",
            "display_layer": "background",
            "background_rationale": empty,
        }
        issues = check_display_layer_policy(entry)
        assert any(i["check"] == "display_layer_rationale" for i in issues), (
            f"empty rationale {empty!r} must trigger Check 14"
        )


def test_background_with_non_string_rationale_is_hard_error():
    """A non-string value (e.g., None, an integer) is also treated as missing."""
    for bad in (None, 0, [], {}):
        entry = {
            "severity": "Minor",
            "display_layer": "background",
            "background_rationale": bad,
        }
        issues = check_display_layer_policy(entry)
        assert any(i["check"] == "display_layer_rationale" for i in issues)


def test_alert_lane_does_not_require_background_rationale():
    """background_rationale is only meaningful for the background lane.
    Setting it on an alert entry is allowed (won't be a finding) but
    isn't required."""
    entry = {"severity": "Major", "display_layer": "alert"}
    issues = check_display_layer_policy(entry)
    assert not any(i["check"] == "display_layer_rationale" for i in issues)


# --------------------------------------------------------------------------- #
# Real-world scenarios from the 9.B classification report
# --------------------------------------------------------------------------- #


def test_scenario_dsi_ssri_fishoil_lane_c_via_retirement():
    """DSI_SSRI_FISHOIL is the firm Lane C candidate. Once
    Phase 5 retires it (sets retired_at + retired_reason), the entry
    must pass all display_layer checks — retirement supersedes lane
    membership."""
    entry = {
        "severity": "Minor",
        "retired_at": "2026-06-01T00:00:00Z",
        "retired_reason": "Entry's own mechanism text states 'no significant adverse interaction is known'.",
    }
    assert check_display_layer_policy(entry) == []


def test_scenario_dsi_statins_coq10_lane_b_with_rationale():
    """DSI_STATINS_COQ10 is a Lane B (background) candidate. Once
    Phase 5 sets display_layer='background' + a rationale, the entry
    must validate clean."""
    entry = {
        "severity": "Minor",
        "display_layer": "background",
        "background_rationale": (
            "CoQ10 is studied as mitigation for statin-associated muscle symptoms (SAMS), "
            "not an adverse interaction. Belongs in profile-informed insights, not user-facing alerts."
        ),
    }
    assert check_display_layer_policy(entry) == []


def test_scenario_legacy_minor_entry_today_emits_one_migration_warning():
    """The current state of all 25 legacy Minor entries: severity=Minor,
    no display_layer, no retired_at. Each one must emit exactly one
    migration warning (the 'display_layer_missing' Check 13 branch) —
    enough signal to track the backlog without blocking the build."""
    entry = {"severity": "Minor"}
    issues = check_display_layer_policy(entry)
    warnings_only = [i for i in issues if i["severity"] == "warning"]
    errors_only = [i for i in issues if i["severity"] == "error"]
    assert errors_only == [], "legacy Minor entries must not block builds during migration"
    assert len(warnings_only) == 1, (
        "legacy Minor entry must emit exactly one migration warning; "
        f"got: {warnings_only}"
    )
    assert warnings_only[0]["check"] == "display_layer_missing"


# --------------------------------------------------------------------------- #
# Negative test: function purity (no side effects on the input)
# --------------------------------------------------------------------------- #


def test_function_does_not_mutate_input_entry():
    """check_display_layer_policy must be a pure function — never mutates
    the input dict. The verifier pipeline relies on this so the entry can
    be passed by reference to multiple checks."""
    entry = {
        "severity": "Major",
        "display_layer": "alert",
        "background_rationale": "irrelevant for alert lane",
    }
    snapshot = dict(entry)
    check_display_layer_policy(entry)
    assert entry == snapshot, "input entry was mutated by check_display_layer_policy"
