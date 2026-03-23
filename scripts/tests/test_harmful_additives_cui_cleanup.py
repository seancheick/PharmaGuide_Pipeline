#!/usr/bin/env python3
"""Regression checks for harmful_additives CUI cleanup and umbrella structure."""

import json
from pathlib import Path


DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "harmful_additives.json"


def _load():
    return json.loads(DATA_FILE.read_text())


def _entries():
    data = _load()
    return {entry["id"]: entry for entry in data["harmful_additives"]}


def test_harmful_additives_metadata_includes_audit_runbook_and_cui_policy():
    metadata = _load()["_metadata"]

    assert "audit_runbook" in metadata
    assert "cui_audit_policy" in metadata
    assert "verify_cui.py" in metadata["audit_runbook"]["release_strict_command"]
    assert metadata["audit_runbook"]["release_gate_checklist"]
    assert "verify_cui.py" in metadata["audit_runbook"]["verify_cui_dry_run_command"]
    assert "no_confirmed_umls_match" in metadata["cui_audit_policy"]["approved_null_statuses"]
    assert "no_single_umls_concept" in metadata["cui_audit_policy"]["approved_null_statuses"]


def test_known_wrong_cuis_are_corrected():
    entries = _entries()

    expected = {
        "ADD_BLUE2": "C0021219",
        "ADD_CANOLA_OIL": "C0072982",
        "ADD_CARMINE_RED": "C0007250",
        "ADD_NEOTAME": "C0912295",
        "ADD_POLYVINYLPYRROLIDONE": "C0032856",
        "ADD_SODIUM_BENZOATE": "C0142805",
        "ADD_SODIUM_CASEINATE": "C0037488",
        "ADD_SODIUM_SULFITE": "C0074771",
        "ADD_SOY_MONOGLYCERIDES": "C0026481",
        "ADD_TBHQ": "C0046563",
        "ADD_HYDROGENATED_COCONUT_OIL": "C3255733",
    }

    for entry_id, cui in expected.items():
        assert entries[entry_id]["cui"] == cui, f"{entry_id} expected {cui}"


def test_umbrella_entries_are_explicitly_structured():
    entries = _entries()

    antioxidants = entries["ADD_SYNTHETIC_ANTIOXIDANTS"]
    assert antioxidants["entity_type"] == "class"
    assert antioxidants["match_rules"]["match_mode"] == "disabled"
    assert antioxidants["cui"] is None
    assert antioxidants["cui_status"] == "no_single_umls_concept"
    assert set(antioxidants["member_ids"]) >= {"ADD_BHA", "ADD_BHT", "ADD_TBHQ"}

    nitrites = entries["ADD_NITRITES"]
    assert nitrites["entity_type"] == "class"
    assert nitrites["match_rules"]["match_mode"] == "disabled"
    assert nitrites["cui"] is None
    assert nitrites["cui_status"] == "no_single_umls_concept"
    assert set(nitrites["member_ids"]) >= {
        "ADD_SODIUM_NITRITE",
        "ADD_SODIUM_NITRATE",
        "ADD_POTASSIUM_NITRITE",
        "ADD_POTASSIUM_NITRATE",
    }


def test_atomic_nitrite_children_exist():
    entries = _entries()

    assert entries["ADD_SODIUM_NITRITE"]["cui"] == "C0037532"
    assert entries["ADD_SODIUM_NITRATE"]["cui"] == "C0074748"
    assert entries["ADD_POTASSIUM_NITRITE"]["cui"] == "C0071773"
    assert entries["ADD_POTASSIUM_NITRATE"]["cui"] == "C0071772"


def test_intentional_null_cuis_are_annotated():
    entries = _entries()

    for entry_id in [
        "ADD_ANTIMONY",
        "ADD_CALCIUM_CITRATE_LAURATE",
        "ADD_CANDURIN_SILVER",
        "ADD_MAGNESIUM_CITRATE_LAURATE",
        "ADD_MALTOTAME",
        "ADD_PUREFRUIT_SELECT",
        "ADD_SLIMSWEET",
        "ADD_SYNTHETIC_B_VITAMINS",
        "ADD_SYNTHETIC_VITAMINS",
        "ADD_SYRUPS",
        "ADD_TAPIOCA_FILLER",
        "ADD_TIME_SORB",
        "ADD_UNSPECIFIED_COLORS",
        "ADD_PARTIALLY_HYDROGENATED_CORN_OIL",
    ]:
        entry = entries[entry_id]
        assert entry["cui"] is None
        assert entry["cui_status"] in {"no_confirmed_umls_match", "no_single_umls_concept"}
        assert entry["cui_note"]
