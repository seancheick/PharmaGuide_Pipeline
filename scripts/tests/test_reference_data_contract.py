"""Release contract for the canonical RDA/UL reference artifact."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from reference_data_contract import (  # noqa: E402
    ReferenceDataContractError,
    assert_emitted_reference_stamp,
    assert_semantic_parity,
    reference_stamp,
    semantic_rda_ul_fingerprint,
    validate_declared_reference_stamp,
)


def _rda_data(*, amount: object = 400, unit: str = "mcg DFE") -> dict:
    return {
        "_metadata": {
            "reference_data_contract": {
                "reference_version": "5.0.0-2026-06-28",
                "semantic_fingerprint": "placeholder",
            }
        },
        "nutrient_recommendations": [
            {
                "id": "folate",
                "standard_name": " Folate ",
                "unit": unit,
                "ul_status": "established",
                "ul_basis": "synthetic_only",
                "data": [
                    {
                        "group": "Female",
                        "age_range": "19-30",
                        "rda_ai": amount,
                        "ul": 1667,
                    }
                ],
            }
        ],
    }


def test_semantic_fingerprint_ignores_json_format_and_numeric_representation() -> None:
    canonical = _rda_data(amount=400, unit="mcg DFE")
    formatted_differently = _rda_data(amount="400.0", unit=" MCG   DFE ")

    assert semantic_rda_ul_fingerprint(canonical) == semantic_rda_ul_fingerprint(
        formatted_differently
    )


def test_semantic_parity_rejects_rda_ul_or_unit_drift() -> None:
    canonical = _rda_data()
    changed = copy.deepcopy(canonical)
    changed["nutrient_recommendations"][0]["data"][0]["ul"] = 1600

    with pytest.raises(ReferenceDataContractError, match="semantic fingerprints differ"):
        assert_semantic_parity(canonical, changed)

    changed = copy.deepcopy(canonical)
    changed["nutrient_recommendations"][0]["unit"] = "mg"
    with pytest.raises(ReferenceDataContractError, match="semantic fingerprints differ"):
        assert_semantic_parity(canonical, changed)


def test_semantic_fingerprint_covers_ul_form_scope_and_clinical_note() -> None:
    canonical = _rda_data()
    canonical["nutrient_recommendations"][0].update({
        "ul_note": "UL applies to both verified forms.",
        "ul_applies_to_forms": ["form a", "form b"],
    })

    changed_note = copy.deepcopy(canonical)
    changed_note["nutrient_recommendations"][0]["ul_note"] = (
        "UL applies only to form a."
    )
    assert semantic_rda_ul_fingerprint(
        canonical
    ) != semantic_rda_ul_fingerprint(changed_note)

    changed_scope = copy.deepcopy(canonical)
    changed_scope["nutrient_recommendations"][0]["ul_applies_to_forms"] = [
        "form a"
    ]
    assert semantic_rda_ul_fingerprint(
        canonical
    ) != semantic_rda_ul_fingerprint(changed_scope)


def test_semantic_fingerprint_covers_consumer_ul_warning_copy() -> None:
    canonical = _rda_data()
    canonical["consumer_ul_warnings"] = {
        "folate": {
            "message": "Too much folic acid can hide a vitamin B12 deficiency.",
            "source_url": "https://ods.od.nih.gov/factsheets/Folate-HealthProfessional/",
        }
    }
    changed = copy.deepcopy(canonical)
    changed["consumer_ul_warnings"]["folate"]["message"] = (
        "Different consumer conclusion"
    )

    assert semantic_rda_ul_fingerprint(
        canonical
    ) != semantic_rda_ul_fingerprint(changed)


def test_v5_1_contract_rejects_established_ul_without_consumer_copy() -> None:
    canonical = _rda_data()
    canonical["_metadata"]["schema_version"] = "5.1.0"
    canonical["_metadata"]["reference_data_contract"]["semantic_fingerprint"] = (
        semantic_rda_ul_fingerprint(canonical)
    )

    with pytest.raises(ReferenceDataContractError, match="consumer UL warning"):
        validate_declared_reference_stamp(canonical)


def test_canonical_reference_stamp_matches_its_semantic_fingerprint() -> None:
    path = Path(__file__).parent.parent / "data" / "rda_optimal_uls.json"
    data = json.loads(path.read_text())
    validate_declared_reference_stamp(data)


def test_emitted_reference_stamp_must_match_canonical_reference() -> None:
    canonical = _rda_data()
    canonical["_metadata"]["reference_data_contract"]["semantic_fingerprint"] = (
        semantic_rda_ul_fingerprint(canonical)
    )
    expected = reference_stamp(canonical)

    assert_emitted_reference_stamp(dict(expected), expected)

    with pytest.raises(ReferenceDataContractError, match="emitted RDA/UL"):
        assert_emitted_reference_stamp(
            {**expected, "reference_data_fingerprint": "sha256:stale"},
            expected,
        )
