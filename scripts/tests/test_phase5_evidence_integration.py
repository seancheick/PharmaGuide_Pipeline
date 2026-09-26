"""Tests for Phase 5 Controlled Production Evidence Integration.

Validates:
1. Universal Evidence Resolver terminal dispositions map deterministically to production states.
2. Legacy `score > 0 -> assessed` inference is removed: assessment state derives strictly from disposition.
3. Strict Product Completeness: a product is complete only if ALL assessable actives have terminal dispositions.
4. Upstream Row-Role Cleanup: analytical markers, excipients, and descriptors are excluded upstream.
5. Honest Residual Preservation: broad actives (polysaccharides, saponins, bile acids) remain partial.
"""

from __future__ import annotations

import pytest
from evidence_resolver import (
    EvidenceDisposition,
    resolve_evidence_for_canonical,
    resolve_product_evidence,
)
from scoring_input_contract import (
    DETERMINISTIC_NON_EFFICACY_CANONICALS,
    get_assessable_evidence_ingredients,
)
from scoring_v4.quality_score import (
    EVIDENCE_ASSESSED_STATES,
    EVIDENCE_COVERAGE_GAP_STATES,
    EVIDENCE_APPLICABILITY_STATES,
    EVIDENCE_NOT_APPLICABLE_STATES,
    evidence_display_state,
)
from scoring_v4.modules.generic_evidence import (
    score_evidence,
    _evidence_result_state,
)


def _wrap_product(rows: list[dict], name: str = "Test Product", dsld_id: str = "999999") -> dict:
    return {
        "dsld_id": dsld_id,
        "product_name": name,
        "ingredient_quality_data": {
            "ingredients": rows,
        },
    }


# ============================================================================
# 1. Removal of Legacy `score > 0 -> assessed` Inference
# ============================================================================

def test_legacy_score_inference_removed():
    """No path can turn points into 'assessed': the display decision cannot see
    the score, and the A/B-only switches that re-enabled the old inference are
    gone from every module that carried one."""
    import inspect

    import scoring_input_contract
    import scoring_v4.modules.generic_evidence as generic_evidence
    import scoring_v4.quality_score as quality_score

    assert list(inspect.signature(evidence_display_state).parameters) == ["state"]
    for module in (quality_score, generic_evidence, scoring_input_contract):
        assert not hasattr(module, "_PHASE5_ENABLED"), module.__name__
    for gap_state in EVIDENCE_COVERAGE_GAP_STATES:
        assert evidence_display_state(gap_state) == "not_yet_reviewed"


def test_undeclared_state_is_never_presented_as_assessed():
    assert evidence_display_state("some_future_state") == "not_yet_reviewed"
    assert evidence_display_state(None) == "not_yet_reviewed"


def test_resolver_failure_is_loud_not_a_silent_complete(monkeypatch):
    """A resolver exception used to be swallowed, after which points alone
    marked the product complete."""
    import evidence_resolver
    from scoring_v4.modules.generic_evidence import _evidence_result_state

    def boom(product, **kwargs):
        raise RuntimeError("resolver down")

    monkeypatch.setattr(evidence_resolver, "resolve_product_evidence", boom)
    product = _wrap_product([
        {"canonical_id": "vitamin_c", "name": "Vitamin C", "amount": 500, "unit": "mg", "cleaner_row_role": "active_scorable"},
    ])
    with pytest.raises(RuntimeError):
        _evidence_result_state(product, 10.0, set(), [])


def test_display_state_strictly_derived_from_state():
    """Every canonical state maps to its exact display state."""
    for state in EVIDENCE_ASSESSED_STATES:
        assert evidence_display_state(state) == "assessed"
    for state in EVIDENCE_APPLICABILITY_STATES:
        assert evidence_display_state(state) == "applicability_unestablished"

    # Not applicable states -> not_applicable
    for state in EVIDENCE_NOT_APPLICABLE_STATES:
        assert evidence_display_state(state) == "not_applicable"


