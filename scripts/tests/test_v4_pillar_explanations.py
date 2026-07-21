from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scoring_v4.pillar_explanations import (  # noqa: E402
    PILLAR_EXPLANATION_SCHEMA_VERSION,
    attach_pillar_explanations,
)


def _cfg():
    return {
        "pillars": {
            "Formulation": {"weight": 25, "assembler": "formulation"},
            "Dose": {"weight": 20, "assembler": "dose"},
            "Evidence": {"weight": 15, "assembler": "evidence"},
        }
    }


def _module_bd(per_day_mid_mg=660.0, form="ee"):
    return {
        "dimensions": {
            "formulation": {"score": 12.0, "max": 25, "metadata": {"form_detected": form}},
            "dose": {"score": 18.0, "max": 20, "metadata": {"per_day_mid_mg": per_day_mid_mg}},
            "evidence": {"score": 10.0, "max": 15, "metadata": {}},
        }
    }


def _pillars():
    return {
        "Formulation": {"score": 12.0, "max": 25, "reason": "Well-formulated."},
        "Dose": {"score": 18.0, "max": 20, "reason": "Strong daily dose."},
        "Evidence": {"score": 10.0, "max": 15, "reason": "Moderate evidence."},
    }


def _generic_cfg():
    return {
        "pillars": {
            "Evidence": {"weight": 20, "assembler": "evidence"},
            "Transparency": {"weight": 15, "source_dim": "transparency"},
        }
    }


def _generic_pillars(evidence_score=0.0):
    return {
        "Evidence": {"score": evidence_score, "max": 20, "reason": "Evidence reason."},
        "Transparency": {"score": 0.0, "max": 15, "reason": "Transparency reason."},
    }


def _generic_module_bd(*, matched_entries=0, blend_counts=None):
    blend_evidence = [
        {"blend_name": f"Blend {index + 1}", "children_without_amount_count": count}
        for index, count in enumerate(blend_counts or [])
    ]
    return {
        "dimensions": {
            "evidence": {"score": 0.0, "max": 20, "metadata": {"matched_entries": matched_entries}},
            "transparency": {
                "score": 0.0,
                "max": 10,
                "metadata": {"B5_blend_evidence": blend_evidence},
            },
        }
    }


def test_omega_dose_pillar_emits_epa_dha_per_day_fact():
    pillars = attach_pillar_explanations(_pillars(), _module_bd(per_day_mid_mg=660.0), _cfg(), "omega")
    explanation = pillars["Dose"]["explanation"]
    assert explanation["schema_version"] == 1
    fact = explanation["facts"][0]
    assert fact["id"] == "epa_dha_per_day"
    assert fact["value_mg"] == 660.0
    assert fact["value_display"] == "660 mg/day"


def test_omega_formulation_pillar_emits_detected_form_fact():
    pillars = attach_pillar_explanations(_pillars(), _module_bd(form="ee"), _cfg(), "omega")
    fact = pillars["Formulation"]["explanation"]["facts"][0]
    assert fact["id"] == "omega_form"
    assert fact["value"] == "ee"
    assert fact["value_display"] == "Ethyl ester"


def test_schema_version_constant_is_one_and_ids_are_stable():
    assert PILLAR_EXPLANATION_SCHEMA_VERSION == 1
    pillars = attach_pillar_explanations(_pillars(), _module_bd(), _cfg(), "omega")
    ids = {
        pillars["Dose"]["explanation"]["facts"][0]["id"],
        pillars["Formulation"]["explanation"]["facts"][0]["id"],
    }
    assert ids == {"epa_dha_per_day", "omega_form"}


def test_absent_dose_metadata_emits_no_fact():
    bd = _module_bd()
    bd["dimensions"]["dose"]["metadata"] = {}  # no per_day_mid_mg
    pillars = attach_pillar_explanations(_pillars(), bd, _cfg(), "omega")
    assert "explanation" not in pillars["Dose"]


def test_undefined_form_emits_no_fact():
    pillars = attach_pillar_explanations(_pillars(), _module_bd(form="undefined"), _cfg(), "omega")
    assert "explanation" not in pillars["Formulation"]


