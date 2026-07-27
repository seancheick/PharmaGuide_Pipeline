"""Release locks for the final B1 medication-nutrient clinical review.

The sign-off ledger pins both consumer-visible clinical copy and the exact
membership of every referenced drug class.  A future edit therefore has to
update the evidence review deliberately; changing a citation, widening a
class, or promoting a suppressed record cannot silently pass.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


DATA_DIR = Path(__file__).parents[1] / "data"
SOURCE_PATH = DATA_DIR / "medication_depletions.json"
CLASSES_PATH = DATA_DIR / "drug_classes.json"
LEDGER_PATH = DATA_DIR / "medication_depletions_b1_signoff.json"

REVIEW_SCOPE = {
    "DEP_ANTACIDS_CALCIUM",
    "DEP_ANTACIDS_IRON",
    "DEP_ANTICOAGULANTS_VITAMINK",
    "DEP_ANTICONVULSANTS_CALCIUM",
    "DEP_ANTICONVULSANTS_FOLATE",
    "DEP_ANTICONVULSANTS_LCARNITINE",
    "DEP_ANTICONVULSANTS_VITAMINB12",
    "DEP_ANTICONVULSANTS_VITAMIND",
    "DEP_ANTICONVULSANTS_VITAMINK",
    "DEP_CHOLESTYRAMINE_VITAMINA",
    "DEP_CHOLESTYRAMINE_VITAMIND",
    "DEP_CHOLESTYRAMINE_VITAMINE",
    "DEP_CHOLESTYRAMINE_VITAMINK",
    "DEP_COLCHICINE_VITAMINB12",
    "DEP_CORTICOSTEROIDS_CALCIUM",
    "DEP_CORTICOSTEROIDS_VITAMIND",
    "DEP_DIURETICS_CALCIUM",
    "DEP_DIURETICS_FOLATE",
    "DEP_DIURETICS_THIAMINE",
    "DEP_DIURETICS_ZINC",
    "DEP_ISONIAZID_VITAMINB6",
    "DEP_LEVOTHYROXINE_CALCIUM",
    "DEP_LEVOTHYROXINE_IRON",
    "DEP_METFORMIN_VITAMINB12",
    "DEP_METHOTREXATE_FOLATE",
    "DEP_OCP_VITAMINB6",
    "DEP_ORLISTAT_VITAMINA",
    "DEP_ORLISTAT_VITAMIND",
    "DEP_ORLISTAT_VITAMINE",
    "DEP_ORLISTAT_VITAMINK",
    "DEP_SSRIS_SODIUM",
    "DEP_STATINS_COQ10",
    "DEP_SULFASALAZINE_FOLATE",
}

DISPOSITIONS = {
    "approved",
    "approved_with_wording_change",
    "requires_evidence_revision",
    "remove_from_release",
}

CLINICAL_FIELDS = (
    "id",
    "drug_ref",
    "depleted_nutrient",
    "depletion_type",
    "severity",
    "mechanism",
    "clinical_impact",
    "recommendation",
    "onset_timeline",
    "evidence_level",
    "monitoring_note",
    "sources",
    "alert_headline",
    "alert_body",
    "acknowledgement_note",
    "monitoring_tip_short",
    "citation_review_status",
    "reviewed_at",
    "reviewer",
    "citation_review_note",
    "b1_clinical_review_disposition",
    "b1_clinical_reviewed_at",
    "b1_clinical_reviewer",
    "b1_clinical_review_note",
)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(value) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _record_fingerprint(record: dict) -> str:
    return _sha256({field: record.get(field) for field in CLINICAL_FIELDS})


def _class_fingerprint(drug_class: dict) -> str:
    return _sha256(
        {
            "member_rxcuis": drug_class.get("member_rxcuis", []),
            "member_names": drug_class.get("member_names", []),
        }
    )


def test_b1_signoff_ledger_covers_every_reviewed_record_once():
    ledger = _load(LEDGER_PATH)
    records = ledger["records"]

    assert set(records) == REVIEW_SCOPE
    assert {row["disposition"] for row in records.values()} <= DISPOSITIONS
    assert ledger["_metadata"]["review_scope_count"] == 33
    assert ledger["_metadata"]["reviewed_at"] == "2026-07-27"
    assert ledger["_metadata"]["licensed_pharmacist_signoff"] is False


def test_active_records_are_signed_off_and_clinically_fingerprinted():
    source = _load(SOURCE_PATH)
    ledger = _load(LEDGER_PATH)
    by_id = {row["id"]: row for row in source["depletions"]}
    active = {
        row["id"]: row
        for row in source["depletions"]
        if row.get("citation_review_status") == "verified"
    }
    signed_active = {
        record_id
        for record_id, review in ledger["records"].items()
        if review["disposition"] in {"approved", "approved_with_wording_change"}
    }

    assert set(active) == signed_active
    assert len(active) == 31
    assert set(ledger["active_record_fingerprints"]) == set(active)

    for record_id, expected in ledger["active_record_fingerprints"].items():
        record = by_id[record_id]
        assert record["b1_clinical_review_disposition"] in {
            "approved",
            "approved_with_wording_change",
        }
        assert record["b1_clinical_reviewed_at"] == "2026-07-27"
        assert record["b1_clinical_reviewer"] == "openai_codex_ai_clinical_audit"
        assert _record_fingerprint(record) == expected


def test_nonapproved_dispositions_fail_closed():
    source = _load(SOURCE_PATH)
    ledger = _load(LEDGER_PATH)
    by_id = {row["id"]: row for row in source["depletions"]}

    for record_id, review in ledger["records"].items():
        record = by_id[record_id]
        disposition = review["disposition"]
        assert record["b1_clinical_review_disposition"] == disposition
        if disposition == "requires_evidence_revision":
            assert record["citation_review_status"] == "needs_revision"
        elif disposition == "remove_from_release":
            assert record["citation_review_status"] == "rejected"


def test_active_drug_class_membership_is_immutable_without_rereview():
    source = _load(SOURCE_PATH)
    classes = _load(CLASSES_PATH)["classes"]
    ledger = _load(LEDGER_PATH)
    active_class_ids = {
        row["drug_ref"]["id"]
        for row in source["depletions"]
        if row.get("citation_review_status") == "verified"
        and row["drug_ref"]["type"] == "class"
    }

    assert set(ledger["active_class_fingerprints"]) == active_class_ids
    for class_id, expected in ledger["active_class_fingerprints"].items():
        assert _class_fingerprint(classes[class_id]) == expected


def test_final_scope_and_safety_copy_locks():
    source = _load(SOURCE_PATH)
    by_id = {row["id"]: row for row in source["depletions"]}

    warfarin = by_id["DEP_ANTICOAGULANTS_VITAMINK"]
    assert warfarin["drug_ref"] == {
        "type": "drug",
        "id": "11289",
        "display_name": "Warfarin (anticoagulant / blood thinner)",
    }
    assert "vascular calcification" not in warfarin["clinical_impact"].lower()
    assert "osteoporosis" not in warfarin["clinical_impact"].lower()

    for record_id in (
        "DEP_CORTICOSTEROIDS_CALCIUM",
        "DEP_CORTICOSTEROIDS_VITAMIND",
    ):
        assert by_id[record_id]["drug_ref"]["type"] == "drug"
        assert by_id[record_id]["drug_ref"]["id"] == "8640"
        assert "long-term oral prednisone" in by_id[record_id]["drug_ref"][
            "display_name"
        ].lower()

    assert by_id["DEP_OCP_VITAMINB6"]["citation_review_status"] == "needs_revision"
    assert (
        by_id["DEP_ANTICONVULSANTS_VITAMINK"]["citation_review_status"]
        == "rejected"
    )

    metformin = by_id["DEP_METFORMIN_VITAMINB12"]
    assert "all patients" not in metformin["recommendation"].lower()
    assert "sublingual methylcobalamin" not in metformin["recommendation"].lower()
    assert "multifactorial" in metformin["mechanism"].lower()

    ssri = by_id["DEP_SSRIS_SODIUM"]
    assert "directly stimulates" not in ssri["mechanism"].lower()
    assert "should be checked" not in ssri["recommendation"].lower()

    zinc = by_id["DEP_DIURETICS_ZINC"]
    assert "10-15 mg/day" not in zinc["recommendation"]
    assert "routine zinc supplement" in zinc["recommendation"].lower()

    levothyroxine = by_id["DEP_LEVOTHYROXINE_CALCIUM"]
    assert "calcium-rich meals" not in levothyroxine["recommendation"].lower()
