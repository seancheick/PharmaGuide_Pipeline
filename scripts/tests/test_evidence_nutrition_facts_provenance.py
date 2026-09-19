"""Regression and contract tests for Phase 1b: Provenance-driven Nutrition Facts rule.

Guardrail:
A row classified by the canonical label/row-role owner as a Nutrition Facts nutrient
declaration cannot independently serve as an efficacy identity. The rule is based on
provenance + semantic role, NOT on hardcoded nutrient name string matching.

Required test cases pinned:
1. Nutrition Facts 'Dietary Fiber 5 g' only -> declaration excluded as Evidence identity.
2. 'Dietary Fiber 5 g' + Psyllium Husk -> psyllium retained as Evidence identity.
3. 'Dietary Fiber 5 g' + Inulin -> inulin retained as Evidence identity.
4. Nutrition Facts 'Protein 25 g' + Whey Protein Isolate -> whey retained, protein declaration excluded.
5. Total Carbohydrate / Calories only -> no Evidence identities created.
6. Same words appearing as a genuine Supplement Facts/ingredient row -> do NOT exclude just because of name.
7. Multiple source ingredients -> assess actual disclosed sources; no invented allocation or inferred dose split.
8. Mass competition and score isolation -> Nutrition Facts declarations never compete for primary mass.
"""

from __future__ import annotations

import pytest

from scoring_v4.modules.generic_evidence import (
    _active_mass_index,
    _assessable_active_ingredients,
    _competing_active_rows,
    _is_nutrition_fact_declaration,
    score_evidence,
)
from tests.test_v4_generic_evidence_p133 import _match, _product


def _nutrition_fact_row(
    name: str,
    canonical_id: str | None = None,
    quantity: float | None = None,
    unit: str | None = None,
    **overrides,
) -> dict:
    """Helper creating a row with canonical Nutrition Facts declaration provenance."""
    row = {
        "name": name,
        "canonical_id": canonical_id,
        "standard_name": name,
        "quantity": quantity,
        "unit": unit,
        "cleaner_row_role": "active_scorable",
        "skip_reason": "excluded_nutrition_fact",
        "score_exclusion_reason": "excluded_nutrition_fact",
        "identity_decision_reason": "excluded_nutrition_fact",
        "role_classification": "inactive_non_scorable",
        "source_section": "active",
        "mapped": False,
        "scoreable_identity": False,
    }
    row.update(overrides)
    return row


def _supplement_active_row(
    name: str,
    canonical_id: str,
    quantity: float | None = None,
    unit: str | None = None,
    **overrides,
) -> dict:
    """Helper creating a genuine Supplement Facts active ingredient row."""
    row = {
        "name": name,
        "canonical_id": canonical_id,
        "standard_name": name,
        "quantity": quantity,
        "unit": unit,
        "cleaner_row_role": "active_scorable",
        "skip_reason": None,
        "score_exclusion_reason": None,
        "role_classification": "active_scorable",
        "source_section": "active",
        "mapped": True,
        "scoreable_identity": True,
    }
    row.update(overrides)
    return row


# 1. Nutrition Facts 'Dietary Fiber 5 g' only
def test_nutrition_facts_dietary_fiber_only_excluded_as_evidence_identity():
    """A product containing only a Nutrition Facts 'Dietary Fiber 5 g' row
    must exclude the declaration as an Evidence identity.

    With no other genuine active remaining, state is 'no_assessable_actives'
    rather than creating fake 'clinical_review_not_covered' backlog."""
    fiber_row = _nutrition_fact_row("Dietary Fiber", canonical_id="fiber", quantity=5.0, unit="g")
    product = _product(ingredients=[fiber_row], matches=[])

    assert _is_nutrition_fact_declaration(fiber_row) is True
    assert _assessable_active_ingredients(product) == []

    result = score_evidence(product)
    assert result["metadata"]["evidence_result_state"] == "no_assessable_actives"
    assert result["score"] == 0.0


# 2. 'Dietary Fiber 5 g' + Psyllium Husk
def test_dietary_fiber_plus_psyllium_husk_retains_psyllium():
    """Dietary Fiber 5 g + Psyllium Husk -> psyllium is retained as the Evidence identity
    while the Nutrition Facts declaration is excluded."""
    fiber_row = _nutrition_fact_row("Dietary Fiber", canonical_id="fiber", quantity=5.0, unit="g")
    psyllium_row = _supplement_active_row(
        "Psyllium Husk",
        canonical_id="psyllium",
        quantity=5.0,
        unit="g",
    )
    product = _product(ingredients=[fiber_row, psyllium_row], matches=[])

    assessable = _assessable_active_ingredients(product)
    assert len(assessable) == 1
    assert assessable[0]["canonical_id"] == "psyllium"


# 3. 'Dietary Fiber 5 g' + Inulin
def test_dietary_fiber_plus_inulin_retains_inulin():
    """Dietary Fiber 5 g + Inulin -> inulin is retained as the Evidence identity
    while the Nutrition Facts declaration is excluded."""
    fiber_row = _nutrition_fact_row("Dietary Fiber", canonical_id="fiber", quantity=5.0, unit="g")
    inulin_row = {
        "name": "Inulin",
        "canonical_id": "inulin",
        "cleaner_row_role": "nested_display_only",
        "skip_reason": "nested_under_non_therapeutic_parent",
        "score_exclusion_reason": "nested_display_only",
        "quantity": None,
        "unit": None,
        "mapped": True,
    }
    product = _product(ingredients=[fiber_row, inulin_row], matches=[])

    assessable = _assessable_active_ingredients(product)
    assert len(assessable) == 1
    assert assessable[0]["canonical_id"] == "inulin"


