"""INGR_CREATINE_ETHYL_ESTER provenance and finding wording (Sean, 2026-11-12).

Authority: scripts/audits/clinical_review_20261111/DR_PHAM_ANSWERS_20261112.md, Part B
section 5. Sean: "Fix it, it was dr pham". The context review recorded as agent review was
Dr. Pham's; the Codex agents prepared the source reading. PMID 19228401 (content-checked on
PubMed, 2026-11-12) measured body composition, muscle mass, strength and power and found no
between-group difference; the credited finding is muscle total-creatine content.
"""
from clinical_applicability import reviewed_entries


def _record():
    return reviewed_entries()["INGR_CREATINE_ETHYL_ESTER"]


def test_cee_context_review_is_attributed_to_dr_pham_with_seans_statement():
    context = _record()["study_contexts"][0]
    assert context["review_status"] == "clinician_approved"
    review = context["clinical_review"]
    assert review["reviewer"] == "Dr. Pham"
    assert "not clinician review" not in review["reviewer"]
    # The correction cites its authority and keeps the agents' work as preparation.
    assert "DR_PHAM_ANSWERS_20261112.md" in review["notes"]
    assert "Fix it, it was dr pham" in review["notes"]
    assert "prepared by Codex" in review["notes"]


def test_cee_text_says_strength_power_and_body_composition_were_measured():
    record = _record()
    endpoints = " ".join(record["key_endpoints"]).lower()
    for outcome in ("strength", "power", "body composition"):
        assert outcome in endpoints
    assert "measured" in endpoints and "no between-group benefit" in endpoints
    # The credited finding stays the muscle creatine content contrast.
    assert "muscle total-creatine content" in endpoints
