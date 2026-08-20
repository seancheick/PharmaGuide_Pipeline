"""US safety-policy readiness and quarantine behavior.

Hard BLOCKED/UNSAFE decisions are live-catalog outcomes, so identity alone is
not enough.  The winning rule must also carry a verified, role-applicable US
policy basis and an authoritative source URL.  An otherwise confirmed match
with incomplete policy evidence becomes a NOT_SCORED review record instead of
silently becoming either SAFE or a legally unsupported hard block.
"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


_AUTHORITATIVE_HOST_SUFFIXES = (
    "fda.gov",
    "federalregister.gov",
    "govinfo.gov",
    "nih.gov",
)


def _clean_contaminants() -> dict:
    return {"banned_substances": {"found": False, "substances": [], "safety_flags": []}}


def _active_product(name: str, *, raw: str | None = None, forms: list | None = None) -> dict:
    return {
        "dsld_id": f"TEST_{name}",
        "fullName": name,
        "status": "active",
        "form_factor": "capsule",
        "supplement_type": {"type": "single_nutrient"},
        "contaminant_data": _clean_contaminants(),
        "activeIngredients": [
            {
                "name": name,
                "standardName": name,
                "raw_source_text": raw or name,
                "forms": forms or [],
                "mapped": True,
            }
        ],
        "inactiveIngredients": [],
        "ingredient_quality_data": {
            "total_active": 1,
            "ingredients_scorable": [
                {
                    "name": name,
                    "canonical_id": name.lower().replace(" ", "_"),
                    "mapped": True,
                    "quantity": 20.0,
                    "unit": "mg",
                }
            ],
        },
    }


def _official_urls(decision) -> list[str]:
    urls = []
    for source in decision.verified_sources:
        value = source.get("url")
        if not value:
            continue
        host = (urlparse(str(value)).hostname or "").lower()
        if any(host == suffix or host.endswith(f".{suffix}") for suffix in _AUTHORITATIVE_HOST_SUFFIXES):
            urls.append(str(value))
    return urls


@pytest.mark.parametrize(
    ("name", "role"),
    [
        ("Cannabidiol", "active"),
        ("Sulbutiamine", "active"),
        ("Brominated Vegetable Oil", "inactive"),
        ("Partially Hydrogenated Soybean Oil", "inactive"),
    ],
)
def test_verified_us_hard_rules_have_source_complete_decisions(name: str, role: str) -> None:
    from scoring_v4.gate_safety import evaluate_safety_gate

    product = _active_product("Magnesium")
    if role == "active":
        product["activeIngredients"] = [{"name": name, "standardName": name, "mapped": True}]
    else:
        product["inactiveIngredients"] = [{"name": name, "standardName": name}]

    result = evaluate_safety_gate(product)

    assert result.verdict == "BLOCKED"
    assert result.short_circuits_scoring is True
    assert result.quarantine_required is False
    assert result.safety_decision is not None
    assert result.safety_decision.jurisdiction == "US"
    assert result.safety_decision.policy_basis
    assert _official_urls(result.safety_decision), result.safety_decision.to_dict()


@pytest.mark.parametrize(
    "name",
    [
        "Vinpocetine",
        "3,3-Azo-17a-Methyl-5a-Androstan-17b-Ol",
        "2, 17a-Dimethyl-17b-Hydroxy-5a-Androst-2-Ene",
        "17a-Ethyl-Estr-5(6)-Ene-3B-Diol",
    ],
)
def test_confirmed_but_unsettled_us_policy_quarantines_instead_of_hard_blocking(name: str) -> None:
    from scoring_v4.gate_safety import evaluate_safety_gate

    result = evaluate_safety_gate(_active_product(name))

    assert result.verdict not in {"BLOCKED", "UNSAFE"}
    assert result.short_circuits_scoring is False
    assert result.blocking_reason is None
    assert result.safety_decision is None
    assert result.quarantine_required is True
    assert result.quarantine_reason == "safety_policy_review_required"
    assert result.review_records
    assert result.review_records[0]["rule_id"]
    assert result.review_records[0]["substance"]
    assert result.review_records[0]["missing_requirements"]


def test_unverified_hard_signal_defaults_to_quarantine(monkeypatch: pytest.MonkeyPatch) -> None:
    import scoring_v4.gate_safety as gate

    entry = {
        "id": "TEST_UNVERIFIED_HARD_RULE",
        "standard_name": "Test Substance",
        "aliases": ["test substance"],
        "status": "banned",
        "legal_status_enum": "not_lawful_as_supplement",
        "jurisdictions": [
            {
                "jurisdiction_code": "US",
                "source": {"type": "fda_action", "citation": "No URL provided"},
            }
        ],
        "references_structured": [],
    }
    monkeypatch.setattr(
        gate,
        "_safety_rule_indexes",
        lambda: ({entry["id"]: entry}, {"test substance": [entry]}),
    )
    product = _active_product("Magnesium")
    product["contaminant_data"] = {
        "banned_substances": {
            "substances": [
                {
                    "banned_id": entry["id"],
                    "banned_name": "Test Substance",
                    "status": "banned",
                    "match_type": "exact",
                    "source_section": "active",
                }
            ]
        }
    }

    result = gate.evaluate_safety_gate(product)

    assert result.verdict != "BLOCKED"
    assert result.quarantine_required is True
    assert result.review_records[0]["rule_id"] == entry["id"]
    assert "verified_authoritative_us_source" in result.review_records[0]["missing_requirements"]


def test_safety_policy_quarantine_becomes_not_scored_with_actionable_reason() -> None:
    from score_supplements_v4 import score_product_v4

    result = score_product_v4(_active_product("Vinpocetine"))

    assert result["v4_verdict"] == "NOT_SCORED"
    assert result["score_unavailable_reason"] == "safety_policy_review_required"
    gate = result["v4_breakdown"]["safety_gate"]
    assert gate["quarantine_required"] is True
    assert gate["review_records"]


def test_supplemental_sodium_tetraborate_boron_is_not_a_hard_safety_match() -> None:
    from scoring_v4.gate_safety import evaluate_safety_gate

    product = _active_product(
        "Boron",
        raw="Boron (as Sodium Tetraborate)",
        forms=[{"prefix": "as", "name": "Sodium Tetraborate"}],
    )

    result = evaluate_safety_gate(product)

    assert result.verdict not in {"BLOCKED", "UNSAFE"}
    assert result.quarantine_required is False
    assert result.blocking_reason is None


def test_stale_generic_red_yeast_rice_hard_signal_is_revalidated_and_ignored() -> None:
    from scoring_v4.gate_safety import evaluate_safety_gate

    product = _active_product("Red Yeast Rice")
    product["contaminant_data"] = {
        "banned_substances": {
            "substances": [
                {
                    "banned_id": "BANNED_RED_YEAST_RICE",
                    "banned_name": "Red Yeast Rice (Monacolin K)",
                    "ingredient": "Red Yeast Rice",
                    "status": "banned",
                    "match_type": "exact",
                    "source_section": "active",
                }
            ]
        }
    }

    result = evaluate_safety_gate(product)

    assert result.verdict == "CAUTION"
    assert result.short_circuits_scoring is False
    assert result.quarantine_required is False
    assert "B0_STALE_POLICY_SIGNAL_IGNORED" in result.safety_signals
    assert "B0_HIGH_RISK_SUBSTANCE" in result.safety_signals


def test_explicit_monacolin_k_red_yeast_rice_remains_a_verified_hard_block() -> None:
    from scoring_v4.gate_safety import evaluate_safety_gate

    product = _active_product(
        "Red Yeast Rice",
        raw="Red Yeast Rice standardized to Monacolin K",
        forms=[{"name": "Monacolin K"}],
    )

    result = evaluate_safety_gate(product)

    assert result.verdict == "BLOCKED"
    assert result.quarantine_required is False
    assert result.safety_decision is not None
    assert result.safety_decision.winning_rule == "BANNED_RED_YEAST_RICE"
    assert _official_urls(result.safety_decision)
