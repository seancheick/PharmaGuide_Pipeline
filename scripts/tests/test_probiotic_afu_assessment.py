"""AFU label evidence is neither CFU nor proof of an inadequate dose."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from enrich_supplements_v3 import SupplementEnricherV3
from enhanced_normalizer import EnhancedDSLDNormalizer


@pytest.fixture(scope="module")
def seed_cleaned():
    path = Path(__file__).parents[2] / "manual_labels/product_submissions/PG_SUB_35E0BD3374BF494B80FEABE87FC559E7.json"
    return EnhancedDSLDNormalizer().normalize_product(json.loads(path.read_text()))


@pytest.fixture(scope="module")
def seed_pdata(seed_cleaned):
    return SupplementEnricherV3()._collect_probiotic_data(seed_cleaned)


def test_seed_afu_rows_survive_as_separate_measurements_not_cfu(seed_pdata):
    measurements = seed_pdata.get("afu_measurements", [])
    assert len(measurements) == 4
    assert [m["normalized_value"] for m in measurements] == pytest.approx(
        [37e9, 8.05e9, 3.3e9, 5.25e9]
    )
    assert all(m["normalized_unit"] == "AFU" for m in measurements)
    assert measurements[1]["normalized_value"] == 8_050_000_000
    assert seed_pdata["total_cfu"] == 0
    assert seed_pdata["total_strain_count"] == 24


def test_afu_cannot_receive_zero_dose_score_or_underdose_copy():
    from scoring_v4.modules.probiotic_dose import score_dose
    from scoring_v4.quality_score import _probiotic_dose_reason

    product = {"probiotic_data": {"afu_measurements": [{
        "source_row_ref": "ingredientRows[0]", "normalized_value": 37e9,
        "normalized_unit": "AFU", "assessment_status": "unresolved_reference",
    }]}}
    dose = score_dose(product)
    assert dose["score"] is None
    assert dose["metadata"]["assessment_status"] == "unresolved_reference"
    copy = _probiotic_dose_reason(dose, "Doses fall short of the amounts shown to work.")
    assert "AFU" in copy
    assert "fall short" not in copy


def test_unassessed_afu_blocks_dose_readiness_even_without_material_iqd_rows(seed_pdata):
    from assessment_readiness import _dose_readiness

    result = _dose_readiness({"probiotic_data": seed_pdata}, [], module="probiotic")
    assert result["readiness"] == "incomplete"
    assert result["reason_code"] == "probiotic_afu_reference_unavailable"
    assert len(result["incomplete_source_row_refs"]) == 4


def test_direct_module_assessment_preserves_unresolved_afu(seed_pdata):
    from scoring_v4.modules.probiotic import score_probiotic

    result = score_probiotic({"probiotic_data": seed_pdata})
    assert result.raw_score_100 is None
    assert result.score_100 is None
    assert result.metadata["score_unavailable_reason"] == "probiotic_afu_reference_unavailable"


def test_afu_display_projection_does_not_double_count_source_rows(seed_cleaned):
    from probiotic_measurements import collect_afu_measurements

    expected = collect_afu_measurements(seed_cleaned)
    assert len(expected) == 4
    display_only = deepcopy(seed_cleaned)
    display_only["activeIngredients"] = []
    assert collect_afu_measurements(display_only) == expected


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, 0, "unreadable"])
def test_invalid_afu_amount_is_unresolved_not_silently_dropped(value):
    from probiotic_measurements import collect_afu_measurements

    rows = collect_afu_measurements({"activeIngredients": [{
        "raw_source_path": "ingredientRows[0]", "quantity": value, "unit": "AFU",
    }]})
    assert len(rows) == 1
    assert rows[0]["normalized_value"] is None
    assert rows[0]["assessment_status"] == "invalid_amount"


def test_cfu_is_not_misread_as_afu():
    from probiotic_measurements import collect_afu_measurements

    assert collect_afu_measurements({"activeIngredients": [{
        "raw_source_path": "ingredientRows[0]", "quantity": 53.6, "unit": "Billion CFU",
    }]}) == []


@pytest.mark.parametrize("payload", [
    [{}], ["malformed"], {"wrong": "shape"},
    [{"source_row_ref": ["not", "a", "reference"]}],
])
def test_malformed_afu_contract_is_incomplete_not_ignored(payload):
    from assessment_readiness import _dose_readiness

    result = _dose_readiness({"probiotic_data": {"afu_measurements": payload}}, [], module="probiotic")
    assert result["readiness"] == "incomplete"
    assert result["incomplete_source_row_refs"]


def test_missing_cfu_is_not_reported_as_proven_underdose():
    from scoring_v4.quality_score import _probiotic_dose_reason

    copy = _probiotic_dose_reason({"metadata": {
        "window_proxy_reason": "per_strain_cfu_missing",
    }}, "Doses fall short of the amounts shown to work.")
    assert "could not be verified" in copy


def test_real_seed_pipeline_is_not_scored_but_label_measurements_export(seed_cleaned):
    from scoring_v4.scored_artifact import build_scored_artifact
    from build_final_db import build_detail_blob

    enriched, _ = SupplementEnricherV3().enrich_product(deepcopy(seed_cleaned))
    scored = build_scored_artifact(enriched)
    assert scored["_v4_scoring_engine_version"] == "4.3.1"
    assert scored["quality_score_status"] == "not_scored"
    assert scored["quality_score_v4_100"] is None
    assert scored["score_unavailable_reason"] == "probiotic_afu_reference_unavailable"
    assert scored["not_scorable_reason"] == "probiotic_afu_reference_unavailable"
    assert scored["assessment_readiness"]["dose"]["reason_code"] == "probiotic_afu_reference_unavailable"
    assert enriched["form_factor_canonical"] == "capsule"
    blob = build_detail_blob(enriched, scored)
    assert len(blob["probiotic_detail"]["afu_measurements"]) == 4
    assert blob["probiotic_detail"]["total_strain_count"] == 24


def test_cfu_only_detail_does_not_gain_empty_afu_payload():
    from build_final_db import build_detail_blob

    blob = build_detail_blob({"probiotic_data": {
        "is_probiotic_product": True, "total_billion_count": 10,
    }}, {})
    assert "afu_measurements" not in blob["probiotic_detail"]
