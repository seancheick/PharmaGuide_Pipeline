"""Q3: sugar and sweetener charges come only from the shared owners, never from a route.

generic_formulation._dietary_sugar_penalty_detail (B1_dietary_sugar) and
_b1_harmful_additive_penalty_detail (B1_harmful_additives) charge every route. The sports-protein
and fiber adapters used to charge the same label facts again ("clean daily use" credit lost, plus a
sports artificial-sweetener penalty), so one sucralose row cost a whey powder up to three times
(DSLD 19166: 4.0 + 2.5 + 2.0), and the 2026-09-19 maltodextrin guard never reached them.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest  # noqa: E402

from scoring_v4.modules import fiber_digestive_formulation as fiber  # noqa: E402
from scoring_v4.modules import sports_formulation as sports  # noqa: E402
from test_v4_fiber_digestive_module import _fiber_product, _row as _fiber_row  # noqa: E402
from test_v4_sports_protein_formulation import _protein_product, _row as _sports_row  # noqa: E402

SUGAR_FREE = {"amount_g": 0.0, "level": "sugar_free", "contains_sugar": False,
              "has_added_sugar": False, "sugar_sources": []}
HIGH_SUGAR = {"amount_g": 12.0, "level": "high", "contains_sugar": True,
              "has_added_sugar": True, "sugar_sources": ["Cane Sugar"]}
NO_SWEETENERS = {"artificial": [], "high_glycemic": [], "sugar_alcohols": [], "safer_alternatives": []}
SUCRALOSE = [{"additive_id": "ADD_SUCRALOSE", "severity_level": "moderate", "source_section": "inactive"}]


def _whey(**label):
    rows = [_sports_row("whey_protein", 25, name="Whey Protein Isolate", matched_form="whey protein isolate")]
    return sports.score_formulation(_protein_product(rows, name="Whey Protein Isolate", **label))


def _psyllium(**label):
    return fiber.score_formulation(_fiber_product([_fiber_row("psyllium_husk", 5.0, name="Psyllium Husk")], **label))


LABELS = {
    "clean": dict(sugar=SUGAR_FREE, sweeteners=NO_SWEETENERS),
    "sucralose": dict(sugar=SUGAR_FREE, sweeteners=dict(NO_SWEETENERS, artificial=["Sucralose"]), additives=SUCRALOSE),
    "high_sugar": dict(sugar=HIGH_SUGAR, sweeteners=NO_SWEETENERS),
    # Sugar owner: no sugar. Maltodextrin is only classified high-glycemic.
    "maltodextrin_carrier": dict(sugar=SUGAR_FREE, sweeteners=dict(NO_SWEETENERS, high_glycemic=["Maltodextrin"])),
}
ROUTE_PENALTIES = {"B1_dietary_sugar", "B1_harmful_additives", "B0_moderate_watchlist"}


@pytest.mark.parametrize("score", [_whey, _psyllium], ids=["sports", "fiber"])
@pytest.mark.parametrize("label", sorted(LABELS))
def test_route_loses_exactly_the_shared_owner_charge(score, label):
    clean, payload = score(**LABELS["clean"]), score(**LABELS[label])
    shared = sum(abs(v) for k, v in payload["penalties"].items() if k in ROUTE_PENALTIES)
    assert payload["components"] == clean["components"]
    assert payload["score"] == pytest.approx(max(0.0, clean["score"] - shared))


@pytest.mark.parametrize("score", [_whey, _psyllium], ids=["sports", "fiber"])
def test_sugar_free_maltodextrin_carrier_costs_nothing(score):
    assert score(**LABELS["maltodextrin_carrier"])["score"] == score(**LABELS["clean"])["score"]


def test_no_route_owned_sweetener_or_sugar_charge_remains():
    for payload in (_whey(**LABELS["sucralose"]), _psyllium(**LABELS["sucralose"])):
        assert set(payload["penalties"]) <= ROUTE_PENALTIES | {
            "sports_opaque_protein_blend", "sports_amino_spiking_risk", "sports_collagen_not_complete_protein",
            "fiber_cleanse_detox_penalty", "fiber_stimulant_laxative_penalty"}
        assert not any("clean_daily_use" in key for key in payload["components"])
