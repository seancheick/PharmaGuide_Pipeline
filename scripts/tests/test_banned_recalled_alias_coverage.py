#!/usr/bin/env python3
"""Regression checks for alias coverage on intentional-null CUI entries."""

import json
from pathlib import Path


DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "banned_recalled_ingredients.json"


def _entry_map():
    data = json.loads(DATA_FILE.read_text())
    return {entry["id"]: entry for entry in data["ingredients"]}


def test_intentional_null_cui_entries_include_normalized_alias_variants():
    entries = _entry_map()

    expected_aliases = {
        "BANNED_YK11": {"yk 11"},
        "NOOTROPIC_FLMODAFINIL": {"fl-modafinil", "crl 40,940"},
        "PEPTIDE_TB500": {"tb-500", "tb 500", "thymosin beta 4"},
        "SPIKE_CHLOROPRETADALAFIL": {"chloro pretadalafil", "chloropre tadalafil"},
        "SPIKE_METHYL7K": {"7 methylkratom", "7-methyl kratom"},
        "SPIKE_PROPOXYPHENYLSILDENAFIL": {"propoxyphenyl-sildenafil"},
        "ADD_N_PHENETHYL_DIMETHYLAMINE": {"n phenethyl dimethylamine", "n,n dimethylphenethylamine"},
        "ADD_HEXADRONE": {"hexa-drone", "6 chloro androst 4 ene 3 one 17b ol"},
    }

    for entry_id, expected in expected_aliases.items():
        aliases = set(entries[entry_id]["aliases"])
        missing = expected - aliases
        assert not missing, f"{entry_id} missing aliases: {sorted(missing)}"


def test_metadata_includes_audit_runbook_and_cui_policy_notes():
    data = json.loads(DATA_FILE.read_text())
    metadata = data["_metadata"]

    runbook = metadata.get("audit_runbook", {})
    cui_policy = metadata.get("cui_audit_policy", {})

    assert "release_strict_command" in runbook
    assert "--release-strict-cui" in runbook["release_strict_command"]
    assert "verify_cui_manual_command" in runbook
    assert "scripts/api_audit/verify_cui.py" in runbook["verify_cui_manual_command"]
    assert "--search" in runbook["verify_cui_manual_command"]
    assert "approved_null_statuses" in cui_policy
    assert "no_confirmed_umls_match" in cui_policy["approved_null_statuses"]
    assert "no_single_umls_concept" in cui_policy["approved_null_statuses"]
