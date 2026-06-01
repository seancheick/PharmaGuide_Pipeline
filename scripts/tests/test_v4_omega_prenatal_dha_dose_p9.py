"""Phase 9.5 — indication-aware omega dose for prenatal DHA.

The general EPA+DHA bands target cardiovascular intakes (~1000-2000 mg/day),
under-crediting a prenatal DHA-dominant product. The prenatal DHA target is
~200 mg DHA/day (EFSA NDA Panel 2014; ACOG). A DHA-dominant prenatal product is
scored against the DHA target (take the higher of it and the general band), so a
650 mg-DHA prenatal product is credited for being generous for its indication.
"""
from __future__ import annotations

import sys
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


def test_prenatal_but_epa_dominant_not_dha_indication():
    # prenatal name but EPA-dominant (not a DHA product) -> general band, no
    # prenatal-DHA indication (the DHA-target only applies to DHA-dominant).
    out = score_dose(_omega("Prenatal Omega EPA Forte", epa=900, dha=100))
    assert out["metadata"]["prenatal_dha_indication"] is None