# ============================================================================
# 2. Strict Product Completeness Contract
# ============================================================================

def test_strict_product_completeness_all_terminal():
    """All assessable ingredients terminal -> is_assessment_complete is True."""
    prod = _wrap_product([
        {"canonical_id": "vitamin_c", "name": "Vitamin C", "amount": 500, "unit": "mg", "cleaner_row_role": "active_scorable"},
        {"canonical_id": "zinc", "name": "Zinc", "amount": 15, "unit": "mg", "cleaner_row_role": "active_scorable"},
    ])
    res = resolve_product_evidence(prod)
    assert res.is_assessment_complete is True
    assert res.overall_disposition in {
        EvidenceDisposition.RESOLVED_BY_AUTHORITY.value,
        EvidenceDisposition.RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE.value,
    }


def test_strict_product_completeness_partial_if_any_unresolved():
    """One resolved active + one unresolved active -> MUST REMAIN PARTIAL."""
    prod = _wrap_product([
        {"canonical_id": "vitamin_c", "name": "Vitamin C", "amount": 500, "unit": "mg", "cleaner_row_role": "active_scorable"},
        {"canonical_id": "polysaccharides", "name": "Polysaccharides", "amount": 100, "unit": "mg", "cleaner_row_role": "active_scorable"},
    ])
    res = resolve_product_evidence(prod)
    # Even though Vitamin C is resolved, polysaccharides is identity_insufficient!
    assert res.is_assessment_complete is False
    assert res.overall_disposition == EvidenceDisposition.IDENTITY_INSUFFICIENT.value

    # Scorer result state must also reflect incomplete assessment
    ev = score_evidence(prod)
    assert ev["metadata"]["evidence_result_state"] == "identity_material_unresolved"
    display = evidence_display_state(ev["metadata"]["evidence_result_state"])
    assert display == "not_yet_reviewed"


# ============================================================================
# 3. Upstream Row-Role & Identity Cleanup
# ============================================================================

def test_deterministic_non_efficacy_identities_excluded_upstream():
    """Analytical markers and excipients are excluded from assessable evidence rows."""
    prod = _wrap_product([
        {"canonical_id": "vitamin_c", "name": "Vitamin C", "amount": 500, "unit": "mg", "cleaner_row_role": "active_scorable"},
        {"canonical_id": "NHA_ROSAVINS_MARKER", "name": "Rosavins", "amount": 3, "unit": "mg", "cleaner_row_role": "standardization_marker"},
        {"canonical_id": "NHA_MICROCRYSTALLINE_CELLULOSE", "name": "Cellulose", "cleaner_row_role": "active_scorable"},
        {"canonical_id": "PII_GELATIN_CAPSULE", "name": "Gelatin Capsule", "cleaner_row_role": "active_scorable"},
    ])
    assessable = get_assessable_evidence_ingredients(prod)
    assessable_cids = {r.get("canonical_id") for r in assessable}

    assert "vitamin_c" in assessable_cids
    assert "NHA_ROSAVINS_MARKER" not in assessable_cids
    assert "NHA_MICROCRYSTALLINE_CELLULOSE" not in assessable_cids
    assert "PII_GELATIN_CAPSULE" not in assessable_cids

    # With only Vitamin C assessable, product evidence resolves completely!
    res = resolve_product_evidence(prod)
    assert res.is_assessment_complete is True


def test_cleaner_non_efficacy_roles_excluded_upstream():
    """Cleaner roles specification_limit, source_descriptor, daily_value_no_amount excluded."""
    prod = _wrap_product([
        {"canonical_id": "iron", "name": "Iron", "cleaner_row_role": "specification_limit"},
        {"canonical_id": "fish_oil", "name": "Fish Oil Source", "cleaner_row_role": "source_descriptor"},
        {"canonical_id": "calcium", "name": "Calcium", "cleaner_row_role": "daily_value_no_amount"},
    ])
    assessable = get_assessable_evidence_ingredients(prod)
    assert len(assessable) == 0

    res = resolve_product_evidence(prod)
    assert res.assessable_ingredients_count == 0
    assert res.overall_disposition == EvidenceDisposition.NOT_EFFICACY_RELEVANT.value
    assert res.is_assessment_complete is True


