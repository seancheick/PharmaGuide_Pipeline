"""Offline regression tests for the reviewed medication-depletion content gate."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api_audit"))
import verify_depletion_timing_citation_content as gate  # noqa: E402


def _expectation(*, disposition="verified_for_claim", **expected):
    return {
        "entry_id": "DEP_TEST",
        "pmid": "111",
        "expected": {
            "drug_terms_any": ["valproic acid", "valproate"],
            "nutrient_terms_any": ["L-carnitine", "carnitine"],
            **expected,
        },
        "reviewer_disposition": disposition,
    }


def _article(title: str, abstract: str):
    return {"title": title, "abstract": abstract, "mesh_terms": []}


def test_normalization_handles_hyphens_case_and_punctuation():
    result = gate.classify_article(
        _article("VALPROATE and L‑CARNITINE", "Long-term valproic-acid treatment reduced carnitine."),
        _expectation(),
    )
    assert result["status"] == "content_match"


def test_known_antiseizure_vitamin_k_ghost_is_a_content_mismatch():
    # PMID 14506311 is real but concerns calcium-channel antagonists and nicotine
    # place preference, not enzyme-inducing antiseizure medications/vitamin K.
    result = gate.classify_article(
        _article(
            "Calcium channel antagonists and nicotine place preference in rats",
            "Nicotine reward was studied in rodents treated with calcium channel antagonists.",
        ),
        {
            **_expectation(),
            "expected": {
                "drug_terms_any": ["carbamazepine", "antiepileptic"],
                "nutrient_terms_any": ["vitamin K"],
            },
        },
    )
    assert result["status"] == "content_mismatch"


def test_known_soil_coq10_ghost_is_a_content_mismatch():
    # PMID 18316143 is microbial hexadecane degradation in soil, not an
    # antipsychotic/CoQ10 clinical depletion study.
    result = gate.classify_article(
        _article(
            "Microbial degradation of 14C-hexadecane in soil",
            "Soil microcosms were used to measure microbial hydrocarbon degradation.",
        ),
        {
            **_expectation(),
            "expected": {
                "drug_terms_any": ["antipsychotic", "olanzapine"],
                "nutrient_terms_any": ["coenzyme Q10", "CoQ10"],
            },
        },
    )
    assert result["status"] == "content_mismatch"


def test_no_abstract_is_not_a_title_only_pass():
    result = gate.classify_article(
        _article("Valproic acid and carnitine", ""), _expectation()
    )
    assert result["status"] == "abstract_unavailable"


def test_no_abstract_requires_an_explicit_reviewed_exception_and_backstop():
    expectation = {
        **_expectation(),
        "no_abstract_evidence": {
            "rationale": "PubMed exposes no abstract; title and MeSH are exact.",
            "backstop_urls": ["https://dailymed.nlm.nih.gov/example"],
        },
    }
    article = {
        "title": "Valproic acid and carnitine",
        "abstract": "",
        "mesh_terms": ["Valproic Acid", "Carnitine"],
    }

    assert gate.classify_article(article, expectation) == {
        "status": "content_match",
        "reason": "all reviewed concepts matched using explicit no-abstract evidence",
    }

    expectation["no_abstract_evidence"]["backstop_urls"] = []
    errors = gate.validate_contract(
        [expectation],
        [{
            "id": "DEP_TEST",
            "citation_review_status": "verified",
            "sources": [{"url": "https://pubmed.ncbi.nlm.nih.gov/111/"}],
        }],
    )
    assert any("no_abstract_evidence.backstop_urls" in error for error in errors)


def test_outcome_source_can_support_a_claim_without_relabeling_it_as_a_nutrient_source():
    expectation = {
        "entry_id": "DEP_TEST",
        "pmid": "111",
        "expected": {
            "drug_terms_any": ["proton pump inhibitors", "PPI"],
            "outcome_terms_any": ["hip fracture"],
            "context_terms_any": ["observational studies", "meta-analysis"],
        },
        "reviewer_disposition": "verified_for_claim",
    }
    article = _article(
        "Proton pump inhibitors and risk of hip fracture",
        "This meta-analysis of observational studies found an association with hip fracture.",
    )

    assert gate.classify_article(article, expectation)["status"] == "content_match"
    assert gate.validate_contract(
        [expectation],
        [{
            "id": "DEP_TEST",
            "citation_review_status": "verified",
            "sources": [{"url": "https://pubmed.ncbi.nlm.nih.gov/111/"}],
        }],
    ) == []


def test_transient_fetch_failure_is_distinct_and_fail_closed():
    result = gate.audit_expectations(
        [_expectation()], lambda _pmid: (_ for _ in ()).throw(RuntimeError("429"))
    )
    assert result[0]["status"] == "transient_api_failure"
    assert gate.decide_exit([], result) == 2


def test_transient_fetch_does_not_reuse_the_previous_articles_title():
    expectations = [
        _expectation(),
        {**_expectation(), "pmid": "222"},
    ]

    def fetch(pmid):
        if pmid == "111":
            return _article("Valproate and carnitine", "Valproate can affect carnitine.")
        raise RuntimeError("429")

    results = gate.audit_expectations(expectations, fetch)

    assert results[0]["title"] == "Valproate and carnitine"
    assert results[1]["title"] == ""
    assert results[1]["status"] == "transient_api_failure"


def test_mismatch_and_abstract_unavailable_fail_the_gate():
    assert gate.decide_exit([], [{"status": "content_mismatch"}]) == 1
    assert gate.decide_exit([], [{"status": "abstract_unavailable"}]) == 1


def test_contract_requires_verified_entry_and_authored_source():
    entry = {
        "id": "DEP_TEST",
        "citation_review_status": "unverified",
        "sources": [{"url": "https://pubmed.ncbi.nlm.nih.gov/222/"}],
    }
    errors = gate.validate_contract([_expectation()], [entry])
    assert any("not citation_review_status=verified" in error for error in errors)
    assert any("not an authored source" in error for error in errors)


def test_candidate_contract_requires_suppressed_entry_until_pharmacist_review():
    entry = {
        "id": "DEP_TEST",
        "citation_review_status": "needs_revision",
        "sources": [{"url": "https://pubmed.ncbi.nlm.nih.gov/111/"}],
    }
    candidate = _expectation(disposition="candidate_for_pharmacist_review")

    assert gate.validate_contract([candidate], [entry]) == []

    entry["citation_review_status"] = "verified"
    errors = gate.validate_contract([candidate], [entry])
    assert any("not citation_review_status=needs_revision" in error for error in errors)


def test_reviewed_contract_covers_every_verified_pubmed_source():
    root = Path(__file__).resolve().parents[1]
    contract = json.loads((root / "data" / "medication_depletion_citation_expectations.json").read_text())
    entries = json.loads((root / "data" / "medication_depletions.json").read_text())["depletions"]
    errors = gate.validate_contract(
        contract["expectations"],
        entries,
        require_coverage=True,
    )
    assert errors == []


def test_b1_delta_contract_locks_study_design_and_context():
    root = Path(__file__).resolve().parents[1]
    contract = json.loads(
        (
            root / "data" / "medication_depletion_citation_expectations.json"
        ).read_text()
    )
    by_key = {
        (item["entry_id"], item["pmid"]): item
        for item in contract["expectations"]
    }

    campbell = by_key[("DEP_LEVOTHYROXINE_IRON", "1443969")]["expected"]
    assert "Uncontrolled clinical trial" in campbell["required_terms_all"]
    assert "14 patients" in campbell["context_terms_any"]

    calcium = by_key[("DEP_LEVOTHYROXINE_CALCIUM", "11716045")]["expected"]
    assert "seven volunteers without thyroid disease" in calcium[
        "context_terms_any"
    ]

    acid_suppression = by_key[("DEP_ANTACIDS_IRON", "27890768")]["expected"]
    assert "decreased after medication discontinuation" in acid_suppression[
        "context_terms_any"
    ]