# 4. Nutrition Facts 'Protein 25 g' + Whey Protein Isolate
def test_nutrition_facts_protein_plus_whey_retains_whey_excludes_protein():
    """Nutrition Facts 'Protein 25 g' + Whey Protein Isolate -> whey retained,
    protein declaration excluded."""
    protein_row = _nutrition_fact_row("Protein", canonical_id="protein", quantity=25.0, unit="g")
    whey_row = _supplement_active_row(
        "Whey Protein Isolate",
        canonical_id="whey_protein",
        quantity=25.0,
        unit="g",
    )
    product = _product(ingredients=[protein_row, whey_row], matches=[])

    assert _is_nutrition_fact_declaration(protein_row) is True
    assert _is_nutrition_fact_declaration(whey_row) is False

    assessable = _assessable_active_ingredients(product)
    assert len(assessable) == 1
    assert assessable[0]["canonical_id"] == "whey_protein"


# 5. Total Carbohydrate / Calories only
def test_total_carbohydrate_and_calories_only_creates_no_evidence_identities():
    """Total Carbohydrate / Calories only -> no Evidence identities created.
    State resolves to 'no_assessable_actives'."""
    calories_row = _nutrition_fact_row("Calories", canonical_id=None, quantity=40.0, unit="kcal")
    carbs_row = _nutrition_fact_row("Total Carbohydrate", canonical_id=None, quantity=10.0, unit="g")
    product = _product(ingredients=[calories_row, carbs_row], matches=[])

    assert _assessable_active_ingredients(product) == []
    result = score_evidence(product)
    assert result["metadata"]["evidence_result_state"] == "no_assessable_actives"
    assert result["score"] == 0.0


# 6. Same words appearing as a genuine Supplement Facts/ingredient row
def test_same_words_as_genuine_supplement_row_not_excluded_by_name():
    """CRITICAL GUARDRAIL: Do not exclude just because of nutrient words ('Dietary Fiber', 'Protein').
    If a row appears as a genuine Supplement Facts active without Nutrition Facts declaration
    provenance, it must NOT be excluded."""
    # A genuine Supplement Facts row labeled 'Dietary Fiber' with active provenance
    genuine_fiber = {
        "name": "Dietary Fiber",
        "canonical_id": "fiber",
        "cleaner_row_role": "active_scorable",
        "source_section": "active",
        "skip_reason": None,
        "score_exclusion_reason": None,
        "quantity": 5.0,
        "unit": "g",
        "mapped": True,
    }
    # It is NOT a Nutrition Facts declaration
    assert _is_nutrition_fact_declaration(genuine_fiber) is False

    product = _product(ingredients=[genuine_fiber], matches=[])
    assessable = _assessable_active_ingredients(product)
    assert len(assessable) == 1
    assert assessable[0]["name"] == "Dietary Fiber"


# 7. Multiple source ingredients
def test_multiple_source_ingredients_assesses_disclosed_sources_no_invented_allocation():
    """Multiple source ingredients under/alongside a nutrition declaration:
    Dietary Fiber 10 g + Psyllium Husk + Inulin.
    Both disclosed source ingredients are retained in assessable actives.
    No inferred dose split; no invented allocation."""
    fiber_decl = _nutrition_fact_row("Dietary Fiber", canonical_id="fiber", quantity=10.0, unit="g")
    psyllium = {
        "name": "Psyllium Husk",
        "canonical_id": "psyllium",
        "cleaner_row_role": "nested_display_only",
        "skip_reason": "nested_under_non_therapeutic_parent",
        "score_exclusion_reason": "nested_display_only",
        "quantity": None,
        "unit": None,
        "mapped": True,
    }
    inulin = {
        "name": "Inulin",
        "canonical_id": "inulin",
        "cleaner_row_role": "nested_display_only",
        "skip_reason": "nested_under_non_therapeutic_parent",
        "score_exclusion_reason": "nested_display_only",
        "quantity": None,
        "unit": None,
        "mapped": True,
    }
    product = _product(ingredients=[fiber_decl, psyllium, inulin], matches=[])

    assessable = _assessable_active_ingredients(product)
    assert len(assessable) == 2
    canonical_ids = {r["canonical_id"] for r in assessable}
    assert canonical_ids == {"psyllium", "inulin"}
    # Verify neither child had a fake dose invented
    for r in assessable:
        assert r["quantity"] is None


# 8. Nutrition Facts declarations never compete for primary mass dominance
def test_nutrition_facts_declaration_never_competes_for_primary_mass():
    """Nutrition Facts declarations (e.g. Protein 25 g) must never compete in
    _competing_active_rows or set max_mass in _active_mass_index."""
    protein_decl = _nutrition_fact_row("Protein", canonical_id="protein", quantity=25.0, unit="g")
    creatine = _supplement_active_row("Creatine Monohydrate", canonical_id="creatine_monohydrate", quantity=5.0, unit="g")

    product = _product(ingredients=[protein_decl, creatine], matches=[])
    competing = _competing_active_rows(product, [protein_decl, creatine])

    # Only creatine competes; protein declaration does not compete
    assert len(competing) == 1
    assert competing[0]["canonical_id"] == "creatine_monohydrate"

    # In active_mass_index, max_mass is creatine's 5000 mg, not protein's 25000 mg
    index, max_mass = _active_mass_index(product)
    assert max_mass == 5000.0
