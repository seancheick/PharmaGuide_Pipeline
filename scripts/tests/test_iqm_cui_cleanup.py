#!/usr/bin/env python3
"""Regression checks for IQM CUI cleanup and governance."""

import json
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
IQM_PATH = DATA_DIR / "ingredient_quality_map.json"
APPROVED_NULL_STATUSES = {"no_confirmed_umls_match", "no_single_umls_concept"}


def load_iqm():
    return json.loads(IQM_PATH.read_text())


def test_iqm_exact_cui_corrections_are_pinned():
    iqm = load_iqm()

    expected = {
        "vitamin_b9_folate": "C0016410",
        "hmb": "C1995592",
        "gaba": "C0016904",
        "tmg_betaine": "C0005304",
        "paba": "C0000473",
        "dmae": "C0011064",
        "dhea": "C0011185",
        "bifidobacterium_lactis": "C1001866",
        "bifidobacterium_bifidum": "C0314974",
        "docosapentaenoic_acid_dpa": "C0058624",
        "inositol_hexaphosphate": "C0031855",
        "d_beta_hydroxybutyrate_bhb": "C0106006",
        "tudca": "C0075857",
        "centrophenoxine": "C0007710",
        "birch_polypore": "C1008862",
        "chanca_piedra": "C1135822",
        "raspberry_ketones": "C0616813",
        "capsaicin": "C0006931",
        "monolaurin": "C4534743",
        "undecylenic_acid": "C0041660",
        "silica": "C0037098",
    }

    for entry_id, cui in expected.items():
        assert iqm[entry_id]["cui"] == cui


def test_iqm_silica_identifiers_align_to_silicon_dioxide():
    iqm = load_iqm()
    silica = iqm["silica"]

    assert silica["cui"] == "C0037098"
    assert silica["rxcui"] == "9771"
    assert silica["external_ids"]["unii"] == "ETJ7Z6XBU4"
    assert silica["external_ids"]["cas"] == "7631-86-9"


def test_iqm_glutathione_peroxidase_does_not_borrow_glutathione_identifiers():
    iqm = load_iqm()
    entry = iqm["glutathione_peroxidase"]

    assert entry["cui"] == "C0017822"
    assert entry["rxcui"] in (None, "")
    assert (entry.get("external_ids") or {}).get("unii") in (None, "")
    assert entry.get("gsrs") is None


def test_iqm_vitamin_k_parent_does_not_borrow_vitamin_k1_identifiers():
    iqm = load_iqm()
    entry = iqm["vitamin_k"]

    assert entry["cui"] == "C0042878"
    assert entry["rxcui"] in (None, "")
    assert (entry.get("external_ids") or {}).get("unii") in (None, "")
    assert entry.get("gsrs") is None


def test_iqm_phosphatidylinositol_does_not_borrow_plain_inositol_identifiers():
    iqm = load_iqm()
    entry = iqm["phosphatidylinositol"]

    assert entry["cui"] == "C0031621"
    assert entry["rxcui"] in (None, "")
    assert (entry.get("external_ids") or {}).get("unii") in (None, "")
    assert entry.get("gsrs") is None


def test_iqm_flower_pollen_does_not_borrow_rye_specific_identifiers_or_aliases():
    iqm = load_iqm()
    entry = iqm["flower_pollen"]
    generic_aliases = entry["forms"]["flower pollen extract"]["aliases"]

    assert entry["cui"] == "C4073752"
    assert entry["rxcui"] in (None, "")
    assert (entry.get("external_ids") or {}).get("unii") in (None, "")
    assert entry.get("gsrs") is None
    assert "rye pollen extract" not in generic_aliases
    assert "secale cereale pollen" not in generic_aliases


def test_iqm_hawthorn_does_not_borrow_vitexin_identifiers_or_aliases():
    iqm = load_iqm()
    entry = iqm["hawthorn"]
    generic_aliases = entry["forms"]["hawthorn (unspecified)"]["aliases"]

    assert entry["cui"] == "C0885252"
    assert (entry.get("external_ids") or {}).get("unii") in (None, "")
    assert entry.get("gsrs") is None
    assert "Vitexin" not in generic_aliases
    assert "Vitexins" not in generic_aliases
    assert "vitexin-2-O-rhamnoside" not in generic_aliases