def test_non_omega_module_keeps_reason_only_pillars():
    pillars = attach_pillar_explanations(_pillars(), _module_bd(), _cfg(), "generic")
    assert all("explanation" not in p for p in pillars.values())


def test_attach_never_changes_score_max_or_reason():
    before = _pillars()
    snapshot = copy.deepcopy(before)
    after = attach_pillar_explanations(before, _module_bd(), _cfg(), "omega")
    for name, pillar in after.items():
        for key in ("score", "max", "reason"):
            assert pillar[key] == snapshot[name][key], f"{name}.{key} changed"


def test_generic_transparency_emits_sku_282638_shaped_blend_facts_in_order():
    before = _generic_pillars()
    snapshot = copy.deepcopy(before)

    pillars = attach_pillar_explanations(
        before,
        _generic_module_bd(blend_counts=[14, 13, 15, 12]),
        _generic_cfg(),
        "generic",
    )

    explanation = pillars["Transparency"]["explanation"]
    assert explanation["schema_version"] == 1
    assert explanation["facts"] == [
        {
            "id": "proprietary_blend_count",
            "label": "Proprietary blends",
            "value_display": "4",
        },
        {
            "id": "undisclosed_ingredient_amount_count",
            "label": "Ingredient amounts not disclosed",
            "value_display": "54",
        },
    ]
    for name, pillar in pillars.items():
        for key in ("score", "max", "reason"):
            assert pillar[key] == snapshot[name][key], f"{name}.{key} changed"


def test_zero_evidence_pillar_emits_current_data_fact():
    pillars = attach_pillar_explanations(
        _generic_pillars(evidence_score=0.0),
        _generic_module_bd(matched_entries=0),
        _generic_cfg(),
        "generic",
    )

    assert pillars["Evidence"]["explanation"] == {
        "schema_version": 1,
        "facts": [
            {
                "id": "matched_evidence_records",
                "label": "Qualifying evidence matches",
                "value_display": "0 in PharmaGuide's current evidence data",
            }
        ],
    }


@pytest.mark.parametrize(
    "metadata",
    [
        {},
        {"B5_blend_evidence": []},
        {"B5_blend_evidence": [{}]},
        {"B5_blend_evidence": [{"children_without_amount_count": True}]},
        {"B5_blend_evidence": [{"children_without_amount_count": "4"}]},
        {"B5_blend_evidence": [{"children_without_amount_count": 4.0}]},
        {"B5_blend_evidence": [{"children_without_amount_count": -1}]},
        {"B5_blend_evidence": [None]},
    ],
)
def test_malformed_or_incomplete_b5_metadata_emits_no_transparency_facts(metadata):
    bd = _generic_module_bd()
    bd["dimensions"]["transparency"]["metadata"] = metadata

    pillars = attach_pillar_explanations(_generic_pillars(), bd, _generic_cfg(), "generic")

    assert "explanation" not in pillars["Transparency"]


@pytest.mark.parametrize(
    "metadata",
    [
        {},
        None,
        [],
        {"matched_entries": 1},
        {"matched_entries": -1},
        {"matched_entries": True},
        {"matched_entries": False},
        {"matched_entries": "0"},
        {"matched_entries": 0.0},
        {"matched_entries": None},
    ],
)
def test_nonzero_or_malformed_evidence_metadata_emits_no_evidence_fact(metadata):
    bd = _generic_module_bd()
    bd["dimensions"]["evidence"]["metadata"] = metadata

    pillars = attach_pillar_explanations(
        _generic_pillars(evidence_score=0.0),
        bd,
        _generic_cfg(),
        "generic",
    )

    assert "explanation" not in pillars["Evidence"]


def test_zero_matched_entries_emits_no_fact_when_public_evidence_score_is_nonzero():
    pillars = attach_pillar_explanations(
        _generic_pillars(evidence_score=0.1),
        _generic_module_bd(matched_entries=0),
        _generic_cfg(),
        "generic",
    )

    assert "explanation" not in pillars["Evidence"]
