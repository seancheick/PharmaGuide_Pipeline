#!/usr/bin/env python3
"""Regression tests for botanical enrichment safety across reference files."""

import json
import sys
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
BOTANICALS_PATH = DATA_DIR / "botanical_ingredients.json"
STANDARDIZED_PATH = DATA_DIR / "standardized_botanicals.json"


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _load_rows(path: Path, key: str) -> dict[str, dict]:
    rows = json.loads(path.read_text())[key]
    return {row["id"]: row for row in rows}


def test_acai_rows_use_plant_cui_not_disease_cui():
    botanicals = _load_rows(BOTANICALS_PATH, "botanical_ingredients")
    standardized = _load_rows(STANDARDIZED_PATH, "standardized_botanicals")

    assert botanicals["acai_berry"]["CUI"] == "C1054955"
    assert standardized["acai"]["CUI"] == "C1054955"


def test_generic_ashwagandha_does_not_carry_withanolide_pubchem_ids():
    botanicals = _load_rows(BOTANICALS_PATH, "botanical_ingredients")
    ashwagandha = botanicals["ashwagandha"]
    ext = ashwagandha.get("external_ids") or {}

    assert ext.get("cas") in (None, "")
    assert ext.get("pubchem_cid") in (None, "")


def test_citrus_bergamot_does_not_borrow_leaf_oil_identity():
    botanicals = _load_rows(BOTANICALS_PATH, "botanical_ingredients")
    bergamot = botanicals["citrus_bergamot"]
    ext = bergamot.get("external_ids") or {}

    assert ext.get("unii") in (None, "")
    assert bergamot.get("rxcui") in (None, "")
    assert bergamot.get("gsrs") is None


def test_enrich_botanicals_dry_run_does_not_write_pre_enrichment_changes(tmp_path, monkeypatch):
    from api_audit import enrich_botanicals

    botanicals_path = tmp_path / "botanical_ingredients.json"
    standardized_path = tmp_path / "standardized_botanicals.json"
    other_path = tmp_path / "other_ingredients.json"

    botanicals_payload = {
        "botanical_ingredients": [
            {
                "id": "acai_berry",
                "standard_name": "Acai Berry",
                "latin_name": "Euterpe oleracea",
                "aliases": ["acai berry extract"],
                "CUI": "C1054955",
            }
        ]
    }
    standardized_payload = {
        "standardized_botanicals": [
            {
                "id": "acai",
                "standard_name": "Acai",
                "aliases": ["acai berry extract"],
            }
        ]
    }
    other_payload = {"other_ingredients": []}

    botanicals_path.write_text(json.dumps(botanicals_payload, indent=2) + "\n")
    standardized_path.write_text(json.dumps(standardized_payload, indent=2) + "\n")
    other_path.write_text(json.dumps(other_payload, indent=2) + "\n")

    original_botanicals = botanicals_path.read_text()
    original_standardized = standardized_path.read_text()

    monkeypatch.setattr(
        enrich_botanicals,
        "TARGETS",
        {
            "botanical_ingredients": {
                "file": botanicals_path,
                "list_key": "botanical_ingredients",
                "cui_field": "CUI",
            },
            "other_ingredients": {
                "file": other_path,
                "list_key": "other_ingredients",
                "cui_field": "CUI",
            },
            "standardized_botanicals": {
                "file": standardized_path,
                "list_key": "standardized_botanicals",
                "cui_field": "CUI",
            },
        },
    )
    monkeypatch.setattr(enrich_botanicals, "run_enrichment_script", lambda *args, **kwargs: 0)
    monkeypatch.setattr(sys, "argv", ["enrich_botanicals.py"])

    enrich_botanicals.main()

    assert botanicals_path.read_text() == original_botanicals
    assert standardized_path.read_text() == original_standardized
