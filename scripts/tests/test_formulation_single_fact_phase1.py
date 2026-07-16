"""Phase 1 — the formulation scoring split consumes the canonical single fact.

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

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

from scoring_v4.modules.generic_helpers import is_single_scorable_active_of  # noqa: E402


def _product(*, taxonomy_single, legacy_type):
    """A product whose two brains disagree on single-ness."""
    return {
        "dsld_id": 920001,
        "product_name": "Test Magnesium Glycinate",
        "supplement_type": {"type": legacy_type},
        "supplement_taxonomy": {
            "primary_type": "single_mineral",
            "is_single_scorable_active": taxonomy_single,
            "scorable_active_count": 1 if taxonomy_single else 2,
        },
    }


def test_taxonomy_fact_wins_when_the_legacy_type_disagrees():
    """The proven case: legacy says `targeted` (counted a decorative row), the
    taxonomy says single. The taxonomy is right and must decide."""
    product = _product(taxonomy_single=True, legacy_type="targeted")
    assert is_single_scorable_active_of(product) is True, (
        "the legacy supplement_type still decides single-ness — this is the "
        "~5-22 point under-score in §3"
    )


def test_legacy_single_nutrient_cannot_override_the_taxonomy():
    """The reverse: legacy claims single, the taxonomy proves otherwise (e.g. a
    BCAA blend). The fact must not be talked into a bonus."""
    product = _product(taxonomy_single=False, legacy_type="single_nutrient")
    assert is_single_scorable_active_of(product) is False


def test_absent_fact_is_not_single():
    """Pre-0d blobs have no fact. Refusing the floor under-credits rather than
    over-credits — the safe direction — and those blobs are already blocked from
    release by the SoT contract-version gate."""
    assert is_single_scorable_active_of({"supplement_type": {"type": "single_nutrient"}}) is False
    assert is_single_scorable_active_of({}) is False
    assert is_single_scorable_active_of(None) is False


def test_formulation_no_longer_reads_the_legacy_type():
    """§9 Phase 1: 'Modules consume the fact; they never rebuild it.'"""
    source = (SCRIPTS_DIR / "scoring_v4" / "modules" / "generic_formulation.py").read_text()
    assert "supp_type_of" not in source, (
        "generic_formulation still reads the legacy supplement_type"
    )
    assert "SINGLE_INGREDIENT_SUPP_TYPES" not in source, (
        "the legacy single-type set is still alive"
    )


def test_all_four_gates_use_the_fact():
    """A6 focus bonus, premium-single floor, standard-single floor, enzyme bonus."""
    source = (SCRIPTS_DIR / "scoring_v4" / "modules" / "generic_formulation.py").read_text()
    assert source.count("is_single_scorable_active_of(product)") == 4


def test_the_fact_is_not_rebuilt_inside_the_module():
    """Consuming means reading the taxonomy's answer, not recomputing it."""
    source = (SCRIPTS_DIR / "scoring_v4" / "modules" / "generic_formulation.py").read_text()
    for rebuilt in ("scorable_active_count ==", "len(scorable) == 1 and"):
        assert rebuilt not in source, (
            f"generic_formulation appears to re-derive single-ness ({rebuilt!r}) "
            "instead of consuming the canonical fact"
        )
