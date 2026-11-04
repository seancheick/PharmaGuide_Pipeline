"""A9: every clinician-team-approved medication-nutrient record, source to app.

The app's reviewer goldens pin two records, and one of them (warfarin) is still
pending its delta review. This walks the whole approved set from the signed
source through the release artifact to the bundled asset. The review states come
from the source and its sign-off ledgers; nothing here adds or changes a review.
"""
import json
import os
from pathlib import Path

import pytest

from build_medication_depletions_artifact import TOP_LEVEL_KEY, build_artifact
from generate_pharmacist_review_packet import CONSUMER_VISIBLE_FIELD_NAMES

DATA = Path(__file__).parents[1] / "data"
FLUTTER_ROOT = Path(os.environ.get("FLUTTER_REPO", "/Users/seancheick/PharmaGuide ai"))
ASSET = FLUTTER_ROOT / "assets" / "reference_data" / "medication_depletions.json"

APPROVED = {
    "DEP_ANTACIDS_CALCIUM", "DEP_ANTICONVULSANTS_CALCIUM", "DEP_ANTICONVULSANTS_FOLATE",
    "DEP_ANTICONVULSANTS_LCARNITINE", "DEP_ANTICONVULSANTS_VITAMINB12",
    "DEP_ANTICONVULSANTS_VITAMIND", "DEP_COLCHICINE_VITAMINB12", "DEP_CORTICOSTEROIDS_CALCIUM",
    "DEP_CORTICOSTEROIDS_VITAMIND", "DEP_DIURETICS_CALCIUM", "DEP_DIURETICS_FOLATE",
    "DEP_DIURETICS_ZINC", "DEP_ISONIAZID_VITAMINB6", "DEP_METFORMIN_VITAMINB12",
    "DEP_METHOTREXATE_FOLATE", "DEP_ORLISTAT_VITAMIND", "DEP_ORLISTAT_VITAMINE",
    "DEP_ORLISTAT_VITAMINK", "DEP_STATINS_COQ10", "DEP_SULFASALAZINE_FOLATE",
}
# Listed for Dr Pham: live consumer copy whose final review is still open.
PENDING_REVIEW = {
    "DEP_ANTACIDS_IRON", "DEP_ANTICOAGULANTS_VITAMINK", "DEP_CHOLESTYRAMINE_VITAMINA",
    "DEP_CHOLESTYRAMINE_VITAMIND", "DEP_CHOLESTYRAMINE_VITAMINE", "DEP_CHOLESTYRAMINE_VITAMINK",
    "DEP_DIURETICS_THIAMINE", "DEP_LEVOTHYROXINE_CALCIUM", "DEP_LEVOTHYROXINE_IRON",
    "DEP_ORLISTAT_VITAMINA", "DEP_SSRIS_SODIUM",
}


def _source():
    return json.loads((DATA / "medication_depletions.json").read_text(encoding="utf-8"))


def _by_status(status):
    return {row["id"] for row in _source()[TOP_LEVEL_KEY]
            if row.get("b1_clinical_approval_status") == status}


def test_the_approved_and_pending_sets_come_from_the_source():
    assert _by_status("approved_for_controlled_beta") == APPROVED
    assert _by_status("pending_delta_review") == PENDING_REVIEW


def test_every_approved_record_names_its_approver_and_a_locked_fingerprint():
    ledger = json.loads((DATA / "medication_depletions_b1_signoff.json").read_text(encoding="utf-8"))
    rows = {row["id"]: row for row in _source()[TOP_LEVEL_KEY]}
    for record_id in APPROVED:
        assert rows[record_id]["b1_clinical_approver"] == "PharmaGuide Clinical Team"
        assert rows[record_id]["b1_clinical_approved_at"]
        assert ledger["active_record_fingerprints"][record_id].startswith("sha256:")
    for record_id in PENDING_REVIEW:
        assert rows[record_id].get("b1_clinical_approver") is None


@pytest.mark.parametrize("record_id", sorted(APPROVED))
def test_approved_copy_reaches_the_release_artifact_unchanged(record_id):
    source = _source()
    built = {row["id"]: row for row in build_artifact(source, content_version="a9")[TOP_LEVEL_KEY]}
    original = {row["id"]: row for row in source[TOP_LEVEL_KEY]}[record_id]
    for field in CONSUMER_VISIBLE_FIELD_NAMES:
        assert built[record_id].get(field) == original.get(field), field


@pytest.mark.parametrize("record_id", sorted(APPROVED | PENDING_REVIEW))
def test_bundled_app_copy_matches_the_source(record_id):
    if not ASSET.exists():
        pytest.skip("Flutter repo not co-located")
    asset = {row["id"]: row for row in json.loads(ASSET.read_text(encoding="utf-8"))[TOP_LEVEL_KEY]}
    original = {row["id"]: row for row in _source()[TOP_LEVEL_KEY]}[record_id]
    for field in CONSUMER_VISIBLE_FIELD_NAMES:
        assert asset[record_id].get(field) == original.get(field), field
    assert asset[record_id].get("b1_clinical_approval_status") == original["b1_clinical_approval_status"]
