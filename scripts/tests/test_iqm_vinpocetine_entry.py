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
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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


def test_absorption_does_not_invent_a_pooled_interval(iqm):
    form = iqm['vinpocetine']['forms']['vinpocetine (unspecified)']
    absorption = form['absorption_structured']
    assert absorption['value'] == 0.067
    assert absorption.get('range_low') is None
    assert absorption.get('range_high') is None
    assert '2624613' in absorption['notes']
    assert '56.6' in form['notes'], 'retain the conflicting older result'


def test_anticoagulant_sources_are_not_misrepresented_as_regulatory():
    from api_audit.verify_interactions import derive_evidence_level
    doc = _load('curated_interactions/curated_interactions_v1.json')
    entry = next(r for r in doc['interactions'] if r['id'] == 'DSI_ANTICOAG_VINPOCETINE')
    assert entry['severity'] == 'Moderate', 'retain the precaution during clinical review'
    assert entry['evidence_basis'] == 'preclinical'
    assert derive_evidence_level(entry['evidence_basis'], entry['clinical_confidence'], entry['source_pmids']) == 'theoretical'
    assert '2272713' in entry['source_pmids']
    assert 'https://pubmed.ncbi.nlm.nih.gov/2272713/' in entry['source_urls']
    assert 'in vitro' in entry['mechanism']
    assert 'unlikely' in entry['mechanism']
    assert entry['verification']['wording_review_status'] == 'complete'
    assert 'project owner' in entry['verification']['approval_provenance']
    assert 'clinician review' not in entry['verification']['wording_review_method']
    assert entry['management'].startswith('Avoid starting vinpocetine')
    assert 'additional monitoring' in entry['management']


def test_single_active_canary_is_restored_and_policy_text_is_current():
    canaries = _load('canary_products.json')
    selected = next(c for c in canaries['canaries'] if c['dsld_id'] == '294063')
    assert selected['subclass'] == 'single_active_caution_scored'
    assert selected['expected_safety_verdict'] == 'CAUTION'
    assert selected['expected_quality_score_status'] == 'scored'
    assert 'FDA enforcement action effectively extinguished' not in json.dumps(canaries)
    doc = _load('interaction_orphan_allowlist.json')
    item = next(r for r in doc['allowlist'] if r['canonical_id'] == 'vinpocetine')
    assert 'Blocked/banned' not in item['reason']


def test_real_single_active_label_reaches_the_scored_artifact():
    from pathlib import Path
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from scoring_v4.scored_artifact import build_scored_artifact
    raw = json.loads((Path(__file__).parent / 'fixtures/vinpocetine_294063_raw.json').read_text())
    cleaned = EnhancedDSLDNormalizer().normalize_product(raw)
    enriched, _ = SupplementEnricherV3().enrich_product(cleaned)
    artifact = build_scored_artifact(enriched)
    assert artifact['quality_score_status'] == 'scored'
    assert isinstance(artifact['quality_score_v4_100'], (int, float))
    assert artifact['safety_verdict'] == 'CAUTION'
    assert artifact['verdict'] == 'CAUTION'
    assert artifact['blocking_reason'] is None
    dose = artifact['quality_pillars_v4']['dose']
    assert 'benchmark is unavailable' in dose['reason']
    assert 'studied range' not in dose['reason']


@pytest.mark.parametrize('name', ['Vincamine', 'Vinca minor', 'Voacanga africana', 'Periwinkle'])
def test_related_names_do_not_become_vinpocetine(name):
    product = {
        'dsld_id': 99999, 'product_name': name,
        'activeIngredients': [{'ingredientName': name, 'standardName': name,
                               'quantity': '20', 'unit': 'mg'}],
        'inactiveIngredients': [],
    }
    enriched, _ = SupplementEnricherV3().enrich_product(product)
    rows = enriched['ingredient_quality_data'].get('ingredients_scorable', [])
    assert all(row.get('canonical_id') != 'vinpocetine' for row in rows)
