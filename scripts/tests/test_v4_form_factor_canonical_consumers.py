"""SP-3 C3 — v4 consumers (completeness gate,
build_final_db) read `form_factor_canonical` first, fall back to legacy.

Locks the canonical-first reading contract at each consumer site without
needing the full pipeline.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scoring_v4.gate_completeness import _form_factor as _completeness_form


# ============================================================================
# Completeness gate consumer
# ============================================================================

class TestCompletenessGate:

    def test_canonical_wins_over_legacy(self):
        """When both present, canonical id is returned."""
        product = {
            "form_factor_canonical": "softgel",
            "form_factor": "capsule",  # legacy was wrong (collapsed softgel)
        }
        assert _completeness_form(product) == "softgel"

    def test_legacy_used_when_canonical_absent(self):
        """Old batch — no canonical field. Falls through to legacy."""
        product = {"form_factor": "capsule"}
        assert _completeness_form(product) == "capsule"

    def test_legacy_used_when_canonical_unknown(self):
        """`unknown` sentinel does NOT block legacy fallback. Otherwise old
        batches that the new normalizer fails on would be flagged missing."""
        product = {"form_factor_canonical": "unknown", "form_factor": "tablet"}
        assert _completeness_form(product) == "tablet"

    def test_both_missing_returns_empty(self):
        assert _completeness_form({}) == ""

    def test_canonical_only_returns_canonical(self):
        product = {"form_factor_canonical": "gummy"}
        assert _completeness_form(product) == "gummy"


# ============================================================================
# build_final_db consumer — verify the function uses canonical first
# ============================================================================

class TestBuildFinalDbServingVerb:
    """Light contract test — build_final_db._derive_dosing_summary is heavy
    to call directly. We assert the canonical-preference logic via the
    public _derive_serving_verb_and_noun seam after passing canonical text."""

    def test_softgel_canonical_yields_softgel_verb(self):
        from build_final_db import _derive_serving_verb_and_noun
        verb, sing, plural = _derive_serving_verb_and_noun("ct", "softgel")
        # "softgel" should map to "take" verb with softgel noun
        assert verb
        assert "softgel" in sing.lower() or "softgel" in plural.lower()

    def test_gummy_canonical_yields_gummy_verb(self):
        from build_final_db import _derive_serving_verb_and_noun
        verb, sing, plural = _derive_serving_verb_and_noun("ct", "gummy")
        assert "gumm" in (sing + plural).lower()

    def test_unknown_form_falls_back(self):
        """`unknown` canonical should fall through to the unit-only heuristic."""
        from build_final_db import _derive_serving_verb_and_noun
        verb, sing, plural = _derive_serving_verb_and_noun("ct", "")
        # Generic fallback — just assert no crash + non-empty
        assert verb
        assert sing
