"""Label certification claims detected by the enricher.

Claims are claims: the enricher records which programs a label names but never
derives purity / heavy-metal / label-accuracy flags from them. Those flags come
only from registry-verified product certifications
(scoring_v4.cert_evidence.verified_quality_flags; see
test_cert_claimed_vs_verified.py)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from cert_resolver import CertRegistry, normalize_program  # noqa: E402
from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402


def _enricher() -> SupplementEnricherV3:
    enricher = SupplementEnricherV3.__new__(SupplementEnricherV3)
    enricher.logger = MagicMock()
    enricher.databases = {
        "cert_claim_rules": json.loads(
            (SCRIPTS_ROOT / "data" / "cert_claim_rules.json").read_text()
        ),
        "top_manufacturers_data": {"top_manufacturers": []},
    }
    enricher.reference_versions = {"cert_claim_rules": {"version": "test"}}
    enricher._cert_registry_cache = CertRegistry()
    enricher._compile_patterns()
    return enricher


def _certification_from_label(label_text: str) -> dict:
    product = {
        "brandName": "Garden of Life Dr. Formulated Probiotics",
        "fullName": "Prenatal Daily Care 20 Billion CFU Guaranteed",
        "labelText": {"raw": label_text, "parsed": {"certifications": [label_text]}},
        "statements": [],
        "claims": [],
        "activeIngredients": [],
        "inactiveIngredients": [],
    }
    return _enricher()._collect_certification_data(product)


def _assert_no_claim_derived_flags(certification_data: dict) -> None:
    for flag in ("purity_verified", "heavy_metal_tested", "label_accuracy_verified"):
        assert flag not in certification_data


def _program_names(certification_data: dict) -> list[str]:
    programs = certification_data["third_party_programs"]["programs"]
    return [program["name"] for program in programs]


def test_nsf_certified_gluten_free_is_not_a_quality_program_claim() -> None:
    certification = _certification_from_label(
        "NSF Certified Gluten-Free Certified Vegan Vegan.org Non-GMO Project Verified"
    )

    assert _program_names(certification) == []
    _assert_no_claim_derived_flags(certification)


def test_generic_nsf_certified_is_not_a_quality_program_claim() -> None:
    certification = _certification_from_label("NSF Certified")

    assert _program_names(certification) == []
    _assert_no_claim_derived_flags(certification)


def test_nsf_contents_certified_is_detected_as_a_claim() -> None:
    certification = _certification_from_label("NSF Contents Certified")

    assert _program_names(certification) == ["NSF Contents Certified"]
    _assert_no_claim_derived_flags(certification)


def test_reversed_contents_certified_nsf_is_detected_as_a_claim() -> None:
    certification = _certification_from_label(
        "Contents Certified NSF\nNSF Certified Gluten-Free\nCertified Vegan"
    )

    assert _program_names(certification) == ["NSF Contents Certified"]
    _assert_no_claim_derived_flags(certification)


def test_nsf_ansi_455_is_detected_as_a_claim() -> None:
    certification = _certification_from_label("NSF/ANSI 455 Dietary Supplement Certified")

    assert _program_names(certification) == ["NSF/ANSI 455 Dietary Supplement"]
    _assert_no_claim_derived_flags(certification)


def test_nsf_contents_rules_db_bridge_preserves_specific_program_name() -> None:
    enricher = _enricher()

    merged = enricher._merge_evidence_third_party_programs(
        {"programs": [], "count": 0, "has_generic_claim_only": False},
        [
            {
                "rule_id": "CERT_NSF_CONTENTS",
                "display_name": "NSF Contents Certified",
                "score_eligible": True,
            }
        ],
    )

    assert merged["programs"] == [
        {"name": "NSF Contents Certified", "source": "rules_db"}
    ]


def test_nsf_contents_certified_resolves_against_existing_nsf_173_registry_name() -> None:
    assert normalize_program("NSF Contents Certified") == "NSF Certified"


def _certification_from_statements(*notes: str) -> dict:
    product = {
        "brandName": "GNC",
        "fullName": "Melatonin 3 mg Timed-Release",
        "statements": [{"type": "General Statements", "notes": note} for note in notes],
        "claims": [],
        "activeIngredients": [],
        "inactiveIngredients": [],
    }
    return _enricher()._collect_certification_data(product)


def test_usp_chapter_and_later_verified_wording_is_not_usp_verified() -> None:
    """GNC 224757 prints "Conforms to USP <2091> for weight." (a pharmacopeial
    test) and, statements later, unrelated "verified" wording. A whole-label
    regex joined the two into "USP Verified" and lit Purity / Heavy Metal /
    Label Accuracy badges on 156 products. Claims are read statement by
    statement by the one rules-DB detector."""
    certification = _certification_from_statements(
        "Conforms to USP <2091> for weight. Meets USP <2040> disintegration.",
        "This statement has not been evaluated by the Food and Drug Administration.",
        "Potency verified by GNC procedure #5008.",
    )

    assert _program_names(certification) == []
    _assert_no_claim_derived_flags(certification)


def test_program_claim_split_across_statements_is_not_a_claim() -> None:
    certification = _certification_from_statements(
        "Ingredients reviewed in a ConsumerLab.com industry report.",
        "Freshness seal: do not use if seal under cap is broken.",
    )

    assert _program_names(certification) == []


def test_seal_statement_program_claims_still_detected() -> None:
    certification = _certification_from_statements("NSF Certified Sport", "USP Verified")

    assert sorted(_program_names(certification)) == ["NSF Sport", "USP Verified"]


def test_generic_third_party_wording_is_display_only() -> None:
    certification = _certification_from_statements("Third-party tested for purity.")

    assert _program_names(certification) == []
    assert certification["third_party_programs"]["has_generic_claim_only"] is True


def test_third_party_programs_have_one_detector() -> None:
    assert not hasattr(SupplementEnricherV3, "_collect_third_party_certs")


def test_verification_assessment_is_not_evaluated_without_registry_sources() -> None:
    certification = _certification_from_label("")

    assert certification["verification_assessment"] == {
        "state": "not_evaluated",
        "readiness": "incomplete",
        "reason_code": "cert_registry_sources_unavailable",
        "matched_programs": [],
        "registry_schema_version": None,
        "registry_source_count": 0,
    }


def test_verification_assessment_distinguishes_completed_absence_and_presence() -> None:
    enricher = _enricher()
    registry = CertRegistry(
        metadata={"schema_version": "fixture-registry"},
        recency_by_program={
            "NSF Sport": {
                "status": "fresh",
                "snapshot_date": "2026-08-01",
                "age_days": 19,
            }
        },
    )
    enricher._cert_registry_cache = registry

    absent = enricher._build_verification_assessment([])
    present = enricher._build_verification_assessment([
        {
            "program": "NSF Sport",
            "scope": "sku",
            "record_id": "fixture-record",
            "recency_status": "fresh",
        }
    ])

    assert absent["state"] == "verified_absent"
    assert absent["readiness"] == "complete"
    assert absent["reason_code"] == "registry_evaluated_no_match"
    assert present["state"] == "verified_present"
    assert present["matched_programs"] == ["NSF Sport"]


@pytest.mark.parametrize(
    ("label_text", "expected_programs"),
    [
        ("Clean Label Project Certified", ["Clean Label Project Certified"]),
        ("Labdoor Tested", ["Labdoor Tested"]),
        ("GOED Certified", ["GOED Certified"]),
        ("IFOS 5-Star", ["IFOS"]),
        ("Informed Choice", ["Informed Choice"]),
    ],
)
def test_program_claims_are_detected_without_quality_flags(
    label_text: str,
    expected_programs: list[str],
) -> None:
    certification = _certification_from_label(label_text)

    assert _program_names(certification) == expected_programs
    _assert_no_claim_derived_flags(certification)
