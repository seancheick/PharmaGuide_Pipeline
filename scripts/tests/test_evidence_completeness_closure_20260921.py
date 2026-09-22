"""Closure of the 33 products that read 'complete' while an active was non-terminal.

Each case is structural or an identity gap on an existing owner, never a
product-id exception:

* silica named as the source of a dosed silica row (bamboo extract) is active
  by provenance, the same authority disposition as the dosed row;
* identities the owner names *_DESCRIPTOR are descriptors, not efficacy actives;
* an undosed flavonoid-subclass label inside a dosed complex is composition;
* an assay-class total ("Alkaloids") under a dosed extract is a marker, while a
  named compound ("Yohimbine Alkaloids") keeps its own identity;
* label spellings that missed an existing IQM owner now reach it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from enhanced_normalizer import EnhancedDSLDNormalizer
from tests.test_clinical_signoff_engineering_fixes_20260919 import _make_dsld_product, _row


@pytest.fixture(scope="module")
def normalizer() -> EnhancedDSLDNormalizer:
    return EnhancedDSLDNormalizer()


def _cleaned_role(normalizer, rows, name):  # noqa: D103
    cleaned = normalizer.normalize_product(_make_dsld_product(990101, "Closure", rows))
    found = [r for r in cleaned.get("activeIngredients") or [] if r.get("name") == name]
    assert len(found) == 1, found
    return found[0].get("cleaner_row_role")


def test_active_panel_silica_source_child_resolves_like_its_dosed_parent():
    import evidence_resolver as er

    child = {
        "canonical_id": "silica", "name": "organic Bamboo extract",
        "cleaner_row_role": "nested_display_only", "source_section": "active",
    }
    resolution = er.resolve_evidence_for_row(child) if hasattr(er, "resolve_evidence_for_row") else None
    if resolution is None:
        product = {"ingredient_quality_data": {"ingredients": [
            {"canonical_id": "silica", "name": "Silica", "cleaner_row_role": "active_scorable",
             "source_section": "active", "amount": 10.5, "unit": "mg"},
            child,
        ]}}
        result = er.resolve_product_evidence(product)
        assert result.is_assessment_complete is True
    else:
        assert resolution.disposition == er.EvidenceDisposition.RESOLVED_BY_AUTHORITY.value


def test_descriptor_identities_are_not_efficacy_actives():
    from scoring_input_contract import get_assessable_evidence_ingredients

    product = {"ingredient_quality_data": {"ingredients": [
        {"canonical_id": "PII_PHOSPHOLIPID_DESCRIPTOR", "name": "essential Phospholipids",
         "cleaner_row_role": "nested_display_only", "source_section": "active"},
        {"canonical_id": "NHA_TOTAL_FLAVONOIDS_DESCRIPTOR", "name": "Total Flavonoids",
         "cleaner_row_role": "active_scorable", "source_section": "active"},
        {"canonical_id": "glutathione", "name": "Glutathione",
         "cleaner_row_role": "active_scorable", "source_section": "active"},
    ]}}
    assert [r["canonical_id"] for r in get_assessable_evidence_ingredients(product)] == ["glutathione"]


@pytest.mark.parametrize("name,quantity,unit,expected", [
    ("Flavones", 0, "NP", True),     # Alive! 242529: class label inside a dosed complex
    ("Flavonols", 0, "NP", True),
    ("Flavonones", 0, "NP", True),
    ("Hesperidin", 0, "NP", False),  # a named compound is not a class label
    ("Flavones", 12, "mg", False),   # a dosed row owns its own identity question
])
def test_undosed_flavonoid_subclass_label_is_composition(name, quantity, unit, expected):
    row = {"name": name, "category": "non-nutrient/non-botanical",
           "quantity": [{"quantity": quantity, "unit": unit}]}
    assert EnhancedDSLDNormalizer._is_chemical_decomposition_leaf(row) is expected


def test_composition_leaf_never_enters_the_evidence_universe():
    from constants import CLEANER_NON_EFFICACY_ROLES, CLEANER_NON_SCORABLE_ROLES
    from scoring_input_contract import get_assessable_evidence_ingredients

    assert CLEANER_NON_EFFICACY_ROLES <= CLEANER_NON_SCORABLE_ROLES
    assert "composition_leaf" in CLEANER_NON_EFFICACY_ROLES
    product = {"ingredient_quality_data": {"ingredients": [
        {"canonical_id": "flavones", "name": "Flavones", "cleaner_row_role": "composition_leaf",
         "source_section": "active"},
    ]}}
    assert get_assessable_evidence_ingredients(product) == []


def test_assay_class_total_is_a_marker_but_a_named_compound_is_not(normalizer):
    cats_claw = [_row("Cat's Claw Bark Extract", 10, "mg", category="botanical", ingredientGroup="Cat's Claw",
                      nestedRows=[_row("Alkaloids", 0.4, "mg", category="non-nutrient/non-botanical",
                                       ingredientGroup="Alkaloid")])]
    assert _cleaned_role(normalizer, cats_claw, "Alkaloids") == "standardization_marker"

    yohimbe = [_row("Yohimbe Bark Extract", 62.5, "mg", category="botanical", ingredientGroup="Yohimbe",
                    nestedRows=[_row("Yohimbine Alkaloids", 5, "mg", category="non-nutrient/non-botanical",
                                     ingredientGroup="Yohimbine")])]
    assert _cleaned_role(normalizer, yohimbe, "Yohimbine Alkaloids") != "standardization_marker"


@pytest.mark.parametrize("label,owner", [
    ("Omega-3 EPA & DHA", "fish_oil"),
    ("Omega-3 EPA and DHA", "fish_oil"),
    ("Citrus Bioflavonoid", "citrus_bioflavonoids"),
    ("Chicory Fiber", "inulin"),
])
def test_label_spellings_reach_their_existing_iqm_owner(label, owner):
    from enrich_supplements_v3 import SupplementEnricherV3

    enricher = SupplementEnricherV3()
    match = enricher._match_quality_map(label, label, enricher.databases["ingredient_quality_map"])
    assert (match or {}).get("canonical_id") == owner


def _reviewed_strain_with_stub():
    from test_probiotic_applicability_rubric import strain_product

    reviewed = strain_product(dose=1e10)
    stub = strain_product(dose=1e10, clinical_id="STRAIN_ACIDOPHILUS_LA14",
                          name="Lactobacillus acidophilus La-14")
    stub["activeIngredients"][0]["raw_source_path"] = "ingredientRows[1]"
    stub["probiotic_data"]["clinical_strains"][0]["source_row_ref"] = "ingredientRows[1]"
    for blend in stub["probiotic_data"]["probiotic_blends"]:
        blend["raw_source_path"] = blend["cfu_data"]["raw_source_path"] = "ingredientRows[1]"
    mixed = strain_product(dose=1e10)
    for key in ("clinical_strains", "probiotic_blends"):
        mixed["probiotic_data"][key] += stub["probiotic_data"][key]
    mixed["activeIngredients"] += stub["activeIngredients"]
    return reviewed, mixed


def test_one_strains_points_cannot_close_a_product_holding_an_unreviewed_strain():
    """185 products shipped 'complete' because a reviewed strain's points were
    checked before the unreviewed registry stub beside it (La-14 et al.)."""
    from scoring_v4.modules.probiotic_evidence import score_evidence
    from scoring_v4.quality_score import evidence_display_state

    reviewed, mixed = _reviewed_strain_with_stub()
    alone, both = score_evidence(reviewed), score_evidence(mixed)
    assert evidence_display_state(alone["metadata"]["evidence_result_state"]) != "not_yet_reviewed"
    assert both["score"] == alone["score"]  # points are untouched
    assert both["metadata"]["evidence_result_state"] == "native_research_review_incomplete"
    assert evidence_display_state(both["metadata"]["evidence_result_state"]) == "not_yet_reviewed"


def test_resolver_never_treats_an_open_strain_review_as_terminal(monkeypatch):
    import evidence_resolver
    import studied_formulas

    monkeypatch.setattr(studied_formulas, "assess_probiotic_component_disposition",
                        lambda product: {"has_probiotic_component": True,
                                         "disposition_state": "native_research_review_incomplete"})
    row = {"name": "Lactobacillus acidophilus La-14", "raw_source_text": "Lactobacillus acidophilus La-14",
           "canonical_id": "lactobacillus_acidophilus"}
    res = evidence_resolver.resolve_evidence_for_row(row, {"ingredient_quality_data": {"ingredients": [row]}})
    assert res.disposition == evidence_resolver.EvidenceDisposition.LITERATURE_RESOLUTION_REQUIRED.value
    assert res.blocking_reasons == ["probiotic_strain_review_incomplete"]
