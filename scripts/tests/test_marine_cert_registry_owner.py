"""Marine certification names come only from cert_claim_rules.json.

The old generic_trust fallback invented ifos / Friend of the Sea / MSC / GOED
whenever that registry could not be read. Invalid canonical policy now stops
scoring instead of inventing tokens or erasing unrelated certification credit.
Sustainability-only claims stay out of testing trust.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scoring_v4 import cert_evidence
from scoring_v4.modules import generic_trust
from scoring_v4.modules.generic_trust import score_trust

REAL_MARINE_TOKENS = frozenset({
    "friend of the sea",
    "goed",
    "goed certified",
    "ifos",
    "ifos certified",
    "msc",
    "msc certified",
})


@pytest.fixture(autouse=True)
def _clear_marine_cache():
    cert_evidence.marine_cert_tokens.cache_clear()
    yield
    cert_evidence.marine_cert_tokens.cache_clear()


def _cert(program: str, scope: str) -> dict:
    return {
        "program": program,
        "scope": scope,
        "record_id": "TEST_RECORD",
        "source_url": "https://registry.example/certified-products",
        "snapshot_date": "2026-09-16",
        "recency_status": "fresh",
        "evidence_source": "product_label",
    }


def _product(**extra) -> dict:
    product = {
        "status": "active",
        "primary_type": extra.pop("primary_type", "single_nutrient"),
        "ingredient_quality_data": {
            "ingredients_scorable": [{"name": extra.pop("ingredient", "Magnesium"), "mapped": True}],
        },
        "verified_cert_programs": extra.pop("verified_cert_programs", []),
        "certification_data": extra.pop("certification_data", {
            "gmp": {},
            "batch_traceability": {},
            "evidence_based": {"third_party_programs": []},
        }),
    }
    product.update(extra)
    return product


def _write_registry(tmp_path: Path, programs: dict) -> None:
    path = tmp_path / "cert_claim_rules.json"
    path.write_text(json.dumps({"rules": {"third_party_programs": programs}}))
    cert_evidence.marine_cert_tokens.cache_clear()


def test_valid_registry_produces_the_registry_tokens():
    assert cert_evidence.marine_cert_tokens() == REAL_MARINE_TOKENS
    assert not hasattr(generic_trust, "MARINE_CERTS_FALLBACK")


def test_ordinary_usp_certification_score_is_unchanged():
    payload = score_trust(_product(verified_cert_programs=[_cert("USP Verified", "sku")]))
    assert payload["components"]["B4a_verified_certifications"] == 8.0
    assert payload["metadata"]["verified_programs_scored"] == ["usp verified"]


def test_marine_cert_stays_unscored_on_a_non_omega_product():
    payload = score_trust(_product(verified_cert_programs=[
        _cert("IFOS", "sku"),
        _cert("Friend of the Sea", "product_line"),
    ]))
    assert payload["components"]["B4a_verified_certifications"] == 0.0
    assert payload["metadata"]["verified_programs_scored"] == []


def test_ifos_label_claim_still_scores_on_omega():
    payload = score_trust(_product(
        primary_type="omega_3",
        certification_data={
            "gmp": {},
            "batch_traceability": {},
            "evidence_based": {"third_party_programs": [{
                "display_name": "IFOS Certified",
                "rule_id": "ifos",
                "score_eligible": True,
            }]},
        },
    ))
    assert payload["components"]["B4a_verified_certifications"] == 2.0
    assert payload["metadata"]["verified_programs_scored"] == ["ifos"]


def test_sustainability_only_claim_does_not_become_testing_credit():
    payload = score_trust(_product(
        primary_type="omega_3",
        ingredient="Fish Oil",
        certification_data={
            "gmp": {},
            "batch_traceability": {},
            "evidence_based": {"third_party_programs": [{
                "display_name": "Friend of the Sea",
                "rule_id": "friend_of_the_sea",
                "score_eligible": True,
            }]},
        },
    ))
    assert payload["components"]["B4a_verified_certifications"] == 0.0
    assert payload["metadata"]["verified_programs_scored"] == []


def test_missing_registry_does_not_use_hardcoded_tokens(tmp_path, monkeypatch):
    monkeypatch.setattr(cert_evidence, "_CERT_CLAIM_RULES_PATH", tmp_path / "absent.json")
    with pytest.raises(cert_evidence.CertificationPolicyError, match="cannot load"):
        score_trust(_product(verified_cert_programs=[_cert("USP Verified", "sku")]))


def test_malformed_registry_does_not_award_certification_credit(tmp_path, monkeypatch):
    path = tmp_path / "cert_claim_rules.json"
    path.write_text("{")
    monkeypatch.setattr(cert_evidence, "_CERT_CLAIM_RULES_PATH", path)
    with pytest.raises(cert_evidence.CertificationPolicyError, match="cannot load"):
        score_trust(_product(verified_cert_programs=[
            _cert("USP Verified", "sku"),
            _cert("IFOS", "sku"),
        ]))


def test_empty_marine_scope_is_a_configuration_failure(tmp_path, monkeypatch):
    _write_registry(tmp_path, {
        "usp_verified": {"display_name": "USP Verified"},
        "ifos": {"display_name": "IFOS Certified", "product_scope": ""},
    })
    monkeypatch.setattr(cert_evidence, "_CERT_CLAIM_RULES_PATH", tmp_path / "cert_claim_rules.json")
    with pytest.raises(cert_evidence.CertificationPolicyError, match="no marine-scoped"):
        score_trust(_product(verified_cert_programs=[
            _cert("USP Verified", "sku"),
            _cert("IFOS", "sku"),
        ]))
