"""Interaction-rule corrections from the PR #184 warning audit (2026-10-20), verified by content.

1. Iron / antihypertensives: the evidence is drug-specific. PMID 9803987 (captopril + ferrous
   sulphate): unconjugated captopril AUC fell 37%, "no significant differences in systolic and
   diastolic blood pressures". PMID 3356082 (methyldopa + ferrous sulfate/gluconate): absorption
   fell and blood pressure rose in 4 of 5 hypertensive patients. No class-wide claim.
2. Iron / liver disease: scoped to iron-overload conditions. NIH ODS Iron fact sheet: AASLD
   recommends that treatment of hemochromatosis include avoiding iron and vitamin C supplements
   (AASLD 2011 guideline, PMID 21452290). PMID 33676282 (CoQ10 in hemochromatosis) did not
   support the claim and is dropped.
3. Calcium / pregnancy-lactation: was unsourced. NIH ODS Calcium fact sheet (updated 2026-06-22):
   RDA 1,000 mg (19-50 y), UL 2,500 mg (19-50 y), the same in pregnancy and lactation.
"""

import json
from pathlib import Path

import pytest

RULES = json.loads(
    (Path(__file__).parent.parent / "data" / "ingredient_interaction_rules.json").read_text()
)["interaction_rules"]


def _rule(rule_id):
    return next(rule for rule in RULES if rule["id"] == rule_id)


def _consumer_copy(block):
    return " ".join(str(block.get(k) or "") for k in ("alert_headline", "alert_body", "action", "informational_note"))


def test_iron_antihypertensive_copy_names_the_studied_drugs_and_no_class_claim():
    block = next(item for item in _rule("RULE_IQM_IRON_HYPERTENSION")["drug_class_rules"]
                 if item["drug_class_id"] == "antihypertensives")
    copy = _consumer_copy(block)
    assert "methyldopa" in block["alert_headline"].lower() and "captopril" in block["alert_headline"].lower()
    assert "May affect blood-pressure control" not in copy
    assert "Iron can affect blood pressure" not in copy
    assert "2 hours" not in copy  # neither study tested a spacing interval
    assert set(block["sources"]) == {
        "https://pubmed.ncbi.nlm.nih.gov/9803987/",
        "https://pubmed.ncbi.nlm.nih.gov/3356082/",
    }


def test_iron_liver_disease_is_scoped_to_iron_overload_with_sources():
    block = next(item for item in _rule("RULE_IQM_IRON_HYPERTENSION")["condition_rules"]
                 if item["condition_id"] == "liver_disease")
    copy = _consumer_copy(block).lower()
    assert "hemochromatosis" in copy
    assert "monitor ferritin and transferrin saturation" not in copy
    assert "https://pubmed.ncbi.nlm.nih.gov/33676282/" not in block["sources"]
    assert "https://ods.od.nih.gov/factsheets/Iron-HealthProfessional/" in block["sources"]
    assert "https://pubmed.ncbi.nlm.nih.gov/21452290/" in block["sources"]


def test_calcium_pregnancy_entry_is_sourced():
    block = _rule("RULE_IQM_CALCIUM")["pregnancy_lactation"]
    assert block["sources"] == ["https://ods.od.nih.gov/factsheets/Calcium-HealthProfessional/"]
    assert "Standard nutrient" not in block["alert_headline"]
    assert "1,000 mg" in block["alert_body"] and "2,500 mg" in block["alert_body"]
    # The gate matches either stage, so the copy names both.
    assert "pregnancy" in block["alert_headline"].lower() and "breastfeeding" in block["alert_headline"].lower()
