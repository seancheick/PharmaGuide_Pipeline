"""Prenatal Dose is proportional to the additional-DHA reference contribution.

EFSA's additional100–200mgDHA reference is distinct from adult EPA+DHA intake.
PharmaGuide selects200mg for comparison; neither EPA nor a trace DHA floor can
substitute for that reference. It does not claim complete pregnancy nutrition.
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


def test_prenatal_dha_within_target_scores_high():
    # 650 mg DHA prenatal -> >=200 mg target -> within (20), not the modest
    # general-band score for ~850 mg combined EPA+DHA.
    out = score_dose(_omega("Prenatal DHA 650 mg", epa=200, dha=650))
    assert out["metadata"]["prenatal_dha_indication"] == "prenatal_dha_within_target"
    assert out["components"]["epa_dha_band"] == 20.0


def test_prenatal_dha_below_target_modest():
    out = score_dose(_omega("Prenatal DHA", epa=10, dha=80))
    assert out["metadata"]["prenatal_dha_indication"] == "prenatal_dha_below_target"


def test_non_prenatal_omega_unaffected_by_indication():
    # A general fish oil (not prenatal) is scored on the general EPA+DHA bands.
    out = score_dose(_omega("Triple Strength Fish Oil", epa=650, dha=450))
    assert out["metadata"]["prenatal_dha_indication"] is None


def test_prenatal_epa_cannot_substitute_for_dha():
    # The prenatal DHA reference applies even when EPA is the larger amount.
    out = score_dose(_omega("Prenatal Omega EPA Forte", epa=900, dha=100))
    assert out["metadata"]["prenatal_dha_indication"] == "prenatal_dha_below_target"
    assert out["score"] == 10


@pytest.mark.parametrize('name,epa,dha,expected', [
    ('Baby & Me 2 Prenatal DHA & Choline', 0, 250, 20),
    ('Prenatal SPM DHA', 900, 100, 10),
    ('Prenatal SPM DHA', 2000, 0, 0),
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
