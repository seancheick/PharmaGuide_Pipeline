"""Contract tests for the SP-6 evidence-strength derivation
(verify_interactions.derive_evidence_level). Locks the rubric, the SP-0
provenance gate, the fail-safe (never NULL / never off-vocab), and the
vocab-alignment self-check.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api_audit"))

from verify_interactions import (  # noqa: E402
    EVIDENCE_STRENGTH_ORDER,
    derive_evidence_level,
)
from review_evidence_derivation import serious_below_probable_flags  # noqa: E402
from review_evidence_derivation import merged_source_pmids  # noqa: E402


def test_strong_designs_with_provenance_are_established():
    assert derive_evidence_level("rct", "high", ["12345"]) == "established"
    assert derive_evidence_level("systematic_review", "medium", ["1"]) == "established"


def test_regulatory_basis_is_self_authoritative_without_pmid():
    # Regulatory backing needs no PMID to hold established.
    assert derive_evidence_level("label_regulatory", "high", []) == "established"


def test_clinical_literature_without_pmid_capped_at_moderate():
    # SP-0 provenance gate: an unverifiable clinical claim cannot be 'probable'.
    assert derive_evidence_level("clinical_literature", "high", []) == "moderate"


def test_clinical_literature_with_pmid_is_probable():
    assert derive_evidence_level("clinical_literature", "medium", ["999"]) == "probable"


def test_review_uses_pubmed_urls_as_evidence_provenance():
    pmids = merged_source_pmids(
        {
            "source_urls": [
                "https://pubmed.ncbi.nlm.nih.gov/21191575/",
                "https://www.ncbi.nlm.nih.gov/books/NBK470313/",
            ],
            "source_pmids": [],
        }
    )

    assert pmids == ["21191575"]
    assert derive_evidence_level("clinical_literature", "medium", pmids) == "probable"


def test_authoritative_review_is_probable_without_pmid():
    assert derive_evidence_level("authoritative_review", "medium", []) == "probable"


def test_low_confidence_steps_down_one_tier():
    # rct base=established, low -> probable (with PMID it is not re-capped).
    assert derive_evidence_level("rct", "low", ["1"]) == "probable"


def test_mechanism_only_is_theoretical():
    assert derive_evidence_level("mechanism_inferred", "high", ["1"]) == "theoretical"
    assert derive_evidence_level("preclinical", "high", ["1"]) == "theoretical"


def test_unknown_or_absent_basis_is_no_data_never_null():
    assert derive_evidence_level(None, "high", ["1"]) == "no_data"
    assert derive_evidence_level("", "high", ["1"]) == "no_data"
    assert derive_evidence_level("marketing_blurb", "high", []) == "no_data"


def test_never_returns_null_or_off_vocab():
    bases = [
        "rct",
        "systematic_review",
        "label_regulatory",
        "authoritative_review",
        "clinical_reference",
        "clinical_literature",
        "review",
        "observational",
        "mechanism_inferred",
        "preclinical",
        None,
        "",
        "unknown",
    ]
    confs = ["high", "medium", "moderate", "low", None, ""]
    for basis in bases:
        for conf in confs:
            for pmids in ([], ["1"]):
                value = derive_evidence_level(basis, conf, pmids)
                assert value in EVIDENCE_STRENGTH_ORDER
                assert value  # never empty / None


def test_review_flags_include_major_rows_below_probable():
    flags = serious_below_probable_flags(
        [
            {
                "id": "MAJOR_MODERATE",
                "severity": "Major",
                "proposed": "moderate",
            },
            {
                "id": "MAJOR_PROBABLE",
                "severity": "Major",
                "proposed": "probable",
            },
            {
                "id": "MODERATE_THEORETICAL",
                "severity": "Moderate",
                "proposed": "theoretical",
            },
            {
                "id": "CONTRAINDICATED_THEORETICAL",
                "severity": "Contraindicated",
                "proposed": "theoretical",
            },
        ]
    )

    assert [r["id"] for r in flags] == [
        "MAJOR_MODERATE",
        "CONTRAINDICATED_THEORETICAL",
    ]
