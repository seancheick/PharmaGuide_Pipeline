"""US verdict applicability and regional safety metadata (finding C5)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3
from scoring_v4.gate_safety import evaluate_safety_gate


DATA_PATH = Path(__file__).parent.parent / "data" / "banned_recalled_ingredients.json"


def _entry(code: str) -> dict:
    entry = {
        "id": f"BAN_{code}",
        "standard_name": "Regional Test Substance",
        "aliases": ["regional test substance"],
        "status": "banned",
        "entity_type": "ingredient",
        "match_rules": {"match_mode": "active"},
        "legal_status_enum": "banned_federal",
        "clinical_risk_enum": "critical",
        "jurisdictions": [{
            "region": code,
            "jurisdiction_type": "country",
            "jurisdiction_code": code,
            "status": "banned",
        }],
    }
    if code == "US":
        entry.update({
            "policy_verification_status": "verified",
            "policy_verified_at": "2026-08-20",
            "hard_verdict_roles": ["active"],
            "references_structured": [{
                "type": "fda_action",
                "title": "Synthetic jurisdiction test policy",
                "url": "https://www.fda.gov/food/dietary-supplements",
                "supports_claims": ["regulatory_status"],
            }],
        })
    return entry


def _enriched_hit(code: str) -> dict:
    enricher = SupplementEnricherV3()
    enricher.databases["banned_recalled_ingredients"] = {
        "ingredients": [_entry(code)]
    }
    result = enricher._check_banned_substances([
        {"name": "Regional Test Substance", "standardName": "Regional Test Substance"}
    ])
    return {
        "dsld_id": f"regional-{code}",
        "contaminant_data": {"banned_substances": result},
    }


def test_non_us_ban_is_retained_as_advisory_but_does_not_block_us_verdict() -> None:
    product = _enriched_hit("GB")
    hit = product["contaminant_data"]["banned_substances"]["substances"][0]

    assert hit["us_applicable"] is False
    assert hit["jurisdictions"][0]["jurisdiction_code"] == "GB"
    assert hit["regional_advisories"] == hit["jurisdictions"]

    result = evaluate_safety_gate(product)
    assert result.verdict is None
    assert result.short_circuits_scoring is False
    assert "B0_REGIONAL_ADVISORY" in result.safety_signals


def test_us_ban_remains_a_confirmed_block(monkeypatch: pytest.MonkeyPatch) -> None:
    import scoring_v4.gate_safety as gate

    entry = _entry("US")
    monkeypatch.setattr(
        gate,
        "_safety_rule_indexes",
        lambda: ({entry["id"]: entry}, {"regional test substance": [entry]}),
    )
    product = _enriched_hit("US")
    hit = product["contaminant_data"]["banned_substances"]["substances"][0]

    assert hit["us_applicable"] is True
    assert hit["regional_advisories"] == []

    result = gate.evaluate_safety_gate(product)
    assert result.verdict == "BLOCKED"
    assert result.short_circuits_scoring is True


@pytest.mark.parametrize(
    "label,rule_id",
    [
        ("Garcinia Cambogia", "RISK_GARCINIA_CAMBOGIA"),
        ("Cascara Sagrada", "ADD_CASCARA_SAGRADA"),
        ("Colloidal Silver", "ADD_COLLOIDAL_SILVER"),
    ],
)
def test_reviewed_us_clinical_risks_produce_caution(label: str, rule_id: str) -> None:
    product = {
        "dsld_id": f"clinical-{rule_id}",
        "activeIngredients": [{"name": label, "standardName": label}],
    }

    result = evaluate_safety_gate(product)

    assert result.verdict == "CAUTION"
    assert result.quarantine_required is False
    assert "B0_REGIONAL_ADVISORY" not in result.safety_signals


def test_us_clinical_risk_rows_have_verified_us_policy_metadata() -> None:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    by_id = {entry["id"]: entry for entry in payload["ingredients"]}

    for rule_id in (
        "RISK_GARCINIA_CAMBOGIA",
        "ADD_CASCARA_SAGRADA",
        "ADD_COLLOIDAL_SILVER",
    ):
        entry = by_id[rule_id]
        assert entry["policy_verification_status"] == "verified"
        assert any(
            str(item.get("jurisdiction_code") or "").upper() == "US"
            for item in entry.get("jurisdictions") or []
        )


def test_matched_high_risk_rule_without_jurisdiction_is_quarantined(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scoring_v4.gate_safety as gate

    entry = {
        "id": "RISK_UNRESOLVED_POLICY",
        "standard_name": "Unresolved Policy Ingredient",
        "aliases": ["unresolved policy ingredient"],
        "status": "high_risk",
        "entity_type": "ingredient",
        "match_mode": "active",
        "jurisdictions": [],
    }
    monkeypatch.setattr(
        gate,
        "_safety_rule_indexes",
        lambda: ({entry["id"]: entry}, {"unresolved policy ingredient": [entry]}),
    )
    result = gate.evaluate_safety_gate({
        "dsld_id": "unresolved-policy",
        "contaminant_data": {
            "banned_substances": {
                "safety_flags": [{
                    "entry_id": entry["id"],
                    "status": "high_risk",
                    "match_type": "alias",
                    "source_db": "banned_recalled_ingredients",
                    "subject_role": "active",
                    "matched_variant": "Unresolved Policy Ingredient",
                }]
            }
        },
    })

    assert result.verdict is None
    assert result.quarantine_required is True
    assert result.quarantine_reason == "safety_policy_review_required"
    assert result.review_records[0]["missing_requirements"] == [
        "explicit_us_jurisdiction"
    ]