# ============================================================================
# 4. Preservation of Legitimate Residual Partials
# ============================================================================

def test_broad_chemical_classes_remain_unresolved_residuals():
    """Genuinely broad chemical classes must NOT be force-fit or resolved."""
    broad_cids = ["polysaccharides", "saponins", "NHA_TOTAL_BILE_ACIDS", "NHA_CONJUGATED_BILE_ACID"]
    for cid in broad_cids:
        assert cid.lower() not in DETERMINISTIC_NON_EFFICACY_CANONICALS
        res = resolve_evidence_for_canonical(cid)
        assert res.disposition == EvidenceDisposition.IDENTITY_INSUFFICIENT.value
        assert res.points_eligible is False

        prod = _wrap_product([{"canonical_id": cid, "name": cid, "cleaner_row_role": "active_scorable"}])
        prod_res = resolve_product_evidence(prod)
        assert prod_res.is_assessment_complete is False
        assert prod_res.overall_disposition == EvidenceDisposition.IDENTITY_INSUFFICIENT.value


# ============================================================================
# 5. Production Evidence States & Zero Points Semantics
# ============================================================================

def test_no_qualifying_human_evidence_semantics():
    """No qualifying human evidence produces 0 points, assessed display state, complete."""
    prod = _wrap_product([
        {"canonical_id": "fadogia_agrestis", "name": "Fadogia Agrestis", "amount": 500, "unit": "mg", "cleaner_row_role": "active_scorable"},
    ])
    ev = score_evidence(prod)
    assert ev["score"] == 0.0
    assert ev["metadata"]["evidence_result_state"] == "no_qualifying_human_evidence"
    display = evidence_display_state(ev["metadata"]["evidence_result_state"])
    assert display == "assessed"


def test_applicability_unestablished_semantics():
    """Research present but applicability unestablished -> 0 points, applicability_unestablished display."""
    prod = _wrap_product([
        {"canonical_id": "cinnamon", "name": "Cinnamon Bark Powder", "matched_form": "bark powder", "amount": 500, "unit": "mg", "cleaner_row_role": "active_scorable"},
    ])
    prod["evidence_data"] = {
        "clinical_matches": [{
            "id": "INGR_CINNAMON_EXTRACT",
            "ingredient": "Cinnamon",
            "canonical_id": "cinnamon",
            "study_type": "systematic_review_meta",
            "evidence_level": "ingredient-human",
            "effect_direction": "positive_strong",
            "exclude_aliases": ["bark powder"],
        }]
    }
    ev = score_evidence(prod)
    assert ev["score"] == 0.0
    assert ev["metadata"]["evidence_result_state"] == "applicability_unestablished"
    display = evidence_display_state(ev["metadata"]["evidence_result_state"])
    assert display == "applicability_unestablished"


# ============================================================================
# 6. Proprietary Blend Semantic Contract: Regression Fixtures A-E
# ============================================================================

