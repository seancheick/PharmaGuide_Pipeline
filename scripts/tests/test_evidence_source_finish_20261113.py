"""Unread declared sources get one finished, no-credit decision each.

Seven records were held only because declared PMIDs had no source context.
None of the 13 papers has open full text, so each closes as a scoped
``rejected_source`` decision from its PubMed abstract: no credit, no Dose
transfer, no invented arms. Credit tiers belong to the Evidence ladder, not
here. Four records with a signed parent eligibility hold stay held.
"""
import json
from pathlib import Path

import pytest

from clinical_applicability import assess_clinical_source_review

DATA = Path(__file__).parents[1] / "data" / "backed_clinical_studies.json"

FINISHED = {
    "BRAND_SETRIA": ["24791752"],
    "BRAND_BIOCELL": ["22486722", "31221944"],
    "INGR_LION_MANE": ["18844328"],
    "INGR_INULIN": ["35833477"],
    "PRECLIN_ASTAXANTHIN_GENERIC": ["32755613", "35091276", "38243785"],
    "INGR_BLACK_SEED_OIL": ["21675032", "37341696", "40210172"],
    "INGR_SEA_BUCKTHORN": ["20554904", "36043374"],
}
HELD_BY_PARENT = ["BRAND_THERACURMIN", "PRECLIN_PQQ", "INGR_LACTOFERRIN", "INGR_COLLAGEN_PEPTIDES"]


@pytest.fixture(scope="module")
def records():
    payload = json.loads(DATA.read_text())
    rows = next(v for v in payload.values() if isinstance(v, list))
    return {row["id"]: row for row in rows}


@pytest.mark.parametrize("record_id", sorted(FINISHED))
def test_record_source_review_is_complete(records, record_id):
    result = assess_clinical_source_review(records[record_id])
    assert result["is_complete"], result["errors"]


@pytest.mark.parametrize("record_id,pmid", [(r, p) for r, ps in FINISHED.items() for p in ps])
def test_each_source_is_a_scoped_no_credit_decision(records, record_id, pmid):
    record = records[record_id]
    contexts = [c for c in record["study_contexts"] if c.get("source_pmids") == [pmid]]
    assert len(contexts) == 1
    context = contexts[0]
    assert context["review_status"] == "rejected_source"
    assert context["scoring_eligible"] is False
    reviewer = context["clinical_review"]["reviewer"]
    assert "agent review, not clinician review" in reviewer
    assert "Pham" not in reviewer
    assert context["dose"]["source_provenance"]["pmid"] == pmid
    assert context["dose"]["source_provenance"]["source_url"].endswith(f"/{pmid}/")
    assert context["limitations"]
    # Every record stays noncredit: no context becomes scoring-eligible.
    assert all(c.get("scoring_eligible") is False for c in record["study_contexts"])


@pytest.mark.parametrize("record_id", HELD_BY_PARENT)
def test_signed_parent_hold_still_wins(records, record_id):
    result = assess_clinical_source_review(records[record_id])
    assert not result["is_complete"]
    assert "clinical_context_eligible_source_missing" in result["errors"]


def test_black_seed_notes_no_longer_claim_consistent_evidence(records):
    notes = records["INGR_BLACK_SEED_OIL"]["notes"]
    assert "strong evidence" not in notes
    assert "consistent glycemic and blood pressure endpoints" not in notes
