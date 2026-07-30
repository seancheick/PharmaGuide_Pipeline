"""Regression locks for the post-sign-off B1 clinical-copy correction.

These assertions pin claims that were rechecked against the cited primary
sources after the original B1 review. They intentionally inspect the authored
record users receive, not an audit-script implementation detail.
"""

from __future__ import annotations

import json
from pathlib import Path


DATA_PATH = Path(__file__).parents[1] / "data" / "medication_depletions.json"


def _records() -> dict[str, dict]:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return {row["id"]: row for row in payload["depletions"]}


def test_levothyroxine_iron_describes_campbell_as_uncontrolled():
    record = _records()["DEP_LEVOTHYROXINE_IRON"]
    copy = " ".join(
        str(record.get(field) or "")
        for field in ("mechanism", "clinical_impact", "citation_review_note")
    ).lower()

    assert "controlled trial" not in copy
    assert "uncontrolled" in copy
    assert "14 patients" in copy
    assert "12-week" in copy
    assert "300 mg" in record["mechanism"]
    assert "mIU/L" in record["mechanism"]
    assert "mU/L" not in record["mechanism"]


def test_levothyroxine_calcium_uses_the_patient_cohort_and_product_scope():
    record = _records()["DEP_LEVOTHYROXINE_CALCIUM"]
    copy = " ".join(
        str(record.get(field) or "")
        for field in (
            "clinical_impact",
            "recommendation",
            "monitoring_note",
            "monitoring_tip_short",
        )
    ).lower()

    assert "calcium-rich meals" not in copy
    assert "84%" not in copy
    assert "58%" not in copy
    assert "20 patients" in record["clinical_impact"].lower()
    assert "1.6 to 2.7" in record["clinical_impact"]
    assert "20%" in record["clinical_impact"]
    assert "supplements or calcium-containing medicines" in copy
    assert "30 to 60 minutes before breakfast" in record["recommendation"]
    assert "thyroid testing" in record["monitoring_tip_short"].lower()
    assert "starting or stopping" in record["monitoring_tip_short"].lower()


def test_furosemide_thiamine_tip_does_not_presume_specialist_or_nudge_a_dose():
    record = _records()["DEP_DIURETICS_THIAMINE"]
    tip = record["monitoring_tip_short"].lower()

    assert "cardiologist" not in tip
    assert "thiamine supplement" not in tip
    assert "treating clinician" in tip
    assert "assessment" in tip


def test_acid_suppression_iron_does_not_claim_complete_reversal():
    record = _records()["DEP_ANTACIDS_IRON"]
    copy = " ".join(
        str(record.get(field) or "")
        for field in ("mechanism", "clinical_impact", "monitoring_note")
    ).lower()

    assert "reverses after stopping" not in copy
    assert "became weaker" in record["mechanism"].lower()
    assert "does not mean" in record["mechanism"].lower()
    assert "will always reverse" in record["mechanism"].lower()
    assert "annually" not in record["monitoring_note"].lower()
    assert "symptom" in record["monitoring_note"].lower()
    assert "risk" in record["monitoring_note"].lower()
    assert "do not stop the acid reducer" in record["recommendation"].lower()
    assert any(
        "gut.bmj.com/content/70/11/2030" in source["url"]
        for source in record["sources"]
    ), "BSG adult IDA diagnostic guideline is not cited"
    assert "stronger for ppis than h2 blockers" in record["clinical_impact"].lower()
    assert "among ppi users" in record["clinical_impact"].lower()
    hutchinson = next(
        source
        for source in record["sources"]
        if source["url"] == "https://pubmed.ncbi.nlm.nih.gov/17344278/"
    )
    assert "mechanistic" in hutchinson["label"].lower()
    assert "hereditary haemochromatosis" in hutchinson["label"].lower()


def test_warfarin_vitamin_k_uses_days_and_immediate_mechanism_copy():
    record = _records()["DEP_ANTICOAGULANTS_VITAMINK"]

    assert record["onset_timeline"] == "days"
    assert "over time" not in record["alert_body"].lower()
    assert "within days" in record["alert_body"].lower()
    assert "intended" in record["alert_body"].lower()
    assert record["drug_ref"]["type"] == "drug"
    assert record["drug_ref"]["id"] == "11289"


def test_furosemide_thiamine_remains_direct_drug_scoped():
    record = _records()["DEP_DIURETICS_THIAMINE"]

    assert record["drug_ref"]["type"] == "drug"
    assert record["drug_ref"]["id"] == "4603"
    assert "furosemide" in record["drug_ref"]["display_name"].lower()


def test_ssri_sodium_copy_does_not_validate_self_supplementation():
    record = _records()["DEP_SSRIS_SODIUM"]

    assert record["depletion_type"] == "monitoring_stability"
    assert not record["acknowledgement_note"].lower().startswith("good")
    assert "supplements do not prevent" in record["acknowledgement_note"].lower()
    assert "self-supplementing sodium" in record["recommendation"].lower()
    assert "do not stop or change your antidepressant on your own" in record[
        "recommendation"
    ].lower()
    assert "contact your prescriber" in record["recommendation"].lower()
    assert "over time" not in record["alert_body"].lower()
    assert "first weeks" in record["alert_body"].lower()
    for field in ("clinical_impact", "monitoring_note", "alert_body"):
        assert "increasing" not in record[field].lower()
    urls = {source["url"] for source in record["sources"]}
    assert "https://pubmed.ncbi.nlm.nih.gov/27194321/" in urls
    assert any(
        "4883ccdf-0e02-579d-e054-00144ff88e88" in url
        for url in urls
    )