def test_fixture_a_blend_header_named_children_no_doses():
    """Fixture A: blend header + named Ashwagandha + named Rhodiola, no child doses.
    -> header excluded
    -> children retained
    -> applicable research identified
    -> dose/applicability unresolved as appropriate
    -> terminal Evidence assessment
    -> zero dose-dependent credit
    """
    blend_header = {
        "name": "Proprietary Adaptogen Blend",
        "canonical_id": "blend_adaptogen",
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
    prod = _wrap_product([blend_header, ashwagandha, rhodiola])

    # 1. Header excluded, children retained
    assessable = get_assessable_evidence_ingredients(prod)
    assessable_cids = [r.get("canonical_id") for r in assessable]
    assert "blend_adaptogen" not in assessable_cids
    assert "ashwagandha" in assessable_cids
    assert "rhodiola" in assessable_cids

    # 2. Terminal evidence assessment (is_assessment_complete is True)
    res = resolve_product_evidence(prod)
    assert res.is_assessment_complete is True
    assert res.overall_disposition == EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value

    # 3. Scorer output: zero credit, applicability_unestablished state, terminal display
    ev = score_evidence(prod)
    assert ev["score"] == 0.0
    assert ev["metadata"]["evidence_result_state"] == "applicability_unestablished"
    display = evidence_display_state(ev["metadata"]["evidence_result_state"])
    assert display == "applicability_unestablished"


def test_fixture_b_blend_with_unidentified_unnamed_components():
    """Fixture B: blend with unidentified unnamed components.
    -> genuinely partial
    """
    blend_header = {
        "name": "Proprietary Blend",
        "canonical_id": "blend_general",
        "cleaner_row_role": "blend_header_total",
        "is_proprietary_blend": True,
        "is_parent_total": True,
        "quantity": 500.0,
        "unit": "mg",
    }
    unidentified_child = {
        "name": "Proprietary Herbal Matrix",
        "canonical_id": None,
        "cleaner_row_role": "active_scorable",
        "is_proprietary_blend": False,
        "mapped": False,
    }
    prod = _wrap_product([blend_header, unidentified_child])

    res = resolve_product_evidence(prod)
    assert res.is_assessment_complete is False
    assert res.overall_disposition == EvidenceDisposition.IDENTITY_INSUFFICIENT.value

    ev = score_evidence(prod)
    assert ev["metadata"]["evidence_result_state"] in {"identity_material_unresolved", "clinical_review_not_covered"}
    display = evidence_display_state(ev["metadata"]["evidence_result_state"])
    assert display == "not_yet_reviewed"


def test_fixture_c_exact_finished_formula_with_formula_evidence(monkeypatch):
    """Fixture C: exact finished formula with formula evidence.
    -> formula owner route
    """
    blend_header = {
        "name": "Proprietary Synbiotic Blend",
        "canonical_id": "blend_synbiotic",
        "cleaner_row_role": "blend_header_total",
        "is_proprietary_blend": True,
        "is_parent_total": True,
        "quantity": 500.0,
        "unit": "mg",
    }
    prod = _wrap_product([blend_header], name="Clinically Studied Formula X", dsld_id="111222")
    prod["brand_name"] = "StudiedBrand"

    mock_formula = {
        "id": "FORMULA_STUDIED_X",
        "standard_name": "Clinically Studied Formula X",
        "ingredient": "Clinically Studied Formula X",
        "study_type": "rct_single",
        "evidence_level": "product-human",
        "effect_direction": "positive_strong",
        "total_enrollment": 150,
        "scope": "formula",
    }
    monkeypatch.setattr("studied_formulas.formula_clinical_match", lambda p: mock_formula)

    ev = score_evidence(prod)
    assert ev["score"] > 0.0
    assert ev["metadata"]["evidence_result_state"] == "evaluated_applicable"
    assert ev["metadata"]["matched_entries"] >= 1


def test_fixture_d_named_child_with_disclosed_adequate_dose():
    """Fixture D: named child with disclosed adequate dose.
    -> normal applicability/scoring route
    """
    blend_header = {
        "name": "Performance Blend",
        "canonical_id": "blend_performance",
        "cleaner_row_role": "blend_header_total",
        "is_proprietary_blend": True,
        "is_parent_total": True,
        "quantity": 1000.0,
        "unit": "mg",
    }
    ashwagandha = {
        "name": "Ashwagandha Extract",
        "canonical_id": "ashwagandha",
        "cleaner_row_role": "active_scorable",
        "is_proprietary_blend": False,
        "quantity": 600.0,
        "amount": 600.0,
        "unit": "mg",
        "mapped": True,
    }
    prod = _wrap_product([blend_header, ashwagandha])
    prod["evidence_data"] = {
        "clinical_matches": [{
            "id": "INGR_ASHWAGANDHA_STUDY",
            "ingredient": "Ashwagandha Extract",
            "canonical_id": "ashwagandha",
            "study_type": "systematic_review_meta",
            "evidence_level": "ingredient-human",
            "effect_direction": "positive_strong",
            "total_enrollment": 400,
            "applicability": {
                "scope": "ingredient",
                "dose_unit": "mg",
                "minimum_daily_dose": 300.0,
            },
        }]
    }

    res = resolve_product_evidence(prod)
    assert res.is_assessment_complete is True

    ev = score_evidence(prod)
    assert ev["score"] > 0.0
    assert ev["metadata"]["evidence_result_state"] == "evaluated_applicable"
    assert ev["metadata"]["matched_entries"] >= 1


def test_fixture_e_named_child_with_disclosed_subclinical_dose():
    """Fixture E: named child with disclosed subclinical dose.
    -> normal below-dose applicability result
    """
    blend_header = {
        "name": "Performance Blend",
        "canonical_id": "blend_performance",
        "cleaner_row_role": "blend_header_total",
        "is_proprietary_blend": True,
        "is_parent_total": True,
        "quantity": 1000.0,
        "unit": "mg",
    }
    ashwagandha = {
        "name": "Ashwagandha Extract",
        "canonical_id": "ashwagandha",
        "cleaner_row_role": "active_scorable",
        "is_proprietary_blend": False,
        "quantity": 50.0,
        "amount": 50.0,
        "unit": "mg",
        "mapped": True,
    }
    prod = _wrap_product([blend_header, ashwagandha])
    prod["evidence_data"] = {
        "clinical_matches": [{
            "id": "INGR_ASHWAGANDHA_STUDY",
            "ingredient": "Ashwagandha Extract",
            "canonical_id": "ashwagandha",
            "study_type": "systematic_review_meta",
            "evidence_level": "ingredient-human",
            "effect_direction": "positive_strong",
            "total_enrollment": 400,
            "applicability": {
                "scope": "ingredient",
                "dose_unit": "mg",
                "minimum_daily_dose": 300.0,
            },
        }]
    }

    res = resolve_product_evidence(prod)
    assert res.is_assessment_complete is True

    ev = score_evidence(prod)
    assert ev["score"] == 0.0
    assert ev["metadata"]["evidence_result_state"] == "applicability_unestablished"
    display = evidence_display_state(ev["metadata"]["evidence_result_state"])
    assert display == "applicability_unestablished"


def test_points_never_prove_the_assessment_finished():
    """Earned points on one active cannot complete a product with another active
    still non-terminal (33 catalog products read 'complete' this way)."""
    from scoring_v4.modules.generic_evidence import _evidence_result_state

    incomplete = _wrap_product([
        {"canonical_id": "vitamin_c", "name": "Vitamin C", "amount": 500, "unit": "mg", "cleaner_row_role": "active_scorable"},
        {"canonical_id": "polysaccharides", "name": "Polysaccharides", "amount": 100, "unit": "mg", "cleaner_row_role": "active_scorable"},
    ])
    state = _evidence_result_state(incomplete, 10.0, set(), [])
    assert state == "identity_material_unresolved"
    assert evidence_display_state(state) == "not_yet_reviewed"

    complete = _wrap_product([
        {"canonical_id": "vitamin_c", "name": "Vitamin C", "amount": 500, "unit": "mg", "cleaner_row_role": "active_scorable"},
        {"canonical_id": "zinc", "name": "Zinc", "amount": 15, "unit": "mg", "cleaner_row_role": "active_scorable"},
    ])
    assert _evidence_result_state(complete, 10.0, set(), []) == "evaluated_applicable"
