"""Regression locks for IQM v4 defensibility-audit mechanical fixes."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


IQM_PATH = Path(__file__).parent.parent / "data" / "ingredient_quality_map.json"


@pytest.fixture(scope="module")
def iqm() -> dict:
    return json.loads(IQM_PATH.read_text())


def test_bcaa_211_does_not_hijack_generic_amino_acid_labels(iqm: dict) -> None:
    aliases = {
        str(a).strip().lower()
        for a in iqm["branched_chain_amino_acids"]["forms"]["bcaa 2:1:1"]["aliases"]
    }
    forbidden = {
        "amino acids",
        "essential amino acids",
        "amino acids supplement",
        "essential amino acids supplement",
    }
    assert aliases.isdisjoint(forbidden), (
        "Generic amino-acid/EAA labels must not resolve to premium BCAA 2:1:1."
    )


def test_generic_bcaa_standard_does_not_receive_natural_bonus(iqm: dict) -> None:
    form = iqm["branched_chain_amino_acids"]["forms"]["branched chain amino acids (standard)"]
    assert form["natural"] is False
    assert form["score"] == form["bio_score"]


@pytest.mark.parametrize(
    "parent,unspecified,specific_forms",
    [
        ("dha", "dha (unspecified)", ["DHA fish oil ethyl ester"]),
        ("epa", "epa (unspecified)", ["EPA fish oil ethyl ester"]),
        ("fish_oil", "fish oil (unspecified)", ["ethyl ester"]),
        ("ceramides", "ceramides (unspecified)", ["synthetic"]),
        ("hemp_seed_oil", "hemp seed oil (unspecified)", ["refined"]),
    ],
)
def test_unspecified_form_does_not_outrank_lowest_specific_form(
    iqm: dict,
    parent: str,
    unspecified: str,
    specific_forms: list[str],
) -> None:
    forms = iqm[parent]["forms"]
    unspecified_form = forms[unspecified]
    specific_scores = [forms[name]["score"] for name in specific_forms]
    assert unspecified_form["score"] <= min(specific_scores), (
        f"{parent}::{unspecified} should not outscore a disclosed lower-quality form."
    )
    assert unspecified_form["natural"] is False
