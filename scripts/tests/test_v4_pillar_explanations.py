from __future__ import annotations

import copy
import sys
from pathlib import Path

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


def test_omega_dose_pillar_emits_epa_dha_per_day_fact():
    pillars = attach_pillar_explanations(_pillars(), _module_bd(per_day_mid_mg=660.0), _cfg(), "omega")
    explanation = pillars["Dose"]["explanation"]
    assert explanation["schema_version"] == 1
    fact = explanation["facts"][0]
    assert fact["id"] == "epa_dha_per_day"
    assert fact["value_mg"] == 660.0
    assert "660" in fact["display"] and "mg" in fact["display"]


def test_omega_formulation_pillar_emits_detected_form_fact():
    pillars = attach_pillar_explanations(_pillars(), _module_bd(form="ee"), _cfg(), "omega")
    fact = pillars["Formulation"]["explanation"]["facts"][0]
    assert fact["id"] == "omega_form"
    assert fact["value"] == "ee"
    assert fact["display"] == "Ethyl ester"


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
