"""First Evidence review batch: reviews stay source-bound, earn no credit and close only what the owners allow."""
import importlib.util
import json
import logging
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "audits" / "evidence_review_batch1_20261102"
DATA = ROOT / "data" / "literature_evidence_records.json"


@pytest.fixture(scope="module")
def records():
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    return {r["canonical_id"]: r for r in payload["literature_evidence_records"]}


@pytest.fixture(scope="module")
def spec():
    loaded = importlib.util.spec_from_file_location("evidence_review_spec", AUDIT / "spec.py")
    module = importlib.util.module_from_spec(loaded)
    loaded.loader.exec_module(module)
    return module.RECORDS


@pytest.fixture(scope="module")
def receipts():
    return json.loads((AUDIT / "receipts.json").read_text(encoding="utf-8"))


def _resolve_label_row(cid, name):
    from evidence_resolver import resolve_evidence_for_row
    logging.disable(logging.WARNING)
    row = {"canonical_id": cid, "name": name, "raw_source_text": name, "source_label_name": name,
           "raw_source_path": "activeIngredients[0]", "source_section": "activeIngredients"}
    return resolve_evidence_for_row(row, {"activeIngredients": [row], "ingredients_scorable": [row]})


def test_reviewed_null_closes_the_question_without_credit():
    resolution = _resolve_label_row("methionine", "L-Methionine")
    assert resolution.disposition == "reviewed_null_unfavorable"
    assert resolution.reason_code == "literature_reviewed_null_or_unfavorable"
    assert resolution.points_eligible is False
    assert not resolution.blocking_reasons


@pytest.mark.parametrize("cid, name, reason", [
    ("turmeric", "Turmeric Root Extract", "literature_applicability_unestablished"),
    ("turmeric", "Turmeric Root Powder", "literature_applicability_unestablished"),
    ("turmeric", "Turmeric", "literature_applicability_unestablished"),
    ("ginkgo", "Ginkgo Flavone Glycosides", "invalid_applicability_contract"),
    ("fiber", "Glucomannan", "invalid_applicability_contract"),
    ("collagen", "Hydrolyzed Collagen", "clinical_sources_ineligible"),
])
def test_review_without_a_signed_scope_stays_open(cid, name, reason):
    """An agent review cannot sign a preparation scope, so these rows do not close yet."""
    resolution = _resolve_label_row(cid, name)
    assert resolution.disposition == "research_present_applicability_unestablished"
    assert resolution.reason_code == reason
    assert resolution.points_eligible is False
    assert resolution.blocking_reasons


@pytest.mark.parametrize("cid, name, reason", [
    ("ginkgo", "Ginkgo Biloba Powder", "clinical_form_excluded"),
    ("ginkgo", "Ginkgo Biloba Leaf Extract", "clinical_form_mismatch"),
    ("fiber", "Fiber", "clinical_form_mismatch"),
    ("fiber", "Total Dietary Fiber", "clinical_form_mismatch"),
    ("fiber", "Fiber, Soluble", "clinical_form_mismatch"),
    ("collagen", "Collagen", "clinical_form_mismatch"),
    ("collagen", "Gelatin", "clinical_form_mismatch"),
    ("collagen", "Undenatured Type II Collagen", "clinical_form_excluded"),
    ("collagen", "Biocell Collagen Hydrolyzed Collagen Complex", "clinical_form_excluded"),
])
def test_scope_exclusion_is_a_reviewed_conclusion_without_credit(cid, name, reason):
    resolution = _resolve_label_row(cid, name)
    assert resolution.disposition == "research_present_applicability_unestablished"
    assert resolution.reason_code == reason
    assert resolution.points_eligible is False
    assert resolution.blocking_reasons == ["literature_applicability_unestablished"]


@pytest.mark.parametrize("cid, name, reason", [
    ("l_carnitine", "L-Carnitine", "clinical_sources_ineligible"),
    ("elderberry", "Elderberry", "clinical_sources_ineligible"),
    ("tmg_betaine", "Betaine Anhydrous", "clinical_sources_ineligible"),
    ("phytosterols", "Plant Sterols", "clinical_sources_ineligible"),
    ("taurine", "Taurine", "clinical_source_contexts_missing"),
    ("grape_seed_extract", "Grape Seed Extract", "clinical_sources_ineligible"),
])
def test_records_waiting_on_clinician_stay_held(cid, name, reason):
    from evidence_resolver import resolve_evidence_for_canonical
    logging.disable(logging.WARNING)
    resolution = resolve_evidence_for_canonical(cid, name=name)
    assert resolution.reason_code == reason
    assert resolution.points_eligible is False
    assert resolution.blocking_reasons


@pytest.mark.parametrize("cid, pmid", [("ginkgo", "19017911"), ("collagen", "31919527")])
def test_paper_with_an_unread_correction_stays_retired(records, cid, pmid):
    assert pmid not in {study["pmid"] for study in records[cid]["qualifying_human_studies"]}
    assert pmid not in records[cid]["applicability_decision"]
    assert pmid in records[cid]["notes"] and "retired from qualifying_human_studies" in records[cid]["notes"]


def test_no_review_claims_clinician_approval_or_credit(records, spec):
    for cid in spec:
        text = json.dumps(records[cid]).lower()
        assert "clinician_approved" not in text and "dr. pham" not in text, cid
        assert "scoring_eligible" not in text, cid
        provenance = records[cid]["verification_provenance"]
        assert "scripts/api_audit" not in provenance["verified_by"], cid
        assert "no clinician approval" in provenance["verified_by"], cid
        assert "no evidence credit" in records[cid]["applicability_decision"].lower(), cid


def test_every_study_is_the_read_paper_and_says_what_was_read(records, spec, receipts):
    for cid, entry in spec.items():
        stored = {s["pmid"]: s for s in records[cid]["qualifying_human_studies"]}
        assert set(stored) == {s["pmid"] for s in entry["studies"]}, cid
        for study in entry["studies"]:
            receipt = receipts["articles"][study["pmid"]]
            saved = stored[study["pmid"]]
            assert saved["title"] == receipt["title"]
            assert saved["verification_provenance"]["authoritative_live_title"] == receipt["title"]
            assert saved["verification_provenance"]["abstract_evidence_quote"] == study["quote"]
            assert study["quote"] in receipt["quotes"], study["pmid"]
            assert receipt["human_mesh"] is True and receipt["retracted"] is False
            assert len(study["quote"].split()) < 15


def test_search_counts_match_the_retained_searches(records, spec, receipts):
    for cid in spec:
        assert records[cid]["records_screened"] == receipts["searches"][cid]["records_screened"]
        assert records[cid]["search_query"] == receipts["searches"][cid]["search_query"]


def test_turmeric_keeps_its_dose_reference(records):
    semantics = records["turmeric"]["reference_semantics"]
    assert semantics["curve"] == "completed_no_benchmark_neutral"
    assert semantics["source_ids"] == ["PMID:38576215", "PMID:38945354", "PMID:40615851"]
    assert records["turmeric"]["verification_provenance"]["reference_citations"]["is_complete"] is True
