"""UL basis and notes in rda_optimal_uls.json must match the NIH ODS fact sheets.

Vitamin E: "The ULs apply to all forms of supplemental alpha-tocopherol, including the
eight stereoisomers present in synthetic vitamin E" -- natural RRR included
(https://ods.od.nih.gov/factsheets/VitaminE-HealthProfessional/, read 2026-10-03).
Manganese: ULs are "based on levels associated with whole-blood manganese concentrations
above the normal range ... and risk of neurotoxicity"
(https://ods.od.nih.gov/factsheets/Manganese-HealthProfessional/, read 2026-10-03).
Zinc: ULs "based on the levels of zinc that have an adverse effect on copper status".
Phosphorus: ULs "based on intakes associated with normal serum phosphate concentrations".
Fluoride: ULs "based on levels associated with dental and skeletal fluorosis".
Calcium: ULs "based on observational evidence from the WHI showing a link between higher
intakes of supplemental calcium ... and a greater risk of kidney stones".
(ods.od.nih.gov/factsheets/{Zinc,Phosphorus,Fluoride,Calcium}-HealthProfessional/, read 2026-10-03.)
The app renders these notes, so a wrong basis is a wrong consumer statement.
"""

import pytest

import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "rda_optimal_uls.json"
RECS = {r["id"]: r for r in json.loads(DATA.read_text())["nutrient_recommendations"]}


def test_vitamin_e_ul_covers_natural_and_synthetic_supplemental_forms():
    entry = RECS["vitamin_e"]
    assert entry["ul_basis"] == "supplemental_only"
    note = entry["ul_note"].lower()
    assert "synthetic alpha-tocopherol only" not in note
    assert "natural" in note and "synthetic" in note


def test_manganese_ul_basis_is_blood_manganese_not_inhalation():
    note = RECS["manganese"]["ul_note"].lower()
    assert "inhalation" not in note
    assert "whole-blood manganese" in note


@pytest.mark.parametrize("nutrient,required,obsolete", [
    ("zinc", "copper status", "immune dysfunction"),
    ("phosphorus", "serum phosphate", "calcium-phosphorus imbalance"),
    ("fluoride", "dental and skeletal fluorosis", None),
    ("calcium", "kidney stone", "cardiovascular"),
])
def test_ul_note_names_the_ods_basis(nutrient, required, obsolete):
    note = RECS[nutrient]["ul_note"].lower()
    assert required in note
    if obsolete:
        assert obsolete not in note
