#!/usr/bin/env python3
"""Regression checks for PubMed remediation and schema alignment."""

import json
from pathlib import Path


CLINICAL_FILE = Path(__file__).resolve().parent.parent / "data" / "backed_clinical_studies.json"
BANNED_FILE = Path(__file__).resolve().parent.parent / "data" / "banned_recalled_ingredients.json"
SCHEMA_FILE = Path(__file__).resolve().parent.parent / "DATABASE_SCHEMA.md"


def _clinical_map():
    data = json.loads(CLINICAL_FILE.read_text())
    return {entry["id"]: entry for entry in data["backed_clinical_studies"]}


def _banned_map():
    data = json.loads(BANNED_FILE.read_text())
    return {entry["id"]: entry for entry in data["ingredients"]}


def test_l_citrulline_retracted_reference_is_removed_or_replaced():
    entry = _clinical_map()["INGR_L_CITRULLINE"]
    pmids = {ref.get("pmid") for ref in entry.get("references_structured", [])}
    retracted = [ref for ref in entry.get("references_structured", []) if ref.get("retracted")]

    assert "30206378" not in pmids
    assert not retracted
    assert "30284051" in pmids


def test_high_confidence_pubmed_suggestions_promoted_for_unresolved_clinical_entries():
    entries = _clinical_map()

    assert any(ref.get("pmid") == "12169147" for ref in entries["INGR_5HTP"].get("references_structured", []))
    assert any(ref.get("pmid") == "22301923" for ref in entries["INGR_EPICATECHIN"].get("references_structured", []))
    assert any(ref.get("pmid") == "31567003" for ref in entries["INGR_OMEGA3"].get("references_structured", []))
    assert any(ref.get("pmid") == "19109655" for ref in entries["INGR_PLANT_STEROLS"].get("references_structured", []))
    assert any(ref.get("pmid") == "25629804" for ref in entries["INGR_CHONDROITIN_SULFATE"].get("references_structured", []))


def test_banned_pho_bad_retracted_doi_reference_is_removed():
    entry = _banned_map()["BANNED_PHO"]
    urls = {ref.get("url") for ref in entry.get("references_structured", [])}
    ids = {ref.get("id") for ref in entry.get("references_structured", [])}

    assert "10.1056/NEJMoa1200303" not in ids
    assert "https://doi.org/10.1056/NEJMoa1200303" not in urls


def test_database_schema_documents_structured_pubmed_references_for_clinical_studies():
    doc = SCHEMA_FILE.read_text()

    assert "references_structured" in doc
    assert "PubMed-backed structured citations" in doc
    assert "study_type" in doc and "rct_multiple" in doc
