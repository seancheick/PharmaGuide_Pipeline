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

from generate_pharmacist_review_packet import CONSUMER_VISIBLE_FIELD_NAMES


DATA_DIR = Path(__file__).parents[1] / "data"
SOURCE_PATH = DATA_DIR / "medication_depletions.json"
CLASSES_PATH = DATA_DIR / "drug_classes.json"
LEDGER_PATH = DATA_DIR / "medication_depletions_b1_signoff.json"
DELTA_LEDGER_PATH = DATA_DIR / "medication_depletions_b1_delta_signoff.json"

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

DELTA_RECORD_IDS = {
    "DEP_ANTACIDS_IRON",
    "DEP_ANTICOAGULANTS_VITAMINK",
    "DEP_CHOLESTYRAMINE_VITAMINA",
    "DEP_CHOLESTYRAMINE_VITAMIND",
    "DEP_CHOLESTYRAMINE_VITAMINE",
    "DEP_CHOLESTYRAMINE_VITAMINK",
    "DEP_LEVOTHYROXINE_CALCIUM",
    "DEP_LEVOTHYROXINE_IRON",
    "DEP_ORLISTAT_VITAMINA",
    "DEP_SSRIS_SODIUM",
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
    # Consumer-visible "From food" copy — see apply.py for why this was added.
    "food_sources_short",
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
    assert (
        ledger["_metadata"]["reviewer"]
        == ""
    )
    assert (
        ledger["_metadata"]["reviewer_type"]
        == "Licensed pharmacist clinical delta review requested"
    )
    assert ledger["_metadata"]["licensed_pharmacist_signoff_date"] is None
    assert ledger["_metadata"]["release_disposition"] == (
        "hold_pending_licensed_pharmacist_delta_review"
    )
    assert set(ledger["_metadata"]["delta_record_ids"]) == DELTA_RECORD_IDS
    assert ledger["_metadata"]["previous_signoff"] == {
        "reviewer": "Dr. Pham, PharmaGuide Clinical Team",
        "reviewer_type": "Licensed pharmacist clinical review",
        "licensed_pharmacist_signoff_date": "2026-07-27",
        "release_disposition": "approved_for_controlled_beta",
    }
    assert (
        ledger["_metadata"]["supporting_reviewer"]
        == "openai_codex_ai_clinical_audit"
    )


def test_active_records_preserve_prior_signoff_and_pin_pending_delta_copy():
    source = _load(SOURCE_PATH)
    ledger = _load(LEDGER_PATH)
    delta_ledger = _load(DELTA_LEDGER_PATH)
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
    assert set(delta_ledger["records"]) == DELTA_RECORD_IDS
    assert set(delta_ledger["delta_record_fingerprints"]) == DELTA_RECORD_IDS
    assert delta_ledger["_metadata"]["delta_record_count"] == len(DELTA_RECORD_IDS)
    assert delta_ledger["_metadata"]["licensed_pharmacist_signoff"] is False

    for record_id, expected in ledger["active_record_fingerprints"].items():
        record = by_id[record_id]
        assert record["b1_clinical_review_disposition"] in {
            "approved",
            "approved_with_wording_change",
        }
        assert record["b1_clinical_reviewed_at"] == "2026-07-27"
        assert record["b1_clinical_reviewer"] == "openai_codex_ai_clinical_audit"
        if record_id not in DELTA_RECORD_IDS:
            assert _record_fingerprint(record) == expected

    for record_id, expected in delta_ledger[
        "delta_record_fingerprints"
    ].items():
        assert _record_fingerprint(by_id[record_id]) == expected


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


def test_every_consumer_visible_field_is_inside_the_clinical_fingerprint():
    """What a user can read must be what the ledger pins.

    The packet's CONSUMER_VISIBLE_FIELDS is the single source of truth for
    "what a reviewer is approving". Any field in it that is NOT part of the
    fingerprint could be reworded after sign-off without tripping change
    control — which is exactly how the metformin/B12 "a supplement is often
    more reliable" line survived the B1 rewording pass and shipped.
    """
    escaped = CONSUMER_VISIBLE_FIELD_NAMES - set(CLINICAL_FIELDS)
    assert not escaped, (
        "consumer-visible fields outside the clinical fingerprint: "
        f"{sorted(escaped)}"
    )


# Copy that clinical review specifically retired: it tells a user that diet is
# inadequate and a supplement is the better option, with no testing or clinician
# gate.  That framing contradicts test-first guidance (MHRA/ADA for metformin),
# and self-starting B12 before a draw makes serum B12 and MMA uninterpretable —
# it can mask the very deficiency the record exists to surface.
#
# This is a regression gate on known-retired wording, NOT a general tone
# detector.  Clinician- or label-directed supplementation is legitimate and must
# keep passing: isoniazid/pyridoxine co-therapy, the methotrexate folate
# schedule, and the orlistat multivitamin timing all say so and are all fine.
RETIRED_CONSUMER_PHRASES = (
    "food sources may not be enough",
    "supplement is often more reliable",
    "a supplement is more reliable",
)


def test_consumer_visible_records_never_carry_retired_supplementation_copy():
    """A suppressed record must not smuggle retired copy in on promotion.

    `DEP_ANTACIDS_VITAMINB12` still carries the exact phrasing removed from
    `DEP_METFORMIN_VITAMINB12`.  It is suppressed today, so no user sees it and
    this test passes.  The moment it is promoted to `verified` without the copy
    being rewritten, this fails — which is the point.  Fix the wording as part
    of that record's evidence revision, not by loosening this gate.
    """
    records = _load(SOURCE_PATH)["depletions"]
    offenders = [
        (record.get("id"), field, phrase)
        for record in records
        if record.get("citation_review_status") == "verified"
        for field in sorted(CONSUMER_VISIBLE_FIELD_NAMES)
        for phrase in RETIRED_CONSUMER_PHRASES
        if phrase in str(record.get(field) or "").lower()
    ]
    assert not offenders, (
        "consumer-visible records carry retired supplementation copy: "
        f"{offenders}"
    )
