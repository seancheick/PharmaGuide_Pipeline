#!/usr/bin/env python3
"""Contract tests for standalone medication profile-gate rules."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
RULES_PATH = DATA_DIR / "medication_profile_gate_rules.json"
TAXONOMY_PATH = DATA_DIR / "clinical_risk_taxonomy.json"
_EVAL_PATH = Path(__file__).resolve().parents[1] / "profile_gate_evaluator.py"

_spec = importlib.util.spec_from_file_location("profile_gate_evaluator", _EVAL_PATH)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["profile_gate_evaluator"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]
validate_profile_gate = _mod.validate_profile_gate
evaluate_profile_gate = _mod.evaluate_profile_gate


@pytest.fixture(scope="module")
def rules_blob() -> dict:
    return json.loads(RULES_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def taxonomy() -> dict:
    return json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))


def test_metadata_count_matches_rule_count(rules_blob):
    rules = rules_blob["medication_profile_gate_rules"]
    assert rules_blob["_metadata"]["total_entries"] == len(rules)


def test_every_rule_profile_gate_validates(rules_blob, taxonomy):
    failures: list[str] = []
    for rule in rules_blob["medication_profile_gate_rules"]:
        errors = validate_profile_gate(rule.get("profile_gate"), taxonomy=taxonomy)
        failures.extend(f"{rule.get('id', '?')}: {e}" for e in errors)
    assert not failures


def test_pregnancy_nsaid_rule_semantics(rules_blob):
    rule = next(
        r
        for r in rules_blob["medication_profile_gate_rules"]
        if r["id"] == "MCR_PREGNANCY_NSAIDS"
    )
    gate = rule["profile_gate"]
    product_context = {
        "product_form": None,
        "nutrient_form": None,
        "dose_per_day": None,
        "dose_unit": None,
    }

    result = evaluate_profile_gate(
        gate,
        {"conditions": [], "drug_classes": ["nsaids"], "profile_flags": ["pregnant"]},
        product_context,
        base_severity=rule["severity"],
    )
    assert result.fires is True
    assert result.severity == "caution"

    non_pregnant = evaluate_profile_gate(
        gate,
        {"conditions": [], "drug_classes": ["nsaids"], "profile_flags": []},
        product_context,
        base_severity=rule["severity"],
    )
    assert non_pregnant.fires is False

    acetaminophen = evaluate_profile_gate(
        gate,
        {"conditions": [], "drug_classes": [], "profile_flags": ["pregnant"]},
        product_context,
        base_severity=rule["severity"],
    )
    assert acetaminophen.fires is False

    aspirin_v1 = evaluate_profile_gate(
        gate,
        {
            "conditions": [],
            "drug_classes": ["antiplatelets"],
            "profile_flags": ["pregnant"],
        },
        product_context,
        base_severity=rule["severity"],
    )
    assert aspirin_v1.fires is False


def test_kidney_disease_nsaid_rule_semantics(rules_blob):
    rule = next(
        r
        for r in rules_blob["medication_profile_gate_rules"]
        if r["id"] == "MCR_KIDNEY_DISEASE_NSAIDS"
    )
    gate = rule["profile_gate"]
    product_context = {
        "product_form": None,
        "nutrient_form": None,
        "dose_per_day": None,
        "dose_unit": None,
    }

    result = evaluate_profile_gate(
        gate,
        {
            "conditions": ["kidney_disease"],
            "drug_classes": ["nsaids"],
            "profile_flags": [],
        },
        product_context,
        base_severity=rule["severity"],
    )
    assert result.fires is True
    assert result.severity == "avoid"

    kidney_without_nsaid = evaluate_profile_gate(
        gate,
        {
            "conditions": ["kidney_disease"],
            "drug_classes": [],
            "profile_flags": [],
        },
        product_context,
        base_severity=rule["severity"],
    )
    assert kidney_without_nsaid.fires is False

    nsaid_without_kidney = evaluate_profile_gate(
        gate,
        {
            "conditions": [],
            "drug_classes": ["nsaids"],
            "profile_flags": [],
        },
        product_context,
        base_severity=rule["severity"],
    )
    assert nsaid_without_kidney.fires is False


def test_rule_sources_are_authoritative_urls(rules_blob):
    allowed_hosts = {
        "www.accessdata.fda.gov",
        "www.fda.gov",
        "www.acog.org",
        "www.niddk.nih.gov",
        "www.kidney.org",
        "publications.smfm.org",
    }
    for rule in rules_blob["medication_profile_gate_rules"]:
        sources = rule.get("sources")
        assert isinstance(sources, list) and sources, f"{rule['id']} missing sources"
        for url in sources:
            parsed = urlparse(url)
            assert parsed.scheme == "https", f"{rule['id']} non-https source: {url}"
            assert parsed.netloc in allowed_hosts, (
                f"{rule['id']} source host {parsed.netloc!r} is not an "
                "approved clinical-authority host"
            )


def test_copy_does_not_claim_acetaminophen_is_safe(rules_blob):
    rule = next(
        r
        for r in rules_blob["medication_profile_gate_rules"]
        if r["id"] == "MCR_PREGNANCY_NSAIDS"
    )
    copy = f"{rule['headline']} {rule['body']} {rule['management']}".lower()
    assert "20 weeks" in copy
    assert "30 weeks" in copy
    assert "acetaminophen" in copy
    assert "safe" not in copy


def test_approved_medication_context_exceptions_are_source_bounded(rules_blob):
    rules = {r['id']: r for r in rules_blob['medication_profile_gate_rules']}
    pregnancy = rules['MCR_PREGNANCY_NSAIDS']
    kidney = rules['MCR_KIDNEY_DISEASE_NSAIDS']
    assert pregnancy['medication_ingredient_rxcuis'] == ['1191']
    assert kidney['medication_ingredient_rxcuis'] == ['1191']
    assert pregnancy['medication_exceptions'] == [
        {'ingredient_rxcuis': ['1191'], 'dose_mg_exact': 81, 'use_context': 'clinician_directed_pregnancy_condition'},
        {'route': 'ophthalmic'},
    ]
    assert kidney['medication_exceptions'] == [
        {'ingredient_rxcuis': ['1191'], 'dose_mg_range_inclusive': [81, 100], 'use_context': 'cardiovascular_protection'},
        {'ingredient_rxcuis': ['3355'], 'route': 'topical', 'use_context': 'within_product_label_directions'},
    ]
