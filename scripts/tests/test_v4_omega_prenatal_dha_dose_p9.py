"""Indication-aware omega dose for prenatal DHA (Dose V4.1 §3.1).

A product the purpose owner (evidence_resolver.resolve_omega_evidence_standard)
classifies as prenatal is scored only against the 200 mg/day DHA reference,
proportionally then plateau; combined EPA+DHA never stands in for DHA. Ordinary
adult products use the 250 mg/day EPA+DHA reference.
"""
from __future__ import annotations

import sys
import pytest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from scoring_v4.modules.omega_dose import score_dose  # noqa: E402


def _omega(name, epa, dha):
    rows = [
        {"canonical_id": "dha", "quantity": dha, "unit": "mg"},
        {"canonical_id": "epa", "quantity": epa, "unit": "mg"},
    ]
    return {"product_name": name, "brand_name": "Test",
            "ingredient_quality_data": {"ingredients_scorable": rows, "ingredients": rows}}


def test_prenatal_dha_at_or_above_target_scores_full():
    out = score_dose(_omega("Prenatal DHA 650 mg", epa=200, dha=650))
    assert out["metadata"]["prenatal_dha_indication"] == "prenatal_dha"
    assert out["metadata"]["adequacy_reference"]["target_mg_day"] == 200.0
    assert out["components"]["epa_dha_band"] == 20.0


def test_prenatal_dha_below_target_is_proportional():
    out = score_dose(_omega("Prenatal DHA", epa=10, dha=80))
    assert out["metadata"]["prenatal_dha_indication"] == "prenatal_dha"
    assert out["components"]["epa_dha_band"] == 8.0


def test_non_prenatal_omega_unaffected_by_indication():
    out = score_dose(_omega("Triple Strength Fish Oil", epa=650, dha=450))
    assert out["metadata"]["prenatal_dha_indication"] is None
    assert out["metadata"]["adequacy_reference"]["purpose"] == "ordinary_adult"


def test_prenatal_epa_dominant_product_is_still_judged_on_its_dha():
    # EPA cannot substitute for the prenatal DHA reference: 100 mg DHA -> 10.
    out = score_dose(_omega("Prenatal Omega EPA Forte", epa=900, dha=100))
    assert out["metadata"]["prenatal_dha_indication"] == "prenatal_dha"
    assert out["components"]["epa_dha_band"] == 10.0


@pytest.mark.parametrize('name,epa,dha,expected', [
    ('Baby & Me 2 Prenatal DHA & Choline', 0, 250, 20),
    ('Prenatal SPM DHA', 900, 100, 10),
    ('Prenatal SPM DHA', 2000, 0, 11.4),
])
def test_prenatal_dha_reference_does_not_clear_evidence_population_hold(name, epa, dha, expected):
    from scoring_v4.scored_artifact import build_scored_artifact
    from evidence_resolver import resolve_omega_evidence_standard
    product = {
        'product_name': name,
        'ingredient_quality_data': {'ingredients_scorable': [
            {'name':'EPA','canonical_id':'epa','quantity':epa,'unit':'mg'},
            {'name':'DHA','canonical_id':'dha','quantity':dha,'unit':'mg'},
        ]},
    }
    held = resolve_omega_evidence_standard(product)
    assert held['applicability_reason'].startswith('held_')
    result = build_scored_artifact(product)
    assert result['quality_pillars_v4']['dose']['score'] == expected
    assert result['quality_pillars_v4']['evidence']['score'] == 0
    assert result['quality_pillars_v4']['evidence']['evidence_result_state'] == 'applicability_unestablished'


def _source_zero_prenatal_dha():
    product = _omega("Prenatal SPM DHA", epa=2000, dha=0)
    row = product["ingredient_quality_data"]["ingredients"][0]
    row.update(raw_source_path="ingredientRows[0]", score_eligible_by_cleaner=True,
               cleaner_row_role="active_scorable", raw_taxonomy={
        "quantityVariants": [{"quantity": 0, "unit": "mg", "operator": "=",
                              "quantity_parsed": True, "selected_for_analysis": True}]})
    return product


def test_source_printed_zero_prenatal_dha_is_not_a_hidden_amount():
    from scoring_v4.scored_artifact import build_scored_artifact
    product = _source_zero_prenatal_dha()
    assert score_dose(product)["score"] == 0
    assert build_scored_artifact(product)["quality_pillars_v4"]["dose"]["score"] == 0


@pytest.mark.parametrize("change", ["np", "missing_source", "ambiguous", "unparsed", "has_dose", "descriptor"])
def test_unqualified_zero_cannot_become_a_known_prenatal_dha_amount(change):
    product = _source_zero_prenatal_dha()
    row = product["ingredient_quality_data"]["ingredients"][0]
    if change == "np":
        row["unit"] = row["raw_taxonomy"]["quantityVariants"][0]["unit"] = "NP"
    elif change == "missing_source":
        row.pop("raw_source_path")
    elif change == "ambiguous":
        row["quantity_operator"] = "ambiguous"
    elif change == "unparsed":
        row["raw_taxonomy"]["quantityVariants"][0]["quantity_parsed"] = False
    elif change == "has_dose":
        row["has_dose"] = True
        row.pop("raw_source_path")
    elif change == "descriptor":
        row.update(score_eligible_by_cleaner=False, cleaner_row_role="source_descriptor")
    out = score_dose(product)
    assert out["metadata"]["adequacy_reference"]["reason"] == "prenatal_dha_amount_not_disclosed"


def test_one_printed_zero_cannot_hide_another_unresolved_dha_owner():
    product = _source_zero_prenatal_dha()
    product["ingredient_quality_data"]["ingredients"].append(
        {"name": "DHA", "canonical_id": "dha", "quantity": 0, "unit": "NP",
         "raw_source_path": "ingredientRows[1]", "score_eligible_by_cleaner": True,
         "cleaner_row_role": "active_scorable"})
    assert score_dose(product)["metadata"]["adequacy_reference"]["reason"] == "prenatal_dha_amount_not_disclosed"
