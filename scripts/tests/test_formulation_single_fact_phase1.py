"""Canonical single-active fact and generic-Formulation separation.

THE BUG (plan §3, "the actual bug")
    generic_formulation.py gated the A6 focus bonus, the premium-single floor,
    the standard-single floor and the enzyme bonus on LEGACY
    `supp_type_of()` + `SINGLE_INGREDIENT_SUPP_TYPES = {"single","single_nutrient"}`.

    Empirically proven: a magnesium product with one decorative zero-dose row is
    `targeted` to the legacy classifier (it counts 2 actives) but `single_mineral`
    to the taxonomy (it counts 1) -> the single floor is denied -> a ~5-22 point
    UNDER-SCORE.

    "Existing tests do not guard the real disagreement because they hard-code the
    legacy type." These do the opposite: they set the two brains against each
    other and require the taxonomy to win.

    (`"single"` in that frozenset was a dead literal — production never emitted
    it. The set is now deleted.)
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))


def test_formulation_no_longer_reads_the_legacy_type():
    """§9 Phase 1: 'Modules consume the fact; they never rebuild it.'"""
    source = (SCRIPTS_DIR / "scoring_v4" / "modules" / "generic_formulation.py").read_text()
    assert "supp_type_of" not in source, (
        "generic_formulation still reads the legacy supplement_type"
    )
    assert "SINGLE_INGREDIENT_SUPP_TYPES" not in source, (
        "the legacy single-type set is still alive"
    )


def test_generic_formulation_no_longer_uses_single_status_for_points():
    """Focus/breadth bonuses are retired; single status cannot change A1."""
    source = (SCRIPTS_DIR / "scoring_v4" / "modules" / "generic_formulation.py").read_text()
    assert "is_single_scorable_active_of" not in source
    for retired in (
        "A6_single_ingredient",
        "premium_single_ingredient_floor",
        "standard_single_ingredient_floor",
        "enzyme_recognition",
    ):
        assert retired not in source


def test_the_fact_is_not_rebuilt_inside_the_module():
    """Consuming means reading the taxonomy's answer, not recomputing it."""
    source = (SCRIPTS_DIR / "scoring_v4" / "modules" / "generic_formulation.py").read_text()
    for rebuilt in ("scorable_active_count ==", "len(scorable) == 1 and"):
        assert rebuilt not in source, (
            f"generic_formulation appears to re-derive single-ness ({rebuilt!r}) "
            "instead of consuming the canonical fact"
        )
