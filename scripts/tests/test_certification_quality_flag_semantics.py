"""Certification capability semantics for app-facing quality flags."""

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


def _program_names(certification_data: dict) -> list[str]:
    programs = certification_data["third_party_programs"]["programs"]
    return [program["name"] for program in programs]


def test_nsf_certified_gluten_free_does_not_imply_quality_testing_flags() -> None:
    certification = _certification_from_label(
        "NSF Certified Gluten-Free Certified Vegan Vegan.org Non-GMO Project Verified"
    )

    assert _program_names(certification) == []
    assert certification["purity_verified"] is False
    assert certification["heavy_metal_tested"] is False
    assert certification["label_accuracy_verified"] is False


def test_generic_nsf_certified_does_not_imply_quality_testing_flags() -> None:
    certification = _certification_from_label("NSF Certified")

    assert _program_names(certification) == []
    assert certification["purity_verified"] is False
    assert certification["heavy_metal_tested"] is False
    assert certification["label_accuracy_verified"] is False


def test_nsf_contents_certified_sets_quality_testing_flags() -> None:
    certification = _certification_from_label("NSF Contents Certified")

    assert _program_names(certification) == ["NSF Contents Certified"]
    assert certification["purity_verified"] is True
    assert certification["heavy_metal_tested"] is True
    assert certification["label_accuracy_verified"] is True


def test_reversed_contents_certified_nsf_sets_specific_quality_program() -> None:
    certification = _certification_from_label(
        "Contents Certified NSF\nNSF Certified Gluten-Free\nCertified Vegan"
    )

    assert _program_names(certification) == ["NSF Contents Certified"]
    assert certification["purity_verified"] is True
    assert certification["heavy_metal_tested"] is True
    assert certification["label_accuracy_verified"] is True


def test_nsf_ansi_455_sets_quality_testing_flags() -> None:
    certification = _certification_from_label("NSF/ANSI 455 Dietary Supplement Certified")

    assert _program_names(certification) == ["NSF/ANSI 455 Dietary Supplement"]
    assert certification["purity_verified"] is True
    assert certification["heavy_metal_tested"] is True
    assert certification["label_accuracy_verified"] is True


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
        {"name": "NSF Contents Certified", "verified": True, "source": "rules_db"}
    ]


def test_nsf_contents_certified_resolves_against_existing_nsf_173_registry_name() -> None:
    assert normalize_program("NSF Contents Certified") == "NSF Certified"


@pytest.mark.parametrize(
    ("label_text", "expected_programs", "expected_flags"),
    [
        (
            "Clean Label Project Certified",
            ["Clean Label Project Certified"],
            {"purity_verified": True, "heavy_metal_tested": True, "label_accuracy_verified": False},
        ),
        (
            "Labdoor Tested",
            ["Labdoor Tested"],
            {"purity_verified": True, "heavy_metal_tested": True, "label_accuracy_verified": True},
        ),
        (
            "GOED Certified",
            ["GOED Certified"],
            {"purity_verified": True, "heavy_metal_tested": True, "label_accuracy_verified": True},
        ),
        (
            "IFOS 5-Star",
            ["IFOS"],
            {"purity_verified": True, "heavy_metal_tested": True, "label_accuracy_verified": False},
        ),
        (
            "Informed Choice",
            ["Informed Choice"],
            {"purity_verified": True, "heavy_metal_tested": False, "label_accuracy_verified": False},
        ),
    ],
)
def test_quality_certification_capabilities_are_program_specific(
    label_text: str,
    expected_programs: list[str],
    expected_flags: dict[str, bool],
) -> None:
    certification = _certification_from_label(label_text)

    assert _program_names(certification) == expected_programs
    for flag, expected in expected_flags.items():
        assert certification[flag] is expected