def test_iqm_ganoderic_acids_do_not_borrow_reishi_identifiers():
    iqm = load_iqm()
    entry = iqm["ganoderic_acids"]

    assert entry["cui"] == "C3180310"
    assert entry["rxcui"] in (None, "")
    assert (entry.get("external_ids") or {}).get("unii") in (None, "")
    assert entry.get("gsrs") is None


def test_iqm_glucosinolates_do_not_borrow_broccoli_identifiers():
    iqm = load_iqm()
    entry = iqm["glucosinolates"]

    assert entry["cui"] == "C0017767"
    assert entry["rxcui"] in (None, "")
    assert (entry.get("external_ids") or {}).get("unii") in (None, "")
    assert entry.get("gsrs") is None


def test_iqm_isothiocyanates_do_not_borrow_broccoli_identifiers():
    iqm = load_iqm()
    entry = iqm["isothiocyanates"]

    assert entry["cui"] == "C0206359"
    assert entry["rxcui"] in (None, "")
    assert (entry.get("external_ids") or {}).get("unii") in (None, "")
    assert entry.get("gsrs") is None


def test_iqm_bioflavonoids_do_not_borrow_citrus_bioflavonoids_identifiers():
    iqm = load_iqm()
    entry = iqm["bioflavonoids"]

    assert entry["cui"] == "C0005492"
    assert entry["rxcui"] in (None, "")
    assert (entry.get("external_ids") or {}).get("unii") in (None, "")
    assert entry.get("gsrs") is None


def test_iqm_saccharomyces_boulardii_does_not_borrow_brewers_yeast_identifiers():
    iqm = load_iqm()
    entry = iqm["saccharomyces_boulardii"]

    assert entry["cui"] == "C0772093"
    assert entry["rxcui"] in (None, "")
    assert (entry.get("external_ids") or {}).get("unii") in (None, "")
    assert entry.get("gsrs") is None


def test_iqm_null_cui_policy_entries_are_annotated():
    iqm = load_iqm()

    expected = {
        "nad_precursors": "no_single_umls_concept",
        "rna_dna": "no_single_umls_concept",
        "other_fatty_acids": "no_single_umls_concept",
        "organ_extracts": "no_single_umls_concept",
        "algae_oil": "no_single_umls_concept",
        "phenolic_acids": "no_single_umls_concept",
        "pqq": "no_confirmed_umls_match",
        "cgf": "no_confirmed_umls_match",
        "d_fraction": "no_confirmed_umls_match",
        "dnj_1_deoxynojirimycin": "no_confirmed_umls_match",
        "opc": "no_confirmed_umls_match",
        "pac": "no_confirmed_umls_match",
        "tsg": "no_confirmed_umls_match",
        "yeast_fermentate": "no_confirmed_umls_match",
    }

    for entry_id, status in expected.items():
        entry = iqm[entry_id]
        assert entry["cui"] in (None, "")
        assert entry["cui_status"] == status
        assert entry["cui_note"]


def test_iqm_aliases_cover_verified_common_name_variants():
    iqm = load_iqm()

    expected_aliases = {
        "green_lipped_mussel": "green lipped mussel",
        "irish_sea_moss": "Chondrus crispus",
        "guggul": "Commiphora mukul",
        "dicalcium_phosphate": "dicalcium phosphate",
        "sesame_seed_oil": "sesame oil",
        "passionflower": "Passiflora",
        "auricularia": "Auricularia",
    }

    for entry_id, alias in expected_aliases.items():
        aliases = iqm[entry_id].get("aliases") or []
        assert alias in aliases


def test_all_iqm_null_cui_entries_have_status_and_note():
    iqm = load_iqm()

    offenders = []
    for entry_id, entry in iqm.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("cui") not in (None, ""):
            continue
        status = entry.get("cui_status")
        note = entry.get("cui_note")
        if status not in APPROVED_NULL_STATUSES or not isinstance(note, str) or not note.strip():
            offenders.append(entry_id)

    assert offenders == []
