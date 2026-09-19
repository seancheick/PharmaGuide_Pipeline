"""Regression and contract tests for Phase 1a blend header wiring fix.

generic_helpers.is_scorable() excludes proprietary blends and parent totals.
generic_evidence previously bypassed this via get_active_ingredients() at lines 415 and 1024.
This test suite pins:
1. Candidate rows with only blend headers/parent totals yield 'no_assessable_actives'.
2. Proprietary blend containing child actives (e.g. ashwagandha + rhodiola) ignores the
   parent header row and assesses the child actives.
3. Blend headers never compete for mass dominance in _competing_active_rows / _active_mass_index.
"""

from __future__ import annotations

import pytest

from scoring_v4.modules.generic_evidence import (
    _active_mass_index,
    _competing_active_rows,
    score_evidence,
)
from tests.test_v4_generic_evidence_p133 import _ingredient, _match, _product


def test_blend_header_alone_yields_no_assessable_actives():
    """A product containing only a proprietary blend header (e.g. BLEND_GENERAL)
    has no assessable active ingredients and must return 'no_assessable_actives'
    rather than 'clinical_review_not_covered'."""
    blend_header = {
        "name": "Proprietary Blend",
        "canonical_id": "blend_general",
        "is_proprietary_blend": True,
        "quantity": 1000.0,
        "unit": "mg",
        "mapped": True,
    }
    product = _product(ingredients=[blend_header], matches=[])
    result = score_evidence(product)
    assert result["metadata"]["evidence_result_state"] == "no_assessable_actives"


def test_parent_total_alone_yields_no_assessable_actives():
    """A product containing only a parent total row has no assessable actives."""
    parent_total = {
        "name": "Total Fatty Acids",
        "canonical_id": "fatty_acids",
        "is_parent_total": True,
        "quantity": 1000.0,
        "unit": "mg",
        "mapped": True,
    }
    product = _product(ingredients=[parent_total], matches=[])
    result = score_evidence(product)
    assert result["metadata"]["evidence_result_state"] == "no_assessable_actives"


def test_proprietary_blend_with_children_ignores_header_and_assesses_children():
    """A 'Proprietary Blend 1000 mg' containing ashwagandha + rhodiola must ignore
    the parent row and assess the children.

    When neither child has clinical matches, state is 'clinical_review_not_covered'
    (assessing the identifiable child actives, NOT returning no_assessable_actives)."""
    blend_header = {
        "name": "Proprietary Blend",
        "canonical_id": "blend_general",
        "cleaner_row_role": "blend_header_total",
        "is_proprietary_blend": True,
        "is_parent_total": True,
        "quantity": 1000.0,
        "unit": "mg",
        "mapped": True,
    }
    ashwagandha = {
        "name": "Ashwagandha Extract",
        "canonical_id": "ashwagandha",
        "cleaner_row_role": "active_scorable",
        "is_proprietary_blend": False,
        "quantity": None,
        "unit": None,
        "mapped": True,
    }
    rhodiola = {
        "name": "Rhodiola Extract",
        "canonical_id": "rhodiola",
        "cleaner_row_role": "active_scorable",
        "is_proprietary_blend": False,
        "quantity": None,
        "unit": None,
        "mapped": True,
    }
    product = _product(ingredients=[blend_header, ashwagandha, rhodiola], matches=[])
    result = score_evidence(product)
    assert result["metadata"]["evidence_result_state"] == "clinical_review_not_covered"


def test_proprietary_blend_with_child_evidence_earns_credit():
    """When a child active inside a proprietary blend has matching clinical evidence,
    the child's evidence is credited and state is 'evaluated_applicable'."""
    blend_header = {
        "name": "Proprietary Blend",
        "canonical_id": "blend_general",
        "cleaner_row_role": "blend_header_total",
        "is_proprietary_blend": True,
        "is_parent_total": True,
        "quantity": 1000.0,
        "unit": "mg",
        "mapped": True,
    }
    ashwagandha = {
        "name": "Ashwagandha Extract",
        "canonical_id": "ashwagandha",
        "cleaner_row_role": "active_scorable",
        "is_proprietary_blend": False,
        "quantity": None,
        "unit": None,
        "mapped": True,
    }
    match = _match(
        id="INGR_ASHWAGANDHA_TEST",
        ingredient="Ashwagandha Extract",
        standard_name="Ashwagandha Extract",
        canonical_id="ashwagandha",
        study_type="systematic_review_meta",
        evidence_level="ingredient-human",
        effect_direction="positive_strong",
        total_enrollment=500,
    )
    product = _product(ingredients=[blend_header, ashwagandha], matches=[match])
    result = score_evidence(product)
    assert result["score"] > 0
    assert result["metadata"]["evidence_result_state"] == "evaluated_applicable"


