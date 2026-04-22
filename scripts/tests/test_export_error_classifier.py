"""Tests for the Sprint E1.5 export-error classification taxonomy.

The classifier in build_final_db.py routes raised ``ValueError`` messages
from per-product export validators into one of three buckets so the
Supabase sync gate can distinguish catastrophic failures (blocking) from
by-design coverage gates and authoring-backlog warnings (non-blocking).

These tests lock down:
  1. Messages from E1.2.5 active-count reconciliation → excluded_by_gate
  2. Messages from E1.2.4 inactive-preservation gate → excluded_by_gate
  3. Messages from E1.1.2 tone sweep validator → warning
  4. Anything else (schema drift, unknown enum, etc.) → error (fail-safe)
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

from scripts.build_final_db import _classify_export_error  # noqa: E402


# ── by-design coverage gates (E1.2.5 / E1.2.4) ────────────────────────
# These are the two stable messages the gate emits on real product
# exclusions in the current E1 build. Gate is WAI — sync should not block.


def test_active_count_reconciliation_unexplained_drop() -> None:
    msg = (
        "[1256] raw DSLD disclosed 8 real active(s) but blob has 0 "
        "ingredients AND 0 drop reasons. Unexplained drop — inspect "
        "normalize_product flatten path (Sprint E1.2.5)."
    )
    assert _classify_export_error(msg) == "excluded_by_gate"


def test_inactive_preservation_filter_regression() -> None:
    msg = (
        "[42] raw DSLD disclosed 3 real inactive(s) but blob emits 0. "
        "Filter regression — inspect enhanced_normalizer"
        "._process_other_ingredients_enhanced (Sprint E1.2.4)."
    )
    assert _classify_export_error(msg) == "excluded_by_gate"


# ── authoring backlog (E1.1.2 tone sweep) ─────────────────────────────
# Warning bucket — non-blocking. Dr Pham authoring pass resolves later.


def test_critical_mode_warning_condition_specific_copy() -> None:
    msg = (
        "[1631] critical-mode warning (type='harmful_additive') "
        "carries condition-specific copy in 'alert_body': 'during "
        "pregnancy' — rewrite as profile-agnostic or set "
        "display_mode_default=\"suppress\" (Sprint E1.1.2)."
    )
    assert _classify_export_error(msg) == "warning"


# ── catastrophic failures (default) ───────────────────────────────────
# Anything not matching a known-safe pattern falls through to 'error'.
# This fail-safe default means new validator messages must be explicitly
# added to the taxonomy before they become non-blocking.


def test_column_count_mismatch_is_blocking_error() -> None:
    msg = "row has 89 columns, expected 91"
    assert _classify_export_error(msg) == "error"


def test_unknown_drop_reason_is_blocking_error() -> None:
    # E1.2.5 validator also raises when it sees a drop-reason outside
    # the allowed enum. That's a real schema violation — blocking.
    msg = (
        "[99] unknown drop reason 'DROPPED_MYSTERIOUS' in "
        "ingredients_dropped_reasons — must be one of "
        "['DROPPED_AS_INACTIVE', 'DROPPED_NUTRITION_FACT'] (Sprint E1.2.5)."
    )
    assert _classify_export_error(msg) == "error"


def test_generic_exception_is_blocking_error() -> None:
    # Random unexpected exceptions (KeyError message, stringified,
    # something outside any validator) default to blocking.
    assert _classify_export_error("KeyError: 'product_name'") == "error"
    assert _classify_export_error("invalid JSON at line 42") == "error"
    assert _classify_export_error("") == "error"


# ── ordering / regression guards ──────────────────────────────────────
# Patterns are ordered in _EXPORT_ERROR_TAXONOMY — first match wins.
# These tests ensure a tone-flavored message can't accidentally match
# the broader coverage-gate pattern and vice versa.


def test_tone_message_does_not_match_coverage_gate_pattern() -> None:
    # A tone message that happens to mention "real actives" must still
    # be classified as 'warning', not 'excluded_by_gate'.
    msg = (
        "critical-mode warning (type='harmful_additive') carries "
        "condition-specific copy in 'alert_body': 'avoid taking with "
        "real actives' — rewrite as profile-agnostic."
    )
    # This message matches tone pattern; coverage-gate pattern expects
    # the more specific "raw DSLD disclosed N real" phrasing.
    assert _classify_export_error(msg) == "warning"


def test_inactive_count_mismatch_matches_coverage_gate() -> None:
    # Variant shape the gate might emit: zero actives vs raw-disclosed.
    msg = (
        "[9999] raw DSLD disclosed 1 real active(s) but blob has 0 "
        "ingredients"
    )
    assert _classify_export_error(msg) == "excluded_by_gate"
