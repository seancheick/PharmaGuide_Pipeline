#!/usr/bin/env python3
"""Tests for clinical PubMed normalization helpers."""

import os
import sys


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_extract_pmids_from_free_text_notable_studies():
    from api_audit.normalize_clinical_pubmed import extract_pmids_from_text

    text = (
        "Belcaro et al. (2010, PMID 21194249) reported improved WOMAC scores. "
        "Later placebo-controlled data also exist in PMID 38809154. "
        "AstaReal materials cite later branded skin RCTs including PubMed 31221944."
    )

    assert extract_pmids_from_text(text) == ["21194249", "38809154", "31221944"]


def test_extract_pmids_from_plural_pmid_block():
    from api_audit.normalize_clinical_pubmed import extract_pmids_from_text

    text = "Recent meta-analyses support the claim (PMIDs: 39519498, 39074168; 33554654)."

    assert extract_pmids_from_text(text) == ["39519498", "39074168", "33554654"]


def test_extract_pmids_does_not_swallow_clinicaltrials_identifiers():
    from api_audit.normalize_clinical_pubmed import extract_pmids_from_text

    text = (
        "A pilot in healthy older adults (PMID 39269340) was uncontrolled. "
        "Ongoing studies include NCT03675724 and NCT04476953."
    )

    assert extract_pmids_from_text(text) == ["39269340"]


def test_extract_ecitmatch_candidates_from_structured_citation_text():
    from api_audit.normalize_clinical_pubmed import extract_ecitmatch_candidates

    text = "Mann, BJ. (1991) Proc Natl Acad Sci U S A. 88:3248."

    assert extract_ecitmatch_candidates(text) == [
        {
            "journal_title": "proc natl acad sci u s a",
            "year": "1991",
            "volume": "88",
            "first_page": "3248",
            "author_name": "mann bj",
        }
    ]


def test_extract_reference_identifiers_finds_doi_and_pmid():
    from api_audit.verify_pubmed_references import extract_reference_identifiers

    text = (
        "Nature Medicine 2023; DOI: 10.1038/s41591-023-02223-9. "
        "PubMed PMID 36849732."
    )

    identifiers = extract_reference_identifiers(text)

    assert identifiers["pmids"] == ["36849732"]
    assert identifiers["dois"] == ["10.1038/s41591-023-02223-9"]


def test_collect_entry_reference_identifiers_skips_redundant_doi_resolution_for_structured_pubmed_refs():
    from api_audit.verify_pubmed_references import collect_entry_reference_identifiers

    identifiers = collect_entry_reference_identifiers(
        {
            "references_structured": [
                {
                    "type": "pubmed",
                    "pmid": "36849732",
                    "doi": "10.1038/s41591-023-02223-9",
                }
            ],
            "notable_studies": "Pilot discussion only.",
        }
    )

    assert identifiers["pmids"] == ["36849732"]
    assert identifiers["dois"] == []


def test_fetch_pubmed_suggestions_returns_parsed_candidates():
    from api_audit.normalize_clinical_pubmed import fetch_pubmed_suggestions

    class FakeClient:
        def esearch(self, query, retmax=3):
            assert "quercetin" in query.lower()
            return {"esearchresult": {"idlist": ["12345"]}}

        def efetch(self, ids):
            assert ids == ["12345"]
            return """<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>12345</PMID><Article><ArticleTitle>Quercetin meta-analysis</ArticleTitle><Journal><Title>Example Journal</Title><JournalIssue><PubDate><Year>2024</Year></PubDate></JournalIssue></Journal><PublicationTypeList><PublicationType>Meta-Analysis</PublicationType></PublicationTypeList></Article></MedlineCitation><PubmedData><ArticleIdList><ArticleId IdType='pubmed'>12345</ArticleId></ArticleIdList></PubmedData></PubmedArticle></PubmedArticleSet>"""

    suggestions = fetch_pubmed_suggestions(FakeClient(), "quercetin meta-analysis")

    assert suggestions == [
        {
            "pmid": "12345",
            "title": "Quercetin meta-analysis",
            "published_date": "2024-01-01",
            "publication_types": ["Meta-Analysis"],
            "retracted": False,
        }
    ]


def test_fetch_articles_for_pmids_batches_large_requests():
    from api_audit.normalize_clinical_pubmed import fetch_articles_for_pmids

    class FakeClient:
        def __init__(self):
            self.calls = []

        def efetch(self, ids):
            self.calls.append(ids)
            return """<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>12345</PMID><Article><ArticleTitle>Example</ArticleTitle><Journal><Title>Example Journal</Title><JournalIssue><PubDate><Year>2024</Year></PubDate></JournalIssue></Journal></Article></MedlineCitation><PubmedData><ArticleIdList><ArticleId IdType='pubmed'>12345</ArticleId></ArticleIdList></PubmedData></PubmedArticle></PubmedArticleSet>"""

    client = FakeClient()
    fetch_articles_for_pmids(client, ["1", "2", "3"], batch_size=2)

    assert client.calls == [["1", "2"], ["3"]]


def test_audit_reference_file_does_not_lookup_doi_when_structured_pubmed_ref_has_pmid(tmp_path):
    from api_audit.verify_pubmed_references import audit_reference_file

    file_path = tmp_path / "clinical.json"
    file_path.write_text(
        """{
  "backed_clinical_studies": [
    {
      "id": "ENTRY_1",
      "references_structured": [
        {
          "type": "pubmed",
          "pmid": "12345",
          "doi": "10.1000/example"
        }
      ]
    }
  ]
}"""
    )

    class FakeClient:
        def esearch(self, *_args, **_kwargs):
            raise AssertionError("DOI lookup should not be called for structured PubMed refs that already have PMIDs")

        def efetch(self, ids):
            assert ids == ["12345"]
            return """<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>12345</PMID><Article><ArticleTitle>Example</ArticleTitle><Journal><Title>Example Journal</Title><JournalIssue><PubDate><Year>2024</Year></PubDate></JournalIssue></Journal></Article></MedlineCitation><PubmedData><ArticleIdList><ArticleId IdType='pubmed'>12345</ArticleId><ArticleId IdType='doi'>10.1000/example</ArticleId></ArticleIdList></PubmedData></PubmedArticle></PubmedArticleSet>"""

    report = audit_reference_file(file_path, "backed_clinical_studies", FakeClient())

    assert report["summary"]["broken_dois"] == 0
    assert report["summary"]["broken_pmids"] == 0