def test_vitamin_a_cards_include_pregnancy_and_preformed_form_safety():
    records = _records()
    for record_id in ("DEP_ORLISTAT_VITAMINA", "DEP_CHOLESTYRAMINE_VITAMINA"):
        record = records[record_id]
        guidance = " ".join(
            str(record.get(field) or "")
            for field in (
                "clinical_impact",
                "recommendation",
                "acknowledgement_note",
                "monitoring_tip_short",
            )
        ).lower()
        source_urls = {source["url"] for source in record["sources"]}

        assert "pregnan" in guidance
        assert "preformed vitamin a" in guidance
        assert "total dose" in guidance
        assert not record["acknowledgement_note"].lower().startswith("good")
        assert (
            "https://ods.od.nih.gov/factsheets/VitaminA-HealthProfessional/"
            in source_urls
        )

    assert "2 hours" in records["DEP_ORLISTAT_VITAMINA"]["recommendation"]
    orlistat_action = records["DEP_ORLISTAT_VITAMINA"]["recommendation"]
    assert "such as at bedtime" in orlistat_action
    assert "Do not add extra vitamin A" in orlistat_action
    assert "not for use during pregnancy" in orlistat_action
    assert "pregnant or think you may be pregnant" in orlistat_action
    assert "medication-safety issue" in records["DEP_ORLISTAT_VITAMINA"][
        "clinical_impact"
    ]
    assert "not a vitamin-dose adjustment" in records["DEP_ORLISTAT_VITAMINA"][
        "clinical_impact"
    ]
    assert "assumes you are not pregnant" in records["DEP_ORLISTAT_VITAMINA"][
        "acknowledgement_note"
    ]
    assert "review the vitamin a form and total dose" not in " ".join(
        [
            records["DEP_ORLISTAT_VITAMINA"]["clinical_impact"],
            records["DEP_ORLISTAT_VITAMINA"]["recommendation"],
        ]
    ).lower()
    assert (
        "water-miscible"
        in records["DEP_CHOLESTYRAMINE_VITAMINA"]["recommendation"].lower()
    )


def test_cholestyramine_vitamin_k_uses_specific_clotting_test_language():
    record = _records()["DEP_CHOLESTYRAMINE_VITAMINK"]

    assert "PT/INR" in record["monitoring_tip_short"]
    assert "long-term" in record["monitoring_tip_short"]


def test_all_cholestyramine_cards_carry_label_specific_form_and_timing():
    records = _records()
    for record_id in (
        "DEP_CHOLESTYRAMINE_VITAMINA",
        "DEP_CHOLESTYRAMINE_VITAMIND",
        "DEP_CHOLESTYRAMINE_VITAMINE",
        "DEP_CHOLESTYRAMINE_VITAMINK",
    ):
        record = records[record_id]
        recommendation = record["recommendation"].lower()

        assert "water-miscible" in recommendation
        assert "1 hour before" in recommendation
        assert "4\u20136 hours after" in recommendation
        assert "timing vitamins apart can help" not in record["alert_body"].lower()
        assert not record["acknowledgement_note"].lower().startswith("good")


def test_levothyroxine_calcium_keeps_product_and_meal_timing_distinct():
    recommendation = _records()["DEP_LEVOTHYROXINE_CALCIUM"]["recommendation"]

    assert "at least 4 hours before or after levothyroxine" in recommendation
    assert "Continue taking levothyroxine on an empty stomach" in recommendation
    assert "30 to 60 minutes before breakfast" in recommendation
    assert "The 4-hour rule applies to calcium supplements and medicines" in recommendation
    assert "ask your clinician if you are unsure how your usual meals fit around it" in recommendation


def test_b11_wording_delta_stays_fail_closed():
    records = _records()
    ppi_magnesium = records["DEP_ANTACIDS_MAGNESIUM"]
    diuretic_potassium = records["DEP_DIURETICS_POTASSIUM"]

    assert ppi_magnesium["onset_timeline"] == "variable"
    assert "most reports follow a year or more" in ppi_magnesium["alert_body"].lower()
    assert "cases have occurred earlier" in ppi_magnesium["alert_body"].lower()
    assert "potassium product" in diuretic_potassium[
        "acknowledgement_note"
    ].lower()
    assert "over-the-counter" in diuretic_potassium[
        "acknowledgement_note"
    ].lower()
    assert "depends on your labs" in diuretic_potassium[
        "acknowledgement_note"
    ].lower()

    for record_id in (
        "DEP_ANTACIDS_VITAMINB12",
        "DEP_ANTACIDS_MAGNESIUM",
        "DEP_DIURETICS_POTASSIUM",
        "DEP_DIURETICS_MAGNESIUM",
    ):
        assert records[record_id]["citation_review_status"] == "needs_revision"
