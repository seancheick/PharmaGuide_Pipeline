#!/usr/bin/env python3
"""
IQM coverage: Vinpocetine.

Nine real catalog products (Pure Encapsulations Vinpocetine 20 mg, the Life
Extension Cognitex line, Garden of Life Oceans 3 Better Brain, Nutricost
Cognitive Complex, Pure Encapsulations Cognitive Factors) were NOT_SCORED and
excluded from the catalog. Vinpocetine was recognised only through its safety
entry (NOOTROPIC_VINPOCETINE), and a safety match is deliberately never a
scoring identity. This entry gives vinpocetine a verified scoring identity;
the CAUTION policy stays on the safety entry. Quality and risk are separate
outputs.

Identifiers verified live on 2026-09-11:
- PubChem CID 443955, C22H26N2O2; CAS 42971-09-5 among its synonyms
- FDA GSRS UNII 543512OBTC ("VINPOCETINE", chemical)
- UMLS CUI C0059752 ("vinpocetine")
- RxNorm RxCUI 24506 ("vinpocetine", TTY IN)

Absorption (PubMed): 6.7% absolute oral bioavailability in 20 elderly
volunteers, oral vs IV (PMID 2624613); 60-100% higher when taken with food
(PMID 1418055). An earlier study reported 56.6% (PMID 582791).
"""

import json
import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
logging.disable(logging.CRITICAL)

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402

_DATA = os.path.join(os.path.dirname(__file__), "..", "data")


def _load(name):
    with open(os.path.join(_DATA, name)) as handle:
        return json.load(handle)


@pytest.fixture(scope="module")
def iqm():
    return _load("ingredient_quality_map.json")


@pytest.fixture(scope="module")
def safety_entry():
    data = _load("banned_recalled_ingredients.json")
    rows = [value for key, value in data.items() if key != "_metadata"][0]
    rows = list(rows.values()) if isinstance(rows, dict) else rows
    return next(row for row in rows if row.get("id") == "NOOTROPIC_VINPOCETINE")


def test_vinpocetine_iqm_entry_exists(iqm):
    assert "vinpocetine" in iqm


def test_vinpocetine_identifiers_are_the_verified_ones(iqm):
    entry = iqm["vinpocetine"]
    assert entry["cui"] == "C0059752"
    assert entry["rxcui"] == "24506"
    assert entry["external_ids"] == {
        "unii": "543512OBTC",
        "cas": "42971-09-5",
        "pubchem_cid": 443955,
    }


def test_scoring_and_safety_entries_name_one_substance(iqm, safety_entry):
    """One chemical, one identity: the two files must not drift apart."""
    entry = iqm["vinpocetine"]
    assert entry["cui"] == safety_entry["cui"]
    assert entry["rxcui"] == safety_entry["rxcui"]
    assert entry["external_ids"]["unii"] == safety_entry["external_ids"]["unii"]


def test_vinpocetine_bio_score_reflects_poor_absorption(iqm):
    """Low, food-dependent absolute bioavailability is scored as such; a CAUTION
    substance is neither rewarded nor penalised for its risk here."""
    for form in iqm["vinpocetine"]["forms"].values():
        assert form["bio_score"] <= 9, "absorption evidence is weak"
        assert form["absorption_structured"]["quality"] in {"poor", "low"}
        assert form["natural"] is False, "semi-synthetic vincamine derivative"
        assert form["score"] == form["bio_score"]


def test_vinpocetine_aliases_cover_the_printed_label(iqm):
    aliases = {
        alias.lower()
        for form in iqm["vinpocetine"]["forms"].values()
        for alias in form["aliases"]
    }
    # Every one of the nine catalog labels prints exactly "Vinpocetine".
    assert "vinpocetine" in aliases


def test_vinpocetine_is_scored_and_keeps_its_safety_identity():
    """End to end: the row gains a scoring identity without losing the safety
    match that drives CAUTION."""
    product = {
        "dsld_id": 99999,
        "product_name": "Vinpocetine 20 mg",
        "fullName": "Vinpocetine 20 mg",
        "productName": "Vinpocetine 20 mg",
        "brandName": "TestBrand",
        "activeIngredients": [
            {
                "ingredientName": "Vinpocetine",
                "standardName": "Vinpocetine",
                "quantity": "20",
                "unit": "mg",
            }
        ],
        "inactiveIngredients": [],
    }
    enriched, _warnings = SupplementEnricherV3().enrich_product(product)
    quality = enriched["ingredient_quality_data"]
    scorable = [
        row for row in quality.get("ingredients_scorable", [])
        if row.get("canonical_id") == "vinpocetine"
    ]
    assert len(scorable) == 1, "vinpocetine must be one scorable active"
    row = scorable[0]
    assert row["canonical_source_db"] == "ingredient_quality_map"
    assert row["identity_disposition"] == "clean"
    assert not quality.get("ingredients_skipped")
    # Safety screening is a separate lane (as for DHEA and yohimbe): the
    # high-risk match that drives CAUTION must still be recorded.
    banned = enriched["contaminant_data"]["banned_substances"]["substances"]
    assert [hit["banned_id"] for hit in banned] == ["NOOTROPIC_VINPOCETINE"]