def test_normalize_clinical_file_preserves_existing_non_pubmed_references(tmp_path):
    from api_audit.normalize_clinical_pubmed import normalize_clinical_file

    file_path = tmp_path / "clinical.json"
    file_path.write_text(
        """{
  "backed_clinical_studies": [
    {
      "id": "ODS_ONLY",
      "standard_name": "Copper",
      "evidence_level": "ingredient-human",
      "notable_studies": "NIH ODS Copper fact sheet supports essentiality and deficiency correction.",
      "references_structured": [
        {
          "type": "nih_ods",
          "authority": "NIH ODS",
          "title": "Copper Fact Sheet for Health Professionals",
          "citation": "NIH ODS",
          "url": "https://ods.od.nih.gov/factsheets/Copper-HealthProfessional/"
        }
      ]
    }
  ]
}"""
    )

    class NoopClient:
        def efetch(self, ids):
            raise AssertionError("efetch should not be called for existing non-PubMed refs")

    report = normalize_clinical_file(file_path, NoopClient(), apply=False)

    assert report["summary"]["unresolved_entries"] == 0


def test_recommended_evidence_level_prefers_systematic_review_over_rct():
    from api_audit.audit_clinical_evidence_strength import recommend_evidence_level

    recommendation = recommend_evidence_level(
        publication_types=["Journal Article", "Randomized Controlled Trial", "Systematic Review"],
        retracted=False,
        reference_count=1,
    )

    assert recommendation["recommended_evidence_level"] == "systematic-review-meta"
    assert recommendation["recommended_study_type"] == "systematic_review_meta"


def test_recommended_evidence_level_treats_clinical_trial_as_interventional_support():
    from api_audit.audit_clinical_evidence_strength import recommend_evidence_level

    recommendation = recommend_evidence_level(
        publication_types=["Clinical Trial", "Journal Article"],
        retracted=False,
        reference_count=1,
    )

    assert recommendation["recommended_evidence_level"] == "rct"
    assert recommendation["recommended_study_type"] == "rct_single"


def test_recommended_evidence_level_flags_retracted_references_as_blockers():
    from api_audit.audit_clinical_evidence_strength import recommend_evidence_level

    recommendation = recommend_evidence_level(
        publication_types=["Meta-Analysis", "Retracted Publication"],
        retracted=True,
        reference_count=1,
    )

    assert recommendation["recommended_evidence_level"] == "retracted"
    assert recommendation["recommended_study_type"] == "retracted"


def test_audit_entries_flags_downgrade_and_missing_structured_support():
    from api_audit.audit_clinical_evidence_strength import audit_entries

    report = audit_entries(
        [
            {
                "id": "RISKY_CITRULLINE",
                "study_type": "rct_multiple",
                "evidence_level": "ingredient-human",
                "references_structured": [
                    {
                        "pmid": "1",
                        "publication_types": ["Journal Article", "Observational Study"],
                        "retracted": False,
                    }
                ],
            },
            {
                "id": "SUPPORTED_MULTI_RCT",
                "study_type": "rct_multiple",
                "evidence_level": "ingredient-human",
                "references_structured": [
                    {
                        "pmid": "2",
                        "publication_types": ["Journal Article", "Randomized Controlled Trial"],
                        "title": "Randomized placebo-controlled trial of example ingredient",
                        "retracted": False,
                    },
                    {
                        "pmid": "3",
                        "publication_types": ["Journal Article", "Randomized Controlled Trial"],
                        "title": "Double-blind randomized trial of example ingredient",
                        "retracted": False,
                    },
                ],
            },
            {
                "id": "HEURISTIC_META",
                "study_type": "systematic_review_meta",
                "evidence_level": "ingredient-human",
                "references_structured": [
                    {
                        "pmid": "4",
                        "publication_types": ["Journal Article"],
                        "title": "Effect of quercetin on blood pressure: a systematic review and meta-analysis",
                        "retracted": False,
                    }
                ],
            },
            {
                "id": "MISSING_SUPPORT",
                "study_type": "systematic_review_meta",
                "evidence_level": "ingredient-human",
                "references_structured": [],
            },
        ]
    )

    mismatch_ids = {item["id"] for item in report["mismatches"]}
    issue_ids = {item["id"] for item in report["issues"]}

    assert "RISKY_CITRULLINE" in mismatch_ids
    assert "MISSING_SUPPORT" in issue_ids
    assert "SUPPORTED_MULTI_RCT" not in mismatch_ids
    assert "HEURISTIC_META" not in mismatch_ids


def test_audit_entries_skips_non_pubmed_structured_refs():
    from api_audit.audit_clinical_evidence_strength import audit_entries

    report = audit_entries(
        [
            {
                "id": "ODS_COPPER",
                "study_type": "observational",
                "evidence_level": "ingredient-human",
                "references_structured": [
                    {
                        "type": "nih_ods",
                        "authority": "NIH ODS",
                        "title": "Copper Fact Sheet for Health Professionals",
                    }
                ],
            }
        ]
    )

    assert report["mismatches"] == []
    assert report["issues"] == []
