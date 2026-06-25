"""D3: recover missing proprietary blends whose parent name lacks a blend
keyword (e.g. "Organic Alkalizing Green Juice Powder") — but ONLY when the
blend is genuinely OPAQUE (per-child amounts withheld). Disclosed aggregates
("Total Omega-3 Fatty Acids" with EPA/DHA amounts) and the `_is_non_proprietary_
aggregate` "Total X" sum-labels must NOT be recovered (they aren't opaque
proprietary blends, so B5 must not fire on them).

Opacity = total weight shown, per-child amounts withheld — the literal
proprietary-blend definition. The signal already exists: a keyword-less parent
group is a blend iff all its children land in `_children_without_amounts`.
"""
import sys
from pathlib import Path

import pytest

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


def _child(name, parent, qty):
    return {
        "name": name,
        "isNestedIngredient": True,
        "parentBlend": parent,
        "proprietaryBlend": True,
        "quantity": qty,
        "unit": "mg" if qty else "NP",
        "category": None,
    }


def _blend_names(enricher, acts):
    pd = enricher._collect_proprietary_data(
        {"activeIngredients": acts, "inactiveIngredients": []}
    )
    return {(b.get("name") or "").strip() for b in (pd.get("blends") or [])}


_GREENS = "Organic Alkalizing Green Juice Powder"  # keyword-less parent


def test_opaque_keyword_less_parent_is_recovered(enricher):
    # grasses with NO disclosed amounts under a non-keyword parent → opaque blend.
    acts = [
        _child("Wheat Grass", _GREENS, 0),
        _child("Kamut", _GREENS, 0),
        _child("Barley Grass", _GREENS, 0),
    ]
    assert _GREENS in _blend_names(enricher, acts)


def test_disclosed_keyword_less_parent_is_not_recovered(enricher):
    # SAME keyword-less parent, but children carry amounts → transparent, NOT a blend.
    acts = [
        _child("Ingredient A", _GREENS, 100),
        _child("Ingredient B", _GREENS, 50),
    ]
    assert _GREENS not in _blend_names(enricher, acts)


def test_total_aggregate_sum_label_is_not_recovered(enricher):
    # "Total X" sum-label → _is_non_proprietary_aggregate guard skips it.
    acts = [
        _child("EPA", "Total Omega-3 Fatty Acids", 500),
        _child("DHA", "Total Omega-3 Fatty Acids", 200),
    ]
    assert "Total Omega-3 Fatty Acids" not in _blend_names(enricher, acts)


def test_keyword_named_blend_still_recovered(enricher):
    # Existing behavior unchanged: a keyword-named blend is recovered regardless.
    acts = [_child("X", "Energy Blend", 0), _child("Y", "Energy Blend", 0)]
    assert "Energy Blend" in _blend_names(enricher, acts)
