"""Unread declared sources get one finished, no-credit decision each.

Seven records were held only because declared PMIDs had no source context.
No PMC full-text copy was found for the 13 papers; each closes as a scoped
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


def test_source_access_claims_do_not_equate_pmc_absence_with_paywall(records):
    for record_id, pmids in FINISHED.items():
        for context in records[record_id]["study_contexts"]:
            if context.get("source_pmids") in [[pmid] for pmid in pmids]:
                assert not any("Full text is not open access (no PMC copy)" in value for value in context["limitations"])
                assert any("No PMC full-text copy was found" in value for value in context["limitations"])


def test_inulin_finished_source_does_not_retain_unqualified_no_completion_note(records):
    assert "No source completion," not in records["INGR_INULIN"]["notes"]


def test_finished_sources_do_not_retain_obsolete_prerequisites(records):
    inulin = records["INGR_INULIN"]
    lion = records["INGR_LION_MANE"]
    assert "full Methods/source review remains on hold" not in json.dumps(inulin)
    assert "principal source (18844328) is unverified" not in json.dumps(lion)
    assert "More recent review literature includes PMID 38140277" not in lion["notable_studies"]
    assert "acute randomized crossover trials" in lion["notable_studies"]


def test_psyllium_retains_scoped_fda_regularity_reference_without_borrowing_lipid_pmid(records):
    record = records["INGR_PSYLLIUM_HUSK"]
    references = [r for r in record["references_structured"] if "Monograph M007" in r.get("title", "")]
    assert len(references) == 1
    reference = references[0]
    assert reference["url"].startswith("https://www.accessdata.fda.gov/")
    assert reference["scoring_eligible"] is False
    assert not reference.get("pmid")
    assert "granular" in reference["notes"]
    assert any(c["context_id"] == "ingr_psyllium_30239559_lipid_marker_review" for c in record["study_contexts"])
