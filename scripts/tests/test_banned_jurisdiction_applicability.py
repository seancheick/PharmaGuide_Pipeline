"""US verdict applicability and regional safety metadata (finding C5)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3
from scoring_v4.gate_safety import evaluate_safety_gate


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