def test_blend_headers_excluded_from_competing_active_rows():
    """_competing_active_rows must exclude blend headers and parent totals so they
    never compete for mass dominance."""
    blend_header = {
        "name": "Proprietary Blend",
        "canonical_id": "blend_general",
        "cleaner_row_role": "blend_header_total",
        "is_proprietary_blend": True,
        "quantity": 1000.0,
        "unit": "mg",
        "mapped": True,
    }
    active_row = {
        "name": "Vitamin C",
        "canonical_id": "vitamin_c",
        "quantity": 500.0,
        "unit": "mg",
        "mapped": True,
    }
    product = _product(ingredients=[blend_header, active_row], matches=[])
    competing = _competing_active_rows(product)
    competing_names = [r.get("name") for r in competing]
    assert "Proprietary Blend" not in competing_names
    assert "Vitamin C" in competing_names


def test_blend_header_does_not_inflate_max_mass():
    """A 1000 mg blend header must not set max_mass in _active_mass_index."""
    blend_header = {
        "name": "Proprietary Blend",
        "canonical_id": "blend_general",
        "cleaner_row_role": "blend_header_total",
        "is_proprietary_blend": True,
        "quantity": 1000.0,
        "unit": "mg",
        "mapped": True,
    }
    active_row = {
        "name": "Vitamin C",
        "canonical_id": "vitamin_c",
        "quantity": 500.0,
        "unit": "mg",
        "mapped": True,
    }
    product = _product(ingredients=[blend_header, active_row], matches=[])
    _, max_mass = _active_mass_index(product)
    assert max_mass == 500.0


def test_proprietary_blend_ashwagandha_rhodiola_canary():
    """Canary: Proprietary Blend 1000 mg with Ashwagandha and Rhodiola (no child doses).

    Pins:
    - Blend parent is not an Evidence identity
    - Blend parent is not a mass competitor
    - Ashwagandha / Rhodiola remain Evidence identities
    - State is NOT 'no_assessable_actives'
    - When an evidence match requires a dose, dose applicability remains unresolved
      ('applicability_unestablished') rather than inventing an equal-share or child dose
    - No child dose is invented in dose_map
    """
    from scoring_v4.modules.generic_evidence import _assessable_active_ingredients

    blend_header = {
        "name": "Proprietary Blend",
        "canonical_id": "blend_general",
        "cleaner_row_role": "blend_header_total",
        "is_proprietary_blend": True,
        "is_parent_total": True,
        "quantity": 1000.0,
        "unit": "mg",
        "mapped": True,
    }
    ashwagandha = {
        "name": "Ashwagandha Extract",
        "canonical_id": "ashwagandha",
        "cleaner_row_role": "active_scorable",
        "is_proprietary_blend": False,
        "quantity": None,
        "unit": None,
        "mapped": True,
    }
    rhodiola = {
        "name": "Rhodiola Extract",
        "canonical_id": "rhodiola",
        "cleaner_row_role": "active_scorable",
        "is_proprietary_blend": False,
        "quantity": None,
        "unit": None,
        "mapped": True,
    }

    # 1. Check assessable active identities: parent is excluded, children are retained
    product_bare = _product(ingredients=[blend_header, ashwagandha, rhodiola], matches=[])
    assessable = _assessable_active_ingredients(product_bare)
    assessable_cids = {r.get("canonical_id") for r in assessable}
    assert "blend_general" not in assessable_cids
    assert "ashwagandha" in assessable_cids
    assert "rhodiola" in assessable_cids

    # 2. Check mass competition: parent is excluded, children have no mass
    competing = _competing_active_rows(product_bare)
    competing_names = {r.get("name") for r in competing}
    assert "Proprietary Blend" not in competing_names
    _, max_mass = _active_mass_index(product_bare)
    assert max_mass == 0.0  # no dose invented

    # 3. State without matches is clinical_review_not_covered (NOT no_assessable_actives)
    res_no_match = score_evidence(product_bare)
    assert res_no_match["metadata"]["evidence_result_state"] == "clinical_review_not_covered"

    # 4. When match requires dose, dose applicability remains unresolved
    match_with_dose_req = _match(
        id="INGR_ASHWAGANDHA_DOSE_REQ",
        ingredient="Ashwagandha Extract",
        standard_name="Ashwagandha Extract",
        canonical_id="ashwagandha",
        applicability={
            "scope": "ingredient",
            "dose_unit": "mg",
            "minimum_daily_dose": 300.0,
        },
    )
    product_with_match = _product(
        ingredients=[blend_header, ashwagandha, rhodiola],
        matches=[match_with_dose_req],
    )
    res_match = score_evidence(product_with_match)
    assert res_match["score"] == 0.0
    assert res_match["metadata"]["evidence_result_state"] == "applicability_unestablished"

