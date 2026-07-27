"""B1.1 four-candidate evidence-revision and fail-closed release locks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


DATA = Path(__file__).resolve().parent.parent / "data"
SOURCE_PATH = DATA / "medication_depletions.json"
LEDGER_PATH = DATA / "medication_depletions_b1_1_signoff.json"

CANDIDATE_IDS = {
    "DEP_ANTACIDS_VITAMINB12",
    "DEP_ANTACIDS_MAGNESIUM",
    "DEP_DIURETICS_POTASSIUM",
    "DEP_DIURETICS_MAGNESIUM",
}

PROPOSAL_FIELDS = (
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
    "food_sources_short",
    "citation_review_status",
    "reviewed_at",
    "reviewer",
    "citation_review_note",
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _records() -> dict[str, dict]:
    source = _load(SOURCE_PATH)
    return {row["id"]: row for row in source["depletions"]}


def _fingerprint(record: dict) -> str:
    payload = json.dumps(
        {field: record.get(field) for field in PROPOSAL_FIELDS},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def test_b1_1_delta_is_exactly_four_candidates_and_remains_fail_closed():
    ledger = _load(LEDGER_PATH)
    records = _records()

    assert set(ledger["records"]) == CANDIDATE_IDS
    assert ledger["_metadata"]["candidate_count"] == 4
    assert ledger["_metadata"]["licensed_pharmacist_signoff"] is False
    assert (
        ledger["_metadata"]["release_disposition"]
        == "pending_licensed_pharmacist_delta_review"
    )
    for entry_id in CANDIDATE_IDS:
        assert records[entry_id]["citation_review_status"] == "needs_revision"
        assert (
            ledger["records"][entry_id]["disposition"]
            == "pending_licensed_pharmacist_review"
        )
        assert ledger["candidate_record_fingerprints"][entry_id] == _fingerprint(
            records[entry_id]
        )


def test_b1_1_candidates_use_narrow_runtime_scopes():
    records = _records()
    for entry_id in ("DEP_ANTACIDS_VITAMINB12", "DEP_ANTACIDS_MAGNESIUM"):
        assert records[entry_id]["drug_ref"] == {
            "type": "class",
            "id": "class:proton_pump_inhibitors",
            "display_name": "Proton pump inhibitors (PPIs)",
        }
    for entry_id in ("DEP_DIURETICS_POTASSIUM", "DEP_DIURETICS_MAGNESIUM"):
        assert records[entry_id]["drug_ref"] == {
            "type": "class",
            "id": "class:loop_and_thiazide_diuretics",
            "display_name": "Loop and thiazide diuretics (water pills)",
        }


def test_b1_1_candidates_remove_blanket_supplement_doses_and_coverage_thresholds():
    records = _records()
    banned = (
        "1,000 mcg/day",
        "1000 mcg/day",
        "200–400 mg/day",
        "200-400 mg/day",
        "20–40 meq/day",
        "20-40 meq/day",
        "supplement with",
        "supplement is often more reliable",
        "food sources may not be enough",
    )
    for entry_id in CANDIDATE_IDS:
        record = records[entry_id]
        consumer_copy = " ".join(
            str(record.get(field) or "")
            for field in (
                "recommendation",
                "alert_headline",
                "alert_body",
                "acknowledgement_note",
                "monitoring_tip_short",
                "food_sources_short",
            )
        ).lower()
        assert not any(phrase.lower() in consumer_copy for phrase in banned)
        assert "adequacy_threshold_mcg" not in record
        assert "adequacy_threshold_mg" not in record


def test_ppi_candidates_have_claim_matched_current_sources():
    records = _records()
    b12_urls = {source["url"] for source in records["DEP_ANTACIDS_VITAMINB12"]["sources"]}
    magnesium_urls = {
        source["url"] for source in records["DEP_ANTACIDS_MAGNESIUM"]["sources"]
    }

    assert {
        "https://pubmed.ncbi.nlm.nih.gov/24327038/",
        "https://pubmed.ncbi.nlm.nih.gov/37060552/",
        (
            "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?"
            "setid=b6761f84-53ac-4745-a8c8-1e5427d7e179"
        ),
    } <= b12_urls
    assert {
        "https://pubmed.ncbi.nlm.nih.gov/22762246/",
        (
            "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?"
            "setid=b6761f84-53ac-4745-a8c8-1e5427d7e179"
        ),
    } <= magnesium_urls
    assert not any("drug-safety-and-availability" in url for url in magnesium_urls)


def test_diuretic_candidates_use_loop_and_thiazide_label_evidence():
    records = _records()
    required = {
        (
            "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?"
            "setid=f3173c0d-2b62-7c7b-e053-2995a90ada05"
        ),
        (
            "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?"
            "setid=8a1de4e2-3aca-a4d3-e053-2995a90a1a41"
        ),
    }
    for entry_id in ("DEP_DIURETICS_POTASSIUM", "DEP_DIURETICS_MAGNESIUM"):
        urls = {source["url"] for source in records[entry_id]["sources"]}
        assert required <= urls

    magnesium_urls = {
        source["url"] for source in records["DEP_DIURETICS_MAGNESIUM"]["sources"]
    }
    assert "https://pubmed.ncbi.nlm.nih.gov/10997911/" in magnesium_urls
    assert "https://pubmed.ncbi.nlm.nih.gov/9083264/" not in magnesium_urls


def test_b1_1_copy_preserves_uncertainty_and_variable_timing():
    records = _records()
    b12 = records["DEP_ANTACIDS_VITAMINB12"]
    ppi_magnesium = records["DEP_ANTACIDS_MAGNESIUM"]
    potassium = records["DEP_DIURETICS_POTASSIUM"]
    diuretic_magnesium = records["DEP_DIURETICS_MAGNESIUM"]

    assert b12["severity"] == "moderate"
    assert b12["evidence_level"] == "probable"
    assert "not everyone" in b12["alert_body"].lower()
    assert "heterogeneous" in b12["clinical_impact"].lower()

    assert ppi_magnesium["evidence_level"] == "established"
    assert "rare" in ppi_magnesium["alert_body"].lower()
    assert "precise molecular mechanism is not established" in ppi_magnesium[
        "mechanism"
    ].lower()

    assert potassium["onset_timeline"] == "variable"
    assert diuretic_magnesium["onset_timeline"] == "variable"
    assert "do not start potassium" in potassium["recommendation"].lower()
    assert "do not start a routine magnesium dose" in diuretic_magnesium[
        "recommendation"
    ].lower()


def test_b1_1_candidate_notes_require_a_new_pharmacist_delta_review():
    for entry_id, record in _records().items():
        if entry_id not in CANDIDATE_IDS:
            continue
        assert record["reviewed_at"] == "2026-07-27"
        assert record["reviewer"] == "b1_1_evidence_audit"
        note = record["citation_review_note"].lower()
        assert "licensed pharmacist" in note
        assert "suppressed" in note
