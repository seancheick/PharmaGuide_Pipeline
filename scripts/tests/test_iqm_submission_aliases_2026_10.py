"""Printed submission rows that blocked scoring for want of a form alias.

C4 Sport (submission S22) prints "Folate (as 6S-5-Methyltetrahydrofolate calcium
salt)" and "Creatine Nitrate (as NO3-T®)"; Woke AF Miami (S23) prints
"Citrulline Malate 2:1". Each names an existing IQM form (levomefolate calcium,
PubChem CID 135564391; creatine nitrate, CID 25231507; citrulline malate,
CID 162762), but the printed spelling matched no alias, so the completeness gate
kept both products unscored.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


@pytest.mark.parametrize(
    "row,canonical,form",
    [
        ({"name": "Folate", "quantity": 100, "unit": "mcg DFE",
          "forms": [{"name": "6S-5-Methyltetrahydrofolate calcium salt"}]},
         "vitamin_b9_folate", "metafolin"),
        ({"name": "Creatine Nitrate", "quantity": 1, "unit": "g",
          "forms": [{"name": "NO3-T®"}]},
         "creatine_monohydrate", "creatine nitrate"),
        ({"name": "Citrulline Malate 2:1", "quantity": 6000, "unit": "mg", "forms": []},
         "l_citrulline", "l-citrulline malate"),
    ],
)
def test_printed_submission_forms_resolve(enricher, row, canonical, form):
    product = {"activeIngredients": [dict(row)], "inactiveIngredients": []}
    scorable = enricher._collect_ingredient_quality_data(product).get("ingredients_scorable") or []
    assert scorable, row["name"]
    got = scorable[0]
    assert got.get("canonical_id") == canonical
    assert got.get("matched_form") == form
