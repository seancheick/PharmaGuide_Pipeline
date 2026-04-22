"""
Sprint E1.2.3 — warning dedup regression tests.

Collapses semantically identical warnings within a list while preserving
the most informative copy. Dev rule: "Only collapse warnings that are
identical in meaning — not just similar in wording."

Dedup key (tuple, fully normalized):
    (severity,
     canonical_id or type,
     condition_id(s) as sorted tuple,
     drug_class_id(s) as sorted tuple,
     source_rule or source)

Completeness ordering (for picking which dupe to keep):
    1. has both alert_headline AND alert_body (richest form)
    2. has safety_warning (banned/recalled authored path)
    3. longest total populated-field char count (tiebreaker)

Hard stops (any of these fires → dedup has a bug):
  * total count increases
  * a kept warning loses fields vs its duplicates
  * condition_id / drug_class_id disappears from any kept entry
  * severity label changes

Dedup runs within each list independently — warnings[] and
warnings_profile_gated[] are NEVER cross-merged.
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

from scripts.build_final_db import _dedup_warnings  # noqa: E402


# ---------------------------------------------------------------------------
# Identity / key construction
# ---------------------------------------------------------------------------

def test_exact_duplicate_collapses_to_one() -> None:
    w = {
        "type": "interaction",
        "severity": "avoid",
        "canonical_id": "cbd_pregnancy",
        "condition_id": "pregnancy",
        "source_rule": "interaction_rules",
        "alert_headline": "Not recommended during pregnancy",
        "alert_body": "FDA advises against CBD use.",
    }
    out = _dedup_warnings([dict(w), dict(w)])
    assert len(out) == 1
    assert out[0]["alert_headline"] == "Not recommended during pregnancy"


def test_none_vs_empty_string_treated_equal_in_key() -> None:
    """Normalization contract: ``None``, ``""``, and missing key must
    hash to the same dedup-key slot."""
    a = {"type": "x", "severity": "moderate", "canonical_id": "k1",
         "condition_id": None, "source_rule": "r"}
    b = {"type": "x", "severity": "moderate", "canonical_id": "k1",
         "condition_id": "", "source_rule": "r"}
    c = {"type": "x", "severity": "moderate", "canonical_id": "k1",
         "source_rule": "r"}   # key absent entirely
    out = _dedup_warnings([a, b, c])
    assert len(out) == 1


def test_condition_id_scalar_vs_list_same_value_dedupe() -> None:
    """condition_id may be scalar pre-E1.4.1, list post-E1.4.1. Same
    logical condition must collapse across shapes."""
    a = {"type": "i", "severity": "avoid", "canonical_id": "k",
         "condition_id": "pregnancy", "source_rule": "r"}
    b = {"type": "i", "severity": "avoid", "canonical_id": "k",
         "condition_ids": ["pregnancy"], "source_rule": "r"}
    out = _dedup_warnings([a, b])
    assert len(out) == 1


# ---------------------------------------------------------------------------
# Different by ANY key component → kept separate
# ---------------------------------------------------------------------------

def test_different_condition_id_not_merged() -> None:
    a = {"type": "i", "severity": "avoid", "canonical_id": "k",
         "condition_id": "pregnancy", "source_rule": "r"}
    b = {"type": "i", "severity": "avoid", "canonical_id": "k",
         "condition_id": "liver_disease", "source_rule": "r"}
    out = _dedup_warnings([a, b])
    assert len(out) == 2


def test_different_severity_not_merged() -> None:
    a = {"type": "i", "severity": "avoid", "canonical_id": "k",
         "condition_id": "pregnancy", "source_rule": "r"}
    b = {"type": "i", "severity": "contraindicated", "canonical_id": "k",
         "condition_id": "pregnancy", "source_rule": "r"}
    out = _dedup_warnings([a, b])
    assert len(out) == 2


def test_different_source_rule_not_merged() -> None:
    """Dev's edge case: same canonical_id, different source_rule (FDA
    vs interaction engine) — these are NOT duplicates, keep both."""
    a = {"type": "ban", "severity": "critical", "canonical_id": "dmaa",
         "source_rule": "fda_recall_list"}
    b = {"type": "ban", "severity": "critical", "canonical_id": "dmaa",
         "source_rule": "interaction_rules"}
    out = _dedup_warnings([a, b])
    assert len(out) == 2


# ---------------------------------------------------------------------------
# Selection rule — keep the most-complete copy
# ---------------------------------------------------------------------------

def test_keeps_entry_with_alert_headline_and_body_over_bare_one() -> None:
    rich = {
        "type": "i", "severity": "avoid", "canonical_id": "k",
        "condition_id": "pregnancy", "source_rule": "r",
        "alert_headline": "Not recommended during pregnancy",
        "alert_body": "FDA advises...",
    }
    bare = {
        "type": "i", "severity": "avoid", "canonical_id": "k",
        "condition_id": "pregnancy", "source_rule": "r",
        "alert_headline": "Not recommended during pregnancy",
    }
    out = _dedup_warnings([bare, rich])
    assert len(out) == 1
    assert out[0]["alert_body"] == "FDA advises..."


def test_vitafusion_canary_pattern() -> None:
    """Canary 246324 pattern: two copies of the CBD/pregnancy warning,
    one with populated `detail` and one with empty. Must keep the
    populated one."""
    full = {
        "type": "interaction", "severity": "avoid",
        "canonical_id": "Cannabidiol / pregnancy",
        "condition_id": "pregnancy", "source": "interaction_rules",
        "alert_headline": "Not recommended during pregnancy",
        "alert_body": "FDA strongly advises against CBD.",
        "detail": "FDA strongly advises against CBD use during pregnancy. Animal data shows...",
    }
    stub = {
        "type": "interaction", "severity": "avoid",
        "canonical_id": "Cannabidiol / pregnancy",
        "condition_id": "pregnancy", "source": "interaction_rules",
        "alert_headline": "Not recommended during pregnancy",
        "alert_body": "FDA strongly advises against CBD.",
        "detail": "",
    }
    out = _dedup_warnings([stub, full])
    assert len(out) == 1
    assert out[0]["detail"].startswith("FDA strongly advises"), out[0]


def test_falls_back_to_safety_warning_when_no_alert_fields() -> None:
    """Banned/recalled entries use safety_warning rather than alert_*."""
    authored = {
        "type": "banned_substance", "severity": "critical",
        "canonical_id": "DMAA", "source_rule": "banned_recalled_ingredients",
        "safety_warning": "FDA-banned stimulant with cardiovascular risk.",
        "safety_warning_one_liner": "FDA-banned. Avoid.",
    }
    stub = {
        "type": "banned_substance", "severity": "critical",
        "canonical_id": "DMAA", "source_rule": "banned_recalled_ingredients",
    }
    out = _dedup_warnings([stub, authored])
    assert len(out) == 1
    assert out[0]["safety_warning"].startswith("FDA-banned stimulant")


# ---------------------------------------------------------------------------
# Hard stops — invariants the impl must never violate
# ---------------------------------------------------------------------------

def test_dedup_never_increases_count() -> None:
    wlist = [
        {"type": "a", "severity": "s", "canonical_id": "1"},
        {"type": "b", "severity": "s", "canonical_id": "2"},
        {"type": "a", "severity": "s", "canonical_id": "1"},  # dup
    ]
    out = _dedup_warnings(wlist)
    assert len(out) <= len(wlist)


def test_dedup_preserves_severity_on_kept_entry() -> None:
    w = {"type": "i", "severity": "avoid", "canonical_id": "k",
         "condition_id": "pregnancy", "source_rule": "r",
         "alert_headline": "h"}
    out = _dedup_warnings([w, dict(w)])
    assert out[0]["severity"] == "avoid"


def test_dedup_preserves_condition_id_on_kept_entry() -> None:
    w = {"type": "i", "severity": "avoid", "canonical_id": "k",
         "condition_id": "pregnancy", "source_rule": "r",
         "alert_headline": "h"}
    out = _dedup_warnings([w, dict(w)])
    assert out[0].get("condition_id") == "pregnancy"


def test_empty_and_non_list_inputs() -> None:
    assert _dedup_warnings([]) == []
    assert _dedup_warnings(None) == []
    # Skip non-dict entries quietly
    assert _dedup_warnings(["bogus", None, 42,
                            {"type": "a", "severity": "s"}]) == [{"type": "a", "severity": "s"}]


def test_dedup_is_idempotent() -> None:
    """dedup(dedup(xs)) == dedup(xs)."""
    wlist = [
        {"type": "i", "severity": "avoid", "canonical_id": "k",
         "condition_id": "pregnancy", "source_rule": "r",
         "alert_headline": "h"},
        {"type": "i", "severity": "avoid", "canonical_id": "k",
         "condition_id": "pregnancy", "source_rule": "r",
         "alert_headline": "h"},
    ]
    once = _dedup_warnings(wlist)
    twice = _dedup_warnings(once)
    assert once == twice


# ---------------------------------------------------------------------------
# Ordering — severity priority preserved across dedup
# ---------------------------------------------------------------------------

def test_dedup_preserves_relative_order_of_distinct_warnings() -> None:
    """Input order of surviving entries must be preserved (their
    severity-first ordering is already applied upstream)."""
    first = {"type": "ban", "severity": "critical", "canonical_id": "a"}
    second = {"type": "i", "severity": "avoid", "canonical_id": "b"}
    third = {"type": "ban", "severity": "critical", "canonical_id": "a"}  # dup of first
    out = _dedup_warnings([first, second, third])
    assert len(out) == 2
    # First survivor must still be the "critical" entry (index 0 originally)
    assert out[0]["canonical_id"] == "a"
    assert out[1]["canonical_id"] == "b"
